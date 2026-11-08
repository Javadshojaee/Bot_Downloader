import os
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# توکن رباتی که دادی
TOKEN = "AAGvB60AX9TurOopag9yqHOqkWdx9twpWuM"

app = Flask(__name__)

# کانفیگ‌های ربات تلگرام
telegram_app = ApplicationBuilder().token(TOKEN).build()

# حداکثر حجم مجاز (۴۸۰ مگابایت)
MAX_FILE_SIZE = 480 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام عمو جواد! 🤖🚀\n"
        "لینک ویدیوی یوتیوب، اینستاگرام یا تیک‌تاک رو بفرست تا با کمک فلسک برات دانلودش کنم و بفرستم.\n"
        "حواسم به محدودیت ۴۸۰ مگابایت هم هست!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("عزیز دل، لطفاً یک لینک معتبر بفرست!")
        return

    msg = await update.message.reply_text("⏳ در حال پردازش و دانلود ویدیو، صبور باش عمو جواد...")

    output_template = "downloaded_video.mp4"
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
        'outtmpl': output_template,
        'max_filesize': MAX_FILE_SIZE,
        'noplaylist': True,
    }

    try:
        def download_video():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        # اجرای دانلود در ترد جداگانه برای جلوگیری از بلاک شدن برنامه
        file_path = await asyncio_to_thread_helper(download_video)

        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            
            if file_size > MAX_FILE_SIZE:
                await msg.edit_text("❌ حجم ویدیوی دانلود شده بیشتر از ۴۸۰ مگابایت است.")
                os.remove(file_path)
                return

            await msg.edit_text("🚀 دانلود انجام شد، در حال ارسال به تلگرام...")
            
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✨ ویدیوی شما آماده است!",
                    supports_streaming=True
                )
            
            os.remove(file_path)
            await msg.delete()
        else:
            await msg.edit_text("❌ متأسفانه دانلود ویدیو با خطا مواجه شد.")

    except Exception as e:
        await msg.edit_text(f"❌ خطایی رخ داد: {str(e)}")
        if os.path.exists(output_template):
            os.remove(output_template)

# تابع کمکی برای اجرای کدهای سنکرون در محیط آسنکرون
def asyncio_to_thread_helper(func):
    import asyncio
    return asyncio.run_coroutine_threadsafe(asyncio.to_thread(func), telegram_app.bot_data.get('loop', asyncio.get_event_loop())).result()

# افزودن هندلرها به اپلیکیشن تلگرام
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

@app.route("/")
def home():
    return "Bot is running with Flask and Telegram!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """دریافت آپدیت‌ها از طریق وب‌هوک تلگرام"""
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    
    # اجرای پردازش پیام در پس‌زمینه
    async def process():
        async with telegram_app:
            await telegram_app.initialize()
            await telegram_app.process_update(update)

    threading.Thread(target=lambda: asyncio.run(process())).start()
    return "OK", 200

if __name__ == "__main__":
    # اگر خواستید به صورت لوکال با پایتون تست کنید
    app.run(host="0.0.0.0", port=5000)
