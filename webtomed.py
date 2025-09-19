import feedparser
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from github import Github
import os
import sys

# --- Configs ---
BOT_TOKEN = os.getenv("MY_BOT_TOKEN")
CHANNEL_ID = os.getenv("MY_CHANNEL_ID")
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "AmirRezaFarhadi/webtomed"

# --- Validation ---
if not BOT_TOKEN or not CHANNEL_ID or not GITHUB_TOKEN:
    print("❌ Error: Missing one or more environment variables (MY_BOT_TOKEN / MY_CHANNEL_ID / MY_GITHUB_TOKEN).")
    sys.exit(1)

try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    print("❌ Error: CHANNEL_ID must be an integer (Telegram chat_id).")
    sys.exit(1)

# --- Init ---
bot = telegram.Bot(BOT_TOKEN)
app = Application.builder().token(BOT_TOKEN).build()
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(REPO_NAME)

# --- Helpers ---
def fetch_latest_article():
    feed = feedparser.parse("https://zee.backpr.com/index.xml")
    if not feed.entries:
        return "⚠️ No articles found.", "No title", "No link"
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
    await update.message.reply_text("🤖 Bot started and ready!")

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
       article_text, title, link = fetch_latest_article()

    # create new branch for PR
    source = repo.get_branch("main")
    new_branch_name = f"bot-article-{title.replace(' ', '-')[:20]}"
    try:
        repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=source.commit.sha)
    except Exception as e:
        print(f"⚠️ Branch may already exist: {e}")

    # create new file content
    file_path = f"posts/{title.replace(' ', '_')}.md"
    commit_message = f"Add article: {title}"
    repo.create_file(file_path, commit_message, article_text, branch=new_branch_name)

    # create PR
    pr = repo.create_pull(
        title=f"📝 New article: {title}",
        body="Auto-generated article from Telegram bot",
        head=new_branch_name,
        base="main"
    )
    await query.edit_message_text("✅ Pull Request created: " + pr.html_url)

# --- Handlers ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("post", publish_article))
app.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    print("🤖 Bot is running...")
    app.run_polling()
