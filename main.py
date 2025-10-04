#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ - Исправленная версия
Полнофункциональный бот с AI, VIP-системой и более чем 50 функциями
"""

import asyncio
import logging
import json
import random
import time
import datetime
import re
import requests
import aiohttp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import os
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from newsapi import NewsApiClient
import nest_asyncio
from flask import Flask
import pytz
from github import Github

nest_asyncio.apply()

# Telegram Bot API

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
Application, CommandHandler, MessageHandler,
filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ChatType
import telegram.error  # ВАЖНО: добавлен импорт для обработки ошибок

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
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# GitHub

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai-bot"
USERS_FILE = "users.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"

# ID создателя бота

CREATOR_ID = 7108255346
CREATOR_USERNAME = "Ernest_Kostevich"
DAD_USERNAME = "mkostevich"
BOT_USERNAME = "@AI_DISCO_BOT"

# Настройка Gemini

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL = os.getenv("MODEL", "gemini-2.5-flash")

# Maintenance mode flag

MAINTENANCE_MODE = False

# Backup path

BACKUP_PATH = "bot_backup.json"

# Render URL для пинга

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai-bot.onrender.com")

# =============================================================================

# КЛАССЫ ДАННЫХ

# =============================================================================

@dataclass
class UserData:
    user_id: int
    username: str
    first_name: str
    is_vip: bool = False
    vip_expires: Optional[str] = None
    language: str = "ru"
    notes: List[str] = field(default_factory=list)
    reminders: List[Dict] = field(default_factory=list)
    birthday: Optional[str] = None
    nickname: Optional[str] = None
    level: int = 1
    experience: int = 0
    achievements: List[str] = field(default_factory=list)
    memory_data: Dict = field(default_factory=dict)
    theme: str = "default"
    color: str = "blue"
    sound_notifications: bool = True
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            user_id=data['user_id'],
            username=data.get('username', ''),
            first_name=data.get('first_name', ''),
            is_vip=data.get('is_vip', False),
            vip_expires=data.get('vip_expires'),
            language=data.get('language', 'ru'),
            notes=data.get('notes', []),
            reminders=data.get('reminders', []),
            birthday=data.get('birthday'),
            nickname=data.get('nickname'),
            level=data.get('level', 1),
            experience=data.get('experience', 0),
            achievements=data.get('achievements', []),
            memory_data=data.get('memory_data', {}),
            theme=data.get('theme', 'default'),
            color=data.get('color', 'blue'),
            sound_notifications=data.get('sound_notifications', True),
            last_activity=data.get('last_activity', datetime.datetime.now().isoformat())
        )

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'is_vip': self.is_vip,
            'vip_expires': self.vip_expires,
            'language': self.language,
            'notes': self.notes,
            'reminders': self.reminders,
            'birthday': self.birthday,
            'nickname': self.nickname,
            'level': self.level,
            'experience': self.experience,
            'achievements': self.achievements,
            'memory_data': self.memory_data,
            'theme': self.theme,
            'color': self.color,
            'sound_notifications': self.sound_notifications,
            'last_activity': self.last_activity
        }

# =============================================================================

# БАЗА ДАННЫХ (GitHub Files)

# =============================================================================

class DatabaseManager:
    def __init__(self):
        self.g = None
        self.repo = None
        self.users = []
        self.logs = []
        self.statistics = {}

        if GITHUB_TOKEN:
            try:
                self.g = Github(GITHUB_TOKEN)
                self.repo = self.g.get_repo(GITHUB_REPO)
                logger.info("GitHub API инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации GitHub API: {e}")
        
        self.users = self.load_data(USERS_FILE, [])
        self.logs = self.load_data(LOGS_FILE, [])
        self.statistics = self.load_data(STATISTICS_FILE, {})

    def load_data(self, path, default):
        if not self.repo:
            logger.warning(f"GitHub не инициализирован, используются дефолтные данные для {path}")
            return default
            
        try:
            file = self.repo.get_contents(path)
            content = file.decoded_content.decode('utf-8')
            data = json.loads(content)
            
            if path == USERS_FILE and isinstance(data, dict) and not data:
                data = []
            elif path == STATISTICS_FILE and isinstance(data, list):
                data = {}
            elif path == LOGS_FILE and isinstance(data, dict) and not data:
                data = []
                
            logger.info(f"Успешно загружено из {path}")
            return data
        except Exception as e:
            logger.warning(f"Не удалось загрузить {path}: {e}")
            return default

    def save_data(self, path, data):
        if not self.repo:
            logger.warning(f"GitHub не инициализирован, данные не сохранены в {path}")
            return False
            
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            
            try:
                file = self.repo.get_contents(path)
                self.repo.update_file(path, f"Update {path}", content, file.sha)
            except:
                self.repo.create_file(path, f"Create {path}", content)
            
            logger.info(f"Успешно сохранено в {path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения в {path}: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[UserData]:
        for user_dict in self.users:
            if user_dict.get('user_id') == user_id:
                return UserData.from_dict(user_dict)
        return None

    def get_user_by_username(self, username: str) -> Optional[UserData]:
        username = username.lstrip('@').lower()
        for user_dict in self.users:
            stored_username = user_dict.get('username', '').lower()
            if stored_username == username:
                return UserData.from_dict(user_dict)
        return None

    def save_user(self, user_data: UserData):
        user_data.last_activity = datetime.datetime.now().isoformat()
        
        if not isinstance(self.users, list):
            self.users = []
        
        for i, user_dict in enumerate(self.users):
            if user_dict.get('user_id') == user_data.user_id:
                self.users[i] = user_data.to_dict()
                break
        else:
            self.users.append(user_data.to_dict())
        
        self.save_data(USERS_FILE, self.users)

    def log_command(self, user_id: int, command: str, message: str = ""):
        log_entry = {
            'user_id': user_id,
            'command': command,
            'message': message,
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        self.logs.append(log_entry)
        
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        
        if command in self.statistics:
            self.statistics[command]['usage_count'] += 1
            self.statistics[command]['last_used'] = datetime.datetime.now().isoformat()
        else:
            self.statistics[command] = {
                'usage_count': 1,
                'last_used': datetime.datetime.now().isoformat()
            }
        
        asyncio.create_task(self._save_logs_async())

    async def _save_logs_async(self):
        await asyncio.get_event_loop().run_in_executor(
            None, self.save_data, LOGS_FILE, self.logs
        )
        await asyncio.get_event_loop().run_in_executor(
            None, self.save_data, STATISTICS_FILE, self.statistics
        )

    def get_all_users(self) -> List[tuple]:
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('level', 1), u.get('last_activity', '')) for u in self.users]

    def get_vip_users(self) -> List[tuple]:
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('vip_expires')) for u in self.users if u.get('is_vip')]

    def get_popular_commands(self) -> List[tuple]:
        return sorted(self.statistics.items(), key=lambda x: x[1]['usage_count'], reverse=True)[:10]

    def get_growth_stats(self):
        return len(self.users)

# =============================================================================

# ОСНОВНОЙ КЛАСС БОТА

# =============================================================================

class TelegramBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.gemini_model = None
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("Gemini модель инициализирована")
            except Exception as e:
                logger.error(f"Ошибка инициализации Gemini: {e}")

        self.user_contexts = {}
        self.scheduler = AsyncIOScheduler()
        self.news_api = NewsApiClient(api_key=NEWSAPI_KEY) if NEWSAPI_KEY else None
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
            
            # Автоматический VIP для создателя
            if self.is_creator(user.id):
                user_data.is_vip = True
                user_data.vip_expires = None
                logger.info(f"Создатель получил автоматический VIP: {user.id}")
            
            self.db.save_user(user_data)
            logger.info(f"Создан новый пользователь: {user.id} ({user.first_name})")
        
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
            except Exception as e:
                logger.error(f"Ошибка проверки VIP срока: {e}")
                return False
        
        return True

    async def add_experience(self, user_data: UserData, points: int = 1):
        user_data.experience += points
        
        required_exp = user_data.level * 100
        if user_data.experience >= required_exp:
            user_data.level += 1
            user_data.experience = 0
            achievement = f"Достигнут {user_data.level} уровень!"
            if achievement not in user_data.achievements:
                user_data.achievements.append(achievement)
        
        self.db.save_user(user_data)

    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

    # ПОЗДРАВЛЕНИЕ ДЛЯ ПАПЫ 3 ОКТЯБРЯ
    async def send_dad_birthday_greeting(self, context: ContextTypes.DEFAULT_TYPE):
        """Отправка поздравления папе"""
        try:
            dad_user = self.db.get_user_by_username(DAD_USERNAME)
            if dad_user:
                greeting = """
🎉🎂 С ДНЁМ РОЖДЕНИЯ! 🎂🎉

Дорогой папа!

От всего сердца поздравляю тебя с Днём Рождения!
Желаю крепкого здоровья, счастья, успехов во всех начинаниях!

Пусть каждый день приносит радость и новые возможности!

С любовью, твой бот! ❤️
"""
                await context.bot.send_message(chat_id=dad_user.user_id, text=greeting)
                logger.info(f"Отправлено поздравление папе {dad_user.user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки поздравления папе: {e}")

    # =============================================================================
    # БАЗОВЫЕ КОМАНДЫ
    # =============================================================================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        if self.is_creator(user_data.user_id):
            message = f"""
🎯 Добро пожаловать, Создатель @{CREATOR_USERNAME}!

👑 Ваши привилегии:
• Полный доступ ко всем функциям
• Управление VIP пользователями
• Статистика и аналитика
• Рассылка сообщений
• Режим обслуживания

🤖 Используйте /help для списка команд
"""
        elif self.is_vip(user_data):
            nickname = user_data.nickname or user_data.first_name
            expires_text = 'бессрочно'
            if user_data.vip_expires:
                try:
                    expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                    expires_text = expires_date.strftime('%d.%m.%Y')
                except:
                    expires_text = 'неопределено'

            message = f"""
💎 Добро пожаловать, {nickname}!

⭐ VIP статус активен до: {expires_text}

VIP возможности:
• Напоминания и уведомления
• Расширенная статистика
• Приоритетная обработка
• Дополнительные команды

🤖 Используйте /help для списка команд
"""
        else:
            message = f"""
🤖 Привет, {user_data.first_name}!

Я AI-бот с 50+ функциями!

🌟 Основные возможности:
• 💬 AI-чат (Gemini 2.0)
• 📝 Заметки и память
• 🌤️ Погода
• 💰 Курсы валют
• 🎮 Игры
• 🌐 Переводы

💎 Хотите VIP? Свяжитесь с @{CREATOR_USERNAME}
🤖 Используйте /help для списка команд
"""

        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🤖 AI", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/help")
        
        help_text = """
📋 СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы
/ping - Проверка соединения

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос AI
Или просто напишите сообщение!

📝 ЗАМЕТКИ:
/note [текст] - Сохранить заметку
/notes - Показать заметки
/delnote [номер] - Удалить заметку
/findnote [текст] - Поиск в заметках
/clearnotes - Очистить все

⏰ ВРЕМЯ И ДАТА:
/time - Текущее время
/date - Текущая дата

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Шутка
/fact - Интересный факт
/quote - Цитата
/coin - Бросить монетку
/dice - Бросить кубик
/8ball [вопрос] - Магический шар

🌤️ УТИЛИТЫ:
/weather [город] - Погода
/currency [из] [в] - Конвертер валют
/translate [язык] [текст] - Перевод

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist - Список
/memorydel [ключ]

📊 ПРОФИЛЬ:
/rank - Ваш уровень
/profile - Полный профиль
"""

        if self.is_vip(user_data):
            help_text += """
💎 VIP КОМАНДЫ:
/vip - Информация о VIP
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/delreminder [номер] - Удалить напоминание
/nickname [имя] - Установить никнейм
/theme [название] - Изменить тему
"""

        if self.is_creator(user_data.user_id):
            help_text += """
👑 КОМАНДЫ СОЗДАТЕЛЯ:
/grant_vip [user_id/@username] [duration]
/revoke_vip [user_id/@username]
/broadcast [текст] - Рассылка
/users - Список пользователей
/vipusers - Список VIP
/stats - Полная статистика
/maintenance [on/off] - Режим обслуживания
/backup - Резервная копия
/cleanup - Очистка неактивных
"""

        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info_text = f"""
🤖 О БОТЕ

Версия: 2.1 (исправленная)
Создатель: @{CREATOR_USERNAME}
Бот: {BOT_USERNAME}

Возможности: 50+ команд
AI: {"Gemini 2.0 ✅" if self.gemini_model else "Недоступен ❌"}
База данных: {"GitHub ✅" if self.db.repo else "Локальная"}
Хостинг: Render

Бот работает 24/7 с автопингом и автоматическими поздравлениями
"""
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        total_users = self.db.get_growth_stats()
        total_commands = len(self.db.logs)
        
        status_text = f"""
⚡ СТАТУС БОТА

Статус: ✅ Онлайн
Версия: 2.1
Пользователей: {total_users}
Команд выполнено: {total_commands}

Компоненты:
• Gemini AI: {"✅" if self.gemini_model else "❌"}
• GitHub DB: {"✅" if self.db.repo else "❌"}
• Планировщик: {"✅" if self.scheduler.running else "❌"}
• Maintenance: {"Вкл" if self.maintenance_mode else "Выкл"}

Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        await update.message.reply_text(status_text)
        await self.add_experience(user_data, 1)

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ping")
        
        start_time = time.time()
        sent_msg = await update.message.reply_text("🏓 Pong!")
        end_time = time.time()
        
        latency = round((end_time - start_time) * 1000, 2)
        await sent_msg.edit_text(f"🏓 Pong! Задержка: {latency}ms")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # AI КОМАНДЫ
    # =============================================================================

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос после /ai!\nПример: /ai Что такое Python?")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен. Gemini API не настроен.")
            return
        
        query = " ".join(context.args)
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            response = self.gemini_model.generate_content(query)
            await update.message.reply_text(response.text)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")
            logger.error(f"Ошибка Gemini: {e}")
        
        await self.add_experience(user_data, 2)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Бот на обслуживании. Попробуйте позже.")
            return
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "message")
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI-чат недоступен. Используйте /ai [вопрос]")
            return
        
        message = update.message.text
        user_id = user_data.user_id
        
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        
        self.user_contexts[user_id].append(f"Пользователь: {message}")
        if len(self.user_contexts[user_id]) > 10:
            self.user_contexts[user_id] = self.user_contexts[user_id][-10:]
        
        context_str = "\n".join(self.user_contexts[user_id][-5:])
        prompt = f"""
Ты полезный AI-ассистент в Telegram боте.
Контекст диалога:
{context_str}

Ответь на последнее сообщение дружелюбно и полезно на русском языке.
"""

        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(response.text)
            
            self.user_contexts[user_id].append(f"Бот: {response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки сообщения")
            logger.error(f"Ошибка обработки сообщения: {e}")
        
        await self.add_experience(user_data, 1)

    # =============================================================================
    # КОМАНДЫ ЗАМЕТОК И ПАМЯТИ
    # =============================================================================

    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/note")
        
        if not context.args:
            await update.message.reply_text("📝 Укажите текст заметки!\nПример: /note Купить молоко")
            return
        
        note = " ".join(context.args)
        user_data.notes.append(note)
        self.db.save_user(user_data)
        await update.message.reply_text(f"✅ Заметка сохранена! (Всего: {len(user_data.notes)})")
        await self.add_experience(user_data, 1)

    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок!")
            return
        
        notes_text = "\n".join(f"{i+1}. {note}" for i, note in enumerate(user_data.notes))
        await update.message.reply_text(f"📝 Ваши заметки:\n{notes_text}")
        await self.add_experience(user_data, 1)

    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер заметки!\nПример: /delnote 1")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            deleted_note = user_data.notes.pop(index)
            self.db.save_user(user_data)
            await update.message.reply_text(f"✅ Заметка удалена: {deleted_note[:50]}...")
        else:
            await update.message.reply_text("❌ Неверный номер заметки!")
        
        await self.add_experience(user_data, 1)

    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            await update.message.reply_text("🔍 Укажите текст для поиска!\nПример: /findnote работа")
            return
        
        keyword = " ".join(context.args).lower()
        found = [(i+1, note) for i, note in enumerate(user_data.notes) if keyword in note.lower()]
        
        if found:
            notes_text = "\n".join(f"{i}. {note}" for i, note in found)
            await update.message.reply_text(f"🔍 Найдено заметок ({len(found)}):\n{notes_text}")
        else:
            await update.message.reply_text("❌ Ничего не найдено!")
        
        await self.add_experience(user_data, 1)

    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clearnotes")
        
        notes_count = len(user_data.notes)
        user_data.notes = []
        self.db.save_user(user_data)
        await update.message.reply_text(f"✅ Очищено {notes_count} заметок!")
        await self.add_experience(user_data, 1)

    async def memorysave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorysave")
        
        if len(context.args) < 2:
            await update.message.reply_text("🧠 /memorysave [ключ] [значение]\nПример: /memorysave любимый_цвет синий")
            return
        
        key = context.args[0]
        value = " ".join(context.args[1:])
        user_data.memory_data[key] = value
        self.db.save_user(user_data)
        await update.message.reply_text(f"🧠 Сохранено: {key} = {value}")
        await self.add_experience(user_data, 1)

    async def memoryget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memoryget")
        
        if not context.args:
            await update.message.reply_text("🧠 /memoryget [ключ]\nПример: /memoryget любимый_цвет")
            return
        
        key = context.args[0]
        value = user_data.memory_data.get(key)
        
        if value:
            await update.message.reply_text(f"🧠 {key}: {value}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
        
        await self.add_experience(user_data, 1)

    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorylist")
        
        if not user_data.memory_data:
            await update.message.reply_text("🧠 Память пуста!")
            return
        
        memory_text = "\n".join(f"• {key}: {value}" for key, value in user_data.memory_data.items())
        await update.message.reply_text(f"🧠 Ваша память:\n{memory_text}")
        await self.add_experience(user_data, 1)

    async def memorydel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorydel")
        
        if not context.args:
            await update.message.reply_text("🧠 /memorydel [ключ]\nПример: /memorydel любимый_цвет")
            return
        
        key = context.args[0]
        if key in user_data.memory_data:
            del user_data.memory_data[key]
            self.db.save_user(user_data)
            await update.message.reply_text(f"🧠 Удалено: {key}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
        
        await self.add_experience(user_data, 1)

    # =============================================================================
    # РАЗВЛЕЧЕНИЯ
    # =============================================================================

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")
        
        if not self.gemini_model:
            jokes = [
                "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
                "Заходит программист в бар, а там нет мест...",
                "- Доктор, я думаю, что я — компьютерный вирус!\n- Не волнуйтесь, примите эту таблетку.\n- А что это?\n- Антивирус!",
                "Как программисты считают овец? 0 овец, 1 овца, 2 овцы, 3 овцы...",
                "Программист - это человек, который решает проблему, о которой вы не знали, способом, который вы не понимаете."
            ]
            await update.message.reply_text(random.choice(jokes))
        else:
            try:
                response = self.gemini_model.generate_content("Расскажи короткую смешную шутку на русском языке про программистов или технологии")
                await update.message.reply_text(f"😄 {response.text}")
            except:
                await update.message.reply_text("😄 К сожалению, не могу придумать шутку прямо сейчас!")
        
        await self.add_experience(user_data, 1)

    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")
        
        if not self.gemini_model:
            facts = [
                "🧠 Человеческий мозг содержит около 86 миллиардов нейронов!",
                "🌊 В океане больше исторических артефактов, чем во всех музеях мира!",
                "🐙 У осьминогов три сердца и голубая кровь!",
                "🌍 За секунду Земля проходит около 30 километров по орбите!",
                "💡 Первый компьютерный баг был настоящей бабочкой, застрявшей в компьютере!"
            ]
            await update.message.reply_text(random.choice(facts))
        else:
            try:
                response = self.gemini_model.generate_content("Расскажи один интересный научный или технологический факт на русском языке")
                await update.message.reply_text(f"🧠 {response.text}")
            except:
                await update.message.reply_text("🧠 Python был назван в честь британской комедийной группы Monty Python!")
        
        await self.add_experience(user_data, 1)

    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")
        
        if not self.gemini_model:
            quotes = [
                "💫 'Будь собой. Остальные роли уже заняты.' - Оскар Уайльд",
                "🚀 'Единственный способ сделать великую работу - любить то, что делаешь.' - Стив Джобс",
                "⭐ 'Успех - это способность идти от неудачи к неудаче, не теряя энтузиазма.' - Черчилль",
                "💻 'Программирование - это искусство говорить человеку, что сказать компьютеру.' - Дональд Кнут"
            ]
            await update.message.reply_text(random.choice(quotes))
        else:
            try:
                response = self.gemini_model.generate_content("Дай вдохновляющую цитату на русском языке с указанием автора")
                await update.message.reply_text(f"💫 {response.text}")
            except:
                await update.message.reply_text("💫 'Лучший способ предсказать будущее - создать его.' - Питер Друкер")
        
        await self.add_experience(user_data, 1)

    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/coin")
        
        result = random.choice(["🪙 Орёл!", "🪙 Решка!"])
        await update.message.reply_text(result)
        await self.add_experience(user_data, 1)

    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/dice")
        
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
        await self.add_experience(user_data, 1)

    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 Задайте вопрос магическому шару!\nПример: /8ball Стоит ли мне изучать Python?")
            return
        
        answers = [
            "✅ Да, определённо!",
            "❌ Нет, не стоит",
            "🤔 Возможно",
            "⏳ Спроси позже",
            "🎯 Без сомнений!",
            "💭 Весьма вероятно",
            "🚫 Мой ответ - нет",
            "🌟 Знаки говорят да"
        ]
        
        result = random.choice(answers)
        await update.message.reply_text(f"🔮 {result}")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # УТИЛИТЫ
    # =============================================================================

    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")
        
        now = datetime.datetime.now()
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = now.astimezone(moscow_tz)
        
        time_text = f"""
⏰ ВРЕМЯ

🌍 UTC: {now.strftime('%H:%M:%S %d.%m.%Y')}
🇷🇺 Москва: {moscow_time.strftime('%H:%M:%S %d.%m.%Y')}
"""
        await update.message.reply_text(time_text)
        await self.add_experience(user_data, 1)

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")
        
        now = datetime.datetime.now()
        await update.message.reply_text(f"📅 Сегодня: {now.strftime('%d.%m.%Y')}")
        await self.add_experience(user_data, 1)

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        if not context.args:
            await update.message.reply_text("🌤️ Укажите город!\nПример: /weather Москва")
            return
            
        if not OPENWEATHER_API_KEY:
            await update.message.reply_text("❌ Функция погоды недоступна - не настроен API ключ.")
            return
        
        city = " ".join(context.args)
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            response = requests.get(url, timeout=10).json()
            
            if response.get("cod") == 200:
                weather = response["weather"][0]["description"]
                temp = round(response["main"]["temp"])
                feels_like = round(response["main"]["feels_like"])
                humidity = response["main"]["humidity"]
                
                weather_text = f"""
🌤️ Погода в {city}:
🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)
☁️ Описание: {weather.capitalize()}
💧 Влажность: {humidity}%
"""
                await update.message.reply_text(weather_text)
            else:
                await update.message.reply_text("❌ Город не найден! Проверьте название.")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка получения погоды.")
            logger.error(f"Ошибка weather API: {e}")
        
        await self.add_experience(user_data, 2)

    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/currency")
        
        if len(context.args) < 2:
            await update.message.reply_text("💰 Укажите валюты!\nПример: /currency USD RUB")
            return
            
        if not CURRENCY_API_KEY:
            await update.message.reply_text("❌ Функция конвертации недоступна.")
            return
        
        from_cur, to_cur = context.args[0].upper(), context.args[1].upper()
        
        try:
            url = f"https://api.freecurrencyapi.com/v1/latest?apikey={CURRENCY_API_KEY}&currencies={to_cur}&base_currency={from_cur}"
            response = requests.get(url, timeout=10).json()
            rate = response.get("data", {}).get(to_cur)
            
            if rate:
                await update.message.reply_text(f"💰 1 {from_cur} = {rate:.4f} {to_cur}")
            else:
                await update.message.reply_text("❌ Не удалось получить курс!")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка конвертации.")
            logger.error(f"Ошибка currency API: {e}")
        
        await self.add_experience(user_data, 2)

    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text("🌐 /translate [язык] [текст]\nПример: /translate en Привет мир")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ Функция перевода недоступна.")
            return
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            prompt = f"Переведи следующий текст на {target_lang}: {text}"
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(f"🌐 Перевод:\n{response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка перевода.")
            logger.error(f"Ошибка перевода: {e}")
        
        await self.add_experience(user_data, 2)

    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")
        
        required_exp = user_data.level * 100
        progress = (user_data.experience / required_exp) * 100 if required_exp > 0 else 0
        
        rank_text = f"""
🏅 ВАШ УРОВЕНЬ

👤 Пользователь: {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{required_exp}
📊 Прогресс: {progress:.1f}%

💎 VIP: {"✅ Активен" if self.is_vip(user_data) else "❌ Неактивен"}
"""
        await update.message.reply_text(rank_text)
        await self.add_experience(user_data, 1)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/profile")
        
        vip_status = "✅ Активен" if self.is_vip(user_data) else "❌ Неактивен"
        vip_expires = "Бессрочно" if not user_data.vip_expires else user_data.vip_expires[:10]
        
        profile_text = f"""
👤 ПРОФИЛЬ

Имя: {user_data.first_name}
Username: @{user_data.username if user_data.username else 'не установлен'}
Никнейм: {user_data.nickname if user_data.nickname else 'не установлен'}

🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{user_data.level * 100}
💎 VIP: {vip_status}
📅 VIP до: {vip_expires}

📝 Заметок: {len(user_data.notes)}
🧠 Записей в памяти: {len(user_data.memory_data)}
⏰ Напоминаний: {len(user_data.reminders)}
🏆 Достижений: {len(user_data.achievements)}

🌐 Язык: {user_data.language}
🎨 Тема: {user_data.theme}
"""
        await update.message.reply_text(profile_text)
        await self.add_experience(user_data, 1)

    # =============================================================================
    # VIP КОМАНДЫ
    # =============================================================================

    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if not self.is_vip(user_data):
            await update.message.reply_text(f"💎 Вы не VIP!\n\nДля получения VIP свяжитесь с @{CREATOR_USERNAME}")
            return
        
        expires_text = 'бессрочно'
        if user_data.vip_expires:
            try:
                expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                expires_text = expires_date.strftime('%d.%m.%Y')
            except:
                expires_text = 'неопределено'
        
        vip_text = f"""
💎 VIP СТАТУС

✅ VIP активен до: {expires_text}

Ваши VIP привилегии:
• ⏰ Напоминания
• 📊 Расширенная статистика
• 🎨 Персонализация
• 🔔 Приоритетная обработка
• 🎁 Дополнительные команды
"""
        await update.message.reply_text(vip_text)
        await self.add_experience(user_data, 1)

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/remind")
        
        if len(context.args) < 2:
            await update.message.reply_text("⏰ /remind [минуты] [текст]\nПример: /remind 30 Позвонить маме")
            return
        
        try:
            minutes = int(context.args[0])
            text = " ".join(context.args[1:])
            
            if minutes <= 0:
                await update.message.reply_text("❌ Время должно быть больше 0!")
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            job = self.scheduler.add_job(
                self.send_notification,
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, f"🔔 Напоминание: {text}"],
                id=f"reminder_{user_data.user_id}_{int(time.time())}"
            )
            
            reminder_data = {
                "id": job.id,
                "text": text,
                "time": run_date.isoformat(),
                "minutes": minutes
            }
            user_data.reminders.append(reminder_data)
            self.db.save_user(user_data)
            
            await update.message.reply_text(f"⏰ Напоминание установлено на {minutes} минут!")
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат времени!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            logger.error(f"Ошибка создания напоминания: {e}")
        
        await self.add_experience(user_data, 2)

    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/reminders")
        
        if not user_data.reminders:
            await update.message.reply_text("❌ Нет активных напоминаний!")
            return
        
        reminders_text = "\n".join([
            f"{i+1}. {rem['text']} ({rem.get('time', '').split('T')[0] if rem.get('time') else 'неизвестно'})" 
            for i, rem in enumerate(user_data.reminders)
        ])
        
        await update.message.reply_text(f"⏰ Ваши напоминания:\n{reminders_text}")
        await self.add_experience(user_data, 1)

    async def delreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/delreminder")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер напоминания!\nПример: /delreminder 1")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.reminders):
            reminder = user_data.reminders.pop(index)
            try:
                self.scheduler.remove_job(reminder.get('id'))
            except:
                pass
            self.db.save_user(user_data)
            await update.message.reply_text(f"✅ Напоминание удалено: {reminder['text']}")
        else:
            await update.message.reply_text("❌ Неверный номер!")
        
        await self.add_experience(user_data, 1)

    async def nickname_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/nickname")
        
        if not context.args:
            await update.message.reply_text("📛 /nickname [новое имя]\nПример: /nickname SuperBot")
            return
        
        new_nickname = " ".join(context.args)
        user_data.nickname = new_nickname
        self.db.save_user(user_data)
        await update.message.reply_text(f"📛 Никнейм изменён на '{new_nickname}'!")
        await self.add_experience(user_data, 1)

    async def theme_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/theme")
        
        if not context.args:
            await update.message.reply_text("🎨 /theme [название]\nДоступные: default, dark, light")
            return
        
        new_theme = " ".join(context.args).lower()
        if new_theme in ["default", "dark", "light"]:
            user_data.theme = new_theme
            self.db.save_user(user_data)
            await update.message.reply_text(f"🎨 Тема изменена на '{new_theme}'!")
        else:
            await update.message.reply_text("❌ Неверная тема! Доступные: default, dark, light")
        
        await self.add_experience(user_data, 1)

    # =============================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # =============================================================================

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/grant_vip")
        
        if len(context.args) < 2:
            await update.message.reply_text("/grant_vip [user_id/@username] [duration]\nDuration: day, week, month, year, forever")
            return
        
        target_identifier = context.args[0]
        duration_str = context.args[1].lower()
        
        target_user = self.db.get_user(int(target_identifier)) if target_identifier.isdigit() else self.db.get_user_by_username(target_identifier)
        
        if not target_user:
            await update.message.reply_text("❌ Пользователь не найден!")
            return
        
        durations = {
            'day': datetime.timedelta(days=1),
            'week': datetime.timedelta(weeks=1),
            'month': datetime.timedelta(days=30),
            'year': datetime.timedelta(days=365),
            'forever': None
        }
        
        if duration_str not in durations:
            await update.message.reply_text("❌ Неверная длительность!")
            return
        
        target_user.is_vip = True
        if durations[duration_str]:
            target_user.vip_expires = (datetime.datetime.now() + durations[duration_str]).isoformat()
        else:
            target_user.vip_expires = None
        
        self.db.save_user(target_user)
        
        await update.message.reply_text(f"💎 VIP выдан пользователю {target_user.first_name} ({target_user.user_id}) на {duration_str}")
        try:
            await context.bot.send_message(target_user.user_id, "🎉 Вы получили VIP статус!")
        except:
            pass
        
        await self.add_experience(user_data, 5)

    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/revoke_vip")
        
        if not context.args:
            await update.message.reply_text("/revoke_vip [user_id/@username]")
            return
        
        target_identifier = context.args[0]
        target_user = self.db.get_user(int(target_identifier)) if target_identifier.isdigit() else self.db.get_user_by_username(target_identifier)
        
        if not target_user:
            await update.message.reply_text("❌ Пользователь не найден!")
            return
        
        target_user.is_vip = False
        target_user.vip_expires = None
        self.db.save_user(target_user)
        
        await update.message.reply_text(f"💎 VIP отозван у пользователя {target_user.first_name} ({target_user.user_id})")
        try:
            await context.bot.send_message(target_user.user_id, "❌ Ваш VIP статус отозван.")
        except:
            pass
        
        await self.add_experience(user_data, 5)

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/broadcast")
        
        if not context.args:
            await update.message.reply_text("/broadcast [текст]")
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        
        sent = 0
        failed = 0
        for user_id, _, _, _ in users:
            try:
                await context.bot.send_message(user_id, f"📢 Сообщение от админа:\n{message}")
                sent += 1
            except:
                failed += 1
        
        await update.message.reply_text(f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")
        await self.add_experience(user_data, 10)

    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/users")
        
        users = self.db.get_all_users()
        users_text = "\n".join(f"{user_id} - {name} (уровень {level}) - {last_activity[:10]}" for user_id, name, level, last_activity in sorted(users, key=lambda x: datetime.datetime.fromisoformat(x[3]), reverse=True))
        
        await update.message.reply_text(f"👥 Пользователи ({len(users)}):\n{users_text}")
        await self.add_experience(user_data, 1)

    async def vipusers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/vipusers")
        
        vips = self.db.get_vip_users()
        vips_text = "\n".join(f"{user_id} - {name} (до {expires[:10] if expires else 'бессрочно'})" for user_id, name, expires in vips)
        
        await update.message.reply_text(f"💎 VIP пользователи ({len(vips)}):\n{vips_text}")
        await self.add_experience(user_data, 1)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/stats")
        
        total_users = self.db.get_growth_stats()
        vip_users = len(self.db.get_vip_users())
        popular_commands = self.db.get_popular_commands()
        
        stats_text = f"""
📊 СТАТИСТИКА

👥 Пользователей: {total_users}
💎 VIP: {vip_users}

📈 Популярные команды:
{"\n".join(f"{cmd}: {data['usage_count']} (последний: {data['last_used'][:10]})" for cmd, data in popular_commands)}
"""
        await update.message.reply_text(stats_text)
        await self.add_experience(user_data, 1)

    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/maintenance")
        
        if not context.args:
            await update.message.reply_text("/maintenance [on/off]")
            return
        
        mode = context.args[0].lower()
        if mode == 'on':
            self.maintenance_mode = True
            await update.message.reply_text("🛠 Режим обслуживания включён!")
        elif mode == 'off':
            self.maintenance_mode = False
            await update.message.reply_text("✅ Режим обслуживания выключён!")
        else:
            await update.message.reply_text("❌ Неверный параметр!")
        
        await self.add_experience(user_data, 5)

    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/backup")
        
        try:
            backup_data = {
                'users': [u.to_dict() for u in (self.db.get_user(uid) for uid in [u[0] for u in self.db.get_all_users()])],
                'logs': self.db.logs,
                'statistics': self.db.statistics,
                'timestamp': datetime.datetime.now().isoformat()
            }
            with open(BACKUP_PATH, 'w') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            await update.message.reply_document(document=open(BACKUP_PATH, 'rb'), caption="📦 Резервная копия создана!")
            os.remove(BACKUP_PATH)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка создания бэкапа: {str(e)}")
            logger.error(f"Ошибка бэкапа: {e}")
        
        await self.add_experience(user_data, 5)

    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(user_data.user_id, "/cleanup")
        
        inactive_threshold = datetime.datetime.now() - datetime.timedelta(days=90)
        removed_users = []
        
        for uid, name, level, last_activity in self.db.get_all_users():
            if datetime.datetime.fromisoformat(last_activity) < inactive_threshold:
                removed_users.append((uid, name))
                # Note: We don't have a delete_user method, so we'd need to implement removal from self.users list
                # For now, assume we remove by filtering
        if removed_users:
            # Implement actual removal
            self.users = [u for u in self.users if datetime.datetime.fromisoformat(u['last_activity']) >= inactive_threshold]
            self.save_data(USERS_FILE, self.users)
            removed_text = "\n".join(f"{uid} - {name}" for uid, name in removed_users)
            await update.message.reply_text(f"🧹 Удалено {len(removed_users)} неактивных пользователей:\n{removed_text}")
        else:
            await update.message.reply_text("✅ Нет неактивных пользователей для удаления!")
        
        await self.add_experience(user_data, 5)

    # =============================================================================
    # CALLBACK HANDLER
    # =============================================================================

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        
        await query.answer()
        
        if data == "help":
            await self.help_command(update, context)
        
        elif data == "vip_info":
            await self.vip_command(update, context)
        
        elif data == "ai_demo":
            await query.message.reply_text("🤖 Привет! Задать вопрос AI? Используйте /ai [вопрос]")
        
        elif data == "my_stats":
            await self.rank_command(update, context)

    # =============================================================================
    # MAIN
    # =============================================================================

def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Базовые команды
    application.add_handler(CommandHandler("start", TelegramBot().start_command))
    application.add_handler(CommandHandler("help", TelegramBot().help_command))
    application.add_handler(CommandHandler("info", TelegramBot().info_command))
    application.add_handler(CommandHandler("status", TelegramBot().status_command))
    application.add_handler(CommandHandler("ping", TelegramBot().ping_command))

    # AI команды
    application.add_handler(CommandHandler("ai", TelegramBot().ai_command))
    
    # Заметки и память
    application.add_handler(CommandHandler("note", TelegramBot().note_command))
    application.add_handler(CommandHandler("notes", TelegramBot().notes_command))
    application.add_handler(CommandHandler("delnote", TelegramBot().delnote_command))
    application.add_handler(CommandHandler("findnote", TelegramBot().findnote_command))
    application.add_handler(CommandHandler("clearnotes", TelegramBot().clearnotes_command))
    application.add_handler(CommandHandler("memorysave", TelegramBot().memorysave_command))
    application.add_handler(CommandHandler("memoryget", TelegramBot().memoryget_command))
    application.add_handler(CommandHandler("memorylist", TelegramBot().memorylist_command))
    application.add_handler(CommandHandler("memorydel", TelegramBot().memorydel_command))

    # Развлечения
    application.add_handler(CommandHandler("joke", TelegramBot().joke_command))
    application.add_handler(CommandHandler("fact", TelegramBot().fact_command))
    application.add_handler(CommandHandler("quote", TelegramBot().quote_command))
    application.add_handler(CommandHandler("coin", TelegramBot().coin_command))
    application.add_handler(CommandHandler("dice", TelegramBot().dice_command))
    application.add_handler(CommandHandler("8ball", TelegramBot().eightball_command))

    # Утилиты
    application.add_handler(CommandHandler("time", TelegramBot().time_command))
    application.add_handler(CommandHandler("date", TelegramBot().date_command))
    application.add_handler(CommandHandler("weather", TelegramBot().weather_command))
    application.add_handler(CommandHandler("currency", TelegramBot().currency_command))
    application.add_handler(CommandHandler("translate", TelegramBot().translate_command))

    # Профиль
    application.add_handler(CommandHandler("rank", TelegramBot().rank_command))
    application.add_handler(CommandHandler("profile", TelegramBot().profile_command))

    # VIP команды
    application.add_handler(CommandHandler("vip", TelegramBot().vip_command))
    application.add_handler(CommandHandler("remind", TelegramBot().remind_command))
    application.add_handler(CommandHandler("reminders", TelegramBot().reminders_command))
    application.add_handler(CommandHandler("delreminder", TelegramBot().delreminder_command))
    application.add_handler(CommandHandler("nickname", TelegramBot().nickname_command))
    application.add_handler(CommandHandler("theme", TelegramBot().theme_command))

    # Админ команды
    application.add_handler(CommandHandler("grant_vip", TelegramBot().grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", TelegramBot().revoke_vip_command))
    application.add_handler(CommandHandler("broadcast", TelegramBot().broadcast_command))
    application.add_handler(CommandHandler("users", TelegramBot().users_command))
    application.add_handler(CommandHandler("vipusers", TelegramBot().vipusers_command))
    application.add_handler(CommandHandler("stats", TelegramBot().stats_command))
    application.add_handler(CommandHandler("maintenance", TelegramBot().maintenance_command))
    application.add_handler(CommandHandler("backup", TelegramBot().backup_command))
    application.add_handler(CommandHandler("cleanup", TelegramBot().cleanup_command))

    # Обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, TelegramBot().handle_message))
    
    # Callback
    application.add_handler(CallbackQueryHandler(TelegramBot().handle_callback))

    # Планировщик
    bot_instance = TelegramBot()
    bot_instance.scheduler.start()
    
    # Ежедневное поздравление папе 3 октября
    bot_instance.scheduler.add_job(
        bot_instance.send_dad_birthday_greeting,
        trigger=CronTrigger(month=10, day=3, hour=0, minute=0, timezone='Europe/Moscow')
    )
    
    # Keep-alive пинг каждые 10 минут
    def keep_alive():
        try:
            requests.get(RENDER_URL, timeout=5)
            logger.info("Keep-alive ping sent")
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")
    
    bot_instance.scheduler.add_job(keep_alive, IntervalTrigger(minutes=10))

    # Запуск Flask для health checks
    flask_app = Flask(__name__)

    @flask_app.route('/health')
    def health():
        return 'OK', 200

    flask_thread = Thread(target=flask_app.run, kwargs={'host': '0.0.0.0', 'port': int(os.environ.get('PORT', 5000))})
    flask_thread.start()

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
