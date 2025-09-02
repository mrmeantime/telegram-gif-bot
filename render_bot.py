#!/usr/bin/env python3

import os
import logging
import sys
from pathlib import Path
import subprocess
import shutil
import requests
import threading
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Starting GIF Bot for Render...")

# Import telegram libraries
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Simple HTTP server for health checks
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'GIF Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

def run_health_server():
    """Run simple HTTP server for Render health checks."""
    port = int(os.environ.get('PORT', 5000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"Health server running on port {port}")
    server.serve_forever()

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
EXPORT_DIR = Path("temp_gifs")
EXPORT_DIR.mkdir(exist_ok=True)

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
    """Simple, working GIF conversion."""
    print(f"Converting {input_path} to GIF...")
    
    gif_path = input_path.with_suffix('.gif')
    
    if not check_ffmpeg():
        print("FFmpeg not available - keeping original")
        return input_path
    
    try:
        # Simple conversion that works
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-vf", "scale=400:-1",  # Bigger than before for better quality
            "-y", str(gif_path)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        if gif_path.exists():
            size_mb = gif_path.stat().st_size / 1024 / 1024
            print(f"GIF created: {size_mb:.2f}MB")
            return gif_path
            
    except Exception as e:
        print(f"Conversion failed: {e}")
    
    return input_path

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    await update.message.reply_text(
        "Hi! Send me a GIF and I'll optimize it and give you a download link!"
    )

async def handle_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process GIF and provide download link."""
    try:
        print("Processing GIF message...")
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
        
        print(f"File detected: {file_name}")
        
        # Download from Telegram
        file = await context.bot.get_file(file_obj.file_id)
        temp_path = EXPORT_DIR / file_name
        await file.download_to_drive(str(temp_path))
        
        print(f"Downloaded: {temp_path}")
        
        # Convert to GIF
        await msg.edit_text("Converting to GIF...")
        gif_path = await convert_to_gif(temp_path)
        
        # Clean up temp file if we converted
        if gif_path != temp_path:
            temp_path.unlink(missing_ok=True)
        
        size_mb = gif_path.stat().st_size / 1024 / 1024
        print(f"Final GIF: {size_mb:.2f}MB")
        
        # Upload and get download link
        await msg.edit_text("Uploading your GIF...")
        
        download_url = upload_to_catbox(gif_path)
        if not download_url:
            download_url = upload_to_0x0(gif_path)
        
        if download_url:
            # Create download button
            keyboard = [[InlineKeyboardButton("Download GIF", url=download_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await msg.edit_text(
                f"Your GIF is ready!\n\n"
                f"Size: {size_mb:.1f}MB\n"
                f"Format: {gif_path.suffix.upper()}\n\n"
                f"Click button or copy link:",
                reply_markup=reply_markup
            )
            
            # Send copyable link
            await update.message.reply_text(f"`{download_url}`", parse_mode='MarkdownV2')
            
            print(f"Success! Download link: {download_url}")
            
        else:
            await msg.edit_text("Upload failed - try again later.")
        
        # Clean up local file
        gif_path.unlink(missing_ok=True)
        
    except Exception as e:
        print(f"Error processing GIF: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"Error: {e}")

def main():
    """Main function."""
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN environment variable not set!")
        return
    
    # Start health check server in background thread
    print("Starting health check server...")
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    print("Creating bot application...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ANIMATION | filters.Document.ALL, handle_gif))
    
    print("Bot ready - send GIFs to test!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
