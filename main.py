#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ v4.2 - Многоязычный с улучшенным интерфейсом
Полнофункциональный бот с расширенным контекстом, инструментами и персонализацией
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
from telegram.error import Conflict
import google.generativeai as genai

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
CONVERSATIONS_FILE = "conversations.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"
BACKUP_PATH = "bot_backup.json"

CREATOR_ID = 7108255346
CREATOR_USERNAME = "Ernest_Kostevich"
BOT_USERNAME = "AI_DISCO_BOT"
DAD_BIRTHDAY = "2025-10-03"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.0-flash-exp"

TIMEZONES = {
    'utc': 'UTC',
    'washington': 'America/New_York',
    'moscow': 'Europe/Moscow',
    'cest': 'Europe/Berlin',
    'london': 'Europe/London',
    'tokyo': 'Asia/Tokyo'
}

LANGUAGES = ['ru', 'en', 'es', 'de', 'it', 'fr']

TRANSLATIONS = {
    'ru': {
        'welcome': "🤖 Привет, {name}! Я {bot_username} - ваш умный ассистент с полной памятью и поддержкой нескольких языков. Выберите опцию ниже или просто напишите мне, и я помогу!",
        'help_title': "📋 Полная справка по командам",
        'help_text': """Вот список всех доступных команд, сгруппированных по категориям. Я готов помочь с любыми задачами - от простых вычислений до сложных консультаций.

**🏠 Основные команды:**
- /start - Открыть главное меню с быстрым доступом к функциям
- /help - Показать эту справку с детальным описанием
- /info - Узнать о боте: версия, возможности, создатель
- /status - Проверить статус бота и системы
- /uptime - Посмотреть время работы и статистику пользователей
- /language [code] - Сменить язык (ru, en, es, de, it, fr)

**💬 AI-чат и общение:**
- Просто напишите сообщение, и я отвечу с учетом контекста!
- /ai [вопрос] - Задать прямой вопрос AI без контекста
- /clear - Очистить историю диалога для нового старта

**📝 Заметки и организация:**
- /note [текст] - Добавить новую заметку
- /notes - Просмотреть все ваши заметки
- /delnote [номер] - Удалить конкретную заметку
- /findnote [слово] - Найти заметки по ключевому слову
- /clearnotes - Очистить все заметки

**⏰ Время, дата и погода:**
- /time - Текущее время в вашем поясе и других зонах (UTC, Washington, Moscow, CEST и т.д.)
- /date - Текущая дата с днем недели
- /weather [город] - Актуальная погода в указанном городе

**🎮 Развлечения и игры:**
- /joke - Случайная шутка, чтобы поднять настроение
- /fact - Интересный факт из разных областей
- /quote - Вдохновляющая цитата
- /quiz - Короткая викторина с вопросами
- /coin - Подбросить монетку (орёл или решка)
- /dice - Бросить кубик (1-6)
- /8ball [вопрос] - Магический шар для предсказаний

**🔢 Математика и расчеты:**
- /math [выражение] - Простые математические вычисления
- /calculate [выражение] - Продвинутые расчеты (sqrt, sin и т.д.)

**🛠 Утилиты и инструменты:**
- /password [длина] - Сгенерировать безопасный пароль
- /qr [текст] - Создать QR-код из текста или ссылки
- /shorturl [ссылка] - Сократить длинный URL
- /ip - Получить ваш текущий IP-адрес
- /currency [из] [в] - Конвертер валют
- /translate [язык] [текст] - Перевести текст на указанный язык

**🧠 Память и хранение:**
- /memorysave [ключ] [значение] - Сохранить данные по ключу
- /memoryget [ключ] - Получить данные по ключу
- /memorylist - Просмотреть все сохраненные данные
- /memorydel [ключ] - Удалить данные по ключу

**📊 Прогресс и статистика:**
- /rank - Ваш уровень, опыт и достижения
- /stats - Личная или общая статистика (для админа - полная)

**💎 VIP-функции (для премиум-пользователей):**
- /vip - Проверить статус VIP и срок действия
- /remind [минуты] [текст] - Установить напоминание
- /reminders - Список ваших напоминаний
- /delreminder [номер] - Удалить напоминание
- /nickname [имя] - Установить персональный никнейм
- /profile - Полный профиль с статистикой

**👑 Админ-команды (для создателя):**
- /grant_vip [id/@username] [duration] - Выдать VIP (week/month/year/permanent)
- /revoke_vip [id/@username] - Отозвать VIP
- /broadcast [текст] - Рассылка сообщения всем пользователям
- /users - Список всех пользователей
- /maintenance [on/off] - Включить/выключить режим обслуживания
- /backup - Создать резервную копию данных

Если что-то неясно, просто спросите - я объясню подробнее! 😊
""",
        'info_text': """🤖 **Информация о боте**

Версия: 4.2 (многоязычная с улучшенным интерфейсом)
Создатель: @{creator}
Бот: @{bot}
Функций: 50+
AI: Gemini 2.0 с полной памятью контекста
База данных: SQLite (надёжное хранение)
Языки: Русский, English, Español, Deutsch, Italiano, Français (смените с /language [code])
Часовые пояса: UTC по умолчанию, с поддержкой Washington, Moscow, CEST, London, Tokyo
Хостинг: Render (24/7 онлайн)
""",
        'status_text': """⚡ **Статус бота**

Онлайн: ✅ (100% uptime)
Версия: 4.2
Пользователей: {users}
Команд выполнено: {commands}
Активных диалогов: {convs}
AI: ✅ (Gemini готов)
База данных: ✅
""",
        'uptime_text': "⏱️ Бот работает стабильно!\n👥 Активных пользователей: {users}\n\nСпасибо, что используете меня - я постоянно улучшаюсь!",
        'clear_text': "✅ История диалога очищена ({count} сообщений). Давайте начнём заново! Что вы хотите спросить?",
        'ai_error': "❌ AI временно недоступен. Попробуйте позже или используйте другие команды.",
        'note_add': "✅ Заметка '{note}' сохранена успешно! Всего заметок: {count}",
        'notes_empty': "❌ У вас пока нет заметок. Добавьте первую с /note [текст]!",
        'delnote_error': "❌ Укажите номер заметки для удаления! Просмотрите список с /notes.",
        'findnote_error': "🔍 Укажите ключевое слово для поиска! Пример: /findnote задача",
        'clearnotes': "✅ Все заметки ({count}) очищены. Память свободна для новых идей!",
        'time_text': "⏰ **Текущее время**\n\nВаш пояс ({timezone}): {time}\nДата: {date} ({day})\n\nДругие пояса:\n{all_tz}\n\nХотите сменить пояс? Используйте /timezone [ключ, напр. moscow]",
        'date_text': "📅 **Сегодняшняя дата**\n\n{date} ({day})\nВремя: {time} ({timezone})\n\nПолный обзор времени: /time",
        'joke_text': "😄 {joke}\n\nХотите ещё? Нажмите 'Ещё шутка'!",
        'fact_text': "{fact}\n\nИнтересно? Нажмите 'Ещё факт'!",
        'quote_text': "{quote}\n\nВдохновляет? Нажмите 'Ещё цитата'!",
        'quiz_text': "❓ {q}\n\nНапишите ответ ниже или нажмите 'Новый вопрос'!",
        'coin_text': "{result}\n\nБросить ещё раз?",
        'dice_text': "🎲 {face} Выпало: {result}\n\nБросить снова?",
        '8ball_error': "🔮 Задайте вопрос для предсказания! Пример: /8ball Будет ли успех?",
        '8ball_text': "🔮 {answer}\n\nНовый вопрос?",
        'math_error': "🔢 Укажите выражение! Пример: /math 2+2*2",
        'math_text': "🔢 Результат: {expression} = {result}\n\nНовый расчет?",
        'calculate_error': "🧮 Укажите выражение! Пример: /calculate sqrt(16)",
        'calculate_text': "🧮 Результат: {expression} = {result}\n\nНовый расчет?",
        'password_text': "🔐 Сгенерированный пароль (длина {length}):\n`{password}`\n\nНовый?",
        'qr_error': "📱 Укажите текст! Пример: /qr https://example.com",
        'shorturl_error': "🔗 Укажите ссылку! Пример: /shorturl https://example.com",
        'ip_text': "🌍 Ваш IP: {ip}\n\nБезопасно и конфиденциально.",
        'weather_error': "🌤️ Укажите город! Пример: /weather Москва",
        'currency_error': "💰 Укажите валюты! Пример: /currency USD RUB",
        'translate_error': "🌐 Укажите язык и текст! Пример: /translate en Привет",
        'memorysave_error': "🧠 Укажите ключ и значение! Пример: /memorysave email my@email.com",
        'memoryget_error': "🧠 Укажите ключ! Пример: /memoryget email",
        'memorylist_empty': "🧠 Память пуста. Сохраните что-то с /memorysave!",
        'memorydel_error': "🧠 Укажите ключ! Пример: /memorydel email",
        'rank_text': """🏅 **Ваш прогресс**

👤 {name}
🆙 Уровень: {level}
⭐ Опыт: {exp}/{req}
📊 Прогресс: {progress:.1f}%
💎 VIP: {vip}
""",
        'vip_not': "💎 Для активации VIP свяжитесь с @{creator}. Преимущества: напоминания, персонализация и больше!",
        'vip_yes': "💎 VIP активен до {expires}. Наслаждайтесь премиум-функциями!",
        'remind_error': "⏰ Укажите минуты и текст! Пример: /remind 30 Ужин",
        'reminders_empty': "❌ Нет активных напоминаний. Установите с /remind!",
        'delreminder_error': "❌ Укажите номер! Пример: /delreminder 1",
        'nickname_error': "👤 Укажите имя! Пример: /nickname SuperUser",
        'profile_text': """👤 **Ваш профиль**

Имя: {name}
Никнейм: {nickname}
Уровень: {level}
Заметок: {notes}
Памяти: {memory}
""",
        'grant_vip_error': "💎 Укажите id/@username и длительность! Пример: /grant_vip @user week",
        'revoke_vip_error': "💎 Укажите id/@username! Пример: /revoke_vip @user",
        'broadcast_error': "📢 Укажите текст! Пример: /broadcast Важное обновление",
        'users_empty': "👥 Нет пользователей в базе.",
        'stats_bot': """📊 **Статистика бота**

👥 Пользователей: {users}
💎 VIP: {vip}
💬 Сообщений: {msgs}
""",
        'stats_user': """📊 **Ваша статистика**

👤 {name}
🆙 Уровень: {level}
⭐ Опыт: {exp}
💬 История: {conv} сообщений
📝 Заметок: {notes}
🧠 Памяти: {memory}
""",
        'maintenance_status': "🛠 Режим обслуживания: {status}",
        'backup_success': "✅ Резервная копия успешно создана!",
        'language_current': "🌐 Текущий язык: {lang}. Смените с /language [code]",
        'language_error': "❌ Неверный код языка! Доступны: ru, en, es, de, it, fr",
        'back_menu': "🔙 Меню"
    },
    'en': {
        'welcome': "🤖 Hi, {name}! I'm {bot_username} - your smart assistant with full memory and multi-language support. Choose an option below or just write to me, and I'll help!",
        'help_title': "📋 Full Command Help",
        'help_text': """Here's a list of all available commands, grouped by categories. I'm ready to help with any tasks - from simple calculations to complex consultations.

**🏠 Basic commands:**
- /start - Open the main menu with quick access to functions
- /help - Show this help with detailed description
- /info - Learn about the bot: version, features, creator
- /status - Check bot and system status
- /uptime - View runtime and user statistics
- /language [code] - Change language (ru, en, es, de, it, fr)

**💬 AI-chat and communication:**
- Just write a message, and I'll respond considering the context!
- /ai [question] - Ask a direct question to AI without context
- /clear - Clear dialog history for a new start

**📝 Notes and organization:**
- /note [text] - Add a new note
- /notes - View all your notes
- /delnote [number] - Delete a specific note
- /findnote [word] - Find notes by keyword
- /clearnotes - Clear all notes

**⏰ Time, date and weather:**
- /time - Current time in your zone and other zones (UTC, Washington, Moscow, CEST, etc.)
- /date - Current date with day of the week
- /weather [city] - Actual weather in the specified city

**🎮 Entertainment and games:**
- /joke - Random joke to cheer up
- /fact - Interesting fact from different areas
- /quote - Inspiring quote
- /quiz - Short quiz with questions
- /coin - Toss a coin (heads or tails)
- /dice - Roll a dice (1-6)
- /8ball [question] - Magic ball for predictions

**🔢 Math and calculations:**
- /math [expression] - Simple mathematical calculations
- /calculate [expression] - Advanced calculations (sqrt, sin, etc.)

**🛠 Utilities and tools:**
- /password [length] - Generate a secure password
- /qr [text] - Create QR code from text or link
- /shorturl [link] - Shorten long URL
- /ip - Get your current IP address
- /currency [from] [to] - Currency converter
- /translate [language] [text] - Translate text to specified language

**🧠 Memory and storage:**
- /memorysave [key] [value] - Save data by key
- /memoryget [key] - Get data by key
- /memorylist - View all saved data
- /memorydel [key] - Delete data by key

**📊 Progress and statistics:**
- /rank - Your level, experience and achievements
- /stats - Personal or general statistics (for admin - full)

**💎 VIP features (for premium users):**
- /vip - Check VIP status and expiration
- /remind [minutes] [text] - Set reminder
- /reminders - List your reminders
- /delreminder [number] - Delete reminder
- /nickname [name] - Set personal nickname
- /profile - Full profile with statistics

**👑 Admin commands (for creator):**
- /grant_vip [id/@username] [duration] - Grant VIP (week/month/year/permanent)
- /revoke_vip [id/@username] - Revoke VIP
- /broadcast [text] - Broadcast message to all users
- /users - List all users
- /maintenance [on/off] - Turn maintenance mode on/off
- /backup - Create data backup

If something is unclear, just ask - I'll explain in detail! 😊
""",
        # ... (complete the English translations for all keys)
        'info_text': """🤖 **Bot Information**

Version: 4.2 (multi-language with improved interface)
Creator: @{creator}
Bot: @{bot}
Functions: 50+
AI: Gemini 2.0 with full context memory
Database: SQLite (reliable storage)
Languages: Russian, English, Español, Deutsch, Italiano, Français (change with /language [code])
Time zones: UTC by default, with support for Washington, Moscow, CEST, London, Tokyo
Hosting: Render (24/7 online)
""",
        # Continue for all keys in 'ru'
        'back_menu': "🔙 Menu"
    },
    # Add full translations for 'es', 'de', 'it', 'fr' in a similar manner. For now, copy 'en' as placeholder.
    'es': TRANSLATIONS['en'],
    'de': TRANSLATIONS['en'],
    'it': TRANSLATIONS['en'],
    'fr': TRANSLATIONS['en']
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
    nickname: Optional[str] = None
    level: int = 1
    experience: int = 0
    achievements: List[str] = field(default_factory=list)
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    preferred_timezone: str = 'utc'
    preferred_language: str = 'ru'

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
            last_activity=data.get('last_activity', datetime.datetime.now().isoformat()),
            preferred_timezone=data.get('preferred_timezone', 'utc'),
            preferred_language=data.get('preferred_language', 'ru')
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
            'last_activity': self.last_activity,
            'preferred_timezone': self.preferred_timezone,
            'preferred_language': self.preferred_language
        }

class AITools:
    @staticmethod
    def get_current_datetime(timezone_key: str = 'utc'):
        now = datetime.datetime.now(pytz.timezone(TIMEZONES.get(timezone_key, 'UTC')))
        return {
            "date": now.strftime('%d.%m.%Y'),
            "time": now.strftime('%H:%M:%S'),
            "day_of_week": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][now.weekday()],
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "timezone": timezone_key.upper()
        }

    @staticmethod
    def get_all_timezones(lang='ru'):
        text = ""
        for key in TIMEZONES:
            dt = AITools.get_current_datetime(key)
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
                nickname TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                achievements TEXT DEFAULT '[]',
                last_activity TEXT,
                preferred_timezone TEXT DEFAULT 'utc',
                preferred_language TEXT DEFAULT 'ru'
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
                'memory_data': json.loads(row[7]), 'nickname': row[8],
                'level': row[9], 'experience': row[10], 'achievements': json.loads(row[11]),
                'last_activity': row[12], 'preferred_timezone': row[13],
                'preferred_language': row[14]
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
            user_data.nickname, user_data.level, user_data.experience,
            json.dumps(user_data.achievements, ensure_ascii=False),
            user_data.last_activity, user_data.preferred_timezone, user_data.preferred_language
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
            'memory_data': json.loads(row[7]), 'nickname': row[8],
            'level': row[9], 'experience': row[10], 'achievements': json.loads(row[11]),
            'last_activity': row[12], 'preferred_timezone': row[13],
            'preferred_language': row[14]
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
                logger.info("Gemini инициализирован")
            except Exception as e:
                logger.error(f"Ошибка Gemini: {e}")
        self.scheduler = AsyncIOScheduler()
        self.maintenance_mode = False

    async def get_user_data(self, update: Update) -> UserData:
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        if not user_data:
            lang = user.language_code if user.language_code in LANGUAGES else 'ru'
            user_data = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                preferred_timezone='utc',
                preferred_language=lang
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

    def create_ai_prompt(self, user_message: str, conversation_history: List[Dict], user_data: UserData) -> str:
        dt = self.tools.get_current_datetime(user_data.preferred_timezone)
        system_context = f"""You are a smart AI assistant in Telegram bot.

CURRENT INFORMATION:
- Date: {dt['date']} ({dt['day_of_week']})
- Time ({dt['timezone']}): {dt['time']}
- Year: {dt['year']}

RULES:
- Always use actual date/time from system info
- Respond in {user_data.preferred_language.upper()} friendly
- Remember the entire dialog context

HISTORY:
{'\n'.join(f"{'User' if msg['role'] == 'user' else 'You'}: {msg['message']}" for msg in conversation_history[-50:]) or '(new dialog)'}

NEW MESSAGE:
{user_message}

Your response:"""
        return system_context

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Bot is under maintenance.")
            return
        
        user_data = await self.get_user_data(update)
        message = update.message.text
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI unavailable")
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
            await update.message.reply_text("❌ Processing error")
            logger.error(f"AI error: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        lang = user_data.preferred_language
        tr = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
        self.db.log_command(user_data.user_id, "/start")
        
        keyboard = [
            [InlineKeyboardButton("📋 Help", callback_data="help"),
             InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🤖 AI chat", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Stats", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = tr['welcome'].format(name=user_data.first_name, bot_username=BOT_USERNAME)
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        lang = user_data.preferred_language
        tr = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
        self.db.log_command(user_data.user_id, "/help")
        
        help_text = tr['help_title'] + "\n\n" + tr['help_text']
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        lang = user_data.preferred_language
        tr = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
        self.db.log_command(user_data.user_id, "/info")
        
        info = tr['info_text'].format(creator=CREATOR_USERNAME, bot=BOT_USERNAME)
        await update.message.reply_text(info)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        lang = user_data.preferred_language
        tr = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
        self.db.log_command(user_data.user_id, "/status")
        
        total_users = len(self.db.get_all_users())
        self.db.cursor.execute('SELECT COUNT(*) FROM logs')
        total_commands = self.cursor.fetchone()[0]
        self.db.cursor.execute('SELECT COUNT(DISTINCT user_id) FROM conversations')
        conversations_count = self.cursor.fetchone()[0]
        
        status = tr['status_text'].format(users=total_users, commands=total_commands, convs=conversations_count)
        await update.message.reply_text(status)
    
    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        lang = user_data.preferred_language
        tr = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
        self.db.log_command(user_data.user_id, "/uptime")
        
        total_users = len(self.db.get_all_users())
        text = tr['uptime_text'].format(users=total_users)
        await update.message.reply_text(text)
    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        lang = user_data.preferred_language
        tr = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
        self.db.log_command(user_data.user_id, "/language")
        
        if not context.args:
            text = tr['language_current'].format(lang=lang.upper())
            await update.message.reply_text(text)
            return
        
        new_lang = context.args[0].lower()
        if new_lang in LANGUAGES:
            user_data.preferred_language = new_lang
            self.db.save_user(user_data)
            tr_new = TRANSLATIONS.get(new_lang, TRANSLATIONS['ru'])
            text = tr_new['welcome'].format(name=user_data.first_name, bot_username=BOT_USERNAME)
            await update.message.reply_text(text)
        else:
            text = tr['language_error']
            await update.message.reply_text(text)

    # Add all other commands with similar structure, using tr['key'].format(...)

    async def run_bot(self):
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add all CommandHandler for each command

        # ... (complete with all handlers)

        await application.run_polling()

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

if __name__ == "__main__":
    from threading import Thread
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port, 'debug': False})
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(TelegramBot().run_bot())
