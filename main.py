#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ТЕЛЕГРАМ БОТ - Полная рабочая версия
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
from apscheduler.triggers.cron import CronTrigger
from newsapi import NewsApiClient
import nest_asyncio
from flask import Flask
import pytz
from github import Github

nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ChatType
import telegram.error
import google.generativeai as genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"

CREATOR_ID = 7108255346
CREATOR_USERNAME = "Ernest_Kostevich"
DAD_USERNAME = "mkostevich"
BOT_USERNAME = "@AI_DISCO_BOT"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL = os.getenv("MODEL", "gemini-2.0-flash-exp")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

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
                logger.error(f"Ошибка GitHub API: {e}")
        
        self.users = self.load_data(USERS_FILE, [])
        self.logs = self.load_data(LOGS_FILE, [])
        self.statistics = self.load_data(STATISTICS_FILE, {})
    
    def load_data(self, path, default):
        if not self.repo:
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
                
            logger.info(f"Загружено из {path}")
            return data
        except Exception as e:
            logger.warning(f"Не удалось загрузить {path}: {e}")
            return default
    
    def save_data(self, path, data):
        if not self.repo:
            return False
            
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            
            try:
                file = self.repo.get_contents(path)
                self.repo.update_file(path, f"Update {path}", content, file.sha)
            except:
                self.repo.create_file(path, f"Create {path}", content)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения {path}: {e}")
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
        else:
            self.statistics[command] = {'usage_count': 1}
        
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

class TelegramBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.gemini_model = None
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("Gemini инициализирован")
            except Exception as e:
                logger.error(f"Ошибка Gemini: {e}")
        
        self.user_contexts = {}
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
            logger.info(f"Новый пользователь: {user.id}")
        
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
                pass
        
        return True
    
    async def add_experience(self, user_data: UserData, points: int = 1):
        user_data.experience += points
        
        required_exp = user_data.level * 100
        if user_data.experience >= required_exp:
            user_data.level += 1
            user_data.experience = 0
        
        self.db.save_user(user_data)
    
    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка уведомления {user_id}: {e}")

    async def send_dad_birthday_greeting(self, context: ContextTypes.DEFAULT_TYPE):
        try:
            dad_user = self.db.get_user_by_username(DAD_USERNAME)
            if dad_user:
                greeting = """
🎉🎂 С ДНЁМ РОЖДЕНИЯ! 🎂🎉

Дорогой папа!

От всего сердца поздравляю тебя с Днём Рождения! 
Желаю крепкого здоровья, счастья, успехов!

Пусть каждый день приносит радость и новые возможности!

С любовью, твой сын! ❤️
                """
                await context.bot.send_message(chat_id=dad_user.user_id, text=greeting)
                logger.info(f"Отправлено поздравление папе")
        except Exception as e:
            logger.error(f"Ошибка поздравления: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        if self.is_creator(user_data.user_id):
            message = f"🎯 Добро пожаловать, Создатель!\n\n👑 У вас полный доступ\n🤖 /help для команд"
        elif self.is_vip(user_data):
            message = f"💎 Добро пожаловать, {user_data.first_name}!\n\n⭐ VIP статус активен\n🤖 /help для команд"
        else:
            message = f"🤖 Привет, {user_data.first_name}!\n\nЯ AI-бот с 50+ функциями!\n\n💎 Хотите VIP? @{CREATOR_USERNAME}\n🤖 /help для команд"
        
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
/status - Статус
/ping - Проверка

💬 AI:
/ai [вопрос] - Задать вопрос
Или просто напишите!

📝 ЗАМЕТКИ:
/note [текст] - Сохранить
/notes - Показать
/delnote [номер] - Удалить

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Шутка
/fact - Факт
/quote - Цитата
/coin - Монетка
/dice - Кубик

🌤️ УТИЛИТЫ:
/weather [город] - Погода
/currency [из] [в] - Валюты
/translate [язык] [текст]
/time - Время
/date - Дата

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist - Список

📊 ПРОФИЛЬ:
/rank - Уровень
/profile - Профиль
        """
        
        if self.is_vip(user_data):
            help_text += "\n💎 VIP:\n/vip\n/remind [мин] [текст]\n/reminders\n/nickname [имя]"
        
        if self.is_creator(user_data.user_id):
            help_text += "\n\n👑 СОЗДАТЕЛЬ:\n/grant_vip [id/@user] [time]\n/revoke_vip [id/@user]\n/broadcast [текст]\n/users\n/stats"
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос!\nПример: /ai Что такое Python?")
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
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")
        
        await self.add_experience(user_data, 2)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            return
        
        user_data = await self.get_user_data(update)
        
        if not self.gemini_model:
            return
        
        message = update.message.text
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            response = self.gemini_model.generate_content(f"Ответь дружелюбно на русском: {message}")
            await update.message.reply_text(response.text)
        except:
            pass
        
        await self.add_experience(user_data, 1)

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("💎 /grant_vip [id/@user] [week/month/year/permanent]")
            return
        
        try:
            target = context.args[0]
            duration = context.args[1].lower()
            
            if target.startswith('@'):
                target_user = self.db.get_user_by_username(target[1:])
                if not target_user:
                    await update.message.reply_text(f"❌ {target} не найден!")
                    return
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
                await update.message.reply_text("❌ Используйте: week/month/year/permanent")
                return
            
            self.db.save_user(target_user)
            await update.message.reply_text(f"✅ VIP выдан {target_user.first_name}!")
            
            try:
                await context.bot.send_message(target_user.user_id, "🎉 Вы получили VIP!")
            except:
                pass
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.help_command(fake_update, context)

    async def self_ping(self):
        try:
            requests.get(RENDER_URL, timeout=10)
            logger.info("Self-ping OK")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")

    async def run_bot(self):
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не найден!")
            return

        application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).build()
        
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(f"Error: {context.error}")
        
        application.add_error_handler(error_handler)
        
        # Регистрация команд
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("ai", self.ai_command))
        application.add_handler(CommandHandler("grant_vip", self.grant_vip_command))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Планировщик
        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()
        
        self.scheduler.add_job(self.self_ping, 'interval', minutes=14, id='self_ping')
        self.scheduler.add_job(
            self.send_dad_birthday_greeting,
            trigger=CronTrigger(month=10, day=3, hour=9, minute=0, timezone='Europe/Moscow'),
            args=[application],
            id='dad_birthday'
        )
        
        logger.info("🤖 Бот запущен!")
        
        await application.run_polling(drop_pending_updates=True, timeout=30)

async def main():
    bot = TelegramBot()
    await bot.run_bot()

app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 Bot Running! {datetime.datetime.now()}"

@app.route('/health')
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    from threading import Thread
    
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port, 'debug': False})
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(main())
