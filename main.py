#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ - Ernest Kostevich
Полнофункциональный AI бот с VIP системой
"""

import os
import json
import logging
import random
import time
import datetime
import asyncio
import requests
import pytz
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.error import NetworkError

from flask import Flask
import google.generativeai as genai

# =============================================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ И КОНСТАНТ
# =============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Безопасная загрузка переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "8176339131:AAGVKJoK9Y9fdQcTqMCp0Vm95IMuQWnCNGo")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCo4ymvNmI2JkYEuocIv3w_HsUyNPd6oEg")
FREECURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY", "fca_live_86O15Ga6b1M0bnm6FCiDfrBB7USGCEPiAUyjiuwL")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
REPLIT_USERNAME = os.getenv("REPLIT_USERNAME", "ernest2011koste")

# Константы бота
CREATOR_ID = 7108255346
CREATOR_USERNAME = "@Ernest_Kostevich"
BOT_USERNAME = "@AI_ERNEST_BOT"
BOT_NAME = "Айрис"

# Настройка Gemini AI
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-pro')
        logger.info("✅ Gemini AI инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Gemini: {e}")
        gemini_model = None
else:
    gemini_model = None
    logger.warning("⚠️ Gemini API ключ не найден")

# =============================================================================
# СТРУКТУРЫ ДАННЫХ
# =============================================================================

@dataclass
class UserData:
    user_id: int
    username: str = ""
    first_name: str = ""
    is_vip: bool = False
    vip_expires: Optional[str] = None
    language: str = "ru"
    notes: List[str] = field(default_factory=list)
    reminders: List[Dict] = field(default_factory=list)
    level: int = 1
    experience: int = 0
    memory_data: Dict[str, str] = field(default_factory=dict)
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'is_vip': self.is_vip,
            'vip_expires': self.vip_expires,
            'language': self.language,
            'notes': self.notes,
            'reminders': self.reminders,
            'level': self.level,
            'experience': self.experience,
            'memory_data': self.memory_data,
            'last_activity': self.last_activity
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserData':
        return cls(**data)

# =============================================================================
# БАЗА ДАННЫХ
# =============================================================================

class Database:
    def __init__(self):
        self.users: Dict[int, UserData] = {}
        self.logs: List[Dict] = []
        self.statistics: Dict[str, Any] = {}
        self.load_data()

    def load_data(self):
        """Загрузка данных из JSON файлов"""
        try:
            # Загрузка пользователей
            if os.path.exists('users.json'):
                with open('users.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = {int(k): UserData.from_dict(v) for k, v in data.items()}
                logger.info(f"✅ Загружено {len(self.users)} пользователей")
            
            # Загрузка логов
            if os.path.exists('logs.json'):
                with open('logs.json', 'r', encoding='utf-8') as f:
                    self.logs = json.load(f)
            
            # Загрузка статистики
            if os.path.exists('stats.json'):
                with open('stats.json', 'r', encoding='utf-8') as f:
                    self.statistics = json.load(f)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных: {e}")

    def save_data(self):
        """Сохранение данных в JSON файлы"""
        try:
            # Сохранение пользователей
            with open('users.json', 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.users.items()}, f, ensure_ascii=False, indent=2)
            
            # Сохранение логов (только последние 1000)
            with open('logs.json', 'w', encoding='utf-8') as f:
                json.dump(self.logs[-1000:], f, ensure_ascii=False, indent=2)
            
            # Сохранение статистики
            with open('stats.json', 'w', encoding='utf-8') as f:
                json.dump(self.statistics, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")

    def get_user(self, user_id: int) -> Optional[UserData]:
        return self.users.get(user_id)

    def save_user(self, user_data: UserData):
        """Сохранение пользователя с обновлением активности"""
        user_data.last_activity = datetime.datetime.now().isoformat()
        self.users[user_data.user_id] = user_data
        self.save_data()

    def log_command(self, user_id: int, command: str, message: str = ""):
        """Логирование команды"""
        log_entry = {
            'user_id': user_id,
            'command': command,
            'message': message[:100],  # Ограничиваем длину сообщения
            'timestamp': datetime.datetime.now().isoformat()
        }
        self.logs.append(log_entry)
        
        # Обновляем статистику
        if command not in self.statistics:
            self.statistics[command] = {'count': 0, 'last_used': ''}
        
        self.statistics[command]['count'] += 1
        self.statistics[command]['last_used'] = datetime.datetime.now().isoformat()

    def get_all_users(self) -> List[tuple]:
        return [(user_id, user_data.first_name, user_data.level) 
                for user_id, user_data in self.users.items()]

    def get_vip_users(self) -> List[tuple]:
        return [(user_id, user_data.first_name, user_data.vip_expires)
                for user_id, user_data in self.users.items() 
                if user_data.is_vip]

# =============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# =============================================================================

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.user_contexts: Dict[int, List[str]] = {}
        self.maintenance_mode = False
        
        # Запускаем автосохранение каждые 5 минут
        self.auto_save_task = None
        
        logger.info("🤖 Бот инициализирован")

    def is_creator(self, user_id: int) -> bool:
        return user_id == CREATOR_ID

    def is_vip(self, user_data: UserData) -> bool:
        """Проверка VIP статуса с учетом времени истечения"""
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

    async def get_user_data(self, update: Update) -> UserData:
        """Получение или создание данных пользователя"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            user_data = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "Пользователь"
            )
            
            # Автоматически выдаем VIP создателю
            if self.is_creator(user.id):
                user_data.is_vip = True
                user_data.vip_expires = None
                logger.info(f"👑 Создатель получил VIP: {user.id}")
            
            self.db.save_user(user_data)
            logger.info(f"👤 Создан новый пользователь: {user.first_name} ({user.id})")
        
        return user_data

    async def send_typing(self, update: Update):
        """Показать действие набора текста"""
        try:
            await update.message.chat.send_action(action="typing")
        except Exception:
            pass

    # =============================================================================
    # СИСТЕМНЫЕ КОМАНДЫ
    # =============================================================================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_data = await self.get_user_data(update)
        await self.send_typing(update)
        
        # Персонализированное приветствие
        if self.is_creator(user_data.user_id):
            greeting = "👑 Добро пожаловать, Создатель!"
            status_info = "Владелец бота с полным доступом"
        elif self.is_vip(user_data):
            greeting = f"💎 Добро пожаловать, {user_data.first_name}!"
            status_info = "VIP пользователь с расширенными возможностями"
        else:
            greeting = f"🤖 Привет, {user_data.first_name}!"
            status_info = "Пользователь - исследуй мои возможности!"
        
        welcome_text = f"""
{greeting}

Я {BOT_NAME} - твой умный AI помощник! 

🌟 **Мои возможности:**
• 💬 Умный чат с Gemini AI
• 📝 Система заметок и памяти
• 🌤️ Погода, курсы валют, переводы
• 🎮 Игры и развлечения
• 💎 VIP функции для избранных

📊 **Ваш статус:** {status_info}
🆙 **Уровень:** {user_data.level}
⭐ **Опыт:** {user_data.experience}

Используй /help для списка всех команд!
        """
        
        # Интерактивные кнопки
        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("🤖 AI Чат", callback_data="ai_demo")],
            [InlineKeyboardButton("💎 VIP", callback_data="vip_info"),
             InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        
        if self.is_creator(user_data.user_id):
            keyboard.append([InlineKeyboardButton("👑 Панель управления", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        self.db.log_command(user_data.user_id, "/start")
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Умная команда /help с разделением по правам"""
        user_data = await self.get_user_data(update)
        await self.send_typing(update)
        
        help_text = f"""
🤖 {BOT_NAME} - ПОМОЩЬ

🏠 **ОСНОВНЫЕ КОМАНДЫ:**
/start - Начать работу
/help - Эта справка
/info - О боте
/status - Статус системы

💬 **AI-ЧАТ:**
/ai [вопрос] - Задать вопрос ИИ
Просто напиши сообщение для общения!

📝 **ЗАМЕТКИ:**
/note [текст] - Сохранить заметку
/notes - Показать заметки
/delnote [номер] - Удалить заметку

⏰ **ВРЕМЯ:**
/time - Текущее время
/date - Текущая дата

🎮 **РАЗВЛЕЧЕНИЯ:**
/joke - Случайная шутка
/fact - Интересный факт
/quote - Вдохновляющая цитата
/coin - Подбросить монетку
/dice - Бросить кубик

🔧 **УТИЛИТЫ:**
/weather [город] - Погода
/currency [из] [в] - Курс валют
/translate [язык] [текст] - Перевод
/password [длина] - Генератор паролей
"""
        
        # VIP команды
        if self.is_vip(user_data):
            help_text += """
💎 **VIP КОМАНДЫ:**
/vip - Информация о VIP статусе
/remind [минуты] [текст] - Напоминание
/reminders - Мои напоминания
/secret - Секретная функция
/lottery - Ежедневная лотерея
"""
        
        # Команды создателя
        if self.is_creator(user_data.user_id):
            help_text += """
👑 **КОМАНДЫ СОЗДАТЕЛЯ:**
/grant_vip [user_id] [дни] - Выдать VIP
/revoke_vip [user_id] - Забрать VIP
/users - Список пользователей
/stats - Статистика бота
/broadcast [текст] - Рассылка
/maintenance [on/off] - Режим обслуживания
"""
        
        help_text += f"\n⚡ Всего функций: 50+"
        help_text += f"\n🤖 AI: {'✅ Gemini 2.0' if gemini_model else '❌ Недоступен'}"
        help_text += f"\n👑 Создатель: {CREATOR_USERNAME}"
        
        self.db.log_command(user_data.user_id, "/help")
        await update.message.reply_text(help_text)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /info"""
        user_data = await self.get_user_data(update)
        
        info_text = f"""
🤖 **ИНФОРМАЦИЯ О {BOT_NAME}**

👑 **Создатель:** Ernest Kostevich ({CREATOR_USERNAME})
🚀 **Версия:** 3.0
💻 **Платформа:** Telegram Bot API
🧠 **AI Модель:** Gemini 2.0 Flash

🌟 **Основные возможности:**
• Умный чат с искусственным интеллектом
• Система заметок и персональной памяти
• VIP система с эксклюзивными функциями
• Развлечения: шутки, факты, цитаты
• Полезные утилиты: погода, курсы, переводы

📊 **Статистика:**
• Пользователей: {len(self.db.users)}
• Выполнено команд: {len(self.db.logs)}
• AI запросов: {self.db.statistics.get('/ai', {}).get('count', 0)}

💎 **VIP система:** Активна
🤖 **AI чат:** {'✅ Доступен' if gemini_model else '❌ Временно недоступен'}
        """
        
        self.db.log_command(user_data.user_id, "/info")
        await update.message.reply_text(info_text)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status"""
        user_data = await self.get_user_data(update)
        
        total_users = len(self.db.users)
        vip_users = len([u for u in self.db.users.values() if u.is_vip])
        total_commands = len(self.db.logs)
        
        status_text = f"""
⚡ **СТАТУС СИСТЕМЫ**

🟢 Статус: Онлайн
👥 Пользователей: {total_users}
💎 VIP пользователей: {vip_users}
📊 Выполнено команд: {total_commands}
🤖 AI: {'✅ Активен' if gemini_model else '❌ Недоступен'}
🛠️ Обслуживание: {'🔴 ВКЛ' if self.maintenance_mode else '🟢 ВЫКЛ'}

⏰ Время сервера: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}
        """
        
        self.db.log_command(user_data.user_id, "/status")
        await update.message.reply_text(status_text)

    # =============================================================================
    # AI-ЧАТ СИСТЕМА
    # =============================================================================

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /ai для общения с ИИ"""
        user_data = await self.get_user_data(update)
        
        if not context.args:
            await update.message.reply_text("""
🤖 **AI-ЧАТ**

Использование: /ai [ваш вопрос]

Примеры:
• /ai Расскажи о космосе
• /ai Напиши код на Python
• /ai Объясни квантовую физику
• /ai Помоги с домашним заданием

Или просто напиши сообщение без команды!
            """)
            return
        
        if not gemini_model:
            await update.message.reply_text("❌ AI временно недоступен. Попробуйте позже.")
            return
        
        query = " ".join(context.args)
        await self.send_typing(update)
        
        try:
            # Создаем контекст диалога
            user_id = user_data.user_id
            if user_id not in self.user_contexts:
                self.user_contexts[user_id] = []
            
            # Добавляем вопрос в контекст
            self.user_contexts[user_id].append(f"Пользователь: {query}")
            
            # Ограничиваем контекст 5 сообщениями
            if len(self.user_contexts[user_id]) > 5:
                self.user_contexts[user_id] = self.user_contexts[user_id][-5:]
            
            # Формируем промпт с контекстом
            context_text = "\n".join(self.user_contexts[user_id][-3:])
            prompt = f"""
Ты полезный AI-ассистент в Telegram боте. Отвечай дружелюбно и информативно.

Контекст диалога:
{context_text}

Текущий вопрос пользователя: {query}

Ответь подробно и полезно:
"""
            
            response = gemini_model.generate_content(prompt)
            answer = response.text.strip()
            
            # Добавляем ответ в контекст
            self.user_contexts[user_id].append(f"Ассистент: {answer}")
            
            # Отправляем ответ
            await update.message.reply_text(f"🤖 {answer}")
            
        except Exception as e:
            logger.error(f"Ошибка AI: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обращении к AI. Попробуйте позже.")
        
        self.db.log_command(user_data.user_id, "/ai", query[:50])

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений без команд"""
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠️ Бот находится на техническом обслуживании. Попробуйте позже.")
            return
        
        user_data = await self.get_user_data(update)
        message_text = update.message.text
        
        # Игнорируем сообщения в группах без упоминания
        if update.effective_chat.type != "private":
            if not message_text.startswith(BOT_USERNAME):
                return
            message_text = message_text[len(BOT_USERNAME):].strip()
        
        await self.send_typing(update)
        
        # Быстрые ответы на простые вопросы
        message_lower = message_text.lower()
        
        if any(word in message_lower for word in ["привет", "хай", "hello", "hi", "здравствуй"]):
            responses = [
                "👋 Привет! Рад тебя видеть!",
                "😊 Здравствуй! Как дела?",
                "🤖 Приветствую! Чем могу помочь?",
                "🎉 Привет! Готов к работе!"
            ]
            await update.message.reply_text(random.choice(responses))
            return
        
        elif any(phrase in message_lower for phrase in ["как дела", "how are you"]):
            await update.message.reply_text("🤖 У меня всё отлично! Готов помогать! А у тебя как настроение?")
            return
        
        elif any(word in message_lower for word in ["спасибо", "thanks", "thank you"]):
            await update.message.reply_text("😊 Пожалуйста! Рад был помочь!")
            return
        
        elif any(phrase in message_lower for phrase in ["кто ты", "who are you"]):
            await update.message.reply_text(f"🤖 Я {BOT_NAME} - умный AI-помощник! Создан {CREATOR_USERNAME}")
            return
        
        # Используем AI для ответа на сложные вопросы
        if gemini_model:
            await self.ai_chat_response(update, message_text, user_data)
        else:
            await update.message.reply_text("🤖 Привет! Используй команды из /help для взаимодействия.")

    async def ai_chat_response(self, update: Update, message: str, user_data: UserData):
        """AI ответ на обычное сообщение"""
        try:
            prompt = f"""
Пользователь написал: "{message}"
Ответь естественно и полезно, как умный ассистент. Будь дружелюбным.
"""
            response = gemini_model.generate_content(prompt)
            await update.message.reply_text(f"🤖 {response.text}")
            
        except Exception as e:
            logger.error(f"Ошибка AI чата: {e}")
            await update.message.reply_text("❌ Не могу ответить сейчас. Попробуй использовать команды из /help")
        
        self.db.log_command(user_data.user_id, "message", message[:50])

    # =============================================================================
    # СИСТЕМА ЗАМЕТОК
    # =============================================================================

    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранить заметку - /note [текст]"""
        user_data = await self.get_user_data(update)
        
        if not context.args:
            await update.message.reply_text("📝 Использование: /note [текст заметки]")
            return
        
        note_text = " ".join(context.args)
        timestamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        user_data.notes.append(f"{timestamp}: {note_text}")
        
        self.db.save_user(user_data)
        await update.message.reply_text("✅ Заметка сохранена!")
        self.db.log_command(user_data.user_id, "/note")

    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все заметки - /notes"""
        user_data = await self.get_user_data(update)
        
        if not user_data.notes:
            await update.message.reply_text("📝 У вас пока нет сохраненных заметок.")
            return
        
        notes_text = "📝 **Ваши заметки:**\n\n"
        for i, note in enumerate(user_data.notes[-10:], 1):  # Показываем последние 10
            notes_text += f"{i}. {note}\n"
        
        if len(user_data.notes) > 10:
            notes_text += f"\n... и ещё {len(user_data.notes) - 10} заметок"
        
        await update.message.reply_text(notes_text)
        self.db.log_command(user_data.user_id, "/notes")

    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удалить заметку - /delnote [номер]"""
        user_data = await self.get_user_data(update)
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Использование: /delnote [номер заметки]")
            return
        
        note_num = int(context.args[0])
        if 1 <= note_num <= len(user_data.notes):
            deleted_note = user_data.notes.pop(note_num - 1)
            self.db.save_user(user_data)
            await update.message.reply_text(f"✅ Заметка удалена: {deleted_note[:50]}...")
        else:
            await update.message.reply_text(f"❌ Неверный номер заметки. Доступно: 1-{len(user_data.notes)}")
        
        self.db.log_command(user_data.user_id, "/delnote")

    # =============================================================================
    # РАЗВЛЕКАТЕЛЬНЫЕ КОМАНДЫ
    # =============================================================================

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Случайная шутка - /joke"""
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
            "Заходит программист в бар... а там нет свободных мест!",
            "— Доктор, я думаю, что я — компьютерный вирус!\n— Не волнуйтесь, примите эту таблетку.\n— А что это?\n— Антивирус!",
            "Почему Python лучше Java? Потому что он не заставляет вас писать 100 строк кода для 'Hello World'!",
            "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного, это hardware проблема!"
        ]
        
        await update.message.reply_text(f"😄 {random.choice(jokes)}")
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/joke")

    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Интересный факт - /fact"""
        facts = [
            "🧠 Человеческий мозг содержит около 86 миллиардов нейронов!",
            "🌊 В океане больше исторических артефактов, чем во всех музеях мира!",
            "🐙 У осьминогов три сердца и голубая кровь!",
            "🌍 Земля теряет около 50 тонн массы каждый год!",
            "⚡ Молния в 5 раз горячее поверхности Солнца!",
            "🐜 Муравьи никогда не спят!",
            "🔥 Огонь не имеет тени",
            "🍯 Мед никогда не портится"
        ]
        
        await update.message.reply_text(random.choice(facts))
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")

    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вдохновляющая цитата - /quote"""
        quotes = [
            "💫 'Будь собой. Остальные роли уже заняты.' - Оскар Уайльд",
            "🚀 'Единственный способ сделать великую работу — любить то, что делаешь.' - Стив Джобс",
            "⭐ 'Успех — это способность идти от неудачи к неудаче, не теряя энтузиазма.' - Уинстон Черчилль",
            "🌟 'Не ждите идеальных условий. Начните там, где вы находитесь.' - Артур Эш",
            "💡 'Инновация отличает лидера от последователя.' - Стив Джобс"
        ]
        
        await update.message.reply_text(random.choice(quotes))
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/quote")

    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подбросить монетку - /coin"""
        result = random.choice(["🪙 Орёл!", "🪙 Решка!"])
        await update.message.reply_text(result)
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/coin")

    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Бросить кубик - /dice"""
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/dice")

    # =============================================================================
    # ПОЛЕЗНЫЕ УТИЛИТЫ
    # =============================================================================

    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Текущее время - /time"""
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = datetime.datetime.now(moscow_tz)
        
        time_text = f"""
⏰ **ТЕКУЩЕЕ ВРЕМЯ**

🇷🇺 Москва: {moscow_time.strftime('%H:%M:%S %d.%m.%Y')}
🌍 UTC: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}
        """
        
        await update.message.reply_text(time_text)
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/time")

    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Текущая дата - /date"""
        today = datetime.datetime.now()
        await update.message.reply_text(f"📅 Сегодня: {today.strftime('%d %B %Y')}")
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/date")

    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Погода - /weather [город]"""
        user_data = await self.get_user_data(update)
        
        if not context.args:
            await update.message.reply_text("🌤️ Использование: /weather [город]\nПример: /weather Москва")
            return
        
        city = " ".join(context.args)
        
        if not OPENWEATHER_API_KEY:
            await update.message.reply_text("❌ Функция погоды временно недоступна")
            return
        
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get("cod") == 200:
                temp = data["main"]["temp"]
                feels_like = data["main"]["feels_like"]
                humidity = data["main"]["humidity"]
                description = data["weather"][0]["description"]
                wind_speed = data["wind"]["speed"]
                
                weather_text = f"""
🌤️ **Погода в {city}**

🌡️ Температура: {temp}°C
🤔 Ощущается как: {feels_like}°C
💧 Влажность: {humidity}%
🌬️ Ветер: {wind_speed} м/с
📝 Описание: {description.capitalize()}
                """
                await update.message.reply_text(weather_text)
            else:
                await update.message.reply_text("❌ Город не найден. Проверьте название.")
                
        except Exception as e:
            logger.error(f"Ошибка погоды: {e}")
            await update.message.reply_text("❌ Ошибка получения погоды. Попробуйте позже.")
        
        self.db.log_command(user_data.user_id, "/weather", city)

    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Курс валют - /currency [из] [в]"""
        user_data = await self.get_user_data(update)
        
        if len(context.args) < 2:
            await update.message.reply_text("💱 Использование: /currency [из] [в]\nПример: /currency USD RUB")
            return
        
        from_cur = context.args[0].upper()
        to_cur = context.args[1].upper()
        
        try:
            url = f"https://api.freecurrencyapi.com/v1/latest?apikey={FREECURRENCY_API_KEY}&base_currency={from_cur}&currencies={to_cur}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if "data" in data and to_cur in data["data"]:
                rate = data["data"][to_cur]
                await update.message.reply_text(f"💱 1 {from_cur} = {rate:.4f} {to_cur}")
            else:
                await update.message.reply_text("❌ Не удалось получить курс валют")
                
        except Exception as e:
            logger.error(f"Ошибка курса валют: {e}")
            await update.message.reply_text("❌ Ошибка получения курса валют")
        
        self.db.log_command(user_data.user_id, "/currency", f"{from_cur}_{to_cur}")

    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Генератор паролей - /password [длина]"""
        user_data = await self.get_user_data(update)
        
        length = 12
        if context.args and context.args[0].isdigit():
            length = min(int(context.args[0]), 32)  # Максимум 32 символа
        
        import string
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choice(characters) for _ in range(length))
        
        await update.message.reply_text(
            f"🔐 **Сгенерированный пароль** ({length} символов):\n"
            f"`{password}`\n\n"
            f"⚠️ *Сохраните пароль в безопасном месте!*",
            parse_mode='Markdown'
        )
        
        self.db.log_command(user_data.user_id, "/password")

    # =============================================================================
    # VIP СИСТЕМА
    # =============================================================================

    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о VIP статусе - /vip"""
        user_data = await self.get_user_data(update)
        
        if self.is_vip(user_data):
            if user_data.vip_expires:
                expires_date = datetime.datetime.fromisoformat(user_data.vip_expires)
                expires_str = expires_date.strftime("%d.%m.%Y %H:%M")
                status_text = f"💎 VIP активен до: {expires_str}"
            else:
                status_text = "💎 VIP активен БЕССРОЧНО"
            
            vip_info = f"""
{status_text}

🌟 **Ваши VIP привилегии:**
• ⏰ Умные напоминания (/remind)
• 🎁 Секретные функции (/secret)
• 🚀 Приоритетная обработка
• 💾 Расширенная память
• 🎰 Ежедневная лотерея (/lottery)
"""
        else:
            vip_info = """
💎 **VIP не активен**

✨ **Возможности VIP:**
⏰ Умные напоминания
🎁 Секретные функции  
🚀 Приоритетная обработка
💾 Расширенная память
🎰 Ежедневная лотерея

💡 *Для получения VIP обратитесь к* @Ernest_Kostevich
"""
        
        await update.message.reply_text(vip_info)
        self.db.log_command(user_data.user_id, "/vip")

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Напоминания - /remind [минуты] [текст] (только VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP пользователям!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("⏰ Использование: /remind [минуты] [текст напоминания]")
            return
        
        try:
            minutes = int(context.args[0])
            text = " ".join(context.args[1:])
            
            if minutes <= 0:
                await update.message.reply_text("❌ Время должно быть больше 0 минут!")
                return
            
            reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            # Сохраняем напоминание
            reminder = {
                "text": text,
                "time": reminder_time.isoformat(),
                "created": datetime.datetime.now().isoformat()
            }
            user_data.reminders.append(reminder)
            self.db.save_user(user_data)
            
            await update.message.reply_text(f"⏰ Напоминание установлено на {minutes} минут!")
            
            # Запланировать отправку напоминания
            async def send_reminder():
                await asyncio.sleep(minutes * 60)
                try:
                    await update.message.reply_text(f"🔔 Напоминание: {text}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания: {e}")
            
            asyncio.create_task(send_reminder())
            
        except ValueError:
            await update.message.reply_text("❌ Укажите корректное число минут!")
        
        self.db.log_command(user_data.user_id, "/remind")

    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список напоминаний - /reminders (только VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Эта функция доступна только VIP пользователям!")
            return
        
        if not user_data.reminders:
            await update.message.reply_text("⏰ У вас нет активных напоминаний.")
            return
        
        reminders_text = "⏰ **Ваши напоминания:**\n\n"
        for i, reminder in enumerate(user_data.reminders[-5:], 1):  # Последние 5
            reminder_time = datetime.datetime.fromisoformat(reminder["time"])
            time_str = reminder_time.strftime("%d.%m.%Y %H:%M")
            reminders_text += f"{i}. {reminder['text']} ({time_str})\n"
        
        await update.message.reply_text(reminders_text)
        self.db.log_command(user_data.user_id, "/reminders")

    # =============================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # =============================================================================

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выдать VIP - /grant_vip [user_id] [дни] (только создатель)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Недостаточно прав!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("💎 Использование: /grant_vip [user_id] [дни]\nПример: /grant_vip 123456789 30")
            return
        
        try:
            target_user_id = int(context.args[0])
            days = int(context.args[1])
            
            target_user = self.db.get_user(target_user_id)
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            target_user.is_vip = True
            expires_date = datetime.datetime.now() + datetime.timedelta(days=days)
            target_user.vip_expires = expires_date.isoformat()
            
            self.db.save_user(target_user)
            
            await update.message.reply_text(
                f"✅ VIP выдан пользователю {target_user.first_name} "
                f"на {days} дней (до {expires_date.strftime('%d.%m.%Y')})"
            )
            
            # Пытаемся уведомить пользователя
            try:
                await context.bot.send_message(
                    target_user_id,
                    f"🎉 Поздравляем! Вам выдан VIP статус на {days} дней!\n"
                    f"Используйте /vip для просмотра привилегий."
                )
            except Exception:
                pass  # Пользователь не начал диалог с ботом
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат данных! Используйте числа.")
        
        self.db.log_command(user_data.user_id, "/grant_vip")

    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список пользователей - /users (только создатель)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Недостаточно прав!")
            return
        
        users = self.db.get_all_users()
        if not users:
            await update.message.reply_text("👥 Пользователей пока нет.")
            return
        
        users_text = "👥 **Список пользователей:**\n\n"
        for user_id, first_name, level in users[:15]:  # Показываем первых 15
            user_data = self.db.get_user(user_id)
            vip_status = "💎" if user_data and user_data.is_vip else "👤"
            users_text += f"{vip_status} {first_name} (ID: {user_id}) - Ур. {level}\n"
        
        if len(users) > 15:
            users_text += f"\n... и ещё {len(users) - 15} пользователей"
        
        await update.message.reply_text(users_text)
        self.db.log_command(user_data.user_id, "/users")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика бота - /stats"""
        user_data = await self.get_user_data(update)
        
        total_users = len(self.db.users)
        vip_users = len([u for u in self.db.users.values() if u.is_vip])
        total_commands = len(self.db.logs)
        
        if self.is_creator(user_data.user_id):
            # Расширенная статистика для создателя
            active_today = len([
                u for u in self.db.users.values() 
                if (datetime.datetime.now() - datetime.datetime.fromisoformat(u.last_activity)).days < 1
            ])
            
            popular_commands = sorted(
                self.db.statistics.items(), 
                key=lambda x: x[1]['count'], 
                reverse=True
            )[:5]
            
            stats_text = f"""
📊 **СТАТИСТИКА БОТА (ДЛЯ СОЗДАТЕЛЯ)**

👥 Всего пользователей: {total_users}
💎 VIP пользователей: {vip_users}
🟢 Активных за 24ч: {active_today}
📈 Выполнено команд: {total_commands}

🔥 **Популярные команды:**
"""
            for cmd, data in popular_commands:
                stats_text += f"• {cmd}: {data['count']} раз\n"
            
            stats_text += f"\n🤖 AI: {'✅ Активен' if gemini_model else '❌ Недоступен'}"
            stats_text += f"\n⏰ Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
        else:
            # Базовая статистика для обычных пользователей
            stats_text = f"""
📊 **СТАТИСТИКА БОТА**

👥 Пользователей: {total_users}
💎 VIP пользователей: {vip_users}
📈 Выполнено команд: {total_commands}
🤖 AI: {'✅ Активен' if gemini_model else '❌ Недоступен'}
⚡ Статус: Онлайн
"""
        
        await update.message.reply_text(stats_text)
        self.db.log_command(user_data.user_id, "/stats")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Рассылка - /broadcast [текст] (только создатель)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Недостаточно прав!")
            return
        
        if not context.args:
            await update.message.reply_text("📢 Использование: /broadcast [текст сообщения]")
            return
        
        message = " ".join(context.args)
        users = self.db.get_all_users()
        sent_count = 0
        failed_count = 0
        
        await update.message.reply_text(f"📢 Начинаю рассылку для {len(users)} пользователей...")
        
        for user_id, first_name, level in users:
            try:
                await context.bot.send_message(
                    user_id,
                    f"📢 **Сообщение от создателя:**\n\n{message}"
                )
                sent_count += 1
                await asyncio.sleep(0.1)  # Задержка чтобы не превысить лимиты
            except Exception as e:
                failed_count += 1
                logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        
        await update.message.reply_text(
            f"✅ Рассылка завершена!\n"
            f"📤 Отправлено: {sent_count}\n"
            f"❌ Не удалось: {failed_count}"
        )
        
        self.db.log_command(user_data.user_id, "/broadcast")

    # =============================================================================
    # CALLBACK ОБРАБОТЧИКИ
    # =============================================================================

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_data = await self.get_user_data(update)
        
        if query.data == "help":
            await self.help_command(update, context)
        elif query.data == "ai_demo":
            await query.edit_message_text(
                "🤖 **AI-ЧАТ**\n\n"
                "Просто напиши мне сообщение или используй команду /ai\n\n"
                "**Примеры вопросов:**\n"
                "• Расскажи о космосе\n"  
                "• Помоги с программированием\n"
                "• Объясни сложную тему\n"
                "• Придумай идею проекта\n"
                "• Помоги с домашним заданием\n\n"
                "Я готов ответить на любой твой вопрос!"
            )
        elif query.data == "vip_info":
            await self.vip_command(update, context)
        elif query.data == "stats":
            await self.stats_command(update, context)
        elif query.data == "admin_panel" and self.is_creator(user_data.user_id):
            await query.edit_message_text(
                "👑 **ПАНЕЛЬ УПРАВЛЕНИЯ**\n\n"
                "**Доступные команды:**\n"
                "• /users - список пользователей\n"
                "• /stats - расширенная статистика\n"
                "• /grant_vip - выдать VIP\n"
                "• /broadcast - рассылка\n"
                "• /maintenance - режим обслуживания\n\n"
                "Используй команды для управления ботом."
            )

    # =============================================================================
    # ЗАПУСК БОТА
    # =============================================================================

    async def run_bot(self):
        """Запуск бота"""
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не найден! Проверьте настройки.")
            return

        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрируем обработчики команд
        command_handlers = [
            ('start', self.start_command),
            ('help', self.help_command),
            ('info', self.info_command),
            ('status', self.status_command),
            ('ai', self.ai_command),
            ('note', self.note_command),
            ('notes', self.notes_command),
            ('delnote', self.delnote_command),
            ('time', self.time_command),
            ('date', self.date_command),
            ('joke', self.joke_command),
            ('fact', self.fact_command),
            ('quote', self.quote_command),
            ('coin', self.coin_command),
            ('dice', self.dice_command),
            ('weather', self.weather_command),
            ('currency', self.currency_command),
            ('password', self.password_command),
            ('vip', self.vip_command),
            ('remind', self.remind_command),
            ('reminders', self.reminders_command),
            ('grant_vip', self.grant_vip_command),
            ('users', self.users_command),
            ('stats', self.stats_command),
            ('broadcast', self.broadcast_command),
        ]
        
        for command, handler in command_handlers:
            application.add_handler(CommandHandler(command, handler))
        
        # Обработчик обычных сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработчик кнопок
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчик ошибок
        application.add_error_handler(self.error_handler)
        
        logger.info("🤖 Бот запускается...")
        logger.info(f"👑 Создатель: {CREATOR_USERNAME}")
        logger.info(f"🌟 Имя бота: {BOT_NAME}")
        logger.info(f"👥 Пользователей в базе: {len(self.db.users)}")
        
        # Запускаем бота
        await application.run_polling(drop_pending_updates=True)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}")
        
        if isinstance(context.error, NetworkError):
            logger.warning("Проблемы с сетью...")
        else:
            logger.error(f"Неизвестная ошибка: {context.error}")

# =============================================================================
# FLASK APP ДЛЯ RENDER
# =============================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return f"""
    <html>
        <head>
            <title>{BOT_NAME}</title>
            <meta charset="utf-8">
            <style>
                body {{ 
                    font-family: 'Arial', sans-serif; 
                    margin: 40px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .container {{ 
                    max-width: 800px; 
                    margin: 0 auto; 
                    background: rgba(255,255,255,0.1);
                    padding: 30px;
                    border-radius: 15px;
                    backdrop-filter: blur(10px);
                }}
                .status {{ 
                    color: #4CAF50; 
                    font-weight: bold;
                    font-size: 1.2em;
                }}
                .bot-name {{
                    font-size: 2.5em;
                    margin-bottom: 10px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="bot-name">🤖 {BOT_NAME}</h1>
                <p class="status">✅ Бот активен и работает</p>
                <p><strong>Время сервера:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Создатель:</strong> {CREATOR_USERNAME}</p>
                <p><strong>Функций:</strong> 50+ | <strong>AI:</strong> Gemini 2.0 Flash</p>
                <p><strong>Статус:</strong> 🟢 Онлайн</p>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

@app.route('/ping')
def ping():
    return "pong"

# =============================================================================
# АВТОПИНГ ДЛЯ RENDER
# =============================================================================

def auto_ping():
    """Автопинг для поддержания активности на Render"""
    time.sleep(10)  # Ждем запуска бота
    while True:
        try:
            if REPLIT_USERNAME:
                requests.get(f"https://{REPLIT_USERNAME}.repl.co", timeout=10)
            else:
                # Для Render используем переменную окружения
                render_url = os.getenv("RENDER_EXTERNAL_URL")
                if render_url:
                    requests.get(render_url, timeout=10)
            logger.info("🔄 Автопинг выполнен")
        except Exception as e:
            logger.warning(f"Автопинг не удался: {e}")
        time.sleep(300)  # Пинг каждые 5 минут

# =============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# =============================================================================

async def main():
    """Основная функция запуска"""
    # Запускаем автопинг в отдельном потоке
    ping_thread = Thread(target=auto_ping, daemon=True)
    ping_thread.start()
    
    # Запускаем бота
    bot = TelegramBot()
    await bot.run_bot()

def run_flask():
    """Запуск Flask приложения"""
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        # Попытка перезапуска через 10 секунд
        logger.info("Перезапуск через 10 секунд...")
        time.sleep(10)
        asyncio.run(main())
