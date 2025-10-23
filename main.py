#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import random
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz
import requests
import io
from urllib.parse import quote as urlquote

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx

# ---------- SQLAlchemy (исправление предупреждения) ----------
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker
# --------------------------------------------------------------

# Переменные окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка переменных окружения
if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ BOT_TOKEN или GEMINI_API_KEY не установлены!")
    raise ValueError("Required environment variables missing")

# Настройка Gemini 2.5 Flash
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

system_instruction = (
    "You are AI DISCO BOT, an extremely intelligent, helpful, and multilingual AI assistant built with Gemini 2.5. "
    "Always respond in the user's preferred language. Be engaging, use emojis appropriately, and provide detailed, "
    "insightful answers. Break down complex topics logically. If a response is long, structure it with headings and lists. "
    "Your creator is @Ernest_Kostevich. Detect and adapt to the user's language if not specified."
)

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash-latest',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction=system_instruction
)

vision_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash-latest',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# ---------- База данных ----------
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    notes = Column(JSON, default=list)
    todos = Column(JSON, default=list)
    memory = Column(JSON, default=dict)
    reminders = Column(JSON, default=list)
    registered = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    messages_count = Column(Integer, default=0)
    commands_count = Column(Integer, default=0)
    language = Column(String(10), default='ru')

class Chat(Base):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    message = Column(Text)
    response = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)

class Statistics(Base):
    __tablename__ = 'statistics'
    key = Column(String(50), primary_key=True)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.now)

engine = None
Session = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("✅ PostgreSQL подключен!")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка подключения к БД: {e}. Fallback на JSON.")
else:
    logger.warning("⚠️ БД не настроена. Используется JSON.")

# ---------- Переводы ----------
SUPPORTED_LANGUAGES = ['ru', 'en', 'es', 'de', 'it', 'fr']

TRANSLATIONS = {
    'ru': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nПривет, {name}! Я бот на <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Возможности:</b>\n💬 AI-чат\n📝 Заметки\n🌍 Погода\n⏰ Время\n🎲 Развлечения\n📎 Анализ (VIP)\n🔍 Анализ фото (VIP)\n🖼️ Генерация фото (VIP)\n\n<b>⚡ Команды:</b>\n/help\n/vip\n\n<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}",
        'help_menu': "📚 <b>Выберите раздел справки:</b>",
        'vip_status_active': "💎 <b>VIP СТАТУС</b>\n\n✅ Активен до {until}\n\n<b>🎁 Преимущества:</b>\n• ⏰ Напоминания\n• 🖼️ Генерация\n• 🔍 Анализ фото\n• 📎 Анализ документов",
        'vip_status_inactive': "💎 <b>VIP СТАТУС</b>\n\n❌ Нет VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'image_gen_error': "❌ Ошибка генерации изображения",
        'voice_processing': "🔊 Обработка голосового сообщения...",
        'voice_error': "❌ Ошибка обработки голоса: {error}",
        'set_language': "✅ Язык установлен на {lang}.",
        'invalid_language': "❌ Неверный язык. Поддерживаемые: ru, en, es, de, it, fr.",
        'ai_chat_button': "💬 AI Чат",
        'notes_button': "📝 Заметки",
        'weather_button': "🌍 Погода",
        'time_button': "⏰ Время",
        'entertainment_button': "🎲 Развлечения",
        'info_button': "ℹ️ Инфо",
        'vip_menu_button': "💎 VIP Меню",
        'generation_button': "🖼️ Генерация",
        'admin_panel_button': "👑 Админ Панель",
        'voice_vip_only': "💎 Обработка голоса — только для VIP.",
        'status_text': "📊 <b>Статус бота</b>\n\n🟢 Работает\n⏱ Время работы: {uptime}\n👥 Пользователей: {users}\n💬 Сообщений: {messages}\n🤖 AI-запросов: {ai}",
        'profile_text': "👤 <b>Ваш профиль</b>\n\n🆔 ID: <code>{id}</code>\n📛 Имя: {name}\n💎 VIP: {vip}\n📅 Регистрация: {reg}\n✉️ Сообщений: {msg}\n⚡ Команд: {cmd}",
        'uptime_text': "⏱ <b>Время работы бота</b>\n\n{uptime}",
    },
    # Для краткости остальные языки опущены — добавьте при необходимости
    'en': { ... },
    'es': { ... },
    'de': { ... },
    'it': { ... },
    'fr': { ... },
}

def get_translation(lang: str, key: str, **kwargs):
    lang = lang if lang in SUPPORTED_LANGUAGES else 'en'
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS['en'].get(key, key))
    return text.format(**kwargs)

# ---------- Хранилище ----------
class DataStorage:
    # ... (полностью тот же код, что был в предыдущей версии) ...
    pass  # <-- замените на ваш оригинальный класс DataStorage

storage = DataStorage()
scheduler = AsyncIOScheduler()

# ---------- Вспомогательные функции ----------
def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Создатель найден: {user.id}")

def is_creator(user_id: int) -> bool:
    return user_id == CREATOR_ID

def format_uptime(start: datetime) -> str:
    delta = datetime.now() - start
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours} ч {minutes} мин {seconds} сек"

def get_main_keyboard(user_id: int, lang: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(get_translation(lang, 'ai_chat_button')), KeyboardButton(get_translation(lang, 'notes_button'))],
        [KeyboardButton(get_translation(lang, 'weather_button')), KeyboardButton(get_translation(lang, 'time_button'))],
        [KeyboardButton(get_translation(lang, 'entertainment_button')), KeyboardButton(get_translation(lang, 'info_button'))]
    ]
    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton(get_translation(lang, 'vip_menu_button')), KeyboardButton(get_translation(lang, 'generation_button'))])
    if is_creator(user_id):
        keyboard.append([KeyboardButton(get_translation(lang, 'admin_panel_button'))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------- Команды ----------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    user_data = storage.get_user(user.id)
    lang = user_data.get('language', 'ru')
    storage.update_user(user.id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'commands_count': user_data.get('commands_count', 0) + 1
    })
    await update.message.reply_text(
        get_translation(lang, 'welcome', name=user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(user.id, lang)
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    lang = user_data.get('language', 'ru')
    uptime = format_uptime(BOT_START_TIME)
    stats = storage.stats
    text = get_translation(lang, 'status_text',
                           uptime=uptime,
                           users=len(storage.get_all_users()),
                           messages=stats.get('total_messages', 0),
                           ai=stats.get('ai_requests', 0))
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = storage.get_user(user.id)
    lang = user_data.get('language', 'ru')
    vip = "✅ Да" if storage.is_vip(user.id) else "❌ Нет"
    reg = user_data.get('registered', '').split('T')[0]
    text = get_translation(lang, 'profile_text',
                           id=user.id,
                           name=user.full_name,
                           vip=vip,
                           reg=reg,
                           msg=user_data.get('messages_count', 0),
                           cmd=user_data.get('commands_count', 0))
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    lang = user_data.get('language', 'ru')
    await update.message.reply_text(
        get_translation(lang, 'uptime_text', uptime=format_uptime(BOT_START_TIME)),
        parse_mode=ParseMode.HTML
    )

# ---------- Остальные команды (заглушки, добавьте реализацию при необходимости) ----------
async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = storage.get_user(user_id).get('language', 'ru')
    if storage.is_vip(user_id):
        until = storage.get_user(user_id).get('vip_until')
        until_str = datetime.fromisoformat(until).strftime('%d.%m.%Y %H:%M') if until else "Бессрочно"
        await update.message.reply_text(get_translation(lang, 'vip_status_active', until=until_str), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(get_translation(lang, 'vip_status_inactive'), parse_mode=ParseMode.HTML)

# ... (добавьте остальные команды: note_command, weather_command, time_command и т.д.) ...

# ---------- Обработчики сообщений ----------
async def send_long_message(update: Update, text: str, parse_mode=None):
    max_len = 4096
    for i in range(0, len(text), max_len):
        await update.message.reply_text(text[i:i+max_len], parse_mode=parse_mode)

async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action("typing")
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response.text)
        await send_long_message(update, response.text)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text("😔 Ошибка при запросе к AI")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    lang = user.get('language', 'ru')
    storage.update_user(user_id, {
        'messages_count': user.get('messages_count', 0) + 1,
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()

    text = update.message.text
    if text in [get_translation(lang, k) for k in ['ai_chat_button','notes_button','weather_button','time_button','entertainment_button','info_button','vip_menu_button','generation_button','admin_panel_button']]:
        # обработка кнопок меню (заглушка)
        await update.message.reply_text("Функция в разработке")
        return

    await process_ai_message(update, text, user_id)

# ---------- Запуск ----------
def signal_handler(signum, frame):
    logger.info("Сигнал завершения. Останавливаем...")
    scheduler.shutdown()
    raise SystemExit

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # === Регистрация всех обработчиков ===
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("uptime", uptime_command))
    application.add_handler(CommandHandler("vip", vip_command))
    # ... добавьте остальные CommandHandler ...

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # ... остальные MessageHandler ...

    scheduler.start()

    logger.info("AI DISCO BOT запущен!")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
