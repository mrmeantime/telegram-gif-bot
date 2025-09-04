import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -----------------------------
# Logging Setup
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------------------
# Load BOT Token
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN is not set! Please configure it in Render environment variables.")

# -----------------------------
# Command Handlers
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when the user sends /start"""
    await update.message.reply_text("👋 Hi! Send me a GIF and I'll process it!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when the user sends /help"""
    await update.message.reply_text("ℹ️ Just send me a GIF, and I'll process it for you!")

# -----------------------------
# GIF Handler
# -----------------------------
async def handle_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming GIFs"""
    if update.message and update.message.animation:
        gif_file = update.message.animation.file_id
        logger.info(f"Received GIF with file_id: {gif_file}")
        await update.message.reply_text("✅ Got your GIF! Processing...")
        # You can add extra GIF processing logic here if needed later.
    else:
        await update.message.reply_text("❌ That doesn’t look like a GIF!")

# -----------------------------
# Error Handler
# -----------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log and report errors"""
    logger.error("Exception while handling update:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("⚠️ Something went wrong! Please try again later.")

# -----------------------------
# Main Bot Entry Point
# -----------------------------
def main():
    print("🚀 Starting Telegram GIF Bot...")

    # Build application
    app = Application.builder().token(BOT_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Register GIF message handler
    app.add_handler(MessageHandler(filters.ANIMATION, handle_gif))

    # Register error handler
    app.add_error_handler(error_handler)

    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# -----------------------------
# Run Bot
# -----------------------------
if __name__ == "__main__":
    main()
