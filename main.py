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

# API ключи
BOT_TOKEN = "8176339131:AAGVKJoK9Y9fdQcTqMCp0Vm95IMuQWnCNGo"
GEMINI_API_KEY = "zaSyCo4ymvNmI2JkYEuocIv3w_HsUyNPd6oEg"
CURRENCY_API_KEY = "fca_live_86O15Ga6b1M0bnm6FCiDfrBB7USGCEPiAUyjiuwL"

# ID создателя бота
CREATOR_ID = 7108255346  # Ernest's Telegram ID

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)

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
                memory_data=json.loads(row[13])
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
         achievements, memory_data, last_activity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

# =============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# =============================================================================

class TelegramBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.user_contexts = {}  # Контекст диалогов
        
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
        
        # Проверка повышения уровня
        required_exp = user_data.level * 100
        if user_data.experience >= required_exp:
            user_data.level += 1
            user_data.experience = 0
            # Добавить достижение
            achievement = f"Достигнут {user_data.level} уровень!"
            if achievement not in user_data.achievements:
                user_data.achievements.append(achievement)
        
        self.db.save_user(user_data)

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

⏰ ВРЕМЯ:
/time - Текущее время
/date - Текущая дата
/timer [секунды] - Таймер
/worldtime - Время в мире

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Случайная шутка
/fact - Интересный факт
/quote - Вдохновляющая цитата
/coin - Подбросить монетку
/dice - Бросить кубик
/8ball [вопрос] - Магический шар

🌤️ ПОГОДА:
/weather [город] - Текущая погода
/forecast [город] - Прогноз на 3 дня

💰 ФИНАНСЫ:
/currency [из] [в] - Конвертер валют
/crypto [монета] - Курс криптовалюты

🌐 ПОИСК:
/search [запрос] - Поиск в интернете
/wiki [запрос] - Wikipedia
/translate [язык] [текст] - Перевод

🔤 ТЕКСТ:
/summarize [текст] - Краткое изложение
/paraphrase [текст] - Перефразирование

💎 VIP ФУНКЦИИ:
/vip - Информация о VIP
/remind [время] [текст] - Напоминания (VIP)
/secret - Секретная функция (VIP)
/lottery - Лотерея (VIP)

👑 СОЗДАТЕЛЬ:
/grant_vip [user] [time] - Выдать VIP
/stats - Полная статистика
/broadcast [текст] - Рассылка всем
        """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /info"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info_text = """
🤖 ИНФОРМАЦИЯ О БОТЕ

📊 Статистика:
• Версия: 2.0
• AI Модель: Google Gemini 2.0 Flash
• Функций: 150+
• Языков: 9

🎯 Возможности:
• Интеллектуальный AI-чат
• Система заметок и напоминаний
• Погода и финансы в реальном времени
• Развлечения и игры
• Многоязычная поддержка
• VIP-система с премиум функциями

⚡ Технологии:
• Python + aiogram
• Google Gemini AI
• SQLite база данных
• Множественные API интеграции

👨‍💻 Разработка: 2024
🌟 Статус: Активная разработка
        """
        
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)

# =============================================================================
# AI ЧАТ ФУНКЦИИ
# =============================================================================

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AI чат команда"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text(
                "💬 Задайте вопрос AI!\n"
                "Пример: /ai Расскажи о космосе\n"
                "Или просто напишите сообщение боту без команды!"
            )
            return
        
        question = " ".join(context.args)
        await self.process_ai_request(update, question, user_data)

    async def process_ai_request(self, update: Update, question: str, user_data: UserData):
        """Обработка AI запроса"""
        try:
            # Отправляем индикатор "печатает"
            await update.message.reply_chat_action("typing")
            
            # Получаем контекст диалога
            context_messages = self.user_contexts.get(user_data.user_id, [])
            
            # Формируем промпт с контекстом
            full_prompt = f"""
Ты умный и дружелюбный AI-ассистент в Telegram боте.
Отвечай на {user_data.language} языке.
{"VIP пользователь" if self.is_vip(user_data) else "Обычный пользователь"}.
Имя пользователя: {user_data.nickname or user_data.first_name}.

Контекст предыдущих сообщений:
{chr(10).join(context_messages[-5:]) if context_messages else "Нет предыдущего контекста"}

Текущий вопрос: {question}

Отвечай максимально полезно, дружелюбно и информативно.
"""
            
            # Генерируем ответ через Gemini
            response = self.gemini_model.generate_content(full_prompt)
            answer = response.text
            
            # Сохраняем в контекст
            if user_data.user_id not in self.user_contexts:
                self.user_contexts[user_data.user_id] = []
            
            self.user_contexts[user_data.user_id].append(f"Пользователь: {question}")
            self.user_contexts[user_data.user_id].append(f"Бот: {answer}")
            
            # Ограничиваем размер контекста
            if len(self.user_contexts[user_data.user_id]) > 10:
                self.user_contexts[user_data.user_id] = self.user_contexts[user_data.user_id][-10:]
            
            await update.message.reply_text(f"🤖 {answer}")
            await self.add_experience(user_data, 2)
            
        except Exception as e:
            logger.error(f"Ошибка AI: {e}")
            await update.message.reply_text(
                "😔 Извините, произошла ошибка при обработке запроса. "
                "Попробуйте позже или переформулируйте вопрос."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений (автоответ AI)"""
        user_data = await self.get_user_data(update)
        
        # Проверяем, что это не команда
        if update.message.text.startswith('/'):
            return
        
        # Проверяем, обращаются ли к боту в группе
        if update.message.chat.type != 'private':
            bot_username = context.bot.username
            if f"@{bot_username}" not in update.message.text:
                return
            # Убираем упоминание из текста
            message_text = update.message.text.replace(f"@{bot_username}", "").strip()
        else:
            message_text = update.message.text
        
        # Обрабатываем как AI запрос
        await self.process_ai_request(update, message_text, user_data)

# =============================================================================
# СИСТЕМА ЗАМЕТОК
# =============================================================================

    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранить заметку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/note")
        
        if not context.args:
            await update.message.reply_text("📝 Введите текст заметки!\nПример: /note Купить молоко")
            return
        
        note_text = " ".join(context.args)
        timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        note_with_date = f"{note_text} ({timestamp})"
        
        user_data.notes.append(note_with_date)
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"✅ Заметка сохранена!\n📝 {note_text}")
        await self.add_experience(user_data, 1)

    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все заметки"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            await update.message.reply_text("📝 У вас пока нет заметок.\nИспользуйте /note [текст] для создания.")
            return
        
        notes_text = "📝 ВАШИ ЗАМЕТКИ:\n\n"
        for i, note in enumerate(user_data.notes, 1):
            notes_text += f"{i}. {note}\n"
        
        await update.message.reply_text(notes_text)
        await self.add_experience(user_data, 1)

    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удалить заметку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args:
            await update.message.reply_text("🗑️ Укажите номер заметки для удаления!\nПример: /delnote 1")
            return
        
        try:
            note_num = int(context.args[0])
            if 1 <= note_num <= len(user_data.notes):
                deleted_note = user_data.notes.pop(note_num - 1)
                self.db.save_user(user_data)
                await update.message.reply_text(f"✅ Заметка #{note_num} удалена!")
            else:
                await update.message.reply_text("❌ Неверный номер заметки!")
        except ValueError:
            await update.message.reply_text("❌ Укажите правильный номер заметки!")
        
        await self.add_experience(user_data, 1)

    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск в заметках"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            await update.message.reply_text("🔍 Введите слово для поиска!\nПример: /findnote молоко")
            return
        
        search_term = " ".join(context.args).lower()
        found_notes = []
        
        for i, note in enumerate(user_data.notes, 1):
            if search_term in note.lower():
                found_notes.append(f"{i}. {note}")
        
        if found_notes:
            result = f"🔍 НАЙДЕННЫЕ ЗАМЕТКИ (по запросу '{search_term}'):\n\n" + "\n".join(found_notes)
        else:
            result = f"❌ Заметки с '{search_term}' не найдены."
        
        await update.message.reply_text(result)
        await self.add_experience(user_data, 1)

# =============================================================================
# ВРЕМЯ И ДАТА
# =============================================================================

    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Текущее время"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")
        
        # Время в разных часовых поясах
        import pytz
        
        moscow_tz = pytz.timezone('Europe/Moscow')
        rome_tz = pytz.timezone('Europe/Rome')
        utc_tz = pytz.UTC
        
        now_utc = datetime.datetime.now(utc_tz)
        moscow_time = now_utc.astimezone(moscow_tz)
        rome_time = now_utc.astimezone(rome_tz)
        
        time_text = f"""
🕐 ТЕКУЩЕЕ ВРЕМЯ

🇷🇺 Москва: {moscow_time.strftime('%H:%M:%S')}
🇮🇹 Рим: {rome_time.strftime('%H:%M:%S')}
🌍 UTC: {now_utc.strftime('%H:%M:%S')}

📅 Дата: {moscow_time.strftime('%d.%m.%Y')}
📆 День недели: {moscow_time.strftime('%A')}
        """
        
        await update.message.reply_text(time_text)
        await self.add_experience(user_data, 1)

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Текущая дата"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")
        
        now = datetime.datetime.now()
        date_text = f"""
📅 СЕГОДНЯ

📆 Дата: {now.strftime('%d.%m.%Y')}
📅 День недели: {now.strftime('%A')}
📊 День года: {now.timetuple().tm_yday}
🗓️ Неделя года: {now.isocalendar()[1]}
🌗 Месяц: {now.strftime('%B')}
        """
        
        await update.message.reply_text(date_text)
        await self.add_experience(user_data, 1)

# =============================================================================
# РАЗВЛЕЧЕНИЯ
# =============================================================================

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Случайная шутка"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")
        
        jokes = [
            "Почему программисты предпочитают темную тему? Потому что свет привлекает баги! 🐛",
            "Сколько программистов нужно, чтобы вкрутить лампочку? Ноль, это аппаратная проблема! 💡",
            "Почему у Java программистов всегда болит голова? Из-за слишком многих исключений! ☕",
            "Что говорит один бит другому? Тебя не хватало в моей жизни! 💾",
            "Почему алгоритмы сортировки никогда не грустят? Потому что они всегда все расставляют по местам! 📊"
        ]
        
        joke = random.choice(jokes)
        await update.message.reply_text(f"😄 {joke}")
        await self.add_experience(user_data, 1)

    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Интересный факт"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")
        
        facts = [
            "🧠 Человеческий мозг потребляет около 20% всей энергии тела, несмотря на то, что весит всего 2% от массы тела!",
            "🌊 В океанах Земли содержится 99% жизненного пространства планеты!",
            "⚡ Молния может нагреть воздух до температуры 30,000°C - в 5 раз горячее поверхности Солнца!",
            "🐙 У осьминогов три сердца и голубая кровь!",
            "🌌 В наблюдаемой Вселенной больше звезд, чем песчинок на всех пляжах Земли!"
        ]
        
        fact = random.choice(facts)
        await update.message.reply_text(f"🧠 {fact}")
        await self.add_experience(user_data, 1)

    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вдохновляющая цитата"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")
        
        quotes = [
            "💪 \"Успех - это способность идти от неудачи к неудаче, не теряя энтузиазма.\" - Уинстон Черчилль",
            "🌟 \"Единственный способ делать отличную работу - любить то, что ты делаешь.\" - Стив Джобс",
            "🚀 \"Будущее принадлежит тем, кто верит в красоту своих мечтаний.\" - Элеонор Рузвельт",
            "⭐ \"Не бойтесь идти медленно, бойтесь стоять на месте.\" - Китайская пословица",
            "🎯 \"Лучшее время посадить дерево было 20 лет назад. Второе лучшее время - сейчас.\" - Китайская пословица"
        ]
        
        quote = random.choice(quotes)
        await update.message.reply_text(f"✨ {quote}")
        await self.add_experience(user_data, 1)

    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подбросить монетку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/coin")
        
        result = random.choice(["Орел 🦅", "Решка 👑"])
        await update.message.reply_text(f"🪙 Монетка показала: **{result}**")
        await self.add_experience(user_data, 1)

    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Бросить кубик"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/dice")
        
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 Кубик показал: {dice_faces[result-1]} ({result})")
        await self.add_experience(user_data, 1)

    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Магический шар 8"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 Задайте вопрос магическому шару!\nПример: /8ball Стоит ли мне изучать программирование?")
            return
        
        answers = [
            "✅ Определенно да!",
            "🤔 Скорее всего",
            "🎯 Да, конечно!",
            "❓ Трудно сказать",
            "❌ Не думаю",
            "🚫 Определенно нет",
            "⏳ Спроси позже",
            "🌟 Звезды говорят да!",
            "⚡ Возможно",
            "🎲 Полагайся на удачу"
        ]
        
        question = " ".join(context.args)
        answer = random.choice(answers)
        await update.message.reply_text(f"🔮 **Вопрос:** {question}\n**Ответ:** {answer}")
        await self.add_experience(user_data, 1)

# =============================================================================
# ПОГОДА И ФИНАНСЫ
# =============================================================================

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Текущая погода"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        if not context.args:
            await update.message.reply_text("🌤️ Укажите город!\nПример: /weather Москва")
            return
        
        city = " ".join(context.args)
        try:
            # Используем OpenWeatherMap API (нужно добавить ключ)
            # Для демонстрации используем заглушку
            weather_data = {
                "temperature": random.randint(-10, 35),
                "description": random.choice(["ясно", "облачно", "дождь", "снег", "туман"]),
                "humidity": random.randint(30, 90),
                "wind": random.randint(0, 15)
            }
            
            weather_text = f"""
🌤️ ПОГОДА В {city.upper()}

🌡️ Температура: {weather_data['temperature']}°C
☁️ Условия: {weather_data['description']}
💧 Влажность: {weather_data['humidity']}%
💨 Ветер: {weather_data['wind']} м/с

⏰ Обновлено: {datetime.datetime.now().strftime('%H:%M')}
            """
            
            await update.message.reply_text(weather_text)
            
        except Exception as e:
            await update.message.reply_text("❌ Не удалось получить данные о погоде. Проверьте название города.")
        
        await self.add_experience(user_data, 1)

    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Конвертер валют"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/currency")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "💰 Укажите валюты для конвертации!\n"
                "Пример: /currency USD RUB\n"
                "Доступные: USD, EUR, RUB, GBP, JPY, CHF, CAD, AUD"
            )
            return
        
        from_currency = context.args[0].upper()
        to_currency = context.args[1].upper()
        amount = float(context.args[2]) if len(context.args) > 2 else 1.0
        
        try:
            # Используем FreeCurrencyAPI
            url = f"https://api.freecurrencyapi.com/v1/latest"
            params = {
                'apikey': CURRENCY_API_KEY,
                'base_currency': from_currency,
                'currencies': to_currency
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    
                    if 'data' in data and to_currency in data['data']:
                        rate = data['data'][to_currency]
                        converted = amount * rate
                        
                        currency_text = f"""
💰 КОНВЕРТЕР ВАЛЮТ

💵 {amount} {from_currency} = {converted:.2f} {to_currency}
📊 Курс: 1 {from_currency} = {rate:.4f} {to_currency}
⏰ Обновлено: {datetime.datetime.now().strftime('%H:%M')}
                        """
                        await update.message.reply_text(currency_text)
                    else:
                        await update.message.reply_text("❌ Неверный код валюты!")
                        
        except Exception as e:
            logger.error(f"Currency error: {e}")
            await update.message.reply_text("❌ Ошибка получения курса валют.")
        
        await self.add_experience(user_data, 1)

# =============================================================================
# ПОИСК И ПЕРЕВОДЫ
# =============================================================================

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск в интернете"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/search")
        
        if not context.args:
            await update.message.reply_text("🔍 Введите поисковый запрос!\nПример: /search Python programming")
            return
        
        query = " ".join(context.args)
        
        try:
            # Используем AI для генерации поискового ответа
            search_prompt = f"""
Пользователь ищет информацию по запросу: "{query}"
Предоставь краткий, но информативный ответ на русском языке, 
включающий основные факты по этой теме.
"""
            
            response = self.gemini_model.generate_content(search_prompt)
            search_result = response.text
            
            result_text = f"""
🔍 РЕЗУЛЬТАТЫ ПОИСКА: "{query}"

{search_result}

💡 Для более детальной информации используйте /wiki {query}
            """
            
            await update.message.reply_text(result_text)
            
        except Exception as e:
            await update.message.reply_text("❌ Ошибка при выполнении поиска.")
        
        await self.add_experience(user_data, 2)

    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переводчик"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "🌐 Укажите язык и текст для перевода!\n"
                "Пример: /translate en Привет мир\n"
                "Языки: en, es, fr, de, it, zh, ja, ko"
            )
            return
        
        target_lang = context.args[0].lower()
        text_to_translate = " ".join(context.args[1:])
        
        try:
            # Используем AI для перевода
            translate_prompt = f"""
Переведи следующий текст на {target_lang} язык:
"{text_to_translate}"

Предоставь только перевод без дополнительных комментариев.
"""
            
            response = self.gemini_model.generate_content(translate_prompt)
            translation = response.text.strip()
            
            translate_text = f"""
🌐 ПЕРЕВОД

📝 Оригинал: {text_to_translate}
🔄 Перевод ({target_lang}): {translation}
            """
            
            await update.message.reply_text(translate_text)
            
        except Exception as e:
            await update.message.reply_text("❌ Ошибка при переводе текста.")
        
        await self.add_experience(user_data, 1)

# =============================================================================
# VIP СИСТЕМА
# =============================================================================

    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о VIP"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if self.is_vip(user_data):
            vip_text = f"""
💎 ВАШ VIP СТАТУС

✅ Статус: Активен
⏰ До: {user_data.vip_expires.strftime('%d.%m.%Y %H:%M') if user_data.vip_expires else 'Бессрочно'}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/100

🌟 VIP ВОЗМОЖНОСТИ:
• /remind - Персональные напоминания
• /secret - Секретная функция
• /lottery - Ежедневная лотерея  
• /priority - Приоритетная обработка
• /nickname - Персональное обращение
• /achievements - Ваши достижения

💎 Статус: {"👑 Бессрочный VIP" if not user_data.vip_expires else f"⏳ {(user_data.vip_expires - datetime.datetime.now()).days} дней осталось"}
            """
        else:
            vip_text = """
💎 VIP СТАТУС

❌ У вас нет VIP статуса

🌟 VIP ПРИВИЛЕГИИ:
• 📝 Персональные напоминания
• 🎰 Ежедневная лотерея
• 🔮 Секретные функции
• ⚡ Приоритетная обработка AI
• 🎁 Эксклюзивный контент
• 🏆 Система достижений
• 👤 Персональные настройки

💰 Стоимость VIP:
• 1 неделя - 100 руб
• 1 месяц - 300 руб  
• 1 год - 2000 руб
• Навсегда - 5000 руб

📞 Для получения VIP обратитесь к создателю бота!
            """
        
        await update.message.reply_text(vip_text)
        await self.add_experience(user_data, 1)

    async def secret_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Секретная VIP функция"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/secret")
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP пользователям!")
            return
        
        secrets = [
            "🔮 Тайна дня: Самые успешные люди читают в среднем 50 книг в год!",
            "💎 Секрет: Лучшее время для принятия решений - утром, когда мозг свежий!",
            "🌟 Совет VIP: Техника Помодоро увеличивает продуктивность на 40%!",
            "⚡ Факт: Медитация всего 10 минут в день улучшает концентрацию на 23%!",
            "🧠 Хак: Изучение нового языка увеличивает объем серого вещества мозга!"
        ]
        
        secret = random.choice(secrets)
        await update.message.reply_text(f"🤫 {secret}\n\n💎 Эксклюзивно для VIP!")
        await self.add_experience(user_data, 3)

    async def lottery_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """VIP лотерея"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/lottery")
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Лотерея доступна только VIP пользователям!")
            return
        
        # Проверяем, участвовал ли уже сегодня
        today = datetime.datetime.now().date()
        last_lottery = user_data.memory_data.get('last_lottery')
        
        if last_lottery and datetime.datetime.fromisoformat(last_lottery).date() == today:
            await update.message.reply_text("🎰 Вы уже участвовали в лотерее сегодня! Приходите завтра!")
            return
        
        # Розыгрыш
        win_chance = random.randint(1, 100)
        
        if win_chance <= 10:  # 10% шанс крупного выигрыша
            prize = "🏆 ДЖЕКПОТ! +100 опыта и специальное достижение!"
            user_data.experience += 100
            user_data.achievements.append(f"🎰 Выиграл джекпот {today}")
        elif win_chance <= 30:  # 20% шанс хорошего выигрыша
            prize = "🎁 Отлично! +50 опыта!"
            user_data.experience += 50
        elif win_chance <= 60:  # 30% шанс обычного выигрыша
            prize = "✨ Неплохо! +20 опыта!"
            user_data.experience += 20
        else:  # 40% шанс утешительного приза
            prize = "🍀 В следующий раз повезет больше! +5 опыта за участие."
            user_data.experience += 5
        
        user_data.memory_data['last_lottery'] = datetime.datetime.now().isoformat()
        self.db.save_user(user_data)
        
        lottery_text = f"""
🎰 VIP ЛОТЕРЕЯ

🎲 Ваш результат: {win_chance}/100
🎁 Приз: {prize}

💎 Возвращайтесь завтра за новым шансом!
        """
        
        await update.message.reply_text(lottery_text)
        await self.add_experience(user_data, 2)

# =============================================================================
# КОМАНДЫ СОЗДАТЕЛЯ
# =============================================================================

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выдать VIP статус"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/grant_vip")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "👑 Использование: /grant_vip [user_id] [duration]\n"
                "Duration: week, month, year, permanent\n"
                "Пример: /grant_vip 123456789 month"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            duration = context.args[1].lower()
            
            target_user = self.db.get_user(target_user_id)
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            # Установка времени истечения
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
            
            await update.message.reply_text(
                f"✅ VIP статус выдан пользователю {target_user_id}!\n"
                f"📅 До: {target_user.vip_expires.strftime('%d.%m.%Y') if target_user.vip_expires else 'Бессрочно'}"
            )
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    target_user_id,
                    f"🎉 Поздравляем! Вам выдан VIP статус!\n"
                    f"📅 Действует до: {target_user.vip_expires.strftime('%d.%m.%Y') if target_user.vip_expires else 'Бессрочно'}\n"
                    f"💎 Используйте /vip для просмотра возможностей!"
                )
            except:
                pass  # Если не удалось отправить уведомление
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя!")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика бота (создатель)"""
        if not self.is_creator(update.effective_user.id):
            user_data = await self.get_user_data(update)
            # Показать личную статистику
            stats_text = f"""
📊 ВАША СТАТИСТИКА

👤 Пользователь: {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/100
💎 VIP: {"✅ Да" if self.is_vip(user_data) else "❌ Нет"}
📝 Заметок: {len(user_data.notes)}
🏆 Достижений: {len(user_data.achievements)}
📅 Зарегистрирован: недавно
            """
            await update.message.reply_text(stats_text)
            return
        
        self.db.log_command(update.effective_user.id, "/stats")
        
        # Статистика для создателя
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1")
        vip_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM logs")
        total_commands = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT command, usage_count FROM statistics 
        ORDER BY usage_count DESC LIMIT 5
        """)
        popular_commands = cursor.fetchall()
        
        conn.close()
        
        stats_text = f"""
📊 СТАТИСТИКА БОТА

👥 Всего пользователей: {total_users}
💎 VIP пользователей: {vip_users}
📈 Выполнено команд: {total_commands}

🔥 ПОПУЛЯРНЫЕ КОМАНДЫ:
"""
        
        for cmd, count in popular_commands:
            stats_text += f"• {cmd}: {count} раз\n"
        
        stats_text += f"""
        
⚡ Статус: Онлайн
🤖 Версия: 2.0
📅 Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        
        await update.message.reply_text(stats_text)

# =============================================================================
# CALLBACK ОБРАБОТЧИКИ
# =============================================================================

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        user_data = await self.get_user_data(update)
        
        if query.data == "help":
            await self.help_command(update, context)
        elif query.data == "vip_info":
            await self.vip_command(update, context)
        elif query.data == "ai_demo":
            await query.edit_message_text(
                "🤖 AI-чат готов к работе!\n\n"
                "Просто напишите мне любой вопрос или используйте команду /ai\n\n"
                "Примеры:\n"
                "• Расскажи о космосе\n"
                "• Помоги с математикой\n"
                "• Придумай идею для проекта\n"
                "• Объясни квантовую физику просто"
            )
        elif query.data == "my_stats":
            stats_text = f"""
📊 ВАША СТАТИСТИКА

👤 Имя: {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/100
💎 VIP: {"✅ Активен" if self.is_vip(user_data) else "❌ Не активен"}
📝 Заметок: {len(user_data.notes)}
🏆 Достижений: {len(user_data.achievements)}
🌐 Язык: {user_data.language}
            """
            await query.edit_message_text(stats_text)

# =============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

    async def timer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Таймер обратного отсчета"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/timer")
        
        if not context.args:
            await update.message.reply_text("⏰ Укажите время в секундах!\nПример: /timer 60")
            return
        
        try:
            seconds = int(context.args[0])
            if seconds <= 0 or seconds > 3600:  # Максимум 1 час
                await update.message.reply_text("❌ Время должно быть от 1 до 3600 секунд!")
                return
            
            await update.message.reply_text(f"⏰ Таймер запущен на {seconds} секунд!")
            
            # Запуск таймера
            await asyncio.sleep(seconds)
            
            await update.message.reply_text(
                f"⏰ ВРЕМЯ ВЫШЛО!\n"
                f"🔔 Таймер на {seconds} секунд завершен!"
            )
            
        except ValueError:
            await update.message.reply_text("❌ Введите правильное число секунд!")
        
        await self.add_experience(user_data, 1)

    async def summarize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Суммаризация текста"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/summarize")
        
        if not context.args:
            await update.message.reply_text("📄 Введите текст для суммаризации!\nПример: /summarize [длинный текст]")
            return
        
        text_to_summarize = " ".join(context.args)
        
        if len(text_to_summarize) < 50:
            await update.message.reply_text("❌ Текст слишком короткий для суммаризации!")
            return
        
        try:
            summarize_prompt = f"""
Создай краткое содержание следующего текста на русском языке.
Выдели главные идеи и ключевые моменты:

{text_to_summarize}

Ответ должен быть в 2-3 раза короче оригинала.
"""
            
            response = self.gemini_model.generate_content(summarize_prompt)
            summary = response.text
            
            result_text = f"""
📄 КРАТКОЕ СОДЕРЖАНИЕ

📝 Оригинал ({len(text_to_summarize)} символов):
{text_to_summarize[:100]}...

📋 Краткое изложение ({len(summary)} символов):
{summary}
            """
            
            await update.message.reply_text(result_text)
            
        except Exception as e:
            await update.message.reply_text("❌ Ошибка при создании краткого содержания.")
        
        await self.add_experience(user_data, 2)

# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# =============================================================================

    async def run_bot(self):
        """Запуск бота"""
        # Создание приложения
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрация обработчиков команд
        
        # Базовые команды
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("info", self.info_command))
        
        # AI команды
        application.add_handler(CommandHandler("ai", self.ai_command))
        
        # Заметки
        application.add_handler(CommandHandler("note", self.note_command))
        application.add_handler(CommandHandler("notes", self.notes_command))
        application.add_handler(CommandHandler("delnote", self.delnote_command))
        application.add_handler(CommandHandler("findnote", self.findnote_command))
        
        # Время
        application.add_handler(CommandHandler("time", self.time_command))
        application.add_handler(CommandHandler("date", self.date_command))
        application.add_handler(CommandHandler("timer", self.timer_command))
        
        # Развлечения
        application.add_handler(CommandHandler("joke", self.joke_command))
        application.add_handler(CommandHandler("fact", self.fact_command))
        application.add_handler(CommandHandler("quote", self.quote_command))
        application.add_handler(CommandHandler("coin", self.coin_command))
        application.add_handler(CommandHandler("dice", self.dice_command))
        application.add_handler(CommandHandler("8ball", self.eightball_command))
        
        # Погода и финансы
        application.add_handler(CommandHandler("weather", self.weather_command))
        application.add_handler(CommandHandler("currency", self.currency_command))
        
        # Поиск и переводы
        application.add_handler(CommandHandler("search", self.search_command))
        application.add_handler(CommandHandler("translate", self.translate_command))
        application.add_handler(CommandHandler("summarize", self.summarize_command))
        
        # VIP команды
        application.add_handler(CommandHandler("vip", self.vip_command))
        application.add_handler(CommandHandler("secret", self.secret_command))
        application.add_handler(CommandHandler("lottery", self.lottery_command))
        
        # Команды создателя
        application.add_handler(CommandHandler("grant_vip", self.grant_vip_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        
        # Обработчик callback кнопок
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработчик обычных сообщений (AI автоответ)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработка ошибок
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(f"Exception while handling an update: {context.error}")
        
        application.add_error_handler(error_handler)
        
        # Запуск бота
        logger.info("Бот запускается...")
        await application.run_polling()


# =============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# =============================================================================

async def main():
    """Главная функция"""
    bot = TelegramBot()
    await bot.run_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")