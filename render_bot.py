#!/usr/bin/env python3
import os
import logging
import sys
import threading
import subprocess
import shutil
import requests
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Starting GIF Bot for Render...")

# Bot config
BOT_TOKEN = os.getenv("BOT_TOKEN")
EXPORT_DIR = Path("temp_gifs")
EXPORT_DIR.mkdir(exist_ok=True)
MAX_SIZE_MB = 3

# ----------------------------
# Health Check Server (Render)
# ----------------------------
def run_health_server():
    """Start a lightweight HTTP server so Render thinks we're alive."""
    port = int(os.environ.get("PORT", 10000))
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
    server = HTTPServer(("", port), HealthHandler)
    print(f"Health server running on port {port}")
    server.serve_forever()

# ----------------------------
# Utility Functions
# ----------------------------
def check_ffmpeg():
    """Check if FFmpeg is available."""
    return shutil.which("ffmpeg") is not None

def upload_to_catbox(file_path):
    """Upload to catbox.moe (permanent)."""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://catbox.moe/user/api.php',
                data={'reqtype': 'fileupload'},
                files={'fileToUpload': f},
                timeout=30
            )
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        print(f"Catbox upload failed: {e}")
    return None

def upload_to_0x0(file_path):
    """Upload to 0x0.st (expires after ~1 year)."""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post('https://0x0.st', files={'file': f}, timeout=30)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        print(f"0x0 upload failed: {e}")
    return None

async def convert_to_gif(input_path: Path) -> Path:
    """Convert video to optimized GIF."""
    print(f"Converting {input_path} to GIF...")
    gif_path = input_path.with_suffix('.gif')

    if not check_ffmpeg():
        print("FFmpeg not available — returning original file")
        return input_path

    try:
        # Optimized settings for Render (lighter, faster)
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-vf", "fps=12,scale=360:-1:flags=lanczos",
            "-loop", "0",
            "-y", str(gif_path)
        ]
        subprocess.run(cmd, capture_output=True)

        # If GIF size > 8MB, downscale progressively
        size_mb = gif_path.stat().st_size / 1024 / 1024
        if size_mb > 8:
            print("GIF too large, compressing...")
            smaller_path = input_path.parent / f"small_{gif_path.name}"
            cmd = [
                "ffmpeg", "-i", str(gif_path),
                "-vf", "fps=10,scale=280:-1:flags=lanczos",
                "-y", str(smaller_path)
            ]
            subprocess.run(cmd, capture_output=True)
            gif_path.unlink(missing_ok=True)
            gif_path = smaller_path
        return gif_path
    except Exception as e:
        print(f"FFmpeg conversion failed: {e}")
        return input_path

# ----------------------------
# Telegram Bot Handlers
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send me a GIF or short video and I'll optimize it and give you a download link!"
    )

async def handle_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("Processing your GIF...")
    temp_path = None
    gif_path = None

    try:
        # Identify file type
        if update.message.animation:
            file_obj = update.message.animation
            file_name = f"gif_{file_obj.file_id}.mp4"
        elif update.message.document:
            file_obj = update.message.document
            file_name = file_obj.file_name or f"doc_{file_obj.file_id}"
        else:
            await msg.edit_text("Please send a GIF or video file!")
            return

        # Download from Telegram
        file = await context.bot.get_file(file_obj.file_id)
        temp_path = EXPORT_DIR / file_name
        await file.download_to_drive(str(temp_path))

        # Convert to optimized GIF
        await msg.edit_text("Converting to optimized GIF...")
        gif_path = await convert_to_gif(temp_path)

        # Upload optimized GIF
        await msg.edit_text("Uploading optimized GIF...")
        download_url = upload_to_catbox(gif_path) or upload_to_0x0(gif_path)

        if download_url:
            keyboard = [[InlineKeyboardButton("📥 Download GIF", url=download_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(
                f"✅ Your GIF is ready!\n\n📁 Size: {gif_path.stat().st_size / 1024 / 1024:.1f}MB\n",
                reply_markup=reply_markup
            )
            await update.message.reply_text(f"`{download_url}`", parse_mode="MarkdownV2")
        else:
            await msg.edit_text("❌ Upload failed. Please try again later.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error: {e}")
    finally:
        # Always clean up files
        if gif_path and gif_path.exists():
            gif_path.unlink(missing_ok=True)
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)

# ----------------------------
# Main Bot Runner
# ----------------------------
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Set it in Render environment variables.")
        sys.exit(1)

    # Start health server for Render
    threading.Thread(target=run_health_server, daemon=True).start()

    # Start Telegram bot app
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ANIMATION | filters.Document.ALL, handle_gif))

    print("Bot running on Render...")
    app.run_polling(drop_pending_updates=True, poll_interval=1.0, timeout=10)

if __name__ == "__main__":
    main()
