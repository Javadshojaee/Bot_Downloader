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

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# وب‌سرور سبک Flask برای زنده نگه داشتن سرویس روی Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

MAX_FILE_SIZE_MB = 750
CORRECT_PASSWORD = "KLi123"

# ذخیره شناسه کاربران احراز هویت شده
authorized_users = set()

# دکمه ثابت ریستارت
restart_keyboard = ReplyKeyboardMarkup(
    [["🔄 شروع مجدد / خروج"]],
    resize_keyboard=True
)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in authorized_users:
        authorized_users.remove(user_id)
        
    await update.message.reply_text(
        "سلام! 🤖\n\nلطفاً رمز عبور را وارد نمایید:",
        reply_markup=ReplyKeyboardRemove()
    )

def run_download(url, user_id):
    """تابع دانلود با yt-dlp بدون نیاز به کوکی مرورگر (سازگار با هاست ابری و لوکال)"""
    ffmpeg_path = r'C:\ffmpeg\ffmpeg-9.0.2-essentials_build\bin' if os.name == 'nt' else None

    ydl_opts = {
        'outtmpl': f'dl_{user_id}.%(ext)s',
        'format': 'bestvideo*+bestaudio/bestvideo+bestaudio/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
        'noplaylist': True,
        'socket_timeout': 60,
        'retries': 20,
        'fragment_retries': 20,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
            }
        },
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'quiet': False,
        'no_warnings': False,
    }

    if ffmpeg_path and os.path.exists(ffmpeg_path):
        ydl_opts['ffmpeg_location'] = ffmpeg_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # مدیریت دکمه خروج یا دستور start
    if text == "/start" or text == "🔄 شروع مجدد / خروج":
        if user_id in authorized_users:
            authorized_users.remove(user_id)
        await update.message.reply_text(
            "🔄 ربات ریست شد!\n\nلطفاً رمز عبور را وارد نمایید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # بررسی رمز عبور
    if user_id not in authorized_users:
        if text == CORRECT_PASSWORD:
            authorized_users.add(user_id)
            await update.message.reply_text(
                f"سلام عمو جواد! 🤖🔥\n\n"
                f"لینک ویدیو (یوتیوب، اینستاگرام، آپارات، تیک‌تاک و...) رو بفرست تا با بالاترین کیفیت برات دانلود کنم!\n"
                f"📌 سقف حجم مجاز: تا {MAX_FILE_SIZE_MB} مگابایت.",
                reply_markup=restart_keyboard
            )
        else:
            await update.message.reply_text("رمز عبور اشتباه است. لطفاً رمز عبور را درست وارد نمایید:")
        return

    url = text
    if not url.startswith("http://") and not url.startswith("https://"):
        await update.message.reply_text("❌ لطفاً یک لینک اینترنتی معتبر بفرست!")
        return

    # پاکسازی فایل‌های باقی‌مانده احتمالی قبلی
    for old_file in glob.glob(f"dl_{user_id}.*"):
        try:
            os.remove(old_file)
        except:
            pass

    status_msg = await update.message.reply_text(
        "📥 در حال دانلود و آماده‌سازی ویدیو... لطفاً صبور باش عمو جان 🙏"
    )

    try:
        # اجرای دانلود در ترد جداگانه بدون بلاک کردن ربات
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_download, url, user_id)

        # پیدا کردن فایل خروجی با هر پسوندی که تولید شده (mp4, mkv, webm و غیره)
        matching_files = [f for f in glob.glob(f"dl_{user_id}.*") if not f.endswith('.part') and not f.endswith('.ytdl')]
        
        if not matching_files:
            await status_msg.edit_text("❌ خطا: فایل دانلود شده پیدا نشد یا لینک پشتیبانی نمی‌شود!")
            return

        downloaded_file = matching_files[0]
        file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)

        if file_size_mb > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(f"❌ حجم ویدیو ({file_size_mb:.1f} مگابایت) بیشتر از حد مجاز ({MAX_FILE_SIZE_MB} مگابایت) است!")
            os.remove(downloaded_file)
            return

        await status_msg.edit_text(f"📤 در حال ارسال ویدیو به تلگرام ({file_size_mb:.1f}MB)...")
        
        with open(downloaded_file, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                read_timeout=360,
                write_timeout=360,
                connect_timeout=60
            )

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error downloading: {e}")
        try:
            await status_msg.edit_text(f"❌ خطا در پردازش یا دانلود:\n{str(e)[:300]}")
        except:
            pass
    finally:
        # پاکسازی نهایی دیسک
        for leftover in glob.glob(f"dl_{user_id}.*"):
            try:
                os.remove(leftover)
            except:
                pass

def main():
    if not BOT_TOKEN:
        print("❌ متغیر BOT_TOKEN یافت نشد!")
        return

    # استارت سرور Flask در پس‌زمینه برای Render
    threading.Thread(target=run_web_server, daemon=True).start()

    # ساخت اپلیکیشن تلگرام با تایم‌اوت‌های استاندارد
    application = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).read_timeout(360).write_timeout(360).connect_timeout(60).pool_timeout(60).build()

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 ربات با موفقیت فعال شد...")
    application.run_polling()

if __name__ == '__main__':
    main()
