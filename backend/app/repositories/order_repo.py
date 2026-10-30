"""Repository order — Postgres.

Interface method identik dengan versi Astra: normalize_order(), fetch_orders(),
get_order_by_id(), insert_order(), update_fields(), update_status(),
push_status_event(), fetch_status_events(), count_orders(),
fetch_orders_between(). Service dan router tidak berubah.

Perbedaan internal dari versi Astra:
- schedule_days disimpan di tabel order_items (hari, menu_id per baris)
- status_events disimpan di tabel order_status_events
- primary key adalah UUID (`id`), order_id publik tetap "ORD-…"
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.domain import (
    ACTIVE_STATUSES,
    AVOIDED_TIME_OPTIONS,
    DAYS,
    STATUS_META,
    TABLE_ORDER_ITEMS,
    TABLE_ORDER_STATUS_EVENTS,
    TABLE_ORDERS,
    normalize_allergen_code,
    normalize_avoided_code,
    split_codes,
)
from app.core.errors import DatabaseError, NotFoundError
from app.core.logging import get_logger
from app.repositories import supabase as db
from app.utils.time import elapsed_minutes, now_iso, now_wib, sla_level

log = get_logger("dova.repo.order")

SCHEMA_VERSION = "v3"


# ── Helper normalizer (identik dengan versi Astra) ──────────────────────────
def _clean_allergen_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = raw
    else:
        values = split_codes(raw)
    return [
        normalize_allergen_code(v)
        for v in values
        if normalize_allergen_code(v)
    ]


def _clean_avoided_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        items = raw
    else:
        items = split_codes(raw)
    out: list[str] = []
    for item in items:
        code = normalize_avoided_code(str(item or ""))
        if code in AVOIDED_TIME_OPTIONS and code not in out:
            out.append(code)
    return out


def order_customer_name(doc: dict[str, Any]) -> str:
    return str(doc.get("customer_name") or doc.get("nama") or "—")


def order_package_label(doc: dict[str, Any]) -> str:
    return str(doc.get("subscription_type") or doc.get("package") or "—")


def package_code_of(doc: dict[str, Any]) -> str:
    return str(doc.get("package_code") or doc.get("package_id") or "")


def scheduled_days(doc: dict[str, Any]) -> list[str]:
    raw = doc.get("schedule_days") or []
    if isinstance(raw, str):
        raw = [raw]
    picked = {str(d).strip() for d in raw}
    return [d for d in DAYS if d in picked]


def order_selections(doc: dict[str, Any]) -> list[dict[str, Any]]:
    raw = doc.get("menu_selections") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        day = str(item.get("hari") or "").strip()
        menu_id = str(item.get("menu_id") or "").strip()
        if day not in DAYS or not menu_id:
            continue
        try:
            quantity = max(1, int(item.get("quantity") or 1))
        except (TypeError, ValueError):
            quantity = 1
        meal_slot = str(item.get("meal_slot") or "lunch")
        if meal_slot not in {"breakfast", "lunch", "dinner"}:
            meal_slot = "lunch"
        out.append({
            "hari": day,
            "menu_id": menu_id,
            "quantity": quantity,
            "meal_slot": meal_slot,
        })
    order = {d: i for i, d in enumerate(DAYS)}
    slot_order = {"breakfast": 0, "lunch": 1, "dinner": 2}
    return sorted(out, key=lambda s: (order.get(s["hari"], 99), slot_order[s["meal_slot"]]))


def selection_map(doc: dict[str, Any]) -> dict[str, str]:
    return {s["hari"]: s["menu_id"] for s in order_selections(doc)}


def today_name() -> str | None:
    idx = now_wib().weekday()
    return DAYS[idx] if idx < 6 else None


def current_service_day(doc: dict[str, Any]) -> str | None:
    sched = scheduled_days(doc)
    if not sched:
        return None
    today = today_name()
    if today and today in sched:
        return today
    start = DAYS.index(today) if today else -1
    for day in DAYS[start + 1:]:
        if day in sched:
            return day
    return sched[-1]


def detect_schema_version(doc: dict[str, Any]) -> str:
    # Semua row baru ditulis sebagai v3
    return str(doc.get("schema_version") or "v3")


def normalize_order(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Row Postgres → dict netral yang sama dengan output versi Astra.

    `doc` sudah harus memuat `schedule_days` (list dari order_items) dan
    `menu_selections` (list dari order_items dengan menu_id terisi).
    `_enrich_order` di bawah ini menambahkan kedua field tersebut dari DB.
    """
    status = str(doc.get("status") or "PENDING").upper()
    if status not in STATUS_META:
        log.warning("Status tak dikenal pada order %s: %r → PENDING", doc.get("order_id"), status)
        status = "PENDING"
    meta = STATUS_META[status]

    allergen_codes = _clean_allergen_list(doc.get("selected_allergens") or [])
    dietary_profile = str(doc.get("dietary_profile") or "").strip()

    notes = str(doc.get("kitchen_notes") or "")
    # Bersihkan sisa prefiks ganda dari data lama yang ter-migrate
    if "alg_alg_" in notes:
        while "alg_alg_" in notes:
            notes = notes.replace("alg_alg_", "alg_")

    days = scheduled_days(doc)
    meal_count = int(doc.get("meal_count") or len(days))

    return {
        "id": str(doc.get("id") or ""),
        "order_id": str(doc.get("order_id") or "—"),
        "customer_id": doc.get("customer_id"),
        "customer_name": order_customer_name(doc),
        "chat_id": doc.get("chat_id"),
        "package_code": package_code_of(doc),
        "subscription_type": order_package_label(doc),
        "schedule_days": days,
        "menu_selections": order_selections(doc),
        "selected_allergens": allergen_codes,
        "dietary_profile": dietary_profile or "Tidak ada",
        "kitchen_notes": notes,
        "customer_note": str(doc.get("customer_note") or ""),
        "delivery_address": str(doc.get("delivery_address") or ""),
        "avoided_times": _clean_avoided_list(doc.get("avoided_times") or []),
        "meal_count": meal_count,
        "status": status,
        "status_meta": meta,
        "next_status": meta["next"],
        "next_action": meta["action"] or "",
        "created_at": str(doc.get("created_at") or ""),
        "updated_at": str(doc.get("updated_at") or ""),
        "elapsed_minutes": elapsed_minutes(doc.get("created_at")),
        "sla_level": sla_level(elapsed_minutes(doc.get("created_at"))),
        "service_day": current_service_day(doc),
        "has_safety_flags": bool(allergen_codes),
        "schema_version": detect_schema_version(doc),
        "invoice_number": str(doc.get("invoice_number") or ""),
        "subtotal": int(doc.get("subtotal") or 0),
        "discount": int(doc.get("discount") or 0),
        "total": int(doc.get("total") or 0),
        "payment_status": str(doc.get("payment_status") or "UNPAID").upper(),
        "legacy_menu_name": str(doc.get("legacy_menu_name") or ""),
    }


def _fetch_order_items(order_ids: list[str]) -> list[dict[str, Any]]:
    if not order_ids:
        return []
    try:
        rows = db.execute(
            f"""
            SELECT order_id, hari, menu_id, quantity, unit, meal_slot
            FROM {TABLE_ORDER_ITEMS}
            WHERE order_id = ANY(%s)
            ORDER BY order_id, sort_order
            """,  # noqa: S608
            (order_ids,),
        )
    except Exception:
        # Migration 017 is optional during the staged rollout. Historical
        # order rows remain lunch by definition until the column is present.
        rows = db.execute(
            f"""
            SELECT order_id, hari, menu_id, quantity, unit
            FROM {TABLE_ORDER_ITEMS}
            WHERE order_id = ANY(%s)
            ORDER BY order_id, sort_order
            """,  # noqa: S608
            (order_ids,),
        )
    for row in rows:
        row.setdefault("meal_slot", "lunch")
    return rows


def _enrich_order(row: dict[str, Any]) -> dict[str, Any]:
    """
    Tambahkan schedule_days dan menu_selections dari order_items ke dalam row.

    Setelah ini row bisa langsung dimasukkan ke normalize_order().
    """
    items = _fetch_order_items([str(row["order_id"])])
    row = dict(row)
    row["schedule_days"] = [d for d in DAYS if any(r["hari"] == d for r in items)]
    row["menu_selections"] = [
        {
            "hari": r["hari"],
            "menu_id": r["menu_id"],
            "quantity": int(r.get("quantity") or 1),
            "unit": r.get("unit") or "portion",
            "meal_slot": r.get("meal_slot") or "lunch",
        }
        for r in items
        if r.get("menu_id")
    ]
    # id UUID → string agar normalize_order tidak error
    if "id" in row and row["id"] is not None:
        row["id"] = str(row["id"])
    return row


def _enrich_orders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bulk-enrich order rows with menu selections in one query.

    The old list path called ``_enrich_order`` once per order, creating an
    N+1 query pattern that made the admin dashboard timeout on live data.
    """
    enriched = [dict(row) for row in rows]
    order_ids = [str(row.get("order_id") or "") for row in enriched if row.get("order_id")]
    items_by_order: dict[str, list[dict[str, Any]]] = {}
    if order_ids:
        items = _fetch_order_items(order_ids)
        for item in items:
            items_by_order.setdefault(str(item.get("order_id") or ""), []).append(item)

    for row in enriched:
        items = items_by_order.get(str(row.get("order_id") or ""), [])
        row["schedule_days"] = [d for d in DAYS if any(item["hari"] == d for item in items)]
        row["menu_selections"] = [
            {
                "hari": item["hari"],
                "menu_id": item["menu_id"],
                "quantity": int(item.get("quantity") or 1),
                "unit": item.get("unit") or "portion",
                "meal_slot": item.get("meal_slot") or "lunch",
            }
            for item in items
            if item.get("menu_id")
        ]
        if "id" in row and row["id"] is not None:
            row["id"] = str(row["id"])
    return enriched


# ── Query ───────────────────────────────────────────────────────────────────
def fetch_orders(
    *,
    statuses: list[str] | None = None,
    payment_statuses: list[str] | None = None,
    customer_id: str | None = None,
    chat_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if statuses:
        conditions.append("status = ANY(%s)")
        params.append(list(statuses))
    if payment_statuses:
        conditions.append("payment_status = ANY(%s)")
        params.append(list(payment_statuses))
    if customer_id:
        conditions.append("customer_id = %s")
        params.append(customer_id)
    if chat_id is not None:
        conditions.append("chat_id = %s")
        params.append(int(chat_id))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM {TABLE_ORDERS} {where} ORDER BY created_at ASC LIMIT %s"  # noqa: S608
    params.append(limit)

    try:
        rows = db.execute(sql, tuple(params))
    except Exception as exc:
        log.error("Baca orders gagal: %s: %s", type(exc).__name__, exc)
        raise DatabaseError("Gagal membaca daftar pesanan.") from exc

    orders = [normalize_order(row) for row in _enrich_orders(rows)]
    orders.sort(key=lambda o: o["created_at"] or "9999")
    return orders


def fetch_active_orders(*, limit: int = 200) -> list[dict[str, Any]]:
    return fetch_orders(statuses=ACTIVE_STATUSES, limit=limit)


def get_order_by_id(order_id: str) -> dict[str, Any]:
    """Cari berdasarkan order_id publik (mis. ORD-2026-…-ABC123)."""
    try:
        row = db.execute_one(
            f"SELECT * FROM {TABLE_ORDERS} WHERE order_id = %s",  # noqa: S608
            (order_id,),
        )
    except Exception as exc:
        log.error("Cari order %s gagal: %s: %s", order_id, type(exc).__name__, exc)
        raise DatabaseError("Gagal mencari pesanan.") from exc
    if not row:
        raise NotFoundError(f"Pesanan '{order_id}' tidak ditemukan.")
    return normalize_order(_enrich_order(row))


def get_order_by_doc_id(doc_id: str) -> dict[str, Any]:
    """Cari berdasarkan UUID internal (kolom `id`)."""
    try:
        row = db.execute_one(
            f"SELECT * FROM {TABLE_ORDERS} WHERE id = %s",  # noqa: S608
            (doc_id,),
        )
    except Exception as exc:
        log.error("Cari order doc %s gagal: %s: %s", doc_id, type(exc).__name__, exc)
        raise DatabaseError("Gagal mencari pesanan.") from exc
    if not row:
        raise NotFoundError("Pesanan tidak ditemukan.")
    return normalize_order(_enrich_order(row))


# ── Penulisan ───────────────────────────────────────────────────────────────
def generate_order_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"ORD-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def build_kitchen_notes(allergen_labels: list[str]) -> str:
    if allergen_labels:
        return (
            "PROTOKOL WAJIB: peralatan, talenan, dan zona masak terpisah. "
            f"Pantangan aktif: {', '.join(allergen_labels)}."
        )
    return "Tidak ada pantangan khusus — prosedur steril standar berlaku."


def insert_order(document: dict[str, Any]) -> str:
    """
    Simpan pesanan baru.

    `document` memakai format yang sama dengan Shape C (Astra):
    schedule_days[], menu_selections[{hari, menu_id}], dll.
    Fungsi ini memecahnya ke tabel orders + order_items.
    """
    order_id = str(document.get("order_id") or generate_order_id())
    allergens_raw = document.get("selected_allergens") or []
    avoided_raw = document.get("avoided_times") or []

    try:
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (
                        order_id, customer_id, customer_name, chat_id,
                        package_code, subscription_type,
                        selected_allergens, dietary_profile,
                        kitchen_notes, customer_note, delivery_address,
                        avoided_times, meal_count, status,
                        invoice_number, subtotal, discount, total,
                        payment_status, schema_version, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    ) RETURNING id
                    """,
                    (
                        order_id,
                        document.get("customer_id"),
                        str(document.get("customer_name") or "—"),
                        document.get("chat_id"),
                        str(document.get("package_code") or ""),
                        str(document.get("subscription_type") or ""),
                        allergens_raw if isinstance(allergens_raw, list) else split_codes(allergens_raw),
                        str(document.get("dietary_profile") or "Tidak ada"),
                        str(document.get("kitchen_notes") or ""),
                        str(document.get("customer_note") or ""),
                        str(document.get("delivery_address") or ""),
                        avoided_raw if isinstance(avoided_raw, list) else split_codes(avoided_raw),
                        int(document.get("meal_count") or 0),
                        str(document.get("status") or "PENDING").upper(),
                        str(document.get("invoice_number") or ""),
                        int(document.get("subtotal") or 0),
                        int(document.get("discount") or 0),
                        int(document.get("total") or 0),
                        str(document.get("payment_status") or "UNPAID").upper(),
                        SCHEMA_VERSION,
                        document.get("created_at") or now_iso(),
                        now_iso(),
                    ),
                )
                row = cur.fetchone()
                inserted_id = str(row["id"]) if row else ""

                # Tulis order_items dari menu_selections (ada menu_id) dan
                # schedule_days (mungkin tidak ada menu_id)
                selections: list[dict[str, Any]] = [
                    s for s in (document.get("menu_selections") or [])
                    if isinstance(s, dict)
                ]

                schedule = document.get("schedule_days") or []
                if isinstance(schedule, str):
                    schedule = split_codes(schedule)
                days_ordered = [d for d in DAYS if d in set(schedule)]

                lines = sorted(
                    selections,
                    key=lambda s: (DAYS.index(str(s.get("hari"))), str(s.get("meal_slot") or "lunch"), str(s.get("menu_id") or "")),
                )
                if not lines:
                    lines = [{"hari": hari, "menu_id": None, "quantity": 1} for hari in days_ordered]

                meal_slot_column = db.has_column(TABLE_ORDER_ITEMS, "meal_slot")
                for i, line in enumerate(lines):
                    hari = str(line.get("hari") or "")
                    if hari not in DAYS:
                        continue
                    try:
                        quantity = max(1, int(line.get("quantity") or 1))
                    except (TypeError, ValueError):
                        quantity = 1
                    if meal_slot_column:
                        cur.execute(
                            f"""
                            INSERT INTO {TABLE_ORDER_ITEMS}
                                (order_id, hari, menu_id, sort_order, quantity, unit, meal_slot)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,  # noqa: S608
                            (
                                order_id,
                                hari,
                                line.get("menu_id"),
                                i,
                                quantity,
                                str(line.get("unit") or "portion"),
                                str(line.get("meal_slot") or "lunch"),
                            ),
                        )
                    else:
                        cur.execute(
                            f"""
                            INSERT INTO {TABLE_ORDER_ITEMS}
                                (order_id, hari, menu_id, sort_order, quantity, unit)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,  # noqa: S608
                            (
                                order_id,
                                hari,
                                line.get("menu_id"),
                                i,
                                quantity,
                                str(line.get("unit") or "portion"),
                            ),
                        )
            conn.commit()
        return inserted_id
    except Exception as exc:
        log.error(
            "Insert order %s gagal: %s: %s",
            order_id, type(exc).__name__, exc,
        )
        raise DatabaseError("Gagal menyimpan pesanan ke database.") from exc


def update_fields(doc_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """$set field + updated_at, lalu kembalikan dokumen ternormalisasi."""
    if not doc_id:
        raise NotFoundError("ID pesanan tidak valid.")

    import re as _re
    selections = fields.get("menu_selections")
    safe = {
        k: v
        for k, v in fields.items()
        if k != "menu_selections" and _re.match(r"^[a-z_]+$", k)
    }
    if not safe and selections is None:
        return get_order_by_doc_id(doc_id)

    safe["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = %s" for k in safe)
    values = tuple(safe.values()) + (doc_id,)
    try:
        if selections is None:
            db.execute_write(
                f"UPDATE {TABLE_ORDERS} SET {set_clause} WHERE id = %s",  # noqa: S608
                values,
            )
        else:
            meal_slot_column = db.has_column(TABLE_ORDER_ITEMS, "meal_slot")
            with db.get_conn() as conn:
                with conn.cursor() as cur:
                    if safe:
                        cur.execute(
                            f"UPDATE {TABLE_ORDERS} SET {set_clause} WHERE id = %s",  # noqa: S608
                            values,
                        )
                    cur.execute(
                        f"SELECT order_id FROM {TABLE_ORDERS} WHERE id = %s FOR UPDATE",  # noqa: S608
                        (doc_id,),
                    )
                    order_row = cur.fetchone()
                    if not order_row:
                        raise NotFoundError("Pesanan tidak ditemukan.")
                    cur.execute(
                        f"DELETE FROM {TABLE_ORDER_ITEMS} WHERE order_id = %s",  # noqa: S608
                        (order_row["order_id"],),
                    )
                    for index, line in enumerate(selections or []):
                        if not isinstance(line, dict) or str(line.get("hari") or "") not in DAYS:
                            continue
                        params = (
                            order_row["order_id"],
                            str(line["hari"]),
                            line.get("menu_id"),
                            index,
                            max(1, int(line.get("quantity") or 1)),
                            str(line.get("unit") or "portion"),
                        )
                        if meal_slot_column:
                            cur.execute(
                                f"""
                                INSERT INTO {TABLE_ORDER_ITEMS}
                                    (order_id, hari, menu_id, sort_order, quantity, unit, meal_slot)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,  # noqa: S608
                                (*params, str(line.get("meal_slot") or "lunch")),
                            )
                        else:
                            cur.execute(
                                f"""
                                INSERT INTO {TABLE_ORDER_ITEMS}
                                    (order_id, hari, menu_id, sort_order, quantity, unit)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """,  # noqa: S608
                                params,
                            )
    except Exception as exc:
        log.error("Update order %s gagal: %s: %s", doc_id, type(exc).__name__, exc)
        raise DatabaseError("Gagal menyimpan perubahan pesanan.") from exc
    return get_order_by_doc_id(doc_id)


def update_status(doc_id: str, new_status: str) -> dict[str, Any]:
    before = get_order_by_doc_id(doc_id)
    result = update_fields(doc_id, {"status": new_status})
    log.info(
        "kitchen_status_update order=%s %s → %s",
        before["order_id"], before["status"], new_status,
    )
    return result


def push_status_event(doc_id: str, status: str, actor: str, note: str = "") -> None:
    """Tambah entri timeline — kegagalan tidak membatalkan transisi status."""
    # doc_id adalah UUID orders.id; kita perlu order_id publik untuk FK
    try:
        row = db.execute_one(
            f"SELECT order_id FROM {TABLE_ORDERS} WHERE id = %s",  # noqa: S608
            (doc_id,),
        )
        if not row:
            return
        db.execute_write(
            f"""
            INSERT INTO {TABLE_ORDER_STATUS_EVENTS} (order_id, status, actor, note)
            VALUES (%s, %s, %s, %s)
            """,  # noqa: S608
            (row["order_id"], status, actor, note),
        )
    except Exception as exc:
        log.warning("Gagal tulis timeline order %s: %s: %s", doc_id, type(exc).__name__, exc)


def fetch_status_events(doc_id: str) -> list[dict[str, Any]]:
    try:
        row = db.execute_one(
            f"SELECT order_id FROM {TABLE_ORDERS} WHERE id = %s",  # noqa: S608
            (doc_id,),
        )
        if not row:
            return []
        events = db.execute(
            f"SELECT * FROM {TABLE_ORDER_STATUS_EVENTS} WHERE order_id = %s ORDER BY created_at",  # noqa: S608
            (row["order_id"],),
        )
        return [
            {
                "status": e["status"],
                "actor": e.get("actor", ""),
                "note": e.get("note", ""),
                "at": str(e.get("created_at") or ""),
                "at_wib": "",  # diisi di layer atas bila perlu
            }
            for e in events
        ]
    except Exception as exc:
        log.warning("Baca timeline %s gagal: %s", doc_id, type(exc).__name__)
        return []


def count_orders(*, statuses: list[str] | None = None) -> int:
    try:
        if statuses:
            row = db.execute_one(
                f"SELECT COUNT(*) AS n FROM {TABLE_ORDERS} WHERE status = ANY(%s)",  # noqa: S608
                (list(statuses),),
            )
        else:
            row = db.execute_one(f"SELECT COUNT(*) AS n FROM {TABLE_ORDERS}")  # noqa: S608
        return int(row["n"]) if row else 0
    except Exception as exc:
        log.warning("Hitung order gagal: %s", type(exc).__name__)
        return 0


def fetch_orders_between(start_iso: str, end_iso: str, *, limit: int = 1000) -> list[dict[str, Any]]:
    try:
        rows = db.execute(
            f"""
            SELECT * FROM {TABLE_ORDERS}
            WHERE created_at >= %s AND created_at < %s
            ORDER BY created_at ASC
            LIMIT %s
            """,  # noqa: S608
            (start_iso, end_iso, limit),
        )
    except Exception as exc:
        log.warning("Fetch rentang order gagal: %s", type(exc).__name__)
        return []
    return [normalize_order(row) for row in _enrich_orders(rows)]
