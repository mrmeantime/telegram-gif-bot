import os
import logging
import requests
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# --------------------------------------
# Logging Setup
# --------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --------------------------------------
# Environment Variables
# --------------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")

# --------------------------------------
# Simple Welcome Command
# --------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your GIF Bot!\n\n"
        "• Send me a keyword and I'll fetch a GIF.\n"
        "• Use /help for more commands."
    )

# --------------------------------------
# Help Command
# --------------------------------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 *Available Commands:*\n"
        "/start → Start the bot\n"
        "/help → Show this message\n"
        "Just send any keyword, and I'll fetch a GIF for you!",
        parse_mode="Markdown"
    )

# --------------------------------------
# Fetch GIFs from Giphy API
# --------------------------------------
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY")
GIPHY_URL = "https://api.giphy.com/v1/gifs/search"

def fetch_gif(query: str):
    params = {
        "api_key": GIPHY_API_KEY,
        "q": query,
        "limit": 1,
        "rating": "pg-13"
    }
    try:
        response = requests.get(GIPHY_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["data"]:
            return data["data"][0]["images"]["original"]["url"]
        return None
    except Exception as e:
        logger.error(f"Error fetching GIF: {e}")
        return None

# --------------------------------------
# Handle User Messages (GIF Search)
# --------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("⚠️ Please send me a keyword!")
        return

    await update.message.reply_text(f"🔍 Searching GIF for: *{query}* ...", parse_mode="Markdown")

    gif_url = fetch_gif(query)
    if gif_url:
        await update.message.reply_animation(animation=gif_url)
    else:
        await update.message.reply_text("😕 Sorry, I couldn't find a GIF for that.")

# --------------------------------------
# Error Handler
# --------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# --------------------------------------
# Main App
# --------------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Message Handler (GIF Fetch)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Errors
    app.add_error_handler(error_handler)

    logger.info("🚀 Bot started successfully!")
    app.run_polling()

# --------------------------------------
# Entry Point
# --------------------------------------
if __name__ == "__main__":
    main()
