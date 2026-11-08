
import os
import re
import asyncio
import logging
import tempfile
import threading

from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from flask import Flask, jsonify
from dotenv import load_dotenv

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -----------------------
# Configuration
# -----------------------

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

MAX_SIZE = 49 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------
# Flask Server
# -----------------------

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "bot": "Video Downloader Bot"
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


def run_flask():
    app.run(
        host="0.0.0.0",
        port=PORT,
        use_reloader=False
    )


# -----------------------
# Supported Websites
# -----------------------

ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",
    "aparat.com",
    "www.aparat.com",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}


def check_url(text):

    match = re.search(r"https?://\S+", text)

    if not match:
        return None

    url = match.group(0).rstrip(".,!?)]}>")

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in ("http", "https"):
        return None

    if host not in ALLOWED_HOSTS:
        return None

    return url


# -----------------------
# Download Function
# -----------------------

def download_video(url, folder):

    output = str(
        Path(folder) / "%(title).70s-%(id)s.%(ext)s"
    )

    options = {
        "outtmpl": output,
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "max_filesize": MAX_SIZE,
        "socket_timeout": 25,
        "retries": 2,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(url, download=True)

        requested = info.get("requested_downloads") or []

        files = [
            Path(item["filepath"])
            for item in requested
            if item.get("filepath")
            and Path(item["filepath"]).is_file()
        ]

        if not files:
            files = [
                p for p in Path(folder).iterdir()
                if p.is_file()
            ]

        if not files:
            raise Exception("Video file not found")

        files.sort(
            key=lambda p: (
                p.suffix.lower() != ".mp4",
                -p.stat().st_size
            )
        )

        video = files[0]

        if video.stat().st_size > MAX_SIZE:
            raise ValueError("Video is too large")

        return video


# -----------------------
# Telegram Commands
# -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "سلام 👋\n\n"
        "به ربات دانلود ویدیو خوش اومدی!\n\n"
        "لینک عمومی ویدیوت رو بفرست:\n\n"
        "YouTube ✅\n"
        "Aparat ✅\n"
        "Instagram ✅\n"
        "TikTok ✅"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "برای دانلود ویدیو فقط لینک عمومی رو ارسال کن."
    )


# -----------------------
# Handle Links
# -----------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message

    url = check_url(message.text or "")

    if not url:

        await message.reply_text(
            "❌ لطفاً یک لینک معتبر ارسال کن."
        )

        return

    status = await message.reply_text(
        "⏳ در حال آماده‌سازی ویدیو..."
    )

    try:

        with tempfile.TemporaryDirectory() as folder:

            video_path = await asyncio.to_thread(
                download_video,
                url,
                folder
            )

            await status.edit_text(
                "📤 در حال ارسال ویدیو..."
            )

            await context.bot.send_chat_action(
                chat_id=message.chat_id,
                action=ChatAction.UPLOAD_VIDEO
            )

            with open(video_path, "rb") as video:

                await message.reply_video(
                    video=video,
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30
                )

        await status.delete()

    except ValueError as error:

        await status.edit_text(f"❌ {error}")

    except Exception:

        logger.exception("Download error")

        await status.edit_text(
            "❌ دانلود انجام نشد.\n"
            "لینک ممکن است خصوصی یا غیرقابل دسترس باشد."
        )


# -----------------------
# Start Telegram Bot
# -----------------------

async def start_bot():

    telegram_app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    telegram_app.add_handler(
        CommandHandler("start", start)
    )

    telegram_app.add_handler(
        CommandHandler("help", help_command)
    )

    telegram_app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()

    logger.info("Telegram bot started")

    return telegram_app


if __name__ == "__main__":

    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    # Start Flask in background
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    # Start Telegram bot
    asyncio.run(
        start_bot()
    )
