#!/usr/bin/env python3
import os
import logging
import sys
import threading
from pathlib import Path
import subprocess
import shutil
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

logger.info("Starting GIF Bot for Render...")

# Telegram bot libs (v13.15)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Bot config
BOT_TOKEN = os.getenv("BOT_TOKEN")
EXPORT_DIR = Path("temp_gifs")
EXPORT_DIR.mkdir(exist_ok=True)

# Limits
MAX_SIZE_MB = 3

def check_ffmpeg():
    """Check if FFmpeg is available."""
    return shutil.which("ffmpeg") is not None

def upload_to_catbox(file_path):
    """Upload GIF to catbox.moe"""
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": f},
                timeout=30
            )
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        logger.error(f"Catbox upload failed: {e}")
    return None

def upload_to_0x0(file_path):
    """Upload GIF to 0x0.st"""
    try:
        with open(file_path, "rb") as f:
            response = requests.post("https://0x0.st", files={"file": f}, timeout=30)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        logger.error(f"0x0 upload failed: {e}")
    return None

def convert_to_gif(input_path: Path) -> Path:
    """Convert MP4 to high-quality GIF"""
    logger.info(f"Converting {input_path} to GIF...")
    gif_path = input_path.with_suffix(".gif")

    if not check_ffmpeg():
        logger.warning("FFmpeg not found — keeping original file")
        return input_path

    try:
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-vf", "fps=15,scale=500:-1:flags=lanczos",
            "-loop", "0",
            "-y", str(gif_path)
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        if gif_path.exists():
            size_mb = gif_path.stat().st_size / 1024 / 1024
            logger.info(f"GIF created: {size_mb:.2f} MB")
            return gif_path
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr}")
    return input_path

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 Hi! Send me a GIF and I'll optimize it and give you a direct download link."
    )

def handle_gif(update: Update, context: CallbackContext):
    """Handle GIF processing"""
    try:
        msg = update.message.reply_text("Processing your GIF...")

        if update.message.animation:
            file_obj = update.message.animation
            file_name = f"gif_{file_obj.file_id}.mp4"
        elif update.message.document:
            file_obj = update.message.document
            file_name = file_obj.file_name or f"doc_{file_obj.file_id}"
        else:
            msg.edit_text("⚠️ Please send a valid GIF file!")
            return

        # Download file
        file = context.bot.get_file(file_obj.file_id)
        temp_path = EXPORT_DIR / file_name
        file.download(str(temp_path))
        logger.info(f"Downloaded: {temp_path} ({temp_path.stat().st_size / 1024 / 1024:.2f} MB)")

        # Convert GIF
        msg.edit_text("Converting to optimized GIF...")
        gif_path = convert_to_gif(temp_path)

        # Clean up if converted
        if gif_path != temp_path:
            temp_path.unlink(missing_ok=True)

        size_mb = gif_path.stat().st_size / 1024 / 1024
        logger.info(f"Final GIF: {size_mb:.2f} MB")

        # Upload file
        msg.edit_text("Uploading your GIF...")
        download_url = upload_to_catbox(gif_path) or upload_to_0x0(gif_path)

        if download_url:
            keyboard = [[InlineKeyboardButton("📥 Download GIF", url=download_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            msg.edit_text(
                f"✅ Your GIF is ready!\n\n"
                f"📁 Size: {size_mb:.1f} MB\n"
                f"🎯 Optimized format\n\n"
                f"Click below to download:",
                reply_markup=reply_markup
            )
            update.message.reply_text(f"`{download_url}`", parse_mode="MarkdownV2")
        else:
            msg.edit_text("❌ Upload failed. Try again later.")

        # Clean up
        gif_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Error processing GIF: {e}")
        update.message.reply_text(f"⚠️ Error: {e}")

# Simple health check for Render
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health check server running on port {port}")
    server.serve_forever()

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return

    # Start Render health check server
    threading.Thread(target=run_health_server, daemon=True).start()

    logger.info("Creating bot application...")
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.ANIMATION | Filters.document.gif, handle_gif))

    logger.info("Bot starting on Render...")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == "__main__":
    main()
