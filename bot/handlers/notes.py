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
