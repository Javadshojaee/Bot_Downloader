import os
import telebot
from yt_dlp import YoutubeDL
from flask import Flask
import threading

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "سلام عمو جواد! 👋 لینک ویدیو رو بفرست تا برات دانلود کنم.")

@bot.message_handler(func=lambda message: True)
def download_video(message):
    url = message.text.strip()
    if not url.startswith("http"):
        bot.reply_to(message, "لطفاً یک لینک معتبر بفرست عمو جواد!")
        return

    msg = bot.reply_to(message, "⏳ در حال بررسی و دانلود ویدیو، صبور باش...")
    
    # استفاده از شناسه چت و پیام برای جلوگیری از تداخل دانلودهای همزمان
    output_template = f"video_{message.chat.id}_{message.message_id}.%(ext)s"

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_template,
        'max_filesize': 50 * 1024 * 1024,  # حداکثر ۵۰ مگابایت برای ارسال عادی تلگرام
        'quiet': True,
        'no_warnings': True,
        # شبیه‌سازی مرورگر واقعی برای رد کردن بلاک اینستاگرام
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    # اگر فایل cookies.txt داری (برای ورود به اینستاگرام)، فعالش می‌کنه:
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"

    downloaded_file = None

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)

        if downloaded_file and os.path.exists(downloaded_file):
            with open(downloaded_file, 'rb') as video:
                bot.send_video(message.chat.id, video, caption="بفرمایید عمو جواد! اینم ویدیوت 🎬✨")
            bot.delete_message(message.chat.id, msg.message_id)
            os.remove(downloaded_file)
        else:
            bot.edit_message_text("❌ فایلی برای ارسال پیدا نشد!", message.chat.id, msg.message_id)

    except Exception as e:
        error_msg = str(e)
        print(f"Error details: {error_msg}")
        
        # اگر خطا مربوط به لاگین اینستاگرام بود:
        if "login" in error_msg.lower() or "checkpoint" in error_msg.lower():
            bot.edit_message_text("❌ اینستاگرام برای این پست نیاز به لاگین (کوکی) دارد یا صفحه خصوصی (Private) است!", message.chat.id, msg.message_id)
        else:
            # نمایش خلاصه‌ای از خطای واقعی در کنسول و تلگرام
            bot.edit_message_text(f"❌ خطا در دانلود:\n{error_msg[:120]}", message.chat.id, msg.message_id)
            
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("Bot is polling...")
    bot.infinity_polling()
