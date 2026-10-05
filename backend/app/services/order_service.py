"""Order service — semua aturan pemesanan ada di sini (spec §5).

Aturan yang dipindahkan dari UI/bot lama:
  * Harga selalu dari katalog paket, tidak pernah dari input klien.
  * Jadwal pesanan harus subset dari hari paket.
  * Tabrakan allergen kritis memblokir pembuatan tiket dapur.
  * Status hanya boleh maju mengikuti `STATUS_META[...]["next"]`.
  * Dietary Passport ikut tersalin ke tiket sebagai bahan rujukan dapur.
"""

from __future__ import annotations

from typing import Any

from app.core.domain import (
    AVOIDED_TIME_OPTIONS,
    CATEGORY_LABELS,
    DAYS,
    SAFETY_CRITICAL_CATEGORIES,
    normalize_allergen_code,
)
from app.core.errors import ConflictError, NotFoundError, PermissionError_, ValidationError
from app.core.logging import get_logger
from app.models.enums import OrderStatus, Role, SafetyLevel
from app.repositories import catalog_repo, customer_repo, order_repo
from app.repositories.order_repo import SCHEMA_VERSION
from app.schemas.customer import CustomerOut, PassportOut
from app.schemas.order import (
    DaySelectionIn,
    InvoiceOut,
    OrderCreateIn,
    OrderDetailOut,
    OrderOut,
    OrderSelectionOut,
    OrderUpdateIn,
    SafetyReportOut,
)
from app.services import invoice_service, safety_service
from app.utils.time import format_service_date, now_iso, service_week_dates

log = get_logger("dova.order")


# ── Validasi ────────────────────────────────────────────────────────────────
def validate_package(package_code: str, requested_days: list[str] | None) -> Any:
    """
    Pastikan paket ada & aktif, dan jadwal yang diminta masuk akal.

    Mengembalikan `PackageOut` dari katalog.
    """
    try:
        package = catalog_repo.get_package(package_code)
    except NotFoundError as exc:
        raise ValidationError(
            f"Paket '{package_code}' tidak ditemukan atau sudah tidak aktif.",
            details={"available": [p.code for p in catalog_repo.list_packages()]},
        ) from exc

    if not package.active:
        raise ValidationError(f"Paket '{package.name}' sedang tidak aktif.")

    if requested_days:
        invalid = [d for d in requested_days if d not in package.days]
        if invalid:
            raise ValidationError(
                f"Hari {', '.join(invalid)} tidak termasuk dalam paket '{package.name}'.",
                details={"package_days": package.days},
            )
    return package


def validate_allergens(codes: list[str]) -> list[str]:
    """
    Pastikan setiap kode ada di katalog.

    Mengembalikan daftar kode yang sudah dibersihkan. Kode tak dikenal
    ditolak — bukan diam-diam diabaikan, karena bisa berarti filter safety gagal.
    """
    cleaned = safety_service.normalize_codes(codes)
    if not cleaned:
        return []

    known = {a.code: a for a in catalog_repo.list_allergens(include_inactive=True)}
    unknown = [c for c in cleaned if c not in known]
    if unknown:
        raise ValidationError(
            f"Profil pantangan tidak dikenal: {', '.join(unknown)}",
            details={"known": sorted(known)},
        )
    inactive = [c for c in cleaned if not known[c].active]
    if inactive:
        raise ValidationError(
            "Profil pantangan berikut sedang tidak aktif: "
            + ", ".join(known[c].label for c in inactive)
        )
    return cleaned


def validate_selections(
    selections: list[DaySelectionIn] | None,
    package: Any,
    *,
    schedule_days: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    Ubah pilihan `{hari, menu_id}` menjadi `{hari, menu_id, nama_menu}` yang valid.

    Inilah penjaga terakhir dari ketersediaan paket: `catalog_repo.get_day_options`
    menyaring tampilan, tapi klien bisa mengirim `menu_id` apa pun. Setiap opsi
    yang tidak memenuhi salah satu dari empat syarat di bawah ditolak dengan
    bahasa manusia, bukan diam-diam diganti:
      * menunya benar-benar ada,
      * menunya masih dipublikasikan,
      * hari-nya termasuk hari paket,
      * menunya tersedia untuk paket tersebut.

    `selections` kosong tidak apa-apa: pemanggil memakai opsi utama tiap hari.
    """
    wanted_days = schedule_days or package.days

    if not selections:
        out: list[dict[str, str]] = []
        for day in wanted_days:
            options = catalog_repo.get_day_options(day, package_code=package.code)
            if not options:
                raise ValidationError(
                    f"Belum ada menu yang tersedia untuk hari {day}.",
                    details={"package_code": package.code, "hari": day},
                )
            out.append({"hari": day, "menu_id": options[0].menu_id, "nama_menu": options[0].nama_menu})
        return out

    out = []
    for item in selections:
        if item.hari not in package.days:
            raise ValidationError(
                f"Hari {item.hari} tidak termasuk dalam paket '{package.name}'.",
                details={"package_days": package.days},
            )

        try:
            menu = catalog_repo.get_menu(item.menu_id)
        except NotFoundError as exc:
            raise ValidationError(
                f"Menu untuk hari {item.hari} tidak ditemukan. Muat ulang halaman menu.",
                details={"hari": item.hari, "menu_id": item.menu_id},
            ) from exc

        if not menu.published:
            raise ValidationError(
                f"Menu '{menu.nama_menu}' untuk hari {item.hari} sudah ditutup pemesanannya.",
                details={"hari": item.hari, "menu_id": menu.menu_id},
            )
        if menu.hari != item.hari:
            raise ValidationError(
                f"Menu '{menu.nama_menu}' adalah menu hari {menu.hari}, bukan {item.hari}.",
                details={"menu_hari": menu.hari, "hari": item.hari},
            )
        if not menu.available_for(package.code):
            raise ValidationError(
                f"Menu '{menu.nama_menu}' tidak tersedia untuk paket '{package.name}'.",
                details={
                    "package_code": package.code,
                    "menu_id": menu.menu_id,
                    "available_for": menu.package_codes,
                },
            )

        out.append({"hari": item.hari, "menu_id": menu.menu_id, "nama_menu": menu.nama_menu})

    # Urut sesuai kalender layanan supaya dokumen tersimpan rapi dan timeline rapi.
    out.sort(key=lambda s: DAYS.index(s["hari"]))
    return out


def _stored_selections(resolved: list[dict[str, str]]) -> list[dict[str, str]]:
    """Buang `nama_menu` sebelum ditulis — katalog adalah sumber nama, bukan order."""
    return [{"hari": s["hari"], "menu_id": s["menu_id"]} for s in resolved]


def enrich_selections(
    stored: list[dict[str, str]], *, level_by_day: dict[str, str] | None = None
) -> list[OrderSelectionOut]:
    """
    Ubah `{hari, menu_id}` tersimpan menjadi DTO siap tampil.

    Opsi yang berubah status katalog setelah pesanan dibuat (ditarik, diganti
    nama) tetap berhasil dibaca; hanya `menu_id` yang benar-benar tidak dikenal
    yang memakai nama tersimpan, bukan membuat KDS gagal.
    """
    dates = service_week_dates([s["hari"] for s in stored])
    levels = level_by_day or {}
    out: list[OrderSelectionOut] = []
    for item in stored:
        day = item["hari"]
        try:
            menu = catalog_repo.get_menu(item["menu_id"])
        except NotFoundError:
            menu = None

        service_date = dates.get(day, "")
        level = levels.get(day, SafetyLevel.SAFE.value)
        out.append(
            OrderSelectionOut(
                hari=day,
                menu_id=item["menu_id"],
                service_date=service_date,
                date_label=format_service_date(service_date),
                nama_menu=(menu.nama_menu if menu else item.get("nama_menu", "")) or "—",
                deskripsi=menu.deskripsi if menu else "",
                allergen_labels=list(menu.allergen_labels) if menu else [],
                alat_dapur_steril=list(menu.alat_dapur_steril) if menu else [],
                level=SafetyLevel(level),
                is_recommended=level != SafetyLevel.BLOCKED.value,
            )
        )
    return out


def resolve_service_menu(order: dict[str, Any], day: str | None) -> Any:
    """
    Menu yang harus ditampilkan dapur untuk satu hari layanan.

    Pesanan yang punya pilihan menampilkan menu ITU. Pesanan lama tanpa pilihan
    memakai opsi utama hari tersebut — perilaku lama, jadi tiket lama tetap
    tampil persis seperti sebelumnya.
    """
    if not day:
        return None
    wanted = selection_map_of(order).get(day)
    if wanted:
        try:
            return catalog_repo.get_menu(wanted)
        except NotFoundError:
            log.warning(
                "menu_pilihan_tidak_ditemukan order=%s day=%s menu_id=%s",
                order.get("order_id"), day, wanted,
            )
    return catalog_repo.primary_menu_by_day().get(day)


def selection_map_of(order: dict[str, Any]) -> dict[str, str]:
    """`hari -> menu_id` dari order yang sudah dinormalisasi (atau dokumen mentah)."""
    raw = order.get("menu_selections") or []
    if raw and isinstance(raw[0], OrderSelectionOut):
        return {s.hari: s.menu_id for s in raw if isinstance(s, OrderSelectionOut)}
    return {s["hari"]: s["menu_id"] for s in raw if isinstance(s, dict)}


def _passport_context(customer: CustomerOut, apply_passport: bool) -> PassportOut | None:
    if not apply_passport:
        return None
    try:
        passport = customer_repo.get_passport(customer.customer_id)
    except NotFoundError:
        return None
    return passport if passport.structured or passport.critical_codes else passport


def build_safety_report(
    *,
    codes: list[str],
    package_days: list[str],
    schedule_days: list[str],
    passport: PassportOut | None,
    selections: dict[str, str] | None = None,
    notes: str = "",
) -> SafetyReportOut:
    return safety_service.build_report(
        selected_codes=codes,
        passport=passport,
        schedule_days=schedule_days,
        selections=selections,
        customer_note=notes,
    )


def _ticket_notes(
    codes: list[str], passport: PassportOut | None, customer_note: str
) -> str:
    """Gabungkan SOP otomatis + catatan Dai (dapur) + catatan pelanggan."""
    parts = [order_repo.build_kitchen_notes(safety_service.critical_labels(codes))]

    if passport:
        critical = [
            r for r in (*passport.allergies, *passport.intolerances, *passport.medical)
        ]
        if critical:
            breakdown = ", ".join(
                f"{CATEGORY_LABELS.get(str(r.category), r.category)}: {r.label}"
                for r in critical
            )
            parts.append(f"Dietary Passport — {breakdown}.")
        if passport.avoided_ingredients:
            parts.append("Bahan dihindari: " + ", ".join(passport.avoided_ingredients) + ".")
        if passport.medical_notes:
            parts.append(f"Catatan medis: {passport.medical_notes}")
        if passport.safety_notes:
            parts.append(f"Catatan keselamatan: {passport.safety_notes}")

    if customer_note.strip():
        parts.append(f"Catatan pelanggan: {customer_note.strip()}")

    return " ".join(parts)


# ── Create ──────────────────────────────────────────────────────────────────
def create_order(
    customer: CustomerOut, payload: OrderCreateIn
) -> OrderDetailOut:
    """
    Buat pesanan mingguan + tiket dapur.

    Setiap hari layanan yang dilayani harus punya SATU opsi menu yang dipilih.
    Bila `payload.selections` kosong, opsi utama tiap hari dipakai — ini yang
    membuat pemanggil lama (Telegram, `verify_phase2.py`) tetap bekerja.

    Ditolak bila:
      * paket tidak valid / jadwal di luar paket
      * kode pantangan tidak dikenal
      * ada tabrakan allergen kritis (`BLOCKED`)
      * menu yang dipilih tidak published / tidak tersedia untuk paket itu
    """
    package = validate_package(payload.package_code, payload.schedule_days)
    codes = validate_allergens(payload.selected_allergen_codes)

    requested_days = [
        d for d in DAYS if d in set(payload.schedule_days or package.days)
    ]
    if not requested_days:
        raise ValidationError("Pesanan harus punya minimal satu hari layanan.")

    resolved = validate_selections(
        payload.selections, package, schedule_days=requested_days
    )
    selection_map = {s["hari"]: s["menu_id"] for s in resolved}
    schedule = [s["hari"] for s in resolved]

    passport = _passport_context(customer, payload.apply_passport)
    report = build_safety_report(
        codes=codes,
        package_days=package.days,
        schedule_days=schedule,
        passport=passport,
        selections=selection_map,
        notes=payload.customer_note,
    )

    if report.level == SafetyLevel.BLOCKED:
        log.info(
            "order_rejected customer=%s reason=allergen_conflict codes=%s",
            customer.customer_id, report.critical_codes,
        )
        raise ConflictError(
            report.headline + " " + report.explanation + " " + report.guidance,
            details={
                "safety": report.model_dump(mode="json"),
                "blocked_days": [d.hari for d in report.per_day if not d.is_recommended],
            },
        )

    labels = safety_service.critical_labels(codes)
    now = now_iso()
    document: dict[str, Any] = {
        "order_id": order_repo.generate_order_id(),
        "schema_version": SCHEMA_VERSION,
        "channel": "web",
        "customer_id": customer.customer_id,
        "chat_id": None,
        "customer_name": customer.display_name or customer.username,
        "customer_contact": customer.phone,
        "package_code": package.code,
        "subscription_type": package.name,
        "schedule_days": schedule,
        "menu_selections": _stored_selections(resolved),
        "selected_allergens": codes,
        "allergen_labels": labels,
        "dietary_profile": ", ".join(labels) or "Tidak ada",
        "kitchen_notes": _ticket_notes(codes, passport, payload.customer_note),
        "customer_note": payload.customer_note.strip(),
        "delivery_address": payload.delivery_address.strip(),
        "avoided_times": (
            passport.avoided_times
            if passport and passport.avoided_times
            else _legacy_avoided_for(customer.telegram_chat_id)
        ),
        "meal_count": len(schedule),
        "status": OrderStatus.PENDING.value,
        "payment_status": "UNPAID",
        "subtotal": package.price or 0,
        "discount": 0,
        "total": package.price or 0,
        "safety_level": report.level.value,
        "status_events": [
            {
                "status": OrderStatus.PENDING.value,
                "actor": f"web:{customer.username}",
                "note": "Pesanan dibuat melalui web",
                "at": now,
                "at_wib": now,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }

    doc_id = order_repo.insert_order(document)
    order = order_repo.get_order_by_doc_id(doc_id)
    order = invoice_service.ensure_invoice_persisted(doc_id, order)

    log.info(
        "order_created order=%s customer=%s package=%s days=%d menus=%s allergens=%s total=%d",
        order["order_id"], customer.customer_id, package.code, len(schedule),
        ",".join(s["menu_id"] for s in resolved) or "-",
        ",".join(codes) or "-", order["total"],
    )
    return get_order_detail(order_id=order["order_id"], customer=customer)


def _legacy_avoided_for(chat_id: int | None) -> list[str]:
    if not chat_id:
        return []
    try:
        return customer_repo.normalize_legacy_avoided_times(
            customer_repo.get_legacy_profile(chat_id).get("avoided_times")
        )
    except Exception as exc:
        log.warning("Baca avoided_times gagal: %s", type(exc).__name__)
        return []


# ── Read ────────────────────────────────────────────────────────────────────
def _assert_visible(order: dict, customer: CustomerOut | None, *, is_staff: bool) -> None:
    """
    Otorisasi pembacaan order.

    Order lama tidak punya `customer_id`; di sana ownership dicocokkan lewat
    `chat_id`. Jangan sampai order orang lain bocor lewat tebakan ID.
    """
    if is_staff:
        return
    if customer is None:
        raise PermissionError_("Autentikasi diperlukan.")
    if order.get("customer_id") == customer.customer_id:
        return
    if (
        customer.telegram_chat_id
        and order.get("chat_id")
        and int(order["chat_id"]) == int(customer.telegram_chat_id)
    ):
        return
    raise NotFoundError("Pesanan tidak ditemukan.")


def list_orders(
    customer: CustomerOut | None = None,
    *,
    is_staff: bool = False,
    statuses: list[str] | None = None,
    limit: int = 100,
) -> list[OrderOut]:
    if is_staff:
        raw = order_repo.fetch_orders(statuses=statuses, limit=limit)
    elif customer:
        raw = order_repo.fetch_orders(
            customer_id=customer.customer_id,
            chat_id=customer.telegram_chat_id,
            statuses=statuses,
            limit=limit,
        )
    else:
        raise PermissionError_("Autentikasi diperlukan.")

    labels = _label_lookup()
    out: list[OrderOut] = []
    for order in raw:
        out.append(_to_out(order, labels))
    out.sort(key=lambda o: o.created_at, reverse=True)
    return out


def _to_out(order: dict[str, Any], labels: dict[str, str]) -> OrderOut:
    """Satu order → DTO, termasuk pilihan menu per hari."""
    enriched = dict(order)
    enriched["allergen_labels"] = [
        labels.get(normalize_allergen_code(c), c) for c in order["selected_allergens"]
    ]
    enriched["selections"] = enrich_selections(order["menu_selections"])
    return OrderOut(**enriched)


def _label_lookup() -> dict[str, str]:
    try:
        return {a.code: a.label for a in catalog_repo.list_allergens(include_inactive=True)}
    except Exception as exc:
        log.warning("Label alergen tidak dapat dimuat: %s", type(exc).__name__)
        return {}


def get_order_detail(
    order_id: str,
    *,
    customer: CustomerOut | None = None,
    is_staff: bool = False,
) -> OrderDetailOut:
    order = order_repo.get_order_by_id(order_id)
    _assert_visible(order, customer, is_staff=is_staff)

    labels = _label_lookup()
    enriched = dict(order)
    enriched["allergen_labels"] = [
        labels.get(normalize_allergen_code(c), c) for c in order["selected_allergens"]
    ]

    passport: PassportOut | None = None
    if enriched.get("customer_id"):
        try:
            passport = customer_repo.get_passport(str(enriched["customer_id"]))
        except NotFoundError:
            passport = None

    stored = order["menu_selections"]
    report = safety_service.build_report(
        selected_codes=enriched["selected_allergens"],
        passport=passport,
        schedule_days=order["schedule_days"] or list(DAYS),
        selections={s["hari"]: s["menu_id"] for s in stored} or None,
        customer_note=enriched["customer_note"],
    )

    # Safety per hari ikut menempel pada pilihan menu, supaya detail pesanan
    # menampilkan "{menu yang dipilih} — {statusnya}", bukan status hari generik.
    levels = {d.hari: d.level.value for d in report.per_day}
    enriched["selections"] = enrich_selections(stored, level_by_day=levels)

    detail = OrderDetailOut(**enriched)
    detail.safety = report
    detail.passport = passport
    detail.timeline = [
        {**event, "status_label": _status_label(str(event.get("status")))}
        for event in order_repo.fetch_status_events(enriched["id"])
    ]
    detail.demo = False
    return detail


def _status_label(status: str) -> str:
    from app.core.domain import STATUS_META

    return str(STATUS_META.get(status, {}).get("label", status))


# ── Update oleh pelanggan ───────────────────────────────────────────────────
def update_order(
    order_id: str, customer: CustomerOut, payload: OrderUpdateIn
) -> OrderDetailOut:
    """Perubahan hanya boleh sebelum masuk dapur (PENDING)."""
    order = order_repo.get_order_by_id(order_id)
    _assert_visible(order, customer, is_staff=False)

    if order["status"] != OrderStatus.PENDING.value:
        raise ConflictError(
            "Pesanan sudah masuk dapur dan tidak dapat diubah. "
            "Hubungi tim kami bila perlu penyesuaian."
        )

    fields: dict[str, Any] = {}
    codes = order["selected_allergens"]
    days = order["schedule_days"]
    stored = order["menu_selections"]
    selection_map = {s["hari"]: s["menu_id"] for s in stored}
    package = catalog_repo.get_package(order["package_code"])

    if payload.selected_allergen_codes is not None:
        codes = validate_allergens(payload.selected_allergen_codes)
        fields["selected_allergens"] = codes
        fields["allergen_labels"] = safety_service.critical_labels(codes)
        fields["dietary_profile"] = ", ".join(fields["allergen_labels"]) or "Tidak ada"

    if payload.schedule_days is not None:
        package = validate_package(order["package_code"], payload.schedule_days)
        days = [d for d in DAYS if d in set(payload.schedule_days)]
        if not days:
            raise ValidationError("Pesanan harus punya minimal satu hari layanan.")
        fields["schedule_days"] = days
        fields["subscription_type"] = package.name
        fields["package_code"] = package.code
        if package.price is not None:
            fields["subtotal"] = package.price
            fields["total"] = package.price
        # Hari berubah → pilihan lama bisa saja tidak lagi sah untuk paket atau
        # paket baru. Resolve ulang agar tidak ada `menu_id` yatim di dokumen.
        if payload.selections is None:
            resolved = validate_selections(None, package, schedule_days=days)
            stored = _stored_selections(resolved)
            fields["menu_selections"] = stored
            fields["meal_count"] = len(days)
            selection_map = {s["hari"]: s["menu_id"] for s in stored}

    if payload.selections is not None:
        resolved = validate_selections(payload.selections, package, schedule_days=days)
        stored = _stored_selections(resolved)
        fields["menu_selections"] = stored
        selection_map = {s["hari"]: s["menu_id"] for s in stored}
        fields["schedule_days"] = [s["hari"] for s in stored]
        fields["meal_count"] = len(stored)
        days = fields["schedule_days"]

    if payload.customer_note is not None:
        fields["customer_note"] = payload.customer_note.strip()
    if payload.delivery_address is not None:
        fields["delivery_address"] = payload.delivery_address.strip()

    # Uji ulang keamanan setelah perubahan.
    passport: PassportOut | None = None
    if order.get("customer_id"):
        try:
            passport = customer_repo.get_passport(str(order["customer_id"]))
        except NotFoundError:
            passport = None

    report = safety_service.build_report(
        selected_codes=codes,
        passport=passport,
        schedule_days=days,
        selections=selection_map or None,
        customer_note=str(fields.get("customer_note", order["customer_note"])),
    )
    if report.level == SafetyLevel.BLOCKED:
        raise ConflictError(
            report.headline + " " + report.explanation,
            details={"blocked_days": [d.hari for d in report.per_day if not d.is_recommended]},
        )

    fields["kitchen_notes"] = _ticket_notes(
        codes, passport, str(fields.get("customer_note", order["customer_note"]))
    )

    updated = order_repo.update_fields(order["id"], fields)
    log.info("order_updated order=%s fields=%s", order_id, list(fields))
    return get_order_detail(order_id=updated["order_id"], customer=customer)


# ── Status transition (KDS + admin) ─────────────────────────────────────────
def advance_status(
    order_doc_id: str,
    new_status: str,
    *,
    role: str = Role.ADMIN.value,
    actor: str = "system",
    note: str = "",
) -> OrderDetailOut:
    """
    Pindahkan status satu tahap.

    Transisi hanya boleh mengikuti `STATUS_META[...]["next"]`. Melompat tahap
    ditolak karena bisa membuat tiket hilang dari papan. Pembatalan adalah satu
   -satunya jalan keluar dari alur normal dan hanya untuk admin.

    `role` dan `actor` sengaja dipisah: `role` menentukan hak akses, `actor`
    hanya mencatat siapa yang melakukan. Kalau keduanya disatukan, audit trail
    dan otorisasi ikut tercampur.
    """
    current = order_repo.get_order_by_doc_id(order_doc_id)
    target = str(new_status).upper()

    if target not in {s.value for s in OrderStatus}:
        raise ValidationError(f"Status tidak dikenal: {target}")

    if target == current["status"]:
        return get_order_detail(order_id=current["order_id"], is_staff=True)

    is_admin = role == Role.ADMIN.value
    if target == OrderStatus.CANCELLED.value:
        if not is_admin:
            log.warning(
                "pembatalan_ditolak order=%s oleh=%s role=%s",
                current["order_id"], actor, role,
            )
            raise PermissionError_("Hanya admin yang dapat membatalkan pesanan.")
        if not note.strip():
            raise ValidationError(
                "Pembatalan wajib disertai alasan agar bisa ditelusuri kemudian."
            )
    else:
        expected = current["next_status"]
        if expected is None:
            raise ConflictError(
                f"Pesanan berstatus {current['status']} sudah final dan tidak "
                "dapat diubah lagi."
            )
        if target != expected:
            raise ConflictError(
                f"Status harus berurutan: {current['status']} → {expected}."
            )

    order_repo.update_status(order_doc_id, target)
    order_repo.push_status_event(order_doc_id, target, actor, note)

    if target == OrderStatus.READY.value:
        log.info("order_sealed order=%s (segel anti-kontaminasi)", current["order_id"])

    if target == OrderStatus.CANCELLED.value:
        cancelled = order_repo.get_order_by_doc_id(order_doc_id)
        order_repo.update_fields(
            order_doc_id,
            {
                "kitchen_notes": _with_prefix(
                    cancelled["kitchen_notes"], "PESANAN DIBATALKAN. "
                )
            },
        )

    updated = order_repo.get_order_by_doc_id(order_doc_id)
    log.info(
        "order_status_changed order=%s %s → %s by=%s role=%s",
        updated["order_id"], current["status"], target, actor, role,
    )
    return get_order_detail(order_id=updated["order_id"], is_staff=True)


def _with_prefix(text: str, prefix: str) -> str:
    return prefix + (text or "")


# ── Timeline ────────────────────────────────────────────────────────────────
def get_invoice(order_id: str, customer: CustomerOut) -> InvoiceOut:
    """
    Invoice untuk satu pesanan milik pemanggil.

    Harga memakai nilai yang tersimpan pada order (hasil hitung saat pesanan
    dibuat dari katalog), bukan harga katalog saat ini — supaya invoice lama
    tidak berubah retroactive.
    """
    order = order_repo.get_order_by_id(order_id)
    _assert_visible(order, customer, is_staff=False)
    return invoice_service.build_invoice(order)


def get_invoice_for_staff(order_id: str) -> InvoiceOut:
    """Invoice tanpa pembatasan kepemilikan — untuk admin."""
    return invoice_service.build_invoice(order_repo.get_order_by_id(order_id))


def timeline(order_id: str) -> list[dict[str, Any]]:
    order = order_repo.get_order_by_id(order_id)
    events = order_repo.fetch_status_events(order["id"])
    return [{**e, "status_label": _status_label(str(e.get("status")))} for e in events]


def avoided_time_labels(codes: list[str]) -> list[str]:
    return [AVOIDED_TIME_OPTIONS.get(c, c) for c in codes if c]


def critical_categories() -> list[str]:
    return list(SAFETY_CRITICAL_CATEGORIES)
