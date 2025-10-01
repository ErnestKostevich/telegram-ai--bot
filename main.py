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
logger = logging.getLogger(name)

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
    def init(self):
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
    def init(self):
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

⭐️ VIP возможности:
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
• 🌤 Погода и новости
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

🛠 УТИЛИТЫ:
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

Ernest, [01.10.2025 03:41]
📊 ПРОГРЕСС:
/rank - Ваш уровень
        """
        
        if self.is_vip(user_data):
            help_text += """
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
⚡️ СТАТУС БОТА

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
            await update.message.reply_text("🤖 Задайте вопрос после /ai!")
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

Ernest, [01.10.2025 03:41]
async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Бот на обслуживании. Попробуйте позже.")
            return
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "message")
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI-чат недоступен. Gemini API не настроен.")
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

Ответь на последнее сообщение пользователя дружелюбно и полезно.
"""
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(response.text)
            
            self.user_contexts[user_id].append(f"Бот: {response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения.")
            logger.error(f"Ошибка обработки сообщения: {e}")
        
        await self.add_experience(user_data, 1)

    # Добавьте остальные методы команд аналогично...
    # (note, memorysave, weather, currency, translate, grant_vip, revoke_vip, и т.д.)

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("💎 /grant_vip [user_id или @username] [week/month/year/permanent]")
            return
        
        try:
            target = context.args[0]
            duration = context.args[1].lower()
            
            if target.startswith('@'):
                username = target[1:]
                target_user = self.db.get_user_by_username(username)
                if not target_user:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
                    return
            else:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
                if not target_user:
                    await update.message.reply_text("❌ Пользователь с таким ID не найден!")
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
                await update.message.reply_text("❌ Неверная длительность! Используйте: week/month/year/permanent")
                return
            
            self.db.save_user(target_user)
            await update.message.reply_text(f"✅ VIP выдан пользователю {target_user.first_name} (ID: {target_user.user_id})")
            
            try:
                await context.bot.send_message(
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
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        if not context.args:
            await update.message.reply_text("💎 /revoke_vip [user_id или @username]")
            return
        
        try:
            target = context.args[0]
            
            if target.startswith('@'):
                username = target[1:]
                target_user = self.db.get_user_by_username(username)
                if not target_user:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
                    return
            else:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
                if not target_user:
                    await update.message.reply_text("❌ Пользователь с таким ID не найден!")
                    return
            
            if not target_user.is_vip:
                await update.message.reply_text(f"❌ Пользователь {target_user.first_name} не является VIP!")
                return
            
            target_user.is_vip = False
            target_user.vip_expires = None
            self.db.save_user(target_user)
            
            await update.message.reply_text(f"✅ VIP статус отозван у {target_user.first_name} (ID: {target_user.user_id})")
            
            try:
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

    # Остальные команды (добавляю ключевые)
    
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

Ernest, [01.10.2025 03:41]
async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер заметки!\nПример: /delnote 1")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            deleted = user_data.notes.pop(index)
            self.db.save_user(user_data)
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

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        if not context.args:
            await update.message.reply_text("🌤 Укажите город!\nПример: /weather Москва")
            return
            
        if not OPENWEATHER_API_KEY:
            await update.message.reply_text("❌ Погода недоступна - не настроен API ключ.")
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
🌤 Погода в {city}:
🌡 Температура: {temp}°C (ощущается как {feels_like}°C)
☁️ Описание: {weather.capitalize()}
💧 Влажность: {humidity}%
                """
                await update.message.reply_text(weather_text)
            else:
                await update.message.reply_text("❌ Город не найден!")
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
                await update.message.reply_text("❌ Не удалось получить курс!")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка конвертации.")
            logger.error(f"Ошибка currency: {e}")
        
        await self.add_experience(user_data, 2)

async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text("🌐 /translate [язык] [текст]\nПример: /translate en Привет")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ Перевод недоступен.")
            return
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            prompt = f"Переведи следующий текст на {target_lang}: {text}"
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(f"🌐 Перевод:\n{response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка перевода.")
            logger.error(f"Ошибка translate: {e}")
        
        await self.add_experience(user_data, 2)

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
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
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
        await self.add_experience(user_data, 1)

    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 Задайте вопрос!\nПример: /8ball Стоит ли мне изучать Python?")
            return
        
        answers = ["✅ Да!", "❌ Нет", "🤔 Возможно", "⏳ Спроси позже"]
        await update.message.reply_text(f"🔮 {random.choice(answers)}")
        await self.add_experience(user_data, 1)

Ernest, [01.10.2025 03:41]
async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quiz")
        
        questions = [
            {"q": "Сколько дней в високосном году?", "a": "366"},
            {"q": "Столица Австралии?", "a": "Канберра"},
            {"q": "Самый большой океан?", "a": "Тихий"}
        ]
        
        question = random.choice(questions)
        await update.message.reply_text(f"❓ {question['q']}\n\n💡 Напишите ответ!")
        await self.add_experience(user_data, 1)

    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/math")
        
        if not context.args:
            await update.message.reply_text("🔢 Введите выражение!\nПример: /math 15 + 25")
            return
        
        expression = " ".join(context.args)
        try:
            allowed_chars = set('0123456789+-*/()., ')
            if not all(c in allowed_chars for c in expression):
                await update.message.reply_text("❌ Разрешены только: +, -, *, /, ()")
                return
            
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
            
            result = eval(expression, {"builtins": {}}, safe_dict)
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
        password = ''.join(random.choice(chars) for _ in range(length))
        
        await update.message.reply_text(f"🔐 Пароль ({length} символов):\n`{password}`", parse_mode='Markdown')
        await self.add_experience(user_data, 1)

    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/qr")
        
        if not context.args:
            await update.message.reply_text("📱 /qr [текст]\nПример: /qr https://google.com")
            return
        
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}"
        
        await update.message.reply_text(f"📱 QR-код:")
        await context.bot.send_photo(update.effective_chat.id, qr_url)
        await self.add_experience(user_data, 1)

async def shorturl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
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

    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/uptime")
        
        await update.message.reply_text(f"⏱️ Бот работает!\n👥 Пользователей: {len(self.db.users)}\n📊 Команд: {len(self.db.logs)}")
        await self.add_experience(user_data, 1)

    async def ip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ip")
        
        try:
            response = requests.get('https://httpbin.org/ip', timeout=5)
            ip = response.json().get('origin', 'Неизвестно')
            await update.message.reply_text(f"🌍 Ваш IP: {ip}")
        except:
            await update.message.reply_text("❌ Не удалось получить IP")
        
        await self.add_experience(user_data, 1)

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
        self.db.log_command(user_data.user_id, "/date")
        
        now = datetime.datetime.now()
        await update.message.reply_text(f"📅 Сегодня: {now.strftime('%d.%m.%Y')}")
        await self.add_experience(user_data, 1)

    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")
        
        required_exp = user_data.level * 100
        progress = (user_data.experience / required_exp) * 100
        
        rank_text = f"""
🏅 ВАШ УРОВЕНЬ

👤 Пользователь: {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐️ Опыт: {user_data.experience}/{required_exp}
📊 Прогресс: {progress:.1f}%

💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}
        """
        
        await update.message.reply_text(rank_text)
        await self.add_experience(user_data, 1)

# VIP команды
    
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Вы не VIP! Свяжитесь с @Ernest_Kostevich")
            return
        
        expires_text = 'бессрочно'
        if user_data.vip_expires:
            try:
                expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                expires_text = expires_date.strftime('%d.%m.%Y')
            except:
                pass
        
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
            await update.message.reply_text("❌ Неверный формат!")
        except Exception as e:
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
        
        reminders_text = "\n".join([
            f"{i+1}. {rem['text']} ({rem.get('time', 'неизвестно')})" 
            for i, rem in enumerate(user_data.reminders)
        ])
        
        await update.message.reply_text(f"⏰ Напоминания:\n{reminders_text}")
        await self.add_experience(user_data, 1)

Ernest, [01.10.2025 03:41]
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

Ernest, [01.10.2025 03:41]
🔥 ТОП-5:
"""
            for cmd, data in popular_commands:
                stats_text += f"• {cmd}: {data['usage_count']}\n"
            
            stats_text += f"\n⚡️ Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
        else:
            stats_text = f"""
📊 СТАТИСТИКА

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐️ Опыт: {user_data.experience}/{user_data.level * 100}
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
            await update.message.reply_text(f"🛠 Режим: {status}\n\n/maintenance [on/off]")
            return
        
        mode = context.args[0].lower()
        if mode in ['on', 'вкл']:
            self.maintenance_mode = True
            await update.message.reply_text("🛠 Режим обслуживания ВКЛЮЧЕН")
        elif mode in ['off', 'выкл']:
            self.maintenance_mode = False
            await update.message.reply_text("✅ Режим обслуживания ВЫКЛЮЧЕН")
        else:
            await update.message.reply_text("❌ Используйте on/off")

    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        try:
            backup_data = {
                'users': self.db.users,
                'logs': self.db.logs[-100:],
                'statistics': self.db.statistics,
                'backup_time': datetime.datetime.now().isoformat()
            }
            
            success = self.db.save_data(BACKUP_PATH, backup_data)
            if success:
                await update.message.reply_text(f"✅ Бэкап создан!\nПользователей: {len(self.db.users)}")
            else:
                await update.message.reply_text("❌ Ошибка создания бэкапа!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    # Обработчики
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.help_command(fake_update, context)
            
        elif query.data == "vip_info":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.vip_command(fake_update, context)
            
        elif query.data == "ai_demo":
            await query.edit_message_text(
                "🤖 AI-чат готов!\n\n"
                "Просто напишите сообщение или используйте /ai\n\n"
                "Примеры:\n"
                "• Расскажи о космосе\n"
                "• Помоги с математикой\n"
                "• Объясни квантовую физику"
            )
            
        elif query.data == "my_stats":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.stats_command(fake_update, context)

    async def self_ping(self):
        try:
            response = requests.get(RENDER_URL, timeout=10)
            logger.info(f"Self-ping: {response.status_code}")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")

    async def run_bot(self):
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не найден!")
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
            logger.error(f"Error: {context.error}")
            
            if isinstance(context.error, Conflict):
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
        
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                self.handle_message
            )
        )
        
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()
        
        # Пинг каждые 14 минут
        self.scheduler.add_job(
            self.self_ping,
            'interval',
            minutes=14,
            id='self_ping'
        )
        
        # Проверка дней рождения каждый день в 9:00
        self.scheduler.add_job(
            self.check_birthdays,
            'cron',
            hour=9,
            minute=0,
            args=[application],
            id='birthday_check'
        )
        
        logger.info("🤖 Бот запущен!")
        
        try:
            await application.run_polling(
                drop_pending_updates=True,
                timeout=30,
                bootstrap_retries=3
            )
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            raise

async def main():
    bot = TelegramBot()
    await bot.run_bot()

# Flask для Render
app = Flask(name)

@app.route('/')
def home():
    return f"🤖 Telegram AI Bot is running!\n⏰ Time: {datetime.datetime.now()}"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

if name == "main":
    from threading import Thread
    
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(
        target=app.run, 
        kwargs={'host': '0.0.0.0', 'port': port, 'debug': False}
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(main())
