import hmac
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlsplit

import requests
import yt_dlp
from flask import Flask, abort, jsonify, request
from requests_toolbelt.multipart.encoder import MultipartEncoder


BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

# فقط وقتی Bot API Server شخصی داری این متغیر را تنظیم کن.
LOCAL_API_URL = os.getenv("BOT_API_BASE_URL", "").rstrip("/")
API_BASE_URL = LOCAL_API_URL or "https://api.telegram.org"

MAX_BYTES = 480_000_000 if LOCAL_API_URL else 49_000_000
MAX_MB = 480 if LOCAL_API_URL else 49

ALLOWED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "tiktok.com",
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

executor = ThreadPoolExecutor(max_workers=1)
job_slots = BoundedSemaphore(2)  # یک دانلود فعال، یک درخواست در صف
logging.basicConfig(level=logging.INFO)


def telegram_url(method):
    return f"{API_BASE_URL}/bot{BOT_TOKEN}/{method}"


def send_text(chat_id, text):
    response = requests.post(
        telegram_url("sendMessage"),
        data={"chat_id": str(chat_id), "text": text},
        timeout=(10, 30),
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram error"))


def send_video(chat_id, file_path):
    # MultipartEncoder فایل بزرگ را بدون بارگذاری کامل در RAM ارسال می‌کند.
    with file_path.open("rb") as video_file:
        body = MultipartEncoder(
            fields={
                "chat_id": str(chat_id),
                "supports_streaming": "true",
                "video": (file_path.name, video_file, "video/mp4"),
            }
        )
        response = requests.post(
            telegram_url("sendVideo"),
            data=body,
            headers={"Content-Type": body.content_type},
            timeout=(15, 900),
        )

    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram error"))


def is_supported_url(text):
    try:
        parsed = urlsplit(text)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and not parsed.username
            and any(
                host == domain or host.endswith("." + domain)
                for domain in ALLOWED_DOMAINS
            )
        )
    except ValueError:
        return False


def estimated_size(fmt, duration):
    for key in ("filesize", "filesize_approx"):
        value = fmt.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)

    bitrate = fmt.get("tbr")
    if bitrate and duration:
        return int(bitrate * 125 * duration)  # kb/s -> bytes

    return None


def resolution(fmt):
    width = fmt.get("width")
    height = fmt.get("height")
    if width and height:
        return min(width, height)  # برای ویدیوهای عمودی هم درست است
    return height or width or 0


def choose_format(info):
    formats = info.get("formats") or [info]
    duration = info.get("duration")

    def has_video(fmt):
        return fmt.get("vcodec") not in (None, "none")

    def has_audio(fmt):
        return fmt.get("acodec") not in (None, "none")

    progressive = [
        f for f in formats
        if f.get("ext") == "mp4"
        and f.get("format_id")
        and has_video(f)
        and has_audio(f)
    ]
    video_only = [
        f for f in formats
        if f.get("ext") == "mp4"
        and f.get("format_id")
        and has_video(f)
        and not has_audio(f)
    ]
    audio_only = [
        f for f in formats
        if f.get("ext") == "m4a"
        and f.get("format_id")
        and has_audio(f)
        and not has_video(f)
    ]

    candidates = []

    for video in progressive:
        candidates.append((
            video["format_id"],
            estimated_size(video, duration),
            resolution(video),
        ))

    for video in video_only:
        for audio in audio_only:
            video_size = estimated_size(video, duration)
            audio_size = estimated_size(audio, duration)
            combined = (
                video_size + audio_size
                if video_size is not None and audio_size is not None
                else None
            )
            candidates.append((
                f'{video["format_id"]}+{audio["format_id"]}',
                combined,
                resolution(video),
            ))

    # برای خطای تخمین حجم و ادغام صدا/تصویر کمی حاشیه می‌گذاریم.
    budget = int(MAX_BYTES * 0.93)
    fitting = [c for c in candidates if c[1] is not None and c[1] <= budget]

    if fitting:
        return max(fitting, key=lambda c: (c[2], c[1]))[0]

    # وقتی سایت حجم را اعلام نمی‌کند، کم‌حجم‌ترین کیفیت احتمالی
    # را امتحان می‌کنیم؛ کنترل نهایی حجم همچنان برقرار است.
    unknown = [c for c in candidates if c[1] is None]
    if unknown:
        return min(unknown, key=lambda c: c[2])[0]

    raise ValueError(f"کیفیت MP4 مناسبی زیر سقف {MAX_MB} مگابایت پیدا نشد.")


def download_video(url, folder):
    def progress_hook(status):
        if (
            status.get("status") == "downloading"
            and (status.get("downloaded_bytes") or 0) > MAX_BYTES
        ):
            raise ValueError(f"حجم دانلود از {MAX_MB} مگابایت گذشت.")

    options = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_BYTES,
        "progress_hooks": [progress_hook],
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info or info.get("entries"):
        raise ValueError("لطفاً لینک یک ویدیوی عمومی بفرست، نه پلی‌لیست.")

    options["format"] = choose_format(info)

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    videos = [p for p in folder.glob("*.mp4") if p.is_file()]
    if not videos:
        raise ValueError("فایل MP4 قابل ارسال ساخته نشد.")

    video = max(videos, key=lambda p: p.stat().st_size)
    if video.stat().st_size > MAX_BYTES:
        raise ValueError(f"حجم نهایی ویدیو بیشتر از {MAX_MB} مگابایت شد.")

    return video


def process_message(chat_id, text):
    try:
        if text.startswith("/start"):
            send_text(
                chat_id,
                f"سلام! لینک ویدیوی عمومی یوتیوب، اینستاگرام یا تیک‌تاک "
                f"را بفرست. سقف ارسال فعلی: {MAX_MB} مگابایت.",
            )
            return

        if not is_supported_url(text):
            send_text(
                chat_id,
                "لطفاً لینک HTTPS ویدیوی عمومی از یوتیوب، اینستاگرام "
                "یا تیک‌تاک بفرست.",
            )
            return

        send_text(chat_id, "⏳ لینک دریافت شد؛ دارم ویدیو را آماده می‌کنم...")

        with tempfile.TemporaryDirectory(prefix="video_bot_") as temp:
            video = download_video(text, Path(temp))
            send_video(chat_id, video)

    except ValueError as exc:
        send_text(chat_id, f"❌ {exc}")
    except Exception:
        app.logger.exception("Video processing failed")
        try:
            send_text(
                chat_id,
                "❌ دانلود یا ارسال انجام نشد. ممکن است ویدیو خصوصی باشد، "
                "سایت دسترسی را محدود کرده باشد یا حجم آن زیاد باشد.",
            )
        except Exception:
            app.logger.exception("Could not report error to user")
    finally:
        job_slots.release()


@app.get("/")
def health():
    return "Bot is running", 200


@app.post("/webhook")
def webhook():
    received_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token", ""
    )
    if not hmac.compare_digest(received_secret, WEBHOOK_SECRET):
        abort(403)

    payload = request.get_json(silent=True) or {}
    message = payload.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if chat_id and text:
        if not job_slots.acquire(blocking=False):
            return jsonify(ok=False, error="busy"), 503

        try:
            executor.submit(process_message, chat_id, text)
        except Exception:
            job_slots.release()
            raise

    return jsonify(ok=True), 200
