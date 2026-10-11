"""
DovaGenome — Landing Page Tamu (Public)
========================================
Situs marketing minimalis dan modern untuk calon pelanggan.
Tampilan dirancang bersih, seimbang, dan proporsional dengan fokus pada:
  • Hero & CTA yang terpadu tanpa tumpang tindih
  • Grid menu mingguan 3x2 yang simetris (Senin - Sabtu)
  • Kartu fitur & paket dengan hirarki visual yang lapang
  • Navigasi dan footer yang rapi dan elegan

Cara menjalankan:
    streamlit run landing_page.py --server.port 8501

Pratinjau di dalam admin dashboard:
    from landing_page import render_landing
    render_landing(preview=True)
"""

from __future__ import annotations

import streamlit as st

import data as D
import theme as T


# ---------------------------------------------------------------------------
# Sumber data
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _db():
    return D.connect_db()


@st.cache_data(ttl=300, show_spinner=False)
def catalog() -> dict:
    return D.load_catalog(_db())


def _rupiah(value) -> str:
    try:
        return f"Rp {int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _cta_url(payload: str | None = None) -> tuple[str, bool]:
    """Kembalikan (url, is_active). Jika bot belum diset, beri fallback internal."""
    url = D.telegram_link(payload)
    if url:
        return url, True
    return "#cara", False


# ---------------------------------------------------------------------------
# Stylesheet Khusus Landing Page Minimalis
# ---------------------------------------------------------------------------

_LANDING_CSS = """
<style>
/* ── Batasi lebar kontainer agar rapi di layar lebar ── */
.block-container {
  max-width: 1060px !important;
  margin-left: auto !important;
  margin-right: auto !important;
  padding-top: 1.6rem !important;
  padding-bottom: 4.5rem !important;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
}

/* ── Typography & Global Reset ── */
h1, h2, h3, h4 {
  letter-spacing: -0.02em !important;
}

/* ── Navigasi Header ── */
.lp-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 22px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--dk-line);
  border-radius: 16px;
  box-shadow: 0 4px 18px -6px rgba(27, 42, 36, 0.06);
  margin-bottom: 2rem;
}
.lp-nav-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  color: inherit;
}
.lp-nav-logo {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(135deg, var(--dk-forest), var(--dk-forest-600));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  color: #fff;
  box-shadow: 0 4px 10px -3px rgba(27, 42, 36, 0.25);
}
.lp-nav-name {
  font-family: var(--dk-display);
  font-weight: 700;
  font-size: 1.15rem;
  color: var(--dk-ink);
  line-height: 1.1;
}
.lp-nav-sub {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--dk-gold);
  font-weight: 800;
}
.lp-nav-links {
  display: flex;
  align-items: center;
  gap: 22px;
  flex-wrap: wrap;
}
.lp-nav-links a {
  color: var(--dk-ink-soft);
  text-decoration: none;
  font-size: 0.88rem;
  font-weight: 600;
  transition: color 0.15s ease;
}
.lp-nav-links a:hover {
  color: var(--dk-forest);
}

/* ── Hero Section ── */
.lp-hero {
  background: linear-gradient(145deg, #12322A 0%, #1C483C 60%, #163B30 100%);
  border-radius: 24px;
  padding: 3.6rem 2.8rem 3rem;
  color: #FFFFFF;
  text-align: center;
  position: relative;
  overflow: hidden;
  box-shadow: 0 20px 40px -20px rgba(18, 50, 42, 0.45);
  margin-bottom: 2rem;
}
.lp-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.22);
  color: #F6E7C6;
  margin-bottom: 1.25rem;
}
.lp-hero h1 {
  color: #FFFFFF !important;
  font-size: 2.35rem !important;
  font-weight: 700 !important;
  line-height: 1.22 !important;
  margin: 0 auto 1.1rem !important;
  max-width: 720px;
}
.lp-hero p.lede {
  color: rgba(255, 255, 255, 0.85);
  font-size: 1.02rem;
  line-height: 1.6;
  max-width: 620px;
  margin: 0 auto 2.2rem;
}
.lp-hero-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 1.4rem;
}
.lp-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 22px;
  border-radius: 12px;
  font-size: 0.92rem;
  font-weight: 700;
  text-decoration: none !important;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
  cursor: pointer;
}
.lp-btn-primary {
  background: #E5B25D;
  color: #12322A !important;
  box-shadow: 0 4px 14px rgba(229, 178, 93, 0.35);
}
.lp-btn-primary:hover {
  background: #F0C477;
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(229, 178, 93, 0.45);
}
.lp-btn-secondary {
  background: rgba(255, 255, 255, 0.12);
  color: #FFFFFF !important;
  border: 1px solid rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(4px);
}
.lp-btn-secondary:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
  transform: translateY(-1px);
}
.lp-btn-outline {
  background: transparent;
  color: rgba(255, 255, 255, 0.85) !important;
  border: 1px solid rgba(255, 255, 255, 0.18);
}
.lp-btn-outline:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #FFFFFF !important;
}
.lp-hero-notice {
  font-size: 0.8rem;
  color: #F6E7C6;
  opacity: 0.9;
  margin-top: 0.5rem;
}
.lp-hero-trust {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 1.8rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}
.lp-hero-trust span {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.82);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* ── Section Headings & Spacing ── */
.lp-section {
  margin-top: 3.8rem;
  margin-bottom: 1.5rem;
}
.lp-section-head {
  text-align: center;
  margin-bottom: 2rem;
}
.lp-section-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--dk-forest);
  background: var(--dk-forest-50);
  border: 1px solid var(--dk-forest-100);
  margin-bottom: 0.65rem;
}
.lp-section-title {
  font-size: 1.85rem;
  font-weight: 700;
  color: var(--dk-ink);
  margin: 0 0 0.5rem 0;
  line-height: 1.25;
}
.lp-section-sub {
  color: var(--dk-muted);
  font-size: 0.96rem;
  max-width: 580px;
  margin: 0 auto;
  line-height: 1.5;
}

/* ── Stats Bar ── */
.lp-stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  background: var(--dk-surface);
  border: 1px solid var(--dk-line);
  border-radius: 16px;
  padding: 1.3rem 0.5rem;
  box-shadow: 0 2px 10px -4px rgba(27, 42, 36, 0.05);
  margin-bottom: 3.5rem;
}
.lp-stat-item {
  text-align: center;
  padding: 0 1rem;
  border-right: 1px solid var(--dk-line);
}
.lp-stat-item:last-child {
  border-right: none;
}
.lp-stat-num {
  font-family: var(--dk-display);
  font-size: 1.85rem;
  font-weight: 700;
  line-height: 1.1;
  color: var(--dk-forest);
  margin-bottom: 0.2rem;
}
.lp-stat-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--dk-ink-soft);
  margin-bottom: 0.15rem;
}
.lp-stat-desc {
  font-size: 0.78rem;
  color: var(--dk-muted);
}

/* ── Fitur Kenapa DovaGenome ── */
.lp-features-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.lp-feature-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-line);
  border-radius: 16px;
  padding: 1.5rem 1.6rem;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.lp-feature-card:hover {
  border-color: var(--dk-forest-100);
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -12px rgba(27, 42, 36, 0.08);
}
.lp-feature-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--dk-forest-50);
  border: 1px solid var(--dk-forest-100);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
}
.lp-feature-content h3 {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0 0 0.35rem 0;
  color: var(--dk-ink);
}
.lp-feature-content p {
  font-size: 0.88rem;
  line-height: 1.5;
  color: var(--dk-muted);
  margin: 0;
}

/* ── Alur Pemesanan ── */
.lp-steps-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.lp-step-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-line);
  border-radius: 16px;
  padding: 1.6rem 1.4rem;
  text-align: center;
  transition: transform 0.15s ease;
}
.lp-step-card:hover {
  transform: translateY(-2px);
}
.lp-step-num {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--dk-forest);
  color: #FFFFFF;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.92rem;
  font-weight: 700;
  margin-bottom: 0.85rem;
}
.lp-step-title {
  font-size: 1.02rem;
  font-weight: 700;
  color: var(--dk-ink);
  margin-bottom: 0.4rem;
}
.lp-step-desc {
  font-size: 0.84rem;
  color: var(--dk-muted);
  line-height: 1.45;
  margin: 0;
}

/* ── Menu Minggu Ini: 3 Kolom x 2 Baris Simetris ── */
.lp-menu-grid {
  display: grid !important;
  grid-template-columns: repeat(3, 1fr) !important;
  gap: 18px !important;
}
.lp-menu-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-line);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 2px 8px -2px rgba(27, 42, 36, 0.04);
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.lp-menu-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -10px rgba(27, 42, 36, 0.1);
}
.lp-menu-card.is-today {
  border-color: var(--dk-gold);
  box-shadow: 0 6px 18px -4px rgba(184, 137, 59, 0.18);
}
.lp-menu-head {
  padding: 10px 16px;
  background: var(--dk-cream);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--dk-line);
}
.lp-menu-card.is-today .lp-menu-head {
  background: #FBF3E3;
}
.lp-menu-day {
  font-weight: 700;
  font-size: 0.9rem;
  color: var(--dk-ink);
}
.lp-menu-badge {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(27, 42, 36, 0.06);
  color: var(--dk-ink-soft);
}
.lp-menu-card.is-today .lp-menu-badge {
  background: #EEDFBE;
  color: #8A6A2B;
}
.lp-menu-body {
  padding: 16px;
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}
.lp-menu-title {
  font-family: var(--dk-display);
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--dk-ink);
  margin: 0 0 0.35rem 0;
  line-height: 1.25;
}
.lp-menu-desc {
  font-size: 0.82rem;
  color: var(--dk-muted);
  line-height: 1.45;
  margin: 0 0 0.75rem 0;
}
.lp-menu-ingredients {
  font-size: 0.8rem;
  color: var(--dk-ink-soft);
  margin: 0 0 0.75rem 0;
  padding-left: 16px;
  line-height: 1.5;
}
.lp-menu-footer {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--dk-line);
}
.lp-menu-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
}
.lp-tag-safe {
  background: var(--dk-forest-50);
  color: var(--dk-forest);
  border: 1px solid var(--dk-forest-100);
}
.lp-tag-alert {
  background: #FDF1F3;
  color: var(--dk-rose);
  border: 1px solid #F2CBD3;
}
.lp-tag-sop {
  background: #FBF8F3;
  color: var(--dk-ink-soft);
  border: 1px solid var(--dk-line);
  font-size: 0.7rem;
  margin-top: 6px;
  display: block;
  border-radius: 6px;
  padding: 3px 6px;
}

/* ── Paket Katering ── */
.lp-pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}
.lp-pricing-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-line);
  border-radius: 16px;
  padding: 1.6rem 1.4rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.lp-pricing-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -10px rgba(27, 42, 36, 0.08);
}
.lp-pricing-card.featured {
  border: 2px solid var(--dk-gold);
  box-shadow: 0 8px 24px -10px rgba(184, 137, 59, 0.2);
}
.lp-popular-badge {
  position: absolute;
  top: -11px;
  right: 18px;
  background: #FBF3E3;
  color: #8A6A2B;
  border: 1px solid #EEDFBE;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 2px 10px;
  border-radius: 999px;
}
.lp-price-val {
  font-family: var(--dk-display);
  font-size: 1.7rem;
  font-weight: 700;
  color: var(--dk-forest);
  margin: 1rem 0 0.4rem;
}
.lp-price-val small {
  font-family: var(--dk-sans);
  font-size: 0.8rem;
  color: var(--dk-muted);
  font-weight: 500;
}
.lp-pricing-btn {
  display: block;
  text-align: center;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 0.88rem;
  font-weight: 700;
  text-decoration: none !important;
  margin-top: 1.25rem;
  transition: all 0.15s ease;
}
.lp-pricing-btn.primary {
  background: var(--dk-forest);
  color: #FFFFFF !important;
}
.lp-pricing-btn.primary:hover {
  background: var(--dk-forest-600);
}
.lp-pricing-btn.secondary {
  background: var(--dk-cream);
  color: var(--dk-ink) !important;
  border: 1px solid var(--dk-line);
}
.lp-pricing-btn.secondary:hover {
  background: var(--dk-surface);
  border-color: var(--dk-forest-600);
  color: var(--dk-forest) !important;
}

/* ── Keamanan Pangan: Grid Profil Alergen ── */
.lp-allergen-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.lp-allergen-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-line);
  border-radius: 14px;
  padding: 14px 16px;
  transition: transform 0.15s ease;
}
.lp-allergen-card:hover {
  transform: translateY(-2px);
}
.lp-allergen-name {
  font-weight: 700;
  font-size: 0.92rem;
  color: var(--dk-ink);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.lp-allergen-desc {
  font-size: 0.8rem;
  color: var(--dk-muted);
  line-height: 1.4;
  margin: 0;
}

/* ── FAQ Minimalis ── */
[data-testid="stExpander"] {
  background: var(--dk-surface) !important;
  border: 1px solid var(--dk-line) !important;
  border-radius: 12px !important;
  margin-bottom: 10px !important;
  box-shadow: 0 1px 3px rgba(27, 42, 36, 0.03) !important;
}
[data-testid="stExpander"] summary {
  font-weight: 600 !important;
  font-size: 0.94rem !important;
  color: var(--dk-ink) !important;
  padding: 12px 16px !important;
}

/* ── CTA Penutup ── */
.lp-cta-card {
  background: linear-gradient(145deg, #12322A 0%, #1C483C 60%, #163B30 100%);
  border-radius: 22px;
  padding: 3rem 2.2rem;
  color: #FFFFFF;
  text-align: center;
  box-shadow: 0 16px 36px -18px rgba(18, 50, 42, 0.35);
  margin-top: 3.5rem;
  margin-bottom: 2.5rem;
}
.lp-cta-card h2 {
  color: #FFFFFF !important;
  font-size: 2rem !important;
  font-weight: 700 !important;
  margin: 0 auto 0.75rem !important;
}
.lp-cta-card p {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.98rem;
  line-height: 1.5;
  max-width: 540px;
  margin: 0 auto 1.6rem;
}

/* ── Footer ── */
.lp-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2rem 0 1rem;
  border-top: 1px solid var(--dk-line);
  margin-top: 2rem;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 0.85rem;
  color: var(--dk-muted);
}
.lp-footer-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: var(--dk-ink);
}
.lp-footer-links {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}
.lp-footer-links a {
  color: var(--dk-ink-soft);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s ease;
}
.lp-footer-links a:hover {
  color: var(--dk-forest);
}

/* ── Responsif Mobile / Layar Kecil ── */
@media (max-width: 820px) {
  .lp-stats-bar { grid-template-columns: repeat(2, 1fr); gap: 14px; }
  .lp-stat-item:nth-child(2) { border-right: none; }
  .lp-features-grid { grid-template-columns: 1fr; }
  .lp-steps-grid { grid-template-columns: 1fr; }
  .lp-menu-grid { grid-template-columns: 1fr !important; }
  .lp-pricing-grid { grid-template-columns: 1fr; }
  .lp-allergen-grid { grid-template-columns: 1fr; }
  .lp-hero { padding: 2.5rem 1.5rem; }
  .lp-hero h1 { font-size: 1.85rem !important; }
}
</style>
"""


# ---------------------------------------------------------------------------
# Komponen Halaman
# ---------------------------------------------------------------------------

def _nav() -> None:
    bot_link, _ = _cta_url()
    html = f"""<header class="lp-nav">
<a href="#" class="lp-nav-brand">
<div class="lp-nav-logo">🍽️</div>
<div>
<div class="lp-nav-name">{T.esc(T.BRAND_NAME)}</div>
<div class="lp-nav-sub">{T.esc(T.BRAND_SUB)}</div>
</div>
</a>
<nav class="lp-nav-links">
<a href="#menu">Menu Minggu Ini</a>
<a href="#paket">Paket</a>
<a href="#keamanan">Keamanan</a>
<a href="#cara">Cara Pesan</a>
<a href="#faq">FAQ</a>
<a href="#cta" style="color:var(--dk-forest);font-weight:700">Mulai Pesan →</a>
</nav>
</header>"""
    st.markdown(html, unsafe_allow_html=True)


def _hero() -> None:
    order_url, has_bot = _cta_url("order")
    ai_url, _ = _cta_url("ai")
    
    notice_html = ""
    if not has_bot:
        notice_html = (
            "<div class='lp-hero-notice'>"
            "💡 <i>Tip: Masukkan <code>TELEGRAM_BOT_USERNAME</code> di file <code>.env</code> "
            "untuk menghubungkan tombol langsung ke bot Anda.</i></div>"
        )

    target_attr = "target='_blank' rel='noopener'" if has_bot else ""

    html = f"""<section class="lp-hero">
<div class="lp-hero-badge">🧬 Precision Catering · Jakarta</div>
<h1>Makan siang mingguan yang benar-benar aman untuk tubuh Anda.</h1>
<p class="lede">
Setiap pesanan membawa profil pantangan sendiri. Dapur kami memisahkan peralatan,
talenan, dan zona masak untuk tiap profil — lalu mengirim tiket yang bisa Anda pantau
statusnya dari masuk hingga diantar.
</p>
<div class="lp-hero-actions">
<a href="{order_url}" {target_attr} class="lp-btn lp-btn-primary">⚡ Pesan Sekarang di Telegram</a>
<a href="{ai_url}" {target_attr} class="lp-btn lp-btn-secondary">🤖 Tanya AI Soal Alergi</a>
<a href="#menu" class="lp-btn lp-btn-outline">📋 Lihat Menu Minggu Ini</a>
</div>
{notice_html}
<div class="lp-hero-trust">
<span>✅ 6 Hari Layanan</span>
<span>🧬 Filter Pantangan Presisi</span>
<span>🔪 Protokol Steril per Pesanan</span>
<span>🧾 Tiket Transparan</span>
</div>
</section>"""
    st.markdown(html, unsafe_allow_html=True)


def _stats() -> None:
    cat = catalog()
    num_menus = len(cat.get("menus", {}))
    num_pkgs = len(cat.get("packages", []))
    num_allergens = len(cat.get("allergens", []))

    html = f"""<div class="lp-stats-bar">
<div class="lp-stat-item">
<div class="lp-stat-num">{num_menus}</div>
<div class="lp-stat-label">Hari Layanan</div>
<div class="lp-stat-desc">Senin sampai Sabtu</div>
</div>
<div class="lp-stat-item">
<div class="lp-stat-num">{num_pkgs}</div>
<div class="lp-stat-label">Paket Fleksibel</div>
<div class="lp-stat-desc">Sesuai ritme kantor</div>
</div>
<div class="lp-stat-item">
<div class="lp-stat-num">{num_allergens}</div>
<div class="lp-stat-label">Profil Pantangan</div>
<div class="lp-stat-desc">Difilter otomatis</div>
</div>
<div class="lp-stat-item">
<div class="lp-stat-num">100%</div>
<div class="lp-stat-label">Keterlacakan</div>
<div class="lp-stat-desc">Pantau status tiket</div>
</div>
</div>"""
    st.markdown(html, unsafe_allow_html=True)


def _fitur() -> None:
    cards = [
        ("🧬", "Filter Pantangan Presisi",
         "Pilih sekali profil pantangan Anda. Semua menu mingguan otomatis disaring, "
         "dan tiap bahan diperiksa satu per satu — bukan sekadar klaim."),
        ("🔪", "Protokol Steril per Pesanan",
         "Setiap tiket membawa catatan peralatan khusus: talenan, wajan, dan minyak "
         "yang steril dari kontak silang bahan profil lain."),
        ("🧾", "Tiket Terlacak Real-Time",
         "Status pesanan terbuka: antrean masuk, sedang dimasak, dikemas, sampai diantar. "
         "Transparan tanpa perlu bertanya-tanya."),
        ("🤖", "Konsultasi AI Setiap Saat",
         "Tanyakan keamanan bahan apa pun via bot. AI kami membaca profil pantangan Anda "
         "sebelum menjawab, bukan sekadar menebak."),
    ]

    cards_html = "".join(f"""<div class="lp-feature-card">
<div class="lp-feature-icon">{glyph}</div>
<div class="lp-feature-content">
<h3>{T.esc(title)}</h3>
<p>{T.esc(desc)}</p>
</div>
</div>""" for glyph, title, desc in cards)

    html = f"""<section id="kenapa" class="lp-section">
<div class="lp-section-head">
<div class="lp-section-badge">Keunggulan</div>
<h2 class="lp-section-title">Kenapa Memilih DovaGenome?</h2>
<p class="lp-section-sub">Empat fondasi yang membedakan kami dari katering kantor konvensional.</p>
</div>
<div class="lp-features-grid">
{cards_html}
</div>
</section>"""
    st.markdown(html, unsafe_allow_html=True)


def _cara_pesan() -> None:
    steps = [
        ("1", "Pilih Paket", "Tentukan ritme layanan: 6 hari penuh, hari kerja kantor, atau 3 hari pilihan."),
        ("2", "Tandai Pantangan", "Pilih profil alergen Anda (gluten, seafood, kacang, susu, telur, kedelai)."),
        ("3", "Konfirmasi ke Dapur", "Periksa pratinjau menu, lalu tiket langsung dikirim ke sistem operasional dapur."),
    ]

    steps_html = "".join(f"""<div class="lp-step-card">
<div class="lp-step-num">{num}</div>
<div class="lp-step-title">{T.esc(title)}</div>
<p class="lp-step-desc">{T.esc(desc)}</p>
</div>""" for num, title, desc in steps)

    html = f"""<section id="cara" class="lp-section">
<div class="lp-section-head">
<div class="lp-section-badge">Alur Pemesanan</div>
<h2 class="lp-section-title">Mudah dalam 3 Langkah</h2>
<p class="lp-section-sub">Tanpa formulir panjang atau registrasi akun. Cukup satu chat via Telegram.</p>
</div>
<div class="lp-steps-grid">
{steps_html}
</div>
</section>"""
    st.markdown(html, unsafe_allow_html=True)


def _menu_mingguan() -> None:
    cat = catalog()
    today = D.today_name()

    cards = []
    for day in D.DAYS:
        doc = cat.get("menus", {}).get(day, {})
        name = doc.get("nama_menu", "—")
        desc = doc.get("deskripsi", "")
        bahan = [b for b in doc.get("bahan_detail", []) if isinstance(b, dict)]
        alat = [a for a in doc.get("alat_dapur_steril", []) if a]
        is_today = (day == today)

        bahan_html = "".join(f"<li>{T.esc(b.get('nama', ''))}</li>" for b in bahan[:3])
        if not bahan_html:
            bahan_html = "<li>Rincian bahan harian diperbarui oleh dapur</li>"

        mengandung = [
            str(b.get("nama", "")) for b in bahan if "⚠" in str(b.get("potensi_alergen", ""))
        ]

        if mengandung:
            alert_html = f"<span class='lp-menu-tag lp-tag-alert'>⚠️ Alergen: {T.esc(', '.join(mengandung))}</span>"
        else:
            alert_html = "<span class='lp-menu-tag lp-tag-safe'>✓ Aman Alergi</span>"

        sop_html = ""
        if alat:
            sop_html = f"<div class='lp-tag-sop'>🔪 <b>Steril:</b> {T.esc(alat[0])}</div>"

        card_cls = "lp-menu-card is-today" if is_today else "lp-menu-card"
        badge_text = "Hari Ini" if is_today else "Menu"

        cards.append(f"""<div class="{card_cls}">
<div class="lp-menu-head">
<span class="lp-menu-day">{T.esc(day)}</span>
<span class="lp-menu-badge">{T.esc(badge_text)}</span>
</div>
<div class="lp-menu-body">
<div class="lp-menu-title">{T.esc(name)}</div>
<div class="lp-menu-desc">{T.esc(desc)}</div>
<ul class="lp-menu-ingredients">{bahan_html}</ul>
<div class="lp-menu-footer">
{alert_html}
{sop_html}
</div>
</div>
</div>""")

    cards_joined = "".join(cards)
    html = f"""<section id="menu" class="lp-section">
<div class="lp-section-head">
<div class="lp-section-badge">Jadwal Kuliner</div>
<h2 class="lp-section-title">Menu Minggu Ini</h2>
<p class="lp-section-sub">Disusun bergizi seimbang dengan rotasi harian simetris 3 kolom dari Senin sampai Sabtu.</p>
</div>
<div class="lp-menu-grid">
{cards_joined}
</div>
</section>"""
    st.markdown(html, unsafe_allow_html=True)


def _paket() -> None:
    cat = catalog()
    packages = cat.get("packages", [])

    cards = []
    for idx, pkg in enumerate(packages):
        days = pkg.get("days") or []
        price = _rupiah(pkg.get("price")) if pkg.get("price") else "Harga via Bot"
        featured = (idx == 0)
        
        card_cls = "lp-pricing-card featured" if featured else "lp-pricing-card"
        badge_html = "<div class='lp-popular-badge'>Paling Populer</div>" if featured else ""
        btn_cls = "primary" if featured else "secondary"
        
        order_url, has_bot = _cta_url("order")
        target_attr = "target='_blank' rel='noopener'" if has_bot else ""
        
        day_pills_html = "".join(f"<span class='dk-pill'>{T.esc(str(d)[:3])}</span>" for d in days)

        cards.append(f"""<div class="{card_cls}">
{badge_html}
<div>
<h3 style="font-size:1.15rem;margin:0 0 6px">{T.esc(pkg.get('name', 'Paket'))}</h3>
<p style="font-size:0.86rem;color:var(--dk-muted);margin:0 0 12px">{T.esc(pkg.get('description', ''))}</p>
<div style="margin-bottom:12px">{day_pills_html}</div>
</div>
<div>
<div class="lp-price-val">{price} <small>/ paket</small></div>
<a href="{order_url}" {target_attr} class="lp-pricing-btn {btn_cls}">Pilih Paket Ini →</a>
</div>
</div>""")

    cards_joined = "".join(cards)
    html = f"""<section id="paket" class="lp-section">
<div class="lp-section-head">
<div class="lp-section-badge">Pilihan Berlangganan</div>
<h2 class="lp-section-title">Paket Katering Fleksibel</h2>
<p class="lp-section-sub">Pilih frekuensi makan siang yang paling sesuai dengan ritme harian Anda.</p>
</div>
<div class="lp-pricing-grid">
{cards_joined}
</div>
</section>"""
    st.markdown(html, unsafe_allow_html=True)


def _keamanan() -> None:
    cat = catalog()
    allergens = cat.get("allergens", [])

    cards_html = "".join(f"""<div class="lp-allergen-card">
<div class="lp-allergen-name">🛡️ {T.esc(a.get('label', ''))}</div>
<p class="lp-allergen-desc">{T.esc(a.get('risiko', 'Peralatan dan area masak disterilisasi khusus.'))}</p>
</div>""" for a in allergens)

    html = f"""<section id="keamanan" class="lp-section">
<div class="lp-section-head">
<div class="lp-section-badge">Standar Higienis</div>
<h2 class="lp-section-title">Keamanan Pangan & Profil Pantangan</h2>
<p class="lp-section-sub">Setiap profil pantangan yang Anda pilih diteruskan ke dapur sebagai protokol wajib.</p>
</div>
<div class="lp-allergen-grid">
{cards_html}
</div>
</section>"""
    st.markdown(html, unsafe_allow_html=True)


def _faq() -> None:
    st.markdown("""<section id="faq" class="lp-section">
<div class="lp-section-head">
<div class="lp-section-badge">Bantuan</div>
<h2 class="lp-section-title">Pertanyaan yang Sering Diajukan</h2>
<p class="lp-section-sub">Ketahui lebih lanjut mengenai proses, keamanan bahan, dan pemesanan.</p>
</div>
</section>""", unsafe_allow_html=True)

    items = [
        ("Apakah semua menu bebas gluten?",
         "Tidak semua, dan kami tidak membuat klaim umum yang menyesatkan. Bot kami menyaring menu yang "
         "benar-benar aman sesuai profil pantangan Anda, dan potensi alergen selalu ditandai terbuka pada menu."),
        ("Bagaimana cara mengubah paket yang sudah dipesan?",
         "Cukup kirimkan perintah <code>/start</code> atau <code>/order</code> ke bot Telegram. Pemesanan baru "
         "tidak akan menghapus riwayat Dietary Passport Anda."),
        ("Bisakah saya memesan tanpa pantangan apa pun?",
         "Tentu saja bisa. Standar kebersihan dan sterilisasi dapur kami tetap diterapkan secara penuh."),
        ("Kapan batas waktu pembatalan pesanan harian?",
         "Pembatalan dapat dilakukan sebelum tiket pesanan masuk ke status “Sedang Dimasak” di dapur."),
        ("Apakah makanan bisa diantar langsung ke kantor?",
         "Bisa. Cukup cantumkan alamat lengkap kantor serta perkiraan jam kirim pada catatan pesanan di bot."),
    ]
    for q, a in items:
        with st.expander(f"💬  {q}"):
            st.markdown(a, unsafe_allow_html=True)


def _cta_akhir() -> None:
    order_url, has_bot = _cta_url("order")
    ai_url, _ = _cta_url("ai")
    target_attr = "target='_blank' rel='noopener'" if has_bot else ""

    html = f"""<section id="cta" class="lp-cta-card">
<h2>Satu Chat, Makan Siang Aman Siap Diantar.</h2>
<p>
Buka bot Telegram DovaGenome untuk memilih paket, menandai pantangan,
dan mengirim tiket langsung ke dapur tanpa formulir yang rumit.
</p>
<div class="lp-hero-actions">
<a href="{order_url}" {target_attr} class="lp-btn lp-btn-primary">⚡ Mulai Pesan Sekarang</a>
<a href="{ai_url}" {target_attr} class="lp-btn lp-btn-secondary">🤖 Konsultasi AI Alergi</a>
</div>
</section>"""
    st.markdown(html, unsafe_allow_html=True)


def _footer() -> None:
    bot_url, _ = _cta_url()
    html = f"""<footer class="lp-footer">
<div class="lp-footer-brand">
<span>🍽️</span> {T.esc(T.BRAND_NAME)} — <span style="font-weight:400;color:var(--dk-muted)">{T.esc(T.BRAND_SUB)}</span>
</div>
<div class="lp-footer-links">
<a href="#menu">Menu</a>
<a href="#paket">Paket</a>
<a href="#keamanan">Keamanan</a>
<a href="#faq">FAQ</a>
<a href="{bot_url}" target="_blank" rel="noopener">Telegram Bot</a>
</div>
<div>© 2026 {T.esc(T.BRAND_NAME)}. All rights reserved.</div>
</footer>"""
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Render Entry Point
# ---------------------------------------------------------------------------

def render_landing(preview: bool = False) -> None:
    """Tampilkan landing page modern & minimalis."""
    st.markdown(_LANDING_CSS, unsafe_allow_html=True)

    if preview:
        st.info("👁️ **Pratinjau Landing Page Tamu.** Inilah tampilan yang dilihat pelanggan.", icon="ℹ️")

    if not preview:
        _nav()

    _hero()
    _stats()
    _fitur()
    _cara_pesan()
    _menu_mingguan()
    _paket()
    _keamanan()
    _faq()
    _cta_akhir()
    _footer()


if __name__ == "__main__":
    T.page_config("Precision Catering", icon="🍽️", layout="wide",
                  initial_sidebar="collapsed")
    T.inject_css(chrome=True)
    render_landing()