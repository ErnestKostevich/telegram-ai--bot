from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.keyboards import get_main_keyboard, get_help_keyboard
from bot.i18n import t, get_text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    lang = user.get("language", "ru")
    await update.message.reply_text(get_text(lang, "welcome"), parse_mode="HTML", reply_markup=get_main_keyboard(lang))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    lang = user.get("language", "ru")
    await update.message.reply_text(get_text(lang, "help"), parse_mode="HTML", reply_markup=get_help_keyboard(lang))

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(t(lang, "info"), parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(
        t(lang, "status", users=len(storage.data["users"]), groups=len(storage.data["groups"])),
        parse_mode="HTML"
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    lang = user.get("language", "ru")
    xp = user.get("stats", {}).get("commands", 0) * 10
    level = xp // 100 + 1
    next_xp = level * 100
    progress = xp % 100
    vip = t(lang, "status_yes") if user.get("vip") else t(lang, "status_no")
    await update.message.reply_text(
        t(lang, "profile_title",
          level=level, xp=xp, next_level_xp=next_xp,
          progress_bar='▓'*(progress//10)+'░'*(10-progress//10), progress=progress,
          vip_status=vip, msgs=user.get('stats',{}).get('msgs',0),
          provider=user.get('ai_provider','gemini'), model=user.get('ai_model','default')),
        parse_mode="HTML"
    )

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
        await update.message.reply_text(t(lang, "disco_off"))
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
