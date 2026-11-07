import asyncio
import logging
import os
import glob
import threading
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import yt_dlp

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# تنظیمات لاگینگ
logging.basicConfig(level=logging.INFO)

# وب‌سرور برای زنده نگه داشتن روی Render
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

MAX_FILE_SIZE_MB = 750
CORRECT_PASSWORD = "KLi123"
authorized_users = set()

# دکمه ریستارت
restart_keyboard = ReplyKeyboardMarkup([["🔄 شروع مجدد"]], resize_keyboard=True)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in authorized_users: authorized_users.remove(user_id)
    await update.message.reply_text("سلام عمو جواد! 🤖\nلطفاً رمز عبور را وارد کنید:", reply_markup=ReplyKeyboardRemove())

def download_sync(url, user_id, status_msg, loop):
    # اسم فایل اختصاصی برای هر کاربر
    output_tmpl = f"dl_{user_id}.%(ext)s"
    
    def progress_hook(data):
        if data['status'] == 'downloading':
            p = data.get('_percent_str', '0%')
            # فقط درصد‌های رند رو خبر بده که تلگرام بلاک نکنه
            if "0.0%" in p or "25." in p or "50." in p or "75." in p or "100." in p:
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit_text(f"⏳ در حال دانلود: {p}"), loop
                )

    ydl_opts = {
        'format': 'bestvideo*+bestaudio/best',
        'outtmpl': output_tmpl,
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'progress_hooks': [progress_hook],
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    # پیدا کردن فایل دانلود شده
    files = glob.glob(f"dl_{user_id}.*")
    return files[0] if files else None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text == "/start" or text == "🔄 شروع مجدد":
        authorized_users.discard(user_id)
        await start_handler(update, context)
        return

    if user_id not in authorized_users:
        if text == CORRECT_PASSWORD:
            authorized_users.add(user_id)
            await update.message.reply_text("✅ تایید شد! حالا لینک ویدیو رو بفرست:", reply_markup=restart_keyboard)
        else:
            await update.message.reply_text("❌ رمز اشتباهه!")
        return

    # شروع دانلود
    status_msg = await update.message.reply_text("📥 شروع پردازش...")
    try:
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(None, download_sync, text, user_id, status_msg, loop)
        
        if file_path:
            await status_msg.edit_text("📤 در حال ارسال به تلگرام...")
            with open(file_path, 'rb') as f:
                await update.message.reply_video(video=f, caption="خدمت شما! 🔥")
            os.remove(file_path)
            await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ خطا: {str(e)[:100]}")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
