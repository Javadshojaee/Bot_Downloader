import os
import telebot
import yt_dlp
import threading
from flask import Flask
from telebot import types

# ۱. راه‌اندازی Flask (برای اینکه هاستِ Render فکر کنه رباتت یه سایت فعاله)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

# ۲. راه‌اندازی ربات تلگرام
TOKEN = os.environ.get('BOT_TOKEN') # حتماً توکن رو توی .env بذار
bot = telebot.TeleBot(TOKEN)

# ۳. منطقِ هوشمند برای تشخیص حجم ویدیو
def process_video_logic(message):
    url = message.text
    chat_id = message.chat.id
    bot.reply_to(message, "عمو جواد داره بررسی می‌کنه... ⏳")

    try:
        # تنظیمات yt-dlp برای گرفتن اطلاعات ویدیو بدون دانلود کردنش
        ydl_opts = {'format': 'best'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            file_size = info.get('filesize') or info.get('filesize_approx', 0)
            video_url = info.get('url')

        # اگه حجم فایل بیشتر از ۵۰ مگابایت بود (۵۰ * ۱۰۲۴ * ۱۰۲۴ بایت)
        if file_size > 50 * 1024 * 1024:
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton("📥 دانلود فایل سنگین (لینک مستقیم)", url=video_url)
            markup.add(btn)
            bot.send_message(chat_id, "ویدیو خیلی سنگینه (بالای ۵۰ مگ). از لینک زیر با سرعت بالا دانلودش کن:", reply_markup=markup)
        
        else:
            # اگه حجم فایل مناسب بود، دانلود و ارسال کن
            bot.send_message(chat_id, "حجم ویدیو مناسبه! دارم دانلودش می‌کنم... 🔄")
            with yt_dlp.YoutubeDL({'outtmpl': 'video.mp4', 'format': 'best'}) as ydl:
                ydl.download([url])
            
            with open('video.mp4', 'rb') as video:
                bot.send_video(chat_id, video)
            
            # پاک کردن فایل بعد از ارسال برای خالی شدن حافظه
            if os.path.exists('video.mp4'):
                os.remove('video.mp4')

    except Exception as e:
        bot.reply_to(message, f"عمو جواد یه خطایی پیش اومد: {str(e)}")

# دستور شروع
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "سلام عمو جواد! لینک ویدیوت رو بفرست تا برات جادویی دانلودش کنم! ✨")

# دریافت لینک ویدیو
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    process_video_logic(message)

# ۴. اجرای همزمان Flask و ربات
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    # اجرای وب‌سرور در یک ترد جداگانه
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # اجرای ربات
    bot.polling(none_stop=True)
