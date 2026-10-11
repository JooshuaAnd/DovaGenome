"""
DovaGenome — Seed Data Awal ke Supabase (Postgres)
Jalankan sekali: python seed_catering_data.py

Prasyarat: migrasi SQL sudah dijalankan.
  psql $DATABASE_URL -f supabase/migrations/001_schema.sql

Mengisi 3 tabel:
  • packages           — paket katering mingguan
  • allergens          — definisi opsi alergen/pantangan
  • menus + menu_ingredients — menu harian + bahan detail + protokol alat steril
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Tambahkan backend/ ke path supaya import app.* berfungsi bila dipanggil dari root
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import psycopg2
import psycopg2.extras


def _get_conn():
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    if not supabase_url:
        host     = os.getenv("SUPABASE_DB_API_ENDPOINT", "").strip().lstrip("https://").lstrip("http://").rstrip("/")
        password = os.getenv("SUPABASE_DB_APPLICATION_TOKEN", "").strip()
        db_name  = os.getenv("SUPABASE_DB_NAME", "postgres")
        user     = os.getenv("SUPABASE_DB_USER", "postgres")
        port     = int(os.getenv("SUPABASE_DB_PORT", "5432"))
        supabase_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    if not supabase_url or "xxxx" in supabase_url:
        raise RuntimeError(
            "SUPABASE_DB_API_ENDPOINT atau SUPABASE_DB_APPLICATION_TOKEN belum diisi di .env"
        )
    return psycopg2.connect(
        supabase_url,
        cursor_factory=psycopg2.extras.RealDictCursor,
        sslmode="require",
        connect_timeout=10,
    )


# ---------------------------------------------------------------------------
# 1. Paket Katering
# ---------------------------------------------------------------------------

PACKAGES = [
    {
        "code": "pkg_full",
        "name": "Full Week (Senin – Sabtu)",
        "days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"],
        "description": "Catering lengkap 6 hari makan siang bersih & steril",
        "active": True,
    },
    {
        "code": "pkg_workday",
        "name": "Hari Kerja (Senin – Jumat)",
        "days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"],
        "description": "Paket produktif bebas alergi untuk hari kerja",
        "active": True,
    },
    {
        "code": "pkg_3hari",
        "name": "3 Hari Pilihan (Sen, Rab, Jum)",
        "days": ["Senin", "Rabu", "Jumat"],
        "description": "Paket rotasi ringan 3 kali seminggu",
        "active": True,
    },
]

# ---------------------------------------------------------------------------
# 2. Definisi Alergen
# ---------------------------------------------------------------------------

ALLERGENS = [
    {"code": "alg_gluten",  "label": "Bebas Gluten",         "risiko": "Gandum, Kecap Kedelai Biasa, Tepung Terigu",   "active": True, "category": "allergy"},
    {"code": "alg_seafood", "label": "Bebas Seafood",         "risiko": "Udang, Kepiting, Kerang, Terasi, Minyak Ikan", "active": True, "category": "allergy"},
    {"code": "alg_kacang",  "label": "Bebas Kacang Tanah",    "risiko": "Kacang Tanah, Selai Kacang, Minyak Kacang",   "active": True, "category": "allergy"},
    {"code": "alg_dairy",   "label": "Bebas Susu/Laktosa",    "risiko": "Butter, Keju, Krim Susu Sapi",                "active": True, "category": "intolerance"},
    {"code": "alg_telur",   "label": "Bebas Telur",           "risiko": "Putih/Kuning Telur, Mayones, Emulsifier",     "active": True, "category": "allergy"},
    {"code": "alg_kedelai", "label": "Bebas Kedelai/Terasi",  "risiko": "Tahu, Tempe, Kecap Asin, Terasi Udang",       "active": True, "category": "allergy"},
]

# ---------------------------------------------------------------------------
# 3. Menu Mingguan
# ---------------------------------------------------------------------------

WEEKLY_MENUS = [
    {
        "menu_id": "menu_senin_ayam-panggang-rosemary-ubi-panggang",
        "hari": "Senin",
        "nama_menu": "Ayam Panggang Rosemary & Ubi Panggang",
        "deskripsi": "Ayam fillet panggang rempah herba segar tanpa tepung",
        "alat_dapur_steril": [
            "Oven Station 1 (Khusus Non-Gluten)",
            "Talenan Polimer Hijau #1 (Khusus Daging Unggas Steril)",
            "Pisau Stainless Steel Grade 316 (Bebas Kontaminasi Seafood/Kacang)",
        ],
        "published": True,
        "package_codes": [],
        "option_index": 0,
        "bahan_detail": [
            {"nama": "Fillet Dada Ayam",          "sumber": "Organik segar",      "potensi_alergen": "Aman"},
            {"nama": "Rosemary & Oregano",         "sumber": "Herba segar",        "potensi_alergen": "Aman"},
            {"nama": "Minyak Zaitun Extra Virgin", "sumber": "Cold-pressed",       "potensi_alergen": "Aman"},
            {"nama": "Garam Laut & Lada Hitam",    "sumber": "Murni tanpa filler", "potensi_alergen": "Aman"},
            {"nama": "Ubi Madu",                   "sumber": "Lokal panggang",     "potensi_alergen": "Bebas Gluten"},
        ],
    },
    {
        "menu_id": "menu_selasa_sup-daging-sapi-jamur-rempah",
        "hari": "Selasa",
        "nama_menu": "Sup Daging Sapi Jamur Rempah",
        "deskripsi": "Kaldu sapi rebusan lambat 12 jam dengan jamur tiram dan rempah lokal",
        "alat_dapur_steril": [
            "Stock Pot Stainless Steel #3 (Khusus Kaldu Non-Seafood)",
            "Sendok Sayur Stainless Khusus Daging",
            "Talenan Kuning #2 (Khusus Sayur Steril)",
        ],
        "published": True,
        "package_codes": [],
        "option_index": 0,
        "bahan_detail": [
            {"nama": "Daging Sapi Sandung Lamur",     "sumber": "Lokal grass-fed",              "potensi_alergen": "Aman"},
            {"nama": "Kaldu Tulang Sapi Slow-cooked", "sumber": "Rebusan murni tanpa MSG/kecap", "potensi_alergen": "Aman"},
            {"nama": "Jamur Tiram & Kancing",         "sumber": "Budidaya higienis",             "potensi_alergen": "Aman"},
            {"nama": "Wortel & Daun Bawang",          "sumber": "Sayur hidroponik",              "potensi_alergen": "Aman"},
        ],
    },
    {
        "menu_id": "menu_rabu_ikan-kakap-bakar-kunyit-nasi-merah",
        "hari": "Rabu",
        "nama_menu": "Ikan Kakap Bakar Kunyit & Nasi Merah",
        "deskripsi": "Fillet kakap segar bumbu ulek kunyit lengkuas tanpa kecap komersial",
        "alat_dapur_steril": [
            "Grill Pan Biru #1 (Khusus Ikan/Seafood — Zona Terisolasi)",
            "Talenan Biru #3 (Zona Khusus Seafood)",
            "Spatula Silikon Tahan Panas Khusus Ikan",
        ],
        "published": True,
        "package_codes": [],
        "option_index": 0,
        "bahan_detail": [
            {"nama": "Fillet Kakap Putih",             "sumber": "Tangkapan laut harian", "potensi_alergen": "⚠️ Seafood/Ikan"},
            {"nama": "Bumbu Kunyit, Bawang, Lengkuas", "sumber": "Ulekan rempah alami",   "potensi_alergen": "Aman"},
            {"nama": "Nasi Merah Organik",             "sumber": "Beras merah pecah kulit","potensi_alergen": "Bebas Gluten"},
            {"nama": "Lalapan Timun & Kemangi",        "sumber": "Cuci ozon steril",       "potensi_alergen": "Aman"},
        ],
    },
    {
        "menu_id": "menu_kamis_tumis-ayam-jamur-brokoli-saus-bawang",
        "hari": "Kamis",
        "nama_menu": "Tumis Ayam Jamur Brokoli Saus Bawang",
        "deskripsi": "Tumis ayam dan brokoli dengan saus bawang putih gurih tanpa kecap kedelai/terasi",
        "alat_dapur_steril": [
            "Wok Wajan Hijau #2 (Khusus Alergen-Free Zone)",
            "Talenan Putih #1 (Khusus Olahan Sayur & Ayam Bersih)",
            "Spatula Kayu Jati Steril",
        ],
        "published": True,
        "package_codes": [],
        "option_index": 0,
        "bahan_detail": [
            {"nama": "Daging Ayam Cincang",              "sumber": "Fillet ayam probiotik",             "potensi_alergen": "Aman"},
            {"nama": "Brokoli Organik",                  "sumber": "Dicuci air garam & ozon",           "potensi_alergen": "Aman"},
            {"nama": "Minyak Kelapa Murni",              "sumber": "Bukan minyak kacang/curah",         "potensi_alergen": "Aman"},
            {"nama": "Saus Bawang Putih Buatan Sendiri", "sumber": "Bawang putih, kaldu ayam, garam",   "potensi_alergen": "Bebas Gluten & Kedelai"},
        ],
    },
    {
        "menu_id": "menu_jumat_salmon-fillet-lemon-herb-kentang-kukus",
        "hari": "Jumat",
        "nama_menu": "Salmon Fillet Lemon Herb & Kentang Kukus",
        "deskripsi": "Salmon panggang dengan perasan lemon segar dan herba dill",
        "alat_dapur_steril": [
            "Pan Panggang Stainless Steel Khusus Salmon",
            "Talenan Biru #2 (Khusus Ikan Salmon)",
            "Kukusan Stainless Susun 2 (Bebas Uap Gluten)",
        ],
        "published": True,
        "package_codes": [],
        "option_index": 0,
        "bahan_detail": [
            {"nama": "Norwegian Salmon Fillet",     "sumber": "Grade sashimi impor", "potensi_alergen": "⚠️ Seafood/Ikan"},
            {"nama": "Minyak Zaitun & Lemon Segar", "sumber": "Lemon segar murni",   "potensi_alergen": "Aman"},
            {"nama": "Kentang Baby Kukus",          "sumber": "Kukusan uap murni",   "potensi_alergen": "Bebas Gluten"},
            {"nama": "Buncis Baby Rebus",           "sumber": "Blanching cepat air es","potensi_alergen": "Aman"},
        ],
    },
    {
        "menu_id": "menu_sabtu_nasi-merah-ayam-bakar-madu-ketumbar",
        "hari": "Sabtu",
        "nama_menu": "Nasi Merah Ayam Bakar Madu Ketumbar",
        "deskripsi": "Ayam bakar karamel madu hutan dan biji ketumbar sangrai murni",
        "alat_dapur_steril": [
            "Panggangan Arang Stainless Area Unggas",
            "Kuas Silikon Khusus Bumbu Madu (Dicuci dishwasher 80°C)",
            "Talenan Polimer Hijau #2",
        ],
        "published": True,
        "package_codes": [],
        "option_index": 0,
        "bahan_detail": [
            {"nama": "Ayam Kampung Potong",                  "sumber": "Segar non-suntik",                "potensi_alergen": "Aman"},
            {"nama": "Madu Hutan Asli",                      "sumber": "Madu mentah tanpa glukosa tambahan","potensi_alergen": "Aman"},
            {"nama": "Biji Ketumbar & Bawang Merah Sangrai", "sumber": "Rempah asli tanpa filler",        "potensi_alergen": "Aman"},
            {"nama": "Nasi Merah Pulen",                     "sumber": "Beras lokal organik",             "potensi_alergen": "Bebas Gluten"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------
def seed_data():
    print("\n🌱 Mulai seeding data ke Supabase (Postgres)...\n")

    conn = _get_conn()
    cur = conn.cursor()

    print("  Seeding packages...")
    for pkg in PACKAGES:
        cur.execute(
            """
            INSERT INTO packages (code, name, days, description, active)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                name=EXCLUDED.name, days=EXCLUDED.days,
                description=EXCLUDED.description, active=EXCLUDED.active
            """,
            (pkg["code"], pkg["name"], pkg["days"], pkg["description"], pkg["active"]),
        )
    print(f"  ✓ {len(PACKAGES)} paket katering berhasil dimasukkan.\n")

    print("  Seeding allergens...")
    for alg in ALLERGENS:
        cur.execute(
            """
            INSERT INTO allergens (code, label, risiko, active, category)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                label=EXCLUDED.label, risiko=EXCLUDED.risiko,
                active=EXCLUDED.active, category=EXCLUDED.category
            """,
            (alg["code"], alg["label"], alg["risiko"], alg["active"], alg["category"]),
        )
    print(f"  ✓ {len(ALLERGENS)} definisi alergen berhasil dimasukkan.\n")

    print("  Seeding menus + menu_ingredients...")
    for menu in WEEKLY_MENUS:
        cur.execute(
            """
            INSERT INTO menus (menu_id, hari, nama_menu, deskripsi, alat_dapur_steril,
                               published, package_codes, option_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (menu_id) DO UPDATE SET
                hari=EXCLUDED.hari, nama_menu=EXCLUDED.nama_menu,
                deskripsi=EXCLUDED.deskripsi,
                alat_dapur_steril=EXCLUDED.alat_dapur_steril,
                published=EXCLUDED.published,
                package_codes=EXCLUDED.package_codes,
                option_index=EXCLUDED.option_index
            """,
            (
                menu["menu_id"], menu["hari"], menu["nama_menu"],
                menu["deskripsi"], menu["alat_dapur_steril"],
                menu["published"], menu["package_codes"], menu["option_index"],
            ),
        )
        # Hapus bahan lama, insert ulang
        cur.execute("DELETE FROM menu_ingredients WHERE menu_id = %s", (menu["menu_id"],))
        for i, bahan in enumerate(menu["bahan_detail"]):
            pot = bahan.get("potensi_alergen", "")
            cur.execute(
                """
                INSERT INTO menu_ingredients
                    (menu_id, nama, sumber, potensi_alergen, is_critical_allergen, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    menu["menu_id"],
                    bahan["nama"],
                    bahan.get("sumber", ""),
                    pot,
                    "⚠" in pot,
                    i,
                ),
            )
    print(f"  ✓ {len(WEEKLY_MENUS)} menu mingguan berhasil dimasukkan.\n")

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Semua data berhasil diseed ke Supabase!")
    print("   Jalankan GET /api/health untuk memverifikasi koneksi dan jumlah baris.")


if __name__ == "__main__":
    seed_data()
