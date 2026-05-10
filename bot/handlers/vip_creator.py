from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.config import CREATOR_ID
from bot.i18n import t
import datetime

# Helper: check if VIP is active (auto-expire)
def check_vip(user):
    if not user.get("vip"):
        return False
    expires = user.get("vip_expires")
    if expires is None:
        return True  # forever
    if datetime.datetime.now().timestamp() > expires:
        user["vip"] = False
        user["vip_expires"] = None
        return False
    return True

# VIP Commands
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

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not check_vip(user):
        await update.message.reply_text(t(lang, "gen_vip_only"))
        return
    if len(context.args) < 2:
        await update.message.reply_text(t(lang, "remind_usage"))
        return
    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌")
        return
    text = " ".join(context.args[1:])
    target_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    storage.data["reminders"].append({
        "user_id": uid, "chat_id": update.effective_chat.id,
        "time": target_time.timestamp(), "text": text
    })
    await storage.save()
    await update.message.reply_text(t(lang, "remind_set", mins=minutes))

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
    text = f"⏰ <b>Reminders ({len(user_reminders)}):</b>\n\n"
    for i, r in enumerate(user_reminders, 1):
        dt = datetime.datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M")
        text += f"<b>#{i}</b> ({dt})\n{r['text']}\n\n"
    await update.message.reply_text(text, parse_mode="HTML")

# Creator Commands
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
            parse_mode="HTML"
        )
        return

    target_arg = context.args[0]
    action = context.args[1].lower() if len(context.args) > 1 else "month"

    # Resolve target
    target_id = None
    target_name = target_arg
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
    else:
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
            target_user["vip_expires"] = None  # forever
        await storage.save()
        await update.message.reply_text(f"✅ VIP выдан <b>{uname}</b> на <b>{label}</b>!", parse_mode="HTML")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌")
        return
    if not context.args:
        await update.message.reply_text("Использование: /broadcast [текст]")
        return
    text = " ".join(context.args)
    users = storage.data["users"]
    await update.message.reply_text(f"📤 Рассылка для {len(users)} пользователей...")
    success = 0
    for uid in users.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>Объявление:</b>\n\n{text}", parse_mode="HTML")
            success += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Отправлено: {success}/{len(users)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌")
        return
    users_data = storage.data["users"]
    users_count = len(users_data)
    groups_count = len(storage.data["groups"])
    vips = sum(1 for u in users_data.values() if u.get("vip"))
    total_cmds = sum(u.get("stats", {}).get("commands", 0) for u in users_data.values())
    text = (
        "📈 <b>Статистика бота:</b>\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"💎 VIP: {vips}\n"
        f"💬 Групп: {groups_count}\n"
        f"⚡ Команд использовано: {total_cmds}\n\n"
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
    for uid_str, udata in list(users_data.items())[:50]:  # Limit to 50
        vip = "💎" if udata.get("vip") else "  "
        uname = f"@{udata.get('username')}" if udata.get("username") else "—"
        cmds = udata.get("stats", {}).get("commands", 0)
        prov = udata.get("ai_provider", "—")
        text += f"{vip} <code>{uid_str}</code> {uname} | {cmds}cmd | {prov}\n"
    if len(users_data) > 50:
        text += f"\n<i>...и ещё {len(users_data) - 50}</i>"
    await update.message.reply_text(text, parse_mode="HTML")
