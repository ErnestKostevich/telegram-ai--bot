#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 Telegram AI Bot with Gemini 2.0
Создатель: @Ernest_Kostevich
Бот: @AI_DISCO_BOT
"""

import os
import json
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# Google Gemini AI
import google.generativeai as genai

# Дополнительные библиотеки
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ====================
# КОНФИГУРАЦИЯ
# ====================

# Получаем токены из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
CURRENCY_API_KEY = os.getenv('CURRENCY_API_KEY', '')

# ID создателя бота
CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None  # Будет определён при первом запуске

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Настройка модели Gemini
generation_config = {
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name='gemini-2.0-flash-exp',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# ====================
# ХРАНИЛИЩЕ ДАННЫХ
# ====================

class DataStorage:
    """Класс для работы с данными пользователей"""
    
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.users = self.load_users()
        self.stats = self.load_stats()
        self.chat_sessions = {}  # Хранение сессий чата для контекста
    
    def load_users(self) -> Dict:
        """Загрузка данных пользователей"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {int(k): v for k, v in data.items()}
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            return {}
    
    def save_users(self):
        """Сохранение данных пользователей"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")
    
    def load_stats(self) -> Dict:
        """Загрузка статистики"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                'total_messages': 0,
                'total_commands': 0,
                'ai_requests': 0,
                'start_date': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки статистики: {e}")
            return {}
    
    def save_stats(self):
        """Сохранение статистики"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения статистики: {e}")
    
    def get_user(self, user_id: int) -> Dict:
        """Получение данных пользователя"""
        if user_id not in self.users:
            self.users[user_id] = {
                'id': user_id,
                'username': '',
                'first_name': '',
                'vip': False,
                'vip_until': None,
                'notes': [],
                'memory': {},
                'reminders': [],
                'registered': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'messages_count': 0,
                'commands_count': 0
            }
            self.save_users()
        return self.users[user_id]
    
    def update_user(self, user_id: int, data: Dict):
        """Обновление данных пользователя"""
        user = self.get_user(user_id)
        user.update(data)
        user['last_active'] = datetime.now().isoformat()
        self.save_users()
    
    def is_vip(self, user_id: int) -> bool:
        """Проверка VIP статуса"""
        user = self.get_user(user_id)
        if not user['vip']:
            return False
        if user['vip_until'] is None:  # Вечный VIP
            return True
        vip_until = datetime.fromisoformat(user['vip_until'])
        if datetime.now() > vip_until:
            user['vip'] = False
            user['vip_until'] = None
            self.save_users()
            return False
        return True
    
    def get_chat_session(self, user_id: int):
        """Получение сессии чата для контекста"""
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = model.start_chat(history=[])
        return self.chat_sessions[user_id]
    
    def clear_chat_session(self, user_id: int):
        """Очистка сессии чата"""
        if user_id in self.chat_sessions:
            del self.chat_sessions[user_id]

# Глобальное хранилище
storage = DataStorage()

# Планировщик задач
scheduler = AsyncIOScheduler()

# ====================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ====================

def is_creator(user_id: int) -> bool:
    """Проверка, является ли пользователь создателем"""
    global CREATOR_ID
    return user_id == CREATOR_ID

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Получение основной клавиатуры"""
    keyboard = [
        [KeyboardButton("💬 AI Чат"), KeyboardButton("📝 Заметки")],
        [KeyboardButton("🌍 Погода"), KeyboardButton("⏰ Время")],
        [KeyboardButton("🎲 Развлечения"), KeyboardButton("ℹ️ Инфо")]
    ]
    
    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton("💎 VIP Меню")])
    
    if is_creator(user_id):
        keyboard.append([KeyboardButton("👑 Админ Панель")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def format_user_info(user: Dict) -> str:
    """Форматирование информации о пользователе"""
    info = f"👤 <b>Пользователь:</b> {user.get('first_name', 'Unknown')}\n"
    info += f"🆔 <b>ID:</b> <code>{user['id']}</code>\n"
    if user.get('username'):
        info += f"📱 <b>Username:</b> @{user['username']}\n"
    
    info += f"📅 <b>Зарегистрирован:</b> {user['registered'][:10]}\n"
    info += f"📊 <b>Сообщений:</b> {user['messages_count']}\n"
    info += f"🎯 <b>Команд:</b> {user['commands_count']}\n"
    
    if user['vip']:
        if user['vip_until']:
            vip_until = datetime.fromisoformat(user['vip_until'])
            info += f"💎 <b>VIP до:</b> {vip_until.strftime('%d.%m.%Y %H:%M')}\n"
        else:
            info += f"💎 <b>VIP:</b> Навсегда ♾️\n"
    
    return info

# ====================
# БАЗОВЫЕ КОМАНДЫ
# ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    
    # Определяем ID создателя
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Создатель определён: {user.id}")
    
    # Обновляем данные пользователя
    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'commands_count': user_data['commands_count'] + 1
    })
    
    welcome_text = f"""
🤖 <b>Добро пожаловать в AI DISCO BOT!</b>

Привет, {user.first_name}! Я многофункциональный бот с искусственным интеллектом на базе <b>Google Gemini 2.0</b>.

<b>🎯 Основные возможности:</b>
💬 Умный AI-чат с контекстом
📝 Система заметок
🌍 Погода и время
🎲 Развлечения и игры
💎 VIP функции

<b>⚡ Быстрый старт:</b>
• Напиши мне что угодно - я отвечу!
• Используй /help для списка команд
• Нажми на кнопки меню ниже

<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(user.id)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {
        'commands_count': user_data['commands_count'] + 1
    })
    
    help_text = """
📚 <b>СПИСОК КОМАНД</b>

<b>🏠 Основные:</b>
/start - Запуск бота
/help - Эта справка
/info - Информация о боте
/status - Статус системы
/profile - Твой профиль

<b>💬 AI и Память:</b>
/ai [вопрос] - Задать вопрос AI
/clear - Очистить контекст чата
/memorysave [ключ] [значение] - Сохранить в память
/memoryget [ключ] - Получить из памяти
/memorylist - Показать всю память
/memorydel [ключ] - Удалить из памяти

<b>📝 Заметки:</b>
/note [текст] - Создать заметку
/notes - Показать все заметки
/delnote [номер] - Удалить заметку

<b>🌍 Утилиты:</b>
/time [город] - Текущее время
/weather [город] - Погода
/translate [язык] [текст] - Перевод

<b>🎲 Развлечения:</b>
/random [min] [max] - Случайное число
/dice - Бросить кубик
/coin - Подбросить монету
/joke - Случайная шутка
/quote - Мудрая цитата

<b>💎 VIP Команды:</b>
/vip - Твой VIP статус
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
"""
    
    if is_creator(user_id):
        help_text += """
<b>👑 Команды Создателя:</b>
/grant_vip [id] [срок] - Выдать VIP
/revoke_vip [id] - Забрать VIP
/users - Список пользователей
/broadcast [текст] - Рассылка
/stats - Полная статистика
/backup - Резервная копия
"""
    
    help_text += "\n<i>💡 Просто напиши мне что-нибудь - я отвечу!</i>"
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /info"""
    info_text = """
🤖 <b>AI DISCO BOT</b>

<b>Версия:</b> 2.0
<b>AI Модель:</b> Google Gemini 2.0 Flash
<b>Создатель:</b> @Ernest_Kostevich

<b>🎯 О боте:</b>
Многофункциональный бот с искусственным интеллектом для Telegram. Умеет общаться, помогать, развлекать и многое другое!

<b>⚡ Особенности:</b>
• Контекстный AI-диалог
• Система памяти
• VIP функции
• Напоминания
• Игры и развлечения
• Погода и время

<b>🔒 Приватность:</b>
Все данные хранятся безопасно. Мы не передаём вашу информацию третьим лицам.

<b>💬 Поддержка:</b>
По всем вопросам: @Ernest_Kostevich
"""
    
    await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    stats = storage.stats
    total_users = len(storage.users)
    vip_users = sum(1 for u in storage.users.values() if u['vip'])
    
    uptime = datetime.now() - datetime.fromisoformat(stats.get('start_date', datetime.now().isoformat()))
    uptime_str = f"{uptime.days}д {uptime.seconds // 3600}ч {(uptime.seconds % 3600) // 60}м"
    
    status_text = f"""
📊 <b>СТАТУС СИСТЕМЫ</b>

<b>👥 Пользователи:</b>
• Всего: {total_users}
• VIP: {vip_users}

<b>📈 Активность:</b>
• Сообщений: {stats.get('total_messages', 0)}
• Команд: {stats.get('total_commands', 0)}
• AI запросов: {stats.get('ai_requests', 0)}

<b>⏱ Время работы:</b> {uptime_str}

<b>✅ Статус:</b> Онлайн
<b>🤖 AI:</b> Gemini 2.0 ✓
"""
    
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile"""
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    profile_text = format_user_info(user)
    profile_text += f"\n📝 <b>Заметок:</b> {len(user['notes'])}\n"
    profile_text += f"🧠 <b>Записей в памяти:</b> {len(user['memory'])}\n"
    
    if storage.is_vip(user_id):
        profile_text += f"⏰ <b>Напоминаний:</b> {len(user['reminders'])}\n"
    
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

# ====================
# AI ФУНКЦИИ
# ====================

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ai"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /ai [ваш вопрос]\n\n"
            "Пример: /ai Расскажи интересный факт"
        )
        return
    
    question = ' '.join(context.args)
    await process_ai_message(update, question, user_id)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /clear - очистка контекста"""
    user_id = update.effective_user.id
    storage.clear_chat_session(user_id)
    
    await update.message.reply_text(
        "🧹 Контекст диалога очищен! Начнём с чистого листа."
    )

async def process_ai_message(update: Update, text: str, user_id: int):
    """Обработка AI сообщения"""
    try:
        # Показываем, что бот думает
        await update.message.chat.send_action("typing")
        
        # Получаем сессию чата для контекста
        chat = storage.get_chat_session(user_id)
        
        # Отправляем запрос к Gemini
        response = chat.send_message(text)
        
        # Обновляем статистику
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        # Отправляем ответ
        await update.message.reply_text(
            response.text,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        await update.message.reply_text(
            "😔 Извините, произошла ошибка при обработке вашего запроса. Попробуйте ещё раз."
        )

# ====================
# СИСТЕМА ПАМЯТИ
# ====================

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /memorysave - сохранение в память"""
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /memorysave [ключ] [значение]\n\n"
            "Пример: /memorysave любимый_цвет синий"
        )
        return
    
    key = context.args[0]
    value = ' '.join(context.args[1:])
    
    user = storage.get_user(user_id)
    user['memory'][key] = value
    storage.save_users()
    
    await update.message.reply_text(
        f"✅ Сохранено в память:\n"
        f"🔑 <b>{key}</b> = <code>{value}</code>",
        parse_mode=ParseMode.HTML
    )

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /memoryget - получение из памяти"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /memoryget [ключ]\n\n"
            "Пример: /memoryget любимый_цвет"
        )
        return
    
    key = context.args[0]
    user = storage.get_user(user_id)
    
    if key in user['memory']:
        await update.message.reply_text(
            f"🔍 Найдено:\n"
            f"🔑 <b>{key}</b> = <code>{user['memory'][key]}</code>",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти.")

async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /memorylist - список всей памяти"""
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not user['memory']:
        await update.message.reply_text("📭 Ваша память пуста.")
        return
    
    memory_text = "🧠 <b>Ваша память:</b>\n\n"
    for key, value in user['memory'].items():
        memory_text += f"🔑 <b>{key}</b>: <code>{value}</code>\n"
    
    await update.message.reply_text(memory_text, parse_mode=ParseMode.HTML)

async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /memorydel - удаление из памяти"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /memorydel [ключ]\n\n"
            "Пример: /memorydel любимый_цвет"
        )
        return
    
    key = context.args[0]
    user = storage.get_user(user_id)
    
    if key in user['memory']:
        del user['memory'][key]
        storage.save_users()
        await update.message.reply_text(f"✅ Ключ '{key}' удалён из памяти.")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти.")

# ====================
# ЗАМЕТКИ
# ====================

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /note - создание заметки"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /note [текст заметки]\n\n"
            "Пример: /note Купить молоко"
        )
        return
    
    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)
    
    note = {
        'text': note_text,
        'created': datetime.now().isoformat()
    }
    
    user['notes'].append(note)
    storage.save_users()
    
    await update.message.reply_text(
        f"✅ Заметка #{len(user['notes'])} сохранена!\n\n"
        f"📝 {note_text}"
    )

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /notes - показать все заметки"""
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if not user['notes']:
        await update.message.reply_text("📭 У вас пока нет заметок.")
        return
    
    notes_text = f"📝 <b>Ваши заметки ({len(user['notes'])}):</b>\n\n"
    
    for i, note in enumerate(user['notes'], 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y %H:%M')})\n"
        notes_text += f"{note['text']}\n\n"
    
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /delnote - удаление заметки"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /delnote [номер]\n\n"
            "Пример: /delnote 1"
        )
        return
    
    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        
        if 1 <= note_num <= len(user['notes']):
            deleted_note = user['notes'].pop(note_num - 1)
            storage.save_users()
            await update.message.reply_text(
                f"✅ Заметка #{note_num} удалена:\n\n"
                f"📝 {deleted_note['text']}"
            )
        else:
            await update.message.reply_text(f"❌ Заметка #{note_num} не найдена.")
    except ValueError:
        await update.message.reply_text("❌ Укажите корректный номер заметки.")

# ====================
# УТИЛИТЫ
# ====================

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /time - текущее время"""
    city = ' '.join(context.args) if context.args else 'Moscow'
    
    timezones = {
        'moscow': 'Europe/Moscow',
        'london': 'Europe/London',
        'new york': 'America/New_York',
        'tokyo': 'Asia/Tokyo',
        'paris': 'Europe/Paris',
        'berlin': 'Europe/Berlin',
        'dubai': 'Asia/Dubai',
        'sydney': 'Australia/Sydney',
        'los angeles': 'America/Los_Angeles',
        'beijing': 'Asia/Shanghai'
    }
    
    city_lower = city.lower()
    tz_name = timezones.get(city_lower, 'Europe/Moscow')
    
    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        
        time_text = f"""
⏰ <b>Текущее время</b>

📍 <b>Город:</b> {city.title()}
🕐 <b>Время:</b> {current_time.strftime('%H:%M:%S')}
📅 <b>Дата:</b> {current_time.strftime('%d.%m.%Y')}
🌍 <b>Часовой пояс:</b> {tz_name}
"""
        await update.message.reply_text(time_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка получения времени: {e}")
        await update.message.reply_text(
            f"❌ Не удалось получить время для города '{city}'.\n"
            f"Доступные города: Moscow, London, New York, Tokyo, Paris, Berlin, Dubai, Sydney, Los Angeles, Beijing"
        )

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /weather - погода"""
    if not OPENWEATHER_API_KEY:
        await update.message.reply_text("❌ API ключ погоды не настроен.")
        return
    
    city = ' '.join(context.args) if context.args else 'Moscow'
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    temp = data['main']['temp']
                    feels_like = data['main']['feels_like']
                    description = data['weather'][0]['description']
                    humidity = data['main']['humidity']
                    wind_speed = data['wind']['speed']
                    
                    weather_text = f"""
🌤 <b>Погода в {city.title()}</b>

🌡 <b>Температура:</b> {temp}°C
🤔 <b>Ощущается как:</b> {feels_like}°C
☁️ <b>Описание:</b> {description}
💧 <b>Влажность:</b> {humidity}%
💨 <b>Ветер:</b> {wind_speed} м/с
"""
                    await update.message.reply_text(weather_text, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(f"❌ Город '{city}' не найден.")
    except Exception as e:
        logger.error(f"Ошибка получения погоды: {e}")
        await update.message.reply_text("❌ Ошибка при получении данных о погоде.")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /translate - перевод текста"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /translate [язык] [текст]\n\n"
            "Пример: /translate en Привет, как дела?"
        )
        return
    
    target_lang = context.args[0]
    text = ' '.join(context.args[1:])
    
    try:
        # Используем Gemini для перевода
        prompt = f"Переведи следующий текст на {target_lang}: {text}"
        chat = storage.get_chat_session(update.effective_user.id)
        response = chat.send_message(prompt)
        
        await update.message.reply_text(
            f"🌐 <b>Перевод:</b>\n\n{response.text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        await update.message.reply_text("❌ Ошибка при переводе текста.")

# ====================
# РАЗВЛЕЧЕНИЯ
# ====================

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /random - случайное число"""
    try:
        if len(context.args) >= 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        else:
            min_val = 1
            max_val = 100
        
        result = random.randint(min_val, max_val)
        await update.message.reply_text(
            f"🎲 Случайное число от {min_val} до {max_val}:\n\n"
            f"<b>{result}</b>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректные числа.")

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /dice - бросить кубик"""
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    
    await update.message.reply_text(
        f"🎲 Бросаем кубик...\n\n"
        f"{dice_emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /coin - подбросить монету"""
    result = random.choice(['Орёл', 'Решка'])
    emoji = '🦅' if result == 'Орёл' else '💰'
    
    await update.message.reply_text(
        f"🪙 Подбрасываем монету...\n\n"
        f"{emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /joke - случайная шутка"""
    jokes = [
        "Программист ложится спать. Жена говорит: — Дорогой, закрой окно, на улице холодно! Программист: — И что, если я закрою окно, на улице станет тепло? 😄",
        "— Почему программисты путают Хэллоуин и Рождество? — Потому что 31 OCT = 25 DEC! 🎃🎄",
        "Зачем программисту очки? Чтобы лучше C++! 👓",
        "Искусственный интеллект никогда не заменит человека. Он слишком умный для этого! 🤖",
        "— Сколько программистов нужно, чтобы вкрутить лампочку? — Ни одного, это аппаратная проблема! 💡"
    ]
    
    joke = random.choice(jokes)
    await update.message.reply_text(f"😄 <b>Шутка дня:</b>\n\n{joke}", parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /quote - мудрая цитата"""
    quotes = [
        "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
        "Инновация отличает лидера от последователя. — Стив Джобс",
        "Программирование — это искусство превращать кофе в код. — Неизвестный автор",
        "Лучший код — это отсутствие кода. — Джефф Этвуд",
        "Сначала сделай это, потом сделай правильно, потом сделай лучше. — Адди Османи"
    ]
    
    quote = random.choice(quotes)
    await update.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{quote}</i>", parse_mode=ParseMode.HTML)

# ====================
# VIP ФУНКЦИИ
# ====================

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /vip - статус VIP"""
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    
    if storage.is_vip(user_id):
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n"
        vip_text += "✅ У вас активен VIP статус!\n\n"
        
        if user['vip_until']:
            vip_until = datetime.fromisoformat(user['vip_until'])
            vip_text += f"⏰ <b>Активен до:</b> {vip_until.strftime('%d.%m.%Y %H:%M')}\n\n"
        else:
            vip_text += "⏰ <b>Активен:</b> Навсегда ♾️\n\n"
        
        vip_text += "<b>🎁 Преимущества VIP:</b>\n"
        vip_text += "• ⏰ Система напоминаний\n"
        vip_text += "• 🎯 Приоритетная обработка\n"
        vip_text += "• 🚀 Расширенные возможности\n"
        vip_text += "• 💬 Увеличенный контекст AI\n"
    else:
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n"
        vip_text += "❌ У вас нет VIP статуса.\n\n"
        vip_text += "Свяжитесь с @Ernest_Kostevich для получения VIP."
    
    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /remind - создать напоминание (VIP)"""
    user_id = update.effective_user.id
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Эта команда доступна только VIP пользователям.\n"
            "Свяжитесь с @Ernest_Kostevich для получения VIP."
        )
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /remind [минуты] [текст]\n\n"
            "Пример: /remind 30 Проверить почту"
        )
        return
    
    try:
        minutes = int(context.args[0])
        text = ' '.join(context.args[1:])
        
        remind_time = datetime.now() + timedelta(minutes=minutes)
        
        user = storage.get_user(user_id)
        reminder = {
            'text': text,
            'time': remind_time.isoformat(),
            'created': datetime.now().isoformat()
        }
        
        user['reminders'].append(reminder)
        storage.save_users()
        
        # Планируем напоминание
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=remind_time,
            args=[context.bot, user_id, text]
        )
        
        await update.message.reply_text(
            f"⏰ Напоминание создано!\n\n"
            f"📝 {text}\n"
            f"🕐 Напомню через {minutes} минут ({remind_time.strftime('%H:%M')})"
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректное количество минут.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /reminders - список напоминаний (VIP)"""
    user_id = update.effective_user.id
    
    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Эта команда доступна только VIP пользователям."
        )
        return
    
    user = storage.get_user(user_id)
    
    if not user['reminders']:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")
        return
    
    reminders_text = f"⏰ <b>Ваши напоминания ({len(user['reminders'])}):</b>\n\n"
    
    for i, reminder in enumerate(user['reminders'], 1):
        remind_time = datetime.fromisoformat(reminder['time'])
        reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n"
        reminders_text += f"📝 {reminder['text']}\n\n"
    
    await update.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)

async def send_reminder(bot, user_id: int, text: str):
    """Отправка напоминания"""
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
            parse_mode=ParseMode.HTML
        )
        
        # Удаляем выполненное напоминание
        user = storage.get_user(user_id)
        user['reminders'] = [r for r in user['reminders'] if r['text'] != text]
        storage.save_users()
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")

# ====================
# КОМАНДЫ СОЗДАТЕЛЯ
# ====================

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /grant_vip - выдать VIP (только создатель)"""
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /grant_vip [user_id] [срок]\n\n"
            "Сроки: week, month, year, forever\n"
            "Пример: /grant_vip 123456789 month"
        )
        return
    
    try:
        target_id = int(context.args[0])
        duration = context.args[1].lower()
        
        durations = {
            'week': timedelta(weeks=1),
            'month': timedelta(days=30),
            'year': timedelta(days=365),
            'forever': None
        }
        
        if duration not in durations:
            await update.message.reply_text("❌ Неверный срок. Используйте: week, month, year, forever")
            return
        
        user = storage.get_user(target_id)
        user['vip'] = True
        
        if durations[duration]:
            vip_until = datetime.now() + durations[duration]
            user['vip_until'] = vip_until.isoformat()
            duration_text = f"до {vip_until.strftime('%d.%m.%Y')}"
        else:
            user['vip_until'] = None
            duration_text = "навсегда"
        
        storage.save_users()
        
        await update.message.reply_text(
            f"✅ VIP статус выдан!\n\n"
            f"👤 ID: <code>{target_id}</code>\n"
            f"⏰ Срок: {duration_text}",
            parse_mode=ParseMode.HTML
        )
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 Поздравляем! Вам выдан VIP статус {duration_text}!",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ Укажите корректный user_id.")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /revoke_vip - забрать VIP (только создатель)"""
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /revoke_vip [user_id]\n\n"
            "Пример: /revoke_vip 123456789"
        )
        return
    
    try:
        target_id = int(context.args[0])
        user = storage.get_user(target_id)
        user['vip'] = False
        user['vip_until'] = None
        storage.save_users()
        
        await update.message.reply_text(
            f"✅ VIP статус отозван!\n\n"
            f"👤 ID: <code>{target_id}</code>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректный user_id.")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /users - список пользователей (только создатель)"""
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    
    users_text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ ({len(storage.users)}):</b>\n\n"
    
    for user_id, user in list(storage.users.items())[:20]:  # Показываем первых 20
        vip_badge = "💎" if user['vip'] else ""
        users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"
        if user.get('username'):
            users_text += f"   @{user['username']}\n"
    
    if len(storage.users) > 20:
        users_text += f"\n<i>... и ещё {len(storage.users) - 20} пользователей</i>"
    
    await update.message.reply_text(users_text, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /broadcast - рассылка (только создатель)"""
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /broadcast [текст сообщения]\n\n"
            "Пример: /broadcast Привет всем!"
        )
        return
    
    message_text = ' '.join(context.args)
    
    success = 0
    failed = 0
    
    status_msg = await update.message.reply_text("📤 Начинаю рассылку...")
    
    for user_id in storage.users.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>Сообщение от создателя:</b>\n\n{message_text}",
                parse_mode=ParseMode.HTML
            )
            success += 1
            await asyncio.sleep(0.05)  # Задержка для избежания лимитов
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка рассылки для {user_id}: {e}")
    
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - полная статистика (только создатель)"""
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    
    stats = storage.stats
    total_users = len(storage.users)
    vip_users = sum(1 for u in storage.users.values() if u['vip'])
    active_users = sum(1 for u in storage.users.values() 
                      if (datetime.now() - datetime.fromisoformat(u['last_active'])).days < 7)
    
    total_notes = sum(len(u['notes']) for u in storage.users.values())
    total_memory = sum(len(u['memory']) for u in storage.users.values())
    
    stats_text = f"""
📊 <b>ПОЛНАЯ СТАТИСТИКА</b>

<b>👥 Пользователи:</b>
• Всего: {total_users}
• VIP: {vip_users}
• Активных (7 дней): {active_users}

<b>📈 Активность:</b>
• Сообщений: {stats.get('total_messages', 0)}
• Команд: {stats.get('total_commands', 0)}
• AI запросов: {stats.get('ai_requests', 0)}

<b>📝 Данные:</b>
• Заметок: {total_notes}
• Записей в памяти: {total_memory}

<b>📅 Запущен:</b> {stats.get('start_date', 'N/A')[:10]}
"""
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /backup - резервная копия (только создатель)"""
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    
    try:
        # Создаём резервные копии
        backup_data = {
            'users': storage.users,
            'stats': storage.stats,
            'backup_date': datetime.now().isoformat()
        }
        
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        # Отправляем файл
        await update.message.reply_document(
            document=open(backup_filename, 'rb'),
            caption=f"✅ Резервная копия создана!\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        # Удаляем временный файл
        os.remove(backup_filename)
        
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")
        await update.message.reply_text("❌ Ошибка при создании резервной копии.")

# ====================
# ОБРАБОТКА СООБЩЕНИЙ
# ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text
    
    # Обновляем статистику
    user = storage.get_user(user_id)
    storage.update_user(user_id, {
        'messages_count': user['messages_count'] + 1,
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # Обработка кнопок меню
    if text in ["💬 AI Чат", "📝 Заметки", "🌍 Погода", "⏰ Время", "🎲 Развлечения", "ℹ️ Инфо", "💎 VIP Меню", "👑 Админ Панель"]:
        await handle_menu_button(update, context, text)
        return
    
    # В группах отвечаем только на упоминания
    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        # Убираем упоминание из текста
        text = text.replace(f"@{bot_username}", "").strip()
    
    # Отправляем в AI
    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str):
    """Обработка нажатий на кнопки меню"""
    user_id = update.effective_user.id
    
    if button == "💬 AI Чат":
        await update.message.reply_text(
            "🤖 <b>AI Чат режим</b>\n\n"
            "Просто напиши мне что-нибудь, и я отвечу!\n"
            "Используй /clear чтобы очистить контекст.",
            parse_mode=ParseMode.HTML
        )
    
    elif button == "📝 Заметки":
        keyboard = [
            [InlineKeyboardButton("➕ Создать заметку", callback_data="note_create")],
            [InlineKeyboardButton("📋 Мои заметки", callback_data="note_list")]
        ]
        await update.message.reply_text(
            "📝 <b>Система заметок</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button == "🌍 Погода":
        await update.message.reply_text(
            "🌍 <b>Погода</b>\n\n"
            "Используй: /weather [город]\n"
            "Пример: /weather London",
            parse_mode=ParseMode.HTML
        )
    
    elif button == "⏰ Время":
        await update.message.reply_text(
            "⏰ <b>Текущее время</b>\n\n"
            "Используй: /time [город]\n"
            "Пример: /time Tokyo",
            parse_mode=ParseMode.HTML
        )
    
    elif button == "🎲 Развлечения":
        keyboard = [
            [InlineKeyboardButton("🎲 Кубик", callback_data="game_dice"),
             InlineKeyboardButton("🪙 Монета", callback_data="game_coin")],
            [InlineKeyboardButton("😄 Шутка", callback_data="game_joke"),
             InlineKeyboardButton("💭 Цитата", callback_data="game_quote")]
        ]
        await update.message.reply_text(
            "🎲 <b>Развлечения</b>\n\nВыбери что-нибудь:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button == "ℹ️ Инфо":
        await info_command(update, context)
    
    elif button == "💎 VIP Меню":
        if storage.is_vip(user_id):
            keyboard = [
                [InlineKeyboardButton("⏰ Напоминания", callback_data="vip_reminders")],
                [InlineKeyboardButton("📊 Статистика", callback_data="vip_stats")]
            ]
            await update.message.reply_text(
                "💎 <b>VIP Меню</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await vip_command(update, context)
    
    elif button == "👑 Админ Панель":
        if is_creator(user_id):
            keyboard = [
                [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
                [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")]
            ]
            await update.message.reply_text(
                "👑 <b>Админ Панель</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "note_create":
        await query.message.reply_text(
            "➕ <b>Создание заметки</b>\n\n"
            "Используй: /note [текст]\n"
            "Пример: /note Купить хлеб",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "note_list":
        await notes_command(update, context)
    
    elif data == "game_dice":
        result = random.randint(1, 6)
        dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
        await query.message.reply_text(f"🎲 {dice_emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)
    
    elif data == "game_coin":
        result = random.choice(['Орёл', 'Решка'])
        emoji = '🦅' if result == 'Орёл' else '💰'
        await query.message.reply_text(f"🪙 {emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)
    
    elif data == "game_joke":
        await joke_command(update, context)
    
    elif data == "game_quote":
        await quote_command(update, context)
    
    elif data == "vip_reminders":
        await reminders_command(update, context)
    
    elif data == "admin_users":
        await users_command(update, context)
    
    elif data == "admin_stats":
        await stats_command(update, context)

# ====================
# ГЛАВНАЯ ФУНКЦИЯ
# ====================

def main():
    """Запуск бота"""
    # Проверка токенов
    if not BOT_TOKEN or not GEMINI_API_KEY:
        logger.error("Ошибка: BOT_TOKEN или GEMINI_API_KEY не установлены!")
        return
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация команд - Базовые
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("profile", profile_command))
    
    # AI команды
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Память
    application.add_handler(CommandHandler("memorysave", memory_save_command))
    application.add_handler(CommandHandler("memoryget", memory_get_command))
    application.add_handler(CommandHandler("memorylist", memory_list_command))
    application.add_handler(CommandHandler("memorydel", memory_del_command))
    
    # Заметки
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("notes", notes_command))
    application.add_handler(CommandHandler("delnote", delnote_command))
    
    # Утилиты
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("translate", translate_command))
    
    # Развлечения
    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("quote", quote_command))
    
    # VIP команды
    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    
    # Команды создателя
    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("backup", backup_command))
    
    # Обработчики сообщений и callback
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запуск планировщика
    scheduler.start()
    
    # Запуск бота
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
