from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import PROVIDERS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    
    text = (
        "🤖 <b>Добро пожаловать в AI DISCO BOT (BYOK Edition)!</b>\n\n"
        "Теперь вы полностью контролируете свои расходы на AI. "
        "Вам нужно использовать собственный API ключ.\n\n"
        "<b>Доступные провайдеры:</b>\n" + ", ".join(PROVIDERS) + "\n\n"
        "<b>С чего начать:</b>\n"
        "1. Выберите провайдера: <code>/setprovider gemini</code>\n"
        "2. Установите ключ: <code>/setkey gemini ВАШ_КЛЮЧ</code>\n"
        "3. Общайтесь: <code>/ai Привет!</code>\n\n"
        "Для просмотра всех команд введите /help"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    
    help_text = """
📚 <b>Список команд AI DISCO BOT:</b>

🏠 <b>Базовые:</b>
/start — запуск бота
/help — список всех команд
/info — информация о боте
/status — статус системы

💬 <b>AI и память:</b>
/setprovider [provider] — выбрать AI
/setkey [provider] [key] — установить ключ
/ai [вопрос] — задать вопрос AI
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist
/memorydel [ключ]

📝 <b>Заметки:</b>
/note [текст]
/notes
/delnote [номер]

💎 <b>VIP функции:</b>
/vip — статус VIP
/remind [минуты] [текст]
/reminders

👑 <b>Создатель:</b>
/grant_vip [user_id] [duration]
/broadcast [текст]
/stats

👥 <b>Функции для групп:</b>
/grouphelp — список групповых команд
"""
    await update.message.reply_text(help_text, parse_mode="HTML")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>Информация о боте</b>\n\n"
        "Версия: 1.0.0 comeback\n"
        "Архитектура: BYOK (Bring Your Own Key)\n"
        "Создатель: @Ernest_Kostevich\n\n"
        "Бот поддерживает 10+ AI провайдеров и предоставляет богатый набор "
        "функций для групп, геймификации и управления."
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_count = len(storage.data["users"])
    groups_count = len(storage.data["groups"])
    
    text = (
        "📊 <b>Статус системы</b>\n\n"
        f"Пользователей: {users_count}\n"
        f"Групп: {groups_count}\n"
        "Хранилище: GitHub API"
    )
    await update.message.reply_text(text, parse_mode="HTML")
