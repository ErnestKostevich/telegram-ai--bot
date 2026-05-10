from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import PROVIDERS
from bot.keyboards import get_main_keyboard, get_help_keyboard
from bot.i18n import get_text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    
    user_lang = user.get("language", "ru")
    
    text = get_text(user_lang, "welcome")
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_main_keyboard(user_lang))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    user_lang = user.get("language", "ru")
    
    text = get_text(user_lang, "help")
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_help_keyboard())

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>Информация о боте</b>\n\n"
        "Версия: 1.0.0 comeback\n"
        "Архитектура: BYOK (Bring Your Own Key)\n"
        "Хранилище: GitHub API Storage\n"
        "Создатель: @Ernest_Kostevich\n\n"
        "Бот поддерживает 10+ AI провайдеров, мультимодальный контекст и предоставляет богатый набор "
        "функций для групп, геймификации и модерации."
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user_lang = user.get("language", "ru")
    
    xp = user.get("stats", {}).get("commands", 0) * 10
    level = xp // 100 + 1
    next_level_xp = level * 100
    progress = xp % 100
    
    from bot.i18n import get_text
    vip_status = get_text(user_lang, "status_yes") if user.get("vip") else get_text(user_lang, "status_no")
    
    template = get_text(user_lang, "profile_title")
    text = template.format(
        level=level,
        xp=xp,
        next_level_xp=next_level_xp,
        progress_bar='▓' * (progress//10) + '░' * (10 - progress//10),
        progress=progress,
        vip_status=vip_status,
        msgs=user.get('stats', {}).get('msgs', 0),
        provider=user.get('ai_provider', 'gemini'),
        model=user.get('ai_model', 'По умолчанию')
    )
    
    await update.message.reply_text(text, parse_mode="HTML")

async def disco_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        status = "ВКЛЮЧЕН" if user.get("disco_mode") else "ВЫКЛЮЧЕН"
        await update.message.reply_text(f"🪩 <b>AI Disco Mode</b> сейчас {status}.\nИспользование: /disco [on|off]", parse_mode="HTML")
        return
        
    action = context.args[0].lower()
    if action == "on":
        user["disco_mode"] = True
        await update.message.reply_text("🪩 <b>AI Disco Mode ВКЛЮЧЕН!</b> Бот будет отвечать более творчески, с юмором и использовать много сленга/эмодзи.", parse_mode="HTML")
    elif action == "off":
        user["disco_mode"] = False
        await update.message.reply_text("🪩 AI Disco Mode ВЫКЛЮЧЕН. Бот вернулся в стандартный режим.")
        
    storage.save()

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_count = len(storage.data["users"])
    groups_count = len(storage.data["groups"])
    
    text = (
        "📊 <b>Статус системы</b>\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"💬 Групп: {groups_count}\n"
        "🗄 Хранилище: GitHub API (Активно)\n"
        "⚡ BYOK Модель: Активна"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not context.args:
        await update.message.reply_text("🌐 Использование / Usage / Uso: /lang [ru|en|it]")
        return
        
    lang = context.args[0].lower()
    if lang not in ["ru", "en", "it"]:
        await update.message.reply_text("❌ Доступные языки / Available languages / Lingue disponibili: ru, en, it")
        return
        
    user["language"] = lang
    storage.save()
    
    text = get_text(lang, "lang_changed")
    await update.message.reply_text(text, reply_markup=get_main_keyboard(lang))
