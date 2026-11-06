import asyncio
import logging
import os
import threading
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import yt_dlp
from httpx import Timeout

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ساخت وب‌سرور سبک برای تایید پورت در Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# افزایش سقف حجم مجاز به 750 مگابایت
MAX_FILE_SIZE_MB = 750
CORRECT_PASSWORD = "KLi12"

# ذخیره وضعیت کاربران تایید شده
authorized_users = set()

# دکمه شیشه‌ای / متنی کیبورد برای ریستارت
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

def run_download(url, output_template):
    """دانلود تمام پسوندها و کیفیت‌ها با yt-dlp و ترکیب خودکار با FFmpeg به MP4"""
    # مسیر FFmpeg: در ویندوز مسیر دستی، در لینوکس سرور مسیر سیستمی
    ffmpeg_path = r'C:\ffmpeg\ffmpeg-9.0.2-essentials_build\bin' if os.name == 'nt' else None

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': output_template,
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
        'noplaylist': True,
        'socket_timeout': 120,
        'retries': 20,
        'fragment_retries': 20,
        # تنظیم کلاینت‌ها برای جلوگیری از ارور Sign in یوتیوب 👇
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    if ffmpeg_path:
        ydl_opts['ffmpeg_location'] = ffmpeg_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # اگر کاربر دستور /start داد یا دکمه ریستارت رو زد
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
            user_name = update.effective_user.first_name or "عمو جواد"
            await update.message.reply_text(
                f"سلام {user_name} گل! 🤖🔥\n\n"
                f"لینک ویدیو رو بفرست تا با بالاترین کیفیت برات دانلود و ارسال کنم!\n"
                f"📌 حداکثر حجم مجاز: تا {MAX_FILE_SIZE_MB} مگابایت.\n\n"
                f"💡 برای ریستارت، می‌تونی از دکمه زیر استفاده کنی.",
                reply_markup=restart_keyboard
            )
        else:
            await update.message.reply_text(
                "رمز عبور را درست وارد نمایید"
            )
        return

    url = text
    if not url.startswith("http"):
        await update.message.reply_text("❌ لطفاً یک لینک معتبر بفرست داداشم!")
        return

    status_msg = await update.message.reply_text(
        "📥 در حال دانلود ویدیو و ترکیب با FFmpeg... صبور باش داداش 🙏\n"
        "بدلیل حجم زیاد ویدیو ممکن است کمی زمان ببرد..."
    )

    output_filename = f"video_{user_id}.mp4"
    
    if os.path.exists(output_filename):
        try:
            os.remove(output_filename)
        except:
            pass

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_download, url, output_filename)

        actual_file = output_filename
        if not os.path.exists(actual_file):
            for f in os.listdir('.'):
                if f.startswith(f"video_{user_id}"):
                    actual_file = f
                    break

        if not os.path.exists(actual_file):
            await status_msg.edit_text("❌ خطا: فایل دانلود شده پیدا نشد!")
            return

        file_size_mb = os.path.getsize(actual_file) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(f"❌ حجم ویدیو ({file_size_mb:.1f} مگابایت) بیشتر از حد مجاز ({MAX_FILE_SIZE_MB} مگابایت) است!")
            os.remove(actual_file)
            return

        await status_msg.edit_text("📤 در حال آپلود ویدیو به تلگرام (کمی صبر کنید)...")
        
        with open(actual_file, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                read_timeout=300,
                write_timeout=300,
                connect_timeout=60
            )

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error downloading: {e}")
        try:
            await status_msg.edit_text(f"❌ خطا در دانلود یا آپلود:\n`{str(e)}`", parse_mode="Markdown")
        except:
            pass
    finally:
        for f in os.listdir('.'):
            if f.startswith(f"video_{user_id}") and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

def main():
    if not BOT_TOKEN:
        print("❌ توکن یافت نشد!")
        return

    # اجرای وب‌سرور فلاسک در پس‌زمینه برای باز کردن پورت مورد نیاز رندر
    threading.Thread(target=run_web_server, daemon=True).start()

    application = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).read_timeout(300).write_timeout(300).connect_timeout(60).pool_timeout(60).build()

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 ربات با موفقیت و دکمه ریستارت روشن شد...")
    application.run_polling()

if __name__ == '__main__':
    main()

