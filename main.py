#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM AI BOT v2.1 - Полная версия
Создатель: Ernest (@Ernest_Kostevich)
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
from telegram.error import NetworkError, TimedOut, Conflict

# Google Gemini
import google.generativeai as genai

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"

# Создатель и папа
CREATOR_ID = 7108255346
DAD_USERNAME = "mkostevich"  # Без @

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = "gemini-2.0-flash-exp"

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
    level: int = 1
    experience: int = 0
    achievements: List[str] = field(default_factory=list)
    memory_data: Dict = field(default_factory=dict)
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
            level=data.get('level', 1),
            experience=data.get('experience', 0),
            achievements=data.get('achievements', []),
            memory_data=data.get('memory_data', {}),
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
            'level': self.level,
            'experience': self.experience,
            'achievements': self.achievements,
            'memory_data': self.memory_data,
            'last_activity': self.last_activity
        }

# =============================================================================
# БАЗА ДАННЫХ
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
                logger.info("✅ GitHub API подключен")
            except Exception as e:
                logger.error(f"❌ GitHub API ошибка: {e}")
        
        self.users = self.load_data(USERS_FILE, [])
        self.logs = self.load_data(LOGS_FILE, [])
        self.statistics = self.load_data(STATISTICS_FILE, {})
    
    def load_data(self, path, default):
        if not self.repo:
            return default
        try:
            file = self.repo.get_contents(path)
            data = json.loads(file.decoded_content.decode('utf-8'))
            
            # Исправление типов
            if path == USERS_FILE and isinstance(data, dict):
                data = []
            elif path == STATISTICS_FILE and isinstance(data, list):
                data = {}
            elif path == LOGS_FILE and isinstance(data, dict):
                data = []
            
            logger.info(f"✅ Загружено: {path}")
            return data
        except Exception as e:
            logger.warning(f"⚠️ {path}: {e}")
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
            logger.error(f"❌ Ошибка сохранения {path}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        for u in self.users:
            if u.get('user_id') == user_id:
                return UserData.from_dict(u)
        return None
    
    def get_user_by_username(self, username: str) -> Optional[UserData]:
        # Убираем @ если есть
        username = username.lstrip('@')
        for u in self.users:
            if u.get('username', '').lower() == username.lower():
                return UserData.from_dict(u)
        return None
    
    def save_user(self, user_data: UserData):
        user_data.last_activity = datetime.datetime.now().isoformat()
        
        if not isinstance(self.users, list):
            self.users = []
        
        for i, u in enumerate(self.users):
            if u.get('user_id') == user_data.user_id:
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
            self.statistics[command] = {'usage_count': 1, 'last_used': datetime.datetime.now().isoformat()}
        
        asyncio.create_task(self._save_logs_async())
    
    async def _save_logs_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, LOGS_FILE, self.logs)
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, STATISTICS_FILE, self.statistics)
    
    def get_all_users(self):
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('level', 1)) for u in self.users]
    
    def get_popular_commands(self):
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
                logger.info("✅ Gemini подключен")
            except Exception as e:
                logger.error(f"❌ Gemini: {e}")
        
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
            
            if user.id == CREATOR_ID:
                user_data.is_vip = True
                user_data.vip_expires = None
            
            self.db.save_user(user_data)
            logger.info(f"✅ Новый пользователь: {user.id}")
        
        return user_data
    
    def is_creator(self, user_id: int) -> bool:
        return user_id == CREATOR_ID
    
    def is_vip(self, user_data: UserData) -> bool:
        if not user_data.is_vip:
            return False
        if user_data.vip_expires:
            try:
                expires = datetime.datetime.fromisoformat(user_data.vip_expires)
                if datetime.datetime.now() > expires:
                    user_data.is_vip = False
                    user_data.vip_expires = None
                    self.db.save_user(user_data)
                    return False
            except:
                return False
        return True
    
    async def add_experience(self, user_data: UserData, points: int = 1):
        user_data.experience += points
        required = user_data.level * 100
        if user_data.experience >= required:
            user_data.level += 1
            user_data.experience = 0
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

    # БАЗОВЫЕ КОМАНДЫ
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        if self.is_creator(user_data.user_id):
            message = """
🎯 Добро пожаловать, Создатель!

👑 Команды создателя:
• /grant_vip - Выдать VIP
• /revoke_vip - Отозвать VIP
• /stats - Статистика
• /broadcast - Рассылка
• /users - Пользователи
• /maintenance - Обслуживание

🤖 /help - Все команды
            """
        elif self.is_vip(user_data):
            expires_text = 'бессрочно'
            if user_data.vip_expires:
                try:
                    expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                    expires_text = expires_date.strftime('%d.%m.%Y')
                except:
                    pass
            
            message = f"""
💎 VIP до: {expires_text}

⭐ VIP команды:
• /remind - Напоминания
• /profile - Профиль
• /vipstats - VIP статистика

🤖 /help - Все команды
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
        """
        
        if self.is_vip(user_data):
            help_text += """
💎 VIP:
/vip /remind [мин] [текст]
/reminders /profile
            """
        
        if self.is_creator(user_data.user_id):
            help_text += """
👑 Создатель:
/grant_vip [id/@username] [duration]
/revoke_vip [id/@username]
/broadcast [текст]
/users /stats /maintenance [on/off]
/backup
            """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 /ai [вопрос]")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        query = " ".join(context.args)
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            response = self.gemini_model.generate_content(query)
            await update.message.reply_text(response.text)
            await self.add_experience(user_data, 2)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Обслуживание. Попробуй позже.")
            return
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "message")
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен. Используй команды!")
            return
        
        message = update.message.text
        user_id = user_data.user_id
        
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        
        self.user_contexts[user_id].append(f"User: {message}")
        if len(self.user_contexts[user_id]) > 10:
            self.user_contexts[user_id] = self.user_contexts[user_id][-10:]
        
        context_str = "\n".join(self.user_contexts[user_id][-5:])
        prompt = f"Ты AI-ассистент. Контекст:\n{context_str}\n\nОтветь кратко и полезно."
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(response.text)
            self.user_contexts[user_id].append(f"Bot: {response.text}")
            await self.add_experience(user_data, 1)
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Message error: {e}")

    # КОМАНДЫ СОЗДАТЕЛЯ
    
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
            
            # Поддержка ID и username
            if target.startswith('@') or not target.isdigit():
                target_user = self.db.get_user_by_username(target)
                if not target_user:
                    await update.message.reply_text(f"❌ Пользователь {target} не найден!")
                    return
            else:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
                if not target_user:
                    await update.message.reply_text("❌ ID не найден!")
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
                await update.message.reply_text("❌ week/month/year/permanent")
                return
            
            self.db.save_user(target_user)
            await update.message.reply_text(f"✅ VIP выдан: {target_user.first_name} ({duration})")
            
            try:
                await context.bot.send_message(
                    target_user.user_id, 
                    f"🎉 Вы получили VIP!\nДлительность: {duration}"
                )
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
            
            if target.startswith('@') or not target.isdigit():
                target_user = self.db.get_user_by_username(target)
            else:
                target_user = self.db.get_user(int(target))
            
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            if not target_user.is_vip:
                await update.message.reply_text("❌ Пользователь не VIP!")
                return
            
            target_user.is_vip = False
            target_user.vip_expires = None
            self.db.save_user(target_user)
            
            await update.message.reply_text(f"✅ VIP отозван у {target_user.first_name}")
            
            try:
                await context.bot.send_message(target_user.user_id, "💎 VIP отозван")
            except:
                pass
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

    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ /delnote [номер]")
            return
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            deleted = user_data.notes.pop(index)
            self.db.save_user(user_data)
            await update.message.reply_text(f"✅ Удалена: {deleted[:50]}...")
        else:
            await update.message.reply_text("❌ Неверный номер!")

    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        count = len(user_data.notes)
        user_data.notes = []
        self.db.save_user(user_data)
        await update.message.reply_text(f"✅ Очищено {count} заметок!")

    # ПАМЯТЬ
    
    async def memorysave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if len(context.args) < 2:
            await update.message.reply_text("🧠 /memorysave [ключ] [значение]")
            return
        key = context.args[0]
        value = " ".join(context.args[1:])
        user_data.memory_data[key] = value
        self.db.save_user(user_data)
        await update.message.reply_text(f"🧠 Сохранено: {key} = {value}")

    async def memoryget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
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
        if not user_data.memory_data:
            await update.message.reply_text("🧠 Память пуста!")
            return
        memory_text = "\n".join(f"• {k}: {v}" for k, v in user_data.memory_data.items())
        await update.message.reply_text(f"🧠 Память:\n{memory_text}")

    # УТИЛИТЫ И ИГРЫ
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not context.args:
            await update.message.reply_text("🌤️ /weather [город]")
            return
        if not OPENWEATHER_API_KEY:
            await update.message.reply_text("❌ API ключ не настроен")
            return
        city = " ".join(context.args)
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            response = requests.get(url, timeout=10).json()
            if response.get("cod") == 200:
                weather = response["weather"][0]["description"]
                temp = round(response["main"]["temp"])
                feels = round(response["main"]["feels_like"])
                humidity = response["main"]["humidity"]
                text = f"🌤️ Погода в {city}:\n🌡️ {temp}°C (ощущается {feels}°C)\n☁️ {weather.capitalize()}\n💧 Влажность: {humidity}%"
                await update.message.reply_text(text)
            else:
                await update.message.reply_text("❌ Город не найден!")
        except:
            await update.message.reply_text("❌ Ошибка API")
        await self.add_experience(user_data, 2)

    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if len(context.args) < 2:
            await update.message.reply_text("💰 /currency [из] [в]\nПример: /currency USD RUB")
            return
        if not CURRENCY_API_KEY:
            await update.message.reply_text("❌ API ключ не настроен")
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
        await self.add_experience(user_data, 2)

    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if len(context.args) < 2:
            await update.message.reply_text("🌐 /translate [язык] [текст]")
            return
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        target = context.args[0]
        text = " ".join(context.args[1:])
        try:
            response = self.gemini_model.generate_content(f"Переведи на {target}: {text}")
            await update.message.reply_text(f"🌐 {response.text}")
        except:
            await update.message.reply_text("❌ Ошибка перевода")
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
        await self.add_experience(user_data, 1)

    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        result = random.choice(["🪙 Орёл!", "🪙 Решка!"])
        await update.message.reply_text(result)
        await self.add_experience(user_data, 1)

    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        result = random.randint(1, 6)
        faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {faces[result-1]} Выпало: {result}")
        await self.add_experience(user_data, 1)

    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not context.args:
            await update.message.reply_text("🔮 /8ball [вопрос]")
            return
        answers = ["✅ Да!", "❌ Нет", "🤔 Возможно", "⏳ Позже", "🎯 Точно!", "💭 Вероятно", "🚫 Нет", "🌟 Да"]
        await update.message.reply_text(f"🔮 {random.choice(answers)}")
        await self.add_experience(user_data, 1)

    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        questions = [
            {"q": "Дней в високосном году?", "a": "366"},
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

    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not context.args:
            await update.message.reply_text("🔢 /math [выражение]")
            return
        expr = " ".join(context.args)
        try:
            allowed = set('0123456789+-*/().,= ')
            if not all(c in allowed for c in expr):
                await update.message.reply_text("❌ Только: +, -, *, /, ()")
                return
            result = eval(expr)
            await update.message.reply_text(f"🔢 {expr} = {result}")
        except:
            await update.message.reply_text("❌ Ошибка вычисления")
        await self.add_experience(user_data, 1)

    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        length = 12
        if context.args and context.args[0].isdigit():
            length = min(int(context.args[0]), 50)
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        pwd = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(f"🔐 Пароль ({length}):\n`{pwd}`\n\n⚠️ Сохрани!", parse_mode='Markdown')
        await self.add_experience(user_data, 1)

    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not context.args:
            await update.message.reply_text("📱 /qr [текст]")
            return
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}"
        await update.message.reply_text(f"📱 QR: {text}")
        await context.bot.send_photo(update.effective_chat.id, qr_url)
        await self.add_experience(user_data, 1)

    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        now = datetime.datetime.now()
        msk = pytz.timezone('Europe/Moscow')
        msk_time = now.astimezone(msk)
        await update.message.reply_text(f"⏰ UTC: {now.strftime('%H:%M:%S')}\n🇷🇺 МСК: {msk_time.strftime('%H:%M:%S')}")
        await self.add_experience(user_data, 1)

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        await update.message.reply_text(f"📅 {datetime.datetime.now().strftime('%d.%m.%Y')}")
        await self.add_experience(user_data, 1)

    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        required = user_data.level * 100
        progress = (user_data.experience / required) * 100
        text = f"🏅 {user_data.first_name}\n🆙 Уровень: {user_data.level}\n⭐ Опыт: {user_data.experience}/{required}\n📊 {progress:.1f}%\n💎 VIP: {'✅' if self.is_vip(user_data) else '❌'}"
        await update.message.reply_text(text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        info = f"🤖 BOT v2.1\nСоздатель: Ernest\nФункций: 50+\nAI: {'✅' if self.gemini_model else '❌'}\nGitHub: {'✅' if self.db.repo else '❌'}\nHosting: Render"
        await update.message.reply_text(info)
        await self.add_experience(user_data, 1)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        status = f"⚡ СТАТУС\n\n✅ Онлайн\n👥 Пользователей: {len(self.db.users)}\n📈 Команд: {len(self.db.logs)}\n🤖 Gemini: {'✅' if self.gemini_model else '❌'}"
        await update.message.reply_text(status)
        await self.add_experience(user_data, 1)

    # VIP КОМАНДЫ
    
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Ты не VIP! Свяжись с @Ernest_Kostevich")
            return
        expires = 'бессрочно'
        if user_data.vip_expires:
            try:
                expires = datetime.datetime.fromisoformat(user_data.vip_expires).strftime('%d.%m.%Y')
            except:
                pass
        await update.message.reply_text(f"💎 VIP до: {expires}")

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
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
                DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, f"🔔 {text}"],
                id=f"reminder_{user_data.user_id}_{int(time.time())}"
            )
            reminder_data = {"id": job.id, "text": text, "time": run_date.isoformat()}
            user_data.reminders.append(reminder_data)
            self.db.save_user(user_data)
            await update.message.reply_text(f"⏰ Напоминание на {minutes} мин!")
        except ValueError:
            await update.message.reply_text("❌ Используй числа!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        if not user_data.reminders:
            await update.message.reply_text("❌ Нет напоминаний!")
            return
        text = "\n".join([f"{i+1}. {r['text']}" for i, r in enumerate(user_data.reminders)])
        await update.message.reply_text(f"⏰ Напоминания:\n{text}")

    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        if not context.args:
            status = "включен" if self.maintenance_mode else "выключен"
            await update.message.reply_text(f"🛠 Режим сейчас {status}\n\n/maintenance [on/off]")
            return
        mode = context.args[0].lower()
        if mode in ['on', 'вкл']:
            self.maintenance_mode = True
            await update.message.reply_text("🛠 Режим ВКЛЮЧЕН")
        elif mode in ['off', 'выкл']:
            self.maintenance_mode = False
            await update.message.reply_text("✅ Режим ВЫКЛЮЧЕН")

    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        try:
            backup = {
                'users': self.db.users,
                'logs': self.db.logs[-100:],
                'statistics': self.db.statistics,
                'time': datetime.datetime.now().isoformat()
            }
            success = self.db.save_data("backup.json", backup)
            if success:
                await update.message.reply_text(f"✅ Backup создан!\nПользователей: {len(self.db.users)}")
            else:
                await update.message.reply_text("❌ Ошибка backup!")
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

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            await query.message.reply_text("/help для списка команд")
        elif query.data == "vip_info":
            await query.message.reply_text("💎 VIP дает расширенные возможности!\nСвяжитесь с @Ernest_Kostevich")
        elif query.data == "ai_demo":
            await query.message.reply_text("🤖 Просто напишите мне вопрос!")
        elif query.data == "my_stats":
            await query.message.reply_text("Используйте /stats")

    async def self_ping(self):
        try:
            response = requests.get(RENDER_URL, timeout=10)
            logger.info(f"Ping: {response.status_code}")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")

    async def run_bot(self):
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
        
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Error: {context.error}")
            if isinstance(context.error, Conflict):
                logger.error("Конфликт: возможно запущено несколько ботов")
                await asyncio.sleep(30)
        
        application.add_error_handler(error_handler)
        
        # Регистрация всех команд
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("ai", self.ai_command))
        application.add_handler(CommandHandler("memorydel", self.memorydel_command))
        application.add_handler(CommandHandler("grant_vip", self.grant_vip_command))
        application.add_handler(CommandHandler("revoke_vip", self.revoke_vip_command))
        application.add_handler(CommandHandler("broadcast", self.broadcast_command))
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
        
        # Пинг каждые 14 минут
        self.scheduler.add_job(
            self.self_ping,
            'interval',
            minutes=14,
            id='self_ping'
        )
        
        # Поздравление папы 3 октября в 9:00 по московскому времени
        moscow_tz = pytz.timezone('Europe/Moscow')
        self.scheduler.add_job(
            self.dad_birthday_congratulation,
            CronTrigger(month=10, day=3, hour=9, minute=0, timezone=moscow_tz),
            args=[application],
            id='dad_birthday'
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

# =============================================================================
# MAIN
# =============================================================================

async def main():
    bot = TelegramBot()
    await bot.run_bot()

# Flask для Render
app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 Bot Online | {datetime.datetime.now()}"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

if __name__ == "__main__":
    from threading import Thread
    
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(
        target=app.run, 
        kwargs={'host': '0.0.0.0', 'port': port, 'debug': False}
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(main())
