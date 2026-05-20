import html
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler, PROVIDERS
from bot.i18n import t

# Per-user cap on long-term memory entries to keep system-prompt size sane
MAX_MEMORY_ENTRIES = 50
MAX_MEMORY_KEY_LEN = 100
MAX_MEMORY_VALUE_LEN = 1000
# Cap memory entries injected into AI system prompts
MEMORY_SYSTEM_PROMPT_CAP = 30


def _build_system_prompt(user: dict, base: str = "") -> str:
    lang = user.get("language", "ru")
    lang_names = {"ru": "Russian", "en": "English", "it": "Italian"}
    sp = base or "You are AI DISCO BOT — a helpful, friendly AI assistant inside Telegram. "
    sp += f"Respond in {lang_names.get(lang, 'English')} unless asked otherwise. "
    sp += "Be concise and clear. Use simple line breaks instead of complex markdown. "
    if user.get("disco_mode"):
        sp += "Style: playful, witty, use emojis and humor moderately. "
    memory = user.get("memory") or {}
    if memory:
        # Cap how many entries get injected — otherwise huge memories blow context
        sp += "User's saved memory:\n"
        for k, v in list(memory.items())[:MEMORY_SYSTEM_PROMPT_CAP]:
            sp += f"- {k}: {v}\n"
    return sp


async def _send_long(message, text: str):
    text = (text or "").strip() or "…"
    # Telegram max ~4096; chunk by 3800 to be safe
    if len(text) <= 3800:
        await message.reply_text(text, disable_web_page_preview=True)
        return
    for i in range(0, len(text), 3800):
        await message.reply_text(text[i:i+3800], disable_web_page_preview=True)


async def setprovider_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "provider_usage", list=', '.join(PROVIDERS)))
        return
    provider = context.args[0].lower()
    if provider not in PROVIDERS:
        await update.message.reply_text(t(lang, "provider_unknown", list=', '.join(PROVIDERS)))
        return
    user["ai_provider"] = provider
    await storage.save()
    await update.message.reply_text(t(lang, "provider_set", provider=provider), parse_mode="HTML")


async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")

    # SECURITY: never let users paste keys in groups — bot may not be admin,
    # so the delete would fail silently and the secret would stay visible.
    if update.effective_chat.type != "private":
        # Best-effort delete; if it fails (we're not admin), at least warn the user.
        try:
            await update.message.delete()
        except Exception:
            pass
        await update.message.reply_text(t(lang, "key_group_refuse"), parse_mode="HTML")
        try:
            await context.bot.send_message(uid, t(lang, "key_group_dm_hint"), parse_mode="HTML")
        except Exception:
            pass
        return

    if len(context.args) < 2:
        await update.message.reply_text(t(lang, "key_usage"))
        return
    provider = context.args[0].lower()
    key = context.args[1]
    if provider not in PROVIDERS:
        await update.message.reply_text(t(lang, "provider_unknown", list=', '.join(PROVIDERS)))
        return
    user["api_keys"][provider] = key
    await storage.save()
    try:
        await update.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=t(lang, "key_saved", provider=provider),
        parse_mode="HTML",
    )


async def setmodel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "model_usage", current=user.get("ai_model", "default")))
        return
    model = " ".join(context.args)
    user["ai_model"] = model
    await storage.save()
    await update.message.reply_text(t(lang, "model_set", model=model), parse_mode="HTML")


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    user["stats"]["commands"] = user["stats"].get("commands", 0) + 1
    user["stats"]["msgs"] = user["stats"].get("msgs", 0) + 1
    if not context.args:
        await update.message.reply_text(t(lang, "ai_no_query"))
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text(t(lang, "ai_thinking"))
    try:
        response = await ai_handler.generate_response(uid, prompt, system_prompt=_build_system_prompt(user))
        if response.startswith("❌"):
            await msg.edit_text(response, parse_mode="HTML")
        elif len(response) > 3800:
            await msg.delete()
            await _send_long(update.message, response)
        else:
            await msg.edit_text(response, disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ {e}")
    await storage.save()


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    had = len(user.get("chat_history", []))
    ai_handler.clear_history(uid)
    await storage.save()
    await update.message.reply_text(t(lang, "ai_cleared", count=had // 2))


async def memorysave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if len(context.args) < 2:
        await update.message.reply_text(t(lang, "mem_usage"))
        return
    key = context.args[0][:MAX_MEMORY_KEY_LEN]
    value = " ".join(context.args[1:])[:MAX_MEMORY_VALUE_LEN]
    memory = user.setdefault("memory", {})
    # If adding a new key would exceed cap, refuse
    if key not in memory and len(memory) >= MAX_MEMORY_ENTRIES:
        await update.message.reply_text(t(lang, "mem_full", max=MAX_MEMORY_ENTRIES))
        return
    memory[key] = value
    await storage.save()
    await update.message.reply_text(t(lang, "mem_saved", key=html.escape(key), value=html.escape(value)))


async def memoryget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "mem_usage"))
        return
    key = context.args[0]
    value = user["memory"].get(key)
    if value:
        await update.message.reply_text(t(lang, "mem_value", key=html.escape(key), value=html.escape(value)))
    else:
        await update.message.reply_text(t(lang, "mem_not_found", key=html.escape(key)))


async def memorylist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not user["memory"]:
        await update.message.reply_text(t(lang, "mem_empty"))
        return
    text = t(lang, "mem_title")
    # Escape so any < or & in keys/values doesn't crash HTML parser
    for k, v in user["memory"].items():
        text += f"• <b>{html.escape(k)}</b>: {html.escape(v)}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def memorydel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "mem_del_usage"))
        return
    key = context.args[0]
    if key in user["memory"]:
        del user["memory"][key]
        await storage.save()
        await update.message.reply_text(t(lang, "mem_deleted", key=html.escape(key)))
    else:
        await update.message.reply_text(t(lang, "mem_not_found", key=html.escape(key)))
