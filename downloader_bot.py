import os
import telebot
from dotenv import load_dotenv
import yt_dlp
import threading

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

# دایرکتوری برای ذخیره موقت ویدیوها
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "سلام عمو جواد! لینک ویدیوت رو بفرست تا برات جادویی دانلودش کنم! ✨")

@bot.message_handler(func=lambda message: True)
def download_video(message):
    url = message.text.strip()
    
    # تبدیل خودکار reels به reel برای اینستاگرام
    if "instagram.com/reels/" in url:
        url = url.replace("instagram.com/reels/", "instagram.com/reel/")

    msg = bot.reply_to(message, "⏳ عمو جواد داره بررسی می‌کنه...")

    def process_download():
        try:
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
                'format': 'best',
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)

            # بررسی حجم فایل برای ارسال در تلگرام (زیر 50 مگابایت)
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            if file_size > 50:
                bot.edit_message_text("❌ حجم ویدیو بیشتر از 50 مگابایت است و تلگرام اجازه ارسال آن را نمی‌دهد.", message.chat.id, msg.message_id)
                os.remove(file_path)
                return

            bot.edit_message_text("📤 در حال ارسال ویدیو...", message.chat.id, msg.message_id)
            
            with open(file_path, 'rb') as video:
                bot.send_video(message.chat.id, video)
            
            bot.delete_message(message.chat.id, msg.message_id)
            
            # پاک کردن فایل از روی هاست/سیستم بعد از ارسال
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            print(f"Error: {e}")
            bot.edit_message_text(f"❌ عمو جواد یه خطایی پیش اومد:\n{str(e)}", message.chat.id, msg.message_id)

    # اجرای عملیات دانلود در یک ترد جداگانه برای جلوگیری از فریز شدن ربات
    threading.Thread(target=process_download).run()

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
