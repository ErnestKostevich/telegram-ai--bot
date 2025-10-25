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

# ============= МУЛЬТИЯЗЫЧНОСТЬ =============
TRANSLATIONS = {
    'ru': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nПривет, {name}!\nЯ бот на <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Возможности:</b>\n💬 AI-чат с контекстом\n📝 Заметки и задачи\n🌍 Погода и время\n🎲 Развлечения\n📎 Анализ файлов (VIP)\n🔍 Анализ изображений (VIP)\n🖼️ Генерация изображений (VIP)\n\n<b>⚡ Команды:</b>\n/help - Все команды\n/language - Сменить язык\n/vip - Статус VIP\n\n<b>👨‍💻 Создатель:</b> @{creator}",
        'language_changed': "✅ Язык изменен на: Русский 🇷🇺",
        'select_language': "🌍 <b>Выберите язык / Select language / Seleziona lingua:</b>",
        'ai_chat': "💬 AI Чат",
        'notes': "📝 Заметки",
        'weather': "🌍 Погода",
        'time': "⏰ Время",
        'entertainment': "🎲 Развлечения",
        'info': "ℹ️ Инфо",
        'vip_menu': "💎 VIP Меню",
        'admin_panel': "👑 Админ Панель",
        'generation': "🖼️ Генерация",
        'generating': "🎨 Генерирую изображение...",
        'generation_success': "🖼️ <b>Изображение готово!</b>\n\n💎 VIP | Stable Diffusion",
        'generation_error': "❌ Ошибка генерации. Попробуйте еще раз.",
        'vip_only': "💎 Доступно только VIP-пользователям.\n\nСвяжитесь с @{creator}",
        'help_text': "📚 <b>Выберите раздел справки:</b>\n\nНажмите кнопку ниже для просмотра команд по теме.",
        'cleared': "🧹 Контекст очищен!",
        'generating_prompt': "/generate [описание]\n\nПример: /generate закат над океаном",
    },
    'en': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nHello, {name}!\nI'm a bot powered by <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Features:</b>\n💬 AI chat with context\n📝 Notes and tasks\n🌍 Weather and time\n🎲 Entertainment\n📎 File analysis (VIP)\n🔍 Image analysis (VIP)\n🖼️ Image generation (VIP)\n\n<b>⚡ Commands:</b>\n/help - All commands\n/language - Change language\n/vip - VIP status\n\n<b>👨‍💻 Creator:</b> @{creator}",
        'language_changed': "✅ Language changed to: English 🇬🇧",
        'select_language': "🌍 <b>Select language / Выберите язык / Seleziona lingua:</b>",
        'ai_chat': "💬 AI Chat",
        'notes': "📝 Notes",
        'weather': "🌍 Weather",
        'time': "⏰ Time",
        'entertainment': "🎲 Games",
        'info': "ℹ️ Info",
        'vip_menu': "💎 VIP Menu",
        'admin_panel': "👑 Admin Panel",
        'generation': "🖼️ Generation",
        'generating': "🎨 Generating image...",
        'generation_success': "🖼️ <b>Image ready!</b>\n\n💎 VIP | Stable Diffusion",
        'generation_error': "❌ Generation error. Please try again.",
        'vip_only': "💎 Available only for VIP users.\n\nContact @{creator}",
        'help_text': "📚 <b>Choose help section:</b>\n\nClick button below to view commands.",
        'cleared': "🧹 Context cleared!",
        'generating_prompt': "/generate [description]\n\nExample: /generate sunset over ocean",
    },
    'it': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nCiao, {name}!\nSono un bot basato su <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Funzionalità:</b>\n💬 Chat AI con contesto\n📝 Note e attività\n🌍 Meteo e ora\n🎲 Intrattenimento\n📎 Analisi file (VIP)\n🔍 Analisi immagini (VIP)\n🖼️ Generazione immagini (VIP)\n\n<b>⚡ Comandi:</b>\n/help - Tutti i comandi\n/language - Cambia lingua\n/vip - Status VIP\n\n<b>👨‍💻 Creatore:</b> @{creator}",
        'language_changed': "✅ Lingua cambiata in: Italiano 🇮🇹",
        'select_language': "🌍 <b>Seleziona lingua / Select language / Выберите язык:</b>",
        'ai_chat': "💬 Chat AI",
        'notes': "📝 Note",
        'weather': "🌍 Meteo",
        'time': "⏰ Ora",
        'entertainment': "🎲 Giochi",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menu VIP",
        'admin_panel': "👑 Pannello Admin",
        'generation': "🖼️ Generazione",
        'generating': "🎨 Generazione immagine...",
        'generation_success': "🖼️ <b>Immagine pronta!</b>\n\n💎 VIP | Stable Diffusion",
        'generation_error': "❌ Errore di generazione. Riprova.",
        'vip_only': "💎 Disponibile solo per utenti VIP.\n\nContatta @{creator}",
        'help_text': "📚 <b>Scegli sezione aiuto:</b>\n\nClicca il pulsante sotto per vedere i comandi.",
        'cleared': "🧹 Contesto cancellato!",
        'generating_prompt': "/generate [descrizione]\n\nEsempio: /generate tramonto sull'oceano",
    }
}

def get_text(user_id: int, key: str, **kwargs) -> str:
    """Получить переведенный текст для пользователя"""
    lang = storage.get_user(user_id).get('language', 'ru')
    text = TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, TRANSLATIONS['ru'].get(key, key))
    return text.format(**kwargs) if kwargs else text

# Проверка переменных окружения
if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ BOT_TOKEN или GEMINI_API_KEY не установлены!")
    raise ValueError("Required environment variables missing")

# Настройка Gemini 2.5 Flash
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

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="Ты — AI DISCO BOT, многофункциональный, очень умный и вежливый ассистент, основанный на Gemini 2.5. Всегда отвечай на том языке, на котором к тебе обращаются, используя дружелюбный и вовлекающий тон. Твои ответы должны быть структурированы, по возможности разделены на абзацы и никогда не превышать 4000 символов (ограничение Telegram). Твой создатель — @Ernest_Kostevich. Включай в ответы эмодзи, где это уместно."
)

vision_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# База данных PostgreSQL
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255))
    language = Column(String(10), default='ru')
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
                    user = User(id=user_id, language='ru')
                    session.add(user)
                    session.commit()
                return {
                    'id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'language': user.language or 'ru',
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
                    'id': user_id, 'username': '', 'first_name': '', 'language': 'ru', 'vip': False, 'vip_until': None,
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
                return {u.id: {'id': u.id, 'username': u.username, 'first_name': u.first_name, 'vip': u.vip, 'language': u.language or 'ru'} for u in users}
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

def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Создатель: {user.id}")

def is_creator(user_id: int) -> bool:
    return user_id == CREATOR_ID

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(get_text(user_id, 'ai_chat')), KeyboardButton(get_text(user_id, 'notes'))],
        [KeyboardButton(get_text(user_id, 'weather')), KeyboardButton(get_text(user_id, 'time'))],
        [KeyboardButton(get_text(user_id, 'entertainment')), KeyboardButton(get_text(user_id, 'info'))]
    ]
    if storage.is_vip(user_id):
        keyboard.insert(0, [KeyboardButton(get_text(user_id, 'vip_menu')), KeyboardButton(get_text(user_id, 'generation'))])
    if is_creator(user_id):
        keyboard.append([KeyboardButton(get_text(user_id, 'admin_panel'))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_help_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🏠 Basic", callback_data="help_basic")],
        [InlineKeyboardButton("💬 AI", callback_data="help_ai")],
        [InlineKeyboardButton("🧠 Memory", callback_data="help_memory")],
        [InlineKeyboardButton("📝 Notes", callback_data="help_notes")],
        [InlineKeyboardButton("📋 Tasks", callback_data="help_todo")],
        [InlineKeyboardButton("🌍 Utils", callback_data="help_utils")],
        [InlineKeyboardButton("🎲 Games", callback_data="help_games")],
        [InlineKeyboardButton("💎 VIP", callback_data="help_vip")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 Admin", callback_data="help_admin")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="help_back")])
    return InlineKeyboardMarkup(keyboard)

# ============= ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ через Stable Diffusion =============
async def generate_image_stable_diffusion(prompt: str) -> Optional[bytes]:
    """Генерация изображения через Hugging Face Inference API (бесплатно)"""
    try:
        API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        
        # Улучшаем промпт для лучшего качества
        enhanced_prompt = f"{prompt}, masterpiece, best quality, highly detailed, 8k"
        
        headers = {"Content-Type": "application/json"}
        payload = {
            "inputs": enhanced_prompt,
            "parameters": {
                "negative_prompt": "blurry, bad quality, distorted, ugly",
                "num_inference_steps": 30,
                "guidance_scale": 7.5
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    image_bytes = await response.read()
                    logger.info(f"✅ Изображение сгенерировано успешно! Размер: {len(image_bytes)} байт")
                    return image_bytes
                else:
                    error_text = await response.text()
                    logger.warning(f"Ошибка генерации: {response.status} - {error_text}")
                    
                    # Если модель загружается, пробуем альтернативную
                    if "loading" in error_text.lower():
                        logger.info("Пробуем альтернативную модель...")
                        ALT_API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
                        async with session.post(ALT_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as alt_response:
                            if alt_response.status == 200:
                                return await alt_response.read()
                    
                    return None
                    
    except asyncio.TimeoutError:
        logger.warning("Таймаут генерации изображения")
        return None
    except Exception as e:
        logger.error(f"Ошибка генерации изображения: {e}")
        return None

async def analyze_image_with_gemini(image_bytes: bytes, prompt: str = "Опиши подробно что изображено") -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = vision_model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка анализа: {str(e)}"

async def transcribe_audio_with_gemini(audio_bytes: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        uploaded_file = genai.upload_file(path=temp_path, mime_type="audio/ogg")
        prompt = "Распознай речь в этом аудиофайле. Верни только текст, без приветствий и комментариев."
        response = model.generate_content([prompt, uploaded_file])
        os.remove(temp_path)
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка транскрипции аудио: {e}")
        return f"❌ Ошибка транскрипции: {str(e)}"

async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
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

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text(user_id, 'vip_only', creator=CREATOR_USERNAME))
        return
    document = update.message.document
    file_name = document.file_name or "file"
    await update.message.reply_text("📥 Загружаю файл...")
    try:
        file_obj = await context.bot.get_file(document.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        extracted_text = await extract_text_from_document(bytes(file_bytes), file_name)
        if extracted_text.startswith("❌") or extracted_text.startswith("⚠️"):
            await update.message.reply_text(extracted_text)
            return
        analysis_prompt = f"Проанализируй файл '{file_name}':\n\n{extracted_text[:4000]}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(analysis_prompt)
        storage.save_chat(user_id, f"Файл {file_name}", response.text)
        await update.message.reply_text(f"📄 <b>Файл:</b> {file_name}\n\n🤖 <b>Анализ:</b>\n\n{response.text}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки документа: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text(user_id, 'vip_only', creator=CREATOR_USERNAME))
        return
    photo = update.message.photo[-1]
    caption = update.message.caption or "Опиши что на картинке"
    await update.message.reply_text("🔍 Анализирую...")
    try:
        file_obj = await context.bot.get_file(photo.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        analysis = await analyze_image_with_gemini(bytes(file_bytes), caption)
        storage.save_chat(user_id, "Анализ фото", analysis)
        await update.message.reply_text(f"📸 <b>Анализ (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки фото: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    voice = update.message.voice
    await update.message.reply_text("🎙️ Транскрибирую аудио...")
    try:
        file_obj = await context.bot.get_file(voice.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        transcribed_text = await transcribe_audio_with_gemini(bytes(file_bytes))
        
        if transcribed_text.startswith("❌"):
            await update.message.reply_text(transcribed_text)
            return
        
        await process_ai_message(update, transcribed_text, user_id)
    except Exception as e:
        logger.warning(f"Ошибка обработки голосового сообщения: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {
        'username': user.username or '', 
        'first_name': user.first_name or '', 
        'commands_count': user_data.get('commands_count', 0) + 1
    })
    
    welcome_text = get_text(user.id, 'welcome', name=user.first_name, creator=CREATOR_USERNAME)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда смены языка"""
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it")]
    ]
    await update.message.reply_text(
        get_text(user_id, 'select_language'),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text(user_id, 'vip_only', creator=CREATOR_USERNAME))
        return
    if not context.args:
        await update.message.reply_text(get_text(user_id, 'generating_prompt'))
        return
    
    prompt = ' '.join(context.args)
    status_msg = await update.message.reply_text(get_text(user_id, 'generating'))
    
    try:
        image_bytes = await generate_image_stable_diffusion(prompt)
        
        if image_bytes:
            await update.message.reply_photo(
                photo=io.BytesIO(image_bytes),
                caption=get_text(user_id, 'generation_success')
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text(get_text(user_id, 'generation_error'))
            
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        await status_msg.edit_text(get_text(user_id, 'generation_error'))

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ /ai [вопрос]")
        return
    await process_ai_message(update, ' '.join(context.args), update.effective_user.id)

async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action("typing")
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response.text)
        await send_long_message(update.message, response.text)
    except Exception as e:
        logger.error(f"AI: {e}")
        await update.message.reply_text("😔 Ошибка")

async def send_long_message(message: Message, text: str):
    if len(text) <= 4000:
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.5)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    storage.clear_chat_session(user_id)
    await update.message.reply_text(get_text(user_id, 'cleared'))

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"""🤖 <b>AI DISCO BOT</b>

<b>Version:</b> 3.1
<b>AI:</b> Gemini 2.5 Flash
<b>Image Gen:</b> Stable Diffusion XL
<b>Creator:</b> @{CREATOR_USERNAME}

<b>⚡ Features:</b>
• Fast AI chat
• PostgreSQL
• VIP functions
• File/photo analysis (VIP)
• Image generation (VIP)
• Multi-language support

<b>💬 Support:</b> @{CREATOR_USERNAME}""", parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = storage.stats
    all_users = storage.get_all_users()
    uptime = datetime.now() - BOT_START_TIME
    status_text = f"""📊 <b>STATUS</b>

<b>👥 Users:</b> {len(all_users)}
<b>💎 VIP:</b> {sum(1 for u in all_users.values() if u.get('vip', False))}

<b>📈 Activity:</b>
• Messages: {stats.get('total_messages', 0)}
• Commands: {stats.get('total_commands', 0)}
• AI requests: {stats.get('ai_requests', 0)}

<b>⏱ Uptime:</b> {uptime.days}d {uptime.seconds // 3600}h

<b>✅ Status:</b> Online
<b>🤖 AI:</b> Gemini 2.5 ✓
<b>🖼️ Image Gen:</b> Stable Diffusion ✓
<b>🗄️ DB:</b> {'PostgreSQL ✓' if engine else 'JSON'}"""
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = storage.get_user(update.effective_user.id)
    profile_text = f"""👤 <b>{user.get('first_name', 'User')}</b>
🆔 <code>{user.get('id')}</code>
"""
    if user.get('username'):
        profile_text += f"📱 @{user['username']}\n"
    profile_text += f"""
📅 {user.get('registered', '')[:10]}
📊 Messages: {user.get('messages_count', 0)}
🎯 Commands: {user.get('commands_count', 0)}
📝 Notes: {len(user.get('notes', []))}
🌍 Language: {user.get('language', 'ru').upper()}"""
    if storage.is_vip(update.effective_user.id):
        vip_until = user.get('vip_until')
        if vip_until:
            profile_text += f"\n💎 VIP until: {datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')}"
        else:
            profile_text += "\n💎 VIP: Forever ♾️"
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - BOT_START_TIME
    await update.message.reply_text(f"""⏱ <b>UPTIME</b>

🕐 Started: {BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S')}
⏰ Running: {uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m

✅ Online""", parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = storage.get_user(update.effective_user.id)
    if storage.is_vip(update.effective_user.id):
        vip_text = "💎 <b>VIP STATUS</b>\n\n✅ Active!\n\n"
        vip_until = user.get('vip_until')
        if vip_until:
            vip_text += f"⏰ Until: {datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')}\n\n"
        else:
            vip_text += "⏰ Forever ♾️\n\n"
        vip_text += "<b>🎁 Benefits:</b>\n• ⏰ Reminders\n• 🖼️ Image generation\n• 🔍 Image analysis\n• 📎 Document analysis"
    else:
        vip_text = f"💎 <b>VIP STATUS</b>\n\n❌ No VIP.\n\nContact @{CREATOR_USERNAME}"
    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /note [text]")
        return
    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)
    note = {'text': note_text, 'created': datetime.now().isoformat()}
    notes = user.get('notes', [])
    notes.append(note)
    storage.update_user(user_id, {'notes': notes})
    await update.message.reply_text(f"✅ Note #{len(notes)} saved!\n\n📝 {note_text}")

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    notes = user.get('notes', [])
    if not notes:
        await update.message.reply_text("📭 No notes.")
        return
    notes_text = f"📝 <b>Notes ({len(notes)}):</b>\n\n"
    for i, note in enumerate(notes, 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y')})\n{note['text']}\n\n"
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /delnote [number]")
        return
    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        if 1 <= note_num <= len(notes):
            deleted_note = notes.pop(note_num - 1)
            storage.update_user(user_id, {'notes': notes})
            await update.message.reply_text(f"✅ Note #{note_num} deleted:\n\n📝 {deleted_note['text']}")
        else:
            await update.message.reply_text(f"❌ Note #{note_num} not found.")
    except ValueError:
        await update.message.reply_text("❌ Enter number.")

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("❓ /memorysave [key] [value]")
        return
    key = context.args[0]
    value = ' '.join(context.args[1:])
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    memory[key] = value
    storage.update_user(user_id, {'memory': memory})
    await update.message.reply_text(f"✅ Saved:\n🔑 <b>{key}</b> = <code>{value}</code>", parse_mode=ParseMode.HTML)

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /memoryget [key]")
        return
    key = context.args[0]
    user = storage.get_user(user_id)
    if key in user.get('memory', {}):
        await update.message.reply_text(f"🔍 <b>{key}</b> = <code>{user['memory'][key]}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Key '{key}' not found.")

async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = storage.get_user(update.effective_user.id)
    memory = user.get('memory', {})
    if not memory:
        await update.message.reply_text("📭 Memory empty.")
        return
    memory_text = "🧠 <b>Memory:</b>\n\n"
    for key, value in memory.items():
        memory_text += f"🔑 <b>{key}</b>: <code>{value}</code>\n"
    await update.message.reply_text(memory_text, parse_mode=ParseMode.HTML)

async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /memorydel [key]")
        return
    key = context.args[0]
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    if key in memory:
        del memory[key]
        storage.update_user(user_id, {'memory': memory})
        await update.message.reply_text(f"✅ Key '{key}' deleted.")
    else:
        await update.message.reply_text(f"❌ Key '{key}' not found.")

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /todo add [text] | list | del [number]")
        return
    subcommand = context.args[0].lower()
    user = storage.get_user(user_id)
    if subcommand == 'add':
        if len(context.args) < 2:
            await update.message.reply_text("❓ /todo add [text]")
            return
        todo_text = ' '.join(context.args[1:])
        todo = {'text': todo_text, 'created': datetime.now().isoformat()}
        todos = user.get('todos', [])
        todos.append(todo)
        storage.update_user(user_id, {'todos': todos})
        await update.message.reply_text(f"✅ Task #{len(todos)} added!\n\n📋 {todo_text}")
    elif subcommand == 'list':
        todos = user.get('todos', [])
        if not todos:
            await update.message.reply_text("📭 No tasks.")
            return
        todos_text = f"📋 <b>Tasks ({len(todos)}):</b>\n\n"
        for i, todo in enumerate(todos, 1):
            created = datetime.fromisoformat(todo['created'])
            todos_text += f"<b>#{i}</b> ({created.strftime('%d.%m')})\n{todo['text']}\n\n"
        await update.message.reply_text(todos_text, parse_mode=ParseMode.HTML)
    elif subcommand == 'del':
        if len(context.args) < 2:
            await update.message.reply_text("❓ /todo del [number]")
            return
        try:
            todo_num = int(context.args[1])
            todos = user.get('todos', [])
            if 1 <= todo_num <= len(todos):
                deleted_todo = todos.pop(todo_num - 1)
                storage.update_user(user_id, {'todos': todos})
                await update.message.reply_text(f"✅ Task #{todo_num} deleted:\n\n📋 {deleted_todo['text']}")
            else:
                await update.message.reply_text(f"❌ Task #{todo_num} not found.")
        except ValueError:
            await update.message.reply_text("❌ Enter number.")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = ' '.join(context.args) if context.args else 'Moscow'
    timezones = {
        'moscow': 'Europe/Moscow', 'london': 'Europe/London', 'new york': 'America/New_York',
        'tokyo': 'Asia/Tokyo', 'paris': 'Europe/Paris', 'berlin': 'Europe/Berlin',
        'dubai': 'Asia/Dubai', 'sydney': 'Australia/Sydney', 'los angeles': 'America/Los_Angeles',
        'milan': 'Europe/Rome', 'rome': 'Europe/Rome', 'milano': 'Europe/Rome'
    }
    tz_name = timezones.get(city.lower(), 'Europe/Moscow')
    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        await update.message.reply_text(f"""⏰ <b>{city.title()}</b>

🕐 Time: {current_time.strftime('%H:%M:%S')}
📅 Date: {current_time.strftime('%d.%m.%Y')}
🌍 Timezone: {tz_name}""", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Time error: {e}")
        await update.message.reply_text(f"❌ City '{city}' not found.")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = ' '.join(context.args) if context.args else 'Moscow'
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?format=j1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data['current_condition'][0]
                    temp_c = current['temp_C']
                    feels_like = current['FeelsLikeC']
                    description = current['weatherDesc'][0]['value']
                    humidity = current['humidity']
                    wind_speed = current['windspeedKmph']
                    weather_text = f"""🌍 <b>{city.title()}</b>

🌡 Temperature: {temp_c}°C
🤔 Feels like: {feels_like}°C
☁️ {description}
💧 Humidity: {humidity}%
💨 Wind: {wind_speed} km/h"""
                    await update.message.reply_text(weather_text, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(f"❌ City '{city}' not found.")
    except Exception as e:
        logger.warning(f"Weather error: {e}")
        await update.message.reply_text("❌ Weather error.")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❓ /translate [lang] [text]\n\nExample: /translate en Hello")
        return
    target_lang = context.args[0]
    text = ' '.join(context.args[1:])
    try:
        prompt = f"Translate to {target_lang}: {text}"
        chat = storage.get_chat_session(update.effective_user.id)
        response = chat.send_message(prompt)
        await send_long_message(update.message, response.text)
    except Exception as e:
        logger.warning(f"Translation error: {e}")
        await update.message.reply_text("❌ Translation error.")

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ /calc [expression]\n\nExample: /calc 2+2*5")
        return
    expression = ' '.join(context.args)
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        await update.message.reply_text(f"🧮 <b>Result:</b>\n\n{expression} = <b>{result}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Calc error: {e}")
        await update.message.reply_text("❌ Calculation error.")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text("❌ Length from 8 to 50.")
            return
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(f"🔑 <b>Password:</b>\n\n<code>{password}</code>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ Enter length.")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) >= 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        else:
            min_val = 1
            max_val = 100
        result = random.randint(min_val, max_val)
        await update.message.reply_text(f"🎲 Number from {min_val} to {max_val}:\n\n<b>{result}</b>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ Enter numbers.")

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    await update.message.reply_text(f"🎲 {dice_emoji} Result: <b>{result}</b>", parse_mode=ParseMode.HTML)

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = {'ru': ['Орёл', 'Решка'], 'en': ['Heads', 'Tails'], 'it': ['Testa', 'Croce']}
    lang = storage.get_user(update.effective_user.id).get('language', 'ru')
    result = random.choice(results.get(lang, results['ru']))
    emoji = '🦅' if 'Орёл' in result or 'Heads' in result or 'Testa' in result else '💰'
    await update.message.reply_text(f"🪙 {emoji} Result: <b>{result}</b>", parse_mode=ParseMode.HTML)

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = {
        'ru': [
            "Программист ложится спать. Жена: — Закрой окно, холодно! Программист: — И что, если я закрою окно, станет тепло? 😄",
            "— Почему программисты путают Хэллоуин и Рождество? — 31 OCT = 25 DEC! 🎃",
            "Зачем программисту очки? Чтобы лучше C++! 👓"
        ],
        'en': [
            "Why do programmers prefer dark mode? Because light attracts bugs! 😄",
            "Why do programmers confuse Halloween and Christmas? Because 31 OCT = 25 DEC! 🎃",
            "How many programmers does it take to change a light bulb? None, it's a hardware problem! 💡"
        ],
        'it': [
            "Perché i programmatori preferiscono la modalità scura? Perché la luce attira i bug! 😄",
            "Perché i programmatori confondono Halloween e Natale? Perché 31 OCT = 25 DEC! 🎃",
            "Quanti programmatori servono per cambiare una lampadina? Nessuno, è un problema hardware! 💡"
        ]
    }
    lang = storage.get_user(update.effective_user.id).get('language', 'ru')
    await update.message.reply_text(f"😄 <b>Joke:</b>\n\n{random.choice(jokes.get(lang, jokes['ru']))}", parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = {
        'ru': [
            "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
            "Инновация отличает лидера от последователя. — Стив Джобс",
            "Программирование — это искусство превращать кофе в код. — Неизвестный",
            "Простота — залог надёжности. — Эдсгер Дейкстра"
        ],
        'en': [
            "The only way to do great work is to love what you do. — Steve Jobs",
            "Innovation distinguishes between a leader and a follower. — Steve Jobs",
            "Programming is the art of turning coffee into code. — Unknown",
            "Simplicity is the soul of efficiency. — Edsger Dijkstra"
        ],
        'it': [
            "L'unico modo per fare un ottimo lavoro è amare quello che fai. — Steve Jobs",
            "L'innovazione distingue un leader da un seguace. — Steve Jobs",
            "La programmazione è l'arte di trasformare il caffè in codice. — Sconosciuto",
            "La semplicità è l'anima dell'efficienza. — Edsger Dijkstra"
        ]
    }
    lang = storage.get_user(update.effective_user.id).get('language', 'ru')
    await update.message.reply_text(f"💭 <b>Quote:</b>\n\n<i>{random.choice(quotes.get(lang, quotes['ru']))}</i>", parse_mode=ParseMode.HTML)

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = {
        'ru': [
            "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
            "🐙 У осьминогов три сердца и голубая кровь.",
            "🍯 Мёд не портится тысячи лет.",
            "💎 Алмазы формируются на глубине ~150 км.",
            "🧠 Мозг потребляет ~20% энергии тела.",
            "⚡ Молния в 5 раз горячее Солнца."
        ],
        'en': [
            "🌍 Earth is the only planet not named after a god.",
            "🐙 Octopuses have three hearts and blue blood.",
            "🍯 Honey never spoils, even after thousands of years.",
            "💎 Diamonds form at depths of ~150 km.",
            "🧠 The brain consumes ~20% of the body's energy.",
            "⚡ Lightning is 5 times hotter than the Sun."
        ],
        'it': [
            "🌍 La Terra è l'unico pianeta non nominato in onore di un dio.",
            "🐙 I polpi hanno tre cuori e sangue blu.",
            "🍯 Il miele non si rovina mai, anche dopo migliaia di anni.",
            "💎 I diamanti si formano a profondità di ~150 km.",
            "🧠 Il cervello consume ~20% dell'energia del corpo.",
            "⚡ Il fulmine è 5 volte più caldo del Sole."
        ]
    }
    lang = storage.get_user(update.effective_user.id).get('language', 'ru')
    await update.message.reply_text(f"🔬 <b>Fact:</b>\n\n{random.choice(facts.get(lang, facts['ru']))}", parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text(user_id, 'vip_only', creator=CREATOR_USERNAME))
        return
    if len(context.args) < 2:
        await update.message.reply_text("❓ /remind [minutes] [text]")
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
        await update.message.reply_text(f"⏰ Reminder created!\n\n📝 {text}\n🕐 In {minutes} minutes")
    except ValueError:
        await update.message.reply_text("❌ Enter minutes.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text(user_id, 'vip_only', creator=CREATOR_USERNAME))
        return
    user = storage.get_user(user_id)
    reminders = user.get('reminders', [])
    if not reminders:
        await update.message.reply_text("📭 No reminders.")
        return
    reminders_text = f"⏰ <b>Reminders ({len(reminders)}):</b>\n\n"
    for i, reminder in enumerate(reminders, 1):
        remind_time = datetime.fromisoformat(reminder['time'])
        reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n📝 {reminder['text']}\n\n"
    await update.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)

async def send_reminder(bot, user_id: int, text: str):
    try:
        await bot.send_message(chat_id=user_id, text=f"⏰ <b>REMINDER</b>\n\n📝 {text}", parse_mode=ParseMode.HTML)
        user = storage.get_user(user_id)
        reminders = [r for r in user.get('reminders', []) if r['text'] != text]
        storage.update_user(user_id, {'reminders': reminders})
    except Exception as e:
        logger.warning(f"Reminder error: {e}")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Creator only.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❓ /grant_vip [id/@username] [period]\n\nPeriods: week, month, year, forever")
        return
    try:
        identifier = context.args[0]
        duration = context.args[1].lower()
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(f"❌ User '{identifier}' not found.")
            return
        durations = {'week': timedelta(weeks=1), 'month': timedelta(days=30), 'year': timedelta(days=365), 'forever': None}
        if duration not in durations:
            await update.message.reply_text("❌ Invalid period.")
            return
        if durations[duration]:
            vip_until = datetime.now() + durations[duration]
            storage.update_user(target_id, {'vip': True, 'vip_until': vip_until.isoformat()})
            duration_text = f"until {vip_until.strftime('%d.%m.%Y')}"
        else:
            storage.update_user(target_id, {'vip': True, 'vip_until': None})
            duration_text = "forever"
        await update.message.reply_text(f"✅ VIP granted!\n\n🆔 <code>{target_id}</code>\n⏰ {duration_text}", parse_mode=ParseMode.HTML)
        try:
            await context.bot.send_message(chat_id=target_id, text=f"🎉 VIP status granted {duration_text}!", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"VIP notification error: {e}")
    except Exception as e:
        logger.warning(f"grant_vip error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Creator only.")
        return
    if not context.args:
        await update.message.reply_text("❓ /revoke_vip [id/@username]")
        return
    try:
        identifier = context.args[0]
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(f"❌ User '{identifier}' not found.")
            return
        storage.update_user(target_id, {'vip': False, 'vip_until': None})
        await update.message.reply_text(f"✅ VIP revoked!\n\n🆔 <code>{target_id}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"revoke_vip error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Creator only.")
        return
    all_users = storage.get_all_users()
    users_text = f"👥 <b>USERS ({len(all_users)}):</b>\n\n"
    for user_id, user in list(all_users.items())[:20]:
        vip_badge = "💎" if user.get('vip', False) else ""
        lang_flag = {'ru': '🇷🇺', 'en': '🇬🇧', 'it': '🇮🇹'}.get(user.get('language', 'ru'), '🌍')
        users_text += f"{vip_badge}{lang_flag} <code>{user_id}</code> - {user.get('first_name', 'Unknown')} @{user.get('username', '')}\n"
    if len(all_users) > 20:
        users_text += f"\n<i>... and {len(all_users) - 20} more</i>"
    await update.message.reply_text(users_text, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Creator only.")
        return
    if not context.args:
        await update.message.reply_text("❓ /broadcast [text]")
        return
    message_text = ' '.join(context.args)
    success = 0
    failed = 0
    status_msg = await update.message.reply_text("📤 Broadcasting...")
    all_users = storage.get_all_users()
    for user_id in all_users.keys():
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 <b>From creator:</b>\n\n{message_text}", parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Broadcast error for user {user_id}: {e}")
            failed += 1
    await status_msg.edit_text(f"✅ Complete!\n\n✅ Success: {success}\n❌ Errors: {failed}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Creator only.")
        return
    stats = storage.stats
    all_users = storage.get_all_users()
    lang_stats = {}
    for user in all_users.values():
        lang = user.get('language', 'ru')
        lang_stats[lang] = lang_stats.get(lang, 0) + 1
    
    stats_text = f"""📊 <b>STATISTICS</b>

<b>👥 Users:</b> {len(all_users)}
<b>💎 VIP:</b> {sum(1 for u in all_users.values() if u.get('vip', False))}

<b>🌍 Languages:</b>
• 🇷🇺 Russian: {lang_stats.get('ru', 0)}
• 🇬🇧 English: {lang_stats.get('en', 0)}
• 🇮🇹 Italian: {lang_stats.get('it', 0)}

<b>📈 Activity:</b>
• Messages: {stats.get('total_messages', 0)}
• Commands: {stats.get('total_commands', 0)}
• AI requests: {stats.get('ai_requests', 0)}"""
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Creator only.")
        return
    try:
        backup_data = {'users': storage.get_all_users(), 'stats': storage.stats, 'backup_date': datetime.now().isoformat()}
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        await update.message.reply_document(document=open(backup_filename, 'rb'), caption=f"✅ Backup\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        os.remove(backup_filename)
    except Exception as e:
        logger.warning(f"Backup error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'commands_count': user_data.get('commands_count', 0) + 1})
    is_admin = is_creator(user_id)
    await update.message.reply_text(
        get_text(user_id, 'help_text'),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(is_admin)
    )

async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    is_admin = is_creator(user_id)

    if data == "help_back":
        await query.edit_message_text(
            get_text(user_id, 'help_text'),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(is_admin)
        )
        return

    sections = {
        "help_basic": (
            "🏠 <b>Basic Commands:</b>\n\n"
            "🚀 /start - Start bot\n\n"
            "📖 /help - All commands\n\n"
            "🌍 /language - Change language\n\n"
            "ℹ️ /info - Bot info\n\n"
            "📊 /status - Status\n\n"
            "👤 /profile - Profile\n\n"
            "⏱ /uptime - Uptime",
            get_help_keyboard(is_admin)
        ),
        "help_ai": (
            "💬 <b>AI Commands:</b>\n\n"
            "🤖 /ai [question] - Ask AI\n\n"
            "🧹 /clear - Clear context",
            get_help_keyboard(is_admin)
        ),
        "help_memory": (
            "🧠 <b>Memory:</b>\n\n"
            "💾 /memorysave [key] [value] - Save\n\n"
            "🔍 /memoryget [key] - Get\n\n"
            "📋 /memorylist - List\n\n"
            "🗑 /memorydel [key] - Delete",
            get_help_keyboard(is_admin)
        ),
        "help_notes": (
            "📝 <b>Notes:</b>\n\n"
            "➕ /note [text] - Create\n\n"
            "📋 /notes - List\n\n"
            "🗑 /delnote [number] - Delete",
            get_help_keyboard(is_admin)
        ),
        "help_todo": (
            "📋 <b>Tasks:</b>\n\n"
            "➕ /todo add [text] - Add\n\n"
            "📋 /todo list - List\n\n"
            "🗑 /todo del [number] - Delete",
            get_help_keyboard(is_admin)
        ),
        "help_utils": (
            "🌍 <b>Utils:</b>\n\n"
            "🕐 /time [city] - Time\n\n"
            "☀️ /weather [city] - Weather\n\n"
            "🌐 /translate [lang] [text] - Translate\n\n"
            "🧮 /calc [expression] - Calculator\n\n"
            "🔑 /password [length] - Password",
            get_help_keyboard(is_admin)
        ),
        "help_games": (
            "🎲 <b>Games:</b>\n\n"
            "🎲 /random [min] [max] - Random\n\n"
            "🎯 /dice - Dice\n\n"
            "🪙 /coin - Coin\n\n"
            "😄 /joke - Joke\n\n"
            "💭 /quote - Quote\n\n"
            "🔬 /fact - Fact",
            get_help_keyboard(is_admin)
        ),
        "help_vip": (
            "💎 <b>VIP Commands:</b>\n\n"
            "👑 /vip - VIP status\n\n"
            "🖼️ /generate [description] - Generate image\n\n"
            "⏰ /remind [minutes] [text] - Reminder\n\n"
            "📋 /reminders - List reminders\n\n"
            "📎 Send file - Analysis (VIP)\n\n"
            "📸 Send photo - Analysis (VIP)",
            get_help_keyboard(is_admin)
        )
    }

    if data == "help_admin" and is_admin:
        text = "👑 <b>Creator Commands:</b>\n\n" \
               "🎁 /grant_vip [id/@username] [period] - Grant VIP\n\n" \
               "❌ /revoke_vip [id/@username] - Revoke VIP\n\n" \
               "👥 /users - Users list\n\n" \
               "📢 /broadcast [text] - Broadcast\n\n" \
               "📈 /stats - Statistics\n\n" \
               "💾 /backup - Backup"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_back")]])
    elif data in sections:
        text, markup = sections[data]
    else:
        await query.edit_message_text("❌ Section not found.")
        return

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text
    user = storage.get_user(user_id)
    storage.update_user(user_id, {
        'messages_count': user.get('messages_count', 0) + 1, 
        'username': update.effective_user.username or '', 
        'first_name': update.effective_user.first_name or ''
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # Menu buttons
    menu_buttons = [
        get_text(user_id, key) for key in ['ai_chat', 'notes', 'weather', 'time', 'entertainment', 'info', 'vip_menu', 'admin_panel', 'generation']
    ]
    
    if text in menu_buttons:
        await handle_menu_button(update, context, text, user_id)
        return
    
    # Groups - only by mention
    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()
    
    # AI response
    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str, user_id: int):
    if button == get_text(user_id, 'ai_chat'):
        await update.message.reply_text("🤖 <b>AI Chat</b>\n\nJust write - I'll answer!\n/clear - clear context", parse_mode=ParseMode.HTML)
    elif button == get_text(user_id, 'notes'):
        keyboard = [[InlineKeyboardButton("➕ Create", callback_data="note_create")], [InlineKeyboardButton("📋 List", callback_data="note_list")]]
        await update.message.reply_text("📝 <b>Notes</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == get_text(user_id, 'weather'):
        await update.message.reply_text("🌍 <b>Weather</b>\n\n/weather [city]\nExample: /weather London", parse_mode=ParseMode.HTML)
    elif button == get_text(user_id, 'time'):
        await update.message.reply_text("⏰ <b>Time</b>\n\n/time [city]\nExample: /time Tokyo", parse_mode=ParseMode.HTML)
    elif button == get_text(user_id, 'entertainment'):
        keyboard = [[InlineKeyboardButton("🎲 Dice", callback_data="game_dice"), InlineKeyboardButton("🪙 Coin", callback_data="game_coin")],
                    [InlineKeyboardButton("😄 Joke", callback_data="game_joke"), InlineKeyboardButton("💭 Quote", callback_data="game_quote")],
                    [InlineKeyboardButton("🔬 Fact", callback_data="game_fact")]]
        await update.message.reply_text("🎲 <b>Games</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == get_text(user_id, 'info'):
        await info_command(update, context)
    elif button == get_text(user_id, 'vip_menu'):
        if storage.is_vip(user_id):
            keyboard = [[InlineKeyboardButton("⏰ Reminders", callback_data="vip_reminders")], [InlineKeyboardButton("📊 Stats", callback_data="vip_stats")]]
            await update.message.reply_text("💎 <b>VIP Menu</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await vip_command(update, context)
    elif button == get_text(user_id, 'admin_panel'):
        if is_creator(user_id):
            keyboard = [[InlineKeyboardButton("👥 Users", callback_data="admin_users")], [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")], [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]]
            await update.message.reply_text("👑 <b>Admin Panel</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == get_text(user_id, 'generation'):
        if storage.is_vip(user_id):
            await update.message.reply_text(get_text(user_id, 'generating_prompt'), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(get_text(user_id, 'vip_only', creator=CREATOR_USERNAME))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    identify_creator(query.from_user)
    user_id = query.from_user.id
    
    # Language change
    if data.startswith("lang_"):
        lang = data.split("_")[1]
        storage.update_user(user_id, {'language': lang})
        await query.edit_message_text(
            get_text(user_id, 'language_changed'),
            parse_mode=ParseMode.HTML
        )
        await query.message.reply_text(
            get_text(user_id, 'welcome', name=query.from_user.first_name, creator=CREATOR_USERNAME),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    # Help callbacks
    if data.startswith("help_"):
        await handle_help_callback(update, context)
        return
    
    if data == "note_create":
        await query.edit_message_text("➕ <b>Create note</b>\n\n/note [text]\nExample: /note Buy bread", parse_mode=ParseMode.HTML)
    elif data == "note_list":
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        if not notes:
            await query.edit_message_text("📭 No notes.")
            return
        notes_text = f"📝 <b>Notes ({len(notes)}):</b>\n\n"
        for i, note in enumerate(notes, 1):
            created = datetime.fromisoformat(note['created'])
            notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m')})\n{note['text']}\n\n"
        await query.edit_message_text(notes_text, parse_mode=ParseMode.HTML)
    elif data == "game_dice":
        await dice_command(update, context)
    elif data == "game_coin":
        await coin_command(update, context)
    elif data == "game_joke":
        await joke_command(update, context)
    elif data == "game_quote":
        await quote_command(update, context)
    elif data == "game_fact":
        await fact_command(update, context)
    elif data == "vip_reminders":
        await reminders_command(update, context)
    elif data == "vip_stats":
        await profile_command(update, context)
    elif data == "admin_users":
        if is_creator(user_id):
            await users_command(update, context)
    elif data == "admin_stats":
        if is_creator(user_id):
            await stats_command(update, context)
    elif data == "admin_broadcast":
        if is_creator(user_id):
            await query.edit_message_text("📢 <b>Broadcast</b>\n\n/broadcast [text]\nExample: /broadcast Hello everyone!", parse_mode=ParseMode.HTML)

def signal_handler(signum, frame):
    logger.info("Signal received. Stopping bot...")
    scheduler.shutdown()
    raise SystemExit

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("language", language_command))
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
    
    application.add_handler(CommandHandler("todo", todo_command))
    
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("password", password_command))
    
    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("fact", fact_command))
    
    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("generate", generate_command))
    
    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("backup", backup_command))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Start scheduler
    scheduler.start()
    
    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT STARTED!")
    logger.info("🤖 Model: Gemini 2.5 Flash")
    logger.info("🖼️ Image Gen: Stable Diffusion XL")
    logger.info("🔍 Analysis: Gemini Vision")
    logger.info("🎙️ Transcription: Gemini 2.5 Flash")
    logger.info("🌍 Languages: Russian, English, Italian")
    logger.info("🗄️ DB: " + ("PostgreSQL ✓" if engine else "Local JSON"))
    logger.info("=" * 50)
    
    # Graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
