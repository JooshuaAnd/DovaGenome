"""
Buat akun admin/kitchen pertama.

Endpoint `/api/admin/staff` hanya bisa dipakai admin yang sudah ada, jadi
akun pertama harus dibuat lewat skrip ini.

Jalankan:
    python backend/scripts/seed_staff.py --username admin --password "rahasia-kuat"
    python backend/scripts/seed_staff.py --username dapur --role kitchen --password "rahasia-kuat"

Password tidak boleh muncul di riwayat shell dan tidak disimpan di repo.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.errors import AppError  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.repositories import astra, customer_repo  # noqa: E402
from app.services import auth_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed akun admin/kitchen")
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", default=Role.ADMIN.value, choices=[Role.ADMIN.value, Role.KITCHEN.value])
    parser.add_argument("--display-name", default="")
    parser.add_argument("--password", default="", help="Kosongkan untuk prompted input.")

    args = parser.parse_args()

    if not astra.is_connected():
        print("Astra DB tidak tersambung. Periksa ASTRA_DB_API_ENDPOINT & token.")
        return 1
    astra.ensure_collections()

    password = args.password or getpass.getpass("Password (minimal 8 karakter): ")
    if len(password) < 8:
        print("Password terlalu pendek (minimal 8 karakter).")
        return 1

    existing = customer_repo.find_by_username(args.username)
    if existing:
        print(f"Username '{args.username}' sudah dipakai (role={existing.get('role')}).")
        overwrite = input("Timpa passwordnya? [y/N] ").strip().lower()
        if overwrite != "y":
            print("Batal.")
            return 1
        customer_repo.update_fields(
            str(existing.get("customer_id") or existing.get("_id")),
            {
                "password_hash": auth_service.hash_password(password),
                "role": args.role,
                "status": "active",
            },
        )
        print(f"Password untuk '{args.username}' diperbarui.")
        return 0

    try:
        staff = auth_service.create_staff(
            username=args.username,
            password=password,
            display_name=args.display_name or args.username,
            role=args.role,
        )
    except AppError as exc:
        print(f"Gagal: {exc.message}")
        return 1

    print(f"Akun {staff.role} '{staff.username}' dibuat ({staff.customer_id}).")
    print("Ingat: kata sandi tidak bisa diambil kembali lewat API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())