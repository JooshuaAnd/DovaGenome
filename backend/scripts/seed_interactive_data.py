"""Script Seeding Data Realistis Dova Kitchen (Supabase).

Mengisi data interaktif untuk:
- Pelanggan & Paspor Alergi (Joshua, Maya, Budi, Siti, Rudi)
- Pesanan Nyata & Order Items (PAID, PREPARING, READY, COMPLETED)
- Master Supplier & Katalog Bahan
- Purchase Orders (PO) & PO Lines
- Stok Bahan (Inventory Stocks)
- Outbox Pesan Otomatis WhatsApp / Telegram (Pelanggan, Dapur, Supplier)
"""

from __future__ import annotations

import sys
import os
import json
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.repositories import supabase

def run_seed():
    print("[*] Memulai seeding data interaktif...")

    # 1. Seed Pelanggan & Paspor Alergi
    customers = [
        ("cust_joshua", "joshua", "Joshua", "+6281234567890", "customer"),
        ("cust_maya", "maya", "Maya Pramesti", "+6281398765432", "customer"),
        ("cust_budi", "budi", "Budi Santoso", "+6281122334455", "customer"),
        ("cust_siti", "siti", "Siti Rahma", "+6285211223344", "customer"),
        ("cust_rudi", "rudi", "Rudi Hermawan", "+6285866408193", "customer"),
    ]

    customer_map = {}
    for cid, uname, dname, phone, role in customers:
        existing = supabase.execute_one("SELECT customer_id FROM customers WHERE phone = %s", (phone,))
        if existing:
            actual_cid = existing["customer_id"]
            supabase.execute_write(
                "UPDATE customers SET display_name = %s, role = %s, status = 'active' WHERE customer_id = %s",
                (dname, role, actual_cid)
            )
            customer_map[uname] = actual_cid
        else:
            supabase.execute_write(
                """
                INSERT INTO customers (customer_id, username, display_name, phone, role, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
                """,
                (cid, uname, dname, phone, role)
            )
            customer_map[uname] = cid

    # Dietary Passports
    passports = [
        ("joshua", [{"code": "alg_udang", "label": "Udang / Krustasea"}], ["udang", "kepiting"]),
        ("maya", [{"code": "alg_kacang", "label": "Kacang Tanah"}], ["kacang tanah", "bumbu kacang"]),
        ("budi", [{"code": "alg_gluten", "label": "Gluten / Gandum"}], ["tepung terigu", "panko"]),
        ("siti", [{"code": "alg_susu", "label": "Susu / Laktosa"}], ["keju", "susu sapi", "mentega"]),
        ("rudi", [], []),
    ]

    for uname, algs, avoided in passports:
        actual_cid = customer_map.get(uname)
        if not actual_cid:
            continue
        supabase.execute_write(
            """
            INSERT INTO dietary_passports (customer_id, allergies, avoided_ingredients, structured, updated_at)
            VALUES (%s, %s, %s, true, NOW())
            ON CONFLICT (customer_id) DO UPDATE
            SET allergies = EXCLUDED.allergies, avoided_ingredients = EXCLUDED.avoided_ingredients
            """,
            (actual_cid, json.dumps(algs), avoided)
        )

    # 2. Seed Real Orders & Order Items
    orders_data = [
        (
            "ORD-20261011-001", customer_map.get("joshua", "cust_joshua"), "Joshua", "Senopati No. 42, Jaksel",
            "PREPARING", "PAID", 84000, ["Udang / Krustasea"],
            [("Senin", "menu_senin_ayam-rosemary", 1), ("Selasa", "menu_selasa_ayam-salted-egg", 1)]
        ),
        (
            "ORD-20261011-002", customer_map.get("maya", "cust_maya"), "Maya Pramesti", "Pondok Indah B3/12, Jaksel",
            "READY", "PAID", 126000, ["Kacang Tanah"],
            [("Senin", "menu_senin_beef-bulgogi", 1), ("Rabu", "menu_rabu_ikan-kakap", 1), ("Kamis", "menu_kamis_rendang-sapi", 1)]
        ),
        (
            "ORD-20261011-003", customer_map.get("budi", "cust_budi"), "Budi Santoso", "Menara Mandiri Lt. 14, Sudirman",
            "COMPLETED", "PAID", 84000, ["Gluten / Gandum"],
            [("Senin", "menu_senin_ayam-rosemary", 1), ("Jumat", "menu_jumat_salmon-lemon", 1)]
        ),
        (
            "ORD-20261011-004", customer_map.get("siti", "cust_siti"), "Siti Rahma", "Apartemen Casablanca Tower A-21",
            "PREPARING", "PAID", 42000, ["Susu / Laktosa"],
            [("Kamis", "menu_kamis_tumis-ayam-jamur", 1)]
        ),
        (
            "ORD-20261011-005", customer_map.get("rudi", "cust_rudi"), "Rudi Hermawan", "Kuningan Timur No. 8, Jaksel",
            "PENDING", "UNPAID", 126000, [],
            [("Kamis", "menu_kamis_udang-bakar-madu", 1), ("Jumat", "menu_jumat_ayam-taliwang", 1), ("Sabtu", "menu_sabtu_nasi-merah-ayam", 1)]
        ),
    ]

    for oid, cid, cname, addr, status, pay_status, total, algs, items in orders_data:
        # Check if package exists or use first package
        pkg = supabase.execute_one("SELECT code FROM packages LIMIT 1")
        pkg_code = pkg["code"] if pkg else "pkg_custom"

        supabase.execute_write(
            """
            INSERT INTO orders (
                order_id, customer_id, customer_name, delivery_address,
                status, payment_status, total, subtotal, selected_allergens,
                package_code, meal_count, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (order_id) DO UPDATE
            SET status = EXCLUDED.status, payment_status = EXCLUDED.payment_status, total = EXCLUDED.total
            """,
            (oid, cid, cname, addr, status, pay_status, total, total, algs, pkg_code, len(items))
        )

        # Clear existing items and insert
        supabase.execute_write("DELETE FROM order_items WHERE order_id = %s", (oid,))
        for idx, (hari, mid, _) in enumerate(items):
            # Check if menu exists, or find by day
            actual_menu = supabase.execute_one("SELECT menu_id FROM menus WHERE menu_id = %s OR hari = %s LIMIT 1", (mid, hari))
            actual_mid = actual_menu["menu_id"] if actual_menu else mid
            supabase.execute_write(
                """
                INSERT INTO order_items (order_id, hari, menu_id, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                (oid, hari, actual_mid, idx)
            )

    # 3. Seed Suppliers
    suppliers_data = [
        ("sup_daging_nusantara", "CV Daging Segar Nusantara (Pak Hadi)", "Daging & Unggas", "+6281326332247", "hadi.daging@dovasuplier.com", "Pasar Modern BSD Blok A-12", 4.9, 1),
        ("sup_sayur_lembang", "Tani Organik Lembang (Ibu Ningsih)", "Sayur & Nabati", "+6285866408193", "ningsih.tani@lembangfresh.com", "Jl. Raya Maribaya No. 88, Lembang", 4.8, 1),
        ("sup_muara_baru", "Muara Baru Seafood Mandiri (Pak Johan)", "Ikan & Seafood", "+6281900112233", "johan.seafood@muarabaru.id", "Kawasan Pelabuhan Muara Baru Blok D", 4.7, 2),
    ]

    for sid, name, cat, phone, email, addr, rat, lt in suppliers_data:
        supabase.execute_write(
            """
            INSERT INTO suppliers (supplier_id, name, category, phone, email, address, rating, lead_time_days, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            ON CONFLICT (supplier_id) DO UPDATE
            SET name = EXCLUDED.name, phone = EXCLUDED.phone, rating = EXCLUDED.rating
            """,
            (sid, name, cat, phone, email, addr, rat, lt)
        )

    # Supplier Items
    items_data = [
        ("sup_daging_nusantara", "Fillet Dada Ayam Organik", "kg", 45000, 5),
        ("sup_daging_nusantara", "Daging Sapi Has Dalam (Tenderloin)", "kg", 130000, 3),
        ("sup_sayur_lembang", "Brokoli Organik Segar", "kg", 25000, 5),
        ("sup_sayur_lembang", "Ubi Madu Cilembu", "kg", 18000, 10),
        ("sup_sayur_lembang", "Jamur Tiram & Shiitake", "kg", 32000, 3),
        ("sup_muara_baru", "Udang Windu Segar (Size 30)", "kg", 115000, 3),
        ("sup_muara_baru", "Fillet Ikan Kakap Merah", "kg", 85000, 5),
        ("sup_muara_baru", "Salmon Segar Norwegia", "kg", 240000, 2),
    ]

    supabase.execute_write("DELETE FROM supplier_items")
    for sid, iname, unit, price, moq in items_data:
        supabase.execute_write(
            """
            INSERT INTO supplier_items (supplier_id, ingredient_name, unit, price_per_unit, moq, lead_time_days)
            VALUES (%s, %s, %s, %s, %s, 1)
            """,
            (sid, iname, unit, price, moq)
        )

    # 4. Seed Purchase Orders (PO)
    supabase.execute_write("DELETE FROM po_items")
    supabase.execute_write("DELETE FROM purchase_orders")
    
    pos = [
        ("PO-20261011-001", "sup_daging_nusantara", "SENT", 675000, "Pengiriman H-1 sebelum masak."),
        ("PO-20261011-002", "sup_sayur_lembang", "ACCEPTED", 340000, "Kirim subuh pukul 05:00 WIB."),
        ("PO-20261011-003", "sup_muara_baru", "DRAFT", 585000, "Menunggu konfirmasi admin untuk menu Kamis."),
    ]

    for poid, sid, stat, total, notes in pos:
        supabase.execute_write(
            """
            INSERT INTO purchase_orders (po_id, supplier_id, status, total_amount, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (poid, sid, stat, total, notes)
        )

    po_lines = [
        ("PO-20261011-001", "Fillet Dada Ayam Organik", 15.0, "kg", 45000, 675000),
        ("PO-20261011-002", "Brokoli Organik Segar", 10.0, "kg", 25000, 250000),
        ("PO-20261011-002", "Ubi Madu Cilembu", 5.0, "kg", 18000, 90000),
        ("PO-20261011-003", "Udang Windu Segar", 3.0, "kg", 115000, 345000),
        ("PO-20261011-003", "Fillet Ikan Kakap Merah", 2.0, "kg", 85000, 170000),
    ]

    for poid, iname, qty, unit, uprice, sub in po_lines:
        supabase.execute_write(
            """
            INSERT INTO po_items (po_id, item_name, qty, unit, unit_price, subtotal)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (poid, iname, qty, unit, uprice, sub)
        )

    # 5. Seed Inventory Stocks
    stocks = [
        ("Fillet Dada Ayam Organik", 12.5, 5.0, "kg", "AMBIL_AMAN"),
        ("Daging Sapi Has Dalam", 8.0, 3.0, "kg", "AMBIL_AMAN"),
        ("Udang Windu Segar", 1.8, 3.0, "kg", "MENIPIS"),
        ("Ubi Madu Cilembu", 15.0, 5.0, "kg", "AMBIL_AMAN"),
        ("Brokoli Organik Segar", 2.2, 4.0, "kg", "MENIPIS"),
        ("Bumbu Kacang Tanah", 0.5, 2.0, "kg", "HABIS"),
    ]

    for iname, cur, mn, unit, stat in stocks:
        supabase.execute_write(
            """
            INSERT INTO inventory_stocks (ingredient_name, current_stock, min_stock, unit, status, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (ingredient_name) DO UPDATE
            SET current_stock = EXCLUDED.current_stock, status = EXCLUDED.status
            """,
            (iname, cur, mn, unit, stat)
        )

    # 6. Seed Notification Outbox (Automated WhatsApp & Telegram)
    notifications = [
        ("customer", "+6281234567890", "Joshua", "whatsapp", "ORDER_PAID", "Halo Kak Joshua! Pembayaran ORD-20261011-001 (Rp84.000) terkonfirmasi. Tim dapur Dova Kitchen mulai menyiapkan hidangan sehatmu!"),
        ("customer", "+6281398765432", "Maya Pramesti", "whatsapp", "TICKET_COOKING", "Update Dova Kitchen: Pesanan ORD-20261011-002 sedang dimasak di workstation bebas kacang steril."),
        ("supplier", "+6281326332247", "Pak Hadi (Daging)", "whatsapp", "PO_SENT", "Yth. Pak Hadi, PO baru PO-20261011-001 (15 kg Fillet Ayam) telah disetujui. Mohon dikirim besok pagi. Terima kasih!"),
        ("supplier", "+6285866408193", "Ibu Ningsih (Sayur)", "whatsapp", "PO_SENT", "Yth. Ibu Ningsih, PO-20261011-002 (Brokoli & Ubi Madu) mohon disiapkan pengiriman subuh 05:00 WIB."),
        ("admin", "+6281326332247", "Admin Dova", "telegram", "TRENDING_ORDER_ALERT", "⚠️ PERINGATAN TREN: Pesanan Ayam Rosemary & Beef Bulgogi naik 45%! Pastikan stok fillet ayam dan daging sapi mencukupi."),
    ]

    supabase.execute_write("DELETE FROM notification_outbox")
    for rtype, rphone, rname, chan, evtype, msg in notifications:
        supabase.execute_write(
            """
            INSERT INTO notification_outbox (recipient_type, recipient_phone, recipient_name, channel, event_type, message, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'SENT', NOW())
            """,
            (rtype, rphone, rname, chan, evtype, msg)
        )

    print("✅ Seeding selesai! Data pelanggan, pesanan, supplier, stok, dan outbox berhasil diperbarui di Supabase.")

if __name__ == "__main__":
    run_seed()
