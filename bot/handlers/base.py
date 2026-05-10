from telegram import Update
from telegram.ext import ContextTypes
from bot.storage import storage
from bot.ai import PROVIDERS
from bot.keyboards import get_main_keyboard, get_help_keyboard

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    
    text = (
        "🤖 <b>Добро пожаловать в AI DISCO BOT!</b>\n\n"
        "Я — многофункциональный ИИ-ассистент.\n"
        "В этой версии внедрена система <b>BYOK (Bring Your Own Key)</b>, "
        "что дает вам свободу выбора из 10+ провайдеров (Gemini, OpenAI, Anthropic и др.).\n\n"
        "<b>С чего начать:</b>\n"
        "1. Перейдите в настройки: <code>/setprovider</code>\n"
        "2. Установите ваш ключ: <code>/setkey [провайдер] [ключ]</code>\n"
        "3. Просто общайтесь или отправляйте файлы/фото!\n\n"
        "👇 <i>Воспользуйтесь меню ниже для управления:</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    user["stats"]["commands"] += 1
    
    text = "📚 <b>Справка по командам:</b>\n\nВыберите нужный раздел в меню ниже:"
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
