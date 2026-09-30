import os
import datetime
import requests
import telebot
from telebot import types
import time
import logging
import threading
import uuid
from dotenv import load_dotenv
from astrapy import DataAPIClient

load_dotenv()


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} belum diisi. Lengkapi nilainya di file .env.")
    return value

# Sembunyikan log error jaringan telebot di terminal
telebot.logger.setLevel(logging.CRITICAL)

# 1. Konfigurasi
TELEGRAM_TOKEN = _required_env("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

FLOW_ID = "09778e1b-f424-48e9-bf6d-36d8fb2cdb90"
LANGFLOW_API_URL = f"http://127.0.0.1:7860/api/v1/run/{FLOW_ID}"
LANGFLOW_API_KEY = _required_env("LANGFLOW_API_KEY")

# Storage FSM pendaftaran user: { user_id: "AWAITING_REGISTRATION" }
user_states = {}

# --- DATABASE HELPER (ASTRA DB) ---

ASTRA_DB_API_ENDPOINT = _required_env("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = _required_env("ASTRA_DB_APPLICATION_TOKEN")
astra_client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
astra_database = astra_client.get_database(ASTRA_DB_API_ENDPOINT)

USER_PROFILES_COLLECTION_NAME = "user_profiles"
if USER_PROFILES_COLLECTION_NAME not in astra_database.list_collection_names():
    astra_database.create_collection(USER_PROFILES_COLLECTION_NAME)
user_profiles_collection = astra_database.get_collection(USER_PROFILES_COLLECTION_NAME)

KITCHEN_ORDERS_COLLECTION_NAME = "kitchen_orders"
if KITCHEN_ORDERS_COLLECTION_NAME not in astra_database.list_collection_names():
    astra_database.create_collection(KITCHEN_ORDERS_COLLECTION_NAME)
kitchen_orders_collection = astra_database.get_collection(KITCHEN_ORDERS_COLLECTION_NAME)


def save_user_profile(chat_id, user_data):
    profile = {key: value for key, value in user_data.items() if key != "_id"}
    user_profiles_collection.update_one(
        {"_id": str(chat_id)},
        {"$set": profile},
        upsert=True
    )


def get_user_profile(chat_id):
    profile = user_profiles_collection.find_one({"_id": str(chat_id)})
    if profile:
        profile.pop("_id", None)
    return profile


def create_kitchen_order(chat_id, menu_name, notes=""):
    profile = get_user_profile(chat_id)
    if not profile:
        raise ValueError("Profil pengguna belum terdaftar.")

    dietary_profile = profile.get("dietary_profile", "udang/seafood")
    kitchen_notes = (
        "Gunakan peralatan masak khusus dan area terpisah untuk mencegah "
        f"kontaminasi silang dengan {dietary_profile}."
    )
    if notes.strip():
        kitchen_notes += f" Catatan pelanggan: {notes.strip()}"

    created_at = datetime.datetime.now(datetime.timezone.utc)
    order = {
        "order_id": f"ORD-{created_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}",
        "chat_id": chat_id,
        "nama": profile.get("nama", ""),
        "menu_name": menu_name.strip(),
        "dietary_profile": dietary_profile,
        "kitchen_notes": kitchen_notes,
        "status": "PENDING",
        "created_at": created_at.isoformat()
    }
    kitchen_orders_collection.insert_one(order)
    return order


def _send_kitchen_order_confirmation(message, menu_name, notes=""):
    try:
        order = create_kitchen_order(message.chat.id, menu_name, notes)
    except ValueError as error:
        bot.reply_to(message, str(error) + " Kirim /start untuk mendaftar.")
        return
    except Exception as error:
        print(f"Error membuat tiket dapur: {error}")
        bot.reply_to(message, "Maaf, pesanan belum dapat dicatat. Silakan coba lagi.")
        return

    confirmation = (
        "Pesanan berhasil dicatat!\n"
        f"Tiket: {order['order_id']}\n"
        f"Menu: {order['menu_name']}\n"
        f"Nama: {order['nama']}\n"
        f"Pantangan/alergi: {order['dietary_profile']}\n"
        f"Catatan dapur: {order['kitchen_notes']}\n"
        f"Status: {order['status']}"
    )
    bot.reply_to(message, confirmation)

# --- LANGFLOW HELPER ---

def get_langflow_response(message_text, session_id=None):
    headers = {
        "x-api-key": LANGFLOW_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "input_value": message_text,
        "output_type": "chat",
        "input_type": "chat",
    }
    if session_id:
        payload["session_id"] = str(session_id)
    
    try:
        # Timeout diperpanjang hingga 300 detik (5 menit)
        response = requests.post(LANGFLOW_API_URL, json=payload, headers=headers, timeout=300)
        
        if response.status_code == 200:
            res_data = response.json()
            
            # 1. Coba ekstraksi dari struktur standar Langflow
            try:
                return res_data['outputs'][0]['outputs'][0]['results']['message']['text']
            except (KeyError, IndexError, TypeError):
                pass
            
            # 2. Coba ekstraksi dari struktur alternatif (artifacts/chat output)
            try:
                return res_data['outputs'][0]['outputs'][0]['artifacts']['text']
            except (KeyError, IndexError, TypeError):
                pass

            # 3. Fallback jika struktur berbentuk dict 'text'
            if isinstance(res_data, dict) and "text" in res_data:
                return res_data["text"]

            return "Maaf, respons dari Langflow tidak dapat diparse."
            
        print(f"Langflow Error Code: {response.status_code}, Body: {response.text}")
        return "Maaf, sistem DovaGenome gagal merespons. Silakan coba beberapa saat lagi."
        
    except requests.exceptions.Timeout:
        return "Maaf, proses analisis AI membutuhkan waktu sangat lama (Timeout 5 menit terlampaui). Silakan coba lagi."
    except Exception as e:
        print(f"Error Langflow Exception: {e}")
        return "Maaf, terjadi gangguan koneksi ke AI DovaGenome."

# --- WORKER THREAD FOR LANGFLOW ---

def process_langflow_async(user_id, loading_msg_id, user_text):
    """
    Fungsi ini berjalan di thread terpisah agar tidak membekukan (freeze) polling bot
    """
    ai_reply = get_langflow_response(user_text, session_id=user_id)
    
    try:
        bot.edit_message_text(
            chat_id=user_id,
            message_id=loading_msg_id,
            text=ai_reply
        )
    except Exception as e:
        print(f"Error Edit Message: {e}")
        bot.send_message(user_id, ai_reply)

# --- BOT HANDLERS ---

@bot.message_handler(commands=['start'])
def send_tahap_1_command(message):
    _kirim_menu_sambutan(message.chat.id)


@bot.message_handler(commands=['pesan'])
def handle_kitchen_order_command(message):
    user_id = message.chat.id
    if not get_user_profile(user_id):
        bot.reply_to(message, "Profil Anda belum terdaftar. Kirim /start untuk mendaftar terlebih dahulu.")
        return

    command_parts = message.text.split(maxsplit=1)
    order_details = command_parts[1].strip() if len(command_parts) > 1 else ""
    if not order_details:
        user_states[user_id] = "AWAITING_ORDER_MENU"
        bot.reply_to(
            message,
            "Kirim nama menu yang ingin dipesan. Catatan opsional: nama menu | catatan"
        )
        return

    menu_name, _, notes = order_details.partition("|")
    if not menu_name.strip():
        bot.reply_to(message, "Nama menu tidak boleh kosong. Contoh: /pesan Nasi Goreng | tanpa pedas")
        return
    _send_kitchen_order_confirmation(message, menu_name, notes)

def _kirim_menu_sambutan(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_baru = types.InlineKeyboardButton("🆕 Customer Baru", callback_data="type_customer_baru")
    btn_lama = types.InlineKeyboardButton("👤 Customer Lama", callback_data="type_customer_lama")
    markup.add(btn_baru, btn_lama)

    bot.send_message(
        user_id,
        "Halo! Selamat datang di *Dova Kitchen* 🍽️\nSilakan pilih status Anda:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data in ["type_customer_baru", "type_customer_lama"])
def handle_tahap_1(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    if call.data == "type_customer_baru":
        user_states[user_id] = "AWAITING_REGISTRATION"
        
        caption_text = (
            "Silakan isi data diri Anda terlebih dahulu dengan membalas pesan ini menggunakan format berikut:\n\n"
            "Nama: [Nama Lengkap Anda]\n"
            "Tanggal lahir: [DD-MM-YYYY]"
        )
        bot.send_message(user_id, caption_text)
        
    elif call.data == "type_customer_lama":
        user_data = get_user_profile(user_id)
        
        if not user_data:
            user_states[user_id] = "AWAITING_REGISTRATION"
            bot.send_message(
                user_id, 
                "⚠️ Data Anda belum terdaftar di sistem kami. Silakan lengkapi data diri Anda terlebih dahulu:\n\n"
                "Nama: [Nama Lengkap Anda]\n"
                "Tanggal lahir: [DD-MM-YYYY]"
            )
            return
            
        nama = user_data.get("nama", "")
        tgl_lahir = user_data.get("tanggal_lahir", "")
        dietary_profile = user_data.get("dietary_profile", "udang/seafood")
        
        hari_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        hari_ini = hari_list[datetime.datetime.now().weekday()]
        
        welcome_text = (
            f"Selamat datang kembali di Dova Kitchen, *{nama}*! Senang bertemu denganmu kembali.\n\n"
            f"Hari ini mau makan apa?\n\n"
            f"⚠️ *Peringatan Nutrisi:* Pada minggu ini di hari *{hari_ini}*, ada menu yang mengandung "
            f"*{dietary_profile}*. Hati-hati dalam memesan ya!"
        )
        
        user_states[user_id] = "REGISTERED"
        bot.send_message(user_id, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text is not None)
def handle_incoming_text(message):
    user_id = message.chat.id
    user_text = message.text
    state = user_states.get(user_id)

    # Pesan pertama apapun dari user baru → tampilkan menu sambutan
    if state is None:
        user_states[user_id] = "GREETING_SHOWN"
        _kirim_menu_sambutan(user_id)
        return

    # Jika sudah lihat sambutan tapi belum pilih, tampilkan lagi tanpa spam
    if state == "GREETING_SHOWN":
        _kirim_menu_sambutan(user_id)
        return

    if state == "AWAITING_ORDER_MENU":
        user_states[user_id] = "REGISTERED"
        menu_name, _, notes = user_text.partition("|")
        if not menu_name.strip():
            bot.reply_to(message, "Nama menu tidak boleh kosong. Silakan kirim nama menu yang ingin dipesan.")
            user_states[user_id] = "AWAITING_ORDER_MENU"
            return
        _send_kitchen_order_confirmation(message, menu_name, notes)
        return

    # 1. Alur Pendaftaran Customer Baru
    if state == "AWAITING_REGISTRATION":
        try:
            lines = user_text.split('\n')
            nama = ""
            tgl_lahir = ""
            
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    key_clean = key.strip().lower()
                    val_clean = value.strip()
                    
                    if "nama" in key_clean:
                        nama = val_clean
                    elif "tanggal" in key_clean or "lahir" in key_clean or "tgl" in key_clean:
                        tgl_lahir = val_clean
            
            if nama and tgl_lahir:
                existing_profile = get_user_profile(user_id) or {}
                save_user_profile(user_id, {
                    "nama": nama,
                    "tanggal_lahir": tgl_lahir,
                    "dietary_profile": existing_profile.get("dietary_profile", "udang/seafood")
                })
                user_states[user_id] = "REGISTERED"
                
                success_msg = (
                    f"Terima kasih *{nama}*, data Anda berhasil disimpan! 🎉\n\n"
                    "Mau pesan makanan apa hari ini? Kirim /pesan <nama menu>. "
                    "Sampaikan juga ya kalau kamu punya alergi atau pantangan makanan tertentu!"
                )
                bot.send_message(user_id, success_msg, parse_mode="Markdown")
            else:
                bot.reply_to(
                    message, 
                    "Format belum sesuai. Mohon tuliskan dengan format:\n\nNama: Nama Anda\nTanggal lahir: DD-MM-YYYY"
                )
        except Exception as e:
            print(f"Error Parsing Reg: {e}")
            bot.reply_to(message, "Gagal memproses data. Mohon gunakan format:\nNama: ...\nTanggal lahir: ...")
            
    # 2. Pesanan / Percakapan Bebas via Langflow AI
    else:
        loading_msg = bot.send_message(
            user_id, 
            "⏳ DovaGenome AI sedang memproses & menganalisis resep...\nMohon tunggu sebentar..."
        )
        bot.send_chat_action(user_id, 'typing')
        
        # Menggunakan Thread agar permintaan ke Langflow berjalan di background tanpa memblokir bot
        threading.Thread(
            target=process_langflow_async,
            args=(user_id, loading_msg.message_id, user_text),
            daemon=True
        ).start()

if __name__ == "__main__":
    print("Bot Telegram DovaGenome AI sedang berjalan...")
    
    while True:
        try:
            bot.infinity_polling(
                timeout=20,
                long_polling_timeout=20,
                skip_pending=True
            )
        except Exception as e:
            time.sleep(3)