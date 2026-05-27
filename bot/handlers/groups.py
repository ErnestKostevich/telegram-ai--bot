import html
import re
import time
import datetime
from collections import defaultdict
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import ai_handler
from bot.i18n import t
from bot.config import GROUP_HISTORY_LIMIT

MAX_RULES_LEN = 2000


URL_RE = re.compile(r"(?i)\b(https?://|www\.|t\.me/|telegram\.me/|tg://)\S+")

# AntiSpam: per (chat_id, user_id) → list of recent (text_hash, ts).
# A user repeating the same message 3+ times within 30s gets muted for 10 min.
SPAM_WINDOW_SEC = 30
SPAM_THRESHOLD = 3
SPAM_MUTE_MIN = 10
_spam_cache: dict = defaultdict(list)


async def grouphelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    texts = {
        "ru": ("👥 <b>Команды для групп:</b>\n\n"
               "🛡️ <b>Модерация:</b>\n"
               "/warn — предупреждение (3 = бан)\n"
               "/warnings — посмотреть варны\n"
               "/unwarn — снять варн\n"
               "/mute [мин] — мут\n"
               "/unmute — снять мут\n"
               "/ban /kick\n"
               "/purge [кол-во] — удалить N сообщений\n"
               "/antilink on/off — авто-удаление ссылок\n"
               "/antispam on/off\n"
               "/guardian on/off — AI защита\n\n"
               "🤖 <b>AI в группах:</b>\n"
               "/ask [вопрос] — AI отвечает\n"
               "/summary — сводка последних сообщений\n"
               "/translate [язык] [текст]\n"
               "@бот [текст] — упоминание = ответ\n\n"
               "📢 <b>Управление:</b>\n"
               "/setrules [текст] • /rules\n"
               "/welcome on/off [текст]\n"
               "/goodbye on/off [текст]\n"
               "/groupstats"),
        "en": ("👥 <b>Group Commands:</b>\n\n"
               "🛡️ <b>Moderation:</b>\n"
               "/warn — warn (3 = ban)\n"
               "/warnings — view warns\n"
               "/unwarn — remove warn\n"
               "/mute [min] — mute\n"
               "/unmute — unmute\n"
               "/ban /kick\n"
               "/purge [count] — delete N messages\n"
               "/antilink on/off — auto-delete links\n"
               "/antispam on/off\n"
               "/guardian on/off — AI protection\n\n"
               "🤖 <b>Group AI:</b>\n"
               "/ask [question]\n"
               "/summary — recap of recent messages\n"
               "/translate [lang] [text]\n"
               "@bot [text] — mention = reply\n\n"
               "📢 <b>Admin:</b>\n"
               "/setrules [text] • /rules\n"
               "/welcome on/off [text]\n"
               "/goodbye on/off [text]\n"
               "/groupstats"),
        "it": ("👥 <b>Comandi Gruppo:</b>\n\n"
               "🛡️ <b>Moderazione:</b>\n"
               "/warn — avvertimento (3 = ban)\n"
               "/warnings — vedi warn\n"
               "/unwarn — rimuovi warn\n"
               "/mute [min] — silenzia\n"
               "/unmute\n"
               "/ban /kick\n"
               "/purge [num] — elimina N messaggi\n"
               "/antilink on/off — auto-elimina link\n"
               "/antispam on/off\n"
               "/guardian on/off — protezione AI\n\n"
               "🤖 <b>AI nel gruppo:</b>\n"
               "/ask [domanda]\n"
               "/summary — riassunto messaggi\n"
               "/translate [lingua] [testo]\n"
               "@bot [testo] — menzione = risposta\n\n"
               "📢 <b>Admin:</b>\n"
               "/setrules [testo] • /rules\n"
               "/welcome on/off [testo]\n"
               "/goodbye on/off [testo]\n"
               "/groupstats"),
    }
    await update.message.reply_text(texts.get(lang, texts["en"]), parse_mode="HTML")


def _is_group(update):
    return update.effective_chat.type in ["group", "supergroup"]


async def _check_admin(update, context):
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return False
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    if member.status not in ["administrator", "creator"]:
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
    group = storage.get_group(update.effective_chat.id)
    warns = group.setdefault("warns", {})
    key = str(target.id)
    warns[key] = warns.get(key, 0) + 1
    count = warns[key]
    await storage.save()

    if count >= 3:
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            warns[key] = 0
            await storage.save()
            await update.message.reply_text(t(lang, "warn_banned", user=target.first_name), parse_mode="HTML")
            return
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
            return
    await update.message.reply_text(t(lang, "warn_count", user=target.first_name, count=count), parse_mode="HTML")


async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not _is_group(update):
        await update.message.reply_text(t(lang, "group_only"))
        return
    group = storage.get_group(update.effective_chat.id)
    warns = group.get("warns", {})
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        count = warns.get(str(target.id), 0)
        await update.message.reply_text(t(lang, "warn_show", user=target.first_name, count=count), parse_mode="HTML")
        return
    # List everyone with warns
    active = {uid: n for uid, n in warns.items() if n > 0}
    if not active:
        await update.message.reply_text(t(lang, "warn_none"))
        return
    text = t(lang, "warn_list_title")
    for uid_str, n in list(active.items())[:30]:
        text += f"• <code>{uid_str}</code>: {n}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        await update.message.reply_text(t(lang, "reply_needed"))
        return
    target = update.message.reply_to_message.from_user
    group = storage.get_group(update.effective_chat.id)
    warns = group.setdefault("warns", {})
    key = str(target.id)
    if warns.get(key, 0) > 0:
        warns[key] -= 1
        await storage.save()
        await update.message.reply_text(t(lang, "warn_removed", user=target.first_name, count=warns[key]), parse_mode="HTML")
    else:
        await update.message.reply_text(t(lang, "warn_none_user", user=target.first_name), parse_mode="HTML")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        await update.message.reply_text(t(lang, "reply_needed"))
        return
    target = update.message.reply_to_message.from_user
    try:
        mins = int(context.args[0]) if context.args else 10
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=mins)
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        await update.message.reply_text(t(lang, "user_muted_for", user=target.first_name, mins=mins), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not update.message.reply_to_message:
        await update.message.reply_text(t(lang, "reply_needed"))
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            ChatPermissions(
                can_send_messages=True, can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_invite_users=True,
            ),
        )
        await update.message.reply_text(t(lang, "user_unmuted", user=target.first_name), parse_mode="HTML")
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


async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    chat_id = update.effective_chat.id
    deleted = 0

    if update.message.reply_to_message:
        from_id = update.message.reply_to_message.message_id
        to_id = update.message.message_id
        # Safety cap: replying to a very old message shouldn't fire thousands
        # of delete API calls. Bound the range to the last 200 message ids.
        if to_id - from_id > 200:
            from_id = to_id - 200
        for mid in range(from_id, to_id + 1):
            try:
                await context.bot.delete_message(chat_id, mid)
                deleted += 1
            except Exception:
                pass
        await context.bot.send_message(chat_id, t(lang, "purge_done", count=deleted))
        return

    try:
        n = int(context.args[0]) if context.args else 10
        n = max(1, min(n, 100))
    except ValueError:
        await update.message.reply_text(t(lang, "purge_usage"))
        return
    base = update.message.message_id
    for mid in range(base, base - n - 1, -1):
        try:
            await context.bot.delete_message(chat_id, mid)
            deleted += 1
        except Exception:
            pass
    await context.bot.send_message(chat_id, t(lang, "purge_done", count=deleted))


async def antilink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    arg = context.args[0].lower() if context.args else None
    if arg == "on":
        group["antilink"] = True
        await storage.save()
        await update.message.reply_text(t(lang, "antilink_on"), parse_mode="HTML")
    elif arg == "off":
        group["antilink"] = False
        await storage.save()
        await update.message.reply_text(t(lang, "antilink_off"), parse_mode="HTML")
    else:
        st = "ON ✅" if group.get("antilink") else "OFF ❌"
        await update.message.reply_text(f"🔗 AntiLink: {st}\nUsage: /antilink [on|off]")


async def antispam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    arg = context.args[0].lower() if context.args else None
    if arg == "on":
        group["antispam"] = True
        await storage.save()
        await update.message.reply_text(t(lang, "antispam_on"), parse_mode="HTML")
    elif arg == "off":
        group["antispam"] = False
        await storage.save()
        await update.message.reply_text(t(lang, "antispam_off"), parse_mode="HTML")
    else:
        st = "ON ✅" if group.get("antispam") else "OFF ❌"
        await update.message.reply_text(f"🚨 AntiSpam: {st}\nUsage: /antispam [on|off]")


async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    if not context.args:
        st = "ON ✅" if group.get("welcome_enabled") else "OFF ❌"
        cur = group.get("welcome_msg") or "—"
        await update.message.reply_text(t(lang, "welcome_status", status=st, msg=cur), parse_mode="HTML")
        return
    first = context.args[0].lower()
    if first == "on":
        group["welcome_enabled"] = True
        if len(context.args) > 1:
            group["welcome_msg"] = " ".join(context.args[1:])
        await storage.save()
        await update.message.reply_text(t(lang, "welcome_on"))
    elif first == "off":
        group["welcome_enabled"] = False
        await storage.save()
        await update.message.reply_text(t(lang, "welcome_off"))
    else:
        group["welcome_msg"] = " ".join(context.args)
        group["welcome_enabled"] = True
        await storage.save()
        await update.message.reply_text(t(lang, "welcome_saved"))


async def goodbye_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    if not context.args:
        st = "ON ✅" if group.get("goodbye_enabled") else "OFF ❌"
        cur = group.get("goodbye_msg") or "—"
        await update.message.reply_text(t(lang, "goodbye_status", status=st, msg=cur), parse_mode="HTML")
        return
    first = context.args[0].lower()
    if first == "on":
        group["goodbye_enabled"] = True
        if len(context.args) > 1:
            group["goodbye_msg"] = " ".join(context.args[1:])
        await storage.save()
        await update.message.reply_text(t(lang, "goodbye_on"))
    elif first == "off":
        group["goodbye_enabled"] = False
        await storage.save()
        await update.message.reply_text(t(lang, "goodbye_off"))
    else:
        group["goodbye_msg"] = " ".join(context.args)
        group["goodbye_enabled"] = True
        await storage.save()
        await update.message.reply_text(t(lang, "goodbye_saved"))


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "ask_usage"))
        return
    prompt = " ".join(context.args)
    # Typing indicator for groups (we don't stream-edit in groups to avoid noise)
    try:
        from telegram.constants import ChatAction
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    except Exception:
        pass
    msg = await update.message.reply_text(t(lang, "ai_thinking"))
    # Inject group's shared memory if any
    group = storage.get_group(update.effective_chat.id) if _is_group(update) else {}
    group_memory = _build_group_memory_block(group)
    sys_prompt = "You are a helpful assistant in a group chat. Be concise (2-5 sentences). "
    if group_memory:
        sys_prompt += group_memory
    try:
        response = await ai_handler.generate_response(
            uid, prompt,
            system_prompt=sys_prompt,
            use_history=False,
        )
        await msg.edit_text(response, disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    messages = group.get("messages", [])

    if not messages:
        await update.message.reply_text(t(lang, "summary_empty"))
        return

    try:
        n = int(context.args[0]) if context.args else 50
        n = max(5, min(n, GROUP_HISTORY_LIMIT))
    except ValueError:
        n = 50

    recent = messages[-n:]
    formatted = "\n".join(f"{m['name']}: {m['text']}" for m in recent)

    msg = await update.message.reply_text(t(lang, "summary_generating"))
    try:
        response = await ai_handler.generate_response(
            uid,
            f"Summarize the following group chat conversation in 3-6 bullet points. "
            f"Capture the main topics, decisions, and any open questions. "
            f"Reply in the user's language.\n\n--- chat ---\n{formatted}",
            system_prompt="You produce concise group-chat summaries.",
            use_history=False,
        )
        if response.startswith("❌"):
            await msg.edit_text(response, parse_mode="HTML")
        else:
            await msg.edit_text(f"📝 <b>Summary</b> ({len(recent)} msgs)\n\n{response}", parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    # Support reply: /translate en (replied msg)
    text_to_translate = None
    target_lang = None
    if update.message.reply_to_message and update.message.reply_to_message.text and context.args:
        target_lang = context.args[0]
        text_to_translate = update.message.reply_to_message.text
    elif len(context.args) >= 2:
        target_lang = context.args[0]
        text_to_translate = " ".join(context.args[1:])
    else:
        await update.message.reply_text(t(lang, "translate_usage"))
        return
    msg = await update.message.reply_text(t(lang, "translate_generating"))
    try:
        response = await ai_handler.generate_response(
            uid,
            f"Translate the following text to {target_lang}. Output only the translation, nothing else:\n\n{text_to_translate}",
            system_prompt="You are a translator. Output only translated text.",
            use_history=False,
        )
        if response.startswith("❌"):
            await msg.edit_text(response, parse_mode="HTML")
        else:
            await msg.edit_text(f"🌍 {response}", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    rules = group.get("rules") or t(lang, "rules_empty")
    # Escape so admin-set rules with < or & don't break HTML
    await update.message.reply_text(
        f"📋 <b>{t(lang, 'rules_title')}</b>\n\n{html.escape(rules)}",
        parse_mode="HTML",
    )


async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update, context): return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "setrules_usage"))
        return
    group = storage.get_group(update.effective_chat.id)
    group["rules"] = " ".join(context.args)[:MAX_RULES_LEN]
    await storage.save()
    await update.message.reply_text(t(lang, "rules_saved"))


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


MAX_GROUP_MEMORY_ENTRIES = 30
MAX_GROUP_MEMORY_KEY_LEN = 50
MAX_GROUP_MEMORY_VAL_LEN = 500


async def groupmem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/groupmem save|get|list|del — shared memory injected into group AI prompts."""
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    group = storage.get_group(update.effective_chat.id)
    mem = group.setdefault("memory", {})

    args = context.args or []
    if not args:
        await update.message.reply_text(t(lang, "groupmem_usage"), parse_mode="HTML")
        return

    action = args[0].lower()

    if action == "list":
        if not mem:
            await update.message.reply_text(t(lang, "groupmem_empty"))
            return
        text = t(lang, "groupmem_list_title", count=len(mem))
        for k, v in list(mem.items())[:MAX_GROUP_MEMORY_ENTRIES]:
            text += f"• <b>{html.escape(k)}</b>: {html.escape(str(v))}\n"
        await update.message.reply_text(text, parse_mode="HTML")
        return

    if action == "get":
        if len(args) < 2:
            await update.message.reply_text(t(lang, "groupmem_get_usage"))
            return
        k = args[1]
        v = mem.get(k)
        if v:
            await update.message.reply_text(
                t(lang, "groupmem_value", k=html.escape(k), v=html.escape(str(v))),
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(t(lang, "groupmem_not_found", k=html.escape(k)))
        return

    # save/del require admin
    if not await _check_admin(update, context):
        return

    if action == "save":
        if len(args) < 3:
            await update.message.reply_text(t(lang, "groupmem_save_usage"))
            return
        k = args[1][:MAX_GROUP_MEMORY_KEY_LEN]
        v = " ".join(args[2:])[:MAX_GROUP_MEMORY_VAL_LEN]
        if k not in mem and len(mem) >= MAX_GROUP_MEMORY_ENTRIES:
            await update.message.reply_text(t(lang, "groupmem_full", max=MAX_GROUP_MEMORY_ENTRIES))
            return
        mem[k] = v
        await storage.save()
        await update.message.reply_text(
            t(lang, "groupmem_saved", k=html.escape(k), v=html.escape(v)),
            parse_mode="HTML",
        )
        return

    if action == "del":
        if len(args) < 2:
            await update.message.reply_text(t(lang, "groupmem_del_usage"))
            return
        k = args[1]
        if k in mem:
            del mem[k]
            await storage.save()
            await update.message.reply_text(t(lang, "groupmem_deleted", k=html.escape(k)))
        else:
            await update.message.reply_text(t(lang, "groupmem_not_found", k=html.escape(k)))
        return

    await update.message.reply_text(t(lang, "groupmem_usage"), parse_mode="HTML")


def _build_group_memory_block(group: dict) -> str:
    """Return a system-prompt fragment for the group's shared memory, or empty string."""
    mem = group.get("memory") or {}
    if not mem:
        return ""
    lines = ["Group context to remember:"]
    for k, v in list(mem.items())[:MAX_GROUP_MEMORY_ENTRIES]:
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"


async def groupstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_group(update):
        lang = storage.get_user(update.effective_user.id).get("language", "ru")
        await update.message.reply_text(t(lang, "group_only"))
        return
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    chat = update.effective_chat
    g = storage.get_group(chat.id)
    count = await context.bot.get_chat_member_count(chat.id)
    msgs = g.get("stats", {}).get("msgs", 0)
    history_len = len(g.get("messages", []))
    flags = []
    if g.get("guardian"): flags.append("🛡️ Guardian")
    if g.get("antilink"): flags.append("🔗 AntiLink")
    if g.get("antispam"): flags.append("🚨 AntiSpam")
    if g.get("welcome_enabled"): flags.append("👋 Welcome")
    if g.get("goodbye_enabled"): flags.append("👋 Goodbye")
    flags_text = " · ".join(flags) if flags else "—"
    await update.message.reply_text(
        t(lang, "groupstats_text", title=chat.title or "Group", members=count, msgs=msgs, buffer=history_len, flags=flags_text),
        parse_mode="HTML"
    )


# ============= Background pre-handler called for ANY group message =============

async def group_message_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tracks group messages: stats, history, antilink, member events."""
    msg = update.message
    if not msg:
        return
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        return

    group = storage.get_group(chat.id)

    # New chat members → welcome
    if msg.new_chat_members:
        if group.get("welcome_enabled") and group.get("welcome_msg"):
            for member in msg.new_chat_members:
                if member.is_bot:
                    continue
                text = group["welcome_msg"].replace("{name}", member.first_name or "").replace("{title}", chat.title or "")
                try:
                    await context.bot.send_message(chat.id, text)
                except Exception:
                    pass
        return

    if msg.left_chat_member:
        m = msg.left_chat_member
        if group.get("goodbye_enabled") and group.get("goodbye_msg") and not m.is_bot:
            text = group["goodbye_msg"].replace("{name}", m.first_name or "").replace("{title}", chat.title or "")
            try:
                await context.bot.send_message(chat.id, text)
            except Exception:
                pass
        return

    text = msg.text or msg.caption
    if not text:
        return

    # Stats
    stats = group.setdefault("stats", {"msgs": 0, "users": {}})
    stats["msgs"] = stats.get("msgs", 0) + 1
    users = stats.setdefault("users", {})
    uid_str = str(msg.from_user.id)
    users[uid_str] = users.get(uid_str, 0) + 1

    # AntiLink
    if group.get("antilink") and URL_RE.search(text):
        try:
            sender = await context.bot.get_chat_member(chat.id, msg.from_user.id)
            if sender.status not in ["administrator", "creator"]:
                await msg.delete()
                return
        except Exception:
            pass

    # AntiSpam: detect rapid repetition of the same message
    if group.get("antispam") and not text.startswith("/"):
        key = (chat.id, msg.from_user.id)
        now = time.time()
        text_hash = hash(text[:200])
        bucket = [(h, ts) for (h, ts) in _spam_cache[key] if now - ts < SPAM_WINDOW_SEC]
        bucket.append((text_hash, now))
        _spam_cache[key] = bucket
        same = sum(1 for (h, _) in bucket if h == text_hash)
        if same >= SPAM_THRESHOLD:
            try:
                sender = await context.bot.get_chat_member(chat.id, msg.from_user.id)
                if sender.status not in ["administrator", "creator"]:
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                    until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=SPAM_MUTE_MIN)
                    try:
                        await context.bot.restrict_chat_member(
                            chat.id, msg.from_user.id,
                            ChatPermissions(can_send_messages=False),
                            until_date=until,
                        )
                        # Reset the bucket so we don't repeat-fire after unmute
                        _spam_cache[key] = []
                        await context.bot.send_message(
                            chat.id,
                            t(storage.get_user(msg.from_user.id).get("language", "ru"),
                              "antispam_muted", user=msg.from_user.first_name, mins=SPAM_MUTE_MIN),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    return
            except Exception:
                pass

    # Append to history buffer (used by /summary)
    if not text.startswith("/"):
        name = msg.from_user.first_name or msg.from_user.username or str(msg.from_user.id)
        history = group.setdefault("messages", [])
        history.append({
            "name": name[:32],
            "text": text[:300],
            "ts": int(time.time()),
        })
        if len(history) > GROUP_HISTORY_LIMIT:
            del history[: len(history) - GROUP_HISTORY_LIMIT]
