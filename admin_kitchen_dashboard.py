"""
DovaGenome — Admin Portal (Analytics & Katalog)
===============================================
Untuk pemilik usaha dan admin: ringkasan performa, papan kendali penuh,
penjadwalan mingguan, pengelolaan katalog (menu / alergen / paket), pratinjau
halaman tamu, dan diagnosa sistem.

Cara menjalankan:
    streamlit run admin_kitchen_dashboard.py

Pembagian peran:
    • `kitchen_dashboard.py` → eksekusi harian tim dapur.
    • `landing_page.py`       → situs publik untuk pelanggan.
    • berkas ini             → kendali & katalog.
"""

from __future__ import annotations

import os

import streamlit as st

import data as D
import theme as T

T.page_config("Admin Portal", icon="🧭", layout="wide")
T.inject_css()

BOARD = ["PENDING", "PREPARING", "READY"]
COLLECTION_PACKAGES  = "catering_packages"
COLLECTION_ALLERGENS = "allergen_definitions"
COLLECTION_MENUS     = "catering_menus"

REFRESH_OPTIONS = [0, 15, 30, 60, 120]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _db():
    return D.connect_db()


@st.cache_data(ttl=60, show_spinner=False)
def catalog() -> dict:
    return D.load_catalog(_db())


def fetch_orders(statuses: list[str]) -> list[dict]:
    rows = D.fetch_orders(_db(), statuses)
    rows.sort(key=lambda o: D.parse_dt(o.get("created_at")) or D.now_wib())
    return rows


def closed_today() -> tuple[int, int]:
    """(selesai hari ini, dibatalkan hari ini)."""
    rows = D.fetch_orders(_db(), ["COMPLETED", "CANCELLED"], limit=500,
                          fallback_to_demo=False)
    today = D.now_wib().date()
    done = cancelled = 0
    for row in rows:
        dt = D.parse_dt(row.get("updated_at") or row.get("created_at"))
        if dt and dt.astimezone(D.WIB).date() == today:
            if row.get("status") == "COMPLETED":
                done += 1
            else:
                cancelled += 1
    return done, cancelled


def _invalidate() -> None:
    st.cache_data.clear()


def _save(collection: str, doc: dict, message: str) -> None:
    try:
        D.upsert_doc(_db(), collection, doc)
        _invalidate()
        st.success(f"✅ {message}")
        st.caption("Bot Telegram memakai data terbaru paling lama 2 menit lagi.")
    except Exception as exc:
        st.error(f"Gagal menyimpan ke Astra DB: {exc}")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def sidebar() -> None:
    live = _db() is not None
    with st.sidebar:
        T.sidebar_brand("Admin Portal")

        T.st_markdown(T.note(
            "<b>Peran: Admin.</b> Kelola katalog, pantau performa, dan tinjau "
            "halaman tamu. Eksekusi harian adalah tugas tim dapur.",
            glyph="🧭",
        ))

        st.subheader("🔗 Halaman lain")
        st.caption("Jalankan tiap halaman di terminal terpisah:")
        st.code("streamlit run kitchen_dashboard.py", language=None)
        st.code("streamlit run landing_page.py", language=None)
        if D.telegram_link():
            st.link_button("🤖 Buka Bot Telegram", D.telegram_link(),
                           use_container_width=True)
        else:
            st.caption("⚠️ `TELEGRAM_BOT_USERNAME` belum diisi di `.env`.")

        st.divider()
        st.subheader("🔄 Penyegaran")
        st.select_slider(
            "Papan diperbarui setiap:",
            options=REFRESH_OPTIONS,
            value=30,
            format_func=lambda v: "Mati" if v == 0 else f"{v} detik",
            key="adm_interval",
        )

        st.divider()
        st.caption(f"Mode: {'🟢 Astra DB live' if live else '🟡 demo (data contoh)'}")
        st.caption("v3.0 · DovaGenome Precision Catering")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def header() -> None:
    now = D.now_wib()
    T.st_markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-end;
            flex-wrap:wrap;gap:16px;margin-bottom:20px">
  <div>
    <p class="dk-eyebrow-2">Admin Portal · {T.esc(now.strftime('%A, %d %B %Y'))}</p>
    <h1 style="font-size:2.3rem;margin:2px 0 6px">Kendali Dapur & Katalog</h1>
    <p class="dk-lede" style="margin:0">
      Alur fulfilment: <b>Diterima → Dimasak → Dikemas → Diantar</b>.
      Semua perubahan katalog langsung dipakai bot Telegram.
    </p>
  </div>
  <div class="dk-small dk-muted" style="text-align:right">
    {T.esc(now.strftime('%H:%M:%S'))} WIB
  </div>
</div>""")


# ---------------------------------------------------------------------------
# Tab 1 — ringkasan & papan kendali
# ---------------------------------------------------------------------------

def _kpi_overview() -> None:
    orders = fetch_orders(BOARD)
    counts = D.count_by_status(orders, BOARD)
    done, cancelled = closed_today()
    alerts = sum(1 for o in orders if D.order_allergens(o))
    waits = [D.elapsed_minutes(o.get("created_at")) for o in orders]
    avg   = int(sum(waits) / len(waits)) if waits else 0
    peak  = max(waits) if waits else 0

    T.st_markdown(T.kpi_row([
        ("📦 Pesanan aktif",  str(len(orders)), "belum selesai",           T.FOREST_600),
        ("🟡 Menunggu",       str(counts["PENDING"]),   "tidak dimasak",       T.GOLD_600),
        ("🔵 Dimasak",        str(counts["PREPARING"]), "di atas wajan",       T.FOREST_700),
        ("🟢 Siap kirim",     str(counts["READY"]),     "menunggu pengantaran", "#15803D"),
        ("🚨 Berpantangan",   str(alerts),              "zona steril khusus",  T.ROSE_600),
        ("⏱ Rata-rata tunggu", f"{avg} mnt",             "sejak tiket masuk",   T.GOLD_600),
        ("⏱ Tertua",          f"{peak} mnt",             "tiket terlama",       T.ROSE_600),
        ("✅ Selesai hari ini", f"{done}",               f"{cancelled} dibatalkan", "#15803D"),
    ]))


def _advance(order: dict, status: str) -> None:
    nxt = D.STATUS_META[status]["next"]
    if not nxt:
        return
    if not D.update_order_status(_db(), str(order.get("_id", "")), nxt):
        st.error("Gagal menyimpan status — Astra DB belum tersambung.")
        st.rerun()
        return
    meta = D.STATUS_META[nxt]
    st.toast(f"{D.order_id(order)} → {meta['label']}", icon=meta["emoji"])
    _invalidate()
    st.rerun()


@st.dialog("Batalkan pesanan ini?")
def _dialog_batal(order_id: str, label: str) -> None:
    st.write(
        f"Pesanan **{label}** akan ditandai `CANCELLED` dan keluar dari papan dapur. "
        "Tindakan ini hanya mengubah status — data tiket tetap tersimpan untuk audit."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("↩️ Batal", use_container_width=True):
            st.rerun()
    with c2:
        if st.button("⛔ Ya, batalkan", type="primary", use_container_width=True):
            D.update_order_status(_db(), order_id, "CANCELLED")
            st.toast(f"{label} dibatalkan", icon="⛔")
            _invalidate()
            st.rerun()


def _admin_column(status: str, orders: list[dict], menus: dict) -> None:
    meta = D.STATUS_META[status]
    T.st_markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:4px 0 14px">
  <span style="font-size:1.2rem">{meta['emoji']}</span>
  <div style="font-weight:800;font-size:1rem;color:{meta['color']}">
    {T.esc(meta['label'])}
  </div>
  <span class="dk-chip" style="margin-left:auto;background:{meta['bg']};
        color:{meta['color']};border:1px solid {meta['border']}">{len(orders)}</span>
</div>""")

    if not orders:
        st.markdown(T.empty_state("Kosong.", glyph="✨"))
        return

    for order in orders:
        st.markdown(T.order_card(order, menus, show_sop=True))
        doc_id = str(order.get("_id", ""))

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            if meta["next"]:
                if st.button(f"{meta['action_emoji']} {meta['action']}",
                             key=f"adm_{status}_{doc_id}", type="primary",
                             use_container_width=True):
                    _advance(order, status)
        with c2:
            with st.popover("Detail", use_container_width=True):
                st.json(order)
                st.caption(f"chat_id: {order.get('chat_id', '—')}")
        with c3:
            if st.button("⛔", key=f"adm_cancel_{doc_id}",
                         use_container_width=True, help="Batalkan pesanan"):
                _dialog_batal(doc_id, D.order_id(order))


@st.fragment(run_every=st.session_state.get("adm_interval", 30) or None)
def _papan() -> None:
    orders = fetch_orders(BOARD)
    menus  = catalog()["menus"]
    for col, status in zip(st.columns(3, gap="medium"), BOARD):
        with col, st.container(border=True):
            _admin_column(status, [o for o in orders if o.get("status") == status], menus)


def tab_ringkasan() -> None:
    _kpi_overview()
    T.st_markdown("<div style='height:26px'></div>")
    T.st_markdown(T.note(
        "<b>Alur kerja:</b> Tiket masuk berstatus <b>Menunggu</b> → "
        "<b>Dimasak</b> → <b>Siap kirim</b> → <b>Selesai</b>. "
        "Tim dapur memakai Papan Kerja Dapur; admin cukup memantau di sini.",
        glyph="🧭",
    ))
    T.st_markdown("<div style='height:16px'></div>")
    _papan()


# ---------------------------------------------------------------------------
# Tab 2 — jadwal mingguan
# ---------------------------------------------------------------------------

def tab_jadwal() -> None:
    orders = fetch_orders(BOARD)
    menus  = catalog()["menus"]
    today  = D.today_name()

    T.st_markdown(T.section_head(
        "Jadwal Mingguan",
        "Enam hari layanan, satu menu per hari.",
        "Setiap kartu menampilkan menu hari itu beserta pesanan yang terjadwal.",
    ))

    if not today:
        T.st_markdown(T.note(
            "<b>Hari Minggu.</b> DovaGenome tidak melayani pengiriman hari ini.",
            kind="warn", glyph="🗓️",
        ))
        T.st_markdown("<div style='height:14px'></div>")

    cards = []
    for day in D.DAYS:
        doc       = menus.get(day, {})
        day_orders = [o for o in orders if day in D.scheduled_days(o)]
        allergens  = sum(1 for o in day_orders if D.order_allergens(o))
        is_today   = day == today

        names = "".join(
            f"<li>{T.esc(D.order_customer(o))} "
            f"<span class='dk-muted'>({T.esc(D.order_id(o))})</span></li>"
            for o in day_orders
        ) or "<li class='dk-muted'>Tidak ada pesanan terjadwal</li>"

        alert = (
            f"<div class='dk-alert' style='margin-top:10px'><b>🚨 {allergens} pesanan "
            f"berpantangan</b> pada hari ini — siapkan peralatan steril khusus.</div>"
            if allergens else ""
        )
        head_cls = "dk-day-head is-today" if is_today else "dk-day-head"
        tag      = "Hari ini" if is_today else f"{len(day_orders)} pesanan"

        cards.append(f"""
<div class="dk-day">
  <div class="{head_cls}">
    <span class="dk-day-name">{T.esc(day)}</span>
    <span class="dk-day-tag">{T.esc(tag)}</span>
  </div>
  <div class="dk-day-body">
    <h4>{T.esc(doc.get('nama_menu', '—'))}</h4>
    <p class="dk-day-desc">{T.esc(doc.get('deskripsi', ''))}</p>
    <ul class="dk-list">{names}</ul>
    {alert}
  </div>
</div>""")

    T.st_markdown(f'<div class="dk-grid dk-c3">{"".join(cards)}</div>')


# ---------------------------------------------------------------------------
# Tab 3 — katalog
# ---------------------------------------------------------------------------

def _katalog_menu() -> None:
    T.st_markdown(T.note(
        "Menu ini yang dibaca bot Telegram saat pelanggan mempratinjau mingguan. "
        "Setelah disimpan, perubahan tampil maksimal 2 menit.", glyph="🍽️",
    ))
    T.st_markdown("<div style='height:14px'></div>")

    day = st.selectbox("Hari yang diedit", D.DAYS, key="adm_menu_day")
    existing = {}
    for doc in D.fetch_collection(_db(), COLLECTION_MENUS, limit=10, sort={"hari": 1}):
        if doc.get("hari") == day:
            existing = doc
            break

    bahan_text = ", ".join(
        b.get("nama", "") for b in existing.get("bahan_detail", []) if isinstance(b, dict)
    )
    alat_text = ", ".join(existing.get("alat_dapur_steril", []) or [])

    with st.form(f"form_menu_{day}", clear_on_submit=False):
        nama = st.text_input("Nama menu", value=existing.get("nama_menu", ""),
                             placeholder="cth. Ayam Panggang Rosemary & Ubi Panggang")
        c1, c2 = st.columns(2)
        with c1:
            deskripsi = st.text_area("Deskripsi", value=existing.get("deskripsi", ""),
                                     height=96,
                                     placeholder="Metode memasak, karakter rasa, dst.")
            bahan = st.text_area("Bahan (pisahkan dengan koma)", value=bahan_text,
                                 height=110,
                                 placeholder="Fillet Dada Ayam, Minyak Zaitun, Ubi Madu")
        with c2:
            st.caption("Alat & zona dapur wajib diisi agar tim dapur aman.")
            alat = st.text_area("Peralatan & zona steril (pisahkan dengan koma)",
                                value=alat_text, height=136,
                                placeholder="Oven Station 1 (Non-Gluten), Talenan Hijau #1")
        if st.form_submit_button(f"💾 Simpan menu {day}", type="primary",
                                 use_container_width=True):
            if not nama.strip():
                st.error("Nama menu tidak boleh kosong.")
            elif not alat.strip():
                st.error("Isi minimal satu peralatan/zona steril.")
            else:
                doc = {
                    "_id":               f"menu_{day.lower()}",
                    "hari":              day,
                    "nama_menu":         nama.strip(),
                    "deskripsi":         deskripsi.strip(),
                    "bahan_detail": [
                        {"nama": b.strip(), "sumber": "—", "potensi_alergen": "Diperiksa dapur"}
                        for b in bahan.split(",") if b.strip()
                    ],
                    "alat_dapur_steril": [a.strip() for a in alat.split(",") if a.strip()],
                }
                _save(COLLECTION_MENUS, doc, f"Menu <b>{day}</b> tersimpan.")

    if existing:
        with st.expander(f"Konfigurasi dapur untuk {day} — tampil di menu pelanggan"):
            st.json(existing)


def _toggle(collection: str, doc_id: str, active: bool, label: str) -> None:
    if D.update_fields(_db(), collection, doc_id, {"active": not active}):
        _invalidate()
        st.toast(f"{label} {'diaktifkan' if not active else 'dinonaktifkan'}",
                 icon="🔁")
        st.rerun()


def _katalog_alergen() -> None:
    rows = D.fetch_collection(_db(), COLLECTION_ALLERGENS, limit=40)
    live = bool(rows)
    if live:
        T.st_markdown(T.section_head("Profil pantangan", "Aktif untuk pelanggan."))
        for alg in rows:
            code  = str(alg.get("_id") or alg.get("code"))
            label = alg.get("label", code)
            active = bool(alg.get("active", True))
            chip = (
                "<span class='dk-chip' style='background:#EBF7F0;color:#15803D;"
                "border:1px solid #C6E7D3'>🟢 Aktif</span>"
                if active else
                "<span class='dk-chip' style='background:#F1F5F9;color:#64748B;"
                "border:1px solid #DCE3EB'>⚪ Nonaktif</span>"
            )
            T.st_markdown(f"""
<div class="dk-card" style="padding:16px 20px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;gap:14px;align-items:center;
              flex-wrap:wrap">
    <div>
      <div style="font-weight:800">{T.esc(label)}</div>
      <div class="dk-small dk-muted">{T.esc(alg.get('risiko', '—'))}</div>
      <div class="dk-small dk-muted dk-mono">{T.esc(code)}</div>
    </div>
    {chip}
  </div>
</div>""")
            if st.button("🔁 Ubah status", key=f"adm_alg_{code}",
                         use_container_width=False):
                _toggle(COLLECTION_ALLERGENS, code, active, label)
        st.divider()
    else:
        T.st_markdown(T.note(
            "Belum ada data di Astra DB. Jalankan <code>python seed_catering_data.py</code> "
            "atau tambahkan lewat formulir di bawah.", kind="warn", glyph="⚠️",
        ))

    T.st_markdown(T.section_head("Tambah / ubah profil", "Kode unik sebagai pengenal."))
    with st.form("form_alergen", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            code_in  = st.text_input("Kode", placeholder="alg_gluten",
                                     help="Format: alg_<nama>, huruf kecil tanpa spasi.")
            label_in = st.text_input("Label", placeholder="Bebas Gluten")
        with c2:
            risiko = st.text_input("Bahan berisiko",
                                   placeholder="Gandum, terigu, kecap kedelai biasa")
            aktif = st.checkbox("Tampilkan ke pelanggan", value=True)
        if st.form_submit_button("💾 Simpan profil", type="primary",
                                 use_container_width=True):
            code_in, label_in = code_in.strip(), label_in.strip()
            if not code_in or not label_in:
                st.error("Kode dan label wajib diisi.")
            else:
                _save(COLLECTION_ALLERGENS, {
                    "_id": code_in, "code": code_in, "label": label_in,
                    "risiko": risiko.strip(), "active": bool(aktif),
                }, f"Profil <b>{label_in}</b> tersimpan.")


def _katalog_paket() -> None:
    rows = D.fetch_collection(_db(), COLLECTION_PACKAGES, limit=40)
    if rows:
        T.st_markdown(T.section_head("Paket katering", "Tampil di bot dan landing page."))
        for pkg in rows:
            code  = str(pkg.get("_id") or pkg.get("code"))
            active = bool(pkg.get("active", True))
            chip = (
                "<span class='dk-chip' style='background:#EBF7F0;color:#15803D;"
                "border:1px solid #C6E7D3'>🟢 Aktif</span>" if active else
                "<span class='dk-chip' style='background:#F1F5F9;color:#64748B;"
                "border:1px solid #DCE3EB'>⚪ Nonaktif</span>"
            )
            price = (
                f"<b>{T.esc(pkg['price'])}</b>" if pkg.get("price") else
                "<span class='dk-muted'>harga via bot</span>"
            )
            T.st_markdown(f"""
<div class="dk-card" style="padding:16px 20px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;gap:14px;align-items:center;
              flex-wrap:wrap">
    <div>
      <div style="font-weight:800">{T.esc(pkg.get('name', code))}</div>
      <div class="dk-small dk-muted">{T.esc(pkg.get('description', '—'))}</div>
      <div style="margin-top:8px">{T.day_pills(pkg.get('days', []))}</div>
      <div class="dk-small dk-muted dk-mono">{T.esc(code)} · {price}</div>
    </div>
    {chip}
  </div>
</div>""")
            if st.button("🔁 Ubah status", key=f"adm_pkg_{code}"):
                _toggle(COLLECTION_PACKAGES, code, active, pkg.get("name", code))
        st.divider()
    else:
        T.st_markdown(T.note(
            "Belum ada paket di Astra DB. Jalankan <code>python seed_catering_data.py</code>.",
            kind="warn", glyph="⚠️",
        ))

    T.st_markdown(T.section_head("Tambah / ubah paket", "Minimal satu hari layanan."))
    with st.form("form_paket", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            code_in = st.text_input("Kode paket", placeholder="pkg_full")
            name_in = st.text_input("Nama paket", placeholder="Full Week (Senin – Sabtu)")
            desc_in = st.text_input("Deskripsi", placeholder="Catering 6 hari kerja")
        with c2:
            days_in = st.multiselect("Hari layanan", D.DAYS, default=D.DAYS)
            price_in = st.number_input("Harga per paket (opsional)", min_value=0,
                                       step=25000, value=0)
            aktif = st.checkbox("Tampilkan ke pelanggan", value=True, key="pkg_aktif")
        if st.form_submit_button("💾 Simpan paket", type="primary", use_container_width=True):
            code_in, name_in = code_in.strip(), name_in.strip()
            if not code_in or not name_in:
                st.error("Kode dan nama paket wajib diisi.")
            elif not days_in:
                st.error("Pilih minimal satu hari layanan.")
            else:
                doc = {
                    "_id": code_in, "code": code_in, "name": name_in,
                    "days": days_in, "description": desc_in.strip(),
                    "active": bool(aktif),
                }
                if price_in:
                    doc["price"] = int(price_in)
                _save(COLLECTION_PACKAGES, doc, f"Paket <b>{name_in}</b> tersimpan.")


def tab_katalog() -> None:
    t_menu, t_alg, t_pkg = st.tabs([
        "🍽️ Menu Mingguan", "🛡️ Profil Pantangan", "📦 Paket Katering",
    ])
    with t_menu:
        _katalog_menu()
    with t_alg:
        _katalog_alergen()
    with t_pkg:
        _katalog_paket()


# ---------------------------------------------------------------------------
# Tab 4 — halaman tamu
# ---------------------------------------------------------------------------

def tab_tamu() -> None:
    T.st_markdown(T.section_head(
        "Halaman Tamu",
        "Situs publik yang dilihat pelanggan.",
        "Jalankan `streamlit run landing_page.py` untuk membuka secara terpisah, "
        "atau bagikan tautan deployment Anda.",
    ))

    c1, c2 = st.columns(2)
    with c1:
        url = D.telegram_link("order")
        if url:
            st.link_button("🤖 Buka alur pemesanan di Telegram", url,
                           type="primary", use_container_width=True)
        else:
            st.button("🤖 Telegram belum dikonfigurasi", disabled=True,
                      use_container_width=True)
        st.caption("Deep-link: `?start=order` membuka langsung langkah pilih paket.")
    with c2:
        st.caption(
            "Deep-link yang didukung: `order` (pilih paket), `ai` (konsultasi), "
            "`menu` (pratinjau mingguan), `passport` (Dietary Passport)."
        )

    st.divider()
    from landing_page import render_landing

    render_landing(preview=True)


# ---------------------------------------------------------------------------
# Tab 5 — sistem
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    if not value:
        return "—"
    return f"{value[:6]}…{value[-4:]}" if len(value) > 14 else "••••"


def tab_sistem() -> None:
    db   = _db()
    live = db is not None

    T.st_markdown(T.section_head("Diagnosis Sistem", "Koneksi, kredensial, dan tautan."))

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Kredensial `.env`**")
        rows = [
            ("ASTRA_DB_API_ENDPOINT", os.getenv("ASTRA_DB_API_ENDPOINT", "")),
            ("ASTRA_DB_APPLICATION_TOKEN", os.getenv("ASTRA_DB_APPLICATION_TOKEN", "")),
            ("TELEGRAM_TOKEN", os.getenv("TELEGRAM_TOKEN", "")),
            ("TELEGRAM_BOT_USERNAME", os.getenv("TELEGRAM_BOT_USERNAME", "")),
            ("LANGFLOW_API_KEY", os.getenv("LANGFLOW_API_KEY", "")),
        ]
        body = "".join(
            f"<tr><td><b>{T.esc(k)}</b></td>"
            f"<td class='dk-mono'>{T.esc(_mask(v))}</td>"
            f"<td>{'🟢 terisi' if v else '🔴 kosong'}</td></tr>"
            for k, v in rows
        )
        T.st_markdown(f"""
<div class="dk-card" style="padding:4px 6px">
  <table class="dk-table">
    <thead><tr><th>Variabel</th><th>Nilai</th><th>Status</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>""")

    with right:
        st.markdown("**Collection**")
        if live:
            try:
                names = sorted(db.list_collection_names())
            except Exception as exc:
                names = [f"gagal: {exc}"]
            for name in names:
                try:
                    count = len(list(db.get_collection(name).find({}, limit=0)))
                except Exception:
                    count = "?"
                T.st_markdown(
                    f"<div class='dk-card' style='padding:12px 16px;margin-bottom:8px;"
                    f"display:flex;justify-content:space-between'>"
                    f"<span class='dk-mono'>{T.esc(name)}</span>"
                    f"<b>{T.esc(str(count))} dok</b></div>",
                )
        else:
            T.st_markdown(T.note(
                "<b>Astra DB tidak tersambung.</b> Dashboard berjalan dengan data "
                "contoh. Isi kredensial di `.env` lalu jalankan "
                "<code>python seed_catering_data.py</code>.",
                kind="warn", glyph="🔌",
            ))

    st.divider()
    if D.telegram_link():
        T.st_markdown(T.note(
            f"Bot Telegram aktif: <b>@{T.esc(D.bot_username())}</b> — "
            f"{D.telegram_link_html('order', 'buka alur pemesanan')}",
            glyph="🤖",
        ))
    else:
        T.st_markdown(T.note(
            "Tautan Telegram belum aktif. Tambahkan <code>TELEGRAM_BOT_USERNAME</code> "
            "ke file `.env` (tanpa tanda <code>@</code>).", kind="warn", glyph="🤖",
        ))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

sidebar()
header()

tab_1, tab_2, tab_3, tab_4, tab_5 = st.tabs([
    "📊 Ringkasan & Papan", "🗓️ Jadwal Mingguan", "⚙️ Katalog",
    "🌐 Halaman Tamu", "🔧 Sistem",
])

with tab_1:
    tab_ringkasan()
with tab_2:
    tab_jadwal()
with tab_3:
    tab_katalog()
with tab_4:
    tab_tamu()
with tab_5:
    tab_sistem()