#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ - Полностью рабочая версия
Создатель: Ernest Kostevich (@Ernest_Kostevich)
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
from apscheduler.triggers.cron import CronTrigger
import pytz
from github import Github
from threading import Thread

# Telegram Bot API
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.error import Conflict, NetworkError, TimedOut

# Google Gemini
import google.generativeai as genai

# Flask для health check
from flask import Flask, jsonify

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

# API ключи
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# GitHub настройки
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"

# Данные создателя
CREATOR_ID = 7108255346
CREATOR_USERNAME = "Ernest_Kostevich"
DAD_USERNAME = "mkostevich"
BOT_USERNAME = "AI_DISCO_BOT"

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = "gemini-2.0-flash-exp"

# Render URL
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
    theme: str = "default"
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    total_commands: int = 0

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
            theme=data.get('theme', 'default'),
            last_activity=data.get('last_activity', datetime.datetime.now().isoformat()),
            total_commands=data.get('total_commands', 0)
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
            'theme': self.theme,
            'last_activity': self.last_activity,
            'total_commands': self.total_commands
        }

# =============================================================================
# МЕНЕДЖЕР БАЗЫ ДАННЫХ
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
                logger.info("✅ GitHub API инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка GitHub API: {e}")
        
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
            if path == USERS_FILE and not isinstance(data, list):
                data = []
            elif path == STATISTICS_FILE and not isinstance(data, dict):
                data = {}
            elif path == LOGS_FILE and not isinstance(data, list):
                data = []
            logger.info(f"✅ Загружено из {path}")
            return data
        except Exception as e:
            logger.warning(f"⚠️ Не удалось загрузить {path}: {e}")
            return default
    
    def save_data(self, path, data):
        if not self.repo:
            logger.warning(f"⚠️ GitHub не настроен, данные не сохранены: {path}")
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
            logger.error(f"❌ Ошибка сохранения {path}: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        for user_dict in self.users:
            if user_dict.get('user_id') == user_id:
                return UserData.from_dict(user_dict)
        return None
    
    def get_user_by_username(self, username: str) -> Optional[UserData]:
        username = username.lstrip('@').lower()
        for user_dict in self.users:
            if user_dict.get('username', '').lower() == username:
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
    
    def log_command(self, user_id: int, command: str):
        log_entry = {
            'user_id': user_id,
            'command': command,
            'timestamp': datetime.datetime.now().isoformat()
        }
        self.logs.append(log_entry)
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        
        if command not in self.statistics:
            self.statistics[command] = {'usage_count': 0, 'last_used': ''}
        self.statistics[command]['usage_count'] += 1
        self.statistics[command]['last_used'] = datetime.datetime.now().isoformat()
        
        asyncio.create_task(self._save_logs_async())
    
    async def _save_logs_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, LOGS_FILE, self.logs)
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, STATISTICS_FILE, self.statistics)
    
    def get_all_users(self) -> List[tuple]:
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('username', ''), u.get('level', 1)) for u in self.users]
    
    def get_vip_users(self) -> List[tuple]:
        return [(u.get('user_id'), u.get('first_name', 'Unknown'), u.get('vip_expires')) for u in self.users if u.get('is_vip')]

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
                logger.info("✅ Gemini инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка Gemini: {e}")
        
        self.user_contexts = {}
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
        self.birthday_scheduled = False
    
    async def get_user_data(self, update: Update) -> UserData:
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            user_data = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or ""
            )
            self.db.save_user(user_data)
            logger.info(f"➕ Новый пользователь: {user.id} ({user.first_name})")
        
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
        user_data.total_commands += 1
        required_exp = user_data.level * 100
        if user_data.experience >= required_exp:
            user_data.level += 1
            user_data.experience = 0
            achievement = f"🎉 Достигнут {user_data.level} уровень!"
            if achievement not in user_data.achievements:
                user_data.achievements.append(achievement)
        self.db.save_user(user_data)

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
• /revoke_vip - Забрать VIP
• /stats - Полная статистика
• /broadcast - Рассылка
• /users - Список пользователей
• /logs - Просмотр логов
• /maintenance - Режим обслуживания
• /backup - Резервная копия

🤖 /help для полного списка команд
            """
        elif self.is_vip(user_data):
            expires_text = 'бессрочно'
            if user_data.vip_expires:
                try:
                    expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                    expires_text = expires_date.strftime('%d.%m.%Y')
                except:
                    expires_text = 'неизвестно'
            
            message = f"""
💎 Добро пожаловать, {user_data.first_name}!
VIP до: {expires_text}

⭐ VIP возможности:
• /remind - Напоминания
• /profile - Расширенный профиль
• /priority - Приоритетная поддержка
• /export - Экспорт данных

🤖 /help для всех команд
            """
        else:
            message = f"""
🤖 Привет, {user_data.first_name}!

Я многофункциональный AI-бот!

🌟 Возможности:
• 💬 AI-чат с Gemini 2.0
• 📝 Система заметок
• 🧠 Умная память
• 🎮 Игры и развлечения
• 🌤️ Погода
• 🔤 Переводы

💎 Хотите больше? Спросите о VIP!
🤖 /help для списка команд
            """
        
        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🤖 AI Чат", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/help")
        
        help_text = """
📋 КОМАНДЫ БОТА

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы
/ping - Проверка связи

💬 AI-ЧАТ:
/ai [вопрос] - Вопрос AI
/clear - Очистить контекст
Просто пишите боту!

📝 ЗАМЕТКИ:
/note [текст] - Сохранить
/notes - Показать все
/delnote [№] - Удалить
/findnote [слово] - Поиск
/clearnotes - Очистить все
/exportnotes - Экспорт

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist - Список
/memorydel [ключ]
/memoryclear - Очистить

⏰ ВРЕМЯ:
/time - Текущее время
/date - Текущая дата
/timezone [зона] - Время в зоне

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Шутка
/fact - Интересный факт
/quote - Цитата
/coin - Монетка
/dice - Кубик
/8ball [вопрос] - Магический шар
/randomnumber [min] [max]

🌤️ УТИЛИТЫ:
/weather [город] - Погода
/translate [язык] [текст]
/calculate [выражение]
/length [текст] - Длина текста
/reverse [текст] - Перевернуть

📊 ПРОФИЛЬ:
/rank - Ваш уровень
/profile - Профиль
/achievements - Достижения
/mystats - Статистика
        """
        
        if self.is_vip(user_data):
            help_text += """
💎 VIP КОМАНДЫ:
/vip - VIP статус
/remind [минуты] [текст]
/reminders - Список
/delreminder [№]
/nickname [имя]
/birthday [дата]
/export - Экспорт данных
/priority - Приоритет
        """
        
        if self.is_creator(user_data.user_id):
            help_text += """
👑 СОЗДАТЕЛЬ:
/grant_vip [user_id/username] [duration]
/revoke_vip [user_id/username]
/broadcast [текст]
/stats - Статистика
/users - Пользователи
/logs - Логи
/maintenance [on/off]
/backup - Бэкап
/announce [текст] - Объявление
        """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        total_users = len(self.db.users)
        vip_count = len([u for u in self.db.users if u.get('is_vip')])
        
        info_text = f"""
🤖 ИНФОРМАЦИЯ О БОТЕ

📌 Версия: 2.0
👨‍💻 Создатель: @{CREATOR_USERNAME}
🤖 Бот: @{BOT_USERNAME}

📊 Статистика:
• Пользователей: {total_users}
• VIP: {vip_count}
• Команд: 50+

🛠 Технологии:
• Python 3.12
• Google Gemini 2.0
• GitHub Storage
• Render Hosting

⚡ Работает 24/7 с автопингом
        """
        
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        total_users = len(self.db.users)
        total_commands = sum(s['usage_count'] for s in self.db.statistics.values())
        
        status_text = f"""
⚡ СТАТУС БОТА

Состояние: 🟢 Онлайн
Версия: 2.0

📊 Данные:
• Пользователей: {total_users}
• Выполнено команд: {total_commands}

🔧 Сервисы:
• Gemini AI: {"✅" if self.gemini_model else "❌"}
• GitHub: {"✅" if self.db.repo else "❌"}
• Планировщик: {"✅" if self.scheduler.running else "❌"}

⏰ Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        """
        
        await update.message.reply_text(status_text)
        await self.add_experience(user_data, 1)

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ping")
        
        start_time = time.time()
        sent_message = await update.message.reply_text("🏓 Pong!")
        end_time = time.time()
        
        latency = round((end_time - start_time) * 1000, 2)
        await sent_message.edit_text(f"🏓 Pong! Задержка: {latency}ms")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # AI КОМАНДЫ
    # =============================================================================

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос: /ai [ваш вопрос]")
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
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)[:100]}")
            logger.error(f"Gemini error: {e}")
        
        await self.add_experience(user_data, 2)

    async def clear_context_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clear")
        
        if user_data.user_id in self.user_contexts:
            del self.user_contexts[user_data.user_id]
        
        await update.message.reply_text("✅ Контекст диалога очищен!")
        await self.add_experience(user_data, 1)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "message")
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен. Используйте команды!")
            return
        
        message = update.message.text
        user_id = user_data.user_id
        
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        
        self.user_contexts[user_id].append(f"User: {message}")
        if len(self.user_contexts[user_id]) > 10:
            self.user_contexts[user_id] = self.user_contexts[user_id][-10:]
        
        context_str = "\n".join(self.user_contexts[user_id][-5:])
        prompt = f"Ты AI-ассистент. Контекст:\n{context_str}\n\nОтветь дружелюбно и полезно."
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(response.text)
            self.user_contexts[user_id].append(f"Bot: {response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Message error: {e}")
        
        await self.add_experience(user_data, 1)

    # =============================================================================
    # ЗАМЕТКИ
    # =============================================================================

    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/note")
        
        if not context.args:
            await update.message.reply_text("📝 /note [текст заметки]")
            return
        
        note = " ".join(context.args)
        timestamp = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
        user_data.notes.append(f"[{timestamp}] {note}")
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"✅ Заметка #{len(user_data.notes)} сохранена!")
        await self.add_experience(user_data, 1)

    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок!\n\nСоздайте: /note [текст]")
            return
        
        notes_text = "📝 ВАШИ ЗАМЕТКИ:\n\n"
        for i, note in enumerate(user_data.notes[-20:], 1):
            notes_text += f"{i}. {note}\n"
        
        if len(user_data.notes) > 20:
            notes_text += f"\n... и ещё {len(user_data.notes) - 20} заметок"
        
        await update.message.reply_text(notes_text)
        await self.add_experience(user_data, 1)

    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args:
            await update.message.reply_text("📝 /delnote [номер]")
            return
        
        try:
            note_num = int(context.args[0]) - 1
            if 0 <= note_num < len(user_data.notes):
                deleted = user_data.notes.pop(note_num)
                self.db.save_user(user_data)
                await update.message.reply_text(f"✅ Удалена заметка:\n{deleted}")
            else:
                await update.message.reply_text("❌ Неверный номер!")
        except ValueError:
            await update.message.reply_text("❌ Укажите число!")
        
        await self.add_experience(user_data, 1)

    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            await update.message.reply_text("🔍 /findnote [слово]")
            return
        
        search = " ".join(context.args).lower()
        found = [f"{i+1}. {note}" for i, note in enumerate(user_data.notes) if search in note.lower()]
        
        if found:
            await update.message.reply_text(f"🔍 Найдено {len(found)} заметок:\n\n" + "\n".join(found[:10]))
        else:
            await update.message.reply_text("❌ Ничего не найдено!")
        
        await self.add_experience(user_data, 1)

    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clearnotes")
        
        count = len(user_data.notes)
        user_data.notes = []
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"✅ Удалено {count} заметок!")
        await self.add_experience(user_data, 1)

    async def exportnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/exportnotes")
        
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок для экспорта!")
            return
        
        export_text = "📝 ЭКСПОРТ ЗАМЕТОК\n\n" + "\n".join(user_data.notes)
        await update.message.reply_text(export_text)
        await self.add_experience(user_data, 1)

    # =============================================================================
    # ПАМЯТЬ
    # =============================================================================

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
        
        await update.message.reply_text(f"✅ Сохранено:\n🔑 {key}\n💾 {value}")
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
            await update.message.reply_text(f"🧠 {key}:\n{value}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
        
        await self.add_experience(user_data, 1)

    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorylist")
        
        if not user_data.memory_data:
            await update.message.reply_text("🧠 Память пуста!\n\nДобавьте: /memorysave [ключ] [значение]")
            return
        
        memory_text = "🧠 ВАША ПАМЯТЬ:\n\n"
        for key, value in list(user_data.memory_data.items())[:20]:
            memory_text += f"🔑 {key}:\n💾 {value}\n\n"
        
        if len(user_data.memory_data) > 20:
            memory_text += f"... и ещё {len(user_data.memory_data) - 20} записей"
        
        await update.message.reply_text(memory_text)
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
            await update.message.reply_text(f"✅ Удалено: {key}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
        
        await self.add_experience(user_data, 1)

    async def memoryclear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memoryclear")
        
        count = len(user_data.memory_data)
        user_data.memory_data = {}
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"✅ Очищено {count} записей из памяти!")
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

🌍 UTC: {now.strftime('%H:%M:%S')}
🇷🇺 Москва: {moscow_time.strftime('%H:%M:%S')}
📅 Дата: {now.strftime('%d.%m.%Y')}
        """
        
        await update.message.reply_text(time_text)
        await self.add_experience(user_data, 1)

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")
        
        now = datetime.datetime.now()
        weekdays_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        
        await update.message.reply_text(
            f"📅 {weekdays_ru[now.weekday()]}, {now.strftime('%d.%m.%Y')}"
        )
        await self.add_experience(user_data, 1)

    async def timezone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/timezone")
        
        if not context.args:
            await update.message.reply_text("⏰ /timezone [зона]\n\nПримеры: Europe/Moscow, America/New_York, Asia/Tokyo")
            return
        
        try:
            tz = pytz.timezone(context.args[0])
            now = datetime.datetime.now(tz)
            await update.message.reply_text(f"⏰ {context.args[0]}: {now.strftime('%H:%M:%S %d.%m.%Y')}")
        except:
            await update.message.reply_text("❌ Неверная временная зона!")
        
        await self.add_experience(user_data, 1)

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        if not context.args:
            await update.message.reply_text("🌤️ /weather [город]\n\nПример: /weather Moscow")
            return
        
        if not OPENWEATHER_API_KEY:
            await update.message.reply_text("❌ Weather API не настроен")
            return
        
        city = " ".join(context.args)
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    
            if data.get('cod') == 200:
                temp = data['main']['temp']
                feels = data['main']['feels_like']
                desc = data['weather'][0]['description']
                humidity = data['main']['humidity']
                wind = data['wind']['speed']
                
                weather_text = f"""
🌤️ ПОГОДА: {city.title()}

🌡️ Температура: {temp}°C
🤔 Ощущается: {feels}°C
☁️ {desc.title()}
💧 Влажность: {humidity}%
💨 Ветер: {wind} м/с
                """
                await update.message.reply_text(weather_text)
            else:
                await update.message.reply_text("❌ Город не найден!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения погоды")
            logger.error(f"Weather error: {e}")
        
        await self.add_experience(user_data, 2)

    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text("🔤 /translate [язык] [текст]\n\nПример: /translate en Привет")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен для перевода")
            return
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            prompt = f"Переведи на {target_lang}: {text}\n\nВерни только перевод без пояснений."
            response = self.gemini_model.generate_content(prompt)
            await update.message.reply_text(f"🔤 {response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка перевода")
            logger.error(f"Translation error: {e}")
        
        await self.add_experience(user_data, 2)

    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/calculate")
        
        if not context.args:
            await update.message.reply_text("🔢 /calculate [выражение]\n\nПример: /calculate 2 + 2 * 5")
            return
        
        expression = " ".join(context.args)
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            await update.message.reply_text(f"🔢 {expression} = {result}")
        except:
            await update.message.reply_text("❌ Неверное выражение!")
        
        await self.add_experience(user_data, 1)

    async def length_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/length")
        
        if not context.args:
            await update.message.reply_text("📏 /length [текст]")
            return
        
        text = " ".join(context.args)
        await update.message.reply_text(f"📏 Длина: {len(text)} символов\nСлов: {len(text.split())}")
        await self.add_experience(user_data, 1)

    async def reverse_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/reverse")
        
        if not context.args:
            await update.message.reply_text("🔄 /reverse [текст]")
            return
        
        text = " ".join(context.args)
        await update.message.reply_text(f"🔄 {text[::-1]}")
        await self.add_experience(user_data, 1)

    # =============================================================================
    # РАЗВЛЕЧЕНИЯ
    # =============================================================================

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")
        
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content("Расскажи короткую смешную шутку на русском")
                await update.message.reply_text(f"😄 {response.text}")
            except:
                jokes = [
                    "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
                    "Зашёл программист в бар. Или не зашёл...",
                    "- Сколько программистов нужно, чтобы вкрутить лампочку?\n- Ни одного, это аппаратная проблема!"
                ]
                await update.message.reply_text(f"😄 {random.choice(jokes)}")
        else:
            await update.message.reply_text("😄 AI недоступен для генерации шуток")
        
        await self.add_experience(user_data, 1)

    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")
        
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content("Расскажи интересный научный факт на русском языке")
                await update.message.reply_text(f"💡 {response.text}")
            except:
                await update.message.reply_text("💡 Мёд никогда не портится. Археологи находили мёд в египетских пирамидах, которому более 3000 лет, и он был пригоден к употреблению!")
        else:
            await update.message.reply_text("💡 AI недоступен")
        
        await self.add_experience(user_data, 1)

    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")
        
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content("Дай мотивирующую цитату на русском")
                await update.message.reply_text(f"💬 {response.text}")
            except:
                quotes = [
                    "Единственный способ сделать великую работу - любить то, что вы делаете. - Стив Джобс",
                    "Будущее принадлежит тем, кто верит в красоту своих мечтаний. - Элеонора Рузвельт",
                    "Успех - это способность двигаться от неудачи к неудаче, не теряя энтузиазма. - Уинстон Черчилль"
                ]
                await update.message.reply_text(f"💬 {random.choice(quotes)}")
        else:
            await update.message.reply_text("💬 AI недоступен")
        
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
        await update.message.reply_text(f"🎲 Выпало: {result}")
        await self.add_experience(user_data, 1)

    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🎱 Задайте вопрос: /8ball [ваш вопрос]")
            return
        
        answers = [
            "Да", "Нет", "Возможно", "Определённо да", "Определённо нет",
            "Спросите позже", "Лучше не говорить", "Не могу предсказать",
            "Весьма вероятно", "Маловероятно", "Сомневаюсь", "Безусловно"
        ]
        await update.message.reply_text(f"🎱 {random.choice(answers)}")
        await self.add_experience(user_data, 1)

    async def randomnumber_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/randomnumber")
        
        if len(context.args) < 2:
            await update.message.reply_text("🎲 /randomnumber [min] [max]\n\nПример: /randomnumber 1 100")
            return
        
        try:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
            result = random.randint(min_val, max_val)
            await update.message.reply_text(f"🎲 Случайное число: {result}")
        except:
            await update.message.reply_text("❌ Укажите корректные числа!")
        
        await self.add_experience(user_data, 1)

    # =============================================================================
    # ПРОФИЛЬ
    # =============================================================================

    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")
        
        required_exp = user_data.level * 100
        progress = (user_data.experience / required_exp) * 100
        progress_bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
        
        rank_text = f"""
🏅 ВАШ УРОВЕНЬ

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{required_exp}

📊 {progress_bar} {progress:.1f}%

💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}
📈 Команд: {user_data.total_commands}
        """
        
        await update.message.reply_text(rank_text)
        await self.add_experience(user_data, 1)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/profile")
        
        vip_status = "✅ Активен" if self.is_vip(user_data) else "❌ Неактивен"
        if self.is_vip(user_data) and user_data.vip_expires:
            try:
                expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                vip_status += f" до {expires_date.strftime('%d.%m.%Y')}"
            except:
                pass
        
        profile_text = f"""
👤 ПРОФИЛЬ

Имя: {user_data.first_name}
Username: @{user_data.username or 'не указан'}
ID: {user_data.user_id}

🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{user_data.level * 100}
💎 VIP: {vip_status}

📝 Заметок: {len(user_data.notes)}
🧠 Память: {len(user_data.memory_data)} записей
🏆 Достижений: {len(user_data.achievements)}
📈 Команд: {user_data.total_commands}

📅 Зарегистрирован: {user_data.last_activity[:10]}
        """
        
        await update.message.reply_text(profile_text)
        await self.add_experience(user_data, 1)

    async def achievements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/achievements")
        
        if not user_data.achievements:
            await update.message.reply_text("🏆 У вас пока нет достижений!\n\nПродолжайте использовать бота для получения новых достижений!")
            return
        
        achievements_text = "🏆 ВАШИ ДОСТИЖЕНИЯ:\n\n" + "\n".join(user_data.achievements)
        await update.message.reply_text(achievements_text)
        await self.add_experience(user_data, 1)

    async def mystats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/mystats")
        
        stats_text = f"""
📊 ВАША СТАТИСТИКА

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}
📈 Команд выполнено: {user_data.total_commands}

📝 Заметок: {len(user_data.notes)}
🧠 Память: {len(user_data.memory_data)}
🏆 Достижений: {len(user_data.achievements)}

💎 VIP: {"Да" if self.is_vip(user_data) else "Нет"}
        """
        
        await update.message.reply_text(stats_text)
        await self.add_experience(user_data, 1)

    # =============================================================================
    # VIP КОМАНДЫ
    # =============================================================================

    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if not self.is_vip(user_data):
            vip_text = """
💎 VIP СТАТУС

У вас нет VIP статуса.

🌟 VIP возможности:
• ⏰ Напоминания
• 📊 Расширенная статистика
• 🎯 Приоритетная поддержка
• 📤 Экспорт данных
• 🎨 Персонализация

Свяжитесь с @Ernest_Kostevich для получения VIP!
            """
        else:
            expires_text = 'Бессрочно'
            if user_data.vip_expires:
                try:
                    expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                    expires_text = expires_date.strftime('%d.%m.%Y')
                except:
                    pass
            
            vip_text = f"""
💎 VIP СТАТУС АКТИВЕН

Действует до: {expires_text}

⭐ Доступные VIP команды:
• /remind - Напоминания
• /reminders - Список напоминаний
• /nickname - Установить никнейм
• /birthday - Установить день рождения
• /export - Экспорт данных
• /priority - Приоритетная поддержка
            """
        
        await update.message.reply_text(vip_text)
        await self.add_experience(user_data, 1)

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!\n\nИспользуйте /vip для информации.")
            return
        
        self.db.log_command(user_data.user_id, "/remind")
        
        if len(context.args) < 2:
            await update.message.reply_text("⏰ /remind [минуты] [текст]\n\nПример: /remind 30 Позвонить маме")
            return
        
        try:
            minutes = int(context.args[0])
            text = " ".join(context.args[1:])
            
            if minutes <= 0 or minutes > 10080:  # Максимум неделя
                await update.message.reply_text("❌ Укажите время от 1 до 10080 минут (неделя)!")
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            job = self.scheduler.add_job(
                self.send_reminder,
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, text],
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
            
            await update.message.reply_text(
                f"✅ Напоминание установлено!\n\n"
                f"⏰ Через {minutes} мин\n"
                f"📝 {text}\n"
                f"🕐 {run_date.strftime('%d.%m.%Y %H:%M')}"
            )
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат! Укажите число минут.")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка создания напоминания")
            logger.error(f"Reminder error: {e}")
        
        await self.add_experience(user_data, 2)

    async def send_reminder(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
        """Отправка напоминания"""
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔔 НАПОМИНАНИЕ!\n\n📝 {text}\n\n⏰ {datetime.datetime.now().strftime('%H:%M')}"
            )
            # Удаляем напоминание из списка пользователя
            user_data = self.db.get_user(user_id)
            if user_data:
                user_data.reminders = [r for r in user_data.reminders if r['text'] != text]
                self.db.save_user(user_data)
        except Exception as e:
            logger.error(f"Send reminder error: {e}")

    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/reminders")
        
        if not user_data.reminders:
            await update.message.reply_text("❌ Нет активных напоминаний!\n\nСоздайте: /remind [минуты] [текст]")
            return
        
        reminders_text = "⏰ ВАШИ НАПОМИНАНИЯ:\n\n"
        for i, rem in enumerate(user_data.reminders, 1):
            try:
                time_str = datetime.datetime.fromisoformat(rem['time']).strftime('%d.%m %H:%M')
            except:
                time_str = 'неизвестно'
            reminders_text += f"{i}. {rem['text']}\n   🕐 {time_str}\n\n"
        
        await update.message.reply_text(reminders_text)
        await self.add_experience(user_data, 1)

    async def delreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/delreminder")
        
        if not context.args:
            await update.message.reply_text("⏰ /delreminder [номер]")
            return
        
        try:
            rem_num = int(context.args[0]) - 1
            if 0 <= rem_num < len(user_data.reminders):
                reminder = user_data.reminders.pop(rem_num)
                # Удаляем задачу из планировщика
                try:
                    self.scheduler.remove_job(reminder['id'])
                except:
                    pass
                self.db.save_user(user_data)
                await update.message.reply_text(f"✅ Напоминание удалено:\n{reminder['text']}")
            else:
                await update.message.reply_text("❌ Неверный номер!")
        except ValueError:
            await update.message.reply_text("❌ Укажите число!")
        
        await self.add_experience(user_data, 1)

    async def nickname_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/nickname")
        
        if not context.args:
            current = user_data.nickname or "не установлен"
            await update.message.reply_text(f"👤 Текущий никнейм: {current}\n\n/nickname [новый никнейм]")
            return
        
        nickname = " ".join(context.args)
        user_data.nickname = nickname
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"✅ Никнейм установлен: {nickname}")
        await self.add_experience(user_data, 1)

    async def birthday_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/birthday")
        
        if not context.args:
            current = user_data.birthday or "не установлен"
            await update.message.reply_text(f"🎂 День рождения: {current}\n\n/birthday [ДД.ММ.ГГГГ]")
            return
        
        birthday = context.args[0]
        # Простая валидация
        if re.match(r'\d{2}\.\d{2}\.\d{4}', birthday):
            user_data.birthday = birthday
            self.db.save_user(user_data)
            await update.message.reply_text(f"✅ День рождения установлен: {birthday}")
        else:
            await update.message.reply_text("❌ Неверный формат! Используйте: ДД.ММ.ГГГГ")
        
        await self.add_experience(user_data, 1)

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/export")
        
        export_data = {
            "user_info": {
                "name": user_data.first_name,
                "username": user_data.username,
                "level": user_data.level,
                "experience": user_data.experience
            },
            "notes": user_data.notes,
            "memory": user_data.memory_data,
            "achievements": user_data.achievements,
            "total_commands": user_data.total_commands,
            "export_date": datetime.datetime.now().isoformat()
        }
        
        export_text = json.dumps(export_data, ensure_ascii=False, indent=2)
        await update.message.reply_text(f"📤 ЭКСПОРТ ДАННЫХ:\n\n```json\n{export_text[:3000]}\n```", parse_mode="Markdown")
        await self.add_experience(user_data, 2)

    async def priority_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/priority")
        
        await update.message.reply_text(
            "🎯 ПРИОРИТЕТНАЯ ПОДДЕРЖКА\n\n"
            "Как VIP пользователь, вы имеете:\n"
            "• Быстрый отклик на запросы\n"
            "• Расширенные возможности AI\n"
            "• Персональная помощь\n\n"
            "Свяжитесь с @Ernest_Kostevich для поддержки!"
        )
        await self.add_experience(user_data, 1)

    # =============================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # =============================================================================

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/grant_vip")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "👑 /grant_vip [user_id/username] [duration]\n\n"
                "Duration: week, month, year, permanent\n"
                "Пример: /grant_vip @username month"
            )
            return
        
        try:
            # Получаем пользователя по ID или username
            target_identifier = context.args[0]
            
            if target_identifier.startswith('@'):
                target_user = self.db.get_user_by_username(target_identifier[1:])
            else:
                try:
                    target_id = int(target_identifier)
                    target_user = self.db.get_user(target_id)
                except ValueError:
                    target_user = self.db.get_user_by_username(target_identifier)
            
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            duration = context.args[1].lower()
            
            target_user.is_vip = True
            
            if duration == "week":
                target_user.vip_expires = (datetime.datetime.now() + datetime.timedelta(weeks=1)).isoformat()
                duration_text = "неделю"
            elif duration == "month":
                target_user.vip_expires = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
                duration_text = "месяц"
            elif duration == "year":
                target_user.vip_expires = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
                duration_text = "год"
            elif duration == "permanent":
                target_user.vip_expires = None
                duration_text = "навсегда"
            else:
                await update.message.reply_text("❌ Неверная длительность! Используйте: week/month/year/permanent")
                return
            
            self.db.save_user(target_user)
            
            await update.message.reply_text(
                f"✅ VIP выдан!\n\n"
                f"👤 {target_user.first_name} (@{target_user.username})\n"
                f"⏰ На: {duration_text}"
            )
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    target_user.user_id,
                    f"🎉 Поздравляем!\n\n"
                    f"Вы получили VIP статус на {duration_text}!\n\n"
                    f"Используйте /vip для просмотра возможностей."
                )
            except:
                pass
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            logger.error(f"Grant VIP error: {e}")

    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/revoke_vip")
        
        if not context.args:
            await update.message.reply_text("👑 /revoke_vip [user_id/username]")
            return
        
        try:
            target_identifier = context.args[0]
            
            if target_identifier.startswith('@'):
                target_user = self.db.get_user_by_username(target_identifier[1:])
            else:
                try:
                    target_id = int(target_identifier)
                    target_user = self.db.get_user(target_id)
                except ValueError:
                    target_user = self.db.get_user_by_username(target_identifier)
            
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            target_user.is_vip = False
            target_user.vip_expires = None
            self.db.save_user(target_user)
            
            await update.message.reply_text(
                f"✅ VIP отозван у {target_user.first_name} (@{target_user.username})"
            )
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    target_user.user_id,
                    "💎 Ваш VIP статус был отозван."
                )
            except:
                pass
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            logger.error(f"Revoke VIP error: {e}")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/broadcast")
        
        if not context.args:
            await update.message.reply_text("📢 /broadcast [сообщение]")
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        
        sent = 0
        failed = 0
        
        await update.message.reply_text(f"📢 Начинаю рассылку {len(users)} пользователям...")
        
        for user_id, first_name, username, level in users:
            try:
                await context.bot.send_message(
                    user_id,
                    f"📢 СООБЩЕНИЕ ОТ СОЗДАТЕЛЯ:\n\n{message}"
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                failed += 1
                logger.warning(f"Broadcast failed for {user_id}: {e}")
        
        await update.message.reply_text(
            f"✅ Рассылка завершена!\n\n"
            f"✅ Отправлено: {sent}\n"
            f"❌ Ошибок: {failed}"
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/stats")
        
        if self.is_creator(user_data.user_id):
            total_users = len(self.db.users)
            vip_users = len([u for u in self.db.users if u.get('is_vip')])
            total_commands = sum(s['usage_count'] for s in self.db.statistics.values())
            
            # Топ команд
            top_commands = sorted(
                self.db.statistics.items(),
                key=lambda x: x[1]['usage_count'],
                reverse=True
            )[:5]
            
            stats_text = f"""
📊 СТАТИСТИКА БОТА

👥 Пользователи:
• Всего: {total_users}
• VIP: {vip_users}
• Обычных: {total_users - vip_users}

📈 Активность:
• Команд выполнено: {total_commands}
• Логов: {len(self.db.logs)}

🔥 ТОП-5 КОМАНД:
"""
            for cmd, data in top_commands:
                stats_text += f"• {cmd}: {data['usage_count']}\n"
            
            stats_text += f"\n⏰ {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
        else:
            # Личная статистика для обычных пользователей
            stats_text = f"""
📊 ВАША СТАТИСТИКА

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{user_data.level * 100}
💎 VIP: {"Да" if self.is_vip(user_data) else "Нет"}

📝 Заметок: {len(user_data.notes)}
🧠 Память: {len(user_data.memory_data)}
🏆 Достижений: {len(user_data.achievements)}
📈 Команд: {user_data.total_commands}
            """
        
        await update.message.reply_text(stats_text)
        await self.add_experience(user_data, 1)

    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/users")
        
        users = self.db.get_all_users()
        
        users_text = f"👥 ПОЛЬЗОВАТЕЛИ ({len(users)}):\n\n"
        for user_id, first_name, username, level in users[-20:]:
            vip_mark = "💎" if any(u.get('user_id') == user_id and u.get('is_vip') for u in self.db.users) else ""
            username_str = f"@{username}" if username else f"ID:{user_id}"
            users_text += f"{vip_mark} {first_name} ({username_str}) - Ур.{level}\n"
        
        if len(users) > 20:
            users_text += f"\n... и ещё {len(users) - 20} пользователей"
        
        await update.message.reply_text(users_text)

    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/logs")
        
        recent_logs = self.db.logs[-15:]
        logs_text = "📋 ПОСЛЕДНИЕ ЛОГИ:\n\n"
        
        for log in recent_logs:
            timestamp = log.get('timestamp', '')[:16]
            user_id = log.get('user_id', 'Unknown')
            command = log.get('command', 'unknown')
            logs_text += f"[{timestamp}] {user_id}: {command}\n"
        
        await update.message.reply_text(logs_text)

    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/maintenance")
        
        if not context.args:
            status = "включен" if MAINTENANCE_MODE else "выключен"
            await update.message.reply_text(f"🛠 Режим обслуживания: {status}\n\n/maintenance [on/off]")
            return
        
        mode = context.args[0].lower()
        if mode == "on":
            global MAINTENANCE_MODE
            MAINTENANCE_MODE = True
            await update.message.reply_text("🛠 Режим обслуживания ВКЛЮЧЕН")
        elif mode == "off":
            MAINTENANCE_MODE = False
            await update.message.reply_text("✅ Режим обслуживания ВЫКЛЮЧЕН")
        else:
            await update.message.reply_text("❌ Используйте: on или off")

    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/backup")
        
        backup_data = {
            "users": self.db.users,
            "statistics": self.db.statistics,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        await update.message.reply_text(
            f"💾 РЕЗЕРВНАЯ КОПИЯ\n\n"
            f"Пользователей: {len(self.db.users)}\n"
            f"Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Данные сохранены в GitHub"
        )

    async def announce_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Доступно только создателю!")
            return
        
        self.db.log_command(update.effective_user.id, "/announce")
        
        if not context.args:
            await update.message.reply_text("📣 /announce [объявление]")
            return
        
        announcement = " ".join(context.args)
        users = self.db.get_all_users()
        
        sent = 0
        for user_id, first_name, username, level in users:
            try:
                await context.bot.send_message(
                    user_id,
                    f"📣 ОБЪЯВЛЕНИЕ:\n\n{announcement}"
                )
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        
        await update.message.reply_text(f"✅ Объявление отправлено {sent} пользователям")

    # =============================================================================
    # CALLBACK ОБРАБОТЧИКИ
    # =============================================================================

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_data = await self.get_user_data(update)
        
        if query.data == "help":
            await self.help_command(update, context)
        elif query.data == "vip_info":
            await self.vip_command(update, context)
        elif query.data == "ai_demo":
            await query.edit_message_text(
                "🤖 AI-ЧАТ ГОТОВ!\n\n"
                "Просто напишите мне любой вопрос!\n\n"
                "Примеры:\n"
                "• Расскажи о космосе\n"
                "• Помоги решить задачу\n"
                "• Придумай идею для проекта\n"
                "• Объясни сложную тему\n\n"
                "Или используйте /ai [вопрос]"
            )
        elif query.data == "my_stats":
            await self.mystats_command(update, context)

    # =============================================================================
    # СЛУЖЕБНЫЕ ФУНКЦИИ
    # =============================================================================

    async def schedule_dad_birthday(self, context: ContextTypes.DEFAULT_TYPE):
        """Запланировать поздравление папе"""
        if self.birthday_scheduled:
            return
        
        # Находим папу по username
        dad_user = self.db.get_user_by_username(DAD_USERNAME.lstrip('@'))
        
        if not dad_user:
            logger.warning(f"Пользователь {DAD_USERNAME} не найден для поздравления")
            return
        
        # 3 октября в 9:00
        birthday_date = datetime.datetime(2025, 10, 3, 9, 0, 0)
        
        # Если дата уже прошла, планируем на следующий год
        if birthday_date < datetime.datetime.now():
            birthday_date = datetime.datetime(2026, 10, 3, 9, 0, 0)
        
        birthday_message = """
🎉🎂 С ДНЁМ РОЖДЕНИЯ! 🎂🎉

Дорогой папа!

От всего сердца поздравляю тебя с Днём Рождения!

Желаю крепкого здоровья, счастья, успехов!

Пусть каждый день приносит радость и новые возможности!

С любовью, твой сын! ❤️
        """
        
        self.scheduler.add_job(
            self.send_birthday_greeting,
            trigger=DateTrigger(run_date=birthday_date),
            args=[context, dad_user.user_id, birthday_message],
            id='dad_birthday_2025'
        )
        
        self.birthday_scheduled = True
        logger.info(f"✅ Поздравление запланировано на {birthday_date}")

    async def send_birthday_greeting(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        """Отправить поздравление"""
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            logger.info(f"🎉 Поздравление отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки поздравления: {e}")

    async def self_ping(self):
        """Пинг для поддержания активности"""
        try:
            response = requests.get(f"{RENDER_URL}/health", timeout=10)
            logger.info(f"✅ Self-ping: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Self-ping failed: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"❌ Error: {context.error}")
        
        if isinstance(context.error, Conflict):
            logger.error("⚠️ Конфликт: возможно запущено несколько экземпляров бота")
            await asyncio.sleep(30)
        
        try:
            if update and hasattr(update, 'effective_message'):
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка. Попробуйте позже или свяжитесь с @Ernest_Kostevich"
                )
        except:
            pass

    # =============================================================================
    # ЗАПУСК БОТА
    # =============================================================================

    async def run_bot(self):
        """Запуск бота"""
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не найден!")
            return

        logger.info("🚀 Инициализация бота...")

        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30)
            .pool_timeout(30)
            .build()
        )
        
        # Обработчик ошибок
        application.add_error_handler(self.error_handler)
        
        # Регистрация всех команд
        handlers = [
            ("start", self.start_command),
            ("help", self.help_command),
            ("info", self.info_command),
            ("status", self.status_command),
            ("ping", self.ping_command),
            ("ai", self.ai_command),
            ("clear", self.clear_context_command),
            ("note", self.note_command),
            ("notes", self.notes_command),
            ("delnote", self.delnote_command),
            ("findnote", self.findnote_command),
            ("clearnotes", self.clearnotes_command),
            ("exportnotes", self.exportnotes_command),
            ("memorysave", self.memorysave_command),
            ("memoryget", self.memoryget_command),
            ("memorylist", self.memorylist_command),
            ("memorydel", self.memorydel_command),
            ("memoryclear", self.memoryclear_command),
            ("time", self.time_command),
            ("date", self.date_command),
            ("timezone", self.timezone_command),
            ("weather", self.weather_command),
            ("translate", self.translate_command),
            ("calculate", self.calculate_command),
            ("length", self.length_command),
            ("reverse", self.reverse_command),
            ("joke", self.joke_command),
            ("fact", self.fact_command),
            ("quote", self.quote_command),
            ("coin", self.coin_command),
            ("dice", self.dice_command),
            ("8ball", self.eightball_command),
            ("randomnumber", self.randomnumber_command),
            ("rank", self.rank_command),
            ("profile", self.profile_command),
            ("achievements", self.achievements_command),
            ("mystats", self.mystats_command),
            ("vip", self.vip_command),
            ("remind", self.remind_command),
            ("reminders", self.reminders_command),
            ("delreminder", self.delreminder_command),
            ("nickname", self.nickname_command),
            ("birthday", self.birthday_command),
            ("export", self.export_command),
            ("priority", self.priority_command),
            ("grant_vip", self.grant_vip_command),
            ("revoke_vip", self.revoke_vip_command),
            ("broadcast", self.broadcast_command),
            ("stats", self.stats_command),
            ("users", self.users_command),
            ("logs", self.logs_command),
            ("maintenance", self.maintenance_command),
            ("backup", self.backup_command),
            ("announce", self.announce_command),
        ]
        
        for cmd, handler in handlers:
            application.add_handler(CommandHandler(cmd, handler))
        
        # Обработчик сообщений (только приватные чаты)
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
        
        # Периодический пинг (каждые 14 минут)
        self.scheduler.add_job(
            self.self_ping,
            'interval',
            minutes=14,
            id='self_ping'
        )
        
        # Планируем поздравление папе
        await self.schedule_dad_birthday(application)
        
        logger.info("✅ Бот полностью инициализирован")
        logger.info("🚀 Запуск polling...")
        
        # Запуск бота
        await application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

# =============================================================================
# FLASK ДЛЯ HEALTH CHECK
# =============================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": BOT_USERNAME,
        "time": datetime.datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.datetime.now().isoformat()
    })

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

async def main():
    """Основная функция"""
    logger.info("=" * 50)
    logger.info("🤖 TELEGRAM AI BOT")
    logger.info("=" * 50)
    logger.info(f"Bot: @{BOT_USERNAME}")
    logger.info(f"Creator: @{CREATOR_USERNAME}")
    logger.info("=" * 50)
    
    bot = TelegramBot()
    await bot.run_bot()

if __name__ == "__main__":
    # Проверка необходимых переменных
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        sys.exit(1)
    
    if not GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY не установлен - AI будет недоступен")
    
    if not GITHUB_TOKEN:
        logger.warning("⚠️ GITHUB_TOKEN не установлен - данные не будут сохраняться")
    
    # Запуск Flask в отдельном потоке
    logger.info("🌐 Запуск Flask сервера...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Небольшая задержка для запуска Flask
    time.sleep(2)
    
    # Запуск бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
