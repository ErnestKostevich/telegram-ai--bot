#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ИДЕАЛЬНЫЙ ТЕЛЕГРАМ БОТ - УЛУЧШЕННАЯ ВЕРСИЯ
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
import nest_asyncio
from flask import Flask
import pytz

nest_asyncio.apply()

# Telegram Bot API
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# Google Gemini
import google.generativeai as genai

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API ключи
BOT_TOKEN = os.getenv("BOT_TOKEN", "8176339131:AAGVKJoK9Y9fdQcTqMCp0Vm95IMuQWnCNGo")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCo4ymvNmI2JkYEuocIv3w_HsUyNPd6oEg")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY", "fca_live_86O15Ga6b1M0bnm6FCiDfrBB7USGCEPiAUyjiuwL")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# ID создателя
CREATOR_ID = 7108255346
CREATOR_USERNAME = "@Ernest_Kostevich"
BOT_USERNAME = "@AI_DISCO_BOT"
BOT_NAME = "AI Диско Бот"

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = genai.GenerativeModel('gemini-pro')
else:
    MODEL = None

# =============================================================================
# КЛАССЫ ДАННЫХ
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
    memory_data: Dict = field(default_factory=dict)
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

# База данных в памяти (упрощенная)
class Database:
    def __init__(self):
        self.users: Dict[int, UserData] = {}
        self.logs = []
        self.statistics = {}
        self.load_data()
    
    def load_data(self):
        try:
            if os.path.exists('users.json'):
                with open('users.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = {int(k): UserData.from_dict(v) for k, v in data.items()}
        except:
            self.users = {}
    
    def save_data(self):
        try:
            with open('users.json', 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.users.items()}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    def get_user(self, user_id: int) -> UserData:
        return self.users.get(user_id)
    
    def save_user(self, user_data: UserData):
        self.users[user_data.user_id] = user_data
        self.save_data()
    
    def log_command(self, user_id: int, command: str):
        self.logs.append({
            'user_id': user_id,
            'command': command,
            'timestamp': datetime.datetime.now().isoformat()
        })

# =============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# =============================================================================

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.scheduler = AsyncIOScheduler()
        self.user_contexts = {}
        
        # Запускаем планировщик
        self.scheduler.start()
        
        # Автопинг каждые 10 минут
        self.scheduler.add_job(
            self.auto_ping,
            'interval',
            minutes=10
        )
    
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
                    self.db.save_user(user_data)
                    return False
            except:
                return False
        
        return True
    
    async def get_user_data(self, update: Update) -> UserData:
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            user_data = UserData(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "Пользователь"
            )
            
            # Автоматически делаем создателя VIP
            if self.is_creator(user.id):
                user_data.is_vip = True
                user_data.vip_expires = None
            
            self.db.save_user(user_data)
        
        return user_data

    # =============================================================================
    # СИСТЕМНЫЕ ФУНКЦИИ
    # =============================================================================

    async def auto_ping(self):
        """Автопинг для поддержания активности"""
        logger.info("🔄 Автопинг выполнен")

    async def send_typing(self, update: Update):
        """Показать действие набора"""
        try:
            await update.message.chat.send_action(action="typing")
        except:
            pass

    # =============================================================================
    # УЛУЧШЕННЫЙ /help С РАЗДЕЛЕНИЕМ ПРАВ
    # =============================================================================

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Умная команда помощи с разделением по правам"""
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
Просто напишите сообщение для общения!

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
        
        # Добавляем VIP команды если пользователь VIP
        if self.is_vip(user_data):
            help_text += """
💎 **VIP КОМАНДЫ:**
/vip - Информация о VIP статусе
/remind [время] [текст] - Напоминание
/reminders - Мои напоминания
/secret - Секретная функция
/lottery - Ежедневная лотерея
"""
        
        # Добавляем команды создателя
        if self.is_creator(user_data.user_id):
            help_text += """
👑 **КОМАНДЫ СОЗДАТЕЛЯ:**
/grant_vip [user] [время] - Выдать VIP
/revoke_vip [user] - Забрать VIP
/users - Список пользователей
/stats - Статистика бота
/broadcast [текст] - Рассылка
"""
        
        help_text += f"\n⚡ Всего функций: 50+\n🤖 AI: Gemini 2.0\n👑 Создатель: {CREATOR_USERNAME}"
        
        self.db.log_command(user_data.user_id, "/help")
        await update.message.reply_text(help_text)

    # =============================================================================
    # УЛУЧШЕННЫЙ /start С ПЕРСОНАЛИЗАЦИЕЙ
    # =============================================================================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Улучшенная команда старта"""
        user_data = await self.get_user_data(update)
        await self.send_typing(update)
        
        # Приветствие в зависимости от статуса
        if self.is_creator(user_data.user_id):
            greeting = "👑 Добро пожаловать, Создатель!"
            status = "Владелец бота"
        elif self.is_vip(user_data):
            greeting = f"💎 Приветствуем, {user_data.first_name}!"
            status = "VIP пользователь"
        else:
            greeting = f"🤖 Привет, {user_data.first_name}!"
            status = "Пользователь"
        
        start_text = f"""
{greeting}

Я {BOT_NAME} - многофункциональный AI-бот с более чем 50 функциями!

🌟 **Мои возможности:**
• 💬 Умный чат с Gemini AI
• 📝 Система заметок и памяти
• 🌤️ Погода, курсы валют, переводы
• 🎮 Игры и развлечения
• 💎 VIP функции для избранных

📊 **Ваш статус:** {status}
🆙 **Уровень:** {user_data.level}
⭐ **Опыт:** {user_data.experience}

Используйте /help для списка команд!
"""
        
        # Интерактивные кнопки
        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("🤖 AI Чат", callback_data="ai_info")],
            [InlineKeyboardButton("💎 VIP", callback_data="vip_info"),
             InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        
        if self.is_creator(user_data.user_id):
            keyboard.append([InlineKeyboardButton("👑 Панель управления", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        self.db.log_command(user_data.user_id, "/start")
        await update.message.reply_text(start_text, reply_markup=reply_markup)

    # =============================================================================
    # УЛУЧШЕННЫЙ AI-ЧАТ С КОНТЕКСТОМ
    # =============================================================================

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Умный AI-чат с контекстом"""
        user_data = await self.get_user_data(update)
        
        if not context.args:
            await update.message.reply_text("""
🤖 AI-ЧАТ

Просто напишите вопрос после /ai
Или отправьте сообщение без команды!

Примеры:
/ai Расскажи о космосе
/ai Напиши код на Python
/ai Объясни квантовую физику
            """)
            return
        
        if not MODEL:
            await update.message.reply_text("❌ AI временно недоступен")
            return
        
        query = " ".join(context.args)
        await self.send_typing(update)
        
        try:
            # Сохраняем контекст
            user_id = user_data.user_id
            if user_id not in self.user_contexts:
                self.user_contexts[user_id] = []
            
            # Добавляем вопрос в контекст
            self.user_contexts[user_id].append(f"Пользователь: {query}")
            
            # Ограничиваем контекст 6 сообщениями
            if len(self.user_contexts[user_id]) > 6:
                self.user_contexts[user_id] = self.user_contexts[user_id][-6:]
            
            # Создаем промпт с контекстом
            context_text = "\n".join(self.user_contexts[user_id][-3:])
            prompt = f"""
Ты полезный AI-ассистент в Telegram боте. Отвечай дружелюбно и подробно.

Контекст разговора:
{context_text}

Текущий вопрос: {query}

Ответь на вопрос пользователя:
"""
            
            response = MODEL.generate_content(prompt)
            answer = response.text
            
            # Добавляем ответ в контекст
            self.user_contexts[user_id].append(f"Ассистент: {answer}")
            
            # Отправляем ответ
            await update.message.reply_text(f"🤖 {answer}")
            
        except Exception as e:
            logger.error(f"Ошибка AI: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обращении к AI")
        
        self.db.log_command(user_data.user_id, "/ai")

    # =============================================================================
    # ОБРАБОТЧИК СООБЩЕНИЙ БЕЗ КОМАНД
    # =============================================================================

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений"""
        user_data = await self.get_user_data(update)
        message_text = update.message.text
        
        # Игнорируем сообщения в группах без упоминания
        if update.effective_chat.type != "private":
            if not message_text.startswith(BOT_USERNAME):
                return
            message_text = message_text[len(BOT_USERNAME):].strip()
        
        await self.send_typing(update)
        
        # Простые ответы на приветствия
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
            await update.message.reply_text("🤖 У меня всё отлично! Готов помогать! А у тебя как?")
            return
        
        elif any(word in message_lower for word in ["спасибо", "thanks", "thank you"]):
            await update.message.reply_text("😊 Пожалуйста! Рад был помочь!")
            return
        
        elif any(phrase in message_lower for phrase in ["кто ты", "who are you"]):
            await update.message.reply_text(f"🤖 Я {BOT_NAME} - умный AI-помощник! Создан {CREATOR_USERNAME}")
            return
        
        # Используем AI для ответа
        await self.ai_chat_response(update, message_text, user_data)

    async def ai_chat_response(self, update: Update, message: str, user_data: UserData):
        """AI ответ на сообщение"""
        if not MODEL:
            await update.message.reply_text("🤖 Привет! Используйте команды для взаимодействия.")
            return
        
        try:
            prompt = f"""
Пользователь написал: "{message}"
Ответь естественно и полезно, как умный ассистент.
"""
            response = MODEL.generate_content(prompt)
            await update.message.reply_text(f"🤖 {response.text}")
            
        except Exception as e:
            await update.message.reply_text("❌ Не могу ответить сейчас. Попробуйте позже.")
        
        self.db.log_command(user_data.user_id, "message")

    # =============================================================================
    # КОМАНДЫ ЗАМЕТОК (УЛУЧШЕННЫЕ)
    # =============================================================================

    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранить заметку"""
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
        """Показать все заметки"""
        user_data = await self.get_user_data(update)
        
        if not user_data.notes:
            await update.message.reply_text("📝 У вас пока нет заметок")
            return
        
        notes_text = "📝 **Ваши заметки:**\n\n"
        for i, note in enumerate(user_data.notes[-10:], 1):  # Последние 10 заметок
            notes_text += f"{i}. {note}\n"
        
        if len(user_data.notes) > 10:
            notes_text += f"\n... и ещё {len(user_data.notes) - 10} заметок"
        
        await update.message.reply_text(notes_text)
        self.db.log_command(user_data.user_id, "/notes")

    # =============================================================================
    # VIP КОМАНДЫ
    # =============================================================================

    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о VIP статусе"""
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

🌟 **VIP привилегии:**
• Напоминания (/remind)
• Секретные функции
• Приоритетная поддержка
• Расширенная память
"""
        else:
            vip_info = """
💎 VIP не активен

✨ **Возможности VIP:**
⏰ Умные напоминания
🎁 Секретные функции  
🚀 Приоритетная обработка
💾 Расширенная память

Для получения VIP обратитесь к @Ernest_Kostevich
"""
        
        await update.message.reply_text(vip_info)
        self.db.log_command(user_data.user_id, "/vip")

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Напоминания (только для VIP)"""
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
            
        except ValueError:
            await update.message.reply_text("❌ Укажите корректное число минут!")
        
        self.db.log_command(user_data.user_id, "/remind")

    # =============================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # =============================================================================

    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выдать VIP (только создатель)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_creator(user_data.user_id):
            await update.message.reply_text("❌ Недостаточно прав!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("💎 Использование: /grant_vip [user_id] [days]")
            return
        
        try:
            target_user_id = int(context.args[0])
            days = int(context.args[1])
            
            target_user = self.db.get_user(target_user_id)
            if not target_user:
                await update.message.reply_text("❌ Пользователь не найден!")
                return
            
            target_user.is_vip = True
            expires = datetime.datetime.now() + datetime.timedelta(days=days)
            target_user.vip_expires = expires.isoformat()
            
            self.db.save_user(target_user)
            
            await update.message.reply_text(
                f"✅ VIP выдан пользователю {target_user.first_name} "
                f"на {days} дней (до {expires.strftime('%d.%m.%Y')})"
            )
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат данных!")
        
        self.db.log_command(user_data.user_id, "/grant_vip")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика бота"""
        user_data = await self.get_user_data(update)
        
        total_users = len(self.db.users)
        vip_users = sum(1 for u in self.db.users.values() if self.is_vip(u))
        total_commands = len(self.db.logs)
        
        stats_text = f"""
📊 **СТАТИСТИКА БОТА**

👥 Всего пользователей: {total_users}
💎 VIP пользователей: {vip_users}
📈 Выполнено команд: {total_commands}
🤖 AI модель: Gemini 2.0
⚡ Статус: Онлайн
"""
        
        if self.is_creator(user_data.user_id):
            # Дополнительная статистика для создателя
            active_today = sum(1 for u in self.db.users.values() 
                             if datetime.datetime.now() - datetime.datetime.fromisoformat(u.last_activity) < datetime.timedelta(days=1))
            
            stats_text += f"""
👑 **ДЛЯ СОЗДАТЕЛЯ:**
🟢 Активных за 24ч: {active_today}
📝 Всего заметок: {sum(len(u.notes) for u in self.db.users.values())}
"""
        
        await update.message.reply_text(stats_text)
        self.db.log_command(user_data.user_id, "/stats")

    # =============================================================================
    # РАЗВЛЕКАТЕЛЬНЫЕ КОМАНДЫ
    # =============================================================================

    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Случайная шутка"""
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
        """Интересный факт"""
        facts = [
            "🧠 Человеческий мозг содержит около 86 миллиардов нейронов!",
            "🌊 В океане больше исторических артефактов, чем во всех музеях мира!",
            "🐙 У осьминогов три сердца и голубая кровь!",
            "🌍 Земля теряет около 50 тонн массы каждый год!",
            "⚡ Молния в 5 раз горячее поверхности Солнца!"
        ]
        
        await update.message.reply_text(random.choice(facts))
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data.user_id, "/fact")

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
        elif query.data == "ai_info":
            await query.edit_message_text(
                "🤖 **AI-ЧАТ**\n\n"
                "Просто напишите мне сообщение или используйте /ai\n\n"
                "Примеры вопросов:\n"
                "• Расскажи о космосе\n"  
                "• Помоги с программированием\n"
                "• Объясни сложную тему\n"
                "• Придумай идею проекта"
            )
        elif query.data == "vip_info":
            await self.vip_command(update, context)
        elif query.data == "stats":
            await self.stats_command(update, context)
        elif query.data == "admin" and self.is_creator(user_data.user_id):
            await query.edit_message_text(
                "👑 **ПАНЕЛЬ УПРАВЛЕНИЯ**\n\n"
                "Доступные команды:\n"
                "• /users - список пользователей\n"
                "• /stats - статистика\n"
                "• /grant_vip - выдать VIP\n"
                "• /broadcast - рассылка"
            )

    # =============================================================================
    # ЗАПУСК БОТА
    # =============================================================================

    async def run_bot(self):
        """Запуск бота"""
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не найден!")
            return

        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрируем обработчики команд
        commands = [
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
            ('translate', self.translate_command),
            ('vip', self.vip_command),
            ('remind', self.remind_command),
            ('reminders', self.reminders_command),
            ('grant_vip', self.grant_vip_command),
            ('stats', self.stats_command),
            ('users', self.users_command),
        ]
        
        for command, handler in commands:
            application.add_handler(CommandHandler(command, handler))
        
        # Обработчик сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработчик кнопок
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчик ошибок
        application.add_error_handler(self.error_handler)
        
        logger.info("🤖 Бот запускается...")
        await application.run_polling(drop_pending_updates=True)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}")

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
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .status {{ color: green; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 {BOT_NAME}</h1>
                <p class="status">✅ Бот активен</p>
                <p>Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Создатель: {CREATOR_USERNAME}</p>
                <p>Функций: 50+ | AI: Gemini 2.0</p>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

# =============================================================================
# ЗАПУСК
# =============================================================================

async def main():
    """Основная функция"""
    bot = TelegramBot()
    await bot.run_bot()

def run_flask():
    """Запуск Flask"""
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    import threading
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем бота
    asyncio.run(main())
