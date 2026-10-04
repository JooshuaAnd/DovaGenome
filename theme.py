"""
DovaGenome — Design System & Komponen UI Bersama
================================================
Satu sumber kebenaran untuk warna, tipografi, dan komponen HTML yang dipakai
oleh `kitchen_dashboard.py`, `admin_kitchen_dashboard.py`, dan
`landing_page.py`.

Arah visual: *light premium* — ivory hangat, hijau forest, dan aksen emas.
"""

from __future__ import annotations

import datetime
import html
from typing import Any, Iterable

import streamlit as st

import data as D

BRAND_NAME    = "DovaGenome"
BRAND_SUB     = "Precision Catering"
BRAND_TAGLINE = "Makan siang mingguan yang aman, steril, dan bisa dilacak sampai ke wajan."

# ---------------------------------------------------------------------------
# Palet
# ---------------------------------------------------------------------------

IVORY      = "#FBF8F3"
CREAM      = "#F4EDE1"
SURFACE    = "#FFFFFF"
INK        = "#1B2A24"
INK_SOFT   = "#41544C"
MUTED      = "#6E8078"
LINE       = "#E7DFD1"
FOREST_900 = "#12322A"
FOREST_700 = "#1F5648"
FOREST_600 = "#2A7261"
FOREST_100 = "#DCEAE5"
FOREST_50  = "#EFF6F3"
GOLD_600   = "#B8893B"
GOLD_500   = "#CFA055"
GOLD_50    = "#FBF3E3"
ROSE_600   = "#C2415A"
ROSE_50    = "#FDF1F3"


# ---------------------------------------------------------------------------
# Utilitas kecil
# ---------------------------------------------------------------------------

def esc(value: Any) -> str:
    """Escape teks agar aman disisipkan ke HTML."""
    return html.escape(str(value if value is not None else ""), quote=True)


def sla_minutes(minutes: int) -> str:
    return f"{minutes} mnt"


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

# Penting: CSS ditulis sebagai string biasa dengan token __TOKEN__ supaya
# kurung kurawal CSS tidak bentrok dengan interpolasi string Python.
_CSS_TEMPLATE = """
:root {
  --dk-ivory: __IVORY__; --dk-cream: __CREAM__; --dk-surface: __SURFACE__;
  --dk-ink: __INK__; --dk-ink-soft: __INK_SOFT__; --dk-muted: __MUTED__;
  --dk-line: __LINE__; --dk-forest: __FOREST_700__; --dk-forest-600: __FOREST_600__;
  --dk-gold: __GOLD_600__; --dk-rose: __ROSE_600__;
  --dk-display: Georgia, 'Cambria', 'Times New Roman', serif;
  --dk-sans: 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', sans-serif;
}

html, body, [class*="css"], .stMarkdown, button, input, textarea, select {
  font-family: var(--dk-sans);
}
.stApp {
  background-color: var(--dk-ivory);
  background-image:
    radial-gradient(1200px 500px at 100% -10%, rgba(207,160,85,.13), transparent 60%),
    radial-gradient(900px 420px at -10% 0%, rgba(42,114,97,.10), transparent 60%);
  color: var(--dk-ink);
}
.block-container { padding-bottom: 4rem; }

h1, h2, h3, h4, h5 { font-family: var(--dk-display); color: var(--dk-ink); }
h1 { font-weight: 700; letter-spacing: -.015em; }
h2 { font-weight: 700; letter-spacing: -.01em; }
p, li, td, th, label, .stMarkdown { color: var(--dk-ink-soft); }
a { color: var(--dk-forest); }
code { background: #F4EFE5 !important; color: #8A6A2B !important; border-radius: 6px; padding: 1px 6px; }

/* ── Sidebar ───────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: #FCFAF6;
  border-right: 1px solid var(--dk-line);
}
section[data-testid="stSidebar"] hr { border-color: var(--dk-line); }

/* ── Tombol ─────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button, .stLinkButton > a {
  border-radius: 11px;
  font-weight: 700;
  letter-spacing: .01em;
  border: 1px solid var(--dk-line);
  background: var(--dk-surface);
  color: var(--dk-ink);
  box-shadow: 0 1px 2px rgba(27,42,36,.05);
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: var(--dk-forest-600);
  color: var(--dk-forest);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px -8px rgba(27,42,36,.28);
}
.stButton > button[kind="primary"], .stLinkButton > a[kind="primary"] {
  background: var(--dk-forest); border-color: var(--dk-forest); color: #fff;
}
.stButton > button[kind="primary"]:hover, .stLinkButton > a[kind="primary"]:hover {
  background: var(--dk-forest-600); border-color: var(--dk-forest-600); color: #fff;
}
.stButton > button:disabled { opacity: .45; }

/* ── Tabs & expander ────────────────────────────────────────── */
button[data-baseweb="tab"] {
  font-family: var(--dk-sans);
  font-weight: 700;
  color: var(--dk-muted);
  padding: .55rem .1rem;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--dk-forest); }
button[data-baseweb="tab-highlight"], button[data-baseweb="tab-border"] { color: var(--dk-gold); }

[data-testid="stExpander"] {
  border: 1px solid var(--dk-line);
  border-radius: 14px;
  background: var(--dk-surface);
}

/* ── Input ──────────────────────────────────────────────────── */
[data-baseweb="select"] > div, .stTextInput input, .stTextArea textarea, .stNumberInput input {
  border-radius: 11px !important;
  border-color: var(--dk-line) !important;
  background: var(--dk-surface);
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--dk-forest-600) !important;
  box-shadow: 0 0 0 3px rgba(42,114,97,.13) !important;
}

/* ── Brand bar ──────────────────────────────────────────────── */
.dk-nav {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px 20px; margin-bottom: 22px;
  background: rgba(255,255,255,.86); backdrop-filter: blur(10px);
  border: 1px solid var(--dk-line); border-radius: 16px;
  box-shadow: 0 10px 30px -22px rgba(27,42,36,.5);
}
.dk-nav-links { display: flex; gap: 22px; flex-wrap: wrap; }
.dk-nav-links a { color: var(--dk-ink-soft); text-decoration: none; font-size: .9rem; font-weight: 600; }
.dk-nav-links a:hover { color: var(--dk-forest); }

.dk-brand { display: flex; align-items: center; gap: 12px; }
.dk-logo {
  width: 44px; height: 44px; border-radius: 13px; flex: none;
  background: linear-gradient(140deg, var(--dk-forest) 0%, var(--dk-forest-600) 60%, var(--dk-gold) 165%);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 1.3rem; box-shadow: 0 6px 14px -6px rgba(27,42,36,.55);
}
.dk-logo-sm {
  width: 34px; height: 34px; border-radius: 10px; flex: none;
  background: linear-gradient(140deg, var(--dk-forest), var(--dk-forest-600) 70%, var(--dk-gold) 175%);
  color: #fff; display: flex; align-items: center; justify-content: center; font-size: 1rem;
}
.dk-brand-name { font-family: var(--dk-display); font-size: 1.18rem; font-weight: 700; line-height: 1.1; color: var(--dk-ink); }
.dk-brand-sub { font-size: .72rem; letter-spacing: .16em; text-transform: uppercase; color: var(--dk-gold); font-weight: 800; }

/* ── Hero ───────────────────────────────────────────────────── */
.dk-hero {
  position: relative; overflow: hidden;
  border-radius: 26px; padding: 52px 48px;
  background:
    radial-gradient(760px 340px at 88% -20%, rgba(207,160,85,.40), transparent 62%),
    linear-gradient(125deg, __FOREST_900__ 0%, __FOREST_700__ 52%, #2C6F5C 100%);
  color: #fff; box-shadow: 0 30px 60px -34px rgba(18,50,42,.75);
}
.dk-hero::after {
  content: ""; position: absolute; inset: auto -70px -130px auto; width: 340px; height: 340px;
  border-radius: 50%; background: rgba(255,255,255,.07);
}
.dk-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28);
  color: #F6E7C6; font-size: .72rem; font-weight: 800;
  letter-spacing: .18em; text-transform: uppercase; padding: 6px 14px; border-radius: 999px;
}
.dk-hero h1 { color: #fff; font-size: 3rem; line-height: 1.08; font-weight: 700; margin: 20px 0 14px; max-width: 20ch; }
.dk-hero p.lede { color: rgba(255,255,255,.88); font-size: 1.06rem; max-width: 58ch; margin: 0; }
.dk-hero .trust { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 22px; }
.dk-hero .trust span {
  background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.24);
  color: #F1F6F3; border-radius: 999px; padding: 6px 13px; font-size: .78rem; font-weight: 600;
}

/* ── Section head ───────────────────────────────────────────── */
.dk-eyebrow-2 {
  font-size: .72rem; font-weight: 800; letter-spacing: .2em; text-transform: uppercase;
  color: var(--dk-forest-600); margin: 0 0 6px;
}
.dk-h2 { font-size: 2rem; line-height: 1.15; margin: 0 0 8px; }
.dk-lede { color: var(--dk-muted); font-size: 1rem; max-width: 70ch; margin: 0; }

/* ── Grid & kartu ───────────────────────────────────────────── */
.dk-grid { display: grid; gap: 18px; }
.dk-c2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.dk-c3 { grid-template-columns: repeat(auto-fit, minmax(238px, 1fr)); }
.dk-c4 { grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }

.dk-card {
  background: var(--dk-surface); border: 1px solid var(--dk-line);
  border-radius: 18px; padding: 22px 22px 20px;
  box-shadow: 0 1px 2px rgba(27,42,36,.04), 0 18px 34px -26px rgba(27,42,36,.35);
}
.dk-card h3 { font-size: 1.14rem; margin: 0 0 6px; }
.dk-card p { margin: 0; color: var(--dk-muted); font-size: .92rem; }
.dk-card-accent { border-top: 3px solid var(--dk-forest-600); }
.dk-card-gold { border-top: 3px solid var(--dk-gold); }

.dk-icon-badge {
  width: 42px; height: 42px; border-radius: 13px; display: flex; align-items: center;
  justify-content: center; font-size: 1.15rem; margin-bottom: 14px;
  background: var(--dk-forest-50); border: 1px solid var(--dk-forest-100); color: var(--dk-forest);
}
.dk-icon-gold { background: var(--dk-gold-50); border-color: #EEDFBE; color: #8A6A2B; }
.dk-icon-rose { background: var(--dk-rose-bg); border-color: #F2CBD3; color: var(--dk-rose); }

/* ── KPI tile ───────────────────────────────────────────────── */
.dk-kpi {
  position: relative; overflow: hidden;
  background: var(--dk-surface); border: 1px solid var(--dk-line);
  border-radius: 18px; padding: 18px 20px 18px 24px; height: 100%;
  box-shadow: 0 1px 2px rgba(27,42,36,.04), 0 14px 28px -24px rgba(27,42,36,.4);
}
.dk-kpi::before {
  content: ""; position: absolute; top: 0; bottom: 0; left: 0; width: 5px;
  background: var(--kpi-accent, var(--dk-forest-600));
}
.dk-kpi-label { font-size: .71rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--dk-muted); }
.dk-kpi-value { font-family: var(--dk-display); font-size: 2.05rem; font-weight: 700; line-height: 1.15; color: var(--dk-ink); }
.dk-kpi-note { font-size: .78rem; color: var(--dk-muted); }

/* ── Chip & pill ────────────────────────────────────────────── */
.dk-chip {
  display: inline-flex; align-items: center; gap: 5px;
  border-radius: 999px; padding: 3px 11px; font-size: .73rem; font-weight: 800;
  letter-spacing: .02em; white-space: nowrap;
}
.dk-pill {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--dk-cream); border: 1px solid var(--dk-line); color: var(--dk-ink-soft);
  border-radius: 999px; padding: 3px 11px; font-size: .75rem; font-weight: 700;
  margin: 0 6px 6px 0;
}
.dk-pill-forest { background: var(--dk-forest-50); border-color: var(--dk-forest-100); color: var(--dk-forest); }
.dk-pill-gold { background: var(--dk-gold-50); border-color: #EEDFBE; color: #8A6A2B; }
.dk-pill-rose { background: var(--dk-rose-bg); border-color: #F2CBD3; color: var(--dk-rose); }

/* ── Kartu pesanan ──────────────────────────────────────────── */
.dk-order {
  background: var(--dk-surface); border: 1px solid var(--dk-line);
  border-radius: 16px; padding: 16px 18px; margin-bottom: 12px;
  box-shadow: 0 1px 2px rgba(27,42,36,.05);
  border-left: 5px solid var(--order-accent, var(--dk-line));
}
.dk-order-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.dk-order-id { font-family: var(--dk-display); font-size: 1.06rem; font-weight: 700; color: var(--dk-ink); }
.dk-order-customer { font-weight: 700; color: var(--dk-ink); font-size: .96rem; margin-top: 6px; }
.dk-order-meta { font-size: .78rem; color: var(--dk-muted); }
.dk-order-menu { font-size: .92rem; color: var(--dk-ink-soft); margin: 8px 0 0; }
.dk-order-menu b { color: var(--dk-ink); }

.dk-alert {
  background: var(--dk-rose-bg); border: 1px solid #F2CBD3;
  border-left: 4px solid var(--dk-rose);
  border-radius: 12px; padding: 10px 14px; margin: 10px 0 0; font-size: .85rem; color: #7F1D2E;
}
.dk-alert b { color: var(--dk-rose); }
.dk-sop {
  background: var(--dk-gold-50); border: 1px solid #EEDFBE;
  border-left: 4px solid var(--dk-gold);
  border-radius: 12px; padding: 10px 14px; margin: 10px 0 0; font-size: .85rem; color: #6E5220;
}

/* ── Stepper alur ───────────────────────────────────────────── */
.dk-steps { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }
.dk-step { background: var(--dk-surface); border: 1px solid var(--dk-line); border-radius: 14px; padding: 14px 16px; }
.dk-step.on {
  border-color: var(--dk-forest-600); background: var(--dk-forest-50);
  box-shadow: 0 12px 24px -20px rgba(42,114,97,.85);
}
.dk-step-num {
  width: 26px; height: 26px; border-radius: 9px; display: inline-flex; align-items: center;
  justify-content: center; font-size: .8rem; font-weight: 800;
  background: var(--dk-cream); color: var(--dk-muted); margin-bottom: 8px;
}
.dk-step.on .dk-step-num { background: var(--dk-forest); color: #fff; }
.dk-step-title { font-weight: 800; font-size: .9rem; color: var(--dk-ink); }
.dk-step-desc { font-size: .78rem; color: var(--dk-muted); }

/* ── Kartu menu hari ────────────────────────────────────────── */
.dk-day {
  background: var(--dk-surface); border: 1px solid var(--dk-line); border-radius: 18px;
  overflow: hidden; box-shadow: 0 14px 30px -26px rgba(27,42,36,.45);
  display: flex; flex-direction: column;
}
.dk-day-head {
  padding: 14px 18px; color: #fff;
  background: linear-gradient(120deg, __FOREST_700__, __FOREST_600__ 70%, #2C6F5C);
  display: flex; align-items: baseline; justify-content: space-between; gap: 10px;
}
.dk-day-head.is-today {
  background: linear-gradient(120deg, __GOLD_600__, __GOLD_500__ 75%, #D8AE6A);
  color: #3B2A08;
}
.dk-day-name { font-family: var(--dk-display); font-size: 1.06rem; font-weight: 700; }
.dk-day-tag { font-size: .68rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; opacity: .85; }
.dk-day-body { padding: 16px 18px 18px; }
.dk-day-body h4 { font-size: .98rem; margin: 0 0 4px; }
.dk-day-desc { font-size: .82rem; color: var(--dk-muted); margin: 0 0 10px; }
.dk-list { margin: 8px 0 0; padding-left: 18px; font-size: .82rem; color: var(--dk-ink-soft); }
.dk-list li { margin-bottom: 3px; }

/* ── Harga ──────────────────────────────────────────────────── */
.dk-price { font-family: var(--dk-display); font-size: 1.7rem; font-weight: 700; color: var(--dk-forest); }
.dk-price small { font-size: .8rem; color: var(--dk-muted); font-family: var(--dk-sans); font-weight: 600; }

/* ── Catatan ────────────────────────────────────────────────── */
.dk-note {
  display: flex; gap: 12px; align-items: flex-start;
  background: var(--dk-forest-50); border: 1px solid var(--dk-forest-100);
  border-radius: 16px; padding: 14px 18px; font-size: .92rem;
}
.dk-note.warn { background: #FDF4E3; border-color: #EFDCB6; }
.dk-note b { color: var(--dk-forest); }
.dk-note.warn b { color: #8A6A2B; }

/* ── Empty state ────────────────────────────────────────────── */
.dk-empty {
  text-align: center; padding: 30px 22px; color: var(--dk-muted);
  border: 1px dashed #DCD2BF; border-radius: 18px; background: #FFFDF9; font-size: .9rem;
}
.dk-empty .big { font-size: 1.9rem; display: block; margin-bottom: 8px; }

/* ── Tabel info ─────────────────────────────────────────────── */
.dk-table { width: 100%; border-collapse: collapse; font-size: .88rem; }
.dk-table th {
  text-align: left; font-size: .71rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--dk-muted); padding: 10px 14px; border-bottom: 1px solid var(--dk-line);
  background: var(--dk-cream);
}
.dk-table td { padding: 11px 14px; border-bottom: 1px solid var(--dk-line); vertical-align: top; }
.dk-table tr:last-child td { border-bottom: 0; }
.dk-table b { color: var(--dk-ink); }

/* ── Footer ─────────────────────────────────────────────────── */
.dk-footer {
  margin-top: 60px; padding: 28px 26px; border-radius: 20px;
  background: var(--dk-surface); border: 1px solid var(--dk-line);
  display: flex; justify-content: space-between; gap: 22px; flex-wrap: wrap; align-items: center;
}
.dk-footer .links { display: flex; gap: 20px; flex-wrap: wrap; font-size: .87rem; }

.dk-trust { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }

/* ── Utilitas ───────────────────────────────────────────────── */
.dk-muted { color: var(--dk-muted); }
.dk-small { font-size: .82rem; }
.dk-mono { font-family: ui-monospace, 'Cascadia Code', Consolas, monospace; }
"""

_HIDE_CHROME_CSS = """
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
[data-testid="stToolbar"] { display: none; }
.block-container { padding-top: 1.2rem; }
"""

_TOKENS = {
    "__IVORY__": IVORY, "__CREAM__": CREAM, "__SURFACE__": SURFACE,
    "__INK__": INK, "__INK_SOFT__": INK_SOFT, "__MUTED__": MUTED, "__LINE__": LINE,
    "__FOREST_900__": FOREST_900, "__FOREST_700__": FOREST_700,
    "__FOREST_600__": FOREST_600, "__FOREST_100__": FOREST_100,
    "__FOREST_50__": FOREST_50,
    "__GOLD_600__": GOLD_600, "__GOLD_500__": GOLD_500, "__GOLD_50__": GOLD_50,
    "__ROSE_600__": ROSE_600, "__ROSE_50__": ROSE_50,
}


def _render_css() -> str:
    css = _CSS_TEMPLATE
    for token, value in _TOKENS.items():
        css = css.replace(token, value)
    return css


def page_config(
    title: str,
    icon: str = "🍽️",
    layout: str = "wide",
    initial_sidebar: str = "expanded",
) -> None:
    """Harus dipanggil sebagai baris pertama pada tiap script Streamlit."""
    st.set_page_config(
        page_title=f"{BRAND_NAME} — {title}",
        page_icon=icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar,
    )


def inject_css(*, base: bool = True, chrome: bool = False) -> None:
    """
    Suntikkan stylesheet DovaGenome.

    Harus dipanggil pada setiap eksekusi script (Streamlit menjalankan ulang
    script pada setiap interaksi), karena elemen-elemen HTML ikut dibangun ulang.

    base=True  → stylesheet utama (warna, tipografi, komponen).
    chrome=True → sembunyikan header/menu Streamlit untuk tampilan situs publik.
    """
    parts: list[str] = []
    if base:
        parts.append(_render_css())
    if chrome:
        parts.append(_HIDE_CHROME_CSS)
    st.markdown(f"<style>{''.join(parts)}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Komponen HTML
# ---------------------------------------------------------------------------

def brand_bar(subtitle: str = BRAND_SUB,
              links: Iterable[tuple[str, str]] = (),
              right_html: str = "") -> str:
    nav = "".join(f'<a href="{esc(href)}">{esc(label)}</a>' for label, href in links)
    sub = f'<div class="dk-brand-sub">{esc(subtitle)}</div>' if subtitle else ""
    right = f'<div class="dk-small">{right_html}</div>' if right_html else ""
    return f"""
<div class="dk-nav">
  <div class="dk-brand">
    <div class="dk-logo">🍽️</div>
    <div><div class="dk-brand-name">{esc(BRAND_NAME)}</div>{sub}</div>
  </div>
  <div class="dk-nav-links">{nav}</div>
  {right}
</div>"""


def sidebar_brand(subtitle: str = BRAND_SUB) -> None:
    st.sidebar.markdown(
        f"""<div class="dk-brand" style="margin-bottom:2px">
  <div class="dk-logo-sm">🍽️</div>
  <div>
    <div class="dk-brand-name" style="font-size:1.05rem">{esc(BRAND_NAME)}</div>
    <div class="dk-brand-sub">{esc(subtitle)}</div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def hero(eyebrow: str, title: str, lede: str, trust: Iterable[str] = ()) -> str:
    chips = "".join(f"<span>{esc(t)}</span>" for t in trust)
    return f"""
<section class="dk-hero">
  <span class="dk-eyebrow">{esc(eyebrow)}</span>
  <h1>{esc(title)}</h1>
  <p class="lede">{esc(lede)}</p>
  <div class="trust">{chips}</div>
</section>"""


def section_head(eyebrow: str, title: str, lede: str = "") -> str:
    sub = f'<p class="dk-lede">{esc(lede)}</p>' if lede else ""
    return f"""
<div style="margin-bottom:22px">
  <p class="dk-eyebrow-2">{esc(eyebrow)}</p>
  <h2 class="dk-h2">{esc(title)}</h2>
  {sub}
</div>"""


def kpi(label: str, value: str, note: str = "", accent: str = FOREST_600) -> str:
    note_html = f'<div class="dk-kpi-note">{esc(note)}</div>' if note else ""
    return f"""
<div class="dk-kpi" style="--kpi-accent:{accent}">
  <div class="dk-kpi-label">{esc(label)}</div>
  <div class="dk-kpi-value">{esc(value)}</div>
  {note_html}
</div>"""


def kpi_row(items: list[tuple[str, str, str, str]]) -> str:
    """items = [(label, value, note, accent), ...] → satu blok HTML."""
    return '<div class="dk-grid dk-c4">' + "".join(kpi(*it) for it in items) + "</div>"


def status_chip(status: str) -> str:
    meta = D.STATUS_META.get(str(status), D.STATUS_META["PENDING"])
    return (
        f"<span class='dk-chip' style='background:{meta['bg']};color:{meta['color']};"
        f"border:1px solid {meta['border']}'>{meta['emoji']} {esc(meta['short'])}</span>"
    )


def allergen_pills(items: Iterable[str], style: str = "rose") -> str:
    vals = [str(i) for i in items if str(i).strip()]
    if not vals:
        return "<span class='dk-pill dk-pill-forest'>✓ Tidak ada pantangan</span>"
    return "".join(f"<span class='dk-pill dk-pill-{style}'>{esc(i)}</span>" for i in vals)


def day_pills(days: Iterable[str]) -> str:
    return "".join(f"<span class='dk-pill'>{esc(str(d)[:3])}</span>" for d in days)


def stepper(current: int) -> str:
    """Stepper 4 tahap fulfilment; current = tahap aktif (0 = belum mulai)."""
    steps = [
        (1, "Pesanan masuk", "Tiket dari bot Telegram"),
        (2, "Dimasak", "Dapur menerapkan protokol steril"),
        (3, "Dikemas", "Segel anti-kontaminasi"),
        (4, "Diantar", "Selesai & billed"),
    ]
    out = []
    for num, title, desc in steps:
        cls = "dk-step on" if num == current else "dk-step"
        mark = "✓" if current > num else str(num)
        out.append(
            f"<div class='{cls}'><div class='dk-step-num'>{mark}</div>"
            f"<div class='dk-step-title'>{esc(title)}</div>"
            f"<div class='dk-step-desc'>{esc(desc)}</div></div>"
        )
    return "<div class='dk-steps'>" + "".join(out) + "</div>"


def order_card(order: dict, menus: dict[str, dict], show_sop: bool = True) -> str:
    """Kartu pesanan siap pakai untuk kedua dashboard."""
    status    = str(order.get("status") or "PENDING")
    meta      = D.STATUS_META.get(status, D.STATUS_META["PENDING"])
    minutes   = D.elapsed_minutes(order.get("created_at"))
    level     = D.sla_level(minutes)
    allergens = D.order_allergens(order)
    day, menu = D.current_menu(order, menus)
    notes     = D.order_notes(order)
    is_today  = bool(day) and day == D.today_name()

    timer_color = {"fresh": MUTED, "soon": GOLD_600, "late": ROSE_600}[level]

    chips = (
        f"<span class='dk-chip' style='background:{meta['bg']};color:{meta['color']};"
        f"border:1px solid {meta['border']}'>{meta['emoji']} {esc(meta['short'])}</span>"
        f"<span class='dk-chip' style='background:#FFF;border:1px solid {LINE};"
        f"color:{timer_color}'>⏱ {minutes} mnt</span>"
    )

    today_badge = (
        f"<span style='color:{FOREST_600};font-weight:700'> · hari ini</span>"
        if is_today else ""
    )
    day_suffix = f" <span class='dk-muted'>({esc(day)})</span>" if day else ""

    alert = ""
    if allergens:
        asap = " — asap" if level == "late" else ""
        alert = (
            f"<div class='dk-alert'><b>🚨 Pantangan{esc(asap)}:</b><br>"
            + allergen_pills(allergens)
            + "<div style='margin-top:6px'>Peralatan, talenan, dan area masak wajib terpisah.</div></div>"
        )

    sop = f"<div class='dk-sop'><b>🔪 Protokol dapur:</b> {esc(notes)}</div>" if (show_sop and notes) else ""

    return f"""
<div class='dk-order' style='--order-accent:{meta['color']}'>
  <div class='dk-order-head'>
    <span class='dk-order-id'>{esc(D.order_id(order))}</span>
    <span style='display:flex;gap:6px;flex-wrap:wrap'>{chips}</span>
  </div>
  <div class='dk-order-customer'>👤 {esc(D.order_customer(order))}</div>
  <div class='dk-order-meta'>
    📦 {esc(D.order_package(order))} · ⏰ {esc(D.fmt_wib(order.get('created_at')))}{today_badge}
  </div>
  <div class='dk-order-menu'>🍽️ <b>{esc(menu)}</b>{day_suffix}</div>
  {alert}
  {sop}
</div>"""


def empty_state(message: str, glyph: str = "🍽️") -> str:
    return f'<div class="dk-empty"><span class="big">{esc(glyph)}</span>{esc(message)}</div>'


def note(html_body: str, kind: str = "", glyph: str = "💡") -> str:
    """kind: '' | 'warn' | 'rose'. html_body harus HTML yang sudah di-escape."""
    cls = f"dk-note {kind}".strip()
    return f'<div class="{cls}"><div style="flex:none">{esc(glyph)}</div><div>{html_body}</div></div>'


def footer(extra_links: Iterable[tuple[str, str]] = ()) -> str:
    links = "".join(f'<a href="{esc(h)}">{esc(l)}</a>' for l, h in extra_links)
    body = links or '<span class="dk-muted">Dapur presisi · Traceable · Allergen-safe</span>'
    year = datetime.datetime.now().year
    return f"""
<div class="dk-footer">
  <div style="max-width:46ch">
    <div class="dk-brand-name">{esc(BRAND_NAME)}</div>
    <p class="dk-small dk-muted" style="margin:4px 0 0">{esc(BRAND_TAGLINE)}</p>
  </div>
  <div class="links">{body}</div>
  <div class="dk-small dk-muted">© {year} {esc(BRAND_NAME)}</div>
</div>"""


def st_markdown(html_text: str) -> None:
    st.markdown(html_text, unsafe_allow_html=True)


def telegram_cta(label: str, payload: str | None = None, **kwargs) -> None:
    """Tombol tautan ke bot Telegram; nonaktif bila bot belum dikonfigurasi."""
    url = D.telegram_link(payload)
    if url:
        st.link_button(label, url, **kwargs)
    else:
        st.button(label, disabled=True, **kwargs)
        st.caption("Isi `TELEGRAM_BOT_USERNAME` di file `.env` untuk mengaktifkan tautan.")