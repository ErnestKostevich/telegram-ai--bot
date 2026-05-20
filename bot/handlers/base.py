import json
import io
from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.keyboards import get_main_keyboard, get_help_keyboard
from bot.i18n import t, get_text
from bot.config import BOT_VERSION, BOT_BUILD_DATE


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    user["state"] = None  # always reset any lingering interactive state
    if update.effective_user.username:
        user["username"] = update.effective_user.username
    lang = user.get("language", "ru")
    if update.effective_chat.type == "private":
        await update.message.reply_text(get_text(lang, "welcome"), parse_mode="HTML", reply_markup=get_main_keyboard(lang))
    else:
        await update.message.reply_text(get_text(lang, "welcome"), parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    lang = user.get("language", "ru")
    await update.message.reply_text(get_text(lang, "help"), parse_mode="HTML", reply_markup=get_help_keyboard(lang, user_id=user_id))


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(
        t(lang, "info", version=BOT_VERSION, date=BOT_BUILD_DATE),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(
        t(lang, "status",
          users=len(storage.data["users"]),
          groups=len(storage.data["groups"]),
          version=BOT_VERSION),
        parse_mode="HTML",
    )


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    await update.message.reply_text(t(lang, "version_text", version=BOT_VERSION, date=BOT_BUILD_DATE), parse_mode="HTML")


async def changelog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_user(update.effective_user.id).get("language", "ru")
    log = {
        "ru": (
            "📜 <b>Что нового в AI DISCO BOT</b>\n\n"
            f"<b>v{BOT_VERSION}</b> ({BOT_BUILD_DATE})\n"
            "• 🧠 Реальная память диалога — бот помнит контекст\n"
            "• 👁 Анализ фото (OpenAI / Anthropic / Gemini)\n"
            "• 📎 Анализ текстовых документов\n"
            "• 📝 Реальный <code>/summary</code> по последним сообщениям\n"
            "• 🛡 Реальный <code>/purge</code>, <code>/antilink</code>, <code>/warnings</code>\n"
            "• 👋 Welcome / Goodbye сообщения\n"
            "• 🚀 Broadcast с rate-limit\n"
            "• 💬 Команды <code>/clear</code>, <code>/feedback</code>, <code>/export</code>\n"
            "• 🌍 Перевод по reply: <code>/translate en</code> на сообщение\n"
            "• ⚡ Таймаут API 60с, обработка ошибок на трёх языках\n"
            "• 🎯 3-варн = автобан\n\n"
            "<b>v1.0 comeback</b>\n"
            "• BYOK: 10+ провайдеров AI\n"
            "• 3 языка: RU / EN / IT\n"
            "• VIP, генерация изображений, напоминания\n"
            "• Хранилище через GitHub API\n"
        ),
        "en": (
            "📜 <b>What's new in AI DISCO BOT</b>\n\n"
            f"<b>v{BOT_VERSION}</b> ({BOT_BUILD_DATE})\n"
            "• 🧠 Real conversation memory — bot remembers context\n"
            "• 👁 Photo analysis (OpenAI / Anthropic / Gemini)\n"
            "• 📎 Text document analysis\n"
            "• 📝 Real <code>/summary</code> based on recent messages\n"
            "• 🛡 Real <code>/purge</code>, <code>/antilink</code>, <code>/warnings</code>\n"
            "• 👋 Welcome / Goodbye messages\n"
            "• 🚀 Rate-limited broadcast\n"
            "• 💬 New commands: <code>/clear</code>, <code>/feedback</code>, <code>/export</code>\n"
            "• 🌍 Translate by reply: <code>/translate en</code> on a message\n"
            "• ⚡ 60s API timeout, errors localized\n"
            "• 🎯 3-warn = auto-ban\n\n"
            "<b>v1.0 comeback</b>\n"
            "• BYOK: 10+ AI providers\n"
            "• 3 languages: RU / EN / IT\n"
            "• VIP, image generation, reminders\n"
            "• Storage via GitHub API\n"
        ),
        "it": (
            "📜 <b>Novità in AI DISCO BOT</b>\n\n"
            f"<b>v{BOT_VERSION}</b> ({BOT_BUILD_DATE})\n"
            "• 🧠 Memoria di conversazione reale\n"
            "• 👁 Analisi foto (OpenAI / Anthropic / Gemini)\n"
            "• 📎 Analisi documenti di testo\n"
            "• 📝 Vero <code>/summary</code> dei messaggi recenti\n"
            "• 🛡 Vero <code>/purge</code>, <code>/antilink</code>, <code>/warnings</code>\n"
            "• 👋 Messaggi Welcome / Goodbye\n"
            "• 🚀 Broadcast con rate-limit\n"
            "• 💬 Nuovi: <code>/clear</code>, <code>/feedback</code>, <code>/export</code>\n"
            "• 🌍 Traduzione su reply: <code>/translate en</code>\n"
            "• ⚡ Timeout API 60s, errori localizzati\n"
            "• 🎯 3 warn = autoban\n\n"
            "<b>v1.0 comeback</b>\n"
            "• BYOK: 10+ provider AI\n"
            "• 3 lingue: RU / EN / IT\n"
            "• VIP, generazione immagini, promemoria\n"
            "• Storage via GitHub API\n"
        ),
    }
    await update.message.reply_text(log.get(lang, log["en"]), parse_mode="HTML")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = storage.get_user(uid)
    lang = user.get("language", "ru")
    export_data = {
        "user_id": uid,
        "username": user.get("username"),
        "language": user.get("language"),
        "ai_provider": user.get("ai_provider"),
        "ai_model": user.get("ai_model"),
        "vip": user.get("vip", False),
        "memory": user.get("memory", {}),
        "notes": user.get("notes", []),
        "tasks": user.get("tasks", []),
        "stats": user.get("stats", {}),
    }
    payload = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
    bio = io.BytesIO(payload)
    bio.name = f"ai_disco_bot_export_{uid}.json"
    await update.message.reply_document(document=bio, caption=t(lang, "export_caption"))


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    lang = user.get("language", "ru")
    xp = user.get("stats", {}).get("commands", 0) * 10
    level = xp // 100 + 1
    next_xp = level * 100
    progress = xp % 100
    from bot.handlers.vip_creator import check_vip
    from bot.ai import DEFAULT_MODELS
    is_vip = check_vip(user)
    vip = t(lang, "status_yes") if is_vip else t(lang, "status_no")
    provider = user.get("ai_provider", "gemini")
    model = user.get("ai_model") or DEFAULT_MODELS.get(provider, "default")
    text = t(lang, "profile_title",
             level=level, xp=xp, next_level_xp=next_xp,
             progress_bar="▓" * (progress // 10) + "░" * (10 - progress // 10),
             progress=progress,
             vip_status=vip,
             msgs=user.get("stats", {}).get("msgs", 0),
             provider=provider,
             model=model,
             notes=len(user.get("notes", [])),
             tasks=len(user.get("tasks", [])),
             memory=len(user.get("memory", {})),
             history=len(user.get("chat_history", [])))
    await update.message.reply_text(text, parse_mode="HTML")


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
        await update.message.reply_text(t(lang, "disco_off"), parse_mode="HTML")
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
