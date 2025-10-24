#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import random
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import pytz
import requests
import io
from urllib.parse import quote as urlquote
import base64
import mimetypes
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
# from pydub import AudioSegment # Зависимость pydub не используется, так как Gemini работает с ogg/mp3 через upload_file

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Переменные окружения ---
# Убедитесь, что эти переменные установлены в вашем окружении (.env файле)
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

CREATOR_USERNAME = os.getenv('CREATOR_USERNAME', "Ernest_Kostevich")
CREATOR_ID = None
BOT_START_TIME = datetime.now()

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка переменных окружения
if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ BOT_TOKEN или GEMINI_API_KEY не установлены!")
    raise ValueError("Required environment variables missing")

# --- Настройка Gemini ---
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

# Модель Gemini 2.5 Flash (для чата, транскрипции, утилит)
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="Ты — AI DISCO BOT, многофункциональный, очень умный и вежливый ассистент, основанный на Gemini 2.5. Всегда отвечай на том языке, на котором к тебе обращаются, используя дружелюбный и вовлекающий тон. Твои ответы должны быть структурированы, по возможности разделены на абзацы и никогда не превышать 4000 символов (ограничение Telegram). Твой создатель — @Ernest_Kostevich. Включай в ответы эмодзи, где это уместно."
)

# Модель для Vision (VIP)
vision_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash', # Используем flash для vision
    generation_config=generation_config,
    safety_settings=safety_settings
)

# --- База данных PostgreSQL / ORM ---
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
        engine = None
        Session = None
else:
    logger.warning("⚠️ БД не настроена. Используется JSON.")

# --- Локальное хранилище (Fallback для JSON) ---
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
            logger.warning(f"Ошибка загрузки users.json: {e}")
            return {}

    def save_users(self):
        if engine:
            return
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            self.update_username_mapping()
        except Exception as e:
            logger.warning(f"Ошибка сохранения users.json: {e}")

    def load_stats(self) -> Dict:
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        return data
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0, 'start_date': datetime.now().isoformat()}
        except Exception as e:
            logger.warning(f"Ошибка загрузки statistics.json: {e}")
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0, 'start_date': datetime.now().isoformat()}

    def save_stats(self):
        if engine:
            session = Session()
            try:
                session.merge(Statistics(key='global', value=self.stats, updated_at=datetime.now()))
                session.commit()
            except Exception as e:
                logger.warning(f"Ошибка сохранения stats в БД: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            try:
                with open(self.stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self.stats, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Ошибка сохранения statistics.json: {e}")

    def get_stats_from_db(self) -> Dict:
        if not engine:
            return self.load_stats()
        session = Session()
        try:
            stat = session.query(Statistics).filter_by(key='global').first()
            if stat:
                return stat.value
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0, 'start_date': datetime.now().isoformat()}
        except Exception as e:
            logger.warning(f"Ошибка загрузки stats из БД: {e}")
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
                user = session.query(User).filter(User.username.ilike(f"%{identifier}%")).first()
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
                    'id': user_id, 'username': '', 'first_name': '', 'vip': False, 'vip_until': None,
                    'notes': [], 'todos': [], 'memory': {}, 'reminders': [],
                    'registered': datetime.now().isoformat(), 'last_active': datetime.now().isoformat(),
                    'messages_count': 0, 'commands_count': 0
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
                logger.warning(f"Ошибка обновления пользователя в БД: {e}")
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
                return {u.id: {'id': u.id, 'username': u.username, 'first_name': u.first_name, 'vip': u.vip} for u in users}
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
            logger.warning(f"Ошибка сохранения чата: {e}")
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
        keyboard.insert(0, [KeyboardButton("💎 VIP Меню"), KeyboardButton("🖼️ Генерация")])
    if is_creator(user_id):
        keyboard.append([KeyboardButton("👑 Админ Панель")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def send_long_message(message: Message, text: str):
    if len(text) <= 4000:
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.5)

# --- Gemini API (Image/Vision/Audio) ---

def save_binary_file(file_name, data):
    with open(file_name, "wb") as f:
        f.write(data)
    logger.info(f"File saved to: {file_name}")

async def generate_image_gemini(prompt: str) -> Optional[str]:
    """Генерация изображения с использованием Gemini 2.5 Flash Image."""
    try:
        # Ваш оригинальный код использует Gemini 2.5 Flash Image,
        # который на момент написания может быть экспериментальным или требовать специфических настроек.
        # Сохраняем логику, используя API, предназначенный для потоковой генерации медиа
        client = genai.GenerativeModel('gemini-2.5-flash-image') 
        contents = [
            genai.Content(
                role="user",
                parts=[
                    genai.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = genai.GenerateContentConfig(
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
        )

        file_index = 0
        file_path = None
        
        # Потоковая генерация и сохранение
        for chunk in client.generate_content_stream(
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
            
            # Поиск части с изображением
            if chunk.candidates[0].content.parts[0].inline_data and chunk.candidates[0].content.parts[0].inline_data.data:
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                data_buffer = inline_data.data
                file_extension = mimetypes.guess_extension(inline_data.mime_type)
                file_path = f"generated_image_{file_index}{file_extension}"
                save_binary_file(file_path, data_buffer)
                file_index += 1
            else:
                logger.info(chunk.text)
                
        return file_path
    except Exception as e:
        logger.warning(f"Ошибка генерации изображения с Gemini: {e}")
        return None

async def analyze_image_with_gemini(image_bytes: bytes, prompt: str = "Опиши подробно что изображено") -> str:
    """Анализ изображения."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = vision_model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка анализа: {str(e)}"

async def transcribe_audio_with_gemini(audio_bytes: bytes) -> str:
    """Транскрипция аудио."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        # Загрузка файла в Gemini и транскрипция
        uploaded_file = genai.upload_file(path=temp_path, mime_type="audio/ogg")
        response = model.generate_content(["Транскрибируй это аудио:", uploaded_file])
        
        # Удаление временного файла
        os.remove(temp_path)
        
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка транскрипции аудио: {e}")
        return f"❌ Ошибка транскрипции: {str(e)}"

async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    """Извлечение текста из документов PDF, DOCX, TXT."""
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
        logger.warning(f"Ошибка извлечения текста: {e}")
        return f"❌ Ошибка: {str(e)}"

# --- Команды и обработчики ---

async def process_ai_message(update: Update, text: str, user_id: int):
    """Общий обработчик AI-сообщений (чат)."""
    try:
        await update.message.chat.send_action("typing")
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        
        # Обновление статистики
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response.text)
        
        await send_long_message(update.message, response.text)
    except Exception as e:
        logger.error(f"AI: {e}")
        await update.message.reply_text("😔 Произошла ошибка при обработке запроса AI.")

# /start, /help, /info, /status, /profile, /uptime, /vip (В ОСНОВНОМ ИЗ СНИППЕТА)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {'username': user.username or '', 'first_name': user.first_name or '', 'commands_count': user_data.get('commands_count', 0) + 1})
    welcome_text = f"""🤖 <b>AI DISCO BOT</b>

Привет, {user.first_name}! Я бот на <b>Gemini 2.5 Flash</b>.

<b>🎯 Возможности:</b>
💬 AI-чат с контекстом
📝 Заметки и задачи
🌍 Погода и время
🎲 Развлечения
📎 Анализ файлов (VIP)
🔍 Анализ изображений (VIP)
🖼️ Генерация изображений (VIP)

<b>⚡ Команды:</b>
/help - Все команды
/vip - Статус VIP

<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}"""
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id))

# ... (Остальные команды /help, /info, /status, /profile, /uptime, /vip, /note, /delnote, /notes, /memory*, /todo* взяты из вашего кода) ...

# --- Утилиты и Развлечения (Дополнение) ---

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    city = ' '.join(context.args) if context.args else 'Moscow'
    
    timezones = {
        'москва': 'Europe/Moscow', 'moscow': 'Europe/Moscow',
        'лондон': 'Europe/London', 'london': 'Europe/London',
        'нью йорк': 'America/New_York', 'new york': 'America/New_York',
        'токио': 'Asia/Tokyo', 'tokyo': 'Asia/Tokyo',
        'париж': 'Europe/Paris', 'paris': 'Europe/Paris',
        'берлин': 'Europe/Berlin', 'berlin': 'Europe/Berlin',
        'дубай': 'Asia/Dubai', 'dubai': 'Asia/Dubai',
        'сидней': 'Australia/Sydney', 'sydney': 'Australia/Sydney',
        'киев': 'Europe/Kiev', 'kiev': 'Europe/Kiev',
        'варшава': 'Europe/Warsaw', 'warsaw': 'Europe/Warsaw',
        'астана': 'Asia/Almaty', 'astana': 'Asia/Almaty',
    }
    
    city_lower = city.lower()
    tz_name = timezones.get(city_lower)
            
    try:
        if not tz_name:
            # Попытка найти часовой пояс через Gemini
            await update.message.chat.send_action("typing")
            response = model.generate_content(f"Какой часовой пояс для города '{city}'? Ответь только названием часового пояса (например, 'Europe/Moscow'). Если не уверен, ответь 'Europe/Moscow'.")
            
            # Очистка и проверка ответа
            tz_name = response.text.strip().split('\n')[0].replace('`', '').replace('"', '').strip()
            if not tz_name or '/' not in tz_name:
                 tz_name = 'Europe/Moscow'
        
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        
        await update.message.reply_text(
            f"🕐 <b>Время в {city.title()}:</b>\n\n"
            f"Дата: {now.strftime('%d.%m.%Y')}\n"
            f"Время: {now.strftime('%H:%M:%S')}\n"
            f"Часовой пояс: <code>{tz_name}</code>",
            parse_mode=ParseMode.HTML
        )
    except pytz.exceptions.UnknownTimeZoneError:
        await update.message.reply_text(f"❌ Часовой пояс для '{city}' не найден. Попробуйте другой город.")
    except Exception as e:
        logger.error(f"Time command error: {e}")
        await update.message.reply_text("😔 Произошла ошибка при получении времени.")

async def get_weather(city: str) -> Optional[str]:
    # Используем aiohttp и requests + BeautifulSoup для парсинга Google, который может быть нестабилен
    url = f"https://www.google.com/search?q=погода+{urlquote(city)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return "❌ Ошибка HTTP"
                html = await resp.text()
        
        soup = BeautifulSoup(html, 'html.parser')
        temp = soup.find('span', {'id': 'wob_tm'})
        status = soup.find('span', {'id': 'wob_dc'})
        
        if temp and status:
            return f"🌡️ <b>{temp.text}°C</b>, {status.text.capitalize()}"
        else:
            # Fallback на Gemini, если парсинг не удался
            response = model.generate_content(f"Какая сейчас погода и температура в городе {city}? Ответь кратко (например: +15°C, солнечно).")
            return response.text
            
    except Exception as e:
        logger.error(f"Weather scraping/AI error: {e}")
        return "❌ Не удалось получить данные о погоде."

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    if not context.args:
        await update.message.reply_text("❓ /weather [город]\n\nПример: /weather Лондон")
        return
    city = ' '.join(context.args)
    await update.message.reply_text(f"🌍 Ищу погоду в {city}...")
    
    weather_info = await get_weather(city)
    
    if weather_info and not weather_info.startswith("❌"):
        await update.message.reply_text(f"☀️ <b>Погода в {city.title()}:</b>\n\n{weather_info}", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"😔 {weather_info if weather_info else 'Не удалось получить данные о погоде. Попробуйте позже.'}")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    if len(context.args) < 2:
        await update.message.reply_text("❓ /translate [код языка] [текст]\n\nПример: /translate en Привет мир")
        return
    
    target_lang = context.args[0]
    text_to_translate = ' '.join(context.args[1:])
    
    if len(text_to_translate) > 4000:
        await update.message.reply_text("❌ Слишком длинный текст (макс. 4000 символов).")
        return

    await update.message.chat.send_action("typing")
    try:
        prompt = f"Переведи следующий текст на язык с кодом '{target_lang}'. Верни только переведенный текст без лишних слов:\n\n{text_to_translate}"
        response = model.generate_content(prompt)
        translated_text = response.text.strip()
        
        await update.message.reply_text(
            f"🌐 <b>Перевод (на {target_lang}):</b>\n\n"
            f"<code>{translated_text}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Translate command error: {e}")
        await update.message.reply_text("😔 Произошла ошибка при переводе.")

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    if not context.args:
        await update.message.reply_text("❓ /calc [выражение]\n\nПример: /calc 2*5 + 10")
        return
    
    expression = ''.join(context.args).replace('^', '**')
    try:
        # Безопасное использование eval для простых мат. выражений
        result = eval(expression, {"__builtins__": None}, {"sqrt": lambda x: x**0.5, "pi": 3.1415926535, "e": 2.7182818284})
        await update.message.reply_text(f"🧮 <b>Результат:</b>\n\n<code>{expression} = {result}</code>", parse_mode=ParseMode.HTML)
    except (NameError, TypeError, SyntaxError, ZeroDivisionError) as e:
        await update.message.reply_text(f"❌ Некорректное выражение или ошибка вычисления: {e}")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    length = 12
    if context.args:
        try:
            length = int(context.args[0])
            if length < 8 or length > 50:
                await update.message.reply_text("❌ Длина пароля должна быть от 8 до 50 символов.")
                return
        except ValueError:
            await update.message.reply_text("❌ Укажите число.")
            return

    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-="
    password = ''.join(random.choice(chars) for _ in range(length))
    
    await update.message.reply_text(f"🔑 <b>Сгенерированный пароль ({length} символов):</b>\n\n<code>{password}</code>", parse_mode=ParseMode.HTML)

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    min_val, max_val = 1, 100
    try:
        if len(context.args) == 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        elif len(context.args) == 1:
            max_val = int(context.args[0])

        if min_val > max_val: min_val, max_val = max_val, min_val
            
        result = random.randint(min_val, max_val)
        await update.message.reply_text(f"🎲 Случайное число в диапазоне <b>[{min_val} - {max_val}]</b>:\n\n<b>{result}</b>", parse_mode=ParseMode.HTML)
        
    except ValueError:
        await update.message.reply_text("❌ Некорректный формат. Используйте: /random [min] [max] (например, /random 1 10).")

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    await update.message.reply_dice(emoji="🎲")

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    result = random.choice(["Орёл 🦅", "Решка 🪙"])
    await update.message.reply_text(f"🪙 Монета подброшена:\n\n<b>{result}</b>", parse_mode=ParseMode.HTML)
    
async def ai_content_command(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    user_data = storage.get_user(update.effective_user.id)
    storage.update_user(update.effective_user.id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    await update.message.chat.send_action("typing")
    try:
        response = model.generate_content(prompt)
        await send_long_message(update.message, response.text)
    except Exception as e:
        logger.error(f"AI content error: {e}")
        await update.message.reply_text("😔 Ошибка генерации контента.")

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ai_content_command(update, context, "Придумай и расскажи мне короткую, смешную шутку.")

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ai_content_command(update, context, "Сгенерируй одну мотивирующую или вдохновляющую цитату известного человека.")

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ai_content_command(update, context, "Напиши один интересный и малоизвестный факт о науке, истории или природе.")
    
# --- Система Напоминаний (VIP) ---

async def send_reminder(user_id: int, reminder_text: str, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет напоминание пользователю."""
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ <b>НАПОМИНАНИЕ:</b>\n\n{reminder_text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to send reminder to {user_id}: {e}")

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и отправляет просроченные напоминания."""
    now = datetime.now()
    all_users = storage.get_all_users()
    
    for user_id in all_users.keys():
        user = storage.get_user(user_id)
        reminders: List[Dict] = user.get('reminders', [])
        reminders_to_keep: List[Dict] = []
        
        for reminder in reminders:
            try:
                remind_time = datetime.fromisoformat(reminder['time'])
                if now >= remind_time:
                    # Добавляем задачу на немедленную отправку
                    scheduler.add_job(
                        send_reminder, 
                        'date', 
                        run_date=datetime.now() + timedelta(seconds=1), 
                        args=[user_id, reminder['text'], context]
                    )
                else:
                    reminders_to_keep.append(reminder)
            except Exception as e:
                logger.error(f"Reminder processing error for user {user_id}: {e}")
        
        if len(reminders) != len(reminders_to_keep):
            storage.update_user(user_id, {'reminders': reminders_to_keep})

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Напоминания доступны только VIP-пользователям.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❓ /remind [минуты/ЧЧ:ММ/дд.мм.гггг ЧЧ:ММ] [текст]\n\nПримеры:\n/remind 30 Позвонить другу\n/remind 18:00 Посмотреть новости\n/remind 01.01.2026 10:00 Новый год")
        return

    time_str = context.args[0]
    reminder_text = ' '.join(context.args[1:])
    now = datetime.now()
    remind_time = None
    
    try:
        if ':' not in time_str and '.' not in time_str:
            # Смещение в минутах
            minutes = int(time_str)
            remind_time = now + timedelta(minutes=minutes)
        elif len(context.args) >= 3 and '.' in context.args[0] and ':' in context.args[1]:
            # Дата и время (дд.мм.гггг ЧЧ:ММ)
            datetime_str = f"{context.args[0]} {context.args[1]}"
            reminder_text = ' '.join(context.args[2:])
            remind_time = datetime.strptime(datetime_str, '%d.%m.%Y %H:%M')
        elif ':' in time_str:
            # Только время (ЧЧ:ММ) - сегодня или завтра
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            remind_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if remind_time <= now:
                remind_time += timedelta(days=1)
                
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Некорректный формат времени/даты.")
        return

    if remind_time and remind_time > now:
        user = storage.get_user(user_id)
        reminders = user.get('reminders', [])
        reminders.append({'time': remind_time.isoformat(), 'text': reminder_text})
        storage.update_user(user_id, {'reminders': reminders})
        
        await update.message.reply_text(f"✅ Напоминание установлено на: <b>{remind_time.strftime('%d.%m.%Y %H:%M')}</b>\n\n📝 {reminder_text}", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ Указанное время уже прошло.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    reminders = user.get('reminders', [])
    
    if not reminders:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")
        return
        
    reminders_text = "⏰ <b>Активные напоминания:</b>\n\n"
    
    for i, reminder in enumerate(reminders, 1):
        remind_time = datetime.fromisoformat(reminder['time'])
        reminders_text += f"<b>#{i}</b> ({remind_time.strftime('%d.%m.%Y %H:%M')})\n{reminder['text']}\n\n"
        
    await update.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)
    
# --- Админ Команды ---

async def admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен.")
        return False
    return True

async def get_target_id(identifier: str, update: Update) -> Optional[int]:
    user_id = storage.get_user_id_by_identifier(identifier)
    if user_id is None:
        await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
    return user_id

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if len(context.args) < 2:
        await update.message.reply_text("❓ /grant_vip [id/@username] [срок (week/month/year/forever)]")
        return
        
    target_identifier = context.args[0]
    duration_str = context.args[1].lower()
    
    target_id = await get_target_id(target_identifier, update)
    if target_id is None: return

    duration_map = {
        'week': timedelta(weeks=1),
        'month': timedelta(days=30),
        'year': timedelta(days=365),
    }

    if duration_str == 'forever':
        vip_until = None
        message = "навсегда ♾️"
    elif duration_str in duration_map:
        user_data = storage.get_user(target_id)
        current_vip_until = datetime.fromisoformat(user_data.get('vip_until')) if user_data.get('vip_until') else datetime.now()
        
        if current_vip_until < datetime.now():
            current_vip_until = datetime.now()
            
        vip_until = current_vip_until + duration_map[duration_str]
        message = f"до {vip_until.strftime('%d.%m.%Y')}"
    else:
        await update.message.reply_text("❌ Некорректный срок. Используйте: week/month/year/forever.")
        return

    storage.update_user(target_id, {'vip': True, 'vip_until': vip_until.isoformat() if vip_until else None})
    await update.message.reply_text(f"✅ Пользователю {target_identifier} выдан VIP-статус {message}.")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args:
        await update.message.reply_text("❓ /revoke_vip [id/@username]")
        return

    target_identifier = context.args[0]
    target_id = await get_target_id(target_identifier, update)
    if target_id is None: return

    storage.update_user(target_id, {'vip': False, 'vip_until': None})
    await update.message.reply_text(f"✅ VIP-статус пользователя {target_identifier} отозван.")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    all_users = storage.get_all_users()
    total = len(all_users)
    vip_count = sum(1 for u in all_users.values() if u.get('vip', False))

    users_list = "👥 <b>ПОЛЬЗОВАТЕЛИ:</b>\n\n"
    # Показываем только первых 30, чтобы не превышать лимит сообщения
    for user_data in sorted(list(all_users.values()), key=lambda x: x['id'])[:30]: 
        vip_status = "💎" if user_data.get('vip') else ""
        username = f"@{user_data.get('username')}" if user_data.get('username') else "Нет ника"
        users_list += f"<code>{user_data['id']}</code> - {user_data.get('first_name')} {vip_status} ({username})\n"

    users_list += f"\n... и еще {total - 30} пользователей." if total > 30 else ""
    users_list += f"\n\n<b>Всего:</b> {total} | <b>VIP:</b> {vip_count}"
    
    await update.message.reply_text(users_list, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args:
        await update.message.reply_text("❓ /broadcast [текст]")
        return

    message = ' '.join(context.args)
    all_users = storage.get_all_users()
    sent_count = 0
    
    await update.message.reply_text(f"📢 Запускаю рассылку для {len(all_users)} пользователей...")

    for user_id in all_users.keys():
        try:
            await context.bot.send_message(user_id, message, parse_mode=ParseMode.HTML)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ Рассылка завершена. Успешно отправлено {sent_count} из {len(all_users)} сообщений.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    stats = storage.stats
    all_users = storage.get_all_users()
    uptime = datetime.now() - BOT_START_TIME

    total_messages = stats.get('total_messages', 0)
    total_commands = stats.get('total_commands', 0)
    ai_requests = stats.get('ai_requests', 0)
    
    # Сбор данных по юзерам
    active_users = sum(1 for u in all_users.values() if datetime.now() - datetime.fromisoformat(storage.get_user(u['id']).get('last_active')) < timedelta(days=7))
    
    stats_text = f"""📈 <b>ПОЛНАЯ СТАТИСТИКА</b>

<b>⏱ Время работы:</b>
• Запущен: {BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S')}
• Работает: {uptime.days}д {uptime.seconds // 3600}ч {(uptime.seconds % 3600) // 60}м

<b>👥 Пользователи:</b>
• Всего: {len(all_users)}
• Активных (7д): {active_users}
• VIP: {sum(1 for u in all_users.values() if u.get('vip', False))}

<b>📊 Активность:</b>
• Сообщений (TEXT): {total_messages}
• Команд: {total_commands}
• AI Запросов: {ai_requests}

<b>🗄️ Хранилище:</b>
• Тип БД: {'PostgreSQL' if engine else 'Local JSON'}
• Пользователей в БД: {len(all_users)} (для JSON) / {len(all_users)} (для PG - примерное)"""

    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return

    if not engine:
        try:
            storage.save_users()
            storage.save_stats()
            # Отправка файлов как документы
            with open('users.json', 'rb') as u_file, open('statistics.json', 'rb') as s_file:
                await update.message.reply_document(
                    document=u_file, 
                    filename=f"users_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    caption="✅ Резервная копия users.json."
                )
                await update.message.reply_document(
                    document=s_file, 
                    filename=f"stats_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    caption="✅ Резервная копия statistics.json."
                )
        except Exception as e:
            logger.error(f"Backup error: {e}")
            await update.message.reply_text(f"❌ Ошибка бэкапа: {e}")
    else:
        await update.message.reply_text("✅ БД PostgreSQL настроена. Резервное копирование должно выполняться на уровне сервера БД.")

# --- Обработка входящих сообщений и колбэков ---

async def handle_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎲 Случайное число", callback_data="game_random")],
        [InlineKeyboardButton("🎯 Бросок кубика", callback_data="game_dice")],
        [InlineKeyboardButton("🪙 Подброс монеты", callback_data="game_coin")],
        [InlineKeyboardButton("😄 Шутка", callback_data="game_joke")],
        [InlineKeyboardButton("💭 Цитата", callback_data="game_quote")],
        [InlineKeyboardButton("🔬 Факт", callback_data="game_fact")]
    ]
    await update.message.reply_text("🎲 <b>Выберите развлечение:</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # При клике на кнопку вызываем соответствующую команду
    if data == "game_random":
        await query.edit_message_text("🎲 Используйте /random [min] [max] (например, /random 1 10).")
    elif data == "game_dice":
        await dice_command(query, context)
        # Удаляем кнопку, чтобы не было повторного нажатия
        await query.edit_message_reply_markup(reply_markup=None) 
    elif data == "game_coin":
        await coin_command(query, context)
        await query.edit_message_reply_markup(reply_markup=None)
    elif data == "game_joke":
        await joke_command(query, context)
    elif data == "game_quote":
        await quote_command(query, context)
    elif data == "game_fact":
        await fact_command(query, context)

async def handle_callback_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.data.startswith("help_"):
        await handle_help_callback(update, context)
        return
    elif query.data.startswith("game_"):
        await handle_game_callback(update, context)
        return
    
    await query.answer()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    user_id = user.id
    
    # 1. Обновление статистики и данных пользователя
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {
        'username': user.username or '', 
        'first_name': user.first_name or '', 
        'messages_count': user_data.get('messages_count', 0) + 1
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # 2. Обработка кнопок основного меню
    if text == "💬 AI Чат":
        await update.message.reply_text("🤖 Вы перешли в режим AI-чата. Задайте свой вопрос!")
    elif text == "📝 Заметки":
        await notes_command(update, context)
    elif text == "🌍 Погода":
        await update.message.reply_text("🌍 Введите /weather [город] для получения погоды.")
    elif text == "⏰ Время":
        await update.message.reply_text("⏰ Введите /time [город] для получения времени.")
    elif text == "🎲 Развлечения":
        await handle_games_menu(update, context)
    elif text == "ℹ️ Инфо":
        await info_command(update, context)
    elif text == "💎 VIP Меню":
        await update.message.reply_text("💎 <b>VIP Меню</b>\n\n🖼️ Используйте /generate [описание] для создания изображений.", parse_mode=ParseMode.HTML)
    elif text == "🖼️ Генерация":
        await update.message.reply_text("🖼️ Введите /generate [описание] для генерации изображения.")
    elif text == "👑 Админ Панель":
        await stats_command(update, context) 
    elif text.startswith('/'):
        # Игнорируем команды, они будут обработаны CommandHandler'ами
        pass
    else:
        # 3. AI-ответ на обычный текст (chat logic)
        await process_ai_message(update, text, user_id)

# --- Главная функция ---

def main():
    """Запуск бота."""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
    except Exception as e:
        logger.error(f"Failed to build Application: {e}")
        return

    # Запуск планировщика и добавление задачи проверки напоминаний
    scheduler.add_job(check_reminders, 'interval', minutes=1, args=[application])
    
    # --- Command Handlers ---
    # Основные
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("uptime", uptime_command))
    application.add_handler(CommandHandler("vip", vip_command))
    
    # AI/Chat
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("generate", generate_command))
    
    # Утилиты
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("password", password_command))
    
    # Развлечения
    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("fact", fact_command))
    
    # Хранилище
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("notes", notes_command))
    application.add_handler(CommandHandler("delnote", delnote_command))
    application.add_handler(CommandHandler("todo", todo_command))
    application.add_handler(CommandHandler("memorysave", memory_save_command))
    application.add_handler(CommandHandler("memoryget", memory_get_command))
    application.add_handler(CommandHandler("memorylist", memory_list_command))
    application.add_handler(CommandHandler("memorydel", memory_del_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    
    # Админ
    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("backup", backup_command))
    
    # --- Message Handlers ---
    # Текстовые сообщения (не команды), которые идут в AI-чат, и кнопки главного меню
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Медиа-обработчики
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Обработчик колбэков
    application.add_handler(CallbackQueryHandler(handle_callback_full))
    
    # Запуск scheduler
    scheduler.start()
    
    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН!")
    logger.info("🤖 Модель: Gemini 2.5 Flash")
    logger.info("🗄️ БД: " + ("PostgreSQL ✓" if engine else "Local JSON"))
    logger.info("🖼️ Генерация: Gemini 2.5 Flash Image")
    logger.info("🔍 Анализ: Gemini Vision")
    logger.info("🎙️ Транскрипция: Gemini 2.5 Flash")
    logger.info("=" * 50)
    
    # Запуск бота
    application.run_polling(poll_interval=1)

if __name__ == '__main__':
    main()
