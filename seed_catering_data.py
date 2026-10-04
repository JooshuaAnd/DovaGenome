"""
DovaGenome — Seed Data Awal ke Astra DB
Jalankan sekali: python seed_catering_data.py

Mengisi 3 collection:
  • catering_packages     — paket katering mingguan
  • allergen_definitions  — definisi opsi alergen/pantangan
  • catering_menus        — menu harian + bahan detail + protokol alat steril
"""

import os
from dotenv import load_dotenv
from astrapy import DataAPIClient

load_dotenv()

ASTRA_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_TOKEN    = os.getenv("ASTRA_DB_APPLICATION_TOKEN")

if not ASTRA_ENDPOINT or not ASTRA_TOKEN:
    raise RuntimeError(
        "ASTRA_DB_API_ENDPOINT atau ASTRA_DB_APPLICATION_TOKEN belum diisi di .env"
    )

client = DataAPIClient(ASTRA_TOKEN)
db     = client.get_database(ASTRA_ENDPOINT)

# Pastikan semua collection tersedia
for col in ("catering_packages", "allergen_definitions", "catering_menus"):
    if col not in db.list_collection_names():
        db.create_collection(col)
        print(f"  → Collection '{col}' dibuat.")

package_col  = db.get_collection("catering_packages")
allergen_col = db.get_collection("allergen_definitions")
menu_col     = db.get_collection("catering_menus")


def upsert(collection, doc: dict):
    """Upsert berdasarkan _id — aman dijalankan berulang kali."""
    collection.find_one_and_replace(
        filter={"_id": doc["_id"]},
        replacement=doc,
        upsert=True,
    )


# ---------------------------------------------------------------------------
# 1. Paket Katering
# ---------------------------------------------------------------------------

PACKAGES = [
    {
        "_id":         "pkg_full",
        "code":        "pkg_full",
        "name":        "Full Week (Senin – Sabtu)",
        "days":        ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"],
        "description": "Catering lengkap 6 hari makan siang bersih & steril",
        "active":      True,
    },
    {
        "_id":         "pkg_workday",
        "code":        "pkg_workday",
        "name":        "Hari Kerja (Senin – Jumat)",
        "days":        ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"],
        "description": "Paket produktif bebas alergi untuk hari kerja",
        "active":      True,
    },
    {
        "_id":         "pkg_3hari",
        "code":        "pkg_3hari",
        "name":        "3 Hari Pilihan (Sen, Rab, Jum)",
        "days":        ["Senin", "Rabu", "Jumat"],
        "description": "Paket rotasi ringan 3 kali seminggu",
        "active":      True,
    },
]

# ---------------------------------------------------------------------------
# 2. Definisi Alergen
# ---------------------------------------------------------------------------

ALLERGENS = [
    {
        "_id":    "alg_gluten",
        "code":   "alg_gluten",
        "label":  "Bebas Gluten",
        "risiko": "Gandum, Kecap Kedelai Biasa, Tepung Terigu",
        "active": True,
    },
    {
        "_id":    "alg_seafood",
        "code":   "alg_seafood",
        "label":  "Bebas Seafood",
        "risiko": "Udang, Kepiting, Kerang, Terasi, Minyak Ikan",
        "active": True,
    },
    {
        "_id":    "alg_kacang",
        "code":   "alg_kacang",
        "label":  "Bebas Kacang Tanah",
        "risiko": "Kacang Tanah, Selai Kacang, Minyak Kacang",
        "active": True,
    },
    {
        "_id":    "alg_dairy",
        "code":   "alg_dairy",
        "label":  "Bebas Susu/Laktosa",
        "risiko": "Butter, Keju, Krim Susu Sapi",
        "active": True,
    },
    {
        "_id":    "alg_telur",
        "code":   "alg_telur",
        "label":  "Bebas Telur",
        "risiko": "Putih/Kuning Telur, Mayones, Emulsifier",
        "active": True,
    },
    {
        "_id":    "alg_kedelai",
        "code":   "alg_kedelai",
        "label":  "Bebas Kedelai/Terasi",
        "risiko": "Tahu, Tempe, Kecap Asin, Terasi Udang",
        "active": True,
    },
]

# ---------------------------------------------------------------------------
# 3. Menu Mingguan (bahan detail + alat dapur steril)
# ---------------------------------------------------------------------------

WEEKLY_MENUS = [
    {
        "_id":       "menu_senin",
        "hari":      "Senin",
        "nama_menu": "Ayam Panggang Rosemary & Ubi Panggang",
        "deskripsi": "Ayam fillet panggang rempah herba segar tanpa tepung",
        "bahan_detail": [
            {"nama": "Fillet Dada Ayam",            "sumber": "Organik segar",               "potensi_alergen": "Aman"},
            {"nama": "Rosemary & Oregano",           "sumber": "Herba segar",                 "potensi_alergen": "Aman"},
            {"nama": "Minyak Zaitun Extra Virgin",   "sumber": "Cold-pressed",                "potensi_alergen": "Aman"},
            {"nama": "Garam Laut & Lada Hitam",      "sumber": "Murni tanpa filler",          "potensi_alergen": "Aman"},
            {"nama": "Ubi Madu",                     "sumber": "Lokal panggang",              "potensi_alergen": "Bebas Gluten"},
        ],
        "alat_dapur_steril": [
            "Oven Station 1 (Khusus Non-Gluten)",
            "Talenan Polimer Hijau #1 (Khusus Daging Unggas Steril)",
            "Pisau Stainless Steel Grade 316 (Bebas Kontaminasi Seafood/Kacang)",
        ],
    },
    {
        "_id":       "menu_selasa",
        "hari":      "Selasa",
        "nama_menu": "Sup Daging Sapi Jamur Rempah",
        "deskripsi": "Kaldu sapi rebusan lambat 12 jam dengan jamur tiram dan rempah lokal",
        "bahan_detail": [
            {"nama": "Daging Sapi Sandung Lamur",        "sumber": "Lokal grass-fed",                    "potensi_alergen": "Aman"},
            {"nama": "Kaldu Tulang Sapi Slow-cooked",    "sumber": "Rebusan murni tanpa MSG/kecap",       "potensi_alergen": "Aman"},
            {"nama": "Jamur Tiram & Kancing",            "sumber": "Budidaya higienis",                  "potensi_alergen": "Aman"},
            {"nama": "Wortel & Daun Bawang",             "sumber": "Sayur hidroponik",                   "potensi_alergen": "Aman"},
        ],
        "alat_dapur_steril": [
            "Stock Pot Stainless Steel #3 (Khusus Kaldu Non-Seafood)",
            "Sendok Sayur Stainless Khusus Daging",
            "Talenan Kuning #2 (Khusus Sayur Steril)",
        ],
    },
    {
        "_id":       "menu_rabu",
        "hari":      "Rabu",
        "nama_menu": "Ikan Kakap Bakar Kunyit & Nasi Merah",
        "deskripsi": "Fillet kakap segar bumbu ulek kunyit lengkuas tanpa kecap komersial",
        "bahan_detail": [
            {"nama": "Fillet Kakap Putih",              "sumber": "Tangkapan laut harian",     "potensi_alergen": "⚠️ Seafood/Ikan"},
            {"nama": "Bumbu Kunyit, Bawang, Lengkuas",  "sumber": "Ulekan rempah alami",       "potensi_alergen": "Aman"},
            {"nama": "Nasi Merah Organik",              "sumber": "Beras merah pecah kulit",   "potensi_alergen": "Bebas Gluten"},
            {"nama": "Lalapan Timun & Kemangi",         "sumber": "Cuci ozon steril",          "potensi_alergen": "Aman"},
        ],
        "alat_dapur_steril": [
            "Grill Pan Biru #1 (Khusus Ikan/Seafood — Zona Terisolasi)",
            "Talenan Biru #3 (Zona Khusus Seafood)",
            "Spatula Silikon Tahan Panas Khusus Ikan",
        ],
    },
    {
        "_id":       "menu_kamis",
        "hari":      "Kamis",
        "nama_menu": "Tumis Ayam Jamur Brokoli Saus Bawang",
        "deskripsi": "Tumis ayam dan brokoli dengan saus bawang putih gurih tanpa kecap kedelai/terasi",
        "bahan_detail": [
            {"nama": "Daging Ayam Cincang",              "sumber": "Fillet ayam probiotik",                      "potensi_alergen": "Aman"},
            {"nama": "Brokoli Organik",                  "sumber": "Dicuci air garam & ozon",                   "potensi_alergen": "Aman"},
            {"nama": "Minyak Kelapa Murni",              "sumber": "Bukan minyak kacang/curah",                  "potensi_alergen": "Aman"},
            {"nama": "Saus Bawang Putih Buatan Sendiri", "sumber": "Bawang putih, kaldu ayam murni, garam",     "potensi_alergen": "Bebas Gluten & Kedelai"},
        ],
        "alat_dapur_steril": [
            "Wok Wajan Hijau #2 (Khusus Alergen-Free Zone)",
            "Talenan Putih #1 (Khusus Olahan Sayur & Ayam Bersih)",
            "Spatula Kayu Jati Steril",
        ],
    },
    {
        "_id":       "menu_jumat",
        "hari":      "Jumat",
        "nama_menu": "Salmon Fillet Lemon Herb & Kentang Kukus",
        "deskripsi": "Salmon panggang dengan perasan lemon segar dan herba dill",
        "bahan_detail": [
            {"nama": "Norwegian Salmon Fillet",     "sumber": "Grade sashimi impor",         "potensi_alergen": "⚠️ Seafood/Ikan"},
            {"nama": "Minyak Zaitun & Lemon Segar", "sumber": "Lemon segar murni",           "potensi_alergen": "Aman"},
            {"nama": "Kentang Baby Kukus",          "sumber": "Kukusan uap murni",           "potensi_alergen": "Bebas Gluten"},
            {"nama": "Buncis Baby Rebus",           "sumber": "Blanching cepat air es",      "potensi_alergen": "Aman"},
        ],
        "alat_dapur_steril": [
            "Pan Panggang Stainless Steel Khusus Salmon",
            "Talenan Biru #2 (Khusus Ikan Salmon)",
            "Kukusan Stainless Susun 2 (Bebas Uap Gluten)",
        ],
    },
    {
        "_id":       "menu_sabtu",
        "hari":      "Sabtu",
        "nama_menu": "Nasi Merah Ayam Bakar Madu Ketumbar",
        "deskripsi": "Ayam bakar karamel madu hutan dan biji ketumbar sangrai murni",
        "bahan_detail": [
            {"nama": "Ayam Kampung Potong",                  "sumber": "Segar non-suntik",                      "potensi_alergen": "Aman"},
            {"nama": "Madu Hutan Asli",                      "sumber": "Madu mentah tanpa glukosa tambahan",    "potensi_alergen": "Aman"},
            {"nama": "Biji Ketumbar & Bawang Merah Sangrai", "sumber": "Rempah asli tanpa filler",              "potensi_alergen": "Aman"},
            {"nama": "Nasi Merah Pulen",                     "sumber": "Beras lokal organik",                   "potensi_alergen": "Bebas Gluten"},
        ],
        "alat_dapur_steril": [
            "Panggangan Arang Stainless Area Unggas",
            "Kuas Silikon Khusus Bumbu Madu (Dicuci dishwasher 80°C)",
            "Talenan Polimer Hijau #2",
        ],
    },
]


# ---------------------------------------------------------------------------
# Jalankan seeding
# ---------------------------------------------------------------------------

def seed_data():
    print("\n🌱 Mulai seeding data ke Astra DB...\n")

    print("  Seeding catering_packages...")
    for doc in PACKAGES:
        upsert(package_col, doc)
    print(f"  ✓ {len(PACKAGES)} paket katering berhasil dimasukkan.\n")

    print("  Seeding allergen_definitions...")
    for doc in ALLERGENS:
        upsert(allergen_col, doc)
    print(f"  ✓ {len(ALLERGENS)} definisi alergen berhasil dimasukkan.\n")

    print("  Seeding catering_menus (dengan bahan & alat steril)...")
    for doc in WEEKLY_MENUS:
        upsert(menu_col, doc)
    print(f"  ✓ {len(WEEKLY_MENUS)} menu mingguan berhasil dimasukkan.\n")

    print("✅ Semua data berhasil diseed ke Astra DB!")
    print("   Jalankan bot Telegram dan dashboard untuk menggunakan data dinamis ini.")


if __name__ == "__main__":
    seed_data()
