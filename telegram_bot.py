"""
DovaGenome — Telegram Bot (Pelanggan)
======================================
Alur pelanggan, dirancang agar tidak ada tombol yang menebak-nebak:

    📍 Langkah 1 dari 3  →  pilih paket
    📍 Langkah 2 dari 3  →  tandai pantangan
    📍 Langkah 3 dari 3  →  konfirmasi ke dapur

Setiap layar selalu punya tombol "🏠 Menu utama" dan "/cancel" untuk keluar.
Menu utama juga bisa dipanggil dari deep-link landing page:

    t.me/<bot>?start=order     → langsung ke langkah 1
    t.me/<bot>?start=ai        → langsung ke konsultasi AI
    t.me/<bot>?start=menu      → pratinjau menu mingguan
    t.me/<bot>?start=orders    → status pesanan sendiri
    t.me/<bot>?start=passport  → Dietary Passport
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
import uuid

import requests
import telebot
from astrapy import DataAPIClient
from dotenv import load_dotenv
from telebot import types
from telebot.formatting import escape_markdown as esc_md

import data as D

load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} belum diisi. Lengkapi nilainya di file .env.")
    return value


# Sembunyikan log error jaringan telebot di terminal
telebot.logger.setLevel(logging.CRITICAL)
log = logging.getLogger("dova.bot")

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN = _required_env("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

FLOW_ID = os.getenv("LANGFLOW_FLOW_ID", "09778e1b-f424-48e9-bf6d-36d8fb2cdb90")
LANGFLOW_API_URL = os.getenv(
    "LANGFLOW_API_URL", f"http://127.0.0.1:7860/api/v1/run/{FLOW_ID}"
)
LANGFLOW_API_KEY = _required_env("LANGFLOW_API_KEY")

#: Nama brand yang tampil di pesan
BRAND = "DovaGenome"
TOTAL_STEPS = 3


# ---------------------------------------------------------------------------
# Astra DB
# ---------------------------------------------------------------------------

ASTRA_DB_API_ENDPOINT      = _required_env("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = _required_env("ASTRA_DB_APPLICATION_TOKEN")
astra_database = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN).get_database(
    ASTRA_DB_API_ENDPOINT
)
D.ensure_collections(astra_database)

user_profiles_collection  = astra_database.get_collection("user_profiles")
kitchen_orders_collection = astra_database.get_collection("kitchen_orders")


# ---------------------------------------------------------------------------
# Katalog dinamis (paket, alergen, menu) — di-cache 2 menit
# ---------------------------------------------------------------------------

_CACHE_LOCK = threading.Lock()
_CACHE_TTL  = 120
_cache_data: dict = {}
_cache_loaded_at: float = 0.0


def _load_config_from_db() -> dict:
    """Tarik katalog dari Astra DB; otomatis jatuh ke data bawaan."""
    raw = D.load_catalog(astra_database)
    packages  = raw["packages"]
    allergens = raw["allergens"]

    def code_of(doc: dict) -> str:
        return str(doc.get("code") or doc.get("_id") or "")

    return {
        "packages":      packages,
        "allergens":     allergens,
        "menus":         raw["menus"],
        "paket_options": {code_of(p): p.get("name", "") for p in packages if code_of(p)},
        "paket_days":    {code_of(p): p.get("days", []) for p in packages if code_of(p)},
        "allergen_opts": {code_of(a): a.get("label", "") for a in allergens if code_of(a)},
        "is_live":       raw["is_live"],
    }


def get_config() -> dict:
    """Katalog ter-cache, dimuat ulang otomatis setelah TTL."""
    global _cache_data, _cache_loaded_at
    with _CACHE_LOCK:
        if time.time() - _cache_loaded_at > _CACHE_TTL or not _cache_data:
            _cache_data      = _load_config_from_db()
            _cache_loaded_at = time.time()
        return _cache_data


def cfg_paket() -> dict[str, str]:   return get_config()["paket_options"]
def cfg_days()  -> dict[str, list]:  return get_config()["paket_days"]
def cfg_algen() -> dict[str, str]:   return get_config()["allergen_opts"]
def cfg_menus() -> dict[str, dict]:  return get_config()["menus"]


# ---------------------------------------------------------------------------
# Session per pengguna
# ---------------------------------------------------------------------------

user_sessions: dict[int, dict] = {}


def session(user_id: int) -> dict:
    return user_sessions.setdefault(user_id, {})


def reset_flow(user_id: int) -> None:
    user_sessions.pop(user_id, None)


# ---------------------------------------------------------------------------
# Penyimpanan profil & pesanan
# ---------------------------------------------------------------------------

def save_user_profile(chat_id, user_data: dict) -> None:
    user_profiles_collection.update_one(
        {"_id": str(chat_id)},
        {"$set": {k: v for k, v in user_data.items() if k != "_id"}},
        upsert=True,
    )


def get_user_profile(chat_id) -> dict:
    try:
        profile = user_profiles_collection.find_one({"_id": str(chat_id)}) or {}
    except Exception as exc:
        print(f"[DB] Gagal membaca profil: {exc}")
        profile = {}
    profile.pop("_id", None)
    return profile


def create_weekly_order(chat_id: int, paket_key: str, allergens: set[str]) -> dict:
    """Buat tiket dapur untuk satu paket mingguan."""
    profile       = get_user_profile(chat_id)
    customer_name = profile.get("nama") or f"Pelanggan-{chat_id}"
    paket_label   = cfg_paket().get(paket_key, paket_key)
    days          = cfg_days().get(paket_key) or D.DAYS[:]
    labels        = [cfg_algen().get(k, k) for k in sorted(allergens)]
    avoided_times = profile.get("avoided_times", [])

    if labels:
        sop = (
            "PROTOKOL WAJIB: peralatan, talenan, dan zona masak terpisah. "
            f"Pantangan aktif: {', '.join(labels)}."
        )
    else:
        sop = "Tidak ada pantangan khusus — prosedur steril standar berlaku."

    now = datetime.datetime.now(datetime.timezone.utc)
    order = {
        "order_id":           f"ORD-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        "chat_id":            chat_id,
        "customer_name":      customer_name,
        "subscription_type":  paket_label,
        "schedule_days":      days,
        "selected_allergens": labels,
        "dietary_profile":    ", ".join(labels) if labels else "Tidak ada",
        "avoided_times":      avoided_times,
        "kitchen_notes":      sop,
        "status":             "PENDING",
        "created_at":         now.isoformat(),
    }
    kitchen_orders_collection.insert_one(order)
    order["_id"] = None

    # Passport selalu diperbarui — termasuk profil lama yang masih "udang/seafood"
    save_user_profile(chat_id, {
        "nama":            customer_name,
        "dietary_profile": order["dietary_profile"],
        "avoided_times":   avoided_times,
    })
    return order


def my_orders(chat_id: int, limit: int = 8) -> list[dict]:
    try:
        return list(
            kitchen_orders_collection.find(
                {"chat_id": int(chat_id)}, sort={"created_at": -1}, limit=limit
            )
        )
    except Exception as exc:
        print(f"[DB] Gagal membaca pesanan: {exc}")
        return []


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

def kb_main() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("1️⃣  Pesan Paket Mingguan", callback_data="menu_order"),
        types.InlineKeyboardButton("2️⃣  Pesanan Saya",         callback_data="menu_orders"),
        types.InlineKeyboardButton("3️⃣  Konsultasi AI Alergi",  callback_data="menu_ai"),
        types.InlineKeyboardButton("4️⃣  Dietary Passport",      callback_data="menu_passport"),
    )
    return kb


def kb_home_row() -> list[types.InlineKeyboardButton]:
    return [types.InlineKeyboardButton("🏠 Menu utama", callback_data="back_main")]


def kb_paket() -> types.InlineKeyboardMarkup:
    kb      = types.InlineKeyboardMarkup(row_width=1)
    options = cfg_paket()
    icons   = ["🍱", "🥗", "📆", "📦"]
    for i, (code, name) in enumerate(options.items()):
        days  = len(cfg_days().get(code, []))
        kb.add(types.InlineKeyboardButton(
            f"{icons[i % len(icons)]}  {name}  ({days} hari)",
            callback_data=f"paket_{code}",
        ))
    kb.add(*kb_home_row())
    return kb


def kb_alergen(active: set[str]) -> types.InlineKeyboardMarkup:
    kb      = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for code, label in cfg_algen().items():
        mark = "✅" if code in active else "⬜"
        # Kode katalog sudah berprefiks "alg_"; jangan ditumpuk jadi "alg_alg_…"
        # (callback_data dibatasi 64 byte oleh Telegram).
        cb = str(code) if str(code).startswith("alg_") else f"alg_{code}"
        buttons.append(types.InlineKeyboardButton(f"{mark} {label}", callback_data=cb))
    if buttons:
        kb.add(*buttons)
    kb.add(
        types.InlineKeyboardButton("➡️  Lanjut — lihat menu", callback_data="alg_done"),
        types.InlineKeyboardButton("⬅️  Ganti paket", callback_data="back_paket"),
    )
    kb.add(*kb_home_row())
    return kb


def kb_konfirmasi() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✅  Kirim Pesanan ke Dapur",    callback_data="confirm_order"),
        types.InlineKeyboardButton("🕐  Atur Waktu yang Dihindari", callback_data="set_avoided"),
        types.InlineKeyboardButton("🤖  Minta Alternatif Menu (AI)", callback_data="alt_menu"),
        types.InlineKeyboardButton("⬅️  Ubah Pantangan",            callback_data="back_allergen"),
    )
    kb.add(*kb_home_row())
    return kb


def kb_back_only() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(row_width=1).add(*kb_home_row())


# ---------------------------------------------------------------------------
# Teks
# ---------------------------------------------------------------------------

def step_header(step: int, title: str) -> str:
    """Penanda posisi agar pengguna selalu tahu di langkah berapa."""
    bar = "".join("▰" if i <= step else "▱" for i in range(1, TOTAL_STEPS + 1))
    return f"📍 *Langkah {step} dari {TOTAL_STEPS}* · {title}\n{bar}"


def md_code(value) -> str:
    """
    Bungkus nilai di dalam code span Telegram.

    Hanya `\\` dan backtick yang perlu di-escape di dalam code span — unlike
    markdown biasa, meng-escape `-` di sana akan menampilkan garis miring
    secara harfiah ke pengguna.
    """
    safe = str(value).replace("\\", "\\\\").replace("`", "\\`")
    return f"`{safe}`"


# Slot waktu yang bisa dihindari pelanggan
AVOIDED_TIME_OPTIONS: dict[str, str] = {
    "avd_pagi":   "Pagi (07.00–09.00)",
    "avd_siang":  "Siang (11.00–13.00)",
    "avd_sore":   "Sore (15.00–17.00)",
    "avd_malam":  "Malam (18.00–20.00)",
}


def kb_avoided_times(active: set[str]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(
            f"{'✅' if code in active else '⬜'} {label}",
            callback_data=f"avd_{code}",
        )
        for code, label in AVOIDED_TIME_OPTIONS.items()
    ]
    kb.add(*buttons)
    kb.add(
        types.InlineKeyboardButton("💾  Simpan & Kembali", callback_data="avd_done"),
    )
    kb.add(*kb_home_row())
    return kb


def text_menu_weekly() -> str:
    menus = cfg_menus()
    lines = ["🍽️ *Menu Mingguan DovaGenome*\n"]
    for day in D.DAYS:
        doc  = menus.get(day, {})
        name = doc.get("nama_menu", "—")
        mark = "👉 " if day == D.today_name() else ""
        lines.append(f"{mark}*{day}* — {name}")
    lines.append(
        "\n_Pesan lewat 1️⃣ *Pesan Paket Mingguan* untuk memakai menu ini._"
    )
    return "\n".join(lines)


def text_avoided_times(active: set[str]) -> str:
    labels = [AVOIDED_TIME_OPTIONS[k] for k in active if k in AVOIDED_TIME_OPTIONS]
    return (
        "🕐 *Atur Waktu Pengiriman yang Dihindari*\n\n"
        "Centak waktu yang *tidak* bisa Anda terima pengiriman.\n"
        "_Ketuk tombol untuk menyalakan/mematikan._\n\n"
        + (f"Saat ini dihindari: _{', '.join(labels)}_" if labels else "Belum ada waktu yang dipilih.")
    )


def text_menu_preview(paket_key: str, allergens: set[str], chat_id: int = 0) -> str:
    days    = cfg_days().get(paket_key) or D.DAYS[:]
    menus   = cfg_menus()
    alg_cfg = cfg_algen()
    lines   = [
        step_header(3, "Konfirmasi"),
        "",
        f"📦 *Paket:* {esc_md(cfg_paket().get(paket_key, paket_key))}",
        f"📅 *Hari layanan:* {', '.join(days)}",
        "",
        "🍽️ *Menu yang akan dimasak:*",
    ]
    for day in days:
        lines.append(f"  • *{day}* — {menus.get(day, {}).get('nama_menu', '—')}")

    if allergens:
        labels = [alg_cfg.get(k, k) for k in sorted(allergens)]
        lines += ["", "🛡️ *Filter pantangan aktif:*", "  " + ", ".join(labels)]
    else:
        lines += ["", "✅ *Tidak ada pantangan* — menu penuh tersedia."]

    # Waktu yang dihindari (dari sesi aktif atau profil tersimpan)
    sess_avoided: set[str] = set()
    if chat_id:
        sess_avoided = session(chat_id).get("avoided_times", set())
        if not sess_avoided:
            sess_avoided = set(get_user_profile(chat_id).get("avoided_times", []))
    if sess_avoided:
        av_labels = [AVOIDED_TIME_OPTIONS.get(k, k) for k in sorted(sess_avoided)]
        lines += ["", f"🕐 *Waktu dihindari:* {', '.join(av_labels)}"]
    else:
        lines += ["", "🕐 *Waktu dihindari:* Belum diatur _(tombol 🕐 di bawah)_"]

    lines += ["", "Tekan *Kirim Pesanan ke Dapur* jika sudah benar."]
    return "\n".join(lines)


def text_ticket(order: dict) -> str:
    days    = ", ".join(order.get("schedule_days", []))
    algs    = ", ".join(order.get("selected_allergens", [])) or "Tidak ada"
    label   = D.STATUS_META.get(order.get("status", "PENDING"), D.STATUS_META["PENDING"])
    avoided = order.get("avoided_times", [])
    av_str  = (
        ", ".join(AVOIDED_TIME_OPTIONS.get(k, k) for k in avoided)
        if avoided else "Tidak ada"
    )
    return (
        "🎫 *Pesanan diterima dapur!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Tiket: {md_code(order['order_id'])}\n"
        f"👤 Nama: {esc_md(str(order['customer_name']))}\n"
        f"📦 Paket: {esc_md(str(order['subscription_type']))}\n"
        f"📅 Hari layanan: {esc_md(days)}\n"
        f"🛡️ Pantangan: {esc_md(algs)}\n"
        f"🕐 Waktu dihindari: {esc_md(av_str)}\n"
        f"🔪 Protokol: _{esc_md(str(order['kitchen_notes']))}_\n"
        f"🔄 Status: {label['emoji']} *{label['label']}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Cek perkembangannya kapan saja lewat *2️⃣ Pesanan Saya*.\n"
        "Terima kasih sudah memesan! 🙏"
    )


def text_orders(rows: list[dict]) -> str:
    if not rows:
        return (
            "🚚 *Belum ada pesanan*\n\n"
            "Yuk mulai lewat 1️⃣ *Pesan Paket Mingguan*. "
            "Pilih paket → tandai pantangan → konfirmasi. Tiga langkah saja."
        )
    lines = ["🚚 *Pesanan Anda*\n"]
    for order in rows:
        status = str(order.get("status", "PENDING"))
        label  = D.STATUS_META.get(status, D.STATUS_META["PENDING"])
        lines += [
            f"{label['emoji']} {md_code(order.get('order_id', '—'))} — {label['label']}",
            f"   📦 {esc_md(str(order.get('subscription_type', '—')))}",
        ]
        day, _ = D.current_menu(order, cfg_menus())
        if day:
            lines.append(f"   📅 Berikutnya: {esc_md(day)}")
        lines.append("")
    lines.append("_Status diperbarui oleh dapur secara otomatis._")
    return "\n".join(lines)


def text_help() -> str:
    return (
        "ℹ️ *Cara pakai bot DovaGenome*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "/start — buka menu utama\n"
        "/order — langsung pilih paket\n"
        "/menu — pratinjau menu minggu ini\n"
        "/orders — status pesanan saya\n"
        "/ai — konsultasi keamanan allergen\n"
        "/passport — Dietary Passport saya\n"
        "/cancel — batalkan alur pemesanan\n\n"
        "Alur pemesanan hanya 3 langkah:\n"
        "1️⃣ pilih paket → 2️⃣ tandai pantangan → 3️⃣ konfirmasi.\n\n"
        "_Setiap layar punya tombol 🏠 Menu utama, jadi tidak pernah tersesat._"
    )


# ---------------------------------------------------------------------------
# Tampilan layar
# ---------------------------------------------------------------------------

def show_main(chat_id: int, edit_id: int | None = None, intro: str = "") -> None:
    name = esc_md(str(get_user_profile(chat_id).get("nama") or "Pelanggan"))
    intro = intro or "Mau melakukan apa hari ini?"
    text = (
        f"👋 Halo, *{name}*!\n\n"
        f"*{BRAND} Precision Catering* 🍽️\n"
        "Makan siang mingguan yang aman untuk profil Anda.\n\n"
        f"{intro}"
    )
    _send_or_edit(chat_id, edit_id, text, kb_main())


def show_paket(chat_id: int, edit_id: int | None = None) -> None:
    text = (
        step_header(1, "Pilih paket") + "\n\n"
        "Berapa hari Anda ingin dilayani?\n"
        "_Paket 6 hari paling sering dipilih._"
    )
    _send_or_edit(chat_id, edit_id, text, kb_paket())


def show_alergen(chat_id: int, edit_id: int | None = None) -> None:
    sess = session(chat_id)
    text = (
        step_header(2, "Tandai pantangan") + "\n\n"
        "Centak semua yang harus dihindari. Bisa lebih dari satu.\n"
        "_Ketuk tombol untuk menyalakan/mematikan._"
    )
    _send_or_edit(chat_id, edit_id, text, kb_alergen(sess.get("allergens", set())))


def show_confirm(chat_id: int, edit_id: int | None = None) -> None:
    sess = session(chat_id)
    text = text_menu_preview(
        sess.get("paket_key", ""),
        sess.get("allergens", set()),
        chat_id=chat_id,
    )
    _send_or_edit(chat_id, edit_id, text, kb_konfirmasi())


def _send_or_edit(chat_id: int, edit_id: int | None, text: str, markup) -> None:
    """Edit pesan yang sama bila memungkinkan; jika tidak, kirim baru."""
    if edit_id:
        try:
            bot.edit_message_text(text, chat_id, edit_id,
                                  parse_mode="Markdown", reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)


def _send_safe(chat_id: int, edit_id: int | None, text: str, markup) -> bool:
    """Kirim teks yang mungkin berisi Markdown valid dari AI (dengan fallback)."""
    attempts = [("edit_message_text", True), ("send_message", False)]
    if not edit_id:
        attempts = [("send_message", False)]

    for index, (method, can_edit) in enumerate(attempts):
        try:
            if method == "send_message":
                bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.edit_message_text(text, chat_id, edit_id,
                                      parse_mode="Markdown", reply_markup=markup)
            return True
        except Exception:
            continue

    # Terakhir: kirim tanpa parse_mode agar isi tetap sampai ke pengguna.
    try:
        if edit_id:
            bot.edit_message_text(text, chat_id, edit_id, reply_markup=markup)
        else:
            bot.send_message(chat_id, text, reply_markup=markup)
        return True
    except Exception as exc:
        print(f"[Kirim] Gagal mengirim pesan: {exc}")
        return False


# ---------------------------------------------------------------------------
# Perintah
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start"])
def cmd_start(message):
    chat_id = message.chat.id
    reset_flow(chat_id)
    payload = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            payload = parts[1].strip().split()[0].lower() if parts[1].strip() else ""
    route_deep_link(chat_id, payload, edit_id=None)


@bot.message_handler(commands=["order"])
def cmd_order(message):
    reset_flow(message.chat.id)
    show_paket(message.chat.id)


@bot.message_handler(commands=["menu"])
def cmd_menu(message):
    bot.send_message(message.chat.id, text_menu_weekly(), parse_mode="Markdown",
                     reply_markup=kb_back_only())


@bot.message_handler(commands=["orders"])
def cmd_orders(message):
    bot.send_message(message.chat.id, text_orders(my_orders(message.chat.id)),
                     parse_mode="Markdown", reply_markup=kb_back_only())


@bot.message_handler(commands=["passport"])
def cmd_passport(message):
    show_passport(message.chat.id, None)


@bot.message_handler(commands=["ai"])
def cmd_ai(message):
    start_ai_chat(message.chat.id, None)


@bot.message_handler(commands=["cancel"])
def cmd_cancel(message):
    reset_flow(message.chat.id)
    bot.send_message(
        message.chat.id,
        "↩️ Alur pemesanan dibatalkan. Tidak ada perubahan yang disimpan.\n"
        "Kapan saja mulai lagi dari menu utama 👇",
        parse_mode="Markdown", reply_markup=kb_main(),
    )


@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.send_message(message.chat.id, text_help(), parse_mode="Markdown",
                     reply_markup=kb_back_only())


def route_deep_link(chat_id: int, payload: str, edit_id: int | None) -> None:
    """Terjemahkan ?start=<payload> dari landing page ke layar yang tepat."""
    if payload == "order":
        show_paket(chat_id, edit_id)
    elif payload in ("ai", "konsultasi"):
        start_ai_chat(chat_id, edit_id)
    elif payload == "menu":
        _send_or_edit(chat_id, edit_id, text_menu_weekly(), kb_back_only())
    elif payload in ("orders", "status"):
        _send_or_edit(chat_id, edit_id, text_orders(my_orders(chat_id)), kb_back_only())
    elif payload == "passport":
        show_passport(chat_id, edit_id)
    else:
        show_main(chat_id, edit_id)


# ---------------------------------------------------------------------------
# Dietary Passport
# ---------------------------------------------------------------------------

def show_passport(chat_id: int, edit_id: int | None = None) -> None:
    profile = get_user_profile(chat_id)
    if not profile:
        text = (
            "📋 *Dietary Passport*\n\n"
            "⚠️ Belum ada profil tercatat.\n"
            "Buat passport otomatis dengan memesan sekali — pilih paket, "
            "lalu tandai pantangan Anda."
        )
    else:
        algs = profile.get("dietary_profile", "Tidak ada")
        text = (
            "📋 *Dietary Passport Anda*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Nama: *{esc_md(str(profile.get('nama', '—')))}*\n"
            f"🛡️ Pantangan aktif: {esc_md(str(algs))}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "_Passport diperbarui setiap kali Anda memesan._"
        )
    _send_or_edit(chat_id, edit_id, text, kb_back_only())


# ---------------------------------------------------------------------------
# Konsultasi AI
# ---------------------------------------------------------------------------

def start_ai_chat(chat_id: int, edit_id: int | None = None) -> None:
    session(chat_id)["step"] = "ai_chat"
    alg = get_user_profile(chat_id).get("dietary_profile") or "belum didaftarkan"
    _send_or_edit(
        chat_id, edit_id,
        "🧬 *Konsultasi Keamanan Allergen*\n\n"
        f"Profil pantangan Anda: _{esc_md(str(alg))}_\n\n"
        "Tulis pertanyaan Anda, misalnya:\n"
        "• _\"Aman gak makan tempe buat bebas gluten?\"_\n"
        "• _\"MENU Rabu mengandung seafood, saya harus ganti apa?\"_\n\n"
        "Tekan 🏠 Menu utama kapan saja untuk berhenti.",
        kb_back_only(),
    )


def ask_langflow(chat_id: int, loading_id: int, prompt: str) -> None:
    """Jawab di thread terpisah agar polling bot tidak terblokir."""
    reply = get_langflow_response(prompt, session_id=chat_id)
    for attempt in range(3):
        if _send_safe(chat_id, loading_id, reply, kb_back_only()):
            return
        if attempt < 2:
            time.sleep(2 ** attempt)
    print("[Langflow] Balasan tidak dapat dikirim ke pengguna.")


# ---------------------------------------------------------------------------
# Langflow
# ---------------------------------------------------------------------------

def get_langflow_response(message_text: str, session_id=None) -> str:
    payload = {
        "input_value": message_text,
        "input_type": "chat",
        "output_type": "chat",
    }
    if session_id:
        payload["session_id"] = str(session_id)
    headers = {"x-api-key": LANGFLOW_API_KEY, "Content-Type": "application/json"}

    try:
        response = requests.post(LANGFLOW_API_URL, json=payload, headers=headers,
                                 timeout=300)
        if response.status_code != 200:
            print(f"[Langflow] HTTP {response.status_code}: {response.text[:300]}")
            return ("Maaf, asisten AI sedang sibuk. Coba lagi beberapa saat lagi, "
                    "atau hubungi tim kami.")
        res = response.json()
        for path in (
            lambda r: r["outputs"][0]["outputs"][0]["results"]["message"]["text"],
            lambda r: r["outputs"][0]["outputs"][0]["artifacts"]["text"],
            lambda r: r["text"],
        ):
            try:
                value = path(res)
                if isinstance(value, str) and value.strip():
                    return value
            except (KeyError, IndexError, TypeError):
                continue
        return "Maaf, balasan AI tidak dapat dibaca. Coba ulangi pertanyaannya."
    except requests.exceptions.Timeout:
        return "Maaf, AI membutuhkan waktu terlalu lama. Silakan coba lagi."
    except Exception as exc:
        print(f"[Langflow] Gangguan koneksi: {exc}")
        return "Maaf, terjadi gangguan koneksi ke asisten AI."


# ---------------------------------------------------------------------------
# Callback query — router
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda c: True)
def on_click(call: types.CallbackQuery):
    """
    Router callback query.

    Penting: satu callback hanya boleh dijawab SATU kali. Telegram menolak
    panggilan `answer_callback_query` kedua dengan "query is too old and invalid",
    sehingga notifikasi kecil (toast) tidak pernah tampil ke pengguna.
    """
    ctx: dict[str, str] = {}
    try:
        _dispatch(call, ctx)
    finally:
        _answer(call, ctx.get("toast"))


def _answer(call: types.CallbackQuery, toast: str | None = None) -> None:
    try:
        if toast:
            bot.answer_callback_query(call.id, toast)
        else:
            bot.answer_callback_query(call.id)
    except Exception:
        log.warning("gagal menjawab callback query", exc_info=True)


def _dispatch(call: types.CallbackQuery, ctx: dict[str, str]) -> None:
    chat_id = call.message.chat.id
    msg_id  = call.message.message_id
    data    = call.data or ""
    sess    = session(chat_id)

    # ── navigasi ──────────────────────────────────────────────────────────
    if data == "back_main":
        reset_flow(chat_id)
        show_main(chat_id, edit_id=msg_id)
        return

    if data == "back_paket":
        sess["step"] = "pick_paket"
        show_paket(chat_id, edit_id=msg_id)
        return

    if data == "back_allergen":
        sess["step"] = "pick_allergen"
        show_alergen(chat_id, edit_id=msg_id)
        return

    if data == "back_ai":
        reset_flow(chat_id)
        show_main(chat_id, edit_id=msg_id)
        return

    # ── menu utama ────────────────────────────────────────────────────────
    if data == "menu_order":
        reset_flow(chat_id)
        session(chat_id)["step"] = "pick_paket"
        show_paket(chat_id, edit_id=msg_id)
        return

    if data == "menu_orders":
        reset_flow(chat_id)
        _send_or_edit(chat_id, msg_id, text_orders(my_orders(chat_id)), kb_back_only())
        return

    if data == "menu_ai":
        start_ai_chat(chat_id, edit_id=msg_id)
        return

    if data == "menu_passport":
        show_passport(chat_id, edit_id=msg_id)
        return

    # ── langkah 1: pilih paket ────────────────────────────────────────────
    if data.startswith("paket_"):
        sess.clear()
        sess["paket_key"] = data[len("paket_"):]
        sess["step"]      = "pick_allergen"
        sess["allergens"] = set()
        show_alergen(chat_id, edit_id=msg_id)
        return

    # ── langkah 2: toggle pantangan ───────────────────────────────────────
    if data.startswith("alg_") and data != "alg_done":
        # callback_data memakai kode katalog apa adanya ("alg_dairy"), namun
        # pesan lama di chat pelanggan masih membawa satu prefiks tambahan
        # ("alg_alg_dairy"). Coba semua bentuknya lalu ambil yang ada di katalog.
        variants = [data]
        while variants[-1].startswith("alg_"):
            variants.append(variants[-1][len("alg_"):])
        cfg = cfg_algen()
        code = next((v for v in variants if v in cfg), variants[-1])
        allergens = sess.setdefault("allergens", set())
        label = cfg.get(code, code)
        if code in allergens:
            allergens.discard(code)
            ctx["toast"] = f"➖ {label} dihapus"
        else:
            allergens.add(code)
            ctx["toast"] = f"✅ {label} ditambahkan"
        try:
            bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=kb_alergen(allergens))
        except Exception:
            pass
        return

    if data == "alg_done":
        sess["step"] = "confirm"
        show_confirm(chat_id, edit_id=msg_id)
        return

    # ── waktu yang dihindari ──────────────────────────────────────────────
    if data == "set_avoided":
        avoided = sess.setdefault("avoided_times", set())
        # Muat dari profil tersimpan jika sesi kosong
        if not avoided:
            stored = get_user_profile(chat_id).get("avoided_times", [])
            avoided.update(stored)
        _send_or_edit(chat_id, msg_id, text_avoided_times(avoided), kb_avoided_times(avoided))
        return

    if data.startswith("avd_") and data != "avd_done":
        code    = data[len("avd_"):]          # "avd_pagi" → "avd_pagi" full code
        full    = data                         # simpan lengkap sebagai key
        avoided = sess.setdefault("avoided_times", set())
        if full in avoided:
            avoided.discard(full)
            ctx["toast"] = f"➖ {AVOIDED_TIME_OPTIONS.get(full, full)} dihapus"
        else:
            avoided.add(full)
            ctx["toast"] = f"✅ {AVOIDED_TIME_OPTIONS.get(full, full)} ditambahkan"
        try:
            bot.edit_message_text(
                text_avoided_times(avoided), chat_id, msg_id,
                parse_mode="Markdown", reply_markup=kb_avoided_times(avoided),
            )
        except Exception:
            pass
        return

    if data == "avd_done":
        # Simpan ke profil DB sekarang agar langsung persisten
        avoided = sess.get("avoided_times", set())
        save_user_profile(chat_id, {"avoided_times": list(avoided)})
        ctx["toast"] = "✅ Waktu yang dihindari tersimpan"
        show_confirm(chat_id, edit_id=msg_id)
        return

    # ── langkah 3: konfirmasi ─────────────────────────────────────────────
    if data == "alt_menu":
        allergens = sess.get("allergens", set())
        labels = [cfg_algen().get(k, k) for k in sorted(allergens)] or ["tanpa pantangan"]
        loading = bot.send_message(
            chat_id, "🤖 AI sedang menyusun alternatif menu…", parse_mode="Markdown"
        )
        threading.Thread(
            target=ask_langflow, args=(chat_id, loading.message_id,
                   "Rekomendasikan menu katering mingguan Senin–Sabtu yang aman untuk "
                   f"pantangan: {', '.join(labels)}. Sebutkan nama menu dan bahan utamanya."),
            daemon=True,
        ).start()
        return

    if data == "confirm_order":
        do_confirm(chat_id, msg_id)
        return

    # ── tombol tidak dikenal ──────────────────────────────────────────────
    try:
        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=kb_main())
    except Exception:
        pass


def do_confirm(chat_id: int, msg_id: int) -> None:
    sess      = session(chat_id)
    paket_key = sess.get("paket_key")
    allergens = sess.get("allergens", set())

    if not paket_key:
        show_paket(chat_id, edit_id=msg_id)
        return

    profile = get_user_profile(chat_id)
    if not profile.get("nama"):
        # Simpan pilihan sementara, lalu minta nama pelanggan.
        sess["step"]          = "awaiting_name"
        sess["pending_paket"] = paket_key
        sess["pending_alg"]   = allergens
        try:
            bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=None)
        except Exception:
            pass
        bot.send_message(
            chat_id,
            "✍️ *Langkah terakhir!* Bot perlu nama Anda untuk mencetak tiket dapur.\n\n"
            "Balas pesan ini dengan *nama lengkap* Anda.",
            parse_mode="Markdown",
        )
        return

    try:
        order = create_weekly_order(chat_id, paket_key, allergens)
    except Exception as exc:
        print(f"[Order] Gagal membuat tiket: {exc}")
        bot.send_message(
            chat_id,
            "😵 Gagal membuat tiket pesanan. Tim teknis sudah diberi tahu. "
            "Silakan coba lagi sebentar lagi.",
            parse_mode="Markdown", reply_markup=kb_main(),
        )
        return

    reset_flow(chat_id)
    _send_or_edit(chat_id, msg_id, text_ticket(order), kb_main())


# ---------------------------------------------------------------------------
# Pesan teks
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text is not None)
def on_text(message):
    chat_id = message.chat.id
    text    = message.text.strip()
    sess    = session(chat_id)

    # Perintah sudah ditangani handler commands — jangan balas dua kali.
    if text.startswith("/"):
        return

    # Nama pelanggan, sebelum tiket dicetak.
    if sess.get("step") == "awaiting_name":
        if len(text) < 2:
            bot.reply_to(message, "Nama terlalu pendek. Tulis nama lengkap Anda ya.")
            return
        pending_alg     = sess.get("pending_alg", set())
        pending_avoided = sess.get("avoided_times", set())
        alg_labels      = [cfg_algen().get(k, k) for k in sorted(pending_alg)]
        # Simpan profil lengkap sebelum buat order agar create_weekly_order baca benar
        save_user_profile(chat_id, {
            "nama":            text[:80],
            "dietary_profile": ", ".join(alg_labels) if alg_labels else "Tidak ada",
            "avoided_times":   list(pending_avoided),
        })
        order = create_weekly_order(
            chat_id,
            sess.get("pending_paket", ""),
            pending_alg,
        )
        reset_flow(chat_id)
        bot.reply_to(message, text_ticket(order), parse_mode="Markdown")
        return

    # Mode konsultasi AI
    if sess.get("step") == "ai_chat":
        loading = bot.send_message(chat_id, "🤖 sedang menganalisis…")
        bot.send_chat_action(chat_id, "typing")
        threading.Thread(target=ask_langflow,
                         args=(chat_id, loading.message_id, text),
                         daemon=True).start()
        return

    # Default: kembalikan ke menu utama
    show_main(chat_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("🤖 Bot Telegram DovaGenome berjalan…  (Ctrl+C untuk berhenti)")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
        except Exception as exc:
            print(f"[Polling] Jaringan bermasalah: {exc}")
            time.sleep(3)