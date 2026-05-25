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

BOT_VERSION = "2.2.0"
BOT_BUILD_DATE = "2026-05-25"

# Chat memory: how many last user/assistant turns to keep
CHAT_HISTORY_LIMIT = 10
# Group message buffer (for /summary)
GROUP_HISTORY_LIMIT = 60

# ====== Free Tier (shared keys provided by creator) ======
# Creator can set any combination of these env vars; the bot will use them
# as fallbacks when the user has no key of their own.
# Recommended: set FALLBACK_GROQ_KEY (Groq has free models, fastest).
SHARED_KEYS = {
    "openai":     os.getenv("FALLBACK_OPENAI_KEY", ""),
    "gemini":     os.getenv("FALLBACK_GEMINI_KEY", ""),
    "anthropic":  os.getenv("FALLBACK_ANTHROPIC_KEY", ""),
    "groq":       os.getenv("FALLBACK_GROQ_KEY", ""),
    "openrouter": os.getenv("FALLBACK_OPENROUTER_KEY", ""),
    "mistral":    os.getenv("FALLBACK_MISTRAL_KEY", ""),
    "together":   os.getenv("FALLBACK_TOGETHER_KEY", ""),
    "deepseek":   os.getenv("FALLBACK_DEEPSEEK_KEY", ""),
}
# Preferred provider when user's selected provider has no shared key.
FREE_TIER_FALLBACK_PROVIDER = os.getenv("FREE_TIER_FALLBACK_PROVIDER", "groq")
# Daily limit of messages on shared-key. 0 = disabled (no free tier).
FREE_TIER_DAILY_LIMIT = _int_env("FREE_TIER_DAILY_LIMIT", 10)


def has_shared_key_for(provider: str) -> bool:
    return bool(SHARED_KEYS.get(provider))


def best_shared_key() -> tuple[str, str]:
    """Return (provider, key) for the best available shared key, or ("", "")."""
    if has_shared_key_for(FREE_TIER_FALLBACK_PROVIDER):
        return FREE_TIER_FALLBACK_PROVIDER, SHARED_KEYS[FREE_TIER_FALLBACK_PROVIDER]
    # Otherwise prefer fast/free ones first
    for p in ("groq", "gemini", "openrouter", "deepseek", "mistral", "together", "anthropic", "openai"):
        if has_shared_key_for(p):
            return p, SHARED_KEYS[p]
    return "", ""
