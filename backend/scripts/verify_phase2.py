r"""
Verifikasi Phase 2 — menjalankan API FastAPI terhadap Astra DB live.

Skrip ini TIDAK mengubah data produksi kecuali lewat flag eksplisit
(`--write`). Defaultnya hanya GET/health + simulasi safety.

Jalankan dari repo root:
    .\.venv\Scripts\python.exe backend\scripts\verify_phase2.py
    .\.venv\Scripts\python.exe backend\scripts\verify_phase2.py --write   # ikut membuat order uji
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


def check(name: str, condition: bool, detail: str = "") -> bool:
    results.append((name, bool(condition), detail))
    print(f"[{PASS if condition else FAIL}] {name}" + (f" — {detail}" if detail else ""))
    return bool(condition)


def cleanup(customer_id: str, chat_id: int, order_id: str, staff_usernames: list[str]) -> None:
    """
    Hapus data uji yang dibuat skrip ini.

    Sengaja eksplisit: dokumen uji tidak boleh tercampur dengan data asli, dan
    `user_profiles` juga dibersihkan karena bot menulis cermin di sana.
    """
    from app.repositories import astra, customer_repo

    if staff_usernames:
        for username in staff_usernames:
            try:
                doc = customer_repo.find_by_username(username)
                if doc:
                    astra.get_collection("customers").delete_one({"_id": doc["_id"]})
                    print(f"[{PASS}] Hapus customers/{username}")
            except Exception as exc:
                print(f"[{FAIL}] Hapus customers/{username} — {type(exc).__name__}: {exc}")

    if not customer_id:
        return

    targets = [("customers", customer_id)]
    if chat_id:
        targets.append(("user_profiles", str(chat_id)))
    for collection, doc_id in targets:
        try:
            astra.get_collection(collection).delete_one({"_id": doc_id})
            print(f"[{PASS}] Hapus {collection}/{doc_id}")
        except Exception as exc:
            print(f"[{FAIL}] Hapus {collection}/{doc_id} — {type(exc).__name__}: {exc}")

    if order_id:
        try:
            astra.get_collection("kitchen_orders").delete_one({"order_id": order_id})
            print(f"[{PASS}] Hapus kitchen_orders/{order_id}")
        except Exception as exc:
            print(f"[{FAIL}] Hapus kitchen_orders/{order_id} — {type(exc).__name__}: {exc}")


def make_staff(username: str, password: str, role: str) -> dict:
    """Buat akun staff sementara dan kembalikan header Authorization."""
    from app.services import auth_service

    auth_service.create_staff(
        username=username, password=password, display_name=username, role=role
    )
    return {"username": username, "role": role}


def login(client, username: str, password: str) -> dict | None:
    """Login staff lewat API supaya alur password + hashing ikut teruji."""
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        print(f"[{FAIL}] login staff {username} → {r.status_code} {r.json()}")
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def verify_kitchen(client, admin_headers: dict, order_id: str) -> None:
    """Uji papan dapur, urutan status, dan aturan pembatalan admin."""
    print("\n=== 9. KDS & transisi status ===")
    r = client.get("/api/kitchen/board", headers=admin_headers)
    check("GET /api/kitchen/board → 200", r.status_code == 200, str(r.status_code))
    board = r.json()
    check(
        "Board punya 3 kolom",
        set(board["columns"]) == {"PENDING", "PREPARING", "READY"},
        str(list(board["columns"])),
    )
    check("Board tidak menampilkan data demo", board.get("demo") is False)
    tickets = board["columns"].get("PENDING", [])
    check(
        "Tiket uji muncul di PENDING",
        any(t["order_id"] == order_id for t in tickets),
        f"{len(tickets)} tiket",
    )

    r = client.patch(
        f"/api/kitchen/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "COMPLETED"},
    )
    check("Lompat PENDING → COMPLETED ditolak → 409", r.status_code == 409, str(r.status_code))

    r = client.patch(
        f"/api/kitchen/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "PREPARING"},
    )
    check("PENDING → PREPARING → 200", r.status_code == 200, str(r.status_code))

    # Pembatalan wajib beralasan supaya bisa ditelusuri di timeline.
    r = client.patch(
        f"/api/kitchen/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "CANCELLED"},
    )
    check("Pembatalan tanpa alasan ditolak → 422", r.status_code == 422, str(r.status_code))

    r = client.patch(
        f"/api/kitchen/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "CANCELLED", "note": "Uji otomatis: bahan habis"},
    )
    cancelled = r.status_code == 200
    check(
        "Admin boleh membatalkan dengan alasan",
        cancelled,
        f"{r.status_code} {r.json().get('error', {}).get('message', '')[:70]}",
    )
    if cancelled:
        check(
            "Timeline mencatat pembatalan",
            len(r.json()["timeline"]) >= 3,
            f"{len(r.json()['timeline'])} entri",
        )
        check(
            "Kitchen notes diberi prefix batal",
            r.json()["kitchen_notes"].startswith("PESANAN DIBATALKAN"),
            r.json()["kitchen_notes"][:40],
        )


def verify_hardening(client, auth_headers: dict) -> None:
    """Cek perbaikan yang ditemukan saat audit Phase 2."""
    print("\n=== 11. Hardening (katalog, passport, rate limit) ===")

    r = client.get("/api/catalog?include_inactive=true")
    check("include_inactive tanpa login → 403", r.status_code == 403, str(r.status_code))

    r = client.get("/api/catalog?include_inactive=true", headers=auth_headers)
    check("include_inactive sebagai customer → 403", r.status_code == 403, str(r.status_code))

    r = client.get("/api/catalog")
    check("katalog normal tetap publik → 200", r.status_code == 200, str(r.status_code))

    # Partial update tidak boleh menghapus batasan yang sudah tersimpan.
    r = client.put(
        "/api/customers/me/passport",
        headers=auth_headers,
        json={"avoided_times": ["avd_pagi"]},
    )
    kept = r.status_code == 200 and "alg_dairy" in (r.json().get("critical_codes") or [])
    check("Partial update menjaga batasan lama", kept, str(r.json().get("critical_codes")))

    r = client.put(
        "/api/customers/me/passport",
        headers=auth_headers,
        json={"avoided_times": []},
    )
    check("Kosongkan avoided_times → 200", r.status_code == 200, str(r.status_code))

    from app.utils.ratelimit import login_limiter

    login_limiter.reset()
    codes = []
    for _ in range(12):
        codes.append(client.post("/api/auth/login", json={"username": "x", "password": "y"}).status_code)
    check("Login kena rate limit → 429", 429 in codes, str(codes))
    login_limiter.reset()


def verify_staff_role_gate(client, kitchen_headers: dict) -> None:
    """Kitchen boleh读写 KDS, tapi tidak boleh cancel atau buka admin."""
    print("\n=== 10. Pembatasan role kitchen ===")
    r = client.get("/api/kitchen/board", headers=kitchen_headers)
    check("Kitchen boleh baca papan → 200", r.status_code == 200, str(r.status_code))

    r = client.get("/api/admin/dashboard", headers=kitchen_headers)
    check("Kitchen tidak boleh buka admin → 403", r.status_code == 403, str(r.status_code))

    r = client.post("/api/orders", headers=kitchen_headers, json={"package_code": "pkg_full"})
    check("Kitchen tidak bisa membuat order", r.status_code in (403, 422), str(r.status_code))


def main() -> int:
    write = "--write" in sys.argv
    suffix = uuid.uuid4().hex[:6]
    # Id yang dibuat mode tulis — dibersihkan di akhir supaya database uji
    # tidak tertinggal dokumen customers/orders palsu.
    customer_id = ""
    chat_id = 0
    created_order_id = ""
    staff_usernames: list[str] = []

    with TestClient(app) as client:  # menjalankan lifespan
        print("\n=== 1. Health & konfigurasi ===")
        r = client.get("/api/health")
        check("GET /api/health → 200", r.status_code == 200, str(r.status_code))
        health = r.json()
        check("Astra terhubung", health.get("astra_connected") is True)
        check("DEMO_MODE mati", health.get("demo_mode") is False)
        counts = health.get("collections", {})
        check(
            "5 koleksi aplikasi terbaca",
            all(k in counts for k in ("kitchen_orders", "catering_packages", "catering_menus", "allergen_definitions", "user_profiles")),
            str(counts),
        )

        r = client.get("/api/health/langflow")
        check("GET /api/health/langflow → 200", r.status_code == 200, str(r.status_code))
        print("      ", r.json())

        print("\n=== 2. Katalog publik ===")
        r = client.get("/api/catalog")
        check("GET /api/catalog → 200", r.status_code == 200, str(r.status_code))
        catalog = r.json()
        check("3 paket", len(catalog["packages"]) == 3, str(len(catalog["packages"])))
        check("6 alergen", len(catalog["allergens"]) == 6, str(len(catalog["allergens"])))
        check("6 menu", len(catalog["menus"]) == 6, str(len(catalog["menus"])))
        prices = {p["code"]: p.get("price") for p in catalog["packages"]}
        check("Harga paket terbaca (None = belum diisi admin)", set(prices.values()) is not None, str(prices))

        r = client.get("/api/catalog/safety", params={"days": "Rabu"})
        check("GET /api/catalog/safety → 200", r.status_code == 200, str(r.status_code))
        check("Menu Rabu terdeteksi", r.json()["per_day"][0]["hari"] == "Rabu")

        print("\n=== 3. Autentikasi ===")
        r = client.post("/api/orders")
        check("POST /api/orders tanpa token → 401", r.status_code == 401, str(r.status_code))
        check("Format error konsisten", "error" in r.json(), str(r.json())[:120])

        r = client.post("/api/auth/register", json={"username": f"test_{suffix}", "display_name": "Uji Phase 2"})
        check("POST /api/auth/register → 201", r.status_code == 201, str(r.status_code))
        if r.status_code != 201:
            print(r.json())
            return 1
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        customer = r.json()["customer"]
        customer_id = customer["customer_id"]
        check("Telegram belum terverifikasi", customer["telegram_verified"] is False)
        check("Kode tautan terbit", bool(customer["telegram_link_code"]), customer["telegram_link_code"])

        r = client.get("/api/customers/me", headers=auth)
        check("GET /api/customers/me → 200", r.status_code == 200, str(r.status_code))

        print("\n=== 4. Gerbang verifikasi Telegram ===")
        r = client.post(
            "/api/orders",
            headers=auth,
            json={"package_code": catalog["packages"][0]["code"], "schedule_days": ["Rabu"]},
        )
        check("Buat order tanpa Telegram tertaut → 422", r.status_code == 422, str(r.status_code))
        check("Pesan penolakan jelas", "Telegram" in r.json()["error"]["message"], r.json()["error"]["message"][:100])

        print("\n=== 5. Role staff ===")
        r = client.get("/api/kitchen/board", headers=auth)
        check("KDS untuk customer → 403", r.status_code == 403, str(r.status_code))
        r = client.get("/api/admin/dashboard", headers=auth)
        check("Admin untuk customer → 403", r.status_code == 403, str(r.status_code))

        print("\n=== 6. Dietary Passport ===")
        # Kode diambil live dari katalog, bukan ditebak — katalog yang jadi acuan.
        codes = [a["code"] for a in catalog["allergens"]]
        dairy = next((c for c in codes if "dairy" in c or "susu" in c), None)
        seafood = next((c for c in codes if "seafood" in c), None)
        check("Katalog punya kode dairy & seafood", bool(dairy and seafood), str(codes))

        r = client.put(
            "/api/customers/me/passport",
            headers=auth,
            json={"intolerances": [{"code": dairy, "label": "Bebas Susu", "category": "intolerance"}]},
        )
        check("Simpan passport → 200", r.status_code == 200, f"{r.status_code} {r.json()}")
        passport = r.json()
        check("Kode kritis tersimpan", passport.get("critical_codes") == [dairy], str(passport.get("critical_codes")))
        check("Passport ditandai terstruktur", passport.get("structured") is True)

        r = client.put(
            "/api/customers/me/passport",
            headers=auth,
            json={"allergies": [{"code": "alg_tidak_ada", "label": "Kode Palsu"}]},
        )
        check("Kode alergen tak dikenal → 422", r.status_code == 422, str(r.status_code))

        r = client.get("/api/customers/me/passport/preview", headers=auth)
        check("Pratinjau passport → 200", r.status_code == 200, str(r.status_code))
        check("Pratinjau melaporkan status", bool(r.json().get("level")), str(r.json().get("level")))

        verify_hardening(client, auth)

        if not write:
            print("\n(lewati pembuatan order — jalankan dengan --write untuk mengujinya)")
        else:
            print("\n=== 7. Pembuatan order (WRITE) ===")
            # Paket 6 hari dipakai agar jadwal tidak jadi variabel.
            full = next(
                (p for p in catalog["packages"] if len(p["days"]) == 6),
                catalog["packages"][0],
            )
            link = client.post("/api/customers/me/telegram/code", headers=auth).json()
            check("Deep link dibentuk", "t.me" in link.get("telegram_deep_link", ""), link.get("telegram_deep_link", "")[:60])

            chat_id = 900000000 + int(suffix[:3], 16) % 9000
            r = client.post(
                "/api/auth/telegram/resolve",
                json={"code": link["telegram_link_code"], "chat_id": chat_id},
            )
            check("Tautkan Telegram → 200", r.status_code == 200, str(r.status_code))
            if r.status_code != 200:
                print(r.json())
                return 1

            # Jadwal = semua hari paket (kosongkan `schedule_days`).
            # Ini aman walau passport menandai seafood; blocking diuji di bagian 8.
            r = client.post(
                "/api/orders",
                headers=auth,
                json={"package_code": full["code"]},
            )
            check("Buat order → 201", r.status_code == 201, f"{r.status_code} {r.json() if r.status_code != 201 else ''}")
            if r.status_code != 201:
                return 1
            order = r.json()
            order_id = order["order_id"]
            created_order_id = order_id
            print(f"      order_id={order_id} total={order['total']} status={order['status']}")

            r = client.get(f"/api/orders/{order_id}", headers=auth)
            check("Detail order → 200", r.status_code == 200, str(r.status_code))
            check("Timeline punya 1 entri", len(r.json()["timeline"]) == 1, str(len(r.json()["timeline"])))

            r = client.get(f"/api/orders/{order_id}/invoice", headers=auth)
            check("Invoice → 200", r.status_code == 200, str(r.status_code))
            check("Nomor invoice terbit", r.json()["invoice_number"].startswith("INV-"), r.json()["invoice_number"])

            print("\n=== 8. Order dengan passport blocking (WRITE) ===")
            # Rabu = menu seafood. Dengan passport seafood aktif, harus ditolak.
            client.put(
                "/api/customers/me/passport",
                headers=auth,
                json={"allergies": [{"code": seafood, "label": "Bebas Seafood", "category": "allergy"}]},
            )
            r = client.post(
                "/api/orders",
                headers=auth,
                json={"package_code": full["code"], "schedule_days": ["Rabu"]},
            )
            blocked = r.status_code == 409
            check("Order dengan tabrakan alergen → 409", blocked, f"{r.status_code} {r.json().get('error', {}).get('message', '')[:80] if blocked else ''}")
            if blocked:
                detail = r.json()["error"]["details"]
                check("Detail safety disertakan", "safety" in detail, str(list(detail)))
                check("Hari terblokir terdeteksi", bool(detail.get("blocked_days")), str(detail.get("blocked_days")))

            print("\n=== 9-10. KDS, transisi status & role staff (WRITE) ===")
            admin_pw = "Adm1nPassw0rd!"
            kitchen_pw = "KdsPassw0rd!"
            admin_name = f"adm_{suffix}"
            kitchen_name = f"kds_{suffix}"
            make_staff(admin_name, admin_pw, "admin")
            make_staff(kitchen_name, kitchen_pw, "kitchen")
            staff_usernames.extend([admin_name, kitchen_name])

            admin_headers = login(client, admin_name, admin_pw)
            kitchen_headers = login(client, kitchen_name, kitchen_pw)
            check("Login admin dengan password → 200", bool(admin_headers))
            check("Login kitchen dengan password → 200", bool(kitchen_headers))
            if admin_headers:
                verify_kitchen(client, admin_headers, order_id)
            if kitchen_headers:
                verify_staff_role_gate(client, kitchen_headers)

    # Selalu dibersihkan: register() membuat akun pelanggan sungguhan, jadi
    # meski mode baca-only, dokumen uji tidak boleh tertinggal.
    print("\n=== Pembersihan data uji ===")
    cleanup(customer_id, chat_id, created_order_id, staff_usernames)

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