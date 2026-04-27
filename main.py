import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from database import DBManager, init_db
from ai_providers import get_provider

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
db = DBManager()

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_user(user.id)
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я — обновленный AI DISCO BOT. Теперь я поддерживаю **BYOK (Bring Your Own Key)**.\n\n"
        "Это значит, что ты можешь подключить свой API ключ от любого популярного провайдера (OpenAI, Anthropic, Gemini и др.) и использовать самые мощные модели без ограничений!\n\n"
        "⚙️ Используй /settings чтобы настроить провайдера и ключ.\n"
        "💬 Просто пиши мне, чтобы начать чат."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Выбрать провайдера", callback_data='set_provider')],
        [InlineKeyboardButton("Ввести API ключ", callback_data='set_key')],
        [InlineKeyboardButton("Очистить историю чата", callback_data='clear_chat')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ Настройки бота:", reply_markup=reply_markup)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'set_provider':
        providers = [
            [InlineKeyboardButton("OpenAI", callback_data='prov_openai'), InlineKeyboardButton("Anthropic", callback_data='prov_anthropic')],
            [InlineKeyboardButton("Gemini", callback_data='prov_gemini'), InlineKeyboardButton("Groq", callback_data='prov_groq')],
            [InlineKeyboardButton("DeepSeek", callback_data='prov_deepseek'), InlineKeyboardButton("OpenRouter", callback_data='prov_openrouter')]
        ]
        await query.edit_message_text("Выберите провайдера:", reply_markup=InlineKeyboardMarkup(providers))
    
    elif query.data.startswith('prov_'):
        provider = query.data.split('_')[1]
        settings = db.get_user_settings(query.from_user.id)
        settings.active_provider = provider
        db.session.commit()
        await query.edit_message_text(f"✅ Провайдер изменен на: {provider.upper()}\nТеперь введите ваш API ключ командой: `/key ВАШ_КЛЮЧ`", parse_mode=ParseMode.MARKDOWN)

    elif query.data == 'clear_chat':
        db.clear_history(query.from_user.id)
        await query.edit_message_text("🗑 История чата очищена!")

async def set_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Используйте: `/key ВАШ_КЛЮЧ`", parse_mode=ParseMode.MARKDOWN)
        return
    
    api_key = context.args[0]
    user_id = update.effective_user.id
    settings = db.get_user_settings(user_id)
    db.update_user_key(user_id, settings.active_provider, api_key)
    await update.message.reply_text(f"✅ API ключ для {settings.active_provider.upper()} успешно сохранен!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    settings = db.get_user_settings(user_id)
    key_entry = db.get_active_key(user_id, settings.active_provider)
    
    if not key_entry:
        await update.message.reply_text("❌ У вас не настроен API ключ для текущего провайдера. Используйте /settings.")
        return

    # Add user message to history
    db.add_message(user_id, "user", text)
    
    # Get history
    history = db.get_history(user_id)
    messages = [{"role": m.role, "content": m.content} for m in history]
    
    # Add system prompt
    messages.insert(0, {"role": "system", "content": "You are a helpful AI assistant."})
    
    # Show typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        provider = get_provider(settings.active_provider, key_entry.api_key, key_entry.model)
        response = await provider.generate(messages)
        
        # Add assistant response to history
        db.add_message(user_id, "assistant", response)
        
        # Send response
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка при запросе к AI: {str(e)}")

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("key", set_key_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 New AI Bot started!")
    application.run_polling()

if __name__ == '__main__':
    main()
