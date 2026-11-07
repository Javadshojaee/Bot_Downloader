import os
import telebot
from dotenv import load_dotenv
import yt_dlp
import threading
from flask import Flask

# بارگذاری متغیرهای محیطی
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# روت وب‌سایت برای جلوگیری از خاموش شدن ربات روی هاست (Render)
@app.route('/')
def home():
    return "Bot is active and running smoothly! 🚀"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "سلام عمو جواد! لینک ویدیوت رو بفرست تا برات جادویی دانلودش کنم! ✨")

@bot.message_handler(func=lambda message: True)
def download_video(message):
    url = message.text.strip()
    
    # اصلاح خودکار لینک‌های اینستاگرام
    if "instagram.com/reels/" in url:
        url = url.replace("instagram.com/reels/", "instagram.com/reel/")

    msg = bot.reply_to(message, "⏳ عمو جواد داره بررسی می‌کنه...")

    def process_download():
        try:
            # تنظیمات پیشرفته yt-dlp برای جلوگیری از خطای Too Many Requests و بن شدن IP
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
                'format': 'best',
                'noplaylist': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.instagram.com/',
                'socket_timeout': 30,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

            # بررسی حجم فایل برای ارسال در تلگرام (زیر 50 مگابایت)
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            if file_size > 50:
                bot.edit_message_text("❌ حجم ویدیو بیشتر از 50 مگابایت است.", message.chat.id, msg.message_id)
                os.remove(file_path)
                return

            bot.edit_message_text("📤 در حال ارسال ویدیو...", message.chat.id, msg.message_id)
            
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            
            bot.delete_message(message.chat.id, msg.message_id)
            
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            print(f"Error: {e}")
            bot.edit_message_text(f"❌ عمو جواد یه خطایی پیش اومد:\n{str(e)}", message.chat.id, msg.message_id)

    threading.Thread(target=process_download).start()

# اجرای هم‌زمان ربات تلگرام و سرور Flask
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    # اجرای ربات در یک ترد جداگانه
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # اجرای وب‌سایت Flask روی پورت مربوطه (مناسب برای Render)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
