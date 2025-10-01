#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПРОФЕССИОНАЛЬНЫЙ TELEGRAM AI-АССИСТЕНТ v4.1
Улучшенный интерфейс с интерактивными меню, персонализацией и умными ответами
"""

import asyncio
import logging
import json
import random
import time
import datetime
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
import nest_asyncio
from flask import Flask
import pytz
import sqlite3
import string
import math

nest_asyncio.apply()

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import google.generativeai as genai

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
CONVERSATIONS_FILE = "conversations.json"
BACKUP_PATH = "bot_backup.json"
DB_FILE = "bot_database.db"

CREATOR_ID = 7108255346
CREATOR_USERNAME = "Ernest_Kostevich"
DAD_USERNAME = "mkostevich"
DAD_BIRTHDAY_MONTH_DAY = "10-03"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.0-flash-exp"

TIMEZONES = {
    'moscow': 'Europe/Moscow',
    'berlin': 'Europe/Berlin',
    'london': 'Europe/London',
    'newyork': 'America/New_York',
    'tokyo': 'Asia/Tokyo'
}

@dataclass
class UserData:
    user_id: int
    username: str
    first_name: str
    is_vip: bool = False
    vip_expires: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    reminders: List[Dict] = field(default_factory=list)
    memory_data: Dict = field(default_factory=dict)
    preferences: Dict = field(default_factory=dict)
    nickname: Optional[str] = None
    level: int = 1
    experience: int = 0
    achievements: List[str] = field(default_factory=list)
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    preferred_timezone: str = 'moscow'

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            user_id=data['user_id'],
            username=data.get('username', ''),
            first_name=data.get('first_name', ''),
            is_vip=data.get('is_vip', False),
            vip_expires=data.get('vip_expires'),
            notes=data.get('notes', []),
            reminders=data.get('reminders', []),
            memory_data=data.get('memory_data', {}),
            preferences=data.get('preferences', {}),
            nickname=data.get('nickname'),
            level=data.get('level', 1),
            experience=data.get('experience', 0),
            achievements=data.get('achievements', []),
            last_activity=data.get('last_activity', datetime.datetime.now().isoformat()),
            preferred_timezone=data.get('preferred_timezone', 'moscow')
        )

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'is_vip': self.is_vip,
            'vip_expires': self.vip_expires,
            'notes': self.notes,
            'reminders': self.reminders,
            'memory_data': self.memory_data,
            'preferences': self.preferences,
            'nickname': self.nickname,
            'level': self.level,
            'experience': self.experience,
            'achievements': self.achievements,
            'last_activity': self.last_activity,
            'preferred_timezone': self.preferred_timezone
        }

class AITools:
    @staticmethod
    def get_datetime(timezone_key: str = 'moscow') -> Dict:
        tz = pytz.timezone(TIMEZONES.get(timezone_key, 'Europe/Moscow'))
        now = datetime.datetime.now(tz)
        return {
            "date": now.strftime('%d.%m.%Y'),
            "time": now.strftime('%H:%M:%S'),
            "day_of_week": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][now.weekday()],
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "timezone": timezone_key.capitalize()
        }

    @staticmethod
    def get_all_timezones() -> str:
        text = ""
        for key in TIMEZONES:
            dt = AITools.get_datetime(key)
            text += f"🕒 {dt['timezone']}: {dt['time']} ({dt['date']})\n"
        return text

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self.cache = {}

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_vip BOOLEAN DEFAULT FALSE,
                vip_expires TEXT,
                notes TEXT DEFAULT '[]',
                reminders TEXT DEFAULT '[]',
                memory_data TEXT DEFAULT '{}',
                preferences TEXT DEFAULT '{}',
                nickname TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                achievements TEXT DEFAULT '[]',
                last_activity TEXT,
                preferred_timezone TEXT DEFAULT 'moscow'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                message TEXT,
                timestamp TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT,
                timestamp TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                command TEXT PRIMARY KEY,
                usage_count INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()

    def get_user(self, user_id: int) -> Optional[UserData]:
        if user_id in self.cache:
            return self.cache[user_id]
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        if row:
            data = {
                'user_id': row[0], 'username': row[1], 'first_name': row[2],
                'is_vip': bool(row[3]), 'vip_expires': row[4],
                'notes': json.loads(row[5]), 'reminders': json.loads(row[6]),
                'memory_data': json.loads(row[7]), 'preferences': json.loads(row[8]),
                'nickname': row[9], 'level': row[10], 'experience': row[11],
                'achievements': json.loads(row[12]), 'last_activity': row[13],
                'preferred_timezone': row[14]
            }
            user = UserData.from_dict(data)
            self.cache[user_id] = user
            return user
        return None

    def save_user(self, user_data: UserData):
        user_data.last_activity = datetime.datetime.now().isoformat()
        params = (
            user_data.user_id, user_data.username, user_data.first_name, user_data.is_vip,
            user_data.vip_expires, json.dumps(user_data.notes, ensure_ascii=False),
            json.dumps(user_data.reminders, ensure_ascii=False),
            json.dumps(user_data.memory_data, ensure_ascii=False),
            json.dumps(user_data.preferences, ensure_ascii=False),
            user_data.nickname, user_data.level, user_data.experience,
            json.dumps(user_data.achievements, ensure_ascii=False),
            user_data.last_activity, user_data.preferred_timezone
        )
        self.cursor.execute('''
            INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', params)
        self.conn.commit()
        self.cache[user_data.user_id] = user_data
        self._backup()

    def get_conversation(self, user_id: int) -> List[Dict]:
        self.cursor.execute('SELECT role, message, timestamp FROM conversations WHERE user_id = ? ORDER BY id', (user_id,))
        return [{"role": r[0], "message": r[1], "timestamp": r[2]} for r in self.cursor.fetchall()]

    def add_to_conversation(self, user_id: int, role: str, message: str):
        timestamp = datetime.datetime.now().isoformat()
        self.cursor.execute('INSERT INTO conversations (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)',
                            (user_id, role, message, timestamp))
        self.conn.commit()
        self._backup()

    def clear_conversation(self, user_id: int):
        self.cursor.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
        self.conn.commit()
        self._backup()

    def log_command(self, user_id: int, command: str):
        timestamp = datetime.datetime.now().isoformat()
        self.cursor.execute('INSERT INTO logs (user_id, command, timestamp) VALUES (?, ?, ?)',
                            (user_id, command, timestamp))
        self.cursor.execute('INSERT OR REPLACE INTO statistics (command, usage_count) VALUES (?, COALESCE((SELECT usage_count FROM statistics WHERE command = ?), 0) + 1)',
                            (command, command))
        self.conn.commit()
        self._backup()

    def get_all_users(self) -> List[UserData]:
        self.cursor.execute('SELECT * FROM users')
        return [UserData.from_dict({
            'user_id': row[0], 'username': row[1], 'first_name': row[2],
            'is_vip': bool(row[3]), 'vip_expires': row[4],
            'notes': json.loads(row[5]), 'reminders': json.loads(row[6]),
            'memory_data': json.loads(row[7]), 'preferences': json.loads(row[8]),
            'nickname': row[9], 'level': row[10], 'experience': row[11],
            'achievements': json.loads(row[12]), 'last_activity': row[13],
            'preferred_timezone': row[14]
        }) for row in self.cursor.fetchall()]

    def _backup(self):
        try:
            convs = {}
            self.cursor.execute('SELECT DISTINCT user_id FROM conversations')
            for (uid,) in self.cursor.fetchall():
                convs[str(uid)] = self.get_conversation(uid)
            with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(convs, f, ensure_ascii=False, indent=2)
            with open(BACKUP_PATH, 'w', encoding='utf-8') as f:
                backup = {
                    'users': [u.to_dict() for u in self.get_all_users()],
                    'conversations': convs,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                json.dump(backup, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Backup error: {e}")

class TelegramBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.gemini_model = None
        self.tools = AITools()
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("Gemini initialized")
            except Exception as e:
                logger.error(f"Gemini error: {e}")
        self.scheduler = AsyncIOScheduler()
        self.maintenance_mode = False
        self.scheduler.add_job(self.check_birthdays, 'cron', hour=9, minute=0)
        self.scheduler.add_job(self.self_ping, 'interval', minutes=14)

    async def get_user_data(self, update: Update) -> UserData:
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        if not user_data:
            user_data = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                preferred_timezone='moscow'
            )
            if self.is_creator(user.id):
                user_data.is_vip = True
                user_data.vip_expires = None
            self.db.save_user(user_data)
        return user_data

    def is_creator(self, user_id: int) -> bool:
        return user_id == CREATOR_ID

    def is_vip(self, user_data: UserData) -> bool:
        if not user_data.is_vip:
            return False
        if user_data.vip_expires:
            try:
                expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                if datetime.datetime.now() > expires_date:
                    user_data.is_vip = False
                    user_data.vip_expires = None
                    self.db.save_user(user_data)
                    return False
            except:
                return False
        return True

    async def add_experience(self, user_data: UserData, points: int = 1):
        user_data.experience += points
        required_exp = user_data.level * 100
        if user_data.experience >= required_exp:
            user_data.level += 1
            user_data.experience = 0
            user_data.achievements.append(f"Достиг уровня {user_data.level}")
        self.db.save_user(user_data)

    def create_ai_prompt(self, user_message: str, conversation_history: List[Dict], user_data: UserData) -> str:
        dt = self.tools.get_datetime(user_data.preferred_timezone)
        preferences = "\n".join(f"- {k}: {v}" for k, v in user_data.preferences.items()) if user_data.preferences else "Нет указанных предпочтений"
        system_context = f"""Ты профессиональный, дружелюбный AI-ассистент.

ТЕКУЩАЯ ИНФОРМАЦИЯ:
- Дата: {dt['date']} ({dt['day_of_week']})
- Время ({dt['timezone']}): {dt['time']}

ПЕРСОНАЛИЗАЦИЯ:
- Имя пользователя: {user_data.first_name} ({user_data.nickname or 'без никнейма'})
- Предпочтения: {preferences}

ПРАВИЛА:
- Отвечай на русском, дружелюбно и структурировано
- Используй эмодзи для визуальности
- Помни весь контекст, предугадывай нужды
- Структура: заголовки, списки, кнопки если нужно"""

        history_text = "\n".join([
            f"{'Пользователь' if msg['role'] == 'user' else 'Ты'}: {msg['message']}"
            for msg in conversation_history[-50:]
        ])
        
        return f"""{system_context}

ИСТОРИЯ ДИАЛОГА:
{history_text if history_text else '(новый диалог)'}

НОВОЕ СООБЩЕНИЕ:
{user_message}

Твой ответ:"""

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Бот на обслуживании.")
            return
        
        user_data = await self.get_user_data(update)
        message = update.message.text
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            self.db.add_to_conversation(user_data.user_id, "user", message)
            conversation_history = self.db.get_conversation(user_data.user_id)
            prompt = self.create_ai_prompt(message, conversation_history, user_data)
            
            response = self.gemini_model.generate_content(prompt)
            bot_response = response.text
            
            self.db.add_to_conversation(user_data.user_id, "assistant", bot_response)
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📋 Меню", callback_data="start")]])
            await update.message.reply_text(bot_response, reply_markup=reply_markup)
            await self.add_experience(user_data, 1)
            
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Ошибка AI: {e}")
    
    # Базовые команды
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Помощь", callback_data="help"), InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🕒 Время", callback_data="time"), InlineKeyboardButton("📊 Профиль", callback_data="profile")],
            [InlineKeyboardButton("🎮 Развлечения", callback_data="entertainment"), InlineKeyboardButton("🛠 Утилиты", callback_data="utilities")]
        ])
        
        message = f"🤖 Добро пожаловать, {user_data.first_name}!\n\nЯ ваш умный ассистент. Выберите опцию ниже или просто напишите вопрос."
        await update.message.reply_text(message, reply_markup=keyboard)
        await self.add_experience(user_data, 1)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/help")
        
        help_text = """📋 **Руководство по ассистенту**

### 🏠 Основное
- /start - Главное меню
- /help - Это руководство
- /info - О ассистенте
- /status - Статус
- /uptime - Время работы

### 💬 AI-чат
- Просто напишите сообщение!
- /ai [вопрос] - Прямой вопрос AI
- /clear - Очистить диалог

### 📝 Заметки
- /note [текст] - Добавить
- /notes - Просмотр
- /delnote [№] - Удалить
- /findnote [слово] - Поиск
- /clearnotes - Очистить все

### ⏰ Время/Дата
- /time - Текущее время
- /date - Дата

### 🎉 Развлечения
- /joke - Шутка
- /fact - Факт
- /quote - Цитата
- /quiz - Викторина
- /coin - Монетка
- /dice - Кубик
- /8ball [вопрос] - Шар предсказаний

### 🔢 Математика
- /math [выражение] - Простой расчет
- /calculate [выражение] - Сложный

### 🛠 Утилиты
- /password [длина] - Генератор пароля
- /qr [текст] - QR-код
- /shorturl [ссылка] - Сократить URL
- /ip - IP-адрес
- /weather [город] - Погода
- /currency [из] [в] - Конвертер валют
- /translate [язык] [текст] - Перевод

### 🧠 Память
- /memorysave [ключ] [значение] - Сохранить
- /memoryget [ключ] - Получить
- /memorylist - Список
- /memorydel [ключ] - Удалить

### 📊 Прогресс
- /rank - Уровень и опыт
"""

        if self.is_vip(user_data):
            help_text += """### 💎 VIP-функции
- /vip - Статус VIP
- /remind [мин] [текст] - Напоминание
- /reminders - Список
- /delreminder [№] - Удалить
- /nickname [имя] - Установить ник
- /profile - Полный профиль
"""

        if self.is_creator(user_data.user_id):
            help_text += """### 👑 Админ
- /grant_vip [id/@user] [duration] - Выдать VIP
- /revoke_vip [id/@user] - Отозвать
- /broadcast [текст] - Рассылка
- /users - Пользователи
- /stats - Статистика
- /maintenance [on/off] - Обслуживание
- /backup - Бэкап
"""

        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)
        await self.add_experience(user_data, 1)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info = f"""🤖 **Информация об ассистенте**

Версия: 4.1
Создатель: @{CREATOR_USERNAME}
Функций: 50+
AI: {"Gemini 2.0 ✅" if self.gemini_model else "❌"}
База данных: SQLite с полной памятью
Интерфейс: Интерактивные меню и кнопки
Хостинг: Render 24/7
"""
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(info, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        total_users = len(self.db.get_all_users())
        self.db.cursor.execute('SELECT COUNT(*) FROM logs')
        total_commands = self.db.cursor.fetchone()[0]
        self.db.cursor.execute('SELECT COUNT(DISTINCT user_id) FROM conversations')
        conversations_count = self.db.cursor.fetchone()[0]
        
        status = f"""⚡ **Статус ассистента**

Онлайн: ✅
Версия: 4.1
Пользователей: {total_users}
Команд выполнено: {total_commands}
Активных диалогов: {conversations_count}
AI: {"✅" if self.gemini_model else "❌"}
"""
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(status, reply_markup=reply_markup)
    
    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/uptime")
        
        text = f"⏱️ Ассистент онлайн!\n👥 Пользователей: {len(self.db.get_all_users())}\n\nСпасибо, что используете меня!"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clear")
        
        count = len(self.db.get_conversation(user_data.user_id))
        self.db.clear_conversation(user_data.user_id)
        text = f"✅ История диалога очищена ({count} сообщений).\n\nНачнем заново!"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            text = "🤖 Задайте вопрос после /ai!\n\nПример: /ai Расскажи о Python"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        query = " ".join(context.args)
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            response = self.gemini_model.generate_content(query)
            text = response.text
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        except Exception as e:
            await update.message.reply_text("❌ Ошибка AI")
    
    # Заметки с улучшенным интерфейсом
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/note")
        
        if not context.args:
            text = "📝 Укажите текст заметки после команды!\n\nПример: /note Купить молоко"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        note = " ".join(context.args)
        user_data.notes.append(note)
        self.db.save_user(user_data)
        text = f"✅ Заметка сохранена: '{note}'\n\nВсего заметок: {len(user_data.notes)}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Просмотреть заметки", callback_data="notes")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            text = "❌ У вас нет заметок.\n\nДобавьте новую с /note [текст]"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        notes_text = "\n\n".join(f"**{i+1}.** {note}" for i, note in enumerate(user_data.notes))
        text = f"📝 **Ваши заметки:**\n\n{notes_text}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Удалить заметку", callback_data="delnote"), InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            text = "❌ Укажите номер заметки!\n\nПример: /delnote 1"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Просмотреть заметки", callback_data="notes")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            deleted = user_data.notes.pop(index)
            self.db.save_user(user_data)
            text = f"✅ Заметка удалена: '{deleted}'\n\nОставшиеся заметки: {len(user_data.notes)}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Просмотреть заметки", callback_data="notes")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ Неверный номер!")
    
    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            text = "🔍 Укажите ключевое слово!\n\nПример: /findnote молоко"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        keyword = " ".join(context.args).lower()
        found = [(i+1, note) for i, note in enumerate(user_data.notes) if keyword in note.lower()]
        
        if found:
            notes_text = "\n\n".join(f"**{i}.** {note}" for i, note in found)
            text = f"🔍 **Найдено ({len(found)}):** \n\n{notes_text}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Удалить заметку", callback_data="delnote")]])
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ Ничего не найдено!")
    
    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clearnotes")
        
        count = len(user_data.notes)
        user_data.notes = []
        self.db.save_user(user_data)
        text = f"✅ Все заметки очищены ({count})!\n\nДобавьте новые с /note"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    # Время и дата с улучшениями
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")
        
        dt = self.tools.get_datetime(user_data.preferred_timezone)
        text = f"⏰ **Текущее время**\n\n**{dt['timezone']}**: {dt['time']}\nДата: {dt['date']} ({dt['day_of_week']})\n\n**Другие зоны:**\n{self.tools.get_all_timezones()}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 Сменить зону", callback_data="change_timezone"), InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")
        
        dt = self.tools.get_datetime(user_data.preferred_timezone)
        text = f"📅 **Сегодняшняя дата**\n\n{dt['date']} ({dt['day_of_week']})\nВремя: {dt['time']} ({dt['timezone']})"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏰ Время", callback_data="time"), InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    # Развлечения с кнопками
    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")
        
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
            "Заходит программист в бар... и выходит из бара, входит в бар, выходит из бара — тестирует функцию.",
            "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного — это проблема оборудования."
        ]
        text = f"😄 **Шутка дня:**\n\n{random.choice(jokes)}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Ещё шутка", callback_data="joke"), InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")
        
        facts = [
            "🧠 Человеческий мозг содержит около 86 миллиардов нейронов.",
            "🐙 У осьминогов три сердца: два для жабр, одно для тела.",
            "🌍 Земля вращается со скоростью около 1670 км/ч на экваторе."
        ]
        text = random.choice(facts)
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Ещё факт", callback_data="fact"), InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")
        
        quotes = [
            "💫 'Будь собой. Остальные роли заняты.' — Оскар Уайльд",
            "🚀 'Единственный способ делать великую работу — любить то, что делаешь.' — Стив Джобс"
        ]
        text = random.choice(quotes)
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Ещё цитата", callback_data="quote"), InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quiz")
        
        questions = [
            {"q": "Сколько дней в високосном году?", "a": "366"},
            {"q": "Какова столица Австралии?", "a": "Канберра"}
        ]
        q = random.choice(questions)
        text = f"❓ **Викторина:** {q['q']}\n\nНапишите ответ ниже!"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый вопрос", callback_data="quiz"), InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/coin")
        
        result = random.choice(["🪙 Орёл!", "🪙 Решка!"])
        text = f"{result}\n\nБросить ещё раз?"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Да", callback_data="coin"), InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/dice")
        
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        text = f"🎲 {dice_faces[result-1]} Выпало: {result}\n\nБросить снова?"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Да", callback_data="dice"), InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            text = "🔮 Задайте вопрос!\n\nПример: /8ball Будет ли дождь завтра?"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        answers = ["✅ Да!", "❌ Нет", "🤔 Возможно", "⏳ Спроси позже", "⭐ Без сомнений!", "🚫 Ни в коем случае"]
        text = f"🔮 **Ответ:** {random.choice(answers)}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый вопрос", callback_data="8ball"), InlineKeyboardButton("🔙 Развлечения", callback_data="entertainment")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    # Математика
    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/math")
        
        if not context.args:
            text = "🔢 Укажите выражение!\n\nПример: /math 2 + 2 * 2"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        expression = " ".join(context.args)
        try:
            result = eval(expression)
            text = f"🔢 **Расчет:** {expression} = {result}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый расчет", callback_data="math"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        except:
            await update.message.reply_text("❌ Ошибка в выражении!")
    
    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/calculate")
        
        if not context.args:
            text = "🧮 Укажите выражение!\n\nПример: /calculate sqrt(16) + sin(pi/2)"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        expression = " ".join(context.args)
        try:
            safe_dict = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "pi": math.pi, "e": math.e}
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            text = f"🧮 **Расчет:** {expression} = {result}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый расчет", callback_data="calculate"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        except:
            await update.message.reply_text("❌ Ошибка в выражении!")
    
    # Утилиты
    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/password")
        
        length = 12 if not context.args or not context.args[0].isdigit() else min(int(context.args[0]), 50)
        
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choice(chars) for _ in range(length))
        text = f"🔐 **Сгенерированный пароль:**\n`{password}`\n\nДлина: {length}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый пароль", callback_data="password"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/qr")
        
        if not context.args:
            text = "📱 Укажите текст для QR-кода!\n\nПример: /qr https://example.com"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={requests.utils.quote(text)}"
        caption = f"📱 QR-код для: {text[:50]}..."
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый QR", callback_data="qr"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
        await context.bot.send_photo(update.effective_chat.id, qr_url, caption=caption, reply_markup=reply_markup)
    
    async def shorturl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/shorturl")
        
        if not context.args:
            text = "🔗 Укажите URL для сокращения!\n\nПример: /shorturl https://example.com"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        url = context.args[0]
        if not url.startswith('http'):
            url = 'https://' + url
        
        try:
            response = requests.get(f"https://is.gd/create.php?format=simple&url={requests.utils.quote(url)}", timeout=10)
            if response.status_code == 200:
                short = response.text.strip()
                text = f"🔗 **Сокращенный URL:** {short}"
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый URL", callback_data="shorturl"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
                await update.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text("❌ Ошибка сокращения")
        except:
            await update.message.reply_text("❌ Ошибка подключения")
    
    async def ip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ip")
        
        try:
            response = requests.get('https://httpbin.org/ip', timeout=5)
            ip = response.json().get('origin', 'Неизвестно')
            text = f"🌍 **Ваш IP-адрес:** {ip}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        except:
            await update.message.reply_text("❌ Не удалось получить IP")
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        city = " ".join(context.args) if context.args else "Москва"
        try:
            response = requests.get(f"http://wttr.in/{requests.utils.quote(city)}?format=%l:+%c+%t+%w+%h+%p", timeout=10)
            if response.status_code == 200:
                weather = response.text.strip()
                text = f"🌤️ **Погода в {city}:**\n\n{weather}"
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Другой город", callback_data="weather"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
                await update.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text("❌ Город не найден")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/currency")
        
        if len(context.args) < 2:
            text = "💰 Укажите валюты!\n\nПример: /currency USD RUB"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        from_cur, to_cur = context.args[0].upper(), context.args[1].upper()
        try:
            url = f"https://api.freecurrencyapi.com/v1/latest?apikey={CURRENCY_API_KEY}&currencies={to_cur}&base_currency={from_cur}"
            response = requests.get(url, timeout=10).json()
            rate = response.get("data", {}).get(to_cur)
            
            if rate:
                text = f"💰 **Конвертер:** 1 {from_cur} = {rate:.4f} {to_cur}"
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый курс", callback_data="currency"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
                await update.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text("❌ Ошибка")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            text = "🌐 Укажите язык и текст!\n\nПример: /translate en Привет, мир"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        target_lang = context.args[0]
        text_input = " ".join(context.args[1:])
        
        try:
            response = self.gemini_model.generate_content(f"Переведи на {target_lang}: {text_input}")
            translated = response.text
            text = f"🌐 **Перевод:**\n\n{translated}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Новый перевод", callback_data="translate"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        except:
            await update.message.reply_text("❌ Ошибка")
    
    # Память
    async def memorysave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorysave")
        
        if len(context.args) < 2:
            text = "🧠 Укажите ключ и значение!\n\nПример: /memorysave email example@mail.com"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        key = context.args[0]
        value = " ".join(context.args[1:])
        user_data.memory_data[key] = value
        self.db.save_user(user_data)
        text = f"🧠 **Сохранено:** {key} = {value}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список памяти", callback_data="memorylist"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def memoryget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memoryget")
        
        if not context.args:
            text = "🧠 Укажите ключ!\n\nПример: /memoryget email"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        key = context.args[0]
        value = user_data.memory_data.get(key)
        
        if value:
            text = f"🧠 **Значение:** {key} = {value}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список памяти", callback_data="memorylist"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
    
    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorylist")
        
        if not user_data.memory_data:
            text = "🧠 Память пуста!\n\nСохраните данные с /memorysave"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        memory_text = "\n\n".join(f"**{key}:** {value}" for key, value in user_data.memory_data.items())
        text = f"🧠 **Ваша память:**\n\n{memory_text}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Удалить запись", callback_data="memorydel"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def memorydel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorydel")
        
        if not context.args:
            text = "🧠 Укажите ключ для удаления!\n\nПример: /memorydel email"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список памяти", callback_data="memorylist")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        key = context.args[0]
        if key in user_data.memory_data:
            del user_data.memory_data[key]
            self.db.save_user(user_data)
            text = f"🧠 **Удалено:** {key}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список памяти", callback_data="memorylist"), InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
    
    # Прогресс
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")
        
        req = user_data.level * 100
        progress = (user_data.experience / req) * 100 if req > 0 else 0
        achievements = "\n".join(user_data.achievements) if user_data.achievements else "Нет достижений"
        
        text = f"🏅 **Ваш прогресс**\n\n**Уровень:** {user_data.level}\n**Опыт:** {user_data.experience}/{req} ({progress:.1f}%)\n**VIP:** {'✅' if self.is_vip(user_data) else '❌'}\n\n**Достижения:**\n{achievements}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Статистика", callback_data="stats"), InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    # VIP команды с улучшениями
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if not self.is_vip(user_data):
            text = "💎 **VIP доступ**\n\nСвяжитесь с @{CREATOR_USERNAME} для активации.\n\nПреимущества: напоминания, профиль, никнейм."
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        expires = 'бессрочно' if not user_data.vip_expires else datetime.datetime.fromisoformat(user_data.vip_expires).strftime('%d.%m.%Y')
        text = f"💎 **VIP статус активен**\n\nДо: {expires}\n\nНаслаждайтесь премиум-функциями!"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Профиль", callback_data="profile"), InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/remind")
        
        if len(context.args) < 2:
            text = "⏰ Укажите минуты и текст!\n\nПример: /remind 30 Купить хлеб"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VIP", callback_data="vip")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        try:
            minutes = int(context.args[0])
            text_remind = " ".join(context.args[1:])
            
            if minutes <= 0:
                await update.message.reply_text("❌ Время должно быть положительным!")
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            job = self.scheduler.add_job(
                self.send_notification,
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, f"🔔 Напоминание: {text_remind}"],
                id=f"rem_{user_data.user_id}_{int(time.time())}"
            )
            
            user_data.reminders.append({"id": job.id, "text": text_remind, "time": run_date.isoformat()})
            self.db.save_user(user_data)
            
            text = f"⏰ Напоминание установлено на {minutes} минут: '{text_remind}'"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список напоминаний", callback_data="reminders"), InlineKeyboardButton("🔙 VIP", callback_data="vip")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        except:
            await update.message.reply_text("❌ Ошибка установки!")
    
    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/reminders")
        
        if not user_data.reminders:
            text = "❌ Нет активных напоминаний.\n\nУстановите новое с /remind"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VIP", callback_data="vip")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        reminders_text = "\n\n".join(f"**{i+1}.** {r['text']} (в {datetime.datetime.fromisoformat(r['time']).strftime('%H:%M %d.%m')})" for i, r in enumerate(user_data.reminders))
        text = f"⏰ **Ваши напоминания:**\n\n{reminders_text}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Удалить", callback_data="delreminder"), InlineKeyboardButton("🔙 VIP", callback_data="vip")]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def delreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/delreminder")
        
        if not context.args or not context.args[0].isdigit():
            text = "❌ Укажите номер напоминания!\n\nПример: /delreminder 1"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список", callback_data="reminders")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.reminders):
            job_id = user_data.reminders[index]['id']
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
            deleted = user_data.reminders.pop(index)['text']
            self.db.save_user(user_data)
            text = f"✅ Напоминание удалено: '{deleted}'"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список напоминаний", callback_data="reminders"), InlineKeyboardButton("🔙 VIP", callback_data="vip")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ Неверный номер!")
    
    async def nickname_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/nickname")
        
        if not context.args:
            text = "👤 Укажите новый никнейм!\n\nПример: /nickname SuperUser"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VIP", callback_data="vip")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        nickname = " ".join(context.args)
        user_data.nickname = nickname
        self.db.save_user(user_data)
        text = f"✅ Никнейм установлен: {nickname}"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Профиль", callback_data="profile"), InlineKeyboardButton("🔙 VIP", callback_data="vip")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/profile")
        
        conv_count = len(self.db.get_conversation(user_data.user_id))
        preferences = "\n".join(f"- {k}: {v}" for k, v in user_data.preferences.items()) if user_data.preferences else "Нет предпочтений"
        text = f"""👤 **Ваш профиль**

**Имя:** {user_data.first_name}
**Никнейм:** {user_data.nickname or "Не установлен"}
**Уровень:** {user_data.level}
**Опыт:** {user_data.experience}
**Заметок:** {len(user_data.notes)}
**Памяти:** {len(user_data.memory_data)}
**Диалогов:** {conv_count} сообщений
**Предпочтения:** {preferences}
**Часовой пояс:** {user_data.preferred_timezone.capitalize()}
"""
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Настройки", callback_data="settings"), InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    # Команды создателя
    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if len(context.args) < 2:
            text = "💎 Укажите ID/юзернейм и длительность!\n\nПример: /grant_vip @user week"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список пользователей", callback_data="users")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        target = context.args[0]
        duration = context.args[1].lower()
        
        target_user = None
        if target.startswith('@'):
            username = target[1:].lower()
            for u in self.db.get_all_users():
                if u.username.lower() == username:
                    target_user = u
                    break
        else:
            target_user = self.db.get_user(int(target))
        
        if not target_user:
            await update.message.reply_text("❌ Пользователь не найден!")
            return
        
        target_user.is_vip = True
        
        now = datetime.datetime.now()
        if duration == "week":
            target_user.vip_expires = (now + datetime.timedelta(weeks=1)).isoformat()
        elif duration == "month":
            target_user.vip_expires = (now + datetime.timedelta(days=30)).isoformat()
        elif duration == "year":
            target_user.vip_expires = (now + datetime.timedelta(days=365)).isoformat()
        elif duration == "permanent":
            target_user.vip_expires = None
        else:
            await update.message.reply_text("❌ Длительность: week/month/year/permanent")
            return
        
        self.db.save_user(target_user)
        text = f"✅ VIP выдан {target_user.first_name} на {duration}"
        await update.message.reply_text(text)
        
        try:
            await context.bot.send_message(target_user.user_id, f"🎉 Вам выдан VIP на {duration}!")
        except:
            pass
    
    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            text = "💎 Укажите ID/юзернейм!\n\nПример: /revoke_vip @user"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Список пользователей", callback_data="users")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        target = context.args[0]
        
        target_user = None
        if target.startswith('@'):
            username = target[1:].lower()
            for u in self.db.get_all_users():
                if u.username.lower() == username:
                    target_user = u
                    break
        else:
            target_user = self.db.get_user(int(target))
        
        if not target_user:
            await update.message.reply_text("❌ Не найден!")
            return
        
        target_user.is_vip = False
        target_user.vip_expires = None
        self.db.save_user(target_user)
        
        text = f"✅ VIP отозван у {target_user.first_name}"
        await update.message.reply_text(text)
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            text = "📢 Укажите текст рассылки!\n\nПример: /broadcast Важное объявление!"
            await update.message.reply_text(text)
            return
        
        message = " ".join(context.args)
        sent = 0
        
        await update.message.reply_text(f"📢 Начинаю рассылку для {len(self.db.get_all_users())} пользователей...")
        
        for u in self.db.get_all_users():
            try:
                await context.bot.send_message(u.user_id, f"📢 Объявление:\n\n{message}")
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        
        await update.message.reply_text(f"✅ Рассылка завершена. Отправлено: {sent}")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        users = self.db.get_all_users()
        if not users:
            await update.message.reply_text("👥 Нет пользователей!")
            return
        
        text = "👥 **Список пользователей:**\n\n"
        for u in users[:20]:
            vip = "💎" if u.is_vip else "👤"
            text += f"{vip} {u.first_name} (@{u.username or 'нет'}) ID: {u.user_id}\n"
        
        if len(users) > 20:
            text += f"\n... и ещё {len(users) - 20}"
        
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Админ", callback_data="admin")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/stats")
        
        if self.is_creator(user_data.user_id):
            users = self.db.get_all_users()
            vip = len([u for u in users if u.is_vip])
            self.db.cursor.execute('SELECT COUNT(*) FROM conversations')
            msgs = self.db.cursor.fetchone()[0]
            
            text = f"""📊 **Статистика бота**

👥 Пользователей: {len(users)}
💎 VIP: {vip}
💬 Сообщений: {msgs}
⚡ Дата: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Админ", callback_data="admin")]])
        else:
            conv = len(self.db.get_conversation(user_data.user_id))
            
            text = f"""📊 **Ваша статистика**

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}
💬 Сообщений в диалоге: {conv}
📝 Заметок: {len(user_data.notes)}
🧠 Записей в памяти: {len(user_data.memory_data)}
"""
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="start")]])
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            status = "включен" if self.maintenance_mode else "выключен"
            text = f"🛠 **Режим обслуживания:** {status}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Админ", callback_data="admin")]])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return
        
        mode = context.args[0].lower()
        if mode in ['on', 'вкл']:
            self.maintenance_mode = True
            await update.message.reply_text("🛠 Режим обслуживания включен")
        elif mode in ['off', 'выкл']:
            self.maintenance_mode = False
            await update.message.reply_text("✅ Режим обслуживания выключен")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        self.db._backup()
        text = "✅ Резервная копия создана!\n\nФайлы: {BACKUP_PATH}, {CONVERSATIONS_FILE}"
        await update.message.reply_text(text)
    
    # Обработчик кнопок с расширенными меню
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "help":
            await self.help_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "vip_info":
            await self.vip_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "ai_demo":
            await query.edit_message_text("🤖 AI готов! Напишите любое сообщение для разговора.")
        elif data == "my_stats":
            await self.stats_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "entertainment":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("😄 Шутка", callback_data="joke"), InlineKeyboardButton("🧠 Факт", callback_data="fact")],
                [InlineKeyboardButton("💫 Цитата", callback_data="quote"), InlineKeyboardButton("❓ Викторина", callback_data="quiz")],
                [InlineKeyboardButton("🪙 Монетка", callback_data="coin"), InlineKeyboardButton("🎲 Кубик", callback_data="dice")],
                [InlineKeyboardButton("🔮 Шар", callback_data="8ball"), InlineKeyboardButton("🔙 Меню", callback_data="start")]
            ])
            await query.edit_message_text("🎮 **Развлечения**", reply_markup=keyboard)
        elif data == "utilities":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Пароль", callback_data="password"), InlineKeyboardButton("📱 QR-код", callback_data="qr")],
                [InlineKeyboardButton("🔗 Сократить URL", callback_data="shorturl"), InlineKeyboardButton("🌍 IP", callback_data="ip")],
                [InlineKeyboardButton("🌤️ Погода", callback_data="weather"), InlineKeyboardButton("💰 Валюта", callback_data="currency")],
                [InlineKeyboardButton("🌐 Перевод", callback_data="translate"), InlineKeyboardButton("🧠 Память", callback_data="memory")],
                [InlineKeyboardButton("🔢 Математика", callback_data="math_menu"), InlineKeyboardButton("🔙 Меню", callback_data="start")]
            ])
            await query.edit_message_text("🛠 **Утилиты**", reply_markup=keyboard)
        elif data == "math_menu":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔢 Простой расчет", callback_data="math"), InlineKeyboardButton("🧮 Сложный расчет", callback_data="calculate")],
                [InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]
            ])
            await query.edit_message_text("🔢 **Математика**", reply_markup=keyboard)
        elif data == "memory":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Сохранить", callback_data="memorysave"), InlineKeyboardButton("Получить", callback_data="memoryget")],
                [InlineKeyboardButton("Список", callback_data="memorylist"), InlineKeyboardButton("Удалить", callback_data="memorydel")],
                [InlineKeyboardButton("🔙 Утилиты", callback_data="utilities")]
            ])
            await query.edit_message_text("🧠 **Память**", reply_markup=keyboard)
        elif data == "joke":
            await self.joke_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "fact":
            await self.fact_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "quote":
            await self.quote_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "quiz":
            await self.quiz_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "coin":
            await self.coin_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "dice":
            await self.dice_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "8ball":
            await update.message.reply_text("🔮 Задайте вопрос в чате!")
        elif data == "password":
            await update.message.reply_text("🔐 Укажите длину: /password [число]")
        elif data == "qr":
            await update.message.reply_text("📱 Укажите текст: /qr [текст]")
        elif data == "shorturl":
            await update.message.reply_text("🔗 Укажите URL: /shorturl [ссылка]")
        elif data == "ip":
            await self.ip_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "weather":
            await update.message.reply_text("🌤️ Укажите город: /weather [город]")
        elif data == "currency":
            await update.message.reply_text("💰 Укажите валюты: /currency [из] [в]")
        elif data == "translate":
            await update.message.reply_text("🌐 Укажите язык и текст: /translate [язык] [текст]")
        elif data == "memorysave":
            await update.message.reply_text("🧠 Укажите ключ и значение: /memorysave [ключ] [значение]")
        elif data == "memoryget":
            await update.message.reply_text("🧠 Укажите ключ: /memoryget [ключ]")
        elif data == "memorylist":
            await self.memorylist_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "memorydel":
            await update.message.reply_text("🧠 Укажите ключ: /memorydel [ключ]")
        elif data == "math":
            await update.message.reply_text("🔢 Укажите выражение: /math [выражение]")
        elif data == "calculate":
            await update.message.reply_text("🧮 Укажите выражение: /calculate [выражение]")
        elif data == "notes":
            await self.notes_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "delnote":
            await update.message.reply_text("🗑 Укажите номер: /delnote [номер]")
        elif data == "time":
            await self.time_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "profile":
            await self.profile_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "reminders":
            await self.reminders_command(Update(update_id=update.update_id, message=query.message), context)
        elif data == "delreminder":
            await update.message.reply_text("🗑 Укажите номер: /delreminder [номер]")
        elif data == "change_timezone":
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(tz.capitalize(), callback_data=f"set_tz_{tz}") for tz in TIMEZONES]])
            await query.edit_message_text("🌍 Выберите часовой пояс:", reply_markup=keyboard)
        elif data.startswith("set_tz_"):
            tz = data.split("_")[2]
            user_data = await self.get_user_data(Update(update_id=update.update_id, message=query.message))
            user_data.preferred_timezone = tz
            self.db.save_user(user_data)
            await query.edit_message_text(f"✅ Часовой пояс установлен: {tz.capitalize()}")
        elif data == "start":
            await self.start_command(Update(update_id=update.update_id, message=query.message), context)
    
    async def self_ping(self):
        try:
            requests.get(RENDER_URL, timeout=10)
            logger.info("Ping OK")
        except:
            pass
    
    async def check_birthdays(self):
        today = datetime.datetime.now().strftime("%m-%d")
        if today == DAD_BIRTHDAY_MONTH_DAY:
            for u in self.db.get_all_users():
                if u.username.lower() == DAD_USERNAME.lower():
                    await self.application.bot.send_message(u.user_id, "🎉 С Днём Рождения, папа! ❤️")
    
    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        try:
            await context.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")
    
    async def run_bot(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        commands = [
            CommandHandler("start", self.start_command),
            CommandHandler("help", self.help_command),
            CommandHandler("info", self.info_command),
            CommandHandler("status", self.status_command),
            CommandHandler("uptime", self.uptime_command),
            CommandHandler("clear", self.clear_command),
            CommandHandler("ai", self.ai_command),
            CommandHandler("note", self.note_command),
            CommandHandler("notes", self.notes_command),
            CommandHandler("delnote", self.delnote_command),
            CommandHandler("findnote", self.findnote_command),
            CommandHandler("clearnotes", self.clearnotes_command),
            CommandHandler("time", self.time_command),
            CommandHandler("date", self.date_command),
            CommandHandler("joke", self.joke_command),
            CommandHandler("fact", self.fact_command),
            CommandHandler("quote", self.quote_command),
            CommandHandler("quiz", self.quiz_command),
            CommandHandler("coin", self.coin_command),
            CommandHandler("dice", self.dice_command),
            CommandHandler("8ball", self.eightball_command),
            CommandHandler("math", self.math_command),
            CommandHandler("calculate", self.calculate_command),
            CommandHandler("password", self.password_command),
            CommandHandler("qr", self.qr_command),
            CommandHandler("shorturl", self.shorturl_command),
            CommandHandler("ip", self.ip_command),
            CommandHandler("weather", self.weather_command),
            CommandHandler("currency", self.currency_command),
            CommandHandler("translate", self.translate_command),
            CommandHandler("memorysave", self.memorysave_command),
            CommandHandler("memoryget", self.memoryget_command),
            CommandHandler("memorylist", self.memorylist_command),
            CommandHandler("memorydel", self.memorydel_command),
            CommandHandler("rank", self.rank_command),
            CommandHandler("vip", self.vip_command),
            CommandHandler("remind", self.remind_command),
            CommandHandler("reminders", self.reminders_command),
            CommandHandler("delreminder", self.delreminder_command),
            CommandHandler("nickname", self.nickname_command),
            CommandHandler("profile", self.profile_command),
            CommandHandler("grant_vip", self.grant_vip_command),
            CommandHandler("revoke_vip", self.revoke_vip_command),
            CommandHandler("broadcast", self.broadcast_command),
            CommandHandler("users", self.users_command),
            CommandHandler("stats", self.stats_command),
            CommandHandler("maintenance", self.maintenance_command),
            CommandHandler("backup", self.backup_command)
        ]
        
        for handler in commands:
            self.application.add_handler(handler)
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        self.scheduler.start()
        
        await self.application.run_polling()

bot = TelegramBot()
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

if __name__ == "__main__":
    from threading import Thread
    port = int(os.getenv("PORT", 5000))
    Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port}).start()
    asyncio.run(bot.run_bot())
