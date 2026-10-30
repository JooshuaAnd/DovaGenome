"""Layanan Analisis Statistik Deskriptif, Deteksi Outlier (IQR), CRM RFM, dan Supply Chain ML.

Mengimplementasikan rumus matematika & statistik presisi sesuai lembar Excel SuperMarket Analysis:
- Statistik Deskriptif: Mean, Median, Std Dev, Min, Q1, Q3, Max, IQR, Outlier, CV, Skewness, Frequency Table
- CRM Marketing: RFM (Recency, Frequency, Monetary) Scoring & Customer Segmentation
- Supply Chain ML: Demand Forecasting (Moving Average & Linear Regression), Safety Stock (SS = Z * sigma * sqrt(L)), Reorder Point (ROP = d * L + SS)
- Rekomendasi Presisi Multi-Faktor: Riwayat Transaksi + Riwayat Keranjang + Likes + Profil Alergi
"""

from __future__ import annotations

import datetime
import math
from typing import Any
from app.core.logging import get_logger
from app.core.errors import DatabaseError
from app.repositories import supabase

log = get_logger("dova.analytics_ml")


def _generate_fallback_rfm_rows() -> list[dict[str, Any]]:
    """Menghasilkan 54 profil pelanggan realistis untuk klasifikasi RFM bila Supabase offline."""
    names = [
        ("Maya Indah", "+6281234567802", 3, 32, 2450000),
        ("Joshua Pratama", "+6281234567801", 5, 28, 2180000),
        ("Budi Santoso", "+6281234567803", 6, 26, 1980000),
        ("Siti Rahmawati", "+6281234567804", 4, 25, 1850000),
        ("Adit Saputra", "+6281234567821", 7, 24, 1720000),
        ("Dimas Kusuma", "+6281234567822", 5, 22, 1650000),
        ("Kevin Hidayat", "+6281234567823", 2, 27, 2050000),
        ("Rian Wijaya", "+6281234567824", 6, 20, 1580000),
        ("Fajar Firmansyah", "+6281234567825", 4, 21, 1620000),
        ("Putri Nugroho", "+6281234567826", 3, 23, 1790000),
        ("Nadia Wibowo", "+6281234567827", 7, 25, 1890000),
        ("Sari Permana", "+6281234567828", 5, 20, 1540000),
        ("Bayu Gunawan", "+6281234567829", 4, 22, 1680000),
        ("Gita Siregar", "+6281234567830", 6, 24, 1810000),
        ("Dewi Lestari", "+6281234567806", 12, 18, 1420000),
        ("Ahmad Fauzi", "+6281234567807", 14, 16, 1280000),
        ("Rina Anggraini", "+6281234567808", 18, 15, 1150000),
        ("Hendro Wicaksono", "+6281234567809", 10, 17, 1340000),
        ("Ratna Sari", "+6281234567810", 15, 14, 1120000),
        ("Dedi Prasetyo", "+6281234567811", 16, 15, 1190000),
        ("Fitri Handayani", "+6281234567812", 11, 18, 1380000),
        ("Eko Purnomo", "+6281234567813", 19, 13, 1050000),
        ("Sri Wahyuni", "+6281234567814", 13, 16, 1260000),
        ("Bambang Irawan", "+6281234567815", 17, 15, 1180000),
        ("Yuni Astuti", "+6281234567816", 12, 17, 1310000),
        ("Agus Setiawan", "+6281234567817", 14, 14, 1140000),
        ("Lestari Ningrum", "+6281234567818", 20, 12, 980000),
        ("Surya Darmawan", "+6281234567819", 15, 15, 1210000),
        ("Mega Putri", "+6281234567820", 16, 13, 1020000),
        ("Arif Siregar", "+6281234567831", 18, 14, 1090000),
        ("Tari Permana", "+6281234567832", 6, 7, 560000),
        ("Hendra Wibowo", "+6281234567833", 5, 8, 640000),
        ("Rizky Pratama", "+6281234567834", 4, 6, 490000),
        ("Annisa Rahma", "+6281234567835", 7, 7, 580000),
        ("Bagus Hidayat", "+6281234567836", 5, 8, 670000),
        ("Citra Dewi", "+6281234567837", 6, 6, 510000),
        ("Doni Kusuma", "+6281234567838", 4, 7, 590000),
        ("Elisa Putri", "+6281234567839", 7, 8, 680000),
        ("Farhan Saputra", "+6281234567840", 5, 6, 520000),
        ("Rudi Hermawan", "+6281234567805", 58, 14, 1150000),
        ("Gilang Firmansyah", "+6281234567841", 62, 12, 980000),
        ("Hani Wijaya", "+6281234567842", 55, 15, 1220000),
        ("Indra Nugroho", "+6281234567843", 68, 11, 890000),
        ("Joko Gunawan", "+6281234567844", 52, 13, 1060000),
        ("Kartika Sari", "+6281234567845", 65, 10, 840000),
        ("Lukman Hidayat", "+6281234567846", 59, 14, 1130000),
        ("Mira Lestari", "+6281234567847", 85, 3, 270000),
        ("Nanda Kusuma", "+6281234567848", 92, 2, 180000),
        ("Oki Pratama", "+6281234567849", 78, 4, 340000),
        ("Panji Wibowo", "+6281234567850", 88, 3, 260000),
        ("Qori Rahmawati", "+6281234567851", 95, 2, 175000),
        ("Reza Firmansyah", "+6281234567852", 2, 1, 95000),
        ("Sinta Dewi", "+6281234567853", 3, 1, 85000),
        ("Taufik Hidayat", "+6281234567854", 1, 1, 110000),
    ]
    now = datetime.datetime.now(datetime.timezone.utc)
    rfm_rows = []
    for idx, (name, phone, recency, freq, monetary) in enumerate(names):
        last_dt = now - datetime.timedelta(days=recency)
        rfm_rows.append({
            "customer_id": f"cust_{idx + 1:03d}",
            "display_name": name,
            "phone": phone,
            "last_order_date": last_dt,
            "frequency": freq,
            "monetary": monetary,
        })
    return rfm_rows


def _percentile(data: list[float], p: float) -> float:
    """Menghitung persentil p (0 - 1) menggunakan metode interpolasi linier standar Excel."""
    if not data:
        return 0.0
    sorted_d = sorted(data)
    n = len(sorted_d)
    if n == 1:
        return sorted_d[0]
    idx = (n - 1) * p
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    weight = idx - lower
    return sorted_d[lower] * (1 - weight) + sorted_d[upper] * weight


def _sample_std(data: list[float], mean: float) -> float:
    """Sample Standard Deviation (STDEV.S)."""
    n = len(data)
    if n <= 1:
        return 0.0
    variance = sum((x - mean) ** 2 for x in data) / (n - 1)
    return math.sqrt(variance)


def _sample_skewness(data: list[float], mean: float, std: float) -> float:
    """Sample Skewness (SKEW)."""
    n = len(data)
    if n < 3 or std == 0:
        return 0.0
    factor = n / ((n - 1) * (n - 2))
    sum_cubed = sum(((x - mean) / std) ** 3 for x in data)
    return factor * sum_cubed


def calculate_descriptive_statistics() -> dict[str, Any]:
    """
    Menghitung statistik deskriptif dan deteksi outlier (metode IQR)
    pada maksimal 1.000 observasi transaksi riil. Nilai yang tidak tercatat
    dikeluarkan per variabel dan tidak diganti dengan angka buatan.
    """
    try:
        rows = supabase.execute(
            """
            SELECT unit_price, quantity, tax_amount, total as sales, cogs, gross_income, rating
            FROM orders
            ORDER BY created_at DESC
            LIMIT 1000
            """
        )
    except Exception as exc:
        log.warning("Supabase unavailable; descriptive statistics held: %s", type(exc).__name__)
        return {
            "status": "UNAVAILABLE",
            "source": "supabase_postgres",
            "reason_code": "database_unavailable",
            "n": 0,
            "variables": [],
            "frequency_table": [],
        }

    if not rows:
        return {
            "status": "UNAVAILABLE",
            "source": "supabase_postgres",
            "reason_code": "no_order_observations",
            "n": 0,
            "variables": [],
            "frequency_table": [],
        }

    n_samples = len(rows)

    # Missing operational values remain missing. Never synthesize prices,
    # quantities, tax, margin, or ratings into analytics output.
    def observed(key: str) -> list[float]:
        return [float(row[key]) for row in rows if row.get(key) is not None]

    var_map: dict[str, list[float]] = {
        "Unit price": observed("unit_price"),
        "Quantity": observed("quantity"),
        "Tax 5%": observed("tax_amount"),
        "Sales": observed("sales"),
        "COGS": observed("cogs"),
        "Gross Margin %": [
            round(float(row["gross_income"]) / float(row["sales"]) * 100, 2)
            for row in rows
            if row.get("gross_income") is not None
            and row.get("sales") is not None
            and float(row["sales"]) > 0
        ],
        "Gross Income": observed("gross_income"),
        "Rating": observed("rating"),
    }

    stats_result = []

    for var_name, values in var_map.items():
        if not values:
            continue
        variable_n = len(values)
        val_sum = sum(values)
        mean = val_sum / variable_n
        sorted_vals = sorted(values)
        median = _percentile(values, 0.50)
        std = _sample_std(values, mean)
        variance = std ** 2
        val_min = sorted_vals[0]
        val_max = sorted_vals[-1]
        val_range = val_max - val_min

        q1 = _percentile(values, 0.25)
        q3 = _percentile(values, 0.75)
        iqr = q3 - q1

        # Rumus Deteksi Outlier Excel: Batas = Q1 - 1.5*IQR dan Q3 + 1.5*IQR
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outlier_count = sum(1 for x in values if x < lower_bound or x > upper_bound)

        # CV = Std / |Rata-rata|
        cv = round(std / abs(mean), 4) if mean != 0 else 0.0

        # SE = Std / sqrt(N)
        se = round(std / math.sqrt(variable_n), 4) if variable_n > 0 else 0.0

        # Skewness
        skew = round(_sample_skewness(values, mean, std), 4)

        stats_result.append({
            "variable": var_name,
            "n": variable_n,
            "mean": round(mean, 2),
            "median": round(median, 2),
            "std_dev": round(std, 2),
            "min": round(val_min, 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "max": round(val_max, 2),
            "iqr": round(iqr, 2),
            "lower_bound": round(lower_bound, 2),
            "upper_bound": round(upper_bound, 2),
            "outlier_count": outlier_count,
            "cv": cv,
            "skewness": skew,
            "sum": round(val_sum, 2),
            "range": round(val_range, 2),
            "variance": round(variance, 2),
            "std_err": se,
            "ci_95_lower": round(mean - 1.96 * se, 2),
            "ci_95_upper": round(mean + 1.96 * se, 2),
        })

    # Distribusi Frekuensi untuk Unit price (10 Kelas Interval)
    unit_prices = var_map["Unit price"]
    price_n = len(unit_prices)
    if not unit_prices:
        return {
            "status": "UNAVAILABLE",
            "source": "supabase_postgres",
            "reason_code": "no_verified_unit_price_observations",
            "n": n_samples,
            "variables": stats_result,
            "frequency_table": [],
            "warnings": ["Tidak ada harga unit aktual; distribusi frekuensi tidak dihitung."],
        }
    min_up = min(unit_prices)
    max_up = max(unit_prices)
    step = (max_up - min_up) / 10 if max_up > min_up else 1.0

    freq_table = []
    cumulative = 0
    for i in range(10):
        low = min_up + i * step
        high = min_up + (i + 1) * step if i < 9 else max_up + 0.01
        count = sum(1 for p in unit_prices if low <= p < high or (i == 9 and p == max_up))
        proportion = round((count / price_n) * 100, 1)
        cumulative += count
        freq_table.append({
            "interval": f"Rp {int(low):,} - Rp {int(high):,}".replace(",", "."),
            "frequency": count,
            "proportion": f"{proportion}%",
            "cumulative": f"{round((cumulative / price_n) * 100, 1)}%",
        })

    return {
        "status": "OK",
        "source": "supabase_postgres",
        "n": n_samples,
        "variables": stats_result,
        "frequency_table": freq_table,
        "warnings": [
            f"{name}: {len(rows) - len(values)} nilai kosong tidak dihitung."
            for name, values in var_map.items()
            if len(values) < len(rows)
        ],
    }


def calculate_crm_rfm_segments() -> dict[str, Any]:
    """Backward-compatible name backed by the strict live RFM service."""
    from app.services.rfm_service import build_rfm_report

    return build_rfm_report()


def _legacy_calculate_crm_rfm_segments() -> dict[str, Any]:
    """
    Analisis CRM & Segmentasi RFM (Recency, Frequency, Monetary).
    Mengelompokkan pelanggan ke dalam segmen: Champions, Loyal, Potential, At Risk, Hibernating, New.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # Tarik agregasi RFM per pelanggan
    try:
        rfm_rows = supabase.execute(
            """
            SELECT c.customer_id, c.display_name, c.phone,
                   MAX(o.created_at) as last_order_date,
                   COUNT(o.id) as frequency,
                   COALESCE(SUM(o.total), 0) as monetary
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            GROUP BY c.customer_id, c.display_name, c.phone
            HAVING COUNT(o.id) > 0
            ORDER BY monetary DESC
            """
        )
    except Exception as exc:
        log.warning("Supabase offline, using synthetic RFM rows: %s", exc)
        rfm_rows = []

    if not rfm_rows:
        rfm_rows = _generate_fallback_rfm_rows()

    customers_rfm = []
    segment_counts = {
        "Champions": 0,
        "Loyal Customers": 0,
        "Potential Loyalists": 0,
        "At Risk": 0,
        "Hibernating": 0,
        "New Customers": 0,
    }

    for row in rfm_rows:
        last_dt = row["last_order_date"]
        if isinstance(last_dt, str):
            from datetime import timezone
            last_dt = datetime.datetime.fromisoformat(last_dt.replace("Z", "+00:00"))
        
        days_recency = max(0, (now - last_dt).days)
        freq = int(row["frequency"])
        monetary = float(row["monetary"])

        # Klasifikasi Skoring
        # R_score: 5 (sangat baru <= 7 hari), 1 (lama > 60 hari)
        if days_recency <= 7:
            r_score = 5
        elif days_recency <= 21:
            r_score = 4
        elif days_recency <= 45:
            r_score = 3
        elif days_recency <= 75:
            r_score = 2
        else:
            r_score = 1

        # F_score: 5 (>= 25 order), 1 (<= 2 order)
        if freq >= 25:
            f_score = 5
        elif freq >= 15:
            f_score = 4
        elif freq >= 8:
            f_score = 3
        elif freq >= 3:
            f_score = 2
        else:
            f_score = 1

        # M_score: 5 (>= Rp 1.5jt)
        if monetary >= 1500000:
            m_score = 5
        elif monetary >= 900000:
            m_score = 4
        elif monetary >= 500000:
            m_score = 3
        elif monetary >= 200000:
            m_score = 2
        else:
            m_score = 1

        # Tentukan Segment
        if r_score >= 4 and f_score >= 4 and m_score >= 4:
            segment = "Champions"
            action = "Beri apresiasi VIP & akses eksklusif menu baru."
        elif r_score >= 3 and f_score >= 3:
            segment = "Loyal Customers"
            action = "Tawarkan program langganan mingguan hemat."
        elif r_score >= 4 and f_score <= 2:
            segment = "New Customers" if freq == 1 else "Potential Loyalists"
            action = "Kirim WA sambutan & voucher porsi kedua."
        elif r_score <= 2 and f_score >= 3:
            segment = "At Risk"
            action = "Kirim penawaran personalisasi 'Kami merindukanmu'."
        else:
            segment = "Hibernating"
            action = "Kirim promo diskon re-engagement katering presisi."

        segment_counts[segment] = segment_counts.get(segment, 0) + 1

        customers_rfm.append({
            "customer_id": row["customer_id"],
            "name": row["display_name"] or "Pelanggan",
            "phone": row["phone"],
            "recency_days": days_recency,
            "frequency": freq,
            "monetary": monetary,
            "r_score": r_score,
            "f_score": f_score,
            "m_score": m_score,
            "rfm_score": f"{r_score}{f_score}{m_score}",
            "segment": segment,
            "recommended_action": action,
        })

    return {
        "customers": customers_rfm,
        "segment_counts": segment_counts,
        "total_analyzed": len(customers_rfm),
    }


def calculate_supply_chain_ml_forecast() -> dict[str, Any]:
    """Reject the legacy synthetic supply-chain facade.

    The old implementation below is retained only as migration reference and
    must never be reachable from a production caller.
    """
    raise DatabaseError(
        "Supply-chain ML legacy dinonaktifkan; gunakan forecast-backtest live. "
        "SS/ROP menunggu BOM, lead time, dan inventory terverifikasi."
    )


def _legacy_calculate_supply_chain_ml_forecast() -> dict[str, Any]:
    """
    Supply Chain Machine Learning:
    - Demand Forecasting (Moving Average & Trend Slope)
    - Safety Stock formula: SS = Z * sigma * sqrt(L)
    - Reorder Point formula: ROP = (d_avg * L) + SS
    - BOM Explosion & Status Restock Otomatis
    """
    # 1. Hitung konsumsi harian dari 1.000 transaksi
    try:
        daily_sales = supabase.execute(
            """
            SELECT DATE(created_at) as tgl, COUNT(*) as meal_units
            FROM orders
            GROUP BY DATE(created_at)
            ORDER BY tgl DESC
            LIMIT 30
            """
        )
    except Exception as exc:
        log.warning("Supabase offline, using fallback daily sales: %s", exc)
        daily_sales = []

    history_units = [int(r["meal_units"]) for r in daily_sales] if daily_sales else [25, 28, 30, 32, 27, 29, 31, 34, 28, 30]
    d_avg = sum(history_units) / len(history_units) if history_units else 28.0
    sigma_d = _sample_std([float(u) for u in history_units], d_avg)

    # Moving Average 7 Hari
    ma_7 = sum(history_units[:7]) / min(7, len(history_units)) if history_units else d_avg

    # Linear Regression Trend (Slope & Intercept)
    n = len(history_units)
    if n > 1:
        x_vals = list(range(n))
        x_mean = sum(x_vals) / n
        y_vals = list(reversed(history_units))
        y_mean = sum(y_vals) / n
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)
        slope = numerator / denominator if denominator != 0 else 0.0
        intercept = y_mean - slope * x_mean
        forecast_next_day = max(10, int(round(intercept + slope * n)))
    else:
        forecast_next_day = int(round(d_avg))

    # 2. Hitung ROP dan Safety Stock per Bahan di Inventory
    try:
        inventory = supabase.execute("SELECT * FROM inventory_stocks ORDER BY status ASC")
    except Exception as exc:
        log.warning("Supabase offline, using fallback inventory: %s", exc)
        inventory = []

    if not inventory:
        inventory = [
            {"ingredient_name": "Fillet Dada Ayam Organik", "current_stock": 12.5, "unit": "kg", "status": "AMAN"},
            {"ingredient_name": "Daging Sapi Has Dalam", "current_stock": 3.2, "unit": "kg", "status": "BUTUH PO"},
            {"ingredient_name": "Brokoli Organik Segar", "current_stock": 4.0, "unit": "kg", "status": "BUTUH PO"},
            {"ingredient_name": "Ubi Madu Cilembu", "current_stock": 15.0, "unit": "kg", "status": "AMAN"},
            {"ingredient_name": "Udang Windu Segar", "current_stock": 1.8, "unit": "kg", "status": "HABIS"},
            {"ingredient_name": "Salmon Segar Norwegia", "current_stock": 2.0, "unit": "kg", "status": "MENIPIS"},
        ]
    
    # Z = 1.65 (95% Service Level)
    Z = 1.65

    material_projections = []
    auto_po_recommendations = []

    for item in inventory:
        stock = float(item.get("current_stock") or 0)
        unit = item.get("unit") or "kg"
        name = item.get("ingredient_name") or ""
        
        # Lead time asumsi 2 hari
        L = 2.0
        # Konsumsi proporsional bahan per porsi rata-rata ~0.15 - 0.25 kg
        daily_material_demand = d_avg * 0.18
        sigma_material = sigma_d * 0.18

        # Rumus ROP: SS = Z * sigma * sqrt(L); ROP = (d_avg * L) + SS
        ss = round(Z * sigma_material * math.sqrt(L), 2)
        rop = round((daily_material_demand * L) + ss, 2)

        needs_reorder = stock <= rop
        shortage = max(0.0, round(rop - stock + (daily_material_demand * 3), 2))

        material_projections.append({
            "ingredient_name": name,
            "current_stock": stock,
            "unit": unit,
            "daily_consumption_avg": round(daily_material_demand, 2),
            "safety_stock": ss,
            "reorder_point_rop": rop,
            "status": "KRITIS / PERLU PO" if needs_reorder else "AMAN",
            "suggested_order_qty": shortage if needs_reorder else 0.0,
        })

        if needs_reorder:
            auto_po_recommendations.append({
                "item_name": name,
                "reorder_qty": shortage,
                "unit": unit,
                "reason": f"Stok saat ini ({stock} {unit}) telah menembus batas ROP ({rop} {unit}).",
            })

    return {
        "demand_forecast": {
            "average_daily_meals": round(d_avg, 1),
            "sigma_daily_demand": round(sigma_d, 2),
            "moving_average_7d": round(ma_7, 1),
            "linear_regression_forecast_tomorrow": forecast_next_day,
            "confidence_level": "95% (Z = 1.65)",
        },
        "materials": material_projections,
        "auto_po_recommendations": auto_po_recommendations,
    }


def get_personalized_recommendations(customer_id: str) -> list[dict[str, Any]]:
    """
    Rekomendasi Presisi Multi-Faktor Menggabungkan:
    1. Profil Alergi & Pantangan (Safety First - filter keras)
    2. Riwayat Transaksi Riil
    3. Riwayat Keranjang (Cart History)
    4. Likes / Favorit Makanan (Customer Likes)
    5. Rating Rata-rata Menu
    """
    # 1. Ambil Profil Pelanggan
    cust = supabase.execute_one(
        """
        SELECT c.customer_id, c.display_name,
               COALESCE(dp.allergies, '[]'::jsonb) as allergies,
               COALESCE(dp.avoided_ingredients, '{}'::text[]) as avoided
        FROM customers c
        LEFT JOIN dietary_passports dp ON c.customer_id = dp.customer_id
        WHERE c.customer_id = %s OR c.phone = %s OR c.username = %s
        LIMIT 1
        """,
        (customer_id, customer_id, customer_id)
    ) or {}

    raw_algs = cust.get("allergies") or []
    if isinstance(raw_algs, str):
        import json
        try:
            raw_algs = json.loads(raw_algs)
        except Exception:
            raw_algs = []
    avoided_algs = [a.get("code", "").lower() for a in raw_algs if isinstance(a, dict)]
    avoided_algs += [x.lower() for x in (cust.get("avoided") or [])]

    # 2. Ambil Likes Pelanggan
    likes = supabase.execute(
        "SELECT menu_id FROM customer_likes WHERE customer_id = %s",
        (customer_id,)
    )
    liked_ids = {l["menu_id"] for l in likes}

    # 3. Ambil Cart History Pelanggan
    cart_items = supabase.execute(
        "SELECT menu_id, COUNT(*) as cnt FROM cart_history WHERE customer_id = %s GROUP BY menu_id",
        (customer_id,)
    )
    cart_score_map = {c["menu_id"]: c["cnt"] for c in cart_items}

    # 4. Ambil Riwayat Transaksi Sebelumnya
    past_order_items = supabase.execute(
        """
        SELECT oi.menu_id, COUNT(*) as order_cnt
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.customer_id = %s
        GROUP BY oi.menu_id
        """,
        (customer_id,)
    )
    order_score_map = {po["menu_id"]: po["order_cnt"] for po in past_order_items}

    # 5. Ambil Semua Menu & Hitung Skor
    all_menus = supabase.execute(
        """
        SELECT m.menu_id, m.hari, m.nama_menu, m.deskripsi,
               COALESCE(array_agg(mi.nama) FILTER (WHERE mi.nama IS NOT NULL), ARRAY[]::TEXT[]) as ingredients,
               COALESCE(array_agg(mi.potensi_alergen) FILTER (WHERE mi.potensi_alergen IS NOT NULL), ARRAY[]::TEXT[]) as allergens
        FROM menus m
        LEFT JOIN menu_ingredients mi ON m.menu_id = mi.menu_id
        WHERE m.published = true
        GROUP BY m.menu_id, m.hari, m.nama_menu, m.deskripsi, m.option_index
        """
    )

    scored_menus = []
    for m in all_menus:
        mid = m["menu_id"]
        text_blob = (
            m["nama_menu"] + " " +
            m["deskripsi"] + " " +
            " ".join(m["ingredients"]) + " " +
            " ".join(m["allergens"])
        ).lower()

        # Cek Alergi Keras
        is_conflict = any(alg in text_blob for alg in avoided_algs if len(alg) >= 3)
        if is_conflict:
            continue  # Singkirkan menu yang berbahaya bagi pelanggan

        # Multi-faktor Pembobotan:
        # Score = w1 * OrderHistory (35%) + w2 * CartHistory (25%) + w3 * Likes (25%) + Base (15%)
        h_score = min(5, order_score_map.get(mid, 0)) * 7.0
        c_score = min(5, cart_score_map.get(mid, 0)) * 5.0
        l_score = 25.0 if mid in liked_ids else 0.0
        base_score = 15.0

        total_score = round(base_score + h_score + c_score + l_score, 1)

        scored_menus.append({
            "menu_id": mid,
            "hari": m["hari"],
            "nama_menu": m["nama_menu"],
            "deskripsi": m["deskripsi"],
            "score": total_score,
            "is_liked": mid in liked_ids,
            "in_cart_history": mid in cart_score_map,
            "order_count_past": order_score_map.get(mid, 0),
            "match_reason": (
                "Sangat cocok karena kamu menyukainya dan pernah memesan sebelumnya."
                if (mid in liked_ids and mid in order_score_map)
                else "Direkomendasikan berdasarkan profil bebas pantanganmu."
            ),
        })

    scored_menus.sort(key=lambda x: x["score"], reverse=True)
    return scored_menus


def calculate_transaction_demand_insights() -> dict[str, Any]:
    """Reject the legacy synthetic demand-insights facade."""
    raise DatabaseError(
        "Demand insights legacy dinonaktifkan; gunakan forecast-backtest live."
    )


def _legacy_calculate_transaction_demand_insights() -> dict[str, Any]:
    """
    Analisis Prediksi Demand Pesanan dari 1.000 Transaksi Riil:
    1. Menu Terlaris (Ranking porsi & revenue).
    2. Pola Hari Pemesanan (Day of Week Analysis: Senin - Minggu).
    3. Tren Bulanan (Monthly Peak Sales & Quantity).
    4. Rekomendasi Menu AI Harian untuk Dapur (Daily Menu Planning).
    5. Proyeksi Kebutuhan Bahan Baku Supplier 7 Hari ke Depan.
    """
    # 1. Menu Terlaris
    try:
        top_dishes_rows = supabase.execute(
            """
            SELECT m.menu_id, m.nama_menu, m.hari,
                   COUNT(oi.id) as total_portions,
                   COALESCE(SUM(oi.subtotal), COUNT(oi.id) * 48000) as total_revenue
            FROM order_items oi
            JOIN menus m ON oi.menu_id = m.menu_id
            GROUP BY m.menu_id, m.nama_menu, m.hari
            ORDER BY total_portions DESC
            LIMIT 6
            """
        )
    except Exception as exc:
        log.warning("Supabase offline, using fallback top dishes: %s", exc)
        top_dishes_rows = []

    if not top_dishes_rows:
        top_dishes = [
            {"menu_id": "menu_senin_ayam-rosemary", "nama_menu": "Ayam Panggang Rosemary & Ubi Madu", "hari": "Senin", "total_portions": 116, "total_revenue": 5697000, "share_percentage": 11.6},
            {"menu_id": "menu_jumat_pasta-fusilli-pesto", "nama_menu": "Pasta Fusilli Ayam Pesto Keju", "hari": "Jumat", "total_portions": 115, "total_revenue": 5642000, "share_percentage": 11.5},
            {"menu_id": "menu_senin_beef-bulgogi", "nama_menu": "Beef Bulgogi Wijen & Nasi Beras Cokelat", "hari": "Senin", "total_portions": 112, "total_revenue": 5445000, "share_percentage": 11.2},
            {"menu_id": "menu_kamis_salmon-lemon", "nama_menu": "Salmon Fillet Lemon Herb & Kentang Kukus", "hari": "Kamis", "total_portions": 98, "total_revenue": 5880000, "share_percentage": 9.8},
            {"menu_id": "menu_selasa_sup-daging-rempah", "nama_menu": "Sup Daging Sapi Jamur Rempah", "hari": "Selasa", "total_portions": 88, "total_revenue": 4312000, "share_percentage": 8.8},
            {"menu_id": "menu_rabu_ayam-suwir-matah", "nama_menu": "Ayam Suwir Sambal Matah & Urap Sayur", "hari": "Rabu", "total_portions": 84, "total_revenue": 4116000, "share_percentage": 8.4},
        ]
    else:
        top_dishes = [
            {
                "menu_id": r["menu_id"],
                "nama_menu": r["nama_menu"],
                "hari": r["hari"],
                "total_portions": int(r["total_portions"]),
                "total_revenue": float(r["total_revenue"]),
                "share_percentage": round((int(r["total_portions"]) / 1000) * 100, 1),
            }
            for r in top_dishes_rows
        ]

    # 2. Pola Hari Pemesanan (Senin - Minggu)
    # Mapping nama hari bahasa Indonesia
    day_map = {
        "Monday": "Senin",
        "Tuesday": "Selasa",
        "Wednesday": "Rabu",
        "Thursday": "Kamis",
        "Friday": "Jumat",
        "Saturday": "Sabtu",
        "Sunday": "Minggu",
    }
    try:
        dow_rows = supabase.execute(
            """
            SELECT 
                TRIM(TO_CHAR(o.created_at, 'Day')) as day_name_en,
                COUNT(o.id) as order_count,
                COALESCE(SUM(o.quantity), COUNT(o.id)) as portion_count,
                COALESCE(SUM(o.total), 0) as revenue
            FROM orders o
            GROUP BY TRIM(TO_CHAR(o.created_at, 'Day'))
            """
        )
    except Exception as exc:
        log.warning("Supabase offline, using fallback DOW stats: %s", exc)
        dow_rows = []

    if not dow_rows:
        dow_dict = {
            "Monday": {"order_count": 168, "portion_count": 245, "revenue": 11760000},
            "Tuesday": {"order_count": 142, "portion_count": 198, "revenue": 9504000},
            "Wednesday": {"order_count": 155, "portion_count": 215, "revenue": 10320000},
            "Thursday": {"order_count": 139, "portion_count": 192, "revenue": 9216000},
            "Friday": {"order_count": 196, "portion_count": 285, "revenue": 13680000},
            "Saturday": {"order_count": 118, "portion_count": 160, "revenue": 7680000},
            "Sunday": {"order_count": 82, "portion_count": 110, "revenue": 5280000},
        }
    else:
        dow_dict = {r["day_name_en"]: r for r in dow_rows}

    ordered_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_stats = []
    total_all_orders = sum(int(r.get("order_count", 0)) for r in (dow_dict.values() if not dow_rows else dow_rows)) or 1000

    peak_day_name = "Jumat"
    max_day_orders = 0

    for en_day in ordered_days:
        r = dow_dict.get(en_day, {"order_count": 0, "portion_count": 0, "revenue": 0})
        cnt = int(r["order_count"])
        id_day = day_map.get(en_day, en_day)
        if cnt > max_day_orders:
            max_day_orders = cnt
            peak_day_name = id_day
        day_stats.append({
            "day": id_day,
            "order_count": cnt,
            "portion_count": int(r["portion_count"]),
            "revenue": float(r["revenue"]),
            "percentage": round((cnt / total_all_orders) * 100, 1),
        })

    # 3. Tren Bulanan
    try:
        month_rows = supabase.execute(
            """
            SELECT 
                TO_CHAR(o.created_at, 'YYYY-MM') as month_key,
                TO_CHAR(o.created_at, 'Mon YYYY') as month_label,
                COUNT(o.id) as order_count,
                COALESCE(SUM(o.total), 0) as total_sales,
                ROUND(AVG(COALESCE(o.rating, 4.8)), 2) as avg_rating
            FROM orders o
            GROUP BY TO_CHAR(o.created_at, 'YYYY-MM'), TO_CHAR(o.created_at, 'Mon YYYY')
            ORDER BY month_key ASC
            """
        )
    except Exception as exc:
        log.warning("Supabase offline, using fallback monthly trends: %s", exc)
        month_rows = []

    if not month_rows:
        monthly_trends = [
            {"month_key": "2026-06", "month_label": "Jun 2026", "order_count": 180, "total_sales": 17800000, "avg_rating": 7.3},
            {"month_key": "2026-07", "month_label": "Jul 2026", "order_count": 210, "total_sales": 20900000, "avg_rating": 7.4},
            {"month_key": "2026-08", "month_label": "Aug 2026", "order_count": 235, "total_sales": 23450000, "avg_rating": 7.2},
            {"month_key": "2026-09", "month_label": "Sep 2026", "order_count": 245, "total_sales": 24650000, "avg_rating": 7.5},
            {"month_key": "2026-10", "month_label": "Oct 2026", "order_count": 130, "total_sales": 13094000, "avg_rating": 7.6},
        ]
    else:
        monthly_trends = [
            {
                "month_key": r["month_key"],
                "month_label": r["month_label"].strip(),
                "order_count": int(r["order_count"]),
                "total_sales": float(r["total_sales"]),
                "avg_rating": float(r["avg_rating"]),
            }
            for r in month_rows
        ]

    # 4. Rekomendasi Menu AI Harian untuk Dapur (Daily Menu Planning)
    # AI menganalisis menu terbaik per hari dan memprediksi target porsi
    ai_daily_plan = [
        {
            "day": "Senin",
            "recommended_menu": "Ayam Panggang Rosemary & Ubi Madu",
            "predicted_portions": 48,
            "rationale": "Menu pembuka pekan paling favorit. Pelanggan menyukai karbohidrat kompleks ubi madu untuk energi kerja.",
            "allergen_notice": "Aman dari 9 alergen mayor.",
        },
        {
            "day": "Selasa",
            "recommended_menu": "Beef Bulgogi Wijen & Nasi Beras Cokelat",
            "predicted_portions": 44,
            "rationale": "Protein tinggi dan repeat order stabil. Cocok dipasangkan dengan saus wijen aromatik.",
            "allergen_notice": "Mengandung Wijen & Kedelai (Saus Bulgogi).",
        },
        {
            "day": "Rabu",
            "recommended_menu": "Fillet Dori Panggang Lemon & Salad Jagung",
            "predicted_portions": 45,
            "rationale": "Pelanggan cenderung memilih hidangan seafood ringan di pertengahan pekan.",
            "allergen_notice": "Mengandung Ikan (Dori).",
        },
        {
            "day": "Kamis",
            "recommended_menu": "Udang Bakar Madu Jimbaran & Nasi Merah",
            "predicted_portions": 42,
            "rationale": "Pemesanan seafood premium meningkat menjelang akhir pekan.",
            "allergen_notice": "Mengandung Krustasea (Udang). Wajib cek profil alergi tiket dapur.",
        },
        {
            "day": "Jumat",
            "recommended_menu": "Salmon Fillet Lemon Herb & Kentang Kukus",
            "predicted_portions": 56,
            "rationale": f"Hari {peak_day_name} adalah hari pemesanan puncak katering mingguan (+32% volume). Salmon adalah menu signature berperingkat 4.9.",
            "allergen_notice": "Mengandung Ikan (Salmon). Siapkan stok bahan baku ekstra ke supplier.",
        },
        {
            "day": "Sabtu",
            "recommended_menu": "Steak Tempe Lada Hitam (Vegetarian)",
            "predicted_portions": 38,
            "rationale": "Menu ramah vegetarian akhir pekan untuk detoksifikasi nutrisi.",
            "allergen_notice": "Mengandung Kedelai (Tempe).",
        },
        {
            "day": "Minggu",
            "recommended_menu": "Sup Daging Sapi Jamur Rempah",
            "predicted_portions": 40,
            "rationale": "Hidangan hangat berkuah keluarga dengan rempah aromatik alami.",
            "allergen_notice": "Bebas dari 9 alergen mayor.",
        },
    ]

    # 5. Proyeksi Bahan Baku Supplier 7 Hari ke Depan
    supplier_7d_forecast = [
        {"material": "Fillet Dada Ayam Organik", "projected_kg": 24.5, "unit": "kg", "urgency": "TINGGI", "supplier": "PT Berkah Unggas"},
        {"material": "Fillet Salmon Segar", "projected_kg": 14.0, "unit": "kg", "urgency": "KRITIS", "supplier": "Muara Baru Seafood"},
        {"material": "Fillet Ikan Dori", "projected_kg": 12.0, "unit": "kg", "urgency": "SEDANG", "supplier": "Muara Baru Seafood"},
        {"material": "Daging Sapi Tenderloin", "projected_kg": 16.5, "unit": "kg", "urgency": "SEDANG", "supplier": "Sumber Daging Halal"},
        {"material": "Beras Merah & Cokelat Organik", "projected_kg": 35.0, "unit": "kg", "urgency": "AMAN", "supplier": "Koperasi Petani Organik"},
        {"material": "Sayuran Hijau & Jamur Segar", "projected_kg": 22.0, "unit": "kg", "urgency": "TINGGI", "supplier": "Sayur Segar Lembang"},
    ]

    return {
        "top_dishes": top_dishes,
        "day_stats": day_stats,
        "peak_day": peak_day_name,
        "monthly_trends": monthly_trends,
        "ai_daily_plan": ai_daily_plan,
        "supplier_7d_forecast": supplier_7d_forecast,
    }

