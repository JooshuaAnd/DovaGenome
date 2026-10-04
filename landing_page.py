"""
DovaGenome — Landing Page Tamu (Public)
========================================
Situs marketing satu halaman untuk calon pelanggan. Semua tombol CTA
mengarah langsung ke bot Telegram lewat deep-link, jadi tamu tidak perlu
mengisi formulir web.

Cara menjalankan:
    streamlit run landing_page.py

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
        return f"Rp{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


# ---------------------------------------------------------------------------
# Bagian-bagian halaman
# ---------------------------------------------------------------------------

def _nav() -> None:
    T.st_markdown(T.brand_bar(
        links=(
            ("Menu Mingguan", "#menu"),
            ("Paket", "#paket"),
            ("Keamanan Pangan", "#keamanan"),
            ("Cara Pesan", "#cara"),
            ("Tanya AI", "#cta"),
        ),
    ))


def _hero() -> None:
    T.st_markdown(T.hero(
        eyebrow="Precision Catering · Jakarta",
        title="Makan siang mingguan yang benar-benar aman untuk tubuh Anda.",
        lede=(
            "Setiap pesanan membawa profil pantangan sendiri. Dapur kami memisahkan "
            "peralatan, talenan, dan zona masak untuk tiap profil — lalu mengirim "
            "tiket yang bisa Anda pantau statusnya dari masuk sampai diantar."
        ),
        trust=(
            "✅ 6 hari layanan",
            "🧬 Filter pantangan presisi",
            "🔪 Protokol steril per pesanan",
            "🧾 Status pesanan transparan",
        ),
    ))

    c1, c2, c3 = st.columns([1.1, 1, 1])
    with c1:
        T.telegram_cta("Pesan Sekarang di Telegram", "order",
                       type="primary", use_container_width=True)
    with c2:
        T.telegram_cta("Tanya AI soal Alergi", "ai", use_container_width=True)
    with c3:
        T.telegram_cta("Lihat Menu via Bot", "menu", use_container_width=True)

    if not D.bot_username():
        st.warning(
            "⚠️ **Tautan Telegram belum aktif.** Isi `TELEGRAM_BOT_USERNAME` di file "
            "`.env` agar tombol di atas mengarah ke bot yang benar.",
            icon="🔗",
        )


def _stats() -> None:
    cat = catalog()
    T.st_markdown(
        "<div style='height:26px'></div>"
        + T.kpi_row([
            ("Hari layanan", f"{len(cat['menus'])}", "Senin sampai Sabtu", T.FOREST_600),
            ("Paket tersedia", f"{len(cat['packages'])}", "pilih sesuai ritme", T.GOLD_600),
            ("Profil pantangan", f"{len(cat['allergens'])}", "difilter otomatis", T.ROSE_600),
            ("Keterlacakan", "100%", "tiap tiket terpantau", T.FOREST_900),
        ])
    )


def _fitur() -> None:
    T.st_markdown('<div id="kenapa"></div>' + T.section_head(
        "Kenapa DovaGenome",
        "Empat hal yang membedakan kami dari katering biasa.",
    ))
    cards = [
        ("🧬", "", "Filter pantangan presisi",
         "Pilih sekali profil pantangan Anda. Semua menu mingguan otomatis disaring, "
         "dan tiap bahan diperiksa satu per satu — bukan sekadar claims bebas gluten."),
        ("🔪", "dk-icon-gold", "Protokol steril per pesanan",
         "Setiap tiket membawa catatan peralatan khusus: talenan, wajan, dan minyak "
         "yang tidak boleh bersentuhan dengan bahan profil lain."),
        ("🧾", "", "Tiket yang bisa dilacak",
         "Status pesanan terbuka: masuk antrean, sedang dimasak, dikemas, sampai diantar. "
         "Tidak ada lagi pertanyaan “sudah dikirim belum?”"),
        ("🤖", "dk-icon-gold", "Asisten AI sepanjang hari",
         "Tanyakan keamanan bahan apa pun lewat bot. AI kami membaca profil Anda "
         "sebelum menjawab, bukan menebak."),
    ]
    html = "".join(
        f"""<div class="dk-card dk-card-accent">
  <div class="dk-icon-badge {mod}">{glyph}</div>
  <h3>{T.esc(title)}</h3>
  <p>{T.esc(text)}</p>
</div>"""
        for glyph, mod, title, text in cards
    )
    T.st_markdown(f'<div class="dk-grid dk-c2">{html}</div>')


def _cara_pesan() -> None:
    T.st_markdown('<div id="cara"></div>' + T.section_head(
        "Cara Pemesanan",
        "Tiga langkah, tanpa formulir, langsung lewat Telegram.",
    ))
    steps = [
        ("1️⃣", "Pilih paket",
         "Tentukan hari layanan: 6 hari penuh, hari kerja, atau 3 hari pilihan."),
        ("2️⃣", "Tandai pantangan",
         "Centang profil alergi Anda — gluten, seafood, kacang, susu, telur, atau kedelai."),
        ("3️⃣", "Konfirmasi ke dapur",
         "Periksa pratinjau menu, lalu tekan konfirmasi. Tiket langsung masuk ke dapur."),
    ]
    html = "".join(
        f"""<div class="dk-step on">
  <div class="dk-step-num" style="font-size:1rem">{glyph}</div>
  <div class="dk-step-title">{T.esc(title)}</div>
  <div class="dk-step-desc">{T.esc(text)}</div>
</div>"""
        for glyph, title, text in steps
    )
    T.st_markdown(f'<div class="dk-steps">{html}</div>')


def _menu_mingguan() -> None:
    cat = catalog()
    today = D.today_name()
    T.st_markdown('<div id="menu"></div>' + T.section_head(
        "Menu Minggu Ini",
        "Satu menu untuk setiap hari layanan.",
        "Menu diperbarui oleh tim dapur setiap awal minggu. Halaman ini selalu "
        "menampilkan versi terbaru.",
    ))

    cards = []
    for day in D.DAYS:
        doc     = cat["menus"].get(day, {})
        name    = doc.get("nama_menu", "—")
        desc    = doc.get("deskripsi", "")
        bahan   = [b for b in doc.get("bahan_detail", []) if isinstance(b, dict)]
        alat    = [a for a in doc.get("alat_dapur_steril", []) if a]
        is_today = day == today

        bahan_html = "".join(f"<li>{T.esc(b.get('nama', ''))}</li>" for b in bahan[:4])
        if not bahan_html:
            bahan_html = "<li>Rincian bahan di-update mingguan oleh dapur</li>"

        mengandung = [
            str(b.get("nama", "")) for b in bahan if "⚠" in str(b.get("potensi_alergen", ""))
        ]
        warn_html = ""
        if mengandung:
            warn_html = (
                "<div class='dk-alert' style='margin-top:12px'><b>⚠️ Mengandung:</b> "
                f"{T.esc(', '.join(mengandung))}</div>"
            )

        alat_html = ""
        if alat:
            sisa = f" +{len(alat) - 1} alat" if len(alat) > 1 else ""
            alat_html = (
                "<div class='dk-sop'><b>🔪 Zona dapur:</b> "
                f"{T.esc(alat[0])}{sisa}</div>"
            )

        tag = "Hari ini" if is_today else "Menu"
        head_cls = "dk-day-head is-today" if is_today else "dk-day-head"
        cards.append(f"""
<div class="dk-day">
  <div class="{head_cls}">
    <span class="dk-day-name">{T.esc(day)}</span>
    <span class="dk-day-tag">{T.esc(tag)}</span>
  </div>
  <div class="dk-day-body">
    <h4>{T.esc(name)}</h4>
    <p class="dk-day-desc">{T.esc(desc)}</p>
    <ul class="dk-list">{bahan_html}</ul>
    {warn_html}
    {alat_html}
  </div>
</div>""")

    T.st_markdown(f'<div class="dk-grid dk-c3">{"".join(cards)}</div>')


def _paket() -> None:
    cat = catalog()
    T.st_markdown('<div id="paket"></div>' + T.section_head(
        "Paket Katering",
        "Pilih ritme yang paling pas untuk Anda.",
    ))

    cards = []
    for idx, pkg in enumerate(cat["packages"]):
        days = pkg.get("days") or []
        if pkg.get("price"):
            price = f"{_rupiah(pkg['price'])} <small>/ paket</small>"
        else:
            price = "Harga dikirim lewat bot"
        featured = idx == 0
        badge = (
            "<span class='dk-chip' style='background:#FBF3E3;color:#8A6A2B;"
            "border:1px solid #EEDFBE'>Paling populer</span>"
            if featured else ""
        )
        accent = "dk-card-gold" if featured else "dk-card-accent"
        cards.append(f"""
<div class="dk-card {accent}">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
    <h3>{T.esc(pkg.get('name', 'Paket'))}</h3>{badge}
  </div>
  <p style="margin:8px 0 12px">{T.esc(pkg.get('description', ''))}</p>
  <div>{T.day_pills(days)}</div>
  <div class="dk-price" style="margin-top:14px">{price}</div>
</div>""")

    T.st_markdown(f'<div class="dk-grid dk-c3">{"".join(cards)}</div>')
    T.st_markdown('<div style="height:12px"></div>')
    T.telegram_cta("Pilih paket lewat Telegram", "order", type="primary")


def _keamanan() -> None:
    cat = catalog()
    T.st_markdown('<div id="keamanan"></div>' + T.section_head(
        "Keamanan Pangan",
        "Profil pantangan yang bisa Anda pilih.",
        "Setiap profil diteruskan ke dapur sebagai protokol wajib pada tiket pesanan Anda.",
    ))
    rows = "".join(
        f"<tr><td><b>{T.esc(a.get('label', ''))}</b></td>"
        f"<td class='dk-muted'>{T.esc(a.get('risiko', '—'))}</td></tr>"
        for a in cat["allergens"]
    )
    T.st_markdown(f"""
<div class="dk-card" style="padding:4px 6px 4px 4px">
  <table class="dk-table">
    <thead><tr><th style="width:34%">Profil pantangan</th><th>Bahan yang dihindari</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>""")


def _faq() -> None:
    T.st_markdown('<div id="faq"></div>' + T.section_head(
        "Pertanyaan Umum",
        "Yang paling sering ditanyakan pelanggan.",
    ))
    items = [
        ("Apakah semua menu bebas gluten?",
         "Tidak semua, dan kami tidak berpura-pura demikian. Bot kami memilih menu yang "
         "aman sesuai profil Anda, dan bila sebuah bahan mengandung alergen, bahan itu "
         "ditandai terbuka di halaman menu."),
        ("Bagaimana cara mengubah paket saya?",
         "Kirim /start lalu pilih lagi paketnya. Pemesanan ulang tidak menghapus "
         "Dietary Passport Anda."),
        ("Bisakah memesan tanpa pantangan apa pun?",
         "Bisa. Prosedurnya tetap steril, hanya tanpa penyiapan peralatan khusus."),
        ("Kapan pesanan bisa dibatalkan?",
         "Sebelum tiket masuk status “Sedang Dimasak”. Hubungi kami lewat bot "
         "sebaiknya agar slot dapur tidak terbuang."),
        ("Apakah bisa kirim ke kantor?",
         "Bisa. Cantumkan alamat dan jam kirim pada catatan pemesanan; pengiriman "
         "menyesuaikan jadwal hari layanan."),
    ]
    for q, a in items:
        with st.expander(q):
            st.markdown(a)


def _cta_akhir() -> None:
    T.st_markdown('<div id="cta"></div>' + T.hero(
        eyebrow="Siap mulai?",
        title="Satu chat, semua langsung beres.",
        lede=(
            "Buka bot Telegram DovaGenome untuk memilih paket, menandai pantangan, "
            "dan mengirim tiket ke dapur — tanpa registrasi, tanpa formulir panjang."
        ),
    ))
    c1, c2, c3 = st.columns([1.1, 1, 1.4])
    with c1:
        T.telegram_cta("Mulai Pesan", "order", type="primary", use_container_width=True)
    with c2:
        T.telegram_cta("Tanya AI", "ai", use_container_width=True)
    with c3:
        st.markdown(
            f"<div class='dk-small dk-muted' style='padding-top:10px'>"
            f"{T.esc(T.BRAND_TAGLINE)}</div>",
            unsafe_allow_html=True,
        )


def _footer() -> None:
    links = [("Menu minggu ini", "#menu"), ("Paket", "#paket"), ("Tanya AI", "#cta")]
    if D.telegram_link():
        links.insert(0, ("Chat Telegram", D.telegram_link()))
    T.st_markdown('<div style="height:40px"></div>' + T.footer(links))


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_landing(preview: bool = False) -> None:
    """
    Tampilkan seluruh landing page.

    preview=True → dipakai admin dashboard untuk menampilkan pratinjau
    (tanpa navigasi anchor agar tidak menggeser halaman admin).
    """
    if preview:
        T.st_markdown(T.note(
            "<b>Pratinjau halaman tamu.</b> Inilah tampilan yang dilihat pelanggan saat "
            "membuka <code>landing_page.py</code>. Setiap tombol mengarah ke bot Telegram.",
            glyph="👁",
        ))
        st.markdown("")

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