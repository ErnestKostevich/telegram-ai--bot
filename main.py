import os
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction
from database import DBManager, init_db
from ai_providers import get_provider, PROVIDERS_LIST

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
db = DBManager()

# --- Cache for performance ---
user_settings_cache = {}

def get_cached_settings(user_id):
    if user_id not in user_settings_cache:
        user_settings_cache[user_id] = db.get_user_settings(user_id)
    return user_settings_cache[user_id]

# --- Helpers ---

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# --- Basic Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_user(user.id)
    
    if update.effective_chat.type == 'private':
        welcome_text = (
            f"🚀 **AI DISCO BOT v5.1: OPTIMIZED**\n\n"
            f"Привет, {user.first_name}! Я стал быстрее и стабильнее.\n\n"
            "🔹 **BYOK**: Подключай свои ключи от 10+ провайдеров.\n"
            "🔹 **Группы**: AI-модерация и общение в чатах.\n"
            "🔹 **Скорость**: Оптимизированные запросы и мгновенные ответы.\n\n"
            "⚙️ Нажми /settings для настройки."
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("🤖 AI DISCO BOT готов к работе! /help_group для команд.")

async def help_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛡 **Команды (админы):**\n"
        "/ban, /mute, /unmute, /warn, /reset_warns\n"
        "/setwelcome [текст], /setai [on/off]\n\n"
        "💡 AI отвечает на упоминание или реплай."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# --- Settings & BYOK ---

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    
    user_id = update.effective_user.id
    user_settings = get_cached_settings(user_id)
    active_prov = user_settings.active_provider or "Не выбран"
    
    keyboard = [
        [InlineKeyboardButton("🌐 Выбрать провайдера", callback_data='set_provider')],
        [InlineKeyboardButton("🔑 Ввести API ключ", callback_data='set_key_prompt')],
        [InlineKeyboardButton("🗑 Очистить историю", callback_data='clear_chat')],
        [InlineKeyboardButton("ℹ️ Мой статус", callback_data='my_status')]
    ]
    
    text = f"⚙️ **Настройки**\n\nТекущий провайдер: `{active_prov.upper()}`"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == 'set_provider':
        keyboard = []
        for i in range(0, len(PROVIDERS_LIST), 2):
            row = [InlineKeyboardButton(PROVIDERS_LIST[i][0], callback_data=f"prov_{PROVIDERS_LIST[i][1]}")]
            if i + 1 < len(PROVIDERS_LIST):
                row.append(InlineKeyboardButton(PROVIDERS_LIST[i+1][0], callback_data=f"prov_{PROVIDERS_LIST[i+1][1]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')])
        await query.edit_message_text("Выберите провайдера:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith('prov_'):
        provider = query.data.split('_')[1]
        user_settings = get_cached_settings(user_id)
        user_settings.active_provider = provider
        db.session.commit()
        await query.edit_message_text(f"✅ Выбран: **{provider.upper()}**\nВведите ключ: `/key {provider} КЛЮЧ`", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]]))

    elif query.data == 'back_to_settings':
        user_settings = get_cached_settings(user_id)
        active_prov = user_settings.active_provider or "Не выбран"
        keyboard = [[InlineKeyboardButton("🌐 Выбрать провайдера", callback_data='set_provider')], [InlineKeyboardButton("🔑 Ввести API ключ", callback_data='set_key_prompt')], [InlineKeyboardButton("🗑 Очистить историю", callback_data='clear_chat')], [InlineKeyboardButton("ℹ️ Мой статус", callback_data='my_status')]]
        await query.edit_message_text(f"⚙️ **Настройки**\n\nТекущий провайдер: `{active_prov.upper()}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    elif query.data == 'clear_chat':
        db.clear_history(user_id)
        await query.edit_message_text("🗑 История очищена!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]]))

async def set_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: `/key [провайдер] [ключ]`")
        return
    
    provider, api_key = context.args[0].lower(), context.args[1]
    user_id = update.effective_user.id
    db.update_user_key(user_id, provider, api_key)
    
    user_settings = get_cached_settings(user_id)
    user_settings.active_provider = provider
    db.session.commit()
    
    await update.message.reply_text(f"✅ Ключ для **{provider.upper()}** сохранен!")

# --- AI Logic ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    is_private = update.effective_chat.type == 'private'
    
    if not is_private:
        bot_username = (await context.bot.get_me()).username
        if f"@{bot_username}" not in text and not (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id):
            return
        text = text.replace(f"@{bot_username}", "").strip()
        group = db.get_group(chat_id)
        if not group.ai_enabled: return

    user_settings = get_cached_settings(user_id)
    active_prov = user_settings.active_provider
    if not active_prov:
        if is_private: await update.message.reply_text("❌ Выберите провайдера в /settings")
        return

    key_entry = db.get_active_key(user_id, active_prov)
    if not key_entry:
        if is_private: await update.message.reply_text(f"❌ Нет ключа для {active_prov.upper()}. Введите его в /settings")
        return

    db.add_message(user_id, "user", text)
    history = db.get_history(user_id, limit=8) # Reduced limit for speed
    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.insert(0, {"role": "system", "content": "You are AI DISCO BOT. Be concise and helpful."})

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    try:
        provider = get_provider(active_prov, key_entry.api_key, key_entry.model)
        response = await provider.generate(messages)
        db.add_message(user_id, "assistant", response)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"AI Error: {e}")
        if is_private: await update.message.reply_text(f"❌ Ошибка: {str(e)}")

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("key", set_key_command))
    application.add_handler(CommandHandler("help_group", help_group))
    
    # Simple moderation handlers
    application.add_handler(CommandHandler("ban", lambda u, c: None)) # Placeholder
    
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 AI DISCO BOT v5.1 Started!")
    application.run_polling()

if __name__ == '__main__':
    main()
