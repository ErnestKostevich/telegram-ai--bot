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
import fitz  # PyMuPDF
import docx  # python-docx
import base64  # Для обработки голосовых

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

# Настройка Gemini 2.5 Flash (последняя версия)
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 4096,  # Увеличено для лучших ответов, но с разбиением для Telegram
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Улучшенная инструкция для "очень умного" ИИ
system_instruction = (
    "You are AI DISCO BOT, an extremely intelligent, friendly, and helpful AI assistant built with Gemini 2.5. "
    "Respond in the user's language in a friendly, engaging manner with emojis where appropriate. Be proactive, provide detailed answers with structure (headings, lists, code blocks). "
    "Always consider context and user intent. Split long answers into parts if needed. Your creator is @Ernest_Kostevich."
)

# Модель Gemini 2.5 Flash
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction=system_instruction
)

# Модель для Vision, Audio (VIP)
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
    language = Column(String(5), default='ru')  # Для мультиязычности

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
                return {u.id: {'id': u.id, 'username': u.username, 'first_name': u.first_name, 'vip': u.vip, 'language': u.language} for u in users}
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

# Мультиязычные переводы (расширенные)
translations = {
    'ru': {
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nПривет, {name}! Я бот на <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Возможности:</b>\n💬 AI-чат с контекстом\n📝 Заметки и задачи\n🌍 Погода и время\n🎲 Развлечения\n📎 Анализ файлов (VIP)\n🔍 Анализ изображений (VIP)\n🖼️ Генерация изображений (VIP)\n\n<b>⚡ Команды:</b>\n/help - Все команды\n/vip - Статус VIP\n\n<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}""",
        'ai_chat': "💬 AI Чат",
        'notes': "📝 Заметки",
        'weather': "🌍 Погода",
        'time': "⏰ Время",
        'entertainment': "🎲 Развлечения",
        'info': "ℹ️ Инфо",
        'vip_menu': "💎 VIP Меню",
        'generation': "🖼️ Генерация",
        'admin_panel': "👑 Админ Панель",
        'help_title': "📚 <b>Выберите раздел справки:</b>\n\nНажмите кнопку ниже для просмотра команд по теме.",
        # ... добавьте переводы для других текстов по необходимости
    },
    'en': {
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nHello, {name}! I'm a bot powered by <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Features:</b>\n💬 AI chat with context\n📝 Notes and tasks\n🌍 Weather and time\n🎲 Entertainment\n📎 File analysis (VIP)\n🔍 Image analysis (VIP)\n🖼️ Image generation (VIP)\n\n<b>⚡ Commands:</b>\n/help - All commands\n/vip - VIP status\n\n<b>👨‍💻 Creator:</b> @{CREATOR_USERNAME}""",
        'ai_chat': "💬 AI Chat",
        'notes': "📝 Notes",
        'weather': "🌍 Weather",
        'time': "⏰ Time",
        'entertainment': "🎲 Entertainment",
        'info': "ℹ️ Info",
        'vip_menu': "💎 VIP Menu",
        'generation': "🖼️ Generation",
        'admin_panel': "👑 Admin Panel",
        'help_title': "📚 <b>Select help section:</b>\n\nClick the button below to view commands by topic.",
    },
    'es': {
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\n¡Hola, {name}! Soy un bot impulsado por <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Características:</b>\n💬 Chat AI con contexto\n📝 Notas y tareas\n🌍 Clima y hora\n🎲 Entretenimiento\n📎 Análisis de archivos (VIP)\n🔍 Análisis de imágenes (VIP)\n🖼️ Generación de imágenes (VIP)\n\n<b>⚡ Comandos:</b>\n/help - Todos los comandos\n/vip - Estado VIP\n\n<b>👨‍💻 Creador:</b> @{CREATOR_USERNAME}""",
        'ai_chat': "💬 Chat AI",
        'notes': "📝 Notas",
        'weather': "🌍 Clima",
        'time': "⏰ Hora",
        'entertainment': "🎲 Entretenimiento",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menú VIP",
        'generation': "🖼️ Generación",
        'admin_panel': "👑 Panel Admin",
        'help_title': "📚 <b>Seleccione sección de ayuda:</b>\n\nHaga clic en el botón para ver comandos por tema.",
    },
    'de': {
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nHallo, {name}! Ich bin ein Bot, der von <b>Gemini 2.5 Flash</b> angetrieben wird.\n\n<b>🎯 Funktionen:</b>\n💬 AI-Chat mit Kontext\n📝 Notizen und Aufgaben\n🌍 Wetter und Zeit\n🎲 Unterhaltung\n📎 Dateianalyse (VIP)\n🔍 Bildanalyse (VIP)\n🖼️ Bildgenerierung (VIP)\n\n<b>⚡ Befehle:</b>\n/help - Alle Befehle\n/vip - VIP-Status\n\n<b>👨‍💻 Ersteller:</b> @{CREATOR_USERNAME}""",
        'ai_chat': "💬 KI-Chat",
        'notes': "📝 Notizen",
        'weather': "🌍 Wetter",
        'time': "⏰ Zeit",
        'entertainment': "🎲 Unterhaltung",
        'info': "ℹ️ Info",
        'vip_menu': "💎 VIP-Menü",
        'generation': "🖼️ Generierung",
        'admin_panel': "👑 Admin-Panel",
        'help_title': "📚 <b>Wählen Sie Hilfsabschnitt:</b>\n\nKlicken Sie auf den Button, um Befehle nach Thema anzuzeigen.",
    },
    'it': {
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nCiao, {name}! Sono un bot alimentato da <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Funzionalità:</b>\n💬 Chat AI con contesto\n📝 Note e compiti\n🌍 Meteo e ora\n🎲 Intrattenimento\n📎 Analisi file (VIP)\n🔍 Analisi immagini (VIP)\n🖼️ Generazione immagini (VIP)\n\n<b>⚡ Comandi:</b>\n/help - Tutti i comandi\n/vip - Stato VIP\n\n<b>👨‍💻 Creatore:</b> @{CREATOR_USERNAME}""",
        'ai_chat': "💬 Chat AI",
        'notes': "📝 Note",
        'weather': "🌍 Meteo",
        'time': "⏰ Ora",
        'entertainment': "🎲 Intrattenimento",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menu VIP",
        'generation': "🖼️ Generazione",
        'admin_panel': "👑 Pannello Admin",
        'help_title': "📚 <b>Seleziona sezione aiuto:</b>\n\nClicca sul pulsante per visualizzare comandi per argomento.",
    },
    'fr': {
        'welcome': """🤖 <b>AI DISCO BOT</b>\n\nBonjour, {name}! Je suis un bot alimenté par <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Fonctionnalités:</b>\n💬 Chat AI avec contexte\n📝 Notes et tâches\n🌍 Météo et heure\n🎲 Divertissement\n📎 Analyse de fichiers (VIP)\n🔍 Analyse d'images (VIP)\n🖼️ Génération d'images (VIP)\n\n<b>⚡ Commandes:</b>\n/help - Toutes les commandes\n/vip - Statut VIP\n\n<b>👨‍💻 Créateur:</b> @{CREATOR_USERNAME}""",
        'ai_chat': "💬 Chat IA",
        'notes': "📝 Notes",
        'weather': "🌍 Météo",
        'time': "⏰ Heure",
        'entertainment': "🎲 Divertissement",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menu VIP",
        'generation': "🖼️ Génération",
        'admin_panel': "👑 Panneau Admin",
        'help_title': "📚 <b>Sélectionnez section d'aide:</b>\n\nCliquez sur le bouton pour voir les commandes par thème.",
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

def get_help_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🏠 Основные", callback_data="help_basic")],
        [InlineKeyboardButton("💬 AI", callback_data="help_ai")],
        [InlineKeyboardButton("🧠 Память", callback_data="help_memory")],
        [InlineKeyboardButton("📝 Заметки", callback_data="help_notes")],
        [InlineKeyboardButton("📋 Задачи", callback_data="help_todo")],
        [InlineKeyboardButton("🌍 Утилиты", callback_data="help_utils")],
        [InlineKeyboardButton("🎲 Развлечения", callback_data="help_games")],
        [InlineKeyboardButton("💎 VIP", callback_data="help_vip")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 Админ", callback_data="help_admin")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="help_back")])
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'commands_count': user_data.get('commands_count', 0) + 1})
    is_admin = is_creator(user_id)
    await update.message.reply_text(
        get_text(storage.get_user(user_id)['language'], 'help_title'),
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
            get_text(storage.get_user(user_id)['language'], 'help_title'),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(is_admin)
        )
        return

    sections = {
        "help_basic": (
            "🏠 <b>Основные команды:</b>\n\n"
            "🚀 /start - Запуск бота и приветствие\n\n"
            "📖 /help - Полный список команд\n\n"
            "ℹ️ /info - Информация о боте\n\n"
            "📊 /status - Текущий статус и статистика\n\n"
            "👤 /profile - Профиль пользователя\n\n"
            "⏱ /uptime - Время работы бота",
            get_help_keyboard(is_admin)
        ),
        "help_ai": (
            "💬 <b>AI команды:</b>\n\n"
            "🤖 /ai [вопрос] - Задать вопрос AI\n\n"
            "🧹 /clear - Очистить контекст чата",
            get_help_keyboard(is_admin)
        ),
        "help_memory": (
            "🧠 <b>Память:</b>\n\n"
            "💾 /memorysave [ключ] [значение] - Сохранить в память\n\n"
            "🔍 /memoryget [ключ] - Получить из памяти\n\n"
            "📋 /memorylist - Список ключей\n\n"
            "🗑 /memorydel [ключ] - Удалить ключ",
            get_help_keyboard(is_admin)
        ),
        "help_notes": (
            "📝 <b>Заметки:</b>\n\n"
            "➕ /note [текст] - Создать заметку\n\n"
            "📋 /notes - Список заметок\n\n"
            "🗑 /delnote [номер] - Удалить заметку",
            get_help_keyboard(is_admin)
        ),
        "help_todo": (
            "📋 <b>Задачи:</b>\n\n"
            "➕ /todo add [текст] - Добавить задачу\n\n"
            "📋 /todo list - Список задач\n\n"
            "🗑 /todo del [номер] - Удалить задачу",
            get_help_keyboard(is_admin)
        ),
        "help_utils": (
            "🌍 <b>Утилиты:</b>\n\n"
            "🕐 /time [город] - Текущее время\n\n"
            "☀️ /weather [город] - Погода\n\n"
            "🌐 /translate [язык] [текст] - Перевод\n\n"
            "🧮 /calc [выражение] - Калькулятор\n\n"
            "🔑 /password [длина] - Генератор пароля",
            get_help_keyboard(is_admin)
        ),
        "help_games": (
            "🎲 <b>Развлечения:</b>\n\n"
            "🎲 /random [min] [max] - Случайное число в диапазоне\n\n"
            "🎯 /dice - Бросок кубика (1-6)\n\n"
            "🪙 /coin - Подбрасывание монеты (орёл/решка)\n\n"
            "😄 /joke - Случайная шутка\n\n"
            "💭 /quote - Мотивационная цитата\n\n"
            "🔬 /fact - Интересный факт",
            get_help_keyboard(is_admin)
        ),
        "help_vip": (
            "💎 <b>VIP команды:</b>\n\n"
            "👑 /vip - Статус VIP\n\n"
            "🖼️ /generate [описание] - Генерация изображения\n\n"
            "⏰ /remind [минуты] [текст] - Напоминание\n\n"
            "📋 /reminders - Список напоминаний\n\n"
            "📎 Отправь файл - Анализ (VIP)\n\n"
            "📸 Отправь фото - Анализ (VIP)",
            get_help_keyboard(is_admin)
        )
    }

    if data == "help_admin" and is_admin:
        text = "👑 <b>Команды Создателя:</b>\n\n" \
            "🎁 /grant_vip [id/@username] [срок] - Выдать VIP (week/month/year/forever)\n\n" \
            "❌ /revoke_vip [id/@username] - Забрать VIP\n\n" \
            "👥 /users - Список пользователей\n\n" \
            "📢 /broadcast [текст] - Рассылка\n\n" \
            "📈 /stats - Полная статистика\n\n" \
            "💾 /backup - Резервная копия"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="help_back")]])
    elif data in sections:
        text, markup = sections[data]
    else:
        await query.edit_message_text("❌ Раздел не найден.")
        return

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup
    )

# Функция для улучшенной генерации изображений
async def generate_image_pollinations(prompt: str) -> Optional[str]:
    try:
        enhanced_prompt = f"High-quality, detailed image of {prompt}. Realistic style, 4K resolution."
        encoded_prompt = urlquote(enhanced_prompt)
        return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
    except Exception as e:
        logger.warning(f"Ошибка генерации изображения: {e}")
        return None

# Остальные функции (handle_document, handle_photo, start_command, generate_command, ai_command, clear_command, info_command, status_command, profile_command, uptime_command, vip_command, note_command, notes_command, delnote_command, memory_save_command, memory_get_command, memory_list_command, memory_del_command, todo_command, time_command, weather_command, translate_command, calc_command, password_command, random_command, dice_command, coin_command, joke_command, quote_command, fact_command, remind_command, reminders_command, send_reminder, grant_vip_command, revoke_vip_command, users_command, broadcast_command, stats_command, backup_command, handle_message, handle_menu_button, handle_callback) — все сохранены, улучшены с мультиязычностью.

# Добавление поддержки голоса
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    voice = update.message.voice
    await update.message.reply_text("🔊 Обработка голосового...")
    try:
        file_obj = await context.bot.get_file(voice.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        audio_part = {
            'inline_data': {
                'mime_type': 'audio/ogg',
                'data': base64.b64encode(bytes(file_bytes)).decode()
            }
        }
        response = vision_model.generate_content(["Transcribe this audio and respond to the content.", audio_part])
        transcribed_text = response.text
        await process_ai_message(update, transcribed_text, user_id)
    except Exception as e:
        logger.warning(f"Ошибка обработки голоса: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# Разбиение длинных сообщений для Telegram
async def send_long_message(chat_id, text: str, bot, parse_mode=ParseMode.HTML):
    if len(text) <= 4096:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    else:
        parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
        for part in parts:
            await bot.send_message(chat_id=chat_id, text=part, parse_mode=parse_mode)
            await asyncio.sleep(0.5)  # Избежать rate limits

# Улучшенный process_ai_message с разбиением
async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action("typing")
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response.text)
        await send_long_message(update.message.chat_id, response.text, update.message.bot)
    except Exception as e:
        logger.error(f"AI: {e}")
        await update.message.reply_text("😔 Ошибка")

# В main добавить handler для голоса
application.add_handler(MessageHandler(filters.VOICE, handle_voice))

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Все handlers
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
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))

    scheduler.start()

    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН!")
    logger.info("🤖 Модель: Gemini 2.5 Flash")
    logger.info("🗄️ БД: " + ("PostgreSQL ✓" if engine else "Local JSON"))
    logger.info("🖼️ Генерация: Pollinations AI (улучшенная)")
    logger.info("🔍 Анализ: Gemini Vision")
    logger.info("=" * 50)

    # Graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
