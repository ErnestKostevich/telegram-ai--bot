#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI DISCO BOT - ОБЛЕГЧЕННАЯ ВЕРСИЯ
Использует только Gemini (работает на Free плане Render)
БЕЗ генерации изображений (по вашему запросу)
"""

import os
import json
import logging
import random
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import pytz
import requests
import io
from urllib.parse import quote as urlquote
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger, inspect, text as sa_text
from sqlalchemy.orm import sessionmaker, declarative_base

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

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

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    raise ValueError("BOT_TOKEN required")

# ============================================================================
# GEMINI - ДЛЯ ВСЕГО (текст + vision)
# ============================================================================

if GEMINI_API_KEY:
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

    # Одна модель для всего
    ai_model = genai.GenerativeModel(
        model_name='gemini-2.0-flash-exp',
        generation_config=generation_config,
        safety_settings=safety_settings
    )
    
    logger.info("✅ Gemini 2.0 Flash загружен для AI-чата и Vision")
else:
    ai_model = None
    logger.error("❌ GEMINI_API_KEY не установлен!")

# ============================================================================
# ЛОКАЛИЗАЦИЯ (сокращенная)
# ============================================================================

localization_strings = {
    'ru': {
        'welcome': (
            "🤖 <b>AI DISCO BOT v3.2</b>\n\n"
            "Привет, {first_name}! Я работаю на <b>Gemini 2.0 Flash</b>.\n\n"
            "<b>🎯 Возможности:</b>\n"
            "💬 AI-чат (БЕЗ лимитов!)\n"
            "📝 Заметки и задачи\n"
            "🌍 Погода и время\n"
            "🎲 Развлечения\n"
            "📎 Анализ файлов (VIP)\n"
            "🔍 Анализ изображений (VIP)\n\n"
            "<b>⚡ Команды:</b>\n"
            "/help - Все команды\n"
            "/vip - Статус VIP\n\n"
            "<b>👨‍💻 Создатель:</b> @{creator}"
        ),
        'ai_prompt_needed': "❓ /ai [вопрос]",
        'ai_typing': "typing",
        'ai_error': "😔 Ошибка AI, попробуйте снова.",
        'vip_only': "💎 Эта функция доступна только для VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'admin_only': "❌ Только для создателя.",
        # ... остальные строки (используйте из вашего main.py)
    }
}

def get_lang(user_id: int) -> str:
    return 'ru'  # Упрощенно

def get_text(key: str, lang: str = 'ru', **kwargs) -> str:
    try:
        keys = key.split('.')
        text = localization_strings[lang]
        for k in keys:
            text = text[k]
        return text.format(**kwargs) if kwargs else text
    except:
        return key

# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================

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
        logger.warning(f"⚠️ Ошибка БД: {e}")
        engine = None

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.chat_sessions = {}
        
        if not engine:
            self.users = self.load_users()
            self.stats = self.load_stats()
        else:
            self.users = {}
            self.stats = self.get_stats_from_db()

    def load_users(self) -> Dict:
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {int(k): v for k, v in data.items()} if isinstance(data, dict) else {}
            return {}
        except:
            return {}

    def save_users(self):
        if engine:
            return
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения: {e}")

    def load_stats(self) -> Dict:
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0}
        except:
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0}

    def save_stats(self):
        if engine:
            session = Session()
            try:
                session.merge(Statistics(key='global', value=self.stats))
                session.commit()
            except:
                session.rollback()
            finally:
                session.close()
        else:
            try:
                with open(self.stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self.stats, f, ensure_ascii=False, indent=2)
            except:
                pass

    def get_stats_from_db(self) -> Dict:
        if not engine:
            return self.load_stats()
        session = Session()
        try:
            stat = session.query(Statistics).filter_by(key='global').first()
            return stat.value if stat else {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0}
        except:
            return self.load_stats()
        finally:
            session.close()

    def get_user(self, user_id: int) -> Dict:
        if engine:
            session = Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id)
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
                logger.error(f"get_user error: {e}")
                return {'id': user_id, 'language': 'ru'}
            finally:
                session.close()
        else:
            if user_id not in self.users:
                self.users[user_id] = {
                    'id': user_id, 'username': '', 'first_name': '', 'vip': False, 
                    'vip_until': None, 'notes': [], 'todos': [], 'memory': {}, 
                    'reminders': [], 'registered': datetime.now().isoformat(), 
                    'last_active': datetime.now().isoformat(), 'messages_count': 0, 
                    'commands_count': 0, 'language': 'ru'
                }
                self.save_users()
            return self.users[user_id]

    def update_user(self, user_id: int, data: Dict):
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
            except:
                session.rollback()
            finally:
                session.close()
        else:
            user = self.get_user(user_id)
            user.update(data)
            user['last_active'] = datetime.now().isoformat()
            self.save_users()

    def is_vip(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user.get('vip', False):
            return False
        vip_until = user.get('vip_until')
        if vip_until is None:
            return True
        try:
            if datetime.now() > datetime.fromisoformat(vip_until):
                self.update_user(user_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True

    def get_all_users(self):
        if engine:
            session = Session()
            try:
                users = session.query(User).all()
                return {u.id: {'id': u.id, 'username': u.username, 'first_name': u.first_name, 
                              'vip': u.vip, 'language': u.language} for u in users}
            finally:
                session.close()
        return self.users

    def get_chat_session(self, user_id: int):
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = ai_model.start_chat(history=[]) if ai_model else None
        return self.chat_sessions[user_id]

    def clear_chat_session(self, user_id: int):
        if user_id in self.chat_sessions:
            del self.chat_sessions[user_id]

storage = DataStorage()
scheduler = AsyncIOScheduler()

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Создатель: {user.id}")

def is_creator(user_id: int) -> bool:
    return user_id == CREATOR_ID

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("💬 AI Чат"), KeyboardButton("📝 Заметки")],
        [KeyboardButton("🌍 Погода"), KeyboardButton("⏰ Время")],
        [KeyboardButton("🎲 Развлечения"), KeyboardButton("ℹ️ Инфо")]
    ]
    if storage.is_vip(user_id):
        keyboard.insert(0, [KeyboardButton("💎 VIP Меню")])
    if is_creator(user_id):
        keyboard.append([KeyboardButton("👑 Админ Панель")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ============================================================================
# КОМАНДЫ БОТА
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    user_data = storage.get_user(user.id)
    
    storage.update_user(user.id, {
        'username': user.username or '', 
        'first_name': user.first_name or '', 
        'commands_count': user_data.get('commands_count', 0) + 1
    })
    
    welcome_text = get_text('welcome', first_name=user.first_name, creator=CREATOR_USERNAME)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, 
                                   reply_markup=get_main_keyboard(user.id))

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(get_text('ai_prompt_needed'))
        return
    await process_ai_message(update, ' '.join(context.args), user_id)

async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action(get_text('ai_typing'))
        
        chat = storage.get_chat_session(user_id)
        if not chat:
            await update.message.reply_text(get_text('ai_error'))
            return
            
        response = chat.send_message(text)
        response_text = response.text
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        await send_long_message(update.message, response_text)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text(get_text('ai_error'))

async def send_long_message(message: Message, text: str):
    if len(text) <= 4000:
        await message.reply_text(text)
    else:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part)
            await asyncio.sleep(0.5)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_chat_session(update.effective_user.id)
    await update.message.reply_text("🧹 Контекст чата очищен!")

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if storage.is_vip(user_id):
        text = "💎 <b>VIP СТАТУС</b>\n\n✅ Активен!\n\n"
        vip_until = user.get('vip_until')
        if vip_until:
            text += f"⏰ До: {datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')}\n\n"
        else:
            text += "⏰ Навсегда ♾️\n\n"
        text += "<b>🎁 Преимущества:</b>\n• ⏰ Напоминания\n• 🔍 Анализ изображений\n• 📎 Анализ документов"
    else:
        text = "💎 <b>VIP СТАТУС</b>\n\n❌ Нет VIP.\n\nСвяжитесь с @Ernest_Kostevich"
        
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    identify_creator(update.effective_user)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only'))
        return
        
    if len(context.args) < 2:
        await update.message.reply_text("❓ /grant_vip [user_id] [week/month/year/forever]")
        return
        
    try:
        target_id = int(context.args[0])
        duration = context.args[1].lower()
        
        durations = {
            'week': timedelta(weeks=1), 
            'month': timedelta(days=30), 
            'year': timedelta(days=365), 
            'forever': None
        }
        
        if duration not in durations:
            await update.message.reply_text("❌ Неверный срок: week, month, year, forever")
            return
            
        if durations[duration]:
            vip_until = datetime.now() + durations[duration]
            storage.update_user(target_id, {'vip': True, 'vip_until': vip_until.isoformat()})
            await update.message.reply_text(f"✅ VIP выдан до {vip_until.strftime('%d.%m.%Y')}")
        else:
            storage.update_user(target_id, {'vip': True, 'vip_until': None})
            await update.message.reply_text("✅ VIP выдан навсегда!")
            
        try:
            await context.bot.send_message(target_id, "🎉 Вам выдан VIP статус!")
        except:
            pass
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    text = update.message.text
    
    user = storage.get_user(user_id)
    storage.update_user(user_id, {
        'messages_count': user.get('messages_count', 0) + 1,
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # Кнопки меню
    if text in ["💬 AI Чат"]:
        await update.message.reply_text("🤖 AI Чат активен!\n\nПросто пиши - я отвечу!")
        return
    elif text in ["ℹ️ Инфо"]:
        await update.message.reply_text(
            "🤖 <b>AI DISCO BOT v3.2</b>\n\n"
            "<b>AI:</b> Gemini 2.0 Flash\n"
            "<b>Создатель:</b> @Ernest_Kostevich\n\n"
            "<b>💬 Поддержка:</b> @Ernest_Kostevich",
            parse_mode=ParseMode.HTML
        )
        return
    
    # AI ответ на обычный текст
    if text and not text.startswith('/'):
        await process_ai_message(update, text, user_id)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only'))
        return
        
    photo = update.message.photo[-1]
    caption = update.message.caption or "Опиши что на картинке"
    
    await update.message.reply_text("🔍 Анализирую изображение...")
    
    try:
        file_obj = await context.bot.get_file(photo.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        
        image = Image.open(io.BytesIO(file_bytes))
        response = ai_model.generate_content([caption, image])
        
        await update.message.reply_text(f"📸 <b>Анализ:</b>\n\n{response.text}\n\n💎 VIP", 
                                       parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Photo error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

def signal_handler(signum, frame):
    logger.info("Останавливаем бота...")
    scheduler.shutdown()
    raise SystemExit

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    
    # Обработчики
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    scheduler.start()
    
    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН (ОБЛЕГЧЕННАЯ ВЕРСИЯ)!")
    logger.info("🤖 AI: Gemini 2.0 Flash (для всего)")
    logger.info("🗄️ БД: " + ("PostgreSQL ✓" if engine else "JSON"))
    logger.info("💾 RAM: ~200MB (работает на Free плане)")
    logger.info("=" * 50)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
