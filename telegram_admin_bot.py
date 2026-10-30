"""Thin Admin Telegram bot.

This process has its own token and allowlist. It only calls FastAPI; all
approval, audit, inventory and database decisions stay in the backend.
"""

from __future__ import annotations

import os
import io
import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import telebot
from dotenv import load_dotenv

load_dotenv()

TOKEN = (os.getenv("TELEGRAM_ADMIN_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN_ADMIN") or "").strip()
BACKEND = os.getenv("DOVAGENOME_BACKEND_URL", "http://127.0.0.1:8000").strip().rstrip("/")
INTERNAL_TOKEN = (os.getenv("DOVAGENOME_INTERNAL_TOKEN") or os.getenv("LANGFLOW_INTERNAL_TOKEN") or "").strip()
ALLOWED = {value.strip() for value in os.getenv("TELEGRAM_ADMIN_CHAT_IDS", "").split(",") if value.strip()}
try:
    ALERT_HOUR_WIB = max(0, min(23, int(os.getenv("ADMIN_STOCK_ALERT_HOUR_WIB", "8"))))
except ValueError:
    ALERT_HOUR_WIB = 8

if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN_ADMIN (atau TELEGRAM_ADMIN_BOT_TOKEN) belum diisi.")
if not INTERNAL_TOKEN:
    raise RuntimeError("DOVAGENOME_INTERNAL_TOKEN belum diisi.")

bot = telebot.TeleBot(TOKEN)


def _allowed(message_or_chat: object) -> bool:
    chat = getattr(getattr(message_or_chat, "chat", message_or_chat), "id", message_or_chat)
    return str(chat) in ALLOWED


def _request(method: str, path: str, chat_id: int, payload: dict | None = None) -> object:
    response = requests.request(
        method,
        f"{BACKEND}{path}",
        json=payload,
        headers={
            "X-Dova-Internal-Token": INTERNAL_TOKEN,
            "X-Telegram-Chat-Id": str(chat_id),
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _upload_recipe(message, file_name: str, content: bytes | None, caption: str) -> object:
    """Send an admin-only recipe upload to the shared FastAPI intake."""
    match = re.match(r"^/resep(?:@\w+)?\s+(Senin|Selasa|Rabu|Kamis|Jumat|Sabtu)(?:\s+(.+))?$", caption.strip(), re.I)
    if not match:
        raise ValueError("Tambahkan caption: /resep <hari> [nama menu]. Contoh: /resep Jumat Salmon panggang")
    day = next(day for day in ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu") if day.lower() == match.group(1).lower())
    fields = {"hari": day, "menu_name": "", "context": "", "recipe_note": ""}
    upload = {}
    if content is None:
        fields["recipe_note"] = (match.group(2) or "").strip()
        name_match = re.search(r"(?:^|\n)\s*Nama menu\s*:\s*(.+)", fields["recipe_note"], re.I)
        if name_match:
            fields["menu_name"] = name_match.group(1).splitlines()[0].strip()[:200]
    else:
        fields["menu_name"] = (match.group(2) or "").strip()[:200]
        upload = {"file": (os.path.basename(file_name), io.BytesIO(content))}
    response = requests.post(
        f"{BACKEND}/api/admin/telegram/recipes/import",
        data=fields,
        files=upload,
        headers={
            "X-Dova-Internal-Token": INTERNAL_TOKEN,
            "X-Telegram-Chat-Id": str(message.chat.id),
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


@bot.message_handler(commands=["resep"])
def recipe_note(message):
    if not _allowed(message):
        return
    try:
        result = _upload_recipe(message, "", None, message.text or "")
        _reply_recipe_result(message, result)
    except ValueError as exc:
        bot.reply_to(message, str(exc))
    except requests.HTTPError as exc:
        detail = exc.response.text[:350] if exc.response is not None else "HTTP error"
        bot.reply_to(message, f"Draft resep ditolak backend: {detail}")
    except requests.RequestException:
        bot.reply_to(message, "Backend belum dapat dihubungi; draft belum dibuat.")


def _reply_recipe_result(message, result: dict) -> None:
    ai = result.get("ai_draft") or {}
    nutrition = ai.get("nutrition") or {}
    composition = result.get("nutrition_from_composition") or {}
    def value(key: str, unit: str) -> str:
        amount = nutrition.get(key)
        return f"{amount} {unit}" if amount is not None else "belum tersedia"
    bot.reply_to(
        message,
        f"Draft menu dibuat: {result.get('menu_name')} ({result.get('service_day')})\n"
        f"Status menu: belum dipublikasikan · resep menunggu verifikasi\n"
        f"Estimasi AI per porsi: {value('calories_kcal', 'kcal')} · protein {value('protein_g', 'g')} · "
        f"karbo {value('carbs_g', 'g')} · lemak {value('fat_g', 'g')}\n"
        f"Gizi dari data komposisi bahan: {composition.get('status', 'UNAVAILABLE')}\n"
        "Periksa bahan, takaran, alergen, dan risiko kontaminasi silang di Admin → Recipe & BOM Verification.",
    )


@bot.message_handler(content_types=["document", "photo"])
def recipe_upload(message):
    if not _allowed(message):
        return
    caption = message.caption or ""
    try:
        if message.content_type == "photo":
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            file_name = file_info.file_path.rsplit("/", 1)[-1] or "recipe.jpg"
            content = bot.download_file(file_info.file_path)
        else:
            document = message.document
            file_name = document.file_name or "recipe"
            file_info = bot.get_file(document.file_id)
            content = bot.download_file(file_info.file_path)
        result = _upload_recipe(message, file_name, content, caption)
        _reply_recipe_result(message, result)
    except ValueError as exc:
        bot.reply_to(message, str(exc))
    except requests.HTTPError as exc:
        detail = exc.response.text[:350] if exc.response is not None else "HTTP error"
        bot.reply_to(message, f"Upload resep ditolak backend: {detail}")
    except requests.RequestException:
        bot.reply_to(message, "Backend belum dapat dihubungi; draft belum dibuat.")
    except Exception:
        bot.reply_to(message, "File belum dapat diproses. Pastikan format PDF, XLSX, CSV, TXT, MD, JPG, PNG, atau WebP.")


def _run(message, method: str, path: str, payload: dict | None = None) -> object | None:
    try:
        return _request(method, path, message.chat.id, payload)
    except requests.HTTPError as exc:
        detail = exc.response.text[:400] if exc.response is not None else "HTTP error"
        bot.reply_to(message, f"Backend menahan aksi ini: {detail}")
    except requests.RequestException:
        bot.reply_to(message, "Backend belum dapat dihubungi; tidak ada aksi yang diklaim berhasil.")
    return None


def _daily_stock_alert_loop() -> None:
    """Queue at most once per WIB date while the Admin Bot process is online."""
    if not ALLOWED:
        return
    service_chat_id = int(next(iter(ALLOWED)))
    last_queued_day = ""
    wib = ZoneInfo("Asia/Jakarta")
    while True:
        now = datetime.now(wib)
        today = now.date().isoformat()
        if now.hour >= ALERT_HOUR_WIB and today != last_queued_day:
            try:
                _request("POST", "/api/admin/telegram/stock-alerts/queue", service_chat_id)
                last_queued_day = today
            except requests.RequestException:
                # Retry on the next loop; the server-side idempotency key keeps
                # a successful retry from duplicating the alert.
                pass
        time.sleep(60)


@bot.message_handler(commands=["start", "help"])
def start(message):
    if not _allowed(message):
        bot.reply_to(message, "Chat ini belum diizinkan untuk Admin Bot.")
        return
    bot.reply_to(
        message,
        "/dashboard | /stok | /stok_tipis | /forecast | /batch | /po_pending | "
        "/approve_po PO-ID | /reject_po PO-ID alasan | /send_po PO-ID | "
        "/tagihan_supplier | /langflow_status\n"
        "Unggah resep: kirim PDF/foto/Excel dengan caption /resep Jumat [nama menu].",
    )


@bot.message_handler(commands=["status", "dashboard"])
def status(message):
    if not _allowed(message):
        return
    result = _run(message, "GET", "/api/admin/telegram/status")
    if result:
        bot.reply_to(message, f"DB: {result.get('supabase_connected')} | migration: {result.get('migration_status')} | Langflow: {result.get('langflow', {}).get('state', 'unknown')}")


@bot.message_handler(commands=["stok", "stok_tipis"])
def stock(message):
    if not _allowed(message):
        return
    rows = _run(message, "GET", "/api/admin/telegram/stock-alerts")
    if rows is not None:
        bot.reply_to(message, "\n".join(f"{row['ingredient_name']}: {row['current_stock']} {row['unit']} / min {row['min_stock']} ({row['status']})" for row in rows) or "Tidak ada stok kritis.")
    if message.text.startswith("/stok_tipis"):
        _run(message, "POST", "/api/admin/telegram/stock-alerts/queue")


@bot.message_handler(commands=["forecast"])
def forecast(message):
    if not _allowed(message):
        return
    result = _run(message, "GET", "/api/admin/telegram/forecast")
    if result:
        bot.reply_to(message, f"Forecast: {result.get('status')} | operasional={result.get('operational')} | stale={result.get('stale_series_count')} | latest={result.get('latest_observation_date')}")


@bot.message_handler(commands=["batch"])
def batches(message):
    if not _allowed(message):
        return
    result = _run(message, "GET", "/api/admin/telegram/batches")
    if result:
        rows = result.get("items") or []
        bot.reply_to(message, "\n".join(f"{row['batch_id'][:8]} | {row['service_date']} | {row['meal_slot']} | {row['status']} | {row['planned_portions']} porsi" for row in rows) or "Belum ada batch produksi.")


@bot.message_handler(commands=["po_pending"])
def pending(message):
    if not _allowed(message):
        return
    rows = _run(message, "GET", "/api/admin/procurement/telegram/pending")
    if rows:
        bot.reply_to(message, "\n".join(f"{row['po_id']} | {row['supplier_name']} | {row['status']} | {row['total_amount']}" for row in rows))
    elif rows is not None:
        bot.reply_to(message, "Tidak ada draft PO.")


@bot.message_handler(commands=["approve_po", "reject_po", "send_po"])
def po_action(message):
    if not _allowed(message):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(message, "Format: /approve_po PO-ID | /reject_po PO-ID alasan | /send_po PO-ID")
        return
    po_id = parts[1].strip()
    command = parts[0].split("@", 1)[0]
    if command == "/reject_po":
        action = "reject"
        path = f"/api/admin/procurement/telegram/{po_id}/{action}?notes={requests.utils.quote(parts[2] if len(parts) == 3 else 'Ditolak admin Telegram')}"
    else:
        action = "approve" if command == "/approve_po" else "send"
        path = f"/api/admin/procurement/telegram/{po_id}/{action}"
    result = _run(message, "POST", path)
    if result:
        bot.reply_to(message, f"PO {po_id}: {result.get('status', 'diproses')}")


@bot.message_handler(commands=["tagihan_supplier"])
def supplier_invoices(message):
    if not _allowed(message):
        return
    rows = _run(message, "GET", "/api/admin/telegram/supplier-invoices")
    if rows is not None:
        bot.reply_to(message, "\n".join(f"{row['invoice_number']} | {row['status']} | {row['amount']}" for row in rows) or "Belum ada invoice supplier.")


@bot.message_handler(commands=["langflow_status"])
def langflow_status(message):
    if not _allowed(message):
        return
    result = _run(message, "GET", "/api/health/langflow")
    if result:
        bot.reply_to(message, f"Langflow: {result.get('state', result.get('status', 'unknown'))} | configured={result.get('configured')}")


if __name__ == "__main__":
    threading.Thread(target=_daily_stock_alert_loop, name="daily-stock-alert", daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
