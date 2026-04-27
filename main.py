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
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ['creator', 'administrator']

# --- Basic Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_user(user.id)
    
    if update.effective_chat.type == 'private':
        welcome_text = (
            f"🚀 **AI DISCO BOT v5.0: THE COMEBACK**\n\n"
            f"Привет, {user.first_name}! Я вернулся и стал мощнее, чем когда-либо.\n\n"
            "🔹 **BYOK (Bring Your Own Key)**: Подключай свои ключи от 10+ провайдеров.\n"
            "🔹 **Групповой режим**: Добавь меня в чат для AI-модерации и общения.\n"
            "🔹 **Полная свобода**: Выбирай модели от GPT-4o до Claude 3.5 и Llama 3.\n\n"
            "⚙️ Нажми /settings для настройки провайдера и ключа."
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("🤖 AI DISCO BOT активирован в этой группе! Используйте /help_group для списка команд.")

async def help_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛡 **Команды модерации (только для админов):**\n"
        "/ban - Бан пользователя (реплаем)\n"
        "/mute [мин] - Мут пользователя (реплаем)\n"
        "/unmute - Размут (реплаем)\n"
        "/warn - Выдать предупреждение (реплаем)\n"
        "/reset_warns - Сбросить варны (реплаем)\n"
        "/setwelcome [текст] - Настроить приветствие\n"
        "/setai [on/off] - Включить/выключить AI в чате\n\n"
        "💡 Чтобы AI ответил в группе, упомяните бота или ответьте на его сообщение."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# --- Settings & BYOK ---

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        await update.message.reply_text("❌ Настройки доступны только в личных сообщениях бота.")
        return

    user_id = update.effective_user.id
    user_settings = db.get_user_settings(user_id)
    active_prov = user_settings.active_provider or "Не выбран"
    
    keyboard = [
        [InlineKeyboardButton("🌐 Выбрать провайдера", callback_data='set_provider')],
        [InlineKeyboardButton("🔑 Ввести API ключ", callback_data='set_key_prompt')],
        [InlineKeyboardButton("🗑 Очистить историю", callback_data='clear_chat')],
        [InlineKeyboardButton("ℹ️ Мой статус", callback_data='my_status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "⚙️ **Настройки AI DISCO BOT**\n\n"
        f"Текущий провайдер: `{active_prov.upper()}`\n"
        "Здесь вы можете настроить свой собственный ключ для использования AI."
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == 'set_provider':
        keyboard = []
        # Create 2 columns of providers
        for i in range(0, len(PROVIDERS_LIST), 2):
            row = [InlineKeyboardButton(PROVIDERS_LIST[i][0], callback_data=f"prov_{PROVIDERS_LIST[i][1]}")]
            if i + 1 < len(PROVIDERS_LIST):
                row.append(InlineKeyboardButton(PROVIDERS_LIST[i+1][0], callback_data=f"prov_{PROVIDERS_LIST[i+1][1]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')])
        await query.edit_message_text("Выберите AI провайдера:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith('prov_'):
        provider = query.data.split('_')[1]
        user_settings = db.get_user_settings(user_id)
        user_settings.active_provider = provider
        db.session.commit()
        await query.edit_message_text(
            f"✅ Провайдер изменен на: **{provider.upper()}**\n\n"
            "Теперь введите ваш API ключ с помощью команды:\n"
            f"`/key {provider} ВАШ_КЛЮЧ`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]])
        )

    elif query.data == 'set_key_prompt':
        user_settings = db.get_user_settings(user_id)
        prov = user_settings.active_provider or "openai"
        await query.edit_message_text(
            f"🔑 **Ввод ключа для {prov.upper()}**\n\n"
            f"Отправьте команду:\n`/key {prov} ВАШ_КЛЮЧ`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]])
        )

    elif query.data == 'back_to_settings':
        # Re-use settings logic
        user_settings = db.get_user_settings(user_id)
        active_prov = user_settings.active_provider or "Не выбран"
        keyboard = [
            [InlineKeyboardButton("🌐 Выбрать провайдера", callback_data='set_provider')],
            [InlineKeyboardButton("🔑 Ввести API ключ", callback_data='set_key_prompt')],
            [InlineKeyboardButton("🗑 Очистить историю", callback_data='clear_chat')],
            [InlineKeyboardButton("ℹ️ Мой статус", callback_data='my_status')]
        ]
        await query.edit_message_text(
            "⚙️ **Настройки AI DISCO BOT**\n\n"
            f"Текущий провайдер: `{active_prov.upper()}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == 'clear_chat':
        db.clear_history(user_id)
        await query.edit_message_text("🗑 История чата очищена!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]]))

    elif query.data == 'my_status':
        user = db.get_user(user_id)
        user_settings = db.get_user_settings(user_id)
        keys = db.session.query(db.UserKey).filter_by(user_id=user_id).all()
        keys_text = "\n".join([f"✅ {k.provider.upper()}" for k in keys]) or "Нет ключей"
        
        status_text = (
            f"👤 **Ваш профиль:**\n"
            f"ID: `{user_id}`\n"
            f"Сообщений: {user.messages_count}\n"
            f"Активный провайдер: `{user_settings.active_provider or 'Не выбран'}`\n\n"
            f"🔑 **Подключенные ключи:**\n{keys_text}"
        )
        await query.edit_message_text(status_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_settings')]]))

async def set_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Используйте: `/key [провайдер] [ключ]`\nПример: `/key openai sk-123...`", parse_mode=ParseMode.MARKDOWN)
        return
    
    provider = context.args[0].lower()
    api_key = context.args[1]
    user_id = update.effective_user.id
    
    # Validate provider
    if provider not in [p[1] for p in PROVIDERS_LIST]:
        await update.message.reply_text(f"❌ Неизвестный провайдер: {provider}")
        return

    db.update_user_key(user_id, provider, api_key)
    db.update_user_settings(user_id, active_provider=provider) # Auto-switch to this provider
    await update.message.reply_text(f"✅ API ключ для **{provider.upper()}** сохранен и выбран как активный!", parse_mode=ParseMode.MARKDOWN)

# --- Group Moderation ---

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение пользователя, которого нужно забанить.")
        return
    
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"✈️ Пользователь {target.full_name} забанен.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение пользователя.")
        return
    
    minutes = 15
    if context.args:
        try: minutes = int(context.args[0])
        except: pass
    
    target = update.message.reply_to_message.from_user
    until = datetime.now() + timedelta(minutes=minutes)
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await update.message.reply_text(f"🔇 {target.full_name} в муте на {minutes} мин.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение пользователя.")
        return
    
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    count = db.add_warn(chat_id, target.id)
    group = db.get_group(chat_id)
    
    if count >= group.warns_limit:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.message.reply_text(f"✈️ {target.full_name} получил {count}/{group.warns_limit} варнов и был забанен.")
            db.reset_warns(chat_id, target.id)
        except: pass
    else:
        await update.message.reply_text(f"⚠️ Предупреждение {target.full_name}: {count}/{group.warns_limit}")

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not context.args:
        await update.message.reply_text("❌ Используйте: `/setwelcome [текст]`\nМожно использовать `{name}` для имени.")
        return
    text = " ".join(context.args)
    db.update_group(update.effective_chat.id, welcome_text=text, welcome_enabled=True)
    await update.message.reply_text("✅ Приветствие обновлено.")

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = db.get_group(chat_id)
    if not group.welcome_enabled: return
    
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        text = group.welcome_text.replace("{name}", member.first_name)
        await update.message.reply_text(text)

# --- AI Logic ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    is_private = update.effective_chat.type == 'private'
    
    # In groups, only respond if mentioned or replied to bot
    if not is_private:
        bot_username = (await context.bot.get_me()).username
        is_mentioned = f"@{bot_username}" in text
        is_reply_to_bot = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        
        group = db.get_group(chat_id)
        if not group.ai_enabled: return
        if not (is_mentioned or is_reply_to_bot): return
        
        # Clean mention from text
        text = text.replace(f"@{bot_username}", "").strip()

    # Update user stats
    user = db.get_user(user_id)
    user.messages_count += 1
    db.session.commit()

    # Get AI settings
    user_settings = db.get_user_settings(user_id)
    active_prov = user_settings.active_provider
    
    if not active_prov:
        if is_private:
            await update.message.reply_text("❌ Провайдер не выбран. Используйте /settings.")
        return

    key_entry = db.get_active_key(user_id, active_prov)
    if not key_entry:
        if is_private:
            await update.message.reply_text(f"❌ У вас нет ключа для {active_prov.upper()}. Используйте /settings.")
        return

    # Build context
    db.add_message(user_id, "user", text)
    history = db.get_history(user_id, limit=10)
    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.insert(0, {"role": "system", "content": "You are AI DISCO BOT, a powerful and helpful assistant. Respond in the language of the user."})

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    try:
        provider = get_provider(active_prov, key_entry.api_key, key_entry.model)
        response = await provider.generate(messages)
        db.add_message(user_id, "assistant", response)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"AI Error: {e}")
        if is_private:
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")

# --- Main ---

def main():
    init_db()
    # Add missing method to DBManager for convenience
    def update_user_settings(self, user_id, **kwargs):
        settings = self.get_user_settings(user_id)
        for k, v in kwargs.items(): setattr(settings, k, v)
        self.session.commit()
    DBManager.update_user_settings = update_user_settings

    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("key", set_key_command))
    application.add_handler(CommandHandler("help_group", help_group))
    
    # Moderation
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", ban_command)) # Reuse logic for simplicity or add unmute
    application.add_handler(CommandHandler("warn", warn_command))
    application.add_handler(CommandHandler("setwelcome", setwelcome))
    
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 AI DISCO BOT v5.0 Started!")
    application.run_polling()

if __name__ == '__main__':
    main()
