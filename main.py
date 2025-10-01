#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПРОФЕССИОНАЛЬНЫЙ TELEGRAM AI-АССИСТЕНТ v4.0
Умный помощник с полной памятью, персонализацией и интуитивным интерфейсом
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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import google.generativeai as genai

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
CONVERSATIONS_FILE = "conversations.json"  # Для бэкапа
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
    preferences: Dict = field(default_factory=dict)  # Для персонализации
    nickname: Optional[str] = None
    level: int = 1
    experience: int = 0
    achievements: List[str] = field(default_factory=list)
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    preferred_timezone: str = 'moscow'  # По умолчанию

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
        self.cache = {}  # Кэш для производительности

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
            await update.message.reply_text(bot_response)
            await self.add_experience(user_data, 1)
            
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Ошибка AI: {e}")
    
    # Базовые команды
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🤖 AI чат", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"🤖 Привет, {user_data.first_name}!\n\nЯ AI-бот с расширенной памятью и точным знанием времени!\n\nПросто напиши мне что-нибудь 💬"
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/help")
        
        help_text = """📋 ПОЛНЫЙ СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы
/uptime - Время работы

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос AI
/clear - Очистить историю диалога
Или просто напишите сообщение!

📝 ЗАМЕТКИ:
/note [текст] - Сохранить заметку
/notes - Показать все заметки
/delnote [номер] - Удалить заметку
/findnote [слово] - Поиск в заметках
/clearnotes - Очистить все заметки

⏰ ВРЕМЯ И ДАТА:
/time - Текущее время
/date - Текущая дата

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Случайная шутка
/fact - Интересный факт
/quote - Вдохновляющая цитата
/quiz - Викторина
/coin - Монетка
/dice - Кубик
/8ball [вопрос] - Магический шар

🔢 МАТЕМАТИКА:
/math [выражение] - Простые вычисления
/calculate [выражение] - Продвинутый калькулятор

🛠️ УТИЛИТЫ:
/password [длина] - Генератор паролей
/qr [текст] - QR-код
/shorturl [ссылка] - Сокращение URL
/ip - Информация об IP
/weather [город] - Текущая погода
/currency [из] [в] - Конвертер валют
/translate [язык] [текст] - Перевод

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение] - Сохранить
/memoryget [ключ] - Получить
/memorylist - Список
/memorydel [ключ] - Удалить

📊 ПРОГРЕСС:
/rank - Ваш уровень"""
        
        if self.is_vip(user_data):
            help_text += """

💎 VIP КОМАНДЫ:
/vip - VIP информация
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/delreminder [номер] - Удалить напоминание
/nickname [имя] - Установить никнейм
/profile - Ваш профиль"""
        
        if self.is_creator(user_data.user_id):
            help_text += """

👑 КОМАНДЫ СОЗДАТЕЛЯ:
/grant_vip [user_id/@username] [duration] - Выдать VIP
/revoke_vip [user_id/@username] - Отозвать VIP
/broadcast [текст] - Рассылка всем
/users - Список пользователей
/stats - Статистика бота
/maintenance [on/off] - Режим обслуживания
/backup - Создать резервную копию"""
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info = f"""🤖 О БОТЕ

Версия: 4.0
Создатель: @Ernest_Kostevich
Функций: 50+
AI: {"Gemini 2.0 ✅" if self.gemini_model else "❌"}
База данных: SQLite
Память: Полная история
Хостинг: Render 24/7"""
        
        await update.message.reply_text(info)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        total_users = len(self.db.get_all_users())
        self.db.cursor.execute('SELECT COUNT(*) FROM logs')
        total_commands = self.db.cursor.fetchone()[0]
        self.db.cursor.execute('SELECT COUNT(DISTINCT user_id) FROM conversations')
        conversations_count = self.db.cursor.fetchone()[0]
        
        status = f"""⚡ СТАТУС БОТА

Онлайн: ✅
Версия: 4.0
Пользователей: {total_users}
Команд: {total_commands}
Диалогов: {conversations_count}
Gemini: {"✅" if self.gemini_model else "❌"}"""
        
        await update.message.reply_text(status)
    
    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/uptime")
        
        await update.message.reply_text(f"⏱️ Бот работает!\n👥 Пользователей: {len(self.db.get_all_users())}")
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clear")
        
        count = len(self.db.get_conversation(user_data.user_id))
        self.db.clear_conversation(user_data.user_id)
        await update.message.reply_text(f"✅ История очищена ({count} сообщений)")
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос после /ai!")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        query = " ".join(context.args)
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            response = self.gemini_model.generate_content(query)
            await update.message.reply_text(response.text)
        except Exception as e:
            await update.message.reply_text("❌ Ошибка AI")
    
    # Заметки
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/note")
        
        if not context.args:
            await update.message.reply_text("📝 Укажите текст заметки!")
            return
        
        note = " ".join(context.args)
        user_data.notes.append(note)
        self.db.save_user(user_data)
        await update.message.reply_text("✅ Заметка сохранена!")
    
    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок!")
            return
        
        notes_text = "\n".join(f"{i+1}. {note}" for i, note in enumerate(user_data.notes))
        await update.message.reply_text(f"📝 Ваши заметки:\n{notes_text}")
    
    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер заметки!")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            user_data.notes.pop(index)
            self.db.save_user(user_data)
            await update.message.reply_text("✅ Заметка удалена")
        else:
            await update.message.reply_text("❌ Неверный номер!")
    
    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            await update.message.reply_text("🔍 Укажите ключевое слово!")
            return
        
        keyword = " ".join(context.args).lower()
        found = [(i+1, note) for i, note in enumerate(user_data.notes) if keyword in note.lower()]
        
        if found:
            notes_text = "\n".join(f"{i}. {note}" for i, note in found)
            await update.message.reply_text(f"🔍 Найдено ({len(found)}):\n{notes_text}")
        else:
            await update.message.reply_text("❌ Ничего не найдено!")
    
    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clearnotes")
        
        count = len(user_data.notes)
        user_data.notes = []
        self.db.save_user(user_data)
        await update.message.reply_text(f"✅ Очищено {count} заметок!")
    
    # Время и дата
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")
        
        dt = self.tools.get_datetime(user_data.preferred_timezone)
        await update.message.reply_text(f"⏰ ВРЕМЯ\n\n{dt['timezone']}: {dt['time']}\nДата: {dt['date']}\nДень: {dt['day_of_week']}")
    
    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")
        
        dt = self.tools.get_datetime(user_data.preferred_timezone)
        await update.message.reply_text(f"📅 Сегодня: {dt['date']} ({dt['day_of_week']})")
    
    # Развлечения
    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")
        
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Oct 31 == Dec 25!",
            "Заходит программист в бар...",
            "10 типов людей: те кто понимает двоичную систему и те кто нет"
        ]
        await update.message.reply_text(f"😄 {random.choice(jokes)}")
    
    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")
        
        facts = [
            "🧠 Человеческий мозг ~86 млрд нейронов",
            "🐙 У осьминогов три сердца",
            "🌍 Земля проходит 30 км/сек по орбите"
        ]
        await update.message.reply_text(random.choice(facts))
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")
        
        quotes = [
            "💫 'Будь собой. Остальные роли заняты.' - Оскар Уайльд",
            "🚀 'Единственный способ - любить то, что делаешь.' - Стив Джобс"
        ]
        await update.message.reply_text(random.choice(quotes))
    
    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quiz")
        
        questions = [
            {"q": "Сколько дней в високосном году?", "a": "366"},
            {"q": "Столица Австралии?", "a": "Канберра"}
        ]
        q = random.choice(questions)
        await update.message.reply_text(f"❓ {q['q']}\n\n💡 Напишите ответ!")
    
    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/coin")
        await update.message.reply_text(random.choice(["🪙 Орёл!", "🪙 Решка!"]))
    
    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/dice")
        
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
    
    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 Задайте вопрос!")
            return
        
        answers = ["✅ Да!", "❌ Нет", "🤔 Возможно", "⏳ Спроси позже"]
        await update.message.reply_text(f"🔮 {random.choice(answers)}")
    
    # Математика
    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/math")
        
        if not context.args:
            await update.message.reply_text("🔢 Пример: /math 15 + 25")
            return
        
        expression = " ".join(context.args)
        try:
            result = eval(expression)
            await update.message.reply_text(f"🔢 {expression} = {result}")
        except:
            await update.message.reply_text("❌ Ошибка вычисления")
    
    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/calculate")
        
        if not context.args:
            await update.message.reply_text("🧮 Пример: /calculate sqrt(16)")
            return
        
        expression = " ".join(context.args)
        try:
            safe_dict = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "pi": math.pi, "e": math.e}
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            await update.message.reply_text(f"🧮 {expression} = {result}")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    # Утилиты
    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/password")
        
        length = 12 if not context.args or not context.args[0].isdigit() else min(int(context.args[0]), 50)
        
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(f"🔐 Пароль:\n`{password}`", parse_mode='Markdown')
    
    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/qr")
        
        if not context.args:
            await update.message.reply_text("📱 /qr [текст]")
            return
        
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={requests.utils.quote(text)}"
        await context.bot.send_photo(update.effective_chat.id, qr_url)
    
    async def shorturl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/shorturl")
        
        if not context.args:
            await update.message.reply_text("🔗 /shorturl [URL]")
            return
        
        url = context.args[0]
        if not url.startswith('http'):
            url = 'https://' + url
        
        try:
            response = requests.get(f"https://is.gd/create.php?format=simple&url={requests.utils.quote(url)}", timeout=10)
            if response.status_code == 200:
                await update.message.reply_text(f"🔗 {response.text.strip()}")
            else:
                await update.message.reply_text("❌ Ошибка")
        except:
            await update.message.reply_text("❌ Ошибка подключения")
    
    async def ip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ip")
        
        try:
            response = requests.get('https://httpbin.org/ip', timeout=5)
            ip = response.json().get('origin', 'Неизвестно')
            await update.message.reply_text(f"🌍 Ваш IP: {ip}")
        except:
            await update.message.reply_text("❌ Не удалось получить IP")
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        city = " ".join(context.args) if context.args else "Москва"
        try:
            response = requests.get(f"http://wttr.in/{requests.utils.quote(city)}?format=3", timeout=10)
            if response.status_code == 200:
                weather = response.text.strip()
                await update.message.reply_text(f"🌤️ {weather}")
            else:
                await update.message.reply_text("❌ Город не найден")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/currency")
        
        if len(context.args) < 2:
            await update.message.reply_text("💰 /currency [из] [в]")
            return
        
        if not CURRENCY_API_KEY:
            await update.message.reply_text("❌ API не настроен")
            return
        
        from_cur, to_cur = context.args[0].upper(), context.args[1].upper()
        try:
            url = f"https://api.freecurrencyapi.com/v1/latest?apikey={CURRENCY_API_KEY}&currencies={to_cur}&base_currency={from_cur}"
            response = requests.get(url, timeout=10).json()
            rate = response.get("data", {}).get(to_cur)
            
            if rate:
                await update.message.reply_text(f"💰 1 {from_cur} = {rate:.4f} {to_cur}")
            else:
                await update.message.reply_text("❌ Ошибка")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text("🌐 /translate [язык] [текст]")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            response = self.gemini_model.generate_content(f"Переведи на {target_lang}: {text}")
            await update.message.reply_text(f"🌐 {response.text}")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    # Память
    async def memorysave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorysave")
        
        if len(context.args) < 2:
            await update.message.reply_text("🧠 /memorysave [ключ] [значение]")
            return
        
        key = context.args[0]
        value = " ".join(context.args[1:])
        user_data.memory_data[key] = value
        self.db.save_user(user_data)
        await update.message.reply_text(f"🧠 Сохранено: {key}")
    
    async def memoryget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memoryget")
        
        if not context.args:
            await update.message.reply_text("🧠 /memoryget [ключ]")
            return
        
        key = context.args[0]
        value = user_data.memory_data.get(key)
        
        if value:
            await update.message.reply_text(f"🧠 {key}: {value}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
    
    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorylist")
        
        if not user_data.memory_data:
            await update.message.reply_text("🧠 Память пуста!")
            return
        
        memory_text = "\n".join(f"• {key}: {value}" for key, value in user_data.memory_data.items())
        await update.message.reply_text(f"🧠 Ваша память:\n{memory_text}")
    
    async def memorydel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorydel")
        
        if not context.args:
            await update.message.reply_text("🧠 /memorydel [ключ]")
            return
        
        key = context.args[0]
        if key in user_data.memory_data:
            del user_data.memory_data[key]
            self.db.save_user(user_data)
            await update.message.reply_text(f"🧠 Удалено: {key}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
    
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")
        
        req = user_data.level * 100
        progress = (user_data.experience / req) * 100
        
        text = f"""🏅 УРОВЕНЬ

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{req}
📊 Прогресс: {progress:.1f}%
💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}"""
        
        await update.message.reply_text(text)
    
    # VIP команды
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Свяжитесь с @Ernest_Kostevich")
            return
        
        expires = 'бессрочно'
        if user_data.vip_expires:
            exp_date = datetime.datetime.fromisoformat(user_data.vip_expires)
            expires = exp_date.strftime('%d.%m.%Y')
        
        await update.message.reply_text(f"💎 VIP активен до: {expires}")
    
    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/remind")
        
        if len(context.args) < 2:
            await update.message.reply_text("⏰ /remind [минуты] [текст]")
            return
        
        try:
            minutes = int(context.args[0])
            text = " ".join(context.args[1:])
            
            if minutes <= 0:
                await update.message.reply_text("❌ Время > 0!")
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            job = self.scheduler.add_job(
                self.send_notification,
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, f"🔔 {text}"],
                id=f"rem_{user_data.user_id}_{int(time.time())}"
            )
            
            user_data.reminders.append({"id": job.id, "text": text, "time": run_date.isoformat()})
            self.db.save_user(user_data)
            
            await update.message.reply_text(f"⏰ Напоминание на {minutes} мин!")
        except:
            await update.message.reply_text("❌ Ошибка!")
    
    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/reminders")
        
        if not user_data.reminders:
            await update.message.reply_text("❌ Нет напоминаний!")
            return
        
        text = "\n".join([f"{i+1}. {r['text']} ({r['time']})" for i, r in enumerate(user_data.reminders)])
        await update.message.reply_text(f"⏰ Напоминания:\n{text}")
    
    async def delreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/delreminder")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ /delreminder [номер]")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.reminders):
            job_id = user_data.reminders[index]['id']
            self.scheduler.remove_job(job_id)
            user_data.reminders.pop(index)
            self.db.save_user(user_data)
            await update.message.reply_text("✅ Напоминание удалено")
        else:
            await update.message.reply_text("❌ Неверный номер!")
    
    async def nickname_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/nickname")
        
        if not context.args:
            await update.message.reply_text("👤 /nickname [имя]")
            return
        
        nickname = " ".join(context.args)
        user_data.nickname = nickname
        self.db.save_user(user_data)
        await update.message.reply_text(f"✅ Никнейм: {nickname}")
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/profile")
        
        text = f"""👤 ПРОФИЛЬ

Имя: {user_data.first_name}
Никнейм: {user_data.nickname or "Не установлен"}
Уровень: {user_data.level}
Заметок: {len(user_data.notes)}
Памяти: {len(user_data.memory_data)}"""
        
        await update.message.reply_text(text)
    
    # Команды создателя
    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("💎 /grant_vip [id/@username] [week/month/year/permanent]")
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
        
        if duration == "week":
            target_user.vip_expires = (datetime.datetime.now() + datetime.timedelta(weeks=1)).isoformat()
        elif duration == "month":
            target_user.vip_expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        elif duration == "year":
            target_user.vip_expires = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
        elif duration == "permanent":
            target_user.vip_expires = None
        else:
            await update.message.reply_text("❌ week/month/year/permanent")
            return
        
        self.db.save_user(target_user)
        await update.message.reply_text(f"✅ VIP выдан {target_user.first_name}")
        
        try:
            await context.bot.send_message(target_user.user_id, f"🎉 VIP ({duration})!")
        except:
            pass
    
    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("💎 /revoke_vip [id/@username]")
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
        
        await update.message.reply_text(f"✅ VIP отозван у {target_user.first_name}")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("📢 /broadcast [текст]")
            return
        
        message = " ".join(context.args)
        sent = 0
        
        await update.message.reply_text(f"📢 Рассылка для {len(self.db.get_all_users())}...")
        
        for u in self.db.get_all_users():
            try:
                await context.bot.send_message(u.user_id, f"📢 От создателя:\n\n{message}")
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        
        await update.message.reply_text(f"✅ Отправлено: {sent}")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        users = self.db.get_all_users()
        if not users:
            await update.message.reply_text("👥 Пользователей нет!")
            return
        
        text = "👥 ПОЛЬЗОВАТЕЛИ:\n\n"
        for u in users[:20]:
            vip = "💎" if u.is_vip else "👤"
            text += f"{vip} {u.first_name} (ID: {u.user_id})\n"
        
        if len(users) > 20:
            text += f"\n... +{len(users) - 20}"
        
        await update.message.reply_text(text)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/stats")
        
        if self.is_creator(user_data.user_id):
            users = self.db.get_all_users()
            vip = len([u for u in users if u.is_vip])
            self.db.cursor.execute('SELECT COUNT(*) FROM conversations')
            msgs = self.db.cursor.fetchone()[0]
            
            text = f"""📊 СТАТИСТИКА БОТА

👥 Пользователей: {len(users)}
💎 VIP: {vip}
💬 Сообщений: {msgs}
⚡ {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        else:
            conv = len(self.db.get_conversation(user_data.user_id))
            
            text = f"""📊 СТАТИСТИКА

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}
💬 История: {conv} сообщений
📝 Заметок: {len(user_data.notes)}
🧠 Памяти: {len(user_data.memory_data)}"""
        
        await update.message.reply_text(text)
    
    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            status = "включен" if self.maintenance_mode else "выключен"
            await update.message.reply_text(f"🛠 Режим: {status}")
            return
        
        mode = context.args[0].lower()
        if mode in ['on', 'вкл']:
            self.maintenance_mode = True
            await update.message.reply_text("🛠 ВКЛЮЧЕН")
        elif mode in ['off', 'выкл']:
            self.maintenance_mode = False
            await update.message.reply_text("✅ ВЫКЛЮЧЕН")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        self.db._backup()
        await update.message.reply_text("✅ Резервная копия создана!")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            await self.help_command(Update(update_id=update.update_id, message=query.message), context)
        elif query.data == "vip_info":
            await query.edit_message_text("💎 VIP дает доступ к напоминаниям.\n\nСвяжитесь с @Ernest_Kostevich")
        elif query.data == "ai_demo":
            await query.edit_message_text("🤖 AI готов!\n\nПросто напишите сообщение!")
        elif query.data == "my_stats":
            await self.stats_command(Update(update_id=update.update_id, message=query.message), context)
    
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
