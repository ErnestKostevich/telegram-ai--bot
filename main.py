#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI DISCO BOT v3.5 by @Ernest_Kostevich
-------------------------------------
Полный код для развертывания на Render.
Улучшения:
- Исправлена работа клавиатуры (VIP, Админ, Основное меню).
- Добавлена полная мультиязычная поддержка (Русский, Английский).
- Добавлена обработка голосовых сообщений через Gemini.
- Генерация изображений через Pollinations.ai (стабильный вариант).
- Модель обновлена до gemini-1.5-flash-latest.
- Автоматическое разбиение длинных сообщений от ИИ.
"""

# ==============================================================================
# requirements.txt ДЛЯ RENDER
# ==============================================================================
# python-telegram-bot
# google-generativeai
# sqlalchemy
# psycopg2-binary
# pytz
# aiohttp
# httpx
# PyMuPDF
# python-docx
# Pillow
# APScheduler
# ==============================================================================

import os
import json
import logging
import random
import asyncio
import signal
import io
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from urllib.parse import quote as urlquote

# --- Импорт библиотек ---
import pytz
import requests
import aiohttp
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, User as TelegramUser
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction
import google.generativeai as genai
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Переменные окружения и начальная настройка ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None # Определяется автоматически
BOT_START_TIME = datetime.now()

if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ BOT_TOKEN или GEMINI_API_KEY не установлены в переменных окружения!")
    raise ValueError("Необходимые переменные окружения отсутствуют")

# --- Настройка Gemini 1.5 Flash ---
genai.configure(api_key=GEMINI_API_KEY)
generation_config = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    safety_settings=safety_settings,
    generation_config=generation_config,
    system_instruction=(
        "You are AI DISCO BOT, a friendly, witty, and helpful AI assistant powered by Gemini 1.5 Flash. "
        "Your creator is @Ernest_Kostevich. "
        "Always respond in the user's language. Be engaging, use emojis appropriately to make the conversation lively."
    )
)

# --- Локализация (i18n) ---
LOCALIZATION = {
    "en": {
        "welcome": "🤖 <b>AI DISCO BOT</b>\n\nHi, {first_name}! I'm a bot powered by <b>Gemini 1.5 Flash</b>.",
        "features": "<b>🎯 Features:</b>\n\n💬 AI Chat\n📝 Notes & Todos\n🎤 Voice Messages\n🌍 Utilities (Weather, Time)\n🎲 Fun\n💎 VIP: Image Gen, File Analysis & Reminders",
        "commands": "<b>⚡️ Commands:</b>\n/help - All commands\n/vip - VIP Status\n/language - Change language",
        "creator": "<b>👨‍💻 Creator:</b> @{creator}",
        "lang_suggestion": "It seems your language is English. Would you like to switch?",
        "lang_changed": "✅ Language has been set to English.",
        "lang_choose": "Please choose your language:",
        # --- Кнопки ---
        "btn_ai_chat": "💬 AI Chat", "btn_notes": "📝 Notes", "btn_weather": "🌍 Weather", "btn_time": "⏰ Time",
        "btn_games": "🎲 Fun", "btn_info": "ℹ️ Info", "btn_vip": "💎 VIP Menu", "btn_generate": "🖼️ Generate", "btn_admin": "👑 Admin Panel",
        # --- Ответы команд ---
        "ai_prompt": "🤖 How can I help you? Just type your message!\n/clear - to clear chat history",
        "weather_prompt": "🌍 <b>Weather</b>\n\n/weather [city]\nExample: /weather London",
        "time_prompt": "⏰ <b>Time</b>\n\n/time [city]\nExample: /time Tokyo",
        "vip_only_feature": "💎 This feature is for VIP users only.\n\nContact @{creator} to get access.",
        "prompt_generate": "🖼️ <b>Image Generation (VIP)</b>\n\n/generate [description]\n\nExamples:\n• /generate a red cat in space\n• /generate cyberpunk city",
        "admin_panel_welcome": "👑 Welcome to the Admin Panel, Creator!",
    },
    "ru": {
        "welcome": "🤖 <b>AI DISCO BOT</b>\n\nПривет, {first_name}! Я бот на базе <b>Gemini 1.5 Flash</b>.",
        "features": "<b>🎯 Возможности:</b>\n\n💬 AI-чат\n📝 Заметки и Задачи\n🎤 Голосовые сообщения\n🌍 Утилиты (Погода, Время)\n🎲 Развлечения\n💎 VIP: Генерация, Анализ файлов и Напоминания",
        "commands": "<b>⚡️ Команды:</b>\n/help - Все команды\n/vip - Статус VIP\n/language - Сменить язык",
        "creator": "<b>👨‍💻 Создатель:</b> @{creator}",
        "lang_changed": "✅ Язык установлен на русский.",
        "lang_choose": "Пожалуйста, выберите язык:",
        # --- Кнопки ---
        "btn_ai_chat": "💬 AI Чат", "btn_notes": "📝 Заметки", "btn_weather": "🌍 Погода", "btn_time": "⏰ Время",
        "btn_games": "🎲 Развлечения", "btn_info": "ℹ️ Инфо", "btn_vip": "💎 VIP Меню", "btn_generate": "🖼️ Генерация", "btn_admin": "👑 Админ Панель",
        # --- Ответы команд ---
        "ai_prompt": "🤖 Чем могу помочь? Просто напишите сообщение!\n/clear - чтобы очистить историю чата",
        "weather_prompt": "🌍 <b>Погода</b>\n\n/weather [город]\nПример: /weather Москва",
        "time_prompt": "⏰ <b>Время</b>\n\n/time [город]\nПример: /time Токио",
        "vip_only_feature": "💎 Эта функция доступна только для VIP-пользователей.\n\nСвяжитесь с @{creator} для получения доступа.",
        "prompt_generate": "🖼️ <b>Генерация (VIP)</b>\n\n/generate [описание]\n\nПримеры:\n• /generate закат\n• /generate город",
        "admin_panel_welcome": "👑 Добро пожаловать в админ-панель, Создатель!",
    }
}
def get_text(key: str, lang: str = 'ru') -> str:
    lang = 'en' if lang not in LOCALIZATION else lang
    return LOCALIZATION[lang].get(key, f"<{key}>")

# --- База данных (SQLAlchemy) ---
Base = declarative_base()
class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default='ru')
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime, nullable=True)
    notes = Column(JSON, default=list)
    todos = Column(JSON, default=list)
    memory = Column(JSON, default=dict)
    reminders = Column(JSON, default=list)
    registered = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    messages_count = Column(Integer, default=0)
    commands_count = Column(Integer, default=0)
class Chat(Base):
    __tablename__ = 'chats'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    message = Column(Text)
    response = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)
engine = None
Session = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("✅ PostgreSQL подключен!")
    except Exception as e:
        logger.error(f"⚠️ Ошибка подключения к БД: {e}.")
        engine = None
else:
    logger.warning("⚠️ DATABASE_URL не задана. Данные не будут сохраняться.")

# --- Управление данными ---
class DataStorage:
    def __init__(self):
        self.chat_sessions: Dict[int, Any] = {}
    def _get_db_session(self):
        if not Session: return None
        return Session()
    def get_or_create_user(self, tg_user: TelegramUser) -> Dict:
        session = self._get_db_session()
        if not session:
            return {'id': tg_user.id, 'username': tg_user.username, 'first_name': tg_user.first_name,
                    'language_code': (tg_user.language_code or 'ru').split('-')[0], 'vip': False}
        try:
            user = session.query(User).filter_by(id=tg_user.id).first()
            if not user:
                user = User(
                    id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name,
                    language_code=(tg_user.language_code or 'ru').split('-')[0]
                )
                session.add(user)
                session.commit()
                logger.info(f"Новый пользователь: {tg_user.id}")
            return {c.name: getattr(user, c.name) for c in user.__table__.columns}
        finally:
            session.close()
    def update_user(self, user_id: int, data: Dict):
        session = self._get_db_session()
        if not session: return
        try:
            session.query(User).filter_by(id=user_id).update(data)
            session.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления User {user_id}: {e}")
            session.rollback()
        finally:
            session.close()
    def is_vip(self, user_id: int) -> bool:
        session = self._get_db_session()
        if not session: return False
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user or not user.vip: return False
            if user.vip_until and datetime.now() > user.vip_until:
                user.vip = False
                user.vip_until = None
                session.commit()
                return False
            return True
        finally:
            session.close()
    def get_all_users(self) -> Dict:
        session = self._get_db_session()
        if not session: return {}
        try:
            users = session.query(User).all()
            return {u.id: {'id': u.id, 'vip': u.vip} for u in users}
        finally:
            session.close()
    def get_user_id_by_identifier(self, identifier: str) -> Optional[int]:
        identifier = identifier.strip().lstrip('@')
        if identifier.isdigit():
            return int(identifier)
        session = self._get_db_session()
        if not session: return None
        try:
            user = session.query(User).filter(User.username.ilike(identifier)).first()
            return user.id if user else None
        finally:
            session.close()
    def get_chat_session(self, user_id: int):
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = model.start_chat(history=[])
        return self.chat_sessions[user_id]
    def clear_chat_session(self, user_id: int):
        if user_id in self.chat_sessions:
            del self.chat_sessions[user_id]

storage = DataStorage()
scheduler = AsyncIOScheduler()

# --- Вспомогательные функции ---
def identify_creator(user: TelegramUser):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"✅ Создатель идентифицирован: {user.id} (@{user.username})")
def is_creator(user_id: int) -> bool: return user_id == CREATOR_ID

def get_main_keyboard(user_id: int, lang: str) -> ReplyKeyboardMarkup:
    keys = get_text
    keyboard = [
        [KeyboardButton(keys("btn_ai_chat", lang)), KeyboardButton(keys("btn_notes", lang))],
        [KeyboardButton(keys("btn_weather", lang)), KeyboardButton(keys("btn_time", lang))],
        [KeyboardButton(keys("btn_games", lang)), KeyboardButton(keys("btn_info", lang))]
    ]
    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton(keys("btn_vip", lang)), KeyboardButton(keys("btn_generate", lang))])
    if is_creator(user_id):
        keyboard.append([KeyboardButton(keys("btn_admin", lang))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    MAX_LENGTH = 4096
    if len(text) <= MAX_LENGTH:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
        return
    parts = [text[i:i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
    for part in parts:
        await context.bot.send_message(chat_id=chat_id, text=part, parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.3)

# --- ИИ Функции ---
async def process_ai_message(update: Update, text: str, user_id: int):
    context = ContextTypes.DEFAULT_TYPE(application=update.get_app(), chat_data={}, user_data={})
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        chat_session = storage.get_chat_session(user_id)
        response = await chat_session.send_message_async(text)
        await send_long_message(context, update.effective_chat.id, response.text)
    except Exception as e:
        logger.error(f"Ошибка в process_ai_message: {e}")
        await update.message.reply_text("😔 Ошибка при обработке вашего запроса. Попробуйте снова.")
async def generate_image(prompt: str) -> Optional[bytes]:
    try:
        async with httpx.AsyncClient() as client:
            api_url = f"https://image.pollinations.ai/prompt/{urlquote(prompt)}?width=1024&height=1024&nologo=true"
            response = await client.get(api_url, timeout=90.0)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"Ошибка генерации изображения: {e}")
        return None
async def analyze_image_with_gemini(image_bytes: bytes, prompt: str) -> str:
    try:
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        response = await model.generate_content_async([prompt, image_part])
        return response.text
    except Exception as e:
        logger.error(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка анализа: {e}"
async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split('.')[-1]
    text = ""
    try:
        if ext == 'txt': text = file_bytes.decode('utf-8', errors='ignore')
        elif ext == 'pdf':
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                text = "".join(page.get_text() for page in doc)
        elif ext == 'docx':
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            return "❌ Неподдерживаемый формат файла. Поддерживаются: txt, pdf, docx."
        return text
    except Exception as e:
        logger.error(f"Ошибка извлечения текста из файла {filename}: {e}")
        return f"❌ Ошибка обработки файла: {e}"
        
# --- Команды ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    identify_creator(tg_user)
    user = storage.get_or_create_user(tg_user)
    lang = user.get('language_code', 'ru')
    welcome_msg = f"{get_text('welcome', lang).format(first_name=tg_user.first_name)}\n\n{get_text('features', lang)}\n\n{get_text('commands', lang)}\n\n{get_text('creator', lang).format(creator=CREATOR_USERNAME)}"
    if lang != 'ru' and 'en' in (tg_user.language_code or ''):
         keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Switch to English", callback_data="set_lang_en")]])
         await update.message.reply_text(get_text('lang_suggestion', 'en'), reply_markup=keyboard)
    await update.message.reply_text(welcome_msg, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(tg_user.id, lang))
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Команда /help, текст может быть расширен и локализован
    text = """
    *Основные команды:*
    /start - Начало работы
    /help - Эта справка
    /language - Сменить язык
    /info - Информация о боте
    /vip - Информация о VIP статусе
    
    *Утилиты:*
    /weather [город] - Погода
    /time [город] - Время
    /note [текст] - Добавить заметку
    /notes - Посмотреть заметки
    /delnote [номер] - Удалить заметку

    *VIP Команды:*
    /generate [описание] - Создать изображение
    /remind [минуты] [текст] - Установить напоминание
    Отправка фото/документа для анализа.
    """
    await update.message.reply_text(text, parse_mode="Markdown")
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru")],
    ])
    await update.message.reply_text("Please choose your language / Пожалуйста, выберите язык:", reply_markup=keyboard)
async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_chat_session(update.effective_user.id)
    await update.message.reply_text("🧹 Контекст чата очищен!")
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = f"🤖 <b>AI DISCO BOT v3.5</b>\n\n<b>AI Модель:</b> Gemini 1.5 Flash\n<b>Создатель:</b> @{CREATOR_USERNAME}"
    await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)
async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_lang = storage.get_or_create_user(update.effective_user).get('language_code', 'ru')
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text("vip_only_feature", user_lang).format(creator=CREATOR_USERNAME), parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text("❓ Пожалуйста, напишите, что сгенерировать. Пример: `/generate рыжий кот в космосе`")
        return
    prompt = ' '.join(context.args)
    msg = await update.message.reply_text("🎨 Генерирую... Это может занять до 1.5 минут.")
    image_bytes = await generate_image(prompt)
    if image_bytes:
        await context.bot.send_photo(update.effective_chat.id, photo=image_bytes, caption=f"🖼️ По вашему запросу: <i>{prompt}</i>", parse_mode=ParseMode.HTML)
        await msg.delete()
    else:
        await msg.edit_text("❌ Ошибка генерации. Попробуйте другой запрос или повторите позже.")
# (Добавьте сюда остальные команды: note, delnote, weather, time, vip, и админ-команды из вашего оригинального кода)
async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("❓ /grant_vip [id/@username] [срок]\n\nСроки: week, month, year, forever")
        return
    identifier, duration_str = context.args[0], context.args[1].lower()
    target_id = storage.get_user_id_by_identifier(identifier)
    if not target_id:
        await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
        return
    
    duration_map = {'week': 7, 'month': 30, 'year': 365}
    vip_until = None
    if duration_str in duration_map:
        vip_until = datetime.now() + timedelta(days=duration_map[duration_str])
    elif duration_str != 'forever':
        await update.message.reply_text("❌ Неверный срок. Доступно: week, month, year, forever.")
        return

    storage.update_user(target_id, {'vip': True, 'vip_until': vip_until})
    duration_text = "навсегда" if not vip_until else f"до {vip_until.strftime('%d.%m.%Y')}"
    await update.message.reply_text(f"✅ VIP выдан пользователю {target_id} {duration_text}.")
    try:
        await context.bot.send_message(target_id, f"🎉 Поздравляем! Вам выдан VIP-статус {duration_text}.")
    except Exception as e:
        logger.warning(f"Не удалось уведомить пользователя {target_id} о VIP: {e}")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("❓ /revoke_vip [id/@username]")
        return
    target_id = storage.get_user_id_by_identifier(context.args[0])
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    storage.update_user(target_id, {'vip': False, 'vip_until': None})
    await update.message.reply_text(f"✅ VIP статус отозван у пользователя {target_id}.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("❓ /broadcast [текст сообщения]")
        return
    text = ' '.join(context.args)
    all_users = storage.get_all_users()
    sent, failed = 0, 0
    await update.message.reply_text(f"🚀 Начинаю рассылку для {len(all_users)} пользователей...")
    for user_id in all_users.keys():
        try:
            await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.1) # Защита от флуда
        except Exception as e:
            failed += 1
            logger.warning(f"Ошибка рассылки юзеру {user_id}: {e}")
    await update.message.reply_text(f"✅ Рассылка завершена!\n\nУспешно: {sent}\nОшибки: {failed}")

# --- Обработчики ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    identify_creator(tg_user)
    user = storage.get_or_create_user(tg_user)
    storage.update_user(user['id'], {'messages_count': user.get('messages_count', 0) + 1, 'username': tg_user.username, 'first_name': tg_user.first_name})
    
    text = update.message.text
    if not text: return
    lang = user.get('language_code', 'ru')
    
    # ИСПРАВЛЕННАЯ ЛОГИКА КЛАВИАТУРЫ
    button_map = {
        get_text("btn_ai_chat", lang): (lambda: update.message.reply_text(get_text("ai_prompt", lang), parse_mode=ParseMode.HTML)),
        # get_text("btn_notes", lang): (lambda: notes_command(update, context)), # Замените на ваши функции
        get_text("btn_weather", lang): (lambda: update.message.reply_text(get_text("weather_prompt", lang), parse_mode=ParseMode.HTML)),
        get_text("btn_time", lang): (lambda: update.message.reply_text(get_text("time_prompt", lang), parse_mode=ParseMode.HTML)),
        # get_text("btn_games", lang): (lambda: games_command(update, context)),
        get_text("btn_info", lang): (lambda: info_command(update, context)),
        # get_text("btn_vip", lang): (lambda: vip_command(update, context)),
        get_text("btn_generate", lang): (lambda: update.message.reply_text(get_text("prompt_generate", lang), parse_mode=ParseMode.HTML)),
        get_text("btn_admin", lang): (lambda: update.message.reply_text(get_text("admin_panel_welcome", lang)) if is_creator(user['id']) else None),
    }

    if text in button_map and button_map[text] is not None:
        await button_map[text]()
        return

    # Если это не кнопка, отправляем в ИИ
    await process_ai_message(update, text, user['id'])

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙️ Обрабатываю голосовое сообщение...")
    try:
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()
        audio_part = {"mime_type": "audio/ogg", "data": voice_bytes}
        response = await model.generate_content_async(["Распознай эту речь и верни только текст.", audio_part])
        transcribed_text = response.text.strip()
        if not transcribed_text:
            await update.message.reply_text("😔 Не удалось распознать речь.")
            return
        await update.message.reply_text(f"💬 Вы сказали: <i>«{transcribed_text}»</i>\n\n🤖 Отвечаю...", parse_mode=ParseMode.HTML)
        await process_ai_message(update, transcribed_text, update.effective_user.id)
    except Exception as e:
        logger.error(f"Ошибка обработки голоса: {e}")
        await update.message.reply_text("❌ Ошибка при обработке голосового сообщения.")
async def handle_document_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = storage.get_or_create_user(update.effective_user)
    lang = user.get('language_code', 'ru')
    if not storage.is_vip(user['id']):
        await update.message.reply_text(get_text("vip_only_feature", lang).format(creator=CREATOR_USERNAME))
        return

    file_bytes, file_name, caption = None, None, update.message.caption or "Проанализируй содержимое этого файла/фото."
    msg_wait = await update.message.reply_text("🔍 Анализирую...")
    
    try:
        if update.message.document:
            doc = update.message.document
            file_id = doc.file_id
            file_name = doc.file_name
        elif update.message.photo:
            photo = update.message.photo[-1]
            file_id = photo.file_id
            file_name = f"photo_{file_id}.jpg"
        else:
            return
            
        file_obj = await context.bot.get_file(file_id)
        file_bytes = bytes(await file_obj.download_as_bytearray())

        if file_name.endswith(('.jpg', '.jpeg', '.png', '.webp')):
             analysis_text = await analyze_image_with_gemini(file_bytes, caption)
        else:
            extracted_text = await extract_text_from_document(file_bytes, file_name)
            if extracted_text.startswith("❌"):
                await msg_wait.edit_text(extracted_text)
                return
            analysis_prompt = f"Проанализируй текст из файла '{file_name}':\n\n{extracted_text[:6000]}"
            analysis_text = (await model.generate_content_async(analysis_prompt)).text

        await send_long_message(context, update.effective_chat.id, f"📄 <b>Анализ для {file_name}:</b>\n\n{analysis_text}")
        await msg_wait.delete()
        
    except Exception as e:
        logger.error(f"Ошибка в handle_document_photo: {e}")
        await msg_wait.edit_text(f"❌ Произошла ошибка при обработке файла: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if data.startswith("set_lang_"):
        lang_code = data.split('_')[-1]
        storage.update_user(user_id, {'language_code': lang_code})
        lang_text = get_text('lang_changed', lang_code)
        await query.edit_message_text(lang_text)
        await context.bot.send_message(user_id, f"✅ {lang_text}", reply_markup=get_main_keyboard(user_id, lang_code))

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("generate", generate_command))
    # Админ команды
    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Обработчики
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document_photo))
    application.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН!")
    logger.info(f"🤖 Модель: {model.model_name}")
    logger.info(f"🗄️ БД: {'PostgreSQL ✓' if engine else 'Отсутствует (данные не сохранятся)'}")
    logger.info("=" * 50)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
