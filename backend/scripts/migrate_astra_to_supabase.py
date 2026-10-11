"""
Migrasi data Astra DB → Supabase (sekali jalan).

Penggunaan:
    # Dry run (hanya cetak jumlah + contoh, tidak menulis)
    python backend/scripts/migrate_astra_to_supabase.py --dry-run

    # Jalankan sungguhan
    python backend/scripts/migrate_astra_to_supabase.py

Prasyarat:
    1. Migrasi SQL sudah dijalankan:
       psql $DATABASE_URL -f supabase/migrations/001_schema.sql
    2. .env berisi ASTRA_DB_* DAN SUPABASE_DB_* (selama proses migrasi).
    3. pip install astrapy psycopg2-binary python-dotenv

Catatan keamanan:
    - Data alergi dan dietary passport tidak masuk ke log.
    - Script tidak menghapus data Astra — read-only terhadap sumber.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# tambahkan backend/ ke path supaya import `app.*` berfungsi
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── Koneksi Astra (sumber) ──────────────────────────────────────────────────
def _get_astra():
    try:
        from astrapy import DataAPIClient
    except ImportError:
        print("SKIP: astrapy tidak terinstall. Script ini dijalankan setelah migrasi selesai.")
        return None, None

    endpoint = os.getenv("ASTRA_DB_API_ENDPOINT", "").strip()
    token    = os.getenv("ASTRA_DB_APPLICATION_TOKEN", "").strip()
    if not endpoint or not token:
        print("ASTRA_DB_API_ENDPOINT / ASTRA_DB_APPLICATION_TOKEN tidak diisi — skip.")
        return None, None

    client = DataAPIClient(token)
    db     = client.get_database(endpoint)
    return client, db


# ── Koneksi Supabase (tujuan) ───────────────────────────────────────────────
def _get_supabase_conn():
    import psycopg2
    import psycopg2.extras

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    if not supabase_url:
        host     = os.getenv("SUPABASE_DB_API_ENDPOINT", "").strip().lstrip("https://").lstrip("http://").rstrip("/")
        password = os.getenv("SUPABASE_DB_APPLICATION_TOKEN", "").strip()
        db_name  = os.getenv("SUPABASE_DB_NAME", "postgres")
        user     = os.getenv("SUPABASE_DB_USER", "postgres")
        port     = int(os.getenv("SUPABASE_DB_PORT", "5432"))
        supabase_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    conn = psycopg2.connect(
        supabase_url,
        cursor_factory=psycopg2.extras.RealDictCursor,
        sslmode="require",
        connect_timeout=10,
    )
    conn.autocommit = False
    return conn


# ── Transformasi ─────────────────────────────────────────────────────────────
def _migrate_packages(astra_db: Any, conn: Any, *, dry_run: bool) -> int:
    col = astra_db.get_collection("catering_packages")
    rows = list(col.find({}, limit=500))
    print(f"  packages: {len(rows)} dokumen ditemukan di Astra")
    if dry_run:
        for r in rows[:2]:
            print(f"    contoh: {r.get('code')} — {r.get('name')}")
        return len(rows)
    with conn.cursor() as cur:
        for r in rows:
            code = str(r.get("code") or r.get("_id") or "")
            if not code:
                continue
            days_raw = r.get("days") or []
            if isinstance(days_raw, str):
                days_raw = [d.strip() for d in days_raw.split(",") if d.strip()]
            cur.execute(
                """
                INSERT INTO packages (code, name, days, description, price, active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                    name=EXCLUDED.name, days=EXCLUDED.days,
                    description=EXCLUDED.description, price=EXCLUDED.price,
                    active=EXCLUDED.active
                """,
                (
                    code,
                    str(r.get("name") or ""),
                    days_raw,
                    str(r.get("description") or ""),
                    r.get("price"),
                    bool(r.get("active", True)),
                ),
            )
    conn.commit()
    return len(rows)


def _migrate_allergens(astra_db: Any, conn: Any, *, dry_run: bool) -> int:
    col = astra_db.get_collection("allergen_definitions")
    rows = list(col.find({}, limit=500))
    print(f"  allergens: {len(rows)} dokumen ditemukan di Astra")
    if dry_run:
        for r in rows[:2]:
            print(f"    contoh: {r.get('code')} — {r.get('label')}")
        return len(rows)
    with conn.cursor() as cur:
        for r in rows:
            code = str(r.get("code") or r.get("_id") or "")
            # Bersihkan prefiks ganda
            while code.startswith("alg_alg_"):
                code = code[len("alg_"):]
            if not code:
                continue
            cur.execute(
                """
                INSERT INTO allergens (code, label, risiko, active, category)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                    label=EXCLUDED.label, risiko=EXCLUDED.risiko,
                    active=EXCLUDED.active, category=EXCLUDED.category
                """,
                (
                    code,
                    str(r.get("label") or ""),
                    str(r.get("risiko") or ""),
                    bool(r.get("active", True)),
                    str(r.get("category") or "allergy"),
                ),
            )
    conn.commit()
    return len(rows)


def _migrate_menus(astra_db: Any, conn: Any, *, dry_run: bool) -> int:
    import re
    col = astra_db.get_collection("catering_menus")
    rows = list(col.find({}, limit=1000))
    print(f"  menus: {len(rows)} dokumen ditemukan di Astra")

    def _menu_id(hari: str, nama: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", nama.lower()).strip("-")[:48]
        return f"menu_{hari.lower()}_{slug}" if slug else f"menu_{hari.lower()}"

    if dry_run:
        for r in rows[:2]:
            print(f"    contoh: {r.get('hari')} — {r.get('nama_menu')}")
        return len(rows)
    with conn.cursor() as cur:
        for r in rows:
            hari = str(r.get("hari") or "")
            nama = str(r.get("nama_menu") or "")
            if not hari or not nama:
                continue
            menu_id = str(r.get("_id") or _menu_id(hari, nama))
            alat_raw = r.get("alat_dapur_steril") or []
            if isinstance(alat_raw, str):
                alat_raw = [a.strip() for a in alat_raw.split(",") if a.strip()]
            pkg_raw = r.get("package_codes") or r.get("packages") or []
            if isinstance(pkg_raw, str):
                pkg_raw = [p.strip() for p in pkg_raw.split(",") if p.strip()]

            cur.execute(
                """
                INSERT INTO menus (menu_id, hari, nama_menu, deskripsi,
                    alat_dapur_steril, published, package_codes, option_index)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (menu_id) DO UPDATE SET
                    hari=EXCLUDED.hari, nama_menu=EXCLUDED.nama_menu,
                    deskripsi=EXCLUDED.deskripsi,
                    alat_dapur_steril=EXCLUDED.alat_dapur_steril,
                    published=EXCLUDED.published,
                    package_codes=EXCLUDED.package_codes,
                    option_index=EXCLUDED.option_index
                """,
                (
                    menu_id, hari, nama,
                    str(r.get("deskripsi") or ""),
                    alat_raw,
                    bool(r.get("published", True)),
                    pkg_raw,
                    int(r.get("option_index") or 0),
                ),
            )
            # Bahan detail
            cur.execute("DELETE FROM menu_ingredients WHERE menu_id = %s", (menu_id,))
            for i, bahan in enumerate(r.get("bahan_detail") or []):
                if not isinstance(bahan, dict):
                    continue
                pot = str(bahan.get("potensi_alergen") or "")
                cur.execute(
                    """
                    INSERT INTO menu_ingredients
                        (menu_id, nama, sumber, potensi_alergen, is_critical_allergen, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        menu_id,
                        str(bahan.get("nama") or ""),
                        str(bahan.get("sumber") or ""),
                        pot,
                        "⚠" in pot,
                        i,
                    ),
                )
    conn.commit()
    return len(rows)


def _migrate_customers(astra_db: Any, conn: Any, *, dry_run: bool) -> int:
    col = astra_db.get_collection("customers")
    rows = list(col.find({}, limit=2000))
    print(f"  customers: {len(rows)} dokumen ditemukan di Astra")
    if dry_run:
        for r in rows[:2]:
            print(f"    contoh: {r.get('username')} role={r.get('role')}")
        return len(rows)
    with conn.cursor() as cur:
        for r in rows:
            cid = str(r.get("customer_id") or r.get("_id") or "")
            uname = str(r.get("username") or "").strip().lower()
            if not cid or not uname:
                continue
            cur.execute(
                """
                INSERT INTO customers
                    (customer_id, username, display_name, phone, role, status,
                     password_hash, telegram_chat_id, telegram_verified,
                     telegram_username, telegram_link_code,
                     telegram_link_code_expires_at, telegram_linked_at,
                     created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (customer_id) DO UPDATE SET
                    username=EXCLUDED.username,
                    display_name=EXCLUDED.display_name,
                    phone=EXCLUDED.phone,
                    role=EXCLUDED.role,
                    status=EXCLUDED.status,
                    password_hash=EXCLUDED.password_hash,
                    telegram_chat_id=EXCLUDED.telegram_chat_id,
                    telegram_verified=EXCLUDED.telegram_verified,
                    telegram_username=EXCLUDED.telegram_username
                """,
                (
                    cid,
                    uname,
                    str(r.get("display_name") or r.get("nama") or uname),
                    str(r.get("phone") or ""),
                    str(r.get("role") or "customer"),
                    str(r.get("status") or "active"),
                    r.get("password_hash") or None,
                    r.get("telegram_chat_id"),
                    bool(r.get("telegram_verified", False)),
                    str(r.get("telegram_username") or ""),
                    r.get("telegram_link_code") or None,
                    r.get("telegram_link_code_expires_at") or None,
                    r.get("telegram_linked_at") or None,
                    r.get("created_at") or None,
                    r.get("updated_at") or None,
                ),
            )
            # Migrate passport
            passport = r.get("passport") or {}
            if passport:
                cur.execute(
                    """
                    INSERT INTO dietary_passports
                        (customer_id, allergies, intolerances, medical, preferences,
                         avoided_ingredients, avoided_times,
                         medical_notes, safety_notes, emergency_notes,
                         emergency_contact, legacy_dietary_profile, structured)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (customer_id) DO UPDATE SET
                        allergies=EXCLUDED.allergies,
                        intolerances=EXCLUDED.intolerances,
                        medical=EXCLUDED.medical,
                        preferences=EXCLUDED.preferences,
                        avoided_ingredients=EXCLUDED.avoided_ingredients,
                        avoided_times=EXCLUDED.avoided_times,
                        medical_notes=EXCLUDED.medical_notes,
                        safety_notes=EXCLUDED.safety_notes,
                        emergency_notes=EXCLUDED.emergency_notes,
                        emergency_contact=EXCLUDED.emergency_contact,
                        legacy_dietary_profile=EXCLUDED.legacy_dietary_profile,
                        structured=EXCLUDED.structured
                    """,
                    (
                        cid,
                        json.dumps(passport.get("allergies") or []),
                        json.dumps(passport.get("intolerances") or []),
                        json.dumps(passport.get("medical") or []),
                        json.dumps(passport.get("preferences") or []),
                        passport.get("avoided_ingredients") or [],
                        passport.get("avoided_times") or [],
                        str(passport.get("medical_notes") or ""),
                        str(passport.get("safety_notes") or ""),
                        str(passport.get("emergency_notes") or ""),
                        json.dumps(passport.get("emergency_contact") or {}),
                        str(passport.get("legacy_dietary_profile") or ""),
                        bool(passport.get("allergies") or passport.get("intolerances")),
                    ),
                )
    conn.commit()
    return len(rows)


def _migrate_orders(astra_db: Any, conn: Any, *, dry_run: bool) -> int:
    import re as _re
    col = astra_db.get_collection("kitchen_orders")
    rows = list(col.find({}, limit=5000))
    print(f"  orders: {len(rows)} dokumen ditemukan di Astra")
    if dry_run:
        for r in rows[:2]:
            print(f"    contoh: {r.get('order_id')} status={r.get('status')}")
        return len(rows)

    with conn.cursor() as cur:
        for r in rows:
            oid = str(r.get("order_id") or r.get("_id") or "")
            if not oid:
                continue
            # Cek apakah sudah ada
            cur.execute("SELECT 1 FROM orders WHERE order_id = %s", (oid,))
            if cur.fetchone():
                continue

            allergens_raw = r.get("selected_allergens") or []
            if isinstance(allergens_raw, str):
                allergens_raw = [a.strip() for a in allergens_raw.split(",") if a.strip()]
            avoided_raw = r.get("avoided_times") or []
            if isinstance(avoided_raw, str):
                avoided_raw = [a.strip() for a in avoided_raw.split(",") if a.strip()]

            pkg_code = str(r.get("package_code") or r.get("package_id") or "")
            # Pastikan package ada — bila tidak ada, jangan masukkan FK
            if pkg_code:
                cur.execute("SELECT 1 FROM packages WHERE code = %s", (pkg_code,))
                if not cur.fetchone():
                    pkg_code = ""

            cur.execute(
                """
                INSERT INTO orders (
                    order_id, customer_id, customer_name, chat_id,
                    package_code, subscription_type, selected_allergens,
                    dietary_profile, kitchen_notes, customer_note,
                    delivery_address, avoided_times, meal_count, status,
                    invoice_number, subtotal, discount, total, payment_status,
                    schema_version, created_at, updated_at
                ) VALUES (
                    %s,%s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s,%s,
                    %s,%s,%s,%s,%s, %s,%s,%s
                )
                """,
                (
                    oid,
                    r.get("customer_id"),
                    str(r.get("customer_name") or r.get("nama") or "—"),
                    r.get("chat_id"),
                    pkg_code,
                    str(r.get("subscription_type") or r.get("package") or ""),
                    allergens_raw,
                    str(r.get("dietary_profile") or "Tidak ada"),
                    str(r.get("kitchen_notes") or ""),
                    str(r.get("customer_note") or ""),
                    str(r.get("delivery_address") or ""),
                    avoided_raw,
                    int(r.get("meal_count") or 0),
                    str(r.get("status") or "PENDING").upper(),
                    str(r.get("invoice_number") or ""),
                    int(r.get("subtotal") or 0),
                    int(r.get("discount") or 0),
                    int(r.get("total") or 0),
                    str(r.get("payment_status") or "UNPAID").upper(),
                    "migrated",
                    r.get("created_at") or None,
                    r.get("updated_at") or None,
                ),
            )

            # order_items dari schedule_days + menu_selections
            sel_map: dict[str, Any] = {}
            for sel in (r.get("menu_selections") or []):
                if isinstance(sel, dict):
                    sel_map[str(sel.get("hari") or "")] = sel.get("menu_id")

            sched = r.get("schedule_days") or []
            if isinstance(sched, str):
                sched = [d.strip() for d in sched.split(",") if d.strip()]
            DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
            days_ordered = [d for d in DAYS if d in set(sched)]

            for i, hari in enumerate(days_ordered):
                mid = sel_map.get(hari)
                # Validasi menu_id ada di tabel menus
                if mid:
                    cur.execute("SELECT 1 FROM menus WHERE menu_id = %s", (mid,))
                    if not cur.fetchone():
                        mid = None
                cur.execute(
                    "INSERT INTO order_items (order_id, hari, menu_id, sort_order) VALUES (%s,%s,%s,%s)",
                    (oid, hari, mid, i),
                )

            # status_events
            for ev in (r.get("status_events") or []):
                if not isinstance(ev, dict):
                    continue
                cur.execute(
                    "INSERT INTO order_status_events (order_id, status, actor, note, created_at) VALUES (%s,%s,%s,%s,%s)",
                    (
                        oid,
                        str(ev.get("status") or ""),
                        str(ev.get("actor") or ""),
                        str(ev.get("note") or ""),
                        ev.get("at") or None,
                    ),
                )
    conn.commit()
    return len(rows)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Astra DB → Supabase")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Hanya cetak jumlah dokumen dan contoh tanpa menulis ke Supabase."
    )
    args = parser.parse_args()
    dry = args.dry_run

    print("=" * 60)
    print("DovaGenome — Migrasi Astra DB → Supabase")
    print(f"Mode: {'DRY RUN (tidak ada penulisan)' if dry else 'SUNGGUHAN'}")
    print("=" * 60)

    _, astra_db = _get_astra()
    if astra_db is None:
        print("Astra tidak tersedia — tidak ada yang bisa dimigrasikan.")
        return 1

    if dry:
        conn = None
    else:
        print("\nMenyambung ke Supabase...")
        try:
            conn = _get_supabase_conn()
        except Exception as exc:
            print(f"Gagal menyambung ke Supabase: {exc}")
            return 1
        print("  Supabase tersambung.\n")

    total = 0
    for label, fn in [
        ("packages",   _migrate_packages),
        ("allergens",  _migrate_allergens),
        ("menus",      _migrate_menus),
        ("customers",  _migrate_customers),
        ("orders",     _migrate_orders),
    ]:
        print(f"\nMigrasi {label}...")
        n = fn(astra_db, conn, dry_run=dry)
        total += n

    if conn and not dry:
        conn.close()

    print(f"\n{'DRY RUN selesai' if dry else 'Migrasi selesai'}. Total dokumen: {total}")
    if not dry:
        print("Verifikasi: GET /api/health harus menampilkan status=ok dengan jumlah baris.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
