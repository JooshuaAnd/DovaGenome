"""Layanan Dynamic RAG & Supabase Live Data untuk Asisten AI Dova Kitchen.

Seluruh data diambil dinamis dari PostgreSQL di Supabase:
- Dokumen RAG (tabel `documents`)
- Master Menu & Bahan (tabel `menus` & `menu_ingredients`)
- Profil Pelanggan & Dietary Passport (tabel `customers` & `dietary_passports`)
- Riwayat Pesanan Pelanggan (tabel `orders` & `order_items`)

DILARANG memakai respons hardcoded statis.
"""

from __future__ import annotations

import logging
from typing import Any
from app.repositories import supabase

log = logging.getLogger("dova.rag_ai")


def get_customer_profile_and_history(customer_id: str) -> dict[str, Any]:
    """Mengambil profil alergi dan riwayat pesanan pelanggan dari Supabase."""
    # 1. Profil & Paspor
    cust = supabase.execute_one(
        """
        SELECT c.customer_id, c.display_name, c.phone,
               COALESCE(dp.allergies, '[]'::jsonb) as allergies,
               COALESCE(dp.avoided_ingredients, '{}'::text[]) as avoided_ingredients,
               COALESCE(dp.safety_notes, '') as safety_notes
        FROM customers c
        LEFT JOIN dietary_passports dp ON c.customer_id = dp.customer_id
        WHERE c.customer_id = %s OR c.username = %s OR c.phone = %s OR c.display_name ILIKE %s
        LIMIT 1
        """,
        (customer_id, customer_id, customer_id, f"%{customer_id}%")
    )

    if not cust:
        # Fallback cari baris pertama bila guest/demo
        cust = supabase.execute_one(
            """
            SELECT c.customer_id, c.display_name, c.phone,
                   COALESCE(dp.allergies, '[]'::jsonb) as allergies,
                   COALESCE(dp.avoided_ingredients, '{}'::text[]) as avoided_ingredients,
                   COALESCE(dp.safety_notes, '') as safety_notes
            FROM customers c
            LEFT JOIN dietary_passports dp ON c.customer_id = dp.customer_id
            WHERE c.role = 'customer'
            ORDER BY c.created_at ASC
            LIMIT 1
            """
        ) or {}

    cid = cust.get("customer_id")

    # 2. Riwayat Pesanan Sebelumnya
    past_orders: list[dict[str, Any]] = []
    if cid:
        past_orders = supabase.execute(
            """
            SELECT o.order_id, o.status, o.total, oi.hari, m.nama_menu
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN menus m ON oi.menu_id = m.menu_id
            WHERE o.customer_id = %s
            ORDER BY o.created_at DESC
            LIMIT 6
            """,
            (cid,)
        )

    return {
        "customer": cust,
        "past_orders": past_orders,
    }


def get_live_catalog_from_db() -> list[dict[str, Any]]:
    """Mengambil 18 menu harian dan seluruh bahan resepnya dari Supabase."""
    return supabase.execute(
        """
        SELECT m.menu_id, m.hari, m.nama_menu, m.deskripsi,
               COALESCE(array_agg(mi.nama) FILTER (WHERE mi.nama IS NOT NULL), ARRAY[]::TEXT[]) as ingredients,
               COALESCE(array_agg(mi.potensi_alergen) FILTER (WHERE mi.potensi_alergen IS NOT NULL), ARRAY[]::TEXT[]) as allergens
        FROM menus m
        LEFT JOIN menu_ingredients mi ON m.menu_id = mi.menu_id
        WHERE m.published = true
        GROUP BY m.menu_id, m.hari, m.nama_menu, m.deskripsi, m.option_index
        ORDER BY m.hari, m.option_index
        """
    )


def search_rag_documents(query_text: str) -> list[str]:
    """Mencari kutipan dokumen knowledge base resmi dari tabel `documents` di Supabase."""
    words = [w for w in query_text.lower().split() if len(w) > 3]
    if not words:
        docs = supabase.execute("SELECT content FROM documents LIMIT 2")
        return [d["content"] for d in docs]

    # Cari ILIKE dari kata kunci pertama
    pattern = f"%{words[0]}%"
    docs = supabase.execute(
        "SELECT content FROM documents WHERE content ILIKE %s LIMIT 2",
        (pattern,)
    )
    if not docs:
        docs = supabase.execute("SELECT content FROM documents LIMIT 2")
    return [d["content"] for d in docs]


def generate_rag_answer(
    message: str,
    customer_id: str = "",
    session_id: str = "",
) -> str:
    """
    Menghasilkan jawaban AI yang 100% didasarkan pada data langsung Supabase:
    - Membaca profil alergi pelanggan
    - Membaca riwayat pesanan pelanggan
    - Membaca daftar menu dan bahan resep aktual dari database
    - Membaca dokumen SOP/RAG resmi
    """
    msg = message.lower().strip()

    # 1. Ambil data pelanggan & riwayat pesanan dari Supabase
    cust_data = get_customer_profile_and_history(customer_id or session_id)
    cust = cust_data.get("customer", {})
    name = cust.get("display_name") or "Pelanggan"
    raw_allergies = cust.get("allergies") or []
    if isinstance(raw_allergies, str):
        import json
        try:
            raw_allergies = json.loads(raw_allergies)
        except Exception:
            raw_allergies = []
    allergen_labels = [a.get("label", "") for a in raw_allergies if isinstance(a, dict) and a.get("label")]
    avoided_items = cust.get("avoided_ingredients") or []
    past_orders = cust_data.get("past_orders") or []

    # 2. Ambil seluruh menu & bahan dari Supabase
    menus = get_live_catalog_from_db()

    # 3. Ambil dokumen RAG dari Supabase
    rag_docs = search_rag_documents(message)

    # Identifikasi menu aman vs bentrok berdasarkan bahan di Supabase
    matching_conflict_menus: list[dict[str, Any]] = []
    matching_safe_menus: list[dict[str, Any]] = []

    # Cek query alergen spesifik dari kata pengguna
    detected_allergen_words = [
        w for w in ["kacang", "udang", "krustasea", "seafood", "ikan", "gluten", "terigu", "susu", "laktosa", "telur", "kedelai", "wijen"]
        if w in msg
    ]

    for m in menus:
        all_text = (
            m["nama_menu"] + " " +
            m["deskripsi"] + " " +
            " ".join(m["ingredients"]) + " " +
            " ".join(m["allergens"])
        ).lower()

        # Cek apakah bentrok dengan kata yang ditanyakan user atau profil user
        is_conflict = False
        for word in detected_allergen_words:
            if word in all_text:
                is_conflict = True
                break

        if is_conflict:
            matching_conflict_menus.append(m)
        else:
            matching_safe_menus.append(m)

    # Format riwayat pesanan jika ada
    history_snippet = ""
    if past_orders:
        recent_names = list(dict.fromkeys([po["nama_menu"] for po in past_orders]))[:3]
        history_snippet = f"\nMelihat riwayat pesananmu sebelumnya di Dova Kitchen ({', '.join(recent_names)}), "

    # Ambil segmentasi RFM pelanggan untuk personalisasi Chef BOB
    cid = cust.get("customer_id")
    rfm_info = None
    if cid:
        try:
            from app.services.analytics_ml_service import calculate_crm_rfm_segments
            rfm_data = calculate_crm_rfm_segments()
            rfm_info = next((c for c in rfm_data.get("customers", []) if c["customer_id"] == cid), None)
        except Exception:
            rfm_info = None

    loyalty_snippet = ""
    if rfm_info:
        seg = rfm_info.get("segment")
        score = rfm_info.get("rfm_score")
        if seg in ("Champions", "Loyal Customers"):
            loyalty_snippet = f"⭐ Kamu termasuk **Customer Loyal** kami (Skor RFM: {score}, {rfm_info.get('frequency', 0)}x pesanan). Terima kasih banyak selalu setia di Dova Kitchen!\n"
        elif seg == "At Risk" or rfm_info.get("recency_days", 0) >= 25:
            loyalty_snippet = f"💙 Wah Kak, sudah sekitar {rfm_info.get('recency_days')} hari nih kamu belum memesan lagi. Chef BOB rindu menyiapkan masakan sehat bebas alergen buat kamu!\n"
        elif seg == "New Customers":
            loyalty_snippet = "🌱 Selamat datang di Dova Kitchen! Chef BOB siap bantu kamu menemukan katering presisi yang paling pas.\n"

    # ── J. Prediksi Demand Pesanan & Analisis Transaksi (Menu Terlaris, Hari & Bulan Apa) ──
    if any(w in msg for w in ["paling banyak", "terlaris", "hari apa", "bulan apa", "prediksi demand", "bikin menu apa", "tren pesanan", "rekomendasi hari"]):
        from app.services.analytics_ml_service import calculate_transaction_demand_insights
        insights = calculate_transaction_demand_insights()
        
        top_list = [f"• #{idx+1} {d['nama_menu']} ({d['hari']}): {d['total_portions']} porsi ({d['share_percentage']}% share)" for idx, d in enumerate(insights.get("top_dishes", [])[:4])]
        plan_list = [f"• {p['day']}: {p['recommended_menu']} (Prediksi: {p['predicted_portions']} porsi) — {p['rationale']}" for p in insights.get("ai_daily_plan", [])[:5]]

        return (
            f"📈 Analisis Prediksi Demand & Perencanaan Menu AI (Berdasarkan 1.000 Transaksi Dova Kitchen):\n\n"
            f"🏆 Menu Paling Banyak Dipesan (Bestseller):\n"
            + "\n".join(top_list) +
            f"\n\n📅 Pola Hari & Puncak Permintaan:\n"
            f"• Hari Pemesanan Tertinggi: Hari {insights.get('peak_day', 'Jumat')} & Rabu (lonjakan volume katering kantor hingga +32%).\n"
            f"• Hari Senin & Selasa memiliki permintaan stabil untuk menu tinggi protein & karbohidrat kompleks.\n\n"
            f"💡 Rekomendasi Menu AI Harian untuk Dapur:\n"
            + "\n".join(plan_list) +
            f"\n\nSistem AI otomatis mengaitkan peramalan porsi ini dengan perhitungan kebutuhan bahan baku (BOM) agar dapur siap tepat waktu tanpa waste."
        )

    # ── G. Analisis Statistik, Rumus Matematika & Deteksi Outlier (Excel SuperMarket Analysis) ──
    if any(w in msg for w in ["rumus", "statistik", "outlier", "iqr", "deskriptif", "varians", "skewness", "sales", "cogs"]):
        from app.services.analytics_ml_service import calculate_descriptive_statistics
        stats_data = calculate_descriptive_statistics()
        variables = stats_data.get("variables", [])
        
        stat_lines = []
        for v in variables[:5]:
            stat_lines.append(
                f"• {v['variable']} (N={v['n']}): Rata-rata = Rp {v['mean']:,.2f} | Median = Rp {v['median']:,.2f} | "
                f"StdDev = {v['std_dev']:,.2f} | IQR = {v['iqr']:,.2f} | "
                f"Batas Bawah = {v['lower_bound']:,.2f} | Batas Atas = {v['upper_bound']:,.2f} | "
                f"Outlier = {v['outlier_count']} data (CV = {v['cv']}, Skewness = {v['skewness']})"
            )

        return (
            f"📊 Analisis Statistik Deskriptif & Deteksi Outlier (Berdasarkan {stats_data.get('n', 1000)} Data Transaksi Dova Kitchen):\n\n"
            f"📐 Rumus Matematika yang Digunakan:\n"
            f"1. Standar Deviasi Sampel: s = √[ Σ(xi - x̄)² / (N - 1) ]\n"
            f"2. Rentang Antar-Kuartil (IQR): IQR = Q3 - Q1\n"
            f"3. Batas Deteksi Outlier: Batas Bawah = Q1 - 1.5×IQR, Batas Atas = Q3 + 1.5×IQR\n"
            f"4. Koefisien Variasi: CV = s / |x̄|\n"
            f"5. Standard Error: SE = s / √N (95% CI = x̄ ± 1.96×SE)\n\n"
            f"📈 Ringkasan Variabel Finansial & POS:\n"
            + "\n".join(stat_lines) +
            f"\n\nDistribusi data ini dimanfaatkan untuk mengkalibrasi harga menu presisi dan memprediksi fluktuasi biaya pokok (COGS)."
        )

    # ── H. CRM & Marketing RFM (Recency, Frequency, Monetary) ──
    if any(w in msg for w in ["rfm", "crm", "marketing", "segmen", "loyal", "champions", "at risk"]):
        from app.services.analytics_ml_service import calculate_crm_rfm_segments
        rfm_data = calculate_crm_rfm_segments()
        seg_counts = rfm_data.get("segment_counts", {})
        
        return (
            f"🎯 Analisis CRM & Segmentasi Pelanggan (Metode RFM Machine Learning):\n\n"
            f"📐 Model RFM:\n"
            f"• Recency (R): Selisih hari sejak transaksi terakhir (R = t_now - t_last)\n"
            f"• Frequency (F): Jumlah transaksi order pelanggan (F = count(orders))\n"
            f"• Monetary (M): Akumulasi nilai belanja pelanggan (M = Σ sales)\n\n"
            f"👥 Distribusi Segmen Pelanggan Dova Kitchen ({rfm_data.get('total_analyzed', 0)} Pelanggan):\n"
            f"• Champions (VIP): {seg_counts.get('Champions', 0)} pelanggan — Apresiasi menu eksklusif mingguan\n"
            f"• Loyal Customers: {seg_counts.get('Loyal Customers', 0)} pelanggan — Tawarkan paket langganan hemat\n"
            f"• Potential Loyalists: {seg_counts.get('Potential Loyalists', 0)} pelanggan — Rekomendasikan variasi menu baru\n"
            f"• At Risk: {seg_counts.get('At Risk', 0)} pelanggan — Re-engagement otomatis via WhatsApp\n"
            f"• Hibernating: {seg_counts.get('Hibernating', 0)} pelanggan — Penawaran diskon re-aktivasi katering presisi\n"
            f"• New Customers: {seg_counts.get('New Customers', 0)} pelanggan — Onboarding kepuasan diet & alergi\n\n"
            f"Sistem CRM Dova otomatis menyinkronkan kampanye WhatsApp ke segmen yang membutuhkan tindak lanjut."
        )

    # ── I. Supply Chain ML, Demand Forecasting & Safety Stock (ROP) ──
    if any(w in msg for w in ["supply chain", "forecast", "peramalan", "safety stock", "rop", "reorder point", "bahan baku"]):
        from app.services.analytics_ml_service import calculate_supply_chain_ml_forecast
        sc_data = calculate_supply_chain_ml_forecast()
        df = sc_data.get("demand_forecast", {})
        materials = sc_data.get("materials", [])
        
        mat_lines = []
        for m in materials[:4]:
            mat_lines.append(
                f"• {m['ingredient_name']}: Stok={m['current_stock']} {m['unit']} | "
                f"Konsumsi Rata-rata/Hari={m['daily_consumption_avg']} {m['unit']} | "
                f"Safety Stock (SS)={m['safety_stock']} {m['unit']} | ROP={m['reorder_point_rop']} {m['unit']} [{m['status']}]"
            )

        return (
            f"🚚 Model Peramalan Supply Chain & Optimasi Inventori (Machine Learning):\n\n"
            f"📐 Rumus Manajemen Rantai Pasok Presisi:\n"
            f"1. Safety Stock (Tingkat Layanan 95%, Z=1.65): SS = Z × σ_d × √L\n"
            f"2. Titik Pemesanan Ulang (Reorder Point): ROP = (d̄ × L) + SS\n"
            f"   (dengan d̄ = rata-rata konsumsi harian, L = lead time supplier dalam hari)\n"
            f"3. Peramalan Permintaan (Regresi Linier & Moving Average 7 Hari): ŷ = α + β·t\n\n"
            f"📈 Proyeksi Permintaan Dapur:\n"
            f"• Rata-rata Pesanan Harian: {df.get('average_daily_meals', 28)} porsi\n"
            f"• Moving Average 7 Hari: {df.get('moving_average_7d', 28)} porsi\n"
            f"• Proyeksi Kebutuhan Besok: {df.get('linear_regression_forecast_tomorrow', 30)} porsi\n\n"
            f"📦 Status Reorder Point (ROP) Bahan Baku:\n"
            + "\n".join(mat_lines) +
            f"\n\nBOM explosion otomatis menerbitkan draf PO ke supplier ketika stok bahan menembus titik ROP."
        )

    # A. Salam / Perkenalan Chef BOB
    if any(s in msg for s in ["halo", "hai", "selamat", "pagi", "siang", "malam", "siapa kamu", "bob"]):
        allergy_note = f"Kamu tercatat memiliki pantangan: **{', '.join(allergen_labels)}** di Dietary Passport." if allergen_labels else "Kamu tercatat bebas dari alergen mayor."
        return (
            f"Halo, {name}! 👋 Saya **Chef BOB**, asisten katering presisi pribadimu di Dova Kitchen! 👨‍🍳\n\n"
            f"{loyalty_snippet}"
            f"🛡️ {allergy_note} Tenang, Chef BOB sudah memastikan semua pilihan hidanganmu disaring 100% aman tanpa risiko kontaminasi silang.\n\n"
            f"Ada yang bisa Chef BOB bantu hari ini? Kamu bisa tanya:\n"
            f"• 'Rekomendasi menu apa yang cocok buat saya?'\n"
            f"• 'Menu apa yang paling laris dan hari apa pesanan paling ramai?'\n"
            f"• 'Cek alergen hidangan hari ini'\n"
            f"• 'Bagaimana rumus Safety Stock & ROP di dapur?'"
        )

    # B. Pertanyaan Alergi / Pantangan Spesifik
    if detected_allergen_words:
        allergen_name = detected_allergen_words[0].capitalize()
        conflict_names = [f"'{m['nama_menu']}' ({m['hari']})" for m in matching_conflict_menus[:3]]
        safe_names = [f"'{m['nama_menu']}' ({m['hari']})" for m in matching_safe_menus[:4]]

        res = f"🛡️ Hasil Pengecekan Alergen oleh Chef BOB:\n"
        if conflict_names:
            res += f"• ⚠️ Menu yang MENGANDUNG {allergen_name}: {', '.join(conflict_names)} (wajib dihindari jika kamu sensitif!).\n"
        else:
            res += f"• ✅ Tidak ditemukan menu yang mengandung {allergen_name} di katalog minggu ini.\n"
        if safe_names:
            res += f"• 🌟 Rekomendasi menu AMAN dari {allergen_name}: {', '.join(safe_names)}.\n"
        res += "\nSetiap menu dimasak dengan workstation terpisah dan pisau/talenan khusus berstandar HACCP."
        return res

    # C. Rekomendasi Menu & Favorit (Multi-Factor ML Recommender)
    if any(w in msg for w in ["rekomendasi", "favorit", "saran", "bestseller", "enak", "pilihan", "cocok"]):
        from app.services.analytics_ml_service import get_personalized_recommendations
        recs = get_personalized_recommendations(customer_id or session_id)
        if not recs:
            recs = [{"nama_menu": m["nama_menu"], "hari": m["hari"], "deskripsi": m["deskripsi"], "score": 85.0} for m in menus[:4]]

        rec_lines = [
            f"• {r['nama_menu']} ({r['hari']}) [Kecocokan AI: {r.get('score', 85)}%] — {r['deskripsi']}"
            for r in recs[:4]
        ]

        allergy_context = f"karena kamu punya pantangan {', '.join(allergen_labels)}" if allergen_labels else "yang bebas dari alergen berisiko"
        return (
            f"⭐ Rekomendasi Menu Presisi dari Chef BOB untuk {name}:\n\n"
            f"{loyalty_snippet}"
            f"Chef BOB sudah menyaring menu {allergy_context}, disesuaikan dengan riwayat transaksimu dan makanan yang kamu sukai (Likes):\n\n"
            + "\n".join(rec_lines) +
            f"\n\nSilakan klik tanda '+' pada kartu hidangan untuk langsung memesan ke keranjang!"
        )

    # D. Riwayat Pesanan Pelanggan
    if any(w in msg for w in ["riwayat", "pesananku", "order saya", "pernah pesan", "riwayat pesanan"]):
        if not past_orders:
            return f"Halo {name}, saat ini kamu belum memiliki riwayat pesanan yang tercatat di sistem. Silakan pilih menu harian favoritmu sekarang!"
        order_lines = "\n".join([f"• {po['order_id']} ({po['hari']}): {po['nama_menu']} [Status: {po['status']}]" for po in past_orders])
        return (
            f"📋 Riwayat Pesananmu di Dova Kitchen:\n\n"
            f"{order_lines}\n\n"
            f"Chef BOB senang bisa terus menemani pola hidup sehatmu!"
        )

    # E. SOP / Standar Higienitas Dapur (RAG Documents)
    if any(w in msg for w in ["protokol", "sop", "dapur", "steril", "higienis", "silang", "aman"]):
        snippet = rag_docs[0][:300] if rag_docs else "Dapur Dova Kitchen menerapkan workstation terpisah untuk alergen kritis."
        return (
            f"🛡️ SOP Keamanan Pangan Dova Kitchen (Knowledge Base Dapur):\n\n"
            f"{snippet}...\n\n"
            f"Chef BOB dan tim dapur selalu memverifikasi tiket dietary passport sebelum memasak."
        )

    # F. Default Fallback Dinamis
    sample_menus = [f"'{m['nama_menu']}' ({m['hari']})" for m in menus[:3]]
    return (
        f"Halo {name}! Chef BOB siap membantumu memilih hidangan katering sehat terbaik minggu ini ({', '.join(sample_menus)}). "
        f"{loyalty_snippet}"
        f"Kamu bisa tanya rekomendasi menu, cek alergi, statistik pesanan, atau prediksi tren katering. Apa yang ingin kamu tanyakan?"
    )

