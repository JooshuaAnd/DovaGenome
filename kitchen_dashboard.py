"""
DovaGenome — Papan Kerja Dapur (KDS)
=====================================
Halaman eksekusi untuk staf dapur: satu kartu per pesanan, satu tombol aksi
per kartu, dan urutan yang tidak pernah ambigu.

    DITERIMA  →  DIMASAK  →  DIKEMAS  →  DIANTAR

Perbedaan dengan `admin_kitchen_dashboard.py`:
    • Halaman ini khusus eksekusi harian — tidak ada form admin.
    • Analytics, katalog menu/alergen/paket, dan pratinjau landing page
      berada di Admin Portal.

Cara menjalankan:
    streamlit run kitchen_dashboard.py
"""

from __future__ import annotations

import streamlit as st

import data as D
import theme as T

T.page_config("Papan Kerja Dapur", icon="🍳", layout="wide")
T.inject_css()

#: Kolom papan kerja, sesuai urutan fulfilment
BOARD = ["PENDING", "PREPARING", "READY"]

COLUMN_HINT = {
    "PENDING":   "Diterima dari bot, belum disentuh.",
    "PREPARING": "Sedang dimasak — perhatikan zona steril.",
    "READY":     "Sudah dikemas, tunggu pengantaran.",
}

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


def apply_filters(orders: list[dict], only_alert: bool, search: str) -> list[dict]:
    if search.strip():
        key = search.strip().lower()
        orders = [
            o for o in orders
            if key in D.order_customer(o).lower() or key in D.order_id(o).lower()
        ]
    if only_alert:
        orders = [o for o in orders if D.order_allergens(o)]
    return orders


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def sidebar() -> None:
    with st.sidebar:
        T.sidebar_brand("Kitchen Display System")

        T.st_markdown(T.note(
            "<b>Peran: Tim Dapur.</b> Isi halaman ini adalah eksekusi harian. "
            "Kelola menu, allergen, dan paket ada di <b>Admin Portal</b>.",
            glyph="👨‍🍳",
        ))

        st.subheader("🎛️ Filter papan")
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("🟡 Diterima", value=True, key="kds_pending")
        with c2:
            st.checkbox("🔵 Dimasak", value=True, key="kds_preparing")
        c3, c4 = st.columns(2)
        with c3:
            st.checkbox("🟢 Dikemas", value=True, key="kds_ready")
        with c4:
            st.checkbox("🚨 Kritis", value=False, key="kds_alert",
                        help="Hanya pesanan dengan pantangan alergi")

        st.text_input("🔎 Cari nama / nomor tiket", placeholder="ORD-2026-081",
                      key="kds_search")

        st.divider()
        st.subheader("🔄 Penyegaran")
        st.select_slider(
            "Otomatis setiap:",
            options=REFRESH_OPTIONS,
            value=30,
            format_func=lambda v: "Mati" if v == 0 else f"{v} detik",
            key="kds_interval",
        )
        st.caption("Papan disegarkan otomatis; tombol status tetap berlaku instan.")

        st.divider()
        st.subheader("🧭 Alur hari ini")
        st.markdown(T.stepper(0))
        st.caption("Kotak bertanda ✓ adalah tahap yang sedang berjalan.")

        st.divider()
        st.caption("v3.0 · DovaGenome Precision Catering")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def header(orders: list[dict], live: bool) -> None:
    now    = D.now_wib()
    counts = D.count_by_status(orders, BOARD)
    alerts = sum(1 for o in orders if D.order_allergens(o))

    badge_bg   = "#EBF7F0" if live else "#FDF4E3"
    badge_fg   = "#15803D" if live else "#B45309"
    badge_bd   = "#C6E7D3" if live else "#EFDCB6"
    badge_txt  = "Astra DB tersambung" if live else "Mode demo — data contoh"

    T.st_markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-end;
            flex-wrap:wrap;gap:16px;margin-bottom:22px">
  <div>
    <p class="dk-eyebrow-2">{T.esc(now.strftime('%A'))} · {T.esc(now.strftime('%d %B %Y'))}</p>
    <h1 style="font-size:2.35rem;margin:2px 0 6px">Papan Kerja Dapur</h1>
    <p class="dk-lede" style="margin:0">
      Satu kartu = satu pesanan. Tekan tombol besar di bawah kartu untuk
      memindahkannya ke tahap berikutnya.
    </p>
  </div>
  <div class="dk-small dk-muted" style="text-align:right">
    <span class="dk-chip" style="background:{badge_bg};color:{badge_fg};
      border:1px solid {badge_bd}">{badge_txt}</span>
    <div style="margin-top:8px">{T.esc(now.strftime('%H:%M:%S'))} WIB</div>
  </div>
</div>""")

    T.st_markdown(T.kpi_row([
        ("🟡 Diterima",    str(counts["PENDING"]),   "siap masuk dapur",   T.GOLD_600),
        ("🔵 Sedang dimasak", str(counts["PREPARING"]), "di atas wajan",   T.FOREST_600),
        ("🟢 Dikemas",      str(counts["READY"]),     "tunggu pengantaran", "#15803D"),
        ("🚨 Berpantangan", str(alerts),              "butuh zona steril", T.ROSE_600),
    ]))
    T.st_markdown("<div style='height:26px'></div>")


# ---------------------------------------------------------------------------
# Kartu + aksi
# ---------------------------------------------------------------------------

def render_column(status: str, orders: list[dict]) -> None:
    meta = D.STATUS_META[status]
    T.st_markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:4px 0 14px">
  <span style="font-size:1.25rem">{meta['emoji']}</span>
  <div>
    <div style="font-weight:800;font-size:1.02rem;color:{meta['color']}">
      {T.esc(meta['label'])}
    </div>
    <div class="dk-small dk-muted">{T.esc(COLUMN_HINT[status])}</div>
  </div>
  <span class="dk-chip" style="margin-left:auto;background:{meta['bg']};
        color:{meta['color']};border:1px solid {meta['border']}">{len(orders)}</span>
</div>""")

    if not orders:
        st.markdown(T.empty_state(
            "Antrean kosong — semua tiket sudah dimasak." if status == "PENDING"
            else "Tidak ada pesanan di tahap ini.",
            glyph="✨",
        ))
        return

    menus = catalog()["menus"]
    for order in orders:
        st.markdown(T.order_card(order, menus), unsafe_allow_html=True)
        doc_id = str(order.get("_id", ""))
        if st.button(
            f"{meta['action_emoji']}  {meta['action']}",
            key=f"act_{status}_{doc_id}",
            type="primary",
            use_container_width=True,
        ):
            advance(order, status)


def advance(order: dict, status: str) -> None:
    """Pindahkan pesanan satu tahap, lalu segarkan papan."""
    nxt = D.STATUS_META[status]["next"]
    if not nxt:
        return
    if not D.update_order_status(_db(), str(order.get("_id", "")), nxt):
        st.error(
            "Gagal menyimpan status. Astra DB belum tersambung — periksa "
            "kredensial di `.env`, atau jalankan `python seed_catering_data.py`."
        )
        st.rerun()
        return

    meta = D.STATUS_META[nxt]
    st.toast(f"{D.order_id(order)} → {meta['label']}", icon=meta["emoji"])
    if nxt == "READY":
        st.toast("Segel anti-kontaminasi terpasang", icon="🔒")
    st.cache_data.clear()
    st.rerun()


# ---------------------------------------------------------------------------
# Papan (fragment agar bisa menyegarkan sendiri tanpa memblokir halaman)
# ---------------------------------------------------------------------------

def _selected_statuses() -> list[str]:
    return [s for s in BOARD if st.session_state.get(f"kds_{s.lower()}", True)]


@st.fragment(run_every=st.session_state.get("kds_interval", 30) or None)
def board() -> None:
    statuses = _selected_statuses()
    if not statuses:
        st.markdown(T.empty_state(
            "Semua filter status dimatikan. Aktifkan minimal satu di sidebar.",
            glyph="🎛️",
        ))
        return

    orders = apply_filters(
        fetch_orders(statuses),
        st.session_state.get("kds_alert", False),
        st.session_state.get("kds_search", ""),
    )

    for col, status in zip(st.columns(len(statuses), gap="medium"), statuses):
        with col, st.container(border=True):
            render_column(status, [o for o in orders if o.get("status") == status])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

sidebar()
header(fetch_orders(_selected_statuses()), live=_db() is not None)
board()