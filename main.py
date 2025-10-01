#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ v2.5 - Главный файл
Полнофункциональный бот с расширенным контекстом и инструментами
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
import nest_asyncio
from flask import Flask
import pytz
from github import Github

nest_asyncio.apply()

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import Conflict
import google.generativeai as genai

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"
USERS_FILE = "users.json"
CONVERSATIONS_FILE = "conversations.json"
LOGS_FILE = "logs.json"
STATISTICS_FILE = "statistics.json"
BACKUP_PATH = "bot_backup.json"

CREATOR_ID = 7108255346
DAD_BIRTHDAY = "2025-10-03"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.0-flash-exp"

@dataclass
class UserData:
    user_id: int
    username: str
    first_name: str
    is_vip: bool = False
    vip_expires: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    reminders: List[Dict] = field(default_factory=list)
    memory_data: Dict = field(default_factory=dict)
    nickname: Optional[str] = None
    level: int = 1
    experience: int = 0
    achievements: List[str] = field(default_factory=list)
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            user_id=data['user_id'],
            username=data.get('username', ''),
            first_name=data.get('first_name', ''),
            is_vip=data.get('is_vip', False),
            vip_expires=data.get('vip_expires'),
            notes=data.get('notes', []),
            reminders=data.get('reminders', []),
            memory_data=data.get('memory_data', {}),
            nickname=data.get('nickname'),
            level=data.get('level', 1),
            experience=data.get('experience', 0),
            achievements=data.get('achievements', []),
            last_activity=data.get('last_activity', datetime.datetime.now().isoformat())
        )

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'is_vip': self.is_vip,
            'vip_expires': self.vip_expires,
            'notes': self.notes,
            'reminders': self.reminders,
            'memory_data': self.memory_data,
            'nickname': self.nickname,
            'level': self.level,
            'experience': self.experience,
            'achievements': self.achievements,
            'last_activity': self.last_activity
        }

class AITools:
    @staticmethod
    def get_current_datetime():
        now = datetime.datetime.now()
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = now.astimezone(moscow_tz)
        return {
            "date": now.strftime('%d.%m.%Y'),
            "time": moscow_time.strftime('%H:%M:%S'),
            "day_of_week": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][now.weekday()],
            "year": now.year,
            "month": now.month,
            "day": now.day
        }

class DatabaseManager:
    def __init__(self):
        self.g = None
        self.repo = None
        self.users = []
        self.conversations = {}
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
        self.conversations = self.load_data(CONVERSATIONS_FILE, {})
        self.logs = self.load_data(LOGS_FILE, [])
        self.statistics = self.load_data(STATISTICS_FILE, {})
    
    def load_data(self, path, default):
        if not self.repo:
            return default
        try:
            file = self.repo.get_contents(path)
            data = json.loads(file.decoded_content.decode('utf-8'))
            logger.info(f"Загружено из {path}")
            return data
        except:
            logger.warning(f"Файл {path} не найден")
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
        for u in self.users:
            if u.get('user_id') == user_id:
                return UserData.from_dict(u)
        return None
    
    def save_user(self, user_data: UserData):
        user_data.last_activity = datetime.datetime.now().isoformat()
        for i, u in enumerate(self.users):
            if u.get('user_id') == user_data.user_id:
                self.users[i] = user_data.to_dict()
                break
        else:
            self.users.append(user_data.to_dict())
        self.save_data(USERS_FILE, self.users)
    
    def get_conversation(self, user_id: int) -> List[Dict]:
        return self.conversations.get(str(user_id), [])
    
    def add_to_conversation(self, user_id: int, role: str, message: str):
        user_id_str = str(user_id)
        if user_id_str not in self.conversations:
            self.conversations[user_id_str] = []
        
        self.conversations[user_id_str].append({
            "role": role,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        if len(self.conversations[user_id_str]) > 50:
            self.conversations[user_id_str] = self.conversations[user_id_str][-50:]
        
        asyncio.create_task(self._save_conversations_async())
    
    async def _save_conversations_async(self):
        await asyncio.get_event_loop().run_in_executor(
            None, self.save_data, CONVERSATIONS_FILE, self.conversations
        )
    
    def log_command(self, user_id: int, command: str):
        self.logs.append({
            'user_id': user_id,
            'command': command,
            'timestamp': datetime.datetime.now().isoformat()
        })
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        
        if command in self.statistics:
            self.statistics[command]['usage_count'] += 1
        else:
            self.statistics[command] = {'usage_count': 1}
        
        asyncio.create_task(self._save_logs_async())
    
    async def _save_logs_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, LOGS_FILE, self.logs)
        await asyncio.get_event_loop().run_in_executor(None, self.save_data, STATISTICS_FILE, self.statistics)

class TelegramBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.gemini_model = None
        self.tools = AITools()
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("Gemini инициализирован")
            except Exception as e:
                logger.error(f"Ошибка Gemini: {e}")
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
                return False
        return True
    
    async def add_experience(self, user_data: UserData, points: int = 1):
        user_data.experience += points
        required_exp = user_data.level * 100
        if user_data.experience >= required_exp:
            user_data.level += 1
            user_data.experience = 0
        self.db.save_user(user_data)
    
    def create_ai_prompt(self, user_message: str, conversation_history: List[Dict]) -> str:
        dt = self.tools.get_current_datetime()
        system_context = f"""Ты умный AI-ассистент в Telegram боте.

ТЕКУЩАЯ ИНФОРМАЦИЯ:
- Дата: {dt['date']} ({dt['day_of_week']})
- Время (МСК): {dt['time']}
- Год: {dt['year']}

ПРАВИЛА:
- Всегда используй актуальные дату/время из системной информации
- Отвечай на русском языке дружелюбно
- Помни весь контекст диалога"""

        history_text = "\n".join([
            f"{'Пользователь' if msg['role'] == 'user' else 'Ты'}: {msg['message']}"
            for msg in conversation_history[-20:]
        ])
        
        return f"""{system_context}

ИСТОРИЯ ДИАЛОГА:
{history_text if history_text else '(новый диалог)'}

НОВОЕ СООБЩЕНИЕ:
{user_message}

Твой ответ:"""
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Бот на обслуживании.")
            return
        
        user_data = await self.get_user_data(update)
        message = update.message.text
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            self.db.add_to_conversation(user_data.user_id, "user", message)
            conversation_history = self.db.get_conversation(user_data.user_id)
            prompt = self.create_ai_prompt(message, conversation_history)
            
            response = self.gemini_model.generate_content(prompt)
            bot_response = response.text
            
            self.db.add_to_conversation(user_data.user_id, "assistant", bot_response)
            await update.message.reply_text(bot_response)
            await self.add_experience(user_data, 1)
            
        except Exception as e:
            await update.message.reply_text("❌ Ошибка обработки")
            logger.error(f"Ошибка AI: {e}")
    
    # Базовые команды
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/start")
        
        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🤖 AI чат", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"🤖 Привет, {user_data.first_name}!\n\nЯ AI-бот с расширенной памятью (50 сообщений) и точным знанием времени!\n\nПросто напиши мне что-нибудь 💬"
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/help")
        
        help_text = """📋 ПОЛНЫЙ СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы
/uptime - Время работы

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос AI
/clear - Очистить историю диалога
Или просто напишите сообщение!

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
/rank - Ваш уровень"""
        
        if self.is_vip(user_data):
            help_text += """

💎 VIP КОМАНДЫ:
/vip - VIP информация
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/nickname [имя] - Установить никнейм
/profile - Ваш профиль"""
        
        if self.is_creator(user_data.user_id):
            help_text += """

👑 КОМАНДЫ СОЗДАТЕЛЯ:
/grant_vip [user_id/@username] [duration] - Выдать VIP
/revoke_vip [user_id/@username] - Отозвать VIP
/broadcast [текст] - Рассылка всем
/users - Список пользователей
/stats - Статистика бота
/maintenance [on/off] - Режим обслуживания
/backup - Создать резервную копию"""
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/info")
        
        info = f"""🤖 О БОТЕ

Версия: 2.5
Создатель: @Ernest_Kostevich
Функций: 50+
AI: {"Gemini 2.0 ✅" if self.gemini_model else "❌"}
База данных: {"GitHub ✅" if self.db.repo else "Локальная"}
Память: 50 сообщений
Хостинг: Render 24/7"""
        
        await update.message.reply_text(info)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/status")
        
        total_users = len(self.db.users)
        total_commands = len(self.db.logs)
        conversations_count = len(self.db.conversations)
        
        status = f"""⚡ СТАТУС БОТА

Онлайн: ✅
Версия: 2.5
Пользователей: {total_users}
Команд: {total_commands}
Диалогов: {conversations_count}
Gemini: {"✅" if self.gemini_model else "❌"}
GitHub: {"✅" if self.db.repo else "❌"}"""
        
        await update.message.reply_text(status)
    
    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/uptime")
        
        await update.message.reply_text(f"⏱️ Бот работает!\n👥 Пользователей: {len(self.db.users)}")
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clear")
        
        user_id_str = str(user_data.user_id)
        if user_id_str in self.db.conversations:
            count = len(self.db.conversations[user_id_str])
            self.db.conversations[user_id_str] = []
            self.db.save_data(CONVERSATIONS_FILE, self.db.conversations)
            await update.message.reply_text(f"✅ История очищена ({count} сообщений)")
        else:
            await update.message.reply_text("❌ История уже пуста")
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос после /ai!")
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
            await update.message.reply_text("❌ Ошибка AI")
    
    # Заметки
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
    
    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/notes")
        
        if not user_data.notes:
            await update.message.reply_text("❌ Нет заметок!")
            return
        
        notes_text = "\n".join(f"{i+1}. {note}" for i, note in enumerate(user_data.notes))
        await update.message.reply_text(f"📝 Ваши заметки:\n{notes_text}")
    
    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер заметки!")
            return
        
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_data.notes):
            user_data.notes.pop(index)
            self.db.save_user(user_data)
            await update.message.reply_text("✅ Заметка удалена")
        else:
            await update.message.reply_text("❌ Неверный номер!")
    
    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/findnote")
        
        if not context.args:
            await update.message.reply_text("🔍 Укажите ключевое слово!")
            return
        
        keyword = " ".join(context.args).lower()
        found = [(i+1, note) for i, note in enumerate(user_data.notes) if keyword in note.lower()]
        
        if found:
            notes_text = "\n".join(f"{i}. {note}" for i, note in found)
            await update.message.reply_text(f"🔍 Найдено ({len(found)}):\n{notes_text}")
        else:
            await update.message.reply_text("❌ Ничего не найдено!")
    
    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/clearnotes")
        
        count = len(user_data.notes)
        user_data.notes = []
        self.db.save_user(user_data)
        await update.message.reply_text(f"✅ Очищено {count} заметок!")
    
    # Память
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
        await update.message.reply_text(f"🧠 Сохранено: {key}")
    
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
    
    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/memorylist")
        
        if not user_data.memory_data:
            await update.message.reply_text("🧠 Память пуста!")
            return
        
        memory_text = "\n".join(f"• {key}: {value}" for key, value in user_data.memory_data.items())
        await update.message.reply_text(f"🧠 Ваша память:\n{memory_text}")
    
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
    
    # Время
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")
        
        dt = self.tools.get_current_datetime()
        await update.message.reply_text(f"⏰ ВРЕМЯ\n\nМосква: {dt['time']}\nДата: {dt['date']}\nДень: {dt['day_of_week']}")
    
    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")
        
        dt = self.tools.get_current_datetime()
        await update.message.reply_text(f"📅 Сегодня: {dt['date']} ({dt['day_of_week']})")
    
    # Развлечения
    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")
        
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Oct 31 == Dec 25!",
            "Заходит программист в бар...",
            "10 типов людей: те кто понимает двоичную систему и те кто нет"
        ]
        await update.message.reply_text(f"😄 {random.choice(jokes)}")
    
    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")
        
        facts = [
            "🧠 Человеческий мозг ~86 млрд нейронов",
            "🐙 У осьминогов три сердца",
            "🌍 Земля проходит 30 км/сек по орбите"
        ]
        await update.message.reply_text(random.choice(facts))
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")
        
        quotes = [
            "💫 'Будь собой. Остальные роли заняты.' - Оскар Уайльд",
            "🚀 'Единственный способ - любить то, что делаешь.' - Стив Джобс"
        ]
        await update.message.reply_text(random.choice(quotes))
    
    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quiz")
        
        questions = [
            {"q": "Сколько дней в високосном году?", "a": "366"},
            {"q": "Столица Австралии?", "a": "Канберра"}
        ]
        q = random.choice(questions)
        await update.message.reply_text(f"❓ {q['q']}\n\n💡 Напишите ответ!")
    
    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/coin")
        await update.message.reply_text(random.choice(["🪙 Орёл!", "🪙 Решка!"]))
    
    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/dice")
        
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
    
    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 Задайте вопрос!")
            return
        
        answers = ["✅ Да!", "❌ Нет", "🤔 Возможно", "⏳ Спроси позже"]
        await update.message.reply_text(f"🔮 {random.choice(answers)}")
    
    # Математика
    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/math")
        
        if not context.args:
            await update.message.reply_text("🔢 Пример: /math 15 + 25")
            return
        
        expression = " ".join(context.args)
        try:
            result = eval(expression)
            await update.message.reply_text(f"🔢 {expression} = {result}")
        except:
            await update.message.reply_text("❌ Ошибка вычисления")
    
    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/calculate")
        
        if not context.args:
            await update.message.reply_text("🧮 Пример: /calculate sqrt(16)")
            return
        
        expression = " ".join(context.args)
        try:
            import math
            safe_dict = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "pi": math.pi, "e": math.e}
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            await update.message.reply_text(f"🧮 {expression} = {result}")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    # Утилиты
    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/password")
        
        length = 12
        if context.args and context.args[0].isdigit():
            length = min(int(context.args[0]), 50)
        
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(f"🔐 Пароль:\n`{password}`", parse_mode='Markdown')
    
    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/qr")
        
        if not context.args:
            await update.message.reply_text("📱 /qr [текст]")
            return
        
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={text}"
        await context.bot.send_photo(update.effective_chat.id, qr_url)
    
    async def shorturl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/shorturl")
        
        if not context.args:
            await update.message.reply_text("🔗 /shorturl [URL]")
            return
        
        url = context.args[0]
        if not url.startswith('http'):
            url = 'https://' + url
        
        try:
            response = requests.get(f"https://is.gd/create.php?format=simple&url={url}", timeout=10)
            if response.status_code == 200:
                await update.message.reply_text(f"🔗 {response.text.strip()}")
            else:
                await update.message.reply_text("❌ Ошибка")
        except:
            await update.message.reply_text("❌ Ошибка подключения")
    
    async def ip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/ip")
        
        try:
            response = requests.get('https://httpbin.org/ip', timeout=5)
            ip = response.json().get('origin', 'Неизвестно')
            await update.message.reply_text(f"🌍 Ваш IP: {ip}")
        except:
            await update.message.reply_text("❌ Не удалось получить IP")
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/weather")
        
        if not context.args:
            await update.message.reply_text("🌤️ /weather [город]")
            return
        
        if not OPENWEATHER_API_KEY:
            await update.message.reply_text("❌ API не настроен")
            return
        
        city = " ".join(context.args)
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            response = requests.get(url, timeout=10).json()
            
            if response.get("cod") == 200:
                temp = round(response["main"]["temp"])
                desc = response["weather"][0]["description"]
                await update.message.reply_text(f"🌤️ {city}: {temp}°C, {desc}")
            else:
                await update.message.reply_text("❌ Город не найден")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/currency")
        
        if len(context.args) < 2:
            await update.message.reply_text("💰 /currency [из] [в]")
            return
        
        if not CURRENCY_API_KEY:
            await update.message.reply_text("❌ API не настроен")
            return
        
        from_cur, to_cur = context.args[0].upper(), context.args[1].upper()
        try:
            url = f"https://api.freecurrencyapi.com/v1/latest?apikey={CURRENCY_API_KEY}&currencies={to_cur}&base_currency={from_cur}"
            response = requests.get(url, timeout=10).json()
            rate = response.get("data", {}).get(to_cur)
            
            if rate:
                await update.message.reply_text(f"💰 1 {from_cur} = {rate:.4f} {to_cur}")
            else:
                await update.message.reply_text("❌ Ошибка")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text("🌐 /translate [язык] [текст]")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен")
            return
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            response = self.gemini_model.generate_content(f"Переведи на {target_lang}: {text}")
            await update.message.reply_text(f"🌐 {response.text}")
        except:
            await update.message.reply_text("❌ Ошибка")
    
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/rank")
        
        req = user_data.level * 100
        progress = (user_data.experience / req) * 100
        
        text = f"""🏅 УРОВЕНЬ

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}/{req}
📊 Прогресс: {progress:.1f}%
💎 VIP: {"✅" if self.is_vip(user_data) else "❌"}"""
        
        await update.message.reply_text(text)
    
    # VIP команды
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/vip")
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Свяжитесь с @Ernest_Kostevich")
            return
        
        expires = 'бессрочно'
        if user_data.vip_expires:
            try:
                exp_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                expires = exp_date.strftime('%d.%m.%Y')
            except:
                pass
        
        await update.message.reply_text(f"💎 VIP активен до: {expires}")
    
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
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            job = self.scheduler.add_job(
                self.send_notification,
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data.user_id, f"🔔 {text}"],
                id=f"rem_{user_data.user_id}_{int(time.time())}"
            )
            
            user_data.reminders.append({"id": job.id, "text": text, "time": run_date.isoformat()})
            self.db.save_user(user_data)
            
            await update.message.reply_text(f"⏰ Напоминание на {minutes} мин!")
        except:
            await update.message.reply_text("❌ Ошибка!")
    
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
        await update.message.reply_text(f"✅ Никнейм: {nickname}")
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data.user_id, "/profile")
        
        text = f"""👤 ПРОФИЛЬ

Имя: {user_data.first_name}
Никнейм: {user_data.nickname or "Не установлен"}
Уровень: {user_data.level}
Заметок: {len(user_data.notes)}
Памяти: {len(user_data.memory_data)}"""
        
        await update.message.reply_text(text)
    
    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка уведомления {user_id}: {e}")
    
    # Команды создателя
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
            
            target_user = None
            if target.startswith('@'):
                username = target[1:].lower()
                for u in self.db.users:
                    if u.get('username', '').lower() == username:
                        target_user = UserData.from_dict(u)
                        break
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
                await update.message.reply_text("❌ week/month/year/permanent")
                return
            
            self.db.save_user(target_user)
            await update.message.reply_text(f"✅ VIP выдан {target_user.first_name}")
            
            try:
                await context.bot.send_message(target_user.user_id, f"🎉 VIP ({duration})!")
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
            
            target_user = None
            if target.startswith('@'):
                username = target[1:].lower()
                for u in self.db.users:
                    if u.get('username', '').lower() == username:
                        target_user = UserData.from_dict(u)
                        break
            else:
                target_user = self.db.get_user(int(target))
            
            if not target_user:
                await update.message.reply_text("❌ Не найден!")
                return
            
            target_user.is_vip = False
            target_user.vip_expires = None
            self.db.save_user(target_user)
            
            await update.message.reply_text(f"✅ VIP отозван у {target_user.first_name}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not self.db.users:
            await update.message.reply_text("👥 Пользователей нет!")
            return
        
        text = "👥 ПОЛЬЗОВАТЕЛИ:\n\n"
        for u in self.db.users[:20]:
            vip = "💎" if u.get('is_vip') else "👤"
            text += f"{vip} {u.get('first_name')} (ID: {u.get('user_id')})\n"
        
        if len(self.db.users) > 20:
            text += f"\n... +{len(self.db.users) - 20}"
        
        await update.message.reply_text(text)
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text("📢 /broadcast [сообщение]")
            return
        
        message = " ".join(context.args)
        sent = 0
        
        await update.message.reply_text(f"📢 Рассылка для {len(self.db.users)}...")
        
        for u in self.db.users:
            try:
                await context.bot.send_message(u.get('user_id'), f"📢 От создателя:\n\n{message}")
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        
        await update.message.reply_text(f"✅ Отправлено: {sent}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_data = await self.get_user_data(update)
        
        if self.is_creator(user_data.user_id):
            vip = len([u for u in self.db.users if u.get('is_vip')])
            msgs = sum(len(c) for c in self.db.conversations.values())
            
            text = f"""📊 СТАТИСТИКА БОТА

👥 Пользователей: {len(self.db.users)}
💎 VIP: {vip}
💬 Сообщений: {msgs}
🗂️ Диалогов: {len(self.db.conversations)}

⚡ {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        else:
            conv = len(self.db.get_conversation(user_data.user_id))
            
            text = f"""📊 СТАТИСТИКА

👤 {user_data.first_name}
🆙 Уровень: {user_data.level}
⭐ Опыт: {user_data.experience}
💬 История: {conv} сообщений
📝 Заметок: {len(user_data.notes)}
🧠 Памяти: {len(user_data.memory_data)}"""
        
        self.db.log_command(user_data.user_id, "/stats")
        await update.message.reply_text(text)
    
    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            status = "включен" if self.maintenance_mode else "выключен"
            await update.message.reply_text(f"🛠 Режим: {status}")
            return
        
        mode = context.args[0].lower()
        if mode in ['on', 'вкл']:
            self.maintenance_mode = True
            await update.message.reply_text("🛠 ВКЛЮЧЕН")
        elif mode in ['off', 'выкл']:
            self.maintenance_mode = False
            await update.message.reply_text("✅ ВЫКЛЮЧЕН")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        try:
            backup_data = {
                'users': self.db.users,
                'conversations': self.db.conversations,
                'logs': self.db.logs[-100:],
                'statistics': self.db.statistics,
                'backup_time': datetime.datetime.now().isoformat()
            }
            
            success = self.db.save_data(BACKUP_PATH, backup_data)
            if success:
                await update.message.reply_text(f"✅ Бэкап создан!\nПользователей: {len(self.db.users)}")
            else:
                await update.message.reply_text("❌ Ошибка!")
        except Exception as e:
            await update.message.reply_text(f"❌ {str(e)}")
    
    # Обработчики
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.help_command(fake_update, context)
        elif query.data == "vip_info":
            await query.edit_message_text("💎 VIP дает доступ к напоминаниям.\n\nСвяжитесь с @Ernest_Kostevich")
        elif query.data == "ai_demo":
            await query.edit_message_text("🤖 AI готов!\n\nПросто напишите сообщение!")
        elif query.data == "my_stats":
            fake_update = Update(update_id=update.update_id, message=query.message)
            await self.stats_command(fake_update, context)
    
    async def self_ping(self):
        try:
            requests.get(RENDER_URL, timeout=10)
            logger.info("Ping OK")
        except:
            pass
    
    async def check_birthdays(self, context: ContextTypes.DEFAULT_TYPE):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if today == DAD_BIRTHDAY:
            for u in self.db.users:
                if u.get('username', '').lower() == 'mkostevich':
                    try:
                        await context.bot.send_message(u.get('user_id'), "🎉🎂 С Днём Рождения, папа!\n\nС любовью, Ernest ❤️")
                    except:
                        pass
    
    async def run_bot(self):
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не найден!")
            return
        
        application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).build()
        
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Error: {context.error}")
        
        application.add_error_handler(error_handler)
        
        # Все команды
        commands = [
            ("start", self.start_command), ("help", self.help_command), ("info", self.info_command),
            ("status", self.status_command), ("uptime", self.uptime_command), ("clear", self.clear_command),
            ("ai", self.ai_command), ("note", self.note_command), ("notes", self.notes_command),
            ("delnote", self.delnote_command), ("findnote", self.findnote_command), ("clearnotes", self.clearnotes_command),
            ("memorysave", self.memorysave_command), ("memoryget", self.memoryget_command),
            ("memorylist", self.memorylist_command), ("memorydel", self.memorydel_command),
            ("time", self.time_command), ("date", self.date_command),
            ("joke", self.joke_command), ("fact", self.fact_command), ("quote", self.quote_command),
            ("quiz", self.quiz_command), ("coin", self.coin_command), ("dice", self.dice_command),
            ("8ball", self.eightball_command), ("math", self.math_command), ("calculate", self.calculate_command),
            ("password", self.password_command), ("qr", self.qr_command), ("shorturl", self.shorturl_command),
            ("ip", self.ip_command), ("weather", self.weather_command), ("currency", self.currency_command),
            ("translate", self.translate_command), ("rank", self.rank_command),
            ("vip", self.vip_command), ("remind", self.remind_command), ("reminders", self.reminders_command),
            ("nickname", self.nickname_command), ("profile", self.profile_command),
            ("grant_vip", self.grant_vip_command), ("revoke_vip", self.revoke_vip_command),
            ("users", self.users_command), ("broadcast", self.broadcast_command),
            ("maintenance", self.maintenance_command), ("backup", self.backup_command), ("stats", self.stats_command)
        ]
        
        for cmd, handler in commands:
            application.add_handler(CommandHandler(cmd, handler))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()
        
        self.scheduler.add_job(self.self_ping, 'interval', minutes=14, id='ping')
        self.scheduler.add_job(self.check_birthdays, 'cron', hour=9, minute=0, args=[application], id='bday')
        
        logger.info("🤖 Бот запущен v2.5!")
        
        await application.run_polling(drop_pending_updates=True, timeout=30)

async def main():
    bot = TelegramBot()
    await bot.run_bot()

# Flask
app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 AI Bot v2.5 | Time: {datetime.datetime.now()}"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

if __name__ == "__main__":
    from threading import Thread
    
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port, 'debug': False})
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(main())
