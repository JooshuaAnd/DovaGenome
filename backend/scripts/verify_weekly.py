r"""
Verifikasi alur "Catering Mingguan" — satu opsi menu per hari layanan.

Menjalankan API FastAPI terhadap Astra DB live. Tidak mengubah data produksi kecuali
dengan flag eksplisit (`--write`). Defaultnya hanya GET + simulasi safety.

    .\.venv\Scripts\python.exe backend\scripts\verify_weekly.py
    .\.venv\Scripts\python.exe backend\scripts\verify_weekly.py --write

Yang diuji dengan `--write`:
  * admin menambah opsi menu KEDUA untuk satu hari — hal yang mustahil sebelum ini,
    karena `_id` selalu `menu_<hari>` sehingga opsi kedua menimpa yang pertama
  * `/catalog/menus/week` menampilkan dua opsi itu dan safety-nya tetap sejajar
  * pemfilteran paket menyembunyikan opsi, safety ikut menyusut — bukan bergeser
  * pesanan memilih menu berbeda per hari, dan yang tersimpan adalah pilihannya
  * KDS menampilkan menu yang DIPILIH, bukan opsi utama
  * order tanpa `selections` tetap memakai opsi utama (kompatibilitas pemanggil lama)

Semua dokumen uji dihapus di akhir, termasuk opsi menu yang dibuat skrip ini.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []

#: Hari untuk uji multi-opsi. Senin dipakai karena paket mana pun memuatnya.
TEST_DAY = "Senin"
#: Awalan `uji_` supaya tidak mungkin bentrok dengan dokumen asli, dan mudah
#: dikenali bila ada sisa data uji yang tertinggal.
TEST_MENU_PREFIX = "uji_opsi_"


def check(name: str, condition: bool, detail: str = "") -> bool:
    results.append((name, bool(condition), detail))
    print(f"[{PASS if condition else FAIL}] {name}" + (f" - {detail}" if detail else ""))
    return bool(condition)


def login(client, username: str, password: str) -> dict | None:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        print(f"[{FAIL}] login {username} -> {r.status_code} {r.json()}")
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def delete_menu(menu_id: str) -> None:
    """Hapus opsi menu uji. Tidak ada endpoint DELETE, jadi langsung ke koleksi."""
    from app.repositories import astra, catalog_repo

    try:
        astra.get_collection("catering_menus").delete_one({"_id": menu_id})
        catalog_repo.invalidate_cache()
        print(f"[{PASS}] Hapus catering_menus/{menu_id}")
    except Exception as exc:
        print(f"[{FAIL}] Hapus catering_menus/{menu_id} - {type(exc).__name__}: {exc}")


def purge_test_menus() -> int:
    """
    Buang sisa opsi menu uji dari run sebelumnya.

    `menu_doc_id` diturunkan dari hari + slug judul, jadi skrip yang crash di
    tengah akan meninggalkan dokumen uji dengan `_id` yang bisa ditebak. Run berikutnya
    lalu gagal di "sebelum tes: satu opsi" — bukan karena katalognya salah.
    Astra tidak mendukung `$regex`, jadi dokumennya dikumpulkan di Python lalu dihapus
    satu per satu. Jumlahnya kecil dan selalu milik skrip ini.
    """
    from app.repositories import astra, catalog_repo

    try:
        stale = [
            m.menu_id
            for m in catalog_repo.list_menus(include_unpublished=True)
            if m.menu_id.startswith(TEST_MENU_PREFIX) or "_uji-" in m.menu_id
        ]
        coll = astra.get_collection("catering_menus")
        for menu_id in stale:
            coll.delete_one({"_id": menu_id})
            print(f"[{PASS}] Hapus sisa catering_menus/{menu_id}")
        catalog_repo.invalidate_cache()
        return len(stale)
    except Exception as exc:
        print(f"[{FAIL}] Pembersihan sisa menu uji - {type(exc).__name__}: {exc}")
        return 0


def purge_orphan_orders() -> int:
    """
    Buang pesanan uji yang pelanggannya sudah dihapus.

    Koneksi Astra sesekali timeout (handshake 10 detik), dan skrip yang gagal di
    tengah tidak sempat menjalankan `cleanup`. Dokumen yatim seperti ini tidak akan
    pernah tampil di UI karena tidak ada pemiliknya, tapi tetap akan muncul di
    KDS/jadwal admin — jadi harus dibereskan.

    Hanya order TANPA `customer_id` yang dipertahankan: itu pesanan lama dari
    Telegram/seed yang memang tidak punya akun web.
    """
    from app.repositories import astra, customer_repo

    try:
        coll = astra.get_collection("kitchen_orders")
        stale = []
        for order in coll.find({}):
            cid = order.get("customer_id")
            if not cid:
                continue
            try:
                customer_repo.get_customer(cid)
            except Exception:
                stale.append(order["_id"])
        for doc_id in stale:
            coll.delete_one({"_id": doc_id})
            print(f"[{PASS}] Hapus order yatim/{doc_id}")
        return len(stale)
    except Exception as exc:
        print(f"[{FAIL}] Pembersihan order yatim - {type(exc).__name__}: {exc}")
        return 0


def alignment(week: dict) -> dict[str, tuple[int, int]]:
    """`hari -> (jumlah opsi, jumlah safety)` untuk memeriksa keselarasan."""
    return {
        d["hari"]: (len(d.get("options") or []), len(d.get("safety") or []))
        for d in week.get("days") or []
    }


# -- Bagian baca-saja --------------------------------------------------------
def verify_week_shape(client) -> dict:
    """`/catalog/menus/week` harus sudah berbentuk "hari -> banyak opsi"."""
    print("\n=== 1. Menu minggu ini (public, tanpa login) ===")
    r = client.get("/api/catalog/menus/week")
    check("GET /api/catalog/menus/week -> 200", r.status_code == 200, str(r.status_code))
    if r.status_code != 200:
        print(r.json())
        return {}

    week = r.json()
    days = week.get("days") or []
    check("Ada hari layanan", bool(days), str(len(days)))
    check("Tanggal minggu terisi", bool(week.get("week_start")), str(week.get("week_start")))

    dated = [d for d in days if d.get("service_date")]
    check("Setiap hari punya tanggal", len(dated) == len(days), f"{len(dated)}/{len(days)}")
    if dated:
        s = dated[0]
        check(
            "Tanggal + label terbaca",
            bool(s["date_label"]) and bool(s["service_date"]),
            f"{s['hari']} {s['service_date']} '{s['date_label']}'",
        )

    pairs = alignment(week)
    check(
        "options & safety sejajar di semua hari",
        all(a == b for a, b in pairs.values()),
        str(pairs),
    )
    return week


def verify_week_by_package(client) -> None:
    """Memilih paket boleh menyembunyikan opsi; safety harus ikut disembunyikan."""
    print("\n=== 2. Penyaringan paket ===")
    packages = client.get("/api/catalog/packages").json()
    check("Paket terbaca", bool(packages), str([p["code"] for p in packages]))

    for pkg in packages:
        r = client.get("/api/catalog/menus/week", params={"package_code": pkg["code"]})
        if r.status_code != 200:
            check(f"weeks?package_code={pkg['code']} -> 200", False, str(r.status_code))
            continue
        pairs = alignment(r.json())
        check(
            f"{pkg['code']}: opsi tersaring & safety tetap sejajar",
            all(a == b for a, b in pairs.values()),
            str({d: a for d, (a, _) in pairs.items()}),
        )


def verify_safety_preview(client) -> None:
    """Kode yang dikirim pemanggil harus muncul sebagai `applied_codes`."""
    print("\n=== 3. Pratinjau safety per opsi ===")
    allergens = client.get("/api/catalog/allergens").json()
    if not check("Katalog punya alergen", bool(allergens), str(len(allergens))):
        return
    code = allergens[0]["code"]

    r = client.get("/api/catalog/menus/week", params={"selected_allergen_codes": [code]})
    check("weeks + selected_allergen_codes -> 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    check(
        "Kode ikut echoed di applied_codes",
        code in (body.get("applied_codes") or []),
        str(body.get("applied_codes")),
    )
    levels = sorted(
        {s.get("level") for d in body.get("days") or [] for s in d.get("safety") or []}
    )
    check("Status keamanan dihitung", bool(levels), str(levels))
    check("Setiap opsi punya menu_id", all(
        s.get("menu_id") for d in body.get("days") or [] for s in d.get("safety") or []
    ))


def verify_order_without_selections(client, auth, week: dict) -> str | None:
    """Pemanggil lama (Telegram, skrip uji) tidak mengirim `selections` sama sekali."""
    print("\n=== 4. Order tanpa selections (kompatibilitas pemanggil lama) ===")
    target = next((d for d in week.get("days") or [] if d.get("options")), None)
    if not check("Ada hari dengan opsi", target is not None):
        return None

    pkg = pick_package(client, days=[target["hari"]])
    if not pkg:
        check("Paket yang mencakup hari uji tersedia", False)
        return None

    r = client.post(
        "/api/orders",
        headers=auth,
        json={"package_code": pkg["code"], "schedule_days": [target["hari"]]},
    )
    if not check("Order tanpa selections -> 201", r.status_code == 201, str(r.status_code)):
        print(r.json())
        return None

    order = r.json()
    sel = order.get("selections") or []
    check("Pilihan terisi otomatis", len(sel) == 1, str(sel))
    check(
        "Pilihan otomatis = opsi utama",
        bool(sel) and sel[0]["menu_id"] == target["options"][0]["menu_id"],
        f"tersimpan={sel[0]['menu_id'] if sel else '-'} utama={target['options'][0]['menu_id']}",
    )

    detail = client.get(f"/api/orders/{order['order_id']}", headers=auth).json()
    per_day = detail.get("safety", {}).get("per_day") or []
    check("Safety per hari menempel pada menu terpilih", bool(per_day),
          str([(d["hari"], d.get("menu_id")) for d in per_day]))
    return order["order_id"]


def pick_package(client, *, days: list[str]) -> dict | None:
    """Paket aktif pertama yang mencakup semua `days`."""
    for pkg in client.get("/api/catalog/packages").json():
        if all(d in pkg["days"] for d in days):
            return pkg
    return None


# -- Bagian tulis -------------------------------------------------------------
def make_staff(username: str, password: str, role: str) -> None:
    from app.services import auth_service

    auth_service.create_staff(
        username=username, password=password, display_name=username, role=role
    )


def register_customer(client, suffix: str) -> tuple[str, dict, int]:
    """Daftarkan pelanggan uji lalu tautkan Telegram agar boleh membuat pesanan."""
    username = f"wpel_{suffix}"
    # Nomor dibuat unik per jalan: `customers.phone` unik, dan sisa dari uji yang
    # gagal di tengah tidak boleh menghalangi run berikutnya.
    phone = f"+6281{int(suffix[:6], 16) % 1000000000:09d}"
    r = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "Pelanggan1!",
            "display_name": "Pelanggan Uji Weekly",
            "phone": phone,
        },
    )
    if r.status_code != 201:
        raise SystemExit(f"register gagal: {r.status_code} {r.json()}")

    # `/auth/register` mengembalikan token, bukan profil — id diambil dari `/me`.
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/customers/me", headers=auth)
    if me.status_code != 200:
        raise SystemExit(f"/customers/me gagal: {me.status_code} {me.json()}")
    customer_id = me.json()["customer_id"]

    link = client.post("/api/customers/me/telegram/code", headers=auth).json()
    chat_id = 910000000 + int(suffix[:3], 16) % 9000
    linked = client.post(
        "/api/auth/telegram/resolve",
        json={"code": link["telegram_link_code"], "chat_id": chat_id},
    )
    if linked.status_code != 200:
        raise SystemExit(f"taut Telegram gagal: {linked.status_code} {linked.json()}")
    return customer_id, auth, chat_id


def verify_multi_option(client, auth, admin: dict, week: dict, extra_orders: list[str]) -> dict:
    """
    Tambah opsi kedua untuk `TEST_DAY`, lalu buktikan pilihan itu benar-benar dihormati
    di seluruh alur: tampilan minggu, filter paket, pesanan, KDS, dan jadwal admin.
    """
    print(f"\n=== 5. Opsi menu kedua untuk {TEST_DAY} (WRITE) ===")
    before = next((d for d in week.get("days") or [] if d["hari"] == TEST_DAY), None)
    if not check(f"{TEST_DAY} ada di minggu layanan", before is not None):
        return {}
    primary = before["options"][0]
    check("Sebelum tes: satu opsi", len(before["options"]) == 1, str(len(before["options"])))

    # Opsi kedua sengaja memakai bahan seafood: kalau allergen seafood diaktifkan,
    # status dua opsi ini harus berbeda. Kalau tidak, tes ini tidak membuktikan apa pun.
    allergen_codes = [a["code"] for a in client.get("/api/catalog/allergens").json()]
    seafood = next((c for c in allergen_codes if "seafood" in c), allergen_codes[0])

    # `menu_id` diberi langsung supaya tiap run terisolasi dan sisa dari run lain
    # tidak ikut terISI. Tanpa ini, dua kali run akan menulis dokumen yang sama.
    created_id = f"{TEST_MENU_PREFIX}{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"/api/admin/menus/{TEST_DAY}",
        headers=admin,
        json={
            "menu_id": created_id,
            "nama_menu": "Uji Opsi Kedua",
            "deskripsi": "Menu uji otomatis untuk memverifikasi multi-opsi per hari.",
            "bahan_detail": [
                {"nama": "Ikan exclude", "sumber": "uji", "potensi_alergen": seafood}
            ],
            "alat_dapur_steril": ["Panci terpisah"],
            "package_codes": [],
            "option_index": 1,
        },
    )
    check("Admin tambah opsi kedua -> 201", r.status_code == 201, str(r.status_code))
    if r.status_code != 201:
        print(r.json())
        return {}
    created = r.json()
    created_id = created["menu_id"]
    check(
        "menu_id baru != menu_id opsi utama",
        created_id != primary["menu_id"],
        f"baru={created_id} utama={primary['menu_id']}",
    )
    check("Opsi utama tidak tertimpa", primary["menu_id"] == "menu_" + TEST_DAY.lower(),
          f"utama={primary['menu_id']}")

    r = client.get("/api/catalog/menus/week")
    after = next(d for d in r.json()["days"] if d["hari"] == TEST_DAY)
    check(f"{TEST_DAY} kini punya 2 opsi", len(after["options"]) == 2,
          str([o["menu_id"] for o in after["options"]]))
    check("Safety ikut 2", len(after["safety"]) == 2, str(len(after["safety"])))
    check(
        "safety sejajar dengan options (menu_id sama urutan)",
        [o["menu_id"] for o in after["options"]] == [s["menu_id"] for s in after["safety"]],
        str([s["menu_id"] for s in after["safety"]]),
    )

    # Status keamanan harus benar-benar berbeda antara opsi utama dan opsi kedua.
    r = client.get(
        "/api/catalog/menus/week", params={"selected_allergen_codes": [seafood]}
    )
    week_seafood = next(d for d in r.json()["days"] if d["hari"] == TEST_DAY)
    levels = {s["menu_id"]: s["level"] for s in week_seafood["safety"]}
    check(
        f"Status opsi berbeda saat {seafood} dipilih",
        len(set(levels.values())) > 1,
        str(levels),
    )

    print("\n=== 6. Opsi kedua hanya untuk satu paket ===")
    pkg = pick_package(client, days=[TEST_DAY])
    patch = client.patch(
        f"/api/admin/menus/{created_id}",
        headers=admin,
        json={"package_codes": [pkg["code"]]},
    )
    check("Patch package_codes -> 200", patch.status_code == 200, str(patch.status_code))
    check("package_codes tersimpan", (patch.json().get("package_codes") or []) == [pkg["code"]],
          str(patch.json().get("package_codes")))

    r = client.get("/api/catalog/menus/week", params={"package_code": pkg["code"]})
    visible = next(d for d in r.json()["days"] if d["hari"] == TEST_DAY)
    check("Opsi tersaring tetap tersedia di paket itu", len(visible["options"]) == 2,
          str(len(visible["options"])))

    # Paket LAIN yang tidak memuat opsi kedua harus menyisakan satu opsi, dan
    # safety-nya harus menyusut jadi satu — bukan tetap dua (gejala misalignment).
    other = next(
        (p for p in client.get("/api/catalog/packages").json() if p["code"] != pkg["code"]),
        None,
    )
    if other:
        r = client.get("/api/catalog/menus/week", params={"package_code": other["code"]})
        hidden = next(d for d in r.json()["days"] if d["hari"] == TEST_DAY)
        check("Opsi kedua tersembunyi di paket lain", len(hidden["options"]) == 1,
              str([o["menu_id"] for o in hidden["options"]]))
        check("Safety ikut menyusut, tidak bergeser", len(hidden["safety"]) == 1,
              str([s["menu_id"] for s in hidden["safety"]]))
        check("Yang tersisa adalah opsi utama",
              [o["menu_id"] for o in hidden["options"]] == [primary["menu_id"]],
              str([o["menu_id"] for o in hidden["options"]]))

    print("\n=== 7. Menarik opsi dari pelanggan (tanpa menghapus data) ===")
    un = client.delete(f"/api/admin/menus/{created_id}/publish", headers=admin)
    check("Unpublish -> 200", un.status_code == 200, str(un.status_code))
    check("published=False", un.json().get("published") is False, str(un.json().get("published")))
    r = client.get("/api/catalog/menus/week")
    days_now = {d["hari"]: d for d in r.json()["days"]}
    check("Opsi ditarik hilang dari /menu",
          len(days_now[TEST_DAY]["options"]) == 1,
          str(len(days_now[TEST_DAY]["options"])))
    pub = client.post(f"/api/admin/menus/{created_id}/publish", headers=admin)
    check("Publish lagi -> 200", pub.status_code == 200, str(pub.status_code))
    check("published=True", pub.json().get("published") is True)

    # Pilihan untuk pesanan: opsi kedua untuk hari uji, dan satu hari lain dari paket
    # yang sama. Paket WAJIB sama dengan paket yang dipakai pada langkah 6 — kalau
    # tidak, backend akan menolak karena opsi kedua memang tidak tersedia di sana,
    # dan tes ini akan mengukur hal yang salah.
    r = client.get("/api/catalog/menus/week", params={"package_code": pkg["code"]})
    fresh = {d["hari"]: d for d in r.json()["days"]}
    selections = [{"hari": TEST_DAY, "menu_id": created_id}]
    extra = next((d for d in pkg["days"] if d != TEST_DAY and fresh.get(d, {}).get("options")), None)
    if extra:
        selections.append({"hari": extra, "menu_id": fresh[extra]["options"][0]["menu_id"]})
    day_list = [s["hari"] for s in selections]
    order_pkg = pkg
    check("Hari uji ada di paket terpilih", TEST_DAY in order_pkg["days"], str(order_pkg["days"]))

    print("\n=== 8. Pesanan memilih menu berbeda per hari ===")
    r = client.post(
        "/api/orders",
        headers=auth,
        json={
            "package_code": order_pkg["code"],
            "schedule_days": day_list,
            "selections": selections,
        },
    )
    check("Order dengan selections -> 201", r.status_code == 201, str(r.status_code))
    if r.status_code != 201:
        print(r.json())
        return {}
    order = r.json()
    order_id = order["order_id"]
    saved = {s["hari"]: s["menu_id"] for s in order.get("selections") or []}
    check("Pilihan tersimpan persis seperti dikirim", saved == {s["hari"]: s["menu_id"] for s in selections},
          str(saved))
    check("Opsi kedua benar-benar tersimpan untuk hari uji", saved.get(TEST_DAY) == created_id,
          f"{saved.get(TEST_DAY)} vs {created_id}")
    check("menu_selections ikut di respons", "selections" in order, str(list(order)[:12]))

    print("\n=== 9. KDS menampilkan menu yang DIPILIH ===")
    board = client.get("/api/kitchen/board", headers=admin)
    check("GET /api/kitchen/board -> 200", board.status_code == 200, str(board.status_code))
    tickets = [t for col in (board.json().get("columns") or {}).values() for t in col]
    mine = next((t for t in tickets if t.get("order_id") == order_id), None)
    check("Tiket pesanan uji muncul di KDS", mine is not None, str(order_id))
    if mine:
        check("service_menu = menu yang dipilih, bukan opsi utama",
              mine.get("service_menu") == "Uji Opsi Kedua",
              f"kds={mine.get('service_menu')!r} utama={primary['nama_menu']!r}")

    print("\n=== 10. Jadwal admin melihat semua opsi + pilihan ===")
    sched = client.get("/api/admin/schedule", headers=admin)
    check("GET /api/admin/schedule -> 200", sched.status_code == 200, str(sched.status_code))
    row = next((d for d in sched.json().get("days") or [] if d["hari"] == TEST_DAY), None)
    check("Baris jadwal ada", row is not None, TEST_DAY)
    if row:
        check("option_count = 2", row.get("option_count") == 2, str(row.get("option_count")))
        check("option_names memuat kedua opsi",
              "Uji Opsi Kedua" in (row.get("option_names") or []),
              str(row.get("option_names")))
        check("chosen_menus mencatat pilihan pelanggan",
              (row.get("chosen_menus") or {}).get(order_id) == "Uji Opsi Kedua",
              str(row.get("chosen_menus")))

    print("\n=== 11. Menolak pilihan yang tidak sah ===")
    bad_day = client.post(
        "/api/orders",
        headers=auth,
        json={
            "package_code": order_pkg["code"],
            "schedule_days": [TEST_DAY],
            "selections": [{"hari": TEST_DAY, "menu_id": "menu_hari_yang_tidak_ada"}],
        },
    )
    check("menu_id tidak dikenal -> 422", bad_day.status_code == 422, str(bad_day.status_code))

    unpub = client.delete(f"/api/admin/menus/{created_id}/publish", headers=admin)
    check("Opsi ditarik lagi untuk tes", unpub.status_code == 200)
    bad_pub = client.post(
        "/api/orders",
        headers=auth,
        json={
            "package_code": order_pkg["code"],
            "schedule_days": [TEST_DAY],
            "selections": [{"hari": TEST_DAY, "menu_id": created_id}],
        },
    )
    check("memilih menu unpublished -> 422", bad_pub.status_code == 422, str(bad_pub.status_code))
    client.post(f"/api/admin/menus/{created_id}/publish", headers=admin)

    bad_day2 = client.post(
        "/api/orders",
        headers=auth,
        json={
            "package_code": order_pkg["code"],
            "schedule_days": [TEST_DAY],
            "selections": [{"hari": TEST_DAY, "menu_id": created_id}],
        },
    )
    check("Menu tersedia untuk pesanan", bad_day2.status_code == 201, str(bad_day2.status_code))
    extra_orders.append(bad_day2.json()["order_id"] if bad_day2.status_code == 201 else "")

    print("\n=== 12. Mengganti pilihan setelah pesanan dibuat ===")
    r = client.patch(
        f"/api/orders/{order_id}",
        headers=auth,
        json={"selections": [{"hari": TEST_DAY, "menu_id": primary["menu_id"]}]},
    )
    check("PATCH selections -> 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        after_sel = {s["hari"]: s["menu_id"] for s in r.json().get("selections") or []}
        check("Pilihan berubah ke opsi utama", after_sel.get(TEST_DAY) == primary["menu_id"],
              str(after_sel))
    return {
        "order_id": order_id,
        "created_id": created_id,
    }


def cleanup(customer_id: str, chat_id: int, order_ids: list[str], staff: list[str], menu_id: str) -> None:
    """Bersihkan semua jejak data uji, termasuk opsi menu yang dibuat skrip ini."""
    from app.repositories import astra, customer_repo

    for username in staff:
        try:
            doc = customer_repo.find_by_username(username)
            if doc:
                astra.get_collection("customers").delete_one({"_id": doc["_id"]})
                print(f"[{PASS}] Hapus customers/{username}")
        except Exception as exc:
            print(f"[{FAIL}] Hapus customers/{username} - {type(exc).__name__}: {exc}")

    if menu_id:
        delete_menu(menu_id)

    for order_id in order_ids:
        if not order_id:
            continue
        try:
            astra.get_collection("kitchen_orders").delete_one({"order_id": order_id})
            print(f"[{PASS}] Hapus kitchen_orders/{order_id}")
        except Exception as exc:
            print(f"[{FAIL}] Hapus kitchen_orders/{order_id} - {type(exc).__name__}: {exc}")

    if customer_id:
        for collection, doc_id in (("customers", customer_id), ("user_profiles", str(chat_id))):
            try:
                astra.get_collection(collection).delete_one({"_id": doc_id})
                print(f"[{PASS}] Hapus {collection}/{doc_id}")
            except Exception as exc:
                print(f"[{FAIL}] Hapus {collection}/{doc_id} - {type(exc).__name__}: {exc}")


def main() -> int:
    write = "--write" in sys.argv
    suffix = uuid.uuid4().hex[:10]
    admin_name = f"wadm_{suffix}"
    admin_pw = "Adm1nPassw0rd!"
    staff = [admin_name]
    customer_id = ""
    chat_id = 0
    order_ids: list[str] = []
    created_menu = ""
    extra_orders: list[str] = []

    with TestClient(app) as client:
        # Pembersihan harus mendahului snapshot minggu, kalau tidak `week` masih
        # menyimpan opsi uji dari run sebelumnya dan assert "satu opsi" selalu gagal.
        if write:
            purge_test_menus()
            purge_orphan_orders()
        week = verify_week_shape(client)
        verify_week_by_package(client)
        verify_safety_preview(client)

        if not write:
            print("\n(lewati penulisan data — jalankan dengan --write untuk mengujinya)")
        else:
            customer_id, auth, chat_id = register_customer(client, suffix)
            legacy_order = verify_order_without_selections(client, auth, week)
            if legacy_order:
                order_ids.append(legacy_order)

            make_staff(admin_name, admin_pw, "admin")
            admin = login(client, admin_name, admin_pw)
            if admin:
                made = verify_multi_option(client, auth, admin, week, extra_orders)
                if made:
                    order_ids.append(made["order_id"])
                    created_menu = made["created_id"]
            else:
                check("Login admin -> 200", False)

    order_ids.extend(extra_orders)
    cleanup(customer_id, chat_id, order_ids, staff, created_menu)

    print("\n=== Ringkasan ===")
    failed = [name for name, ok, _ in results if not ok]
    print(f"{len(results) - len(failed)}/{len(results)} pemeriksaan lulus")
    if failed:
        print("Gagal:")
        for name in failed:
            print("  -", name)
        return 1
    print("Semua pemeriksaan lulus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
