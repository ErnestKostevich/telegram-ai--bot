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

# --- Helpers ---

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ['creator', 'administrator']
    except Exception as e:
        logger.error(f"Admin check error: {e}")
        return False

# --- Basic Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    try:
        await db.get_user(user.id)
        if chat.type != 'private':
            await db.get_group(chat.id)
    except Exception as e:
        logger.error(f"Start command DB error: {e}")

    if chat.type == 'private':
        welcome_text = (
            f"🚀 **AI DISCO BOT v5.6: COMMANDS FIXED**\n\n"
            f"Привет, {user.first_name}! Теперь все команды работают.\n\n"
            "🔹 **Настройки**: /settings\n"
            "🔹 **Ввод ключа**: `/key [провайдер] [ключ]`\n"
            "🔹 **Группы**: /help_group\n\n"
            "Попробуйте нажать /settings прямо сейчас!"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("🤖 AI DISCO BOT активен! Используйте /help_group для списка команд.")

async def help_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛡 **Команды для групп:**\n"
        "/setai [on/off] - Включить/выключить AI\n"
        "/setwelcome [текст] - Приветствие новых участников\n\n"
        "💡 Чтобы я ответил, тегните меня или сделайте реплай."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# --- Settings & BYOK ---

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Настройки доступны только в ЛС бота.")
        return
    
    user_id = update.effective_user.id
    try:
        user_settings = await db.get_user_settings(user_id)
        active_prov = user_settings.active_provider if user_settings and user_settings.active_provider else "Не выбран"
        
        keyboard = [
            [InlineKeyboardButton("🌐 Выбрать провайдера", callback_data='set_provider')],
            [InlineKeyboardButton("🔑 Ввести API ключ", callback_data='set_key_prompt')],
            [InlineKeyboardButton("🗑 Очистить историю", callback_data='clear_chat')]
        ]
        
        text = f"⚙️ **Настройки**\n\nТекущий провайдер: `{str(active_prov).upper()}`"
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Settings error: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке настроек.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    try:
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
            await db.update_user_settings(user_id, active_provider=provider)
            await query.edit_message_text(f"✅ Выбран: **{provider.upper()}**\nВведите ключ: `/key {provider} КЛЮЧ`", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]]))

        elif query.data == 'set_key_prompt':
            user_settings = await db.get_user_settings(user_id)
            prov = user_settings.active_provider if user_settings and user_settings.active_provider else "openai"
            await query.edit_message_text(f"🔑 Введите ключ для **{prov.upper()}**:\n\n`/key {prov} ВАШ_КЛЮЧ`", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]]))

        elif query.data == 'back_to_settings':
            user_settings = await db.get_user_settings(user_id)
            active_prov = user_settings.active_provider if user_settings and user_settings.active_provider else "Не выбран"
            keyboard = [[InlineKeyboardButton("🌐 Выбрать провайдера", callback_data='set_provider')], [InlineKeyboardButton("🔑 Ввести API ключ", callback_data='set_key_prompt')], [InlineKeyboardButton("🗑 Очистить историю", callback_data='clear_chat')]]
            await query.edit_message_text(f"⚙️ **Настройки**\n\nТекущий провайдер: `{str(active_prov).upper()}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

        elif query.data == 'clear_chat':
            await db.clear_history(user_id)
            await query.edit_message_text("🗑 История очищена!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]]))
    except Exception as e:
        logger.error(f"Callback error: {e}")

async def set_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: `/key [провайдер] [ключ]`")
        return
    
    provider, api_key = context.args[0].lower(), context.args[1]
    user_id = update.effective_user.id
    try:
        await db.update_user_key(user_id, provider, api_key)
        await db.update_user_settings(user_id, active_provider=provider)
        await update.message.reply_text(f"✅ Ключ для **{provider.upper()}** сохранен!")
    except Exception as e:
        logger.error(f"Key save error: {e}")
        await update.message.reply_text("❌ Ошибка при сохранении ключа.")

# --- Group Logic ---

async def setai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not context.args:
        await update.message.reply_text("❌ Используйте: `/setai on` или `/setai off`")
        return
    
    state = context.args[0].lower() in ['on', 'true', '1']
    try:
        await db.update_group(update.effective_chat.id, ai_enabled=state)
        await update.message.reply_text(f"✅ AI в чате: {'ВКЛ' if state else 'ВЫКЛ'}")
    except Exception as e:
        logger.error(f"SetAI error: {e}")

# --- AI Logic ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    is_private = update.effective_chat.type == 'private'
    
    # Group logic
    if not is_private:
        bot_me = await context.bot.get_me()
        is_mentioned = f"@{bot_me.username}" in text
        is_reply_to_bot = update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_me.id
        
        if not (is_mentioned or is_reply_to_bot):
            return
        
        try:
            group = await db.get_group(chat_id)
            if not group.ai_enabled: return
        except: return
            
        text = text.replace(f"@{bot_me.username}", "").strip()

    try:
        user_settings = await db.get_user_settings(user_id)
        if not user_settings or not user_settings.active_provider:
            if is_private: await update.message.reply_text("❌ Выберите провайдера в /settings")
            return

        active_prov = user_settings.active_provider
        key_entry = await db.get_active_key(user_id, active_prov)
        
        if not key_entry:
            if is_private: await update.message.reply_text(f"❌ Нет ключа для {active_prov.upper()}. Введите его в /settings")
            return

        await db.add_message(user_id, "user", text)
        history = await db.get_history(user_id, limit=6)
        messages = [{"role": m.role, "content": m.content} for m in history]
        messages.insert(0, {"role": "system", "content": "You are AI DISCO BOT. Be helpful and concise."})

        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        
        provider = get_provider(active_prov, key_entry.api_key, key_entry.model)
        if not provider: return
            
        response = await provider.generate(messages)
        await db.add_message(user_id, "assistant", response)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"AI Process Error: {e}")
        if is_private: await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def post_init(application: Application):
    await init_db()
    logger.info("✅ Database initialized")

def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Регистрация команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("key", set_key_command))
    application.add_handler(CommandHandler("help_group", help_group))
    application.add_handler(CommandHandler("setai", setai_command))
    
    # Обработка кнопок
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Обработка текстовых сообщений (должна быть последней)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 AI DISCO BOT v5.6 Started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
