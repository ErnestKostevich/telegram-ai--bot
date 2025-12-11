#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI DISCO BOT v4.0 - Multi-Language Telegram Bot with Unified Context
Features:
- Unified context for text, photos, voice, files
- Group chat support with moderation
- VIP system for users and groups
- Multi-language support (RU, EN, IT)
"""

import os
import json
import logging
import random
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
import pytz
import io
from urllib.parse import quote as urlquote
import base64
import tempfile

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, Message, ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatMemberStatus

import google.generativeai as genai
import aiohttp
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx

from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, 
    DateTime, JSON, Text, BigInteger, inspect, text as sa_text
)
from sqlalchemy.orm import sessionmaker, declarative_base

# ============================================
# CONFIGURATION
# ============================================

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

# Context settings
MAX_CONTEXT_MESSAGES = 15  # Maximum messages in unified context per user
MAX_CONTEXT_IMAGES = 3     # Maximum images to keep in context

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ BOT_TOKEN или GEMINI_API_KEY не установлены!")
    raise ValueError("Required environment variables missing")

# ============================================
# GEMINI CONFIGURATION
# ============================================

genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

SYSTEM_INSTRUCTION = """Ты — AI DISCO BOT, многофункциональный, очень умный и вежливый ассистент, основанный на Gemini 2.5. 
Всегда отвечай на том языке, на котором к тебе обращаются, используя дружелюбный и вовлекающий тон. 
Твои ответы должны быть структурированы, по возможности разделены на абзацы и никогда не превышать 4000 символов (ограничение Telegram). 
Твой создатель — @Ernest_Kostevich. Включай в ответы эмодзи, где это уместно.

ВАЖНО: Ты можешь видеть изображения, анализировать документы и понимать голосовые сообщения. 
Если пользователь отправляет фото без подписи, используй контекст предыдущих сообщений чтобы понять что нужно сделать.
Если контекст не ясен - вежливо уточни что пользователь хочет сделать с изображением."""

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction=SYSTEM_INSTRUCTION
)

# ============================================
# UNIFIED CONTEXT CLASS
# ============================================

@dataclass
class ContextMessage:
    """Single message in unified context"""
    role: str  # 'user' or 'model'
    content_type: str  # 'text', 'image', 'file', 'voice'
    text: str = ""
    image_data: Optional[bytes] = None
    file_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class UnifiedContext:
    """Unified context manager for multimodal conversations"""
    
    def __init__(self, max_messages: int = MAX_CONTEXT_MESSAGES, max_images: int = MAX_CONTEXT_IMAGES):
        self.messages: List[ContextMessage] = []
        self.max_messages = max_messages
        self.max_images = max_images
        self.pending_image: Optional[bytes] = None  # For photos without caption
    
    def add_user_text(self, text: str):
        """Add user text message"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='text',
            text=text
        ))
        self._trim_context()
    
    def add_user_image(self, image_data: bytes, caption: str = ""):
        """Add user image with optional caption"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='image',
            text=caption,
            image_data=image_data
        ))
        self._trim_context()
    
    def add_user_voice(self, transcription: str):
        """Add transcribed voice message"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='voice',
            text=f"[Голосовое сообщение]: {transcription}"
        ))
        self._trim_context()
    
    def add_user_file(self, file_name: str, content: str):
        """Add file content"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='file',
            text=f"[Файл: {file_name}]\n{content}",
            file_name=file_name
        ))
        self._trim_context()
    
    def add_assistant_response(self, text: str):
        """Add assistant response"""
        self.messages.append(ContextMessage(
            role='model',
            content_type='text',
            text=text
        ))
        self._trim_context()
    
    def set_pending_image(self, image_data: bytes):
        """Set pending image waiting for context"""
        self.pending_image = image_data
    
    def get_pending_image(self) -> Optional[bytes]:
        """Get and clear pending image"""
        img = self.pending_image
        self.pending_image = None
        return img
    
    def _trim_context(self):
        """Trim context to max limits"""
        # Trim total messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        
        # Trim images (keep only last N images)
        image_count = sum(1 for m in self.messages if m.content_type == 'image')
        if image_count > self.max_images:
            # Remove oldest images
            to_remove = image_count - self.max_images
            new_messages = []
            for msg in self.messages:
                if msg.content_type == 'image' and to_remove > 0:
                    to_remove -= 1
                    continue
                new_messages.append(msg)
            self.messages = new_messages
    
    def build_gemini_content(self) -> List:
        """Build content for Gemini API"""
        contents = []
        
        for msg in self.messages:
            parts = []
            
            if msg.text:
                parts.append(msg.text)
            
            if msg.image_data:
                try:
                    img = Image.open(io.BytesIO(msg.image_data))
                    parts.append(img)
                except Exception as e:
                    logger.warning(f"Error loading image: {e}")
            
            if parts:
                contents.append({
                    'role': msg.role,
                    'parts': parts
                })
        
        return contents
    
    def get_text_history(self) -> str:
        """Get text-only history for display"""
        history = []
        for msg in self.messages:
            prefix = "👤" if msg.role == 'user' else "🤖"
            if msg.content_type == 'image':
                history.append(f"{prefix} [Изображение] {msg.text}")
            else:
                history.append(f"{prefix} {msg.text[:100]}...")
        return "\n".join(history[-5:])  # Last 5 messages
    
    def clear(self):
        """Clear all context"""
        self.messages.clear()
        self.pending_image = None


# ============================================
# DATABASE MODELS
# ============================================

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
    language = Column(String(5), default='ru')


class GroupChat(Base):
    """Model for group chat settings"""
    __tablename__ = 'group_chats'
    
    id = Column(BigInteger, primary_key=True)  # chat_id (negative for groups)
    title = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    welcome_text = Column(Text, default="Добро пожаловать, {name}! 👋")
    welcome_enabled = Column(Boolean, default=True)
    rules = Column(Text)
    ai_enabled = Column(Boolean, default=True)
    warns = Column(JSON, default=dict)  # {user_id: count}
    messages_count = Column(Integer, default=0)
    top_users = Column(JSON, default=dict)  # {user_id: msg_count}
    registered = Column(DateTime, default=datetime.now)


class ChatHistory(Base):
    __tablename__ = 'chat_history'
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


# ============================================
# DATABASE INITIALIZATION
# ============================================

engine = None
Session = None

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
        
        # Auto-migration
        try:
            inspector = inspect(engine)
            
            # Migrate users table
            if inspector.has_table('users'):
                columns = [col['name'] for col in inspector.get_columns('users')]
                if 'language' not in columns:
                    logger.warning("Adding 'language' column to 'users'...")
                    with engine.connect() as conn:
                        conn.execute(sa_text("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru'"))
                        conn.commit()
                    logger.info("✅ Column 'language' added.")
            
            # Check if group_chats table exists
            if not inspector.has_table('group_chats'):
                logger.info("Creating 'group_chats' table...")
                
        except Exception as migration_error:
            logger.error(f"❌ Migration error: {migration_error}")
        
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("✅ PostgreSQL connected!")
        
    except Exception as e:
        logger.warning(f"⚠️ DB connection error: {e}. Fallback to JSON.")
        engine = None
        Session = None
else:
    logger.warning("⚠️ DATABASE_URL not set. Using JSON storage.")


# ============================================
# LOCALIZATION STRINGS
# ============================================

localization_strings = {
    'ru': {
        'welcome': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "Привет, {first_name}! Я бот на <b>Gemini 2.5</b>.\n\n"
            "<b>🎯 Возможности:</b>\n"
            "💬 AI-чат с контекстом (помню фото, голос, файлы)\n"
            "📝 Заметки и задачи\n"
            "🌍 Погода и время\n"
            "🎲 Развлечения\n"
            "📎 Анализ файлов (VIP)\n"
            "🔍 Анализ изображений (VIP)\n"
            "🖼️ Генерация изображений (VIP)\n"
            "👥 Модерация групп\n\n"
            "<b>⚡ Команды:</b>\n"
            "/help - Все команды\n"
            "/language - Сменить язык\n"
            "/vip - Статус VIP\n\n"
            "<b>👨‍💻 Создатель:</b> @{creator}"
        ),
        'lang_changed': "✅ Язык изменен на Русский 🇷🇺",
        'lang_choose': "🌐 Выберите язык:",
        'main_keyboard': {
            'chat': "💬 AI Чат", 'notes': "📝 Заметки", 'weather': "🌍 Погода", 'time': "⏰ Время",
            'games': "🎲 Развлечения", 'info': "ℹ️ Инфо", 'vip_menu': "💎 VIP Меню",
            'admin_panel': "👑 Админ Панель", 'generate': "🖼️ Генерация"
        },
        'help_title': "📚 <b>Выберите раздел справки:</b>\n\nНажмите кнопку ниже для просмотра команд по теме.",
        'help_back': "🔙 Назад",
        'help_sections': {
            'help_basic': "🏠 Основные", 'help_ai': "💬 AI", 'help_memory': "🧠 Память",
            'help_notes': "📝 Заметки", 'help_todo': "📋 Задачи", 'help_utils': "🌍 Утилиты",
            'help_games': "🎲 Развлечения", 'help_vip': "💎 VIP", 'help_admin': "👑 Админ",
            'help_groups': "👥 Группы"
        },
        'help_text': {
            'help_basic': (
                "🏠 <b>Основные команды:</b>\n\n"
                "🚀 /start - Запуск бота\n"
                "📖 /help - Список команд\n"
                "ℹ️ /info - Информация о боте\n"
                "📊 /status - Статус и статистика\n"
                "👤 /profile - Профиль\n"
                "⏱ /uptime - Время работы\n"
                "🗣️ /language - Сменить язык"
            ),
            'help_ai': (
                "💬 <b>AI команды:</b>\n\n"
                "🤖 /ai [вопрос] - Задать вопрос AI\n"
                "🧹 /clear - Очистить контекст\n\n"
                "💡 <b>Подсказка:</b> Бот помнит контекст разговора, включая фото и голосовые!"
            ),
            'help_memory': "🧠 <b>Память:</b>\n\n💾 /memorysave [ключ] [значение]\n🔍 /memoryget [ключ]\n📋 /memorylist\n🗑 /memorydel [ключ]",
            'help_notes': "📝 <b>Заметки:</b>\n\n➕ /note [текст]\n📋 /notes\n🗑 /delnote [номер]",
            'help_todo': "📋 <b>Задачи:</b>\n\n➕ /todo add [текст]\n📋 /todo list\n🗑 /todo del [номер]",
            'help_utils': "🌍 <b>Утилиты:</b>\n\n🕐 /time [город]\n☀️ /weather [город]\n🌐 /translate [язык] [текст]\n🧮 /calc [выражение]\n🔑 /password [длина]",
            'help_games': "🎲 <b>Развлечения:</b>\n\n🎲 /random [min] [max]\n🎯 /dice\n🪙 /coin\n😄 /joke\n💭 /quote\n🔬 /fact",
            'help_vip': (
                "💎 <b>VIP команды:</b>\n\n"
                "👑 /vip - Статус VIP\n"
                "🖼️ /generate [описание] - Генерация изображения\n"
                "⏰ /remind [минуты] [текст] - Напоминание\n"
                "📋 /reminders - Список напоминаний\n"
                "📎 Отправь файл - Анализ\n"
                "📸 Отправь фото - Анализ"
            ),
            'help_admin': (
                "👑 <b>Команды Создателя:</b>\n\n"
                "🎁 /grant_vip [id] [срок] - Выдать VIP\n"
                "❌ /revoke_vip [id] - Забрать VIP\n"
                "👥 /users - Список пользователей\n"
                "📢 /broadcast [текст] - Рассылка\n"
                "📈 /stats - Статистика\n"
                "💾 /backup - Резервная копия"
            ),
            'help_groups': (
                "👥 <b>Команды для групп:</b>\n\n"
                "<b>Модерация:</b>\n"
                "🚫 /ban - Забанить (ответом)\n"
                "✅ /unban [id] - Разбанить\n"
                "👢 /kick - Кикнуть\n"
                "🔇 /mute [мин] - Замутить\n"
                "🔊 /unmute - Размутить\n"
                "⚠️ /warn - Предупреждение\n"
                "✅ /unwarn - Снять варн\n"
                "📋 /warns - Список варнов\n\n"
                "<b>Настройки:</b>\n"
                "👋 /setwelcome [текст] - Приветствие\n"
                "🚫 /welcomeoff - Выкл. приветствие\n"
                "📜 /setrules [текст] - Правила\n"
                "📖 /rules - Показать правила\n"
                "🤖 /setai [on/off] - Вкл/выкл AI\n"
                "ℹ️ /chatinfo - Инфо о чате\n"
                "🏆 /top - Топ активных"
            )
        },
        'menu': {
            'chat': "🤖 <b>AI Чат</b>\n\nПросто пиши - я отвечу!\nОтправь фото или голосовое - я пойму!\n/clear - очистить контекст",
            'notes': "📝 <b>Заметки</b>", 'notes_create': "➕ Создать", 'notes_list': "📋 Список",
            'weather': "🌍 <b>Погода</b>\n\n/weather [город]\nПример: /weather London",
            'time': "⏰ <b>Время</b>\n\n/time [город]\nПример: /time Tokyo",
            'games': "🎲 <b>Развлечения</b>", 'games_dice': "🎲 Кубик", 'games_coin': "🪙 Монета",
            'games_joke': "😄 Шутка", 'games_quote': "💭 Цитата", 'games_fact': "🔬 Факт",
            'vip': "💎 <b>VIP Меню</b>", 'vip_reminders': "⏰ Напоминания", 'vip_stats': "📊 Статистика",
            'admin': "👑 <b>Админ Панель</b>", 'admin_users': "👥 Пользователи", 'admin_stats': "📊 Статистика",
            'admin_broadcast': "📢 Рассылка",
            'generate': "🖼️ <b>Генерация (VIP)</b>\n\n/generate [описание]\n\nПримеры:\n• /generate закат\n• /generate город\n\n💡 Gemini Imagen"
        },
        'info': (
            "🤖 <b>AI DISCO BOT v4.0</b>\n\n"
            "<b>Версия:</b> 4.0 (Unified Context)\n"
            "<b>AI:</b> Gemini 2.5 Flash\n"
            "<b>Создатель:</b> @Ernest_Kostevich\n\n"
            "<b>⚡ Особенности:</b>\n"
            "• Единый контекст (текст+фото+голос)\n"
            "• PostgreSQL\n"
            "• VIP для пользователей и групп\n"
            "• Модерация групп\n"
            "• Генерация изображений\n\n"
            "<b>💬 Поддержка:</b> @Ernest_Kostevich"
        ),
        'status': (
            "📊 <b>СТАТУС</b>\n\n"
            "👥 Пользователи: {users}\n"
            "💎 VIP: {vips}\n"
            "👥 Групп: {groups}\n\n"
            "<b>📈 Активность:</b>\n"
            "• Сообщений: {msg_count}\n"
            "• Команд: {cmd_count}\n"
            "• AI запросов: {ai_count}\n\n"
            "<b>⏱ Работает:</b> {days}д {hours}ч\n\n"
            "<b>✅ Статус:</b> Онлайн\n"
            "<b>🤖 AI:</b> Gemini 2.5 ✓\n"
            "<b>🗄️ БД:</b> {db_status}"
        ),
        'profile': (
            "👤 <b>{first_name}</b>\n"
            "🆔 <code>{user_id}</code>\n"
            "{username_line}\n"
            "📅 {registered_date}\n"
            "📊 Сообщений: {msg_count}\n"
            "🎯 Команд: {cmd_count}\n"
            "📝 Заметок: {notes_count}"
        ),
        'profile_vip': "\n💎 VIP до: {date}",
        'profile_vip_forever': "\n💎 VIP: Навсегда ♾️",
        'uptime': "⏱ <b>АПТАЙМ</b>\n\n🕐 Запущен: {start_time}\n⏰ Работает: {days}д {hours}ч {minutes}м\n\n✅ Онлайн",
        'vip_status_active': "💎 <b>VIP СТАТУС</b>\n\n✅ Активен!\n\n",
        'vip_status_until': "⏰ До: {date}\n\n",
        'vip_status_forever': "⏰ Навсегда ♾️\n\n",
        'vip_status_bonus': "<b>🎁 Преимущества:</b>\n• ⏰ Напоминания\n• 🖼️ Генерация изображений\n• 🔍 Анализ изображений\n• 📎 Анализ документов",
        'vip_status_inactive': "💎 <b>VIP СТАТУС</b>\n\n❌ Нет VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'vip_only': "💎 Эта функция доступна только для VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'admin_only': "❌ Только для создателя.",
        'gen_prompt_needed': "❓ /generate [описание]\n\nПример: /generate закат над океаном",
        'gen_in_progress': "🎨 Генерирую с Imagen 3...",
        'gen_caption': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Ошибка генерации изображения",
        'gen_error_api': "❌ Ошибка API: {error}",
        'ai_prompt_needed': "❓ /ai [вопрос]",
        'ai_error': "😔 Ошибка AI, попробуйте снова.",
        'clear_context': "🧹 Контекст чата очищен!",
        'note_prompt_needed': "❓ /note [текст]",
        'note_saved': "✅ Заметка #{num} сохранена!\n\n📝 {text}",
        'notes_empty': "📭 У вас нет заметок.",
        'notes_list_title': "📝 <b>Заметки ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "❓ /delnote [номер]",
        'delnote_success': "✅ Заметка #{num} удалена:\n\n📝 {text}",
        'delnote_not_found': "❌ Заметка #{num} не найдена.",
        'delnote_invalid_num': "❌ Укажите корректный номер.",
        'todo_prompt_needed': "❓ /todo add [текст] | list | del [номер]",
        'todo_add_prompt_needed': "❓ /todo add [текст]",
        'todo_saved': "✅ Задача #{num} добавлена!\n\n📋 {text}",
        'todo_empty': "📭 У вас нет задач.",
        'todo_list_title': "📋 <b>Задачи ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "❓ /todo del [номер]",
        'todo_del_success': "✅ Задача #{num} удалена:\n\n📋 {text}",
        'todo_del_not_found': "❌ Задача #{num} не найдена.",
        'todo_del_invalid_num': "❌ Укажите корректный номер.",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 Время: {time}\n📅 Дата: {date}\n🌍 Пояс: {tz}",
        'time_city_not_found': "❌ Город '{city}' не найден.",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 Температура: {temp}°C\n🤔 Ощущается: {feels}°C\n☁️ {desc}\n💧 Влажность: {humidity}%\n💨 Ветер: {wind} км/ч",
        'weather_city_not_found': "❌ Город '{city}' не найден.",
        'weather_error': "❌ Ошибка получения погоды.",
        'translate_prompt_needed': "❓ /translate [язык] [текст]\n\nПример: /translate en Привет",
        'translate_error': "❌ Ошибка перевода.",
        'calc_prompt_needed': "❓ /calc [выражение]\n\nПример: /calc 2+2*5",
        'calc_result': "🧮 <b>Результат:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "❌ Ошибка вычисления.",
        'password_length_error': "❌ Длина пароля должна быть от 8 до 50.",
        'password_result': "🔑 <b>Ваш пароль:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "❌ Укажите корректную длину.",
        'random_result': "🎲 Случайное число от {min} до {max}:\n\n<b>{result}</b>",
        'random_invalid_range': "❌ Укажите корректный диапазон.",
        'dice_result': "🎲 {emoji} Выпало: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Выпало: <b>{result}</b>",
        'coin_heads': "Орёл", 'coin_tails': "Решка",
        'joke_title': "😄 <b>Шутка:</b>\n\n",
        'quote_title': "💭 <b>Цитата:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "🔬 <b>Факт:</b>\n\n",
        'remind_prompt_needed': "❓ /remind [минуты] [текст]",
        'remind_success': "⏰ Напоминание создано!\n\n📝 {text}\n🕐 Через {minutes} мин",
        'remind_invalid_time': "❌ Укажите корректное время.",
        'reminders_empty': "📭 Нет активных напоминаний.",
        'reminders_list_title': "⏰ <b>Напоминания ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\n📝 {text}\n\n",
        'reminder_alert': "⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
        'grant_vip_prompt': "❓ /grant_vip [id/@username] [срок]\n\nСроки: week, month, year, forever",
        'grant_vip_user_not_found': "❌ Пользователь/чат '{id}' не найден.",
        'grant_vip_invalid_duration': "❌ Неверный срок. Доступно: week, month, year, forever",
        'grant_vip_success': "✅ VIP статус выдан!\n\n🆔 <code>{id}</code>\n⏰ {duration_text}",
        'grant_vip_dm': "🎉 Вам выдан VIP статус {duration_text}!",
        'duration_until': "до {date}",
        'duration_forever': "навсегда",
        'revoke_vip_prompt': "❓ /revoke_vip [id/@username]",
        'revoke_vip_success': "✅ VIP статус отозван у <code>{id}</code>.",
        'users_list_title': "👥 <b>ПОЛЬЗОВАТЕЛИ ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... и ещё {count}</i>",
        'broadcast_prompt': "❓ /broadcast [текст сообщения]",
        'broadcast_started': "📤 Начинаю рассылку...",
        'broadcast_finished': "✅ Рассылка завершена!\n\n✅ Успешно: {success}\n❌ Ошибок: {failed}",
        'broadcast_dm': "📢 <b>Сообщение от создателя:</b>\n\n{text}",
        'stats_admin_title': "📊 <b>СТАТИСТИКА</b>\n\n<b>👥 Пользователи:</b> {users}\n<b>💎 VIP:</b> {vips}\n\n<b>📈 Активность:</b>\n• Сообщений: {msg_count}\n• Команд: {cmd_count}\n• AI запросов: {ai_count}",
        'backup_success': "✅ Бэкап создан\n\n📅 {date}",
        'backup_error': "❌ Ошибка бэкапа: {error}",
        'file_received': "📥 Загружаю файл...",
        'file_analyzing': "📄 <b>Файл:</b> {filename}\n\n🤖 <b>Анализ:</b>\n\n{text}",
        'file_error': "❌ Ошибка обработки: {error}",
        'photo_analyzing': "🔍 Анализирую изображение...",
        'photo_result': "📸 <b>Анализ:</b>\n\n{text}\n\n💎 VIP",
        'photo_error': "❌ Ошибка обработки фото: {error}",
        'photo_no_caption': "📸 Получил изображение. Что мне с ним сделать?\n\n💡 Подсказка: отправьте текст с вопросом об этом фото.",
        'voice_transcribing': "🎙️ Распознаю голос...",
        'voice_result': "📝 <b>Транскрипция:</b>\n\n{text}",
        'voice_error': "❌ Ошибка обработки голоса: {error}",
        'error_generic': "❌ Ошибка: {error}",
        'section_not_found': "❌ Раздел не найден.",
        
        # Group moderation strings
        'need_admin': "❌ Нужны права администратора.",
        'need_reply': "❌ Ответьте на сообщение пользователя.",
        'bot_need_admin': "❌ Бот должен быть администратором.",
        'cant_self': "❌ Нельзя применить к себе.",
        'cant_admin': "❌ Нельзя применить к администратору.",
        'user_banned': "🚫 <b>{name}</b> забанен.\n\nПричина: {reason}",
        'user_unbanned': "✅ Пользователь <code>{id}</code> разбанен.",
        'user_kicked': "👢 <b>{name}</b> кикнут.",
        'user_muted': "🔇 <b>{name}</b> замучен на {minutes} мин.",
        'user_unmuted': "🔊 <b>{name}</b> размучен.",
        'user_warned': "⚠️ <b>{name}</b> получил предупреждение ({count}/3).\n\nПричина: {reason}",
        'user_warned_ban': "🚫 <b>{name}</b> забанен (3/3 варнов).",
        'user_unwarned': "✅ Варн снят с <b>{name}</b> ({count}/3).",
        'warns_list': "⚠️ <b>Варны {name}:</b> {count}/3",
        'warns_empty': "✅ У <b>{name}</b> нет варнов.",
        'welcome_set': "✅ Приветствие установлено!\n\n{text}",
        'welcome_off': "✅ Приветствие выключено.",
        'rules_set': "✅ Правила установлены!",
        'rules_text': "📜 <b>Правила чата:</b>\n\n{rules}",
        'rules_empty': "📜 Правила не установлены.",
        'ai_enabled': "✅ AI включен в этом чате.",
        'ai_disabled': "❌ AI выключен в этом чате.",
        'chat_info': (
            "ℹ️ <b>Информация о чате</b>\n\n"
            "📛 Название: {title}\n"
            "🆔 ID: <code>{id}</code>\n"
            "💎 VIP: {vip_status}\n"
            "🤖 AI: {ai_status}\n"
            "👋 Приветствие: {welcome_status}\n"
            "📊 Сообщений: {messages}"
        ),
        'top_users': "🏆 <b>Топ активных:</b>\n\n",
        'top_users_item': "{medal} <b>{name}</b> - {count} сообщений\n",
        'top_empty': "📭 Пока нет статистики.",
        'new_member_welcome': "👋 Добро пожаловать, <b>{name}</b>!",
        'group_help': "👥 Используйте /help и выберите раздел 'Группы' для списка команд модерации.",
    },
    'en': {
        'welcome': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "Hi, {first_name}! I'm a bot powered by <b>Gemini 2.5</b>.\n\n"
            "<b>🎯 Features:</b>\n"
            "💬 AI chat with context (remembers photos, voice, files)\n"
            "📝 Notes and To-Dos\n"
            "🌍 Weather and Time\n"
            "🎲 Entertainment\n"
            "📎 File Analysis (VIP)\n"
            "🔍 Image Analysis (VIP)\n"
            "🖼️ Image Generation (VIP)\n"
            "👥 Group moderation\n\n"
            "<b>⚡ Commands:</b>\n"
            "/help - All commands\n"
            "/language - Change language\n"
            "/vip - VIP Status\n\n"
            "<b>👨‍💻 Creator:</b> @{creator}"
        ),
        'lang_changed': "✅ Language changed to English 🇬🇧",
        'lang_choose': "🌐 Please select a language:",
        'main_keyboard': {
            'chat': "💬 AI Chat", 'notes': "📝 Notes", 'weather': "🌍 Weather", 'time': "⏰ Time",
            'games': "🎲 Games", 'info': "ℹ️ Info", 'vip_menu': "💎 VIP Menu",
            'admin_panel': "👑 Admin Panel", 'generate': "🖼️ Generate"
        },
        'help_title': "📚 <b>Choose a help section:</b>\n\nPress a button below to see commands.",
        'help_back': "🔙 Back",
        'help_sections': {
            'help_basic': "🏠 Basic", 'help_ai': "💬 AI", 'help_memory': "🧠 Memory",
            'help_notes': "📝 Notes", 'help_todo': "📋 To-Do", 'help_utils': "🌍 Utilities",
            'help_games': "🎲 Games", 'help_vip': "💎 VIP", 'help_admin': "👑 Admin",
            'help_groups': "👥 Groups"
        },
        'help_text': {
            'help_basic': "🏠 <b>Basic Commands:</b>\n\n🚀 /start - Start bot\n📖 /help - Commands\nℹ️ /info - Bot info\n📊 /status - Status\n👤 /profile - Profile\n⏱ /uptime - Uptime\n🗣️ /language - Language",
            'help_ai': "💬 <b>AI Commands:</b>\n\n🤖 /ai [question] - Ask AI\n🧹 /clear - Clear context\n\n💡 Bot remembers context including photos and voice!",
            'help_memory': "🧠 <b>Memory:</b>\n\n💾 /memorysave [key] [value]\n🔍 /memoryget [key]\n📋 /memorylist\n🗑 /memorydel [key]",
            'help_notes': "📝 <b>Notes:</b>\n\n➕ /note [text]\n📋 /notes\n🗑 /delnote [number]",
            'help_todo': "📋 <b>To-Do:</b>\n\n➕ /todo add [text]\n📋 /todo list\n🗑 /todo del [number]",
            'help_utils': "🌍 <b>Utilities:</b>\n\n🕐 /time [city]\n☀️ /weather [city]\n🌐 /translate [lang] [text]\n🧮 /calc [expr]\n🔑 /password [length]",
            'help_games': "🎲 <b>Games:</b>\n\n🎲 /random [min] [max]\n🎯 /dice\n🪙 /coin\n😄 /joke\n💭 /quote\n🔬 /fact",
            'help_vip': "💎 <b>VIP Commands:</b>\n\n👑 /vip - Status\n🖼️ /generate [prompt]\n⏰ /remind [min] [text]\n📋 /reminders\n📎 Send file - Analyze\n📸 Send photo - Analyze",
            'help_admin': "👑 <b>Creator Commands:</b>\n\n🎁 /grant_vip [id] [duration]\n❌ /revoke_vip [id]\n👥 /users\n📢 /broadcast [text]\n📈 /stats\n💾 /backup",
            'help_groups': "👥 <b>Group Commands:</b>\n\n<b>Moderation:</b>\n🚫 /ban - Ban (reply)\n✅ /unban [id]\n👢 /kick\n🔇 /mute [min]\n🔊 /unmute\n⚠️ /warn\n✅ /unwarn\n📋 /warns\n\n<b>Settings:</b>\n👋 /setwelcome [text]\n🚫 /welcomeoff\n📜 /setrules [text]\n📖 /rules\n🤖 /setai [on/off]\nℹ️ /chatinfo\n🏆 /top"
        },
        'menu': {
            'chat': "🤖 <b>AI Chat</b>\n\nJust type - I'll answer!\nSend photo or voice - I understand!\n/clear - clear context",
            'notes': "📝 <b>Notes</b>", 'notes_create': "➕ Create", 'notes_list': "📋 List",
            'weather': "🌍 <b>Weather</b>\n\n/weather [city]",
            'time': "⏰ <b>Time</b>\n\n/time [city]",
            'games': "🎲 <b>Games</b>", 'games_dice': "🎲 Dice", 'games_coin': "🪙 Coin",
            'games_joke': "😄 Joke", 'games_quote': "💭 Quote", 'games_fact': "🔬 Fact",
            'vip': "💎 <b>VIP Menu</b>", 'vip_reminders': "⏰ Reminders", 'vip_stats': "📊 Stats",
            'admin': "👑 <b>Admin Panel</b>", 'admin_users': "👥 Users", 'admin_stats': "📊 Stats",
            'admin_broadcast': "📢 Broadcast",
            'generate': "🖼️ <b>Generation (VIP)</b>\n\n/generate [prompt]"
        },
        'info': "🤖 <b>AI DISCO BOT v4.0</b>\n\n<b>Version:</b> 4.0 (Unified Context)\n<b>AI:</b> Gemini 2.5 Flash\n<b>Creator:</b> @Ernest_Kostevich\n\n<b>⚡ Features:</b>\n• Unified context (text+photo+voice)\n• PostgreSQL\n• VIP for users and groups\n• Group moderation\n• Image generation\n\n<b>💬 Support:</b> @Ernest_Kostevich",
        'status': "📊 <b>STATUS</b>\n\n👥 Users: {users}\n💎 VIPs: {vips}\n👥 Groups: {groups}\n\n<b>📈 Activity:</b>\n• Messages: {msg_count}\n• Commands: {cmd_count}\n• AI Requests: {ai_count}\n\n<b>⏱ Uptime:</b> {days}d {hours}h\n\n<b>✅ Status:</b> Online\n<b>🤖 AI:</b> Gemini 2.5 ✓\n<b>🗄️ DB:</b> {db_status}",
        'profile': "👤 <b>{first_name}</b>\n🆔 <code>{user_id}</code>\n{username_line}\n📅 {registered_date}\n📊 Messages: {msg_count}\n🎯 Commands: {cmd_count}\n📝 Notes: {notes_count}",
        'profile_vip': "\n💎 VIP until: {date}",
        'profile_vip_forever': "\n💎 VIP: Forever ♾️",
        'uptime': "⏱ <b>UPTIME</b>\n\n🕐 Started: {start_time}\n⏰ Running: {days}d {hours}h {minutes}m\n\n✅ Online",
        'vip_status_active': "💎 <b>VIP STATUS</b>\n\n✅ Active!\n\n",
        'vip_status_until': "⏰ Until: {date}\n\n",
        'vip_status_forever': "⏰ Forever ♾️\n\n",
        'vip_status_bonus': "<b>🎁 Perks:</b>\n• ⏰ Reminders\n• 🖼️ Image Generation\n• 🔍 Image Analysis\n• 📎 Document Analysis",
        'vip_status_inactive': "💎 <b>VIP STATUS</b>\n\n❌ No VIP.\n\nContact @Ernest_Kostevich",
        'vip_only': "💎 VIP only feature.\n\nContact @Ernest_Kostevich",
        'admin_only': "❌ Creator only.",
        'gen_prompt_needed': "❓ /generate [prompt]",
        'gen_in_progress': "🎨 Generating with Imagen 3...",
        'gen_caption': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Image generation failed",
        'gen_error_api': "❌ API Error: {error}",
        'ai_prompt_needed': "❓ /ai [question]",
        'ai_error': "😔 AI Error, try again.",
        'clear_context': "🧹 Chat context cleared!",
        'note_prompt_needed': "❓ /note [text]",
        'note_saved': "✅ Note #{num} saved!\n\n📝 {text}",
        'notes_empty': "📭 No notes.",
        'notes_list_title': "📝 <b>Notes ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "❓ /delnote [number]",
        'delnote_success': "✅ Note #{num} deleted:\n\n📝 {text}",
        'delnote_not_found': "❌ Note #{num} not found.",
        'delnote_invalid_num': "❌ Invalid number.",
        'todo_prompt_needed': "❓ /todo add [text] | list | del [number]",
        'todo_add_prompt_needed': "❓ /todo add [text]",
        'todo_saved': "✅ Task #{num} added!\n\n📋 {text}",
        'todo_empty': "📭 No tasks.",
        'todo_list_title': "📋 <b>Tasks ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "❓ /todo del [number]",
        'todo_del_success': "✅ Task #{num} deleted:\n\n📋 {text}",
        'todo_del_not_found': "❌ Task #{num} not found.",
        'todo_del_invalid_num': "❌ Invalid number.",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 Time: {time}\n📅 Date: {date}\n🌍 Zone: {tz}",
        'time_city_not_found': "❌ City '{city}' not found.",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 Temp: {temp}°C\n🤔 Feels: {feels}°C\n☁️ {desc}\n💧 Humidity: {humidity}%\n💨 Wind: {wind} km/h",
        'weather_city_not_found': "❌ City '{city}' not found.",
        'weather_error': "❌ Weather error.",
        'translate_prompt_needed': "❓ /translate [lang] [text]",
        'translate_error': "❌ Translation error.",
        'calc_prompt_needed': "❓ /calc [expression]",
        'calc_result': "🧮 <b>Result:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "❌ Calculation error.",
        'password_length_error': "❌ Password length 8-50.",
        'password_result': "🔑 <b>Password:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "❌ Invalid length.",
        'random_result': "🎲 Random {min}-{max}:\n\n<b>{result}</b>",
        'random_invalid_range': "❌ Invalid range.",
        'dice_result': "🎲 {emoji} Rolled: <b>{result}</b>",
        'coin_result': "🪙 {emoji} It's <b>{result}</b>",
        'coin_heads': "Heads", 'coin_tails': "Tails",
        'joke_title': "😄 <b>Joke:</b>\n\n",
        'quote_title': "💭 <b>Quote:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "🔬 <b>Fact:</b>\n\n",
        'remind_prompt_needed': "❓ /remind [minutes] [text]",
        'remind_success': "⏰ Reminder set!\n\n📝 {text}\n🕐 In {minutes} min",
        'remind_invalid_time': "❌ Invalid time.",
        'reminders_empty': "📭 No reminders.",
        'reminders_list_title': "⏰ <b>Reminders ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\n📝 {text}\n\n",
        'reminder_alert': "⏰ <b>REMINDER</b>\n\n📝 {text}",
        'grant_vip_prompt': "❓ /grant_vip [id] [duration]\n\nDurations: week, month, year, forever",
        'grant_vip_user_not_found': "❌ User/chat '{id}' not found.",
        'grant_vip_invalid_duration': "❌ Invalid duration.",
        'grant_vip_success': "✅ VIP granted!\n\n🆔 <code>{id}</code>\n⏰ {duration_text}",
        'grant_vip_dm': "🎉 VIP granted {duration_text}!",
        'duration_until': "until {date}",
        'duration_forever': "forever",
        'revoke_vip_prompt': "❓ /revoke_vip [id]",
        'revoke_vip_success': "✅ VIP revoked for <code>{id}</code>.",
        'users_list_title': "👥 <b>USERS ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... and {count} more</i>",
        'broadcast_prompt': "❓ /broadcast [message]",
        'broadcast_started': "📤 Broadcasting...",
        'broadcast_finished': "✅ Done!\n\n✅ Success: {success}\n❌ Failed: {failed}",
        'broadcast_dm': "📢 <b>From creator:</b>\n\n{text}",
        'stats_admin_title': "📊 <b>STATISTICS</b>\n\n<b>👥 Users:</b> {users}\n<b>💎 VIPs:</b> {vips}\n\n<b>📈 Activity:</b>\n• Messages: {msg_count}\n• Commands: {cmd_count}\n• AI: {ai_count}",
        'backup_success': "✅ Backup created\n\n📅 {date}",
        'backup_error': "❌ Backup error: {error}",
        'file_received': "📥 Loading file...",
        'file_analyzing': "📄 <b>File:</b> {filename}\n\n🤖 <b>Analysis:</b>\n\n{text}",
        'file_error': "❌ Error: {error}",
        'photo_analyzing': "🔍 Analyzing...",
        'photo_result': "📸 <b>Analysis:</b>\n\n{text}\n\n💎 VIP",
        'photo_error': "❌ Photo error: {error}",
        'photo_no_caption': "📸 Got image. What should I do with it?\n\n💡 Tip: send a text with your question about this photo.",
        'voice_transcribing': "🎙️ Transcribing...",
        'voice_result': "📝 <b>Transcription:</b>\n\n{text}",
        'voice_error': "❌ Voice error: {error}",
        'error_generic': "❌ Error: {error}",
        'section_not_found': "❌ Section not found.",
        'need_admin': "❌ Admin rights required.",
        'need_reply': "❌ Reply to a user's message.",
        'bot_need_admin': "❌ Bot must be admin.",
        'cant_self': "❌ Can't apply to yourself.",
        'cant_admin': "❌ Can't apply to admin.",
        'user_banned': "🚫 <b>{name}</b> banned.\n\nReason: {reason}",
        'user_unbanned': "✅ User <code>{id}</code> unbanned.",
        'user_kicked': "👢 <b>{name}</b> kicked.",
        'user_muted': "🔇 <b>{name}</b> muted for {minutes} min.",
        'user_unmuted': "🔊 <b>{name}</b> unmuted.",
        'user_warned': "⚠️ <b>{name}</b> warned ({count}/3).\n\nReason: {reason}",
        'user_warned_ban': "🚫 <b>{name}</b> banned (3/3 warns).",
        'user_unwarned': "✅ Warn removed from <b>{name}</b> ({count}/3).",
        'warns_list': "⚠️ <b>Warns for {name}:</b> {count}/3",
        'warns_empty': "✅ <b>{name}</b> has no warns.",
        'welcome_set': "✅ Welcome message set!\n\n{text}",
        'welcome_off': "✅ Welcome disabled.",
        'rules_set': "✅ Rules set!",
        'rules_text': "📜 <b>Chat rules:</b>\n\n{rules}",
        'rules_empty': "📜 No rules set.",
        'ai_enabled': "✅ AI enabled in this chat.",
        'ai_disabled': "❌ AI disabled in this chat.",
        'chat_info': "ℹ️ <b>Chat Info</b>\n\n📛 Title: {title}\n🆔 ID: <code>{id}</code>\n💎 VIP: {vip_status}\n🤖 AI: {ai_status}\n👋 Welcome: {welcome_status}\n📊 Messages: {messages}",
        'top_users': "🏆 <b>Top active:</b>\n\n",
        'top_users_item': "{medal} <b>{name}</b> - {count} messages\n",
        'top_empty': "📭 No stats yet.",
        'new_member_welcome': "👋 Welcome, <b>{name}</b>!",
        'group_help': "👥 Use /help and select 'Groups' section for moderation commands.",
    },
    'it': {
        'welcome': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "Ciao, {first_name}! Sono un bot basato su <b>Gemini 2.5</b>.\n\n"
            "<b>🎯 Funzionalità:</b>\n"
            "💬 Chat AI con contesto (ricorda foto, voce, file)\n"
            "📝 Note e Impegni\n"
            "🌍 Meteo e Ora\n"
            "🎲 Intrattenimento\n"
            "📎 Analisi File (VIP)\n"
            "🔍 Analisi Immagini (VIP)\n"
            "🖼️ Generazione Immagini (VIP)\n"
            "👥 Moderazione gruppi\n\n"
            "<b>⚡ Comandi:</b>\n"
            "/help - Comandi\n"
            "/language - Lingua\n"
            "/vip - Stato VIP\n\n"
            "<b>👨‍💻 Creatore:</b> @{creator}"
        ),
        'lang_changed': "✅ Lingua: Italiano 🇮🇹",
        'lang_choose': "🌐 Seleziona una lingua:",
        'main_keyboard': {
            'chat': "💬 Chat AI", 'notes': "📝 Note", 'weather': "🌍 Meteo", 'time': "⏰ Ora",
            'games': "🎲 Giochi", 'info': "ℹ️ Info", 'vip_menu': "💎 Menu VIP",
            'admin_panel': "👑 Pannello Admin", 'generate': "🖼️ Genera"
        },
        'help_title': "📚 <b>Scegli una sezione:</b>",
        'help_back': "🔙 Indietro",
        'help_sections': {
            'help_basic': "🏠 Base", 'help_ai': "💬 AI", 'help_memory': "🧠 Memoria",
            'help_notes': "📝 Note", 'help_todo': "📋 Impegni", 'help_utils': "🌍 Utilità",
            'help_games': "🎲 Giochi", 'help_vip': "💎 VIP", 'help_admin': "👑 Admin",
            'help_groups': "👥 Gruppi"
        },
        'help_text': {
            'help_basic': "🏠 <b>Comandi Base:</b>\n\n🚀 /start\n📖 /help\nℹ️ /info\n📊 /status\n👤 /profile\n⏱ /uptime\n🗣️ /language",
            'help_ai': "💬 <b>Comandi AI:</b>\n\n🤖 /ai [domanda]\n🧹 /clear\n\n💡 Il bot ricorda il contesto!",
            'help_memory': "🧠 <b>Memoria:</b>\n\n💾 /memorysave [chiave] [valore]\n🔍 /memoryget [chiave]\n📋 /memorylist\n🗑 /memorydel [chiave]",
            'help_notes': "📝 <b>Note:</b>\n\n➕ /note [testo]\n📋 /notes\n🗑 /delnote [numero]",
            'help_todo': "📋 <b>Impegni:</b>\n\n➕ /todo add [testo]\n📋 /todo list\n🗑 /todo del [numero]",
            'help_utils': "🌍 <b>Utilità:</b>\n\n🕐 /time [città]\n☀️ /weather [città]\n🌐 /translate [lingua] [testo]\n🧮 /calc [expr]\n🔑 /password [lunghezza]",
            'help_games': "🎲 <b>Giochi:</b>\n\n🎲 /random [min] [max]\n🎯 /dice\n🪙 /coin\n😄 /joke\n💭 /quote\n🔬 /fact",
            'help_vip': "💎 <b>Comandi VIP:</b>\n\n👑 /vip\n🖼️ /generate [prompt]\n⏰ /remind [min] [testo]\n📋 /reminders",
            'help_admin': "👑 <b>Comandi Creatore:</b>\n\n🎁 /grant_vip [id] [durata]\n❌ /revoke_vip [id]\n👥 /users\n📢 /broadcast [testo]\n📈 /stats\n💾 /backup",
            'help_groups': "👥 <b>Comandi Gruppo:</b>\n\n<b>Moderazione:</b>\n🚫 /ban\n✅ /unban [id]\n👢 /kick\n🔇 /mute [min]\n🔊 /unmute\n⚠️ /warn\n✅ /unwarn\n📋 /warns\n\n<b>Impostazioni:</b>\n👋 /setwelcome [testo]\n🚫 /welcomeoff\n📜 /setrules [testo]\n📖 /rules\n🤖 /setai [on/off]\nℹ️ /chatinfo\n🏆 /top"
        },
        'menu': {
            'chat': "🤖 <b>Chat AI</b>\n\nScrivi - rispondo!\nInvia foto o vocale - capisco!\n/clear - pulisci",
            'notes': "📝 <b>Note</b>", 'notes_create': "➕ Crea", 'notes_list': "📋 Lista",
            'weather': "🌍 <b>Meteo</b>\n\n/weather [città]",
            'time': "⏰ <b>Ora</b>\n\n/time [città]",
            'games': "🎲 <b>Giochi</b>", 'games_dice': "🎲 Dado", 'games_coin': "🪙 Moneta",
            'games_joke': "😄 Battuta", 'games_quote': "💭 Citazione", 'games_fact': "🔬 Fatto",
            'vip': "💎 <b>Menu VIP</b>", 'vip_reminders': "⏰ Promemoria", 'vip_stats': "📊 Stats",
            'admin': "👑 <b>Pannello Admin</b>", 'admin_users': "👥 Utenti", 'admin_stats': "📊 Stats",
            'admin_broadcast': "📢 Broadcast",
            'generate': "🖼️ <b>Generazione (VIP)</b>\n\n/generate [prompt]"
        },
        'info': "🤖 <b>AI DISCO BOT v4.0</b>\n\n<b>Versione:</b> 4.0\n<b>AI:</b> Gemini 2.5 Flash\n<b>Creatore:</b> @Ernest_Kostevich\n\n<b>💬 Supporto:</b> @Ernest_Kostevich",
        'status': "📊 <b>STATO</b>\n\n👥 Utenti: {users}\n💎 VIP: {vips}\n👥 Gruppi: {groups}\n\n<b>📈 Attività:</b>\n• Messaggi: {msg_count}\n• Comandi: {cmd_count}\n• AI: {ai_count}\n\n<b>⏱ Uptime:</b> {days}g {hours}h\n\n<b>✅ Stato:</b> Online\n<b>🗄️ DB:</b> {db_status}",
        'profile': "👤 <b>{first_name}</b>\n🆔 <code>{user_id}</code>\n{username_line}\n📅 {registered_date}\n📊 Messaggi: {msg_count}\n🎯 Comandi: {cmd_count}\n📝 Note: {notes_count}",
        'profile_vip': "\n💎 VIP fino: {date}",
        'profile_vip_forever': "\n💎 VIP: Illimitato ♾️",
        'uptime': "⏱ <b>UPTIME</b>\n\n🕐 Avviato: {start_time}\n⏰ Attivo: {days}g {hours}h {minutes}m\n\n✅ Online",
        'vip_status_active': "💎 <b>STATO VIP</b>\n\n✅ Attivo!\n\n",
        'vip_status_until': "⏰ Fino: {date}\n\n",
        'vip_status_forever': "⏰ Illimitato ♾️\n\n",
        'vip_status_bonus': "<b>🎁 Vantaggi:</b>\n• ⏰ Promemoria\n• 🖼️ Generazione\n• 🔍 Analisi immagini\n• 📎 Analisi documenti",
        'vip_status_inactive': "💎 <b>STATO VIP</b>\n\n❌ Non VIP.\n\nContatta @Ernest_Kostevich",
        'vip_only': "💎 Solo VIP.\n\nContatta @Ernest_Kostevich",
        'admin_only': "❌ Solo creatore.",
        'gen_prompt_needed': "❓ /generate [prompt]",
        'gen_in_progress': "🎨 Generando...",
        'gen_caption': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Errore generazione",
        'gen_error_api': "❌ Errore API: {error}",
        'ai_prompt_needed': "❓ /ai [domanda]",
        'ai_error': "😔 Errore AI, riprova.",
        'clear_context': "🧹 Contesto pulito!",
        'note_prompt_needed': "❓ /note [testo]",
        'note_saved': "✅ Nota #{num} salvata!\n\n📝 {text}",
        'notes_empty': "📭 Nessuna nota.",
        'notes_list_title': "📝 <b>Note ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "❓ /delnote [numero]",
        'delnote_success': "✅ Nota #{num} eliminata:\n\n📝 {text}",
        'delnote_not_found': "❌ Nota #{num} non trovata.",
        'delnote_invalid_num': "❌ Numero non valido.",
        'todo_prompt_needed': "❓ /todo add [testo] | list | del [numero]",
        'todo_add_prompt_needed': "❓ /todo add [testo]",
        'todo_saved': "✅ Impegno #{num} aggiunto!\n\n📋 {text}",
        'todo_empty': "📭 Nessun impegno.",
        'todo_list_title': "📋 <b>Impegni ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "❓ /todo del [numero]",
        'todo_del_success': "✅ Impegno #{num} eliminato:\n\n📋 {text}",
        'todo_del_not_found': "❌ Impegno #{num} non trovato.",
        'todo_del_invalid_num': "❌ Numero non valido.",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 Ora: {time}\n📅 Data: {date}\n🌍 Fuso: {tz}",
        'time_city_not_found': "❌ Città '{city}' non trovata.",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 Temp: {temp}°C\n🤔 Percepita: {feels}°C\n☁️ {desc}\n💧 Umidità: {humidity}%\n💨 Vento: {wind} km/h",
        'weather_city_not_found': "❌ Città '{city}' non trovata.",
        'weather_error': "❌ Errore meteo.",
        'translate_prompt_needed': "❓ /translate [lingua] [testo]",
        'translate_error': "❌ Errore traduzione.",
        'calc_prompt_needed': "❓ /calc [espressione]",
        'calc_result': "🧮 <b>Risultato:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "❌ Errore calcolo.",
        'password_length_error': "❌ Lunghezza 8-50.",
        'password_result': "🔑 <b>Password:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "❌ Lunghezza non valida.",
        'random_result': "🎲 Casuale {min}-{max}:\n\n<b>{result}</b>",
        'random_invalid_range': "❌ Range non valido.",
        'dice_result': "🎲 {emoji} Uscito: <b>{result}</b>",
        'coin_result': "🪙 {emoji} È uscito: <b>{result}</b>",
        'coin_heads': "Testa", 'coin_tails': "Croce",
        'joke_title': "😄 <b>Battuta:</b>\n\n",
        'quote_title': "💭 <b>Citazione:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "🔬 <b>Fatto:</b>\n\n",
        'remind_prompt_needed': "❓ /remind [minuti] [testo]",
        'remind_success': "⏰ Promemoria impostato!\n\n📝 {text}\n🕐 Tra {minutes} min",
        'remind_invalid_time': "❌ Tempo non valido.",
        'reminders_empty': "📭 Nessun promemoria.",
        'reminders_list_title': "⏰ <b>Promemoria ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\n📝 {text}\n\n",
        'reminder_alert': "⏰ <b>PROMEMORIA</b>\n\n📝 {text}",
        'grant_vip_prompt': "❓ /grant_vip [id] [durata]",
        'grant_vip_user_not_found': "❌ Utente/chat '{id}' non trovato.",
        'grant_vip_invalid_duration': "❌ Durata non valida.",
        'grant_vip_success': "✅ VIP concesso!\n\n🆔 <code>{id}</code>\n⏰ {duration_text}",
        'grant_vip_dm': "🎉 VIP concesso {duration_text}!",
        'duration_until': "fino {date}",
        'duration_forever': "per sempre",
        'revoke_vip_prompt': "❓ /revoke_vip [id]",
        'revoke_vip_success': "✅ VIP revocato per <code>{id}</code>.",
        'users_list_title': "👥 <b>UTENTI ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... e altri {count}</i>",
        'broadcast_prompt': "❓ /broadcast [messaggio]",
        'broadcast_started': "📤 Invio...",
        'broadcast_finished': "✅ Fatto!\n\n✅ Successo: {success}\n❌ Falliti: {failed}",
        'broadcast_dm': "📢 <b>Dal creatore:</b>\n\n{text}",
        'stats_admin_title': "📊 <b>STATISTICHE</b>\n\n<b>👥 Utenti:</b> {users}\n<b>💎 VIP:</b> {vips}\n\n<b>📈 Attività:</b>\n• Messaggi: {msg_count}\n• Comandi: {cmd_count}\n• AI: {ai_count}",
        'backup_success': "✅ Backup creato\n\n📅 {date}",
        'backup_error': "❌ Errore backup: {error}",
        'file_received': "📥 Caricando...",
        'file_analyzing': "📄 <b>File:</b> {filename}\n\n🤖 <b>Analisi:</b>\n\n{text}",
        'file_error': "❌ Errore: {error}",
        'photo_analyzing': "🔍 Analizzando...",
        'photo_result': "📸 <b>Analisi:</b>\n\n{text}\n\n💎 VIP",
        'photo_error': "❌ Errore foto: {error}",
        'photo_no_caption': "📸 Foto ricevuta. Cosa devo fare?\n\n💡 Suggerimento: invia un testo con la tua domanda.",
        'voice_transcribing': "🎙️ Trascrivendo...",
        'voice_result': "📝 <b>Trascrizione:</b>\n\n{text}",
        'voice_error': "❌ Errore voce: {error}",
        'error_generic': "❌ Errore: {error}",
        'section_not_found': "❌ Sezione non trovata.",
        'need_admin': "❌ Servono diritti admin.",
        'need_reply': "❌ Rispondi a un messaggio.",
        'bot_need_admin': "❌ Il bot deve essere admin.",
        'cant_self': "❌ Non puoi applicarlo a te stesso.",
        'cant_admin': "❌ Non puoi applicarlo a un admin.",
        'user_banned': "🚫 <b>{name}</b> bannato.\n\nMotivo: {reason}",
        'user_unbanned': "✅ Utente <code>{id}</code> sbannato.",
        'user_kicked': "👢 <b>{name}</b> espulso.",
        'user_muted': "🔇 <b>{name}</b> mutato per {minutes} min.",
        'user_unmuted': "🔊 <b>{name}</b> smutato.",
        'user_warned': "⚠️ <b>{name}</b> avvisato ({count}/3).\n\nMotivo: {reason}",
        'user_warned_ban': "🚫 <b>{name}</b> bannato (3/3 avvisi).",
        'user_unwarned': "✅ Avviso rimosso da <b>{name}</b> ({count}/3).",
        'warns_list': "⚠️ <b>Avvisi {name}:</b> {count}/3",
        'warns_empty': "✅ <b>{name}</b> non ha avvisi.",
        'welcome_set': "✅ Benvenuto impostato!\n\n{text}",
        'welcome_off': "✅ Benvenuto disabilitato.",
        'rules_set': "✅ Regole impostate!",
        'rules_text': "📜 <b>Regole chat:</b>\n\n{rules}",
        'rules_empty': "📜 Nessuna regola.",
        'ai_enabled': "✅ AI abilitato.",
        'ai_disabled': "❌ AI disabilitato.",
        'chat_info': "ℹ️ <b>Info Chat</b>\n\n📛 Titolo: {title}\n🆔 ID: <code>{id}</code>\n💎 VIP: {vip_status}\n🤖 AI: {ai_status}\n👋 Benvenuto: {welcome_status}\n📊 Messaggi: {messages}",
        'top_users': "🏆 <b>Top attivi:</b>\n\n",
        'top_users_item': "{medal} <b>{name}</b> - {count} messaggi\n",
        'top_empty': "📭 Nessuna statistica.",
        'new_member_welcome': "👋 Benvenuto, <b>{name}</b>!",
        'group_help': "👥 Usa /help e seleziona 'Gruppi' per i comandi di moderazione.",
    }
}


# ============================================
# LOCALIZATION HELPERS
# ============================================

def get_lang(user_id: int) -> str:
    """Get user language, default 'ru'"""
    user = storage.get_user(user_id)
    return user.get('language', 'ru')


def get_text(key: str, lang: str, **kwargs: Any) -> str:
    """Get localized text by key"""
    if lang not in localization_strings:
        lang = 'ru'
    
    try:
        keys = key.split('.')
        text_template = localization_strings[lang]
        for k in keys:
            text_template = text_template[k]
        
        if kwargs:
            return text_template.format(**kwargs)
        return text_template
    except KeyError:
        try:
            fallback_lang = 'ru' if lang != 'ru' else 'en'
            text_template = localization_strings[fallback_lang]
            for k in keys:
                text_template = text_template[k]
            if kwargs:
                return text_template.format(**kwargs)
            return text_template
        except KeyError:
            logger.warning(f"Localization key '{key}' not found")
            return key


# Button map for menu detection
menu_button_map = {}
for lang in localization_strings:
    for btn_key in ['chat', 'notes', 'weather', 'time', 'games', 'info', 'vip_menu', 'admin_panel', 'generate']:
        if btn_key not in menu_button_map:
            menu_button_map[btn_key] = []
        try:
            menu_button_map[btn_key].append(localization_strings[lang]['main_keyboard'][btn_key])
        except:
            pass


# ============================================
# DATA STORAGE CLASS
# ============================================

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.unified_contexts: Dict[int, UnifiedContext] = {}
        self.username_to_id = {}
        
        if not engine:
            self.users = self._load_json(self.users_file, {})
            self.stats = self._load_json(self.stats_file, {
                'total_messages': 0, 'total_commands': 0, 
                'ai_requests': 0, 'start_date': datetime.now().isoformat()
            })
            self._update_username_mapping()
        else:
            self.users = {}
            self.stats = self._get_stats_from_db()
    
    def _load_json(self, filename: str, default: Any) -> Any:
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {int(k) if k.lstrip('-').isdigit() else k: v for k, v in data.items()}
            return default
        except Exception as e:
            logger.warning(f"Error loading {filename}: {e}")
            return default
    
    def _save_json(self, filename: str, data: Any):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error saving {filename}: {e}")
    
    def _update_username_mapping(self):
        self.username_to_id = {}
        for user_id, user_data in self.users.items():
            username = user_data.get('username')
            if username:
                self.username_to_id[username.lower()] = user_id
    
    def _get_stats_from_db(self) -> Dict:
        if not engine:
            return {}
        session = Session()
        try:
            stat = session.query(Statistics).filter_by(key='global').first()
            return stat.value if stat else {
                'total_messages': 0, 'total_commands': 0, 
                'ai_requests': 0, 'start_date': datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"Error loading stats: {e}")
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0}
        finally:
            session.close()
    
    def save_stats(self):
        if engine:
            session = Session()
            try:
                session.merge(Statistics(key='global', value=self.stats, updated_at=datetime.now()))
                session.commit()
            except Exception as e:
                logger.warning(f"Error saving stats: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            self._save_json(self.stats_file, self.stats)
    
    # ============================================
    # USER METHODS
    # ============================================
    
    def get_user_id_by_identifier(self, identifier: str) -> Optional[int]:
        """Get user/chat ID by username or ID string"""
        identifier = identifier.strip()
        if identifier.startswith('@'):
            identifier = identifier[1:]
        
        # Support negative IDs for groups
        if identifier.lstrip('-').isdigit():
            return int(identifier)
        
        if engine:
            session = Session()
            try:
                user = session.query(User).filter(User.username.ilike(f"%{identifier}%")).first()
                return user.id if user else None
            finally:
                session.close()
        
        return self.username_to_id.get(identifier.lower())
    
    def get_user(self, user_id: int) -> Dict:
        """Get user data"""
        if engine:
            session = Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id, language='ru')
                    session.add(user)
                    session.commit()
                    user = session.query(User).filter_by(id=user_id).first()
                
                return {
                    'id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'vip': user.vip,
                    'vip_until': user.vip_until.isoformat() if user.vip_until else None,
                    'notes': user.notes or [],
                    'todos': user.todos or [],
                    'memory': user.memory or {},
                    'reminders': user.reminders or [],
                    'registered': user.registered.isoformat() if user.registered else datetime.now().isoformat(),
                    'last_active': user.last_active.isoformat() if user.last_active else datetime.now().isoformat(),
                    'messages_count': user.messages_count or 0,
                    'commands_count': user.commands_count or 0,
                    'language': user.language or 'ru'
                }
            except Exception as e:
                logger.error(f"Error get_user ({user_id}): {e}")
                return {'id': user_id, 'language': 'ru'}
            finally:
                session.close()
        else:
            if user_id not in self.users:
                self.users[user_id] = {
                    'id': user_id, 'username': '', 'first_name': '', 'vip': False, 'vip_until': None,
                    'notes': [], 'todos': [], 'memory': {}, 'reminders': [],
                    'registered': datetime.now().isoformat(), 'last_active': datetime.now().isoformat(),
                    'messages_count': 0, 'commands_count': 0, 'language': 'ru'
                }
                self._save_json(self.users_file, self.users)
            return self.users[user_id]
    
    def update_user(self, user_id: int, data: Dict):
        """Update user data"""
        if engine:
            session = Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id)
                    session.add(user)
                
                for key, value in data.items():
                    if key == 'vip_until' and value:
                        value = datetime.fromisoformat(value) if isinstance(value, str) else value
                    setattr(user, key, value)
                
                user.last_active = datetime.now()
                session.commit()
            except Exception as e:
                logger.warning(f"Error updating user {user_id}: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            user = self.get_user(user_id)
            user.update(data)
            user['last_active'] = datetime.now().isoformat()
            self._save_json(self.users_file, self.users)
            self._update_username_mapping()
    
    def is_vip(self, user_id: int) -> bool:
        """Check if user has VIP status"""
        user = self.get_user(user_id)
        if not user.get('vip', False):
            return False
        
        vip_until = user.get('vip_until')
        if vip_until is None:
            return True
        
        try:
            vip_until_dt = datetime.fromisoformat(vip_until)
            if datetime.now() > vip_until_dt:
                self.update_user(user_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True
    
    def get_all_users(self) -> Dict:
        """Get all users"""
        if engine:
            session = Session()
            try:
                users = session.query(User).all()
                return {u.id: {
                    'id': u.id, 'username': u.username, 
                    'first_name': u.first_name, 'vip': u.vip, 
                    'language': u.language
                } for u in users}
            finally:
                session.close()
        return self.users
    
    # ============================================
    # GROUP CHAT METHODS
    # ============================================
    
    def get_chat(self, chat_id: int) -> Dict:
        """Get group chat settings"""
        if engine:
            session = Session()
            try:
                chat = session.query(GroupChat).filter_by(id=chat_id).first()
                if not chat:
                    chat = GroupChat(id=chat_id)
                    session.add(chat)
                    session.commit()
                    chat = session.query(GroupChat).filter_by(id=chat_id).first()
                
                return {
                    'id': chat.id,
                    'title': chat.title or '',
                    'vip': chat.vip,
                    'vip_until': chat.vip_until.isoformat() if chat.vip_until else None,
                    'welcome_text': chat.welcome_text or "Добро пожаловать, {name}! 👋",
                    'welcome_enabled': chat.welcome_enabled,
                    'rules': chat.rules or '',
                    'ai_enabled': chat.ai_enabled,
                    'warns': chat.warns or {},
                    'messages_count': chat.messages_count or 0,
                    'top_users': chat.top_users or {}
                }
            except Exception as e:
                logger.error(f"Error get_chat ({chat_id}): {e}")
                return {'id': chat_id, 'ai_enabled': True, 'vip': False}
            finally:
                session.close()
        else:
            # JSON fallback
            key = f"chat_{chat_id}"
            if key not in self.users:
                self.users[key] = {
                    'id': chat_id, 'title': '', 'vip': False, 'vip_until': None,
                    'welcome_text': "Добро пожаловать, {name}! 👋",
                    'welcome_enabled': True, 'rules': '', 'ai_enabled': True,
                    'warns': {}, 'messages_count': 0, 'top_users': {}
                }
                self._save_json(self.users_file, self.users)
            return self.users[key]
    
    def update_chat(self, chat_id: int, data: Dict):
        """Update group chat settings"""
        if engine:
            session = Session()
            try:
                chat = session.query(GroupChat).filter_by(id=chat_id).first()
                if not chat:
                    chat = GroupChat(id=chat_id)
                    session.add(chat)
                
                for key, value in data.items():
                    if key == 'vip_until' and value:
                        value = datetime.fromisoformat(value) if isinstance(value, str) else value
                    setattr(chat, key, value)
                
                session.commit()
            except Exception as e:
                logger.warning(f"Error updating chat {chat_id}: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            chat = self.get_chat(chat_id)
            chat.update(data)
            self._save_json(self.users_file, self.users)
    
    def is_chat_vip(self, chat_id: int) -> bool:
        """Check if chat has VIP status"""
        chat = self.get_chat(chat_id)
        if not chat.get('vip', False):
            return False
        
        vip_until = chat.get('vip_until')
        if vip_until is None:
            return True
        
        try:
            vip_until_dt = datetime.fromisoformat(vip_until)
            if datetime.now() > vip_until_dt:
                self.update_chat(chat_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True
    
    def add_chat_message(self, chat_id: int, user_id: int):
        """Increment message counter for chat statistics"""
        chat = self.get_chat(chat_id)
        top_users = chat.get('top_users', {})
        user_id_str = str(user_id)
        top_users[user_id_str] = top_users.get(user_id_str, 0) + 1
        self.update_chat(chat_id, {
            'messages_count': chat.get('messages_count', 0) + 1,
            'top_users': top_users
        })
    
    def get_all_chats(self) -> Dict:
        """Get all group chats"""
        if engine:
            session = Session()
            try:
                chats = session.query(GroupChat).all()
                return {c.id: {'id': c.id, 'title': c.title, 'vip': c.vip} for c in chats}
            finally:
                session.close()
        return {k: v for k, v in self.users.items() if str(k).startswith('chat_')}
    
    # ============================================
    # UNIFIED CONTEXT METHODS
    # ============================================
    
    def get_context(self, user_id: int) -> UnifiedContext:
        """Get or create unified context for user"""
        if user_id not in self.unified_contexts:
            self.unified_contexts[user_id] = UnifiedContext()
        return self.unified_contexts[user_id]
    
    def clear_context(self, user_id: int):
        """Clear user's context"""
        if user_id in self.unified_contexts:
            self.unified_contexts[user_id].clear()
    
    # ============================================
    # CHAT HISTORY
    # ============================================
    
    def save_chat_history(self, user_id: int, message: str, response: str):
        """Save chat to history"""
        if not engine:
            return
        
        session = Session()
        try:
            chat = ChatHistory(user_id=user_id, message=message[:1000], response=response[:1000])
            session.add(chat)
            session.commit()
        except Exception as e:
            logger.warning(f"Error saving chat history: {e}")
        finally:
            session.close()


# Initialize storage
storage = DataStorage()


# ============================================
# HELPER FUNCTIONS
# ============================================

def identify_creator(user):
    """Identify creator by username"""
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Creator identified: {user.id}")


def is_creator(user_id: int) -> bool:
    """Check if user is creator"""
    return user_id == CREATOR_ID


async def is_user_admin(chat_id: int, user_id: int, bot) -> bool:
    """Check if user is admin in chat"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False


async def is_bot_admin(chat_id: int, bot) -> bool:
    """Check if bot is admin in chat"""
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False


def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Get main keyboard for user"""
    lang = get_lang(user_id)
    keyboard = [
        [KeyboardButton(get_text('main_keyboard.chat', lang)), KeyboardButton(get_text('main_keyboard.notes', lang))],
        [KeyboardButton(get_text('main_keyboard.weather', lang)), KeyboardButton(get_text('main_keyboard.time', lang))],
        [KeyboardButton(get_text('main_keyboard.games', lang)), KeyboardButton(get_text('main_keyboard.info', lang))]
    ]
    
    if storage.is_vip(user_id):
        keyboard.insert(0, [
            KeyboardButton(get_text('main_keyboard.vip_menu', lang)), 
            KeyboardButton(get_text('main_keyboard.generate', lang))
        ])
    
    if is_creator(user_id):
        keyboard.append([KeyboardButton(get_text('main_keyboard.admin_panel', lang))])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_help_keyboard(lang: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Get help keyboard"""
    keyboard = [
        [InlineKeyboardButton(get_text('help_sections.help_basic', lang), callback_data="help_basic")],
        [InlineKeyboardButton(get_text('help_sections.help_ai', lang), callback_data="help_ai")],
        [InlineKeyboardButton(get_text('help_sections.help_memory', lang), callback_data="help_memory")],
        [InlineKeyboardButton(get_text('help_sections.help_notes', lang), callback_data="help_notes")],
        [InlineKeyboardButton(get_text('help_sections.help_todo', lang), callback_data="help_todo")],
        [InlineKeyboardButton(get_text('help_sections.help_utils', lang), callback_data="help_utils")],
        [InlineKeyboardButton(get_text('help_sections.help_games', lang), callback_data="help_games")],
        [InlineKeyboardButton(get_text('help_sections.help_vip', lang), callback_data="help_vip")],
        [InlineKeyboardButton(get_text('help_sections.help_groups', lang), callback_data="help_groups")],
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton(get_text('help_sections.help_admin', lang), callback_data="help_admin")])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================
# AI FUNCTIONS
# ============================================

async def generate_with_context(user_id: int, new_content: str = None, image_data: bytes = None) -> str:
    """Generate response using unified context"""
    context = storage.get_context(user_id)
    
    # Add new content to context
    if image_data and new_content:
        context.add_user_image(image_data, new_content)
    elif image_data:
        # Check for pending context
        pending = context.get_pending_image()
        if pending:
            # Previous image, now with text
            context.add_user_image(pending, new_content or "Опиши это изображение")
        else:
            context.set_pending_image(image_data)
            return None  # Signal to ask user
    elif new_content:
        # Check if there's a pending image
        pending = context.get_pending_image()
        if pending:
            context.add_user_image(pending, new_content)
        else:
            context.add_user_text(new_content)
    
    try:
        # Build content for Gemini
        contents = context.build_gemini_content()
        
        if not contents:
            return "Пожалуйста, напишите сообщение."
        
        # Generate response
        response = model.generate_content(contents)
        response_text = response.text
        
        # Add response to context
        context.add_assistant_response(response_text)
        
        # Update stats
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        # Save to history
        storage.save_chat_history(user_id, new_content or "[image/voice]", response_text)
        
        return response_text
        
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return f"Ошибка AI: {str(e)}"


async def generate_image_imagen(prompt: str) -> Optional[bytes]:
    """Generate image with Imagen 3"""
    if not GEMINI_API_KEY:
        return None
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
    
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("predictions") and result["predictions"][0].get("bytesBase64Encoded"):
                        return base64.b64decode(result["predictions"][0]["bytesBase64Encoded"])
                else:
                    error_text = await response.text()
                    logger.error(f"Imagen API error {response.status}: {error_text}")
    except Exception as e:
        logger.error(f"Imagen API exception: {e}")
    
    return None


async def transcribe_audio_with_gemini(audio_bytes: bytes) -> str:
    """Transcribe audio with Gemini"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        uploaded_file = genai.upload_file(path=temp_path, mime_type="audio/ogg")
        response = model.generate_content(["Транскрибируй это аудио:", uploaded_file])
        
        os.remove(temp_path)
        return response.text
    except Exception as e:
        logger.warning(f"Transcription error: {e}")
        return f"Ошибка транскрипции: {str(e)}"


async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    """Extract text from document"""
    try:
        ext = filename.lower().split('.')[-1]
        
        if ext == 'txt':
            try:
                return file_bytes.decode('utf-8')
            except:
                return file_bytes.decode('cp1251', errors='ignore')
        elif ext == 'pdf':
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
            text = "".join([page.get_text() for page in doc])
            doc.close()
            return text
        elif ext in ['doc', 'docx']:
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join([para.text for para in doc.paragraphs])
        else:
            return file_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Text extraction error: {e}")
        return f"Ошибка: {str(e)}"


async def send_long_message(message: Message, text: str):
    """Send long message in chunks"""
    if len(text) <= 4000:
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.3)


# ============================================
# COMMAND HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    identify_creator(user)
    
    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'commands_count': user_data.get('commands_count', 0) + 1
    })
    
    lang = get_lang(user.id)
    welcome_text = get_text('welcome', lang, first_name=user.first_name, creator=CREATOR_USERNAME)
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=get_main_keyboard(user.id)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    await update.message.reply_text(
        get_text('help_title', lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(lang, is_creator(user_id))
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    keyboard = [
        [InlineKeyboardButton("Русский 🇷🇺", callback_data="set_lang:ru")],
        [InlineKeyboardButton("English 🇬🇧", callback_data="set_lang:en")],
        [InlineKeyboardButton("Italiano 🇮🇹", callback_data="set_lang:it")],
    ]
    
    await update.message.reply_text(
        get_text('lang_choose', lang), 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /info command"""
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(get_text('info', lang), parse_mode=ParseMode.HTML)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    lang = get_lang(update.effective_user.id)
    stats = storage.stats
    all_users = storage.get_all_users()
    all_chats = storage.get_all_chats()
    uptime = datetime.now() - BOT_START_TIME
    db_status = 'PostgreSQL ✓' if engine else 'JSON'
    
    await update.message.reply_text(
        get_text('status', lang,
            users=len(all_users),
            vips=sum(1 for u in all_users.values() if u.get('vip', False)),
            groups=len(all_chats),
            msg_count=stats.get('total_messages', 0),
            cmd_count=stats.get('total_commands', 0),
            ai_count=stats.get('ai_requests', 0),
            days=uptime.days,
            hours=uptime.seconds // 3600,
            db_status=db_status
        ), 
        parse_mode=ParseMode.HTML
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user = storage.get_user(user_id)
    
    username_line = f"📱 @{user['username']}" if user.get('username') else ""
    reg_date = datetime.fromisoformat(user.get('registered', datetime.now().isoformat())).strftime('%d.%m.%Y')
    
    profile_text = get_text('profile', lang,
        first_name=user.get('first_name', 'User'),
        user_id=user.get('id'),
        username_line=username_line,
        registered_date=reg_date,
        msg_count=user.get('messages_count', 0),
        cmd_count=user.get('commands_count', 0),
        notes_count=len(user.get('notes', []))
    )
    
    if storage.is_vip(user_id):
        vip_until = user.get('vip_until')
        if vip_until:
            profile_text += get_text('profile_vip', lang, date=datetime.fromisoformat(vip_until).strftime('%d.%m.%Y'))
        else:
            profile_text += get_text('profile_vip_forever', lang)
    
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)


async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /uptime command"""
    lang = get_lang(update.effective_user.id)
    uptime = datetime.now() - BOT_START_TIME
    
    await update.message.reply_text(
        get_text('uptime', lang,
            start_time=BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S'),
            days=uptime.days,
            hours=uptime.seconds // 3600,
            minutes=(uptime.seconds % 3600) // 60
        ), 
        parse_mode=ParseMode.HTML
    )


async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vip command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user = storage.get_user(user_id)
    
    if storage.is_vip(user_id):
        vip_text = get_text('vip_status_active', lang)
        vip_until = user.get('vip_until')
        if vip_until:
            vip_text += get_text('vip_status_until', lang, date=datetime.fromisoformat(vip_until).strftime('%d.%m.%Y'))
        else:
            vip_text += get_text('vip_status_forever', lang)
        vip_text += get_text('vip_status_bonus', lang)
    else:
        vip_text = get_text('vip_status_inactive', lang)
    
    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ai command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not context.args:
        await update.message.reply_text(get_text('ai_prompt_needed', lang))
        return
    
    text = ' '.join(context.args)
    await update.message.chat.send_action('typing')
    
    response = await generate_with_context(user_id, text)
    if response:
        await send_long_message(update.message, response)
    else:
        await update.message.reply_text(get_text('ai_error', lang))


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    storage.clear_context(user_id)
    await update.message.reply_text(get_text('clear_context', lang))


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /generate command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    chat_id = update.message.chat.id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP (user or chat)
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    if not context.args:
        await update.message.reply_text(get_text('gen_prompt_needed', lang))
        return
    
    prompt = ' '.join(context.args)
    await update.message.reply_text(get_text('gen_in_progress', lang))
    
    try:
        image_bytes = await generate_image_imagen(prompt)
        if image_bytes:
            await update.message.reply_photo(
                photo=image_bytes,
                caption=get_text('gen_caption', lang, prompt=prompt),
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(get_text('gen_error', lang))
    except Exception as e:
        logger.warning(f"Generate error: {e}")
        await update.message.reply_text(get_text('gen_error_api', lang, error=str(e)))


# ============================================
# NOTES & TODO HANDLERS
# ============================================

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /note command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not context.args:
        await update.message.reply_text(get_text('note_prompt_needed', lang))
        return
    
    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)
    note = {'text': note_text, 'created': datetime.now().isoformat()}
    notes = user.get('notes', [])
    notes.append(note)
    storage.update_user(user_id, {'notes': notes})
    
    await update.message.reply_text(get_text('note_saved', lang, num=len(notes), text=note_text))


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /notes command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user = storage.get_user(user_id)
    notes = user.get('notes', [])
    
    if not notes:
        await update.message.reply_text(get_text('notes_empty', lang))
        return
    
    notes_text = get_text('notes_list_title', lang, count=len(notes))
    for i, note in enumerate(notes, 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += get_text('notes_list_item', lang, i=i, date=created.strftime('%d.%m'), text=note['text'])
    
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)


async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /delnote command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not context.args:
        await update.message.reply_text(get_text('delnote_prompt_needed', lang))
        return
    
    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        
        if 1 <= note_num <= len(notes):
            deleted_note = notes.pop(note_num - 1)
            storage.update_user(user_id, {'notes': notes})
            await update.message.reply_text(get_text('delnote_success', lang, num=note_num, text=deleted_note['text']))
        else:
            await update.message.reply_text(get_text('delnote_not_found', lang, num=note_num))
    except ValueError:
        await update.message.reply_text(get_text('delnote_invalid_num', lang))


async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /todo command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not context.args:
        await update.message.reply_text(get_text('todo_prompt_needed', lang))
        return
    
    subcommand = context.args[0].lower()
    user = storage.get_user(user_id)
    
    if subcommand == 'add':
        if len(context.args) < 2:
            await update.message.reply_text(get_text('todo_add_prompt_needed', lang))
            return
        
        todo_text = ' '.join(context.args[1:])
        todo = {'text': todo_text, 'created': datetime.now().isoformat()}
        todos = user.get('todos', [])
        todos.append(todo)
        storage.update_user(user_id, {'todos': todos})
        await update.message.reply_text(get_text('todo_saved', lang, num=len(todos), text=todo_text))
    
    elif subcommand == 'list':
        todos = user.get('todos', [])
        if not todos:
            await update.message.reply_text(get_text('todo_empty', lang))
            return
        
        todos_text = get_text('todo_list_title', lang, count=len(todos))
        for i, todo in enumerate(todos, 1):
            created = datetime.fromisoformat(todo['created'])
            todos_text += get_text('todo_list_item', lang, i=i, date=created.strftime('%d.%m'), text=todo['text'])
        await update.message.reply_text(todos_text, parse_mode=ParseMode.HTML)
    
    elif subcommand == 'del':
        if len(context.args) < 2:
            await update.message.reply_text(get_text('todo_del_prompt_needed', lang))
            return
        
        try:
            todo_num = int(context.args[1])
            todos = user.get('todos', [])
            if 1 <= todo_num <= len(todos):
                deleted_todo = todos.pop(todo_num - 1)
                storage.update_user(user_id, {'todos': todos})
                await update.message.reply_text(get_text('todo_del_success', lang, num=todo_num, text=deleted_todo['text']))
            else:
                await update.message.reply_text(get_text('todo_del_not_found', lang, num=todo_num))
        except ValueError:
            await update.message.reply_text(get_text('todo_del_invalid_num', lang))
    else:
        await update.message.reply_text(get_text('todo_prompt_needed', lang))


# ============================================
# MEMORY HANDLERS
# ============================================

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text("❓ /memorysave [ключ] [значение]")
        return
    
    key = context.args[0]
    value = ' '.join(context.args[1:])
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    memory[key] = value
    storage.update_user(user_id, {'memory': memory})
    
    await update.message.reply_text(f"✅ Сохранено:\n🔑 <b>{key}</b> = <code>{value}</code>", parse_mode=ParseMode.HTML)


async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❓ /memoryget [ключ]")
        return
    
    key = context.args[0]
    user = storage.get_user(user_id)
    
    if key in user.get('memory', {}):
        await update.message.reply_text(f"🔍 <b>{key}</b> = <code>{user['memory'][key]}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден.")


async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    
    if not memory:
        await update.message.reply_text("📭 Память пуста.")
        return
    
    memory_text = "🧠 <b>Память:</b>\n\n"
    for key, value in memory.items():
        memory_text += f"🔑 <b>{key}</b>: <code>{value}</code>\n"
    
    await update.message.reply_text(memory_text, parse_mode=ParseMode.HTML)


async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❓ /memorydel [ключ]")
        return
    
    key = context.args[0]
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    
    if key in memory:
        del memory[key]
        storage.update_user(user_id, {'memory': memory})
        await update.message.reply_text(f"✅ Ключ '{key}' удалён.")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден.")


# ============================================
# UTILITY HANDLERS
# ============================================

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /time command"""
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    
    timezones = {
        'moscow': 'Europe/Moscow', 'москва': 'Europe/Moscow',
        'london': 'Europe/London', 'лондон': 'Europe/London',
        'new york': 'America/New_York', 'нью-йорк': 'America/New_York',
        'tokyo': 'Asia/Tokyo', 'токио': 'Asia/Tokyo',
        'paris': 'Europe/Paris', 'париж': 'Europe/Paris',
        'berlin': 'Europe/Berlin', 'берлин': 'Europe/Berlin',
        'dubai': 'Asia/Dubai', 'дубай': 'Asia/Dubai',
        'sydney': 'Australia/Sydney', 'сидней': 'Australia/Sydney',
        'los angeles': 'America/Los_Angeles',
        'rome': 'Europe/Rome', 'рим': 'Europe/Rome', 'roma': 'Europe/Rome'
    }
    
    tz_name = timezones.get(city.lower())
    
    if not tz_name:
        matching_tz = [tz for tz in pytz.all_timezones if city.lower() in tz.lower()]
        tz_name = matching_tz[0] if matching_tz else 'Europe/Moscow'
    
    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        await update.message.reply_text(
            get_text('time_result', lang,
                city=city.title(),
                time=current_time.strftime('%H:%M:%S'),
                date=current_time.strftime('%d.%m.%Y'),
                tz=tz_name
            ), 
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Time error: {e}")
        await update.message.reply_text(get_text('time_city_not_found', lang, city=city))


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /weather command"""
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{urlquote(city)}?format=j1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data['current_condition'][0]
                    
                    await update.message.reply_text(
                        get_text('weather_result', lang,
                            city=city.title(),
                            temp=current['temp_C'],
                            feels=current['FeelsLikeC'],
                            desc=current['weatherDesc'][0]['value'],
                            humidity=current['humidity'],
                            wind=current['windspeedKmph']
                        ), 
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await update.message.reply_text(get_text('weather_city_not_found', lang, city=city))
    except Exception as e:
        logger.warning(f"Weather error: {e}")
        await update.message.reply_text(get_text('weather_error', lang))


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /translate command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if len(context.args) < 2:
        await update.message.reply_text(get_text('translate_prompt_needed', lang))
        return
    
    target_lang = context.args[0]
    text_to_translate = ' '.join(context.args[1:])
    
    try:
        response = await generate_with_context(user_id, f"Переведи на {target_lang}: {text_to_translate}")
        await send_long_message(update.message, response)
    except Exception as e:
        logger.warning(f"Translation error: {e}")
        await update.message.reply_text(get_text('translate_error', lang))


async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /calc command"""
    lang = get_lang(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text(get_text('calc_prompt_needed', lang))
        return
    
    expression = ' '.join(context.args)
    allowed_chars = "0123456789.+-*/() "
    
    if not all(char in allowed_chars for char in expression):
        await update.message.reply_text(get_text('calc_error', lang))
        return
    
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        await update.message.reply_text(
            get_text('calc_result', lang, expr=expression, result=result), 
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await update.message.reply_text(get_text('calc_error', lang))


async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /password command"""
    lang = get_lang(update.effective_user.id)
    
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text(get_text('password_length_error', lang))
            return
        
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(get_text('password_result', lang, password=password), parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(get_text('password_invalid_length', lang))


# ============================================
# GAMES HANDLERS
# ============================================

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    try:
        min_val = int(context.args[0]) if len(context.args) >= 1 else 1
        max_val = int(context.args[1]) if len(context.args) >= 2 else 100
        result = random.randint(min_val, max_val)
        await update.message.reply_text(
            get_text('random_result', lang, min=min_val, max=max_val, result=result), 
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text(get_text('random_invalid_range', lang))


async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    await update.message.reply_text(get_text('dice_result', lang, emoji=dice_emoji, result=result), parse_mode=ParseMode.HTML)


async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    result_key = random.choice(['coin_heads', 'coin_tails'])
    result_text = get_text(result_key, lang)
    emoji = '🦅' if result_key == 'coin_heads' else '💰'
    await update.message.reply_text(get_text('coin_result', lang, emoji=emoji, result=result_text), parse_mode=ParseMode.HTML)


async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    jokes = {
        'ru': [
            "Программист ложится спать. Жена: — Закрой окно, холодно! Программист: — И что, станет тепло? 😄",
            "— Почему программисты путают Хэллоуин и Рождество? — 31 OCT = 25 DEC! 🎃",
            "Зачем программисту очки? Чтобы лучше C++! 👓",
        ],
        'en': [
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "Why did the programmer quit his job? He didn't get arrays. 🤷‍♂️",
            "What's a programmer's favorite hangout spot? Foo bar. 🍻",
        ],
        'it': [
            "Perché i programmatori confondono Halloween e Natale? Perché 31 OCT = 25 DEC! 🎃",
            "Come muore un programmatore? In un loop infinito. 🔄",
            "Qual è l'animale preferito di un programmatore? Il Python. 🐍",
        ]
    }
    await update.message.reply_text(f"{get_text('joke_title', lang)}{random.choice(jokes.get(lang, jokes['en']))}", parse_mode=ParseMode.HTML)


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    quotes = {
        'ru': [
            "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
            "Инновация отличает лидера от последователя. — Стив Джобс",
            "Простота — залог надёжности. — Эдсгер Дейкстра"
        ],
        'en': [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "Simplicity is the soul of efficiency. - Edsger Dijkstra"
        ],
        'it': [
            "L'unico modo per fare un ottimo lavoro è amare quello che fai. - Steve Jobs",
            "L'innovazione distingue un leader da un seguace. - Steve Jobs",
            "La semplicità è la chiave dell'affidabilità. - Edsger Dijkstra"
        ]
    }
    await update.message.reply_text(
        f"{get_text('quote_title', lang)}{random.choice(quotes.get(lang, quotes['en']))}{get_text('quote_title_end', lang)}", 
        parse_mode=ParseMode.HTML
    )


async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    facts = {
        'ru': [
            "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
            "🐙 У осьминогов три сердца и голубая кровь.",
            "🍯 Мёд не портится тысячи лет.",
        ],
        'en': [
            "🌍 Earth is the only planet in our solar system not named after a god.",
            "🐙 Octopuses have three hearts and blue blood.",
            "🍯 Honey never spoils. Archaeologists have found pots of honey thousands of years old.",
        ],
        'it': [
            "🌍 La Terra è l'unico pianeta del sistema solare a non avere il nome di una divinità.",
            "🐙 I polpi hanno tre cuori e il sangue blu.",
            "🍯 Il miele non scade mai. Può durare migliaia di anni.",
        ]
    }
    await update.message.reply_text(f"{get_text('fact_title', lang)}{random.choice(facts.get(lang, facts['en']))}", parse_mode=ParseMode.HTML)


# ============================================
# REMINDER HANDLERS
# ============================================

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remind command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(get_text('remind_prompt_needed', lang))
        return
    
    try:
        minutes = int(context.args[0])
        text = ' '.join(context.args[1:])
        remind_time = datetime.now() + timedelta(minutes=minutes)
        
        user = storage.get_user(user_id)
        reminder = {'text': text, 'time': remind_time.isoformat(), 'created': datetime.now().isoformat(), 'lang': lang}
        reminders = user.get('reminders', [])
        reminders.append(reminder)
        storage.update_user(user_id, {'reminders': reminders})
        
        # Schedule reminder using job_queue
        context.job_queue.run_once(
            send_reminder_job,
            when=timedelta(minutes=minutes),
            data={'user_id': user_id, 'text': text, 'lang': lang},
            name=f"reminder_{user_id}_{remind_time.timestamp()}"
        )
        
        await update.message.reply_text(get_text('remind_success', lang, text=text, minutes=minutes))
    except ValueError:
        await update.message.reply_text(get_text('remind_invalid_time', lang))


async def send_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """Send reminder from job queue"""
    job_data = context.job.data
    user_id = job_data['user_id']
    text = job_data['text']
    lang = job_data['lang']
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=get_text('reminder_alert', lang, text=text),
            parse_mode=ParseMode.HTML
        )
        
        # Remove reminder from storage
        user = storage.get_user(user_id)
        reminders = [r for r in user.get('reminders', []) if r['text'] != text]
        storage.update_user(user_id, {'reminders': reminders})
    except Exception as e:
        logger.warning(f"Reminder send error: {e}")


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reminders command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    user = storage.get_user(user_id)
    reminders = user.get('reminders', [])
    
    if not reminders:
        await update.message.reply_text(get_text('reminders_empty', lang))
        return
    
    text = get_text('reminders_list_title', lang, count=len(reminders))
    for i, rem in enumerate(reminders, 1):
        rem_time = datetime.fromisoformat(rem['time'])
        text += get_text('reminders_list_item', lang, i=i, time=rem_time.strftime('%d.%m %H:%M'), text=rem['text'])
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ============================================
# GROUP MODERATION HANDLERS
# ============================================

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context.bot):
        await update.message.reply_text(get_text('bot_need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    reason = ' '.join(context.args) if context.args else "Не указана"
    
    try:
        await context.bot.ban_chat_member(chat_id, target_user.id)
        await update.message.reply_text(
            get_text('user_banned', lang, name=target_user.full_name, reason=reason),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Ban error: {e}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("❓ /unban [user_id]")
        return
    
    try:
        target_id = int(context.args[0])
        await context.bot.unban_chat_member(chat_id, target_id, only_if_banned=True)
        await update.message.reply_text(get_text('user_unbanned', lang, id=target_id), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Unban error: {e}")


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kick command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context.bot):
        await update.message.reply_text(get_text('bot_need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    try:
        await context.bot.ban_chat_member(chat_id, target_user.id)
        await context.bot.unban_chat_member(chat_id, target_user.id)
        await update.message.reply_text(
            get_text('user_kicked', lang, name=target_user.full_name),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Kick error: {e}")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mute command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context.bot):
        await update.message.reply_text(get_text('bot_need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    minutes = 15
    if context.args:
        try:
            minutes = int(context.args[0])
        except ValueError:
            pass
    
    until_date = datetime.now() + timedelta(minutes=minutes)
    
    try:
        await context.bot.restrict_chat_member(
            chat_id, 
            target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        await update.message.reply_text(
            get_text('user_muted', lang, name=target_user.full_name, minutes=minutes),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Mute error: {e}")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmute command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    try:
        await context.bot.restrict_chat_member(
            chat_id,
            target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await update.message.reply_text(
            get_text('user_unmuted', lang, name=target_user.full_name),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Unmute error: {e}")


async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warn command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    reason = ' '.join(context.args) if context.args else "Не указана"
    
    chat = storage.get_chat(chat_id)
    warns = chat.get('warns', {})
    user_id_str = str(target_user.id)
    warns[user_id_str] = warns.get(user_id_str, 0) + 1
    storage.update_chat(chat_id, {'warns': warns})
    
    if warns[user_id_str] >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target_user.id)
            await update.message.reply_text(
                get_text('user_warned_ban', lang, name=target_user.full_name),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Warn-ban error: {e}")
    else:
        await update.message.reply_text(
            get_text('user_warned', lang, name=target_user.full_name, count=warns[user_id_str], reason=reason),
            parse_mode=ParseMode.HTML
        )


async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unwarn command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    chat = storage.get_chat(chat_id)
    warns = chat.get('warns', {})
    user_id_str = str(target_user.id)
    
    if user_id_str in warns and warns[user_id_str] > 0:
        warns[user_id_str] -= 1
        storage.update_chat(chat_id, {'warns': warns})
    
    await update.message.reply_text(
        get_text('user_unwarned', lang, name=target_user.full_name, count=warns.get(user_id_str, 0)),
        parse_mode=ParseMode.HTML
    )


async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warns command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    chat = storage.get_chat(chat_id)
    warns = chat.get('warns', {})
    user_id_str = str(target_user.id)
    count = warns.get(user_id_str, 0)
    
    if count > 0:
        await update.message.reply_text(
            get_text('warns_list', lang, name=target_user.full_name, count=count),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            get_text('warns_empty', lang, name=target_user.full_name),
            parse_mode=ParseMode.HTML
        )


async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setwelcome command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("❓ /setwelcome [текст]\n\nИспользуйте {name} для имени пользователя")
        return
    
    welcome_text = ' '.join(context.args)
    storage.update_chat(chat_id, {'welcome_text': welcome_text, 'welcome_enabled': True})
    
    await update.message.reply_text(
        get_text('welcome_set', lang, text=welcome_text),
        parse_mode=ParseMode.HTML
    )


async def welcomeoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /welcomeoff command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    storage.update_chat(chat_id, {'welcome_enabled': False})
    await update.message.reply_text(get_text('welcome_off', lang))


async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setrules command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("❓ /setrules [текст правил]")
        return
    
    rules_text = ' '.join(context.args)
    storage.update_chat(chat_id, {'rules': rules_text})
    
    await update.message.reply_text(get_text('rules_set', lang))


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rules command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    rules = chat.get('rules', '')
    
    if rules:
        await update.message.reply_text(
            get_text('rules_text', lang, rules=rules),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(get_text('rules_empty', lang))


async def setai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setai command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("❓ /setai [on/off]")
        return
    
    setting = context.args[0].lower()
    
    if setting in ['on', '1', 'yes', 'да', 'вкл']:
        storage.update_chat(chat_id, {'ai_enabled': True})
        await update.message.reply_text(get_text('ai_enabled', lang))
    elif setting in ['off', '0', 'no', 'нет', 'выкл']:
        storage.update_chat(chat_id, {'ai_enabled': False})
        await update.message.reply_text(get_text('ai_disabled', lang))
    else:
        await update.message.reply_text("❓ /setai [on/off]")


async def chatinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chatinfo command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    chat_obj = update.message.chat
    
    vip_status = "✅" if storage.is_chat_vip(chat_id) else "❌"
    ai_status = "✅" if chat.get('ai_enabled', True) else "❌"
    welcome_status = "✅" if chat.get('welcome_enabled', True) else "❌"
    
    await update.message.reply_text(
        get_text('chat_info', lang,
            title=chat_obj.title or "Unknown",
            id=chat_id,
            vip_status=vip_status,
            ai_status=ai_status,
            welcome_status=welcome_status,
            messages=chat.get('messages_count', 0)
        ),
        parse_mode=ParseMode.HTML
    )


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /top command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    top_users = chat.get('top_users', {})
    
    if not top_users:
        await update.message.reply_text(get_text('top_empty', lang))
        return
    
    # Sort by message count
    sorted_users = sorted(top_users.items(), key=lambda x: x[1], reverse=True)[:10]
    
    text = get_text('top_users', lang)
    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    
    for i, (uid, count) in enumerate(sorted_users):
        try:
            member = await context.bot.get_chat_member(chat_id, int(uid))
            name = member.user.full_name
        except:
            name = f"User {uid}"
        
        text += get_text('top_users_item', lang, medal=medals[i], name=name, count=count)
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new chat members"""
    chat_id = update.message.chat.id
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    
    if not chat.get('welcome_enabled', True):
        return
    
    welcome_text = chat.get('welcome_text', "Добро пожаловать, {name}! 👋")
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        personalized_welcome = welcome_text.replace('{name}', member.full_name)
        
        try:
            await update.message.reply_text(personalized_welcome, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Welcome message error: {e}")


# ============================================
# ADMIN HANDLERS
# ============================================

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /grant_vip command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(get_text('grant_vip_prompt', lang))
        return
    
    identifier = context.args[0]
    duration = context.args[1].lower()
    
    target_id = storage.get_user_id_by_identifier(identifier)
    
    if target_id is None:
        await update.message.reply_text(get_text('grant_vip_user_not_found', lang, id=identifier))
        return
    
    # Determine if it's a group (negative ID) or user
    is_group = target_id < 0
    
    durations = {
        'week': timedelta(days=7),
        'month': timedelta(days=30),
        'year': timedelta(days=365),
        'forever': None
    }
    
    if duration not in durations:
        await update.message.reply_text(get_text('grant_vip_invalid_duration', lang))
        return
    
    if durations[duration]:
        vip_until = datetime.now() + durations[duration]
        duration_text = get_text('duration_until', lang, date=vip_until.strftime('%d.%m.%Y'))
    else:
        vip_until = None
        duration_text = get_text('duration_forever', lang)
    
    if is_group:
        storage.update_chat(target_id, {
            'vip': True, 
            'vip_until': vip_until.isoformat() if vip_until else None
        })
    else:
        storage.update_user(target_id, {
            'vip': True, 
            'vip_until': vip_until.isoformat() if vip_until else None
        })
    
    await update.message.reply_text(
        get_text('grant_vip_success', lang, id=target_id, duration_text=duration_text),
        parse_mode=ParseMode.HTML
    )
    
    # Notify user (not group)
    if not is_group:
        try:
            await context.bot.send_message(
                target_id,
                get_text('grant_vip_dm', lang, duration_text=duration_text),
                parse_mode=ParseMode.HTML
            )
        except:
            pass


async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /revoke_vip command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    if not context.args:
        await update.message.reply_text(get_text('revoke_vip_prompt', lang))
        return
    
    identifier = context.args[0]
    target_id = storage.get_user_id_by_identifier(identifier)
    
    if target_id is None:
        await update.message.reply_text(get_text('grant_vip_user_not_found', lang, id=identifier))
        return
    
    is_group = target_id < 0
    
    if is_group:
        storage.update_chat(target_id, {'vip': False, 'vip_until': None})
    else:
        storage.update_user(target_id, {'vip': False, 'vip_until': None})
    
    await update.message.reply_text(
        get_text('revoke_vip_success', lang, id=target_id),
        parse_mode=ParseMode.HTML
    )


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /users command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    all_users = storage.get_all_users()
    
    text = get_text('users_list_title', lang, count=len(all_users))
    
    users_list = list(all_users.values())[:50]
    
    for user in users_list:
        vip_badge = "💎" if user.get('vip', False) else "👤"
        text += get_text('users_list_item', lang,
            vip_badge=vip_badge,
            id=user.get('id', 0),
            name=user.get('first_name', 'Unknown'),
            username=user.get('username', 'none')
        )
    
    if len(all_users) > 50:
        text += get_text('users_list_more', lang, count=len(all_users) - 50)
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    if not context.args:
        await update.message.reply_text(get_text('broadcast_prompt', lang))
        return
    
    text = ' '.join(context.args)
    await update.message.reply_text(get_text('broadcast_started', lang))
    
    all_users = storage.get_all_users()
    success = 0
    failed = 0
    
    for uid in all_users.keys():
        try:
            user_lang = all_users[uid].get('language', 'ru')
            await context.bot.send_message(
                uid,
                get_text('broadcast_dm', user_lang, text=text),
                parse_mode=ParseMode.HTML
            )
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await update.message.reply_text(
        get_text('broadcast_finished', lang, success=success, failed=failed)
    )


async def stats_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (admin)"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    all_users = storage.get_all_users()
    stats = storage.stats
    
    await update.message.reply_text(
        get_text('stats_admin_title', lang,
            users=len(all_users),
            vips=sum(1 for u in all_users.values() if u.get('vip', False)),
            msg_count=stats.get('total_messages', 0),
            cmd_count=stats.get('total_commands', 0),
            ai_count=stats.get('ai_requests', 0)
        ),
        parse_mode=ParseMode.HTML
    )


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /backup command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    try:
        all_users = storage.get_all_users()
        all_chats = storage.get_all_chats()
        
        backup_data = {
            'users': {str(k): v for k, v in all_users.items()},
            'chats': {str(k): v for k, v in all_chats.items()},
            'stats': storage.stats,
            'backup_date': datetime.now().isoformat()
        }
        
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        await update.message.reply_document(
            document=io.BytesIO(backup_json.encode('utf-8')),
            filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            caption=get_text('backup_success', lang, date=datetime.now().strftime('%d.%m.%Y %H:%M'))
        )
    except Exception as e:
        await update.message.reply_text(get_text('backup_error', lang, error=str(e)))


# ============================================
# MESSAGE HANDLERS
# ============================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages"""
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    # Check AI enabled in group
    if is_group:
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        
        caption = update.message.caption or ""
        
        if caption:
            # Photo with caption - analyze immediately
            await update.message.reply_text(get_text('photo_analyzing', lang))
            response = await generate_with_context(user_id, caption, bytes(file_bytes))
            if response:
                await send_long_message(update.message, response)
        else:
            # Photo without caption - set as pending and ask
            ctx = storage.get_context(user_id)
            ctx.set_pending_image(bytes(file_bytes))
            await update.message.reply_text(get_text('photo_no_caption', lang))
    
    except Exception as e:
        logger.warning(f"Photo error: {e}")
        await update.message.reply_text(get_text('photo_error', lang, error=str(e)))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages"""
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    # Check AI enabled in group
    if is_group:
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    try:
        await update.message.reply_text(get_text('voice_transcribing', lang))
        
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Transcribe
        transcription = await transcribe_audio_with_gemini(bytes(file_bytes))
        
        # Add to context and generate response
        ctx = storage.get_context(user_id)
        ctx.add_user_voice(transcription)
        
        response = await generate_with_context(user_id, transcription)
        
        result_text = get_text('voice_result', lang, text=transcription)
        if response:
            result_text += f"\n\n🤖 <b>Ответ:</b>\n\n{response}"
        
        await send_long_message(update.message, result_text)
    
    except Exception as e:
        logger.warning(f"Voice error: {e}")
        await update.message.reply_text(get_text('voice_error', lang, error=str(e)))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages"""
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    # Check AI enabled in group
    if is_group:
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    try:
        await update.message.reply_text(get_text('file_received', lang))
        
        document = update.message.document
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Extract text
        content = await extract_text_from_document(bytes(file_bytes), document.file_name)
        
        # Add to context
        ctx = storage.get_context(user_id)
        ctx.add_user_file(document.file_name, content[:5000])  # Limit content
        
        # Generate analysis
        prompt = update.message.caption or f"Проанализируй этот документ: {document.file_name}"
        response = await generate_with_context(user_id, prompt)
        
        await send_long_message(
            update.message, 
            get_text('file_analyzing', lang, filename=document.file_name, text=response)
        )
    
    except Exception as e:
        logger.warning(f"Document error: {e}")
        await update.message.reply_text(get_text('file_error', lang, error=str(e)))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    identify_creator(user)
    
    user_id = user.id
    chat_id = update.message.chat.id
    text = update.message.text
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Update stats
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'messages_count': user_data.get('messages_count', 0) + 1
    })
    
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # Track group stats
    if is_group:
        storage.add_chat_message(chat_id, user_id)
        storage.update_chat(chat_id, {'title': update.message.chat.title})
        
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    # Handle menu buttons
    for btn_key, btn_texts in menu_button_map.items():
        if text in btn_texts:
            await handle_menu_button(update, context, btn_key)
            return
    
    # In groups, only respond to replies or mentions
    if is_group:
        bot_username = (await context.bot.get_me()).username
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        is_mention = f"@{bot_username}" in text
        
        if not is_reply_to_bot and not is_mention:
            return
        
        # Remove mention from text
        text = text.replace(f"@{bot_username}", "").strip()
    
    # Generate AI response
    await update.message.chat.send_action('typing')
    
    response = await generate_with_context(user_id, text)
    
    if response is None:
        # Pending image - already handled
        return
    
    await send_long_message(update.message, response)


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_key: str):
    """Handle menu button presses"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if button_key == 'chat':
        await update.message.reply_text(get_text('menu.chat', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'notes':
        keyboard = [
            [InlineKeyboardButton(get_text('menu.notes_create', lang), callback_data="notes_create")],
            [InlineKeyboardButton(get_text('menu.notes_list', lang), callback_data="notes_list")]
        ]
        await update.message.reply_text(
            get_text('menu.notes', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'weather':
        await update.message.reply_text(get_text('menu.weather', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'time':
        await update.message.reply_text(get_text('menu.time', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'games':
        keyboard = [
            [InlineKeyboardButton(get_text('menu.games_dice', lang), callback_data="game_dice"),
             InlineKeyboardButton(get_text('menu.games_coin', lang), callback_data="game_coin")],
            [InlineKeyboardButton(get_text('menu.games_joke', lang), callback_data="game_joke"),
             InlineKeyboardButton(get_text('menu.games_quote', lang), callback_data="game_quote")],
            [InlineKeyboardButton(get_text('menu.games_fact', lang), callback_data="game_fact")]
        ]
        await update.message.reply_text(
            get_text('menu.games', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'info':
        await update.message.reply_text(get_text('info', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'vip_menu':
        keyboard = [
            [InlineKeyboardButton(get_text('menu.vip_reminders', lang), callback_data="vip_reminders")],
            [InlineKeyboardButton(get_text('menu.vip_stats', lang), callback_data="vip_stats")]
        ]
        await update.message.reply_text(
            get_text('menu.vip', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'admin_panel':
        if not is_creator(user_id):
            await update.message.reply_text(get_text('admin_only', lang))
            return
        
        keyboard = [
            [InlineKeyboardButton(get_text('menu.admin_users', lang), callback_data="admin_users")],
            [InlineKeyboardButton(get_text('menu.admin_stats', lang), callback_data="admin_stats")],
            [InlineKeyboardButton(get_text('menu.admin_broadcast', lang), callback_data="admin_broadcast")]
        ]
        await update.message.reply_text(
            get_text('menu.admin', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'generate':
        await update.message.reply_text(get_text('menu.generate', lang), parse_mode=ParseMode.HTML)


# ============================================
# CALLBACK QUERY HANDLER
# ============================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_lang(user_id)
    data = query.data
    
    # Language selection
    if data.startswith('set_lang:'):
        new_lang = data.split(':')[1]
        storage.update_user(user_id, {'language': new_lang})
        await query.edit_message_text(get_text('lang_changed', new_lang))
        return
    
    # Help sections# Help back button - ПЕРВЫМ!
    if data == 'help_back':
        await query.edit_message_text(
            get_text('help_title', lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(lang, is_creator(user_id))
        )
        return
    
    if data.startswith('help_'):
        section = data
        help_text = get_text(f'help_text.{section}', lang)
        keyboard = [[InlineKeyboardButton(get_text('help_back', lang), callback_data="help_back")]]
        await query.edit_message_text(
            help_text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if data == 'help_back':
        await query.edit_message_text(
            get_text('help_title', lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(lang, is_creator(user_id))
        )
        return
    
    # Notes
    if data == 'notes_create':
        await query.edit_message_text(get_text('note_prompt_needed', lang))
        return
    
    if data == 'notes_list':
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        
        if not notes:
            await query.edit_message_text(get_text('notes_empty', lang))
            return
        
        notes_text = get_text('notes_list_title', lang, count=len(notes))
        for i, note in enumerate(notes, 1):
            created = datetime.fromisoformat(note['created'])
            notes_text += get_text('notes_list_item', lang, i=i, date=created.strftime('%d.%m'), text=note['text'])
        await query.edit_message_text(notes_text, parse_mode=ParseMode.HTML)
        return
    
    # Games
    if data == 'game_dice':
        result = random.randint(1, 6)
        dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
        await query.edit_message_text(
            get_text('dice_result', lang, emoji=dice_emoji, result=result), 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_coin':
        result_key = random.choice(['coin_heads', 'coin_tails'])
        result_text = get_text(result_key, lang)
        emoji = '🦅' if result_key == 'coin_heads' else '💰'
        await query.edit_message_text(
            get_text('coin_result', lang, emoji=emoji, result=result_text), 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_joke':
        jokes = {
            'ru': ["Программист ложится спать. Жена: — Закрой окно, холодно! Программист: — И что, станет тепло? 😄"],
            'en': ["Why do programmers prefer dark mode? Because light attracts bugs! 🐛"],
            'it': ["Perché i programmatori confondono Halloween e Natale? Perché 31 OCT = 25 DEC! 🎃"]
        }
        await query.edit_message_text(
            f"{get_text('joke_title', lang)}{random.choice(jokes.get(lang, jokes['en']))}", 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_quote':
        quotes = {
            'ru': ["Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс"],
            'en': ["The only way to do great work is to love what you do. - Steve Jobs"],
            'it': ["L'unico modo per fare un ottimo lavoro è amare quello che fai. - Steve Jobs"]
        }
        await query.edit_message_text(
            f"{get_text('quote_title', lang)}{random.choice(quotes.get(lang, quotes['en']))}{get_text('quote_title_end', lang)}", 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_fact':
        facts = {
            'ru': ["🌍 Земля — единственная планета Солнечной системы, названная не в честь бога."],
            'en': ["🌍 Earth is the only planet in our solar system not named after a god."],
            'it': ["🌍 La Terra è l'unico pianeta del sistema solare a non avere il nome di una divinità."]
        }
        await query.edit_message_text(
            f"{get_text('fact_title', lang)}{random.choice(facts.get(lang, facts['en']))}", 
            parse_mode=ParseMode.HTML
        )
        return
    
    # VIP menu
    if data == 'vip_reminders':
        if not storage.is_vip(user_id):
            await query.edit_message_text(get_text('vip_only', lang))
            return
        
        user = storage.get_user(user_id)
        reminders = user.get('reminders', [])
        
        if not reminders:
            await query.edit_message_text(get_text('reminders_empty', lang))
            return
        
        text = get_text('reminders_list_title', lang, count=len(reminders))
        for i, rem in enumerate(reminders, 1):
            rem_time = datetime.fromisoformat(rem['time'])
            text += get_text('reminders_list_item', lang, i=i, time=rem_time.strftime('%d.%m %H:%M'), text=rem['text'])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        return
    
    if data == 'vip_stats':
        if not storage.is_vip(user_id):
            await query.edit_message_text(get_text('vip_only', lang))
            return
        
        user = storage.get_user(user_id)
        await query.edit_message_text(
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"📨 Сообщений: {user.get('messages_count', 0)}\n"
            f"🎯 Команд: {user.get('commands_count', 0)}\n"
            f"📝 Заметок: {len(user.get('notes', []))}\n"
            f"📋 Задач: {len(user.get('todos', []))}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Admin menu
    if data == 'admin_users':
        if not is_creator(user_id):
            await query.edit_message_text(get_text('admin_only', lang))
            return
        
        all_users = storage.get_all_users()
        text = get_text('users_list_title', lang, count=len(all_users))
        
        for user in list(all_users.values())[:20]:
            vip_badge = "💎" if user.get('vip', False) else "👤"
            text += f"{vip_badge} <code>{user.get('id', 0)}</code> - {user.get('first_name', 'Unknown')}\n"
        
        if len(all_users) > 20:
            text += f"\n<i>... и ещё {len(all_users) - 20}</i>"
        
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        return
    
    if data == 'admin_stats':
        if not is_creator(user_id):
            await query.edit_message_text(get_text('admin_only', lang))
            return
        
        all_users = storage.get_all_users()
        stats = storage.stats
        
        await query.edit_message_text(
            get_text('stats_admin_title', lang,
                users=len(all_users),
                vips=sum(1 for u in all_users.values() if u.get('vip', False)),
                msg_count=stats.get('total_messages', 0),
                cmd_count=stats.get('total_commands', 0),
                ai_count=stats.get('ai_requests', 0)
            ),
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'admin_broadcast':
        if not is_creator(user_id):
            await query.edit_message_text(get_text('admin_only', lang))
            return
        
        await query.edit_message_text(get_text('broadcast_prompt', lang))
        return


# ============================================
# MAIN FUNCTION
# ============================================

def main():
    """Main function"""
    logger.info("🚀 Starting AI DISCO BOT v4.0...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Basic commands
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('language', language_command))
    application.add_handler(CommandHandler('info', info_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('profile', profile_command))
    application.add_handler(CommandHandler('uptime', uptime_command))
    application.add_handler(CommandHandler('vip', vip_command))
    
    # AI commands
    application.add_handler(CommandHandler('ai', ai_command))
    application.add_handler(CommandHandler('clear', clear_command))
    application.add_handler(CommandHandler('generate', generate_command))
    
    # Notes & Todo
    application.add_handler(CommandHandler('note', note_command))
    application.add_handler(CommandHandler('notes', notes_command))
    application.add_handler(CommandHandler('delnote', delnote_command))
    application.add_handler(CommandHandler('todo', todo_command))
    
    # Memory
    application.add_handler(CommandHandler('memorysave', memory_save_command))
    application.add_handler(CommandHandler('memoryget', memory_get_command))
    application.add_handler(CommandHandler('memorylist', memory_list_command))
    application.add_handler(CommandHandler('memorydel', memory_del_command))
    
    # Utilities
    application.add_handler(CommandHandler('time', time_command))
    application.add_handler(CommandHandler('weather', weather_command))
    application.add_handler(CommandHandler('translate', translate_command))
    application.add_handler(CommandHandler('calc', calc_command))
    application.add_handler(CommandHandler('password', password_command))
    
    # Games
    application.add_handler(CommandHandler('random', random_command))
    application.add_handler(CommandHandler('dice', dice_command))
    application.add_handler(CommandHandler('coin', coin_command))
    application.add_handler(CommandHandler('joke', joke_command))
    application.add_handler(CommandHandler('quote', quote_command))
    application.add_handler(CommandHandler('fact', fact_command))
    
    # Reminders (VIP)
    application.add_handler(CommandHandler('remind', remind_command))
    application.add_handler(CommandHandler('reminders', reminders_command))
    
    # Group moderation
    application.add_handler(CommandHandler('ban', ban_command))
    application.add_handler(CommandHandler('unban', unban_command))
    application.add_handler(CommandHandler('kick', kick_command))
    application.add_handler(CommandHandler('mute', mute_command))
    application.add_handler(CommandHandler('unmute', unmute_command))
    application.add_handler(CommandHandler('warn', warn_command))
    application.add_handler(CommandHandler('unwarn', unwarn_command))
    application.add_handler(CommandHandler('warns', warns_command))
    application.add_handler(CommandHandler('setwelcome', setwelcome_command))
    application.add_handler(CommandHandler('welcomeoff', welcomeoff_command))
    application.add_handler(CommandHandler('setrules', setrules_command))
    application.add_handler(CommandHandler('rules', rules_command))
    application.add_handler(CommandHandler('setai', setai_command))
    application.add_handler(CommandHandler('chatinfo', chatinfo_command))
    application.add_handler(CommandHandler('top', top_command))
    
    # Admin commands
    application.add_handler(CommandHandler('grant_vip', grant_vip_command))
    application.add_handler(CommandHandler('revoke_vip', revoke_vip_command))
    application.add_handler(CommandHandler('users', users_command))
    application.add_handler(CommandHandler('broadcast', broadcast_command))
    application.add_handler(CommandHandler('stats', stats_admin_command))
    application.add_handler(CommandHandler('backup', backup_command))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("✅ Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

