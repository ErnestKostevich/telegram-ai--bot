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
import fitz # PyMuPDF
import docx # python-docx
import base64

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
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

system_instruction = (
    "You are AI DISCO BOT, a friendly and helpful AI assistant built with Gemini 2.5. "
    "Respond in the user's preferred language in a friendly, engaging manner with emojis where appropriate. "
    "Your creator is @Ernest_Kostevich."
)

# Модель Gemini 2.5 Flash
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction=system_instruction
)

# Модель для Vision (VIP)
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
                    'commands_count': user.commands_count or 0,
                    'language': user.language or 'ru'
                }
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

def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Создатель: {user.id}")

def is_creator(user_id: int) -> bool:
    return user_id == CREATOR_ID

# Мультиязычные переводы
translations = {
    'ru': {
        'ai_chat': "💬 AI Чат",
        'notes': "📝 Заметки",
        'weather': "🌍 Погода",
        'time': "⏰ Время",
        'entertainment': "🎲 Развлечения",
        'info': "ℹ️ Инфо",
        'vip_menu': "💎 VIP Меню",
        'generation': "🖼️ Генерация",
        'admin_panel': "👑 Админ Панель",
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nПривет, {name}! Я бот на <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Возможности:</b>\n💬 AI-чат с контекстом\n📝 Заметки и задачи\n🌍 Погода и время\n🎲 Развлечения\n📎 Анализ файлов (VIP)\n🔍 Анализ изображений (VIP)\n🖼️ Генерация изображений (VIP)\n\n<b>⚡ Команды:</b>\n/help - Все команды\n/vip - Статус VIP\n\n<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}"""
    },
    'en': {
        'ai_chat': "💬 AI Chat",
        'notes': "📝 Notes",
        'weather': "🌍 Weather",
        'time': "⏰ Time",
        'entertainment': "🎲 Entertainment",
        'info': "ℹ️ Info",
        'vip_menu': "💎 VIP Menu",
        'generation': "🖼️ Generation",
        'admin_panel': "👑 Admin Panel",
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nHello, {name}! I'm a bot powered by <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Features:</b>\n💬 AI chat with context\n📝 Notes and tasks\n🌍 Weather and time\n🎲 Entertainment\n📎 File analysis (VIP)\n🔍 Image analysis (VIP)\n🖼️ Image generation (VIP)\n\n<b>⚡ Commands:</b>\n/help - All commands\n/vip - VIP status\n\n<b>👨‍💻 Creator:</b> @{CREATOR_USERNAME}"""
    },
    'es': {
        'ai_chat': "💬 Chat IA",
        'notes': "📝 Notas",
        'weather': "🌍 Clima",
        'time': "⏰ Hora",
        'entertainment': "🎲 Entretenimiento",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menú VIP",
        'generation': "🖼️ Generación",
        'admin_panel': "👑 Panel Admin",
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\n¡Hola, {name}! Estoy impulsado por <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Características:</b>\n💬 Chat IA con contexto\n📝 Notas y tareas\n🌍 Clima y hora\n🎲 Entretenimiento\n📎 Análisis de archivos (VIP)\n🔍 Análisis de imágenes (VIP)\n🖼️ Generación de imágenes (VIP)\n\n<b>⚡ Comandos:</b>\n/help - Todos los comandos\n/vip - Estado VIP\n\n<b>👨‍💻 Creador:</b> @{CREATOR_USERNAME}"""
    },
    'de': {
        'ai_chat': "💬 KI-Chat",
        'notes': "📝 Notizen",
        'weather': "🌍 Wetter",
        'time': "⏰ Zeit",
        'entertainment': "🎲 Unterhaltung",
        'info': "ℹ️ Info",
        'vip_menu': "💎 VIP-Menü",
        'generation': "🖼️ Generierung",
        'admin_panel': "👑 Admin-Panel",
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nHallo, {name}! Ich werde von <b>Gemini 2.5 Flash</b> angetrieben.\n\n<b>🎯 Funktionen:</b>\n💬 KI-Chat mit Kontext\n📝 Notizen und Aufgaben\n🌍 Wetter und Zeit\n🎲 Unterhaltung\n📎 Dateianalyse (VIP)\n🔍 Bildanalyse (VIP)\n🖼️ Bildgenerierung (VIP)\n\n<b>⚡ Befehle:</b>\n/help - Alle Befehle\n/vip - VIP-Status\n\n<b>👨‍💻 Ersteller:</b> @{CREATOR_USERNAME}"""
    },
    'it': {
        'ai_chat': "💬 Chat AI",
        'notes': "📝 Note",
        'weather': "🌍 Meteo",
        'time': "⏰ Tempo",
        'entertainment': "🎲 Intrattenimento",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menu VIP",
        'generation': "🖼️ Generazione",
        'admin_panel': "👑 Pannello Admin",
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nCiao, {name}! Sono alimentato da <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Funzionalità:</b>\n💬 Chat AI con contesto\n📝 Note e compiti\n🌍 Meteo e ora\n🎲 Intrattenimento\n📎 Analisi file (VIP)\n🔍 Analisi immagini (VIP)\n🖼️ Generazione immagini (VIP)\n\n<b>⚡ Comandi:</b>\n/help - Tutti i comandi\n/vip - Stato VIP\n\n<b>👨‍💻 Creatore:</b> @{CREATOR_USERNAME}"""
    },
    'fr': {
        'ai_chat': "💬 Chat IA",
        'notes': "📝 Notes",
        'weather': "🌍 Météo",
        'time': "⏰ Temps",
        'entertainment': "🎲 Divertissement",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menu VIP",
        'generation': "🖼️ Génération",
        'admin_panel': "👑 Panneau Admin",
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nBonjour, {name}! Je suis alimenté par <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Fonctionnalités:</b>\n💬 Chat IA avec contexte\n📝 Notes et tâches\n🌍 Météo et heure\n🎲 Divertissement\n📎 Analyse de fichiers (VIP)\n🔍 Analyse d'images (VIP)\n🖼️ Génération d'images (VIP)\n\n<b>⚡ Commandes:</b>\n/help - Toutes les commandes\n/vip - Statut VIP\n\n<b>👨‍💻 Créateur:</b> @{CREATOR_USERNAME}"""
    }
}

def get_text(lang: str, key: str, **kwargs):
    return translations.get(lang, translations['ru']).get(key, key).format(**kwargs)

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    lang = storage.get_user(user_id)['language']
    keyboard = [
        [KeyboardButton(get_text(lang, 'ai_chat')), KeyboardButton(get_text(lang, 'notes'))],
        [KeyboardButton(get_text(lang, 'weather')), KeyboardButton(get_text(lang, 'time'))],
        [KeyboardButton(get_text(lang, 'entertainment')), KeyboardButton(get_text(lang, 'info'))]
    ]
    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton(get_text(lang, 'vip_menu')), KeyboardButton(get_text(lang, 'generation'))])
    if is_creator(user_id):
        keyboard.append([KeyboardButton(get_text(lang, 'admin_panel'))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def generate_image_pollinations(prompt: str) -> Optional[str]:
    try:
        encoded_prompt = urlquote(prompt)
        return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
    except Exception as e:
        logger.warning(f"Ошибка генерации изображения: {e}")
        return None

async def analyze_image_with_gemini(image_bytes: bytes, prompt: str = "Опиши подробно что изображено") -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = vision_model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка анализа: {str(e)}"

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
        await update.message.reply_text("💎 Анализ файлов доступен только VIP-пользователям.\n\nСвяжитесь с @Ernest_Kostevich")
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
        await update.message.reply_text("💎 Анализ изображений для VIP.\n\nСвяжитесь с @Ernest_Kostevich")
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    lang = user.language_code[:2] if user.language_code and user.language_code[:2] in translations else 'ru'
    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {'username': user.username or '', 'first_name': user.first_name or '', 'language': lang, 'commands_count': user_data.get('commands_count', 0) + 1})
    welcome_text = get_text(lang, 'welcome', name=user.first_name)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id))

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Генерация для VIP.\n\nСвяжитесь с @Ernest_Kostevich")
        return
    if not context.args:
        await update.message.reply_text("❓ /generate [описание]\n\nПример: /generate закат над океаном")
        return
    prompt = ' '.join(context.args)
    await update.message.reply_text("🎨 Генерирую...")
    try:
        image_url = await generate_image_pollinations(prompt)
        if image_url:
            await update.message.reply_photo(photo=image_url, caption=f"🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Ошибка генерации")
    except Exception as e:
        logger.warning(f"Ошибка генерации: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

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
        await update.message.reply_text(response.text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"AI: {e}")
        await update.message.reply_text("😔 Ошибка")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_chat_session(update.effective_user.id)
    await update.message.reply_text("🧹 Контекст очищен!")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""🤖 <b>AI DISCO BOT</b>\n\n<b>Версия:</b> 3.0\n<b>AI:</b> Gemini 2.5 Flash\n<b>Создатель:</b> @Ernest_Kostevich\n\n<b>⚡ Особенности:</b>\n• Быстрый AI-чат\n• PostgreSQL\n• VIP функции\n• Анализ файлов/фото (VIP)\n• Генерация изображений (VIP)\n\n<b>💬 Поддержка:</b> @Ernest_Kostevich""", parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = storage.stats
    all_users = storage.get_all_users()
    uptime = datetime.now() - BOT_START_TIME
    status_text = f"""📊 <b>СТАТУС</b>\n\n<b>👥 Пользователи:</b> {len(all_users)}\n<b>💎 VIP:</b> {sum(1 for u in all_users.values() if u.get('vip', False))}\n\n<b>📈 Активность:</b>\n• Сообщений: {stats.get('total_messages', 0)}\n• Команд: {stats.get('total_commands', 0)}\n• AI запросов: {stats.get('ai_requests', 0)}\n\n<b>⏱ Работает:</b> {uptime.days}д {uptime.seconds // 3600}ч\n\n<b>✅ Статус:</b> Онлайн\n<b>🤖 AI:</b> Gemini 2.5 ✓\n<b>🗄️ БД:</b> {'PostgreSQL ✓' if engine else 'JSON'}"""
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = storage.get_user(update.effective_user.id)
    profile_text = f"""👤 <b>{user.get('first_name', 'User')}</b>\n🆔 <code>{user.get('id')}</code>\n"""
    if user.get('username'):
        profile_text += f"📱 @{user['username']}\n"
    profile_text += f"""\n📅 {user.get('registered', '')[:10]}\n📊 Сообщений: {user.get('messages_count', 0)}\n🎯 Команд: {user.get('commands_count', 0)}\n📝 Заметок: {len(user.get('notes', []))}"""
    if storage.is_vip(update.effective_user.id):
        vip_until = user.get('vip_until')
        if vip_until:
            profile_text += f"\n💎 VIP до: {datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')}"
        else:
            profile_text += "\n💎 VIP: Навсегда ♾️"
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - BOT_START_TIME
    await update.message.reply_text(f"""⏱ <b>ВРЕМЯ РАБОТЫ</b>\n\n🕐 Запущен: {BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S')}\n⏰ Работает: {uptime.days}д {uptime.seconds // 3600}ч {(uptime.seconds % 3600) // 60}м\n\n✅ Онлайн""", parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = storage.get_user(update.effective_user.id)
    if storage.is_vip(update.effective_user.id):
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n✅ Активен!\n\n"
        vip_until = user.get('vip_until')
        if vip_until:
            vip_text += f"⏰ До: {datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')}\n\n"
        else:
            vip_text += "⏰ Навсегда ♾️\n\n"
        vip_text += "<b>🎁 Преимущества:</b>\n• ⏰ Напоминания\n• 🖼️ Генерация изображений\n• 🔍 Анализ изображений\n• 📎 Анализ документов"
    else:
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n❌ Нет VIP.\n\nСвяжитесь с @Ernest_Kostevich"
    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /note [текст]")
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
        await update.message.reply_text("📭 Нет заметок.")
        return
    notes_text = f"📝 <b>Заметки ({len(notes)}):</b>\n\n"
    for i, note in enumerate(notes, 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y')})\n{note['text']}\n\n"
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /delnote [номер]")
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
        await update.message.reply_text("❌ Укажите номер.")

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
    user = storage.get_user(update.effective_user.id)
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

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /todo add [текст] | list | del [номер]")
        return
    subcommand = context.args[0].lower()
    user = storage.get_user(user_id)
    if subcommand == 'add':
        if len(context.args) < 2:
            await update.message.reply_text("❓ /todo add [текст]")
            return
        todo_text = ' '.join(context.args[1:])
        todo = {'text': todo_text, 'created': datetime.now().isoformat()}
        todos = user.get('todos', [])
        todos.append(todo)
        storage.update_user(user_id, {'todos': todos})
        await update.message.reply_text(f"✅ Задача #{len(todos)} добавлена!\n\n📋 {todo_text}")
    elif subcommand == 'list':
        todos = user.get('todos', [])
        if not todos:
            await update.message.reply_text("📭 Нет задач.")
            return
        todos_text = f"📋 <b>Задачи ({len(todos)}):</b>\n\n"
        for i, todo in enumerate(todos, 1):
            created = datetime.fromisoformat(todo['created'])
            todos_text += f"<b>#{i}</b> ({created.strftime('%d.%m')})\n{todo['text']}\n\n"
        await update.message.reply_text(todos_text, parse_mode=ParseMode.HTML)
    elif subcommand == 'del':
        if len(context.args) < 2:
            await update.message.reply_text("❓ /todo del [номер]")
            return
        try:
            todo_num = int(context.args[1])
            todos = user.get('todos', [])
            if 1 <= todo_num <= len(todos):
                deleted_todo = todos.pop(todo_num - 1)
                storage.update_user(user_id, {'todos': todos})
                await update.message.reply_text(f"✅ Задача #{todo_num} удалена:\n\n📋 {deleted_todo['text']}")
            else:
                await update.message.reply_text(f"❌ Задача #{todo_num} не найдена.")
        except ValueError:
            await update.message.reply_text("❌ Укажите номер.")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = ' '.join(context.args) if context.args else 'Moscow'
    timezones = {
        'moscow': 'Europe/Moscow', 'london': 'Europe/London', 'new york': 'America/New_York',
        'tokyo': 'Asia/Tokyo', 'paris': 'Europe/Paris', 'berlin': 'Europe/Berlin',
        'dubai': 'Asia/Dubai', 'sydney': 'Australia/Sydney', 'los angeles': 'America/Los_Angeles'
    }
    tz_name = timezones.get(city.lower(), 'Europe/Moscow')
    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        await update.message.reply_text(f"""⏰ <b>{city.title()}</b>\n\n🕐 Время: {current_time.strftime('%H:%M:%S')}\n📅 Дата: {current_time.strftime('%d.%m.%Y')}\n🌍 Пояс: {tz_name}""", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка времени: {e}")
        await update.message.reply_text(f"❌ Город '{city}' не найден.")

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
                    weather_text = f"""🌍 <b>{city.title()}</b>\n\n🌡 Температура: {temp_c}°C\n🤔 Ощущается: {feels_like}°C\n☁️ {description}\n💧 Влажность: {humidity}%\n💨 Ветер: {wind_speed} км/ч"""
                    await update.message.reply_text(weather_text, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(f"❌ Город '{city}' не найден.")
    except Exception as e:
        logger.warning(f"Ошибка погоды: {e}")
        await update.message.reply_text("❌ Ошибка получения погоды.")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❓ /translate [язык] [текст]\n\nПример: /translate en Привет")
        return
    target_lang = context.args[0]
    text = ' '.join(context.args[1:])
    try:
        prompt = f"Переведи на {target_lang}: {text}"
        chat = storage.get_chat_session(update.effective_user.id)
        response = chat.send_message(prompt)
        await update.message.reply_text(f"🌐 <b>Перевод:</b>\n\n{response.text}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка перевода: {e}")
        await update.message.reply_text("❌ Ошибка перевода.")

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ /calc [выражение]\n\nПример: /calc 2+2*5")
        return
    expression = ' '.join(context.args)
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        await update.message.reply_text(f"🧮 <b>Результат:</b>\n\n{expression} = <b>{result}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка расчета: {e}")
        await update.message.reply_text("❌ Ошибка вычисления.")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text("❌ Длина от 8 до 50.")
            return
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(f"🔑 <b>Пароль:</b>\n\n<code>{password}</code>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ Укажите длину.")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) >= 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        else:
            min_val = 1
            max_val = 100
        result = random.randint(min_val, max_val)
        await update.message.reply_text(f"🎲 Число от {min_val} до {max_val}:\n\n<b>{result}</b>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ Укажите числа.")

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    await update.message.reply_text(f"🎲 {dice_emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(['Орёл', 'Решка'])
    emoji = '🦅' if result == 'Орёл' else '💰'
    await update.message.reply_text(f"🪙 {emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Программист ложится спать. Жена: — Закрой окно, холодно! Программист: — И что, если я закрою окно, станет тепло? 😄",
        "— Почему программисты путают Хэллоуин и Рождество? — 31 OCT = 25 DEC! 🎃",
        "Зачем программисту очки? Чтобы лучше C++! 👓",
        "— Сколько программистов нужно, чтобы вкрутить лампочку? — Ни одного, это аппаратная проблема! 💡"
    ]
    await update.message.reply_text(f"😄 <b>Шутка:</b>\n\n{random.choice(jokes)}", parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
        "Инновация отличает лидера от последователя. — Стив Джобс",
        "Программирование — это искусство превращать кофе в код. — Неизвестный",
        "Простота — залог надёжности. — Эдсгер Дейкстра"
    ]
    await update.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{random.choice(quotes)}</i>", parse_mode=ParseMode.HTML)

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = [
        "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
        "🐙 У осьминогов три сердца и голубая кровь.",
        "🍯 Мёд не портится тысячи лет.",
        "💎 Алмазы формируются на глубине ~150 км.",
        "🧠 Мозг потребляет ~20% энергии тела.",
        "⚡ Молния в 5 раз горячее Солнца."
    ]
    await update.message.reply_text(f"🔬 <b>Факт:</b>\n\n{random.choice(facts)}", parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Напоминания для VIP.\n\nСвяжитесь с @Ernest_Kostevich")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❓ /remind [минуты] [текст]")
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
        await update.message.reply_text(f"⏰ Напоминание создано!\n\n📝 {text}\n🕐 Через {minutes} минут")
    except ValueError:
        await update.message.reply_text("❌ Укажите минуты.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Напоминания для VIP.")
        return
    user = storage.get_user(user_id)
    reminders = user.get('reminders', [])
    if not reminders:
        await update.message.reply_text("📭 Нет напоминаний.")
        return
    reminders_text = f"⏰ <b>Напоминания ({len(reminders)}):</b>\n\n"
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
        logger.warning(f"Ошибка отправки напоминания: {e}")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Только для создателя.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❓ /grant_vip [id/@username] [срок]\n\nСроки: week, month, year, forever")
        return
    try:
        identifier = context.args[0]
        duration = context.args[1].lower()
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
            return
        durations = {'week': timedelta(weeks=1), 'month': timedelta(days=30), 'year': timedelta(days=365), 'forever': None}
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
        await update.message.reply_text(f"✅ VIP выдан!\n\n🆔 <code>{target_id}</code>\n⏰ {duration_text}", parse_mode=ParseMode.HTML)
        try:
            await context.bot.send_message(chat_id=target_id, text=f"🎉 VIP статус выдан {duration_text}!", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Ошибка уведомления о VIP: {e}")
    except Exception as e:
        logger.warning(f"Ошибка grant_vip: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Только для создателя.")
        return
    if not context.args:
        await update.message.reply_text("❓ /revoke_vip [id/@username]")
        return
    try:
        identifier = context.args[0]
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
            return
        storage.update_user(target_id, {'vip': False, 'vip_until': None})
        await update.message.reply_text(f"✅ VIP отозван!\n\n🆔 <code>{target_id}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка revoke_vip: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Только для создателя.")
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
        await update.message.reply_text("❌ Только для создателя.")
        return
    if not context.args:
        await update.message.reply_text("❓ /broadcast [текст]")
        return
    message_text = ' '.join(context.args)
    success = 0
    failed = 0
    status_msg = await update.message.reply_text("📤 Рассылка...")
    all_users = storage.get_all_users()
    for user_id in all_users.keys():
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 <b>От создателя:</b>\n\n{message_text}", parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Ошибка рассылки пользователю {user_id}: {e}")
            failed += 1
    await status_msg.edit_text(f"✅ Завершено!\n\n✅ Успешно: {success}\n❌ Ошибок: {failed}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Только для создателя.")
        return
    stats = storage.stats
    all_users = storage.get_all_users()
    stats_text = f"""📊 <b>СТАТИСТИКА</b>\n\n<b>👥 Пользователи:</b> {len(all_users)}\n<b>💎 VIP:</b> {sum(1 for u in all_users.values() if u.get('vip', False))}\n\n<b>📈 Активность:</b>\n• Сообщений: {stats.get('total_messages', 0)}\n• Команд: {stats.get('total_commands', 0)}\n• AI запросов: {stats.get('ai_requests', 0)}"""
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Только для создателя.")
        return
    try:
        backup_data = {'users': storage.get_all_users(), 'stats': storage.stats, 'backup_date': datetime.now().isoformat()}
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        await update.message.reply_document(document=open(backup_filename, 'rb'), caption=f"✅ Резервная копия\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        os.remove(backup_filename)
    except Exception as e:
        logger.warning(f"Ошибка бэкапа: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text
    user = storage.get_user(user_id)
    storage.update_user(user_id, {'messages_count': user.get('messages_count', 0) + 1, 'username': update.effective_user.username or '', 'first_name': update.effective_user.first_name or ''})
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()

    # Кнопки меню
    if text in [get_text(user['language'], key) for key in ['ai_chat', 'notes', 'weather', 'time', 'entertainment', 'info', 'vip_menu', 'generation', 'admin_panel']]:
        await handle_menu_button(update, context, text)
        return

    # В группах только по упоминанию
    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    # AI ответ
    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str):
    user_id = update.effective_user.id
    lang = storage.get_user(user_id)['language']
    if button == get_text(lang, 'ai_chat'):
        await update.message.reply_text("💬 <b>AI Чат</b>\n\nПросто пиши - я отвечу!\n/clear - очистить контекст", parse_mode=ParseMode.HTML)
    elif button == get_text(lang, 'notes'):
        keyboard = [[InlineKeyboardButton("➕ Создать", callback_data="note_create")], [InlineKeyboardButton("📋 Список", callback_data="note_list")]]
        await update.message.reply_text("📝 <b>Заметки</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == get_text(lang, 'weather'):
        await update.message.reply_text("🌍 <b>Погода</b>\n\n/weather [город]\nПример: /weather London", parse_mode=ParseMode.HTML)
    elif button == get_text(lang, 'time'):
        await update.message.reply_text("⏰ <b>Время</b>\n\n/time [город]\nПример: /time Tokyo", parse_mode=ParseMode.HTML)
    elif button == get_text(lang, 'entertainment'):
        keyboard = [[InlineKeyboardButton("🎲 Кубик", callback_data="game_dice"), InlineKeyboardButton("🪙 Монета", callback_data="game_coin")],
                    [InlineKeyboardButton("😄 Шутка", callback_data="game_joke"), InlineKeyboardButton("💭 Цитата", callback_data="game_quote")],
                    [InlineKeyboardButton("🔬 Факт", callback_data="game_fact")]]
        await update.message.reply_text("🎲 <b>Развлечения</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == get_text(lang, 'info'):
        await info_command(update, context)
    elif button == get_text(lang, 'vip_menu'):
        if storage.is_vip(user_id):
            keyboard = [[InlineKeyboardButton("⏰ Напоминания", callback_data="vip_reminders")], [InlineKeyboardButton("📊 Статистика", callback_data="vip_stats")]]
            await update.message.reply_text("💎 <b>VIP Меню</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await vip_command(update, context)
    elif button == get_text(lang, 'admin_panel'):
        if is_creator(user_id):
            keyboard = [[InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")], [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")], [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")]]
            await update.message.reply_text("👑 <b>Админ Панель</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == get_text(lang, 'generation'):
        if storage.is_vip(user_id):
            await update.message.reply_text("🖼️ <b>Генерация (VIP)</b>\n\n/generate [описание]\n\nПримеры:\n• /generate закат\n• /generate город\n\n💡 Pollinations AI", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("💎 Генерация для VIP")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    identify_creator(query.from_user)

    if data.startswith("help_"):
        await handle_help_callback(update, context)
        return

    if data == "note_create":
        await query.message.reply_text("➕ <b>Создать заметку</b>\n\n/note [текст]\nПример: /note Купить хлеб", parse_mode=ParseMode.HTML)
    elif data == "note_list":
        user_id = query.from_user.id
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        if not notes:
            await query.message.reply_text("📭 Нет заметок.")
            return
        notes_text = f"📝 <b>Заметки ({len(notes)}):</b>\n\n"
        for i, note in enumerate(notes, 1):
            created = datetime.fromisoformat(note['created'])
            notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m')})\n{note['text']}\n\n"
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
        jokes = ["Программист ложится спать. Жена: — Закрой окно, холодно! Программист: — И что, если я закрою окно, станет тепло? 😄",
                 "— Почему программисты путают Хэллоуин и Рождество? — 31 OCT = 25 DEC! 🎃", "Зачем программисту очки? Чтобы лучше C++! 👓"]
        await query.message.reply_text(f"😄 <b>Шутка:</b>\n\n{random.choice(jokes)}", parse_mode=ParseMode.HTML)
    elif data == "game_quote":
        quotes = ["Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
                  "Инновация отличает лидера от последователя. — Стив Джобс", "Простота — залог надёжности. — Эдсгер Дейкстра"]
        await query.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{random.choice(quotes)}</i>", parse_mode=ParseMode.HTML)
    elif data == "game_fact":
        facts = ["🌍 Земля — единственная планета не в честь бога.", "🐙 У осьминогов три сердца.", "🍯 Мёд не портится тысячи лет."]
        await query.message.reply_text(f"🔬 <b>Факт:</b>\n\n{random.choice(facts)}", parse_mode=ParseMode.HTML)
    elif data == "vip_reminders":
        await reminders_command(query, context)
    elif data == "vip_stats":
        await profile_command(query, context)
    elif data == "admin_users":
        if is_creator(query.from_user.id):
            await users_command(query, context)
    elif data == "admin_stats":
        if is_creator(query.from_user.id):
            await stats_command(query, context)
    elif data == "admin_broadcast":
        if is_creator(query.from_user.id):
            await query.message.reply_text("📢 <b>Рассылка</b>\n\n/broadcast [текст]\nПример: /broadcast Привет всем!", parse_mode=ParseMode.HTML)

def signal_handler(signum, frame):
    logger.info("Получен сигнал завершения. Останавливаем бота...")
    scheduler.shutdown()
    raise SystemExit

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Команды
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

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск scheduler
    scheduler.start()

    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН!")
    logger.info("🤖 Модель: Gemini 2.5 Flash")
    logger.info("🗄️ БД: " + ("PostgreSQL ✓" if engine else "Local JSON"))
    logger.info("🖼️ Генерация: Pollinations AI")
    logger.info("🔍 Анализ: Gemini Vision")
    logger.info("=" * 50)

    # Graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
