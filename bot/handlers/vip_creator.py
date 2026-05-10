from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.config import CREATOR_ID
import datetime

# VIP Commands
async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if user["vip"]:
        await update.message.reply_text("💎 <b>VIP Статус:</b> Активен\n\nВам доступны напоминания и другие бонусы!", parse_mode="HTML")
    else:
        await update.message.reply_text("💎 <b>VIP Статус:</b> Неактивен\n\nОбратитесь к создателю для получения статуса.", parse_mode="HTML")

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not user["vip"]:
        await update.message.reply_text("💎 Эта функция доступна только для VIP пользователей.")
        return
        
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /remind [минуты] [текст]")
        return
        
    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Количество минут должно быть числом.")
        return
        
    text = " ".join(context.args[1:])
    target_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    
    # Add to global reminders storage
    storage.data["reminders"].append({
        "user_id": user_id,
        "chat_id": update.effective_chat.id,
        "time": target_time.timestamp(),
        "text": text
    })
    
    await storage.save()
    await update.message.reply_text(f"⏰ Напоминание установлено! Сработает через {minutes} минут.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not user["vip"]:
        await update.message.reply_text("💎 Эта функция доступна только для VIP пользователей.")
        return
        
    user_reminders = [r for r in storage.data["reminders"] if r["user_id"] == user_id]
    
    if not user_reminders:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")
        return
        
    text = f"⏰ <b>Ваши напоминания ({len(user_reminders)}):</b>\n\n"
    for i, r in enumerate(user_reminders, 1):
        dt = datetime.datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M:%S")
        text += f"<b>#{i}</b> ({dt})\n{r['text']}\n\n"
        
    await update.message.reply_text(text, parse_mode="HTML")

# Creator Commands
async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌ Доступно только создателю бота.")
        return
        
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /grant_vip [user_id]")
        return
        
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом.")
        return
        
    target_user = storage.get_user(target_id)
    target_user["vip"] = True
    await storage.save()
    
    await update.message.reply_text(f"✅ VIP статус успешно выдан пользователю {target_id}!")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌ Доступно только создателю бота.")
        return
        
    if not context.args:
        await update.message.reply_text("Использование: /broadcast [текст]")
        return
        
    text = " ".join(context.args)
    users = storage.data["users"]
    
    await update.message.reply_text(f"📤 Начинаю рассылку для {len(users)} пользователей...")
    
    success = 0
    for uid in users.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>Объявление:</b>\n\n{text}", parse_mode="HTML")
            success += 1
        except Exception:
            pass
            
    await update.message.reply_text(f"✅ Рассылка завершена!\nУспешно отправлено: {success} из {len(users)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != CREATOR_ID:
        await update.message.reply_text("❌ Доступно только создателю бота.")
        return
        
    users = len(storage.data["users"])
    groups = len(storage.data["groups"])
    vips = sum(1 for u in storage.data["users"].values() if u.get("vip"))
    
    total_cmds = sum(u.get("stats", {}).get("commands", 0) for u in storage.data["users"].values())
    
    text = (
        "📈 <b>Глобальная статистика:</b>\n\n"
        f"Пользователей: {users}\n"
        f"VIP пользователей: {vips}\n"
        f"Групп: {groups}\n"
        f"Всего команд использовано: {total_cmds}"
    )
    
    await update.message.reply_text(text, parse_mode="HTML")
