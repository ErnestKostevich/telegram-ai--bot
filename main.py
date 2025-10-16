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
from threading import Thread
import requests
import base64
import io
from urllib.parse import quote as urlquote

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask
from bs4 import BeautifulSoup
from PIL import Image

# Импорты для работы с БД и файлами
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Переменные окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PORT = int(os.getenv('PORT', 5000))
APP_URL = os.getenv('APP_URL')

# Параметры подключения к PostgreSQL
PG_HOST = os.getenv('PG_HOST')
PG_PORT = os.getenv('PG_PORT')
PG_DATABASE = os.getenv('PG_DATABASE')
PG_USER = os.getenv('PG_USER')
PG_PASSWORD = os.getenv('PG_PASSWORD')

if all([PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD]):
    DB_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
else:
    DB_URL = None
    logging.warning("PostgreSQL не настроен, используется локальное хранилище")

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

# Основная модель для текста
model = genai.GenerativeModel(
    model_name='gemini-2.0-flash-exp',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="You are AI DISCO BOT, a friendly and helpful AI assistant. Respond in Russian with emojis. Your creator is @Ernest_Kostevich."
)

# Модель с поддержкой изображений
vision_model = genai.GenerativeModel(
    model_name='gemini-2.0-flash-exp',
    generation_config=generation_config,
    safety_settings=safety_settings
)

flask_app = Flask(__name__)
last_activity = datetime.now()

@flask_app.route('/')
def health_check():
    global last_activity
    last_activity = datetime.now()
    uptime = datetime.now() - BOT_START_TIME
    return {
        'status': 'OK',
        'uptime_seconds': int(uptime.total_seconds()),
        'last_activity': last_activity.isoformat()
    }, 200

@flask_app.route('/health')
def health():
    global last_activity
    last_activity = datetime.now()
    return 'Healthy', 200

@flask_app.route('/ping')
def ping():
    global last_activity
    last_activity = datetime.now()
    return 'pong', 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, threaded=True)

# Класс для управления PostgreSQL
class DatabaseManager:
    def __init__(self, db_url: str):
        if not db_url:
            self.engine = None
            self.Session = None
            logger.warning("БД не настроена, используется локальное хранилище")
            return
        
        try:
            self.engine = create_engine(db_url, echo=False, pool_pre_ping=True)
            self.Session = sessionmaker(bind=self.engine)
            self.init_database()
            logger.info("✅ PostgreSQL подключен!")
        except Exception as e:
            logger.error(f"❌ Ошибка БД: {e}")
            self.engine = None
            self.Session = None

    def init_database(self):
        if not self.engine:
            return
        
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        vip BOOLEAN DEFAULT FALSE,
                        vip_until TIMESTAMP,
                        notes JSONB DEFAULT '[]'::JSONB,
                        todos JSONB DEFAULT '[]'::JSONB,
                        memory JSONB DEFAULT '{}'::JSONB,
                        reminders JSONB DEFAULT '[]'::JSONB,
                        registered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        messages_count INTEGER DEFAULT 0,
                        commands_count INTEGER DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS chats (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        message TEXT,
                        response TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS statistics (
                        key VARCHAR(50) PRIMARY KEY,
                        value JSONB,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.commit()
                logger.info("Таблицы БД инициализированы")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")

    def get_user(self, user_id: int) -> Dict:
        if not self.engine:
            return self._default_user(user_id)
        
        session = self.Session()
        try:
            result = session.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id})
            user = result.fetchone()
            
            if not user:
                session.execute(text("INSERT INTO users (id) VALUES (:user_id)"), {"user_id": user_id})
                session.commit()
                result = session.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id})
                user = result.fetchone()
            
            return dict(user._mapping) if user else self._default_user(user_id)
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return self._default_user(user_id)
        finally:
            session.close()

    def _default_user(self, user_id: int) -> Dict:
        return {
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

    def update_user(self, user_id: int, data: Dict):
        if not self.engine:
            return
        
        session = self.Session()
        try:
            update_fields = {k: v for k, v in data.items() if k not in ['notes', 'todos', 'memory', 'reminders']}
            update_fields['last_active'] = datetime.now()
            
            if update_fields:
                set_clause = ', '.join([f"{k} = :{k}" for k in update_fields])
                session.execute(text(f"UPDATE users SET {set_clause} WHERE id = :user_id"), 
                              {**update_fields, "user_id": user_id})
            
            for field in ['notes', 'todos', 'memory', 'reminders']:
                if field in data:
                    session.execute(
                        text(f"UPDATE users SET {field} = :{field}::JSONB WHERE id = :user_id"),
                        {field: json.dumps(data[field]), "user_id": user_id}
                    )
            
            session.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя: {e}")
            session.rollback()
        finally:
            session.close()

    def save_chat(self, user_id: int, message: str, response: str):
        if not self.engine:
            return
        
        session = self.Session()
        try:
            session.execute(
                text("INSERT INTO chats (user_id, message, response) VALUES (:user_id, :message, :response)"),
                {"user_id": user_id, "message": message[:1000], "response": response[:1000]}
            )
            session.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения чата: {e}")
        finally:
            session.close()

    def update_stats(self, key: str, value: Dict):
        if not self.engine:
            return
        
        session = self.Session()
        try:
            session.execute(
                text("""
                    INSERT INTO statistics (key, value) VALUES (:key, :value::JSONB)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """),
                {"key": key, "value": json.dumps(value)}
            )
            session.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления статистики: {e}")
        finally:
            session.close()

db_manager = DatabaseManager(DB_URL)

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.users = self.load_users()
        self.stats = self.load_stats()
        self.chat_sessions = {}
        self.username_to_id = {}
        self.update_username_mapping()

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
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            self.update_username_mapping()
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")

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
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            if db_manager.engine:
                db_manager.update_stats('global_stats', self.stats)
        except Exception as e:
            logger.error(f"Ошибка сохранения статистики: {e}")

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
        
        return self.username_to_id.get(identifier.lower())

    def get_user(self, user_id: int) -> Dict:
        if user_id not in self.users:
            if db_manager.engine:
                user_db = db_manager.get_user(user_id)
                self.users[user_id] = user_db
            else:
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
        user = self.get_user(user_id)
        user.update(data)
        user['last_active'] = datetime.now().isoformat()
        self.save_users()
        
        if db_manager.engine:
            db_manager.update_user(user_id, data)

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
                user['vip'] = False
                user['vip_until'] = None
                self.save_users()
                if db_manager.engine:
                    db_manager.update_user(user_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True

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
    global CREATOR_ID
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

def format_user_info(user: Dict) -> str:
    info = f"👤 <b>Пользователь:</b> {user.get('first_name', 'Unknown')}\n"
    info += f"🆔 <b>ID:</b> <code>{user.get('id', 'Unknown')}</code>\n"
    if user.get('username'):
        info += f"📱 <b>Username:</b> @{user['username']}\n"

    registered = user.get('registered', datetime.now().isoformat())
    info += f"📅 <b>Зарегистрирован:</b> {registered[:10]}\n"
    info += f"📊 <b>Сообщений:</b> {user.get('messages_count', 0)}\n"
    info += f"🎯 <b>Команд:</b> {user.get('commands_count', 0)}\n"

    if user.get('vip', False):
        vip_until = user.get('vip_until')
        if vip_until:
            try:
                vip_until_dt = datetime.fromisoformat(vip_until)
                info += f"💎 <b>VIP до:</b> {vip_until_dt.strftime('%d.%m.%Y %H:%M')}\n"
            except:
                info += f"💎 <b>VIP:</b> Активен\n"
        else:
            info += f"💎 <b>VIP:</b> Навсегда ♾️\n"

    return info

async def get_weather_data(city: str) -> Optional[str]:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?0&T&lang=ru"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
    except Exception as e:
        logger.error(f"Ошибка погоды: {e}")
        return None

def keep_awake():
    global last_activity
    try:
        if APP_URL:
            response = requests.get(f"{APP_URL}/health", timeout=5)
            logger.info(f"Keep-alive пинг. Статус: {response.status_code}")
            last_activity = datetime.now()
    except Exception as e:
        logger.error(f"Ошибка keep-awake: {e}")

# Функции для работы с изображениями и файлами

async def generate_image_pollinations(prompt: str) -> Optional[str]:
    """Генерация изображений через Pollinations AI (бесплатно)"""
    try:
        # Pollinations AI - бесплатный API для генерации изображений
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
        
        # Используем Gemini с поддержкой изображений
        response = vision_model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logger.error(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка при анализе изображения: {str(e)}"

async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    """Извлечение текста из различных документов"""
    try:
        ext = filename.lower().split('.')[-1]
        
        if ext == 'txt':
            # Текстовый файл
            try:
                return file_bytes.decode('utf-8')
            except:
                return file_bytes.decode('cp1251', errors='ignore')
        
        elif ext == 'pdf':
            # PDF файл
            try:
                import fitz  # PyMuPDF
                pdf_file = io.BytesIO(file_bytes)
                doc = fitz.open(stream=pdf_file, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except ImportError:
                return "⚠️ PyMuPDF не установлен. Установите: pip install PyMuPDF"
            except Exception as e:
                return f"❌ Ошибка чтения PDF: {str(e)}"
        
        elif ext in ['doc', 'docx']:
            # Word документ
            try:
                import docx
                doc_file = io.BytesIO(file_bytes)
                doc = docx.Document(doc_file)
                text = "\n".join([para.text for para in doc.paragraphs])
                return text
            except ImportError:
                return "⚠️ python-docx не установлен. Установите: pip install python-docx"
            except Exception as e:
                return f"❌ Ошибка чтения DOCX: {str(e)}"
        
        else:
            # Попытка прочитать как текст
            try:
                return file_bytes.decode('utf-8', errors='ignore')
            except:
                return "❌ Неподдерживаемый формат файла"
                
    except Exception as e:
        logger.error(f"Ошибка извлечения текста: {e}")
        return f"❌ Ошибка обработки файла: {str(e)}"

# Обработчики для файлов и изображений

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загруженных документов"""
    user_id = update.effective_user.id
    document = update.message.document
    file_name = document.file_name or "unknown_file"
    
    await update.message.reply_text("📥 Загружаю и анализирую файл...")
    
    try:
        file_obj = await context.bot.get_file(document.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        
        # Извлекаем текст из файла
        extracted_text = await extract_text_from_document(bytes(file_bytes), file_name)
        
        if extracted_text.startswith("❌") or extracted_text.startswith("⚠️"):
            await update.message.reply_text(extracted_text)
            return
        
        # Анализируем через AI
        analysis_prompt = f"Проанализируй содержимое файла '{file_name}' и дай краткий обзор:\n\n{extracted_text[:4000]}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(analysis_prompt)
        
        # Сохраняем в БД
        if db_manager.engine:
            db_manager.save_chat(user_id, f"Анализ файла {file_name}", response.text)
        
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
    """Анализ изображений (VIP функция с Gemini Vision)"""
    user_id = update.effective_user.id
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Анализ изображений доступен только VIP-пользователям.\n\n"
            "Свяжитесь с @Ernest_Kostevich для получения VIP статуса."
        )
        return
    
    photo = update.message.photo[-1]  # Берем самое большое качество
    caption = update.message.caption or "Опиши подробно что изображено на этой картинке"
    
    await update.message.reply_text("🔍 Анализирую изображение...")
    
    try:
        file_obj = await context.bot.get_file(photo.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        
        # Анализируем изображение с помощью Gemini Vision
        analysis = await analyze_image_with_gemini(bytes(file_bytes), caption)
        
        # Сохраняем в БД
        if db_manager.engine:
            db_manager.save_chat(user_id, "Анализ изображения", analysis)
        
        await update.message.reply_text(
            f"📸 <b>Анализ изображения (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP-функция",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка анализа фото: {e}")
        await update.message.reply_text(f"❌ Ошибка анализа изображения: {str(e)}")

# Команды бота

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
• Игры и развлечения
• Погода и время
• Обработка документов (TXT, PDF, DOCX)
• Анализ изображений (VIP, Gemini Vision)
• Генерация изображений (VIP, Pollinations AI)
• Калькулятор и утилиты

<b>🔒 Приватность:</b>
Все данные хранятся безопасно.

<b>💬 Поддержка:</b>
По всем вопросам: @Ernest_Kostevich
"""

    await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = storage.stats
    total_users = len(storage.users)
    vip_users = sum(1 for u in storage.users.values() if u.get('vip', False))

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
<b>🗄️ БД:</b> {'PostgreSQL ✓' if db_manager.engine else 'Local JSON'}
<b>🖼️ Генерация:</b> Pollinations AI ✓
<b>🔍 Анализ:</b> Gemini Vision ✓
"""

    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)

    profile_text = format_user_info(user)
    profile_text += f"\n📝 <b>Заметок:</b> {len(user.get('notes', []))}\n"
    profile_text += f"📋 <b>Задач:</b> {len(user.get('todos', []))}\n"
    profile_text += f"🧠 <b>Записей в памяти:</b> {len(user.get('memory', {}))}\n"

    if storage.is_vip(user_id):
        profile_text += f"⏰ <b>Напоминаний:</b> {len(user.get('reminders', []))}\n"

    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда генерации изображений (только VIP)"""
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
        # Генерируем изображение через Pollinations AI
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

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /ai [ваш вопрос]\n\n"
            "Пример: /ai Расскажи интересный факт"
        )
        return

    question = ' '.join(context.args)
    await process_ai_message(update, question, user_id)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    storage.clear_chat_session(user_id)
    await update.message.reply_text("🧹 Контекст диалога очищен!")

async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action("typing")

        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        if db_manager.engine:
            db_manager.save_chat(user_id, text, response.text)
        
        await update.message.reply_text(response.text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        await update.message.reply_text(
            "😔 Извините, произошла ошибка при обработке вашего запроса. Попробуйте ещё раз."
        )

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /memorysave [ключ] [значение]\n\n"
            "Пример: /memorysave любимый_цвет синий"
        )
        return

    key = context.args[0]
    value = ' '.join(context.args[1:])

    user = storage.get_user(user_id)
    if 'memory' not in user:
        user['memory'] = {}
    user['memory'][key] = value
    storage.update_user(user_id, {'memory': user['memory']})

    await update.message.reply_text(
        f"✅ Сохранено в память:\n"
        f"🔑 <b>{key}</b> = <code>{value}</code>",
        parse_mode=ParseMode.HTML
    )

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /memoryget [ключ]\n\n"
            "Пример: /memoryget любимый_цвет"
        )
        return

    key = context.args[0]
    user = storage.get_user(user_id)

    if key in user.get('memory', {}):
        await update.message.reply_text(
            f"🔍 Найдено:\n"
            f"🔑 <b>{key}</b> = <code>{user['memory'][key]}</code>",
            parse_mode=ParseMode.HTML
        )
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
        await update.message.reply_text(
            "❓ Использование: /memorydel [ключ]\n\n"
            "Пример: /memorydel любимый_цвет"
        )
        return

    key = context.args[0]
    user = storage.get_user(user_id)

    if key in user.get('memory', {}):
        del user['memory'][key]
        storage.update_user(user_id, {'memory': user['memory']})
        await update.message.reply_text(f"✅ Ключ '{key}' удалён из памяти.")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти.")

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /note [текст заметки]\n\n"
            "Пример: /note Купить молоко"
        )
        return

    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)

    note = {
        'text': note_text,
        'created': datetime.now().isoformat()
    }

    notes = user.get('notes', [])
    notes.append(note)
    storage.update_user(user_id, {'notes': notes})

    await update.message.reply_text(
        f"✅ Заметка #{len(notes)} сохранена!\n\n"
        f"📝 {note_text}"
    )

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
        notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y %H:%M')})\n"
        notes_text += f"{note['text']}\n\n"

    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /delnote [номер]\n\n"
            "Пример: /delnote 1"
        )
        return

    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        
        if 1 <= note_num <= len(notes):
            deleted_note = notes.pop(note_num - 1)
            storage.update_user(user_id, {'notes': notes})
            await update.message.reply_text(
                f"✅ Заметка #{note_num} удалена:\n\n"
                f"📝 {deleted_note['text']}"
            )
        else:
            await update.message.reply_text(f"❌ Заметка #{note_num} не найдена.")
    except ValueError:
        await update.message.reply_text("❌ Укажите корректный номер заметки.")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = ' '.join(context.args).lower() if context.args else 'moscow'

    timezones = {
        'moscow': 'Europe/Moscow',
        'london': 'Europe/London',
        'new york': 'America/New_York',
        'tokyo': 'Asia/Tokyo',
        'paris': 'Europe/Paris',
        'berlin': 'Europe/Berlin',
        'dubai': 'Asia/Dubai',
        'sydney': 'Australia/Sydney',
        'los angeles': 'America/Los_Angeles'
    }

    tz_name = timezones.get(city, 'Europe/Moscow')

    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        
        time_text = f"""
⏰ <b>Текущее время</b>

📍 <b>Город:</b> {city.title()}
🕐 <b>Время:</b> {current_time.strftime('%H:%M:%S')}
📅 <b>Дата:</b> {current_time.strftime('%d.%m.%Y')}
🌍 <b>Часовой пояс:</b> {tz_name}
"""
        await update.message.reply_text(time_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка времени: {e}")
        await update.message.reply_text(
            f"❌ Не удалось получить время для '{city}'."
        )

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = ' '.join(context.args) if context.args else 'Moscow'

    try:
        weather_text = await get_weather_data(city)
        
        if weather_text:
            await update.message.reply_text(
                f"🌍 <b>Погода в {city.title()}:</b>\n\n"
                f"<pre>{weather_text}</pre>",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(f"❌ Город '{city}' не найден.")
    except Exception as e:
        logger.error(f"Ошибка погоды: {e}")
        await update.message.reply_text("❌ Ошибка при получении данных о погоде.")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /translate [язык] [текст]\n\n"
            "Пример: /translate en Привет, как дела?"
        )
        return

    target_lang = context.args[0]
    text = ' '.join(context.args[1:])

    try:
        prompt = f"Переведи следующий текст на {target_lang}: {text}"
        chat = storage.get_chat_session(update.effective_user.id)
        response = chat.send_message(prompt)
        
        await update.message.reply_text(
            f"🌐 <b>Перевод:</b>\n\n{response.text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        await update.message.reply_text("❌ Ошибка при переводе текста.")

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /calc [выражение]\n\n"
            "Пример: /calc (15 * 3 + 7) / 4"
        )
        return

    expression = ' '.join(context.args)

    try:
        allowed_names = {"__builtins__": None}
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        
        await update.message.reply_text(
            f"🧮 <b>Результат:</b>\n\n{expression} = <b>{result}</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка калькулятора: {e}")
        await update.message.reply_text("❌ Ошибка при вычислении выражения.")

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /todo add [текст] | list | del [номер]\n\n"
            "Пример: /todo add Купить продукты"
        )
        return

    subcommand = context.args[0].lower()
    user = storage.get_user(user_id)

    if subcommand == 'add':
        if len(context.args) < 2:
            await update.message.reply_text("❓ Укажите текст задачи.")
            return
        todo_text = ' '.join(context.args[1:])
        todo = {
            'text': todo_text,
            'created': datetime.now().isoformat()
        }
        todos = user.get('todos', [])
        todos.append(todo)
        storage.update_user(user_id, {'todos': todos})
        await update.message.reply_text(
            f"✅ Задача #{len(todos)} добавлена!\n\n"
            f"📋 {todo_text}"
        )
    elif subcommand == 'list':
        todos = user.get('todos', [])
        if not todos:
            await update.message.reply_text("📭 У вас нет задач.")
            return
        todos_text = f"📋 <b>Ваши задачи ({len(todos)}):</b>\n\n"
        for i, todo in enumerate(todos, 1):
            created = datetime.fromisoformat(todo['created'])
            todos_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y')})\n"
            todos_text += f"{todo['text']}\n\n"
        await update.message.reply_text(todos_text, parse_mode=ParseMode.HTML)
    elif subcommand == 'del':
        if len(context.args) < 2:
            await update.message.reply_text("❓ Укажите номер задачи.")
            return
        try:
            todo_num = int(context.args[1])
            todos = user.get('todos', [])
            if 1 <= todo_num <= len(todos):
                deleted_todo = todos.pop(todo_num - 1)
                storage.update_user(user_id, {'todos': todos})
                await update.message.reply_text(
                    f"✅ Задача #{todo_num} удалена:\n\n"
                    f"📋 {deleted_todo['text']}"
                )
            else:
                await update.message.reply_text(f"❌ Задача #{todo_num} не найдена.")
        except ValueError:
            await update.message.reply_text("❌ Укажите корректный номер.")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text("❌ Длина должна быть от 8 до 50 символов.")
            return
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(
            f"🔑 <b>Сгенерированный пароль:</b>\n\n<code>{password}</code>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректную длину.")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) >= 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        else:
            min_val = 1
            max_val = 100

        result = random.randint(min_val, max_val)
        await update.message.reply_text(
            f"🎲 Случайное число от {min_val} до {max_val}:\n\n"
            f"<b>{result}</b>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректные числа.")

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    await update.message.reply_text(
        f"🎲 {dice_emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(['Орёл', 'Решка'])
    emoji = '🦅' if result == 'Орёл' else '💰'
    await update.message.reply_text(
        f"🪙 {emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Программист ложится спать. Жена говорит: — Дорогой, закрой окно, на улице холодно! Программист: — И что, если я закрою окно, на улице станет тепло? 😄",
        "— Почему программисты путают Хэллоуин и Рождество? — Потому что 31 OCT = 25 DEC! 🎃🎄",
        "Зачем программисту очки? Чтобы лучше C++! 👓"
    ]
    joke = random.choice(jokes)
    await update.message.reply_text(f"😄 <b>Шутка:</b>\n\n{joke}", parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
        "Инновация отличает лидера от последователя. — Стив Джобс",
        "Программирование — это искусство превращать кофе в код. — Неизвестный автор"
    ]
    quote = random.choice(quotes)
    await update.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{quote}</i>", parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)

    if storage.is_vip(user_id):
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n"
        vip_text += "✅ У вас активен VIP статус!\n\n"
        
        vip_until = user.get('vip_until')
        if vip_until:
            try:
                vip_until_dt = datetime.fromisoformat(vip_until)
                vip_text += f"⏰ <b>Активен до:</b> {vip_until_dt.strftime('%d.%m.%Y %H:%M')}\n\n"
            except:
                vip_text += "⏰ <b>Активен</b>\n\n"
        else:
            vip_text += "⏰ <b>Активен:</b> Навсегда ♾️\n\n"
        
        vip_text += "<b>🎁 Преимущества VIP:</b>\n"
        vip_text += "• ⏰ Система напоминаний\n"
        vip_text += "• 🖼️ Генерация изображений (Pollinations AI)\n"
        vip_text += "• 🔍 Анализ изображений (Gemini Vision)\n"
        vip_text += "• 🎯 Приоритетная обработка\n"
        vip_text += "• 💬 Увеличенный контекст AI\n"
    else:
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n"
        vip_text += "❌ У вас нет VIP статуса.\n\n"
        vip_text += "Свяжитесь с @Ernest_Kostevich для получения VIP."

    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Эта команда доступна только VIP пользователям.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /remind [минуты] [текст]\n\n"
            "Пример: /remind 30 Проверить почту"
        )
        return

    try:
        minutes = int(context.args[0])
        text = ' '.join(context.args[1:])
        
        remind_time = datetime.now() + timedelta(minutes=minutes)
        
        user = storage.get_user(user_id)
        reminder = {
            'text': text,
            'time': remind_time.isoformat(),
            'created': datetime.now().isoformat()
        }
        
        reminders = user.get('reminders', [])
        reminders.append(reminder)
        storage.update_user(user_id, {'reminders': reminders})
        
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=remind_time,
            args=[context.bot, user_id, text]
        )
        
        await update.message.reply_text(
            f"⏰ Напоминание создано!\n\n"
            f"📝 {text}\n"
            f"🕐 Напомню через {minutes} минут"
        )
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
        reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n"
        reminders_text += f"📝 {reminder['text']}\n\n"

    await update.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)

async def send_reminder(bot, user_id: int, text: str):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
            parse_mode=ParseMode.HTML
        )

        user = storage.get_user(user_id)
        reminders = [r for r in user.get('reminders', []) if r['text'] != text]
        storage.update_user(user_id, {'reminders': reminders})
    except Exception as e:
        logger.error(f"Ошибка напоминания: {e}")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /grant_vip [id/@username] [срок]\n\n"
            "Сроки: week, month, year, forever\n"
            "Пример: /grant_vip @username month"
        )
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
        
        user = storage.get_user(target_id)
        
        if durations[duration]:
            vip_until = datetime.now() + durations[duration]
            storage.update_user(target_id, {
                'vip': True,
                'vip_until': vip_until.isoformat()
            })
            duration_text = f"до {vip_until.strftime('%d.%m.%Y')}"
        else:
            storage.update_user(target_id, {
                'vip': True,
                'vip_until': None
            })
            duration_text = "навсегда"
        
        await update.message.reply_text(
            f"✅ VIP статус выдан!\n\n"
            f"🆔 ID: <code>{target_id}</code>\n"
            f"⏰ Срок: {duration_text}",
            parse_mode=ParseMode.HTML
        )
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 Поздравляем! Вам выдан VIP статус {duration_text}!",
                parse_mode=ParseMode.HTML
            )
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
        
        await update.message.reply_text(
            f"✅ VIP статус отозван!\n\n"
            f"🆔 ID: <code>{target_id}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка отзыва VIP: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    users_text = f"👥 <b>ПОЛЬЗОВАТЕЛИ ({len(storage.users)}):</b>\n\n"

    for user_id, user in list(storage.users.items())[:20]:
        vip_badge = "💎" if user.get('vip', False) else ""
        users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"

    if len(storage.users) > 20:
        users_text += f"\n<i>... и ещё {len(storage.users) - 20}</i>"

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

    for user_id in storage.users.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>Сообщение от создателя:</b>\n\n{message_text}",
                parse_mode=ParseMode.HTML
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    stats = storage.stats
    total_users = len(storage.users)
    vip_users = sum(1 for u in storage.users.values() if u.get('vip', False))

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

    # Обработка кнопок меню
    if text in ["💬 AI Чат", "📝 Заметки", "🌍 Погода", "⏰ Время", "🎲 Развлечения", "ℹ️ Инфо", "💎 VIP Меню", "👑 Админ", "🖼️ Генерация"]:
        await handle_menu_button(update, context, text)
        return

    # Обычное сообщение - отправляем в AI
    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str):
    user_id = update.effective_user.id

    if button == "💬 AI Чат":
        await update.message.reply_text(
            "🤖 <b>AI Чат режим</b>\n\n"
            "Просто напиши мне что-нибудь, и я отвечу!\n"
            "Используй /clear чтобы очистить контекст.",
            parse_mode=ParseMode.HTML
        )

    elif button == "📝 Заметки":
        keyboard = [
            [InlineKeyboardButton("➕ Создать заметку", callback_data="note_create")],
            [InlineKeyboardButton("📋 Мои заметки", callback_data="note_list")]
        ]
        await update.message.reply_text(
            "📝 <b>Система заметок</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif button == "🌍 Погода":
        await update.message.reply_text(
            "🌍 <b>Погода</b>\n\n"
            "Используй: /weather [город]\n"
            "Пример: /weather London",
            parse_mode=ParseMode.HTML
        )

    elif button == "⏰ Время":
        await update.message.reply_text(
            "⏰ <b>Текущее время</b>\n\n"
            "Используй: /time [город]\n"
            "Пример: /time Tokyo",
            parse_mode=ParseMode.HTML
        )

    elif button == "🎲 Развлечения":
        keyboard = [
            [InlineKeyboardButton("🎲 Кубик", callback_data="game_dice"),
             InlineKeyboardButton("🪙 Монета", callback_data="game_coin")],
            [InlineKeyboardButton("😄 Шутка", callback_data="game_joke"),
             InlineKeyboardButton("💭 Цитата", callback_data="game_quote")]
        ]
        await update.message.reply_text(
            "🎲 <b>Развлечения</b>\n\nВыбери что-нибудь:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif button == "ℹ️ Инфо":
        await info_command(update, context)

    elif button == "💎 VIP Меню":
        if storage.is_vip(user_id):
            keyboard = [
                [InlineKeyboardButton("⏰ Напоминания", callback_data="vip_reminders")],
                [InlineKeyboardButton("📊 Статистика", callback_data="vip_stats")]
            ]
            await update.message.reply_text(
                "💎 <b>VIP Меню</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await vip_command(update, context)

    elif button == "👑 Админ":
        if is_creator(user_id):
            keyboard = [
                [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
                [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")]
            ]
            await update.message.reply_text(
                "👑 <b>Админ Панель</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif button == "🖼️ Генерация":
        if storage.is_vip(user_id):
            await update.message.reply_text(
                "🖼️ <b>Генерация изображений (VIP)</b>\n\n"
                "Используй: /generate [описание]\n\n"
                "Примеры:\n"
                "• /generate красивый закат\n"
                "• /generate футуристический город\n"
                "• /generate милый котенок\n\n"
                "💡 Работает на Pollinations AI",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("💎 Генерация изображений доступна только VIP-пользователям.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    identify_creator(query.from_user)

    if data == "note_create":
        await query.message.reply_text(
            "➕ <b>Создание заметки</b>\n\n"
            "Используй: /note [текст]\n"
            "Пример: /note Купить хлеб",
            parse_mode=ParseMode.HTML
        )

    elif data == "note_list":
        user_id = query.from_user.id
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        
        if not notes:
            await query.message.reply_text("📭 У вас пока нет заметок.")
            return
        
        notes_text = f"📝 <b>Ваши заметки ({len(notes)}):</b>\n\n"
        for i, note in enumerate(notes, 1):
            created = datetime.fromisoformat(note['created'])
            notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y')})\n{note['text']}\n\n"
        
        await query.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

    elif data == "game_dice":
        result = random.randint(1, 6)
        dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
        await query.message.reply_text(f"🎲 {dice_emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)

    elif data == "game_coin":
        result = random.choice(['Орёл', 'Решка'])
        emoji = '🦅' if result == 'Орёл' else '💰'
        await query.message.reply_text(f"🪙 {emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)

    elif data == "game_joke":
        jokes = [
            "Программист ложится спать. Жена говорит: — Дорогой, закрой окно, на улице холодно! Программист: — И что, если я закрою окно, на улице станет тепло? 😄",
            "— Почему программисты путают Хэллоуин и Рождество? — Потому что 31 OCT = 25 DEC! 🎃🎄"
        ]
        joke = random.choice(jokes)
        await query.message.reply_text(f"😄 <b>Шутка:</b>\n\n{joke}", parse_mode=ParseMode.HTML)

    elif data == "game_quote":
        quotes = [
            "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
            "Инновация отличает лидера от последователя. — Стив Джобс"
        ]
        quote = random.choice(quotes)
        await query.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{quote}</i>", parse_mode=ParseMode.HTML)

    elif data == "vip_reminders":
        await reminders_command(query, context)

    elif data == "vip_stats":
        await profile_command(query, context)

    elif data == "admin_users":
        await users_command(query, context)

    elif data == "admin_stats":
        await stats_command(query, context)

    elif data == "admin_broadcast":
        if is_creator(query.from_user.id):
            await query.message.reply_text(
                "📢 <b>Рассылка</b>\n\n"
                "Используй: /broadcast [текст]\n"
                "Пример: /broadcast Привет всем!",
                parse_mode=ParseMode.HTML
            )

def main():
    if not BOT_TOKEN or not GEMINI_API_KEY:
        logger.error("Ошибка: BOT_TOKEN или GEMINI_API_KEY не установлены!")
        return

    # Запуск Flask в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask сервер запущен на порту {PORT}")

    # Настройка keep-alive пингов
    if APP_URL:
        scheduler.add_job(keep_awake, 'interval', minutes=5)
        logger.info("Keep-alive планировщик настроен")

    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация handlers
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

    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("todo", todo_command))
    application.add_handler(CommandHandler("password", password_command))

    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("quote", quote_command))

    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))

    # Новые команды
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
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск scheduler
    scheduler.start()

    logger.info("✅ Бот успешно запущен!")
    logger.info("=" * 50)
    logger.info("🤖 AI DISCO BOT работает!")
    logger.info("📦 Gemini 2.0 | Pollinations AI | PostgreSQL")
    logger.info("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
