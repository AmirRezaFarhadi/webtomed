import feedparser
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from github import Github
import os
import datetime
import re
from bs4 import BeautifulSoup   # ✅ برای پاک کردن HTML

# --- Configs ---
BOT_TOKEN = os.getenv("MY_BOT_TOKEN")
CHANNEL_ID = os.getenv("MY_CHANNEL_ID")
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "AmirRezaFarhadi/webtomed"

# --- Safety Check ---
if not BOT_TOKEN or not CHANNEL_ID or not GITHUB_TOKEN:
    raise ValueError("❌ Missing one or more environment variables!")

# --- Init ---
bot = telegram.Bot(BOT_TOKEN)
app = Application.builder().token(BOT_TOKEN).build()
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(REPO_NAME)

# --- Helpers ---
def slugify(text):
    return re.sub(r'[^a-zA-Z0-9\-]', '-', text).strip('-').lower()

def clean_html(raw_html):
    return BeautifulSoup(raw_html, "html.parser").get_text()

def fetch_latest_article():
    feed = feedparser.parse("https://zee.backpr.com/index.xml")
    item = feed.entries[0]
    title = item.title
    link = item.link                      # ✅ لینک مستقیم مقاله
    category = item.get("category", "general")
    raw_summary = item.summary if hasattr(item, "summary") else ""
    summary = clean_html(raw_summary)     # ✅ پاکسازی HTML

    template = f"""{title}

TL;DR 🚀
{summary[:200]}...

{summary[:500]}

---

👉 Want the full deep dive? Check it out here:  
{link}
"""
    return template, title, link, category

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot started and ready!")

async def publish_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    article_text, title, link, category = fetch_latest_article()

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

# --- Button Handler ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        article_text, title, link, category = fetch_latest_article()

        # branch name
        today = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        branch_name = f"bot-article-{slugify(title)[:30]}-{today}"

        # base branch
        source = repo.get_branch("main")
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=source.commit.sha)

        # file path
        safe_title = slugify(title)
        file_path = f"articles/{safe_title}.md"

        # markdown with front matter
        md_content = f"""---
title: "{title}"
date: "{datetime.datetime.utcnow().isoformat()}"
category: "{category}"
tags: ["ai-generated"]
---

{article_text}
"""

        # commit file
        repo.create_file(
            path=file_path,
            message=f"Add article: {title}",
            content=md_content,
            branch=branch_name
        )

        # create PR
        pr = repo.create_pull(
            title=f"📝 New article: {title}",
            body=f"Auto-generated article via Telegram Bot 🤖\n\n---\n\n{article_text}",
            head=branch_name,
            base="main"
        )

        # add label ai-generated
        pr.add_to_labels("ai-generated")

        await query.edit_message_text("✅ Pull Request created: " + pr.html_url)

    elif query.data == "cancel":
        await query.edit_message_text("❌ Publishing cancelled.")

# --- Handlers ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("post", publish_article))
app.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    app.run_polling()
