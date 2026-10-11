# Alur Target (Target Flow) — Dapur Harian (Bagian A 4.1 – 4.3)

Diagram target ini menjadi acuan tunggal (*single source of truth*) untuk Web dan Bot Telegram. Keduanya adalah **klien tipis** dari satu backend yang sama.

---

## 1. Arsitektur Target (Satu Backend Tunggal)

```mermaid
flowchart TD
    subgraph Klien
        WEB[React Web App - apps/web]
        BOT[Telegram Bot - aiogram 3 / apps/bot]
    end

    subgraph Backend Tunggal - FastAPI
        API_AUTH[/api/auth & /me]
        API_DRAFT[/api/drafts Server-side OrderDraft]
        API_MENU[/api/menu/window Jendela & Pencocokan Alergi]
        API_ORDER[/api/orders & /api/orders/:id/pay]
        API_ADDR[/api/me/addresses]
    end

    subgraph Data & Layanan
        DB[(PostgreSQL 16)]
        REDIS[(Redis 7)]
        PAY[Payment Gateway - Midtrans Sandbox]
    end

    WEB --> API_AUTH
    WEB --> API_DRAFT
    WEB --> API_MENU
    WEB --> API_ORDER
    WEB --> API_ADDR

    BOT --> API_AUTH
    BOT --> API_DRAFT
    BOT --> API_MENU
    BOT --> API_ORDER
    BOT --> API_ADDR

    API_AUTH --> DB
    API_DRAFT --> DB
    API_MENU --> DB
    API_ORDER --> DB
    API_ORDER --> REDIS
    API_ORDER --> PAY
```

---

## 2. Alur Wizard 8 Langkah Target (Satu Layar / Pesan = Satu Keputusan)

```mermaid
sequenceDiagram
    autonumber
    actor C as Pelanggan (Web / Bot)
    participant S as Backend API
    participant D as PostgreSQL / OrderDraft
    participant P as Gateway Pembayaran

    Note over C,S: 1. Alergi (Returning Customer check)
    C->>S: GET /me/allergies
    alt Returning Customer
        S-->>C: Tercatat alergi [A, B]. (Tidak ada perubahan / Tambah / Kurangi)
    else Pelanggan Baru
        S-->>C: Daftar multi-select alergen + catatan teks
    end
    C->>S: PATCH /drafts/:id {step: 1, allergies: [...]}
    S->>D: Simpan OrderDraft current_step=1

    Note over C,S: 2. Catatan Diet (Opsional)
    C->>S: PATCH /drafts/:id {step: 2, diet_notes: "..."}
    S->>D: Simpan OrderDraft current_step=2

    Note over C,S: 3. Pilih Menu (1 Hari Per Layar, 3 Menu/Hari)
    C->>S: GET /menu/window (hitung cutoff 20:00, cocokkan alergi)
    S-->>C: Daftar menu per hari (status: safe/warning + reasons)
    C->>S: PATCH /drafts/:id {step: 3, daily_menus: [...]}

    Note over C,S: 4. Jumlah Porsi (Stepper Qty)
    C->>S: PATCH /drafts/:id {step: 4, portions: {menu_id: qty}}

    Note over C,S: 5. Ringkasan Keranjang
    C->>S: GET /drafts/:id/summary
    S-->>C: Total dihitung server, rincian menu & jadwal

    Note over C,S: 6. Alamat Kirim & Catatan Kurir
    C->>S: GET /me/addresses (pilihan cepat Rumah/Kantor)
    C->>S: PATCH /drafts/:id {step: 6, address_id / custom_address}

    Note over C,S: 7. Pembayaran (Batas Waktu 10 Menit)
    C->>S: POST /orders {draft_id}
    S->>P: Buat transaksi (Midtrans QRIS/VA, expiry: now + 10m)
    P-->>S: QR URL / VA Number, expires_at
    S-->>C: Tampilkan countdown 10 menit + QRIS / VA

    Note over C,S: 8. Pelacakan Pesanan (Tiket Dapur)
    P-->>S: Webhook transaksi lunas (Signature valid & Idempotent)
    S->>D: Update order: status=paid, buat KitchenTicket per tanggal
    S-->>C: Status: paid -> accepted -> cooking -> packed -> out_for_delivery
```
