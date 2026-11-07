import asyncio
import glob
import logging
import os
import threading
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import yt_dlp

# بارگذاری توکن
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# تنظیمات لاگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# وب‌سرور سبک برای زنده ماندن روی Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running happily!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

MAX_FILE_SIZE_MB = 750
CORRECT_PASSWORD = "KLi123"
authorized_users = set()

restart_keyboard = ReplyKeyboardMarkup(
    [["🔄 شروع مجدد / خروج"]],
    resize_keyboard=True
)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    authorized_users.discard(user_id)
    await update.message.reply_text(
        "سلام عمو جواد! 🤖✨\nلطفاً رمز عبور را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )

def download_video(url: str, user_id: int):
    """دانلود هوشمند با استفاده مستقیم از فایل cookies.txt موجود در پروژه"""
    output_tmpl = f"dl_{user_id}.%(ext)s"
    
    # پیدا کردن فایل کوکی در پوشه پروژه
    cookie_file = "cookies.txt"
    has_cookie = os.path.exists(cookie_file)

    ydl_opts = {
        'outtmpl': output_tmpl,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'socket_timeout': 60,
        'retries': 15,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'web'],
            }
        },
        'quiet': True,
        'no_warnings': True,
        # هدرهای واقعی برای جلوگیری از خطای ۴۲۹ اینستاگرام
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    # اگر فایل کوکی وجود داشت، به تنظیمات اضافه اش کن
    if has_cookie:
        ydl_opts['cookiefile'] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text in ["/start", "🔄 شروع مجدد / خروج"]:
        authorized_users.discard(user_id)
        await start_handler(update, context)
        return

    if user_id not in authorized_users:
        if text == CORRECT_PASSWORD:
            authorized_users.add(user_id)
            await update.message.reply_text(
                "✅ خوش اومدی عمو جواد!\n"
                "لینک ویدیو (یوتیوب یا اینستاگرام) رو بفرست تا بدون خطا دانلود کنم 🚀",
                reply_markup=restart_keyboard
            )
        else:
            await update.message.reply_text("❌ رمز اشتباهه! دوباره وارد کن:")
        return

    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("⚠️ لطفاً یک لینک معتبر اینترنتی بفرست عمو جان!")
        return

    for old_file in glob.glob(f"dl_{user_id}.*"):
        try:
            os.remove(old_file)
        except Exception:
            pass

    status_msg = await update.message.reply_text("📥 در حال دریافت ویدیو... چند لحظه صبر کن ⏳")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, download_video, text, user_id)

        matching_files = [f for f in glob.glob(f"dl_{user_id}.*") if not f.endswith(('.part', '.ytdl'))]
        if not matching_files:
            await status_msg.edit_text("❌ خطایی رخ داد: فایل دانلود شده پیدا نشد!")
            return

        downloaded_file = matching_files[0]
        size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(f"❌ حجم ویدیو ({size_mb:.1f}MB) از سقف مجاز ({MAX_FILE_SIZE_MB}MB) بیشتر است!")
            os.remove(downloaded_file)
            return

        await status_msg.edit_text(f"📤 در حال آپلود ویدیو در تلگرام ({size_mb:.1f} مگابایت)...")
        with open(downloaded_file, 'rb') as video_data:
            await update.message.reply_video(
                video=video_data,
                caption="خدمت شما عمو جواد عزیز! 🎬🔥",
                read_timeout=360,
                write_timeout=360,
                connect_timeout=60
            )

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Download Error: {e}")
        await status_msg.edit_text(f"❌ خطا در پردازش یا دانلود:\n{str(e)[:250]}")

    finally:
        for f in glob.glob(f"dl_{user_id}.*"):
            try:
                os.remove(f)
            except Exception:
                pass

def main():
    if not BOT_TOKEN:
        print("❌ توکن BOT_TOKEN یافت نشد!")
        return

    threading.Thread(target=run_web_server, daemon=True).start()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .read_timeout(360)
        .write_timeout(360)
        .build()
    )

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 ربات روشن شد و آماده کار است...")
    application.run_polling()

if __name__ == '__main__':
    main()

