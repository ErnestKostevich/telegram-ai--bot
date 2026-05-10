from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler, PROVIDERS
from bot.i18n import t

async def grouphelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    texts = {
        "ru": "👥 <b>Групповые команды:</b>\n\n🛡️ <b>Модерация:</b>\n/warn — предупреждение\n/mute [мин] — мут\n/ban — бан\n/kick — кик\n/purge [кол-во] — удалить\n/antispam on/off\n/guardian on/off\n\n🤖 <b>AI:</b>\n/ask [вопрос] — AI в группе\n/summary — сводка чата\n/translate [язык] [текст]\n\n📢 <b>Админ:</b>\n/setrules [текст]\n/rules — правила\n/groupstats — статистика",
        "en": "👥 <b>Group Commands:</b>\n\n🛡️ <b>Moderation:</b>\n/warn — warning\n/mute [min] — mute\n/ban — ban\n/kick — kick\n/purge [count] — delete\n/antispam on/off\n/guardian on/off\n\n🤖 <b>AI:</b>\n/ask [question] — AI in group\n/summary — chat summary\n/translate [lang] [text]\n\n📢 <b>Admin:</b>\n/setrules [text]\n/rules — rules\n/groupstats — stats",
        "it": "👥 <b>Comandi Gruppo:</b>\n\n🛡️ <b>Moderazione:</b>\n/warn — avvertimento\n/mute [min] — silenzia\n/ban — banna\n/kick — espelli\n/purge [num] — elimina\n/antispam on/off\n/guardian on/off\n\n🤖 <b>AI:</b>\n/ask [domanda] — AI nel gruppo\n/summary — riassunto chat\n/translate [lingua] [testo]\n\n📢 <b>Admin:</b>\n/setrules [testo]\n/rules — regole\n/groupstats — statistiche"
    }
    await update.message.reply_text(texts.get(lang, texts["en"]), parse_mode="HTML")

def _is_group(update):
    return update.effective_chat.type in ['group', 'supergroup']

async def _check_admin(update, context):
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return False
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    if member.status not in ['administrator', 'creator']:
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "admin_only"))
        return False
    return True

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        await update.message.reply_text(t(lang, "reply_needed"))
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(t(lang, "user_banned", user=target.first_name), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        await update.message.reply_text(t(lang, "reply_needed"))
        return
    target = update.message.reply_to_message.from_user
    await update.message.reply_text(t(lang, "user_warned", user=target.first_name), parse_mode="HTML")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        await update.message.reply_text(t(lang, "reply_needed"))
        return
    target = update.message.reply_to_message.from_user
    try:
        from telegram import ChatPermissions
        import datetime
        mins = int(context.args[0]) if context.args else 10
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=mins)
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, ChatPermissions(can_send_messages=False), until_date=until)
        await update.message.reply_text(t(lang, "user_muted", user=target.first_name), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        await update.message.reply_text(t(lang, "reply_needed"))
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(t(lang, "user_kicked", user=target.first_name), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "ask_usage"))
        return
    prompt = " ".join(context.args)
    msg = await update.message.reply_text(t(lang, "ai_thinking"))
    try:
        response = await ai_handler.generate_response(uid, prompt, system_prompt="You are a helpful assistant in a group chat. Be concise.")
        await msg.edit_text(response)
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    msg = await update.message.reply_text(t(lang, "summary_generating"))
    try:
        response = await ai_handler.generate_response(uid, "Please generate a brief summary of a typical group chat discussion. Be creative and helpful.", system_prompt="You generate chat summaries.")
        await msg.edit_text(f"📝 <b>Summary:</b>\n\n{response}", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if len(context.args) < 2:
        await update.message.reply_text(t(lang, "translate_usage"))
        return
    target_lang = context.args[0]
    text_to_translate = " ".join(context.args[1:])
    msg = await update.message.reply_text(t(lang, "translate_generating"))
    try:
        response = await ai_handler.generate_response(uid, f"Translate the following text to {target_lang}. Only output the translation, nothing else:\n\n{text_to_translate}", system_prompt="You are a translator. Only output the translated text.")
        await msg.edit_text(f"🌍 {response}")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return
    group = storage.get_group(update.effective_chat.id)
    rules = group.get("rules", "No rules set.")
    await update.message.reply_text(f"📋 <b>Rules:</b>\n\n{rules}", parse_mode="HTML")

async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    if not context.args:
        await update.message.reply_text("Usage: /setrules [text]")
        return
    group = storage.get_group(update.effective_chat.id)
    group["rules"] = " ".join(context.args)
    await storage.save()
    await update.message.reply_text("✅ Rules saved!")

async def guardian_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    if context.args and context.args[0].lower() == "on":
        group["guardian"] = True
        await storage.save()
        await update.message.reply_text(t(lang, "guardian_on"), parse_mode="HTML")
    elif context.args and context.args[0].lower() == "off":
        group["guardian"] = False
        await storage.save()
        await update.message.reply_text(t(lang, "guardian_off"), parse_mode="HTML")
    else:
        st = "ON ✅" if group.get("guardian") else "OFF ❌"
        await update.message.reply_text(f"🛡️ AI Guardian: {st}\nUsage: /guardian [on|off]")

async def groupstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return
    chat = update.effective_chat
    count = await context.bot.get_chat_member_count(chat.id)
    await update.message.reply_text(f"📊 <b>{chat.title}</b>\n\n👥 Members: {count}\n🛡️ Guardian: {'ON' if storage.get_group(chat.id).get('guardian') else 'OFF'}", parse_mode="HTML")
