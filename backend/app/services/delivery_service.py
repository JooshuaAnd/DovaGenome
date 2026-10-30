"""Status-based courier dispatch and customer delivery tracking."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.errors import ConflictError, DatabaseError, NotFoundError, PermissionError_, ValidationError
from app.repositories import supabase as db


_TRANSITIONS = {
    "PLANNED": {"ASSIGNED", "CANCELLED"},
    "ASSIGNED": {"PICKED_UP", "CANCELLED"},
    "PICKED_UP": {"OUT_FOR_DELIVERY", "FAILED"},
    "OUT_FOR_DELIVERY": {"DELIVERED", "FAILED"},
    "FAILED": {"ASSIGNED", "CANCELLED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}


def _check() -> None:
    if not db.check_delivery_migrations():
        raise DatabaseError("Migration delivery dispatch belum diterapkan di Supabase.")


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _out(row: dict[str, Any], *, include_address: bool = True) -> dict[str, Any]:
    result = {
        "stop_id": str(row["stop_id"]),
        "order_id": str(row["order_id"]),
        "customer_id": str(row.get("customer_id") or ""),
        "customer_name": str(row.get("customer_name") or ""),
        "service_date": _iso(row.get("service_date")),
        "meal_slot": str(row.get("meal_slot") or "lunch"),
        "status": str(row.get("status") or "PLANNED"),
        "courier_id": str(row.get("courier_id") or "") or None,
        "proof_ref": str(row.get("proof_ref") or ""),
        "notes": str(row.get("notes") or ""),
        "assigned_at": _iso(row.get("assigned_at")) if row.get("assigned_at") else None,
        "picked_up_at": _iso(row.get("picked_up_at")) if row.get("picked_up_at") else None,
        "delivered_at": _iso(row.get("delivered_at")) if row.get("delivered_at") else None,
    }
    if include_address:
        result["address"] = str(row.get("address_snapshot") or "")
    return result


def create_stop(
    *, order_id: str, service_date: date, meal_slot: str, actor_id: str
) -> dict[str, Any]:
    _check()
    if meal_slot not in {"breakfast", "lunch", "dinner"}:
        raise ValidationError("Meal slot delivery tidak valid.")
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT order_id, customer_id, customer_name, delivery_address, payment_status, status
                FROM orders WHERE order_id = %s FOR UPDATE
                """,
                (order_id,),
            )
            order = cur.fetchone()
            if not order:
                raise NotFoundError("Pesanan tidak ditemukan.")
            if order["payment_status"] != "PAID":
                raise ConflictError("Manifest delivery hanya boleh dibuat untuk order PAID.")
            if order["status"] == "CANCELLED":
                raise ConflictError("Order yang dibatalkan tidak dapat dikirim.")
            if not str(order["delivery_address"] or "").strip():
                raise ValidationError("Alamat delivery order masih kosong.")
            cur.execute(
                """
                INSERT INTO delivery_stops
                    (order_id, customer_id, customer_name, service_date, meal_slot, address_snapshot)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id, service_date, meal_slot) DO UPDATE
                    SET updated_at = NOW()
                RETURNING *
                """,
                (order_id, order["customer_id"], order["customer_name"], service_date,
                 meal_slot, str(order["delivery_address"]).strip()),
            )
            row = cur.fetchone()
            return _out(row)


def list_stops(*, service_date: date | None = None, courier_id: str | None = None) -> list[dict[str, Any]]:
    _check()
    clauses = ["1=1"]
    params: list[Any] = []
    if service_date:
        clauses.append("service_date = %s")
        params.append(service_date)
    if courier_id:
        clauses.append("courier_id = %s")
        params.append(courier_id)
    rows = db.execute(
        f"""
        SELECT * FROM delivery_stops
        WHERE {' AND '.join(clauses)}
        ORDER BY service_date, meal_slot, created_at
        """,
        tuple(params),
    )
    return [_out(row) for row in rows]


def assign_stop(*, stop_id: str, courier_id: str, actor_id: str) -> dict[str, Any]:
    _check()
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id, role, status FROM customers WHERE customer_id = %s", (courier_id,))
            courier = cur.fetchone()
            if not courier or courier["role"] != "courier" or courier["status"] != "active":
                raise ValidationError("Akun courier tidak aktif atau role belum courier.")
            cur.execute("SELECT * FROM delivery_stops WHERE stop_id = %s FOR UPDATE", (stop_id,))
            stop = cur.fetchone()
            if not stop:
                raise NotFoundError("Delivery stop tidak ditemukan.")
            if stop["status"] not in {"PLANNED", "FAILED"}:
                raise ConflictError(f"Stop berstatus {stop['status']} tidak dapat di-assign ulang.")
            cur.execute(
                """
                UPDATE delivery_stops
                SET courier_id = %s, status = 'ASSIGNED', assigned_at = NOW(), updated_at = NOW()
                WHERE stop_id = %s RETURNING *
                """,
                (courier_id, stop_id),
            )
            return _out(cur.fetchone())


def update_status(
    *, stop_id: str, status: str, actor_id: str, idempotency_key: str,
    proof_ref: str = "", note: str = "",
) -> dict[str, Any]:
    _check()
    normalized = str(status or "").strip().upper()
    clean_key = str(idempotency_key or "").strip()
    if normalized not in {"PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED", "FAILED"}:
        raise ValidationError("Status courier tidak valid.")
    if not clean_key:
        raise ValidationError("Idempotency-Key event delivery wajib diisi.")
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM delivery_events WHERE idempotency_key = %s FOR UPDATE",
                (clean_key,),
            )
            existing = cur.fetchone()
            if existing:
                if str(existing["stop_id"]) != stop_id:
                    raise ConflictError("Idempotency-Key event delivery sudah dipakai stop lain.")
                cur.execute("SELECT * FROM delivery_stops WHERE stop_id = %s", (stop_id,))
                existing_stop = cur.fetchone()
                if not existing_stop:
                    raise NotFoundError("Delivery stop tidak ditemukan.")
                return _out(existing_stop)
            cur.execute("SELECT * FROM delivery_stops WHERE stop_id = %s FOR UPDATE", (stop_id,))
            stop = cur.fetchone()
            if not stop:
                raise NotFoundError("Delivery stop tidak ditemukan.")
            if str(stop.get("courier_id") or "") != actor_id:
                raise PermissionError_("Courier hanya dapat memperbarui stop yang ditugaskan kepadanya.")
            if str(stop["status"]) == normalized:
                raise ConflictError("Status delivery sudah sama; gunakan idempotency key sebelumnya.")
            if normalized not in _TRANSITIONS.get(str(stop["status"]), set()):
                raise ConflictError(f"Transisi {stop['status']} ke {normalized} tidak diizinkan.")
            if normalized in {"PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED"} and not stop.get("courier_id"):
                raise ConflictError("Stop belum memiliki courier.")
            timestamp_column = {"PICKED_UP": "picked_up_at", "DELIVERED": "delivered_at"}.get(normalized)
            time_sql = f", {timestamp_column} = NOW()" if timestamp_column else ""
            cur.execute(
                f"""
                UPDATE delivery_stops
                SET status = %s, proof_ref = %s, notes = CASE WHEN %s <> '' THEN notes || ' | ' || %s ELSE notes END,
                    updated_at = NOW(){time_sql}
                WHERE stop_id = %s RETURNING *
                """,
                (normalized, str(proof_ref or "").strip(), str(note or "").strip(), str(note or "").strip(), stop_id),
            )
            updated = cur.fetchone()
            cur.execute(
                """
                INSERT INTO delivery_events
                    (stop_id, status, idempotency_key, actor_id, proof_ref, note)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (stop_id, normalized, clean_key, actor_id, str(proof_ref or "").strip(), str(note or "").strip()),
            )
            return _out(updated)


def customer_tracking(*, order_id: str, customer_id: str) -> list[dict[str, Any]]:
    _check()
    rows = db.execute(
        """
        SELECT ds.*
        FROM delivery_stops ds
        JOIN orders o ON o.order_id = ds.order_id
        WHERE ds.order_id = %s AND o.customer_id = %s
        ORDER BY ds.service_date, ds.meal_slot
        """,
        (order_id, customer_id),
    )
    return [_out(row) for row in rows]
