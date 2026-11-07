import os
import telebot
from yt_dlp import YoutubeDL
from flask import Flask

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

app = Flask('')

@app.route('/')
def home():
    print("Ping received!")
    return "Bot is alive and running!"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "سلام عمو جواد! 👋 لینک ویدیو (از یوتیوب، اینستاگرام و...) رو بفرست تا برات دانلود کنم و بفرستم.")

@bot.message_handler(func=lambda message: True)
def download_video(message):
    url = message.text.strip()
    if not url.startswith("http"):
        bot.reply_to(message, "لطفاً یک لینک معتبر بفرست عمو جواد!")
        return

    msg = bot.reply_to(message, "⏳ در حال دانلود ویدیو، صبور باش...")
    
    output_template = 'downloaded_video.mp4'
    
    # اگر فایل قبلی مانده پاکش کنیم
    if os.path.exists(output_template):
        os.remove(output_template)

    ydl_opts = {
        'format': 'best',
        'outtmpl': output_template,
        'max_filesize': 50 * 1024 * 1024, # محدودیت ۵۰ مگابایت تلگرام
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(output_template):
            with open(output_template, 'rb') as video:
                bot.send_video(message.chat.id, video, caption="بفرمایید عمو جواد! اینم ویدیویی که خواستی 🎬✨")
            bot.delete_message(message.chat.id, msg.message_id)
            os.remove(output_template)
        else:
            bot.edit_message_text("❌ خطا در دانلود فایل خروجی!", message.chat.id, msg.message_id)

    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text(f"❌ خطا: امکان دانلود این لینک وجود ندارد یا حجم فایل خیلی زیاد است.", message.chat.id, msg.message_id)
        if os.path.exists(output_template):
            os.remove(output_template)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("Bot is polling...")
    bot.infinity_polling()
