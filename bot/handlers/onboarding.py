"""Onboarding wizard for new users.

A multi-step intro that walks brand-new users from zero to a working
key in ~30 seconds. Designed for BYOK: we never use the creator's key,
but we make getting your OWN free key trivial by pointing at the
fastest free-tier providers and pre-selecting them in the picker.

Triggers:
- /onboard — always
- First /start of a user who has no api_keys set — auto-run

Steps:
  1. Choose language (RU/EN/IT)
  2. Pick a FREE provider (Groq / Gemini / OpenRouter), with a "where
     to get key" button that opens that provider's signup page
  3. Bot puts the user in awaiting_key_for_<provider> state and shows
     a friendly "send your key" message
  4. After key is saved (handled by existing key flow), bot sends a
     short tour and the main keyboard

The wizard reuses get_provider_picker_keyboard with a custom prefix
so we can hook the "free provider chosen" event distinctly.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t, get_text
from bot.keyboards import get_main_keyboard


# Providers we recommend in onboarding — all have a free tier
FREE_PROVIDERS = [
    # (provider_id, label_emoji, signup_url, why)
    ("groq",       "⚡ Groq",       "https://console.groq.com/keys",  "free + fastest"),
    ("gemini",     "✨ Gemini",     "https://aistudio.google.com/apikey", "free, Google"),
    ("openrouter", "🌐 OpenRouter", "https://openrouter.ai/keys",     "free models inc."),
]


def _step1_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="onb_lang_ru"),
         InlineKeyboardButton("🇬🇧 English", callback_data="onb_lang_en"),
         InlineKeyboardButton("🇮🇹 Italiano", callback_data="onb_lang_it")],
    ])


def _step2_provider_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Cards for the three free providers + a 'I already have a key' shortcut.

    A compact language row sits on top: English is the default, RU/IT are
    one tap away (re-renders this step via the onb_lang_* handler). This
    replaces the old separate language step — English-first, no redundancy.
    """
    rows = [[
        InlineKeyboardButton(("🇬🇧 EN" if lang != "en" else "🔵 EN"), callback_data="onb_lang_en"),
        InlineKeyboardButton(("🇷🇺 RU" if lang != "ru" else "🔵 RU"), callback_data="onb_lang_ru"),
        InlineKeyboardButton(("🇮🇹 IT" if lang != "it" else "🔵 IT"), callback_data="onb_lang_it"),
    ]]
    for pid, label, url, _why in FREE_PROVIDERS:
        # First button: opens signup page in browser
        # Second button: picks this provider in the wizard
        rows.append([
            InlineKeyboardButton(f"🌐 {label}", url=url),
            InlineKeyboardButton(t(lang, "onb_use_btn"), callback_data=f"onb_pick_{pid}"),
        ])
    rows.append([InlineKeyboardButton(t(lang, "onb_have_key"), callback_data="onb_have_key")])
    rows.append([InlineKeyboardButton(t(lang, "onb_skip"), callback_data="onb_skip")])
    return InlineKeyboardMarkup(rows)


async def onboarding_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point.

    If the user's language is already known (auto-detected from
    Telegram's BCP-47 language_code in start_command, or set previously),
    we skip step 1 entirely and jump straight to the provider picker —
    no point asking again. Otherwise we show the trilingual greeting.
    """
    user = storage.get_user(update.effective_user.id)
    user["state"] = "onboarding"
    await storage.save()

    # English-first: default to EN, but the provider keyboard carries a
    # one-tap language row so RU/IT users switch instantly without a
    # separate step.
    eff_lang = user.get("language") if user.get("language") in ("ru", "en", "it") else "en"
    await update.message.reply_text(
        t(eff_lang, "onb_step2_text"),
        parse_mode="HTML",
        reply_markup=_step2_provider_keyboard(eff_lang),
        disable_web_page_preview=True,
    )


async def onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all onb_* callbacks. Dispatched from main button_callback."""
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = update.effective_user.id
    user = storage.get_user(uid)

    # --- Step 1 → 2: language picked ---
    if data.startswith("onb_lang_"):
        lang = data.split("_", 2)[2]
        if lang not in ("ru", "en", "it"):
            return
        user["language"] = lang
        await storage.save()
        await query.edit_message_text(
            t(lang, "onb_step2_text"),
            parse_mode="HTML",
            reply_markup=_step2_provider_keyboard(lang),
            disable_web_page_preview=True,
        )
        return

    lang = user.get("language", "en")

    # --- Step 2 → 3: a free provider chosen, ask for key ---
    if data.startswith("onb_pick_"):
        provider = data.split("_", 2)[2]
        if provider not in {p[0] for p in FREE_PROVIDERS}:
            return
        user["ai_provider"] = provider
        user["state"] = f"awaiting_key_for_{provider}"
        await storage.save()
        try:
            await query.edit_message_text(
                t(lang, "onb_step3_text", provider=provider),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t(lang, "onb_back_btn"), callback_data="onb_back_provider"),
                ]]),
            )
        except Exception:
            pass
        return

    # --- Back from "send key" to provider picker ---
    if data == "onb_back_provider":
        user["state"] = "onboarding"
        await storage.save()
        await query.edit_message_text(
            t(lang, "onb_step2_text"),
            parse_mode="HTML",
            reply_markup=_step2_provider_keyboard(lang),
            disable_web_page_preview=True,
        )
        return

    # --- "I already have a key" → jump straight into the regular 2-step setkey flow ---
    if data == "onb_have_key":
        from bot.keyboards import get_provider_picker_keyboard
        user["state"] = None
        await storage.save()
        await query.edit_message_text(
            t(lang, "key_pick_provider"),
            parse_mode="HTML",
            reply_markup=get_provider_picker_keyboard(lang, action_prefix="keyfor"),
        )
        return

    # --- "Skip for now" → finish onboarding, show main keyboard ---
    if data == "onb_skip":
        user["state"] = None
        await storage.save()
        try:
            await query.edit_message_text(t(lang, "onb_skipped"), parse_mode="HTML")
        except Exception:
            pass
        await context.bot.send_message(
            update.effective_chat.id,
            t(lang, "welcome", version=__import__("bot.config", fromlist=["BOT_VERSION"]).BOT_VERSION.rsplit(".", 1)[0]),
            parse_mode="HTML",
            reply_markup=get_main_keyboard(lang),
        )
        return


async def onboarding_finished_hook(update_or_chat_id, context, user, lang):
    """Called externally after the user successfully sets their first key.
    Sends the post-onboarding tour + main keyboard."""
    chat_id = update_or_chat_id if isinstance(update_or_chat_id, int) else update_or_chat_id.effective_chat.id
    try:
        await context.bot.send_message(
            chat_id,
            t(lang, "onb_done"),
            parse_mode="HTML",
            reply_markup=get_main_keyboard(lang),
        )
    except Exception:
        pass
