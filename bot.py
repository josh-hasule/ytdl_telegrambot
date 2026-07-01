import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.request import HTTPXRequest
from telegram.error import Conflict, TimedOut
from downloader import download_video, is_youtube_url
from config import BOT_TOKEN, DOWNLOAD_DIR, BOT_PASSWORD

logging.basicConfig(level=logging.INFO)


def is_authenticated(ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    return ctx.user_data.get("authenticated") is True


# ── /start ────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *YouTube Downloader Bot*\n\n"
        "Just send me a YouTube link (video or Short) and I'll ask you the quality.\n\n"
        "Commands:\n"
        "/start — show this message\n"
        "/help  — usage tips\n"
        "/login — unlock downloads (once per session)",
        parse_mode="Markdown"
    )


# ── /login ────────────────────────────────────────────────────
async def login(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "🔐 Send your password:\n`/login your_password`",
            parse_mode="Markdown",
        )
        return

    if args[0] == BOT_PASSWORD:
        ctx.user_data["authenticated"] = True
        await update.message.reply_text("✅ Logged in. You can send YouTube links now.")
    else:
        await update.message.reply_text("❌ Wrong password.")


# ── /help ─────────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use:*\n\n"
        "1. Paste any YouTube or YouTube Shorts URL\n"
        "2. Choose your download quality\n"
        "3. Wait for the file ✅\n\n"
        "⚠️ Files over 50 MB can't be sent via Telegram bots.",
        parse_mode="Markdown"
    )

# ── Receives a URL ────────────────────────────────────────────
async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authenticated(ctx):
        await update.message.reply_text(
            "🔐 Please log in first:\n`/login your_password`",
            parse_mode="Markdown",
        )
        return

    url = update.message.text.strip()

    if not is_youtube_url(url):
        await update.message.reply_text("❌ Please send a valid YouTube or Shorts URL.")
        return

    # Store URL in user context
    ctx.user_data["url"] = url

    keyboard = [
        [
            InlineKeyboardButton("🎥 Best Quality", callback_data="best"),
            InlineKeyboardButton("📺 720p", callback_data="720p"),
        ],
        [
            InlineKeyboardButton("📱 480p", callback_data="480p"),
            InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data="audio"),
        ],
    ]

    await update.message.reply_text(
        "Choose download quality:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── Handles quality button press ──────────────────────────────
async def handle_quality(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality = query.data
    url = ctx.user_data.get("url")

    if not url:
        await query.edit_message_text("❌ Session expired. Please send the URL again.")
        return

    await query.edit_message_text(f"⏳ Downloading ({quality})... please wait.")

    try:
        result = download_video(url, quality)
        filepath = result["filepath"]
        title = result["title"]
        is_short = result["is_short"]

        label = "🩳 YouTube Short" if is_short else "🎬 YouTube Video"
        caption = (
            f"{label}\n"
            f"📌 *{title}*\n"
            f"👤 {result['uploader']}\n"
            f"⏱ {result['duration']}s"
        )

        with open(filepath, "rb") as f:
            if quality == "audio":
                await query.message.reply_audio(
                    audio=f,
                    caption=caption,
                    parse_mode="Markdown",
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30,
                )
            else:
                await query.message.reply_video(
                    video=f,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True,
                    width=result.get("width"),
                    height=result.get("height"),
                    duration=result.get("duration"),
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=30,
                )

        os.remove(filepath)

        # Send description + tags as a separate message (captions cap at 1024 chars,
        # messages cap at 4096, so we chunk if needed).
        tags = result.get("tags") or []
        description = result.get("description") or "No description available."
        tags_line = f"\n\n🏷 *Tags:* {', '.join(tags[:30])}" if tags else ""
        info_text = f"📝 *Description:*\n{description}{tags_line}"

        for i in range(0, len(info_text), 4000):
            await query.message.reply_text(info_text[i:i + 4000], parse_mode="Markdown")

    except Exception as e:
        err = str(e)
        if "File is too large" in err or "max_filesize" in err.lower():
            await query.message.reply_text("❌ File exceeds 50 MB — Telegram's bot limit. Try 480p or audio.")
        else:
            await query.message.reply_text(f"❌ Download failed:\n`{err}`", parse_mode="Markdown")

# ── Errors ────────────────────────────────────────────────────
async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    err = ctx.error
    if isinstance(err, Conflict):
        logging.error(
            "409 Conflict: another bot instance is polling with this token. "
            "Stop the duplicate (local terminal, old Docker container, or server)."
        )
    elif isinstance(err, TimedOut):
        logging.warning("Telegram request timed out — will retry.")
    else:
        logging.exception("Unhandled error", exc_info=err)

# ── Main ──────────────────────────────────────────────────────
def main():
    # read_timeout must exceed Telegram long-poll hold time (see run_polling timeout).
    poll_timeout = 20
    polling_request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=poll_timeout + 15.0,
        write_timeout=30.0,
    )
    media_request = HTTPXRequest(connect_timeout=30.0, read_timeout=120.0, write_timeout=120.0)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(media_request)
        .get_updates_request(polling_request)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_quality))
    app.add_error_handler(on_error)

    print("Bot is running...")
    app.run_polling(timeout=poll_timeout, bootstrap_retries=-1)

if __name__ == "__main__":
    main()