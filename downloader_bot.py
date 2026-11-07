import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import yt_dlp
from flask import Flask, request

# بارگذاری توکن از فایل .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# تنظیمات لاگینگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# سقف حجم ویدیو (۶۵۰ مگابایت)
MAX_FILE_SIZE_MB = 650
MILESTONES = (10, 25, 37, 46, 55, 67, 77, 84, 99, 100)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "عمو جواد"
    welcome_text = (
        f"سلام {user_name} عزیز! 🚀🤖\n\n"
        "لینک ویدیوی مورد نظرت (یوتیوب، شورتس، اینستاگرام، تیک‌تاک و...) رو بفرست "
        "تا با درصدشمار پله‌پله برات دانلودش کنم و بفرستم!\n\n"
        f"📌 نکته: حداکثر حجم پشتیبانی شده تا {MAX_FILE_SIZE_MB} مگابایت تنظیم شده است."
    )
    await update.message.reply_text(welcome_text)

def download_video_sync(target_url, status_msg, loop):
    output_template = "downloaded_video.%(ext)s"
    reported = set()

    # پاک کردن فایل‌های موقت قبلی برای جلوگیری از ارورهای تداخل
    for ext in ['mp4', 'mkv', 'webm', 'mov', 'm4v', 'avi', 'part', 'ytdl']:
        old_file = f"downloaded_video.{ext}"
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except:
                pass

    def report_progress(text: str):
        future = asyncio.run_coroutine_threadsafe(
            status_msg.edit_text(text),
            loop,
        )
        try:
            future.result(timeout=2)
        except Exception:
            pass

    def progress_hook(data):
        if data.get("status") != "downloading":
            return

        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        downloaded = data.get("downloaded_bytes", 0)

        if not total:
            return

        percent = min(99, int(downloaded * 100 / total))

        for milestone in MILESTONES:
            if percent >= milestone and milestone not in reported:
                reported.add(milestone)
                report_progress(f"⏳ {milestone}٪ از ویدیو دانلود شد...")
                break

    # تنظیمات کاملاً امن و سازگار با فرمت‌های مختلف بدون نیاز به ابزار جانبی
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'continuedl': False,
        'progress_hooks': [progress_hook],
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])
    except Exception as e:
        logging.warning(f"Primary download warning: {e}")

    filename = None
    for ext in ['mp4', 'mkv', 'webm', 'mov', 'm4v', 'avi']:
        test_name = f"downloaded_video.{ext}"
        if os.path.exists(test_name):
            filename = test_name
            break
    
    if not filename:
        files = [f for f in os.listdir('.') if f.startswith('downloaded_video') and not f.endswith('.part') and not f.endswith('.ytdl')]
        if files:
            filename = files[0]

    # حالت پشتیبان (Fallback) برای لینک‌های بسیار سخت‌گیر
    if not filename or not os.path.exists(filename):
        fallback_opts = {
            'format': 'b',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'continuedl': False,
            'progress_hooks': [progress_hook],
        }
        try:
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                ydl.download([target_url])
        except Exception:
            pass
            
        for ext in ['mp4', 'mkv', 'webm', 'mov', 'm4v', 'avi']:
            test_name = f"downloaded_video.{ext}"
            if os.path.exists(test_name):
                filename = test_name
                break

    if not filename or not os.path.exists(filename):
        raise ValueError("متأسفانه ویدیو دانلود نشد یا فرمت آن توسط پلتفرم محدود شده است.")

    filesize_bytes = os.path.getsize(filename)
    filesize_mb = filesize_bytes / (1024 * 1024)
    
    if filesize_mb > MAX_FILE_SIZE_MB:
        if os.path.exists(filename):
            os.remove(filename)
        raise ValueError(f"حجم ویدیو ({filesize_mb:.1f} مگابایت) بیشتر از سقف مجاز {MAX_FILE_SIZE_MB} مگابایت است!")
        
    return filename, filesize_mb

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ لطفاً یک لینک معتبر (شروع شونده با http یا https) بفرستید.")
        return

    status_msg = await update.message.reply_text("📥 در حال شروع دانلود ویدیو...")
    loop = asyncio.get_running_loop()

    filename = None
    try:
        filename, filesize_mb = await asyncio.to_thread(
            download_video_sync, url, status_msg, loop
        )

        await status_msg.edit_text(f"📤 در حال آپلود ویدیو به تلگرام (حجم: {filesize_mb:.1f} مگابایت)...")

        caption_text = (
            f"📦 **حجم ویدیو:** {filesize_mb:.1f} مگابایت\n\n"
            f"✅ با موفقیت دانلود و ارسال شد!"
        )

        with open(filename, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=caption_text,
                parse_mode="Markdown",
                read_timeout=300,
                write_timeout=300,
            )
            
        await status_msg.delete()

    except Exception as e:
        error_str = str(e)
        logging.error(f"Error downloading: {error_str}")
        try:
            await status_msg.edit_text(f"❌ خطایی رخ داد:\n{error_str[:300]}")
        except Exception:
            pass

    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass

def main():
    if not BOT_TOKEN:
        print("❌ توکن ربات پیدا نشد! لطفاً فایل .env را بررسی کنید.")
        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Application started successfully! Bot is running without errors...")
    app.run_polling()

if __name__ == '__main__':
    main()