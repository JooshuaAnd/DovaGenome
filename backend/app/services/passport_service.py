"""Passport service — Dietary Passport sebagai sumber kebenaran safety.

Satu-satunya tempat yang boleh menulis passport. Ini penting karena:
  * `customers.passport` (terstruktur) adalah sumber utama,
  * `user_profiles.dietary_profile` (string) hanya cermin untuk bot Telegram,
  * keduanya harus tetap sinkron agar pelanggan tidak melihat berbeda di web vs bot.
"""

from __future__ import annotations

from typing import Any

from app.core.domain import DAYS, normalize_allergen_code
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.enums import RestrictionCategory, SafetyLevel
from app.repositories import catalog_repo, customer_repo
from app.schemas.customer import CustomerOut, PassportIn, PassportOut
from app.schemas.order import SafetyReportOut
from app.services import safety_service
from app.utils.time import now_iso

log = get_logger("dova.passport")


def get_passport(customer_id: str) -> PassportOut:
    return customer_repo.get_passport(customer_id)


def passport_for(customer: CustomerOut | None) -> PassportOut | None:
    """
    Passport milik pelanggan, atau `None` bila belum pernah dibuat.

    Kegagalan membaca passport tidak boleh menggagalkan halaman yang memakainya —
    `/menu` dan `/order` lebih baik menampilkan menu tanpa personalisasi daripada
    error 500. Token/JWT sudah dijamin valid oleh dependency, jadi yang kita toleransi
    di sini murni masalah data (dokumen hilang atau rusak).
    """
    if customer is None:
        return None
    try:
        return customer_repo.get_passport(customer.customer_id)
    except NotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Passport customer=%s gagal dibaca: %s", customer.customer_id, type(exc).__name__
        )
        return None


def save_passport(customer_id: str, payload: PassportIn) -> PassportOut:
    """
    Simpan passport. Partial update: hanya bagian yang dikirim yang berubah.

    Validasi:
      * kode profil harus dikenal katalog (kode asing ditolak, bukan diabaikan diam-diam)
      * kategori tiap batasan mengikuti grupnya (allergy tidak boleh masuk `preferences`)
    """
    groups = {
        "allergies": RestrictionCategory.ALLERGY,
        "intolerances": RestrictionCategory.INTOLERANCE,
        "medical": RestrictionCategory.MEDICAL,
        "preferences": RestrictionCategory.PREFERENCE,
    }

    data = payload.model_dump(exclude_none=True)
    for key, category in groups.items():
        items = data.get(key)
        if not items:
            continue
        for item in items:
            item["code"] = normalize_allergen_code(item.get("code"))
            item["category"] = category
            if not item["code"]:
                raise ValidationError(f"Batasan pada '{key}' tidak memiliki kode.")
            if not item.get("label"):
                item["label"] = _label(item["code"])

    unknown = _unknown_codes(data)
    if unknown:
        raise ValidationError(
            "Profil pantangan tidak dikenal: " + ", ".join(sorted(unknown)),
            details={"known": sorted(a.code for a in catalog_repo.list_allergens(include_inactive=True))},
        )

    if data.get("avoided_times") is not None:
        from app.core.domain import AVOIDED_TIME_OPTIONS

        invalid = [t for t in data["avoided_times"] if t not in AVOIDED_TIME_OPTIONS]
        if invalid:
            raise ValidationError(
                "Slot waktu tidak dikenal: " + ", ".join(invalid),
                details={"allowed": list(AVOIDED_TIME_OPTIONS)},
            )

    # Simpan hasil normalisasi, bukan `payload` asli: kode yang sudah dinormalkan
    # dan kategori yang dipaksa sesuai grupnya harus ikut ke database. Kalau
    # tidak, passport tersimpan apa adanya dan preview bisa berbeda dari safety.
    normalized = PassportIn.model_validate(data)

    saved = customer_repo.save_passport(customer_id, normalized)
    log.info(
        "passport_saved customer=%s allergies=%d intolerances=%d medical=%d preferences=%d",
        customer_id,
        len(saved.allergies), len(saved.intolerances),
        len(saved.medical), len(saved.preferences),
    )
    return saved


def _label(code: str) -> str:
    try:
        found = next(
            (a for a in catalog_repo.list_allergens(include_inactive=True) if a.code == code),
            None,
        )
    except Exception as exc:
        log.warning("Label alergen gagal dimuat: %s", type(exc).__name__)
        found = None
    return found.label if found else code


def _unknown_codes(data: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for key in ("allergies", "intolerances", "medical", "preferences"):
        for item in data.get(key) or []:
            code = str(item.get("code") or "")
            if code:
                codes.add(code)
    if not codes:
        return set()
    try:
        known = {a.code for a in catalog_repo.list_allergens(include_inactive=True)}
    except Exception as exc:
        log.warning("Daftar alergen gagal dimuat: %s", type(exc).__name__)
        return set()
    return codes - known


def preview_report(
    customer: CustomerOut, *, days: list[str] | None = None, note: str = ""
) -> SafetyReportOut:
    """
    Simulasi menu terhadap passport TANPA menyimpan apa pun.

    Dipakai frontend agar pelanggan bisa melihat dampak sebelum menyimpan.
    """
    passport = customer_repo.get_passport(customer.customer_id)
    return safety_service.build_report(
        selected_codes=[],
        passport=passport,
        schedule_days=days or list(DAYS),
        customer_note=note,
    )


def legacy_snapshot(customer: CustomerOut) -> dict[str, Any]:
    """Ringkasan passport untuk ditampilkan pada halaman ringkasan."""
    passport = customer_repo.get_passport(customer.customer_id)
    return {
        "critical_codes": passport.critical_codes,
        "critical_labels": safety_service.critical_labels(passport.critical_codes),
        "avoided_times": passport.avoided_times,
        "avoided_ingredients": passport.avoided_ingredients,
        "is_blocking": any(
            r.category in safety_service.SAFETY_CRITICAL_CATEGORIES
            for group in (passport.allergies, passport.intolerances, passport.medical)
            for r in group
        ),
        "updated_at": passport.updated_at or now_iso(),
        "level": SafetyLevel.BLOCKED.value if passport.critical_codes else SafetyLevel.SAFE.value,
    }