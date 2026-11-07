
import os
import re
import glob
import asyncio
import logging
import threading
import hmac

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


# =========================
# تنظیمات اولیه
# =========================

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PASSWORD = os.getenv("BOT_PASSWORD", "KLi4874")

MAX_DOWNLOAD_SIZE = 200 * 1024 * 1024

MAX_TELEGRAM_SIZE = 50 * 1024 * 1024

DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


keyboard = ReplyKeyboardMarkup(
    [["🔄 شروع مجدد"]],
    resize_keyboard=True
)


# =========================
# سرور Render
# =========================

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


# =========================
# بررسی لینک
# =========================

def valid_link(url):

    try:

        parsed = urlparse(url)

        domain = parsed.hostname or ""

        allowed = (
            "youtube.com",
            "youtu.be",
            "instagram.com",
            "tiktok.com",
            "aparat.com",
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


# =========================
# دانلود ویدیو
# =========================

def download_video(url, user_id):

    user_folder = os.path.join(
        DOWNLOAD_DIR,
        str(user_id)
    )

    os.makedirs(user_folder, exist_ok=True)

    # پاک کردن فایل های قبلی کاربر

    for file in glob.glob(
        os.path.join(user_folder, "*")
    ):

        if os.path.isfile(file):

            try:
                os.remove(file)

            except OSError:
                pass


    options = {

        "format": "best[ext=mp4]/best",

        "outtmpl": os.path.join(
            user_folder,
            "%(title).80s-%(id)s.%(ext)s"
        ),

        "noplaylist": True,

        "quiet": True,

        "no_warnings": True,

        "max_filesize": MAX_DOWNLOAD_SIZE,

        "socket_timeout": 30,

        "retries": 3,

        "extractor_retries": 2,

        "fragment_retries": 3,

        "sleep_interval_requests": 2,

        "overwrites": True,

    }


    with yt_dlp.YoutubeDL(options) as ydl:

        ydl.download([url])


    files = glob.glob(
        os.path.join(user_folder, "*")
    )

    files = [
        file for file in files
        if os.path.isfile(file)
    ]

    if not files:

        raise Exception("فایل دانلود نشد.")


    file_path = max(
        files,
        key=os.path.getmtime
    )


    file_size = os.path.getsize(file_path)


    if file_size > MAX_DOWNLOAD_SIZE:

        os.remove(file_path)

        raise Exception(
            "حجم ویدیو بیشتر از ۲۰۰ مگابایت است."
        )


    return file_path


# =========================
# شروع ربات
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if context.user_data.get("authorized"):

        await update.message.reply_text(
            "سلام! 👋\n\n"
            "لینک ویدیوت رو ارسال کن.",
            reply_markup=keyboard
        )

    else:

        await update.message.reply_text(
            "🔐 برای استفاده از ربات، رمز ورود را ارسال کن."
        )


# =========================
# دریافت پیام
# =========================

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
                "🔄 ربات آماده است.\n"
                "لینک جدید را ارسال کن.",
                reply_markup=keyboard
            )

        else:

            await message.reply_text(
                "🔐 ابتدا رمز ورود را ارسال کن."
            )

        return


    # بررسی رمز

    if not context.user_data.get("authorized"):

        if hmac.compare_digest(text, PASSWORD):

            context.user_data["authorized"] = True

            await message.reply_text(
                "✅ رمز صحیح است!\n\n"
                "حالا لینک ویدیوی موردنظرت را ارسال کن.",
                reply_markup=keyboard
            )

        else:

            await message.reply_text(
                "❌ رمز اشتباه است.\n"
                "دوباره تلاش کن."
            )

        return


    # بررسی لینک

    if not valid_link(text):

        await message.reply_text(
            "❌ لینک معتبر نیست.\n\n"
            "لطفاً لینک عمومی یکی از سایت‌های زیر را بفرست:\n\n"
            "YouTube\n"
            "Instagram\n"
            "TikTok\n"
            "Aparat"
        )

        return


    status = await message.reply_text(
        "⏳ در حال بررسی و دانلود ویدیو...\n\n"
        "لطفاً صبر کن."
    )


    file_path = None


    try:

        # دانلود بدون متوقف کردن ربات

        file_path = await asyncio.to_thread(
            download_video,
            text,
            update.effective_user.id
        )


        # بررسی حجم قابل ارسال در تلگرام

        file_size = os.path.getsize(file_path)


        if file_size > MAX_TELEGRAM_SIZE:

            await status.edit_text(
                "⚠️ دانلود انجام شد، اما ارسال ممکن نیست.\n\n"
                f"حجم فایل: {file_size / (1024 * 1024):.1f} MB\n"
                "محدودیت ارسال Bot API معمولی تلگرام ۵۰ مگابایت است."
            )

            return


        await status.edit_text(
            "📤 دانلود با موفقیت انجام شد!\n"
            "در حال ارسال ویدیو..."
        )


        # ارسال ویدیو

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


        error_text = str(error).lower()


        if "429" in error_text or "too many requests" in error_text:

            user_error = (
                "⚠️ سایت موقتاً درخواست‌های دانلود را محدود کرده است.\n\n"
                "چند دقیقه بعد دوباره امتحان کن."
            )

        elif "max-filesize" in error_text or "maximum file size" in error_text:

            user_error = (
                "❌ حجم ویدیو بیشتر از محدودیت ۲۰۰ مگابایت است."
            )

        else:

            user_error = (
                "❌ دانلود انجام نشد.\n\n"
                "ممکن است لینک در دسترس نباشد، "
                "ویدیو خصوصی باشد یا سایت اجازه دانلود ندهد."
            )


        try:

            await status.edit_text(user_error)

        except Exception:

            await message.reply_text(user_error)


    finally:

        # حذف فایل موقت

        if file_path and os.path.exists(file_path):

            try:

                os.remove(file_path)

            except OSError:

                logging.warning(
                    "Could not remove temporary file."
                )


# =========================
# مدیریت خطاها
# =========================

async def error_handler(update, context):

    logger.error(
        "Telegram application error:",
        exc_info=context.error
    )


# =========================
# اجرای اصلی
# =========================

def main():

    if not TOKEN:

        raise ValueError(
            "BOT_TOKEN در Environment تنظیم نشده است."
        )


    # اجرای سرور Render

    threading.Thread(
        target=run_server,
        daemon=True
    ).start()


    # ساخت ربات

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )


    # دستورات

    application.add_handler(
        CommandHandler("start", start)
    )


    # دریافت پیام ها

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )


    application.add_error_handler(error_handler)


    print("Bot is running...")


    application.run_polling()


if __name__ == "__main__":

    main()

