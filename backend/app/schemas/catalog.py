"""Schema katalog: paket, alergen, menu mingguan."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.core.domain import DAYS, normalize_allergen_code, split_codes
from app.schemas.common import ApiModel
from app.schemas.order import MenuOptionSafetyOut


# ── Alergen ─────────────────────────────────────────────────────────────────
class AllergenOut(ApiModel):
    code: str
    label: str
    risiko: str = ""
    active: bool = True
    category: str = "allergy"


class AllergenIn(ApiModel):
    code: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=2, max_length=120)
    risiko: str = ""
    active: bool = True
    category: str = "allergy"

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str) -> str:
        v = normalize_allergen_code(v)
        if not v:
            raise ValueError("kode alergen tidak boleh kosong")
        return v


class AllergenPatch(ApiModel):
    label: str | None = Field(default=None, max_length=120)
    risiko: str | None = None
    active: bool | None = None
    category: str | None = None


# ── Paket ───────────────────────────────────────────────────────────────────
class PackageOut(ApiModel):
    code: str
    name: str
    days: list[str]
    description: str = ""
    meal_count: int = 0
    price: int | None = None
    active: bool = True


class PackageIn(ApiModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=160)
    days: list[str] = Field(min_length=1)
    description: str = ""
    price: int | None = Field(default=None, ge=0)
    active: bool = True

    @field_validator("days")
    @classmethod
    def _valid_days(cls, v: list[str]) -> list[str]:
        bad = [d for d in v if d not in DAYS]
        if bad:
            raise ValueError(f"hari tidak dikenal: {', '.join(bad)}")
        # Jaga urutan canonik dan buang duplikat.
        return [d for d in DAYS if d in set(v)]


class PackagePatch(ApiModel):
    name: str | None = Field(default=None, max_length=160)
    days: list[str] | None = None
    description: str | None = None
    price: int | None = Field(default=None, ge=0)
    active: bool | None = None


# ── Menu mingguan ───────────────────────────────────────────────────────────
class MenuIngredient(ApiModel):
    nama: str
    sumber: str = ""
    potensi_alergen: str = ""
    is_critical_allergen: bool = False


class MenuOut(ApiModel):
    """
    Satu OPSI menu pada satu hari layanan.

    Satu hari layanan bisa punya banyak opsi (`Senin` → 5 menu). `menu_id` adalah
    identitas stabil opsi itu, bukan nama hari — inilah yang membuat "pilih satu
    menu per hari" bisa ditulis dan dibaca kembali tanpa ambigu.
    """

    menu_id: str = ""
    hari: str
    nama_menu: str
    deskripsi: str = ""
    bahan_detail: list[MenuIngredient] = Field(default_factory=list)
    alat_dapur_steril: list[str] = Field(default_factory=list)
    allergen_codes: list[str] = Field(default_factory=list)
    allergen_labels: list[str] = Field(default_factory=list)
    #: Hanya `PUBLISHED` yang boleh dipesan. Absen pada dokumen lama = published.
    published: bool = True
    #: Kode paket yang boleh memilih opsi ini. Kosong = semua paket.
    package_codes: list[str] = Field(default_factory=list)
    #: Urutan pilihan di dalam satu hari (0 = utama).
    option_index: int = 0

    def available_for(self, package_code: str) -> bool:
        """Ketersediaan paket. Aturan tunggal, dipakai backend maupun UI."""
        return not self.package_codes or package_code in self.package_codes


class MenuIn(ApiModel):
    """
    Body admin untuk membuat atau mengubah satu opsi menu.

    `menu_id` opsional: kosongkan untuk membuat opsi baru, isi untuk mengubah
    opsi yang ada. Ini yang memungkinkan satu hari punya lebih dari satu menu —
    sebelumnya `_id` selalu `menu_<hari>` sehingga opsi kedua menimpa yang pertama.
    """

    menu_id: str = Field(default="", max_length=120)
    #: Diisi dari path (`/admin/menus/{hari}`), jadi body boleh mengirimnya atau
    #: tidak. Kosong di sini bukan berarti "hari mana saja" — `upsert_menu`
    #: menolaknya, karena menu tanpa hari tidak akan pernah sampai ke dapur.
    hari: str = ""
    nama_menu: str = Field(min_length=2, max_length=200)
    deskripsi: str = ""
    bahan_detail: list[MenuIngredient] = Field(default_factory=list)
    alat_dapur_steril: list[str] = Field(min_length=1)
    published: bool = True
    package_codes: list[str] = Field(default_factory=list)
    option_index: int = Field(default=0, ge=0)

    @field_validator("hari")
    @classmethod
    def _valid_day(cls, v: str) -> str:
        if v and v not in DAYS:
            raise ValueError(f"hari harus salah satu dari: {', '.join(DAYS)}")
        return v


class MenuPatch(ApiModel):
    """Partial update satu opsi menu — hanya field yang dikirim yang berubah."""

    nama_menu: str | None = Field(default=None, min_length=2, max_length=200)
    deskripsi: str | None = None
    bahan_detail: list[MenuIngredient] | None = None
    alat_dapur_steril: list[str] | None = Field(default=None, min_length=1)
    published: bool | None = None
    package_codes: list[str] | None = None
    option_index: int | None = Field(default=None, ge=0)


# ── Minggu layanan (read model untuk /menu dan /order) ──────────────────────
class DayOptionsOut(ApiModel):
    """Satu hari layanan + tanggalnya + semua opsi menunya."""

    hari: str
    service_date: str = ""
    date_label: str = ""
    is_past: bool = False
    options: list[MenuOut] = Field(default_factory=list)
    #: Satu entri per opsi, sejajar dengan `options` (index sama = menu yang sama).
    safety: list[MenuOptionSafetyOut] = Field(default_factory=list)


class ServiceWeekOut(ApiModel):
    """
    Pembacaan "menu minggu ini": hari → banyak opsi.

    Dipakai `/menu` dan langkah pemilihan harian di `/order`. Endpoint katalog
    lama (`/catalog/menus`) tetap hidup dan tidak berubah bentuknya.
    """

    week_start: str = ""
    days: list[DayOptionsOut] = Field(default_factory=list)
    #: Batasan yang dipakai untuk menghitung `safety` di respons ini.
    applied_codes: list[str] = Field(default_factory=list)
    has_passport: bool = False
    is_live: bool = True


# ── Agregat katalog ─────────────────────────────────────────────────────────
class CatalogOut(ApiModel):
    packages: list[PackageOut]
    allergens: list[AllergenOut]
    menus: list[MenuOut]
    service_days: list[str]
    is_live: bool
    source: str = "astra"


class CatalogMetaOut(ApiModel):
    service_days: list[str]
    total_packages: int
    total_allergens: int
    total_menus: int
    is_live: bool
    generated_at: str


__all__ = [
    "AllergenIn",
    "AllergenOut",
    "AllergenPatch",
    "CatalogMetaOut",
    "CatalogOut",
    "DayOptionsOut",
    "MenuIn",
    "MenuIngredient",
    "MenuOptionSafetyOut",
    "MenuOut",
    "MenuPatch",
    "PackageIn",
    "PackageOut",
    "PackagePatch",
    "ServiceWeekOut",
    "split_codes",
]
