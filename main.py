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
import zipfile
from urllib.parse import quote as urlquote

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from flask import Flask

from bs4 import BeautifulSoup

# Новые импорты для добавленных функций
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import fitz  # PyMuPDF для PDF
import docx  # python-docx для DOCX
import chardet  # для определения кодировки
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from diffusers import StableDiffusionPipeline

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PORT = int(os.getenv('PORT', 5000))
APP_URL = os.getenv('APP_URL')

# Параметры подключения к PostgreSQL
DB_URL = "postgresql://aiernestbot:VoAA5jJYe1P4ggnBPxtXeT3xi4DMcPaX@dpg-d3lv582dbo4c73bf4tcg-a.oregon-postgres.render.com/aibot_e56m"

CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="You are AI DISCO BOT, a friendly and helpful AI assistant built with Gemini 2.5. Respond in a friendly, engaging manner with emojis where appropriate. Your creator is @Ernest_Kostevich."
)

flask_app = Flask(__name__)

# Инициализация моделей для новых функций
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device for ML models: {device}")

# BLIP для анализа изображений (VIP only)
blip_processor = None
blip_model = None
try:
    blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
    logger.info("BLIP model loaded for image analysis")
except Exception as e:
    logger.error(f"Failed to load BLIP model: {e}")

# Stable Diffusion для генерации изображений (VIP only)
sd_pipeline = None
try:
    sd_pipeline = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    ).to(device)
    sd_pipeline.enable_attention_slicing()
    logger.info("Stable Diffusion loaded for image generation")
except Exception as e:
    logger.error(f"Failed to load Stable Diffusion: {e}")
    # Fallback to HuggingFace API if token provided
    HF_API_TOKEN = os.getenv('HF_API_TOKEN')

# Глобальная переменная для отслеживания активности
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

# Класс для управления PostgreSQL базой данных
class DatabaseManager:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        self.init_database()

    def init_database(self):
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
                    user_id BIGINT REFERENCES users(id),
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

    def get_user(self, user_id: int) -> Dict:
        session = self.Session()
        try:
            user = session.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id}).fetchone()
            if not user:
                session.execute(text("INSERT INTO users (id) VALUES (:user_id)"), {"user_id": user_id})
                session.commit()
                user = session.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id}).fetchone()
            user_dict = dict(user._mapping) if user else {}
            user_dict.setdefault('notes', [])
            user_dict.setdefault('todos', [])
            user_dict.setdefault('memory', {})
            user_dict.setdefault('reminders', [])
            user_dict.setdefault('registered', datetime.now().isoformat())
            user_dict.setdefault('last_active', datetime.now().isoformat())
            user_dict.setdefault('messages_count', 0)
            user_dict.setdefault('commands_count', 0)
            return user_dict
        finally:
            session.close()

    def update_user(self, user_id: int, data: Dict):
        session = self.Session()
        try:
            # Обновление скалярных полей
            update_fields = {k: v for k, v in data.items() if k not in ['notes', 'todos', 'memory', 'reminders']}
            update_fields['last_active'] = datetime.now()
            if update_fields:
                set_clause = ', '.join([f"{k} = :{k}" for k in update_fields])
                session.execute(text(f"UPDATE users SET {set_clause} WHERE id = :user_id"), {**update_fields, "user_id": user_id})
            # JSON поля
            for field in ['notes', 'todos', 'memory', 'reminders']:
                if field in data:
                    session.execute(
                        text(f"UPDATE users SET {field} = :{field}::JSONB WHERE id = :user_id"),
                        {field: json.dumps(data[field]), "user_id": user_id}
                    )
            session.commit()
        finally:
            session.close()

    def save_chat(self, user_id: int, message: str, response: str):
        session = self.Session()
        try:
            session.execute(
                text("INSERT INTO chats (user_id, message, response) VALUES (:user_id, :message, :response)"),
                {"user_id": user_id, "message": message, "response": response}
            )
            session.commit()
        finally:
            session.close()

    def update_stats(self, key: str, value: Dict):
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
        finally:
            session.close()

# Инициализация менеджера БД
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
        self.sync_from_db()

    def sync_from_db(self):
        """Синхронизация локальных данных с БД"""
        try:
            # Загрузка статистики из БД
            stats_row = db_manager.engine.execute(text("SELECT value FROM statistics WHERE key = 'global_stats'")).fetchone()
            if stats_row:
                self.stats = dict(stats_row[0])
            else:
                self.stats = {
                    'total_messages': 0,
                    'total_commands': 0,
                    'ai_requests': 0,
                    'start_date': datetime.now().isoformat()
                }
                db_manager.update_stats('global_stats', self.stats)

            # Обновление маппинга username
            users = db_manager.engine.execute(text("SELECT id, username FROM users")).fetchall()
            self.username_to_id = {u.username.lower(): u.id for u in users if u.username}
        except Exception as e:
            logger.error(f"Error syncing from DB: {e}")

    def load_users(self) -> Dict:
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {int(k): v for k, v in data.items()}
            return {}
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}

    def save_users(self):
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            self.update_username_mapping()
        except Exception as e:
            logger.error(f"Error saving users: {e}")

    def load_stats(self) -> Dict:
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                'total_messages': 0,
                'total_commands': 0,
                'ai_requests': 0,
                'start_date': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            return {}

    def save_stats(self):
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            db_manager.update_stats('global_stats', self.stats)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")

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
        # Проверяем локально, если нет - загружаем из БД
        if user_id not in self.users:
            user_db = db_manager.get_user(user_id)
            self.users[user_id] = user_db
            self.save_users()
        return self.users[user_id]

    def update_user(self, user_id: int, data: Dict):
        user = self.get_user(user_id)
        user.update(data)
        user['last_active'] = datetime.now().isoformat()
        self.save_users()
        # Синхронизируем с БД
        db_manager.update_user(user_id, data)

    def is_vip(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user['vip']:
            return False
        if user['vip_until'] is None:
            return True
        vip_until = datetime.fromisoformat(user['vip_until'])
        if datetime.now() > vip_until:
            user['vip'] = False
            user['vip_until'] = None
            self.save_users()
            db_manager.update_user(user_id, {'vip': False, 'vip_until': None})
            return False
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
        logger.info(f"Creator identified: {user.id}")

def is_creator(user_id: int) -> bool:
    global CREATOR_ID
    return user_id == CREATOR_ID

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("💬 AI Чат"), KeyboardButton("📝 Заметки")],
        [KeyboardButton("🌍 Погода"), KeyboardButton("⏰ Время")],
        [KeyboardButton("🎲 Развлечения"), KeyboardButton("ℹ️ Инфо")],
        [KeyboardButton("🖼️ Генерация"), KeyboardButton("📎 Файлы")],
        [KeyboardButton("🔍 Анализ фото")]
    ]

    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton("💎 VIP Меню")])

    if is_creator(user_id):
        keyboard.append([KeyboardButton("👑 Админ Панель")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def format_user_info(user: Dict) -> str:
    info = f"👤 <b>Пользователь:</b> {user.get('first_name', 'Unknown')}\n"
    info += f"🆔 <b>ID:</b> <code>{user['id']}</code>\n"
    if user.get('username'):
        info += f"📱 <b>Username:</b> @{user['username']}\n"

    info += f"📅 <b>Зарегистрирован:</b> {user['registered'][:10]}\n"
    info += f"📊 <b>Сообщений:</b> {user['messages_count']}\n"
    info += f"🎯 <b>Команд:</b> {user['commands_count']}\n"

    if user['vip']:
        if user['vip_until']:
            vip_until = datetime.fromisoformat(user['vip_until'])
            info += f"💎 <b>VIP до:</b> {vip_until.strftime('%d.%m.%Y %H:%M')}\n"
        else:
            info += f"💎 <b>VIP:</b> Навсегда ♾️\n"

    return info

async def get_weather_data(city: str) -> Optional[str]:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?0&T"  # ?0 for short version, &T for plain text without ANSI
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return None

# Keep-alive функция
def keep_awake():
    global last_activity
    try:
        if APP_URL:
            response = requests.get(f"{APP_URL}/health", timeout=5)
            logger.info(f"Keep-alive ping sent. Status: {response.status_code}")
            last_activity = datetime.now()
    except Exception as e:
        logger.error(f"Keep-awake error: {e}")

# Новые функции для обработки файлов и изображений
async def extract_text_from_file(file_path: str, file_name: str) -> str:
    """Извлечение текста из различных типов файлов"""
    try:
        ext = file_name.lower().split('.')[-1]
        if ext == 'pdf':
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        elif ext == 'docx':
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        elif ext == 'txt':
            with open(file_path, 'rb') as f:
                raw = f.read()
                encoding = chardet.detect(raw)['encoding'] or 'utf-8'
                return raw.decode(encoding)
        elif ext == 'zip':
            text = ""
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    if not file_info.is_dir() and file_info.filename.endswith(('.txt', '.md')):
                        with zip_ref.open(file_info) as f:
                            content = f.read().decode('utf-8', errors='ignore')
                            text += f"\n--- {file_info.filename} ---\n{content}\n"
            return text
        else:
            # Попытка прочитать как текст
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                with open(file_path, 'rb') as f:
                    raw = f.read()
                    encoding = chardet.detect(raw)['encoding']
                    return raw.decode(encoding, errors='ignore')
    except Exception as e:
        logger.error(f"Error extracting text from {file_name}: {e}")
        return f"Ошибка при извлечении текста из файла: {str(e)}"

def analyze_image_with_blip(image_bytes: bytes) -> str:
    """Анализ изображения с помощью BLIP (только для VIP)"""
    if blip_model is None or blip_processor is None:
        return "❌ Модель анализа изображений недоступна"
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        inputs = blip_processor(image, return_tensors="pt").to(device)
        with torch.no_grad():
            out = blip_model.generate(**inputs, max_length=50)
        description = blip_processor.decode(out[0], skip_special_tokens=True)
        return description
    except Exception as e:
        logger.error(f"BLIP analysis error: {e}")
        return "❌ Ошибка при анализе изображения"

async def generate_image(prompt: str) -> Optional[io.BytesIO]:
    """Генерация изображения (только для VIP)"""
    try:
        if sd_pipeline:
            image = sd_pipeline(prompt, num_inference_steps=20, guidance_scale=7.5).images[0]
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer
        elif HF_API_TOKEN:
            api_url = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
            headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
            payload = {"inputs": prompt}
            response = requests.post(api_url, headers=headers, json=payload)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                buffer = io.BytesIO()
                image.save(buffer, format='PNG')
                buffer.seek(0)
                return buffer
        return None
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return None

# Новые команды
async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда генерации изображений (только VIP)"""
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Генерация изображений доступна только VIP-пользователям.")
        return
    if not context.args:
        await update.message.reply_text("❓ Использование: /generate [описание изображения]\nПример: /generate красивый закат")
        return
    prompt = ' '.join(context.args)
    await update.message.chat.send_action("upload_photo")
    await update.message.reply_text("🎨 Генерирую изображение...")
    buffer = await generate_image(prompt)
    if buffer:
        await update.message.reply_photo(
            photo=buffer,
            caption=f"🖼️ Сгенерировано по запросу: {prompt}\n\n💎 VIP-функция",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("❌ Не удалось сгенерировать изображение. Попробуйте другой запрос.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загруженных файлов"""
    user_id = update.effective_user.id
    document = update.message.document
    file_name = document.file_name or "unknown_file"
    file_id = document.file_id
    await update.message.reply_text("📥 Загружаю и анализирую файл...")
    try:
        file_obj = await context.bot.get_file(file_id)
        file_bytes = await file_obj.download_as_bytearray()
        temp_path = "temp_file"
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
        extracted_text = await extract_text_from_file(temp_path, file_name)
        # Сохраняем в БД
        db_manager.save_chat(user_id, f"Анализ файла {file_name}", extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text)
        # Анализ через AI
        analysis_prompt = f"Проанализируй содержимое файла '{file_name}' и дай краткий обзор или ответ на основе его:\n\n{extracted_text[:4000]}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(analysis_prompt)
        await update.message.reply_text(
            f"📄 <b>Файл: {file_name}</b>\n"
            f"Тип: {document.mime_type or 'неизвестно'}\n"
            f"Размер: {document.file_size / 1024:.1f} KB\n\n"
            f"🤖 <b>Анализ AI:</b>\n\n{response.text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Document handling error: {e}")
        await update.message.reply_text(f"❌ Ошибка обработки файла: {str(e)}")
    finally:
        if os.path.exists("temp_file"):
            os.remove("temp_file")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ изображений (только VIP)"""
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Анализ изображений доступен только VIP-пользователям.")
        return
    photo = update.message.photo[-1]  # Лучшее качество
    file_id = photo.file_id
    await update.message.reply_text("🔍 Анализирую изображение...")
    try:
        file_obj = await context.bot.get_file(file_id)
        file_bytes = await file_obj.download_as_bytearray()
        blip_desc = analyze_image_with_blip(file_bytes)
        chat = storage.get_chat_session(user_id)
        ai_prompt = f"Опиши подробнее изображение на основе: {blip_desc}"
        response = chat.send_message(ai_prompt)
        db_manager.save_chat(user_id, "Анализ изображения", f"{blip_desc}\n{response.text}")
        await update.message.reply_text(
            f"📸 <b>Описание изображения (BLIP):</b> {blip_desc}\n\n"
            f"🤖 <b>Подробный анализ AI:</b>\n{response.text}\n\n💎 VIP-функция",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Photo analysis error: {e}")
        await update.message.reply_text("❌ Ошибка анализа изображения.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    identify_creator(user)

    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'commands_count': user_data['commands_count'] + 1
    })

    welcome_text = f"""
🤖 <b>Добро пожаловать в AI DISCO BOT!</b>

Привет, {user.first_name}! Я многофункциональный бот с искусственным интеллектом на базе <b>Google Gemini 2.5</b>.

<b>🎯 Основные возможности:</b>
💬 Умный AI-чат с контекстом
📝 Система заметок
🌍 Погода и время
🎲 Развлечения и игры
🖼️ Генерация изображений (VIP)
📎 Обработка файлов (PDF, TXT, DOCX, ZIP)
🔍 Анализ изображений (VIP)
💎 VIP функции

<b>⚡ Быстрый старт:</b>
• Напиши мне что угодно - я отвечу!
• Загрузи файл для анализа
• /generate для изображений (VIP)
• Используй /help для списка команд
• Нажми на кнопки меню ниже

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
        'commands_count': user_data['commands_count'] + 1
    })

    help_text = """
📚 <b>СПИСОК КОМАНД</b>

<b>🆕 Новые функции (VIP):</b>
/generate [описание] - Генерация изображений
/vipphoto - Анализ фото (или отправь фото)

<b>📎 Файлы:</b>
Отправь PDF, TXT, DOCX, ZIP - бот извлечет текст и проанализирует

<b>🏠 Основные:</b>
/start - Запуск бота
/help - Эта справка
/info - Информация о боте
/status - Статус системы
/profile - Твой профиль
/uptime - Время работы бота

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
/fixtext [текст] - Корректор текста
/calc [выражение] - Калькулятор
/convert [значение] [из] to [в] - Конвертер
/analyze [url] - Анализатор ссылок
/password [длина] - Генератор паролей
/base64 encode/decode [текст] - Base64 кодировка
/qrcode [текст/url] - Генератор QR-кода

<b>🎲 Развлечения:</b>
/random [min] [max] - Случайное число
/dice - Бросить кубик
/coin - Подбросить монету
/joke - Случайная шутка
/quote - Мудрая цитата
/fact - Интересный факт

<b>📋 Задачи:</b>
/todo add [текст] - Добавить задачу
/todo list - Показать задачи
/todo del [номер] - Удалить задачу

<b>💎 VIP Команды:</b>
/vip - Твой VIP статус
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/generate - Генерация изображений
/vipphoto - Анализ фото

<i>🆕 Все данные сохраняются в PostgreSQL! 💡 Просто напиши мне что-нибудь - я отвечу!</i>
"""

    if is_creator(user_id):
        help_text += """
<b>👑 Команды Создателя:</b>
/grant_vip [id/@username] [срок] - Выдать VIP
/revoke_vip [id/@username] - Забрать VIP
/users - Список пользователей
/broadcast [текст] - Рассылка
/stats - Полная статистика
/backup - Резервная копия
"""

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = """
🤖 <b>AI DISCO BOT</b>

<b>Версия:</b> 2.4
<b>AI Модель:</b> Google Gemini 2.5 Flash
<b>Создатель:</b> @Ernest_Kostevich

<b>🎯 О боте:</b>
Многофункциональный бот с искусственным интеллектом для Telegram. Умеет общаться, помогать, развлекать и многое другое!

<b>⚡ Особенности:</b>
• Контекстный AI-диалог
• Система памяти (PostgreSQL)
• VIP функции
• Напоминания
• Игры и развлечения
• Погода и время
• Корректор текста, калькулятор, конвертер, органайзер задач, анализатор ссылок, генератор паролей, base64, QR-коды
• Генерация изображений (VIP, Stable Diffusion)
• Обработка файлов (PDF, DOCX, TXT, ZIP)
• Анализ изображений (VIP, BLIP + Gemini)

<b>🔒 Приватность:</b>
Все данные хранятся безопасно. Мы не передаём вашу информацию третьим лицам.

<b>💬 Поддержка:</b>
По всем вопросам: @Ernest_Kostevich
"""

    await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = storage.stats
    total_users = len(storage.users)
    vip_users = sum(1 for u in storage.users.values() if u['vip'])

    uptime = datetime.now() - datetime.fromisoformat(stats.get('start_date', datetime.now().isoformat()))
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
<b>🤖 AI:</b> Gemini 2.5 ✓
<b>🗄️ БД:</b> PostgreSQL ✓
<b>🖼️ Генерация:</b> {'Stable Diffusion ✓' if sd_pipeline else 'HF API'}
<b>🔍 Анализ:</b> {'BLIP ✓' if blip_model else 'Недоступно'}
"""

    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)

    profile_text = format_user_info(user)
    profile_text += f"\n📝 <b>Заметок:</b> {len(user['notes'])}\n"
    profile_text += f"📋 <b>Задач:</b> {len(user['todos'])}\n"
    profile_text += f"🧠 <b>Записей в памяти:</b> {len(user['memory'])}\n"

    if storage.is_vip(user_id):
        profile_text += f"⏰ <b>Напоминаний:</b> {len(user['reminders'])}\n"

    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - BOT_START_TIME
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    seconds = uptime.seconds % 60

    uptime_text = f"""
⏱ <b>ВРЕМЯ РАБОТЫ БОТА</b>

🕐 <b>Запущен:</b> {BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S')}
⏰ <b>Работает:</b> {days}д {hours}ч {minutes}м {seconds}с

<b>✅ Статус:</b> Онлайн и стабильно работает!
"""

    await update.message.reply_text(uptime_text, parse_mode=ParseMode.HTML)

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

    await update.message.reply_text(
        "🧹 Контекст диалога очищен! Начнём с чистого листа."
    )

async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action("typing")

        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        # Сохраняем чат в БД
        db_manager.save_chat(user_id, text, response.text)
        
        await update.message.reply_text(
            response.text,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"AI error: {e}")
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
    user['memory'][key] = value
    storage.save_users()

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

    if key in user['memory']:
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

    if not user['memory']:
        await update.message.reply_text("📭 Ваша память пуста.")
        return

    memory_text = "🧠 <b>Ваша память:</b>\n\n"
    for key, value in user['memory'].items():
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

    if key in user['memory']:
        del user['memory'][key]
        storage.save_users()
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

    user['notes'].append(note)
    storage.save_users()

    await update.message.reply_text(
        f"✅ Заметка #{len(user['notes'])} сохранена!\n\n"
        f"📝 {note_text}"
    )

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)

    if not user['notes']:
        await update.message.reply_text("📭 У вас пока нет заметок.")
        return

    notes_text = f"📝 <b>Ваши заметки ({len(user['notes'])}):</b>\n\n"

    for i, note in enumerate(user['notes'], 1):
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
        
        if 1 <= note_num <= len(user['notes']):
            deleted_note = user['notes'].pop(note_num - 1)
            storage.save_users()
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
        'los angeles': 'America/Los_Angeles',
        'beijing': 'Asia/Shanghai',
        'washington': 'America/New_York',
        'shanghai': 'Asia/Shanghai',
        'italy': 'Europe/Rome',
        'france': 'Europe/Paris',
        'rome': 'Europe/Rome'
    }

    tz_name = timezones.get(city, 'Europe/Moscow')

    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        
        time_text = f"""
⏰ <b>Текущее время</b>

📍 <b>Город/Страна:</b> {city.title()}
🕐 <b>Время:</b> {current_time.strftime('%H:%M:%S')}
📅 <b>Дата:</b> {current_time.strftime('%d.%m.%Y')}
🌍 <b>Часовой пояс:</b> {tz_name}
"""
        await update.message.reply_text(time_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Time error: {e}")
        await update.message.reply_text(
            f"❌ Не удалось получить время для '{city}'.\n"
            f"Доступные: Moscow, London, New York, Tokyo, Paris, Berlin, Dubai, Sydney, Los Angeles, Beijing, Washington, Shanghai, Italy, France, Rome"
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
        logger.error(f"Weather error: {e}")
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
        logger.error(f"Translation error: {e}")
        await update.message.reply_text("❌ Ошибка при переводе текста.")

async def fixtext_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /fixtext [текст]\n\n"
            "Пример: /fixtext privet kak dela"
        )
        return

    text = ' '.join(context.args)

    try:
        prompt = f"Исправь орфографию, грамматику и пунктуацию в этом тексте: {text}"
        chat = storage.get_chat_session(update.effective_user.id)
        response = chat.send_message(prompt)
        
        await update.message.reply_text(
            f"📝 <b>Исправленный текст:</b>\n\n{response.text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Fixtext error: {e}")
        await update.message.reply_text("❌ Ошибка при исправлении текста.")

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /calc [выражение]\n\n"
            "Пример: /calc (15 * 3 + 7) / 4"
        )
        return

    expression = ' '.join(context.args)

    try:
        # Безопасный eval с ограниченным globals
        allowed_names = {"__builtins__": None, "abs": abs, "pow": pow, "round": round}
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        
        await update.message.reply_text(
            f"🧮 <b>Результат:</b>\n\n{expression} = <b>{result}</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Calc error: {e}")
        await update.message.reply_text("❌ Ошибка при вычислении выражения. Убедитесь, что оно корректно.")

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 4 or context.args[2].lower() != 'to':
        await update.message.reply_text(
            "❓ Использование: /convert [значение] [из] to [в]\n\n"
            "Пример: /convert 100 USD to EUR\n"
            "Или: /convert 10 km to miles"
        )
        return

    value = context.args[0]
    from_unit = context.args[1]
    to_unit = context.args[3]

    try:
        prompt = f"Конвертируй {value} {from_unit} в {to_unit}. Если это валюта, используй приблизительные текущие курсы."
        chat = storage.get_chat_session(update.effective_user.id)
        response = chat.send_message(prompt)
        
        await update.message.reply_text(
            f"📏 <b>Конвертация:</b>\n\n{response.text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Convert error: {e}")
        await update.message.reply_text("❌ Ошибка при конвертации.")

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
        user['todos'].append(todo)
        storage.save_users()
        await update.message.reply_text(
            f"✅ Задача #{len(user['todos'])} добавлена!\n\n"
            f"📋 {todo_text}"
        )
    elif subcommand == 'list':
        if not user['todos']:
            await update.message.reply_text("📭 У вас нет задач.")
            return
        todos_text = f"📋 <b>Ваши задачи ({len(user['todos'])}):</b>\n\n"
        for i, todo in enumerate(user['todos'], 1):
            created = datetime.fromisoformat(todo['created'])
            todos_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y %H:%M')})\n"
            todos_text += f"{todo['text']}\n\n"
        await update.message.reply_text(todos_text, parse_mode=ParseMode.HTML)
    elif subcommand == 'del':
        if len(context.args) < 2:
            await update.message.reply_text("❓ Укажите номер задачи.")
            return
        try:
            todo_num = int(context.args[1])
            if 1 <= todo_num <= len(user['todos']):
                deleted_todo = user['todos'].pop(todo_num - 1)
                storage.save_users()
                await update.message.reply_text(
                    f"✅ Задача #{todo_num} удалена:\n\n"
                    f"📋 {deleted_todo['text']}"
                )
            else:
                await update.message.reply_text(f"❌ Задача #{todo_num} не найдена.")
        except ValueError:
            await update.message.reply_text("❌ Укажите корректный номер.")
    else:
        await update.message.reply_text("❌ Неизвестная подкоманда. Используйте add, list или del.")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /analyze [url]\n\n"
            "Пример: /analyze https://example.com"
        )
        return

    url = context.args[0]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    await update.message.reply_text(f"❌ Ошибка: статус {resp.status}")
                    return
                html = await resp.text()
                size_kb = len(html) / 1024
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.title.string.strip() if soup.title else 'Нет заголовка'
                desc_tag = soup.find('meta', attrs={'name': 'description'})
                description = desc_tag['content'].strip() if desc_tag else 'Нет описания'

        analyze_text = f"""
🔍 <b>Анализ ссылки:</b> {url}

📝 <b>Заголовок:</b> {title}
📄 <b>Описание:</b> {description}
📏 <b>Размер страницы:</b> {size_kb:.2f} KB
"""
        await update.message.reply_text(analyze_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        await update.message.reply_text("❌ Ошибка при анализе ссылки.")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text("❌ Длина должна быть от 8 до 50 символов.")
            return
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(
            f"🔑 <b>Сгенерированный пароль (длина {length}):</b>\n\n<code>{password}</code>\n\n💡 Скопируйте и сохраните в безопасном месте!",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректную длину (число). Пример: /password 16")

async def base64_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /base64 encode/decode [текст]\n\n"
            "Пример: /base64 encode Hello World"
        )
        return

    mode = context.args[0].lower()
    text = ' '.join(context.args[1:])

    try:
        if mode == 'encode':
            result = base64.b64encode(text.encode('utf-8')).decode('utf-8')
            title = "Закодировано в Base64"
        elif mode == 'decode':
            result = base64.b64decode(text).decode('utf-8')
            title = "Декодировано из Base64"
        else:
            await update.message.reply_text("❌ Режим должен быть encode или decode.")
            return

        await update.message.reply_text(
            f"🔐 <b>{title}:</b>\n\n<code>{result}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Base64 error: {e}")
        await update.message.reply_text("❌ Ошибка при обработке. Убедитесь, что текст корректен для выбранного режима.")

async def qrcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /qrcode [текст или URL]\n\n"
            "Пример: /qrcode https://example.com"
        )
        return

    text = ' '.join(context.args)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?data={urlquote(text)}&size=200x200"

    await update.message.reply_photo(
        photo=qr_url,
        caption=f"🔳 <b>QR-код для:</b> {text}\n\nСканируйте камерой телефона!",
        parse_mode=ParseMode.HTML
    )

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
        f"🎲 Бросаем кубик...\n\n"
        f"{dice_emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(['Орёл', 'Решка'])
    emoji = '🦅' if result == 'Орёл' else '💰'

    await update.message.reply_text(
        f"🪙 Подбрасываем монету...\n\n"
        f"{emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Программист ложится спать. Жена говорит: — Дорогой, закрой окно, на улице холодно! Программист: — И что, если я закрою окно, на улице станет тепло? 😄",
        "— Почему программисты путают Хэллоуин и Рождество? — Потому что 31 OCT = 25 DEC! 🎃🎄",
        "Зачем программисту очки? Чтобы лучше C++! 👓",
        "Искусственный интеллект никогда не заменит человека. Он слишком умный для этого! 🤖",
        "— Сколько программистов нужно, чтобы вкрутить лампочку? — Ни одного, это аппаратная проблема! 💡",
        "Жена программиста просит: — Сходи в магазин, купи батон хлеба, и если будут яйца — возьми десяток. Он приходит с 10 батонами. — Зачем?! — Ну, яйца же были! 🥚",
        "— Что такое рекурсия? — Чтобы понять что такое рекурсия, нужно сначала понять что такое рекурсия… 🔄"
    ]

    joke = random.choice(jokes)
    await update.message.reply_text(f"😄 <b>Шутка дня:</b>\n\n{joke}", parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
        "Инновация отличает лидера от последователя. — Стив Джобс",
        "Программирование — это искусство превращать кофе в код. — Неизвестный автор",
        "Лучший код — это отсутствие кода. — Джефф Этвуд",
        "Сначала сделай это, потом сделай правильно, потом сделай лучше. — Адди Османи",
        "Простота — залог надёжности. — Эдсгер Дейкстра",
        "Любой дурак может написать код, который поймёт компьютер. Хорошие программисты пишут код, который поймут люди. — Мартин Фаулер"
    ]

    quote = random.choice(quotes)
    await update.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{quote}</i>", parse_mode=ParseMode.HTML)

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = [
        "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
        "🐙 У осьминогов три сердца и голубая кровь.",
        "🍯 Мёд — единственный продукт питания, который не портится тысячи лет.",
        "💎 Алмазы формируются на глубине около 150 км под землёй.",
        "🧠 Человеческий мозг потребляет около 20% всей энергии тела.",
        "🌊 95% мирового океана остаются неисследованными.",
        "⚡ Молния в 5 раз горячее поверхности Солнца.",
        "🦈 Акулы существуют дольше, чем деревья — более 400 миллионов лет!"
    ]

    fact = random.choice(facts)
    await update.message.reply_text(f"🔬 <b>Интересный факт:</b>\n\n{fact}", parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)

    if storage.is_vip(user_id):
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n"
        vip_text += "✅ У вас активен VIP статус!\n\n"
        
        if user['vip_until']:
            vip_until = datetime.fromisoformat(user['vip_until'])
            vip_text += f"⏰ <b>Активен до:</b> {vip_until.strftime('%d.%m.%Y %H:%M')}\n\n"
        else:
            vip_text += "⏰ <b>Активен:</b> Навсегда ♾️\n\n"
        
        vip_text += "<b>🎁 Преимущества VIP:</b>\n"
        vip_text += "• ⏰ Система напоминаний\n"
        vip_text += "• 🎯 Приоритетная обработка\n"
        vip_text += "• 🚀 Генерация изображений\n"
        vip_text += "• 🔍 Анализ изображений\n"
        vip_text += "• 💬 Увеличенный контекст AI\n"
    else:
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n"
        vip_text += "❌ У вас нет VIP статуса.\n\n"
        vip_text += "Свяжитесь с @Ernest_Kostevich для получения VIP."

    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Эта команда доступна только VIP пользователям.\n"
            "Свяжитесь с @Ernest_Kostevich для получения VIP."
        )
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
        
        user['reminders'].append(reminder)
        storage.save_users()
        
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=remind_time,
            args=[context.bot, user_id, text]
        )
        
        await update.message.reply_text(
            f"⏰ Напоминание создано!\n\n"
            f"📝 {text}\n"
            f"🕐 Напомню через {minutes} минут ({remind_time.strftime('%H:%M')})"
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректное количество минут.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Эта команда доступна только VIP пользователям."
        )
        return

    user = storage.get_user(user_id)

    if not user['reminders']:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")
        return

    reminders_text = f"⏰ <b>Ваши напоминания ({len(user['reminders'])}):</b>\n\n"

    for i, reminder in enumerate(user['reminders'], 1):
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
        user['reminders'] = [r for r in user['reminders'] if r['text'] != text]
        storage.save_users()
    except Exception as e:
        logger.error(f"Reminder error: {e}")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /grant_vip [id/@username] [срок]\n\n"
            "Сроки: week, month, year, forever\n"
            "Пример: /grant_vip @username month\n"
            "Пример: /grant_vip 123456789 forever"
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
            await update.message.reply_text("❌ Неверный срок. Используйте: week, month, year, forever")
            return
        
        user = storage.get_user(target_id)
        user['vip'] = True
        
        if durations[duration]:
            vip_until = datetime.now() + durations[duration]
            user['vip_until'] = vip_until.isoformat()
            duration_text = f"до {vip_until.strftime('%d.%m.%Y')}"
        else:
            user['vip_until'] = None
            duration_text = "навсегда"
        
        storage.save_users()
        
        username_info = f"@{user['username']}" if user.get('username') else ""
        
        await update.message.reply_text(
            f"✅ VIP статус выдан!\n\n"
            f"👤 {user.get('first_name', 'Unknown')} {username_info}\n"
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
        logger.error(f"Grant VIP error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /revoke_vip [id/@username]\n\n"
            "Пример: /revoke_vip @username\n"
            "Пример: /revoke_vip 123456789"
        )
        return

    try:
        identifier = context.args[0]
        target_id = storage.get_user_id_by_identifier(identifier)
        
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
            return
        
        user = storage.get_user(target_id)
        user['vip'] = False
        user['vip_until'] = None
        storage.save_users()
        
        username_info = f"@{user['username']}" if user.get('username') else ""
        
        await update.message.reply_text(
            f"✅ VIP статус отозван!\n\n"
            f"👤 {user.get('first_name', 'Unknown')} {username_info}\n"
            f"🆔 ID: <code>{target_id}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Revoke VIP error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    users_text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ ({len(storage.users)}):</b>\n\n"

    for user_id, user in list(storage.users.items())[:20]:
        vip_badge = "💎" if user['vip'] else ""
        users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"
        if user.get('username'):
            users_text += f"   @{user['username']}\n"

    if len(storage.users) > 20:
        users_text += f"\n<i>... и ещё {len(storage.users) - 20} пользователей</i>"

    await update.message.reply_text(users_text, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /broadcast [текст сообщения]\n\n"
            "Пример: /broadcast Привет всем!"
        )
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
            logger.error(f"Broadcast error for {user_id}: {e}")

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
    vip_users = sum(1 for u in storage.users.values() if u['vip'])
    active_users = sum(1 for u in storage.users.values() 
                      if (datetime.now() - datetime.fromisoformat(u['last_active'])).days < 7)

    total_notes = sum(len(u['notes']) for u in storage.users.values())
    total_todos = sum(len(u['todos']) for u in storage.users.values())
    total_memory = sum(len(u['memory']) for u in storage.users.values())

    stats_text = f"""
📊 <b>ПОЛНАЯ СТАТИСТИКА</b>

<b>👥 Пользователи:</b>
• Всего: {total_users}
• VIP: {vip_users}
• Активных (7 дней): {active_users}

<b>📈 Активность:</b>
• Сообщений: {stats.get('total_messages', 0)}
• Команд: {stats.get('total_commands', 0)}
• AI запросов: {stats.get('ai_requests', 0)}

<b>📝 Данные:</b>
• Заметок: {total_notes}
• Задач: {total_todos}
• Записей в памяти: {total_memory}

<b>📅 Запущен:</b> {stats.get('start_date', 'N/A')[:10]}
"""

    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return

    try:
        backup_data = {
            'users': storage.users,
            'stats': storage.stats,
            'backup_date': datetime.now().isoformat()
        }
        
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        await update.message.reply_document(
            document=open(backup_filename, 'rb'),
            caption=f"✅ Резервная копия создана!\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        os.remove(backup_filename)
        
    except Exception as e:
        logger.error(f"Backup error: {e}")
        await update.message.reply_text("❌ Ошибка при создании резервной копии.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text

    user = storage.get_user(user_id)
    storage.update_user(user_id, {
        'messages_count': user['messages_count'] + 1,
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()

    # Новые обработчики для файлов и фото
    if update.message.document:
        await handle_document(update, context)
        return
    if update.message.photo and storage.is_vip(user_id):
        await handle_photo(update, context)
        return

    if text in ["💬 AI Чат", "📝 Заметки", "🌍 Погода", "⏰ Время", "🎲 Развлечения", "ℹ️ Инфо", "💎 VIP Меню", "👑 Админ Панель", "🖼️ Генерация", "📎 Файлы", "🔍 Анализ фото"]:
        await handle_menu_button(update, context, text)
        return

    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str):
    user_id = update.effective_user.id

    if button == "🖼️ Генерация":
        if storage.is_vip(user_id):
            await update.message.reply_text(
                "🖼️ <b>Генерация изображений (VIP)</b>\n\n"
                "Используй: /generate [описание]\n"
                "Пример: /generate футуристический город ночью",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("💎 Генерация изображений доступна только VIP-пользователям.")
    
    elif button == "📎 Файлы":
        await update.message.reply_text(
            "📎 <b>Обработка файлов</b>\n\n"
            "Поддерживаемые форматы:\n"
            "• PDF - извлечение текста\n"
            "• DOCX - чтение документов\n"
            "• TXT - текстовые файлы\n"
            "• ZIP - архивы с текстом\n\n"
            "💡 Просто отправь файл - я проанализирую!",
            parse_mode=ParseMode.HTML
        )
    
    elif button == "🔍 Анализ фото":
        if storage.is_vip(user_id):
            await update.message.reply_text(
                "🔍 <b>Анализ изображений (VIP)</b>\n\n"
                "Отправь фото - я опишу, что на нем изображено (BLIP + Gemini).\n"
                "Или используй /vipphoto",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("💎 Анализ изображений доступен только VIP-пользователям.")

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
             InlineKeyboardButton("💭 Цитата", callback_data="game_quote")],
            [InlineKeyboardButton("🔬 Факт", callback_data="game_fact")]
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

    elif button == "👑 Админ Панель":
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
        
        if not user['notes']:
            await query.message.reply_text("📭 У вас пока нет заметок.")
            return
        
        notes_text = f"📝 <b>Ваши заметки ({len(user['notes'])}):</b>\n\n"
        
        for i, note in enumerate(user['notes'], 1):
            created = datetime.fromisoformat(note['created'])
            notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y %H:%M')})\n"
            notes_text += f"{note['text']}\n\n"
        
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
            "— Почему программисты путают Хэллоуин и Рождество? — Потому что 31 OCT = 25 DEC! 🎃🎄",
            "Зачем программисту очки? Чтобы лучше C++! 👓",
            "Искусственный интеллект никогда не заменит человека. Он слишком умный для этого! 🤖",
            "— Сколько программистов нужно, чтобы вкрутить лампочку? — Ни одного, это аппаратная проблема! 💡"
        ]
        joke = random.choice(jokes)
        await query.message.reply_text(f"😄 <b>Шутка:</b>\n\n{joke}", parse_mode=ParseMode.HTML)

    elif data == "game_quote":
        quotes = [
            "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
            "Инновация отличает лидера от последователя. — Стив Джобс",
            "Программирование — это искусство превращать кофе в код. — Неизвестный автор",
            "Лучший код — это отсутствие кода. — Джефф Этвуд"
        ]
        quote = random.choice(quotes)
        await query.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{quote}</i>", parse_mode=ParseMode.HTML)

    elif data == "game_fact":
        facts = [
            "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
            "🐙 У осьминогов три сердца и голубая кровь.",
            "🍯 Мёд — единственный продукт питания, который не портится тысячи лет.",
            "💎 Алмазы формируются на глубине около 150 км под землёй."
        ]
        fact = random.choice(facts)
        await query.message.reply_text(f"🔬 <b>Факт:</b>\n\n{fact}", parse_mode=ParseMode.HTML)

    elif data == "vip_reminders":
        user_id = query.from_user.id
        user = storage.get_user(user_id)
        
        if not user['reminders']:
            await query.message.reply_text("📭 У вас нет активных напоминаний.")
            return
        
        reminders_text = f"⏰ <b>Ваши напоминания ({len(user['reminders'])}):</b>\n\n"
        
        for i, reminder in enumerate(user['reminders'], 1):
            remind_time = datetime.fromisoformat(reminder['time'])
            reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n"
            reminders_text += f"📝 {reminder['text']}\n\n"
        
        await query.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)

    elif data == "vip_stats":
        user_id = query.from_user.id
        user = storage.get_user(user_id)
        
        profile_text = format_user_info(user)
        profile_text += f"\n📝 <b>Заметок:</b> {len(user['notes'])}\n"
        profile_text += f"📋 <b>Задач:</b> {len(user['todos'])}\n"
        profile_text += f"🧠 <b>Записей в памяти:</b> {len(user['memory'])}\n"
        profile_text += f"⏰ <b>Напоминаний:</b> {len(user['reminders'])}\n"
        
        await query.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

    elif data == "admin_users":
        if not is_creator(query.from_user.id):
            await query.message.reply_text("❌ Доступ запрещён.")
            return
        
        users_text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ ({len(storage.users)}):</b>\n\n"
        
        for user_id, user in list(storage.users.items())[:20]:
            vip_badge = "💎" if user['vip'] else ""
            users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"
            if user.get('username'):
                users_text += f"   @{user['username']}\n"
        
        if len(storage.users) > 20:
            users_text += f"\n<i>... и ещё {len(storage.users) - 20} пользователей</i>"
        
        await query.message.reply_text(users_text, parse_mode=ParseMode.HTML)

    elif data == "admin_stats":
        if not is_creator(query.from_user.id):
            await query.message.reply_text("❌ Доступ запрещён.")
            return
        
        stats = storage.stats
        total_users = len(storage.users)
        vip_users = sum(1 for u in storage.users.values() if u['vip'])
        active_users = sum(1 for u in storage.users.values() 
                          if (datetime.now() - datetime.fromisoformat(u['last_active'])).days < 7)
        
        total_notes = sum(len(u['notes']) for u in storage.users.values())
        total_todos = sum(len(u['todos']) for u in storage.users.values())
        total_memory = sum(len(u['memory']) for u in storage.users.values())
        
        stats_text = f"""
📊 <b>ПОЛНАЯ СТАТИСТИКА</b>

<b>👥 Пользователи:</b>
• Всего: {total_users}
• VIP: {vip_users}
• Активных (7 дней): {active_users}

<b>📈 Активность:</b>
• Сообщений: {stats.get('total_messages', 0)}
• Команд: {stats.get('total_commands', 0)}
• AI запросов: {stats.get('ai_requests', 0)}

<b>📝 Данные:</b>
• Заметок: {total_notes}
• Задач: {total_todos}
• Записей в памяти: {total_memory}

<b>📅 Запущен:</b> {stats.get('start_date', 'N/A')[:10]}
"""

        await query.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

    elif data == "admin_broadcast":
        if not is_creator(query.from_user.id):
            await query.message.reply_text("❌ Доступ запрещён.")
            return
        
        await query.message.reply_text(
            "📢 <b>Рассылка</b>\n\n"
            "Используй: /broadcast [текст]\n"
            "Пример: /broadcast Привет всем!",
            parse_mode=ParseMode.HTML
        )

def main():
    if not BOT_TOKEN or not GEMINI_API_KEY:
        logger.error("Error: BOT_TOKEN or GEMINI_API_KEY not set!")
        return

    # Тестирование подключения к БД
    try:
        with db_manager.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL подключен успешно!")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return

    # Запуск Flask в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask server started on port {PORT}")

    # Настройка keep-alive пингов каждые 5 минут
    if APP_URL:
        scheduler.add_job(keep_awake, 'interval', minutes=5)
        logger.info("Keep-alive scheduler configured")

    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация всех handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("uptime", uptime_command))

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
    application.add_handler(CommandHandler("fixtext", fixtext_command))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("convert", convert_command))
    application.add_handler(CommandHandler("todo", todo_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("password", password_command))
    application.add_handler(CommandHandler("base64", base64_command))
    application.add_handler(CommandHandler("qrcode", qrcode_command))

    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("fact", fact_command))

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
    application.add_handler(CommandHandler("backup", backup_command))

    # Обработчики сообщений (текст, файлы, фото)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск scheduler
    scheduler.start()

    logger.info("Bot started successfully!")
    logger.info("=" * 50)
    logger.info("AI DISCO BOT is now running with new features!")
    logger.info("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
