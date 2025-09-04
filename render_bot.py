#!/usr/bin/env python3

import os
import logging
import sys
from pathlib import Path
import subprocess
import shutil
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Starting Telegram GIF Bot...")

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
EXPORT_DIR = Path("temp_gifs")
EXPORT_DIR.mkdir(exist_ok=True)

def check_ffmpeg():
    """Check if FFmpeg is available."""
    return shutil.which("ffmpeg") is not None

def upload_to_catbox(file_path):
    """Upload to Catbox."""
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
        logger.error(f"Catbox upload failed: {e}")
    return None

def upload_to_0x0(file_path):
    """Upload to 0x0.st."""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post('https://0x0.st', files={'file': f}, timeout=30)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        logger.error(f"0x0 upload failed: {e}")
    return None

async def convert_to_gif(input_path: Path) -> Path:
    """Convert MP4 to optimized GIF."""
    gif_path = input_path.with_suffix('.gif')
    if not check_ffmpeg():
        return input_path

    try:
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-vf", "fps=15,scale=500:-1:flags=lanczos",
            "-loop", "0",
            "-y", str(gif_path)
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return gif_path
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e}")
        return input_path

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    await update.message.reply_text(
        "👋 Hi! Send me a GIF and I’ll optimize it and give you a download link."
    )

async def handle_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming GIFs only."""
    try:
        msg = await update.message.reply_text("Processing your GIF...")

        # Check if user sent a GIF
        if update.message.animation:
            file_obj = update.message.animation
            file_name = f"gif_{file_obj.file_id}.mp4"
        else:
            await msg.edit_text("❌ Please send a valid GIF file!")
            return

        # Download from Telegram
        file = await context.bot.get_file(file_obj.file_id)
        temp_path = EXPORT_DIR / file_name
        await file.download_to_drive(str(temp_path))

        # Convert to GIF
        await msg.edit_text("Converting to optimized GIF...")
        gif_path = await convert_to_gif(temp_path)

        # Remove temp file if converted
        if gif_path != temp_path:
            temp_path.unlink(missing_ok=True)

        # Upload GIF to hosting
        await msg.edit_text("Uploading your GIF...")
        download_url = upload_to_catbox(gif_path) or upload_to_0x0(gif_path)

        if download_url:
            keyboard = [[InlineKeyboardButton("📥 Download GIF", url=download_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await msg.edit_text(
                f"✅ Your optimized GIF is ready!\n\n"
                f"📁 Size: {gif_path.stat().st_size / 1024 / 1024:.1f}MB",
                reply_markup=reply_markup
            )
            await update.message.reply_text(f"`{download_url}`", parse_mode='MarkdownV2')
        else:
            await msg.edit_text("⚠️ Upload failed. Try again later.")

        gif_path.unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"Error processing GIF: {e}")
        await update.message.reply_text(f"Error: {e}")

def main():
    """Start bot with polling."""
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable not set!")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_gif))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
