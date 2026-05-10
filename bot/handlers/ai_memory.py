from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler, PROVIDERS
from bot.i18n import t

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
    await context.bot.send_message(chat_id=update.effective_chat.id, text=t(lang, "key_saved", provider=provider), parse_mode="HTML")

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
    user["stats"]["commands"] += 1
    user["stats"]["msgs"] += 1
    if not context.args:
        await update.message.reply_text(t(lang, "ai_no_query"))
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text(t(lang, "ai_thinking"))
    system_prompt = "You are an AI assistant. "
    if user.get("disco_mode"):
        system_prompt = "You are a fun, creative AI. Use emojis, humor, and slang. "
    if user.get("memory"):
        system_prompt += "User memory:\n"
        for k, v in user["memory"].items():
            system_prompt += f"- {k}: {v}\n"
    try:
        response = await ai_handler.generate_response(uid, prompt, system_prompt=system_prompt)
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
            await msg.delete()
        else:
            await msg.edit_text(response)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")
    await storage.save()

async def memorysave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if len(context.args) < 2:
        await update.message.reply_text(t(lang, "mem_usage"))
        return
    key = context.args[0]
    value = " ".join(context.args[1:])
    user["memory"][key] = value
    await storage.save()
    await update.message.reply_text(t(lang, "mem_saved", key=key, value=value))

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
        await update.message.reply_text(t(lang, "mem_value", key=key, value=value))
    else:
        await update.message.reply_text(t(lang, "mem_not_found", key=key))

async def memorylist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not user["memory"]:
        await update.message.reply_text(t(lang, "mem_empty"))
        return
    text = t(lang, "mem_title")
    for k, v in user["memory"].items():
        text += f"• <b>{k}</b>: {v}\n"
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
        await update.message.reply_text(t(lang, "mem_deleted", key=key))
    else:
        await update.message.reply_text(t(lang, "mem_not_found", key=key))
