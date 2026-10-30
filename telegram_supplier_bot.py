"""Thin Supplier Telegram bot with a separate token and tenant bridge."""

from __future__ import annotations

import os
import hashlib

import requests
import telebot
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_SUPPLIER_BOT_TOKEN", "").strip()
BACKEND = os.getenv("DOVAGENOME_BACKEND_URL", "http://127.0.0.1:8000").strip().rstrip("/")
INTERNAL_TOKEN = (os.getenv("DOVAGENOME_INTERNAL_TOKEN") or os.getenv("LANGFLOW_INTERNAL_TOKEN") or "").strip()

if not TOKEN:
    raise RuntimeError("TELEGRAM_SUPPLIER_BOT_TOKEN belum diisi.")
if not INTERNAL_TOKEN:
    raise RuntimeError("DOVAGENOME_INTERNAL_TOKEN belum diisi.")

bot = telebot.TeleBot(TOKEN)


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


def _po_id_and_rest(message) -> tuple[str, str] | None:
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        return None
    return parts[1].strip(), parts[2].strip() if len(parts) == 3 else ""


def _stable_key(prefix: str, chat_id: int, po_id: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{chat_id}-{po_id}-{digest}"


@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.reply_to(
        message,
        "/po_baru | /po_detail PO-ID | /terima_po PO-ID | /tolak_po PO-ID | "
        "/ajukan_perubahan PO-ID catatan | /kirim_barang PO-ID item_id=qty:unit,... | "
        "/upload_invoice PO-ID NOMOR JUMLAH YYYY-MM-DD | /status_tagihan",
    )


@bot.message_handler(commands=["po_baru"])
def new_pos(message):
    rows = _request("GET", f"/api/internal/telegram/supplier/{message.chat.id}/pos", message.chat.id)
    rows = [row for row in rows if row.get("status") in {"SENT", "ACCEPTED", "PARTIAL"}]
    bot.reply_to(message, "\n".join(f"{row['po_id']} | {row['status']}" for row in rows) or "Tidak ada PO baru.")


@bot.message_handler(commands=["po_detail"])
def detail(message):
    parsed = _po_id_and_rest(message)
    if not parsed:
        bot.reply_to(message, "Format: /po_detail PO-ID")
        return
    po_id, _ = parsed
    row = _request("GET", f"/api/internal/telegram/supplier/{message.chat.id}/pos/{po_id}", message.chat.id)
    items = row.get("items") or []
    body = [f"{row['po_id']} | {row['status']}", f"Total: {row.get('total_amount')}"]
    body.extend(f"#{item['id']} {item['item_name']}: {item['qty']} {item['unit']}" for item in items)
    bot.reply_to(message, "\n".join(body))


@bot.message_handler(commands=["terima_po", "tolak_po"])
def respond(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(message, "Format: /terima_po PO-ID atau /tolak_po PO-ID")
        return
    status = "ACCEPTED" if message.text.startswith("/terima_po") else "REJECTED"
    po_id = parts[1].strip()
    result = _request(
        "POST",
        f"/api/internal/telegram/supplier/{message.chat.id}/pos/{po_id}/respond",
        message.chat.id,
        {"status": status},
    )
    bot.reply_to(message, f"PO {po_id}: {result.get('status', status)}")


@bot.message_handler(commands=["ajukan_perubahan"])
def change_request(message):
    parsed = _po_id_and_rest(message)
    if not parsed or not parsed[1]:
        bot.reply_to(message, "Format: /ajukan_perubahan PO-ID jelaskan perubahan atau ETA")
        return
    po_id, notes = parsed
    result = _request(
        "POST",
        f"/api/internal/telegram/supplier/{message.chat.id}/pos/{po_id}/change-request",
        message.chat.id,
        {
            "notes": notes,
            "idempotency_key": _stable_key("tg-change", message.chat.id, po_id, notes),
        },
    )
    bot.reply_to(message, f"Permintaan perubahan PO {po_id} diteruskan ke admin: {result.get('notification_status', 'PENDING')}")


@bot.message_handler(commands=["kirim_barang"])
def receive_goods(message):
    parsed = _po_id_and_rest(message)
    if not parsed or not parsed[1]:
        bot.reply_to(message, "Format: /kirim_barang PO-ID item_id=qty:unit,item_id=qty:unit")
        return
    po_id, raw_lines = parsed
    lines = []
    try:
        for raw in raw_lines.split(","):
            item_id, amount = raw.strip().split("=", 1)
            quantity, unit = amount.split(":", 1)
            lines.append({"po_item_id": int(item_id), "quantity": float(quantity), "unit": unit.strip()})
    except (ValueError, TypeError):
        bot.reply_to(message, "Format line tidak valid. Contoh: 12=2:kg,13=5:kg")
        return
    result = _request(
        "POST",
        f"/api/internal/telegram/supplier/{message.chat.id}/pos/{po_id}/receive",
        message.chat.id,
        {"lines": lines, "idempotency_key": _stable_key("tg-receipt", message.chat.id, po_id, raw_lines)},
    )
    bot.reply_to(message, f"Penerimaan PO {po_id}: {result.get('status', 'POSTED')} | stok diproses backend.")


@bot.message_handler(commands=["upload_invoice"])
def upload_invoice(message):
    parts = message.text.split()
    if len(parts) != 5:
        bot.reply_to(message, "Format: /upload_invoice PO-ID NOMOR JUMLAH YYYY-MM-DD")
        return
    po_id, invoice_number, amount, due_date = parts[1:]
    try:
        amount_number = float(amount)
    except ValueError:
        bot.reply_to(message, "Jumlah invoice harus berupa angka.")
        return
    result = _request(
        "POST",
        f"/api/internal/telegram/supplier/{message.chat.id}/invoices",
        message.chat.id,
        {
            "invoice_number": invoice_number,
            "payment_terms": "PAY_ON_DELIVERY",
            "amount": amount_number,
            "due_date": due_date,
            "po_id": po_id,
            "idempotency_key": f"tg-invoice-{message.chat.id}-{invoice_number}",
        },
    )
    bot.reply_to(message, f"Invoice {invoice_number} masuk review admin: {result.get('status', 'SUBMITTED')}.")


@bot.message_handler(commands=["status_tagihan", "invoice_mingguan"])
def invoices(message):
    rows = _request("GET", f"/api/internal/telegram/supplier/{message.chat.id}/invoices", message.chat.id)
    bot.reply_to(message, "\n".join(f"{row['invoice_number']} | {row['status']} | {row['amount']}" for row in rows) or "Belum ada invoice supplier.")


if __name__ == "__main__":
    bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
