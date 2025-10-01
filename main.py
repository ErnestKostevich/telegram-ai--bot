#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ v3.0 - Улучшенная версия для Render
Полнофункциональный бот с расширенным контекстом, SQLite базой и инструментами
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

nest_asyncio.apply()

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import Conflict
import google.generativeai as genai

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
USERS_FILE = "users.json"  # Для совместимости, но основное - SQLite
CONVERSATIONS_FILE = "conversations.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"
BACKUP_PATH = "bot_backup.json"
DB_FILE = "bot_database.db"  # SQLite файл

CREATOR_ID = 7108255346
CREATOR_USERNAME = "Ernest_Kostevich"
DAD_USERNAME = "mkostevich"
DAD_BIRTHDAY_MONTH_DAY = "10-03"  # 3 октября ежегодно
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.0-flash-exp"

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
    nickname: Optional[str] = None
    level: int = 1
    experience: int = 0
    achievements: List[str] = field(default_factory=list)
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

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
            nickname=data.get('nickname'),
            level=data.get('level', 1),
            experience=data.get('experience', 0),
            achievements=data.get('achievements', []),
            last_activity=data.get('last_activity', datetime.datetime.now().isoformat())
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
            'nickname': self.nickname,
            'level': self.level,
            'experience': self.experience,
            'achievements': self.achievements,
            'last_activity': self.last_activity
        }

class AITools:
    @staticmethod
    def get_current_datetime():
        now = datetime.datetime.now()
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = now.astimezone(moscow_tz)
        return {
            "date": now.strftime('%d.%m.%Y'),
            "time": moscow_time.strftime('%H:%M:%S'),
            "day_of_week": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][now.weekday()],
            "year": now.year,
            "month": now.month,
            "day": now.day
        }

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._load_from_json_if_needed()  # Миграция из JSON если нужно
        self.cache = {}  # Smart caching

    def _create_tables(self):
        # Таблица users
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_vip BOOLEAN DEFAULT FALSE,
                vip_expires TEXT,
                notes TEXT DEFAULT '[]',  -- JSON
                reminders TEXT DEFAULT '[]',  -- JSON
                memory_data TEXT DEFAULT '{}',  -- JSON
                nickname TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                achievements TEXT DEFAULT '[]',  -- JSON
                last_activity TEXT
            )
        ''')
        # Таблица conversations
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                message TEXT,
                timestamp TEXT
            )
        ''')
        # Таблица logs
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT,
                timestamp TEXT
            )
        ''')
        # Таблица statistics
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                command TEXT PRIMARY KEY,
                usage_count INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()

    def _load_from_json_if_needed(self):
        # Миграция из JSON файлов в SQLite, если файлы существуют
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
                for u in users:
                    self.save_user(UserData.from_dict(u))
            os.rename(USERS_FILE, USERS_FILE + '.bak')  # Backup

        if os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                convs = json.load(f)
                for user_id_str, messages in convs.items():
                    user_id = int(user_id_str)
                    for msg in messages:
                        self.add_to_conversation(user_id, msg['role'], msg['message'], msg['timestamp'])
            os.rename(CONVERSATIONS_FILE, CONVERSATIONS_FILE + '.bak')

        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                for log in logs:
                    self.cursor.execute('INSERT INTO logs (user_id, command, timestamp) VALUES (?, ?, ?)',
                                        (log['user_id'], log['command'], log['timestamp']))
                self.conn.commit()
            os.rename(LOGS_FILE, LOGS_FILE + '.bak')

        if os.path.exists(STATISTICS_FILE):
            with open(STATISTICS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                for cmd, data in stats.items():
                    self.cursor.execute('INSERT OR REPLACE INTO statistics (command, usage_count) VALUES (?, ?)',
                                        (cmd, data['usage_count']))
                self.conn.commit()
            os.rename(STATISTICS_FILE, STATISTICS_FILE + '.bak')

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
                'memory_data': json.loads(row[7]), 'nickname': row[8],
                'level': row[9], 'experience': row[10], 'achievements': json.loads(row[11]),
                'last_activity': row[12]
            }
            user = UserData.from_dict(data)
            self.cache[user_id] = user
            return user
        return None

    def save_user(self, user_data: UserData):
        user_data.last_activity = datetime.datetime.now().isoformat()
        notes_json = json.dumps(user_data.notes, ensure_ascii=False)
        reminders_json = json.dumps(user_data.reminders, ensure_ascii=False)
        memory_json = json.dumps(user_data.memory_data, ensure_ascii=False)
        ach_json = json.dumps(user_data.achievements, ensure_ascii=False)
        self.cursor.execute('''
            INSERT OR REPLACE INTO users (
                user_id, username, first_name, is_vip, vip_expires, notes, reminders,
                memory_data, nickname, level, experience, achievements, last_activity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_data.user_id, user_data.username, user_data.first_name, user_data.is_vip,
              user_data.vip_expires, notes_json, reminders_json, memory_json,
              user_data.nickname, user_data.level, user_data.experience, ach_json,
              user_data.last_activity))
        self.conn.commit()
        self.cache[user_data.user_id] = user_data
        # Синхронизация с JSON для бэкапа
        self._sync_to_json()

    def get_conversation(self, user_id: int) -> List[Dict]:
        self.cursor.execute('SELECT role, message, timestamp FROM conversations WHERE user_id = ? ORDER BY id', (user_id,))
        return [{"role": row[0], "message": row[1], "timestamp": row[2]} for row in self.cursor.fetchall()]

    def add_to_conversation(self, user_id: int, role: str, message: str, timestamp: str = None):
        if not timestamp:
            timestamp = datetime.datetime.now().isoformat()
        self.cursor.execute('INSERT INTO conversations (user_id, role, message, timestamp) VALUES (?, ?, ?, ?)',
                            (user_id, role, message, timestamp))
        self.conn.commit()
        # Нет лимита - храним все
        # Синхронизация с JSON
        self._sync_to_json()

    def clear_conversation(self, user_id: int):
        self.cursor.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
        self.conn.commit()
        self._sync_to_json()

    def log_command(self, user_id: int, command: str):
        timestamp = datetime.datetime.now().isoformat()
        self.cursor.execute('INSERT INTO logs (user_id, command, timestamp) VALUES (?, ?, ?)',
                            (user_id, command, timestamp))
        self.cursor.execute('INSERT OR REPLACE INTO statistics (command, usage_count) VALUES (?, COALESCE((SELECT usage_count FROM statistics WHERE command = ?), 0) + 1)',
                            (command, command))
        self.conn.commit()
        self._sync_to_json()

    def get_logs(self) -> List[Dict]:
        self.cursor.execute('SELECT user_id, command, timestamp FROM logs ORDER BY id DESC LIMIT 1000')
        return [{"user_id": row[0], "command": row[1], "timestamp": row[2]} for row in self.cursor.fetchall()]

    def get_statistics(self) -> Dict:
        self.cursor.execute('SELECT command, usage_count FROM statistics')
        return {row[0]: {"usage_count": row[1]} for row in self.cursor.fetchall()}

    def get_all_users(self) -> List[Dict]:
        self.cursor.execute('SELECT * FROM users')
        users = []
        for row in self.cursor.fetchall():
            data = {
                'user_id': row[0], 'username': row[1], 'first_name': row[2],
                'is_vip': bool(row[3]), 'vip_expires': row[4],
                'notes': json.loads(row[5]), 'reminders': json.loads(row[6]),
                'memory_data': json.loads(row[7]), 'nickname': row[8],
                'level': row[9], 'experience': row[10], 'achievements': json.loads(row[11]),
                'last_activity': row[12]
            }
            users.append(data)
        return users

    def _sync_to_json(self):
        # Синхронизация с JSON файлами для бэкапа и совместимости
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.get_all_users(), f, ensure_ascii=False, indent=2)
            with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
                convs = {}
                self.cursor.execute('SELECT DISTINCT user_id FROM conversations')
                for (user_id,) in self.cursor.fetchall():
                    convs[str(user_id)] = self.get_conversation(user_id)
                json.dump(convs, f, ensure_ascii=False, indent=2)
            with open(LOGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.get_logs(), f, ensure_ascii=False, indent=2)
            with open(STATISTICS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.get_statistics(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка синхронизации JSON: {e}")

    def backup(self):
        backup_data = {
            'users': self.get_all_users(),
            'conversations': {},
            'logs': self.get_logs(),
            'statistics': self.get_statistics(),
            'backup_time': datetime.datetime.now().isoformat()
        }
        self.cursor.execute('SELECT DISTINCT user_id FROM conversations')
        for (user_id,) in self.cursor.fetchall():
            backup_data['conversations'][str(user_id)] = self.get_conversation(user_id)
        with open(BACKUP_PATH, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        return True

class TelegramBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.gemini_model = None
        self.tools = AITools()
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("Gemini инициализирован")
            except Exception as e:
                logger.error(f"Ошибка Gemini: {e}")
        self.scheduler = AsyncIOScheduler()
        self.maintenance_mode = False

    async def get_user_data(self, update: Update) -> UserData:
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        if not user_data:
            user_data = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or ""
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
        self.db.save_user(user_data)

    def create_ai_prompt(self, user_message: str, conversation_history: List[Dict]) -> str:
        dt = self.tools.get_current_datetime()
        system_context = f"""Ты умный AI-ассистент в Telegram боте.

ТЕКУЩАЯ ИНФОРМАЦИЯ:
- Дата: {dt['date']} ({dt['day_of_week']})
- Время (МСК): {dt['time']}
- Год: {dt['year']}

ПРАВИЛА:
- Всегда используй актуальные дату/время из системной информации
- Отвечай на русском языке дружелюбно
- Помни весь контекст диалога"""

        # Сжатие контекста для длинных диалогов
        if len(conversation_history) > 50:
            summary_prompt = "Суммируй предыдущий диалог кратко: " + "\n".join([f"{msg['role']}: {msg['message']}" for msg in conversation_history[:20]])
            try:
                summary = self.gemini_model.generate_content(summary_prompt).text
                history_text = summary + "\n" + "\n".join([f"{'Пользователь' if msg['role'] == 'user' else 'Ты'}: {msg['message']}" for msg in conversation_history[-30:]])
            except:
                history_text = "\n".join([f"{'Пользователь' if msg['role'] == 'user' else 'Ты'}: {msg['message']}" for msg in conversation_history[-50:]])
        else:
            history_text = "\n".join([f"{'Пользователь' if msg['role'] == 'user' else 'Ты'}: {msg['message']}" for msg in conversation_history])

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
            prompt = self.create_ai_prompt(message, conversation_history)

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

Версия: 3.0
Создатель: @{CREATOR_USERNAME}
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
Версия: 3.0
Пользователей: {total_users}
Команд: {total_commands}
Диалогов: {conversations_count}
Gemini: {"✅" if self.gemini_model else "❌"}
SQLite: ✅"""
        await update.message.reply_text(status)

    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/uptime")

        await update.message.reply_text(f"⏱️ Бот работает!\n👥 Пользователей: {len(self.db.get_all_users())}")

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clear")

        conv = self.db.get_conversation(user_data.user_id)
        count = len(conv)
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

    # Время
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")

        dt = self.tools.get_current_datetime()
        await update.message.reply_text(f"⏰ ВРЕМЯ\n\nМосква: {dt['time']}\nДата: {dt['date']}\nДень: {dt['day_of_week']}")

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")

        dt = self.tools.get_current_datetime()
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
            import math
            safe_dict = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "pi": math.pi, "e": math.e}
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            await update.message.reply_text(f"🧮 {expression} = {result}")
        except:
            await update.message.reply_text("❌ Ошибка")

    # Утилиты
    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/password")

        length = 12
        if context.args and context.args[0].isdigit():
            length = min(int(context.args[0]), 50)

        import string
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
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}"
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
            response = requests.get(f"https://is.gd/create.php?format=simple&url={url}", timeout=10)
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

        if not context.args:
            city = "Moscow"  # Авто-определение по умолчанию, но для простоты - Москва
        else:
            city = " ".join(context.args)

        try:
            # Используем wttr.in без API ключа
            response = requests.get(f"https://wttr.in/{city}?format=3", timeout=10)
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

    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")

        req = user_data.level * 100
        progress = (user_data.experience / req) * 100 if req > 0 else 0

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
            await update.message.reply_text("💎 Свяжитесь с @{CREATOR_USERNAME}")
            return

        expires = 'бессрочно'
        if user_data.vip_expires:
            try:
                exp_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                expires = exp_date.strftime('%d.%m.%Y')
            except:
                pass

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
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
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

        conv_len = len(self.db.get_conversation(user_data.user_id))
        text = f"""👤 ПРОФИЛЬ

Имя: {user_data.first_name}
Никнейм: {user_data.nickname or "Не установлен"}
Уровень: {user_data.level}
Заметок: {len(user_data.notes)}
Памяти: {len(user_data.memory_data)}
Диалог: {conv_len} сообщений"""
        await update.message.reply_text(text)

    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            # Удалить из reminders после отправки
            user_data = self.db.get_user(user_id)
            if user_data:
                user_data.reminders = [r for r in user_data.reminders if r['text'] not in message]
                self.db.save_user(user_data)
        except Exception as e:
            logger.error(f"Ошибка уведомления {user_id}: {e}")

    # Команды создателя
    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return

        if len(context.args) < 2:
            await update.message.reply_text("💎 /grant_vip [id/@username] [week/month/year/permanent]")
            return

        try:
            target = context.args[0]
            duration = context.args[1].lower()

            target_user = None
            if target.startswith('@'):
                username = target[1:].lower()
                for u in self.db.get_all_users():
                    if u.get('username', '').lower() == username:
                        target_user = UserData.from_dict(u)
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
                await update.message.reply_text("❌ week/month/year/permanent")
                return

            self.db.save_user(target_user)
            await update.message.reply_text(f"✅ VIP выдан {target_user.first_name}")

            try:
                await context.bot.send_message(target_user.user_id, f"🎉 VIP ({duration})!")
            except:
                pass
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return

        if not context.args:
            await update.message.reply_text("💎 /revoke_vip [id/@username]")
            return

        try:
            target = context.args[0]

            target_user = None
            if target.startswith('@'):
                username = target[1:].lower()
                for u in self.db.get_all_users():
                    if u.get('username', '').lower() == username:
                        target_user = UserData.from_dict(u)
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
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

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
            vip = "💎" if u.get('is_vip') else "👤"
            text += f"{vip} {u.get('first_name')} (ID: {u.get('user_id')})\n"

        if len(users) > 20:
            text += f"\n... +{len(users) - 20}"

        await update.message.reply_text(text)

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return

        if not context.args:
            await update.message.reply_text("📢 /broadcast [сообщение]")
            return

        message = " ".join(context.args)
        sent = 0

        await update.message.reply_text(f"📢 Рассылка для {len(self.db.get_all_users())}...")

        for u in self.db.get_all_users():
            try:
                await context.bot.send_message(u.get('user_id'), f"📢 От создателя:\n\n{message}")
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass

        await update.message.reply_text(f"✅ Отправлено: {sent}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)

        if self.is_creator(user_data.user_id):
            users = self.db.get_all_users()
            vip = len([u for u in users if u.get('is_vip')])
            self.db.cursor.execute('SELECT COUNT(*) FROM conversations')
            msgs = self.db.cursor.fetchone()[0]
            self.db.cursor.execute('SELECT COUNT(DISTINCT user_id) FROM conversations')
            convs = self.db.cursor.fetchone()[0]

            text = f"""📊 СТАТИСТИКА БОТА

👥 Пользователей: {len(users)}
💎 VIP: {vip}
💬 Сообщений: {msgs}
🗂️ Диалогов: {convs}

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

        self.db.log_command(user_data.user_id, "/stats")
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

        try:
            success = self.db.backup()
            if success:
                await update.message.reply_text(f"✅ Бэкап создан!\nПользователей: {len(self.db.get_all_users())}")
            else:
                await update.message.reply_text("❌ Ошибка!")
        except Exception as e:
            await update.message.reply_text(f"❌ {str(e)}")

    # Обработчики
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "help":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.help_command(fake_update, context)
        elif query.data == "vip_info":
            await query.edit_message_text("💎 VIP дает доступ к напоминаниям.\n\nСвяжитесь с @{CREATOR_USERNAME}")
        elif query.data == "ai_demo":
            await query.edit_message_text("🤖 AI готов!\n\nПросто напишите сообщение!")
        elif query.data == "my_stats":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.stats_command(fake_update, context)

    async def self_ping(self):
        try:
            requests.get(RENDER_URL, timeout=10)
            logger.info("Ping OK")
        except:
            pass

    async def check_birthdays(self, context: ContextTypes.DEFAULT_TYPE):
        today = datetime.datetime.now().strftime("%m-%d")
        if today == DAD_BIRTHDAY_MONTH_DAY:
            users = self.db.get_all_users()
            for u in users:
                if u.get('username', '').lower() == DAD_USERNAME.lower():
                    try:
                        await context.bot.send_message(u.get('user_id'), "🎉🎂 С Днём Рождения, папа!\n\nС любовью, Ernest ❤️")
                    except:
                        pass

    async def run_bot(self):
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не найден!")
            return

        application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).build()

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Error: {context.error}")

        application.add_error_handler(error_handler)

        # Все команды
        commands = [
            ("start", self.start_command), ("help", self.help_command), ("info", self.info_command),
            ("status", self.status_command), ("uptime", self.uptime_command), ("clear", self.clear_command),
            ("ai", self.ai_command), ("note", self.note_command), ("notes", self.notes_command),
            ("delnote", self.delnote_command), ("findnote", self.findnote_command), ("clearnotes", self.clearnotes_command),
            ("memorysave", self.memorysave_command), ("memoryget", self.memoryget_command),
            ("memorylist", self.memorylist_command), ("memorydel", self.memorydel_command),
            ("time", self.time_command), ("date", self.date_command),
            ("joke", self.joke_command), ("fact", self.fact_command), ("quote", self.quote_command),
            ("quiz", self.quiz_command), ("coin", self.coin_command), ("dice", self.dice_command),
            ("8ball", self.eightball_command), ("math", self.math_command), ("calculate", self.calculate_command),
            ("password", self.password_command), ("qr", self.qr_command), ("shorturl", self.shorturl_command),
            ("ip", self.ip_command), ("weather", self.weather_command), ("currency", self.currency_command),
            ("translate", self.translate_command), ("rank", self.rank_command),
            ("vip", self.vip_command), ("remind", self.remind_command), ("reminders", self.reminders_command),
            ("delreminder", self.delreminder_command), ("nickname", self.nickname_command), ("profile", self.profile_command),
            ("grant_vip", self.grant_vip_command), ("revoke_vip", self.revoke_vip_command),
            ("users", self.users_command), ("broadcast", self.broadcast_command),
            ("maintenance", self.maintenance_command), ("backup", self.backup_command), ("stats", self.stats_command)
        ]

        for cmd, handler in commands:
            application.add_handler(CommandHandler(cmd, handler))

        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.button_callback))

        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()

        self.scheduler.add_job(self.self_ping, 'interval', minutes=14, id='ping')
        self.scheduler.add_job(self.check_birthdays, 'cron', hour=9, minute=0, args=[application], id='bday')

        logger.info("🤖 Бот запущен v3.0!")

        await application.run_polling(drop_pending_updates=True, timeout=30)

async def main():
    bot = TelegramBot()
    await bot.run_bot()

# Flask для Render
app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 AI Bot v3.0 | Time: {datetime.datetime.now()}"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

if __name__ == "__main__":
    from threading import Thread

    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port, 'debug': False})
    flask_thread.daemon = True
    flask_thread.start()

    asyncio.run(main())
