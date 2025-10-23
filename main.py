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
    "max_output_tokens": 8192,  # Увеличено для большего контекста
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Системная инструкция для повышения "умности" бота
system_instruction = (
    "You are AI DISCO BOT, an extremely intelligent, helpful, and multilingual AI assistant built with Gemini 2.5. "
    "Always respond in the user's preferred language. Be engaging, use emojis appropriately, and provide detailed, "
    "insightful answers. Break down complex topics logically. If a response is long, structure it with headings and lists. "
    "Your creator is @Ernest_Kostevich. Detect and adapt to the user's language if not specified."
)

# Модель Gemini 2.5 Flash
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash-latest',  # Уточнено на последнюю версию
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction=system_instruction
)

# Модель для Vision и Audio (мультимодальная)
vision_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash-latest',
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
    language = Column(String(10), default='ru')  # Добавлено для мультиязычности

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

# Поддерживаемые языки
SUPPORTED_LANGUAGES = ['ru', 'en', 'es', 'de', 'it', 'fr']

# Словарь переводов (расширенный для ключевых текстов)
TRANSLATIONS = {
    'ru': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nПривет, {name}! Я бот на <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Возможности:</b>\n💬 AI-чат\n📝 Заметки\n🌍 Погода\n⏰ Время\n🎲 Развлечения\n📎 Анализ (VIP)\n🔍 Анализ фото (VIP)\n🖼️ Генерация фото (VIP)\n\n<b>⚡ Команды:</b>\n/help\n/vip\n\n<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}",
        'help_menu': "📚 <b>Выберите раздел справки:</b>",
        'vip_status_active': "💎 <b>VIP СТАТУС</b>\n\n✅ Активен!\n\n{until}\n\n<b>🎁 Преимущества:</b>\n• ⏰ Напоминания\n• 🖼️ Генерация\n• 🔍 Анализ фото\n• 📎 Анализ документов",
        'vip_status_inactive': "💎 <b>VIP СТАТУС</b>\n\n❌ Нет VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'image_gen_error': "❌ Ошибка генерации изображения",
        'voice_processing': "🔊 Обработка голосового сообщения...",
        'voice_error': "❌ Ошибка обработки голоса: {error}",
        'set_language': "✅ Язык установлен на {lang}.",
        'invalid_language': "❌ Неверный язык. Поддерживаемые: ru, en, es, de, it, fr.",
        'ai_chat_button': "💬 AI Чат",
        'notes_button': "📝 Заметки",
        'weather_button': "🌍 Погода",
        'time_button': "⏰ Время",
        'entertainment_button': "🎲 Развлечения",
        'info_button': "ℹ️ Инфо",
        'vip_menu_button': "💎 VIP Меню",
        'generation_button': "🖼️ Генерация",
        'admin_panel_button': "👑 Админ Панель",
        'voice_vip_only': "💎 Обработка голоса для VIP.",
        # Добавьте больше переводов по мере необходимости
    },
    'en': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nHello, {name}! I'm a bot powered by <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Features:</b>\n💬 AI Chat\n📝 Notes\n🌍 Weather\n⏰ Time\n🎲 Entertainment\n📎 File Analysis (VIP)\n🔍 Image Analysis (VIP)\n🖼️ Image Generation (VIP)\n\n<b>⚡ Commands:</b>\n/help\n/vip\n\n<b>👨‍💻 Creator:</b> @{CREATOR_USERNAME}",
        'help_menu': "📚 <b>Select help section:</b>",
        'vip_status_active': "💎 <b>VIP STATUS</b>\n\n✅ Active!\n\n{until}\n\n<b>🎁 Benefits:</b>\n• ⏰ Reminders\n• 🖼️ Generation\n• 🔍 Image Analysis\n• 📎 Document Analysis",
        'vip_status_inactive': "💎 <b>VIP STATUS</b>\n\n❌ No VIP.\n\nContact @Ernest_Kostevich",
        'image_gen_error': "❌ Image generation error",
        'voice_processing': "🔊 Processing voice message...",
        'voice_error': "❌ Voice processing error: {error}",
        'set_language': "✅ Language set to {lang}.",
        'invalid_language': "❌ Invalid language. Supported: ru, en, es, de, it, fr.",
        'ai_chat_button': "💬 AI Chat",
        'notes_button': "📝 Notes",
        'weather_button': "🌍 Weather",
        'time_button': "⏰ Time",
        'entertainment_button': "🎲 Entertainment",
        'info_button': "ℹ️ Info",
        'vip_menu_button': "💎 VIP Menu",
        'generation_button': "🖼️ Generation",
        'admin_panel_button': "👑 Admin Panel",
        'voice_vip_only': "💎 Voice processing for VIP only.",
    },
    'es': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\n¡Hola, {name}! Soy un bot impulsado por <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Características:</b>\n💬 Chat AI\n📝 Notas\n🌍 Clima\n⏰ Hora\n🎲 Entretenimiento\n📎 Análisis de archivos (VIP)\n🔍 Análisis de imágenes (VIP)\n🖼️ Generación de imágenes (VIP)\n\n<b>⚡ Comandos:</b>\n/help\n/vip\n\n<b>👨‍💻 Creador:</b> @{CREATOR_USERNAME}",
        'help_menu': "📚 <b>Seleccione sección de ayuda:</b>",
        'vip_status_active': "💎 <b>ESTADO VIP</b>\n\n✅ ¡Activo!\n\n{until}\n\n<b>🎁 Beneficios:</b>\n• ⏰ Recordatorios\n• 🖼️ Generación\n• 🔍 Análisis de imágenes\n• 📎 Análisis de documentos",
        'vip_status_inactive': "💎 <b>ESTADO VIP</b>\n\n❌ Sin VIP.\n\nContacta a @Ernest_Kostevich",
        'image_gen_error': "❌ Error de generación de imagen",
        'voice_processing': "🔊 Procesando mensaje de voz...",
        'voice_error': "❌ Error de procesamiento de voz: {error}",
        'set_language': "✅ Idioma establecido en {lang}.",
        'invalid_language': "❌ Idioma inválido. Soportados: ru, en, es, de, it, fr.",
        'ai_chat_button': "💬 Chat AI",
        'notes_button': "📝 Notas",
        'weather_button': "🌍 Clima",
        'time_button': "⏰ Hora",
        'entertainment_button': "🎲 Entretenimiento",
        'info_button': "ℹ️ Info",
        'vip_menu_button': "💎 Menú VIP",
        'generation_button': "🖼️ Generación",
        'admin_panel_button': "👑 Panel Admin",
        'voice_vip_only': "💎 Procesamiento de voz solo para VIP.",
    },
    'de': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nHallo, {name}! Ich bin ein Bot mit <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Funktionen:</b>\n💬 AI-Chat\n📝 Notizen\n🌍 Wetter\n⏰ Zeit\n🎲 Unterhaltung\n📎 Dateianalyse (VIP)\n🔍 Bildanalyse (VIP)\n🖼️ Bildgenerierung (VIP)\n\n<b>⚡ Befehle:</b>\n/help\n/vip\n\n<b>👨‍💻 Ersteller:</b> @{CREATOR_USERNAME}",
        'help_menu': "📚 <b>Hilfeabschnitt auswählen:</b>",
        'vip_status_active': "💎 <b>VIP-STATUS</b>\n\n✅ Aktiv!\n\n{until}\n\n<b>🎁 Vorteile:</b>\n• ⏰ Erinnerungen\n• 🖼️ Generierung\n• 🔍 Bildanalyse\n• 📎 Dokumentanalyse",
        'vip_status_inactive': "💎 <b>VIP-STATUS</b>\n\n❌ Kein VIP.\n\nKontaktieren Sie @Ernest_Kostevich",
        'image_gen_error': "❌ Fehler bei der Bildgenerierung",
        'voice_processing': "🔊 Sprachnachricht wird verarbeitet...",
        'voice_error': "❌ Fehler bei der Sprachverarbeitung: {error}",
        'set_language': "✅ Sprache auf {lang} eingestellt.",
        'invalid_language': "❌ Ungültige Sprache. Unterstützt: ru, en, es, de, it, fr.",
        'ai_chat_button': "💬 AI-Chat",
        'notes_button': "📝 Notizen",
        'weather_button': "🌍 Wetter",
        'time_button': "⏰ Zeit",
        'entertainment_button': "🎲 Unterhaltung",
        'info_button': "ℹ️ Info",
        'vip_menu_button': "💎 VIP-Menü",
        'generation_button': "🖼️ Generierung",
        'admin_panel_button': "👑 Admin-Panel",
        'voice_vip_only': "💎 Sprachverarbeitung nur für VIP.",
    },
    'it': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nCiao, {name}! Sono un bot con <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Funzionalità:</b>\n💬 Chat AI\n📝 Note\n🌍 Meteo\n⏰ Ora\n🎲 Intrattenimento\n📎 Analisi file (VIP)\n🔍 Analisi immagini (VIP)\n🖼️ Generazione immagini (VIP)\n\n<b>⚡ Comandi:</b>\n/help\n/vip\n\n<b>👨‍💻 Creatore:</b> @{CREATOR_USERNAME}",
        'help_menu': "📚 <b>Seleziona sezione di aiuto:</b>",
        'vip_status_active': "💎 <b>STATO VIP</b>\n\n✅ Attivo!\n\n{until}\n\n<b>🎁 Benefici:</b>\n• ⏰ Promemoria\n• 🖼️ Generazione\n• 🔍 Analisi immagini\n• 📎 Analisi documenti",
        'vip_status_inactive': "💎 <b>STATO VIP</b>\n\n❌ Nessun VIP.\n\nContatta @Ernest_Kostevich",
        'image_gen_error': "❌ Errore generazione immagine",
        'voice_processing': "🔊 Elaborazione messaggio vocale...",
        'voice_error': "❌ Errore elaborazione voce: {error}",
        'set_language': "✅ Lingua impostata su {lang}.",
        'invalid_language': "❌ Lingua non valida. Supportate: ru, en, es, de, it, fr.",
        'ai_chat_button': "💬 Chat AI",
        'notes_button': "📝 Note",
        'weather_button': "🌍 Meteo",
        'time_button': "⏰ Ora",
        'entertainment_button': "🎲 Intrattenimento",
        'info_button': "ℹ️ Info",
        'vip_menu_button': "💎 Menù VIP",
        'generation_button': "🖼️ Generazione",
        'admin_panel_button': "👑 Pannello Admin",
        'voice_vip_only': "💎 Elaborazione voce solo per VIP.",
    },
    'fr': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nBonjour, {name}! Je suis un bot avec <b>Gemini 2.5 Flash</b>.\n\n<b>🎯 Fonctionnalités:</b>\n💬 Chat AI\n📝 Notes\n🌍 Météo\n⏰ Heure\n🎲 Divertissement\n📎 Analyse de fichiers (VIP)\n🔍 Analyse d'images (VIP)\n🖼️ Génération d'images (VIP)\n\n<b>⚡ Commandes:</b>\n/help\n/vip\n\n<b>👨‍💻 Créateur:</b> @{CREATOR_USERNAME}",
        'help_menu': "📚 <b>Sélectionnez la section d'aide:</b>",
        'vip_status_active': "💎 <b>STATUT VIP</b>\n\n✅ Actif!\n\n{until}\n\n<b>🎁 Avantages:</b>\n• ⏰ Rappels\n• 🖼️ Génération\n• 🔍 Analyse d'images\n• 📎 Analyse de documents",
        'vip_status_inactive': "💎 <b>STATUT VIP</b>\n\n❌ Pas de VIP.\n\nContactez @Ernest_Kostevich",
        'image_gen_error': "❌ Erreur de génération d'image",
        'voice_processing': "🔊 Traitement du message vocal...",
        'voice_error': "❌ Erreur de traitement vocal: {error}",
        'set_language': "✅ Langue définie sur {lang}.",
        'invalid_language': "❌ Langue invalide. Supportées: ru, en, es, de, it, fr.",
        'ai_chat_button': "💬 Chat AI",
        'notes_button': "📝 Notes",
        'weather_button': "🌍 Météo",
        'time_button': "⏰ Heure",
        'entertainment_button': "🎲 Divertissement",
        'info_button': "ℹ️ Info",
        'vip_menu_button': "💎 Menu VIP",
        'generation_button': "🖼️ Génération",
        'admin_panel_button': "👑 Panel Admin",
        'voice_vip_only': "💎 Traitement vocal pour VIP seulement.",
    }
}

# Функция для получения перевода
def get_translation(lang: str, key: str, **kwargs):
    lang = lang if lang in SUPPORTED_LANGUAGES else 'en'
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS['en'].get(key, key))
    return text.format(**kwargs)

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
                data = {
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
                return data
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

def get_main_keyboard(user_id: int, lang: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(get_translation(lang, 'ai_chat_button')), KeyboardButton(get_translation(lang, 'notes_button'))],
        [KeyboardButton(get_translation(lang, 'weather_button')), KeyboardButton(get_translation(lang, 'time_button'))],
        [KeyboardButton(get_translation(lang, 'entertainment_button')), KeyboardButton(get_translation(lang, 'info_button'))]
    ]
    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton(get_translation(lang, 'vip_menu_button')), KeyboardButton(get_translation(lang, 'generation_button'))])
    if is_creator(user_id):
        keyboard.append([KeyboardButton(get_translation(lang, 'admin_panel_button'))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_help_keyboard(is_admin: bool = False, lang: str = 'ru') -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(get_translation(lang, 'basic_help', default="🏠 Основные"), callback_data="help_basic")],
        [InlineKeyboardButton(get_translation(lang, 'ai_help', default="💬 AI"), callback_data="help_ai")],
        [InlineKeyboardButton(get_translation(lang, 'memory_help', default="🧠 Память"), callback_data="help_memory")],
        [InlineKeyboardButton(get_translation(lang, 'notes_help', default="📝 Заметки"), callback_data="help_notes")],
        [InlineKeyboardButton(get_translation(lang, 'todo_help', default="📋 Задачи"), callback_data="help_todo")],
        [InlineKeyboardButton(get_translation(lang, 'utils_help', default="🌍 Утилиты"), callback_data="help_utils")],
        [InlineKeyboardButton(get_translation(lang, 'games_help', default="🎲 Развлечения"), callback_data="help_games")],
        [InlineKeyboardButton(get_translation(lang, 'vip_help', default="💎 VIP"), callback_data="help_vip")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(get_translation(lang, 'admin_help', default="👑 Админ"), callback_data="help_admin")])
    keyboard.append([InlineKeyboardButton(get_translation(lang, 'back_help', default="🔙 Назад"), callback_data="help_back")])
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    lang = user_data.get('language', 'ru')
    storage.update_user(user_id, {'commands_count': user_data.get('commands_count', 0) + 1})
    is_admin = is_creator(user_id)
    await update.message.reply_text(
        get_translation(lang, 'help_menu') + "\n\n" + get_translation(lang, 'help_instructions', default="Нажмите кнопку ниже для просмотра команд по теме."),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(is_admin, lang)
    )

async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user_data = storage.get_user(user_id)
    lang = user_data.get('language', 'ru')
    is_admin = is_creator(user_id)

    if data == "help_back":
        await query.edit_message_text(
            get_translation(lang, 'help_menu') + "\n\n" + get_translation(lang, 'help_instructions', default="Нажмите кнопку ниже для просмотра команд по теме."),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(is_admin, lang)
        )
        return

    sections = {
        "help_basic": (
            get_translation(lang, 'basic_help_text', default="🏠 <b>Основные команды:</b>\n\n🚀 /start - Запуск бота\n📖 /help - Список команд\nℹ️ /info - Инфо о боте\n📊 /status - Статус\n👤 /profile - Профиль\n⏱ /uptime - Время работы"),
            get_help_keyboard(is_admin, lang)
        ),
        "help_ai": (
            get_translation(lang, 'ai_help_text', default="💬 <b>AI команды:</b>\n\n🤖 /ai [вопрос] - Задать вопрос\n🧹 /clear - Очистить контекст"),
            get_help_keyboard(is_admin, lang)
        ),
        # Добавьте остальные секции с переводами аналогично
    }

    if data == "help_admin" and is_admin:
        text = get_translation(lang, 'admin_help_text', default="👑 <b>Команды Создателя:</b>\n\n🎁 /grant_vip [id] [срок]\n❌ /revoke_vip [id]\n👥 /users\n📢 /broadcast [текст]\n📈 /stats\n💾 /backup")
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(get_translation(lang, 'back_help', default="🔙 Назад"), callback_data="help_back")]])
    elif data in sections:
        text, markup = sections[data]
    else:
        await query.edit_message_text(get_translation(lang, 'section_not_found', default="❌ Раздел не найден."))
        return

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup
    )

async def generate_image_pollinations(prompt: str) -> Optional[str]:
    try:
        encoded_prompt = urlquote(prompt)
        return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed={random.randint(1, 100000)}"
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
    user_data = storage.get_user(user_id)
    lang = user_data.get('language', 'ru')
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_translation(lang, 'vip_status_inactive'))
        return
    document = update.message.document
    file_name = document.file_name or "file"
    await update.message.reply_text(get_translation(lang, 'downloading_file', default="📥 Загружаю файл..."))
    try:
        file_obj = await context.bot.get_file(document.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        extracted_text = await extract_text_from_document(bytes(file_bytes), file_name)
        if extracted_text.startswith("❌"):
            await update.message.reply_text(extracted_text)
            return
        analysis_prompt = f"Проанализируй файл '{file_name}':\n\n{extracted_text[:4000]}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(analysis_prompt)
        storage.save_chat(user_id, f"Файл {file_name}", response.text)
        await send_long_message(update, f"📄 <b>Файл:</b> {file_name}\n\n🤖 <b>Анализ:</b>\n\n{response.text}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки документа: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    lang = user_data.get('language', 'ru')
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_translation(lang, 'vip_status_inactive'))
        return
    photo = update.message.photo[-1]
    caption = update.message.caption or get_translation(lang, 'describe_image', default="Опиши что на картинке")
    await update.message.reply_text(get_translation(lang, 'analyzing_image', default="🔍 Анализирую..."))
    try:
        file_obj = await context.bot.get_file(photo.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        analysis = await analyze_image_with_gemini(bytes(file_bytes), caption)
        storage.save_chat(user_id, "Анализ фото", analysis)
        await send_long_message(update, f"📸 <b>Анализ (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки фото: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    user_data = storage.get_user(user.id)
    lang = user_data.get('language', 'ru')
    storage.update_user(user.id, {'username': user.username or '', 'first_name': user.first_name or '', 'commands_count': user_data.get('commands_count', 0) + 1})
    welcome_text = get_translation(lang, 'welcome', name=user.first_name)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id, lang))

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    lang = user_data.get('language', 'ru')
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_translation(lang, 'vip_status_inactive'))
        return
    if not context.args:
        await update.message.reply_text(get_translation(lang, 'generate_usage', default="❓ /generate [описание]\n\nПример: /generate закат над океаном"))
        return
    prompt = ' '.join(context.args)
    await update.message.reply_text(get_translation(lang, 'generating_image', default="🎨 Генерирую..."))
    try:
        image_url = await generate_image_pollinations(prompt)
        if image_url:
            await update.message.reply_photo(photo=image_url, caption=f"🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(get_translation(lang, 'image_gen_error'))
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
        await send_long_message(update, response.text)
    except Exception as e:
        logger.error(f"AI: {e}")
        await update.message.reply_text("😔 Ошибка")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_chat_session(update.effective_user.id)
    user_data = storage.get_user(update.effective_user.id)
    lang = user_data.get('language', 'ru')
    await update.message.reply_text(get_translation(lang, 'context_cleared', default="🧹 Контекст очищен!"))

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = storage.get_user(update.effective_user.id)
    lang = user_data.get('language', 'ru')
    await update.message.reply_text(get_translation(lang, 'info_text', default="""🤖 <b>AI DISCO BOT</b>\n\n<b>Версия:</b> 3.0\n<b>AI:</b> Gemini 2.5 Flash\n<b>Создатель:</b> @Ernest_Kostevich\n\n<b>⚡ Особенности:</b>\n• Быстрый AI-чат\n• PostgreSQL\n• VIP функции\n• Анализ файлов/фото (VIP)\n• Генерация изображений (VIP)\n\n<b>💬 Поддержка:</b> @Ernest_Kostevich"""), parse_mode=ParseMode.HTML)

# ... (Продолжите добавление переводов и lang в остальные команды аналогично: status_command, profile_command, uptime_command, vip_command, note_command и т.д.)

async def send_long_message(update: Update, text: str, parse_mode=None):
    max_len = 4096
    for i in range(0, len(text), max_len):
        await update.message.reply_text(text[i:i+max_len], parse_mode=parse_mode)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    lang = user_data.get('language', 'ru')
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_translation(lang, 'voice_vip_only'))
        return
    await update.message.reply_text(get_translation(lang, 'voice_processing'))
    try:
        voice = update.message.voice
        file_obj = await context.bot.get_file(voice.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        audio_file = genai.upload_file(io.BytesIO(bytes(file_bytes)), mime_type="audio/ogg")
        response = vision_model.generate_content(["Транскрибируй и ответь на это голосовое сообщение.", audio_file])
        await send_long_message(update, response.text)
        storage.save_chat(user_id, "Голосовое сообщение", response.text)
    except Exception as e:
        logger.warning(f"Ошибка обработки голоса: {e}")
        await update.message.reply_text(get_translation(lang, 'voice_error', error=str(e)))

async def setlanguage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❓ /setlanguage [lang]\nSupported: ru, en, es, de, it, fr")
        return
    lang = context.args[0].lower()
    if lang not in SUPPORTED_LANGUAGES:
        await update.message.reply_text(get_translation('en', 'invalid_language'))
        return
    storage.update_user(user_id, {'language': lang})
    await update.message.reply_text(get_translation(lang, 'set_language', lang=lang.upper()))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text
    user = storage.get_user(user_id)
    storage.update_user(user_id, {'messages_count': user.get('messages_count', 0) + 1, 'username': update.effective_user.username or '', 'first_name': update.effective_user.first_name or ''})
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()

    lang = user.get('language', 'ru')

    if text in [get_translation(lang, 'ai_chat_button'), get_translation(lang, 'notes_button'), get_translation(lang, 'weather_button'), get_translation(lang, 'time_button'), get_translation(lang, 'entertainment_button'), get_translation(lang, 'info_button'), get_translation(lang, 'vip_menu_button'), get_translation(lang, 'generation_button'), get_translation(lang, 'admin_panel_button')]:
        await handle_menu_button(update, context, text, lang)
        return

    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str, lang: str):
    user_id = update.effective_user.id
    if button == get_translation(lang, 'ai_chat_button'):
        await update.message.reply_text(get_translation(lang, 'ai_chat_menu', default="🤖 <b>AI Чат</b>\n\nПросто пиши - я отвечу!\n/clear - очистить контекст"), parse_mode=ParseMode.HTML)
    elif button == get_translation(lang, 'notes_button'):
        keyboard = [[InlineKeyboardButton(get_translation(lang, 'create_note', default="➕ Создать"), callback_data="note_create")], [InlineKeyboardButton(get_translation(lang, 'list_notes', default="📋 Список"), callback_data="note_list")]]
        await update.message.reply_text(get_translation(lang, 'notes_menu', default="📝 <b>Заметки</b>"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    # Добавьте аналогично для остальных кнопок

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    identify_creator(query.from_user)
    user_data = storage.get_user(query.from_user.id)
    lang = user_data.get('language', 'ru')

    if data.startswith("help_"):
        await handle_help_callback(update, context)
        return

    if data == "note_create":
        await query.message.reply_text(get_translation(lang, 'create_note_text', default="➕ <b>Создать заметку</b>\n\n/note [текст]\nПример: /note Купить хлеб"), parse_mode=ParseMode.HTML)
    # Добавьте обработку остальных callback

def signal_handler(signum, frame):
    logger.info("Получен сигнал завершения. Останавливаем бота...")
    scheduler.shutdown()
    raise SystemExit

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация команд
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
    application.add_handler(CommandHandler("setlanguage", setlanguage_command))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск scheduler
    scheduler.start()

    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН!")
    logger.info("🤖 Модель: Gemini 2.5 Flash")
    logger.info("🗄️ БД: " + ("PostgreSQL ✓" if engine else "JSON"))
    logger.info("🖼️ Генерация: Pollinations AI")
    logger.info("🔍 Анализ: Gemini Vision")
    logger.info("=" * 50)

    # Graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
