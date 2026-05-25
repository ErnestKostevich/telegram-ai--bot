"""Inline mode: @AI_DISCO_BOT <query> in any chat → AI answer inline.

Telegram requires inline answers within ~3 seconds, but AI calls take
much longer. So we use a 2-step pattern:

  1. inline_query handler returns an article card with a placeholder
     message + an inline "✨ Generate" button bound to a callback.
  2. When the user picks the card, the placeholder lands in the target
     chat carrying the button.
  3. When *the original asker* taps Generate, we call the AI (using
     their key) and edit the placeholder via inline_message_id.

This works without enabling /setinlinefeedback at BotFather.

BYOK enforcement: if the user has no API key set, we don't show any
results — instead we surface Telegram's switch_pm button that opens
the bot in a private chat for onboarding.
"""
import html
import secrets
import time
from typing import Dict, Tuple
from telegram import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardButton, InlineKeyboardMarkup, Update,
)
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from bot.storage import storage
from bot.ai import ai_handler
from bot.i18n import t


# In-memory cache: short_id → (author_uid, query_text, timestamp).
# Inline queries are short-lived (user picks within seconds), so an
# in-memory dict is fine. We GC entries older than 1h on each access.
_QUERY_CACHE: Dict[str, Tuple[int, str, float]] = {}
_CACHE_TTL_SEC = 3600  # 1 hour


def _gc_cache():
    """Drop entries older than TTL. Called opportunistically on each insert."""
    cutoff = time.time() - _CACHE_TTL_SEC
    stale = [k for k, (_, _, ts) in _QUERY_CACHE.items() if ts < cutoff]
    for k in stale:
        _QUERY_CACHE.pop(k, None)


def _cache_query(author_uid: int, query: str) -> str:
    """Store query in cache, return short_id usable in callback_data."""
    _gc_cache()
    short_id = secrets.token_urlsafe(8)  # ~11 chars, fits 64-byte limit easily
    _QUERY_CACHE[short_id] = (author_uid, query, time.time())
    # Hard cap cache size to prevent unbounded growth
    if len(_QUERY_CACHE) > 5000:
        oldest = sorted(_QUERY_CACHE.items(), key=lambda kv: kv[1][2])[:1000]
        for k, _ in oldest:
            _QUERY_CACHE.pop(k, None)
    return short_id


def _user_has_any_key(user: dict) -> bool:
    return any((user.get("api_keys") or {}).values())


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    iq: InlineQuery = update.inline_query
    if iq is None:
        return
    uid = iq.from_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    raw_query = (iq.query or "").strip()

    # Case 1: no key → surface switch_pm to onboarding
    if not _user_has_any_key(user):
        try:
            await iq.answer(
                results=[],
                cache_time=1,  # very short so user sees the switch_pm
                switch_pm_text=t(lang, "inline_setup_btn"),
                switch_pm_parameter="from_inline",
                is_personal=True,
            )
        except Exception:
            pass
        return

    # Case 2: empty query — show a hint card
    if not raw_query:
        results = [InlineQueryResultArticle(
            id="hint",
            title=t(lang, "inline_hint_title"),
            description=t(lang, "inline_hint_desc"),
            input_message_content=InputTextMessageContent(t(lang, "inline_hint_msg")),
        )]
        try:
            await iq.answer(results, cache_time=10, is_personal=True)
        except Exception:
            pass
        return

    # Case 3: real query — store + return article with callback button
    query_preview = raw_query[:120]
    short_id = _cache_query(uid, raw_query[:1000])  # cap stored query
    placeholder_text = (
        f"💭 <i>{html.escape(query_preview)}</i>\n\n"
        f"<i>{t(lang, 'inline_tap_to_generate')}</i>"
    )
    button = InlineKeyboardButton(
        t(lang, "inline_generate_btn"),
        callback_data=f"ig_{short_id}",
    )
    result = InlineQueryResultArticle(
        id=short_id,
        title=t(lang, "inline_ask_title", q=query_preview[:80]),
        description=t(lang, "inline_ask_desc"),
        input_message_content=InputTextMessageContent(
            placeholder_text, parse_mode="HTML",
        ),
        reply_markup=InlineKeyboardMarkup([[button]]),
    )
    try:
        await iq.answer([result], cache_time=1, is_personal=True)
    except Exception:
        pass


async def inline_generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ig_<short_id> callback from inline placeholder."""
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("ig_"):
        return
    short_id = data[3:]
    cached = _QUERY_CACHE.get(short_id)

    asker_uid = update.effective_user.id
    user = storage.get_user(asker_uid)
    lang = user.get("language", "ru")

    if cached is None:
        try:
            await query.answer(t(lang, "inline_expired"), show_alert=True)
        except Exception:
            pass
        return

    author_uid, prompt, _ts = cached
    # Security: only the original asker can spend their key
    if asker_uid != author_uid:
        try:
            await query.answer(t(lang, "inline_not_author"), show_alert=True)
        except Exception:
            pass
        return

    # Pop the entry so it can't be re-fired
    _QUERY_CACHE.pop(short_id, None)

    try:
        await query.answer(t(lang, "inline_working"))
    except Exception:
        pass

    inline_message_id = query.inline_message_id
    if not inline_message_id:
        # Should not happen for inline callbacks, but bail gracefully
        return

    # Mark as generating
    try:
        await context.bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=(f"💭 <i>{html.escape(prompt[:120])}</i>\n\n"
                  f"⏳ <i>{t(lang, 'ai_thinking')}</i>"),
            parse_mode="HTML",
        )
    except BadRequest:
        pass
    except Exception:
        pass

    # Run AI (single-shot, no streaming for inline — message-edit rate would
    # be terrible across foreign chats).
    from bot.handlers.ai_memory import _build_system_prompt
    try:
        response = await ai_handler.generate_response(
            asker_uid,
            prompt,
            system_prompt=_build_system_prompt(user, "You are AI DISCO BOT answering inline in a Telegram chat. Be concise (1-6 short paragraphs). "),
            use_history=False,
        )
    except Exception as e:
        response = f"❌ {e}"

    # Compose final message: quote the prompt + answer, with a small "via" footer
    safe_prompt = html.escape(prompt[:300])
    if response.startswith("❌"):
        final = f"💭 <i>{safe_prompt}</i>\n\n{response}"
    else:
        truncated = response[:3500]
        if len(response) > 3500:
            truncated += "…"
        final = (
            f"💭 <i>{safe_prompt}</i>\n\n"
            f"{truncated}\n\n"
            f"<i>— via @{(await context.bot.get_me()).username}</i>"
        )

    try:
        await context.bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=final,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except BadRequest:
        # Edit failed (message too old or formatting issue). Send a plain version.
        try:
            await context.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=final[:3900],
            )
        except Exception:
            pass
    except Exception:
        pass


# Module-level export used by tests
def _cache_size() -> int:
    return len(_QUERY_CACHE)


def _cache_clear():
    """For tests."""
    _QUERY_CACHE.clear()
