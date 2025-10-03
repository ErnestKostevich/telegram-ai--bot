#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import os
import json
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz
from threading import Thread
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from flask import Flask

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PORT = int(os.getenv('PORT', 10000))
APP_URL = os.getenv('APP_URL')  # e.g., https://your-bot.onrender.com

CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

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
    model_name='gemini-1.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="You are AI DISCO BOT, a friendly and helpful AI assistant built with Gemini. Respond in a friendly, engaging manner with emojis where appropriate. Your creator is @Ernest_Kostevich."
)

flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return 'OK', 200

@flask_app.route('/health')
def health():
    return 'Healthy', 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT)

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.users = self.load_users()
        self.stats = self.load_stats()
        self.chat_sessions = {}
        self.username_to_id = {}
        self.update_username_mapping()

    def load_users(self) -> Dict:
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        logger.warning("users.json is a list; converting to dictionary")
                        return {str(user['id']): user for user in data if 'id' in user}
                    return {str(k): v for k, v in data.items()}
            return {}
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}

    def save_users(self):
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            self.update_username_mapping()
        except Exception as e:
            logger.error(f"Error saving users: {e}")

    def load_stats(self) -> Dict:
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
            logger.error(f"Error loading stats: {e}")
            return {}

    def save_stats(self):
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")

    def update_username_mapping(self):
        self.username_to_id = {}
        for user_id, user_data in self.users.items():
            username = user_data.get('username')
            if username:
                self.username_to_id[username.lower()] = int(user_id)

    def get_user_id_by_identifier(self, identifier: str) -> Optional[int]:
        identifier = identifier.strip()
        if identifier.startswith('@'):
            identifier = identifier[1:]
        if identifier.isdigit():
            return int(identifier)
        return self.username_to_id.get(identifier.lower())

    def get_user(self, user_id: int) -> Dict:
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {
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
        return self.users[user_id_str]

    def update_user(self, user_id: int, data: Dict):
        user = self.get_user(user_id)
        user.update(data)
        user['last_active'] = datetime.now().isoformat()
        self.save_users()

    def is_vip(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user['vip']:
            return False
        if user['vip_until'] is None:
            return True
        vip_until = datetime.fromisoformat(user['vip_until'])
        if datetime.now() > vip_until:
            user['vip'] = False
            user['vip_until'] = None
            self.save_users()
            return False
        return True

    def get_chat_session(self, user_id: int):
        user_id_str = str(user_id)
        if user_id_str not in self.chat_sessions:
            self.chat_sessions[user_id_str] = model.start_chat(history=[])
        return self.chat_sessions[user_id_str]

    def clear_chat_session(self, user_id: int):
        user_id_str = str(user_id)
        if user_id_str in self.chat_sessions:
            del self.chat_sessions[user_id_str]

storage = DataStorage()
scheduler = AsyncIOScheduler()

def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Creator identified: {user.id}")

def is_creator(user_id: int) -> bool:
    global CREATOR_ID
    return user_id == CREATOR_ID

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
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

async def get_weather_data(city: str) -> Optional[Dict]:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?format=j1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'commands_count': user_data['commands_count'] + 1
    })
    welcome_text = f"""
🤖 <b>Добро пожаловать в AI DISCO BOT!</b>
Привет, {user.first_name}! Я многофункциональный бот с искусственным интеллектом на базе <b>Google Gemini</b>.
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
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'commands_count': user_data['commands_count'] + 1})
    help_text = """
📚 <b>СПИСОК КОМАНД</b>
<b>🏠 Основные:</b>
/start - Запуск бота
/help - Эта справка
/info - Информация о боте
/status - Статус системы
/profile - Твой профиль
/uptime - Время работы бота
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
/fact - Интересный факт
<b>💎 VIP Команды:</b>
/vip - Твой VIP статус
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
"""
    if is_creator(user_id):
        help_text += """
<b>👑 Команды Создателя:</b>
/grant_vip [id/@username] [срок] - Выдать VIP
/revoke_vip [id/@username] - Забрать VIP
/users - Список пользователей
/broadcast [текст] - Рассылка
/stats - Полная статистика
/backup - Резервная копия
"""
    help_text += "\n<i>💡 Просто напиши мне что-нибудь - я отвечу!</i>"
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = """
🤖 <b>AI DISCO BOT</b>
<b>Версия:</b> 2.1
<b>AI Модель:</b> Google Gemini
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
<b>🤖 AI:</b> Gemini ✓
"""
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    profile_text = format_user_info(user)
    profile_text += f"\n📝 <b>Заметок:</b> {len(user['notes'])}\n"
    profile_text += f"🧠 <b>Записей в памяти:</b> {len(user['memory'])}\n"
    if storage.is_vip(user_id):
        profile_text += f"⏰ <b>Напоминаний:</b> {len(user['reminders'])}\n"
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - BOT_START_TIME
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    seconds = uptime.seconds % 60
    uptime_text = f"""
⏱ <b>ВРЕМЯ РАБОТЫ БОТА</b>
🕐 <b>Запущен:</b> {BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S')}
⏰ <b>Работает:</b> {days}д {hours}ч {minutes}м {seconds}с
<b>✅ Статус:</b> Онлайн и стабильно работает!
"""
    await update.message.reply_text(uptime_text, parse_mode=ParseMode.HTML)

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /ai [ваш вопрос]\n\nПример: /ai Расскажи интересный факт"
        )
        return
    question = ' '.join(context.args)
    await process_ai_message(update, question, user_id)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    storage.clear_chat_session(user_id)
    await update.message.reply_text("🧹 Контекст диалога очищен! Начнём с чистого листа.")

async def process_ai_message(update: Update, text: str, user_id: int):
    try:
        await update.message.chat.send_action("typing")
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        await update.message.reply_text(response.text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text("😔 Извините, произошла ошибка при обработке вашего запроса. Попробуйте ещё раз.")

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /memorysave [ключ] [значение]\n\nПример: /memorysave любимый_цвет синий"
        )
        return
    key = context.args[0]
    value = ' '.join(context.args[1:])
    user = storage.get_user(user_id)
    user['memory'][key] = value
    storage.save_users()
    await update.message.reply_text(
        f"✅ Сохранено в память:\n🔑 <b>{key}</b> = <code>{value}</code>",
        parse_mode=ParseMode.HTML
    )

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /memoryget [ключ]\n\nПример: /memoryget любимый_цвет"
        )
        return
    key = context.args[0]
    user = storage.get_user(user_id)
    if key in user['memory']:
        await update.message.reply_text(
            f"🔍 Найдено:\n🔑 <b>{key}</b> = <code>{user['memory'][key]}</code>",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти.")

async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /memorydel [ключ]\n\nПример: /memorydel любимый_цвет"
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

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /note [текст заметки]\n\nПример: /note Купить молоко"
        )
        return
    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)
    note = {'text': note_text, 'created': datetime.now().isoformat()}
    user['notes'].append(note)
    storage.save_users()
    await update.message.reply_text(
        f"✅ Заметка #{len(user['notes'])} сохранена!\n\n📝 {note_text}"
    )

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    if not user['notes']:
        await update.message.reply_text("📭 У вас пока нет заметок.")
        return
    notes_text = f"📝 <b>Ваши заметки ({len(user['notes'])}):</b>\n\n"
    for i, note in enumerate(user['notes'], 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y %H:%M')})\n{note['text']}\n\n"
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /delnote [номер]\n\nПример: /delnote 1"
        )
        return
    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        if 1 <= note_num <= len(user['notes']):
            deleted_note = user['notes'].pop(note_num - 1)
            storage.save_users()
            await update.message.reply_text(
                f"✅ Заметка #{note_num} удалена:\n\n📝 {deleted_note['text']}"
            )
        else:
            await update.message.reply_text(f"❌ Заметка #{note_num} не найдена.")
    except ValueError:
        await update.message.reply_text("❌ Укажите корректный номер заметки.")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = ' '.join(context.args) if context.args else 'Moscow'
    timezones = {
        'moscow': 'Europe/Moscow', 'london': 'Europe/London', 'new york': 'America/New_York',
        'tokyo': 'Asia/Tokyo', 'paris': 'Europe/Paris', 'berlin': 'Europe/Berlin',
        'dubai': 'Asia/Dubai', 'sydney': 'Australia/Sydney', 'los angeles': 'America/Los_Angeles',
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
        logger.error(f"Time error: {e}")
        await update.message.reply_text(
            f"❌ Не удалось получить время для города '{city}'.\nДоступные города: Moscow, London, New York, Tokyo, Paris, Berlin, Dubai, Sydney, Los Angeles, Beijing"
        )

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = ' '.join(context.args) if context.args else 'Moscow'
    try:
        weather_data = await get_weather_data(city)
        if weather_data and 'current_condition' in weather_data:
            current = weather_data['current_condition'][0]
            temp_c = current['temp_C']
            feels_like = current['FeelsLikeC']
            description = current['weatherDesc'][0]['value']
            humidity = current['humidity']
            wind_speed = current['windspeedKmph']
            weather_emojis = {
                'Sunny': '☀️', 'Clear': '🌙', 'Partly cloudy': '⛅', 'Cloudy': '☁️', 'Overcast': '☁️', 'Mist': '🌫️',
                'Patchy rain possible': '🌦️', 'Light rain': '🌧️', 'Moderate rain': '🌧️', 'Heavy rain': '⛈️',
                'Patchy snow possible': '🌨️', 'Light snow': '❄️', 'Moderate snow': '❄️', 'Heavy snow': '❄️'
            }
            emoji = weather_emojis.get(description, '🌤️')
            weather_text = f"""
{emoji} <b>Погода в {city.title()}</b>
🌡 <b>Температура:</b> {temp_c}°C
🤔 <b>Ощущается как:</b> {feels_like}°C
☁️ <b>Описание:</b> {description}
💧 <b>Влажность:</b> {humidity}%
💨 <b>Ветер:</b> {wind_speed} км/ч
"""
            await update.message.reply_text(weather_text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"❌ Город '{city}' не найден.")
    except Exception as e:
        logger.error(f"Weather error: {e}")
        await update.message.reply_text("❌ Ошибка при получении данных о погоде.")

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /translate [язык] [текст]\n\nПример: /translate en Привет, как дела?"
        )
        return
    target_lang = context.args[0]
    text = ' '.join(context.args[1:])
    try:
        prompt = f"Переведи следующий текст на {target_lang}: {text}"
        chat = storage.get_chat_session(update.effective_user.id)
        response = chat.send_message(prompt)
        await update.message.reply_text(f"🌐 <b>Перевод:</b>\n\n{response.text}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await update.message.reply_text("❌ Ошибка при переводе текста.")

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) >= 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        else:
            min_val = 1
            max_val = 100
        result = random.randint(min_val, max_val)
        await update.message.reply_text(
            f"🎲 Случайное число от {min_val} до {max_val}:\n\n<b>{result}</b>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректные числа.")

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    await update.message.reply_text(
        f"🎲 Бросаем кубик...\n\n{dice_emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(['Орёл', 'Решка'])
    emoji = '🦅' if result == 'Орёл' else '💰'
    await update.message.reply_text(
        f"🪙 Подбрасываем монету...\n\n{emoji} Выпало: <b>{result}</b>",
        parse_mode=ParseMode.HTML
    )

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Программист ложится спать. Жена говорит: — Дорогой, закрой окно, на улице холодно! Программист: — И что, если я закрою окно, на улице станет тепло? 😄",
        "— Почему программисты путают Хэллоуин и Рождество? — Потому что 31 OCT = 25 DEC! 🎃🎄",
        "Зачем программисту очки? Чтобы лучше C++! 👓",
        "Искусственный интеллект никогда не заменит человека. Он слишком умный для этого! 🤖",
        "— Сколько программистов нужно, чтобы вкрутить лампочку? — Ни одного, это аппаратная проблема! 💡",
        "Жена программиста просит: — Сходи в магазин, купи батон хлеба, и если будут яйца — возьми десяток. Он приходит с 10 батонами. — Зачем?! — Ну, яйца же были! 🥚",
        "— Что такое рекурсия? — Чтобы понять что такое рекурсия, нужно сначала понять что такое рекурсия… 🔄"
    ]
    joke = random.choice(jokes)
    await update.message.reply_text(f"😄 <b>Шутка дня:</b>\n\n{joke}", parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
        "Инновация отличает лидера от последователя. — Стив Джобс",
        "Программирование — это искусство превращать кофе в код. — Неизвестный автор",
        "Лучший код — это отсутствие кода. — Джефф Этвуд",
        "Сначала сделай это, потом сделай правильно, потом сделай лучше. — Адди Османи",
        "Простота — залог надёжности. — Эдсгер Дейкстра",
        "Любой дурак может написать код, который поймёт компьютер. Хорошие программисты пишут код, который поймут люди. — Мартин Фаулер"
    ]
    quote = random.choice(quotes)
    await update.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{quote}</i>", parse_mode=ParseMode.HTML)

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = [
        "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
        "🐙 У осьминогов три сердца и голубая кровь.",
        "🍯 Мёд — единственный продукт питания, который не портится тысячи лет.",
        "💎 Алмазы формируются на глубине около 150 км под землёй.",
        "🧠 Человеческий мозг потребляет около 20% всей энергии тела.",
        "🌊 95% мирового океана остаются неисследованными.",
        "⚡ Молния в 5 раз горячее поверхности Солнца.",
        "🦈 Акулы существуют дольше, чем деревья — более 400 миллионов лет!"
    ]
    fact = random.choice(facts)
    await update.message.reply_text(f"🔬 <b>Интересный факт:</b>\n\n{fact}", parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    if storage.is_vip(user_id):
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n✅ У вас активен VIP статус!\n\n"
        if user['vip_until']:
            vip_until = datetime.fromisoformat(user['vip_until'])
            vip_text += f"⏰ <b>Активен до:</b> {vip_until.strftime('%d.%m.%Y %H:%M')}\n\n"
        else:
            vip_text += "⏰ <b>Активен:</b> Навсегда ♾️\n\n"
        vip_text += "<b>🎁 Преимущества VIP:</b>\n• ⏰ Система напоминаний\n• 🎯 Приоритетная обработка\n• 🚀 Расширенные возможности\n• 💬 Увеличенный контекст AI\n"
    else:
        vip_text = "💎 <b>VIP СТАТУС</b>\n\n❌ У вас нет VIP статуса.\n\nСвяжитесь с @Ernest_Kostevich для получения VIP."
    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text(
            "💎 Эта команда доступна только VIP пользователям.\nСвяжитесь с @Ernest_Kostevich для получения VIP."
        )
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /remind [минуты] [текст]\n\nПример: /remind 30 Проверить почту"
        )
        return
    try:
        minutes = int(context.args[0])
        text = ' '.join(context.args[1:])
        remind_time = datetime.now() + timedelta(minutes=minutes)
        user = storage.get_user(user_id)
        reminder = {'text': text, 'time': remind_time.isoformat(), 'created': datetime.now().isoformat()}
        user['reminders'].append(reminder)
        storage.save_users()
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=remind_time,
            args=[context.bot, user_id, text]
        )
        await update.message.reply_text(
            f"⏰ Напоминание создано!\n\n📝 {text}\n🕐 Напомню через {minutes} минут ({remind_time.strftime('%H:%M')})"
        )
    except ValueError:
        await update.message.reply_text("❌ Укажите корректное количество минут.")

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not storage.is_vip(user_id):
        await update.message.reply_text("💎 Эта команда доступна только VIP пользователям.")
        return
    user = storage.get_user(user_id)
    if not user['reminders']:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")
        return
    reminders_text = f"⏰ <b>Ваши напоминания ({len(user['reminders'])}):</b>\n\n"
    for i, reminder in enumerate(user['reminders'], 1):
        remind_time = datetime.fromisoformat(reminder['time'])
        reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n📝 {reminder['text']}\n\n"
    await update.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)

async def send_reminder(bot, user_id: int, text: str):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
            parse_mode=ParseMode.HTML
        )
        user = storage.get_user(user_id)
        user['reminders'] = [r for r in user['reminders'] if r['text'] != text]
        storage.save_users()
    except Exception as e:
        logger.error(f"Reminder error: {e}")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "❓ Использование: /grant_vip [id/@username] [срок]\n\nСроки: week, month, year, forever\nПример: /grant_vip @username month\nПример: /grant_vip 123456789 forever"
        )
        return
    try:
        identifier = context.args[0]
        duration = context.args[1].lower()
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
            return
        durations = {'week': timedelta(weeks=1), 'month': timedelta(days=30), 'year': timedelta(days=365), 'forever': None}
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
        username_info = f"@{user['username']}" if user.get('username') else ""
        await update.message.reply_text(
            f"✅ VIP статус выдан!\n\n👤 {user.get('first_name', 'Unknown')} {username_info}\n🆔 ID: <code>{target_id}</code>\n⏰ Срок: {duration_text}",
            parse_mode=ParseMode.HTML
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 Поздравляем! Вам выдан VIP статус {duration_text}!",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    except Exception as e:
        logger.error(f"Grant VIP error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /revoke_vip [id/@username]\n\nПример: /revoke_vip @username\nПример: /revoke_vip 123456789"
        )
        return
    try:
        identifier = context.args[0]
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(f"❌ Пользователь '{identifier}' не найден.")
            return
        user = storage.get_user(target_id)
        user['vip'] = False
        user['vip_until'] = None
        storage.save_users()
        username_info = f"@{user['username']}" if user.get('username') else ""
        await update.message.reply_text(
            f"✅ VIP статус отозван!\n\n👤 {user.get('first_name', 'Unknown')} {username_info}\n�ID: <code>{target_id}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Revoke VIP error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    users_text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ ({len(storage.users)}):</b>\n\n"
    for user_id, user in list(storage.users.items())[:20]:
        vip_badge = "💎" if user['vip'] else ""
        users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"
        if user.get('username'):
            users_text += f"   @{user['username']}\n"
    if len(storage.users) > 20:
        users_text += f"\n<i>... и ещё {len(storage.users) - 20} пользователей</i>"
    await update.message.reply_text(users_text, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    if not context.args:
        await update.message.reply_text(
            "❓ Использование: /broadcast [текст сообщения]\n\nПример: /broadcast Привет всем!"
        )
        return
    message_text = ' '.join(context.args)
    success = 0
    failed = 0
    status_msg = await update.message.reply_text("📤 Начинаю рассылку...")
    for user_id in storage.users.keys():
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"📢 <b>Сообщение от создателя:</b>\n\n{message_text}",
                parse_mode=ParseMode.HTML
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast error for {user_id}: {e}")
    await status_msg.edit_text(f"✅ Рассылка завершена!\n\n✅ Успешно: {success}\n❌ Ошибок: {failed}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    stats = storage.stats
    total_users = len(storage.users)
    vip_users = sum(1 for u in storage.users.values() if u['vip'])
    active_users = sum(1 for u in storage.users.values() if (datetime.now() - datetime.fromisoformat(u['last_active'])).days < 7)
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
    identify_creator(update.effective_user)
    if not is_creator(update.effective_user.id):
        await update.message.reply_text("❌ Эта команда доступна только создателю.")
        return
    try:
        backup_data = {'users': storage.users, 'stats': storage.stats, 'backup_date': datetime.now().isoformat()}
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        await update.message.reply_document(
            document=open(backup_filename, 'rb'),
            caption=f"✅ Резервная копия создана!\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        os.remove(backup_filename)
    except Exception as e:
        logger.error(f"Backup error: {e}")
        await update.message.reply_text("❌ Ошибка при создании резервной копии.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text
    user = storage.get_user(user_id)
    storage.update_user(user_id, {
        'messages_count': user['messages_count'] + 1,
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    if text in ["💬 AI Чат", "📝 Заметки", "🌍 Погода", "⏰ Время", "🎲 Развлечения", "ℹ️ Инфо", "💎 VIP Меню", "👑 Админ Панель"]:
        await handle_menu_button(update, context, text)
        return
    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()
    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str):
    user_id = update.effective_user.id
    if button == "💬 AI Чат":
        await update.message.reply_text(
            "🤖 <b>AI Чат режим</b>\n\nПросто напиши мне что-нибудь, и я отвечу!\nИспользуй /clear чтобы очистить контекст.",
            parse_mode=ParseMode.HTML
        )
    elif button == "📝 Заметки":
        keyboard = [
            [InlineKeyboardButton("➕ Создать заметку", callback_data="note_create")],
            [InlineKeyboardButton("📋 Мои заметки", callback_data="note_list")]
        ]
        await update.message.reply_text(
            "📝 <b>Система заметок</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif button == "🌍 Погода":
        await update.message.reply_text(
            "🌍 <b>Погода</b>\n\nИспользуй: /weather [город]\nПример: /weather London", parse_mode=ParseMode.HTML
        )
    elif button == "⏰ Время":
        await update.message.reply_text(
            "⏰ <b>Текущее время</b>\n\nИспользуй: /time [город]\nПример: /time Tokyo", parse_mode=ParseMode.HTML
        )
    elif button == "🎲 Развлечения":
        keyboard = [
            [InlineKeyboardButton("🎲 Кубик", callback_data="game_dice"), InlineKeyboardButton("🪙 Монета", callback_data="game_coin")],
            [InlineKeyboardButton("😄 Шутка", callback_data="game_joke"), InlineKeyboardButton("💭 Цитата", callback_data="game_quote")],
            [InlineKeyboardButton("🔬 Факт", callback_data="game_fact")]
        ]
        await update.message.reply_text(
            "🎲 <b>Развлечения</b>\n\nВыбери что-нибудь:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
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
                "💎 <b>VIP Меню</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
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
                "👑 <b>Админ Панель</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    identify_creator(query.from_user)
    if data == "note_create":
        await query.message.reply_text(
            "➕ <b>Создание заметки</b>\n\nИспользуй: /note [текст]\nПример: /note Купить хлеб", parse_mode=ParseMode.HTML
        )
    elif data == "note_list":
        user_id = query.from_user.id
        user = storage.get_user(user_id)
        if not user['notes']:
            await query.message.reply_text("📭 У вас пока нет заметок.")
            return
        notes_text = f"📝 <b>Ваши заметки ({len(user['notes'])}):</b>\n\n"
        for i, note in enumerate(user['notes'], 1):
            created = datetime.fromisoformat(note['created'])
            notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y %H:%M')})\n{note['text']}\n\n"
        await query.message.reply_text(notes_text, parse_mode=ParseMode.HTML)
    elif data == "game_dice":
        result = random.randint(1, 6)
        dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
        await query.message.reply_text(f"🎲 {dice_emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)
    elif data == "game_coin":
        result = random.choice(['Орёл', 'Решка'])
        emoji = '🦅' if result == 'Орёл' else '💰'
        await query.message.reply_text(f"🪙 {emoji} Выпало: <b>{result}</b>", parse_mode=ParseMode.HTML)
    elif data == "game_joke":
        jokes = [
            "Программист ложится спать. Жена говорит: — Дорогой, закрой окно, на улице холодно! Программист: — И что, если я закрою окно, на улице станет тепло? 😄",
            "— Почему программисты путают Хэллоуин и Рождество? — Потому что 31 OCT = 25 DEC! 🎃🎄",
            "Зачем программисту очки? Чтобы лучше C++! 👓",
            "Искусственный интеллект никогда не заменит человека. Он слишком умный для этого! 🤖",
            "— Сколько программистов нужно, чтобы вкрутить лампочку? — Ни одного, это аппаратная проблема! 💡"
        ]
        joke = random.choice(jokes)
        await query.message.reply_text(f"😄 <b>Шутка:</b>\n\n{joke}", parse_mode=ParseMode.HTML)
    elif data == "game_quote":
        quotes = [
            "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
            "Инновация отличает лидера от последователя. — Стив Джобс",
            "Программирование — это искусство превращать кофе в код. — Неизвестный автор",
            "Лучший код — это отсутствие кода. — Джефф Этвуд"
        ]
        quote = random.choice(quotes)
        await query.message.reply_text(f"💭 <b>Цитата:</b>\n\n<i>{quote}</i>", parse_mode=ParseMode.HTML)
    elif data == "game_fact":
        facts = [
            "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
            "🐙 У осьминогов три сердца и голубая кровь.",
            "🍯 Мёд — единственный продукт питания, который не портится тысячи лет.",
            "💎 Алмазы формируются на глубине около 150 км под землёй."
        ]
        fact = random.choice(facts)
        await query.message.reply_text(f"🔬 <b>Факт:</b>\n\n{fact}", parse_mode=ParseMode.HTML)
    elif data == "vip_reminders":
        user_id = query.from_user.id
        user = storage.get_user(user_id)
        if not user['reminders']:
            await query.message.reply_text("📭 У вас нет активных напоминаний.")
            return
        reminders_text = f"⏰ <b>Ваши напоминания ({len(user['reminders'])}):</b>\n\n"
        for i, reminder in enumerate(user['reminders'], 1):
            remind_time = datetime.fromisoformat(reminder['time'])
            reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n📝 {reminder['text']}\n\n"
        await query.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)
    elif data == "vip_stats":
        user_id = query.from_user.id
        user = storage.get_user(user_id)
        profile_text = format_user_info(user)
        profile_text += f"\n📝 <b>Заметок:</b> {len(user['notes'])}\n🧠 <b>Записей в памяти:</b> {len(user['memory'])}\n⏰ <b>Напоминаний:</b> {len(user['reminders'])}\n"
        await query.message.reply_text(profile_text, parse_mode=ParseMode.HTML)
    elif data == "admin_users":
        if not is_creator(query.from_user.id):
            await query.message.reply_text("❌ Доступ запрещён.")
            return
        users_text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ ({len(storage.users)}):</b>\n\n"
        for user_id, user in list(storage.users.items())[:20]:
            vip_badge = "💎" if user['vip'] else ""
            users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"
            if user.get('username'):
                users_text += f"   @{user['username']}\n"
        if len(storage.users) > 20:
            users_text += f"\n<i>... и ещё {len(storage.users) - 20} пользователей</i>"
        await query.message.reply_text(users_text, parse_mode=ParseMode.HTML)
    elif data == "admin_stats":
        if not is_creator(query.from_user.id):
            await query.message.reply_text("❌ Доступ запрещён.")
            return
        stats = storage.stats
        total_users = len(storage.users)
        vip_users = sum(1 for u in storage.users.values() if u['vip'])
        active_users = sum(1 for u in storage.users.values() if (datetime.now() - datetime.fromisoformat(u['last_active'])).days < 7)
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
        await query.message.reply_text(stats_text, parse_mode=ParseMode.HTML)
    elif data == "admin_broadcast":
        if not is_creator(query.from_user.id):
            await query.message.reply_text("❌ Доступ запрещён.")
            return
        await query.message.reply_text(
            "📢 <b>Рассылка</b>\n\nИспользуй: /broadcast [текст]\nПример: /broadcast Привет всем!", parse_mode=ParseMode.HTML
        )

def main():
    if not BOT_TOKEN or not GEMINI_API_KEY:
        logger.error("Error: BOT_TOKEN or GEMINI_API_KEY not set!")
        return

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask server started on port {PORT}")

    if APP_URL:
        def keep_awake():
            try:
                requests.get(APP_URL + '/health')
                logger.info("Sent keep-awake ping")
            except Exception as e:
                logger.error(f"Keep-awake error: {e}")
        scheduler.add_job(keep_awake, 'interval', minutes=10)

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("uptime", uptime_command))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("memorysave", memory_save_command))
    application.add_handler(CommandHandler("memoryget", memory_get_command))
    application.add_handler(CommandHandler("memorylist", memory_list_command))
    application.add_handler(CommandHandler("memorydel", memory_del_command))
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("notes", notes_command))
    application.add_handler(CommandHandler("delnote", delnote_command))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("fact", fact_command))
    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    scheduler.start()
    logger.info("Bot started successfully!")

    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
