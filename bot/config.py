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

BOT_VERSION = "3.4.0"
BOT_BUILD_DATE = "2026-06-16"

# Chat memory: how many last user/assistant turns to keep
CHAT_HISTORY_LIMIT = 10
# Group message buffer (for /summary)
GROUP_HISTORY_LIMIT = 60

# ====== Monetization ======
# NEVER hardcode keys here — read from env, set via `flyctl secrets set ...`.
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY", "")
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
# Public base URL where this bot serves HTTP (webhook endpoint + mini app).
# Set to your Fly.io app's URL, e.g. "https://telegram-ai--bot.fly.dev"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
WEBHOOK_PORT = _int_env("WEBHOOK_PORT", 8080)

# ====== Subscription tiers ======
# Source of truth for pricing, included features, and image credit budgets.
TIERS = {
    "free": {
        "label": "Free",
        "stars": 0,
        "usd": 0.0,
        "days": 0,
        "image_credits": 0,
        "features": ["AI chat (BYOK)", "Voice input", "Persona", "Notes", "Mini-games"],
    },
    "plus": {
        "label": "Plus",
        "stars": 199,
        "usd": 3.99,
        "days": 30,
        "image_credits": 20,
        "features": ["Everything in Free", "Reminders", "Voice replies (TTS)", "Smart NL reminders"],
    },
    "pro": {
        "label": "Pro",
        "stars": 399,
        "usd": 7.99,
        "days": 30,
        "image_credits": 100,
        "features": ["Everything in Plus", "Image generation", "Photo analysis (Vision)", "Document analysis", "Priority support"],
    },
}

# Partner reward: when a referred user makes their first paid purchase,
# the referrer gets this many days of free Plus tier.
PARTNER_REWARD_DAYS = 30
