import logging
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from yt_dlp import YoutubeDL

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("متغیر BOT_TOKEN تنظیم نشده است.")

API = f"https://api.telegram.org/bot{TOKEN}"
MAX_BYTES = 49 * 1024 * 1024  # کمی کمتر از سقف ۵۰ مگابایتی تلگرام

ALLOWED_DOMAINS = (
    "aparat.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "instagram.com",
)

logging.basicConfig(level=logging.INFO)


def telegram(method, *, timeout=60, **kwargs):
    response = requests.post(
        f"{API}/{method}",
        timeout=timeout,
        **kwargs,
    )
    response.raise_for_status()
    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(result.get("description", "خطای تلگرام"))

    return result["result"]


def say(chat_id, text):
    telegram("sendMessage", data={"chat_id": chat_id, "text": text})


def extract_allowed_url(text):
    match = re.search(r"https?://[^\s<>]+", text)
    if not match:
        return None

    url = match.group(0).rstrip(".,!?)،؛]}")
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in ("http", "https"):
        return None

    if parsed.username or parsed.password:
        return None

    if not any(
        host == domain or host.endswith("." + domain)
        for domain in ALLOWED_DOMAINS
    ):
        return None

    return url


def download_video(url, directory):
    def check_size(progress):
        if progress.get("status") == "downloading":
            downloaded = progress.get("downloaded_bytes", 0)
            if downloaded > MAX_BYTES:
                raise ValueError("حجم ویدیو از سقف ارسال بات بیشتر است.")

    options = {
        "format": "b[height<=480]/bv*[height<=480]+ba/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "outtmpl": str(directory / "%(id)s.%(ext)s"),
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "progress_hooks": [check_size],
    }

    with YoutubeDL(options) as downloader:
        downloader.download([url])

    files = [
        path for path in directory.iterdir()
        if path.is_file()
        and not path.name.endswith((".part", ".ytdl"))
    ]

    if not files:
        raise RuntimeError("فایل ویدیویی دریافت نشد.")

    video = max(files, key=lambda path: path.stat().st_size)

    if video.stat().st_size > MAX_BYTES:
        raise ValueError("حجم ویدیو از سقف ارسال بات بیشتر است.")

    return video


def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()

    if not chat_id:
        return

    if text.startswith("/start"):
        say(
            chat_id,
            "سلام! لینک ویدیوی عمومی آپارات، یوتیوب، تیک‌تاک "
            "یا اینستاگرام را بفرست تا دانلودش کنم."
        )
        return

    url = extract_allowed_url(text)
    if not url:
        say(chat_id, "یک لینک معتبر از آپارات، یوتیوب، تیک‌تاک یا اینستاگرام بفرست.")
        return

    say(chat_id, "دارم ویدیو را دانلود می‌کنم؛ کمی صبر کن…")

    try:
        with tempfile.TemporaryDirectory() as temp:
            video = download_video(url, Path(temp))
            method = "sendVideo" if video.suffix.lower() == ".mp4" else "sendDocument"
            field = "video" if method == "sendVideo" else "document"

            with video.open("rb") as file:
                telegram(
                    method,
                    timeout=180,
                    data={"chat_id": chat_id},
                    files={field: (video.name, file)},
                )

    except ValueError as error:
        say(chat_id, str(error))
    except Exception:
        logging.exception("Download or upload failed")
        say(
            chat_id,
            "دانلود یا ارسال این لینک ممکن نشد. اگر محتوا خصوصی است، "
            "به ورود نیاز دارد یا سایت روش دسترسی‌اش را تغییر داده، "
            "ممکن است این بات نتواند آن را دریافت کند."
        )


def main():
    # اگر قبلاً برای بات webhook تنظیم شده باشد، polling کار نمی‌کند.
    telegram("deleteWebhook", data={"drop_pending_updates": False})

    offset = None
    logging.info("Bot is running")

    while True:
        try:
            updates = telegram(
                "getUpdates",
                timeout=35,
                json={
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": ["message"],
                },
            )

            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])

        except requests.RequestException:
            logging.exception("Telegram connection error")
            time.sleep(5)
        except Exception:
            logging.exception("Unexpected bot error")
            time.sleep(5)


if __name__ == "__main__":
    main()
