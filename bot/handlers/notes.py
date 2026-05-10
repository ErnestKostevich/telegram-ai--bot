from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t
import datetime

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "note_usage"))
        return
    text = " ".join(context.args)
    user["notes"].append({"text": text, "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
    await storage.save()
    await update.message.reply_text(t(lang, "note_saved", num=len(user["notes"])))

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not user["notes"]:
        await update.message.reply_text(t(lang, "notes_empty"))
        return
    text = t(lang, "notes_title", count=len(user["notes"]))
    for i, note in enumerate(user["notes"], 1):
        text += f"<b>#{i}</b> ({note['date']})\n{note['text']}\n\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "note_del_usage"))
        return
    try:
        num = int(context.args[0])
        if 1 <= num <= len(user["notes"]):
            user["notes"].pop(num - 1)
            await storage.save()
            await update.message.reply_text(t(lang, "note_deleted", num=num))
        else:
            await update.message.reply_text(t(lang, "note_not_found"))
    except ValueError:
        await update.message.reply_text(t(lang, "note_not_found"))

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if "tasks" not in user:
        user["tasks"] = []
    if not context.args:
        if not user["tasks"]:
            await update.message.reply_text(t(lang, "todo_empty"))
            return
        text = t(lang, "todo_title")
        for i, task in enumerate(user["tasks"], 1):
            s = "✅" if task.get("done") else "⏳"
            text += f"<b>{i}.</b> {s} {task['text']}\n"
        text += f"\n<code>/todo done [#]</code> | <code>/todo del [#]</code>"
        await update.message.reply_text(text, parse_mode="HTML")
        return
    action = context.args[0].lower()
    if action == "done" and len(context.args) > 1:
        try:
            idx = int(context.args[1]) - 1
            user["tasks"][idx]["done"] = True
            await storage.save()
            await update.message.reply_text(t(lang, "todo_done", num=idx+1))
        except (ValueError, IndexError):
            await update.message.reply_text(t(lang, "todo_bad_num"))
    elif action == "del" and len(context.args) > 1:
        try:
            idx = int(context.args[1]) - 1
            user["tasks"].pop(idx)
            await storage.save()
            await update.message.reply_text(t(lang, "todo_deleted"))
        except (ValueError, IndexError):
            await update.message.reply_text(t(lang, "todo_bad_num"))
    else:
        user["tasks"].append({"text": " ".join(context.args), "done": False})
        await storage.save()
        await update.message.reply_text(t(lang, "todo_added"))
