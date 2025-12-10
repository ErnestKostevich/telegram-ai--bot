#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI DISCO BOT v4.1 - FIXED VERSION
All bugs fixed:
- help_back callback bug
- Context management improved
- Menu buttons fixed
- Group moderation working
"""

import os
import json
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
import pytz
import io
from urllib.parse import quote as urlquote
import base64
import tempfile

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatMemberStatus

import google.generativeai as genai
import aiohttp
from PIL import Image
import fitz
import docx

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

MAX_CONTEXT_MESSAGES = 20
MAX_CONTEXT_IMAGES = 4

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ BOT_TOKEN or GEMINI_API_KEY not set!")
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

SYSTEM_INSTRUCTION = """Ты — AI DISCO BOT, многофункциональный ассистент на Gemini 2.5. 
Отвечай на языке пользователя, дружелюбно и структурированно.
Максимум 4000 символов. Создатель: @Ernest_Kostevich.
Ты можешь видеть изображения, анализировать документы и понимать голосовые сообщения."""

text_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction=SYSTEM_INSTRUCTION
)

vision_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings
)


# ============================================
# UNIFIED CONTEXT - FIXED VERSION
# ============================================

class UnifiedContext:
    """Unified context manager - stores text, images, voice in one history"""
    
    def __init__(self, max_history: int = MAX_CONTEXT_MESSAGES):
        self.max_history = max_history
        self.sessions: Dict[int, List[Dict]] = {}
    
    def get_history(self, user_id: int) -> List[Dict]:
        if user_id not in self.sessions:
            self.sessions[user_id] = []
        return self.sessions[user_id]
    
    def add_user_message(self, user_id: int, content: Any):
        """Add user message (text, image, or mixed)"""
        history = self.get_history(user_id)
        parts = content if isinstance(content, list) else [content]
        history.append({"role": "user", "parts": parts})
        self._trim(user_id)
    
    def add_bot_message(self, user_id: int, content: str):
        """Add bot response"""
        history = self.get_history(user_id)
        history.append({"role": "model", "parts": [content]})
        self._trim(user_id)
    
    def _trim(self, user_id: int):
        """Trim history to max size"""
        history = self.sessions.get(user_id, [])
        if len(history) > self.max_history * 2:
            self.sessions[user_id] = history[-self.max_history * 2:]
    
    def clear(self, user_id: int):
        """Clear user's context"""
        if user_id in self.sessions:
            del self.sessions[user_id]
    
    def get_gemini_history(self, user_id: int) -> List[Dict]:
        """Get history formatted for Gemini, keeping only recent images"""
        history = self.get_history(user_id)
        result = []
        image_count = 0
        
        # Process from end to keep recent images
        for i in range(len(history) - 1, -1, -1):
            msg = history[i]
            new_parts = []
            
            for part in msg["parts"]:
                if isinstance(part, Image.Image):
                    if image_count < MAX_CONTEXT_IMAGES:
                        new_parts.append(part)
                        image_count += 1
                else:
                    new_parts.append(part)
            
            if new_parts:
                result.insert(0, {"role": msg["role"], "parts": new_parts})
        
        return result


unified_ctx = UnifiedContext()


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
    __tablename__ = 'group_chats'
    id = Column(BigInteger, primary_key=True)
    title = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    welcome_text = Column(Text)
    welcome_enabled = Column(Boolean, default=True)
    rules = Column(Text)
    ai_enabled = Column(Boolean, default=True)
    warns = Column(JSON, default=dict)
    messages_count = Column(Integer, default=0)
    top_users = Column(JSON, default=dict)
    registered = Column(DateTime, default=datetime.now)


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
        
        try:
            inspector = inspect(engine)
            if inspector.has_table('users'):
                columns = [col['name'] for col in inspector.get_columns('users')]
                if 'language' not in columns:
                    with engine.connect() as conn:
                        conn.execute(sa_text("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru'"))
                        conn.commit()
        except Exception as e:
            logger.warning(f"Migration error: {e}")
        
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("✅ PostgreSQL connected!")
        
    except Exception as e:
        logger.warning(f"⚠️ DB error: {e}")
        engine = None


# ============================================
# LOCALIZATION - FIXED
# ============================================

L = {
    'ru': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nПривет, {name}! Я бот на <b>Gemini 2.5</b>.\n\n<b>🎯 Возможности:</b>\n💬 AI-чат с контекстом\n📝 Заметки и задачи\n🌍 Погода и время\n🎲 Развлечения\n📎 Анализ файлов (VIP)\n🔍 Анализ фото (VIP)\n🖼️ Генерация картинок (VIP)\n👥 Модерация групп\n\n/help - команды\n/language - язык\n\n👨‍💻 @{creator}",
        'lang_changed': "✅ Язык: Русский 🇷🇺",
        'lang_choose': "🌐 Выберите язык:",
        'help_title': "📚 <b>Выберите раздел справки:</b>",
        'help_back': "🔙 Назад",
        'help_basic': "🏠 <b>Основные:</b>\n\n/start - Запуск\n/help - Справка\n/info - О боте\n/status - Статус\n/profile - Профиль\n/language - Язык\n/clear - Очистить контекст",
        'help_ai': "💬 <b>AI команды:</b>\n\n/ai [вопрос] - Спросить AI\nПросто пишите - бот ответит!\n\n💡 Бот помнит контекст разговора, включая фото и голосовые!",
        'help_notes': "📝 <b>Заметки:</b>\n\n/note [текст] - Создать\n/notes - Список\n/delnote [№] - Удалить",
        'help_todo': "📋 <b>Задачи:</b>\n\n/todo add [текст] - Добавить\n/todo list - Список\n/todo del [№] - Удалить",
        'help_memory': "🧠 <b>Память:</b>\n\n/memorysave [ключ] [значение]\n/memoryget [ключ]\n/memorylist\n/memorydel [ключ]",
        'help_utils': "🌍 <b>Утилиты:</b>\n\n/time [город]\n/weather [город]\n/translate [язык] [текст]\n/calc [выражение]\n/password [длина]",
        'help_games': "🎲 <b>Развлечения:</b>\n\n/random [min] [max]\n/dice\n/coin\n/joke\n/quote\n/fact",
        'help_vip': "💎 <b>VIP функции:</b>\n\n/vip - Статус\n/generate [описание] - Генерация картинки\n/remind [мин] [текст] - Напоминание\n/reminders - Список\n\n📎 Отправь файл/фото - анализ",
        'help_groups': "👥 <b>Группы:</b>\n\n<b>Модерация:</b>\n/ban /unban /kick\n/mute [мин] /unmute\n/warn /unwarn /warns\n\n<b>Настройки:</b>\n/setwelcome [текст]\n/welcomeoff\n/setrules [текст] /rules\n/setai [on/off]\n/chatinfo /top",
        'help_admin': "👑 <b>Админ:</b>\n\n/grant_vip [id] [срок]\n/revoke_vip [id]\n/users\n/broadcast [текст]\n/stats\n/backup",
        'info': "🤖 <b>AI DISCO BOT v4.1</b>\n\n<b>AI:</b> Gemini 2.5 Flash\n<b>Контекст:</b> Единый (текст+фото+голос)\n<b>БД:</b> {db}\n\n👨‍💻 @Ernest_Kostevich",
        'status': "📊 <b>Статус</b>\n\n👥 Пользователей: {users}\n💎 VIP: {vips}\n👥 Групп: {groups}\n📨 Сообщений: {msgs}\n🤖 AI запросов: {ai}\n⏱ Аптайм: {days}д {hours}ч\n✅ Онлайн",
        'profile': "👤 <b>{name}</b>\n🆔 <code>{id}</code>\n📊 Сообщений: {msgs}\n📝 Заметок: {notes}",
        'profile_vip': "\n💎 VIP до: {date}",
        'profile_vip_forever': "\n💎 VIP: Навсегда ♾️",
        'vip_active': "💎 <b>VIP активен!</b>\n\n{until}\n\n🎁 Бонусы:\n• Анализ фото/файлов\n• Генерация картинок\n• Напоминания",
        'vip_until': "⏰ До: {date}",
        'vip_forever': "⏰ Навсегда ♾️",
        'vip_inactive': "💎 <b>VIP не активен</b>\n\nСвяжитесь с @Ernest_Kostevich",
        'vip_only': "💎 Только для VIP. Свяжитесь с @Ernest_Kostevich",
        'admin_only': "❌ Только для создателя",
        'clear': "🧹 Контекст очищен!",
        'ai_error': "😔 Ошибка AI, попробуйте снова",
        'photo_analyzing': "🔍 Анализирую...",
        'photo_result': "📸 <b>Ответ:</b>\n\n{text}",
        'photo_error': "❌ Ошибка: {e}",
        'photo_no_caption': "📸 Получил фото! Что с ним сделать?\n\n💡 Напишите вопрос об этом фото.",
        'voice_transcribing': "🎙️ Распознаю голос...",
        'voice_result': "🎙️ <b>Вы:</b> <i>{text}</i>\n\n🤖 <b>Ответ:</b>\n\n{response}",
        'voice_error': "❌ Ошибка голоса: {e}",
        'file_analyzing': "📥 Анализирую файл...",
        'file_result': "📄 <b>{name}</b>\n\n🤖 {text}",
        'file_error': "❌ Ошибка файла: {e}",
        'gen_prompt': "❓ /generate [описание]\n\nПример: /generate закат над океаном",
        'gen_progress': "🎨 Генерирую...",
        'gen_done': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Ошибка генерации",
        'note_saved': "✅ Заметка #{n} сохранена",
        'note_prompt': "❓ /note [текст]",
        'notes_empty': "📭 Нет заметок",
        'notes_list': "📝 <b>Заметки ({n}):</b>\n\n{list}",
        'delnote_ok': "✅ Заметка #{n} удалена",
        'delnote_err': "❌ Заметка не найдена",
        'todo_prompt': "❓ /todo add [текст] | list | del [№]",
        'todo_saved': "✅ Задача #{n} добавлена",
        'todo_empty': "📭 Нет задач",
        'todo_list': "📋 <b>Задачи ({n}):</b>\n\n{list}",
        'todo_del_ok': "✅ Задача #{n} удалена",
        'todo_del_err': "❌ Задача не найдена",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 {time}\n📅 {date}\n🌍 {tz}",
        'time_error': "❌ Город не найден",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 {temp}°C (ощущается {feels}°C)\n☁️ {desc}\n💧 {humidity}%\n💨 {wind} км/ч",
        'weather_error': "❌ Ошибка погоды",
        'calc_result': "🧮 {expr} = <b>{result}</b>",
        'calc_error': "❌ Ошибка вычисления",
        'password_result': "🔑 <code>{pwd}</code>",
        'random_result': "🎲 {min}-{max}: <b>{r}</b>",
        'dice_result': "🎲 Выпало: <b>{r}</b>",
        'coin_heads': "Орёл 🦅",
        'coin_tails': "Решка 💰",
        'remind_ok': "⏰ Напоминание через {m} мин:\n📝 {text}",
        'remind_prompt': "❓ /remind [минуты] [текст]",
        'remind_alert': "⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
        'reminders_empty': "📭 Нет напоминаний",
        'reminders_list': "⏰ <b>Напоминания ({n}):</b>\n\n{list}",
        'grant_ok': "✅ VIP выдан: {id}\n⏰ {dur}",
        'grant_prompt': "❓ /grant_vip [id/@username] [week/month/year/forever]",
        'revoke_ok': "✅ VIP отозван: {id}",
        'users_list': "👥 <b>Пользователи ({n}):</b>\n\n{list}",
        'broadcast_start': "📤 Рассылка...",
        'broadcast_done': "✅ Отправлено: {ok}, ошибок: {err}",
        'broadcast_prompt': "❓ /broadcast [текст]",
        'joke': "😄 <b>Шутка:</b>\n\n{text}",
        'quote': "💭 <b>Цитата:</b>\n\n<i>{text}</i>",
        'fact': "🔬 <b>Факт:</b>\n\n{text}",
        # Кнопки меню
        'btn_chat': "💬 Чат",
        'btn_notes': "📝 Заметки",
        'btn_weather': "🌍 Погода",
        'btn_time': "⏰ Время",
        'btn_games': "🎲 Игры",
        'btn_info': "ℹ️ Инфо",
        'btn_vip': "💎 VIP",
        'btn_gen': "🖼️ Генерация",
        'btn_admin': "👑 Админ",
        # Групповые
        'need_admin': "❌ Нужны права админа!",
        'need_reply': "❌ Ответьте на сообщение!",
        'bot_need_admin': "❌ Бот должен быть админом!",
        'user_banned': "🚫 {name} забанен!",
        'user_unbanned': "✅ Пользователь разбанен!",
        'user_kicked': "👢 {name} кикнут!",
        'user_muted': "🔇 {name} замьючен на {mins} мин!",
        'user_unmuted': "🔊 {name} размьючен!",
        'user_warned': "⚠️ {name} предупреждён! ({count}/3)",
        'user_warn_ban': "🚫 {name} забанен за 3 варна!",
        'user_unwarned': "✅ Варн снят с {name} ({count}/3)",
        'warns_list': "⚠️ <b>Варны {name}:</b> {count}/3",
        'warns_empty': "✅ У {name} нет варнов",
        'welcome_set': "✅ Приветствие установлено!",
        'welcome_off': "✅ Приветствие выключено",
        'rules_set': "✅ Правила установлены!",
        'rules_text': "📜 <b>Правила:</b>\n\n{rules}",
        'rules_empty': "📜 Правила не установлены",
        'ai_enabled': "✅ AI включен",
        'ai_disabled': "❌ AI выключен",
        'chat_info': "📊 <b>Чат</b>\n\n🆔 <code>{id}</code>\n📛 {title}\n👥 {members}\n💎 VIP: {vip}\n🤖 AI: {ai}",
        'top_users': "🏆 <b>Топ активных:</b>\n\n{list}",
        'top_empty': "📭 Статистика пуста",
        'new_member': "👋 Добро пожаловать, {name}!",
    },
    'en': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nHi, {name}! I'm a <b>Gemini 2.5</b> bot.\n\n<b>🎯 Features:</b>\n💬 AI chat with context\n📝 Notes and tasks\n🌍 Weather and time\n🎲 Games\n📎 File analysis (VIP)\n🔍 Photo analysis (VIP)\n🖼️ Image generation (VIP)\n👥 Group moderation\n\n/help - commands\n/language - language\n\n👨‍💻 @{creator}",
        'lang_changed': "✅ Language: English 🇬🇧",
        'lang_choose': "🌐 Choose language:",
        'help_title': "📚 <b>Choose help section:</b>",
        'help_back': "🔙 Back",
        'help_basic': "🏠 <b>Basic:</b>\n\n/start - Start\n/help - Help\n/info - About\n/status - Status\n/profile - Profile\n/language - Language\n/clear - Clear context",
        'help_ai': "💬 <b>AI commands:</b>\n\n/ai [question] - Ask AI\nJust type - bot will answer!\n\n💡 Bot remembers context including photos and voice!",
        'help_notes': "📝 <b>Notes:</b>\n\n/note [text] - Create\n/notes - List\n/delnote [#] - Delete",
        'help_todo': "📋 <b>Tasks:</b>\n\n/todo add [text] - Add\n/todo list - List\n/todo del [#] - Delete",
        'help_memory': "🧠 <b>Memory:</b>\n\n/memorysave [key] [value]\n/memoryget [key]\n/memorylist\n/memorydel [key]",
        'help_utils': "🌍 <b>Utilities:</b>\n\n/time [city]\n/weather [city]\n/translate [lang] [text]\n/calc [expression]\n/password [length]",
        'help_games': "🎲 <b>Games:</b>\n\n/random [min] [max]\n/dice\n/coin\n/joke\n/quote\n/fact",
        'help_vip': "💎 <b>VIP features:</b>\n\n/vip - Status\n/generate [prompt] - Generate image\n/remind [min] [text] - Reminder\n/reminders - List\n\n📎 Send file/photo - analysis",
        'help_groups': "👥 <b>Groups:</b>\n\n<b>Moderation:</b>\n/ban /unban /kick\n/mute [min] /unmute\n/warn /unwarn /warns\n\n<b>Settings:</b>\n/setwelcome [text]\n/welcomeoff\n/setrules [text] /rules\n/setai [on/off]\n/chatinfo /top",
        'help_admin': "👑 <b>Admin:</b>\n\n/grant_vip [id] [duration]\n/revoke_vip [id]\n/users\n/broadcast [text]\n/stats\n/backup",
        'info': "🤖 <b>AI DISCO BOT v4.1</b>\n\n<b>AI:</b> Gemini 2.5 Flash\n<b>Context:</b> Unified (text+photo+voice)\n<b>DB:</b> {db}\n\n👨‍💻 @Ernest_Kostevich",
        'status': "📊 <b>Status</b>\n\n👥 Users: {users}\n💎 VIP: {vips}\n👥 Groups: {groups}\n📨 Messages: {msgs}\n🤖 AI requests: {ai}\n⏱ Uptime: {days}d {hours}h\n✅ Online",
        'profile': "👤 <b>{name}</b>\n🆔 <code>{id}</code>\n📊 Messages: {msgs}\n📝 Notes: {notes}",
        'profile_vip': "\n💎 VIP until: {date}",
        'profile_vip_forever': "\n💎 VIP: Forever ♾️",
        'vip_active': "💎 <b>VIP active!</b>\n\n{until}\n\n🎁 Perks:\n• Photo/file analysis\n• Image generation\n• Reminders",
        'vip_until': "⏰ Until: {date}",
        'vip_forever': "⏰ Forever ♾️",
        'vip_inactive': "💎 <b>No VIP</b>\n\nContact @Ernest_Kostevich",
        'vip_only': "💎 VIP only. Contact @Ernest_Kostevich",
        'admin_only': "❌ Creator only",
        'clear': "🧹 Context cleared!",
        'ai_error': "😔 AI error, try again",
        'photo_analyzing': "🔍 Analyzing...",
        'photo_result': "📸 <b>Response:</b>\n\n{text}",
        'photo_error': "❌ Error: {e}",
        'photo_no_caption': "📸 Got photo! What should I do with it?\n\n💡 Write your question about this photo.",
        'voice_transcribing': "🎙️ Transcribing...",
        'voice_result': "🎙️ <b>You:</b> <i>{text}</i>\n\n🤖 <b>Response:</b>\n\n{response}",
        'voice_error': "❌ Voice error: {e}",
        'file_analyzing': "📥 Analyzing file...",
        'file_result': "📄 <b>{name}</b>\n\n🤖 {text}",
        'file_error': "❌ File error: {e}",
        'gen_prompt': "❓ /generate [prompt]\n\nExample: /generate sunset over ocean",
        'gen_progress': "🎨 Generating...",
        'gen_done': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Generation error",
        'note_saved': "✅ Note #{n} saved",
        'note_prompt': "❓ /note [text]",
        'notes_empty': "📭 No notes",
        'notes_list': "📝 <b>Notes ({n}):</b>\n\n{list}",
        'delnote_ok': "✅ Note #{n} deleted",
        'delnote_err': "❌ Note not found",
        'todo_prompt': "❓ /todo add [text] | list | del [#]",
        'todo_saved': "✅ Task #{n} added",
        'todo_empty': "📭 No tasks",
        'todo_list': "📋 <b>Tasks ({n}):</b>\n\n{list}",
        'todo_del_ok': "✅ Task #{n} deleted",
        'todo_del_err': "❌ Task not found",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 {time}\n📅 {date}\n🌍 {tz}",
        'time_error': "❌ City not found",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 {temp}°C (feels {feels}°C)\n☁️ {desc}\n💧 {humidity}%\n💨 {wind} km/h",
        'weather_error': "❌ Weather error",
        'calc_result': "🧮 {expr} = <b>{result}</b>",
        'calc_error': "❌ Calculation error",
        'password_result': "🔑 <code>{pwd}</code>",
        'random_result': "🎲 {min}-{max}: <b>{r}</b>",
        'dice_result': "🎲 Rolled: <b>{r}</b>",
        'coin_heads': "Heads 🦅",
        'coin_tails': "Tails 💰",
        'remind_ok': "⏰ Reminder in {m} min:\n📝 {text}",
        'remind_prompt': "❓ /remind [minutes] [text]",
        'remind_alert': "⏰ <b>REMINDER</b>\n\n📝 {text}",
        'reminders_empty': "📭 No reminders",
        'reminders_list': "⏰ <b>Reminders ({n}):</b>\n\n{list}",
        'grant_ok': "✅ VIP granted: {id}\n⏰ {dur}",
        'grant_prompt': "❓ /grant_vip [id/@username] [week/month/year/forever]",
        'revoke_ok': "✅ VIP revoked: {id}",
        'users_list': "👥 <b>Users ({n}):</b>\n\n{list}",
        'broadcast_start': "📤 Broadcasting...",
        'broadcast_done': "✅ Sent: {ok}, errors: {err}",
        'broadcast_prompt': "❓ /broadcast [text]",
        'joke': "😄 <b>Joke:</b>\n\n{text}",
        'quote': "💭 <b>Quote:</b>\n\n<i>{text}</i>",
        'fact': "🔬 <b>Fact:</b>\n\n{text}",
        'btn_chat': "💬 Chat",
        'btn_notes': "📝 Notes",
        'btn_weather': "🌍 Weather",
        'btn_time': "⏰ Time",
        'btn_games': "🎲 Games",
        'btn_info': "ℹ️ Info",
        'btn_vip': "💎 VIP",
        'btn_gen': "🖼️ Generate",
        'btn_admin': "👑 Admin",
        'need_admin': "❌ Admin rights required!",
        'need_reply': "❌ Reply to a message!",
        'bot_need_admin': "❌ Bot must be admin!",
        'user_banned': "🚫 {name} banned!",
        'user_unbanned': "✅ User unbanned!",
        'user_kicked': "👢 {name} kicked!",
        'user_muted': "🔇 {name} muted for {mins} min!",
        'user_unmuted': "🔊 {name} unmuted!",
        'user_warned': "⚠️ {name} warned! ({count}/3)",
        'user_warn_ban': "🚫 {name} banned for 3 warnings!",
        'user_unwarned': "✅ Warning removed from {name} ({count}/3)",
        'warns_list': "⚠️ <b>Warnings {name}:</b> {count}/3",
        'warns_empty': "✅ {name} has no warnings",
        'welcome_set': "✅ Welcome message set!",
        'welcome_off': "✅ Welcome disabled",
        'rules_set': "✅ Rules set!",
        'rules_text': "📜 <b>Rules:</b>\n\n{rules}",
        'rules_empty': "📜 No rules set",
        'ai_enabled': "✅ AI enabled",
        'ai_disabled': "❌ AI disabled",
        'chat_info': "📊 <b>Chat</b>\n\n🆔 <code>{id}</code>\n📛 {title}\n👥 {members}\n💎 VIP: {vip}\n🤖 AI: {ai}",
        'top_users': "🏆 <b>Top active:</b>\n\n{list}",
        'top_empty': "📭 No stats yet",
        'new_member': "👋 Welcome, {name}!",
    },
    'it': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nCiao, {name}! Sono un bot <b>Gemini 2.5</b>.\n\n<b>🎯 Funzioni:</b>\n💬 Chat AI con contesto\n📝 Note e attività\n🌍 Meteo e ora\n🎲 Giochi\n📎 Analisi file (VIP)\n🔍 Analisi foto (VIP)\n🖼️ Generazione immagini (VIP)\n👥 Moderazione gruppi\n\n/help - comandi\n/language - lingua\n\n👨‍💻 @{creator}",
        'lang_changed': "✅ Lingua: Italiano 🇮🇹",
        'lang_choose': "🌐 Scegli lingua:",
        'help_title': "📚 <b>Scegli sezione:</b>",
        'help_back': "🔙 Indietro",
        'help_basic': "🏠 <b>Base:</b>\n\n/start - Avvia\n/help - Aiuto\n/info - Info\n/status - Stato\n/profile - Profilo\n/language - Lingua\n/clear - Pulisci contesto",
        'help_ai': "💬 <b>Comandi AI:</b>\n\n/ai [domanda] - Chiedi all'AI\nScrivi e basta - il bot risponde!\n\n💡 Il bot ricorda il contesto!",
        'help_notes': "📝 <b>Note:</b>\n\n/note [testo] - Crea\n/notes - Lista\n/delnote [#] - Elimina",
        'help_todo': "📋 <b>Attività:</b>\n\n/todo add [testo] - Aggiungi\n/todo list - Lista\n/todo del [#] - Elimina",
        'help_memory': "🧠 <b>Memoria:</b>\n\n/memorysave [chiave] [valore]\n/memoryget [chiave]\n/memorylist\n/memorydel [chiave]",
        'help_utils': "🌍 <b>Utilità:</b>\n\n/time [città]\n/weather [città]\n/translate [lingua] [testo]\n/calc [espressione]\n/password [lunghezza]",
        'help_games': "🎲 <b>Giochi:</b>\n\n/random [min] [max]\n/dice\n/coin\n/joke\n/quote\n/fact",
        'help_vip': "💎 <b>Funzioni VIP:</b>\n\n/vip - Stato\n/generate [prompt] - Genera immagine\n/remind [min] [testo] - Promemoria\n/reminders - Lista\n\n📎 Invia file/foto - analisi",
        'help_groups': "👥 <b>Gruppi:</b>\n\n<b>Moderazione:</b>\n/ban /unban /kick\n/mute [min] /unmute\n/warn /unwarn /warns\n\n<b>Impostazioni:</b>\n/setwelcome [testo]\n/welcomeoff\n/setrules [testo] /rules\n/setai [on/off]\n/chatinfo /top",
        'help_admin': "👑 <b>Admin:</b>\n\n/grant_vip [id] [durata]\n/revoke_vip [id]\n/users\n/broadcast [testo]\n/stats\n/backup",
        'info': "🤖 <b>AI DISCO BOT v4.1</b>\n\n<b>AI:</b> Gemini 2.5 Flash\n<b>Contesto:</b> Unificato\n<b>DB:</b> {db}\n\n👨‍💻 @Ernest_Kostevich",
        'status': "📊 <b>Stato</b>\n\n👥 Utenti: {users}\n💎 VIP: {vips}\n👥 Gruppi: {groups}\n📨 Messaggi: {msgs}\n🤖 Richieste AI: {ai}\n⏱ Uptime: {days}g {hours}h\n✅ Online",
        'profile': "👤 <b>{name}</b>\n🆔 <code>{id}</code>\n📊 Messaggi: {msgs}\n📝 Note: {notes}",
        'profile_vip': "\n💎 VIP fino: {date}",
        'profile_vip_forever': "\n💎 VIP: Per sempre ♾️",
        'vip_active': "💎 <b>VIP attivo!</b>\n\n{until}\n\n🎁 Vantaggi:\n• Analisi foto/file\n• Generazione immagini\n• Promemoria",
        'vip_until': "⏰ Fino: {date}",
        'vip_forever': "⏰ Per sempre ♾️",
        'vip_inactive': "💎 <b>Nessun VIP</b>\n\nContatta @Ernest_Kostevich",
        'vip_only': "💎 Solo VIP. Contatta @Ernest_Kostevich",
        'admin_only': "❌ Solo creatore",
        'clear': "🧹 Contesto pulito!",
        'ai_error': "😔 Errore AI, riprova",
        'photo_analyzing': "🔍 Analizzo...",
        'photo_result': "📸 <b>Risposta:</b>\n\n{text}",
        'photo_error': "❌ Errore: {e}",
        'photo_no_caption': "📸 Foto ricevuta! Cosa devo fare?\n\n💡 Scrivi la tua domanda su questa foto.",
        'voice_transcribing': "🎙️ Trascrivo...",
        'voice_result': "🎙️ <b>Tu:</b> <i>{text}</i>\n\n🤖 <b>Risposta:</b>\n\n{response}",
        'voice_error': "❌ Errore voce: {e}",
        'file_analyzing': "📥 Analizzo file...",
        'file_result': "📄 <b>{name}</b>\n\n🤖 {text}",
        'file_error': "❌ Errore file: {e}",
        'gen_prompt': "❓ /generate [prompt]\n\nEsempio: /generate tramonto sull'oceano",
        'gen_progress': "🎨 Genero...",
        'gen_done': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Errore generazione",
        'note_saved': "✅ Nota #{n} salvata",
        'note_prompt': "❓ /note [testo]",
        'notes_empty': "📭 Nessuna nota",
        'notes_list': "📝 <b>Note ({n}):</b>\n\n{list}",
        'delnote_ok': "✅ Nota #{n} eliminata",
        'delnote_err': "❌ Nota non trovata",
        'todo_prompt': "❓ /todo add [testo] | list | del [#]",
        'todo_saved': "✅ Attività #{n} aggiunta",
        'todo_empty': "📭 Nessuna attività",
        'todo_list': "📋 <b>Attività ({n}):</b>\n\n{list}",
        'todo_del_ok': "✅ Attività #{n} eliminata",
        'todo_del_err': "❌ Attività non trovata",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 {time}\n📅 {date}\n🌍 {tz}",
        'time_error': "❌ Città non trovata",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 {temp}°C (percepiti {feels}°C)\n☁️ {desc}\n💧 {humidity}%\n💨 {wind} km/h",
        'weather_error': "❌ Errore meteo",
        'calc_result': "🧮 {expr} = <b>{result}</b>",
        'calc_error': "❌ Errore calcolo",
        'password_result': "🔑 <code>{pwd}</code>",
        'random_result': "🎲 {min}-{max}: <b>{r}</b>",
        'dice_result': "🎲 Uscito: <b>{r}</b>",
        'coin_heads': "Testa 🦅",
        'coin_tails': "Croce 💰",
        'remind_ok': "⏰ Promemoria tra {m} min:\n📝 {text}",
        'remind_prompt': "❓ /remind [minuti] [testo]",
        'remind_alert': "⏰ <b>PROMEMORIA</b>\n\n📝 {text}",
        'reminders_empty': "📭 Nessun promemoria",
        'reminders_list': "⏰ <b>Promemoria ({n}):</b>\n\n{list}",
        'grant_ok': "✅ VIP concesso: {id}\n⏰ {dur}",
        'grant_prompt': "❓ /grant_vip [id/@username] [week/month/year/forever]",
        'revoke_ok': "✅ VIP revocato: {id}",
        'users_list': "👥 <b>Utenti ({n}):</b>\n\n{list}",
        'broadcast_start': "📤 Invio...",
        'broadcast_done': "✅ Inviati: {ok}, errori: {err}",
        'broadcast_prompt': "❓ /broadcast [testo]",
        'joke': "😄 <b>Battuta:</b>\n\n{text}",
        'quote': "💭 <b>Citazione:</b>\n\n<i>{text}</i>",
        'fact': "🔬 <b>Fatto:</b>\n\n{text}",
        'btn_chat': "💬 Chat",
        'btn_notes': "📝 Note",
        'btn_weather': "🌍 Meteo",
        'btn_time': "⏰ Ora",
        'btn_games': "🎲 Giochi",
        'btn_info': "ℹ️ Info",
        'btn_vip': "💎 VIP",
        'btn_gen': "🖼️ Genera",
        'btn_admin': "👑 Admin",
        'need_admin': "❌ Serve admin!",
        'need_reply': "❌ Rispondi a un messaggio!",
        'bot_need_admin': "❌ Il bot deve essere admin!",
        'user_banned': "🚫 {name} bannato!",
        'user_unbanned': "✅ Utente sbannato!",
        'user_kicked': "👢 {name} espulso!",
        'user_muted': "🔇 {name} mutato per {mins} min!",
        'user_unmuted': "🔊 {name} smutato!",
        'user_warned': "⚠️ {name} avvertito! ({count}/3)",
        'user_warn_ban': "🚫 {name} bannato per 3 avvertimenti!",
        'user_unwarned': "✅ Avvertimento rimosso da {name} ({count}/3)",
        'warns_list': "⚠️ <b>Avvertimenti {name}:</b> {count}/3",
        'warns_empty': "✅ {name} non ha avvertimenti",
        'welcome_set': "✅ Benvenuto impostato!",
        'welcome_off': "✅ Benvenuto disabilitato",
        'rules_set': "✅ Regole impostate!",
        'rules_text': "📜 <b>Regole:</b>\n\n{rules}",
        'rules_empty': "📜 Nessuna regola",
        'ai_enabled': "✅ AI abilitato",
        'ai_disabled': "❌ AI disabilitato",
        'chat_info': "📊 <b>Chat</b>\n\n🆔 <code>{id}</code>\n📛 {title}\n👥 {members}\n💎 VIP: {vip}\n🤖 AI: {ai}",
        'top_users': "🏆 <b>Top attivi:</b>\n\n{list}",
        'top_empty': "📭 Nessuna statistica",
        'new_member': "👋 Benvenuto, {name}!",
    }
}


def t(key: str, lang: str, **kw) -> str:
    """Get localized text"""
    txt = L.get(lang, L['ru']).get(key, L['ru'].get(key, key))
    return txt.format(**kw) if kw else txt


# ============================================
# STORAGE CLASS
# ============================================

class Storage:
    def __init__(self):
        self.stats = self._load_stats()
        self.pending_images: Dict[int, bytes] = {}  # user_id -> image bytes
    
    def _load_stats(self):
        if engine:
            try:
                s = Session()
                st = s.query(Statistics).filter_by(key='global').first()
                s.close()
                return st.value if st else {}
            except:
                pass
        return {'total_messages': 0, 'ai_requests': 0}
    
    def save_stats(self):
        if engine:
            try:
                s = Session()
                s.merge(Statistics(key='global', value=self.stats))
                s.commit()
                s.close()
            except:
                pass
    
    def get_user(self, uid: int) -> Dict:
        if engine:
            s = Session()
            try:
                u = s.query(User).filter_by(id=uid).first()
                if not u:
                    u = User(id=uid)
                    s.add(u)
                    s.commit()
                return {
                    'id': u.id, 'username': u.username or '', 'first_name': u.first_name or '',
                    'vip': u.vip, 'vip_until': u.vip_until.isoformat() if u.vip_until else None,
                    'notes': u.notes or [], 'todos': u.todos or [], 'memory': u.memory or {},
                    'reminders': u.reminders or [], 'messages_count': u.messages_count or 0,
                    'language': u.language or 'ru'
                }
            except:
                return {'id': uid, 'language': 'ru', 'notes': [], 'todos': [], 'memory': {}}
            finally:
                s.close()
        return {'id': uid, 'language': 'ru', 'notes': [], 'todos': [], 'memory': {}, 'messages_count': 0}
    
    def update_user(self, uid: int, data: Dict):
        if engine:
            s = Session()
            try:
                u = s.query(User).filter_by(id=uid).first()
                if not u:
                    u = User(id=uid)
                    s.add(u)
                for k, v in data.items():
                    if k == 'vip_until' and v and isinstance(v, str):
                        v = datetime.fromisoformat(v)
                    setattr(u, k, v)
                u.last_active = datetime.now()
                s.commit()
            except:
                s.rollback()
            finally:
                s.close()
    
    def is_vip(self, uid: int) -> bool:
        u = self.get_user(uid)
        if not u.get('vip'):
            return False
        vu = u.get('vip_until')
        if not vu:
            return True
        try:
            if datetime.now() > datetime.fromisoformat(vu):
                self.update_user(uid, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True
    
    def get_chat(self, chat_id: int) -> Dict:
        if engine:
            s = Session()
            try:
                c = s.query(GroupChat).filter_by(id=chat_id).first()
                if not c:
                    c = GroupChat(id=chat_id)
                    s.add(c)
                    s.commit()
                return {
                    'id': c.id, 'title': c.title or '', 'vip': c.vip,
                    'vip_until': c.vip_until.isoformat() if c.vip_until else None,
                    'welcome_text': c.welcome_text, 'welcome_enabled': c.welcome_enabled,
                    'rules': c.rules, 'ai_enabled': c.ai_enabled,
                    'warns': c.warns or {}, 'messages_count': c.messages_count or 0,
                    'top_users': c.top_users or {}
                }
            except:
                return {'id': chat_id, 'ai_enabled': True, 'warns': {}, 'top_users': {}}
            finally:
                s.close()
        return {'id': chat_id, 'ai_enabled': True, 'warns': {}, 'top_users': {}}
    
    def update_chat(self, chat_id: int, data: Dict):
        if engine:
            s = Session()
            try:
                c = s.query(GroupChat).filter_by(id=chat_id).first()
                if not c:
                    c = GroupChat(id=chat_id)
                    s.add(c)
                for k, v in data.items():
                    if k == 'vip_until' and v and isinstance(v, str):
                        v = datetime.fromisoformat(v)
                    setattr(c, k, v)
                s.commit()
            except:
                s.rollback()
            finally:
                s.close()
    
    def is_chat_vip(self, chat_id: int) -> bool:
        c = self.get_chat(chat_id)
        if not c.get('vip'):
            return False
        vu = c.get('vip_until')
        if not vu:
            return True
        try:
            if datetime.now() > datetime.fromisoformat(vu):
                self.update_chat(chat_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True
    
    def add_chat_message(self, chat_id: int, user_id: int):
        c = self.get_chat(chat_id)
        top = c.get('top_users', {})
        top[str(user_id)] = top.get(str(user_id), 0) + 1
        self.update_chat(chat_id, {
            'messages_count': c.get('messages_count', 0) + 1,
            'top_users': top
        })
    
    def get_all_users(self) -> Dict:
        if engine:
            s = Session()
            try:
                users = s.query(User).all()
                return {u.id: {'id': u.id, 'username': u.username or '', 'first_name': u.first_name or '', 'vip': u.vip, 'language': u.language or 'ru'} for u in users}
            finally:
                s.close()
        return {}
    
    def get_all_chats(self) -> Dict:
        if engine:
            s = Session()
            try:
                chats = s.query(GroupChat).all()
                return {c.id: {'id': c.id, 'title': c.title, 'vip': c.vip} for c in chats}
            finally:
                s.close()
        return {}
    
    def get_user_by_identifier(self, ident: str) -> Optional[int]:
        ident = ident.strip().lstrip('@')
        if ident.startswith('-') and ident[1:].isdigit():
            return int(ident)
        if ident.isdigit():
            return int(ident)
        if engine:
            s = Session()
            try:
                u = s.query(User).filter(User.username.ilike(f"%{ident}%")).first()
                return u.id if u else None
            finally:
                s.close()
        return None
    
    def set_pending_image(self, uid: int, data: bytes):
        self.pending_images[uid] = data
    
    def get_pending_image(self, uid: int) -> Optional[bytes]:
        return self.pending_images.pop(uid, None)


storage = Storage()


# ============================================
# HELPERS
# ============================================

def identify_creator(user):
    global CREATOR_ID
    if user and user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id


def is_creator(uid: int) -> bool:
    return uid == CREATOR_ID


def get_lang(uid: int) -> str:
    return storage.get_user(uid).get('language', 'ru')


def get_keyboard(uid: int) -> ReplyKeyboardMarkup:
    lang = get_lang(uid)
    kb = [
        [KeyboardButton(t('btn_chat', lang)), KeyboardButton(t('btn_notes', lang))],
        [KeyboardButton(t('btn_weather', lang)), KeyboardButton(t('btn_time', lang))],
        [KeyboardButton(t('btn_games', lang)), KeyboardButton(t('btn_info', lang))]
    ]
    if storage.is_vip(uid):
        kb.insert(0, [KeyboardButton(t('btn_vip', lang)), KeyboardButton(t('btn_gen', lang))])
    if is_creator(uid):
        kb.append([KeyboardButton(t('btn_admin', lang))])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def get_help_keyboard(lang: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("🏠 " + ("Основные" if lang == 'ru' else "Базові" if lang == 'it' else "Basic"), callback_data="help:basic")],
        [InlineKeyboardButton("💬 AI", callback_data="help:ai")],
        [InlineKeyboardButton("📝 " + ("Заметки" if lang == 'ru' else "Note" if lang == 'it' else "Notes"), callback_data="help:notes")],
        [InlineKeyboardButton("📋 " + ("Задачи" if lang == 'ru' else "Attività" if lang == 'it' else "Tasks"), callback_data="help:todo")],
        [InlineKeyboardButton("🧠 " + ("Память" if lang == 'ru' else "Memoria" if lang == 'it' else "Memory"), callback_data="help:memory")],
        [InlineKeyboardButton("🌍 " + ("Утилиты" if lang == 'ru' else "Utilità" if lang == 'it' else "Utils"), callback_data="help:utils")],
        [InlineKeyboardButton("🎲 " + ("Игры" if lang == 'ru' else "Giochi" if lang == 'it' else "Games"), callback_data="help:games")],
        [InlineKeyboardButton("💎 VIP", callback_data="help:vip")],
        [InlineKeyboardButton("👥 " + ("Группы" if lang == 'ru' else "Gruppi" if lang == 'it' else "Groups"), callback_data="help:groups")],
    ]
    if is_admin:
        kb.append([InlineKeyboardButton("👑 Admin", callback_data="help:admin")])
    return InlineKeyboardMarkup(kb)


async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False


async def is_bot_admin(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, context.bot.id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False


async def send_long(msg, text: str):
    for i in range(0, len(text), 4000):
        await msg.reply_text(text[i:i+4000], parse_mode=ParseMode.HTML)
        if i + 4000 < len(text):
            await asyncio.sleep(0.3)


# ============================================
# AI FUNCTIONS
# ============================================

async def generate_ai_response(user_id: int, new_text: str = None, image: Image.Image = None) -> str:
    """Generate AI response with unified context"""
    try:
        # Build content for this request
        if image and new_text:
            # Image with caption
            unified_ctx.add_user_message(user_id, [new_text, image])
            history = unified_ctx.get_gemini_history(user_id)
            resp = vision_model.generate_content(history)
        elif image:
            # Image without caption - shouldn't happen, handled elsewhere
            unified_ctx.add_user_message(user_id, ["Что на этом изображении?", image])
            history = unified_ctx.get_gemini_history(user_id)
            resp = vision_model.generate_content(history)
        else:
            # Text only
            unified_ctx.add_user_message(user_id, new_text)
            history = unified_ctx.get_gemini_history(user_id)
            
            # Use chat for text-only
            chat = text_model.start_chat(history=history[:-1] if len(history) > 1 else [])
            resp = chat.send_message(new_text)
        
        response_text = resp.text
        unified_ctx.add_bot_message(user_id, response_text)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        return response_text
    except Exception as e:
        logger.error(f"AI error: {e}")
        return f"Ошибка AI: {str(e)}"


async def transcribe_audio(data: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            f.write(data)
            path = f.name
        uploaded = genai.upload_file(path=path, mime_type="audio/ogg")
        resp = text_model.generate_content(["Транскрибируй аудио. Только текст:", uploaded])
        os.remove(path)
        return resp.text.strip()
    except Exception as e:
        return f"❌ {e}"


async def extract_text_from_doc(data: bytes, name: str) -> str:
    try:
        ext = name.lower().split('.')[-1]
        if ext == 'txt':
            try:
                return data.decode('utf-8')
            except:
                return data.decode('cp1251', errors='ignore')
        elif ext == 'pdf':
            doc = fitz.open(stream=io.BytesIO(data), filetype="pdf")
            text = "".join([p.get_text() for p in doc])
            doc.close()
            return text
        elif ext in ['doc', 'docx']:
            d = docx.Document(io.BytesIO(data))
            return "\n".join([p.text for p in d.paragraphs])
        return data.decode('utf-8', errors='ignore')
    except Exception as e:
        return f"❌ {e}"


async def generate_imagen(prompt: str) -> Optional[bytes]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}, timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 200:
                    res = await r.json()
                    if res.get("predictions"):
                        return base64.b64decode(res["predictions"][0]["bytesBase64Encoded"])
    except Exception as e:
        logger.error(f"Imagen error: {e}")
    return None


# ============================================
# COMMAND HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    storage.update_user(uid, {
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    lang = get_lang(uid)
    
    if update.message.chat.type in ['group', 'supergroup']:
        chat_id = update.message.chat.id
        storage.update_chat(chat_id, {'title': update.message.chat.title})
        await update.message.reply_text(
            f"👋 Привет! Я <b>AI DISCO BOT</b>.\n\n"
            f"🤖 Упомяните @{context.bot.username} чтобы задать вопрос\n"
            f"📚 /help — команды\n"
            f"💎 VIP = безлимитный AI для чата!",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            t('welcome', lang, name=update.effective_user.first_name or 'User', creator=CREATOR_USERNAME),
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(uid)
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    await update.message.reply_text(
        t('help_title', lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(lang, is_creator(uid))
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    kb = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang:it")]
    ]
    await update.message.reply_text(t('lang_choose', lang), reply_markup=InlineKeyboardMarkup(kb))


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    unified_ctx.clear(uid)
    storage.pending_images.pop(uid, None)
    await update.message.reply_text(t('clear', get_lang(uid)))


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    db = "PostgreSQL ✓" if engine else "JSON"
    await update.message.reply_text(t('info', lang, db=db), parse_mode=ParseMode.HTML)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    users = storage.get_all_users()
    chats = storage.get_all_chats()
    up = datetime.now() - BOT_START_TIME
    await update.message.reply_text(
        t('status', lang,
          users=len(users),
          vips=sum(1 for u in users.values() if u.get('vip')),
          groups=len(chats),
          msgs=storage.stats.get('total_messages', 0),
          ai=storage.stats.get('ai_requests', 0),
          days=up.days,
          hours=up.seconds // 3600),
        parse_mode=ParseMode.HTML
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    u = storage.get_user(uid)
    txt = t('profile', lang,
            name=u.get('first_name') or 'User',
            id=uid,
            msgs=u.get('messages_count', 0),
            notes=len(u.get('notes', [])))
    if storage.is_vip(uid):
        vu = u.get('vip_until')
        txt += t('profile_vip', lang, date=datetime.fromisoformat(vu).strftime('%d.%m.%Y')) if vu else t('profile_vip_forever', lang)
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)


async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    chat_id = update.message.chat.id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    if is_group:
        if storage.is_chat_vip(chat_id):
            chat_data = storage.get_chat(chat_id)
            vu = chat_data.get('vip_until')
            until = f"До: {datetime.fromisoformat(vu).strftime('%d.%m.%Y')}" if vu else "Навсегда ♾️"
            await update.message.reply_text(f"💎 <b>VIP чат!</b>\n\n⏰ {until}\n\n🤖 AI доступен всем!", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(t('vip_inactive', lang), parse_mode=ParseMode.HTML)
        return
    
    if storage.is_vip(uid):
        u = storage.get_user(uid)
        vu = u.get('vip_until')
        until = t('vip_until', lang, date=datetime.fromisoformat(vu).strftime('%d.%m.%Y')) if vu else t('vip_forever', lang)
        await update.message.reply_text(t('vip_active', lang, until=until), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t('vip_inactive', lang), parse_mode=ParseMode.HTML)


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    if not context.args:
        await update.message.reply_text("❓ /ai [вопрос]")
        return
    uid = update.effective_user.id
    text = ' '.join(context.args)
    await update.message.chat.send_action('typing')
    response = await generate_ai_response(uid, text)
    await send_long(update.message, response)


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(uid)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    if not storage.is_vip(uid) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(t('vip_only', lang))
        return
    if not context.args:
        await update.message.reply_text(t('gen_prompt', lang))
        return
    
    prompt = ' '.join(context.args)
    await update.message.reply_text(t('gen_progress', lang))
    img = await generate_imagen(prompt)
    if img:
        await update.message.reply_photo(photo=img, caption=t('gen_done', lang, prompt=prompt), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t('gen_error', lang))


# ============================================
# NOTES & TODO
# ============================================

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args:
        await update.message.reply_text(t('note_prompt', lang))
        return
    txt = ' '.join(context.args)
    u = storage.get_user(uid)
    notes = u.get('notes', [])
    notes.append({'text': txt, 'date': datetime.now().isoformat()})
    storage.update_user(uid, {'notes': notes})
    await update.message.reply_text(t('note_saved', lang, n=len(notes)))


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    notes = storage.get_user(uid).get('notes', [])
    if not notes:
        await update.message.reply_text(t('notes_empty', lang))
        return
    lst = "\n".join([f"<b>#{i+1}</b> {n['text'][:50]}" for i, n in enumerate(notes)])
    await update.message.reply_text(t('notes_list', lang, n=len(notes), list=lst), parse_mode=ParseMode.HTML)


async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❓ /delnote [номер]")
        return
    n = int(context.args[0])
    notes = storage.get_user(uid).get('notes', [])
    if 1 <= n <= len(notes):
        notes.pop(n - 1)
        storage.update_user(uid, {'notes': notes})
        await update.message.reply_text(t('delnote_ok', lang, n=n))
    else:
        await update.message.reply_text(t('delnote_err', lang))


async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if not context.args:
        await update.message.reply_text(t('todo_prompt', lang))
        return
    
    sub = context.args[0].lower()
    u = storage.get_user(uid)
    todos = u.get('todos', [])
    
    if sub == 'add' and len(context.args) > 1:
        txt = ' '.join(context.args[1:])
        todos.append({'text': txt, 'date': datetime.now().isoformat()})
        storage.update_user(uid, {'todos': todos})
        await update.message.reply_text(t('todo_saved', lang, n=len(todos)))
    elif sub == 'list':
        if not todos:
            await update.message.reply_text(t('todo_empty', lang))
            return
        lst = "\n".join([f"<b>#{i+1}</b> {td['text'][:50]}" for i, td in enumerate(todos)])
        await update.message.reply_text(t('todo_list', lang, n=len(todos), list=lst), parse_mode=ParseMode.HTML)
    elif sub == 'del' and len(context.args) > 1 and context.args[1].isdigit():
        n = int(context.args[1])
        if 1 <= n <= len(todos):
            todos.pop(n - 1)
            storage.update_user(uid, {'todos': todos})
            await update.message.reply_text(t('todo_del_ok', lang, n=n))
        else:
            await update.message.reply_text(t('todo_del_err', lang))
    else:
        await update.message.reply_text(t('todo_prompt', lang))


# ============================================
# MEMORY
# ============================================

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("❓ /memorysave [ключ] [значение]")
        return
    key = context.args[0]
    value = ' '.join(context.args[1:])
    u = storage.get_user(uid)
    memory = u.get('memory', {})
    memory[key] = value
    storage.update_user(uid, {'memory': memory})
    await update.message.reply_text(f"✅ <b>{key}</b> = <code>{value}</code>", parse_mode=ParseMode.HTML)


async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /memoryget [ключ]")
        return
    key = context.args[0]
    u = storage.get_user(uid)
    if key in u.get('memory', {}):
        await update.message.reply_text(f"🔍 <b>{key}</b> = <code>{u['memory'][key]}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден")


async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    memory = storage.get_user(uid).get('memory', {})
    if not memory:
        await update.message.reply_text("📭 Память пуста")
        return
    txt = "🧠 <b>Память:</b>\n\n" + "\n".join([f"🔑 <b>{k}</b>: <code>{v}</code>" for k, v in memory.items()])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)


async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /memorydel [ключ]")
        return
    key = context.args[0]
    u = storage.get_user(uid)
    memory = u.get('memory', {})
    if key in memory:
        del memory[key]
        storage.update_user(uid, {'memory': memory})
        await update.message.reply_text(f"✅ Ключ '{key}' удалён")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден")


# ============================================
# UTILITIES
# ============================================

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    tzs = {
        'moscow': 'Europe/Moscow', 'москва': 'Europe/Moscow',
        'london': 'Europe/London', 'лондон': 'Europe/London',
        'new york': 'America/New_York', 'tokyo': 'Asia/Tokyo',
        'paris': 'Europe/Paris', 'berlin': 'Europe/Berlin',
        'rome': 'Europe/Rome', 'рим': 'Europe/Rome', 'roma': 'Europe/Rome'
    }
    tz_name = tzs.get(city.lower())
    if not tz_name:
        match = [z for z in pytz.all_timezones if city.lower().replace(" ", "_") in z.lower()]
        tz_name = match[0] if match else 'Europe/Moscow'
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        await update.message.reply_text(
            t('time_result', lang, city=city.title(), time=now.strftime('%H:%M:%S'), date=now.strftime('%d.%m.%Y'), tz=tz_name),
            parse_mode=ParseMode.HTML
        )
    except:
        await update.message.reply_text(t('time_error', lang))


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://wttr.in/{urlquote(city)}?format=j1", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    d = await r.json()
                    c = d['current_condition'][0]
                    await update.message.reply_text(
                        t('weather_result', lang, city=city.title(), temp=c['temp_C'], feels=c['FeelsLikeC'],
                          desc=c['weatherDesc'][0]['value'], humidity=c['humidity'], wind=c['windspeedKmph']),
                        parse_mode=ParseMode.HTML
                    )
                    return
    except:
        pass
    await update.message.reply_text(t('weather_error', lang))


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if len(context.args) < 2:
        await update.message.reply_text("❓ /translate [язык] [текст]")
        return
    target_lang = context.args[0]
    text = ' '.join(context.args[1:])
    await update.message.chat.send_action('typing')
    response = await generate_ai_response(uid, f"Переведи на {target_lang}: {text}")
    await send_long(update.message, response)


async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("❓ /calc [выражение]")
        return
    expr = ' '.join(context.args)
    if not all(c in "0123456789.+-*/() " for c in expr):
        await update.message.reply_text(t('calc_error', lang))
        return
    try:
        result = eval(expr, {"__builtins__": {}}, {})
        await update.message.reply_text(t('calc_result', lang, expr=expr, result=result), parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(t('calc_error', lang))


async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    length = int(context.args[0]) if context.args and context.args[0].isdigit() else 12
    length = max(8, min(50, length))
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    pwd = ''.join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(t('password_result', lang, pwd=pwd), parse_mode=ParseMode.HTML)


# ============================================
# GAMES
# ============================================

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    try:
        mn, mx = (int(context.args[0]), int(context.args[1])) if len(context.args) >= 2 else (1, 100)
    except:
        mn, mx = 1, 100
    await update.message.reply_text(t('random_result', lang, min=mn, max=mx, r=random.randint(mn, mx)), parse_mode=ParseMode.HTML)


async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    await update.message.reply_text(t('dice_result', get_lang(update.effective_user.id), r=random.randint(1, 6)), parse_mode=ParseMode.HTML)


async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(t('coin_heads' if random.choice([True, False]) else 'coin_tails', lang))


async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    jokes = {
        'ru': ["Программист: — Закрой окно! — И что, станет тепло? 😄", "31 OCT = 25 DEC 🎃", "Зачем очки? Чтобы лучше C++ 👓"],
        'en': ["Why dark mode? Light attracts bugs! 🐛", "Why quit? Didn't get arrays 🤷", "Favorite spot? Foo bar 🍻"],
        'it': ["31 OCT = 25 DEC 🎃", "Perché dark mode? La luce attira i bug! 🐛"]
    }
    await update.message.reply_text(t('joke', lang, text=random.choice(jokes.get(lang, jokes['en']))), parse_mode=ParseMode.HTML)


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    quotes = {
        'ru': ["Единственный способ делать великую работу — любить её. — Джобс", "Инновация отличает лидера. — Джобс"],
        'en': ["The only way to do great work is to love it. - Jobs", "Innovation distinguishes leaders. - Jobs"],
        'it': ["L'unico modo di fare un ottimo lavoro è amarlo. - Jobs", "L'innovazione distingue i leader. - Jobs"]
    }
    await update.message.reply_text(t('quote', lang, text=random.choice(quotes.get(lang, quotes['en']))), parse_mode=ParseMode.HTML)


async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    facts = {
        'ru': ["🌍 Земля — единственная планета не в честь бога", "🐙 У осьминога 3 сердца и голубая кровь"],
        'en': ["🌍 Earth is the only planet not named after a god", "🐙 Octopuses have 3 hearts and blue blood"],
        'it': ["🌍 La Terra è l'unico pianeta non dedicato a un dio", "🐙 I polpi hanno 3 cuori e sangue blu"]
    }
    await update.message.reply_text(t('fact', lang, text=random.choice(facts.get(lang, facts['en']))), parse_mode=ParseMode.HTML)


# ============================================
# REMINDERS
# ============================================

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not storage.is_vip(uid):
        await update.message.reply_text(t('vip_only', lang))
        return
    if len(context.args) < 2:
        await update.message.reply_text(t('remind_prompt', lang))
        return
    try:
        mins = int(context.args[0])
        txt = ' '.join(context.args[1:])
        when = datetime.now() + timedelta(minutes=mins)
        u = storage.get_user(uid)
        rems = u.get('reminders', [])
        rems.append({'text': txt, 'time': when.isoformat(), 'lang': lang})
        storage.update_user(uid, {'reminders': rems})
        
        context.job_queue.run_once(
            send_reminder_job,
            when=timedelta(minutes=mins),
            data={'user_id': uid, 'text': txt, 'lang': lang}
        )
        
        await update.message.reply_text(t('remind_ok', lang, m=mins, text=txt))
    except:
        await update.message.reply_text(t('remind_prompt', lang))


async def send_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    uid = data['user_id']
    txt = data['text']
    lang = data['lang']
    try:
        await context.bot.send_message(chat_id=uid, text=t('remind_alert', lang, text=txt), parse_mode=ParseMode.HTML)
        u = storage.get_user(uid)
        rems = [r for r in u.get('reminders', []) if r['text'] != txt]
        storage.update_user(uid, {'reminders': rems})
    except Exception as e:
        logger.warning(f"Remind error: {e}")


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not storage.is_vip(uid):
        await update.message.reply_text(t('vip_only', lang))
        return
    rems = storage.get_user(uid).get('reminders', [])
    if not rems:
        await update.message.reply_text(t('reminders_empty', lang))
        return
    lst = "\n".join([f"<b>#{i+1}</b> {datetime.fromisoformat(r['time']).strftime('%d.%m %H:%M')} - {r['text'][:30]}" for i, r in enumerate(rems)])
    await update.message.reply_text(t('reminders_list', lang, n=len(rems), list=lst), parse_mode=ParseMode.HTML)


# ============================================
# GROUP MODERATION
# ============================================

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not await is_bot_admin(chat_id, context):
        await update.message.reply_text(t('bot_need_admin', lang))
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await update.message.reply_text(t('user_banned', lang, name=target.first_name or target.username))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not context.args:
        await update.message.reply_text("❓ /unban [user_id]")
        return
    
    try:
        target_id = int(context.args[0])
        await context.bot.unban_chat_member(chat_id, target_id)
        await update.message.reply_text(t('user_unbanned', lang))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not await is_bot_admin(chat_id, context):
        await update.message.reply_text(t('bot_need_admin', lang))
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await context.bot.unban_chat_member(chat_id, target.id)
        await update.message.reply_text(t('user_kicked', lang, name=target.first_name or target.username))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not await is_bot_admin(chat_id, context):
        await update.message.reply_text(t('bot_need_admin', lang))
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    mins = int(context.args[0]) if context.args and context.args[0].isdigit() else 15
    target = update.message.reply_to_message.from_user
    
    try:
        until = datetime.now() + timedelta(minutes=mins)
        await context.bot.restrict_chat_member(
            chat_id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await update.message.reply_text(t('user_muted', lang, name=target.first_name or target.username, mins=mins))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    
    try:
        await context.bot.restrict_chat_member(
            chat_id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_invite_users=True
            )
        )
        await update.message.reply_text(t('user_unmuted', lang, name=target.first_name or target.username))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    chat_data = storage.get_chat(chat_id)
    warns = chat_data.get('warns', {})
    
    target_warns = warns.get(str(target.id), 0) + 1
    warns[str(target.id)] = target_warns
    storage.update_chat(chat_id, {'warns': warns})
    
    if target_warns >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.message.reply_text(t('user_warn_ban', lang, name=target.first_name or target.username))
            warns[str(target.id)] = 0
            storage.update_chat(chat_id, {'warns': warns})
        except:
            pass
    else:
        await update.message.reply_text(t('user_warned', lang, name=target.first_name or target.username, count=target_warns))


async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    chat_data = storage.get_chat(chat_id)
    warns = chat_data.get('warns', {})
    
    target_warns = max(0, warns.get(str(target.id), 0) - 1)
    warns[str(target.id)] = target_warns
    storage.update_chat(chat_id, {'warns': warns})
    
    await update.message.reply_text(t('user_unwarned', lang, name=target.first_name or target.username, count=target_warns))


async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = update.effective_user
    
    chat_data = storage.get_chat(chat_id)
    warns = chat_data.get('warns', {})
    count = warns.get(str(target.id), 0)
    
    if count > 0:
        await update.message.reply_text(t('warns_list', lang, name=target.first_name or target.username, count=count), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t('warns_empty', lang, name=target.first_name or target.username))


async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not context.args:
        await update.message.reply_text("❓ /setwelcome [текст]\n\nИспользуйте {name} для имени")
        return
    
    welcome_text = ' '.join(context.args)
    storage.update_chat(chat_id, {'welcome_text': welcome_text, 'welcome_enabled': True})
    await update.message.reply_text(t('welcome_set', lang))


async def welcomeoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    storage.update_chat(chat_id, {'welcome_enabled': False})
    await update.message.reply_text(t('welcome_off', lang))


async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not context.args:
        await update.message.reply_text("❓ /setrules [текст правил]")
        return
    
    rules = ' '.join(context.args)
    storage.update_chat(chat_id, {'rules': rules})
    await update.message.reply_text(t('rules_set', lang))


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    chat_data = storage.get_chat(chat_id)
    rules = chat_data.get('rules')
    
    if rules:
        await update.message.reply_text(t('rules_text', lang, rules=rules), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t('rules_empty', lang))


async def setai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.message.reply_text("❓ /setai [on/off]")
        return
    
    enabled = context.args[0].lower() == 'on'
    storage.update_chat(chat_id, {'ai_enabled': enabled})
    await update.message.reply_text(t('ai_enabled' if enabled else 'ai_disabled', lang))


async def chatinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat_data = storage.get_chat(chat_id)
    
    try:
        members = await context.bot.get_chat_member_count(chat_id)
    except:
        members = "?"
    
    vip_status = "✅" if storage.is_chat_vip(chat_id) else "❌"
    ai_status = "✅" if chat_data.get('ai_enabled', True) else "❌"
    
    await update.message.reply_text(
        t('chat_info', lang,
          id=chat_id,
          title=update.message.chat.title or "?",
          members=members,
          vip=vip_status,
          ai=ai_status),
        parse_mode=ParseMode.HTML
    )


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat_data = storage.get_chat(chat_id)
    top_users = chat_data.get('top_users', {})
    
    if not top_users:
        await update.message.reply_text(t('top_empty', lang))
        return
    
    sorted_users = sorted(top_users.items(), key=lambda x: x[1], reverse=True)[:10]
    
    lines = []
    medals = ['🥇', '🥈', '🥉']
    for i, (user_id, count) in enumerate(sorted_users):
        user_data = storage.get_user(int(user_id))
        name = user_data.get('first_name') or user_data.get('username') or user_id
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} {name} — {count}")
    
    await update.message.reply_text(t('top_users', lang, list='\n'.join(lines)), parse_mode=ParseMode.HTML)


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    
    chat_id = update.message.chat.id
    chat_data = storage.get_chat(chat_id)
    
    if not chat_data.get('welcome_enabled', True):
        return
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        name = member.first_name or member.username or "User"
        custom = chat_data.get('welcome_text') or t('new_member', 'ru', name=name)
        
        welcome_text = custom.replace('{name}', name)
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


# ============================================
# ADMIN COMMANDS
# ============================================

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    if len(context.args) < 2:
        await update.message.reply_text(t('grant_prompt', lang))
        return
    
    target = storage.get_user_by_identifier(context.args[0])
    if not target:
        await update.message.reply_text("❌ User/Chat not found")
        return
    
    dur = context.args[1].lower()
    durations = {'week': timedelta(weeks=1), 'month': timedelta(days=30), 'year': timedelta(days=365), 'forever': None}
    if dur not in durations:
        await update.message.reply_text(t('grant_prompt', lang))
        return
    
    delta = durations[dur]
    is_chat = target < 0
    
    if delta:
        until = datetime.now() + delta
        if is_chat:
            storage.update_chat(target, {'vip': True, 'vip_until': until.isoformat()})
        else:
            storage.update_user(target, {'vip': True, 'vip_until': until.isoformat()})
        dur_txt = until.strftime('%d.%m.%Y')
    else:
        if is_chat:
            storage.update_chat(target, {'vip': True, 'vip_until': None})
        else:
            storage.update_user(target, {'vip': True, 'vip_until': None})
        dur_txt = "Forever ♾️"
    
    await update.message.reply_text(t('grant_ok', lang, id=target, dur=dur_txt), parse_mode=ParseMode.HTML)
    
    try:
        await context.bot.send_message(chat_id=target, text=f"🎉 VIP granted! {dur_txt}")
    except:
        pass


async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    if not context.args:
        await update.message.reply_text("❓ /revoke_vip [id/@username]")
        return
    
    target = storage.get_user_by_identifier(context.args[0])
    if target:
        is_chat = target < 0
        if is_chat:
            storage.update_chat(target, {'vip': False, 'vip_until': None})
        else:
            storage.update_user(target, {'vip': False, 'vip_until': None})
        await update.message.reply_text(t('revoke_ok', lang, id=target), parse_mode=ParseMode.HTML)


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    users = storage.get_all_users()
    lst = "\n".join([f"{'💎' if u.get('vip') else ''} <code>{i}</code> {(u.get('first_name') or 'Unknown')[:15]}" for i, u in list(users.items())[:20]])
    await update.message.reply_text(t('users_list', lang, n=len(users), list=lst), parse_mode=ParseMode.HTML)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await status_command(update, context)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    if not context.args:
        await update.message.reply_text(t('broadcast_prompt', lang))
        return
    txt = ' '.join(context.args)
    await update.message.reply_text(t('broadcast_start', lang))
    users = storage.get_all_users()
    ok, err = 0, 0
    for target in users.keys():
        try:
            await context.bot.send_message(chat_id=target, text=f"📢 <b>Broadcast:</b>\n\n{txt}", parse_mode=ParseMode.HTML)
            ok += 1
            await asyncio.sleep(0.05)
        except:
            err += 1
    await update.message.reply_text(t('broadcast_done', lang, ok=ok, err=err))


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    
    try:
        users = storage.get_all_users()
        chats = storage.get_all_chats()
        backup_data = {
            'users': {str(k): v for k, v in users.items()},
            'chats': {str(k): v for k, v in chats.items()},
            'stats': storage.stats,
            'date': datetime.now().isoformat()
        }
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        await update.message.reply_document(
            document=io.BytesIO(backup_json.encode('utf-8')),
            filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            caption=f"✅ Backup created\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Backup error: {e}")


# ============================================
# MESSAGE HANDLERS
# ============================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    
    uid = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(uid)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP
    if not storage.is_vip(uid) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(t('vip_only', lang))
        return
    
    try:
        photo = update.message.photo[-1]
        f = await context.bot.get_file(photo.file_id)
        data = await f.download_as_bytearray()
        img = Image.open(io.BytesIO(bytes(data)))
        
        caption = update.message.caption
        
        if caption:
            # Photo with caption - analyze immediately
            await update.message.reply_text(t('photo_analyzing', lang))
            response = await generate_ai_response(uid, caption, img)
            await send_long(update.message, t('photo_result', lang, text=response))
        else:
            # Photo without caption - save and ask
            storage.set_pending_image(uid, bytes(data))
            await update.message.reply_text(t('photo_no_caption', lang))
    
    except Exception as e:
        await update.message.reply_text(t('photo_error', lang, e=str(e)))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not update.message.voice:
        return
    
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    await update.message.reply_text(t('voice_transcribing', lang))
    
    try:
        f = await context.bot.get_file(update.message.voice.file_id)
        data = await f.download_as_bytearray()
        
        transcription = await transcribe_audio(bytes(data))
        if transcription.startswith("❌"):
            await update.message.reply_text(transcription)
            return
        
        # Generate response
        response = await generate_ai_response(uid, f"[Голосовое]: {transcription}")
        
        await send_long(update.message, t('voice_result', lang, text=transcription, response=response))
    except Exception as e:
        await update.message.reply_text(t('voice_error', lang, e=str(e)))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not update.message.document:
        return
    
    uid = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(uid)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    if not storage.is_vip(uid) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(t('vip_only', lang))
        return
    
    doc = update.message.document
    name = doc.file_name or "file"
    caption = update.message.caption
    
    await update.message.reply_text(t('file_analyzing', lang))
    
    try:
        f = await context.bot.get_file(doc.file_id)
        data = await f.download_as_bytearray()
        
        doc_text = await extract_text_from_doc(bytes(data), name)
        if doc_text.startswith("❌"):
            await update.message.reply_text(doc_text)
            return
        
        prompt = f"Файл '{name}'. {caption or 'Проанализируй:'}\n\n{doc_text[:3000]}"
        response = await generate_ai_response(uid, prompt)
        
        await send_long(update.message, t('file_result', lang, name=name, text=response))
    except Exception as e:
        await update.message.reply_text(t('file_error', lang, e=str(e)))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not update.message.text:
        return
    
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    text = update.message.text
    lang = get_lang(uid)
    chat_id = update.message.chat.id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Update stats
    u = storage.get_user(uid)
    storage.update_user(uid, {
        'messages_count': u.get('messages_count', 0) + 1,
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # Track group stats
    if is_group:
        storage.add_chat_message(chat_id, uid)
    
    # Check menu buttons (private chat only)
    if not is_group:
        # Build button map dynamically
        btn_map = {}
        for lng in ['ru', 'en', 'it']:
            btn_map[L[lng].get('btn_chat', '')] = 'chat'
            btn_map[L[lng].get('btn_notes', '')] = 'notes'
            btn_map[L[lng].get('btn_weather', '')] = 'weather'
            btn_map[L[lng].get('btn_time', '')] = 'time'
            btn_map[L[lng].get('btn_games', '')] = 'games'
            btn_map[L[lng].get('btn_info', '')] = 'info'
            btn_map[L[lng].get('btn_vip', '')] = 'vip'
            btn_map[L[lng].get('btn_gen', '')] = 'gen'
            btn_map[L[lng].get('btn_admin', '')] = 'admin'
        
        if text in btn_map:
            await handle_menu_action(update, context, btn_map[text], lang)
            return
    
    # In groups, check mention or AI enabled
    if is_group:
        chat_data = storage.get_chat(chat_id)
        bot_un = context.bot.username
        
        if f"@{bot_un}" in text:
            text = text.replace(f"@{bot_un}", "").strip()
        elif not chat_data.get('ai_enabled', True):
            return
        elif not storage.is_chat_vip(chat_id) and not storage.is_vip(uid):
            return
    
    if not text:
        return
    
    # Check for pending image
    pending_img = storage.get_pending_image(uid)
    
    await update.message.chat.send_action("typing")
    
    try:
        if pending_img:
            # User sent text after image - analyze image with this text
            img = Image.open(io.BytesIO(pending_img))
            response = await generate_ai_response(uid, text, img)
        else:
            response = await generate_ai_response(uid, text)
        
        await send_long(update.message, response)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text(t('ai_error', lang))


async def handle_menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, lang: str):
    uid = update.effective_user.id
    
    if action == 'chat':
        await update.message.reply_text("💬 Просто пиши - отвечу!\n/clear - очистить контекст" if lang == 'ru' else "💬 Just type - I'll answer!\n/clear - clear context")
    elif action == 'notes':
        await notes_command(update, context)
    elif action == 'weather':
        await update.message.reply_text("/weather [город]" if lang == 'ru' else "/weather [city]")
    elif action == 'time':
        await update.message.reply_text("/time [город]" if lang == 'ru' else "/time [city]")
    elif action == 'games':
        kb = [
            [InlineKeyboardButton("🎲", callback_data="game:dice"), InlineKeyboardButton("🪙", callback_data="game:coin")],
            [InlineKeyboardButton("😄", callback_data="game:joke"), InlineKeyboardButton("💭", callback_data="game:quote")]
        ]
        await update.message.reply_text("🎲 " + ("Игры:" if lang == 'ru' else "Games:"), reply_markup=InlineKeyboardMarkup(kb))
    elif action == 'info':
        await info_command(update, context)
    elif action == 'vip':
        await vip_command(update, context)
    elif action == 'gen':
        await update.message.reply_text(t('gen_prompt', lang))
    elif action == 'admin' and is_creator(uid):
        await update.message.reply_text("👑 /users /stats /broadcast /grant_vip /revoke_vip /backup")


# ============================================
# CALLBACK HANDLER - FIXED
# ============================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user:
        return
    await q.answer()
    
    data = q.data
    uid = q.from_user.id
    lang = get_lang(uid)
    
    # Language change
    if data.startswith("lang:"):
        new_lang = data.split(":")[1]
        storage.update_user(uid, {'language': new_lang})
        await q.edit_message_text(t('lang_changed', new_lang))
        await q.message.reply_text(
            t('welcome', new_lang, name=q.from_user.first_name or 'User', creator=CREATOR_USERNAME),
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(uid)
        )
        return
    
    # Help sections - FIXED: check help:back BEFORE help:*
    if data == "help:back":
        await q.edit_message_text(
            t('help_title', lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(lang, is_creator(uid))
        )
        return
    
    if data.startswith("help:"):
        section = data.split(":")[1]
        help_key = f"help_{section}"
        help_text = t(help_key, lang)
        kb = [[InlineKeyboardButton(t('help_back', lang), callback_data="help:back")]]
        await q.edit_message_text(help_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return
    
    # Games
    if data == "game:dice":
        await q.message.reply_text(t('dice_result', lang, r=random.randint(1, 6)), parse_mode=ParseMode.HTML)
    elif data == "game:coin":
        await q.message.reply_text(t('coin_heads' if random.choice([True, False]) else 'coin_tails', lang))
    elif data == "game:joke":
        jokes = ["Программист: — Закрой окно! 😄", "31 OCT = 25 DEC 🎃"] if lang == 'ru' else ["Dark mode? Light attracts bugs! 🐛"]
        await q.message.reply_text(t('joke', lang, text=random.choice(jokes)), parse_mode=ParseMode.HTML)
    elif data == "game:quote":
        quotes = ["Любите то, что делаете. — Джобс"] if lang == 'ru' else ["Love what you do. - Jobs"]
        await q.message.reply_text(t('quote', lang, text=random.choice(quotes)), parse_mode=ParseMode.HTML)


# ============================================
# MAIN
# ============================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Basic commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("generate", generate_command))
    app.add_handler(CommandHandler("vip", vip_command))
    
    # Notes & Todo
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("delnote", delnote_command))
    app.add_handler(CommandHandler("todo", todo_command))
    
    # Memory
    app.add_handler(CommandHandler("memorysave", memory_save_command))
    app.add_handler(CommandHandler("memoryget", memory_get_command))
    app.add_handler(CommandHandler("memorylist", memory_list_command))
    app.add_handler(CommandHandler("memorydel", memory_del_command))
    
    # Utilities
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("calc", calc_command))
    app.add_handler(CommandHandler("password", password_command))
    
    # Games
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("dice", dice_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("joke", joke_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("fact", fact_command))
    
    # Reminders
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    
    # Group moderation
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("kick", kick_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("unwarn", unwarn_command))
    app.add_handler(CommandHandler("warns", warns_command))
    app.add_handler(CommandHandler("setwelcome", setwelcome_command))
    app.add_handler(CommandHandler("welcomeoff", welcomeoff_command))
    app.add_handler(CommandHandler("setrules", setrules_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("setai", setai_command))
    app.add_handler(CommandHandler("chatinfo", chatinfo_command))
    app.add_handler(CommandHandler("top", top_command))
    
    # Admin
    app.add_handler(CommandHandler("grant_vip", grant_vip_command))
    app.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("backup", backup_command))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT v4.1 STARTED!")
    logger.info("🤖 Gemini 2.5 Flash")
    logger.info("🔄 Unified context (text+photo+voice)")
    logger.info("👥 Group support with moderation")
    logger.info("🗄️ " + ("PostgreSQL ✓" if engine else "JSON"))
    logger.info("=" * 50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
