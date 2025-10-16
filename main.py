#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import random
import asyncio
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

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.9,
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

# Модели Gemini
model = genai.GenerativeModel(
    model_name='gemini-2.0-flash-exp',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="You are AI DISCO BOT, a friendly and helpful AI assistant. Respond in Russian with emojis. Your creator is @Ernest_Kostevich."
)

vision_model = genai.GenerativeModel(
    model_name='gemini-2.0-flash-exp',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# База данных
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

# Инициализация БД
if DATABASE_URL:
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    logger.info("✅ PostgreSQL подключен!")
else:
    engine = None
    Session = None
    logger.warning("⚠️ БД не настроена, используется локальное хранилище")

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.chat_sessions = {}
        self.username_to_id = {}
        
        if not engine:
            self.users = self.load_users()
            self.stats = self.load_stats()
            self.update_username_mapping()
        else:
            self.users = {}
            self.stats = self.get_stats_from_db()

    def load_users(self) -> Dict:
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {}
                    return {int(k): v for k, v in data.items()}
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            return {}

    def save_users(self):
        if engine:
            return
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            self.update_username_mapping()
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")

    def load_stats(self) -> Dict:
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        return data
            return {
                'total_messages': 0,
                'total_commands': 0,
                'ai_requests': 0,
                'start_date': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки статистики: {e}")
            return {
                'total_messages': 0,
                'total_commands': 0,
                'ai_requests': 0,
                'start_date': datetime.now().isoformat()
            }

    def save_stats(self):
        if engine:
            session = Session()
            try:
                session.merge(Statistics(key='global', value=self.stats, updated_at=datetime.now()))
                session.commit()
            except Exception as e:
                logger.error(f"Ошибка сохранения статистики в БД: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            try:
                with open(self.stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self.stats, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Ошибка сохранения статистики: {e}")

    def get_stats_from_db(self) -> Dict:
        if not engine:
            return self.load_stats()
        
        session = Session()
        try:
            stat = session.query(Statistics).filter_by(key='global').first()
            if stat:
                return stat.value
            return {
                'total_messages': 0,
                'total_commands': 0,
                'ai_requests': 0,
                'start_date': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return self.load_stats()
        finally:
            session.close()

    def update_username_mapping(self):
        self.username_to_id = {}
        for user_id, user_data in self.users.items():
            username = user_data.get('username')
            if username:
                self.username_to_id[username.lower()] = user_id

    def get_user_id_by_identifier(self, identifier: str) -> Optional[int]:
        identifier = identifier.strip()
        if identifier.startswith('@'):
            identifier = identifier[1:]
        
        if identifier.isdigit():
            return int(identifier)
        
        if engine:
            session = Session()
            try:
                user = session.query(User).filter(User.username.ilike(identifier)).first()
                return user.id if user else None
            finally:
                session.close()
        
        return self.username_to_id.get(identifier.lower())

    def get_user(self, user_id: int) -> Dict:
        if engine:
            session = Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id)
                    session.add(user)
                    session.commit()
                
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
                    'commands_count': user.commands_count or 0
                }
            finally:
                session.close()
        else:
            if user_id not in self.users:
                self.users[user_id] = {
                    'id': user_id,
                    'username': '',
                    'first_name': '',
                    'vip': False,
                    'vip_until': None,
                    'notes': [],
                    'todos': [],
                    'memory': {},
                    'reminders': [],
                    'registered': datetime.now().isoformat(),
                    'last_active': datetime.now().isoformat(),
                    'messages_count': 0,
                    'commands_count': 0
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
            except Exception as e:
                logger.error(f"Ошибка обновления пользователя: {e}")
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
            vip_until_dt = datetime.fromisoformat(vip_until)
            if datetime.now() > vip_until_dt:
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
                return {u.id: {
                    'id': u.id,
                    'username': u.username,
                    'first_name': u.first_name,
                    'vip': u.vip
                } for u in users}
            finally:
                session.close()
        return self.users

    def save_chat(self, user_id: int, message: str, response: str):
        if not engine:
            return
        
        session = Session()
        try:
            chat = Chat(user_id=user_id, message=message[:1000], response=response[:1000])
            session.add(chat)
            session.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения чата: {e}")
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

def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Создатель идентифицирован: {user.id}")

def is_creator(user_id: int) -> bool:
    return user_id == CREATOR_ID

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("💬 AI Чат"), KeyboardButton("📝 Заметки")],
        [KeyboardButton("🌍 Погода"), KeyboardButton("⏰ Время")],
        [KeyboardButton("🎲 Развлечения"), KeyboardButton("ℹ️ Инфо")]
    ]

    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton("💎 VIP Меню"), KeyboardButton("🖼️ Генерация")])

    if is_creator(user_id):
        keyboard.append([KeyboardButton("👑 Админ")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def generate_image_pollinations(prompt: str) -> Optional[str]:
    """Генерация изображений через Pollinations AI (бесплатно)"""
    try:
        encoded_prompt = urlquote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        return image_url
    except Exception as e:
        logger.error(f"Ошибка генерации изображения: {e}")
        return None

async def analyze_image_with_gemini(image_bytes: bytes, prompt: str = "Опиши подробно что изображено на этой картинке") -> str:
    """Анализ изображения с помощью Gemini Vision"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = vision_model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logger.error(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка при анализе изображения: {str(e)}"

async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    """Извлечение текста из документов"""
    try:
        ext = filename.lower().split('.')[-1]
        
        if ext == 'txt':
            try:
                return file_bytes.decode('utf-8')
            except:
                return file_bytes.decode('cp1251', errors='ignore')
        
        elif ext == 'pdf':
            try:
                import fitz
                pdf_file = io.BytesIO(file_bytes)
                doc = fitz.open(stream=pdf_file, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except ImportError:
                return "⚠️ PyMuPDF не установлен"
            except Exception as e:
                return f"❌ Ошибка чтения PDF: {str(e)}"
        
        elif ext in ['doc', 'docx']:
            try:
                import docx
                doc_file = io.BytesIO(file_bytes)
                doc = docx.Document(doc_file)
                text = "\n".join([para.text for para in doc.paragraphs])
                return text
            except ImportError:
                return "⚠️ python-docx не установлен"
            except Exception as e:
                return f"❌ Ошибка чтения DOCX: {str(e)}"
        
        else:
            try:
                return file_bytes.decode('utf-8', errors='ignore')
            except:
                return "❌ Неподдерживаемый формат файла"
                
    except Exception as e:
        logger.error(f"Ошибка извлечения текста: {e}")
        return f"❌ Ошибка обработки файла: {str(e)}"

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка документов"""
    user_id = update.effective_user.id
    document = update.message.document
    file_name = document.file_name or "unknown_file"
    
    await update.message.reply_text("📥 Загружаю и анализирую файл...")
    
    try:
        file_obj = await context.bot.get_file(document.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        
        extracted_text = await extract_text_from_document(bytes(file_bytes), file_name)
        
        if extracted_text.startswith("❌") or extracted_text.startswith("⚠️"):
            await update.message.reply_text(extracted_text)
            return
        
        analysis_prompt = f"Проанализируй содержимое файла '{file_name}' и дай краткий обзор:\n\n{extracted_text[:4000]}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(analysis_prompt)
        
        storage.save_chat(user_id, f"Анализ файла {file_name}", response.text)
        
        await update.message.reply_text(
            f"📄 <b>Файл:</b> {file_name}\n"
            f"📏 <b>Размер:</b> {document.file_size / 1024:.1f} KB\n\n"
            f"🤖 <b>Анализ AI:</b>\n\n{response.text}",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки документа: {e}")
        await update.message.reply_text(f"❌ Ошибка обработки файла: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ изображений (VIP)"""
    user_id = update.effective_user.id
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Анализ изображений доступен только VIP-пользователям.\n\n"
            "Свяжитесь с @Ernest_Kostevich для получения VIP статуса."
        )
        return
    
    photo = update.message.photo[-1]
    caption = update.message.caption or "Опиши подробно что изображено на этой картинке"
    
    await update.message.reply_text("🔍 Анализирую изображение...")
    
    try:
        file_obj = await context.bot.get_file(photo.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        
        analysis = await analyze_image_with_gemini(bytes(file_bytes), caption)
        
        storage.save_chat(user_id, "Анализ изображения", analysis)
        
        await update.message.reply_text(
            f"📸 <b>Анализ изображения (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP-функция",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка анализа фото: {e}")
        await update.message.reply_text(f"❌ Ошибка анализа изображения: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)

    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'commands_count': user_data.get('commands_count', 0) + 1
    })

    welcome_text = f"""
🤖 <b>Добро пожаловать в AI DISCO BOT!</b>

Привет, {user.first_name}! Я многофункциональный бот с ИИ на базе <b>Google Gemini 2.0</b>.

<b>🎯 Основные возможности:</b>
💬 Умный AI-чат с контекстом
📝 Система заметок и задач
🌍 Погода и время
🎲 Развлечения и игры
📎 Обработка файлов (TXT, PDF, DOCX)
🔍 Анализ изображений (VIP, Gemini Vision)
🖼️ Генерация изображений (VIP, Pollinations AI)

<b>⚡ Быстрый старт:</b>
• Напиши мне что угодно - я отвечу!
• Отправь файл - я проанализирую его
• /generate для создания изображений (VIP)
• Отправь фото - я опишу его (VIP)
• Используй /help для списка команд

<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}
"""

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(user.id)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {
        'commands_count': user_data.get('commands_count', 0) + 1
    })

    help_text = """
📚 <b>СПИСОК КОМАНД</b>

<b>🆕 Новые функции:</b>
🖼️ /generate [описание] - Генерация изображений (VIP)
📎 Отправь файл (TXT/PDF/DOCX) - Анализ документа
📸 Отправь фото - Анализ изображения (VIP)

<b>🏠 Основные:</b>
/start - Запуск бота
/help - Эта справка
/info - Информация о боте
/status - Статус системы
/profile - Твой профиль

<b>💬 AI и Память:</b>
/ai [вопрос] - Задать вопрос AI
/clear - Очистить контекст чата
/memorysave [ключ] [значение] - Сохранить в память
/memoryget [ключ] - Получить из памяти
/memorylist - Показать всю память
/memorydel [ключ] - Удалить из памяти

<b>📝 Заметки:</b>
/note [текст] - Создать заметку
/notes - Показать все заметки
/delnote [номер] - Удалить заметку

<b>🌍 Утилиты:</b>
/time [город] - Текущее время
/weather [город] - Погода
/translate [язык] [текст] - Перевод
/calc [выражение] - Калькулятор
/password [длина] - Генератор паролей

<b>🎲 Развлечения:</b>
/random [min] [max] - Случайное число
/dice - Бросить кубик
/coin - Подбросить монету
/joke - Случайная шутка
/quote - Мудрая цитата

<b>📋 Задачи:</b>
/todo add [текст] - Добавить задачу
/todo list - Показать задачи
/todo del [номер] - Удалить задачу

<b>💎 VIP Команды:</b>
/vip - Твой VIP статус
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/generate [описание] - Генерация изображений

💡 <i>Просто напиши мне что-нибудь - я отвечу!</i>
"""

    if is_creator(user_id):
        help_text += """
<b>👑 Команды Создателя:</b>
/grant_vip [id/@username] [срок] - Выдать VIP
/revoke_vip [id/@username] - Забрать VIP
/users - Список пользователей
/broadcast [текст] - Рассылка
/stats - Полная статистика
"""

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация изображений (VIP)"""
    user_id = update.effective_user.id
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Генерация изображений доступна только VIP-пользователям.\n\n"
            "Свяжитесь с @Ernest_Kostevich для получения VIP статуса."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /generate [описание изображения]\n\n"
            "Примеры:\n"
            "• /generate красивый закат над океаном\n"
            "• /generate футуристический город ночью\n"
            "• /generate милый котенок в корзине"
        )
        return
    
    prompt = ' '.join(context.args)
    await update.message.reply_text("🎨 Генерирую изображение, подождите...")
    
    try:
        image_url = await generate_image_pollinations(prompt)
        
        if image_url:
            await update.message.reply_photo(
                photo=image_url,
                caption=f"🖼️ <b>Сгенерировано:</b> {prompt}\n\n💎 VIP-функция | Pollinations AI",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ Не удалось сгенерировать изображение. Попробуйте другой запрос.")
    
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        await update.message.reply_text(f"❌ Ошибка генерации изображения: {str(e)}")

# Остальные команды (сокращенная версия для экономии места)

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ Использование: /ai [ваш вопрос]")
        return
    question = ' '.join(context.args)
    await process_ai_message(update, question, user_id)

async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action("typing")
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response.text)
        await update.message.reply_text(response.text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        await update.message.reply_text("😔 Извините, произошла ошибка.")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_chat_session(update.effective_user.id)
    await update.message.reply_text("🧹 Контекст диалога очищен!")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = """
🤖 <b>AI DISCO BOT</b>

<b>Версия:</b> 3.0
<b>AI Модель:</b> Google Gemini 2.0 Flash
<b>Создатель:</b> @Ernest_Kostevich

<b>🎯 О боте:</b>
Многофункциональный бот с ИИ для Telegram.

<b>⚡ Особенности:</b>
• Контекстный AI-диалог (Gemini 2.0)
• Система памяти (PostgreSQL)
• VIP функции
• Напоминания
• Обработка документов (TXT, PDF, DOCX)
• Анализ изображений (VIP, Gemini Vision)
• Генерация изображений (VIP, Pollinations AI)

<b>💬 Поддержка:</b>
По всем вопросам: @Ernest_Kostevich
"""
    await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = storage.stats
    all_users = storage.get_all_users()
    total_users = len(all_users)
    vip_users = sum(1 for u in all_users.values() if u.get('vip', False))

    uptime = datetime.now() - BOT_START_TIME
    uptime_str = f"{uptime.days}д {uptime.seconds // 3600}ч {(uptime.seconds % 3600) // 60}м"

    status_text = f"""
📊 <b>СТАТУС СИСТЕМЫ</b>

<b>👥 Пользователи:</b>
• Всего: {total_users}
• VIP: {vip_users}

<b>📈 Активность:</b>
• Сообщений: {stats.get('total_messages', 0)}
• Команд: {stats.get('total_commands', 0)}
• AI запросов: {stats.get('ai_requests', 0)}

<b>⏱ Время работы:</b> {uptime_str}

<b>✅ Статус:</b> Онлайн
<b>🤖 AI:</b> Gemini 2.0 ✓
<b>🗄️ БД:</b> {'PostgreSQL ✓' if engine else 'Local JSON'}
<b>🖼️ Генерация:</b> Pollinations AI ✓
<b>🔍 Анализ:</b> Gemini Vision ✓
"""
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)

    profile_text = f"""
👤 <b>Пользователь:</b> {user.get('first_name', 'Unknown')}
🆔 <b>ID:</b> <code>{user.get('id')}</code>
"""
    if user.get('username'):
        profile_text += f"📱 <b>Username:</b> @{user['username']}\n"

    profile_text += f"""
📅 <b>Зарегистрирован:</b> {user.get('registered', '')[:10]}
📊 <b>Сообщений:</b> {user.get('messages_count', 0)}
🎯 <b>Команд:</b> {user.get('commands_count', 0)}
📝 <b>Заметок:</b> {len(user.get('notes', []))}
📋 <b>Задач:</b> {len(user.get('todos', []))}
🧠 <b>Записей в памяти:</b> {len(user.get('memory', {}))}
"""

    if storage.is_vip(user_id):
        vip_until = user.get('vip_until')
        if vip_until:
            try:
                vip_until_dt = datetime.fromisoformat(vip_until)
                profile_text += f"💎 <b>VIP до:</b> {vip_until_dt.strftime('%d.%m.%Y %H:%M')}\n"
            except:
                profile_text += f"💎 <b>VIP:</b> Активен\n"
        else:
            profile_text += f"💎 <b>VIP:</b> Навсегда ♾️\n"

    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)

    if storage.is_vip(user_id):
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n✅ У вас активен VIP статус!\n\n"
        
        vip_until = user.get('vip_until')
        if vip_until:
            try:
                vip_until_dt = datetime.fromisoformat(vip_until)
                vip_text += f"⏰ <b>Активен до:</b> {vip_until_dt.strftime('%d.%m.%Y %H:%M')}\n\n"
            except:
                vip_text += "⏰ <b>Активен</b>\n\n"
        else:
            vip_text += "⏰ <b>Активен:</b> Навсегда ♾️\n\n"
        
        vip_text += """<b>🎁 Преимущества VIP:</b>
• ⏰ Система напоминаний
• 🖼️ Генерация изображений (Pollinations AI)
• 🔍 Анализ изображений (Gemini Vision)
• 🎯 Приоритетная обработка
• 💬 Увеличенный контекст AI"""
    else:
        vip_text = """💎 <b>VIP СТАТУС</b>

❌ У вас нет VIP статуса.

Свяжитесь с @Ernest_Kostevich для получения VIP."""

    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ Использование: /note [текст заметки]")
        return

    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)
    note = {'text': note_text, 'created': datetime.now().isoformat()}
    notes = user.get('notes', [])
    notes.append(note)
    storage.update_user(user_id, {'notes': notes})
    await update.message.reply_text(f"✅ Заметка #{len(notes)} сохранена!\n\n📝 {note_text}")

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    notes = user.get('notes', [])
    
    if not notes:
        await update.message.reply_text("📭 У вас пока нет заметок.")
        return

    notes_text = f"📝 <b>Ваши заметки ({len(notes)}):</b>\n\n"
    for i, note in enumerate(notes, 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y %H:%M')})\n{note['text']}\n\n"
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ Использование: /delnote [номер]")
        return

    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        
        if 1 <= note_num <= len(notes):
            deleted_note = notes.pop(note_num - 1)
            storage.update_user(user_id, {'notes': notes})
            await update.message.reply_text(f"✅ Заметка #{note_num} удалена:\n\n📝 {deleted_note['text']}")
        else:
            await update.message.reply_text(f"❌ Заметка #{note_num} не найдена.")
    except ValueError:
        await update.message.reply_text("❌ Укажите корректный номер заметки.")

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("❓ Использование: /memorysave [ключ] [значение]")
        return

    key = context.args[0]
    value = ' '.join(context.args[1:])
    user = storage.get_user(user_id)
    if 'memory' not in user:
        user['memory'] = {}
    user['memory'][key] = value
    storage.update_user(user_id, {'memory': user['memory']})
    await update.message.reply_text(f"✅ Сохранено в память:\n🔑 <b>{key}</b> = <code>{value}</code>", parse_mode=ParseMode.HTML)

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ Использование: /memoryget [ключ]")
        return

    key = context.args[0]
    user = storage.get_user(user_id)
    if key in user.get('memory', {}):
        await update.message.reply_text(f"🔍 Найдено:\n🔑 <b>{key}</b> = <code>{user['memory'][key]}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти.")

async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    
    if not memory:
        await update.message.reply_text("📭 Ваша память пуста.")
        return

    memory_text = "🧠 <b>Ваша память:</b>\n\n"
    for key, value in memory.items():
        memory_text += f"🔑 <b>{key}</b>: <code>{value}</code>\n"
    await update.message.reply_text(memory_text, parse_mode=ParseMode.HTML)

async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ Использование: /memorydel [ключ]")
        return

    key = context.args[0]
    user = storage.get_user(user_id)
    if key in user.get('memory', {}):
        del user['memory'][key]
        storage.update_user(user_id, {'memory': user['memory']})
        await update.message.reply_text(f"✅ Ключ '{key}' удалён из памяти.")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти.")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❓ Использование: /grant_vip [id/@username] [срок]\n\nСроки: week, month, year, forever")
        return

    try:
        identifier = context.args[0]
        duration = context.args[1].lower()
        target_id = storage.get_user_id_by_identifier(identifier)
        
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
            return
        
        durations = {
            'week': timedelta(weeks=1),
            'month': timedelta(days=30),
            'year': timedelta(days=365),
            'forever': None
        }
        
        if duration not in durations:
            await update.message.reply_text("❌ Неверный срок.")
            return
        
        if durations[duration]:
            vip_until = datetime.now() + durations[duration]
            storage.update_user(target_id, {'vip': True, 'vip_until': vip_until.isoformat()})
            duration_text = f"до {vip_until.strftime('%d.%m.%Y')}"
        else:
            storage.update_user(target_id, {'vip': True, 'vip_until': None})
            duration_text = "навсегда"
        
        await update.message.reply_text(f"✅ VIP статус выдан!\n\n🆔 ID: <code>{target_id}</code>\n⏰ Срок: {duration_text}", parse_mode=ParseMode.HTML)
        
        try:
            await context.bot.send_message(chat_id=target_id, text=f"🎉 Поздравляем! Вам выдан VIP статус {duration_text}!", parse_mode=ParseMode.HTML)
        except:
            pass
            
    except Exception as e:
        logger.error(f"Ошибка выдачи VIP: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    if not context.args:
        await update.message.reply_text("❓ Использование: /revoke_vip [id/@username]")
        return

    try:
        identifier = context.args[0]
        target_id = storage.get_user_id_by_identifier(identifier)
        
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
            return
        
        storage.update_user(target_id, {'vip': False, 'vip_until': None})
        await update.message.reply_text(f"✅ VIP статус отозван!\n\n🆔 ID: <code>{target_id}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка отзыва VIP: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    all_users = storage.get_all_users()
    users_text = f"👥 <b>ПОЛЬЗОВАТЕЛИ ({len(all_users)}):</b>\n\n"

    for user_id, user in list(all_users.items())[:20]:
        vip_badge = "💎" if user.get('vip', False) else ""
        users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"

    if len(all_users) > 20:
        users_text += f"\n<i>... и ещё {len(all_users) - 20}</i>"

    await update.message.reply_text(users_text, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    if not context.args:
        await update.message.reply_text("❓ Использование: /broadcast [текст]")
        return

    message_text = ' '.join(context.args)
    success = 0
    failed = 0

    status_msg = await update.message.reply_text("📤 Начинаю рассылку...")
    all_users = storage.get_all_users()

    for user_id in all_users.keys():
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 <b>Сообщение от создателя:</b>\n\n{message_text}", parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    await status_msg.edit_text(f"✅ Рассылка завершена!\n\n✅ Успешно: {success}\n❌ Ошибок: {failed}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    stats = storage.stats
    all_users = storage.get_all_users()
    total_users = len(all_users)
    vip_users = sum(1 for u in all_users.values() if u.get('vip', False))

    stats_text = f"""
📊 <b>СТАТИСТИКА</b>

<b>👥 Пользователи:</b>
• Всего: {total_users}
• VIP: {vip_users}

<b>📈 Активность:</b>
• Сообщений: {stats.get('total_messages', 0)}
• Команд: {stats.get('total_commands', 0)}
• AI запросов: {stats.get('ai_requests', 0)}
"""
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Эта команда доступна только VIP пользователям.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❓ Использование: /remind [минуты] [текст]")
        return

    try:
        minutes = int(context.args[0])
        text = ' '.join(context.args[1:])
        remind_time = datetime.now() + timedelta(minutes=minutes)
        
        user = storage.get_user(user_id)
        reminder = {'text': text, 'time': remind_time.isoformat(), 'created': datetime.now().isoformat()}
        reminders = user.get('reminders', [])
        reminders.append(reminder)
        storage.update_user(user_id, {'reminders': reminders})
        
        scheduler.add_job(send_reminder, 'date', run_date=remind_time, args=[context.bot, user_id, text])
        await update.message.reply_text(f"⏰ Напоминание создано!\n\n📝 {text}\n🕐 Напомню через {minutes} минут")
    except ValueError:
        await update.message.reply_text("❌ Укажите корректное количество минут.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Эта команда доступна только VIP пользователям.")
        return

    user = storage.get_user(user_id)
    reminders = user.get('reminders', [])

    if not reminders:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")
        return

    reminders_text = f"⏰ <b>Ваши напоминания ({len(reminders)}):</b>\n\n"
    for i, reminder in enumerate(reminders, 1):
        remind_time = datetime.fromisoformat(reminder['time'])
        reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n📝 {reminder['text']}\n\n"
    await update.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)

async def send_reminder(bot, user_id: int, text: str):
    try:
        await bot.send_message(chat_id=user_id, text=f"⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}", parse_mode=ParseMode.HTML)
        user = storage.get_user(user_id)
        reminders = [r for r in user.get('reminders', []) if r['text'] != text]
        storage.update_user(user_id, {'reminders': reminders})
    except Exception as e:
        logger.error(f"Ошибка напоминания: {e}")

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

    if text:
        await process_ai_message(update, text, user_id)

def main():
    if not BOT_TOKEN or not GEMINI_API_KEY:
        logger.error("Ошибка: BOT_TOKEN или GEMINI_API_KEY не установлены!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("memorysave", memory_save_command))
    application.add_handler(CommandHandler("memoryget", memory_get_command))
    application.add_handler(CommandHandler("memorylist", memory_list_command))
    application.add_handler(CommandHandler("memorydel", memory_del_command))
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("notes", notes_command))
    application.add_handler(CommandHandler("delnote", delnote_command))
    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    scheduler.start()

    logger.info("✅ Бот успешно запущен!")
    logger.info("=" * 50)
    logger.info("🤖 AI DISCO BOT работает!")
    logger.info("📦 Gemini 2.0 | Pollinations AI | PostgreSQL")
    logger.info("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
