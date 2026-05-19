import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "") # e.g. username/repo
GITHUB_FILE_PATH = os.getenv("GITHUB_FILE_PATH", "bot_data.json")
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))

BOT_VERSION = "2.0.0"
BOT_BUILD_DATE = "2026-05-20"

# Chat memory: how many last user/assistant turns to keep
CHAT_HISTORY_LIMIT = 10
# Group message buffer (for /summary)
GROUP_HISTORY_LIMIT = 60
