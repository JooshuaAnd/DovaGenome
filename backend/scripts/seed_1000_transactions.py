"""Script Seeding 1.000 Transaksi Realistis untuk Analitik POS, RFM, Supply Chain ML, dan RAG.

Menghasilkan:
- 60+ pelanggan beragam dengan nomor HP Indonesia & dietary passport
- 1.000 data pesanan (orders) lengkap dengan tanggal transaksi (Juni - Oktober 2026)
- Finansial presisi: Unit price, Quantity, Tax 5%, Sales, COGS, Gross Income, Customer Rating
- Riwayat keranjang (cart_history) & likes (customer_likes)
- Persis sesuai variabel analitik lembar Excel SuperMarket Analysis.
"""

from __future__ import annotations

import datetime
import random
import sys
import os
from psycopg2.extras import execute_values

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.repositories import supabase

CUSTOMER_NAMES = [
    ("Joshua Pratama", "+6281234567801", ["udang", "krustasea"]),
    ("Maya Indah", "+6281234567802", ["kacang"]),
    ("Budi Santoso", "+6281234567803", ["gluten", "terigu"]),
    ("Siti Rahmawati", "+6281234567804", ["susu", "laktosa"]),
    ("Rudi Hermawan", "+6281234567805", []),
    ("Dewi Lestari", "+6281234567806", ["ikan"]),
    ("Ahmad Fauzi", "+6281234567807", []),
    ("Rina Anggraini", "+6281234567808", ["telur"]),
    ("Hendro Wicaksono", "+6281234567809", ["kedelai"]),
    ("Ratna Sari", "+6281234567810", []),
    ("Dedi Prasetyo", "+6281234567811", ["kacang", "wijen"]),
    ("Fitri Handayani", "+6281234567812", []),
    ("Eko Purnomo", "+6281234567813", ["udang"]),
    ("Sri Wahyuni", "+6281234567814", ["gluten"]),
    ("Bambang Irawan", "+6281234567815", []),
    ("Yuni Astuti", "+6281234567816", ["susu"]),
    ("Agus Setiawan", "+6281234567817", []),
    ("Lestari Ningrum", "+6281234567818", []),
    ("Surya Darmawan", "+6281234567819", ["krustasea"]),
    ("Mega Putri", "+6281234567820", []),
]

# Tambah variasi nama pelanggan hingga 50 nama
for i in range(21, 55):
    first = random.choice(["Adit", "Dimas", "Kevin", "Rian", "Fajar", "Putri", "Nadia", "Sari", "Bayu", "Gita", "Tari", "Arif", "Hendra"])
    last = random.choice(["Saputra", "Kusuma", "Hidayat", "Wijaya", "Firmansyah", "Nugroho", "Wibowo", "Permana", "Gunawan", "Siregar"])
    phone = f"+628123456{7800 + i}"
    allergens = random.choice([[], ["kacang"], ["udang"], ["gluten"], ["susu"], []])
    CUSTOMER_NAMES.append((f"{first} {last}", phone, allergens))


def seed_1000_transactions():
    print("Memulai seeding 1.000 transaksi realistis ke Supabase...")

    # 1. Pastikan menu diambil dari database
    menus = supabase.execute("SELECT menu_id, hari, nama_menu FROM menus WHERE published = true")
    if not menus:
        print("Menu belum ada, silakan periksa tabel menus.")
        return
    menu_ids = [m["menu_id"] for m in menus]

    # 2. Upsert Customers & Passports
    cust_id_map: list[dict] = []
    with supabase.get_conn() as conn:
        with conn.cursor() as cur:
            for idx, (name, phone, algs) in enumerate(CUSTOMER_NAMES, start=1):
                cid = f"cust_ml_{idx:03d}"
                cur.execute(
                    """
                    INSERT INTO customers (customer_id, phone, username, display_name, role)
                    VALUES (%s, %s, %s, %s, 'customer')
                    ON CONFLICT (customer_id) DO UPDATE
                    SET display_name = EXCLUDED.display_name, phone = EXCLUDED.phone
                    RETURNING customer_id, display_name, phone
                    """,
                    (cid, phone, f"user_{idx}_{cid}", name)
                )
                row = cur.fetchone()
                actual_cid = row["customer_id"] if row else cid

                # Upsert passport
                import json
                alg_json = json.dumps([{"code": a, "label": a.capitalize()} for a in algs])
                cur.execute(
                    """
                    INSERT INTO dietary_passports (customer_id, allergies, avoided_ingredients, safety_notes)
                    VALUES (%s, %s::jsonb, %s, %s)
                    ON CONFLICT (customer_id) DO UPDATE
                    SET allergies = EXCLUDED.allergies
                    """,
                    (actual_cid, alg_json, algs, f"Pantangan: {', '.join(algs) if algs else 'Tidak ada'}")
                )

                cust_id_map.append({"cid": actual_cid, "name": name, "phone": phone, "algs": algs})

    print(f"Berhasil sinkron {len(cust_id_map)} profil pelanggan dan dietary passport.")

    # 3. Generate 1.000 Transaksi dengan Variasi Tanggal 120 Hari Terakhir
    now = datetime.datetime.now(datetime.timezone.utc)
    base_date = now - datetime.timedelta(days=120)

    orders_data = []
    order_items_data = []
    likes_data = set()
    cart_history_data = []

    statuses = ["COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "READY", "PREPARING", "PENDING"]
    payment_statuses = ["PAID", "PAID", "PAID", "PAID", "PAID", "PAID", "UNPAID"]

    for i in range(1, 1001):
        order_id = f"ORD-2026-{i:05d}"
        inv_number = f"INV-2026-{i:05d}"
        cust = random.choice(cust_id_map)

        # Distribusi waktu bertahap
        days_offset = int((i / 1000.0) * 120) + random.randint(-2, 2)
        days_offset = max(0, min(120, days_offset))
        order_time = base_date + datetime.timedelta(
            days=days_offset,
            hours=random.randint(8, 20),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )

        # Variabel Finansial Sesuai Analisis Excel
        # Unit price rata-rata ~Rp 42.000 - Rp 55.000
        unit_price = float(random.choice([38000, 42000, 45000, 48000, 52000, 55000, 60000]))
        qty = random.choices([1, 2, 3, 4, 5, 6, 8, 10], weights=[20, 35, 20, 10, 8, 4, 2, 1])[0]

        subtotal = unit_price * qty
        tax_5pct = round(subtotal * 0.05, 2)
        sales = subtotal + tax_5pct

        # COGS rata-rata 60% - 68% dari penjualan
        cogs_pct = random.uniform(0.60, 0.68)
        cogs = round(sales * cogs_pct, 2)
        gross_income = round(sales - cogs, 2)

        # Customer satisfaction rating (1.0 - 10.0, rata-rata ~7.0)
        rating = round(random.gauss(7.0, 1.6), 2)
        rating = max(1.0, min(10.0, rating))

        status = random.choice(statuses) if days_offset < 118 else random.choice(["PREPARING", "READY", "PENDING"])
        pay_status = "PAID" if status in ("COMPLETED", "READY") else random.choice(payment_statuses)
        pkg_code = "pkg_personal_3d" if qty <= 3 else ("pkg_workweek_5d" if qty <= 5 else "pkg_fullweek_6d")

        addr = f"Jl. {random.choice(['Sudirman', 'Senopati', 'Gatot Subroto', 'Kuningan', 'Thamrin', 'Diponegoro'])} No. {random.randint(1, 120)}, Jakarta"

        orders_data.append((
            order_id,
            cust["cid"],
            cust["name"],
            pkg_code,
            f"Paket Presisi {qty} Porsi",
            cust["algs"],
            f"Pantangan: {', '.join(cust['algs']) if cust['algs'] else 'Bebas'}",
            addr,
            qty,
            status,
            inv_number,
            int(subtotal),
            int(sales),
            pay_status,
            order_time,
            order_time,
            rating,
            tax_5pct,
            cogs,
            gross_income,
            qty,
            unit_price
        ))

        # Order Items (pilih 1 - 3 menu untuk pesanan ini)
        chosen_menus = random.sample(menu_ids, k=min(len(menu_ids), random.randint(1, 3)))
        for s_idx, mid in enumerate(chosen_menus):
            order_items_data.append((
                order_id,
                random.choice(["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]),
                mid,
                s_idx,
                unit_price,
                1,
                unit_price
            ))

        # Generate Like & Cart History
        if random.random() < 0.4:
            fav_menu = random.choice(menu_ids)
            likes_data.add((cust["cid"], fav_menu, order_time))

        if random.random() < 0.7:
            cart_menu = random.choice(menu_ids)
            cart_history_data.append((
                cust["cid"],
                cart_menu,
                random.randint(1, 3),
                random.choice(["checkout", "add", "add", "abandon"]),
                order_time
            ))

    # 4. Batch Insert ke Supabase
    print(f"Menyimpan {len(orders_data)} baris orders...")
    with supabase.get_conn() as conn:
        with conn.cursor() as cur:
            # Bersihkan data lama jika ingin regenerasi bersih
            cur.execute("DELETE FROM order_items WHERE order_id LIKE 'ORD-2026-%'")
            cur.execute("DELETE FROM orders WHERE order_id LIKE 'ORD-2026-%'")

            execute_values(
                cur,
                """
                INSERT INTO orders (
                    order_id, customer_id, customer_name, package_code, subscription_type,
                    selected_allergens, dietary_profile, delivery_address,
                    meal_count, status, invoice_number, subtotal, total,
                    payment_status, created_at, updated_at,
                    rating, tax_amount, cogs, gross_income, quantity, unit_price
                ) VALUES %s
                """,
                orders_data
            )

            print(f"Menyimpan {len(order_items_data)} baris order_items...")
            execute_values(
                cur,
                """
                INSERT INTO order_items (
                    order_id, hari, menu_id, sort_order, unit_price, quantity, subtotal
                ) VALUES %s
                """,
                order_items_data
            )

            print(f"Menyimpan {len(likes_data)} baris customer_likes...")
            execute_values(
                cur,
                """
                INSERT INTO customer_likes (customer_id, menu_id, created_at)
                VALUES %s
                ON CONFLICT (customer_id, menu_id) DO NOTHING
                """,
                list(likes_data)
            )

            print(f"Menyimpan {len(cart_history_data)} baris cart_history...")
            execute_values(
                cur,
                """
                INSERT INTO cart_history (customer_id, menu_id, quantity, action, created_at)
                VALUES %s
                """,
                cart_history_data
            )

    print("SELESAI! 1.000 transaksi realistis dengan analisis finansial & rating sukses di-seed ke Supabase.")


if __name__ == "__main__":
    seed_1000_transactions()
