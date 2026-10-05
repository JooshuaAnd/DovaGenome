"""Safety service — mesin kecocokan allergen (spec §10).

Aturan main:
  * Alergen yang dikecualikan dietary passport dibandingkan dengan allergen yang
    benar-benar terdapat di menu.
  * Tabrakan → `BLOCKED` + penjelasan bahasa manusia, bukan sekadar warna merah.
  * Dapur hanya menampilkan label, bukan kode internal.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.domain import (
    ALLERGEN_KEYWORDS,
    DAYS,
    SAFETY_CRITICAL_CATEGORIES,
    normalize_allergen_code,
)
from app.core.logging import get_logger
from app.models.enums import RestrictionCategory, SafetyLevel
from app.repositories.catalog_repo import list_allergens, menus_by_day
from app.schemas.customer import PassportOut
from app.schemas.order import (
    DaySafetyOut,
    MenuOptionSafetyOut,
    SafetyConflict,
    SafetyReportOut,
)

log = get_logger("dova.safety")


def detect_allergy_risks(*texts: str | None) -> list[str]:
    """
    Kata kunci alergen yang muncul pada teks (port `data.detect_allergy_risks`).

    Dipakai untuk menandai catatan dapur, bukan untuk kesetiaan katalog.
    """
    blob = " ".join(t for t in texts if t).lower()
    found = [kw for kw in ALLERGEN_KEYWORDS if kw in blob]
    found.sort(key=len, reverse=True)
    seen: list[str] = []
    for kw in found:
        if not any(kw in s and s in kw for s in seen):
            seen.append(kw)
    return seen


def _label_map() -> dict[str, str]:
    try:
        return {a.code: a.label for a in list_allergens(include_inactive=True)}
    except Exception as exc:
        log.warning("Label alergen tidak dapat dimuat: %s", type(exc).__name__)
        return {}


def _category_map() -> dict[str, str]:
    try:
        return {
            a.code: str(a.category) for a in list_allergens(include_inactive=True)
        }
    except Exception as exc:
        log.warning("Kategori alergen tidak dapat dimuat: %s", type(exc).__name__)
        return {}


def _passport_restrictions(passport: PassportOut) -> list[tuple[str, str, RestrictionCategory]]:
    """Kumpulkan (code, label, category) dari tiga kelompok yang Dendang-critical."""
    out: list[tuple[str, str, RestrictionCategory]] = []
    for group in (passport.allergies, passport.intolerances, passport.medical):
        for r in group:
            code = normalize_allergen_code(r.code)
            if code:
                out.append((code, r.label or code, r.category))
    # Preferensi TIDAK memicu penolakan menu — hanya catatan.
    for r in passport.preferences:
        code = normalize_allergen_code(r.code)
        if code:
            out.append((code, r.label or code, r.category))
    return out


class CatalogContext:
    """
    Katalog yang sudah dimuat satu kali untuk satu laporan safety.

    Tanpa ini `build_report` untuk 6 hari akan membaca Astra 6× menu + 12×
    label — cukup untuk membuat satu permintaan terasa macet.

    `menus` bernilai `hari -> daftar opsi`. Dahulu bernilai `hari -> satu menu`,
    yang membuat seluruh produk hanya bisa merepresentasikan satu menu per hari.
    """

    __slots__ = ("menus", "primary", "labels", "categories")

    def __init__(self) -> None:
        grouped: dict[str, list[Any]] = menus_by_day()
        self.menus: dict[str, list[Any]] = grouped
        self.primary: dict[str, Any] = {
            day: options[0] for day, options in grouped.items() if options
        }
        self.labels: dict[str, str] = _label_map()
        self.categories: dict[str, str] = _category_map()


def _context(ctx: CatalogContext | None) -> CatalogContext:
    return ctx if ctx is not None else CatalogContext()


def check_menu(
    day: str,
    menu: Any,
    excluded_codes: set[str],
    *,
    preference_codes: set[str] | None = None,
    catalog: CatalogContext | None = None,
) -> DaySafetyOut:
    """
    Periksa SATU opsi menu terhadap daftar kode yang dikecualikan.

    Ini implementasi tunggal dari aturan kecocokan allergen. `check_day` dan
    `build_report` sama-sama memanggilnya, sehingga tidak ada dua versi aturan
    yang bisa berbeda pendapat.
    """
    cat = _context(catalog)
    preference_codes = preference_codes or set()

    labels = cat.labels
    categories = cat.categories
    ingredient_names = [i.nama for i in menu.bahan_detail]

    conflicts: list[SafetyConflict] = []
    for code in sorted(excluded_codes & set(menu.allergen_codes)):
        category = categories.get(code, RestrictionCategory.ALLERGY.value)
        # Dapur perlu tahu BAHAN mana yang memicu, bukan cuma nama menunya.
        found_in = [
            f"{i.nama} ({i.potensi_alergen})"
            for i in menu.bahan_detail
            if i.is_critical_allergen
        ] or [menu.nama_menu]
        conflicts.append(
            SafetyConflict(
                allergen_code=code,
                allergen_label=labels.get(code, code),
                category=category,
                found_in=found_in,
                ingredient_names=ingredient_names,
                explanation=(
                    f"Menu hari {day} memuat {labels.get(code, code)}. "
                    "Bahan ini teridentifikasi pada detail bahan dan ditandai "
                    "alergen kritis oleh dapur."
                ),
            )
        )

    critical_conflicts = [
        c for c in conflicts if c.category in SAFETY_CRITICAL_CATEGORIES
    ]
    soft_conflicts = [c for c in conflicts if c.category not in SAFETY_CRITICAL_CATEGORIES]
    preference_hits = sorted(preference_codes & set(menu.allergen_codes))

    if critical_conflicts:
        level = SafetyLevel.BLOCKED
        names = ", ".join(c.allergen_label for c in critical_conflicts)
        headline = f"Menu {day} tidak direkomendasikan untuk profil Anda."
        explanation = (
            f"{menu.nama_menu} mengandung {names}, sedangkan Dietary Passport Anda "
            f"mengecualikan {', '.join(c.allergen_label for c in critical_conflicts)}."
        )
        guidance = (
            "Pilih menu lain untuk hari ini, atau minta dapur menyiapkan menu "
            "alternatif dengan protokol steril terpisah. Jangan konsumsi hidangan "
            "ini bila alergi Anda berat."
        )
        recommended = False
    elif soft_conflicts or preference_hits:
        level = SafetyLevel.CAUTION
        names = ", ".join(
            [c.allergen_label for c in soft_conflicts] + preference_hits
        )
        headline = f"Menu {day} perlu diperhatikan."
        explanation = f"{menu.nama_menu} mengandung {names}."
        guidance = (
            "Batasan ini bukan alergi berat, namun perlu dicatat ke dapur agar "
            "penyiapan tetap disesuaikan."
        )
        recommended = True
    else:
        level = SafetyLevel.SAFE
        headline = f"{menu.nama_menu} cocok dengan preferensi Anda."
        explanation = "Tidak ada allergen yang dikecualikan passport ditemukan di menu ini."
        guidance = "Protokol steril standar tetap berlaku."
        recommended = True

    return DaySafetyOut(
        hari=day,
        menu_id=menu.menu_id,
        nama_menu=menu.nama_menu,
        deskripsi=menu.deskripsi,
        allergen_codes=menu.allergen_codes,
        allergen_labels=menu.allergen_labels,
        alat_dapur_steril=menu.alat_dapur_steril,
        level=level,
        conflicts=conflicts,
        headline=headline,
        explanation=explanation,
        guidance=guidance,
        is_recommended=recommended,
    )


def check_day(
    day: str,
    excluded_codes: set[str],
    *,
    preference_codes: set[str] | None = None,
    ctx: CatalogContext | None = None,
) -> DaySafetyOut:
    """
    Periksa satu hari terhadap daftar kode yang dikecualikan.

    Reports the day's PRIMARY option, kept for the endpoints that do not yet carry
    a customer selection (`/catalog/safety`, passport preview, Telegram). Orders
    that have a real selection are checked against THAT menu via `check_menu`.
    """
    catalog = _context(ctx)
    options = catalog.menus.get(day) or []
    if not options:
        return DaySafetyOut(
            hari=day,
            nama_menu="Menu belum dipublikasikan",
            level=SafetyLevel.SAFE,
            headline="Menu hari ini belum tersedia.",
            guidance="Tim dapur belum memasukkan menu untuk hari ini.",
            is_recommended=True,
        )

    return check_menu(
        day, options[0], excluded_codes, preference_codes=preference_codes, catalog=catalog
    )


def check_options(
    options: list[Any],
    day: str,
    excluded_codes: set[str],
    *,
    preference_codes: set[str] | None = None,
    ctx: CatalogContext | None = None,
) -> list[MenuOptionSafetyOut]:
    """
    Periksa daftar opsi yang sudah difilter, lalu kembalikan safety sejajar.

    Keselarasan dijamin oleh urutan, bukan `menu_id`. Pemanggil yang sudah menyaring
    opsi (mis. berdasarkan ketersediaan paket) harus memakai daftar yang sama persis;
    kalau tidak, `options` dan `safety` akan bergeser dan status keamanan menempel ke
    menu yang salah.
    """
    catalog = _context(ctx)
    out: list[MenuOptionSafetyOut] = []
    for menu in options:
        result = check_menu(
            day, menu, excluded_codes, preference_codes=preference_codes, catalog=catalog
        )
        out.append(
            MenuOptionSafetyOut(
                menu_id=menu.menu_id,
                level=result.level,
                headline=result.headline,
                explanation=result.explanation,
                guidance=result.guidance,
                is_recommended=result.is_recommended,
                conflicts=result.conflicts,
            )
        )
    return out


def check_day_options(
    day: str,
    excluded_codes: set[str],
    *,
    preference_codes: set[str] | None = None,
    ctx: CatalogContext | None = None,
) -> list[MenuOptionSafetyOut]:
    """Semua opsi satu hari dari katalog — inilah yang dibutuhkan layar pemilihan menu."""
    catalog = _context(ctx)
    return check_options(
        catalog.menus.get(day) or [],
        day,
        excluded_codes,
        preference_codes=preference_codes,
        ctx=catalog,
    )


def check_selected(
    selections: dict[str, str],
    excluded_codes: set[str],
    *,
    preference_codes: set[str] | None = None,
    ctx: CatalogContext | None = None,
) -> list[DaySafetyOut]:
    """
    Periksa menu yang benar-benar DIPILIH pelanggan untuk tiap hari.

    `selections` memetakan `hari -> menu_id`. Hari yang menunjuk `menu_id` yang
    sudah tidak dipublikasikan jatuh kembali ke opsi utama supaya laporan tetap
    bisa dibaca tanpa melempar error.
    """
    catalog = _context(ctx)
    out: list[DaySafetyOut] = []
    for day in DAYS:
        if day not in selections:
            continue
        options = catalog.menus.get(day) or []
        wanted = selections[day]
        chosen = next((m for m in options if m.menu_id == wanted), None) or (
            options[0] if options else None
        )
        if chosen is None:
            out.append(
                DaySafetyOut(
                    hari=day,
                    menu_id=wanted,
                    nama_menu="Menu belum dipublikasikan",
                    level=SafetyLevel.SAFE,
                    headline="Menu hari ini belum tersedia.",
                    guidance="Tim dapur belum memasukkan menu untuk hari ini.",
                    is_recommended=True,
                )
            )
            continue
        out.append(
            check_menu(
                day, chosen, excluded_codes,
                preference_codes=preference_codes, catalog=catalog,
            )
        )
    return out


def resolve_exclusions(
    *,
    selected_codes: list[str] | None = None,
    passport: PassportOut | None = None,
) -> tuple[set[str], set[str], set[str]]:
    """
    Bagi kode batasan menjadi tiga kelompok.

    Mengembalikan `(excluded, preference, all_codes)`. Dipisah di sini supaya
    `/catalog/menus/week`, `/catalog/safety`, dan pembuatan pesawan menghitung
    "menu ini aman atau tidak" dari sumber yang sama.
    """
    explicit = {normalize_allergen_code(c) for c in (selected_codes or [])}
    explicit.discard("")

    passport_critical: set[str] = set()
    passport_preference: set[str] = set()
    if passport:
        for code, _label, category in _passport_restrictions(passport):
            if category in SAFETY_CRITICAL_CATEGORIES:
                passport_critical.add(code)
            else:
                passport_preference.add(code)

    excluded = explicit | passport_critical
    preference = passport_preference - excluded
    return excluded, preference, excluded | preference


def _rollup(
    per_day: list[DaySafetyOut], *, excluded: set[str]
) -> SafetyReportOut:
    """
    Naikkan hasil per-hari menjadi satu level + narasi.

    Dipisah dari `build_report` supaya perhitungannya tidak pernah diulang di
    tempat lain.
    """
    labels = _label_map()
    blocked = [d for d in per_day if d.level == SafetyLevel.BLOCKED]
    caution = [d for d in per_day if d.level == SafetyLevel.CAUTION]

    menu_contains: list[str] = []
    for d in per_day:
        for label in d.allergen_labels:
            if label not in menu_contains:
                menu_contains.append(label)

    if blocked:
        level = SafetyLevel.BLOCKED
        headline = (
            f"{len(blocked)} dari {len(per_day)} hari tidak cocok dengan preferensi Anda."
        )
        explanation = (
            "Menu pada hari berikut mengandung bahan yang Anda hindari: "
            + ", ".join(sorted({d.hari for d in blocked}))
            + "."
        )
        guidance = (
            "Ganti paket/hari, atau minta alternatif menu dari tim dapur. "
            "Sistem tidak akan mengirim tiket dapur selama masih ada tabrakan kritis."
        )
    elif caution:
        level = SafetyLevel.CAUTION
        headline = f"{len(caution)} hari perlu perhatian lebih."
        explanation = "Tidak ada bahan kritis, ada batasan ringan atau preferensi."
        guidance = "Sampaikan catatan ini ke dapur saat konfirmasi."
    else:
        level = SafetyLevel.SAFE
        headline = "Seluruh menu yang dipilih aman untuk preferensi Anda."
        explanation = (
            f"{len(per_day)} hari diperiksa terhadap "
            f"{len(excluded)} batasan yang tercatat."
        )
        guidance = "Protokol steril per pesanan tetap diterapkan di dapur."

    return SafetyReportOut(
        level=level,
        is_recommended=not blocked,
        headline=headline,
        explanation=explanation,
        guidance=guidance,
        menu_contains=menu_contains,
        passport_excludes=[labels.get(c, c) for c in sorted(excluded)],
        conflicts=[c for d in per_day for c in d.conflicts],
        per_day=per_day,
        critical_codes=sorted(excluded),
        keywords_detected=[],
    )


def build_report(
    *,
    selected_codes: list[str] | None = None,
    passport: PassportOut | None = None,
    schedule_days: list[str] | None = None,
    selections: dict[str, str] | None = None,
    kitchen_notes: str = "",
    customer_note: str = "",
    ctx: CatalogContext | None = None,
) -> SafetyReportOut:
    """
    Laporan kecocokan lengkap untuk satu rencana pesanan.

    Sumber batasan = kode terpilih pesanan ∪ (kalau ada passport) kode
    kritisnya. Bila `selections` diisi, setiap hari diperiksa terhadap menu yang
    DIPILIH; tanpa itu dipakai opsi utama hari tersebut.
    """
    ctx = _context(ctx)
    excluded, preference, _all = resolve_exclusions(
        selected_codes=selected_codes, passport=passport
    )

    days = [d for d in (schedule_days or list(DAYS)) if d in DAYS]
    if selections:
        per_day = check_selected(
            selections, excluded, preference_codes=preference, ctx=ctx
        )
    else:
        per_day = [
            check_day(d, excluded, preference_codes=preference, ctx=ctx) for d in days
        ]

    report = _rollup(per_day, excluded=excluded)
    report.keywords_detected = detect_allergy_risks(kitchen_notes, customer_note)
    return report


def safety_summary_text(report: SafetyReportOut) -> str:
    """Ringkasan satu paragraf untuk invoice & tiket dapur."""
    if report.level == SafetyLevel.BLOCKED:
        head = f"PERINGATAN: {len(report.conflicts)} tabrakan allergen belum terselesaikan."
    elif report.level == SafetyLevel.CAUTION:
        head = "Catatan: menu lolos dari alergen kritis, ada batasan ringan."
    else:
        head = "Aman: tidak ada allergen yang dikecualikan passport pada menu terpilih."

    parts = [head]
    if report.passport_excludes:
        parts.append("Batasan: " + ", ".join(report.passport_excludes) + ".")
    if report.menu_contains:
        parts.append("Menu memuat: " + ", ".join(report.menu_contains) + ".")
    parts.append(report.guidance)
    return " ".join(parts)


def critical_labels(codes: list[str]) -> list[str]:
    """Label siap tampil untuk daftar kode alergen (dipakai KDS & invoice)."""
    labels = _label_map()
    return [labels.get(normalize_allergen_code(c), c) for c in codes if c]


def normalize_codes(raw: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in raw or []:
        code = normalize_allergen_code(value)
        if code and code not in out:
            out.append(code)
    return out


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
