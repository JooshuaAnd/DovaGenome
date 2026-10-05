"""Dashboard service — data untuk KDS, Admin, dan metrik.

Aturan yang tidak bisa ditawar:
  * Tidak ada data demo/fallback. Bila Astra DB mati, endpoint harus gagal
    dengan jelas, bukan menampilkan pesanan palsu ke dapur.
  * KDS hanya menampilkan label siap tampil, bukan kode internal.
  * Penghitungan "hari ini" memakai WIB.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.domain import (
    ACTIVE_STATUSES,
    CATEGORY_LABELS,
    DAYS,
    STATUS_FLOW,
    normalize_allergen_code,
)
from app.core.errors import DatabaseError
from app.core.logging import get_logger
from app.models.enums import OrderStatus
from app.repositories import catalog_repo, customer_repo, order_repo
from app.schemas.internal import (
    AdminDashboardOut,
    AdminDayScheduleOut,
    AdminKpi,
    AdminOrderRow,
    AdminScheduleOut,
    CollectionCount,
    KitchenBoardOut,
    KitchenTicketOut,
)
from app.schemas.order import OrderOut
from app.services import order_service, safety_service
from app.utils.time import now_iso, now_wib

log = get_logger("dova.dashboard")


# ── Kitchen Display System ──────────────────────────────────────────────────
def kitchen_board(*, statuses: list[str] | None = None) -> KitchenBoardOut:
    """
    Papan dapur dengan kolom per status aktif.

    `statuses` default = `ACTIVE_STATUSES` (PENDING/PREPARING/READY).
    """
    wanted = [s.upper() for s in (statuses or ACTIVE_STATUSES)]
    unknown = [s for s in wanted if s not in set(ACTIVE_STATUSES)]
    if unknown:
        raise DatabaseError(f"Status tidak valid untuk papan dapur: {', '.join(unknown)}")

    orders = order_repo.fetch_orders(statuses=wanted, limit=300)
    labels = _label_lookup()

    columns: dict[str, list[KitchenTicketOut]] = {s: [] for s in wanted}
    critical_count = 0

    for order in orders:
        critical = [
            labels.get(normalize_allergen_code(c), c)
            for c in order["selected_allergens"]
        ]
        is_critical = bool(order["selected_allergens"])
        if is_critical:
            critical_count += 1

        day = order["service_day"]
        # Menu yang ditampilkan adalah menu yang DIPILIH pelanggan untuk hari itu.
        # Order lama tanpa pilihan tetap memakai opsi utama, seperti sebelumnya.
        menu = order_service.resolve_service_menu(order, day)

        # Mulai dari OrderOut supaya tiket selalu punya field yang sama dengan
        # respons order; field KDS menimpa nilai yang kurang relevan.
        fields = OrderOut(**{**order, "selections": []}).model_dump()
        fields.update(
            critical_allergens=critical,
            allergen_labels=critical,
            is_critical=is_critical,
            safety_banner=_banner(order, critical, menu),
            equipment_notes=list(menu.alat_dapur_steril) if menu else [],
            menu_ingredients=[i.nama for i in menu.bahan_detail] if menu else [],
            service_menu=menu.nama_menu if menu else "",
        )
        ticket = KitchenTicketOut(**fields)
        columns.setdefault(order["status"], []).append(ticket)

    # Urutkan dalam kolom: tiket dengan pantangan allergen lebih dulu, lalu
    # yang paling lama menunggu.
    for tickets in columns.values():
        tickets.sort(key=lambda t: (t.is_critical, -int(t.elapsed_minutes or 0)), reverse=True)

    counts = {s: len(columns.get(s, [])) for s in columns}
    return KitchenBoardOut(
        columns=columns,
        counts=counts,
        critical_count=critical_count,
        total_active=sum(counts.values()),
        fetched_at=now_iso(),
        demo=False,
    )


def _banner(order: dict[str, Any], critical: list[str], menu: Any) -> str:
    """Satu kalimat yang bisa dibaca cepat dari jauh di layar dapur."""
    if not critical:
        return "PROTOKOL STERIL STANDAR"
    day = order["service_day"] or "hari layanan"
    menu_name = getattr(menu, "nama_menu", "") or "menu"
    return f"PROTOKOL WAJIB · {day} · {menu_name} · pisahkan alat untuk " + ", ".join(critical)


def _label_lookup() -> dict[str, str]:
    try:
        return {a.code: a.label for a in catalog_repo.list_allergens(include_inactive=True)}
    except Exception as exc:
        log.warning("Label alergen gagal dimuat: %s", type(exc).__name__)
        return {}


def _menu_lookup() -> dict[str, Any]:
    """
    Opsi utama per hari — dipakai rekap admin yang tidak menampilkan pilihan
    per pelanggan. KDS memakai `order_service.resolve_service_menu` supaya
    yang tampil adalah menu yang benar-benar dipesan.
    """
    try:
        return catalog_repo.primary_menu_by_day()
    except Exception as exc:
        log.warning("Menu gagal dimuat: %s", type(exc).__name__)
        return {}


# ── Admin dashboard ──────────────────────────────────────────────────────────
def admin_dashboard() -> AdminDashboardOut:
    orders = order_repo.fetch_orders(limit=500)
    today = now_wib().date()

    by_status: dict[str, int] = {s: 0 for s in STATUS_FLOW + ["CANCELLED"]}
    completed_today = cancelled_today = 0
    waits: list[int] = []
    package_counts: dict[str, int] = {}
    restriction_counts: dict[str, int] = {}
    safety_alerts = 0
    oldest = 0

    labels = _label_lookup()
    for order in orders:
        status = order["status"]
        by_status[status] = by_status.get(status, 0) + 1
        package_counts[order["subscription_type"]] = package_counts.get(order["subscription_type"], 0) + 1

        for code in order["selected_allergens"]:
            clean = normalize_allergen_code(code)
            label = labels.get(clean, clean)
            restriction_counts[label] = restriction_counts.get(label, 0) + 1
        if order["selected_allergens"]:
            safety_alerts += 1

        if order["status"] in ACTIVE_STATUSES:
            elapsed = int(order["elapsed_minutes"] or 0)
            waits.append(elapsed)
            oldest = max(oldest, elapsed)

        if _is_today(order["created_at"]) and status == OrderStatus.COMPLETED.value:
            completed_today += 1
        if _is_today(order["created_at"]) and status == OrderStatus.CANCELLED.value:
            cancelled_today += 1

    average_wait = int(sum(waits) / len(waits)) if waits else 0

    return AdminDashboardOut(
        generated_at=now_iso(),
        active_orders=sum(by_status.get(s, 0) for s in ACTIVE_STATUSES),
        pending_orders=by_status.get("PENDING", 0),
        preparing_orders=by_status.get("PREPARING", 0),
        packed_orders=by_status.get("READY", 0),
        # Belum ada status DELIVERING terpisah di STATUS_FLOW; "dikirim"
        # dihitung dari COMPLETED hari ini.
        delivering_orders=completed_today,
        completed_today=completed_today,
        cancelled_today=cancelled_today,
        safety_alerts=safety_alerts,
        average_wait_minutes=average_wait,
        oldest_ticket_minutes=oldest,
        total_customers=customer_repo.count_customers(),
        verified_customers=customer_repo.count_customers(verified_only=True),
        orders_by_package=_top(package_counts),
        orders_by_restriction=_top(restriction_counts),
        orders_by_status=[{"status": s, "label": _status_label(s), "count": by_status.get(s, 0)} for s in STATUS_FLOW + ["CANCELLED"]],
        weekly_trend=weekly_trend(),
        demo=False,
    )


def _status_label(status: str) -> str:
    from app.core.domain import STATUS_META

    return str(STATUS_META.get(status, {}).get("label", status))


def _top(counts: dict[str, int], *, limit: int = 8) -> list[dict[str, Any]]:
    return [
        {"label": label, "count": count, "key": label}
        for label, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    ]


def _is_today(value: str) -> bool:
    try:
        return bool(value) and value[:10] == now_wib().date().isoformat()
    except Exception:
        return False


def weekly_trend(*, days: int = 7) -> list[dict[str, Any]]:
    """Tren jumlah pesanan per hari (WIB) untuk sparkline admin."""
    today = now_wib().date()
    buckets: dict[str, dict[str, Any]] = {}
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        buckets[day.isoformat()] = {"date": day.isoformat(), "label": day.strftime("%a"), "count": 0}

    for order in order_repo.fetch_orders(limit=1000):
        key = str(order["created_at"] or "")[:10]
        bucket = buckets.get(key)
        if bucket is not None:
            bucket["count"] += 1

    return list(buckets.values())


def admin_schedule() -> AdminScheduleOut:
    """Rekap pesanan per hari layanan + menu yang dipakai dapur."""
    orders = order_repo.fetch_orders(limit=500)
    labels = _label_lookup()
    menus = _menu_lookup()
    options_by_day = catalog_repo.menus_by_day()
    today_name = order_repo.today_name()

    rows: list[AdminDayScheduleOut] = []
    for day in DAYS:
        menu = menus.get(day)
        day_orders = [o for o in orders if day in o["schedule_days"]]

        list_rows = [
            AdminOrderRow(
                id=o["id"],
                order_id=o["order_id"],
                customer_name=o["customer_name"],
                customer_id=o["customer_id"],
                subscription_type=o["subscription_type"],
                status=o["status"],
                allergen_labels=[
                    labels.get(normalize_allergen_code(c), c) for c in o["selected_allergens"]
                ],
                created_at=o["created_at"],
                elapsed_minutes=int(o["elapsed_minutes"] or 0),
                total=int(o["total"] or 0),
                payment_status=o["payment_status"],
            )
            for o in day_orders
        ]
        list_rows.sort(key=lambda r: (bool(r.allergen_labels), r.created_at), reverse=True)

        options = options_by_day.get(day) or []
        chosen: dict[str, str] = {}
        for o in day_orders:
            wanted = order_service.selection_map_of(o).get(day)
            if not wanted:
                continue
            resolved = order_service.resolve_service_menu(o, day)
            if resolved is not None:
                chosen[o["order_id"]] = resolved.nama_menu

        rows.append(
            AdminDayScheduleOut(
                hari=day,
                nama_menu=getattr(menu, "nama_menu", "") or "Menu belum dipublikasikan",
                deskripsi=getattr(menu, "deskripsi", "") or "",
                order_count=len(list_rows),
                orders=list_rows,
                flagged_count=sum(1 for r in list_rows if r.allergen_labels),
                alat_dapur_steril=list(getattr(menu, "alat_dapur_steril", []) or []),
                is_today=day == today_name,
                option_count=len(options),
                option_names=[m.nama_menu for m in options],
                chosen_menus=chosen,
            )
        )

    return AdminScheduleOut(
        days=rows,
        is_service_day=today_name is not None,
        generated_at=now_iso(),
    )


def kpi_cards() -> list[AdminKpi]:
    """Kartu KPI ringkas untuk dashboard admin."""
    data = admin_dashboard()
    return [
        AdminKpi(key="active", label="Pesanan Aktif", value=data.active_orders, note="PENDING + PREPARING + READY", tone="info"),
        AdminKpi(key="pending", label="Menunggu Dimasak", value=data.pending_orders, tone="warning"),
        AdminKpi(key="preparing", label="Sedang Dimasak", value=data.preparing_orders, tone="info"),
        AdminKpi(key="ready", label="Siap Dikirim", value=data.packed_orders, tone="success"),
        AdminKpi(key="safety", label="Pesanan Bernuansa Alergi", value=data.safety_alerts, note="Perlu protokol steril", tone="danger"),
        AdminKpi(key="wait", label="Rata-rata Tunggu (menit)", value=data.average_wait_minutes),
        AdminKpi(key="oldest", label="Tiket Paling Lama", value=data.oldest_ticket_minutes, note="menit", tone="warning"),
        AdminKpi(key="customers", label="Pelanggan", value=data.total_customers, note=f"{data.verified_customers} tertaut Telegram"),
    ]


# ── System ───────────────────────────────────────────────────────────────────
def system_status(*, collections: list[CollectionCount] | None = None) -> dict[str, Any]:
    """Ringkasan koneksi untuk halaman admin — tanpa membocorkan credential."""
    from app.core.config import settings

    return {
        "credentials": settings.credential_status(),
        "collections": collections or [],
        "telegram_bot_username": settings.telegram_bot_username,
        "langflow_configured": bool(settings.langflow_flow_id),
    }


def customer_impact_labels(codes: list[str]) -> dict[str, str]:
    """Map kode → label + kategori, untuk tooltip dashboard."""
    labels = _label_lookup()
    try:
        categories = {
            a.code: str(a.category) for a in catalog_repo.list_allergens(include_inactive=True)
        }
    except Exception:
        categories = {}
    return {
        normalize_allergen_code(c): CATEGORY_LABELS.get(
            categories.get(normalize_allergen_code(c), "allergy"), "Alergi"
        )
        for c in codes
        if c
    }


def critical_label_for_dashboard(codes: list[str]) -> list[str]:
    return safety_service.critical_labels(codes)