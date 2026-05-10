from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
import datetime

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        await update.message.reply_text("Использование: /note [текст]")
        return
        
    text = " ".join(context.args)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user["notes"].append({
        "text": text,
        "date": date_str
    })
    
    await storage.save()
    num = len(user["notes"])
    await update.message.reply_text(f"✅ Заметка #{num} сохранена!")

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not user["notes"]:
        await update.message.reply_text("📭 У вас нет заметок.")
        return
        
    text = f"📝 <b>Ваши заметки ({len(user['notes'])}):</b>\n\n"
    for i, note in enumerate(user["notes"], 1):
        text += f"<b>#{i}</b> ({note['date']})\n{note['text']}\n\n"
        
    await update.message.reply_text(text, parse_mode="HTML")

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        await update.message.reply_text("Использование: /delnote [номер]")
        return
        
    try:
        num = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Номер должен быть числом.")
        return
        
    if 1 <= num <= len(user["notes"]):
        deleted = user["notes"].pop(num - 1)
        await storage.save()
        await update.message.reply_text(f"✅ Заметка #{num} удалена:\n\n{deleted['text']}")
    else:
        await update.message.reply_text(f"❌ Заметка #{num} не найдена.")

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if "tasks" not in user:
        user["tasks"] = []
        
    if not context.args:
        if not user["tasks"]:
            await update.message.reply_text("📭 Ваш список задач пуст. Добавьте задачу: /todo [текст]")
            return
            
        text = "📋 <b>Ваши задачи:</b>\n\n"
        for i, task in enumerate(user["tasks"], 1):
            status = "✅" if task.get("done") else "⏳"
            text += f"<b>{i}.</b> {status} {task['text']}\n"
        text += "\nЗавершить задачу: <code>/todo done [номер]</code>\nУдалить задачу: <code>/todo del [номер]</code>"
        await update.message.reply_text(text, parse_mode="HTML")
        return
        
    action = context.args[0].lower()
    
    if action == "done" and len(context.args) > 1:
        try:
            index = int(context.args[1]) - 1
            user["tasks"][index]["done"] = True
            await storage.save()
            await update.message.reply_text(f"✅ Задача #{index+1} выполнена!")
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Укажите правильный номер задачи.")
    elif action == "del" and len(context.args) > 1:
        try:
            index = int(context.args[1]) - 1
            task = user["tasks"].pop(index)
            await storage.save()
            await update.message.reply_text(f"🗑 Задача удалена: {task['text']}")
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Укажите правильный номер задачи.")
    else:
        task_text = " ".join(context.args)
        user["tasks"].append({"text": task_text, "done": False})
        await storage.save()
        await update.message.reply_text("✅ Задача добавлена!")
