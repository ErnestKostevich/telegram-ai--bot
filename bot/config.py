import logging
import os
from dotenv import load_dotenv

load_dotenv()

_logger = logging.getLogger(__name__)


def _int_env(name: str, default: int = 0) -> int:
    """Read an integer env var; log and fall back to default on garbage input
    so a typo in CREATOR_ID doesn't crash the bot on import."""
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        _logger.warning(f"Env var {name}={raw!r} is not a valid int — using {default}")
        return default


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # e.g. username/repo
GITHUB_FILE_PATH = os.getenv("GITHUB_FILE_PATH", "bot_data.json")
CREATOR_ID = _int_env("CREATOR_ID", 0)

BOT_VERSION = "2.0.3"
BOT_BUILD_DATE = "2026-05-20"

# Chat memory: how many last user/assistant turns to keep
CHAT_HISTORY_LIMIT = 10
# Group message buffer (for /summary)
GROUP_HISTORY_LIMIT = 60
