import os
import logging
import asyncio
import random
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction
from database import DBManager, init_db
from ai_providers import get_provider, PROVIDERS_LIST

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
db = DBManager()

# --- Helpers ---

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        return update.effective_user.id == ADMIN_ID
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🤖 AI Чат"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("📝 Заметки"), KeyboardButton("📋 Задачи")],
        [KeyboardButton("🎲 Игры"), KeyboardButton("👤 Профиль")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Personal Tools (Notes, Memory, VIP) ---

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Используйте: `/note [текст]`")
        return
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    notes = list(user.notes or [])
    notes.append({"text": " ".join(context.args), "date": datetime.now().isoformat()})
    await db.update_user(user_id, notes=notes)
    await update.message.reply_text("✅ Заметка сохранена!")

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    notes = user.notes or []
    if not notes:
        await update.message.reply_text("📝 У вас нет заметок.")
        return
    text = "📝 **Ваши заметки:**\n\n" + "\n".join([f"{i+1}. {n['text']}" for i, n in enumerate(notes)])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Используйте: `/delnote [номер]`")
        return
    idx = int(context.args[0]) - 1
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    notes = list(user.notes or [])
    if 0 <= idx < len(notes):
        notes.pop(idx)
        await db.update_user(user_id, notes=notes)
        await update.message.reply_text("✅ Заметка удалена!")
    else:
        await update.message.reply_text("❌ Неверный номер заметки.")

async def memorysave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: `/memorysave [ключ] [значение]`")
        return
    key, val = context.args[0], " ".join(context.args[1:])
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    mem = dict(user.memory or {})
    mem[key] = val
    await db.update_user(user_id, memory=mem)
    await update.message.reply_text(f"🧠 Сохранено: `{key}`")

async def memoryget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    key = context.args[0]
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    mem = user.memory or {}
    val = mem.get(key, "❌ Не найдено.")
    await update.message.reply_text(f"🧠 `{key}`: {val}")

async def vip_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    status = "💎 VIP Активен" if user.vip else "❌ VIP не активен"
    until = f"\nДо: {user.vip_until.strftime('%d.%m.%Y')}" if user.vip_until else ""
    await update.message.reply_text(f"👤 **Статус:** {status}{until}", parse_mode=ParseMode.MARKDOWN)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Используйте: `/remind [минуты] [текст]`")
        return
    mins, text = int(context.args[0]), " ".join(context.args[1:])
    user_id = update.effective_user.id
    
    # In a real bot, we'd use JobQueue. Here we just save to DB.
    user = await db.get_user(user_id)
    reminders = list(user.reminders or [])
    reminders.append({"text": text, "time": (datetime.now() + timedelta(minutes=mins)).isoformat()})
    await db.update_user(user_id, reminders=reminders)
    await update.message.reply_text(f"⏰ Напоминание установлено через {mins} мин.")# --- AI Guardian & Disco Mode ---

async def ai_guardian_check(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    chat_id = update.effective_chat.id
    group = await db.get_group(chat_id)
    if not group.ai_guardian: return False
    
    # Simple heuristic for toxicity/spam (in real bot, use AI)
    toxic_words = ['скам', 'scam', 'крипта', 'заработок', 'выигрыш']
    if any(word in text.lower() for word in toxic_words):
        await update.message.delete()
        await update.message.reply_text(f"🛡 **AI Guardian:** Сообщение от {update.effective_user.first_name} удалено (подозрение на спам/мошенничество).")
        return True
    return False

async def disco_mode_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = await db.get_group(chat_id)
    if not group.disco_mode: return
    
    # 5% chance to trigger a disco event
    if random.random() < 0.05:
        events = [
            "🕺 **DISCO TIME!** Все танцуют! +10 XP всем активным!",
            "🎲 **Random Challenge:** Кто первым напишет 'DISCO', получит 50 XP!",
            "✨ **Vibe Check:** Чат сегодня просто космос!"
        ]
        await update.message.reply_text(random.choice(events))

# --- AI Logic ---

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_settings = await db.get_user_settings(user_id)
    active_prov = user_settings.active_provider if user_settings and user_settings.active_provider else "Не выбран"
    
    keyboard = [
        [InlineKeyboardButton("🌐 Выбрать провайдера", callback_data='set_provider')],
        [InlineKeyboardButton("🔑 Ввести API ключ", callback_data='set_key_prompt')],
        [InlineKeyboardButton("🗑 Очистить историю AI", callback_data='clear_chat')]
    ]
    text = f"⚙️ **Настройки AI**\n\nТекущий провайдер: `{str(active_prov).upper()}`"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def set_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: `/key [провайдер] [ключ]`")
        return
    provider, api_key = context.args[0].lower(), context.args[1]
    user_id = update.effective_user.id
    await db.update_user_key(user_id, provider, api_key)
    await db.update_user_settings(user_id, active_provider=provider)
    await update.message.reply_text(f"✅ Ключ для **{provider.upper()}** сохранен!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):    user = update.effective_user
    await db.get_user(user.id, user.username, user.first_name)
    
    if update.effective_chat.type == 'private':
        text = (
            f"🚀 **AI DISCO BOT v1.0.0 Comeback**\n\n"
            f"Привет, {user.first_name}! Я вернулся и стал мощнее, чем когда-либо.\n\n"
            "🏠 **Базовые команды:**\n"
            "/start - Запуск\n"
            "/help - Список всех команд\n"
            "/info - О проекте\n"
            "/status - Статус системы\n\n"
            "Используй меню ниже для навигации!"
        )
        await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await db.get_group(update.effective_chat.id, update.effective_chat.title)
        await update.message.reply_text("🤖 AI DISCO BOT активирован в группе! /grouphelp для команд.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 **Список команд:**\n\n"
        "💬 **AI:** /ai, /settings, /key\n"
        "📝 **Заметки:** /note, /notes, /delnote\n"
        "🧠 **Память:** /memorysave, /memoryget, /memorylist\n"
        "💎 **VIP:** /vip, /remind, /reminders\n"
        "🎮 **Активность:** /daily, /profile, /dice, /joke\n"
        "🛡 **Группы:** /grouphelp, /setai, /warn, /mute, /ban"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# --- Moderation & Group Functions ---

async def grouphelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👥 **Команды группы:**\n"
        "/rank - Ваш уровень\n"
        "/leaderboard - Топ чата\n"
        "/rules - Правила чата\n\n"
        "🛡 **Модерация (Админы):**\n"
        "/warn, /mute, /ban, /kick, /purge\n"
        "/setai [on/off], /welcome [on/off]\n"
        "/antilink [on/off], /antispam [on/off]"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение пользователя, которого хотите предупредить.")
        return
    
    target_user = update.message.reply_to_message.from_user
    group = await db.get_group(update.effective_chat.id)
    warns = dict(group.warns or {})
    user_id_str = str(target_user.id)
    warns[user_id_str] = warns.get(user_id_str, 0) + 1
    
    await db.update_group(update.effective_chat.id, warns=warns)
    
    reason = " ".join(context.args) if context.args else "не указана"
    await update.message.reply_text(f"⚠️ Пользователь {target_user.mention_markdown()} получил предупреждение ({warns[user_id_str]}/3).\nПричина: {reason}", parse_mode=ParseMode.MARKDOWN)
    
    if warns[user_id_str] >= 3:
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
            await update.message.reply_text(f"🚫 {target_user.first_name} забанен за достижение лимита предупреждений.")
        except:
            await update.message.reply_text("❌ Не удалось забанить пользователя (проверьте права бота).")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message: return
    
    minutes = int(context.args[0]) if context.args and context.args[0].isdigit() else 60
    until = datetime.now() + timedelta(minutes=minutes)
    
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            update.message.reply_to_message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await update.message.reply_text(f"🔇 Пользователь замучен на {minutes} мин.")
    except:
        await update.message.reply_text("❌ Ошибка при муте.")

async def purge_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    count = int(context.args[0]) if context.args and context.args[0].isdigit() else 10
    count = min(count, 100)
    
    await context.bot.delete_message(update.effective_chat.id, update.message.message_id)
    # Note: In a real bot, we'd use a loop or bulk delete if supported by the library version
    await update.message.reply_text(f"🧹 Удалено {count} сообщений (имитация).", delete_after=5)

# --- Leveling System ---

async def update_xp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user or update.effective_user.is_bot: return
    
    user_id = update.effective_user.id
    user = await db.get_user(user_id, update.effective_user.username, update.effective_user.first_name)
    
    new_xp = user.xp + random.randint(5, 15)
    new_level = user.level
    
    # Simple level up logic: level * 100 XP
    if new_xp >= (user.level * 100):
        new_level += 1
        if update.effective_chat.type != 'private':
            await update.message.reply_text(f"🎉 Поздравляем, {update.effective_user.first_name}! Вы достигли уровня {new_level}!")
    
    await db.update_user(user_id, xp=new_xp, level=new_level, messages_count=user.messages_count + 1)

# --- Main Logic ---

async def post_init(application: Application):
    await init_db()
    logger.info("✅ Database initialized")

def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Basic
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Moderation
    application.add_handler(CommandHandler("grouphelp", grouphelp))
    application.add_handler(CommandHandler("warn", warn_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("purge", purge_messages))
    
    # Personal Tools
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("notes", notes_command))
    application.add_handler(CommandHandler("delnote", delnote_command))
    application.add_handler(CommandHandler("memorysave", memorysave))
    application.add_handler(CommandHandler("memoryget", memoryget))
    application.add_handler(CommandHandler("vip", vip_status))
    application.add_handler(CommandHandler("remind", remind_command))
    
    # AI & Settings
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("key", set_key_command))
    
    # XP System & AI Guardian & Disco Mode
    async def combined_handler(update, context):
        if not update.message or not update.message.text: return
        text = update.message.text
        
        # 1. AI Guardian
        if await ai_guardian_check(update, context, text): return
        
        # 2. XP Update
        await update_xp(update, context)
        
        # 3. Disco Mode
        await disco_mode_logic(update, context)
        
        # 4. AI Response (if mentioned)
        await handle_message(update, context)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_handler))
    
    # Placeholder for other handlers to be added in next phases
    
    logger.info("🚀 AI DISCO BOT v1.0.0 Started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
