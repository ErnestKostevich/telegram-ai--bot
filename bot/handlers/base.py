import json
import io
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.keyboards import get_main_keyboard, get_help_keyboard
from bot.i18n import t, get_text
from bot.config import BOT_VERSION, BOT_BUILD_DATE


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    user["state"] = None
    if update.effective_user.username:
        user["username"] = update.effective_user.username
    lang = user.get("language", "ru")

    # Referral parsing: /start ref_<inviter_uid>
    if context.args and context.args[0].startswith("ref_") and not user.get("referred_by"):
        try:
            inviter_uid = int(context.args[0][4:])
            if inviter_uid != user_id:
                inviter = storage.data.get("users", {}).get(str(inviter_uid))
                if inviter is not None:
                    user["referred_by"] = inviter_uid
                    inviter["referrals"] = int(inviter.get("referrals", 0)) + 1
                    # Notify the inviter
                    try:
                        new_name = update.effective_user.first_name or "Friend"
                        inv_lang = inviter.get("language", "ru")
                        await context.bot.send_message(
                            inviter_uid,
                            t(inv_lang, "ref_inviter_notify", name=new_name, total=inviter["referrals"]),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
        except (ValueError, IndexError):
            pass

    if update.effective_chat.type == "private":
        await update.message.reply_text(get_text(lang, "welcome"), parse_mode="HTML", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text(get_text(lang, "welcome"), parse_mode="HTML")


async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a ready-to-share invite message with the user's referral link."""
    user = storage.get_user(update.effective_user.id)
    lang = user.get("language", "ru")
    try:
        me = await context.bot.get_me()
        bot_username = me.username
    except Exception:
        bot_username = "AI_DISCO_BOT"
    link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
    body = t(lang, "share_text", link=link)
    refs = int(user.get("referrals", 0))
    body += "\n\n" + t(lang, "share_stats", count=refs)
    await update.message.reply_text(body, parse_mode="HTML", disable_web_page_preview=True)


async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = storage.get_user(update.effective_user.id)
    lang = user.get("language", "ru")
    refs = int(user.get("referrals", 0))
    await update.message.reply_text(t(lang, "ref_stats", count=refs), parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    user["state"] = None  # reset any half-finished interactive flow
    lang = user.get("language", "ru")
    await update.message.reply_text(get_text(lang, "help"), parse_mode="HTML", reply_markup=get_help_keyboard(lang, user_id=user_id))


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(
        t(lang, "info", version=BOT_VERSION, date=BOT_BUILD_DATE),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(
        t(lang, "status",
          users=len(storage.data["users"]),
          groups=len(storage.data["groups"]),
          version=BOT_VERSION),
        parse_mode="HTML",
    )


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(t(lang, "version_text", version=BOT_VERSION, date=BOT_BUILD_DATE), parse_mode="HTML")


async def changelog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    log = {
        "ru": (
            "📜 <b>Что нового в AI DISCO BOT</b>\n\n"
            f"<b>v{BOT_VERSION}</b> — Wow Effect 🎉\n"
            "• 🌊 <b>Стриминг ответов</b> как в ChatGPT — текст появляется на лету\n"
            "• 🎙 <b>Голосовые сообщения</b> через Whisper (нужен OpenAI ключ)\n"
            "• 🎭 <b>/persona</b> — 8 характеров AI (comedian, philosopher, pirate…)\n"
            "• 🎰 <b>Мини-игры:</b> /slots /basket /football /dart /bowl\n"
            "• 🔮 <b>/today</b> — AI-прогноз дня\n"
            "• 🧠 <b>/quiz [тема]</b> — квиз с кнопками + счётом\n"
            "• 🏆 <b>/leaderboard</b> — топ пользователей\n"
            "• ⏰ <b>/unremind</b> — отменить напоминание\n"
            "• 🛑 <b>/cancel</b> — отменить текущее действие\n"
            "• 🗑 <b>/reset confirm</b> — удалить все мои данные\n"
            "• 🎨 Кнопочные пикеры для /setprovider /setkey /setmodel\n"
            "• 🔐 Безопасное сохранение ключа в группах (если бот admin)\n\n"
            "<b>v2.0.x</b>\n"
            "• 🧠 Память диалога • 👁 Vision • 📎 Документы\n"
            "• 👥 Реальный /summary, /purge, /antilink, /antispam\n"
            "• 🛡 20+ багфиксов: HTML-инъекции, гонки записи, лимиты памяти\n\n"
            "<b>v1.0 comeback</b>\n"
            "• BYOK: 10+ провайдеров AI • 3 языка • VIP\n"
        ),
        "en": (
            "📜 <b>What's new in AI DISCO BOT</b>\n\n"
            f"<b>v{BOT_VERSION}</b> — Wow Effect 🎉\n"
            "• 🌊 <b>Streaming responses</b> like ChatGPT\n"
            "• 🎙 <b>Voice messages</b> via Whisper (needs OpenAI key)\n"
            "• 🎭 <b>/persona</b> — 8 AI characters (comedian, philosopher, pirate…)\n"
            "• 🎰 <b>Mini-games:</b> /slots /basket /football /dart /bowl\n"
            "• 🔮 <b>/today</b> — AI fortune of the day\n"
            "• 🧠 <b>/quiz [topic]</b> — quiz with buttons + score\n"
            "• 🏆 <b>/leaderboard</b> — top users\n"
            "• ⏰ <b>/unremind</b> — cancel a reminder\n"
            "• 🛑 <b>/cancel</b> — cancel current action\n"
            "• 🗑 <b>/reset confirm</b> — wipe my data\n"
            "• 🎨 Button pickers for /setprovider /setkey /setmodel\n"
            "• 🔐 Safe key save in groups (if bot is admin)\n\n"
            "<b>v2.0.x</b>\n"
            "• 🧠 Conversation memory • 👁 Vision • 📎 Documents\n"
            "• 👥 Real /summary, /purge, /antilink, /antispam\n"
            "• 🛡 20+ bugfixes: HTML injection, write races, memory caps\n\n"
            "<b>v1.0 comeback</b>\n"
            "• BYOK: 10+ AI providers • 3 languages • VIP\n"
        ),
        "it": (
            "📜 <b>Novità in AI DISCO BOT</b>\n\n"
            f"<b>v{BOT_VERSION}</b> — Wow Effect 🎉\n"
            "• 🌊 <b>Risposte in streaming</b> come ChatGPT\n"
            "• 🎙 <b>Messaggi vocali</b> via Whisper (richiede chiave OpenAI)\n"
            "• 🎭 <b>/persona</b> — 8 personaggi AI\n"
            "• 🎰 <b>Mini-giochi:</b> /slots /basket /football /dart /bowl\n"
            "• 🔮 <b>/today</b> — oroscopo AI del giorno\n"
            "• 🧠 <b>/quiz [tema]</b> — quiz con bottoni\n"
            "• 🏆 <b>/leaderboard</b> — top utenti\n"
            "• ⏰ <b>/unremind</b> — annulla promemoria\n"
            "• 🛑 <b>/cancel</b> — annulla azione\n"
            "• 🗑 <b>/reset confirm</b> — elimina i miei dati\n"
            "• 🎨 Picker a bottoni per /setprovider /setkey /setmodel\n"
            "• 🔐 Salvataggio sicuro della chiave nei gruppi (se admin)\n\n"
            "<b>v2.0.x</b>\n"
            "• 🧠 Memoria • 👁 Vision • 📎 Documenti\n"
            "• 👥 /summary vero, /purge, /antilink, /antispam\n"
            "• 🛡 20+ fix: HTML, race condition, limiti memoria\n\n"
            "<b>v1.0 comeback</b>\n"
            "• BYOK: 10+ provider AI • 3 lingue • VIP\n"
        ),
    }
    await update.message.reply_text(log.get(lang, log["en"]), parse_mode="HTML")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    export_data = {
        "user_id": uid,
        "username": user.get("username"),
        "language": user.get("language"),
        "ai_provider": user.get("ai_provider"),
        "ai_model": user.get("ai_model"),
        "vip": user.get("vip", False),
        "memory": user.get("memory", {}),
        "notes": user.get("notes", []),
        "tasks": user.get("tasks", []),
        "stats": user.get("stats", {}),
    }
    payload = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
    bio = io.BytesIO(payload)
    bio.name = f"ai_disco_bot_export_{uid}.json"
    await update.message.reply_document(document=bio, caption=t(lang, "export_caption"))


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    lang = user.get("language", "ru")
    xp = user.get("stats", {}).get("commands", 0) * 10
    level = xp // 100 + 1
    next_xp = level * 100
    progress = xp % 100
    from bot.handlers.vip_creator import check_vip
    from bot.ai import DEFAULT_MODELS
    is_vip = check_vip(user)
    vip = t(lang, "status_yes") if is_vip else t(lang, "status_no")
    provider = user.get("ai_provider", "gemini")
    model = user.get("ai_model") or DEFAULT_MODELS.get(provider, "default")
    text = t(lang, "profile_title",
             level=level, xp=xp, next_level_xp=next_xp,
             progress_bar="▓" * (progress // 10) + "░" * (10 - progress // 10),
             progress=progress,
             vip_status=vip,
             msgs=user.get("stats", {}).get("msgs", 0),
             provider=provider,
             model=model,
             notes=len(user.get("notes", [])),
             tasks=len(user.get("tasks", [])),
             memory=len(user.get("memory", {})),
             history=len(user.get("chat_history", [])))
    await update.message.reply_text(text, parse_mode="HTML")


async def disco_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    lang = user.get("language", "ru")
    if not context.args:
        st = t(lang, "disco_enabled") if user.get("disco_mode") else t(lang, "disco_disabled")
        await update.message.reply_text(t(lang, "disco_status", status=st), parse_mode="HTML")
        return
    action = context.args[0].lower()
    if action == "on":
        user["disco_mode"] = True
        await update.message.reply_text(t(lang, "disco_on"), parse_mode="HTML")
    elif action == "off":
        user["disco_mode"] = False
        await update.message.reply_text(t(lang, "disco_off"), parse_mode="HTML")
    await storage.save()


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    if not context.args:
        from bot.keyboards import get_lang_keyboard
        await update.message.reply_text("🌐 Choose / Выберите / Scegli:", reply_markup=get_lang_keyboard())
        return
    lang = context.args[0].lower()
    if lang not in ["ru", "en", "it"]:
        await update.message.reply_text("❌ ru / en / it")
        return
    user["language"] = lang
    await storage.save()
    await update.message.reply_text(get_text(lang, "lang_changed"), reply_markup=get_main_keyboard(lang))


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abort any in-progress interactive flow (awaiting_setkey, awaiting_calc, etc.)."""
    user = storage.get_user(update.effective_user.id)
    lang = user.get("language", "ru")
    had_state = user.get("state")
    user["state"] = None
    await storage.save()
    if had_state:
        await update.message.reply_text(t(lang, "cancel_done"))
    else:
        await update.message.reply_text(t(lang, "cancel_nothing"))


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Top users by command activity. Public-safe — only first names + position."""
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    users = storage.data.get("users", {})
    ranked = sorted(
        users.items(),
        key=lambda kv: kv[1].get("stats", {}).get("commands", 0),
        reverse=True,
    )
    if not ranked:
        await update.message.reply_text(t(lang, "leaderboard_empty"))
        return
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 17
    own_uid = str(update.effective_user.id)
    lines = [t(lang, "leaderboard_title")]
    own_rank = None
    for i, (uid_str, udata) in enumerate(ranked[:10], 1):
        name = udata.get("username") or f"user{uid_str[-4:]}"
        if uid_str == own_uid:
            name = f"<b>{name}</b> (вы)" if lang == "ru" else f"<b>{name}</b> (you)" if lang == "en" else f"<b>{name}</b> (tu)"
            own_rank = i
        cmds = udata.get("stats", {}).get("commands", 0)
        xp = cmds * 10
        lines.append(f"{medals[i-1]} <b>{i}.</b> {name} — {xp} XP")
    # Show user's own rank if outside top 10
    if own_rank is None:
        for i, (uid_str, _) in enumerate(ranked, 1):
            if uid_str == own_uid:
                own_rank = i
                break
        if own_rank:
            lines.append("…")
            udata = ranked[own_rank - 1][1]
            cmds = udata.get("stats", {}).get("commands", 0)
            you = "вы" if lang == "ru" else ("you" if lang == "en" else "tu")
            lines.append(f"▫️ <b>{own_rank}.</b> ({you}) — {cmds * 10} XP")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Two-step user-data wipe. First call shows confirmation, second confirms."""
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if context.args and context.args[0].lower() == "confirm":
        # Export first
        try:
            await export_command(update, context)
        except Exception:
            pass
        # Then nuke
        uid_str = str(uid)
        storage.data.get("users", {}).pop(uid_str, None)
        # Drop reminders belonging to this user
        storage.data["reminders"] = [r for r in storage.data.get("reminders", []) if r.get("user_id") != uid]
        await storage.save()
        await update.message.reply_text(t(lang, "reset_done"))
        return
    await update.message.reply_text(t(lang, "reset_warn"), parse_mode="HTML")
