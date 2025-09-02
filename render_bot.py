#!/usr/bin/env python3

import os
import logging
import sys
from pathlib import Path
import subprocess
import shutil
import requests
import threading
from flask import Flask

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Starting GIF Bot for Render...")

# Import telegram libraries
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Create Flask app for health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return "GIF Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}

def run_flask():
    """Run Flask server in background thread."""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Get from environment variable
EXPORT_DIR = Path("temp_gifs")
EXPORT_DIR.mkdir(exist_ok=True)
MAX_SIZE_MB = 8  # Increased from 3MB to 8MB

def check_ffmpeg():
    """Check if FFmpeg is available."""
    return shutil.which("ffmpeg") is not None

def upload_to_catbox(file_path):
    """Upload to catbox.moe (permanent, reliable)"""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://catbox.moe/user/api.php',
                data={'reqtype': 'fileupload'},
                files={'fileToUpload': f},
                timeout=30
            )
        
        if response.status_code == 200:
            url = response.text.strip()
            print(f"Catbox upload success: {url}")
            return url
    except Exception as e:
        print(f"Catbox upload failed: {e}")
    return None

def upload_to_0x0(file_path):
    """Upload to 0x0.st (365 day expiry)"""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post('https://0x0.st', files={'file': f}, timeout=30)
        
        if response.status_code == 200:
            url = response.text.strip()
            print(f"0x0 upload success: {url}")
            return url
    except Exception as e:
        print(f"0x0 upload failed: {e}")
    return None

async def convert_to_gif(input_path: Path) -> Path:
    """Convert MP4 to high-quality GIF with better settings."""
    print(f"Converting {input_path} to high-quality GIF...")
    
    gif_path = input_path.with_suffix('.gif')
    
    if not check_ffmpeg():
        print("FFmpeg not available - keeping original format")
        return input_path
    
    try:
        # High quality settings - bigger size, better frame rate, custom palette
        palette_path = input_path.parent / f"palette_{input_path.stem}.png"
        
        # Generate optimized palette for better colors
        palette_cmd = [
            "ffmpeg", "-i", str(input_path),
            "-vf", "fps=15,scale=500:-1:flags=lanczos,palettegen=stats_mode=diff",
            "-y", str(palette_path)
        ]
        subprocess.run(palette_cmd, capture_output=True)
        
        # Create high-quality GIF with custom palette
        gif_cmd = [
            "ffmpeg", "-i", str(input_path), "-i", str(palette_path),
            "-lavfi", "fps=15,scale=500:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
            "-y", str(gif_path)
        ]
        subprocess.run(gif_cmd, capture_output=True)
        
        # Clean up palette
        palette_path.unlink(missing_ok=True)
        
        if gif_path.exists():
            size_mb = gif_path.stat().st_size / 1024 / 1024
            print(f"High-quality GIF created: {size_mb:.2f}MB")
            
            # Only compress if over 8MB now
            if size_mb > 8:
                print("Over 8MB, reducing size while keeping quality...")
                medium_path = input_path.parent / f"medium_{gif_path.name}"
                
                # Generate new palette for medium size
                med_palette = input_path.parent / f"med_palette_{input_path.stem}.png"
                palette_cmd = [
                    "ffmpeg", "-i", str(gif_path),
                    "-vf", "scale=400:-1:flags=lanczos,palettegen=stats_mode=diff",
                    "-y", str(med_palette)
                ]
                subprocess.run(palette_cmd, capture_output=True)
                
                # Create medium quality with palette
                cmd = [
                    "ffmpeg", "-i", str(gif_path), "-i", str(med_palette),
                    "-lavfi", "scale=400:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5",
                    "-y", str(medium_path)
                ]
                subprocess.run(cmd, capture_output=True)
                
                med_palette.unlink(missing_ok=True)
                
                if medium_path.exists():
                    gif_path.unlink()
                    gif_path = medium_path
                    size_mb = medium_path.stat().st_size / 1024 / 1024
                    print(f"Medium quality GIF: {size_mb:.2f}MB")
            
            return gif_path
            
    except Exception as e:
        print(f"Conversion failed: {e}")
    
    return input_path

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    await update.message.reply_text(
        "Hi! Send me a GIF and I'll optimize it and give you a download link!\n\n"
        "Works on any device - no special setup needed."
    )

async def handle_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process GIF and provide download link."""
    try:
        msg = await update.message.reply_text("Processing your GIF...")
        
        # Get file object
        if update.message.animation:
            file_obj = update.message.animation
            file_name = f"gif_{file_obj.file_id}.mp4"
        elif update.message.document:
            file_obj = update.message.document
            file_name = file_obj.file_name or f"doc_{file_obj.file_id}"
        else:
            await msg.edit_text("Please send a GIF file!")
            return
        
        # Download from Telegram
        file = await context.bot.get_file(file_obj.file_id)
        temp_path = EXPORT_DIR / file_name
        await file.download_to_drive(str(temp_path))
        
        print(f"Downloaded: {temp_path} ({temp_path.stat().st_size / 1024 / 1024:.2f}MB)")
        
        # Convert to GIF
        await msg.edit_text("Converting to optimized GIF...")
        gif_path = await convert_to_gif(temp_path)
        
        # Clean up temp file if we converted
        if gif_path != temp_path:
            temp_path.unlink(missing_ok=True)
        
        size_mb = gif_path.stat().st_size / 1024 / 1024
        print(f"Final GIF: {size_mb:.2f}MB")
        
        # Upload and get download link
        await msg.edit_text("Uploading your GIF...")
        
        # Try hosting services
        download_url = upload_to_catbox(gif_path)
        if not download_url:
            download_url = upload_to_0x0(gif_path)
        
        if download_url:
            # Create download button
            keyboard = [[InlineKeyboardButton("📥 Download GIF", url=download_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await msg.edit_text(
                f"✅ Your GIF is ready!\n\n"
                f"📁 Size: {size_mb:.1f}MB\n"
                f"🎯 Format: Optimized GIF\n\n"
                f"Click the button below or copy this link:",
                reply_markup=reply_markup
            )
            
            # Send copyable link
            await update.message.reply_text(f"`{download_url}`", parse_mode='MarkdownV2')
            
        else:
            await msg.edit_text("Upload failed - all services down. Try again later.")
        
        # Clean up local file
        gif_path.unlink(missing_ok=True)
        
    except Exception as e:
        print(f"Error processing GIF: {e}")
        await update.message.reply_text(f"Error: {e}")

def main():
    """Main function."""
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable not set!")
        return
    
    # Start Flask server in background thread for Render health check
    print("Starting health check server...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Creating bot application...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ANIMATION | filters.Document.ALL, handle_gif))
    
    print("Bot starting on Render...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
