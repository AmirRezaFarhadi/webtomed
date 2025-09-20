import feedparser
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from github import Github
import os
import datetime
import re
import requests
from bs4 import BeautifulSoup   # ✅ برای پاک کردن HTML

# --- Configs ---
BOT_TOKEN = os.getenv("MY_BOT_TOKEN")
CHANNEL_ID = os.getenv("MY_CHANNEL_ID")
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
HASHNODE_KEY = os.getenv("HASHNODE_API_KEY")
REPO_NAME = "AmirRezaFarhadi/webtomed"

# --- Safety Check ---
if not BOT_TOKEN or not CHANNEL_ID or not GITHUB_TOKEN or not HASHNODE_KEY:
    raise ValueError("❌ Missing one or more environment variables!")

# --- Init ---
bot = telegram.Bot(BOT_TOKEN)
app = Application.builder().token(BOT_TOKEN).build()
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(REPO_NAME)

# --- Helpers ---
def slugify(text):
    """ تبدیل عنوان مقاله به فرمت امن برای فایل و برنچ """
    return re.sub(r'[^a-zA-Z0-9\-]', '-', text).strip('-').lower()

def clean_html(raw_html):
    """ پاک کردن تگ‌های HTML از خلاصه مقاله """
    return BeautifulSoup(raw_html, "html.parser").get_text()

def fetch_latest_article():
    """ گرفتن اولین مقاله جدید از RSS که قبلاً پست نشده """
    feed = feedparser.parse("https://zee.backpr.com/index.xml")
    posted_file = "posted_articles.txt"

    if os.path.exists(posted_file):
        with open(posted_file, "r") as f:
            posted_links = set(f.read().splitlines())
    else:
        posted_links = set()

    for item in feed.entries:
        link = item.link
        if link not in posted_links:
            title = item.title
            category = item.get("category", "general")
            raw_summary = item.summary if hasattr(item, "summary") else ""
            summary = clean_html(raw_summary)

            with open(posted_file, "a") as f:
                f.write(link + "\n")

            template = f"""{title}

TL;DR 🚀
{summary[:200]}...

{summary[:500]}

---

👉 Want the full deep dive? Check it out here:  
{link}
"""
            return template, title, link, category

    return None, None, None, None

# --- Hashnode Publisher ---
def publish_to_hashnode(title, article_text):
    """ پابلیش مقاله روی Hashnode با API """
    url = "https://api.hashnode.com/"
    headers = {
        "Authorization": HASHNODE_KEY,
        "Content-Type": "application/json"
    }
    query = """
    mutation CreateStory($input: CreateStoryInput!) {
      createStory(input: $input) {
        _id
        slug
        title
      }
    }
    """
    variables = {
        "input": {
            "title": title,
            "contentMarkdown": article_text,
            "tags": []
        }
    }

    response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
    return response.json()

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot started and ready!")

async def publish_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    article_text, title, link, category = fetch_latest_article()

    if not article_text:
        await bot.send_message(chat_id=CHANNEL_ID, text="⚠️ No new articles found.")
        return

    # --- Create new branch ---
    today = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    branch_name = f"bot-article-{slugify(title)[:30]}-{today}"

    source = repo.get_branch("main")
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=source.commit.sha)

    # --- File path (برای Jekyll) ---
    today_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    safe_title = slugify(title)
    file_path = f"_posts/{today_date}-{safe_title}.md"

    # --- Markdown content ---
    md_content = f"""---
layout: post
title: "{title}"
date: "{datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}"
categories: "{category}"
tags: ["ai-generated"]
---

{article_text}
"""

    # --- Commit or update file ---
    try:
        contents = repo.get_contents(file_path, ref=branch_name)
        # اگر فایل وجود داشت → آپدیت
        repo.update_file(
            path=file_path,
            message=f"Update article: {title}",
            content=md_content,
            sha=contents.sha,
            branch=branch_name
        )
    except Exception:
        # اگر فایل وجود نداشت → بساز
        repo.create_file(
            path=file_path,
            message=f"Add article: {title}",
            content=md_content,
            branch=branch_name
        )

    # --- Create PR ---
    pr = repo.create_pull(
        title=f"📝 New article: {title}",
        body=f"Auto-generated article via Telegram Bot 🤖\n\n---\n\n{article_text}",
        head=branch_name,
        base="main"
    )

    pr.add_to_labels("ai-generated")
    pr.merge(commit_message=f"Auto-merged article: {title}")

    # --- Publish to Hashnode ---
    try:
        result = publish_to_hashnode(title, article_text)
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🌐 Hashnode post created: {result}"
        )
    except Exception as e:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"⚠️ Failed to publish to Hashnode: {e}"
        )

    # --- Telegram Report ---
    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=(
            f"✅ New article published!\n\n"
            f"📌 Title: {title}\n"
            f"🔗 Link: {link}\n"
            f"📂 Branch: {branch_name}\n"
            f"📜 Pull Request: {pr.html_url}\n"
            f"✅ Successfully merged into main!\n"
            f"🌐 Also published to Hashnode!"
        )
    )

# --- Handlers ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("post", publish_article))

if __name__ == "__main__":
    app.run_polling()
