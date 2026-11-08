import os
import threading
import yt_dlp
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# توکن بات شما
TOKEN = "9057289606:AAGvB60AX9TurOopag9yqHOqkWdx9twpWuM"
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__)
telegram_app = None

@app.route('/')
def home():
    return "Bot is active and running!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string, telegram_app.bot)
        telegram_app.update_queue.put(update)
        return 'ok'
    return 'invalid', 400

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام عمو جواد! 👋 لینک یوتیوب، اینستاگرام یا تیک‌تاک رو بفرست تا ویدیو رو برات دانلود کنم.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("لطفاً یک لینک معتبر بفرست!")
        return

    await update.message.reply_text("⏳ در حال دانلود ویدیو، لطفاً کمی صبر کن...")

    output_template = "video.mp4"
    if os.path.exists(output_template):
        os.remove(output_template)

    ydl_opts = {
        'format': 'mp4/best',
        'max_filesize': 480 * 1024 * 1024, # حداکثر 480 مگابایت
        'outtmpl': output_template,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(output_template):
            file_size = os.path.getsize(output_template)
            if file_size > 50 * 1024 * 1024:
                await update.message.reply_text("⚠️ حجم ویدیو بالاست (بیشتر از حد مجاز تلگرام برای ارسال مستقیم)، اما دانلود انجام شد.")
            else:
                with open(output_template, 'rb') as video_file:
                    await update.message.reply_video(video=video_file)
            os.remove(output_template)
        else:
            await update.message.reply_text("❌ دانلود ویدیو انجام نشد یا فایل پیدا نشد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در دانلود: {str(e)}")

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

def main():
    global telegram_app
    telegram_app = Application.builder().token(TOKEN).build()
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # اجرای وب‌سرور فلاسک در یک ترد جداگانه
    threading.Thread(target=run_flask).start()

    # راه‌اندازی ربات به صورت پولینگ یا وب‌هوک ساده
    print("Bot is starting...")
    telegram_app.run_polling()

if __name__ == '__main__':
    main()

