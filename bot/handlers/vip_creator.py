import asyncio
import datetime
import html
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.config import CREATOR_ID, BOT_VERSION
from bot.i18n import t


def check_vip(user: dict) -> bool:
    if not user.get("vip"):
        return False
    expires = user.get("vip_expires")
    if expires is None:
        return True
    if datetime.datetime.now().timestamp() > expires:
        user["vip"] = False
        user["vip_expires"] = None
        return False
    return True


async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    is_vip = check_vip(user)
    if is_vip:
        expires = user.get("vip_expires")
        if expires:
            exp_date = datetime.datetime.fromtimestamp(expires).strftime("%d.%m.%Y")
            exp_text = {"ru": f"до {exp_date}", "en": f"until {exp_date}", "it": f"fino al {exp_date}"}.get(lang, f"until {exp_date}")
        else:
            exp_text = {"ru": "навсегда ♾️", "en": "forever ♾️", "it": "per sempre ♾️"}.get(lang, "forever ♾️")
        status = f"👑 {t(lang, 'status_yes')} ({exp_text})"
    else:
        status = t(lang, "status_no")
    await update.message.reply_text(t(lang, "vip_status", status=status), parse_mode="HTML")


MAX_REMIND_MINUTES = 60 * 24 * 365  # 1 year — generous cap for natural-language dates


async def _ai_parse_reminder(uid: int, raw: str, now_iso: str):
    """Ask the AI to parse a natural-language reminder.
    Returns (minutes:int, text:str) or (None, error_msg:str)."""
    from bot.ai import ai_handler
    import json, re as _re
    prompt = (
        f"Current time (UTC): {now_iso}\n"
        f"User said: {raw!r}\n\n"
        "Extract a reminder time (in MINUTES from now, integer >= 1) and "
        "the cleaned reminder text from the user's input. The user may write "
        "in any language. Use the current time as reference for relative "
        "expressions like 'tomorrow', 'in 2 hours', 'next Monday 9am'.\n\n"
        "Reply with STRICT JSON only, no markdown, no commentary:\n"
        '{"minutes": <int>, "text": "<cleaned reminder body>"}\n\n'
        "If you can't parse a time, reply: "
        '{"minutes": 0, "text": "<reason>"}'
    )
    try:
        raw_resp = await ai_handler.generate_response(
            uid, prompt,
            system_prompt="You output ONLY valid JSON, no markdown fences, no extra text.",
            use_history=False,
        )
    except Exception as e:
        return None, f"AI error: {e}"
    if raw_resp.startswith("❌"):
        return None, raw_resp
    cleaned = _re.sub(r"^```(?:json)?|```$", "", raw_resp.strip(), flags=_re.MULTILINE).strip()
    try:
        obj = json.loads(cleaned)
        minutes = int(obj["minutes"])
        text = str(obj["text"]).strip()
        if minutes < 1:
            return None, text or "couldn't parse a future time"
        if minutes > MAX_REMIND_MINUTES:
            return None, "time too far in the future"
        return minutes, text[:2000]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        return None, f"bad AI output: {e}"


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not check_vip(user):
        await update.message.reply_text(t(lang, "gen_vip_only"))
        return
    if not context.args:
        await update.message.reply_text(t(lang, "remind_usage"))
        return

    minutes: int | None = None
    text: str = ""

    # Fast path 1: classic "/remind 30 текст напоминания"
    if len(context.args) >= 2:
        try:
            m = int(context.args[0])
            if 1 <= m <= MAX_REMIND_MINUTES:
                minutes = m
                text = " ".join(context.args[1:])[:2000]
        except ValueError:
            pass

    # Slow path: natural language → AI parse
    if minutes is None:
        raw = " ".join(context.args)
        # Tell the user we're parsing (AI takes 1-3s)
        thinking = await update.message.reply_text(t(lang, "remind_parsing"))
        # Need a user key for the AI parse — surface a friendly hint if missing
        provider = user.get("ai_provider", "gemini")
        if not user.get("api_keys", {}).get(provider):
            await thinking.edit_text(t(lang, "remind_needs_key"), parse_mode="HTML")
            return
        import datetime as _dt
        now_iso = _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        parsed_minutes, parsed_text_or_err = await _ai_parse_reminder(uid, raw, now_iso)
        if parsed_minutes is None:
            await thinking.edit_text(
                t(lang, "remind_parse_fail", err=html.escape(str(parsed_text_or_err))[:300]),
                parse_mode="HTML",
            )
            return
        minutes = parsed_minutes
        text = parsed_text_or_err
        # Replace the thinking message with the success later
        try:
            await thinking.delete()
        except Exception:
            pass

    if not text:
        await update.message.reply_text(t(lang, "remind_usage"))
        return

    target_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    storage.data["reminders"].append({
        "user_id": uid, "chat_id": update.effective_chat.id,
        "time": target_time.timestamp(), "text": text,
    })
    await storage.save()
    # Render time in a friendly form
    when_str = _humanize_minutes(minutes, lang)
    await update.message.reply_text(
        t(lang, "remind_set_smart", when=when_str, text=html.escape(text)),
        parse_mode="HTML",
    )


def _humanize_minutes(m: int, lang: str) -> str:
    """Turn N minutes into a friendly relative string."""
    if m < 60:
        unit = {"ru": "мин", "en": "min", "it": "min"}.get(lang, "min")
        return f"{m} {unit}"
    if m < 60 * 24:
        h = m // 60
        rem = m % 60
        h_unit = {"ru": "ч", "en": "h", "it": "h"}.get(lang, "h")
        if rem == 0:
            return f"{h}{h_unit}"
        return f"{h}{h_unit} {rem}{'мин' if lang == 'ru' else 'min'}"
    days = m // (60 * 24)
    d_unit = {"ru": "д", "en": "d", "it": "g"}.get(lang, "d")
    return f"{days}{d_unit}"


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not check_vip(user):
        await update.message.reply_text(t(lang, "gen_vip_only"))
        return
    user_reminders = [r for r in storage.data["reminders"] if r["user_id"] == uid]
    if not user_reminders:
        await update.message.reply_text(t(lang, "reminders_empty"))
        return
    text = t(lang, "reminders_title", count=len(user_reminders))
    for i, r in enumerate(user_reminders, 1):
        dt = datetime.datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M")
        text += f"<b>#{i}</b> ({dt})\n{html.escape(r.get('text', ''))}\n\n"
    text += "\n<i>" + t(lang, "reminders_hint") + "</i>"
    await update.message.reply_text(text, parse_mode="HTML")


async def unremind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    user_reminders = [r for r in storage.data["reminders"] if r["user_id"] == uid]
    if not user_reminders:
        await update.message.reply_text(t(lang, "reminders_empty"))
        return
    # /unremind all
    if context.args and context.args[0].lower() == "all":
        storage.data["reminders"] = [r for r in storage.data["reminders"] if r["user_id"] != uid]
        await storage.save()
        await update.message.reply_text(t(lang, "unremind_all", count=len(user_reminders)))
        return
    if not context.args:
        await update.message.reply_text(t(lang, "unremind_usage"))
        return
    try:
        num = int(context.args[0])
    except ValueError:
        await update.message.reply_text(t(lang, "unremind_usage"))
        return
    if num < 1 or num > len(user_reminders):
        await update.message.reply_text(t(lang, "unremind_bad_num", max=len(user_reminders)))
        return
    target = user_reminders[num - 1]
    try:
        storage.data["reminders"].remove(target)
        await storage.save()
        await update.message.reply_text(t(lang, "unremind_ok", num=num))
    except ValueError:
        await update.message.reply_text(t(lang, "unremind_bad_num", max=len(user_reminders)))


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "feedback_usage"))
        return
    text = " ".join(context.args)[:2000]
    uname = update.effective_user.username
    uname_disp = f"@{uname}" if uname else (update.effective_user.first_name or str(uid))
    if CREATOR_ID:
        try:
            # Escape user-supplied text & username so notification renders safely
            await context.bot.send_message(
                CREATOR_ID,
                f"💬 <b>Feedback</b>\nFrom: {html.escape(uname_disp)} (<code>{uid}</code>)\nLang: {lang}\n\n{html.escape(text)}",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await update.message.reply_text(t(lang, "feedback_thanks"))


# ============== Creator-only ==============

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌")
        return
    if len(context.args) < 1:
        await update.message.reply_text(
            "👑 <b>Управление VIP</b>\n\n"
            "<b>Выдать:</b>\n"
            "<code>/grant_vip @user week</code> — на неделю\n"
            "<code>/grant_vip @user month</code> — на месяц\n"
            "<code>/grant_vip @user year</code> — на год\n"
            "<code>/grant_vip @user forever</code> — навсегда\n\n"
            "<b>Забрать:</b>\n"
            "<code>/grant_vip @user remove</code>\n\n"
            "Можно использовать @username или числовой ID.",
            parse_mode="HTML",
        )
        return

    target_arg = context.args[0]
    action = context.args[1].lower() if len(context.args) > 1 else "month"

    target_id = None
    if target_arg.startswith("@"):
        username = target_arg[1:].lower()
        for uid_str, udata in storage.data["users"].items():
            if udata.get("username", "").lower() == username:
                target_id = int(uid_str)
                break
        if not target_id:
            await update.message.reply_text(f"❌ @{username} не найден в базе.")
            return
    else:
        try:
            target_id = int(target_arg)
        except ValueError:
            await update.message.reply_text("❌ Укажите @username или числовой ID.")
            return

    target_user = storage.get_user(target_id)
    uname = f"@{target_user.get('username', target_id)}"

    if action == "remove":
        target_user["vip"] = False
        target_user["vip_expires"] = None
        await storage.save()
        await update.message.reply_text(f"🚫 VIP снят с <b>{uname}</b>", parse_mode="HTML")
        return

    durations = {
        "week": (7, "7 дней"),
        "month": (30, "30 дней"),
        "year": (365, "1 год"),
        "forever": (0, "навсегда"),
    }
    if action not in durations:
        await update.message.reply_text("❌ Доступно: week, month, year, forever, remove")
        return

    days, label = durations[action]
    target_user["vip"] = True
    if days > 0:
        expires = datetime.datetime.now() + datetime.timedelta(days=days)
        target_user["vip_expires"] = expires.timestamp()
    else:
        target_user["vip_expires"] = None
    await storage.save()
    await update.message.reply_text(f"✅ VIP выдан <b>{uname}</b> на <b>{label}</b>!", parse_mode="HTML")

    # Notify the recipient if possible
    try:
        notif = {
            "ru": f"🎉 <b>Вам выдан VIP-статус!</b>\nСрок: <b>{label}</b>\n\n💎 Доступно: генерация изображений, анализ фото и документов, напоминания.",
            "en": f"🎉 <b>You've been granted VIP!</b>\nDuration: <b>{label}</b>\n\n💎 Unlocked: image generation, photo/doc analysis, reminders.",
            "it": f"🎉 <b>Hai ottenuto il VIP!</b>\nDurata: <b>{label}</b>\n\n💎 Sbloccato: generazione immagini, analisi foto/doc, promemoria.",
        }
        target_lang = target_user.get("language", "ru")
        await context.bot.send_message(target_id, notif.get(target_lang, notif["en"]), parse_mode="HTML")
    except Exception:
        pass


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌")
        return
    if not context.args:
        await update.message.reply_text("Использование: /broadcast [текст]")
        return
    raw = " ".join(context.args)
    # Escape user input so unbalanced <, >, & don't break HTML parsing for every recipient
    safe = html.escape(raw)
    text = f"📢 <b>Объявление:</b>\n\n{safe}"
    users = list(storage.data["users"].keys())
    total = len(users)
    progress = await update.message.reply_text(f"📤 Рассылка для {total} пользователей...")
    success = 0
    failed = 0
    for i, uid in enumerate(users, 1):
        try:
            await context.bot.send_message(chat_id=int(uid), text=text, parse_mode="HTML")
            success += 1
        except Exception:
            failed += 1
        # Telegram limit: ~25 msg/sec → 40ms sleep
        await asyncio.sleep(0.05)
        if i % 25 == 0:
            try:
                await progress.edit_text(f"📤 {i}/{total}  ✅ {success}  ❌ {failed}")
            except Exception:
                pass
    await progress.edit_text(f"✅ Готово: <b>{success}</b>/{total}  ❌ ошибок: {failed}", parse_mode="HTML")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌")
        return
    users_data = storage.data["users"]
    users_count = len(users_data)
    groups_count = len(storage.data["groups"])
    vips = sum(1 for u in users_data.values() if u.get("vip"))
    total_cmds = sum(u.get("stats", {}).get("commands", 0) for u in users_data.values())
    total_msgs = sum(u.get("stats", {}).get("msgs", 0) for u in users_data.values())
    total_notes = sum(len(u.get("notes", [])) for u in users_data.values())
    total_memory = sum(len(u.get("memory", {})) for u in users_data.values())

    # Provider breakdown
    providers: dict = {}
    for u in users_data.values():
        p = u.get("ai_provider", "?")
        providers[p] = providers.get(p, 0) + 1
    prov_text = "\n".join(f"  • {p}: {n}" for p, n in sorted(providers.items(), key=lambda x: -x[1])[:6])

    active_reminders = len(storage.data.get("reminders", []))

    text = (
        f"📈 <b>Статистика AI DISCO BOT v{BOT_VERSION}</b>\n\n"
        f"👥 Пользователей: <b>{users_count}</b>\n"
        f"💎 VIP: <b>{vips}</b>\n"
        f"💬 Групп: <b>{groups_count}</b>\n"
        f"⚡ Команд: <b>{total_cmds}</b>\n"
        f"📨 Сообщений: <b>{total_msgs}</b>\n"
        f"📝 Заметок: <b>{total_notes}</b>\n"
        f"🧠 Memory entries: <b>{total_memory}</b>\n"
        f"⏰ Активных напоминаний: <b>{active_reminders}</b>\n\n"
        f"<b>Топ провайдеров:</b>\n{prov_text}\n\n"
        f"📋 Список: /users"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌")
        return
    users_data = storage.data["users"]
    if not users_data:
        await update.message.reply_text("📭 Пользователей нет.")
        return
    text = f"👥 <b>Пользователи ({len(users_data)}):</b>\n\n"
    sorted_users = sorted(
        users_data.items(),
        key=lambda x: x[1].get("stats", {}).get("commands", 0),
        reverse=True,
    )
    for uid_str, udata in sorted_users[:50]:
        vip = "💎" if udata.get("vip") else "  "
        uname = f"@{udata.get('username')}" if udata.get("username") else "—"
        cmds = udata.get("stats", {}).get("commands", 0)
        prov = udata.get("ai_provider", "—")
        text += f"{vip} <code>{uid_str}</code> {uname} | {cmds}cmd | {prov}\n"
    if len(users_data) > 50:
        text += f"\n<i>...и ещё {len(users_data) - 50}</i>"
    await update.message.reply_text(text, parse_mode="HTML")
