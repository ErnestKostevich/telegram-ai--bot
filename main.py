#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM AI BOT - Исправленная версия
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
from telegram.error import NetworkError, TimedOut

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

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"

# ID создателя бота
CREATOR_ID = 7108255346

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL = os.getenv("MODEL", "gemini-2.0-flash-exp")

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
        
        # Инициализация GitHub API
        if GITHUB_TOKEN:
            try:
                self.g = Github(GITHUB_TOKEN)
                self.repo = self.g.get_repo(GITHUB_REPO)
                logger.info("✅ GitHub API инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации GitHub API: {e}")
        
        # Загрузка данных
        self.users = self.load_data(USERS_FILE, [])
        self.logs = self.load_data(LOGS_FILE, [])
        self.statistics = self.load_data(STATISTICS_FILE, {})
    
    def load_data(self, path, default):
        """Безопасная загрузка данных"""
        if not self.repo:
            logger.warning(f"GitHub не инициализирован, используются дефолтные данные для {path}")
            return default
            
        try:
            file = self.repo.get_contents(path)
            content = file.decoded_content.decode('utf-8')
            data = json.loads(content)
            
            # Исправляем тип данных если нужно
            if path == USERS_FILE and isinstance(data, dict) and not data:
                data = []
            elif path == STATISTICS_FILE and isinstance(data, list):
                data = {}
            elif path == LOGS_FILE and isinstance(data, dict) and not data:
                data = []
                
            logger.info(f"✅ Загружено из {path}")
            return data
        except Exception as e:
            logger.warning(f"⚠️ Не удалось загрузить {path}: {e}")
            return default
    
    def save_data(self, path, data):
        """Безопасное сохранение данных"""
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
            
            logger.info(f"✅ Сохранено в {path}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в {path}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        for user_dict in self.users:
            if user_dict.get('user_id') == user_id:
                return UserData.from_dict(user_dict)
        return None
    
    def get_user_by_username(self, username: str) -> Optional[UserData]:
        for user_dict in self.users:
            if user_dict.get('username') == username:
                return UserData.from_dict(user_dict)
        return None
    
    def save_user(self, user_data: UserData):
        """Сохранение пользователя"""
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
        """Асинхронное сохранение логов"""
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
                logger.info("✅ Gemini модель инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации Gemini: {e}")
        
        self.user_contexts = {}
        self.scheduler = AsyncIOScheduler()
        self.maintenance_mode = False
    
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
            
            if self.is_creator(user.id):
                user_data.is_vip = True
                user_data.vip_expires = None
                logger.info(f"✅ Создатель получил автоматический VIP: {user.id}")
            
            self.db.save_user(user_data)
            logger.info(f"✅ Создан новый пользователь: {user.id} ({user.first_name})")
        
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
                logger.error(f"Ошибка проверки VIP: {e}")
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
            logger.error(f"Ошибка отправки уведомления: {e}")

    # =============================================================================
    # БАЗОВЫЕ КОМАНДЫ
    # =============================================================================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        if self.is_creator(user_data.user_id):
            message = """
🎯 Добро пожаловать, Создатель!

👑 Команды создателя:
• /grant_vip - Выдать VIP
• /revoke_vip - Отозвать VIP
• /stats - Статистика бота
• /broadcast - Рассылка
• /users - Список пользователей
• /maintenance - Режим обслуживания
• /backup - Резервная копия
• /logs - Логи системы
• /cleanup - Очистка неактивных

🤖 /help - Все команды
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
VIP до: {expires_text}

⭐ VIP команды:
• /remind - Напоминания
• /vipstats - VIP статистика
• /priority - Приоритет
• /profile - Профиль
• /nickname - Установить ник

🤖 /help - Все команды
            """
        else:
            message = f"""
🤖 Привет, {user_data.first_name}!

Я AI-бот с множеством функций!

🌟 Основные:
• 💬 AI-чат (просто напишите)
• 📝 Заметки (/note)
• 🧠 Память (/memorysave)
• 🌤️ Погода (/weather)
• 💰 Валюты (/currency)
• 🎮 Игры (/coin, /dice, /quiz)

💎 Хотите VIP? Свяжитесь с создателем!
🤖 /help - Все команды
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
        
        # Базовые команды для всех
        help_text = """
📋 КОМАНДЫ БОТА

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы
/rank - Ваш уровень

💬 AI-ЧАТ:
/ai [вопрос] - Вопрос AI
Или просто напишите!

📝 ЗАМЕТКИ:
/note [текст] - Создать
/notes - Показать все
/delnote [номер] - Удалить
/findnote [слово] - Поиск
/clearnotes - Очистить

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist - Список
/memorydel [ключ] - Удалить

⏰ ВРЕМЯ:
/time - Текущее время
/date - Текущая дата

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Шутка
/fact - Интересный факт
/quote - Цитата
/quiz - Викторина
/coin - Монетка
/dice - Кубик
/8ball [вопрос] - Шар

🔢 МАТЕМАТИКА:
/math [выражение]
/calculate [выражение]

🛠️ УТИЛИТЫ:
/password [длина] - Генератор
/qr [текст] - QR-код
/shorturl [ссылка] - Сокращение
/ip - Информация об IP
/weather [город] - Погода
/currency [из] [в] - Конвертер
/translate [язык] [текст]
        """
        
        # VIP команды
        if self.is_vip(user_data):
            help_text += """
💎 VIP КОМАНДЫ:
/vip - VIP статус
/remind [мин] [текст] - Напоминание
/reminders - Список напоминаний
/delreminder [номер] - Удалить
/nickname [имя] - Установить ник
/profile - Профиль
/vipstats - VIP статистика
/priority - Приоритет обработки
            """
        
        # Команды создателя
        if self.is_creator(user_data.user_id):
            help_text += """
👑 КОМАНДЫ СОЗДАТЕЛЯ:
/grant_vip [id/@username] [week/month/year/permanent]
/revoke_vip [id/@username]
/broadcast [текст] - Рассылка
/users - Список пользователей
/stats - Полная статистика
/maintenance [on/off] - Режим обслуживания
/backup - Резервная копия
/logs - Логи системы
/cleanup - Очистка неактивных
/systeminfo - Информация о системе
/resetuser [id] - Сброс пользователя
            """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info_text = f"""
🤖 О БОТЕ

Версия: 2.1
Создатель: Ernest
Функций: 50+
AI: {"Gemini 2.0 ✅" if self.gemini_model else "❌"}
База: {"GitHub ✅" if self.db.repo else "Локальная"}
Хостинг: Render

Бот работает 24/7
        """
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        total_users = len(self.db.users)
        total_commands = len(self.db.logs)
        
        status_text = f"""
⚡ СТАТУС БОТА

Онлайн: ✅
Пользователей: {total_users}
Команд: {total_commands}
Gemini: {"✅" if self.gemini_model else "❌"}
GitHub: {"✅" if self.db.repo else "❌"}
Обслуживание: {"Вкл" if self.maintenance_mode else "Выкл"}
        """
        await update.message.reply_text(status_text)
        await self.add_experience(user_data, 1)

    # ==================== ПРОДОЛЖЕНИЕ В СЛЕДУЮЩЕЙ ЧАСТИ ====================
    # Добавим остальные команды...

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос после /ai\nПример: /ai Что такое Python?")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен. Gemini API не настроен.")
            return
        
        query = " ".join(context.args)
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            response = self.gemini_model.generate_content(query)
            await update.message.reply_text(response.text)
            await self.add_experience(user_data, 2)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")
            logger.error(f"Ошибка Gemini: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Автоответ на сообщения"""
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Бот на обслуживании. Попробуйте позже.")
            return
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "message")
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI-чат недоступен. Используйте команды!")
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

Ответь дружелюбно и кратко.
"""
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(response.text)
            
            self.user_contexts[user_id].append(f"Бот: {response.text}")
            await self.add_experience(user_data, 1)
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки сообщения.")
            logger.error(f"Ошибка сообщения: {e}")

    # Добавляем недостающую команду memorydel
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
            await update.message.reply_text(f"✅ Удалено: {key}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
        
        await self.add_experience(user_data, 1)

    # Остальные базовые команды (краткая версия)
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not context.args:
            await update.message.reply_text("📝 /note [текст]")
            return
        note = " ".join(context.args)
        user_data.notes.append(note)
        self.db.save_user(user_data)
        await update.message.reply_text("✅ Заметка сохранена!")
        await self.add_experience(user_data, 1)

    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок!")
            return
        notes_text = "\n".join(f"{i+1}. {note}" for i, note in enumerate(user_data.notes))
        await update.message.reply_text(f"📝 Заметки:\n{notes_text}")

    # Продолжение команд см. в оригинальном коде...
    # Из-за ограничения длины показаны ключевые исправления

    async def run_bot(self):
        """Запуск бота"""
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не найден!")
            return

        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30)
            .pool_timeout(30)
            .build()
        )
        
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(f"❌ Ошибка: {context.error}")
            
            if isinstance(context.error, telegram.error.Conflict):
                logger.error("Конфликт: возможно запущено несколько ботов")
                await asyncio.sleep(30)
        
        application.add_error_handler(error_handler)
        
        # Регистрация команд
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("info", self.info_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("ai", self.ai_command))
        application.add_handler(CommandHandler("note", self.note_command))
        application.add_handler(CommandHandler("notes", self.notes_command))
        application.add_handler(CommandHandler("memorydel", self.memorydel_command))
        # ... добавьте все ост
