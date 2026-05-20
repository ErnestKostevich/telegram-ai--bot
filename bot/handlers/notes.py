import datetime
import html
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.i18n import t

# Per-user caps to keep storage size bounded
MAX_NOTES = 100
MAX_NOTE_LEN = 2000
MAX_TASKS = 100
MAX_TASK_LEN = 1000


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    if not context.args:
        await update.message.reply_text(t(lang, "note_usage"))
        return
    if len(user["notes"]) >= MAX_NOTES:
        await update.message.reply_text(t(lang, "notes_full", max=MAX_NOTES))
        return
    text = " ".join(context.args)[:MAX_NOTE_LEN]
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
    # Escape user-supplied content so any <, >, & don't break HTML rendering
    for i, note in enumerate(user["notes"], 1):
        text += f"<b>#{i}</b> ({html.escape(note['date'])})\n{html.escape(note['text'])}\n\n"
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
    except ValueError:
        await update.message.reply_text(t(lang, "note_not_found"))
        return
    # Strict bounds: must be 1-indexed positive within range
    if num < 1 or num > len(user["notes"]):
        await update.message.reply_text(t(lang, "note_not_found"))
        return
    user["notes"].pop(num - 1)
    await storage.save()
    await update.message.reply_text(t(lang, "note_deleted", num=num))


def _todo_index(args, user):
    """Parse a 1-indexed task number from args[1] with strict validation.
    Returns int idx (0-indexed) or None on any bad input."""
    if len(args) < 2:
        return None
    try:
        num = int(args[1])
    except ValueError:
        return None
    if num < 1 or num > len(user.get("tasks", [])):
        return None
    return num - 1


async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    user.setdefault("tasks", [])

    if not context.args:
        if not user["tasks"]:
            await update.message.reply_text(t(lang, "todo_empty"))
            return
        text = t(lang, "todo_title")
        for i, task in enumerate(user["tasks"], 1):
            s = "✅" if task.get("done") else "⏳"
            text += f"<b>{i}.</b> {s} {html.escape(task.get('text', ''))}\n"
        text += "\n<code>/todo done [#]</code> | <code>/todo del [#]</code>"
        await update.message.reply_text(text, parse_mode="HTML")
        return

    action = context.args[0].lower()

    if action == "done":
        idx = _todo_index(context.args, user)
        if idx is None:
            await update.message.reply_text(t(lang, "todo_bad_num"))
            return
        user["tasks"][idx]["done"] = True
        await storage.save()
        await update.message.reply_text(t(lang, "todo_done", num=idx + 1))
        return

    if action == "del":
        idx = _todo_index(context.args, user)
        if idx is None:
            await update.message.reply_text(t(lang, "todo_bad_num"))
            return
        user["tasks"].pop(idx)
        await storage.save()
        await update.message.reply_text(t(lang, "todo_deleted"))
        return

    # Default: add task
    if len(user["tasks"]) >= MAX_TASKS:
        await update.message.reply_text(t(lang, "tasks_full", max=MAX_TASKS))
        return
    user["tasks"].append({"text": " ".join(context.args)[:MAX_TASK_LEN], "done": False})
    await storage.save()
    await update.message.reply_text(t(lang, "todo_added"))
