import feedparser
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from github import Github
import os

# --- Configs ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # کانال یا گروهی که باید ریپورت بره
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "AmirRezaFarhadi/webtomed"

# --- Init ---
bot = telegram.Bot(BOT_TOKEN)
app = Application.builder().token(BOT_TOKEN).build()
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(REPO_NAME)

# --- Helpers ---
def fetch_latest_article():
    feed = feedparser.parse("https://zee.backpr.com/index.xml")
    item = feed.entries[0]
    title = item.title
    link = item.link
    summary = item.summary if hasattr(item, "summary") else ""
    
    template = f"""{title}

TL;DR 🚀
{summary[:200]}...

{summary[:500]}

---

👉 Want the full deep dive? Check it out here:  
{link}
"""
    return template, title, link

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot started ✅")

async def publish_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    article_text, title, link = fetch_latest_article()

    keyboard = [
        [InlineKeyboardButton("✅ Publish", callback_data="publish"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"🚀 New Article Ready:\n\n{article_text}",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        pr = repo.create_pull(
            title="New article from bot",
            body="Auto-generated article",
            head="main",
            base="main"
        )
        await query.edit_message_text("✅ Pull Request created: " + pr.html_url)

    elif query.data == "cancel":
        await query.edit_message_text("❌ Publishing cancelled.")

# --- Handlers ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("post", publish_article))
app.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    app.run_polling()
