#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ - Главный файл
Полнофункциональный бот с AI, VIP-системой и более чем 150 функциями
"""

import asyncio
import logging
import json
import sqlite3
import random
import time
import datetime
import re
import requests
import aiohttp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pickle
import os
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from newsapi import NewsApiClient

# Telegram Bot API
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# Google Gemini
import google.generativeai as genai

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================================================================
# КОНФИГУРАЦИЯ И КОНСТАНТЫ
# =============================================================================

# API ключи из env
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # Добавь в Render
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")  # Добавь в Render
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")  # Добавь в Render

# ID создателя бота
CREATOR_ID = 7108255346  # Ernest's Telegram ID

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)

MODEL = os.getenv("MODEL", "gemini-2.0-flash")

# =============================================================================
# КЛАССЫ ДАННЫХ
# =============================================================================

@dataclass
class UserData:
    user_id: int
    username: str
    first_name: str
    is_vip: bool = False
    vip_expires: Optional[datetime.datetime] = None
    language: str = "ru"
    notes: List[str] = None
    reminders: List[Dict] = None
    birthday: Optional[str] = None
    nickname: Optional[str] = None
    level: int = 1
    experience: int = 0
    achievements: List[str] = None
    memory_data: Dict = None
    theme: str = "default"
    color: str = "blue"
    sound_notifications: bool = True
    
    def __post_init__(self):
        if self.notes is None:
            self.notes = []
        if self.reminders is None:
            self.reminders = []
        if self.achievements is None:
            self.achievements = []
        if self.memory_data is None:
            self.memory_data = {}

# =============================================================================
# БАЗА ДАННЫХ
# =============================================================================

class DatabaseManager:
    def __init__(self, db_path="bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_vip BOOLEAN DEFAULT FALSE,
            vip_expires TEXT,
            language TEXT DEFAULT 'ru',
            notes TEXT DEFAULT '[]',
            reminders TEXT DEFAULT '[]',
            birthday TEXT,
            nickname TEXT,
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '[]',
            memory_data TEXT DEFAULT '{}',
            theme TEXT DEFAULT 'default',
            color TEXT DEFAULT 'blue',
            sound_notifications BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Таблица статистики
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS statistics (
            command TEXT PRIMARY KEY,
            usage_count INTEGER DEFAULT 0,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Таблица логов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            command TEXT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        """Получить данные пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return UserData(
                user_id=row[0],
                username=row[1],
                first_name=row[2],
                is_vip=bool(row[3]),
                vip_expires=datetime.datetime.fromisoformat(row[4]) if row[4] else None,
                language=row[5],
                notes=json.loads(row[6]),
                reminders=json.loads(row[7]),
                birthday=row[8],
                nickname=row[9],
                level=row[10],
                experience=row[11],
                achievements=json.loads(row[12]),
                memory_data=json.loads(row[13]),
                theme=row[14],
                color=row[15],
                sound_notifications=bool(row[16])
            )
        return None
    
    def save_user(self, user_data: UserData):
        """Сохранить данные пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, is_vip, vip_expires, language, 
         notes, reminders, birthday, nickname, level, experience, 
         achievements, memory_data, theme, color, sound_notifications, last_activity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_data.user_id,
            user_data.username,
            user_data.first_name,
            user_data.is_vip,
            user_data.vip_expires.isoformat() if user_data.vip_expires else None,
            user_data.language,
            json.dumps(user_data.notes, ensure_ascii=False),
            json.dumps(user_data.reminders, ensure_ascii=False),
            user_data.birthday,
            user_data.nickname,
            user_data.level,
            user_data.experience,
            json.dumps(user_data.achievements, ensure_ascii=False),
            json.dumps(user_data.memory_data, ensure_ascii=False),
            user_data.theme,
            user_data.color,
            user_data.sound_notifications,
            datetime.datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def log_command(self, user_id: int, command: str, message: str = ""):
        """Логирование команд"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Логирование
        cursor.execute(
            "INSERT INTO logs (user_id, command, message) VALUES (?, ?, ?)",
            (user_id, command, message)
        )
        
        # Обновление статистики
        cursor.execute("""
        INSERT OR REPLACE INTO statistics (command, usage_count, last_used)
        VALUES (?, COALESCE((SELECT usage_count FROM statistics WHERE command = ?), 0) + 1, ?)
        """, (command, command, datetime.datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        """Получить всех пользователей"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name, level FROM users ORDER BY level DESC")
        users = cursor.fetchall()
        conn.close()
        return users
    
    def get_vip_users(self):
        """Получить VIP пользователей"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name, vip_expires FROM users WHERE is_vip = 1")
        vips = cursor.fetchone()
        conn.close()
        return vips
    
    # Добавь другие методы для аналитики, если нужно

# =============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# =============================================================================

class TelegramBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.gemini_model = genai.GenerativeModel(MODEL)
        self.user_contexts = {}  # Контекст диалогов
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self.news_api = NewsApiClient(api_key=NEWSAPI_KEY) if NEWSAPI_KEY else None
    
    async def get_user_data(self, update: Update) -> UserData:
        """Получить или создать данные пользователя"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            user_data = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or ""
            )
            self.db.save_user(user_data)
        
        return user_data
    
    def is_creator(self, user_id: int) -> bool:
        """Проверка на создателя"""
        return user_id == CREATOR_ID
    
    def is_vip(self, user_data: UserData) -> bool:
        """Проверка VIP статуса"""
        if not user_data.is_vip:
            return False
        if user_data.vip_expires and datetime.datetime.now() > user_data.vip_expires:
            user_data.is_vip = False
            self.db.save_user(user_data)
            return False
        return True
    
    async def add_experience(self, user_data: UserData, points: int = 1):
        """Добавление опыта и проверка уровня"""
        user_data.experience += points
        
        required_exp = user_data.level * 100
        if user_data.experience >= required_exp:
            user_data.level += 1
            user_data.experience = 0
            achievement = f"Достигнут {user_data.level} уровень!"
            if achievement not in user_data.achievements:
                user_data.achievements.append(achievement)
        
        self.db.save_user(user_data)
    
    # Функция для отправки уведомлений
    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        await context.bot.send_message(chat_id=user_id, text=message)
    
    # =============================================================================
    # БАЗОВЫЕ КОМАНДЫ
    # =============================================================================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        if self.is_creator(user_data.user_id):
            message = """
🎯 Добро пожаловать, Создатель!
Вы имеете полный доступ ко всем функциям бота.

👑 Доступные команды создателя:
• /grant_vip - Выдать VIP
• /stats - Полная статистика
• /broadcast - Рассылка
• /users - Список пользователей

🤖 Используйте /help для полного списка команд.
            """
        elif self.is_vip(user_data):
            nickname = user_data.nickname or user_data.first_name
            message = f"""
💎 Добро пожаловать, {nickname}!
У вас VIP статус до {user_data.vip_expires.strftime('%d.%m.%Y') if user_data.vip_expires else 'бессрочно'}.

⭐ VIP возможности:
• /remind - Напоминания
• /secret - Секретные функции
• /lottery - Ежедневная лотерея
• /priority - Приоритетная обработка

🤖 Используйте /help для полного списка команд.
            """
        else:
            message = f"""
🤖 Привет, {user_data.first_name}!
Я многофункциональный AI-бот с более чем 150 возможностями!

🌟 Основные функции:
• 💬 AI-чат с Gemini 2.0
• 📝 Система заметок
• 🌤️ Погода и новости
• 🎮 Игры и развлечения
• 💰 Курсы валют
• 🌐 Поиск и переводы

💎 Хотите больше возможностей? Спросите о VIP!
🤖 Используйте /help для полного списка команд.
            """
        
        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🤖 AI чат", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/help")
        
        help_text = """
📋 ПОЛНЫЙ СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос AI
Или просто напишите сообщение боту!

📝 ЗАМЕТКИ:
/note [текст] - Сохранить заметку
/notes - Показать все заметки
/delnote [номер] - Удалить заметку
/findnote [слово] - Поиск в заметках
/clearnotes - Очистить все заметки

⏰ ВРЕМЯ:
/time - Текущее время
/date - Текущая дата
/timer [секунды] - Таймер
/worldtime - Время в мире

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Случайная шутка
/fact - Интересный факт
/quote - Вдохновляющая цитата
/story - Короткая история
/riddle - Загадка
/motivate - Мотивация
/coin - Монетка
/dice - Кубик
/random [число] - Случайное число
/8ball [вопрос] - Магический шар
/quiz - Викторина
/poem - Стихотворение
/storygen [тема] - История
/idea - Идея
/compliment - Комплимент

🌤️ ПОГОДА:
/weather [город] - Текущая погода
/forecast [город] - Прогноз
/weatheralert [город] - Предупреждения

💰 ФИНАНСЫ:
/currency [из] [в] - Конвертер
/crypto [монета] - Крипта
/stock [тикер] - Акции

🌐 ПОИСК:
/search [запрос] - Поиск
/wiki [запрос] - Wikipedia
/news [тема] - Новости
/youtube [запрос] - YouTube

🔤 ТЕКСТ:
/translate [язык] [текст] - Перевод
/summarize [текст] - Суммаризация
/paraphrase [текст] - Перефраз
/spellcheck [текст] - Орфография

💎 VIP:
/vip - Инфо
/vipbenefits - Преимущества
/viptime - Время
/remind [время] [текст] - Напоминание
/reminders - Список
/delreminder [номер] - Удалить
/recurring [интервал] [текст] - Повторяющееся
/secret - Секрет
/lottery - Лотерея
/exquote - Эксклюзивная цитата
/exfact - Уникальный факт
/gift - Подарок
/priority - Приоритет
/nickname [имя] - Никнейм
/profile - Профиль
/achievements - Достижения
/stats personal - Статистика

👑 СОЗДАТЕЛЬ:
/grant_vip [user] [duration] - Выдать VIP
/revoke_vip [user] - Забрать
/vip_list - Список VIP
/userinfo [user] - Инфо пользователя
/broadcast [текст] - Рассылка
/stats - Статистика
/users - Пользователи
/activity - Активность
/popular - Популярные команды
/growth - Рост
/memory - Память
/backup - Бэкап
/restore - Восстановление
/export [user] - Экспорт
/cleanup - Очистка
/restart - Перезапуск
/maintenance [on/off] - Обслуживание
/log [уровень] - Логи
/config - Конфиг
/update - Обновление

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение] - Сохранить
/ask [вопрос] - Поиск
/memorylist - Список
/memorydel [ключ] - Удалить

🎉 ДНИ РОЖДЕНИЯ:
/setbirthday [дата] - Установить
/birthdays - Ближайшие
/rank - Уровень
/leaderboard - Лидеры

🌐 ЯЗЫКИ:
/language [код] - Смена языка

👥 ГРУППЫ:
/quiz group - Групповая викторина
/wordchain - Слова
/guessnumber - Угадай число
/trivia - Тривья

🎨 КАСТОМИЗАЦИЯ:
/theme [тема] - Тема
/color [цвет] - Цвет
/sound [on/off] - Звуки
/notifications [настройки] - Уведомления
        """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /info"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info_text = """
🤖 О БОТЕ

Версия: 2.0
Создатель: Ernest
Функций: 150+
AI: Gemini 2.0 Flash
База данных: SQLite
Хостинг: Render

Бот работает 24/7 с автопингом.
        """
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        status_text = """
⚡ СТАТУС БОТА

Онлайн: ✅
Версия: 2.0
Пользователей: [кол-во из DB]
Команд выполнено: [из stats]
        """
        # Добавь реальные числа из DB
        await update.message.reply_text(status_text)
        await self.add_experience(user_data, 1)

    # =============================================================================
    # AI-ЧАТ КОМАНДЫ
    # =============================================================================

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /ai"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос после /ai!")
            return
        
        query = " ".join(context.args)
        try:
            response = self.gemini_model.generate_content(query)
            await update.message.reply_text(response.text)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")
        
        await self.add_experience(user_data, 2)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Автоответ на сообщения"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "message")
        
        message = update.message.text
        # Анализ настроения (простой пример)
        sentiment = "положительное" if "хорошо" in message else "нейтральное"
        
        # Контекст диалога
        user_id = user_data.user_id
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        
        self.user_contexts[user_id].append(message)
        if len(self.user_contexts[user_id]) > 10:
            self.user_contexts[user_id] = self.user_contexts[user_id][-10:]
        
        context_str = "\n".join(self.user_contexts[user_id])
        
        prompt = f"Контекст: {context_str}\nНастроение: {sentiment}\nОтветь на: {message}"
        
        try:
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(response.text)
            self.user_contexts[user_id].append(response.text)
        except:
            await update.message.reply_text("❌ Ошибка обработки.")
        
        await self.add_experience(user_data, 1)

    # =============================================================================
    # СИСТЕМА ЗАМЕТОК
    # =============================================================================

    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /note """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/note")
        
        if not context.args:
            await update.message.reply_text("📝 Укажите текст заметки!")
            return
        
        note = " ".join(context.args)
        user_data.notes.append(note)
        self.db.save_user(user_data)
        await update.message.reply_text("✅ Заметка сохранена!")
        await self.add_experience(user_data, 1)

    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /notes """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок!")
            return
        
        notes_text = "\n".join(f"{i+1}. {note}" for i, note in enumerate(user_data.notes))
        await update.message.reply_text(f"📝 Ваши заметки:\n{notes_text}")
        await self.add_experience(user_data, 1)

    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /delnote """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер заметки!")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            del user_data.notes[index]
            self.db.save_user(user_data)
            await update.message.reply_text("✅ Заметка удалена!")
        else:
            await update.message.reply_text("❌ Неверный номер!")
        
        await self.add_experience(user_data, 1)

    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /clearnotes """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clearnotes")
        
        user_data.notes = []
        self.db.save_user(user_data)
        await update.message.reply_text("✅ Все заметки очищены!")
        await self.add_experience(user_data, 1)

    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /findnote """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            await update.message.reply_text("❌ Укажите ключевое слово!")
            return
        
        keyword = " ".join(context.args).lower()
        found = [note for note in user_data.notes if keyword in note.lower()]
        if found:
            notes_text = "\n".join(found)
            await update.message.reply_text(f"🔍 Найденные заметки:\n{notes_text}")
        else:
            await update.message.reply_text("❌ Ничего не найдено!")
        
        await self.add_experience(user_data, 1)

    # =============================================================================
    # ВРЕМЯ И ДАТА
    # =============================================================================

    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /time """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")
        
        now = datetime.datetime.now()
        await update.message.reply_text(f"⏰ Текущее время: {now.strftime('%H:%M:%S')}")
        await self.add_experience(user_data, 1)

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /date """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")
        
        now = datetime.datetime.now()
        await update.message.reply_text(f"📅 Текущая дата: {now.strftime('%d.%m.%Y')}")
        await self.add_experience(user_data, 1)

    async def timer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /timer """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/timer")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("⏰ /timer [секунды]")
            return
        
        seconds = int(context.args[0])
        await update.message.reply_text(f"⏰ Таймер на {seconds} с запущен!")
        await asyncio.sleep(seconds)
        await update.message.reply_text("🔔 Время вышло!")
        await self.add_experience(user_data, 1)

    async def worldtime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /worldtime """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/worldtime")
        
        times = {
            "Москва": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3),
            "Нью-Йорк": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4),
            # Добавь больше
        }
        text = "\n".join(f"{city}: {t.strftime('%H:%M')}" for city, t in times.items())
        await update.message.reply_text(f"🌍 Мировое время:\n{text}")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # РАЗВЛЕКАТЕЛЬНЫЕ КОМАНДЫ
    # =============================================================================

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /joke """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")
        
        prompt = "Расскажи случайную шутку"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /fact """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")
        
        prompt = "Расскажи интересный факт"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /quote """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")
        
        prompt = "Дай вдохновляющую цитату"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def story_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /story """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/story")
        
        prompt = "Придумай короткую историю"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def riddle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /riddle """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/riddle")
        
        prompt = "Задай загадку"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await asyncio.sleep(30)
        prompt2 = "Ответ на предыдущую загадку"
        response2 = self.gemini_model.generate_content(prompt2)
        await update.message.reply_text(response2.text)
        await self.add_experience(user_data, 1)

    async def motivate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /motivate """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/motivate")
        
        prompt = "Дай мотивационное сообщение"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /coin """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/coin")
        
        result = random.choice(["Орёл", "Решка"])
        await update.message.reply_text(f"🪙 {result}!")
        await self.add_experience(user_data, 1)

    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /dice """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/dice")
        
        result = random.randint(1, 6)
        await update.message.reply_text(f"🎲 {result}!")
        await self.add_experience(user_data, 1)

    async def random_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /random """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/random")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("🎲 /random [максимум]")
            return
        
        max_num = int(context.args[0])
        result = random.randint(1, max_num)
        await update.message.reply_text(f"🎲 Случайное число: {result}")
        await self.add_experience(user_data, 1)

    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /8ball """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 Задайте вопрос!")
            return
        
        answers = ["Да", "Нет", "Возможно", "Спроси позже"]
        result = random.choice(answers)
        await update.message.reply_text(f"🔮 {result}")
        await self.add_experience(user_data, 1)

    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /quiz """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quiz")
        
        # Простая викторина, используй Gemini для вопросов
        prompt = "Задай вопрос для викторины с вариантами ответов"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def poem_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /poem """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/poem")
        
        prompt = "Сгенерируй стихотворение"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def storygen_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /storygen """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/storygen")
        
        theme = " ".join(context.args) if context.args else "случайная"
        prompt = f"Сгенерируй историю на тему: {theme}"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def idea_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /idea """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/idea")
        
        prompt = "Придумай идею для проекта"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def compliment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /compliment """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/compliment")
        
        prompt = "Сделай комплимент пользователю"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    # =============================================================================
    # ПОГОДА
    # =============================================================================

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /weather """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        if not context.args or not OPENWEATHER_API_KEY:
            await update.message.reply_text("🌤️ /weather [город]. Установите OPENWEATHER_API_KEY!")
            return
        
        city = " ".join(context.args)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        response = requests.get(url).json()
        if response.get("cod") == 200:
            weather = response["weather"][0]["description"]
            temp = response["main"]["temp"]
            await update.message.reply_text(f"🌤️ В {city}: {weather}, {temp}°C")
        else:
            await update.message.reply_text("❌ Город не найден!")
        await self.add_experience(user_data, 2)

    async def forecast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /forecast """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/forecast")
        
        if not context.args or not OPENWEATHER_API_KEY:
            await update.message.reply_text("📅 /forecast [город]")
            return
        
        city = " ".join(context.args)
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        response = requests.get(url).json()
        if response.get("cod") == "200":
            forecast = "\n".join(f"{item['dt_txt']}: {item['weather'][0]['description']}, {item['main']['temp']}°C" for item in response["list"][:3])
            await update.message.reply_text(f"📅 Прогноз для {city}:\n{forecast}")
        else:
            await update.message.reply_text("❌ Город не найден!")
        await self.add_experience(user_data, 2)

    async def weatheralert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /weatheralert """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weatheralert")
        
        # Используй API для алертов, если доступно
        await update.message.reply_text("⚠️ Предупреждения: Нет активных (проверьте API)")
        await self.add_experience(user_data, 2)

    # =============================================================================
    # ФИНАНСЫ
    # =============================================================================

    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /currency """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/currency")
        
        if len(context.args) < 2:
            await update.message.reply_text("💰 /currency [from] [to]")
            return
        
        from_cur, to_cur = context.args[0].upper(), context.args[1].upper()
        url = f"https://api.freecurrencyapi.com/v1/latest?apikey={CURRENCY_API_KEY}&currencies={to_cur}&base_currency={from_cur}"
        response = requests.get(url).json()
        rate = response.get("data", {}).get(to_cur)
        if rate:
            await update.message.reply_text(f"💰 1 {from_cur} = {rate} {to_cur}")
        else:
            await update.message.reply_text("❌ Ошибка конвертации!")
        await self.add_experience(user_data, 2)

    async def crypto_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /crypto """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/crypto")
        
        if not context.args:
            await update.message.reply_text("📈 /crypto [монета]")
            return
        
        coin = context.args[0].lower()
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
        response = requests.get(url).json()
        price = response.get(coin, {}).get('usd')
        if price:
            await update.message.reply_text(f"💰 {coin.capitalize()}: ${price}")
        else:
            await update.message.reply_text("❌ Монета не найдена!")
        await self.add_experience(user_data, 2)

    async def stock_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /stock """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/stock")
        
        if not context.args or not ALPHAVANTAGE_API_KEY:
            await update.message.reply_text("📈 /stock [тикер]. Установите ALPHAVANTAGE_API_KEY!")
            return
        
        ticker = context.args[0].upper()
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval=5min&apikey={ALPHAVANTAGE_API_KEY}"
        response = requests.get(url).json()
        last_price = list(response.get("Time Series (5min)", {}).values())[0]["4. close"] if response else None
        if last_price:
            await update.message.reply_text(f"📈 {ticker}: ${last_price}")
        else:
            await update.message.reply_text("❌ Тикер не найден!")
        await self.add_experience(user_data, 2)

    # =============================================================================
    # ПОИСК И ПЕРЕВОД
    # =============================================================================

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /search """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/search")
        
        if not context.args:
            await update.message.reply_text("🔍 /search [запрос]")
            return
        
        query = " ".join(context.args)
        prompt = f"Найди информацию по запросу: {query}"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 2)

    async def wiki_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /wiki """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/wiki")
        
        if not context.args:
            await update.message.reply_text("📖 /wiki [запрос]")
            return
        
        query = " ".join(context.args)
        prompt = f"Расскажи о {query} из Wikipedia"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 2)

    async def news_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /news """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/news")
        
        if not context.args or not self.news_api:
            await update.message.reply_text("📰 /news [тема]. Установите NEWSAPI_KEY!")
            return
        
        topic = " ".join(context.args)
        articles = self.news_api.get_top_headlines(q=topic, language='ru')
        if articles['articles']:
            news_text = "\n".join(f"• {art['title']}" for art in articles['articles'][:3])
            await update.message.reply_text(f"📰 Новости по {topic}:\n{news_text}")
        else:
            await update.message.reply_text("❌ Новости не найдены!")
        await self.add_experience(user_data, 2)

    async def youtube_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /youtube """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/youtube")
        
        if not context.args:
            await update.message.reply_text("📺 /youtube [запрос]")
            return
        
        query = " ".join(context.args)
        prompt = f"Найди видео на YouTube по: {query}"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 2)

    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /translate """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text("🌐 /translate [язык] [текст]")
            return
        
        lang = context.args[0]
        text = " ".join(context.args[1:])
        prompt = f"Переведи на {lang}: {text}"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 2)

    async def summarize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /summarize """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/summarize")
        
        if not context.args:
            await update.message.reply_text("📄 /summarize [текст]")
            return
        
        text = " ".join(context.args)
        prompt = f"Суммаризируй: {text}"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 2)

    async def paraphrase_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /paraphrase """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/paraphrase")
        
        if not context.args:
            await update.message.reply_text("🔄 /paraphrase [текст]")
            return
        
        text = " ".join(context.args)
        prompt = f"Перефразируй: {text}"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 2)

    async def spellcheck_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /spellcheck """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/spellcheck")
        
        if not context.args:
            await update.message.reply_text("🖊️ /spellcheck [текст]")
            return
        
        text = " ".join(context.args)
        prompt = f"Проверь орфографию и исправь: {text}"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 2)

    # =============================================================================
    # VIP ФУНКЦИИ
    # =============================================================================

    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /vip """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if self.is_vip(user_data):
            expires = user_data.vip_expires.strftime('%d.%m.%Y') if user_data.vip_expires else 'бессрочно'
            await update.message.reply_text(f"💎 VIP активен до {expires}")
        else:
            await update.message.reply_text("💎 VIP не активен. Спросите у создателя!")
        await self.add_experience(user_data, 1)

    async def vipbenefits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /vipbenefits """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vipbenefits")
        
        benefits = """
⭐ VIP преимущества:
- Напоминания
- Лотерея
- Эксклюзивный контент
- Приоритет
- Персонализация
        """
        await update.message.reply_text(benefits)
        await self.add_experience(user_data, 1)

    async def viptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /viptime """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/viptime")
        
        if self.is_vip(user_data):
            if user_data.vip_expires:
                remaining = (user_data.vip_expires - datetime.datetime.now()).days
                await update.message.reply_text(f"⏳ Осталось {remaining} дней VIP")
            else:
                await update.message.reply_text("⏳ VIP бессрочный")
        else:
            await update.message.reply_text("❌ Нет VIP")
        await self.add_experience(user_data, 1)

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /remind """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        self.db.log_command(user_data.user_id, "/remind")
        
        if len(context.args) < 2:
            await update.message.reply_text("⏰ /remind [время в минутах] [текст]")
            return
        
        minutes = int(context.args[0])
        text = " ".join(context.args[1:])
        run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        
        job = self.scheduler.add_job(
            self.send_notification,
            trigger=DateTrigger(run_date=run_date),
            args=[context, user_data.user_id, f"🔔 Напоминание: {text}"]
        )
        
        user_data.reminders.append({"id": job.id, "text": text, "time": run_date.isoformat()})
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"⏰ Напоминание установлено на {minutes} мин")
        await self.add_experience(user_data, 2)

    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /reminders """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        self.db.log_command(user_data.user_id, "/reminders")
        
        if not user_data.reminders:
            await update.message.reply_text("❌ Нет напоминаний!")
            return
        
        text = "\n".join(f"{i+1}. {rem['text']} at {rem['time']}" for i, rem in enumerate(user_data.reminders))
        await update.message.reply_text(f"⏰ Напоминания:\n{text}")
        await self.add_experience(user_data, 1)

    async def delreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /delreminder """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        self.db.log_command(user_data.user_id, "/delreminder")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ /delreminder [номер]")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.reminders):
            job_id = user_data.reminders[index]["id"]
            self.scheduler.remove_job(job_id)
            del user_data.reminders[index]
            self.db.save_user(user_data)
            await update.message.reply_text("✅ Напоминание удалено!")
        else:
            await update.message.reply_text("❌ Неверный номер!")
        await self.add_experience(user_data, 1)

    async def recurring_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /recurring """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        self.db.log_command(user_data.user_id, "/recurring")
        
        if len(context.args) < 2:
            await update.message.reply_text("🔄 /recurring [интервал в минутах] [текст]")
            return
        
        interval = int(context.args[0])
        text = " ".join(context.args[1:])
        
        job = self.scheduler.add_job(
            self.send_notification,
            trigger=IntervalTrigger(minutes=interval),
            args=[context, user_data.user_id, f"🔔 Повторяющееся: {text}"]
        )
        
        user_data.reminders.append({"id": job.id, "text": text, "interval": interval})
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"🔄 Повторяющееся напоминание каждые {interval} мин")
        await self.add_experience(user_data, 2)

    async def secret_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /secret """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        self.db.log_command(user_data.user_id, "/secret")
        
        await update.message.reply_text("🤫 Секрет: Ты особенный!")
        await self.add_experience(user_data, 1)

    async def lottery_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /lottery """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        self.db.log_command(user_data.user_id, "/lottery")
        
        prize = random.choice(["100 XP", "VIP день", "Секретный факт"])
        await update.message.reply_text(f"🎰 Вы выиграли: {prize}!")
        if prize == "100 XP":
            await self.add_experience(user_data, 100)
        # Добавь логику для других призов
        await self.add_experience(user_data, 1)

    async def exquote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /exquote """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        prompt = "Эксклюзивная цитата для VIP"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def exfact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /exfact """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        prompt = "Уникальный факт для VIP"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def gift_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /gift """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        gift = random.choice(["🎁 Подарок1", "🎁 Подарок2"])
        await update.message.reply_text(gift)
        await self.add_experience(user_data, 1)

    async def priority_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /priority """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        await update.message.reply_text("🚀 Приоритет активирован (просто placeholder)")
        await self.add_experience(user_data, 1)

    async def nickname_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /nickname """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        if not context.args:
            await update.message.reply_text("👤 /nickname [имя]")
            return
        
        user_data.nickname = " ".join(context.args)
        self.db.save_user(user_data)
        await update.message.reply_text(f"👤 Никнейм установлен: {user_data.nickname}")
        await self.add_experience(user_data, 1)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /profile """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        profile = f"""
👤 Профиль:
Имя: {user_data.first_name}
Ник: {user_data.nickname}
Уровень: {user_data.level}
VIP: {"Да" if self.is_vip(user_data) else "Нет"}
        """
        await update.message.reply_text(profile)
        await self.add_experience(user_data, 1)

    async def achievements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /achievements """
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 VIP функция!")
            return
        
        ach = "\n".join(user_data.achievements)
        await update.message.reply_text(f"🏆 Достижения:\n{ach}")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # =============================================================================

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /grant_vip """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("/grant_vip [user_id] [duration: week/month/year/permanent]")
            return
        
        target_id = int(context.args[0])
        duration = context.args[1].lower()
        target_user = self.db.get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ Пользователь не найден!")
            return
        
        now = datetime.datetime.now()
        if duration == "week":
            target_user.vip_expires = now + datetime.timedelta(weeks=1)
        elif duration == "month":
            target_user.vip_expires = now + datetime.timedelta(days=30)
        elif duration == "year":
            target_user.vip_expires = now + datetime.timedelta(days=365)
        elif duration == "permanent":
            target_user.vip_expires = None
        else:
            await update.message.reply_text("❌ Неверная длительность!")
            return
        
        target_user.is_vip = True
        self.db.save_user(target_user)
        await update.message.reply_text("✅ VIP выдан!")
        try:
            await context.bot.send_message(target_id, "🎉 Вы получили VIP!")
        except:
            pass

    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /revoke_vip """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("/revoke_vip [user_id]")
            return
        
        target_id = int(context.args[0])
        target_user = self.db.get_user(target_id)
        if target_user:
            target_user.is_vip = False
            target_user.vip_expires = None
            self.db.save_user(target_user)
            await update.message.reply_text("✅ VIP отозван!")
        else:
            await update.message.reply_text("❌ Пользователь не найден!")

    async def vip_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /vip_list """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        vips = self.db.get_vip_users()  # Предполагая метод возвращает список
        text = "\n".join(f"{vip[1]} (ID: {vip[0]})" for vip in vips) if vips else "Нет VIP"
        await update.message.reply_text(f"💎 VIP список:\n{text}")

    async def userinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /userinfo """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("/userinfo [user_id]")
            return
        
        target_id = int(context.args[0])
        target_user = self.db.get_user(target_id)
        if target_user:
            info = f"ID: {target_user.user_id}\nИмя: {target_user.first_name}\nVIP: {target_user.is_vip}"
            await update.message.reply_text(info)
        else:
            await update.message.reply_text("❌ Не найден!")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /broadcast """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("/broadcast [текст]")
            return
        
        text = " ".join(context.args)
        users = self.db.get_all_users()
        for user in users:
            try:
                await context.bot.send_message(user[0], text)
            except:
                pass
        await update.message.reply_text("✅ Рассылка отправлена!")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /stats """
        user_data = await self.get_user_data(update)
        if not self.is_creator(user_data.user_id):
            # Личная статистика
            stats = f"Уровень: {user_data.level}\nОпыт: {user_data.experience}\nVIP: {'Да' if self.is_vip(user_data) else 'Нет'}"
            await update.message.reply_text(stats)
            return
        
        # Полная для создателя
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        # Добавь больше stats
        await update.message.reply_text(f"Пользователей: {total_users}")
        conn.close()

    # Добавь остальные команды создателя аналогично: /users, /activity, /popular, /growth, /memory, /backup и т.д.
    # Для backup: pickle.dump или json.dump DB
    # Для restart: os._exit(0) - но на Render лучше manual

    # =============================================================================
    # ИНТЕЛЛЕКТУАЛЬНЫЕ ФУНКЦИИ
    # =============================================================================

    async def memorysave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /memorysave """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorysave")
        
        if len(context.args) < 2:
            await update.message.reply_text("/memorysave [ключ] [значение]")
            return
        
        key = context.args[0]
        value = " ".join(context.args[1:])
        user_data.memory_data[key] = value
        self.db.save_user(user_data)
        await update.message.reply_text("🧠 Сохранено!")
        await self.add_experience(user_data, 1)

    async def ask_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /ask """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ask")
        
        if not context.args:
            await update.message.reply_text("/ask [вопрос]")
            return
        
        question = " ".join(context.args)
        # Поиск в памяти
        for key, value in user_data.memory_data.items():
            if question in key:
                await update.message.reply_text(value)
                return
        
        # Если не найдено, Gemini
        response = self.gemini_model.generate_content(question)
        await update.message.reply_text(response.text)
        await self.add_experience(user_data, 1)

    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /memorylist """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorylist")
        
        if not user_data.memory_data:
            await update.message.reply_text("🧠 Память пуста!")
            return
        
        text = "\n".join(f"{key}: {value}" for key, value in user_data.memory_data.items())
        await update.message.reply_text(f"🧠 Память:\n{text}")
        await self.add_experience(user_data, 1)

    async def memorydel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /memorydel """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorydel")
        
        if not context.args:
            await update.message.reply_text("/memorydel [ключ]")
            return
        
        key = context.args[0]
        if key in user_data.memory_data:
            del user_data.memory_data[key]
            self.db.save_user(user_data)
            await update.message.reply_text("🧠 Удалено!")
        else:
            await update.message.reply_text("❌ Ключ не найден!")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # СПЕЦИАЛЬНЫЕ ВОЗМОЖНОСТИ
    # =============================================================================

    async def setbirthday_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /setbirthday """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/setbirthday")
        
        if not context.args:
            await update.message.reply_text("/setbirthday [dd.mm]")
            return
        
        user_data.birthday = context.args[0]
        self.db.save_user(user_data)
        await update.message.reply_text("🎂 Дата рождения установлена!")
        await self.add_experience(user_data, 1)

    async def birthdays_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /birthdays """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/birthdays")
        
        # Логика для ближайших ДР из DB (добавь query)
        await update.message.reply_text("🎂 Ближайшие ДР: [список]")
        await self.add_experience(user_data, 1)

    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /rank """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")
        
        await update.message.reply_text(f"🏅 Уровень: {user_data.level}, Опыт: {user_data.experience}")
        await self.add_experience(user_data, 1)

    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /leaderboard """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/leaderboard")
        
        leaders = self.db.get_all_users()[:10]
        text = "\n".join(f"{i+1}. {user[1]} - lvl {user[2]}" for i, user in enumerate(leaders))
        await update.message.reply_text(f"🏆 Лидеры:\n{text}")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # МУЛЬТИЯЗЫЧНАЯ ПОДДЕРЖКА
    # =============================================================================

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /language """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/language")
        
        if not context.args:
            await update.message.reply_text("/language [ru/en/etc]")
            return
        
        lang = context.args[0]
        user_data.language = lang
        self.db.save_user(user_data)
        await update.message.reply_text("🈯 Язык изменён!")
        # В реальности адаптируй ответы на lang
        await self.add_experience(user_data, 1)

    # =============================================================================
    # РАБОТА В ГРУППАХ
    # =============================================================================

    # Для групповых игр - используй chat_id, храни состояние в dict
    # Пример для /quiz group - аналогично quiz, но для группы

    # =============================================================================
    # КАСТОМИЗАЦИЯ
    # =============================================================================

    async def theme_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /theme """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/theme")
        
        if not context.args:
            await update.message.reply_text("/theme [тема]")
            return
        
        user_data.theme = context.args[0]
        self.db.save_user(user_data)
        await update.message.reply_text("🎭 Тема изменена!")
        await self.add_experience(user_data, 1)

    async def color_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /color """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/color")
        
        if not context.args:
            await update.message.reply_text("/color [цвет]")
            return
        
        user_data.color = context.args[0]
        self.db.save_user(user_data)
        await update.message.reply_text("🌈 Цвет изменён!")
        await self.add_experience(user_data, 1)

    async def sound_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /sound """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/sound")
        
        if not context.args:
            await update.message.reply_text("/sound [on/off]")
            return
        
        user_data.sound_notifications = context.args[0].lower() == "on"
        self.db.save_user(user_data)
        await update.message.reply_text("🔊 Звуки изменены!")
        await self.add_experience(user_data, 1)

    async def notifications_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /notifications """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notifications")
        
        # Логика настройки
        await update.message.reply_text("🔔 Настройки уведомлений (placeholder)")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # CALLBACK ОБРАБОТЧИКИ
    # =============================================================================

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            await self.help_command(update, context)
        # Добавь другие

    # =============================================================================
    # ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
    # =============================================================================

    async def run_bot(self):
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавь ВСЕ handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("info", self.info_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("ai", self.ai_command))
        application.add_handler(CommandHandler("note", self.note_command))
        application.add_handler(CommandHandler("notes", self.notes_command))
        application.add_handler(CommandHandler("delnote", self.delnote_command))
        application.add_handler(CommandHandler("clearnotes", self.clearnotes_command))
        application.add_handler(CommandHandler("findnote", self.findnote_command))
        application.add_handler(CommandHandler("time", self.time_command))
        application.add_handler(CommandHandler("date", self.date_command))
        application.add_handler(CommandHandler("timer", self.timer_command))
        application.add_handler(CommandHandler("worldtime", self.worldtime_command))
        application.add_handler(CommandHandler("joke", self.joke_command))
        application.add_handler(CommandHandler("fact", self.fact_command))
        application.add_handler(CommandHandler("quote", self.quote_command))
        application.add_handler(CommandHandler("story", self.story_command))
        application.add_handler(CommandHandler("riddle", self.riddle_command))
        application.add_handler(CommandHandler("motivate", self.motivate_command))
        application.add_handler(CommandHandler("coin", self.coin_command))
        application.add_handler(CommandHandler("dice", self.dice_command))
        application.add_handler(CommandHandler("random", self.random_command))
        application.add_handler(CommandHandler("8ball", self.eightball_command))
        application.add_handler(CommandHandler("quiz", self.quiz_command))
        application.add_handler(CommandHandler("poem", self.poem_command))
        application.add_handler(CommandHandler("storygen", self.storygen_command))
        application.add_handler(CommandHandler("idea", self.idea_command))
        application.add_handler(CommandHandler("compliment", self.compliment_command))
        application.add_handler(CommandHandler("weather", self.weather_command))
        application.add_handler(CommandHandler("forecast", self.forecast_command))
        application.add_handler(CommandHandler("weatheralert", self.weatheralert_command))
        application.add_handler(CommandHandler("currency", self.currency_command))
        application.add_handler(CommandHandler("crypto", self.crypto_command))
        application.add_handler(CommandHandler("stock", self.stock_command))
        application.add_handler(CommandHandler("search", self.search_command))
        application.add_handler(CommandHandler("wiki", self.wiki_command))
        application.add_handler(CommandHandler("news", self.news_command))
        application.add_handler(CommandHandler("youtube", self.youtube_command))
        application.add_handler(CommandHandler("translate", self.translate_command))
        application.add_handler(CommandHandler("summarize", self.summarize_command))
        application.add_handler(CommandHandler("paraphrase", self.paraphrase_command))
        application.add_handler(CommandHandler("spellcheck", self.spellcheck_command))
        application.add_handler(CommandHandler("vip", self.vip_command))
        application.add_handler(CommandHandler("vipbenefits", self.vipbenefits_command))
        application.add_handler(CommandHandler("viptime", self.viptime_command))
        application.add_handler(CommandHandler("remind", self.remind_command))
        application.add_handler(CommandHandler("reminders", self.reminders_command))
        application.add_handler(CommandHandler("delreminder", self.delreminder_command))
        application.add_handler(CommandHandler("recurring", self.recurring_command))
        application.add_handler(CommandHandler("secret", self.secret_command))
        application.add_handler(CommandHandler("lottery", self.lottery_command))
        application.add_handler(CommandHandler("exquote", self.exquote_command))
        application.add_handler(CommandHandler("exfact", self.exfact_command))
        application.add_handler(CommandHandler("gift", self.gift_command))
        application.add_handler(CommandHandler("priority", self.priority_command))
        application.add_handler(CommandHandler("nickname", self.nickname_command))
        application.add_handler(CommandHandler("profile", self.profile_command))
        application.add_handler(CommandHandler("achievements", self.achievements_command))
        application.add_handler(CommandHandler("grant_vip", self.grant_vip_command))
        application.add_handler(CommandHandler("revoke_vip", self.revoke_vip_command))
        application.add_handler(CommandHandler("vip_list", self.vip_list_command))
        application.add_handler(CommandHandler("userinfo", self.userinfo_command))
        application.add_handler(CommandHandler("broadcast", self.broadcast_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        # Добавь handlers для остальных: /users, /activity и т.д.
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        await application.run_polling()

async def main():
    bot = TelegramBot()
    await bot.run_bot()

if __name__ == "__main__":
    asyncio.run(main())
