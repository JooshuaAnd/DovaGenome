"""Repository untuk mapping akun supplier ke tenant supplier."""

from __future__ import annotations

from typing import Any

from app.repositories import supabase as db


def get_account_for_customer(customer_id: str) -> dict[str, Any] | None:
    """Ambil mapping supplier yang dimiliki akun customer/staff tertentu."""
    return db.execute_one(
        """
        SELECT sa.customer_id, sa.supplier_id, sa.status, s.name AS supplier_name
        FROM supplier_accounts sa
        JOIN suppliers s ON s.supplier_id = sa.supplier_id
        WHERE sa.customer_id = %s AND sa.status = 'active' AND s.status = 'active'
        LIMIT 1
        """,
        (customer_id,),
    )


def get_supplier(supplier_id: str) -> dict[str, Any] | None:
    """Ambil supplier aktif tanpa mengekspos data lewat query user."""
    return db.execute_one(
        """
        SELECT supplier_id, name, category, phone, email, address, rating,
               lead_time_days, status
        FROM suppliers
        WHERE supplier_id = %s AND status = 'active'
        """,
        (supplier_id,),
    )
