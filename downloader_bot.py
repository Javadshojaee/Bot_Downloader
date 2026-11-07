import os
import re
import glob
import asyncio
import logging
import threading
from urllib.parse import urlparse

import yt_dlp
from flask import Flask
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# تنظیمات
TOKEN = os.getenv("BOT_TOKEN")
PASSWORD = os.getenv("BOT_PASSWORD", "KLi4874")

MAX_FILE_SIZE = 50 * 1024 * 1024

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

keyboard = ReplyKeyboardMarkup(
    [["🔄 شروع مجدد"]],
    resize_keyboard=True
)

# سرور کوچک برای Render
server = Flask(__name__)


@server.route("/")
def home():
    return "Downloader Bot is Running!"


def run_server():
    port = int(os.environ.get("PORT", 10000))
    server.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# بررسی لینک
def valid_link(url):
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""

        allowed = (
            "youtube.com",
            "youtu.be",
            "instagram.com",
            "tiktok.com",
        )

        return (
            parsed.scheme in ("http", "https")
            and any(
                domain == item or domain.endswith("." + item)
                for item in allowed
            )
        )

    except Exception:
        return False


# دانلود ویدیو
def download_video(url, user_id):
    user_folder = os.path.join(DOWNLOAD_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)

    # پاک کردن فایل‌های قبلی همین کاربر
    for file in glob.glob(os.path.join(user_folder, "*")):
        if os.path.isfile(file):
            os.remove(file)

    options = {
        "format": "best[ext=mp4][filesize<=52428800]/best[filesize<=52428800]",
        "outtmpl": os.path.join(
            user_folder,
            "%(title).80s-%(id)s.%(ext)s"
        ),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE,
        "socket_timeout": 30,
        "retries": 2,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    files = glob.glob(os.path.join(user_folder, "*"))

    if not files:
        raise Exception("فایل دانلود نشد.")

    file_path = max(files, key=os.path.getmtime)

    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        os.remove(file_path)
        raise Exception("حجم فایل بیشتر از ۵۰ مگابایت است.")

    return file_path


# شروع ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("authorized"):
        await update.message.reply_text(
            "سلام! لینک ویدیوت رو ارسال کن.",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            "🔐 برای استفاده از ربات، رمز ورود را ارسال کن."
        )


# دریافت لینک و رمز
async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message
    text = message.text.strip()

    # شروع مجدد
    if text == "🔄 شروع مجدد":
        if context.user_data.get("authorized"):
            await message.reply_text(
                "🔄 ربات آماده است. لینک جدید را ارسال کن.",
                reply_markup=keyboard
            )
        else:
            await message.reply_text("🔐 ابتدا رمز ورود را ارسال کن.")
        return

    # بررسی رمز
    if not context.user_data.get("authorized"):
        import hmac

        if hmac.compare_digest(text, PASSWORD):
            context.user_data["authorized"] = True

            await message.reply_text(
                "✅ رمز صحیح است!\n\n"
                "حالا لینک ویدیوی موردنظرت را ارسال کن.",
                reply_markup=keyboard
            )
        else:
            await message.reply_text(
                "❌ رمز اشتباه است. دوباره تلاش کن."
            )
        return

    # بررسی لینک
    if not valid_link(text):
        await message.reply_text(
            "❌ لینک معتبر نیست.\n"
            "لطفاً لینک عمومی یوتیوب، اینستاگرام یا تیک‌تاک را بفرست."
        )
        return

    status = await message.reply_text(
        "⏳ در حال بررسی و دانلود ویدیو..."
    )

    file_path = None

    try:
        file_path = await asyncio.to_thread(
            download_video,
            text,
            update.effective_user.id
        )

        await status.edit_text("📤 دانلود انجام شد؛ در حال ارسال...")

        with open(file_path, "rb") as video:
            if file_path.lower().endswith(".mp4"):
                await message.reply_video(
                    video=video,
                    caption="✅ دانلود با موفقیت انجام شد."
                )
            else:
                await message.reply_document(
                    document=video,
                    caption="✅ فایل آماده است."
                )

        await status.delete()

    except Exception as error:
        logging.exception("Download error")

        await status.edit_text(
            "❌ دانلود انجام نشد.\n\n"
            "ممکن است لینک در دسترس نباشد، سایت از دانلود پشتیبانی نکند "
            "یا حجم فایل بیشتر از حد مجاز باشد."
        )

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN در فایل .env تنظیم نشده است.")

    threading.Thread(
        target=run_server,
        daemon=True
    ).start()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("Bot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
