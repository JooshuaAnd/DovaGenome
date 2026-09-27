import telebot
from telebot import types
import requests

# 1. Masukkan Token Telegram
TELEGRAM_TOKEN = "8660984945:AAEVZVzriYzthf9sGTI3dj0MBFfaoQ9ROZU"
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 2. Setup Langflow API
FLOW_ID = "09778e1b-f424-48e9-bf6d-36d8fb2cdb90"
LANGFLOW_API_URL = f"http://127.0.0.1:7860/api/v1/run/{FLOW_ID}" 
LANGFLOW_API_KEY = "sk-icsStYjpZbmbkFTxsOPApv1yMH1qAKwSWijMrqjuFNM"

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
        response = requests.post(LANGFLOW_API_URL, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"DEBUG - API Error {response.status_code}: {response.text}")
            return "Maaf, sistem DovaGenome gagal merespons. Cek log terminal Anda."
            
        response_json = response.json()
        return response_json['outputs'][0]['outputs'][0]['results']['message']['text']
        
    except KeyError as e:
        print(f"DEBUG - Struktur JSON tidak sesuai: {e}\nIsi JSON asli:\n{response_json}")
        return "Maaf, format data dari DovaGenome tidak cocok."
    except Exception as e:
        print(f"DEBUG - Koneksi gagal: {e}")
        return "Maaf, sistem DovaGenome sedang mengalami gangguan jaringan."

def send_welcome_screen(chat_id):
    """Menampilkan pesan sambutan dan tombol menu utama"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_pesan = types.InlineKeyboardButton("🍱 Pesan Menu Aman (Kurasi AI)", callback_data="btn_pesan")
    btn_konsul = types.InlineKeyboardButton("🧬 Konsultasi Alergi & Toleransi", callback_data="btn_konsul")
    btn_profil = types.InlineKeyboardButton("📋 Cek Dynamic Dietary Passport", callback_data="btn_profil")
    markup.add(btn_pesan, btn_konsul, btn_profil)
    
    welcome_text = (
        "👋 *Halo! Selamat datang di Dova Kitchen - DovaGenome AI.*\n\n"
        "Platform katering presisi cerdas dengan audit fasilitas dapur otonom. "
        "Kami membedah resep hingga tingkat molekuler untuk memastikan pesanan Anda 100% bebas dari risiko kontaminasi alergi.\n\n"
        "Silakan pilih layanan yang ingin Anda gunakan:"
    )
    bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode="Markdown")

# 3. Trigger Otomatis saat klik START (/start)
@bot.message_handler(commands=['start'])
def handle_start(message):
    send_welcome_screen(message.chat.id)

# 4. Handle Respons Klik Tombol
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)  # Menghilangkan status loading tombol
    
    if call.data == "btn_pesan":
        bot.send_message(user_id, "🔍 *Memverifikasi katalog resep dan kesiapan dapur steril...*", parse_mode="Markdown")
        bot.send_chat_action(user_id, 'typing')
        ai_reply = get_langflow_response("Tolong tampilkan daftar menu katering yang aman dan siap dipesan hari ini.", session_id=user_id)
        bot.send_message(user_id, ai_reply)
        
    elif call.data == "btn_konsul":
        bot.send_message(
            user_id,
            "💬 *Mode Konsultasi Diet:*\nSilakan ketik pantangan, riwayat alergi, atau kondisi medis Anda "
            "(misal: *'Saya alergi udang, apakah olahan terasi aman?'* atau *'Saya intoleransi laktosa bertingkat'*).",
            parse_mode="Markdown"
        )
        
    elif call.data == "btn_profil":
        bot.send_message(
            user_id,
            f"👤 *Dynamic Dietary Passport*\n"
            f"• User ID: `{user_id}`\n"
            f"• Status Integrasi: Aktif ke Astra DB & Langflow\n\n"
            f"Ketik riwayat reaksi makanan terbaru Anda untuk memperbarui memori biologis adaptif.",
            parse_mode="Markdown"
        )

# 5. Handle Pesan Teks Bebas
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_text = message.text
    user_id = message.chat.id
    
    bot.send_chat_action(user_id, 'typing')
    ai_response = get_langflow_response(user_text, session_id=user_id)
    bot.reply_to(message, ai_response)

if __name__ == "__main__":
    print("Bot Telegram DovaGenome AI sedang berjalan...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"Server error: {e}")