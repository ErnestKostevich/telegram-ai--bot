#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ - Главный файл
Полнофункциональный бот с AI, VIP-системой и более чем 150 функциями
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
from newsapi import NewsApiClient
import nest_asyncio
from flask import Flask
import pytz
from github import Github

nest_asyncio.apply()

# Telegram Bot API
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ChatType
from telegram.error import Conflict, TimedOut, NetworkError

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
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"

# ID создателя бота
CREATOR_ID = 7108255346
CREATOR_USERNAME = "@Ernest_Kostevich"
DAD_USERNAME = "@mkostevich"
DAD_BIRTHDAY = "2025-10-03"  # Дата для поздравления папы
BOT_USERNAME = "@AI_DISCO_BOT"

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL = os.getenv("MODEL", "gemini-2.0-flash-exp")

# Maintenance mode flag
MAINTENANCE_MODE = False

# Backup path
BACKUP_PATH = "bot_backup.json"

# Render URL для пинга
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

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
                
            logger.info(f"Успешно загружено {len(data) if isinstance(data, (list, dict)) else 'данные'} из {path}")
            return data
        except Exception as e:
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
            logger.error(f"Ошибка сохранения в {path}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        for user_dict in self.users:
            if user_dict.get('user_id') == user_id:
                return UserData.from_dict(user_dict)
        return None
    
    def get_user_by_username(self, username: str) -> Optional[UserData]:
        username_clean = username.lstrip('@').lower()
        for user_dict in self.users:
            user_username = user_dict.get('username', '').lower()
            if user_username == username_clean:
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
        
        # Обновление VIP для создателя, если он не VIP
        if self.is_creator(user.id) and not self.is_vip(user_data):
            user_data.is_vip = True
            user_data.vip_expires = None
            self.db.save_user(user_data)
            logger.info(f"Обновлен VIP для создателя: {user.id}")
        
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

👑 Доступные команды создателя:
• /grant_vip - Выдать VIP
• /revoke_vip - Отозвать VIP
• /stats - Полная статистика
• /broadcast - Рассылка
• /users - Список пользователей
• /maintenance - Режим обслуживания
• /backup - Резервная копия

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
                    expires_text = 'неопределено'
            
            message = f"""
💎 Добро пожаловать, {nickname}!
У вас VIP статус до {expires_text}.

⭐ VIP возможности:
• /remind - Напоминания
• /reminders - Список напоминаний
• /nickname - Установить никнейм
• /profile - Ваш профиль

🤖 Используйте /help для полного списка команд.
            """
        else:
            message = f"""
🤖 Привет, {user_data.first_name}!
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
            [InlineKeyboardButton("🤖 AI чат", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        """
        
        if self.is_vip(user_data):
            help_text += """
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
            """
        
        if self.is_creator(update.effective_user.id):
            help_text += """
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
            """
        
        help_text += """
🧠 ПАМЯТЬ:
/memorysave [ключ] [значение] - Сохранить
/ask [вопрос] - Поиск
/memorylist - Список
/memorydel [ключ] - Удалить

/rank - Уровень
/leaderboard - Лидеры

🌐 ЯЗЫКИ:
/language [код] - Смена языка
        """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info_text = """
🤖 О БОТЕ

Версия: 2.0
Создатель: Ernest
Функций: 150+
AI: Gemini 2.0 Flash
База данных: GitHub
Хостинг: Render

Бот работает 24/7 с автопингом.
        """
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM logs")
        total_commands = cursor.fetchone()[0]
        conn.close()
        
        status_text = f"""
⚡ СТАТУС БОТА

Онлайн: ✅
Версия: 2.0
Пользователей: {total_users}
Команд выполнено: {total_commands}
Maintenance: {"Вкл" if self.maintenance_mode else "Выкл"}
        """
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
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Бот на обслуживании. Попробуйте позже.")
            return
        
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
        
        now_utc = datetime.datetime.now(pytz.utc)
        
        times = {
            "GMT (UTC)": now_utc.astimezone(pytz.utc).strftime('%H:%M:%S'),
            "МСК (Moscow)": now_utc.astimezone(pytz.timezone('Europe/Moscow')).strftime('%H:%M:%S'),
            "Washington (US/Eastern)": now_utc.astimezone(pytz.timezone('US/Eastern')).strftime('%H:%M:%S'),
            "New York (US/Eastern)": now_utc.astimezone(pytz.timezone('US/Eastern')).strftime('%H:%M:%S'),
            "CEST (Europe/Paris)": now_utc.astimezone(pytz.timezone('Europe/Paris')).strftime('%H:%M:%S')
        }
        
        text = "\n".join(f"{zone}: {t}" for zone, t in times.items())
        await update.message.reply_text(f"⏰ Время:\n{text}")
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
        
        # Генерация вопроса без ответа
        prompt = "Задай вопрос для викторины с вариантами ответов. Не раскрывай ответ сразу!"
        response = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(response.text)
        
        # Планируем отправку ответа через 30 секунд
        async def send_answer():
            prompt_answer = "Правильный ответ на предыдущий вопрос викторины"
            response_answer = self.gemini_model.generate_content(prompt_answer)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_answer.text)
        
        self.scheduler.add_job(send_answer, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=30))
        
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
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Вы не VIP! Спросите у создателя.")
            return
        
        expires = user_data.vip_expires.strftime('%d.%m.%Y') if user_data.vip_expires else 'бессрочно'
        await update.message.reply_text(f"💎 VIP активен до {expires}")
        await self.add_experience(user_data, 1)

    async def vipbenefits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /vipbenefits """
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vipbenefits")
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Вы не VIP!")
            return
        
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
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Вы не VIP!")
            return
        
        if user_data.vip_expires:
            remaining = (user_data.vip_expires - datetime.datetime.now()).days
            await update.message.reply_text(f"⏳ Осталось {remaining} дней VIP")
        else:
            await update.message.reply_text("⏳ VIP бессрочный")
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
            await update.message.reply_text("/grant_vip [user_id или @username] [duration: week/month/year/permanent]")
            return
        
        target = context.args[0]
        duration = context.args[1].lower()
        
        if target.startswith('@'):
            target_user = self.db.get_user_by_username(target[1:])
        else:
            target_user = self.db.get_user(int(target))
        
        if not target_user:
            await update.message.reply_text("❌ Пользователь не найден!")
            return
        
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
            await update.message.reply_text("❌ Неверная длительность!")
            return
        
        target_user.is_vip = True
        self.db.save_user(target_user)
        await update.message.reply_text("✅ VIP выдан!")
        try:
            await context.bot.send_message(target_user.user_id, "🎉 Вы получили VIP!")
        except:
            pass

    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /revoke_vip """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("/revoke_vip [user_id или @username]")
            return
        
        target = context.args[0]
        if target.startswith('@'):
            target_user = self.db.get_user_by_username(target[1:])
        else:
            target_user = self.db.get_user(int(target))
        
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
        
        vips = self.db.get_vip_users()
        text = "\n".join(f"{vip[1]} (ID: {vip[0]}) expires {vip[2]}" for vip in vips) if vips else "Нет VIP"
        await update.message.reply_text(f"💎 VIP список:\n{text}")

    async def userinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /userinfo """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("/userinfo [user_id или @username]")
            return
        
        target = context.args[0]
        if target.startswith('@'):
            target_user = self.db.get_user_by_username(target[1:])
        else:
            target_user = self.db.get_user(int(target))
        
        if target_user:
            info = f"ID: {target_user.user_id}\nИмя: {target_user.first_name}\nVIP: {target_user.is_vip}\nУровень: {target_user.level}"
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
        sent = 0
        for user in users:
            try:
                await context.bot.send_message(user[0], text)
                sent += 1
            except:
                pass
        await update.message.reply_text(f"✅ Рассылка отправлена {sent} пользователям!")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /stats """
        user_id = update.effective_user.id
        if not self.is_creator(user_id):
            user_data = await self.get_user_data(update)
            # Личная статистика
            stats_text = f"""
📊 ВАША СТАТИСТИКА

👤 Пользователь: {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{user_data.level * 100}
💎 VIP: {"✅ Да" if self.is_vip(user_data) else "❌ Нет"}
📝 Заметок: {len(user_data.notes)}
🏆 Достижений: {len(user_data.achievements)}
            """
            await update.message.reply_text(stats_text)
            return
        
        self.db.log_command(user_id, "/stats")
        
        total_users = self.db.get_growth_stats()
        vip_users = len(self.db.get_vip_users())
        total_commands = len(self.db.logs)
        
        stats_text = f"""
📊 СТАТИСТИКА БОТА

👥 Всего пользователей: {total_users}
💎 VIP пользователей: {vip_users}
📈 Выполнено команд: {total_commands}

🔥 ПОПУЛЯРНЫЕ КОМАНДЫ:
"""
        
        for cmd, count in self.db.get_popular_commands():
            stats_text += f"• {cmd}: {count} раз\n"
        
        stats_text += f"""
        
⚡ Статус: Онлайн
🤖 Версия: 2.0
📅 Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        
        await update.message.reply_text(stats_text)

    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /users """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        users = self.db.get_all_users()
        text = "\n".join(f"{user[1]} (ID: {user[0]}) lvl {user[2]}" for user in users[:20])  # Лимит 20
        await update.message.reply_text(f"👥 Пользователи (первые 20):\n{text}")

    async def activity_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /activity """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        users = self.db.get_all_users()
        active = [user for user in users if datetime.datetime.fromisoformat(user[3]) > datetime.datetime.now() - datetime.timedelta(days=7)]
        text = f"Активных за неделю: {len(active)} из {len(users)}"
        await update.message.reply_text(text)

    async def popular_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /popular """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        popular = self.db.get_popular_commands()
        text = "\n".join(f"{cmd}: {count} раз" for cmd, count in popular)
        await update.message.reply_text(f"🔥 Популярные команды:\n{text}")

    async def growth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /growth """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        total = self.db.get_growth_stats()
        await update.message.reply_text(f"📈 Рост: Всего пользователей {total}")

    async def memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /memory """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        # Пример просмотра памяти, адаптируй
        await update.message.reply_text("🧠 Память: (placeholder)")

    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /backup """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        self.db.save_data(BACKUP_PATH, {'users': self.db.users, 'logs': self.db.logs, 'statistics': self.db.statistics})
        await update.message.reply_text("💾 Бэкап создан!")

    async def restore_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /restore """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        try:
            data = self.db.load_data(BACKUP_PATH, {})
            self.db.users = data.get('users', [])
            self.db.logs = data.get('logs', [])
            self.db.statistics = data.get('statistics', {})
            self.db.save_data(USERS_FILE, self.db.users)
            self.db.save_data(LOGS_FILE, self.db.logs)
            self.db.save_data(STATISTICS_FILE, self.db.statistics)
            await update.message.reply_text("🔄 Восстановлено из бэкапа!")
        except:
            await update.message.reply_text("❌ Бэкап не найден!")

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /export """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("/export [user_id или @username]")
            return
        
        target = context.args[0]
        if target.startswith('@'):
            target_user = self.db.get_user_by_username(target[1:])
        else:
            target_user = self.db.get_user(int(target))
        
        if target_user:
            data = json.dumps(target_user.to_dict(), ensure_ascii=False)
            await update.message.reply_text(f"📤 Экспорт: {data}")
        else:
            await update.message.reply_text("❌ Не найден!")

    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /cleanup """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        deleted = self.db.cleanup_inactive()
        await update.message.reply_text(f"🧹 Очищено {deleted} неактивных пользователей")

    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /restart """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        await update.message.reply_text("🔄 Перезапуск...")
        sys.exit(0)  # На Render перезапустит сервис

    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /maintenance """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("/maintenance [on/off]")
            return
        
        mode = context.args[0].lower()
        self.maintenance_mode = mode == "on"
        await update.message.reply_text(f"🛠 Maintenance: {'Вкл' if self.maintenance_mode else 'Выкл'}")

    async def log_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /log """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        level = context.args[0] if context.args else "all"
        logs = self.db.get_logs(level)
        text = "\n".join(f"{log[4]} - User {log[1]}: {log[2]} {log[3]}" for log in logs)
        await update.message.reply_text(f"📜 Логи ({level}):\n{text}")

    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /config """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        # Placeholder для конфига
        await update.message.reply_text("⚙️ Конфиг: (placeholder)")

    async def update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ /update """
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        # На Render: git pull или manual deploy
        await update.message.reply_text("🔄 Обновление: Выполните manual deploy на Render")

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
            await update.message.reply_text("/language [ru/en/es/de/it]")
            return
        
        lang = context.args[0].lower()
        if lang in ['ru', 'en', 'es', 'de', 'it']:
            user_data.language = lang
            self.db.save_user(user_data)
            await update.message.reply_text("🈯 Язык изменён!")
        else:
            await update.message.reply_text("❌ Неверный код языка! Доступны: ru, en, es, de, it")
        # В реальности адаптируй ответы на lang
        await self.add_experience(user_data, 1)

    # =============================================================================
    # CALLBACK ОБРАБОТЧИКИ
    # =============================================================================

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
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
            await self.stats_command(update, context)

    # =============================================================================
    # ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
    # =============================================================================

    async def run_bot(self):
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавь handlers только для оставшихся команд
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
        application.add_handler(CommandHandler("compliment", self.com
