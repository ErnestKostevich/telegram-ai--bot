@@ -1,8 +1,8 @@
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM AI BOT v2.1 - Полная версия
Создатель: Ernest (@Ernest_Kostevich)
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ - Главный файл
Полнофункциональный бот с AI, VIP-системой и более чем 150 функциями
"""

import asyncio
@@ -11,13 +11,17 @@
import random
import time
import datetime
import re
import requests
from typing import Dict, List, Optional
import aiohttp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import os
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from newsapi import NewsApiClient
import nest_asyncio
from flask import Flask
import pytz
@@ -32,7 +36,8 @@
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.error import NetworkError, TimedOut, Conflict
from telegram.constants import ChatType
from telegram.error import Conflict, TimedOut, NetworkError

# Google Gemini
import google.generativeai as genai
@@ -45,29 +50,44 @@
logger = logging.getLogger(__name__)

# =============================================================================
# КОНФИГУРАЦИЯ
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
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"

# Создатель и папа
# ID создателя бота
CREATOR_ID = 7108255346
DAD_USERNAME = "mkostevich"  # Без @
CREATOR_USERNAME = "@Ernest_Kostevich"
DAD_USERNAME = "@mkostevich"
DAD_BIRTHDAY = "2025-10-03"  # Дата для поздравления папы
BOT_USERNAME = "@AI_DISCO_BOT"

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = "gemini-2.0-flash-exp"

MODEL = os.getenv("MODEL", "gemini-2.0-flash-exp")

# Maintenance mode flag
MAINTENANCE_MODE = False

# Backup path
BACKUP_PATH = "bot_backup.json"

# Render URL для пинга
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

# =============================================================================
@@ -85,10 +105,14 @@ class UserData:
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
@@ -103,10 +127,14 @@ def from_dict(cls, data: Dict):
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

@@ -121,15 +149,19 @@ def to_dict(self):
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
# БАЗА ДАННЫХ
# БАЗА ДАННЫХ (GitHub Files)
# =============================================================================

class DatabaseManager:
@@ -144,62 +176,69 @@ def __init__(self):
            try:
                self.g = Github(GITHUB_TOKEN)
                self.repo = self.g.get_repo(GITHUB_REPO)
                logger.info("✅ GitHub API подключен")
                logger.info("GitHub API инициализирован")
            except Exception as e:
                logger.error(f"❌ GitHub API ошибка: {e}")
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
            data = json.loads(file.decoded_content.decode('utf-8'))
            content = file.decoded_content.decode('utf-8')
            data = json.loads(content)

            # Исправление типов
            if path == USERS_FILE and isinstance(data, dict):
            if path == USERS_FILE and isinstance(data, dict) and not data:
                data = []
            elif path == STATISTICS_FILE and isinstance(data, list):
                data = {}
            elif path == LOGS_FILE and isinstance(data, dict):
            elif path == LOGS_FILE and isinstance(data, dict) and not data:
                data = []
            
            logger.info(f"✅ Загружено: {path}")
                
            logger.info(f"Успешно загружено {len(data) if isinstance(data, (list, dict)) else 'данные'} из {path}")
            return data
        except Exception as e:
            logger.warning(f"⚠️ {path}: {e}")
            logger.warning(f"Не удалось загрузить {path}: {e}. Используются дефолтные данные.")
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
            logger.error(f"❌ Ошибка сохранения {path}: {e}")
            logger.error(f"Ошибка сохранения в {path}: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[UserData]:
        for u in self.users:
            if u.get('user_id') == user_id:
                return UserData.from_dict(u)
        for user_dict in self.users:
            if user_dict.get('user_id') == user_id:
                return UserData.from_dict(user_dict)
        return None

    def get_user_by_username(self, username: str) -> Optional[UserData]:
        # Убираем @ если есть
        username = username.lstrip('@')
        for u in self.users:
            if u.get('username', '').lower() == username.lower():
                return UserData.from_dict(u)
        username_clean = username.lstrip('@').lower()
        for user_dict in self.users:
            user_username = user_dict.get('username', '').lower()
            if user_username == username_clean:
                return UserData.from_dict(user_dict)
        return None

    def save_user(self, user_data: UserData):
@@ -208,8 +247,8 @@ def save_user(self, user_data: UserData):
        if not isinstance(self.users, list):
            self.users = []

        for i, u in enumerate(self.users):
            if u.get('user_id') == user_data.user_id:
        for i, user_dict in enumerate(self.users):
            if user_dict.get('user_id') == user_data.user_id:
                self.users[i] = user_data.to_dict()
                break
        else:
@@ -224,27 +263,42 @@ def log_command(self, user_id: int, command: str, message: str = ""):
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
            self.statistics[command] = {'usage_count': 1, 'last_used': datetime.datetime.now().isoformat()}
            self.statistics[command] = {
                'usage_count': 1,
                'last_used': datetime.datetime.now().isoformat()
            }

        asyncio.create_task(self._save_logs_async())

    async def _save_logs_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, LOGS_FILE, self.logs)
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, STATISTICS_FILE, self.statistics)
        await asyncio.get_event_loop().run_in_executor(
            None, self.save_data, LOGS_FILE, self.logs
        )
        await asyncio.get_event_loop().run_in_executor(
            None, self.save_data, STATISTICS_FILE, self.statistics
        )
    
    def get_all_users(self) -> List[tuple]:
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('level', 1), u.get('last_activity', '')) for u in self.users]

    def get_all_users(self):
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('level', 1)) for u in self.users]
    def get_vip_users(self) -> List[tuple]:
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('vip_expires')) for u in self.users if u.get('is_vip')]

    def get_popular_commands(self):
    def get_popular_commands(self) -> List[tuple]:
        return sorted(self.statistics.items(), key=lambda x: x[1]['usage_count'], reverse=True)[:10]
    
    def get_growth_stats(self):
        return len(self.users)

# =============================================================================
# ОСНОВНОЙ КЛАСС БОТА
@@ -257,12 +311,13 @@ def __init__(self):
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("✅ Gemini подключен")
                logger.info("Gemini модель инициализирована")
            except Exception as e:
                logger.error(f"❌ Gemini: {e}")
                logger.error(f"Ошибка инициализации Gemini: {e}")

        self.user_contexts = {}
        self.scheduler = AsyncIOScheduler()
        self.news_api = NewsApiClient(api_key=NEWSAPI_KEY) if NEWSAPI_KEY else None
        self.maintenance_mode = False

    async def get_user_data(self, update: Update) -> UserData:
@@ -276,12 +331,14 @@ async def get_user_data(self, update: Update) -> UserData:
                first_name=user.first_name or ""
            )

            if user.id == CREATOR_ID:
            # Автоматический VIP для создателя
            if self.is_creator(user.id):
                user_data.is_vip = True
                user_data.vip_expires = None
                logger.info(f"Создатель получил автоматический VIP: {user.id}")

            self.db.save_user(user_data)
            logger.info(f"✅ Новый пользователь: {user.id}")
            logger.info(f"Создан новый пользователь: {user.id} ({user.first_name})")

        return user_data

@@ -291,116 +348,126 @@ def is_creator(self, user_id: int) -> bool:
    def is_vip(self, user_data: UserData) -> bool:
        if not user_data.is_vip:
            return False
        
        if user_data.vip_expires:
            try:
                expires = datetime.datetime.fromisoformat(user_data.vip_expires)
                if datetime.datetime.now() > expires:
                expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                if datetime.datetime.now() > expires_date:
                    user_data.is_vip = False
                    user_data.vip_expires = None
                    self.db.save_user(user_data)
                    return False
            except:
            except Exception as e:
                logger.error(f"Ошибка проверки VIP срока: {e}")
                return False
        
        return True

    async def add_experience(self, user_data: UserData, points: int = 1):
        user_data.experience += points
        required = user_data.level * 100
        if user_data.experience >= required:
        
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
            logger.error(f"Ошибка уведомления {user_id}: {e}")
    
    # Поздравление папы
    async def dad_birthday_congratulation(self, context: ContextTypes.DEFAULT_TYPE):
        """Поздравление папы 3 октября"""
        dad_user = self.db.get_user_by_username(DAD_USERNAME)
        if dad_user:
            message = """
🎉🎂 ПОЗДРАВЛЯЮ С ДНЁМ РОЖДЕНИЯ! 🎂🎉

Дорогой папа!

От всей души поздравляю тебя с днём рождения! 
Желаю крепкого здоровья, счастья, успехов во всем!

Пусть каждый день приносит радость и новые возможности!

С любовью, твой сын Ernest ❤️

P.S. Это автоматическое поздравление от моего AI-бота! 🤖
            """
            try:
                await context.bot.send_message(chat_id=dad_user.user_id, text=message)
                logger.info(f"✅ Отправлено поздравление папе")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки поздравления: {e}")
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

    async def check_birthdays(self, context: ContextTypes.DEFAULT_TYPE):
        """Проверка дней рождения"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if today == DAD_BIRTHDAY:
            dad_user = self.db.get_user_by_username("mkostevich")
            if dad_user:
                try:
                    await context.bot.send_message(
                        dad_user.user_id,
                        "🎉🎂 С Днём Рождения, папа! 🎂🎉\n\n"
                        "Желаю здоровья, счастья и исполнения всех желаний!\n"
                        "Пусть этот год принесёт много радости и успехов!\n\n"
                        "С любовью, твой сын Ernest ❤️"
                    )
                    logger.info("Отправлено поздравление папе!")
                except Exception as e:
                    logger.error(f"Ошибка отправки поздравления: {e}")

    # =============================================================================
    # БАЗОВЫЕ КОМАНДЫ
    
    # =============================================================================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")

        if self.is_creator(user_data.user_id):
            message = """
🎯 Добро пожаловать, Создатель!
Вы имеете полный доступ ко всем функциям бота.

👑 Команды создателя:
👑 Доступные команды создателя:
• /grant_vip - Выдать VIP
• /revoke_vip - Отозвать VIP
• /stats - Статистика
• /stats - Полная статистика
• /broadcast - Рассылка
• /users - Пользователи
• /maintenance - Обслуживание
• /users - Список пользователей
• /maintenance - Режим обслуживания
• /backup - Резервная копия

🤖 /help - Все команды
🤖 Используйте /help для полного списка команд.
            """
        elif self.is_vip(user_data):
            nickname = user_data.nickname or user_data.first_name
            expires_text = 'бессрочно'
            if user_data.vip_expires:
                try:
                    expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                    expires_text = expires_date.strftime('%d.%m.%Y')
                except:
                    pass
                    expires_text = 'неопределено'

            message = f"""
💎 VIP до: {expires_text}
💎 Добро пожаловать, {nickname}!
У вас VIP статус до {expires_text}.

⭐ VIP команды:
⭐ VIP возможности:
• /remind - Напоминания
• /profile - Профиль
• /vipstats - VIP статистика
• /reminders - Список напоминаний
• /nickname - Установить никнейм
• /profile - Ваш профиль

🤖 /help - Все команды
🤖 Используйте /help для полного списка команд.
            """
        else:
            message = f"""
🤖 Привет, {user_data.first_name}!

🌟 Функции:
• 💬 AI-чат (просто пиши)
• 📝 Заметки (/note)
• 🧠 Память (/memorysave)
• 🌤️ Погода (/weather)
• 💰 Валюты (/currency)
• 🎮 Игры (/quiz, /coin)

💎 Хочешь VIP? Свяжись с создателем!
🤖 /help - Все команды
Я многофункциональный AI-бот с более чем 50 возможностями!

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
            [InlineKeyboardButton("🤖 AI", callback_data="ai_demo"),
            [InlineKeyboardButton("🤖 AI чат", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
@@ -413,97 +480,164 @@ async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE)
        self.db.log_command(user_data.user_id, "/help")

        help_text = """
📋 КОМАНДЫ

🏠 Базовые:
/start /help /info /status /rank

💬 AI:
/ai [вопрос] - или просто пиши!

📝 Заметки:
/note [текст] - создать
/notes - показать
/delnote [№] - удалить
/clearnotes - очистить

🧠 Память:
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist
/memorydel [ключ]

⏰ Время:
/time /date

🎮 Игры:
/joke /fact /quote /quiz
/coin /dice /8ball [вопрос]

🔢 Математика:
/math [выражение]
/calculate [выражение]

🛠️ Утилиты:
/password [длина]
/qr [текст]
/shorturl [ссылка]
/weather [город]
/currency [из] [в]
/translate [язык] [текст]
📋 ПОЛНЫЙ СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы
/uptime - Время работы

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос AI
Или просто напишите сообщение боту!

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
/rank - Ваш уровень
        """

        if self.is_vip(user_data):
            help_text += """
💎 VIP:
/vip /remind [мин] [текст]
/reminders /profile
💎 VIP КОМАНДЫ:
/vip - VIP информация
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/delreminder [номер] - Удалить напоминание
/nickname [имя] - Установить никнейм
/profile - Ваш профиль
            """

        if self.is_creator(user_data.user_id):
            help_text += """
👑 Создатель:
/grant_vip [id/@username] [duration]
/revoke_vip [id/@username]
/broadcast [текст]
/users /stats /maintenance [on/off]
/backup
👑 КОМАНДЫ СОЗДАТЕЛЯ:
/grant_vip [user_id/@username] [duration] - Выдать VIP
/revoke_vip [user_id/@username] - Отозвать VIP
/broadcast [текст] - Рассылка всем
/users - Список пользователей
/stats - Статистика бота
/maintenance [on/off] - Режим обслуживания
/backup - Создать резервную копию
            """

        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info_text = f"""
🤖 О БОТЕ

Версия: 2.0
Создатель: Ernest (@Ernest_Kostevich)
Функций: 50+
AI: {"Gemini 2.0" if self.gemini_model else "Недоступен"}
База данных: {"GitHub" if self.db.repo else "Локальная"}
Хостинг: Render

Бот работает 24/7 с автопингом.
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

Онлайн: ✅
Версия: 2.0
Пользователей: {total_users}
Команд выполнено: {total_commands}
Gemini: {"✅" if self.gemini_model else "❌"}
GitHub: {"✅" if self.db.repo else "❌"}
Maintenance: {"Вкл" if self.maintenance_mode else "Выкл"}
        """
        await update.message.reply_text(status_text)
        await self.add_experience(user_data, 1)

    # Продолжение в следующем сообщении из-за ограничения размера...
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")

        if not context.args:
            await update.message.reply_text("🤖 /ai [вопрос]")
            await update.message.reply_text("🤖 Задайте вопрос после /ai!")
            return

        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            await update.message.reply_text("❌ AI недоступен. Gemini API не настроен.")
            return

        query = " ".join(context.args)
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            response = self.gemini_model.generate_content(query)
            await update.message.reply_text(response.text)
            await self.add_experience(user_data, 2)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")
            logger.error(f"Ошибка Gemini: {e}")
        
        await self.add_experience(user_data, 2)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Обслуживание. Попробуй позже.")
            await update.message.reply_text("🛠 Бот на обслуживании. Попробуйте позже.")
            return

        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "message")

        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен. Используй команды!")
            await update.message.reply_text("❌ AI-чат недоступен. Gemini API не настроен.")
            return

        message = update.message.text
@@ -512,49 +646,59 @@ async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYP
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []

        self.user_contexts[user_id].append(f"User: {message}")
        self.user_contexts[user_id].append(f"Пользователь: {message}")
        if len(self.user_contexts[user_id]) > 10:
            self.user_contexts[user_id] = self.user_contexts[user_id][-10:]

        context_str = "\n".join(self.user_contexts[user_id][-5:])
        prompt = f"Ты AI-ассистент. Контекст:\n{context_str}\n\nОтветь кратко и полезно."
        prompt = f"""
Ты полезный AI-ассистент в Telegram боте. 
Контекст диалога:
{context_str}

Ответь на последнее сообщение пользователя дружелюбно и полезно.
"""

        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(response.text)
            self.user_contexts[user_id].append(f"Bot: {response.text}")
            await self.add_experience(user_data, 1)
            
            self.user_contexts[user_id].append(f"Бот: {response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Message error: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения.")
            logger.error(f"Ошибка обработки сообщения: {e}")
        
        await self.add_experience(user_data, 1)

    # Добавьте остальные методы команд аналогично...
    # (note, memorysave, weather, currency, translate, grant_vip, revoke_vip, и т.д.)

    # КОМАНДЫ СОЗДАТЕЛЯ
    
    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            await update.message.reply_text("❌ Доступно только создателю!")
            return

        if len(context.args) < 2:
            await update.message.reply_text("💎 /grant_vip [id/@username] [week/month/year/permanent]")
            await update.message.reply_text("💎 /grant_vip [user_id или @username] [week/month/year/permanent]")
            return

        try:
            target = context.args[0]
            duration = context.args[1].lower()

            # Поддержка ID и username
            if target.startswith('@') or not target.isdigit():
                target_user = self.db.get_user_by_username(target)
            if target.startswith('@'):
                username = target[1:]
                target_user = self.db.get_user_by_username(username)
                if not target_user:
                    await update.message.reply_text(f"❌ Пользователь {target} не найден!")
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
                    return
            else:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
                if not target_user:
                    await update.message.reply_text("❌ ID не найден!")
                    await update.message.reply_text("❌ Пользователь с таким ID не найден!")
                    return

            target_user.is_vip = True
@@ -568,129 +712,83 @@ async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_
            elif duration == "permanent":
                target_user.vip_expires = None
            else:
                await update.message.reply_text("❌ week/month/year/permanent")
                await update.message.reply_text("❌ Неверная длительность! Используйте: week/month/year/permanent")
                return

            self.db.save_user(target_user)
            await update.message.reply_text(f"✅ VIP выдан: {target_user.first_name} ({duration})")
            await update.message.reply_text(f"✅ VIP выдан пользователю {target_user.first_name} (ID: {target_user.user_id})")

            try:
                await context.bot.send_message(
                    target_user.user_id, 
                    f"🎉 Вы получили VIP!\nДлительность: {duration}"
                    target_user.user_id,
                    f"🎉 Поздравляем! Вы получили VIP статус!\nДлительность: {duration}"
                )
            except:
                pass
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя! Используйте число или @username")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            await update.message.reply_text("❌ Доступно только создателю!")
            return

        if not context.args:
            await update.message.reply_text("💎 /revoke_vip [id/@username]")
            await update.message.reply_text("💎 /revoke_vip [user_id или @username]")
            return

        try:
            target = context.args[0]

            if target.startswith('@') or not target.isdigit():
                target_user = self.db.get_user_by_username(target)
            if target.startswith('@'):
                username = target[1:]
                target_user = self.db.get_user_by_username(username)
                if not target_user:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
                    return
            else:
                target_user = self.db.get_user(int(target))
            
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
                target_id = int(target)
                target_user = self.db.get_user(target_id)
                if not target_user:
                    await update.message.reply_text("❌ Пользователь с таким ID не найден!")
                    return

            if not target_user.is_vip:
                await update.message.reply_text("❌ Пользователь не VIP!")
                await update.message.reply_text(f"❌ Пользователь {target_user.first_name} не является VIP!")
                return

            target_user.is_vip = False
            target_user.vip_expires = None
            self.db.save_user(target_user)

            await update.message.reply_text(f"✅ VIP отозван у {target_user.first_name}")
            await update.message.reply_text(f"✅ VIP статус отозван у {target_user.first_name} (ID: {target_user.user_id})")

            try:
                await context.bot.send_message(target_user.user_id, "💎 VIP отозван")
                await context.bot.send_message(
                    target_user.user_id,
                    "💎 Ваш VIP статус был отозван администратором."
                )
            except:
                pass
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("📢 /broadcast [сообщение]")
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        sent = failed = 0
        
        await update.message.reply_text(f"📢 Рассылка для {len(users)} пользователей...")
        
        for user_id, _, _ in users:
            try:
                await context.bot.send_message(user_id, f"📢 От создателя:\n\n{message}")
                sent += 1
                await asyncio.sleep(0.1)
            except:
                failed += 1
        
        await update.message.reply_text(f"✅ Отправлено: {sent}\n❌ Неудачно: {failed}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if self.is_creator(user_data.user_id):
            total = len(self.db.users)
            vip = len([u for u in self.db.users if u.get('is_vip')])
            cmds = len(self.db.logs)
            top = self.db.get_popular_commands()[:5]
            
            stats_text = f"""
📊 СТАТИСТИКА БОТА

👥 Пользователей: {total}
💎 VIP: {vip}
📈 Команд: {cmds}

🔥 ТОП-5:
"""
            for cmd, data in top:
                stats_text += f"• {cmd}: {data['usage_count']}\n"
            
            stats_text += f"\n⚡ Онлайн\n📅 {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
        else:
            stats_text = f"""
📊 СТАТИСТИКА

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{user_data.level * 100}
💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}
📝 Заметок: {len(user_data.notes)}
🧠 Памяти: {len(user_data.memory_data)}
            """
        
        self.db.log_command(user_data.user_id, "/stats")
        await update.message.reply_text(stats_text)

    # ЗАМЕТКИ
    # Остальные команды (добавляю ключевые)

    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/note")
        
        if not context.args:
            await update.message.reply_text("📝 /note [текст]")
            await update.message.reply_text("📝 Укажите текст заметки!")
            return
        
        note = " ".join(context.args)
        user_data.notes.append(note)
        self.db.save_user(user_data)
@@ -699,427 +797,755 @@ async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE)

    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок!")
            return
        
        notes_text = "\n".join(f"{i+1}. {note}" for i, note in enumerate(user_data.notes))
        await update.message.reply_text(f"📝 Заметки:\n{notes_text}")
        await update.message.reply_text(f"📝 Ваши заметки:\n{notes_text}")
        await self.add_experience(user_data, 1)

    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ /delnote [номер]")
            await update.message.reply_text("❌ Укажите номер заметки!\nПример: /delnote 1")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            deleted = user_data.notes.pop(index)
            self.db.save_user(user_data)
            await update.message.reply_text(f"✅ Удалена: {deleted[:50]}...")
            await update.message.reply_text(f"✅ Заметка удалена: {deleted[:50]}...")
        else:
            await update.message.reply_text("❌ Неверный номер заметки!")
        
        await self.add_experience(user_data, 1)

    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            await update.message.reply_text("🔍 Укажите ключевое слово!\nПример: /findnote работа")
            return
        
        keyword = " ".join(context.args).lower()
        found = [(i+1, note) for i, note in enumerate(user_data.notes) if keyword in note.lower()]
        
        if found:
            notes_text = "\n".join(f"{i}. {note}" for i, note in found)
            await update.message.reply_text(f"🔍 Найдено ({len(found)}):\n{notes_text}")
        else:
            await update.message.reply_text("❌ Неверный номер!")
            await update.message.reply_text("❌ Ничего не найдено!")
        
        await self.add_experience(user_data, 1)

    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clearnotes")
        
        count = len(user_data.notes)
        user_data.notes = []
        self.db.save_user(user_data)
        await update.message.reply_text(f"✅ Очищено {count} заметок!")
        await self.add_experience(user_data, 1)

    # ПАМЯТЬ
    
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
        await update.message.reply_text(f"🧠 Сохранено: {key} = {value}")
        await self.add_experience(user_data, 1)

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
        
        await self.add_experience(user_data, 1)

    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorylist")
        
        if not user_data.memory_data:
            await update.message.reply_text("🧠 Память пуста!")
            return
        memory_text = "\n".join(f"• {k}: {v}" for k, v in user_data.memory_data.items())
        await update.message.reply_text(f"🧠 Память:\n{memory_text}")
        
        memory_text = "\n".join(f"• {key}: {value}" for key, value in user_data.memory_data.items())
        await update.message.reply_text(f"🧠 Ваша память:\n{memory_text}")
        await self.add_experience(user_data, 1)

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
        
        await self.add_experience(user_data, 1)

    # УТИЛИТЫ И ИГРЫ
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        if not context.args:
            await update.message.reply_text("🌤️ /weather [город]")
            await update.message.reply_text("🌤️ Укажите город!\nПример: /weather Москва")
            return
            
        if not OPENWEATHER_API_KEY:
            await update.message.reply_text("❌ API ключ не настроен")
            await update.message.reply_text("❌ Погода недоступна - не настроен API ключ.")
            return
        
        city = " ".join(context.args)
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            response = requests.get(url, timeout=10).json()
            
            if response.get("cod") == 200:
                weather = response["weather"][0]["description"]
                temp = round(response["main"]["temp"])
                feels = round(response["main"]["feels_like"])
                feels_like = round(response["main"]["feels_like"])
                humidity = response["main"]["humidity"]
                text = f"🌤️ Погода в {city}:\n🌡️ {temp}°C (ощущается {feels}°C)\n☁️ {weather.capitalize()}\n💧 Влажность: {humidity}%"
                await update.message.reply_text(text)
                
                weather_text = f"""
🌤️ Погода в {city}:
🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)
☁️ Описание: {weather.capitalize()}
💧 Влажность: {humidity}%
                """
                await update.message.reply_text(weather_text)
            else:
                await update.message.reply_text("❌ Город не найден!")
        except:
            await update.message.reply_text("❌ Ошибка API")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка получения погоды.")
            logger.error(f"Ошибка weather: {e}")
        
        await self.add_experience(user_data, 2)

    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/currency")
        
        if len(context.args) < 2:
            await update.message.reply_text("💰 /currency [из] [в]\nПример: /currency USD RUB")
            return
            
        if not CURRENCY_API_KEY:
            await update.message.reply_text("❌ API ключ не настроен")
            await update.message.reply_text("❌ Конвертация недоступна.")
            return
        
        from_cur, to_cur = context.args[0].upper(), context.args[1].upper()
        
        try:
            url = f"https://api.freecurrencyapi.com/v1/latest?apikey={CURRENCY_API_KEY}&currencies={to_cur}&base_currency={from_cur}"
            response = requests.get(url, timeout=10).json()
            rate = response.get("data", {}).get(to_cur)
            
            if rate:
                await update.message.reply_text(f"💰 1 {from_cur} = {rate:.4f} {to_cur}")
            else:
                await update.message.reply_text("❌ Ошибка получения курса")
        except:
            await update.message.reply_text("❌ Ошибка API")
                await update.message.reply_text("❌ Не удалось получить курс!")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка конвертации.")
            logger.error(f"Ошибка currency: {e}")
        
        await self.add_experience(user_data, 2)

    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text("🌐 /translate [язык] [текст]")
            await update.message.reply_text("🌐 /translate [язык] [текст]\nПример: /translate en Привет")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            await update.message.reply_text("❌ Перевод недоступен.")
            return
        target = context.args[0]
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            response = self.gemini_model.generate_content(f"Переведи на {target}: {text}")
            await update.message.reply_text(f"🌐 {response.text}")
        except:
            await update.message.reply_text("❌ Ошибка перевода")
            prompt = f"Переведи следующий текст на {target_lang}: {text}"
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(f"🌐 Перевод:\n{response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка перевода.")
            logger.error(f"Ошибка translate: {e}")
        
        await self.add_experience(user_data, 2)

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content("Расскажи короткую шутку на русском")
                await update.message.reply_text(f"😄 {response.text}")
            except:
                await update.message.reply_text("😄 Почему программисты путают Halloween и Christmas? Потому что Oct 31 == Dec 25!")
        else:
            jokes = [
                "Почему программисты путают Halloween и Christmas? Oct 31 == Dec 25!",
                "Заходит программист в бар, а там нет мест...",
                "- Я компьютерный вирус!\n- Примите антивирус!"
            ]
            await update.message.reply_text(f"😄 {random.choice(jokes)}")
        self.db.log_command(user_data.user_id, "/joke")
        
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
            "Заходит программист в бар, а там нет мест...",
            "- Доктор, я думаю, что я компьютерный вирус!\n- Не волнуйтесь, примите эту таблетку.\n- А что это?\n- Антивирус!"
        ]
        await update.message.reply_text(f"😄 {random.choice(jokes)}")
        await self.add_experience(user_data, 1)

    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content("Расскажи научный факт на русском")
                await update.message.reply_text(f"🧠 {response.text}")
            except:
                await update.message.reply_text("🧠 Человеческий мозг содержит ~86 млрд нейронов!")
        else:
            facts = [
                "🧠 Мозг содержит ~86 млрд нейронов!",
                "🌊 В океане больше артефактов, чем в музеях!",
                "🐙 У осьминогов 3 сердца!",
                "🌍 Земля проходит 30 км/сек по орбите!"
            ]
            await update.message.reply_text(random.choice(facts))
        self.db.log_command(user_data.user_id, "/fact")
        
        facts = [
            "🧠 Человеческий мозг содержит около 86 миллиардов нейронов!",
            "🌊 В океане больше исторических артефактов, чем во всех музеях мира!",
            "🐙 У осьминогов три сердца и голубая кровь!"
        ]
        await update.message.reply_text(random.choice(facts))
        await self.add_experience(user_data, 1)

    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content("Вдохновляющая цитата на русском с автором")
                await update.message.reply_text(f"💫 {response.text}")
            except:
                await update.message.reply_text("💫 'Будь собой. Остальные роли заняты.' - Оскар Уайльд")
        else:
            quotes = [
                "'Будь собой. Остальные роли заняты.' - Уайльд",
                "'Любить дело - путь к успеху.' - Джобс",
                "'Успех - идти без потери энтузиазма.' - Черчилль"
            ]
            await update.message.reply_text(f"💫 {random.choice(quotes)}")
        self.db.log_command(user_data.user_id, "/quote")
        
        quotes = [
            "💫 'Будь собой. Остальные роли уже заняты.' - Оскар Уайльд",
            "🚀 'Единственный способ сделать великую работу - любить то, что делаешь.' - Стив Джобс"
        ]
        await update.message.reply_text(random.choice(quotes))
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
        faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {faces[result-1]} Выпало: {result}")
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
        await self.add_experience(user_data, 1)

    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 /8ball [вопрос]")
            await update.message.reply_text("🔮 Задайте вопрос!\nПример: /8ball Стоит ли мне изучать Python?")
            return
        answers = ["✅ Да!", "❌ Нет", "🤔 Возможно", "⏳ Позже", "🎯 Точно!", "💭 Вероятно", "🚫 Нет", "🌟 Да"]
        
        answers = ["✅ Да!", "❌ Нет", "🤔 Возможно", "⏳ Спроси позже"]
        await update.message.reply_text(f"🔮 {random.choice(answers)}")
        await self.add_experience(user_data, 1)

    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quiz")
        
        questions = [
            {"q": "Дней в високосном году?", "a": "366"},
            {"q": "Сколько дней в високосном году?", "a": "366"},
            {"q": "Столица Австралии?", "a": "Канберра"},
            {"q": "Самый большой океан?", "a": "Тихий"}
        ]
        q = random.choice(questions)
        await update.message.reply_text(f"❓ {q['q']}\n\n💡 Ответ через 30 сек...")
        
        async def send_answer():
            await asyncio.sleep(30)
            await context.bot.send_message(update.effective_chat.id, f"✅ Ответ: {q['a']}")

        asyncio.create_task(send_answer())
        await self.add_experience(user_data, 2)
        question = random.choice(questions)
        await update.message.reply_text(f"❓ {question['q']}\n\n💡 Напишите ответ!")
        await self.add_experience(user_data, 1)

    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/math")
        
        if not context.args:
            await update.message.reply_text("🔢 /math [выражение]")
            await update.message.reply_text("🔢 Введите выражение!\nПример: /math 15 + 25")
            return
        expr = " ".join(context.args)
        
        expression = " ".join(context.args)
        try:
            allowed = set('0123456789+-*/().,= ')
            if not all(c in allowed for c in expr):
                await update.message.reply_text("❌ Только: +, -, *, /, ()")
            allowed_chars = set('0123456789+-*/()., ')
            if not all(c in allowed_chars for c in expression):
                await update.message.reply_text("❌ Разрешены только: +, -, *, /, ()")
                return
            result = eval(expr)
            await update.message.reply_text(f"🔢 {expr} = {result}")
        except:
            await update.message.reply_text("❌ Ошибка вычисления")
            
            result = eval(expression)
            await update.message.reply_text(f"🔢 {expression} = {result}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка вычисления")
        
        await self.add_experience(user_data, 1)

    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/calculate")
        
        if not context.args:
            await update.message.reply_text("🧮 /calculate [выражение]\nПример: /calculate sqrt(16)")
            return
        
        expression = " ".join(context.args)
        
        try:
            import math
            safe_dict = {
                "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                "log": math.log, "pi": math.pi, "e": math.e
            }
            
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            await update.message.reply_text(f"🧮 {expression} = {result}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка вычисления")
        
        await self.add_experience(user_data, 1)

    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/password")
        
        length = 12
        if context.args and context.args[0].isdigit():
            length = min(int(context.args[0]), 50)
        
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        pwd = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(f"🔐 Пароль ({length}):\n`{pwd}`\n\n⚠️ Сохрани!", parse_mode='Markdown')
        password = ''.join(random.choice(chars) for _ in range(length))
        
        await update.message.reply_text(f"🔐 Пароль ({length} символов):\n`{password}`", parse_mode='Markdown')
        await self.add_experience(user_data, 1)

    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/qr")
        
        if not context.args:
            await update.message.reply_text("📱 /qr [текст]")
            await update.message.reply_text("📱 /qr [текст]\nПример: /qr https://google.com")
            return
        
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}"
        await update.message.reply_text(f"📱 QR: {text}")
        
        await update.message.reply_text(f"📱 QR-код:")
        await context.bot.send_photo(update.effective_chat.id, qr_url)
        await self.add_experience(user_data, 1)

    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def shorturl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        now = datetime.datetime.now()
        msk = pytz.timezone('Europe/Moscow')
        msk_time = now.astimezone(msk)
        await update.message.reply_text(f"⏰ UTC: {now.strftime('%H:%M:%S')}\n🇷🇺 МСК: {msk_time.strftime('%H:%M:%S')}")
        self.db.log_command(user_data.user_id, "/shorturl")
        
        if not context.args:
            await update.message.reply_text("🔗 /shorturl [URL]\nПример: /shorturl https://very-long-url.com")
            return
        
        url = context.args[0]
        if not url.startswith('http'):
            url = 'https://' + url
        
        try:
            response = requests.get(f"https://is.gd/create.php?format=simple&url={url}", timeout=10)
            if response.status_code == 200:
                await update.message.reply_text(f"🔗 Сокращённый URL:\n{response.text.strip()}")
            else:
                await update.message.reply_text("❌ Ошибка сокращения")
        except:
            await update.message.reply_text("❌ Ошибка подключения")
        
        await self.add_experience(user_data, 1)

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        await update.message.reply_text(f"📅 {datetime.datetime.now().strftime('%d.%m.%Y')}")
        self.db.log_command(user_data.user_id, "/uptime")
        
        await update.message.reply_text(f"⏱️ Бот работает!\n👥 Пользователей: {len(self.db.users)}\n📊 Команд: {len(self.db.logs)}")
        await self.add_experience(user_data, 1)

    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def ip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        required = user_data.level * 100
        progress = (user_data.experience / required) * 100
        text = f"🏅 {user_data.first_name}\n🆙 Уровень: {user_data.level}\n⭐ Опыт: {user_data.experience}/{required}\n📊 {progress:.1f}%\n💎 VIP: {'✅' if self.is_vip(user_data) else '❌'}"
        await update.message.reply_text(text)
        self.db.log_command(user_data.user_id, "/ip")
        
        try:
            response = requests.get('https://httpbin.org/ip', timeout=5)
            ip = response.json().get('origin', 'Неизвестно')
            await update.message.reply_text(f"🌍 Ваш IP: {ip}")
        except:
            await update.message.reply_text("❌ Не удалось получить IP")
        
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")
        
        now = datetime.datetime.now()
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = now.astimezone(moscow_tz)
        
        await update.message.reply_text(f"⏰ Москва: {moscow_time.strftime('%H:%M:%S %d.%m.%Y')}")
        await self.add_experience(user_data, 1)

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        info = f"🤖 BOT v2.1\nСоздатель: Ernest\nФункций: 50+\nAI: {'✅' if self.gemini_model else '❌'}\nGitHub: {'✅' if self.db.repo else '❌'}\nHosting: Render"
        await update.message.reply_text(info)
        self.db.log_command(user_data.user_id, "/date")
        
        now = datetime.datetime.now()
        await update.message.reply_text(f"📅 Сегодня: {now.strftime('%d.%m.%Y')}")
        await self.add_experience(user_data, 1)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        status = f"⚡ СТАТУС\n\n✅ Онлайн\n👥 Пользователей: {len(self.db.users)}\n📈 Команд: {len(self.db.logs)}\n🤖 Gemini: {'✅' if self.gemini_model else '❌'}"
        await update.message.reply_text(status)
        self.db.log_command(user_data.user_id, "/rank")
        
        required_exp = user_data.level * 100
        progress = (user_data.experience / required_exp) * 100
        
        rank_text = f"""
🏅 ВАШ УРОВЕНЬ

👤 Пользователь: {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{required_exp}
📊 Прогресс: {progress:.1f}%

💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}
        """
        
        await update.message.reply_text(rank_text)
        await self.add_experience(user_data, 1)

    # VIP КОМАНДЫ
    # VIP команды

    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Ты не VIP! Свяжись с @Ernest_Kostevich")
            await update.message.reply_text("💎 Вы не VIP! Свяжитесь с @Ernest_Kostevich")
            return
        expires = 'бессрочно'
        
        expires_text = 'бессрочно'
        if user_data.vip_expires:
            try:
                expires = datetime.datetime.fromisoformat(user_data.vip_expires).strftime('%d.%m.%Y')
                expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                expires_text = expires_date.strftime('%d.%m.%Y')
            except:
                pass
        await update.message.reply_text(f"💎 VIP до: {expires}")
        
        await update.message.reply_text(f"💎 VIP активен до: {expires_text}")
        await self.add_experience(user_data, 1)

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
                await update.message.reply_text("❌ Время должно быть больше 0!")
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            job = self.scheduler.add_job(
                self.send_notification,
                DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, f"🔔 {text}"],
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, f"🔔 Напоминание: {text}"],
                id=f"reminder_{user_data.user_id}_{int(time.time())}"
            )
            reminder_data = {"id": job.id, "text": text, "time": run_date.isoformat()}
            
            reminder_data = {
                "id": job.id,
                "text": text,
                "time": run_date.isoformat(),
                "minutes": minutes
            }
            user_data.reminders.append(reminder_data)
            self.db.save_user(user_data)
            await update.message.reply_text(f"⏰ Напоминание на {minutes} мин!")
            
            await update.message.reply_text(f"⏰ Напоминание установлено на {minutes} минут!")
            
        except ValueError:
            await update.message.reply_text("❌ Используй числа!")
            await update.message.reply_text("❌ Неверный формат!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        
        await self.add_experience(user_data, 2)

    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/reminders")
        
        if not user_data.reminders:
            await update.message.reply_text("❌ Нет напоминаний!")
            return
        text = "\n".join([f"{i+1}. {r['text']}" for i, r in enumerate(user_data.reminders)])
        await update.message.reply_text(f"⏰ Напоминания:\n{text}")
        
        reminders_text = "\n".join([
            f"{i+1}. {rem['text']} ({rem.get('time', 'неизвестно')})" 
            for i, rem in enumerate(user_data.reminders)
        ])
        
        await update.message.reply_text(f"⏰ Напоминания:\n{reminders_text}")
        await self.add_experience(user_data, 1)

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
        await update.message.reply_text(f"✅ Никнейм установлен: {nickname}")
        await self.add_experience(user_data, 1)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/profile")
        
        profile_text = f"""
👤 ПРОФИЛЬ

Имя: {user_data.first_name}
Никнейм: {user_data.nickname or "Не установлен"}
Уровень: {user_data.level}
VIP: {"✅" if self.is_vip(user_data) else "❌"}
Заметок: {len(user_data.notes)}
Памяти: {len(user_data.memory_data)}
Достижений: {len(user_data.achievements)}
        """
        
        await update.message.reply_text(profile_text)
        await self.add_experience(user_data, 1)

    # Команды создателя
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        users = self.db.get_all_users()
        if not users:
            await update.message.reply_text("👥 Пользователей пока нет!")
            return
            
        users_text = "👥 ПОЛЬЗОВАТЕЛИ:\n\n"
        for user_id, first_name, level, last_activity in users[:20]:
            vip_status = "💎" if any(u.get('user_id') == user_id and u.get('is_vip') for u in self.db.users) else "👤"
            users_text += f"{vip_status} {first_name} (ID: {user_id}) - Ур.{level}\n"
        
        if len(users) > 20:
            users_text += f"\n... и ещё {len(users) - 20}"
            
        await update.message.reply_text(users_text)

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("📢 /broadcast [сообщение]")
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        sent = 0
        failed = 0
        
        await update.message.reply_text(f"📢 Рассылка для {len(users)} пользователей...")
        
        for user_id, first_name, level, last_activity in users:
            try:
                await context.bot.send_message(user_id, f"📢 Сообщение от создателя:\n\n{message}")
                sent += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed += 1
                logger.warning(f"Не удалось отправить {user_id}: {e}")
        
        await update.message.reply_text(f"✅ Отправлено: {sent}\n❌ Неудачно: {failed}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if self.is_creator(user_data.user_id):
            total_users = self.db.get_growth_stats()
            vip_users = len(self.db.get_vip_users())
            total_commands = len(self.db.logs)
            popular_commands = self.db.get_popular_commands()[:5]
            
            stats_text = f"""
📊 СТАТИСТИКА БОТА

👥 Пользователей: {total_users}
💎 VIP: {vip_users}
📈 Команд: {total_commands}

🔥 ТОП-5:
"""
            for cmd, data in popular_commands:
                stats_text += f"• {cmd}: {data['usage_count']}\n"
            
            stats_text += f"\n⚡ Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
        else:
            stats_text = f"""
📊 СТАТИСТИКА

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{user_data.level * 100}
💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}
📝 Заметок: {len(user_data.notes)}
🧠 Памяти: {len(user_data.memory_data)}
            """
        
        self.db.log_command(user_data.user_id, "/stats")
        await update.message.reply_text(stats_text)
        await self.add_experience(user_data, 1)

    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            status = "включен" if self.maintenance_mode else "выключен"
            await update.message.reply_text(f"🛠 Режим сейчас {status}\n\n/maintenance [on/off]")
            await update.message.reply_text(f"🛠 Режим: {status}\n\n/maintenance [on/off]")
            return
        
        mode = context.args[0].lower()
        if mode in ['on', 'вкл']:
            self.maintenance_mode = True
            await update.message.reply_text("🛠 Режим ВКЛЮЧЕН")
            await update.message.reply_text("🛠 Режим обслуживания ВКЛЮЧЕН")
        elif mode in ['off', 'выкл']:
            self.maintenance_mode = False
            await update.message.reply_text("✅ Режим ВЫКЛЮЧЕН")
            await update.message.reply_text("✅ Режим обслуживания ВЫКЛЮЧЕН")
        else:
            await update.message.reply_text("❌ Используйте on/off")

    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        try:
            backup = {
            backup_data = {
                'users': self.db.users,
                'logs': self.db.logs[-100:],
                'statistics': self.db.statistics,
                'time': datetime.datetime.now().isoformat()
                'backup_time': datetime.datetime.now().isoformat()
            }
            success = self.db.save_data("backup.json", backup)
            
            success = self.db.save_data(BACKUP_PATH, backup_data)
            if success:
                await update.message.reply_text(f"✅ Backup создан!\nПользователей: {len(self.db.users)}")
                await update.message.reply_text(f"✅ Бэкап создан!\nПользователей: {len(self.db.users)}")
            else:
                await update.message.reply_text("❌ Ошибка backup!")
                await update.message.reply_text("❌ Ошибка создания бэкапа!")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        users = self.db.get_all_users()
        if not users:
            await update.message.reply_text("👥 Нет пользователей!")
            return
        text = "👥 ПОЛЬЗОВАТЕЛИ:\n\n"
        for uid, name, lvl in users[:20]:
            vip = "💎" if any(u.get('user_id') == uid and u.get('is_vip') for u in self.db.users) else "👤"
            text += f"{vip} {name} ({uid}) - Lvl {lvl}\n"
        if len(users) > 20:
            text += f"\n...ещё {len(users) - 20}"
        await update.message.reply_text(text)data.memory_data[key]
            self.db.save_user(user_data)
            await update.message.reply_text(f"✅ Удалено: {key}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    # Обработчики
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "help":
            await query.message.reply_text("/help для списка команд")
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.help_command(fake_update, context)
            
        elif query.data == "vip_info":
            await query.message.reply_text("💎 VIP дает расширенные возможности!\nСвяжитесь с @Ernest_Kostevich")
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.vip_command(fake_update, context)
            
        elif query.data == "ai_demo":
            await query.message.reply_text("🤖 Просто напишите мне вопрос!")
            await query.edit_message_text(
                "🤖 AI-чат готов!\n\n"
                "Просто напишите сообщение или используйте /ai\n\n"
                "Примеры:\n"
                "• Расскажи о космосе\n"
                "• Помоги с математикой\n"
                "• Объясни квантовую физику"
            )
            
        elif query.data == "my_stats":
            await query.message.reply_text("Используйте /stats")
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.stats_command(fake_update, context)

    async def self_ping(self):
        try:
            response = requests.get(RENDER_URL, timeout=10)
            logger.info(f"Ping: {response.status_code}")
            logger.info(f"Self-ping: {response.status_code}")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")
            logger.warning(f"Self-ping failed: {e}")

    async def run_bot(self):
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не найден!")
            logger.error("BOT_TOKEN не найден!")
            return

        application = (
@@ -1132,36 +1558,72 @@ async def run_bot(self):
            .build()
        )

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(f"Error: {context.error}")
            
            if isinstance(context.error, Conflict):
                logger.error("Конфликт: возможно запущено несколько ботов")
                logger.error("Конфликт: несколько экземпляров бота")
                await asyncio.sleep(30)
        
            
        application.add_error_handler(error_handler)

        # Регистрация всех команд
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("info", self.info_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("ai", self.ai_command))
        application.add_handler(CommandHandler("note", self.note_command))
        application.add_handler(CommandHandler("notes", self.notes_command))
        application.add_handler(CommandHandler("delnote", self.delnote_command))
        application.add_handler(CommandHandler("findnote", self.findnote_command))
        application.add_handler(CommandHandler("clearnotes", self.clearnotes_command))
        application.add_handler(CommandHandler("memorysave", self.memorysave_command))
        application.add_handler(CommandHandler("memoryget", self.memoryget_command))
        application.add_handler(CommandHandler("memorylist", self.memorylist_command))
        application.add_handler(CommandHandler("memorydel", self.memorydel_command))
        application.add_handler(CommandHandler("time", self.time_command))
        application.add_handler(CommandHandler("date", self.date_command))
        application.add_handler(CommandHandler("joke", self.joke_command))
        application.add_handler(CommandHandler("fact", self.fact_command))
        application.add_handler(CommandHandler("quote", self.quote_command))
        application.add_handler(CommandHandler("coin", self.coin_command))
        application.add_handler(CommandHandler("dice", self.dice_command))
        application.add_handler(CommandHandler("8ball", self.eightball_command))
        application.add_handler(CommandHandler("quiz", self.quiz_command))
        application.add_handler(CommandHandler("math", self.math_command))
        application.add_handler(CommandHandler("calculate", self.calculate_command))
        application.add_handler(CommandHandler("password", self.password_command))
        application.add_handler(CommandHandler("qr", self.qr_command))
        application.add_handler(CommandHandler("shorturl", self.shorturl_command))
        application.add_handler(CommandHandler("uptime", self.uptime_command))
        application.add_handler(CommandHandler("ip", self.ip_command))
        application.add_handler(CommandHandler("weather", self.weather_command))
        application.add_handler(CommandHandler("currency", self.currency_command))
        application.add_handler(CommandHandler("translate", self.translate_command))
        application.add_handler(CommandHandler("rank", self.rank_command))
        application.add_handler(CommandHandler("vip", self.vip_command))
        application.add_handler(CommandHandler("remind", self.remind_command))
        application.add_handler(CommandHandler("reminders", self.reminders_command))
        application.add_handler(CommandHandler("nickname", self.nickname_command))
        application.add_handler(CommandHandler("profile", self.profile_command))
        application.add_handler(CommandHandler("grant_vip", self.grant_vip_command))
        application.add_handler(CommandHandler("revoke_vip", self.revoke_vip_command))
        application.add_handler(CommandHandler("users", self.users_command))
        application.add_handler(CommandHandler("broadcast", self.broadcast_command))
        application.add_handler(CommandHandler("maintenance", self.maintenance_command))
        application.add_handler(CommandHandler("backup", self.backup_command))
        application.add_handler(CommandHandler("stats", self.stats_command))

        # Обработчик сообщений
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                self.handle_message
            )
        )

        # Обработчик кнопок
        application.add_handler(CallbackQueryHandler(self.button_callback))

        # Настройка планировщика
        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()
@@ -1174,13 +1636,14 @@ async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            id='self_ping'
        )

        # Поздравление папы 3 октября в 9:00 по московскому времени
        moscow_tz = pytz.timezone('Europe/Moscow')
        # Проверка дней рождения каждый день в 9:00
        self.scheduler.add_job(
            self.dad_birthday_congratulation,
            CronTrigger(month=10, day=3, hour=9, minute=0, timezone=moscow_tz),
            self.check_birthdays,
            'cron',
            hour=9,
            minute=0,
            args=[application],
            id='dad_birthday'
            id='birthday_check'
        )

        logger.info("🤖 Бот запущен!")
@@ -1195,10 +1658,6 @@ async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Критическая ошибка: {e}")
            raise

# =============================================================================
# MAIN
# =============================================================================

async def main():
    bot = TelegramBot()
    await bot.run_bot()
@@ -1208,7 +1667,7 @@ async def main():

@app.route('/')
def home():
    return f"🤖 Bot Online | {datetime.datetime.now()}"
    return f"🤖 Telegram AI Bot is running!\n⏰ Time: {datetime.datetime.now()}"

@app.route('/health')
def health():
