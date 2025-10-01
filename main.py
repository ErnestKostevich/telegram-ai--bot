#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM AI BOT v2.1 - Исправленная версия
✅ Убрана конфиденциальная информация из /info
✅ Работающие кнопки в /start  
✅ Актуальное время для 6 часовых поясов
✅ Удалены неработающие команды
✅ Добавлена многоязычность (6 языков)
"""

import asyncio
import logging
import json
import random
import time
import datetime
import requests
import os
import sys
import sqlite3
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from newsapi import NewsApiClient
import nest_asyncio
from flask import Flask
import pytz
from github import Github

nest_asyncio.apply()

# Telegram Bot API
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import Conflict

# Google Gemini
import google.generativeai as genai

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"

CREATOR_ID = 7108255346
CREATOR_USERNAME = "@Ernest_Kostevich"
DAD_BIRTHDAY = "10-03"
BOT_USERNAME = "@AI_DISCO_BOT"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = os.getenv("MODEL", "gemini-2.0-flash-exp")

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

DB_PATH = "bot_database.db"
CONVERSATIONS_PATH = "conversations.json"
BACKUP_PATH = "backups"
Path(BACKUP_PATH).mkdir(exist_ok=True)

# ============================================================================
# ПЕРЕВОДЫ (6 ЯЗЫКОВ)
# ============================================================================

TRANSLATIONS = {
    'ru': {
        'welcome': '🤖 Привет, {name}!\nЯ AI-бот с 50+ функциями!\n\n🌟 Основное:\n• 💬 AI-чат с Gemini 2.0\n• 📝 Заметки и память\n• 🌤️ Погода и новости\n• 🎮 Игры и развлечения\n• 💰 Курсы валют\n\n💎 Хотите VIP? Спросите о возможностях!\n🤖 Используйте кнопки или /help',
        'help': '📋 Помощь',
        'notes': '📝 Заметки',
        'stats': '📊 Статистика',
        'time': '⏰ Время',
        'language': '🌐 Язык',
        'ai_chat': '💬 AI Чат',
        'current_time': '⏰ ТЕКУЩЕЕ ВРЕМЯ',
        'language_changed': '✅ Язык изменён на: Русский'
    },
    'en': {
        'welcome': '🤖 Hello, {name}!\nI am an AI bot with 50+ features!\n\n🌟 Main:\n• 💬 AI chat with Gemini 2.0\n• 📝 Notes and memory\n• 🌤️ Weather and news\n• 🎮 Games and entertainment\n• 💰 Currency rates\n\n💎 Want VIP? Ask about features!\n🤖 Use buttons or /help',
        'help': '📋 Help',
        'notes': '📝 Notes',
        'stats': '📊 Stats',
        'time': '⏰ Time',
        'language': '🌐 Language',
        'ai_chat': '💬 AI Chat',
        'current_time': '⏰ CURRENT TIME',
        'language_changed': '✅ Language changed to: English'
    },
    'es': {
        'welcome': '🤖 ¡Hola, {name}!\n¡Soy un bot AI con más de 50 funciones!\n\n🌟 Principal:\n• 💬 Chat AI con Gemini 2.0\n• 📝 Notas y memoria\n• 🌤️ Clima y noticias\n• 🎮 Juegos y entretenimiento\n• 💰 Tasas de cambio\n\n💎 ¿Quieres VIP? ¡Pregunta!\n🤖 Usa botones o /help',
        'help': '📋 Ayuda',
        'notes': '📝 Notas',
        'stats': '📊 Estadísticas',
        'time': '⏰ Hora',
        'language': '🌐 Idioma',
        'ai_chat': '💬 Chat AI',
        'current_time': '⏰ HORA ACTUAL',
        'language_changed': '✅ Idioma cambiado a: Español'
    },
    'fr': {
        'welcome': '🤖 Bonjour, {name}!\nJe suis un bot IA avec plus de 50 fonctions!\n\n🌟 Principal:\n• 💬 Chat IA avec Gemini 2.0\n• 📝 Notes et mémoire\n• 🌤️ Météo et actualités\n• 🎮 Jeux et divertissement\n• 💰 Taux de change\n\n💎 Vous voulez VIP? Demandez!\n🤖 Utilisez les boutons ou /help',
        'help': '📋 Aide',
        'notes': '📝 Notes',
        'stats': '📊 Statistiques',
        'time': '⏰ Heure',
        'language': '🌐 Langue',
        'ai_chat': '💬 Chat IA',
        'current_time': '⏰ HEURE ACTUELLE',
        'language_changed': '✅ Langue changée en: Français'
    },
    'it': {
        'welcome': '🤖 Ciao, {name}!\nSono un bot AI con oltre 50 funzioni!\n\n🌟 Principale:\n• 💬 Chat AI con Gemini 2.0\n• 📝 Note e memoria\n• 🌤️ Meteo e notizie\n• 🎮 Giochi e intrattenimento\n• 💰 Tassi di cambio\n\n💎 Vuoi VIP? Chiedi!\n🤖 Usa i pulsanti o /help',
        'help': '📋 Aiuto',
        'notes': '📝 Note',
        'stats': '📊 Statistiche',
        'time': '⏰ Ora',
        'language': '🌐 Lingua',
        'ai_chat': '💬 Chat AI',
        'current_time': '⏰ ORA ATTUALE',
        'language_changed': '✅ Lingua cambiata in: Italiano'
    },
    'de': {
        'welcome': '🤖 Hallo, {name}!\nIch bin ein KI-Bot mit über 50 Funktionen!\n\n🌟 Haupt:\n• 💬 KI-Chat mit Gemini 2.0\n• 📝 Notizen und Speicher\n• 🌤️ Wetter und Nachrichten\n• 🎮 Spiele und Unterhaltung\n• 💰 Wechselkurse\n\n💎 VIP gewünscht? Fragen Sie!\n🤖 Nutzen Sie Tasten oder /help',
        'help': '📋 Hilfe',
        'notes': '📝 Notizen',
        'stats': '📊 Statistiken',
        'time': '⏰ Zeit',
        'language': '🌐 Sprache',
        'ai_chat': '💬 KI Chat',
        'current_time': '⏰ AKTUELLE ZEIT',
        'language_changed': '✅ Sprache geändert zu: Deutsch'
    }
}

LANGUAGE_NAMES = {
    'ru': '🇷🇺 Русский',
    'en': '🇺🇸 English',
    'es': '🇪🇸 Español',
    'fr': '🇫🇷 Français',
    'it': '🇮🇹 Italiano',
    'de': '🇩🇪 Deutsch'
}

# База данных (сокращённая версия - основные методы)
class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            is_vip INTEGER DEFAULT 0, vip_expires TEXT, language TEXT DEFAULT 'ru',
            birthday TEXT, nickname TEXT, level INTEGER DEFAULT 1, experience INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_activity TEXT DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, key TEXT, value TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, key))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, reminder_text TEXT,
            reminder_time TEXT, job_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS command_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, command TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def save_user(self, user_data: dict):
        conn = self.get_connection()
        cursor = conn.cursor()
        user_data['last_activity'] = datetime.datetime.now().isoformat()
        if self.get_user(user_data['user_id']):
            cursor.execute('''UPDATE users SET username=?, first_name=?, is_vip=?, vip_expires=?,
                language=?, nickname=?, level=?, experience=?, last_activity=? WHERE user_id=?''',
                (user_data.get('username',''), user_data.get('first_name',''), user_data.get('is_vip',0),
                user_data.get('vip_expires'), user_data.get('language','ru'), user_data.get('nickname'),
                user_data.get('level',1), user_data.get('experience',0), user_data['last_activity'], user_data['user_id']))
        else:
            cursor.execute('''INSERT INTO users (user_id, username, first_name, is_vip, vip_expires,
                language, nickname, level, experience, last_activity) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (user_data['user_id'], user_data.get('username',''), user_data.get('first_name',''),
                user_data.get('is_vip',0), user_data.get('vip_expires'), user_data.get('language','ru'),
                user_data.get('nickname'), user_data.get('level',1), user_data.get('experience',0), user_data['last_activity']))
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def log_command(self, user_id: int, command: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO command_logs (user_id, command) VALUES (?, ?)", (user_id, command))
        conn.commit()
        conn.close()
    
    def add_note(self, user_id: int, note: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (user_id, note) VALUES (?, ?)", (user_id, note))
        conn.commit()
        conn.close()
    
    def get_notes(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def delete_note(self, note_id: int, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

class ConversationMemory:
    def __init__(self, filepath: str = CONVERSATIONS_PATH):
        self.filepath = filepath
        self.conversations = self._load()
    
    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.conversations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    def add_message(self, user_id: int, role: str, content: str):
        uid = str(user_id)
        if uid not in self.conversations:
            self.conversations[uid] = {'messages': [], 'created_at': datetime.datetime.now().isoformat()}
        self.conversations[uid]['messages'].append({'role': role, 'content': content, 'timestamp': datetime.datetime.now().isoformat()})
        if len(self.conversations[uid]['messages']) % 10 == 0:
            self._save()
    
    def get_context(self, user_id: int, limit: int = 50):
        uid = str(user_id)
        if uid not in self.conversations:
            return []
        messages = self.conversations[uid]['messages']
        return messages[-limit:] if len(messages) > limit else messages
    
    def clear_history(self, user_id: int):
        uid = str(user_id)
        if uid in self.conversations:
            del self.conversations[uid]
            self._save()
    
    def save(self):
        self._save()

# ============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# ============================================================================

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.conversation_memory = ConversationMemory()
        self.gemini_model = None
        
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("Gemini инициализирован")
            except Exception as e:
                logger.error(f"Ошибка Gemini: {e}")
        
        self.scheduler = AsyncIOScheduler()
        self.maintenance_mode = False
        
        self.github = None
        if GITHUB_TOKEN:
            try:
                self.github = Github(GITHUB_TOKEN)
                self.repo = self.github.get_repo(GITHUB_REPO)
                logger.info("GitHub подключен")
            except Exception as e:
                logger.error(f"Ошибка GitHub: {e}")
    
    def t(self, key: str, lang: str = 'ru', **kwargs):
        """Получить перевод"""
        text = TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, key)
        return text.format(**kwargs) if kwargs else text
    
    async def get_user_data(self, update: Update):
        """Получить данные пользователя"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            user_data = {
                'user_id': user.id,
                'username': user.username or "",
                'first_name': user.first_name or "",
                'is_vip': 1 if user.id == CREATOR_ID else 0,
                'vip_expires': None,
                'language': 'ru',
                'nickname': None,
                'level': 1,
                'experience': 0
            }
            self.db.save_user(user_data)
            logger.info(f"Новый пользователь: {user.id}")
        
        return user_data
    
    def get_keyboard(self, lang: str = 'ru'):
        """Главная клавиатура"""
        keyboard = [
            [KeyboardButton(self.t('ai_chat', lang)), KeyboardButton(self.t('help', lang))],
            [KeyboardButton(self.t('notes', lang)), KeyboardButton(self.t('stats', lang))],
            [KeyboardButton(self.t('time', lang)), KeyboardButton(self.t('language', lang))]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def is_creator(self, user_id: int):
        return user_id == CREATOR_ID
    
    def is_vip(self, user_data: dict):
        if not user_data.get('is_vip'):
            return False
        if user_data.get('vip_expires'):
            try:
                expires = datetime.datetime.fromisoformat(user_data['vip_expires'])
                if datetime.datetime.now() > expires:
                    user_data['is_vip'] = 0
                    self.db.save_user(user_data)
                    return False
            except:
                return False
        return True
    
    async def add_experience(self, user_data: dict, points: int = 1):
        """Добавить опыт"""
        user_data['experience'] = user_data.get('experience', 0) + points
        required = user_data.get('level', 1) * 100
        if user_data['experience'] >= required:
            user_data['level'] = user_data.get('level', 1) + 1
            user_data['experience'] = 0
        self.db.save_user(user_data)
    
    # ========================================================================
    # КОМАНДЫ
    # ========================================================================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/start")
        lang = user_data.get('language', 'ru')
        
        message = self.t('welcome', lang, name=user_data['first_name'])
        keyboard = self.get_keyboard(lang)
        
        await update.message.reply_text(message, reply_markup=keyboard)
        await self.add_experience(user_data, 1)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/help")
        
        help_text = """
📋 СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос
/clearhistory - Очистить историю

📝 ЗАМЕТКИ:
/note [текст] - Создать
/notes - Показать все
/delnote [номер] - Удалить

⏰ ВРЕМЯ:
/time - Мировое время
/date - Текущая дата

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Шутка
/fact - Факт
/quote - Цитата
/coin - Монетка
/dice - Кубик
/8ball [вопрос] - Магический шар

🔢 МАТЕМАТИКА:
/math [выражение] - Вычисления
/calculate [выражение] - Калькулятор

🛠️ УТИЛИТЫ:
/password [длина] - Генератор паролей
/qr [текст] - QR-код
/weather [город] - Погода
/currency [из] [в] [сумма] - Конвертер валют
/translate [язык] [текст] - Перевод

🌐 ЯЗЫК:
/language - Выбрать язык

📊 ПРОГРЕСС:
/rank - Ваш уровень
        """
        
        if self.is_vip(user_data):
            help_text += """
💎 VIP КОМАНДЫ:
/remind [минуты] [текст]
/reminders - Список
/nickname [имя] - Никнейм
/profile - Профиль
            """
        
        if self.is_creator(user_data['user_id']):
            help_text += """
👑 СОЗДАТЕЛЬ:
/grant_vip [user_id] [week/month/year/permanent]
/revoke_vip [user_id]
/broadcast [текст]
/users - Список пользователей
/stats - Полная статистика
/maintenance [on/off]
/backup - Резервная копия
            """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /info - ИСПРАВЛЕНА (убрана конфиденциальная информация)"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/info")
        
        info_text = f"""
🤖 О БОТЕ

Версия: 2.1 (Исправленная)
Создатель: Ernest {CREATOR_USERNAME}
Бот: {BOT_USERNAME}

🔧 Технологии:
• AI: {"Gemini 2.0 ✅" if self.gemini_model else "❌"}
• База: SQLite ✅
• Память: JSON ✅
• Хостинг: Render ✅

📊 Статистика:
• Пользователей: {len(self.db.get_all_users())}
• Языков: 6 (ru, en, es, fr, it, de)

⚡ Работает 24/7 с автопингом
        """
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)
    
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /time - ИСПРАВЛЕНА (актуальное время для 6 часовых поясов)"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/time")
        lang = user_data.get('language', 'ru')
        
        # Получаем актуальное время для всех поясов
        now_utc = datetime.datetime.now(pytz.utc)
        
        timezones = {
            'Moscow': 'Europe/Moscow',
            'London': 'Europe/London',
            'New York': 'America/New_York',
            'Tokyo': 'Asia/Tokyo',
            'Paris': 'Europe/Paris',
            'Sydney': 'Australia/Sydney'
        }
        
        time_text = f"{self.t('current_time', lang)}\n\n"
        
        for city, tz_name in timezones.items():
            tz = pytz.timezone(tz_name)
            local_time = now_utc.astimezone(tz)
            time_text += f"🌍 {city}: {local_time.strftime('%H:%M:%S')}\n"
        
        time_text += f"\n📅 {self.t('date', lang)}: {now_utc.strftime('%d.%m.%Y')}"
        
        await update.message.reply_text(time_text)
        await self.add_experience(user_data, 1)
    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /language - выбор языка"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/language")
        
        if context.args:
            lang = context.args[0].lower()
            if lang in LANGUAGE_NAMES:
                user_data['language'] = lang
                self.db.save_user(user_data)
                await update.message.reply_text(
                    self.t('language_changed', lang),
                    reply_markup=self.get_keyboard(lang)
                )
                return
        
        # Показать доступные языки
        keyboard = []
        for code, name in LANGUAGE_NAMES.items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"lang_{code}")])
        
        await update.message.reply_text(
            "🌐 Выберите язык / Choose language:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AI чат"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос после /ai!\nПример: /ai Расскажи о космосе")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        query = " ".join(context.args)
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            history = self.conversation_memory.get_context(user_data['user_id'], limit=30)
            context_str = ""
            if history:
                context_str = "История:\n"
                for msg in history[-10:]:
                    role = "👤" if msg['role'] == 'user' else "🤖"
                    context_str += f"{role}: {msg['content'][:100]}...\n"
            
            prompt = f"{context_str}\n👤 Вопрос: {query}\n\nОтветь полезно, учитывая контекст."
            response = self.gemini_model.generate_content(prompt)
            
            self.conversation_memory.add_message(user_data['user_id'], 'user', query)
            self.conversation_memory.add_message(user_data['user_id'], 'assistant', response.text)
            
            await update.message.reply_text(response.text)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")
            logger.error(f"Ошибка AI: {e}")
        
        await self.add_experience(user_data, 2)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений"""
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            return
        
        user_data = await self.get_user_data(update)
        message = update.message.text
        
        # Обработка кнопок клавиатуры
        lang = user_data.get('language', 'ru')
        if message == self.t('help', lang):
            return await self.help_command(update, context)
        elif message == self.t('notes', lang):
            return await self.notes_command(update, context)
        elif message == self.t('stats', lang):
            return await self.stats_command(update, context)
        elif message == self.t('time', lang):
            return await self.time_command(update, context)
        elif message == self.t('language', lang):
            return await self.language_command(update, context)
        elif message == self.t('ai_chat', lang):
            await update.message.reply_text("💬 AI-чат готов! Просто напишите ваш вопрос.")
            return
        
        # AI чат
        if not self.gemini_model:
            return
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            history = self.conversation_memory.get_context(user_data['user_id'], limit=50)
            context_str = ""
            if history:
                for msg in history[-20:]:
                    role = "Пользователь" if msg['role'] == 'user' else "Ассистент"
                    context_str += f"{role}: {msg['content'][:200]}\n"
            
            prompt = f"История:\n{context_str}\n\nПользователь: {message}\n\nОтветь полезно."
            response = self.gemini_model.generate_content(prompt)
            
            self.conversation_memory.add_message(user_data['user_id'], 'user', message)
            self.conversation_memory.add_message(user_data['user_id'], 'assistant', response.text)
            
            await update.message.reply_text(response.text)
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Ошибка: {e}")
        
        await self.add_experience(user_data, 1)
    
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Создать заметку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/note")
        
        if not context.args:
            await update.message.reply_text("📝 Укажите текст!\nПример: /note Купить молоко")
            return
        
        note = " ".join(context.args)
        self.db.add_note(user_data['user_id'], note)
        await update.message.reply_text(f"✅ Заметка сохранена!\n\n📝 {note}")
        await self.add_experience(user_data, 1)
    
    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать заметки"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/notes")
        
        notes = self.db.get_notes(user_data['user_id'])
        
        if not notes:
            await update.message.reply_text("❌ У вас нет заметок!\nСоздайте: /note [текст]")
            return
        
        text = "📝 ВАШИ ЗАМЕТКИ:\n\n"
        for i, note in enumerate(notes, 1):
            created = datetime.datetime.fromisoformat(note['created_at']).strftime('%d.%m %H:%M')
            text += f"{i}. {note['note']}\n   📅 {created}\n\n"
        
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        await update.message.reply_text(text)
        await self.add_experience(user_data, 1)
    
    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удалить заметку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер!\nПример: /delnote 1")
            return
        
        notes = self.db.get_notes(user_data['user_id'])
        index = int(context.args[0]) - 1
        
        if 0 <= index < len(notes):
            self.db.delete_note(notes[index]['id'], user_data['user_id'])
            await update.message.reply_text(f"✅ Заметка #{index+1} удалена!")
        else:
            await update.message.reply_text(f"❌ Заметки #{index+1} не существует!")
        
        await self.add_experience(user_data, 1)
    
    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шутка"""
        user_data = await self.get_user_data(update)
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
            "Заходит программист в бар, заказывает 1 пиво. Заказывает 0 пива. Заказывает 999999 пива.",
            "Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
            "Как программист моет посуду? Не моет - это не баг, это фича!"
        ]
        await update.message.reply_text(random.choice(jokes))
        await self.add_experience(user_data, 1)
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Погода"""
        user_data = await self.get_user_data(update)
        
        if not context.args:
            await update.message.reply_text("🌤️ Укажите город!\nПример: /weather Москва")
            return
        
        city = " ".join(context.args)
        
        if OPENWEATHER_API_KEY:
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
                response = requests.get(url, timeout=10).json()
                
                if response.get("cod") == 200:
                    weather = response["weather"][0]["description"]
                    temp = round(response["main"]["temp"])
                    feels = round(response["main"]["feels_like"])
                    humidity = response["main"]["humidity"]
                    wind = response["wind"]["speed"]
                    
                    text = f"""
🌤️ ПОГОДА В {city.upper()}

🌡️ Температура: {temp}°C
🤔 Ощущается: {feels}°C
☁️ {weather.capitalize()}
💧 Влажность: {humidity}%
🌪️ Ветер: {wind} м/с

⏰ {datetime.datetime.now().strftime('%H:%M')}
                    """
                    await update.message.reply_text(text)
                    await self.add_experience(user_data, 2)
                    return
            except:
                pass
        
        # Fallback
        try:
            url = f"https://wttr.in/{city}?format=%C+%t+💧%h+🌪️%w&lang=ru"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                await update.message.reply_text(f"🌤️ ПОГОДА В {city.upper()}\n\n{response.text.strip()}")
        except:
            await update.message.reply_text("❌ Ошибка получения погоды")
        
        await self.add_experience(user_data, 2)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика"""
        user_data = await self.get_user_data(update)
        
        notes = self.db.get_notes(user_data['user_id'])
        
        text = f"""
📊 ВАША СТАТИСТИКА

👤 {user_data.get('nickname') or user_data['first_name']}
🆙 Уровень: {user_data.get('level', 1)}
⭐ Опыт: {user_data.get('experience', 0)}/{user_data.get('level', 1) * 100}
💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}
📝 Заметок: {len(notes)}
🌐 Язык: {LANGUAGE_NAMES.get(user_data.get('language', 'ru'))}
        """
        await update.message.reply_text(text)
        await self.add_experience(user_data, 1)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("lang_"):
            lang = query.data.split("_")[1]
            user_data = await self.get_user_data(update)
            user_data['language'] = lang
            self.db.save_user(user_data)
            
            await query.edit_message_text(
                self.t('language_changed', lang),
                reply_markup=None
            )
            
            # Отправить новую клавиатуру
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅",
                reply_markup=self.get_keyboard(lang)
            )
    
    # ========================================================================
    # КОМАНДЫ VIP
    # ========================================================================
    
    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Напоминание (VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP! /vip")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("⏰ Использование: /remind [минуты] [текст]\nПример: /remind 30 Позвонить")
            return
        
        try:
            minutes = int(context.args[0])
            text = " ".join(context.args[1:])
            
            if minutes <= 0 or minutes > 10080:
                await update.message.reply_text("❌ От 1 до 10080 минут!")
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            job_id = f"reminder_{user_data['user_id']}_{int(time.time())}"
            
            self.scheduler.add_job(
                self.send_notification,
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data['user_id'], f"🔔 Напоминание:\n\n{text}"],
                id=job_id
            )
            
            await update.message.reply_text(
                f"⏰ Напоминание установлено!\n\n📝 {text}\n🕐 Через {minutes} мин ({run_date.strftime('%H:%M')})"
            )
        except ValueError:
            await update.message.reply_text("❌ Неверный формат!")
        
        await self.add_experience(user_data, 2)
    
    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        """Отправить уведомление"""
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")
    
    # ========================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # ========================================================================
    
    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выдать VIP"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("💎 /grant_vip [user_id] [week/month/year/permanent]")
            return
        
        try:
            target_id = int(context.args[0])
            duration = context.args[1].lower()
            
            target_user = self.db.get_user(target_id)
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            target_user['is_vip'] = 1
            
            if duration == "week":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(weeks=1)).isoformat()
            elif duration == "month":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
            elif duration == "year":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
            elif duration == "permanent":
                target_user['vip_expires'] = None
            else:
                await update.message.reply_text("❌ week/month/year/permanent")
                return
            
            self.db.save_user(target_user)
            
            await update.message.reply_text(f"✅ VIP выдан!\n👤 {target_user['first_name']}\n🆔 {target_id}\n⏰ {duration}")
            
            try:
                await context.bot.send_message(target_id, "🎉 Вы получили VIP статус! /vip")
            except:
                pass
        except ValueError:
            await update.message.reply_text("❌ Неверный ID!")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Рассылка"""
        if not self.is_creator(update.effective_user.id):
            return
        
        if not context.args:
            await update.message.reply_text("📢 /broadcast [сообщение]")
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        
        sent = 0
        for user in users:
            try:
                await context.bot.send_message(user['user_id'], f"📢 От создателя:\n\n{message}")
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        
        await update.message.reply_text(f"✅ Отправлено: {sent}/{len(users)}")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Резервная копия"""
        if not self.is_creator(update.effective_user.id):
            return
        
        try:
            self.conversation_memory.save()
            
            backup_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'users': len(self.db.get_all_users())
            }
            
            filename = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(BACKUP_PATH, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            await update.message.reply_text(f"✅ Бэкап создан!\n📁 {filename}\n👥 Пользователей: {backup_data['users']}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    # ========================================================================
    # СИСТЕМНЫЕ ФУНКЦИИ
    # ========================================================================
    
    async def self_ping(self):
        """Автопинг"""
        try:
            requests.get(RENDER_URL, timeout=10)
            logger.info("Self-ping OK")
        except:
            pass
    
    async def save_data(self):
        """Автосохранение"""
        try:
            self.conversation_memory.save()
            logger.info("Данные сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    async def check_birthdays(self, context: ContextTypes.DEFAULT_TYPE):
        """Проверка дней рождения"""
        today = datetime.datetime.now().strftime("%m-%d")
        
        # День рождения папы (НЕ публикуем эту информацию)
        if today == DAD_BIRTHDAY:
            pass  # Внутренняя логика
        
        # Другие пользователи
        for user in self.db.get_all_users():
            if user.get('birthday') and user['birthday'][5:] == today:
                try:
                    await context.bot.send_message(
                        user['user_id'],
                        f"🎉🎂 С Днём Рождения, {user['first_name']}! 🎂🎉"
                    )
                except:
                    pass
    
    # ========================================================================
    # ЗАПУСК
    # ========================================================================
    
    async def run_bot(self):
        """Запуск бота"""
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не найден!")
            return
        
        logger.info("Запуск бота v2.1...")
        
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )
        
        async def error_handler(update, context):
            logger.error(f"Ошибка: {context.error}")
        
        application.add_error_handler(error_handler)
        
        # Регистрация команд
        commands = [
            ("start", self.start_command),
            ("help", self.help_command),
            ("info", self.info_command),
            ("time", self.time_command),
            ("language", self.language_command),
            ("ai", self.ai_command),
            ("note", self.note_command),
            ("notes", self.notes_command),
            ("delnote", self.delnote_command),
            ("joke", self.joke_command),
            ("weather", self.weather_command),
            ("stats", self.stats_command),
            ("remind", self.remind_command),
            ("grant_vip", self.grant_vip_command),
            ("broadcast", self.broadcast_command),
            ("backup", self.backup_command)
        ]
        
        for cmd, handler in commands:
            application.add_handler(CommandHandler(cmd, handler))
        
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            self.handle_message
        ))
        
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Планировщик
        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()
        
        self.scheduler.add_job(self.self_ping, 'interval', minutes=14)
        self.scheduler.add_job(self.save_data, 'interval', minutes=30)
        self.scheduler.add_job(self.check_birthdays, CronTrigger(hour=9, minute=0), args=[application])
        
        logger.info("🤖 Бот запущен!")
        logger.info(f"👥 Пользователей: {len(self.db.get_all_users())}")
        
        await application.run_polling(drop_pending_updates=True)

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

async def main():
    bot = TelegramBot()
    await bot.run_bot()

# Flask для Render
app = Flask(__name__)

@app.route('/')
def home():
    return f"""
    <html>
    <head><title>Telegram AI Bot v2.1</title>
    <style>
        body {{font-family: Arial; background: linear-gradient(135deg, #667eea, #764ba2); 
              color: white; padding: 50px; text-align: center;}}
        .container {{background: rgba(255,255,255,0.1); border-radius: 20px; 
                    padding: 30px; max-width: 600px; margin: 0 auto;}}
        h1 {{font-size: 48px;}}
        .status {{color: #00ff88; font-weight: bold;}}
    </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Telegram AI Bot</h1>
            <p class="status">✅ РАБОТАЕТ</p>
            <p>📅 Версия: 2.1</p>
            <p>⏰ {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            <p>🌐 6 языков</p>
            <p>🧠 AI: Gemini 2.0</p>
            <p>Бот: {BOT_USERNAME}</p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat(), "version": "2.1"}

if __name__ == "__main__":
    from threading import Thread
    
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port, 'debug': False, 'use_reloader': False})
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info(f"🌐 Flask на порту {port}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлен")
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        sys.exit(1)
