from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.config import CREATOR_ID
from bot.i18n import t
import datetime

# VIP Commands
async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    status = t(lang, "status_yes") if user["vip"] else t(lang, "status_no")
    await update.message.reply_text(t(lang, "vip_status", status=status), parse_mode="HTML")

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not user["vip"]:
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
    if not user["vip"]:
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
            "👑 <b>Выдача VIP</b>\n\n"
            "По ID: <code>/grant_vip 123456789</code>\n"
            "По username: <code>/grant_vip @username</code>\n"
            "Забрать: <code>/grant_vip @username remove</code>",
            parse_mode="HTML"
        )
        return

    target_arg = context.args[0]
    remove = len(context.args) > 1 and context.args[1].lower() == "remove"

    # Resolve target: by ID or by @username
    target_id = None
    if target_arg.startswith("@"):
        username = target_arg[1:].lower()
        # Search in our storage for a user with this username
        for uid_str, udata in storage.data["users"].items():
            if udata.get("username", "").lower() == username:
                target_id = int(uid_str)
                break
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь @{username} не найден в базе.\nОн должен хотя бы раз написать боту.")
            return
    else:
        try:
            target_id = int(target_arg)
        except ValueError:
            await update.message.reply_text("❌ Укажите числовой ID или @username.")
            return

    target_user = storage.get_user(target_id)
    if remove:
        target_user["vip"] = False
        await storage.save()
        await update.message.reply_text(f"🚫 VIP снят с пользователя {target_id}.")
    else:
        target_user["vip"] = True
        await storage.save()
        await update.message.reply_text(f"✅ VIP выдан пользователю <b>{target_id}</b>!", parse_mode="HTML")

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
