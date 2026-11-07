import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import yt_dlp

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

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"سلام {user_name} عزیز! 🚀\n\n"
        "لینک ویدیوی مورد نظرت رو بفرست تا مستقیم و بدون معطلی برات دانلودش کنم و بفرستم!\n\n"
        f"📌 نکته: حداکثر حجم پشتیبانی شده تا {MAX_FILE_SIZE_MB} مگابایت تنظیم شده است."
    )
    await update.message.reply_text(welcome_text)

def download_video_sync(target_url):
    # یک نام فایل رندوم یا ثابت تمیز برای دانلود
    output_template = "downloaded_video.%(ext)s"
    
    ydl_opts = {
        'format': 'best/bestvideo+bestaudio',
        'outtmpl': output_template,
        'noplaylist': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
    }
    
    # پاک کردن فایل‌های موقت قبلی اگر مونده باشن
    for ext in ['mp4', 'mkv', 'webm', 'mov', 'm4v', 'avi', 'part']:
        old_file = f"downloaded_video.{ext}"
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except:
                pass

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # مستقیماً دانلود را انجام میدهیم و از try_getting info صرف نظر می‌کنیم
        ydl.download([target_url])
        
    # پیدا کردن فایل دانلود شده با هر پسوندی
    filename = None
    for ext in ['mp4', 'mkv', 'webm', 'mov', 'm4v', 'avi']:
        test_name = f"downloaded_video.{ext}"
        if os.path.exists(test_name):
            filename = test_name
            break
    
    if not filename:
        files = [f for f in os.listdir('.') if f.startswith('downloaded_video') and not f.endswith('.part')]
        if files:
            filename = files.get() if hasattr(files, 'get') else files[0]

    if not filename or not os.path.exists(filename):
        raise ValueError("دانلود انجام شد اما فایل نهایی ویدیو پیدا نشد!")

    filesize_bytes = os.path.getsize(filename)
    filesize_mb = filesize_bytes / (1024 * 1024)
    
    if filesize_mb > MAX_FILE_SIZE_MB:
        if os.path.exists(filename):
            os.remove(filename)
        raise ValueError(f"حجم ویدیو ({filesize_mb:.1f} مگابایت) بیشتر از سقف مجاز {MAX_FILE_SIZE_MB} مگابایت است!")
        
    return filename, filesize_mb

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ لطفاً یک لینک معتبر (شروع شونده با http یا https) بفرستید.")
        return

    status_msg = await update.message.reply_text(
        "⏳ در حال دانلود ویدیو...\n\n"
        "⚠️ *توجه:* هرچه حجم ویدیو بالاتر باشد، ویدیو دیرتر دانلود می‌شود. لطفاً صبور باشید..."
    )

    filename = None
    try:
        filename, filesize_mb = await asyncio.to_thread(download_video_sync, url)

        await status_msg.edit_text("📤 دانلود انجام شد! در حال ارسال ویدیو به تلگرام...")

        caption_text = (
            f"📦 **حجم ویدیو:** {filesize_mb:.1f} مگابایت\n\n"
            f"✅ با موفقیت دانلود و ارسال شد!"
        )

        with open(filename, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=caption_text,
                parse_mode="Markdown"
            )
            
        await status_msg.delete()

    except Exception as e:
        error_str = str(e)
        logging.error(f"Error downloading: {error_str}")
        await status_msg.edit_text(f"❌ خطایی رخ داد:\n{error_str[:180]}")

    finally:
        # پاکسازی فایل موقت
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
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )

    app.add_handler(MessageHandler(filters.TEXT & filters.COMMAND & filters.Regex("^/start$"), start_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Application started successfully! Bot is running without errors...")
    app.run_polling()

if __name__ == '__main__':
    main()