#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import random
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz
import requests
import io
from urllib.parse import quote as urlquote

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Переменные окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка переменных окружения
if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("❌ BOT_TOKEN или GEMINI_API_KEY не установлены!")
    raise ValueError("Required environment variables missing")

# Настройка Gemini 1.5 Flash (быстрая модель)
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

# Полные названия языков для AI
lang_full = {
    'ru': 'Russian',
    'en': 'English',
    'es': 'Spanish',
    'it': 'Italian',
    'de': 'German',
    'fr': 'French'
}

# Переводы текстов
translations = {
    'ru': {
        'welcome': """🤖 <b>AI DISCO BOT</b>

Привет, {first_name}! Я бот на <b>Gemini 1.5 Flash</b>.

<b>🎯 Возможности:</b>
💬 AI-чат с контекстом
📝 Заметки и задачи
🌍 Погода и время
🎲 Развлечения
📎 Анализ файлов (VIP)
🔍 Анализ изображений (VIP)
🖼️ Генерация изображений (VIP)

<b>⚡ Команды:</b>
/help - Все команды
/vip - Статус VIP

<b>👨‍💻 Создатель:</b> @{CREATOR_USERNAME}""",
        'help_text': "📚 <b>Выберите раздел справки:</b>\n\nНажмите кнопку ниже для просмотра команд по теме.",
        'help_back': "🔙 Назад",
        'help_basic': "🏠 <b>Основные команды:</b>\n\n🚀 /start - Запуск бота и приветствие\n\n📖 /help - Полный список команд\n\nℹ️ /info - Информация о боте\n\n📊 /status - Текущий статус и статистика\n\n👤 /profile - Профиль пользователя\n\n⏱ /uptime - Время работы бота",
        'help_ai': "💬 <b>AI команды:</b>\n\n🤖 /ai [вопрос] - Задать вопрос AI\n\n🧹 /clear - Очистить контекст чата",
        'help_memory': "🧠 <b>Память:</b>\n\n💾 /memorysave [ключ] [значение] - Сохранить в память\n\n🔍 /memoryget [ключ] - Получить из памяти\n\n📋 /memorylist - Список ключей\n\n🗑 /memorydel [ключ] - Удалить ключ",
        'help_notes': "📝 <b>Заметки:</b>\n\n➕ /note [текст] - Создать заметку\n\n📋 /notes - Список заметок\n\n🗑 /delnote [номер] - Удалить заметку",
        'help_todo': "📋 <b>Задачи:</b>\n\n➕ /todo add [текст] - Добавить задачу\n\n📋 /todo list - Список задач\n\n🗑 /todo del [номер] - Удалить задачу",
        'help_utils': "🌍 <b>Утилиты:</b>\n\n🕐 /time [город] - Текущее время\n\n☀️ /weather [город] - Погода\n\n🌐 /translate [язык] [текст] - Перевод\n\n🧮 /calc [выражение] - Калькулятор\n\n🔑 /password [длина] - Генератор пароля",
        'help_games': "🎲 <b>Развлечения:</b>\n\n🎲 /random [min] [max] - Случайное число в диапазоне\n\n🎯 /dice - Бросок кубика (1-6)\n\n🪙 /coin - Подбрасывание монеты (орёл/решка)\n\n😄 /joke - Случайная шутка\n\n💭 /quote - Мотивационная цитата\n\n🔬 /fact - Интересный факт",
        'help_vip': "💎 <b>VIP команды:</b>\n\n👑 /vip - Статус VIP\n\n🖼️ /generate [описание] - Генерация изображения\n\n⏰ /remind [минуты] [текст] - Напоминание\n\n📋 /reminders - Список напоминаний\n\n📎 Отправь файл - Анализ (VIP)\n\n📸 Отправь фото - Анализ (VIP)",
        'help_admin': "👑 <b>Команды Создателя:</b>\n\n🎁 /grant_vip [id/@username] [срок] - Выдать VIP (week/month/year/forever)\n\n❌ /revoke_vip [id/@username] - Забрать VIP\n\n👥 /users - Список пользователей\n\n📢 /broadcast [текст] - Рассылка\n\n📈 /stats - Полная статистика\n\n💾 /backup - Резервная копия",
        'info_text': """🤖 <b>AI DISCO BOT</b>

<b>Версия:</b> 3.0
<b>AI:</b> Gemini 1.5 Flash
<b>Создатель:</b> @Ernest_Kostevich

<b>⚡ Особенности:</b>
• Быстрый AI-чат
• PostgreSQL
• VIP функции
• Анализ файлов/фото (VIP)
• Генерация изображений (VIP)

<b>💬 Поддержка:</b> @Ernest_Kostevich""",
        'status_text': """📊 <b>СТАТУС</b>

<b>👥 Пользователи:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Активность:</b>
• Сообщений: {total_messages}
• Команд: {total_commands}
• AI запросов: {ai_requests}

<b>⏱ Работает:</b> {uptime_days}д {uptime_hours}ч

<b>✅ Статус:</b> Онлайн
<b>🤖 AI:</b> Gemini 1.5 ✓
<b>🗄️ БД:</b> {db_status}""",
        'profile_text': """👤 <b>{first_name}</b>
🆔 <code>{user_id}</code>
{username_line}
📅 {registered}
📊 Сообщений: {messages_count}
🎯 Команд: {commands_count}
📝 Заметок: {notes_count}
{language_line}
{vip_line}""",
        'uptime_text': """⏱ <b>ВРЕМЯ РАБОТЫ</b>

🕐 Запущен: {start_time}
⏰ Работает: {uptime_days}д {uptime_hours}ч {uptime_minutes}м

✅ Онлайн""",
        'vip_active': "💎 <b>VIP СТАТУС</b>\n\n✅ Активен!\n\n{vip_duration}\n\n<b>🎁 Преимущества:</b>\n• ⏰ Напоминания\n• 🖼️ Генерация изображений\n• 🔍 Анализ изображений\n• 📎 Анализ документов",
        'vip_inactive': "💎 <b>VIP СТАТУС</b>\n\n❌ Нет VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'note_added': "✅ Заметка #{note_id} сохранена!\n\n📝 {note_text}",
        'notes_empty': "📭 Нет заметок.",
        'notes_list': "📝 <b>Заметки ({notes_count}):</b>\n\n{notes_text}",
        'note_deleted': "✅ Заметка #{note_id} удалена:\n\n📝 {note_text}",
        'note_not_found': "❌ Заметка #{note_id} не найдена.",
        'memory_saved': "✅ Сохранено:\n🔑 <b>{key}</b> = <code>{value}</code>",
        'memory_got': "🔍 <b>{key}</b> = <code>{value}</code>",
        'memory_empty': "📭 Память пуста.",
        'memory_list': "🧠 <b>Память:</b>\n\n{memory_text}",
        'memory_deleted': "✅ Ключ '{key}' удалён.",
        'memory_not_found': "❌ Ключ '{key}' не найден.",
        'todo_added': "✅ Задача #{todo_id} добавлена!\n\n📋 {todo_text}",
        'todos_empty': "📭 Нет задач.",
        'todos_list': "📋 <b>Задачи ({todos_count}):</b>\n\n{todos_text}",
        'todo_deleted': "✅ Задача #{todo_id} удалена:\n\n📋 {todo_text}",
        'todo_not_found': "❌ Задача #{todo_id} не найдена.",
        'city_not_found': "❌ Город '{city}' не найден.",
        'time_text': """⏰ <b>{city}</b>

🕐 Время: {time}
📅 Дата: {date}
🌍 Пояс: {tz}""",
        'weather_text': """🌍 <b>{city}</b>

🌡 Температура: {temp}°C
🤔 Ощущается: {feels}°C
☁️ {desc}
💧 Влажность: {humidity}%
💨 Ветер: {wind} км/ч""",
        'translate_text': "🌐 <b>Перевод:</b>\n\n{translation}",
        'calc_result': "🧮 <b>Результат:</b>\n\n{expr} = <b>{result}</b>",
        'password_length_error': "❌ Длина от 8 до 50.",
        'password_generated': "🔑 <b>Пароль:</b>\n\n<code>{password}</code>",
        'random_result': "🎲 Число от {min} до {max}:\n\n<b>{result}</b>",
        'dice_result': "🎲 {emoji} Выпало: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Выпало: <b>{result}</b>",
        'joke_text': "😄 <b>Шутка:</b>\n\n{joke}",
        'quote_text': "💭 <b>Цитата:</b>\n\n<i>{quote}</i>",
        'fact_text': "🔬 <b>Факт:</b>\n\n{fact}",
        'reminder_created': "⏰ Напоминание создано!\n\n📝 {text}\n🕐 Через {minutes} минут",
        'reminders_empty': "📭 Нет напоминаний.",
        'reminders_list': "⏰ <b>Напоминания ({count}):</b>\n\n{reminders_text}",
        'reminder_sent': "⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
        'vip_granted': "✅ VIP выдан!\n\n🆔 <code>{user_id}</code>\n⏰ {duration}",
        'vip_revoked': "✅ VIP отозван!\n\n🆔 <code>{user_id}</code>",
        'user_not_found': "❌ Пользователь '{identifier}' не найден.",
        'invalid_duration': "❌ Неверный срок.",
        'users_list': "👥 <b>ПОЛЬЗОВАТЕЛИ ({count}):</b>\n\n{users_text}",
        'broadcast_done': "✅ Завершено!\n\n✅ Успешно: {success}\n❌ Ошибок: {failed}",
        'stats_text': """📊 <b>СТАТИСТИКА</b>

<b>👥 Пользователи:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Активность:</b>
• Сообщений: {total_messages}
• Команд: {total_commands}
• AI запросов: {ai_requests}""",
        'backup_caption': "✅ Резервная копия\n\n📅 {date}",
        'ai_chat_menu': "🤖 <b>AI Чат</b>\n\nПросто пиши - я отвечу!\n/clear - очистить контекст",
        'notes_menu': "📝 <b>Заметки</b>",
        'weather_menu': "🌍 <b>Погода</b>\n\n/weather [город]\nПример: /weather London",
        'time_menu': "⏰ <b>Время</b>\n\n/time [город]\nПример: /time Tokyo",
        'entertainment_menu': "🎲 <b>Развлечения</b>",
        'vip_menu': "💎 <b>VIP Меню</b>",
        'admin_panel': "👑 <b>Админ Панель</b>",
        'generation_menu': "🖼️ <b>Генерация (VIP)</b>\n\n/generate [описание]\n\nПримеры:\n• /generate закат\n• /generate город\n\n💡 Pollinations AI",
        'vip_required': "💎 {feature} для VIP",
        'file_analysis_vip': "💎 Анализ файлов доступен только VIP-пользователям.\n\nСвяжитесь с @Ernest_Kostevich",
        'image_analysis_vip': "💎 Анализ изображений для VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'file_downloading': "📥 Загружаю файл...",
        'file_analysis': "📄 <b>Файл:</b> {file_name}\n\n🤖 <b>Анализ:</b>\n\n{analysis}",
        'image_analyzing': "🔍 Анализирую...",
        'image_analysis': "📸 <b>Анализ (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP",
        'image_generating': "🎨 Генерирую...",
        'image_generated': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI",
        'generation_error': "❌ Ошибка генерации",
        'ai_no_question': "❓ /ai [вопрос]",
        'context_cleared': "🧹 Контекст очищен!",
        'error': "❌ Ошибка: {error}",
        'ai_error': "😔 Ошибка",
        'note_no_text': "❓ /note [текст]",
        'delnote_no_num': "❓ /delnote [номер]",
        'memorysave_usage': "❓ /memorysave [ключ] [значение]",
        'memoryget_usage': "❓ /memoryget [ключ]",
        'memorydel_usage': "❓ /memorydel [ключ]",
        'todo_usage': "❓ /todo add [текст] | list | del [номер]",
        'todo_add_usage': "❓ /todo add [текст]",
        'todo_del_usage': "❓ /todo del [номер]",
        'translate_usage': "❓ /translate [язык] [текст]\n\nПример: /translate en Привет",
        'calc_usage': "❓ /calc [выражение]\n\nПример: /calc 2+2*5",
        'password_usage': "❓ /password [длина]",
        'random_usage': "❓ /random [min] [max]",
        'remind_usage': "❓ /remind [минуты] [текст]",
        'grant_vip_usage': "❓ /grant_vip [id/@username] [срок]\n\nСроки: week, month, year, forever",
        'revoke_vip_usage': "❓ /revoke_vip [id/@username]",
        'broadcast_usage': "❓ /broadcast [текст]",
        'admin_only': "❌ Только для создателя.",
        'language_changed': "✅ Язык изменён на {lang}.",
        'choose_language': "🌐 <b>Выберите язык:</b>",
        'broadcast_start': "📤 Рассылка...",
        'generate_usage': "❓ /generate [описание]\n\nПример: /generate закат над океаном",
        'section_not_found': "❌ Раздел не найден.",
        'note_create': "➕ <b>Создать заметку</b>\n\n/note [текст]\nПример: /note Купить хлеб",
    },
    'en': {
        'welcome': """🤖 <b>AI DISCO BOT</b>

Hello, {first_name}! I'm a bot powered by <b>Gemini 1.5 Flash</b>.

<b>🎯 Features:</b>
💬 AI chat with context
📝 Notes and tasks
🌍 Weather and time
🎲 Entertainment
📎 File analysis (VIP)
🔍 Image analysis (VIP)
🖼️ Image generation (VIP)

<b>⚡ Commands:</b>
/help - All commands
/vip - VIP status

<b>👨‍💻 Creator:</b> @{CREATOR_USERNAME}""",
        'help_text': "📚 <b>Select help section:</b>\n\nClick the button below to view commands by topic.",
        'help_back': "🔙 Back",
        'help_basic': "🏠 <b>Basic commands:</b>\n\n🚀 /start - Start the bot and greeting\n\n📖 /help - Full list of commands\n\nℹ️ /info - Bot information\n\n📊 /status - Current status and statistics\n\n👤 /profile - User profile\n\n⏱ /uptime - Bot uptime",
        'help_ai': "💬 <b>AI commands:</b>\n\n🤖 /ai [question] - Ask AI a question\n\n🧹 /clear - Clear chat context",
        'help_memory': "🧠 <b>Memory:</b>\n\n💾 /memorysave [key] [value] - Save to memory\n\n🔍 /memoryget [key] - Get from memory\n\n📋 /memorylist - List keys\n\n🗑 /memorydel [key] - Delete key",
        'help_notes': "📝 <b>Notes:</b>\n\n➕ /note [text] - Create note\n\n📋 /notes - List notes\n\n🗑 /delnote [number] - Delete note",
        'help_todo': "📋 <b>Tasks:</b>\n\n➕ /todo add [text] - Add task\n\n📋 /todo list - List tasks\n\n🗑 /todo del [number] - Delete task",
        'help_utils': "🌍 <b>Utilities:</b>\n\n🕐 /time [city] - Current time\n\n☀️ /weather [city] - Weather\n\n🌐 /translate [language] [text] - Translation\n\n🧮 /calc [expression] - Calculator\n\n🔑 /password [length] - Password generator",
        'help_games': "🎲 <b>Entertainment:</b>\n\n🎲 /random [min] [max] - Random number in range\n\n🎯 /dice - Dice roll (1-6)\n\n🪙 /coin - Coin flip (heads/tails)\n\n😄 /joke - Random joke\n\n💭 /quote - Motivational quote\n\n🔬 /fact - Interesting fact",
        'help_vip': "💎 <b>VIP commands:</b>\n\n👑 /vip - VIP status\n\n🖼️ /generate [description] - Image generation\n\n⏰ /remind [minutes] [text] - Reminder\n\n📋 /reminders - List reminders\n\n📎 Send file - Analysis (VIP)\n\n📸 Send photo - Analysis (VIP)",
        'help_admin': "👑 <b>Creator commands:</b>\n\n🎁 /grant_vip [id/@username] [term] - Grant VIP (week/month/year/forever)\n\n❌ /revoke_vip [id/@username] - Revoke VIP\n\n👥 /users - List users\n\n📢 /broadcast [text] - Broadcast\n\n📈 /stats - Full statistics\n\n💾 /backup - Backup",
        'info_text': """🤖 <b>AI DISCO BOT</b>

<b>Version:</b> 3.0
<b>AI:</b> Gemini 1.5 Flash
<b>Creator:</b> @Ernest_Kostevich

<b>⚡ Features:</b>
• Fast AI chat
• PostgreSQL
• VIP features
• File/photo analysis (VIP)
• Image generation (VIP)

<b>💬 Support:</b> @Ernest_Kostevich""",
        'status_text': """📊 <b>STATUS</b>

<b>👥 Users:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Activity:</b>
• Messages: {total_messages}
• Commands: {total_commands}
• AI requests: {ai_requests}

<b>⏱ Uptime:</b> {uptime_days}d {uptime_hours}h

<b>✅ Status:</b> Online
<b>🤖 AI:</b> Gemini 1.5 ✓
<b>🗄️ DB:</b> {db_status}""",
        'profile_text': """👤 <b>{first_name}</b>
🆔 <code>{user_id}</code>
{username_line}
📅 {registered}
📊 Messages: {messages_count}
🎯 Commands: {commands_count}
📝 Notes: {notes_count}
{language_line}
{vip_line}""",
        'uptime_text': """⏱ <b>UPTIME</b>

🕐 Started: {start_time}
⏰ Running: {uptime_days}d {uptime_hours}h {uptime_minutes}m

✅ Online""",
        'vip_active': "💎 <b>VIP STATUS</b>\n\n✅ Active!\n\n{vip_duration}\n\n<b>🎁 Benefits:</b>\n• ⏰ Reminders\n• 🖼️ Image generation\n• 🔍 Image analysis\n• 📎 Document analysis",
        'vip_inactive': "💎 <b>VIP STATUS</b>\n\n❌ No VIP.\n\nContact @Ernest_Kostevich",
        'note_added': "✅ Note #{note_id} saved!\n\n📝 {note_text}",
        'notes_empty': "📭 No notes.",
        'notes_list': "📝 <b>Notes ({notes_count}):</b>\n\n{notes_text}",
        'note_deleted': "✅ Note #{note_id} deleted:\n\n📝 {note_text}",
        'note_not_found': "❌ Note #{note_id} not found.",
        'memory_saved': "✅ Saved:\n🔑 <b>{key}</b> = <code>{value}</code>",
        'memory_got': "🔍 <b>{key}</b> = <code>{value}</code>",
        'memory_empty': "📭 Memory is empty.",
        'memory_list': "🧠 <b>Memory:</b>\n\n{memory_text}",
        'memory_deleted': "✅ Key '{key}' deleted.",
        'memory_not_found': "❌ Key '{key}' not found.",
        'todo_added': "✅ Task #{todo_id} added!\n\n📋 {todo_text}",
        'todos_empty': "📭 No tasks.",
        'todos_list': "📋 <b>Tasks ({todos_count}):</b>\n\n{todos_text}",
        'todo_deleted': "✅ Task #{todo_id} deleted:\n\n📋 {todo_text}",
        'todo_not_found': "❌ Task #{todo_id} not found.",
        'city_not_found': "❌ City '{city}' not found.",
        'time_text': """⏰ <b>{city}</b>

🕐 Time: {time}
📅 Date: {date}
🌍 Zone: {tz}""",
        'weather_text': """🌍 <b>{city}</b>

🌡 Temperature: {temp}°C
🤔 Feels like: {feels}°C
☁️ {desc}
💧 Humidity: {humidity}%
💨 Wind: {wind} km/h""",
        'translate_text': "🌐 <b>Translation:</b>\n\n{translation}",
        'calc_result': "🧮 <b>Result:</b>\n\n{expr} = <b>{result}</b>",
        'password_length_error': "❌ Length from 8 to 50.",
        'password_generated': "🔑 <b>Password:</b>\n\n<code>{password}</code>",
        'random_result': "🎲 Number from {min} to {max}:\n\n<b>{result}</b>",
        'dice_result': "🎲 {emoji} Rolled: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Flipped: <b>{result}</b>",
        'joke_text': "😄 <b>Joke:</b>\n\n{joke}",
        'quote_text': "💭 <b>Quote:</b>\n\n<i>{quote}</i>",
        'fact_text': "🔬 <b>Fact:</b>\n\n{fact}",
        'reminder_created': "⏰ Reminder created!\n\n📝 {text}\n🕐 In {minutes} minutes",
        'reminders_empty': "📭 No reminders.",
        'reminders_list': "⏰ <b>Reminders ({count}):</b>\n\n{reminders_text}",
        'reminder_sent': "⏰ <b>REMINDER</b>\n\n📝 {text}",
        'vip_granted': "✅ VIP granted!\n\n🆔 <code>{user_id}</code>\n⏰ {duration}",
        'vip_revoked': "✅ VIP revoked!\n\n🆔 <code>{user_id}</code>",
        'user_not_found': "❌ User '{identifier}' not found.",
        'invalid_duration': "❌ Invalid term.",
        'users_list': "👥 <b>USERS ({count}):</b>\n\n{users_text}",
        'broadcast_done': "✅ Completed!\n\n✅ Successful: {success}\n❌ Errors: {failed}",
        'stats_text': """📊 <b>STATISTICS</b>

<b>👥 Users:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Activity:</b>
• Messages: {total_messages}
• Commands: {total_commands}
• AI requests: {ai_requests}""",
        'backup_caption': "✅ Backup\n\n📅 {date}",
        'ai_chat_menu': "🤖 <b>AI Chat</b>\n\nJust write - I'll answer!\n/clear - clear context",
        'notes_menu': "📝 <b>Notes</b>",
        'weather_menu': "🌍 <b>Weather</b>\n\n/weather [city]\nExample: /weather London",
        'time_menu': "⏰ <b>Time</b>\n\n/time [city]\nExample: /time Tokyo",
        'entertainment_menu': "🎲 <b>Entertainment</b>",
        'vip_menu': "💎 <b>VIP Menu</b>",
        'admin_panel': "👑 <b>Admin Panel</b>",
        'generation_menu': "🖼️ <b>Generation (VIP)</b>\n\n/generate [description]\n\nExamples:\n• /generate sunset\n• /generate city\n\n💡 Pollinations AI",
        'vip_required': "💎 {feature} for VIP",
        'file_analysis_vip': "💎 File analysis available only for VIP users.\n\nContact @Ernest_Kostevich",
        'image_analysis_vip': "💎 Image analysis for VIP.\n\nContact @Ernest_Kostevich",
        'file_downloading': "📥 Downloading file...",
        'file_analysis': "📄 <b>File:</b> {file_name}\n\n🤖 <b>Analysis:</b>\n\n{analysis}",
        'image_analyzing': "🔍 Analyzing...",
        'image_analysis': "📸 <b>Analysis (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP",
        'image_generating': "🎨 Generating...",
        'image_generated': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI",
        'generation_error': "❌ Generation error",
        'ai_no_question': "❓ /ai [question]",
        'context_cleared': "🧹 Context cleared!",
        'error': "❌ Error: {error}",
        'ai_error': "😔 Error",
        'note_no_text': "❓ /note [text]",
        'delnote_no_num': "❓ /delnote [number]",
        'memorysave_usage': "❓ /memorysave [key] [value]",
        'memoryget_usage': "❓ /memoryget [key]",
        'memorydel_usage': "❓ /memorydel [key]",
        'todo_usage': "❓ /todo add [text] | list | del [number]",
        'todo_add_usage': "❓ /todo add [text]",
        'todo_del_usage': "❓ /todo del [number]",
        'translate_usage': "❓ /translate [language] [text]\n\nExample: /translate en Hello",
        'calc_usage': "❓ /calc [expression]\n\nExample: /calc 2+2*5",
        'password_usage': "❓ /password [length]",
        'random_usage': "❓ /random [min] [max]",
        'remind_usage': "❓ /remind [minutes] [text]",
        'grant_vip_usage': "❓ /grant_vip [id/@username] [term]\n\nTerms: week, month, year, forever",
        'revoke_vip_usage': "❓ /revoke_vip [id/@username]",
        'broadcast_usage': "❓ /broadcast [text]",
        'admin_only': "❌ Creator only.",
        'language_changed': "✅ Language changed to {lang}.",
        'choose_language': "🌐 <b>Choose language:</b>",
        'broadcast_start': "📤 Broadcasting...",
        'generate_usage': "❓ /generate [description]\n\nExample: /generate sunset over ocean",
        'section_not_found': "❌ Section not found.",
        'note_create': "➕ <b>Create note</b>\n\n/note [text]\nExample: /note Buy bread",
    },
    'es': {
        'welcome': """🤖 <b>AI DISCO BOT</b>

¡Hola, {first_name}! Soy un bot impulsado por <b>Gemini 1.5 Flash</b>.

<b>🎯 Características:</b>
💬 Chat AI con contexto
📝 Notas y tareas
🌍 Clima y hora
🎲 Entretenimiento
📎 Análisis de archivos (VIP)
🔍 Análisis de imágenes (VIP)
🖼️ Generación de imágenes (VIP)

<b>⚡ Comandos:</b>
/help - Todos los comandos
/vip - Estado VIP

<b>👨‍💻 Creador:</b> @{CREATOR_USERNAME}""",
        'help_text': "📚 <b>Seleccione sección de ayuda:</b>\n\nHaga clic en el botón a continuación para ver comandos por tema.",
        'help_back': "🔙 Atrás",
        'help_basic': "🏠 <b>Comandos básicos:</b>\n\n🚀 /start - Iniciar el bot y saludo\n\n📖 /help - Lista completa de comandos\n\nℹ️ /info - Información del bot\n\n📊 /status - Estado actual y estadísticas\n\n👤 /profile - Perfil de usuario\n\n⏱ /uptime - Tiempo de actividad del bot",
        'help_ai': "💬 <b>Comandos AI:</b>\n\n🤖 /ai [pregunta] - Preguntar a AI\n\n🧹 /clear - Limpiar contexto del chat",
        'help_memory': "🧠 <b>Memoria:</b>\n\n💾 /memorysave [clave] [valor] - Guardar en memoria\n\n🔍 /memoryget [clave] - Obtener de memoria\n\n📋 /memorylist - Lista de claves\n\n🗑 /memorydel [clave] - Eliminar clave",
        'help_notes': "📝 <b>Notas:</b>\n\n➕ /note [texto] - Crear nota\n\n📋 /notes - Lista de notas\n\n🗑 /delnote [número] - Eliminar nota",
        'help_todo': "📋 <b>Tareas:</b>\n\n➕ /todo add [texto] - Añadir tarea\n\n📋 /todo list - Lista de tareas\n\n🗑 /todo del [número] - Eliminar tarea",
        'help_utils': "🌍 <b>Utilidades:</b>\n\n🕐 /time [ciudad] - Hora actual\n\n☀️ /weather [ciudad] - Clima\n\n🌐 /translate [idioma] [texto] - Traducción\n\n🧮 /calc [expresión] - Calculadora\n\n🔑 /password [longitud] - Generador de contraseña",
        'help_games': "🎲 <b>Entretenimiento:</b>\n\n🎲 /random [min] [max] - Número aleatorio en rango\n\n🎯 /dice - Lanzar dado (1-6)\n\n🪙 /coin - Lanzar moneda (cara/cruz)\n\n😄 /joke - Chiste aleatorio\n\n💭 /quote - Cita motivacional\n\n🔬 /fact - Hecho interesante",
        'help_vip': "💎 <b>Comandos VIP:</b>\n\n👑 /vip - Estado VIP\n\n🖼️ /generate [descripción] - Generación de imagen\n\n⏰ /remind [minutos] [texto] - Recordatorio\n\n📋 /reminders - Lista de recordatorios\n\n📎 Enviar archivo - Análisis (VIP)\n\n📸 Enviar foto - Análisis (VIP)",
        'help_admin': "👑 <b>Comandos del Creador:</b>\n\n🎁 /grant_vip [id/@username] [término] - Otorgar VIP (week/month/year/forever)\n\n❌ /revoke_vip [id/@username] - Revocar VIP\n\n👥 /users - Lista de usuarios\n\n📢 /broadcast [texto] - Difusión\n\n📈 /stats - Estadísticas completas\n\n💾 /backup - Copia de seguridad",
        'info_text': """🤖 <b>AI DISCO BOT</b>

<b>Versión:</b> 3.0
<b>AI:</b> Gemini 1.5 Flash
<b>Creador:</b> @Ernest_Kostevich

<b>⚡ Características:</b>
• Chat AI rápido
• PostgreSQL
• Funciones VIP
• Análisis de archivos/fotos (VIP)
• Generación de imágenes (VIP)

<b>💬 Soporte:</b> @Ernest_Kostevich""",
        'status_text': """📊 <b>ESTADO</b>

<b>👥 Usuarios:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Actividad:</b>
• Mensajes: {total_messages}
• Comandos: {total_commands}
• Solicitudes AI: {ai_requests}

<b>⏱ Tiempo de actividad:</b> {uptime_days}d {uptime_hours}h

<b>✅ Estado:</b> En línea
<b>🤖 AI:</b> Gemini 1.5 ✓
<b>🗄️ BD:</b> {db_status}""",
        'profile_text': """👤 <b>{first_name}</b>
🆔 <code>{user_id}</code>
{username_line}
📅 {registered}
📊 Mensajes: {messages_count}
🎯 Comandos: {commands_count}
📝 Notas: {notes_count}
{language_line}
{vip_line}""",
        'uptime_text': """⏱ <b>TIEMPO DE ACTIVIDAD</b>

🕐 Iniciado: {start_time}
⏰ Ejecutando: {uptime_days}d {uptime_hours}h {uptime_minutes}m

✅ En línea""",
        'vip_active': "💎 <b>ESTADO VIP</b>\n\n✅ ¡Activo!\n\n{vip_duration}\n\n<b>🎁 Beneficios:</b>\n• ⏰ Recordatorios\n• 🖼️ Generación de imágenes\n• 🔍 Análisis de imágenes\n• 📎 Análisis de documentos",
        'vip_inactive': "💎 <b>ESTADO VIP</b>\n\n❌ Sin VIP.\n\nContacta @Ernest_Kostevich",
        'note_added': "✅ Nota #{note_id} guardada!\n\n📝 {note_text}",
        'notes_empty': "📭 Sin notas.",
        'notes_list': "📝 <b>Notas ({notes_count}):</b>\n\n{notes_text}",
        'note_deleted': "✅ Nota #{note_id} eliminada:\n\n📝 {note_text}",
        'note_not_found': "❌ Nota #{note_id} no encontrada.",
        'memory_saved': "✅ Guardado:\n🔑 <b>{key}</b> = <code>{value}</code>",
        'memory_got': "🔍 <b>{key}</b> = <code>{value}</code>",
        'memory_empty': "📭 Memoria vacía.",
        'memory_list': "🧠 <b>Memoria:</b>\n\n{memory_text}",
        'memory_deleted': "✅ Clave '{key}' eliminada.",
        'memory_not_found': "❌ Clave '{key}' no encontrada.",
        'todo_added': "✅ Tarea #{todo_id} añadida!\n\n📋 {todo_text}",
        'todos_empty': "📭 Sin tareas.",
        'todos_list': "📋 <b>Tareas ({todos_count}):</b>\n\n{todos_text}",
        'todo_deleted': "✅ Tarea #{todo_id} eliminada:\n\n📋 {todo_text}",
        'todo_not_found': "❌ Tarea #{todo_id} no encontrada.",
        'city_not_found': "❌ Ciudad '{city}' no encontrada.",
        'time_text': """⏰ <b>{city}</b>

🕐 Hora: {time}
📅 Fecha: {date}
🌍 Zona: {tz}""",
        'weather_text': """🌍 <b>{city}</b>

🌡 Temperatura: {temp}°C
🤔 Se siente como: {feels}°C
☁️ {desc}
💧 Humedad: {humidity}%
💨 Viento: {wind} km/h""",
        'translate_text': "🌐 <b>Traducción:</b>\n\n{translation}",
        'calc_result': "🧮 <b>Resultado:</b>\n\n{expr} = <b>{result}</b>",
        'password_length_error': "❌ Longitud de 8 a 50.",
        'password_generated': "🔑 <b>Contraseña:</b>\n\n<code>{password}</code>",
        'random_result': "🎲 Número de {min} a {max}:\n\n<b>{result}</b>",
        'dice_result': "🎲 {emoji} Salió: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Salió: <b>{result}</b>",
        'joke_text': "😄 <b>Chiste:</b>\n\n{joke}",
        'quote_text': "💭 <b>Cita:</b>\n\n<i>{quote}</i>",
        'fact_text': "🔬 <b>Hecho:</b>\n\n{fact}",
        'reminder_created': "⏰ Recordatorio creado!\n\n📝 {text}\n🕐 En {minutes} minutos",
        'reminders_empty': "📭 Sin recordatorios.",
        'reminders_list': "⏰ <b>Recordatorios ({count}):</b>\n\n{reminders_text}",
        'reminder_sent': "⏰ <b>RECORDATORIO</b>\n\n📝 {text}",
        'vip_granted': "✅ VIP otorgado!\n\n🆔 <code>{user_id}</code>\n⏰ {duration}",
        'vip_revoked': "✅ VIP revocado!\n\n🆔 <code>{user_id}</code>",
        'user_not_found': "❌ Usuario '{identifier}' no encontrado.",
        'invalid_duration': "❌ Término inválido.",
        'users_list': "👥 <b>USUARIOS ({count}):</b>\n\n{users_text}",
        'broadcast_done': "✅ Completado!\n\n✅ Exitoso: {success}\n❌ Errores: {failed}",
        'stats_text': """📊 <b>ESTADÍSTICAS</b>

<b>👥 Usuarios:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Actividad:</b>
• Mensajes: {total_messages}
• Comandos: {total_commands}
• Solicitudes AI: {ai_requests}""",
        'backup_caption': "✅ Copia de seguridad\n\n📅 {date}",
        'ai_chat_menu': "🤖 <b>Chat AI</b>\n\n¡Solo escribe - responderé!\n/clear - limpiar contexto",
        'notes_menu': "📝 <b>Notas</b>",
        'weather_menu': "🌍 <b>Clima</b>\n\n/weather [ciudad]\nEjemplo: /weather London",
        'time_menu': "⏰ <b>Hora</b>\n\n/time [ciudad]\nEjemplo: /time Tokyo",
        'entertainment_menu': "🎲 <b>Entretenimiento</b>",
        'vip_menu': "💎 <b>Menú VIP</b>",
        'admin_panel': "👑 <b>Panel Admin</b>",
        'generation_menu': "🖼️ <b>Generación (VIP)</b>\n\n/generate [descripción]\n\nEjemplos:\n• /generate atardecer\n• /generate ciudad\n\n💡 Pollinations AI",
        'vip_required': "💎 {feature} para VIP",
        'file_analysis_vip': "💎 Análisis de archivos disponible solo para usuarios VIP.\n\nContacta @Ernest_Kostevich",
        'image_analysis_vip': "💎 Análisis de imágenes para VIP.\n\nContacta @Ernest_Kostevich",
        'file_downloading': "📥 Descargando archivo...",
        'file_analysis': "📄 <b>Archivo:</b> {file_name}\n\n🤖 <b>Análisis:</b>\n\n{analysis}",
        'image_analyzing': "🔍 Analizando...",
        'image_analysis': "📸 <b>Análisis (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP",
        'image_generating': "🎨 Generando...",
        'image_generated': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI",
        'generation_error': "❌ Error de generación",
        'ai_no_question': "❓ /ai [pregunta]",
        'context_cleared': "🧹 Contexto limpiado!",
        'error': "❌ Error: {error}",
        'ai_error': "😔 Error",
        'note_no_text': "❓ /note [texto]",
        'delnote_no_num': "❓ /delnote [número]",
        'memorysave_usage': "❓ /memorysave [clave] [valor]",
        'memoryget_usage': "❓ /memoryget [clave]",
        'memorydel_usage': "❓ /memorydel [clave]",
        'todo_usage': "❓ /todo add [texto] | list | del [número]",
        'todo_add_usage': "❓ /todo add [texto]",
        'todo_del_usage': "❓ /todo del [número]",
        'translate_usage': "❓ /translate [idioma] [texto]\n\nEjemplo: /translate en Hola",
        'calc_usage': "❓ /calc [expresión]\n\nEjemplo: /calc 2+2*5",
        'password_usage': "❓ /password [longitud]",
        'random_usage': "❓ /random [min] [max]",
        'remind_usage': "❓ /remind [minutos] [texto]",
        'grant_vip_usage': "❓ /grant_vip [id/@username] [término]\n\nTérminos: week, month, year, forever",
        'revoke_vip_usage': "❓ /revoke_vip [id/@username]",
        'broadcast_usage': "❓ /broadcast [texto]",
        'admin_only': "❌ Solo para el creador.",
        'language_changed': "✅ Idioma cambiado a {lang}.",
        'choose_language': "🌐 <b>Elige idioma:</b>",
        'broadcast_start': "📤 Difusión...",
        'generate_usage': "❓ /generate [descripción]\n\nEjemplo: /generate atardecer sobre el océano",
        'section_not_found': "❌ Sección no encontrada.",
        'note_create': "➕ <b>Crear nota</b>\n\n/note [texto]\nEjemplo: /note Comprar pan",
    },
    'it': {
        'welcome': """🤖 <b>AI DISCO BOT</b>

Ciao, {first_name}! Sono un bot alimentato da <b>Gemini 1.5 Flash</b>.

<b>🎯 Funzionalità:</b>
💬 Chat AI con contesto
📝 Note e compiti
🌍 Meteo e ora
🎲 Intrattenimento
📎 Analisi file (VIP)
🔍 Analisi immagini (VIP)
🖼️ Generazione immagini (VIP)

<b>⚡ Comandi:</b>
/help - Tutti i comandi
/vip - Stato VIP

<b>👨‍💻 Creatore:</b> @{CREATOR_USERNAME}""",
        'help_text': "📚 <b>Seleziona sezione aiuto:</b>\n\nClicca sul pulsante sotto per visualizzare i comandi per argomento.",
        'help_back': "🔙 Indietro",
        'help_basic': "🏠 <b>Comandi di base:</b>\n\n🚀 /start - Avvia il bot e saluto\n\n📖 /help - Elenco completo comandi\n\nℹ️ /info - Informazioni bot\n\n📊 /status - Stato corrente e statistiche\n\n👤 /profile - Profilo utente\n\n⏱ /uptime - Tempo di attività bot",
        'help_ai': "💬 <b>Comandi AI:</b>\n\n🤖 /ai [domanda] - Chiedi a AI\n\n🧹 /clear - Pulisci contesto chat",
        'help_memory': "🧠 <b>Memoria:</b>\n\n💾 /memorysave [chiave] [valore] - Salva in memoria\n\n🔍 /memoryget [chiave] - Ottieni dalla memoria\n\n📋 /memorylist - Elenco chiavi\n\n🗑 /memorydel [chiave] - Elimina chiave",
        'help_notes': "📝 <b>Note:</b>\n\n➕ /note [testo] - Crea nota\n\n📋 /notes - Elenco note\n\n🗑 /delnote [numero] - Elimina nota",
        'help_todo': "📋 <b>Compiti:</b>\n\n➕ /todo add [testo] - Aggiungi compito\n\n📋 /todo list - Elenco compiti\n\n🗑 /todo del [numero] - Elimina compito",
        'help_utils': "🌍 <b>Utilità:</b>\n\n🕐 /time [città] - Ora attuale\n\n☀️ /weather [città] - Meteo\n\n🌐 /translate [lingua] [testo] - Traduzione\n\n🧮 /calc [espressione] - Calcolatrice\n\n🔑 /password [lunghezza] - Generatore password",
        'help_games': "🎲 <b>Intrattenimento:</b>\n\n🎲 /random [min] [max] - Numero casuale in range\n\n🎯 /dice - Lancio dado (1-6)\n\n🪙 /coin - Lancio moneta (testa/croce)\n\n😄 /joke - Barzelletta casuale\n\n💭 /quote - Citazione motivazionale\n\n🔬 /fact - Fatto interessante",
        'help_vip': "💎 <b>Comandi VIP:</b>\n\n👑 /vip - Stato VIP\n\n🖼️ /generate [descrizione] - Generazione immagine\n\n⏰ /remind [minuti] [testo] - Promemoria\n\n📋 /reminders - Elenco promemoria\n\n📎 Invia file - Analisi (VIP)\n\n📸 Invia foto - Analisi (VIP)",
        'help_admin': "👑 <b>Comandi Creatore:</b>\n\n🎁 /grant_vip [id/@username] [termine] - Concedi VIP (week/month/year/forever)\n\n❌ /revoke_vip [id/@username] - Revoca VIP\n\n👥 /users - Elenco utenti\n\n📢 /broadcast [testo] - Trasmissione\n\n📈 /stats - Statistiche complete\n\n💾 /backup - Backup",
        'info_text': """🤖 <b>AI DISCO BOT</b>

<b>Versione:</b> 3.0
<b>AI:</b> Gemini 1.5 Flash
<b>Creatore:</b> @Ernest_Kostevich

<b>⚡ Funzionalità:</b>
• Chat AI veloce
• PostgreSQL
• Funzioni VIP
• Analisi file/foto (VIP)
• Generazione immagini (VIP)

<b>💬 Supporto:</b> @Ernest_Kostevich""",
        'status_text': """📊 <b>STATO</b>

<b>👥 Utenti:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Attività:</b>
• Messaggi: {total_messages}
• Comandi: {total_commands}
• Richieste AI: {ai_requests}

<b>⏱ Tempo di attività:</b> {uptime_days}g {uptime_hours}o

<b>✅ Stato:</b> Online
<b>🤖 AI:</b> Gemini 1.5 ✓
<b>🗄️ DB:</b> {db_status}""",
        'profile_text': """👤 <b>{first_name}</b>
🆔 <code>{user_id}</code>
{username_line}
📅 {registered}
📊 Messaggi: {messages_count}
🎯 Comandi: {commands_count}
📝 Note: {notes_count}
{language_line}
{vip_line}""",
        'uptime_text': """⏱ <b>TEMPO DI ATTIVITÀ</b>

🕐 Avviato: {start_time}
⏰ Esecuzione: {uptime_days}g {uptime_hours}o {uptime_minutes}m

✅ Online""",
        'vip_active': "💎 <b>STATO VIP</b>\n\n✅ Attivo!\n\n{vip_duration}\n\n<b>🎁 Benefici:</b>\n• ⏰ Promemoria\n• 🖼️ Generazione immagini\n• 🔍 Analisi immagini\n• 📎 Analisi documenti",
        'vip_inactive': "💎 <b>STATO VIP</b>\n\n❌ Nessun VIP.\n\nContatta @Ernest_Kostevich",
        'note_added': "✅ Nota #{note_id} salvata!\n\n📝 {note_text}",
        'notes_empty': "📭 Nessuna nota.",
        'notes_list': "📝 <b>Note ({notes_count}):</b>\n\n{notes_text}",
        'note_deleted': "✅ Nota #{note_id} eliminata:\n\n📝 {note_text}",
        'note_not_found': "❌ Nota #{note_id} non trovata.",
        'memory_saved': "✅ Salvato:\n🔑 <b>{key}</b> = <code>{value}</code>",
        'memory_got': "🔍 <b>{key}</b> = <code>{value}</code>",
        'memory_empty': "📭 Memoria vuota.",
        'memory_list': "🧠 <b>Memoria:</b>\n\n{memory_text}",
        'memory_deleted': "✅ Chiave '{key}' eliminata.",
        'memory_not_found': "❌ Chiave '{key}' non trovata.",
        'todo_added': "✅ Compito #{todo_id} aggiunto!\n\n📋 {todo_text}",
        'todos_empty': "📭 Nessun compito.",
        'todos_list': "📋 <b>Compiti ({todos_count}):</b>\n\n{todos_text}",
        'todo_deleted': "✅ Compito #{todo_id} eliminato:\n\n📋 {todo_text}",
        'todo_not_found': "❌ Compito #{todo_id} non trovato.",
        'city_not_found': "❌ Città '{city}' non trovata.",
        'time_text': """⏰ <b>{city}</b>

🕐 Ora: {time}
📅 Data: {date}
🌍 Zona: {tz}""",
        'weather_text': """🌍 <b>{city}</b>

🌡 Temperatura: {temp}°C
🤔 Si sente come: {feels}°C
☁️ {desc}
💧 Umidità: {humidity}%
💨 Vento: {wind} km/h""",
        'translate_text': "🌐 <b>Traduzione:</b>\n\n{translation}",
        'calc_result': "🧮 <b>Risultato:</b>\n\n{expr} = <b>{result}</b>",
        'password_length_error': "❌ Lunghezza da 8 a 50.",
        'password_generated': "🔑 <b>Password:</b>\n\n<code>{password}</code>",
        'random_result': "🎲 Numero da {min} a {max}:\n\n<b>{result}</b>",
        'dice_result': "🎲 {emoji} Uscito: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Uscito: <b>{result}</b>",
        'joke_text': "😄 <b>Barzelletta:</b>\n\n{joke}",
        'quote_text': "💭 <b>Citazione:</b>\n\n<i>{quote}</i>",
        'fact_text': "🔬 <b>Fatto:</b>\n\n{fact}",
        'reminder_created': "⏰ Promemoria creato!\n\n📝 {text}\n🕐 In {minutes} minuti",
        'reminders_empty': "📭 Nessun promemoria.",
        'reminders_list': "⏰ <b>Promemoria ({count}):</b>\n\n{reminders_text}",
        'reminder_sent': "⏰ <b>PROMEMORIA</b>\n\n📝 {text}",
        'vip_granted': "✅ VIP concesso!\n\n🆔 <code>{user_id}</code>\n⏰ {duration}",
        'vip_revoked': "✅ VIP revocato!\n\n🆔 <code>{user_id}</code>",
        'user_not_found': "❌ Utente '{identifier}' non trovato.",
        'invalid_duration': "❌ Termine non valido.",
        'users_list': "👥 <b>UTENTI ({count}):</b>\n\n{users_text}",
        'broadcast_done': "✅ Completato!\n\n✅ Riuscito: {success}\n❌ Errori: {failed}",
        'stats_text': """📊 <b>STATISTICHE</b>

<b>👥 Utenti:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Attività:</b>
• Messaggi: {total_messages}
• Comandi: {total_commands}
• Richieste AI: {ai_requests}""",
        'backup_caption': "✅ Backup\n\n📅 {date}",
        'ai_chat_menu': "🤖 <b>Chat AI</b>\n\nScrivi solo - risponderò!\n/clear - pulisci contesto",
        'notes_menu': "📝 <b>Note</b>",
        'weather_menu': "🌍 <b>Meteo</b>\n\n/weather [città]\nEsempio: /weather London",
        'time_menu': "⏰ <b>Ora</b>\n\n/time [città]\nEsempio: /time Tokyo",
        'entertainment_menu': "🎲 <b>Intrattenimento</b>",
        'vip_menu': "💎 <b>Menù VIP</b>",
        'admin_panel': "👑 <b>Pannello Admin</b>",
        'generation_menu': "🖼️ <b>Generazione (VIP)</b>\n\n/generate [descrizione]\n\nEsempi:\n• /generate tramonto\n• /generate città\n\n💡 Pollinations AI",
        'vip_required': "💎 {feature} per VIP",
        'file_analysis_vip': "💎 Analisi file disponibile solo per utenti VIP.\n\nContatta @Ernest_Kostevich",
        'image_analysis_vip': "💎 Analisi immagini per VIP.\n\nContatta @Ernest_Kostevich",
        'file_downloading': "📥 Scaricando file...",
        'file_analysis': "📄 <b>File:</b> {file_name}\n\n🤖 <b>Analisi:</b>\n\n{analysis}",
        'image_analyzing': "🔍 Analizzando...",
        'image_analysis': "📸 <b>Analisi (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP",
        'image_generating': "🎨 Generando...",
        'image_generated': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI",
        'generation_error': "❌ Errore generazione",
        'ai_no_question': "❓ /ai [domanda]",
        'context_cleared': "🧹 Contesto pulito!",
        'error': "❌ Errore: {error}",
        'ai_error': "😔 Errore",
        'note_no_text': "❓ /note [testo]",
        'delnote_no_num': "❓ /delnote [numero]",
        'memorysave_usage': "❓ /memorysave [chiave] [valore]",
        'memoryget_usage': "❓ /memoryget [chiave]",
        'memorydel_usage': "❓ /memorydel [chiave]",
        'todo_usage': "❓ /todo add [testo] | list | del [numero]",
        'todo_add_usage': "❓ /todo add [testo]",
        'todo_del_usage': "❓ /todo del [numero]",
        'translate_usage': "❓ /translate [lingua] [testo]\n\nEsempio: /translate en Ciao",
        'calc_usage': "❓ /calc [espressione]\n\nEsempio: /calc 2+2*5",
        'password_usage': "❓ /password [lunghezza]",
        'random_usage': "❓ /random [min] [max]",
        'remind_usage': "❓ /remind [minuti] [testo]",
        'grant_vip_usage': "❓ /grant_vip [id/@username] [termine]\n\nTermini: week, month, year, forever",
        'revoke_vip_usage': "❓ /revoke_vip [id/@username]",
        'broadcast_usage': "❓ /broadcast [testo]",
        'admin_only': "❌ Solo per il creatore.",
        'language_changed': "✅ Lingua cambiata in {lang}.",
        'choose_language': "🌐 <b>Scegli lingua:</b>",
        'broadcast_start': "📤 Trasmissione...",
        'generate_usage': "❓ /generate [descrizione]\n\nEsempio: /generate tramonto sull'oceano",
        'section_not_found': "❌ Sezione non trovata.",
        'note_create': "➕ <b>Crea nota</b>\n\n/note [testo]\nEsempio: /note Compra pane",
    },
    'de': {
        'welcome': """🤖 <b>AI DISCO BOT</b>

Hallo, {first_name}! Ich bin ein Bot, der von <b>Gemini 1.5 Flash</b> angetrieben wird.

<b>🎯 Funktionen:</b>
💬 AI-Chat mit Kontext
📝 Notizen und Aufgaben
🌍 Wetter und Zeit
🎲 Unterhaltung
📎 Dateianalyse (VIP)
🔍 Bildanalyse (VIP)
🖼️ Bildgenerierung (VIP)

<b>⚡ Befehle:</b>
/help - Alle Befehle
/vip - VIP-Status

<b>👨‍💻 Ersteller:</b> @{CREATOR_USERNAME}""",
        'help_text': "📚 <b>Wählen Sie Hilfsabschnitt:</b>\n\nKlicken Sie auf die Schaltfläche unten, um Befehle nach Thema anzuzeigen.",
        'help_back': "🔙 Zurück",
        'help_basic': "🏠 <b>Grundbefehle:</b>\n\n🚀 /start - Bot starten und Begrüßung\n\n📖 /help - Vollständige Liste der Befehle\n\nℹ️ /info - Bot-Informationen\n\n📊 /status - Aktueller Status und Statistiken\n\n👤 /profile - Benutzerprofil\n\n⏱ /uptime - Bot-Laufzeit",
        'help_ai': "💬 <b>AI-Befehle:</b>\n\n🤖 /ai [Frage] - AI eine Frage stellen\n\n🧹 /clear - Chat-Kontext löschen",
        'help_memory': "🧠 <b>Speicher:</b>\n\n💾 /memorysave [Schlüssel] [Wert] - In Speicher speichern\n\n🔍 /memoryget [Schlüssel] - Aus Speicher abrufen\n\n📋 /memorylist - Liste der Schlüssel\n\n🗑 /memorydel [Schlüssel] - Schlüssel löschen",
        'help_notes': "📝 <b>Notizen:</b>\n\n➕ /note [Text] - Notiz erstellen\n\n📋 /notes - Notizen auflisten\n\n🗑 /delnote [Nummer] - Notiz löschen",
        'help_todo': "📋 <b>Aufgaben:</b>\n\n➕ /todo add [Text] - Aufgabe hinzufügen\n\n📋 /todo list - Aufgaben auflisten\n\n🗑 /todo del [Nummer] - Aufgabe löschen",
        'help_utils': "🌍 <b>Utilities:</b>\n\n🕐 /time [Stadt] - Aktuelle Zeit\n\n☀️ /weather [Stadt] - Wetter\n\n🌐 /translate [Sprache] [Text] - Übersetzung\n\n🧮 /calc [Ausdruck] - Rechner\n\n🔑 /password [Länge] - Passwortgenerator",
        'help_games': "🎲 <b>Unterhaltung:</b>\n\n🎲 /random [min] [max] - Zufallszahl im Bereich\n\n🎯 /dice - Würfelwurf (1-6)\n\n🪙 /coin - Münzwurf (Kopf/Zahl)\n\n😄 /joke - Zufälliger Witz\n\n💭 /quote - Motivationszitat\n\n🔬 /fact - Interessanter Fakt",
        'help_vip': "💎 <b>VIP-Befehle:</b>\n\n👑 /vip - VIP-Status\n\n🖼️ /generate [Beschreibung] - Bildgenerierung\n\n⏰ /remind [Minuten] [Text] - Erinnerung\n\n📋 /reminders - Erinnerungen auflisten\n\n📎 Datei senden - Analyse (VIP)\n\n📸 Foto senden - Analyse (VIP)",
        'help_admin': "👑 <b>Ersteller-Befehle:</b>\n\n🎁 /grant_vip [id/@username] [Laufzeit] - VIP gewähren (week/month/year/forever)\n\n❌ /revoke_vip [id/@username] - VIP widerrufen\n\n👥 /users - Benutzer auflisten\n\n📢 /broadcast [Text] - Broadcast\n\n📈 /stats - Vollständige Statistiken\n\n💾 /backup - Backup",
        'info_text': """🤖 <b>AI DISCO BOT</b>

<b>Version:</b> 3.0
<b>AI:</b> Gemini 1.5 Flash
<b>Ersteller:</b> @Ernest_Kostevich

<b>⚡ Funktionen:</b>
• Schneller AI-Chat
• PostgreSQL
• VIP-Funktionen
• Datei/Foto-Analyse (VIP)
• Bildgenerierung (VIP)

<b>💬 Support:</b> @Ernest_Kostevich""",
        'status_text': """📊 <b>STATUS</b>

<b>👥 Benutzer:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Aktivität:</b>
• Nachrichten: {total_messages}
• Befehle: {total_commands}
• AI-Anfragen: {ai_requests}

<b>⏱ Laufzeit:</b> {uptime_days}t {uptime_hours}s

<b>✅ Status:</b> Online
<b>🤖 AI:</b> Gemini 1.5 ✓
<b>🗄️ DB:</b> {db_status}""",
        'profile_text': """👤 <b>{first_name}</b>
🆔 <code>{user_id}</code>
{username_line}
📅 {registered}
📊 Nachrichten: {messages_count}
🎯 Befehle: {commands_count}
📝 Notizen: {notes_count}
{language_line}
{vip_line}""",
        'uptime_text': """⏱ <b>LAUFZEIT</b>

🕐 Gestartet: {start_time}
⏰ Läuft: {uptime_days}t {uptime_hours}s {uptime_minutes}m

✅ Online""",
        'vip_active': "💎 <b>VIP-STATUS</b>\n\n✅ Aktiv!\n\n{vip_duration}\n\n<b>🎁 Vorteile:</b>\n• ⏰ Erinnerungen\n• 🖼️ Bildgenerierung\n• 🔍 Bildanalyse\n• 📎 Dokumentanalyse",
        'vip_inactive': "💎 <b>VIP-STATUS</b>\n\n❌ Kein VIP.\n\nKontakt @Ernest_Kostevich",
        'note_added': "✅ Notiz #{note_id} gespeichert!\n\n📝 {note_text}",
        'notes_empty': "📭 Keine Notizen.",
        'notes_list': "📝 <b>Notizen ({notes_count}):</b>\n\n{notes_text}",
        'note_deleted': "✅ Notiz #{note_id} gelöscht:\n\n📝 {note_text}",
        'note_not_found': "❌ Notiz #{note_id} nicht gefunden.",
        'memory_saved': "✅ Gespeichert:\n🔑 <b>{key}</b> = <code>{value}</code>",
        'memory_got': "🔍 <b>{key}</b> = <code>{value}</code>",
        'memory_empty': "📭 Speicher leer.",
        'memory_list': "🧠 <b>Speicher:</b>\n\n{memory_text}",
        'memory_deleted': "✅ Schlüssel '{key}' gelöscht.",
        'memory_not_found': "❌ Schlüssel '{key}' nicht gefunden.",
        'todo_added': "✅ Aufgabe #{todo_id} hinzugefügt!\n\n📋 {todo_text}",
        'todos_empty': "📭 Keine Aufgaben.",
        'todos_list': "📋 <b>Aufgaben ({todos_count}):</b>\n\n{todos_text}",
        'todo_deleted': "✅ Aufgabe #{todo_id} gelöscht:\n\n📋 {todo_text}",
        'todo_not_found': "❌ Aufgabe #{todo_id} nicht gefunden.",
        'city_not_found': "❌ Stadt '{city}' nicht gefunden.",
        'time_text': """⏰ <b>{city}</b>

🕐 Zeit: {time}
📅 Datum: {date}
🌍 Zone: {tz}""",
        'weather_text': """🌍 <b>{city}</b>

🌡 Temperatur: {temp}°C
🤔 Fühlt sich an wie: {feels}°C
☁️ {desc}
💧 Feuchtigkeit: {humidity}%
💨 Wind: {wind} km/h""",
        'translate_text': "🌐 <b>Übersetzung:</b>\n\n{translation}",
        'calc_result': "🧮 <b>Ergebnis:</b>\n\n{expr} = <b>{result}</b>",
        'password_length_error': "❌ Länge von 8 bis 50.",
        'password_generated': "🔑 <b>Passwort:</b>\n\n<code>{password}</code>",
        'random_result': "🎲 Zahl von {min} bis {max}:\n\n<b>{result}</b>",
        'dice_result': "🎲 {emoji} Gewürfelt: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Geworfen: <b>{result}</b>",
        'joke_text': "😄 <b>Witz:</b>\n\n{joke}",
        'quote_text': "💭 <b>Zitat:</b>\n\n<i>{quote}</i>",
        'fact_text': "🔬 <b>Fakt:</b>\n\n{fact}",
        'reminder_created': "⏰ Erinnerung erstellt!\n\n📝 {text}\n🕐 In {minutes} Minuten",
        'reminders_empty': "📭 Keine Erinnerungen.",
        'reminders_list': "⏰ <b>Erinnerungen ({count}):</b>\n\n{reminders_text}",
        'reminder_sent': "⏰ <b>ERINNERUNG</b>\n\n📝 {text}",
        'vip_granted': "✅ VIP gewährt!\n\n🆔 <code>{user_id}</code>\n⏰ {duration}",
        'vip_revoked': "✅ VIP widerrufen!\n\n🆔 <code>{user_id}</code>",
        'user_not_found': "❌ Benutzer '{identifier}' nicht gefunden.",
        'invalid_duration': "❌ Ungültige Laufzeit.",
        'users_list': "👥 <b>BENUTZER ({count}):</b>\n\n{users_text}",
        'broadcast_done': "✅ Abgeschlossen!\n\n✅ Erfolgreich: {success}\n❌ Fehler: {failed}",
        'stats_text': """📊 <b>STATISTIKEN</b>

<b>👥 Benutzer:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Aktivität:</b>
• Nachrichten: {total_messages}
• Befehle: {total_commands}
• AI-Anfragen: {ai_requests}""",
        'backup_caption': "✅ Backup\n\n📅 {date}",
        'ai_chat_menu': "🤖 <b>AI-Chat</b>\n\nSchreibe einfach - ich antworte!\n/clear - Kontext löschen",
        'notes_menu': "📝 <b>Notizen</b>",
        'weather_menu': "🌍 <b>Wetter</b>\n\n/weather [Stadt]\nBeispiel: /weather London",
        'time_menu': "⏰ <b>Zeit</b>\n\n/time [Stadt]\nBeispiel: /time Tokyo",
        'entertainment_menu': "🎲 <b>Unterhaltung</b>",
        'vip_menu': "💎 <b>VIP-Menü</b>",
        'admin_panel': "👑 <b>Admin-Panel</b>",
        'generation_menu': "🖼️ <b>Generierung (VIP)</b>\n\n/generate [Beschreibung]\n\nBeispiele:\n• /generate Sonnenuntergang\n• /generate Stadt\n\n💡 Pollinations AI",
        'vip_required': "💎 {feature} für VIP",
        'file_analysis_vip': "💎 Dateianalyse nur für VIP-Benutzer verfügbar.\n\nKontakt @Ernest_Kostevich",
        'image_analysis_vip': "💎 Bildanalyse für VIP.\n\nKontakt @Ernest_Kostevich",
        'file_downloading': "📥 Datei herunterladen...",
        'file_analysis': "📄 <b>Datei:</b> {file_name}\n\n🤖 <b>Analyse:</b>\n\n{analysis}",
        'image_analyzing': "🔍 Analysieren...",
        'image_analysis': "📸 <b>Analyse (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP",
        'image_generating': "🎨 Generieren...",
        'image_generated': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI",
        'generation_error': "❌ Generierungsfehler",
        'ai_no_question': "❓ /ai [Frage]",
        'context_cleared': "🧹 Kontext gelöscht!",
        'error': "❌ Fehler: {error}",
        'ai_error': "😔 Fehler",
        'note_no_text': "❓ /note [Text]",
        'delnote_no_num': "❓ /delnote [Nummer]",
        'memorysave_usage': "❓ /memorysave [Schlüssel] [Wert]",
        'memoryget_usage': "❓ /memoryget [Schlüssel]",
        'memorydel_usage': "❓ /memorydel [Schlüssel]",
        'todo_usage': "❓ /todo add [Text] | list | del [Nummer]",
        'todo_add_usage': "❓ /todo add [Text]",
        'todo_del_usage': "❓ /todo del [Nummer]",
        'translate_usage': "❓ /translate [Sprache] [Text]\n\nBeispiel: /translate en Hallo",
        'calc_usage': "❓ /calc [Ausdruck]\n\nBeispiel: /calc 2+2*5",
        'password_usage': "❓ /password [Länge]",
        'random_usage': "❓ /random [min] [max]",
        'remind_usage': "❓ /remind [Minuten] [Text]",
        'grant_vip_usage': "❓ /grant_vip [id/@username] [Laufzeit]\n\nLaufzeiten: week, month, year, forever",
        'revoke_vip_usage': "❓ /revoke_vip [id/@username]",
        'broadcast_usage': "❓ /broadcast [Text]",
        'admin_only': "❌ Nur für den Ersteller.",
        'language_changed': "✅ Sprache geändert auf {lang}.",
        'choose_language': "🌐 <b>Sprache wählen:</b>",
        'broadcast_start': "📤 Broadcast...",
        'generate_usage': "❓ /generate [Beschreibung]\n\nBeispiel: /generate Sonnenuntergang über dem Ozean",
        'section_not_found': "❌ Abschnitt nicht gefunden.",
        'note_create': "➕ <b>Notiz erstellen</b>\n\n/note [Text]\nBeispiel: /note Brot kaufen",
    },
    'fr': {
        'welcome': """🤖 <b>AI DISCO BOT</b>

Bonjour, {first_name}! Je suis un bot alimenté par <b>Gemini 1.5 Flash</b>.

<b>🎯 Fonctionnalités:</b>
💬 Chat AI avec contexte
📝 Notes et tâches
🌍 Météo et heure
🎲 Divertissement
📎 Analyse de fichiers (VIP)
🔍 Analyse d'images (VIP)
🖼️ Génération d'images (VIP)

<b>⚡ Commandes:</b>
/help - Toutes les commandes
/vip - Statut VIP

<b>👨‍💻 Créateur:</b> @{CREATOR_USERNAME}""",
        'help_text': "📚 <b>Sélectionnez la section d'aide:</b>\n\nCliquez sur le bouton ci-dessous pour voir les commandes par thème.",
        'help_back': "🔙 Retour",
        'help_basic': "🏠 <b>Commandes de base:</b>\n\n🚀 /start - Démarrer le bot et salutation\n\n📖 /help - Liste complète des commandes\n\nℹ️ /info - Informations sur le bot\n\n📊 /status - Statut actuel et statistiques\n\n👤 /profile - Profil utilisateur\n\n⏱ /uptime - Temps de fonctionnement du bot",
        'help_ai': "💬 <b>Commandes AI:</b>\n\n🤖 /ai [question] - Poser une question à AI\n\n🧹 /clear - Effacer le contexte du chat",
        'help_memory': "🧠 <b>Mémoire:</b>\n\n💾 /memorysave [clé] [valeur] - Enregistrer dans la mémoire\n\n🔍 /memoryget [clé] - Obtenir de la mémoire\n\n📋 /memorylist - Liste des clés\n\n🗑 /memorydel [clé] - Supprimer la clé",
        'help_notes': "📝 <b>Notes:</b>\n\n➕ /note [texte] - Créer une note\n\n📋 /notes - Liste des notes\n\n🗑 /delnote [numéro] - Supprimer la note",
        'help_todo': "📋 <b>Tâches:</b>\n\n➕ /todo add [texte] - Ajouter une tâche\n\n📋 /todo list - Liste des tâches\n\n🗑 /todo del [numéro] - Supprimer la tâche",
        'help_utils': "🌍 <b>Utilitaires:</b>\n\n🕐 /time [ville] - Heure actuelle\n\n☀️ /weather [ville] - Météo\n\n🌐 /translate [langue] [texte] - Traduction\n\n🧮 /calc [expression] - Calculatrice\n\n🔑 /password [longueur] - Générateur de mot de passe",
        'help_games': "🎲 <b>Divertissement:</b>\n\n🎲 /random [min] [max] - Nombre aléatoire dans la plage\n\n🎯 /dice - Lancer de dé (1-6)\n\n🪙 /coin - Lancer de pièce (pile/face)\n\n😄 /joke - Blague aléatoire\n\n💭 /quote - Citation motivationnelle\n\n🔬 /fact - Fait intéressant",
        'help_vip': "💎 <b>Commandes VIP:</b>\n\n👑 /vip - Statut VIP\n\n🖼️ /generate [description] - Génération d'image\n\n⏰ /remind [minutes] [texte] - Rappel\n\n📋 /reminders - Liste des rappels\n\n📎 Envoyer fichier - Analyse (VIP)\n\n📸 Envoyer photo - Analyse (VIP)",
        'help_admin': "👑 <b>Commandes du Créateur:</b>\n\n🎁 /grant_vip [id/@username] [terme] - Accorder VIP (week/month/year/forever)\n\n❌ /revoke_vip [id/@username] - Révoquer VIP\n\n👥 /users - Liste des utilisateurs\n\n📢 /broadcast [texte] - Diffusion\n\n📈 /stats - Statistiques complètes\n\n💾 /backup - Sauvegarde",
        'info_text': """🤖 <b>AI DISCO BOT</b>

<b>Version:</b> 3.0
<b>AI:</b> Gemini 1.5 Flash
<b>Créateur:</b> @Ernest_Kostevich

<b>⚡ Fonctionnalités:</b>
• Chat AI rapide
• PostgreSQL
• Fonctionnalités VIP
• Analyse fichiers/photos (VIP)
• Génération d'images (VIP)

<b>💬 Support:</b> @Ernest_Kostevich""",
        'status_text': """📊 <b>STATUT</b>

<b>👥 Utilisateurs:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Activité:</b>
• Messages: {total_messages}
• Commandes: {total_commands}
• Requêtes AI: {ai_requests}

<b>⏱ Temps de fonctionnement:</b> {uptime_days}j {uptime_hours}h

<b>✅ Statut:</b> En ligne
<b>🤖 AI:</b> Gemini 1.5 ✓
<b>🗄️ BD:</b> {db_status}""",
        'profile_text': """👤 <b>{first_name}</b>
🆔 <code>{user_id}</code>
{username_line}
📅 {registered}
📊 Messages: {messages_count}
🎯 Commandes: {commands_count}
📝 Notes: {notes_count}
{language_line}
{vip_line}""",
        'uptime_text': """⏱ <b>TEMPS DE FONCTIONNEMENT</b>

🕐 Démarré: {start_time}
⏰ En exécution: {uptime_days}j {uptime_hours}h {uptime_minutes}m

✅ En ligne""",
        'vip_active': "💎 <b>STATUT VIP</b>\n\n✅ Actif!\n\n{vip_duration}\n\n<b>🎁 Avantages:</b>\n• ⏰ Rappels\n• 🖼️ Génération d'images\n• 🔍 Analyse d'images\n• 📎 Analyse de documents",
        'vip_inactive': "💎 <b>STATUT VIP</b>\n\n❌ Pas de VIP.\n\nContactez @Ernest_Kostevich",
        'note_added': "✅ Note #{note_id} enregistrée!\n\n📝 {note_text}",
        'notes_empty': "📭 Pas de notes.",
        'notes_list': "📝 <b>Notes ({notes_count}):</b>\n\n{notes_text}",
        'note_deleted': "✅ Note #{note_id} supprimée:\n\n📝 {note_text}",
        'note_not_found': "❌ Note #{note_id} non trouvée.",
        'memory_saved': "✅ Enregistré:\n🔑 <b>{key}</b> = <code>{value}</code>",
        'memory_got': "🔍 <b>{key}</b> = <code>{value}</code>",
        'memory_empty': "📭 Mémoire vide.",
        'memory_list': "🧠 <b>Mémoire:</b>\n\n{memory_text}",
        'memory_deleted': "✅ Clé '{key}' supprimée.",
        'memory_not_found': "❌ Clé '{key}' non trouvée.",
        'todo_added': "✅ Tâche #{todo_id} ajoutée!\n\n📋 {todo_text}",
        'todos_empty': "📭 Pas de tâches.",
        'todos_list': "📋 <b>Tâches ({todos_count}):</b>\n\n{todos_text}",
        'todo_deleted': "✅ Tâche #{todo_id} supprimée:\n\n📋 {todo_text}",
        'todo_not_found': "❌ Tâche #{todo_id} non trouvée.",
        'city_not_found': "❌ Ville '{city}' non trouvée.",
        'time_text': """⏰ <b>{city}</b>

🕐 Heure: {time}
📅 Date: {date}
🌍 Zone: {tz}""",
        'weather_text': """🌍 <b>{city}</b>

🌡 Température: {temp}°C
🤔 Ressentie: {feels}°C
☁️ {desc}
💧 Humidité: {humidity}%
💨 Vent: {wind} km/h""",
        'translate_text': "🌐 <b>Traduction:</b>\n\n{translation}",
        'calc_result': "🧮 <b>Résultat:</b>\n\n{expr} = <b>{result}</b>",
        'password_length_error': "❌ Longueur de 8 à 50.",
        'password_generated': "🔑 <b>Mot de passe:</b>\n\n<code>{password}</code>",
        'random_result': "🎲 Nombre de {min} à {max}:\n\n<b>{result}</b>",
        'dice_result': "🎲 {emoji} Lancé: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Lancé: <b>{result}</b>",
        'joke_text': "😄 <b>Blague:</b>\n\n{joke}",
        'quote_text': "💭 <b>Citation:</b>\n\n<i>{quote}</i>",
        'fact_text': "🔬 <b>Fait:</b>\n\n{fact}",
        'reminder_created': "⏰ Rappel créé!\n\n📝 {text}\n🕐 Dans {minutes} minutes",
        'reminders_empty': "📭 Pas de rappels.",
        'reminders_list': "⏰ <b>Rappels ({count}):</b>\n\n{reminders_text}",
        'reminder_sent': "⏰ <b>RAPPEL</b>\n\n📝 {text}",
        'vip_granted': "✅ VIP accordé!\n\n🆔 <code>{user_id}</code>\n⏰ {duration}",
        'vip_revoked': "✅ VIP révoqué!\n\n🆔 <code>{user_id}</code>",
        'user_not_found': "❌ Utilisateur '{identifier}' non trouvé.",
        'invalid_duration': "❌ Terme invalide.",
        'users_list': "👥 <b>UTILISATEURS ({count}):</b>\n\n{users_text}",
        'broadcast_done': "✅ Terminé!\n\n✅ Réussi: {success}\n❌ Erreurs: {failed}",
        'stats_text': """📊 <b>STATISTIQUES</b>

<b>👥 Utilisateurs:</b> {users_count}
<b>💎 VIP:</b> {vip_count}

<b>📈 Activité:</b>
• Messages: {total_messages}
• Commandes: {total_commands}
• Requêtes AI: {ai_requests}""",
        'backup_caption': "✅ Sauvegarde\n\n📅 {date}",
        'ai_chat_menu': "🤖 <b>Chat AI</b>\n\nÉcrivez simplement - je répondrai!\n/clear - effacer contexte",
        'notes_menu': "📝 <b>Notes</b>",
        'weather_menu': "🌍 <b>Météo</b>\n\n/weather [ville]\nExemple: /weather London",
        'time_menu': "⏰ <b>Heure</b>\n\n/time [ville]\nExemple: /time Tokyo",
        'entertainment_menu': "🎲 <b>Divertissement</b>",
        'vip_menu': "💎 <b>Menu VIP</b>",
        'admin_panel': "👑 <b>Panel Admin</b>",
        'generation_menu': "🖼️ <b>Génération (VIP)</b>\n\n/generate [description]\n\nExemples:\n• /generate coucher de soleil\n• /generate ville\n\n💡 Pollinations AI",
        'vip_required': "💎 {feature} pour VIP",
        'file_analysis_vip': "💎 Analyse de fichiers disponible uniquement pour les utilisateurs VIP.\n\nContactez @Ernest_Kostevich",
        'image_analysis_vip': "💎 Analyse d'images pour VIP.\n\nContactez @Ernest_Kostevich",
        'file_downloading': "📥 Téléchargement du fichier...",
        'file_analysis': "📄 <b>Fichier:</b> {file_name}\n\n🤖 <b>Analyse:</b>\n\n{analysis}",
        'image_analyzing': "🔍 Analyse...",
        'image_analysis': "📸 <b>Analyse (Gemini Vision):</b>\n\n{analysis}\n\n💎 VIP",
        'image_generating': "🎨 Génération...",
        'image_generated': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Pollinations AI",
        'generation_error': "❌ Erreur de génération",
        'ai_no_question': "❓ /ai [question]",
        'context_cleared': "🧹 Contexte effacé!",
        'error': "❌ Erreur: {error}",
        'ai_error': "😔 Erreur",
        'note_no_text': "❓ /note [texte]",
        'delnote_no_num': "❓ /delnote [numéro]",
        'memorysave_usage': "❓ /memorysave [clé] [valeur]",
        'memoryget_usage': "❓ /memoryget [clé]",
        'memorydel_usage': "❓ /memorydel [clé]",
        'todo_usage': "❓ /todo add [texte] | list | del [numéro]",
        'todo_add_usage': "❓ /todo add [texte]",
        'todo_del_usage': "❓ /todo del [numéro]",
        'translate_usage': "❓ /translate [langue] [texte]\n\nExemple: /translate en Bonjour",
        'calc_usage': "❓ /calc [expression]\n\nExemple: /calc 2+2*5",
        'password_usage': "❓ /password [longueur]",
        'random_usage': "❓ /random [min] [max]",
        'remind_usage': "❓ /remind [minutes] [texte]",
        'grant_vip_usage': "❓ /grant_vip [id/@username] [terme]\n\nTermes: week, month, year, forever",
        'revoke_vip_usage': "❓ /revoke_vip [id/@username]",
        'broadcast_usage': "❓ /broadcast [texte]",
        'admin_only': "❌ Uniquement pour le créateur.",
        'language_changed': "✅ Langue changée en {lang}.",
        'choose_language': "🌐 <b>Choisir la langue:</b>",
        'broadcast_start': "📤 Diffusion...",
        'generate_usage': "❓ /generate [description]\n\nExemple: /generate coucher de soleil sur l'océan",
        'section_not_found': "❌ Section non trouvée.",
        'note_create': "➕ <b>Créer une note</b>\n\n/note [texte]\nExemple: /note Acheter du pain",
    }
}

# Переводы кнопок меню
menu_buttons = {
    'ru': {
        'ai_chat': "💬 AI Чат",
        'notes': "📝 Заметки",
        'weather': "🌍 Погода",
        'time': "⏰ Время",
        'entertainment': "🎲 Развлечения",
        'info': "ℹ️ Инфо",
        'vip_menu': "💎 VIP Меню",
        'admin_panel': "👑 Админ Панель",
        'generation': "🖼️ Генерация",
    },
    'en': {
        'ai_chat': "💬 AI Chat",
        'notes': "📝 Notes",
        'weather': "🌍 Weather",
        'time': "⏰ Time",
        'entertainment': "🎲 Entertainment",
        'info': "ℹ️ Info",
        'vip_menu': "💎 VIP Menu",
        'admin_panel': "👑 Admin Panel",
        'generation': "🖼️ Generation",
    },
    'es': {
        'ai_chat': "💬 Chat AI",
        'notes': "📝 Notas",
        'weather': "🌍 Clima",
        'time': "⏰ Hora",
        'entertainment': "🎲 Entretenimiento",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menú VIP",
        'admin_panel': "👑 Panel Admin",
        'generation': "🖼️ Generación",
    },
    'it': {
        'ai_chat': "💬 Chat AI",
        'notes': "📝 Note",
        'weather': "🌍 Meteo",
        'time': "⏰ Ora",
        'entertainment': "🎲 Intrattenimento",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menù VIP",
        'admin_panel': "👑 Pannello Admin",
        'generation': "🖼️ Generazione",
    },
    'de': {
        'ai_chat': "💬 AI-Chat",
        'notes': "📝 Notizen",
        'weather': "🌍 Wetter",
        'time': "⏰ Zeit",
        'entertainment': "🎲 Unterhaltung",
        'info': "ℹ️ Info",
        'vip_menu': "💎 VIP-Menü",
        'admin_panel': "👑 Admin-Panel",
        'generation': "🖼️ Generierung",
    },
    'fr': {
        'ai_chat': "💬 Chat AI",
        'notes': "📝 Notes",
        'weather': "🌍 Météo",
        'time': "⏰ Heure",
        'entertainment': "🎲 Divertissement",
        'info': "ℹ️ Info",
        'vip_menu': "💎 Menu VIP",
        'admin_panel': "👑 Panel Admin",
        'generation': "🖼️ Génération",
    },
}

# Локализованные имена команд
command_names = {
    'start': {'ru': 'start', 'en': 'start', 'es': 'start', 'it': 'start', 'de': 'start', 'fr': 'start'},
    'help': {'ru': 'help', 'en': 'help', 'es': 'ayuda', 'it': 'aiuto', 'de': 'hilfe', 'fr': 'aide'},
    'info': {'ru': 'info', 'en': 'info', 'es': 'info', 'it': 'info', 'de': 'info', 'fr': 'info'},
    'status': {'ru': 'status', 'en': 'status', 'es': 'estado', 'it': 'stato', 'de': 'status', 'fr': 'statut'},
    'profile': {'ru': 'profile', 'en': 'profile', 'es': 'perfil', 'it': 'profilo', 'de': 'profil', 'fr': 'profil'},
    'uptime': {'ru': 'uptime', 'en': 'uptime', 'es': 'tiempoactivo', 'it': 'tempofunzionamento', 'de': 'laufzeit', 'fr': 'tempsfonctionnement'},
    'ai': {'ru': 'ai', 'en': 'ai', 'es': 'ia', 'it': 'ia', 'de': 'ki', 'fr': 'ia'},
    'clear': {'ru': 'clear', 'en': 'clear', 'es': 'limpiar', 'it': 'pulisci', 'de': 'löschen', 'fr': 'effacer'},
    'memorysave': {'ru': 'memorysave', 'en': 'memorysave', 'es': 'guardarmemoria', 'it': 'salvamemoria', 'de': 'speicherspeichern', 'fr': 'sauvegardermemoire'},
    'memoryget': {'ru': 'memoryget', 'en': 'memoryget', 'es': 'obtenermemoria', 'it': 'ottienimemoria', 'de': 'speicherabrufen', 'fr': 'obtenirmemoire'},
    'memorylist': {'ru': 'memorylist', 'en': 'memorylist', 'es': 'listamemoria', 'it': 'listamemoria', 'de': 'speicherliste', 'fr': 'listememoire'},
    'memorydel': {'ru': 'memorydel', 'en': 'memorydel', 'es': 'eliminarmemoria', 'it': 'eliminamemoria', 'de': 'speicherlöschen', 'fr': 'supprimermemoire'},
    'note': {'ru': 'note', 'en': 'note', 'es': 'nota', 'it': 'nota', 'de': 'notiz', 'fr': 'note'},
    'notes': {'ru': 'notes', 'en': 'notes', 'es': 'notas', 'it': 'note', 'de': 'notizen', 'fr': 'notes'},
    'delnote': {'ru': 'delnote', 'en': 'delnote', 'es': 'eliminarnota', 'it': 'eliminanota', 'de': 'notizlöschen', 'fr': 'supprimernote'},
    'todo': {'ru': 'todo', 'en': 'todo', 'es': 'tarea', 'it': 'compito', 'de': 'aufgabe', 'fr': 'tache'},
    'time': {'ru': 'time', 'en': 'time', 'es': 'hora', 'it': 'tempo', 'de': 'zeit', 'fr': 'temps'},
    'weather': {'ru': 'weather', 'en': 'weather', 'es': 'clima', 'it': 'meteo', 'de': 'wetter', 'fr': 'meteo'},
    'translate': {'ru': 'translate', 'en': 'translate', 'es': 'traducir', 'it': 'traduci', 'de': 'übersetzen', 'fr': 'traduire'},
    'calc': {'ru': 'calc', 'en': 'calc', 'es': 'calc', 'it': 'calc', 'de': 'rechner', 'fr': 'calc'},
    'password': {'ru': 'password', 'en': 'password', 'es': 'contrasena', 'it': 'password', 'de': 'passwort', 'fr': 'motdepasse'},
    'random': {'ru': 'random', 'en': 'random', 'es': 'aleatorio', 'it': 'casuale', 'de': 'zufall', 'fr': 'aleatoire'},
    'dice': {'ru': 'dice', 'en': 'dice', 'es': 'dado', 'it': 'dado', 'de': 'würfel', 'fr': 'de'},
    'coin': {'ru': 'coin', 'en': 'coin', 'es': 'moneda', 'it': 'moneta', 'de': 'münze', 'fr': 'piece'},
    'joke': {'ru': 'joke', 'en': 'joke', 'es': 'chiste', 'it': 'barzelletta', 'de': 'witz', 'fr': 'blague'},
    'quote': {'ru': 'quote', 'en': 'quote', 'es': 'cita', 'it': 'citazione', 'de': 'zitat', 'fr': 'citation'},
    'fact': {'ru': 'fact', 'en': 'fact', 'es': 'hecho', 'it': 'fatto', 'de': 'fakt', 'fr': 'fait'},
    'vip': {'ru': 'vip', 'en': 'vip', 'es': 'vip', 'it': 'vip', 'de': 'vip', 'fr': 'vip'},
    'remind': {'ru': 'remind', 'en': 'remind', 'es': 'recordar', 'it': 'ricorda', 'de': 'erinnern', 'fr': 'rappeler'},
    'reminders': {'ru': 'reminders', 'en': 'reminders', 'es': 'recordatorios', 'it': 'promemoria', 'de': 'erinnerungen', 'fr': 'rappels'},
    'generate': {'ru': 'generate', 'en': 'generate', 'es': 'generar', 'it': 'genera', 'de': 'generieren', 'fr': 'generer'},
    'grant_vip': {'ru': 'grant_vip', 'en': 'grant_vip', 'es': 'otorgar_vip', 'it': 'concedi_vip', 'de': 'gewähre_vip', 'fr': 'accorder_vip'},
    'revoke_vip': {'ru': 'revoke_vip', 'en': 'revoke_vip', 'es': 'revocar_vip', 'it': 'revoca_vip', 'de': 'widerrufe_vip', 'fr': 'revoquer_vip'},
    'users': {'ru': 'users', 'en': 'users', 'es': 'usuarios', 'it': 'utenti', 'de': 'benutzer', 'fr': 'utilisateurs'},
    'broadcast': {'ru': 'broadcast', 'en': 'broadcast', 'es': 'difusion', 'it': 'trasmissione', 'de': 'broadcast', 'fr': 'diffusion'},
    'stats': {'ru': 'stats', 'en': 'stats', 'es': 'estadisticas', 'it': 'statistiche', 'de': 'statistiken', 'fr': 'statistiques'},
    'backup': {'ru': 'backup', 'en': 'backup', 'es': 'respaldo', 'it': 'backup', 'de': 'backup', 'fr': 'sauvegarde'},
    'lang': {'ru': 'lang', 'en': 'lang', 'es': 'idioma', 'it': 'lingua', 'de': 'sprache', 'fr': 'langue'},
}

# Модель Gemini
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="You are AI DISCO BOT, a friendly and helpful AI assistant built with Gemini 1.5. Respond in a friendly, engaging manner with emojis where appropriate. Your creator is @Ernest_Kostevich."
)

vision_model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# База данных
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    notes = Column(JSON, default=list)
    todos = Column(JSON, default=list)
    memory = Column(JSON, default=dict)
    reminders = Column(JSON, default=list)
    registered = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    messages_count = Column(Integer, default=0)
    commands_count = Column(Integer, default=0)
    language = Column(String(2), default='ru')

class Chat(Base):
    __tablename__ = 'chats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    message = Column(Text)
    response = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)

class Statistics(Base):
    __tablename__ = 'statistics'
    
    key = Column(String(50), primary_key=True)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.now)

# Инициализация БД
engine = None
Session = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("✅ PostgreSQL подключен!")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка подключения к БД: {e}. Fallback на JSON.")
        engine = None
        Session = None
else:
    logger.warning("⚠️ БД не настроена. Используется JSON.")

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.chat_sessions = {}
        self.username_to_id = {}
        
        if not engine:
            self.users = self.load_users()
            self.stats = self.load_stats()
            self.update_username_mapping()
        else:
            self.users = {}
            self.stats = self.get_stats_from_db()

    def load_users(self) -> Dict:
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {}
                    return {int(k): v for k, v in data.items()}
            return {}
        except Exception as e:
            logger.warning(f"Ошибка загрузки users.json: {e}")
            return {}

    def save_users(self):
        if engine:
            return
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            self.update_username_mapping()
        except Exception as e:
            logger.warning(f"Ошибка сохранения users.json: {e}")

    def load_stats(self) -> Dict:
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        return data
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0, 'start_date': datetime.now().isoformat()}
        except Exception as e:
            logger.warning(f"Ошибка загрузки statistics.json: {e}")
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0, 'start_date': datetime.now().isoformat()}

    def save_stats(self):
        if engine:
            session = Session()
            try:
                session.merge(Statistics(key='global', value=self.stats, updated_at=datetime.now()))
                session.commit()
            except Exception as e:
                logger.warning(f"Ошибка сохранения stats в БД: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            try:
                with open(self.stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self.stats, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Ошибка сохранения statistics.json: {e}")

    def get_stats_from_db(self) -> Dict:
        if not engine:
            return self.load_stats()
        session = Session()
        try:
            stat = session.query(Statistics).filter_by(key='global').first()
            if stat:
                return stat.value
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0, 'start_date': datetime.now().isoformat()}
        except Exception as e:
            logger.warning(f"Ошибка загрузки stats из БД: {e}")
            return self.load_stats()
        finally:
            session.close()

    def update_username_mapping(self):
        self.username_to_id = {}
        for user_id, user_data in self.users.items():
            username = user_data.get('username')
            if username:
                self.username_to_id[username.lower()] = user_id

    def get_user_id_by_identifier(self, identifier: str) -> Optional[int]:
        identifier = identifier.strip()
        if identifier.startswith('@'):
            identifier = identifier[1:]
        if identifier.isdigit():
            return int(identifier)
        if engine:
            session = Session()
            try:
                user = session.query(User).filter(User.username.ilike(f"%{identifier}%")).first()
                return user.id if user else None
            finally:
                session.close()
        return self.username_to_id.get(identifier.lower())

    def get_user(self, user_id: int) -> Dict:
        if engine:
            session = Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id)
                    session.add(user)
                    session.commit()
                return {
                    'id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'vip': user.vip,
                    'vip_until': user.vip_until.isoformat() if user.vip_until else None,
                    'notes': user.notes or [],
                    'todos': user.todos or [],
                    'memory': user.memory or {},
                    'reminders': user.reminders or [],
                    'registered': user.registered.isoformat() if user.registered else datetime.now().isoformat(),
                    'last_active': user.last_active.isoformat() if user.last_active else datetime.now().isoformat(),
                    'messages_count': user.messages_count or 0,
                    'commands_count': user.commands_count or 0,
                    'language': user.language or 'ru'
                }
            finally:
                session.close()
        else:
            if user_id not in self.users:
                self.users[user_id] = {
                    'id': user_id, 'username': '', 'first_name': '', 'vip': False, 'vip_until': None,
                    'notes': [], 'todos': [], 'memory': {}, 'reminders': [],
                    'registered': datetime.now().isoformat(), 'last_active': datetime.now().isoformat(),
                    'messages_count': 0, 'commands_count': 0, 'language': 'ru'
                }
                self.save_users()
            return self.users[user_id]

    def update_user(self, user_id: int, data: Dict):
        if engine:
            session = Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id)
                    session.add(user)
                for key, value in data.items():
                    if key == 'vip_until' and value:
                        value = datetime.fromisoformat(value) if isinstance(value, str) else value
                    setattr(user, key, value)
                user.last_active = datetime.now()
                session.commit()
            except Exception as e:
                logger.warning(f"Ошибка обновления пользователя в БД: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            user = self.get_user(user_id)
            user.update(data)
            user['last_active'] = datetime.now().isoformat()
            self.save_users()

    def is_vip(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user.get('vip', False):
            return False
        vip_until = user.get('vip_until')
        if vip_until is None:
            return True
        try:
            vip_until_dt = datetime.fromisoformat(vip_until)
            if datetime.now() > vip_until_dt:
                self.update_user(user_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True

    def get_all_users(self):
        if engine:
            session = Session()
            try:
                users = session.query(User).all()
                return {u.id: {'id': u.id, 'username': u.username, 'first_name': u.first_name, 'vip': u.vip, 'language': u.language} for u in users}
            finally:
                session.close()
        return self.users

    def save_chat(self, user_id: int, message: str, response: str):
        if not engine:
            return
        session = Session()
        try:
            chat = Chat(user_id=user_id, message=message[:1000], response=response[:1000])
            session.add(chat)
            session.commit()
        except Exception as e:
            logger.warning(f"Ошибка сохранения чата: {e}")
        finally:
            session.close()

    def get_chat_session(self, user_id: int):
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = model.start_chat(history=[])
        return self.chat_sessions[user_id]

    def clear_chat_session(self, user_id: int):
        if user_id in self.chat_sessions:
            del self.chat_sessions[user_id]

storage = DataStorage()
scheduler = AsyncIOScheduler()

def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Создатель: {user.id}")

def is_creator(user_id: int) -> bool:
    return user_id == CREATOR_ID

def get_lang(user_id: int) -> str:
    user = storage.get_user(user_id)
    return user.get('language', 'ru')

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    lang = get_lang(user_id)
    mb = menu_buttons[lang]
    keyboard = [
        [KeyboardButton(mb['ai_chat']), KeyboardButton(mb['notes'])],
        [KeyboardButton(mb['weather']), KeyboardButton(mb['time'])],
        [KeyboardButton(mb['entertainment']), KeyboardButton(mb['info'])],
    ]
    if storage.is_vip(user_id):
        keyboard.append([KeyboardButton(mb['vip_menu']), KeyboardButton(mb['generation'])])
    if is_creator(user_id):
        keyboard.append([KeyboardButton(mb['admin_panel'])])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_help_keyboard(lang: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    tr = translations[lang]
    keyboard = [
        [InlineKeyboardButton(tr['help_basic'].split('<b>')[0].strip(), callback_data="help_basic")],
        [InlineKeyboardButton(tr['help_ai'].split('<b>')[0].strip(), callback_data="help_ai")],
        [InlineKeyboardButton(tr['help_memory'].split('<b>')[0].strip(), callback_data="help_memory")],
        [InlineKeyboardButton(tr['help_notes'].split('<b>')[0].strip(), callback_data="help_notes")],
        [InlineKeyboardButton(tr['help_todo'].split('<b>')[0].strip(), callback_data="help_todo")],
        [InlineKeyboardButton(tr['help_utils'].split('<b>')[0].strip(), callback_data="help_utils")],
        [InlineKeyboardButton(tr['help_games'].split('<b>')[0].strip(), callback_data="help_games")],
        [InlineKeyboardButton(tr['help_vip'].split('<b>')[0].strip(), callback_data="help_vip")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(tr['help_admin'].split('<b>')[0].strip(), callback_data="help_admin")])
    keyboard.append([InlineKeyboardButton(tr['help_back'], callback_data="help_back")])
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    identify_creator(update.effective_user)
    lang = get_lang(user_id)
    tr = translations[lang]
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'commands_count': user_data.get('commands_count', 0) + 1})
    is_admin = is_creator(user_id)
    await update.message.reply_text(
        tr['help_text'],
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(lang, is_admin)
    )

async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    is_admin = is_creator(user_id)

    if data == "help_back":
        await query.edit_message_text(
            tr['help_text'],
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(lang, is_admin)
        )
        return

    sections = {
        "help_basic": tr['help_basic'],
        "help_ai": tr['help_ai'],
        "help_memory": tr['help_memory'],
        "help_notes": tr['help_notes'],
        "help_todo': tr['help_todo'],
        'help_utils': tr['help_utils'],
        'help_games': tr['help_games'],
        'help_vip': tr['help_vip'],
    }

    if data == "help_admin" and is_admin:
        text = tr['help_admin']
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(tr['help_back'], callback_data="help_back")]])
    elif data in sections:
        text = sections[data]
        markup = get_help_keyboard(lang, is_admin)
    else:
        await query.edit_message_text(tr['section_not_found'])
        return

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup
    )

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")],
    ]
    await update.message.reply_text(tr['choose_language'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def generate_image_pollinations(prompt: str) -> Optional[str]:
    try:
        encoded_prompt = urlquote(prompt)
        return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
    except Exception as e:
        logger.warning(f"Ошибка генерации изображения: {e}")
        return None

async def analyze_image_with_gemini(image_bytes: bytes, prompt: str = "Опиши подробно что изображено") -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = vision_model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка анализа: {str(e)}"

async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    try:
        ext = filename.lower().split('.')[-1]
        if ext == 'txt':
            try:
                return file_bytes.decode('utf-8')
            except:
                return file_bytes.decode('cp1251', errors='ignore')
        elif ext == 'pdf':
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
            text = "".join([page.get_text() for page in doc])
            doc.close()
            return text
        elif ext in ['doc', 'docx']:
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join([para.text for para in doc.paragraphs])
        else:
            return file_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Ошибка извлечения текста: {e}")
        return f"❌ Ошибка: {str(e)}"

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not storage.is_vip(user_id):
        await update.message.reply_text(tr['file_analysis_vip'])
        return
    document = update.message.document
    file_name = document.file_name or "file"
    await update.message.reply_text(tr['file_downloading'])
    try:
        file_obj = await context.bot.get_file(document.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        extracted_text = await extract_text_from_document(bytes(file_bytes), file_name)
        if extracted_text.startswith("❌") or extracted_text.startswith("⚠️"):
            await update.message.reply_text(extracted_text)
            return
        analysis_prompt = f"Analyse the file '{file_name}':\n\n{extracted_text[:4000]}"  # Adapt prompt to lang if needed
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(analysis_prompt)
        storage.save_chat(user_id, f"File {file_name}", response.text)
        await update.message.reply_text(tr['file_analysis'].format(file_name=file_name, analysis=response.text), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки документа: {e}")
        await update.message.reply_text(tr['error'].format(error=str(e)))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not storage.is_vip(user_id):
        await update.message.reply_text(tr['image_analysis_vip'])
        return
    photo = update.message.photo[-1]
    caption = update.message.caption or "Describe what's in the picture"  # Adapt to lang
    await update.message.reply_text(tr['image_analyzing'])
    try:
        file_obj = await context.bot.get_file(photo.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        analysis = await analyze_image_with_gemini(bytes(file_bytes), caption)
        storage.save_chat(user_id, "Photo analysis", analysis)
        await update.message.reply_text(tr['image_analysis'].format(analysis=analysis), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки фото: {e}")
        await update.message.reply_text(tr['error'].format(error=str(e)))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    user_id = user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'username': user.username or '', 'first_name': user.first_name or '', 'commands_count': user_data.get('commands_count', 0) + 1})
    welcome_text = tr['welcome'].format(first_name=user.first_name)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not storage.is_vip(user_id):
        await update.message.reply_text(tr['vip_required'].format(feature="Generation"))
        return
    if not context.args:
        await update.message.reply_text(tr['generate_usage'])
        return
    prompt = ' '.join(context.args)
    await update.message.reply_text(tr['image_generating'])
    try:
        image_url = await generate_image_pollinations(prompt)
        if image_url:
            await update.message.reply_photo(photo=image_url, caption=tr['image_generated'].format(prompt=prompt), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(tr['generation_error'])
    except Exception as e:
        logger.warning(f"Ошибка генерации: {e}")
        await update.message.reply_text(tr['error'].format(error=str(e)))

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not context.args:
        await update.message.reply_text(tr['ai_no_question'])
        return
    await process_ai_message(update, ' '.join(context.args), user_id)

async def process_ai_message(update: Update, text: str, user_id: int):
    lang = get_lang(user_id)
    tr = translations[lang]
    try:
        await update.message.chat.send_action("typing")
        chat = storage.get_chat_session(user_id)
        prompt = f"Respond in {lang_full[lang]}: {text}"
        response = chat.send_message(prompt)
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response.text)
        await update.message.reply_text(response.text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"AI: {e}")
        await update.message.reply_text(tr['ai_error'])

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    storage.clear_chat_session(user_id)
    await update.message.reply_text(tr['context_cleared'])

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    await update.message.reply_text(tr['info_text'], parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    stats = storage.stats
    all_users = storage.get_all_users()
    uptime = datetime.now() - BOT_START_TIME
    db_status = 'PostgreSQL ✓' if engine else 'JSON'
    status_text = tr['status_text'].format(
        users_count=len(all_users),
        vip_count=sum(1 for u in all_users.values() if u.get('vip', False)),
        total_messages=stats.get('total_messages', 0),
        total_commands=stats.get('total_commands', 0),
        ai_requests=stats.get('ai_requests', 0),
        uptime_days=uptime.days,
        uptime_hours=uptime.seconds // 3600,
        db_status=db_status
    )
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    user = storage.get_user(user_id)
    username_line = f"📱 @{user['username']}\n" if user.get('username') else ""
    language_line = f"🌐 Language: {lang_full[lang]}\n" 
    vip_line = ""
    if storage.is_vip(user_id):
        vip_until = user.get('vip_until')
        if vip_until:
            vip_line = f"\n💎 VIP until: {datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')}"
        else:
            vip_line = "\n💎 VIP: Forever ♾️"
    profile_text = tr['profile_text'].format(
        first_name=user.get('first_name', 'User'),
        user_id=user.get('id'),
        username_line=username_line,
        registered=user.get('registered', '')[:10],
        messages_count=user.get('messages_count', 0),
        commands_count=user.get('commands_count', 0),
        notes_count=len(user.get('notes', [])),
        language_line=language_line,
        vip_line=vip_line
    )
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    uptime = datetime.now() - BOT_START_TIME
    await update.message.reply_text(tr['uptime_text'].format(
        start_time=BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S'),
        uptime_days=uptime.days,
        uptime_hours=uptime.seconds // 3600,
        uptime_minutes=(uptime.seconds % 3600) // 60
    ), parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    user = storage.get_user(user_id)
    if storage.is_vip(user_id):
        vip_duration = ""
        vip_until = user.get('vip_until')
        if vip_until:
            vip_duration = f"⏰ Until: {datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')}\n\n"
        else:
            vip_duration = "⏰ Forever ♾️\n\n"
        vip_text = tr['vip_active'].format(vip_duration=vip_duration)
    else:
        vip_text = tr['vip_inactive']
    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not context.args:
        await update.message.reply_text(tr['note_no_text'])
        return
    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)
    note = {'text': note_text, 'created': datetime.now().isoformat()}
    notes = user.get('notes', [])
    notes.append(note)
    storage.update_user(user_id, {'notes': notes})
    await update.message.reply_text(tr['note_added'].format(note_id=len(notes), note_text=note_text))

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    user = storage.get_user(user_id)
    notes = user.get('notes', [])
    if not notes:
        await update.message.reply_text(tr['notes_empty'])
        return
    notes_text = ""
    for i, note in enumerate(notes, 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += f"<b>#{i}</b> ({created.strftime('%d.%m.%Y')})\n{note['text']}\n\n"
    await update.message.reply_text(tr['notes_list'].format(notes_count=len(notes), notes_text=notes_text), parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not context.args:
        await update.message.reply_text(tr['delnote_no_num'])
        return
    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        if 1 <= note_num <= len(notes):
            deleted_note = notes.pop(note_num - 1)
            storage.update_user(user_id, {'notes': notes})
            await update.message.reply_text(tr['note_deleted'].format(note_id=note_num, note_text=deleted_note['text']))
        else:
            await update.message.reply_text(tr['note_not_found'].format(note_id=note_num))
    except ValueError:
        await update.message.reply_text("❌ Specify number.")

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if len(context.args) < 2:
        await update.message.reply_text(tr['memorysave_usage'])
        return
    key = context.args[0]
    value = ' '.join(context.args[1:])
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    memory[key] = value
    storage.update_user(user_id, {'memory': memory})
    await update.message.reply_text(tr['memory_saved'].format(key=key, value=value), parse_mode=ParseMode.HTML)

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not context.args:
        await update.message.reply_text(tr['memoryget_usage'])
        return
    key = context.args[0]
    user = storage.get_user(user_id)
    if key in user.get('memory', {}):
        await update.message.reply_text(tr['memory_got'].format(key=key, value=user['memory'][key]), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(tr['memory_not_found'].format(key=key))

async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    if not memory:
        await update.message.reply_text(tr['memory_empty'])
        return
    memory_text = ""
    for key, value in memory.items():
        memory_text += f"🔑 <b>{key}</b>: <code>{value}</code>\n"
    await update.message.reply_text(tr['memory_list'].format(memory_text=memory_text), parse_mode=ParseMode.HTML)

async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not context.args:
        await update.message.reply_text(tr['memorydel_usage'])
        return
    key = context.args[0]
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    if key in memory:
        del memory[key]
        storage.update_user(user_id, {'memory': memory})
        await update.message.reply_text(tr['memory_deleted'].format(key=key))
    else:
        await update.message.reply_text(tr['memory_not_found'].format(key=key))

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not context.args:
        await update.message.reply_text(tr['todo_usage'])
        return
    subcommand = context.args[0].lower()
    user = storage.get_user(user_id)
    if subcommand == 'add':
        if len(context.args) < 2:
            await update.message.reply_text(tr['todo_add_usage'])
            return
        todo_text = ' '.join(context.args[1:])
        todo = {'text': todo_text, 'created': datetime.now().isoformat()}
        todos = user.get('todos', [])
        todos.append(todo)
        storage.update_user(user_id, {'todos': todos})
        await update.message.reply_text(tr['todo_added'].format(todo_id=len(todos), todo_text=todo_text))
    elif subcommand == 'list':
        todos = user.get('todos', [])
        if not todos:
            await update.message.reply_text(tr['todos_empty'])
            return
        todos_text = ""
        for i, todo in enumerate(todos, 1):
            created = datetime.fromisoformat(todo['created'])
            todos_text += f"<b>#{i}</b> ({created.strftime('%d.%m')})\n{todo['text']}\n\n"
        await update.message.reply_text(tr['todos_list'].format(todos_count=len(todos), todos_text=todos_text), parse_mode=ParseMode.HTML)
    elif subcommand == 'del':
        if len(context.args) < 2:
            await update.message.reply_text(tr['todo_del_usage'])
            return
        try:
            todo_num = int(context.args[1])
            todos = user.get('todos', [])
            if 1 <= todo_num <= len(todos):
                deleted_todo = todos.pop(todo_num - 1)
                storage.update_user(user_id, {'todos': todos})
                await update.message.reply_text(tr['todo_deleted'].format(todo_id=todo_num, todo_text=deleted_todo['text']))
            else:
                await update.message.reply_text(tr['todo_not_found'].format(todo_id=todo_num))
        except ValueError:
            await update.message.reply_text("❌ Specify number.")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    city = ' '.join(context.args) if context.args else 'Moscow'
    # Расширенный словарь часовых поясов
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
        'beijing': 'Asia/Shanghai',
        'madrid': 'Europe/Madrid',
        'rome': 'Europe/Rome',
        'berlin': 'Europe/Berlin',
        'paris': 'Europe/Paris',
        # Добавьте больше по необходимости
    }
    city_lower = city.lower()
    tz_name = timezones.get(city_lower, None)
    if tz_name is None:
        # Пытаемся найти похожий
        for key, value in timezones.items():
            if city_lower in key:
                tz_name = value
                break
    if tz_name is None:
        await update.message.reply_text(tr['city_not_found'].format(city=city))
        return
    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        await update.message.reply_text(tr['time_text'].format(
            city=city.title(),
            time=current_time.strftime('%H:%M:%S'),
            date=current_time.strftime('%d.%m.%Y'),
            tz=tz_name
        ), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка времени: {e}")
        await update.message.reply_text(tr['error'].format(error=str(e)))

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    city = ' '.join(context.args) if context.args else 'Moscow'
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?format=j1&lang={lang}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data['current_condition'][0]
                    temp_c = current['temp_C']
                    feels_like = current['FeelsLikeC']
                    description = current.get(f'lang_{lang}', current['weatherDesc'][0]['value'])
                    humidity = current['humidity']
                    wind_speed = current['windspeedKmph']
                    weather_text = tr['weather_text'].format(
                        city=city.title(),
                        temp=temp_c,
                        feels=feels_like,
                        desc=description,
                        humidity=humidity,
                        wind=wind_speed
                    )
                    await update.message.reply_text(weather_text, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(tr['city_not_found'].format(city=city))
    except Exception as e:
        logger.warning(f"Ошибка погоды: {e}")
        await update.message.reply_text(tr['error'].format(error="Weather retrieval error."))

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if len(context.args) < 2:
        await update.message.reply_text(tr['translate_usage'])
        return
    target_lang = context.args[0]
    text = ' '.join(context.args[1:])
    try:
        prompt = f"Translate to {target_lang}: {text}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(prompt)
        await update.message.reply_text(tr['translate_text'].format(translation=response.text), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка перевода: {e}")
        await update.message.reply_text(tr['error'].format(error="Translation error."))

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not context.args:
        await update.message.reply_text(tr['calc_usage'])
        return
    expression = ' '.join(context.args)
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        await update.message.reply_text(tr['calc_result'].format(expr=expression, result=result), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка расчета: {e}")
        await update.message.reply_text(tr['error'].format(error="Calculation error."))

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text(tr['password_length_error'])
            return
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(tr['password_generated'].format(password=password), parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(tr['password_usage'])

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    try:
        if len(context.args) >= 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        else:
            min_val = 1
            max_val = 100
        result = random.randint(min_val, max_val)
        await update.message.reply_text(tr['random_result'].format(min=min_val, max=max_val, result=result), parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(tr['random_usage'])

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    await update.message.reply_text(tr['dice_result'].format(emoji=dice_emoji, result=result), parse_mode=ParseMode.HTML)

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    coin_results = {'ru': ['Орёл', 'Решка'], 'en': ['Heads', 'Tails'], 'es': ['Cara', 'Cruz'], 'it': ['Testa', 'Croce'], 'de': ['Kopf', 'Zahl'], 'fr': ['Pile', 'Face']}
    emojis = {'ru': ['🦅', '💰'], 'en': ['🦅', '💰'], 'es': ['🦅', '💰'], 'it': ['🦅', '💰'], 'de': ['🦅', '💰'], 'fr': ['🦅', '💰']}
    result = random.choice(coin_results[lang])
    emoji = emojis[lang][0] if result == coin_results[lang][0] else emojis[lang][1]
    await update.message.reply_text(tr['coin_result'].format(emoji=emoji, result=result), parse_mode=ParseMode.HTML)

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    jokes = {
        'ru': ["Программист ложится спать. Жена: — Закрой окно, холодно! Программист: — И что, если я закрою окно, станет тепло? 😄"],
        'en': ["Why do programmers prefer dark mode? Because light attracts bugs! 😄"],
        'es': ["¿Por qué los programadores prefieren el modo oscuro? ¡Porque la luz atrae errores! 😄"],
        'it': ["Perché i programmatori preferiscono la modalità oscura? Perché la luce attrae bug! 😄"],
        'de': ["Warum bevorzugen Programmierer den Dark Mode? Weil Licht Bugs anzieht! 😄"],
        'fr': ["Pourquoi les programmeurs préfèrent le mode sombre ? Parce que la lumière attire les bugs ! 😄"],
    }
    joke = random.choice(jokes[lang])
    await update.message.reply_text(tr['joke_text'].format(joke=joke), parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    quotes = {
        'ru': ["Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс"],
        'en': ["The only way to do great work is to love what you do. — Steve Jobs"],
        'es': ["La única forma de hacer un gran trabajo es amar lo que haces. — Steve Jobs"],
        'it': ["L'unico modo per fare un ottimo lavoro è amare ciò che fai. — Steve Jobs"],
        'de': ["Der einzige Weg, großartige Arbeit zu leisten, ist zu lieben, was man tut. — Steve Jobs"],
        'fr': ["La seule façon de faire du bon travail est d'aimer ce que vous faites. — Steve Jobs"],
    }
    quote = random.choice(quotes[lang])
    await update.message.reply_text(tr['quote_text'].format(quote=quote), parse_mode=ParseMode.HTML)

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    facts = {
        'ru': ["🌍 Земля — единственная планета Солнечной системы, названная не в честь бога."],
        'en': ["🌍 Earth is the only planet in the Solar System not named after a god."],
        'es': ["🌍 La Tierra es el único planeta del Sistema Solar no nombrado en honor a un dios."],
        'it': ["🌍 La Terra è l'unico pianeta del Sistema Solare non chiamato in onore di un dio."],
        'de': ["🌍 Die Erde ist der einzige Planet im Sonnensystem, der nicht nach einem Gott benannt ist."],
        'fr': ["🌍 La Terre est la seule planète du Système Solaire non nommée d'après un dieu."],
    }
    fact = random.choice(facts[lang])
    await update.message.reply_text(tr['fact_text'].format(fact=fact), parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not storage.is_vip(user_id):
        await update.message.reply_text(tr['vip_required'].format(feature="Reminders"))
        return
    if len(context.args) < 2:
        await update.message.reply_text(tr['remind_usage'])
        return
    try:
        minutes = int(context.args[0])
        text = ' '.join(context.args[1:])
        remind_time = datetime.now() + timedelta(minutes=minutes)
        user = storage.get_user(user_id)
        reminder = {'text': text, 'time': remind_time.isoformat(), 'created': datetime.now().isoformat()}
        reminders = user.get('reminders', [])
        reminders.append(reminder)
        storage.update_user(user_id, {'reminders': reminders})
        scheduler.add_job(send_reminder, 'date', run_date=remind_time, args=[context.bot, user_id, text, lang])
        await update.message.reply_text(tr['reminder_created'].format(text=text, minutes=minutes))
    except ValueError:
        await update.message.reply_text(tr['remind_usage'])

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    if not storage.is_vip(user_id):
        await update.message.reply_text(tr['vip_required'].format(feature="Reminders"))
        return
    user = storage.get_user(user_id)
    reminders = user.get('reminders', [])
    if not reminders:
        await update.message.reply_text(tr['reminders_empty'])
        return
    reminders_text = ""
    for i, reminder in enumerate(reminders, 1):
        remind_time = datetime.fromisoformat(reminder['time'])
        reminders_text += f"<b>#{i}</b> {remind_time.strftime('%d.%m %H:%M')}\n📝 {reminder['text']}\n\n"
    await update.message.reply_text(tr['reminders_list'].format(count=len(reminders), reminders_text=reminders_text), parse_mode=ParseMode.HTML)

async def send_reminder(bot, user_id: int, text: str, lang: str):
    tr = translations[lang]
    try:
        await bot.send_message(chat_id=user_id, text=tr['reminder_sent'].format(text=text), parse_mode=ParseMode.HTML)
        user = storage.get_user(user_id)
        reminders = [r for r in user.get('reminders', []) if r['text'] != text]
        storage.update_user(user_id, {'reminders': reminders})
    except Exception as e:
        logger.warning(f"Ошибка отправки напоминания: {e}")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    identify_creator(update.effective_user)
    if not is_creator(user_id):
        await update.message.reply_text(tr['admin_only'])
        return
    if len(context.args) < 2:
        await update.message.reply_text(tr['grant_vip_usage'])
        return
    try:
        identifier = context.args[0]
        duration = context.args[1].lower()
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(tr['user_not_found'].format(identifier=identifier))
            return
        durations = {'week': timedelta(weeks=1), 'month': timedelta(days=30), 'year': timedelta(days=365), 'forever': None}
        if duration not in durations:
            await update.message.reply_text(tr['invalid_duration'])
            return
        if durations[duration]:
            vip_until = datetime.now() + durations[duration]
            storage.update_user(target_id, {'vip': True, 'vip_until': vip_until.isoformat()})
            duration_text = f"until {vip_until.strftime('%d.%m.%Y')}"
        else:
            storage.update_user(target_id, {'vip': True, 'vip_until': None})
            duration_text = "forever"
        await update.message.reply_text(tr['vip_granted'].format(user_id=target_id, duration=duration_text), parse_mode=ParseMode.HTML)
        target_lang = get_lang(target_id)
        target_tr = translations[target_lang]
        try:
            await context.bot.send_message(chat_id=target_id, text=target_tr['vip_granted'].format(user_id=target_id, duration=duration_text), parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Ошибка уведомления о VIP: {e}")
    except Exception as e:
        logger.warning(f"Ошибка grant_vip: {e}")
        await update.message.reply_text(tr['error'].format(error=str(e)))

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    identify_creator(update.effective_user)
    if not is_creator(user_id):
        await update.message.reply_text(tr['admin_only'])
        return
    if not context.args:
        await update.message.reply_text(tr['revoke_vip_usage'])
        return
    try:
        identifier = context.args[0]
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(tr['user_not_found'].format(identifier=identifier))
            return
        storage.update_user(target_id, {'vip': False, 'vip_until': None})
        await update.message.reply_text(tr['vip_revoked'].format(user_id=target_id), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка revoke_vip: {e}")
        await update.message.reply_text(tr['error'].format(error=str(e)))

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    identify_creator(update.effective_user)
    if not is_creator(user_id):
        await update.message.reply_text(tr['admin_only'])
        return
    all_users = storage.get_all_users()
    users_text = ""
    for user_id, user in list(all_users.items())[:20]:
        vip_badge = "💎" if user.get('vip', False) else ""
        users_text += f"{vip_badge} <code>{user_id}</code> - {user.get('first_name', 'Unknown')}\n"
    if len(all_users) > 20:
        users_text += f"\n<i>... and {len(all_users) - 20} more</i>"
    await update.message.reply_text(tr['users_list'].format(count=len(all_users), users_text=users_text), parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    identify_creator(update.effective_user)
    if not is_creator(user_id):
        await update.message.reply_text(tr['admin_only'])
        return
    if not context.args:
        await update.message.reply_text(tr['broadcast_usage'])
        return
    message_text = ' '.join(context.args)
    success = 0
    failed = 0
    status_msg = await update.message.reply_text(tr['broadcast_start'])
    all_users = storage.get_all_users()
    for target_id in all_users.keys():
        target_lang = all_users[target_id].get('language', 'ru')
        target_tr = translations[target_lang]
        try:
            await context.bot.send_message(chat_id=target_id, text=target_tr['broadcast_start'] + f"\n\n{message_text}", parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Ошибка рассылки пользователю {target_id}: {e}")
            failed += 1
    await status_msg.edit_text(tr['broadcast_done'].format(success=success, failed=failed))

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    identify_creator(update.effective_user)
    if not is_creator(user_id):
        await update.message.reply_text(tr['admin_only'])
        return
    stats = storage.stats
    all_users = storage.get_all_users()
    stats_text = tr['stats_text'].format(
        users_count=len(all_users),
        vip_count=sum(1 for u in all_users.values() if u.get('vip', False)),
        total_messages=stats.get('total_messages', 0),
        total_commands=stats.get('total_commands', 0),
        ai_requests=stats.get('ai_requests', 0)
    )
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    identify_creator(update.effective_user)
    if not is_creator(user_id):
        await update.message.reply_text(tr['admin_only'])
        return
    try:
        backup_data = {'users': storage.get_all_users(), 'stats': storage.stats, 'backup_date': datetime.now().isoformat()}
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        await update.message.reply_document(document=open(backup_filename, 'rb'), caption=tr['backup_caption'].format(date=datetime.now().strftime('%d.%m.%Y %H:%M')))
        os.remove(backup_filename)
    except Exception as e:
        logger.warning(f"Ошибка бэкапа: {e}")
        await update.message.reply_text(tr['error'].format(error=str(e)))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text
    user = storage.get_user(user_id)
    storage.update_user(user_id, {'messages_count': user.get('messages_count', 0) + 1, 'username': update.effective_user.username or '', 'first_name': update.effective_user.first_name or ''})
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    lang = get_lang(user_id)
    mb = menu_buttons[lang]
    if text in [mb['ai_chat'], mb['notes'], mb['weather'], mb['time'], mb['entertainment'], mb['info'], mb['vip_menu'], mb['generation'], mb['admin_panel']]:
        await handle_menu_button(update, context, text, lang)
        return
    
    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()
    
    if text:
        await process_ai_message(update, text, user_id)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button: str, lang: str):
    tr = translations[lang]
    mb = menu_buttons[lang]
    user_id = update.effective_user.id
    if button == mb['ai_chat']:
        await update.message.reply_text(tr['ai_chat_menu'], parse_mode=ParseMode.HTML)
    elif button == mb['notes']:
        keyboard = [[InlineKeyboardButton("➕ Create", callback_data="note_create")], [InlineKeyboardButton("📋 List", callback_data="note_list")]]  # Adapt to lang
        await update.message.reply_text(tr['notes_menu'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == mb['weather']:
        await update.message.reply_text(tr['weather_menu'], parse_mode=ParseMode.HTML)
    elif button == mb['time']:
        await update.message.reply_text(tr['time_menu'], parse_mode=ParseMode.HTML)
    elif button == mb['entertainment']:
        keyboard = [[InlineKeyboardButton("🎲 Dice", callback_data="game_dice"), InlineKeyboardButton("🪙 Coin", callback_data="game_coin")],
                    [InlineKeyboardButton("😄 Joke", callback_data="game_joke"), InlineKeyboardButton("💭 Quote", callback_data="game_quote")],
                    [InlineKeyboardButton("🔬 Fact", callback_data="game_fact")]]  # Adapt to lang
        await update.message.reply_text(tr['entertainment_menu'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == mb['info']:
        await info_command(update, context)
    elif button == mb['vip_menu']:
        if storage.is_vip(user_id):
            keyboard = [[InlineKeyboardButton("⏰ Reminders", callback_data="vip_reminders")], [InlineKeyboardButton("📊 Statistics", callback_data="vip_stats")]]  # Adapt
            await update.message.reply_text(tr['vip_menu'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await vip_command(update, context)
    elif button == mb['admin_panel']:
        if is_creator(user_id):
            keyboard = [[InlineKeyboardButton("👥 Users", callback_data="admin_users")], [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")], [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]]  # Adapt
            await update.message.reply_text(tr['admin_panel'], parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button == mb['generation']:
        if storage.is_vip(user_id):
            await update.message.reply_text(tr['generation_menu'], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(tr['vip_required'].format(feature="Generation"))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = get_lang(user_id)
    tr = translations[lang]
    identify_creator(query.from_user)
    
    if data.startswith("help_"):
        await handle_help_callback(update, context)
        return
    
    if data.startswith("lang_"):
        new_lang = data[5:]
        if new_lang in lang_full:
            storage.update_user(user_id, {'language': new_lang})
            await query.edit_message_text(tr['language_changed'].format(lang=lang_full[new_lang]))
        return
    
    if data == "note_create":
        await query.message.reply_text(tr['note_create'], parse_mode=ParseMode.HTML)
    elif data == "note_list":
        await notes_command(update, context)
    elif data == "game_dice":
        await dice_command(update, context)
    elif data == "game_coin":
        await coin_command(update, context)
    elif data == "game_joke":
        await joke_command(update, context)
    elif data == "game_quote":
        await quote_command(update, context)
    elif data == "game_fact":
        await fact_command(update, context)
    elif data == "vip_reminders":
        await reminders_command(update, context)
    elif data == "vip_stats":
        await profile_command(update, context)
    elif data == "admin_users":
        if is_creator(user_id):
            await users_command(update, context)
    elif data == "admin_stats":
        if is_creator(user_id):
            await stats_command(update, context)
    elif data == "admin_broadcast":
        if is_creator(user_id):
            await query.message.reply_text(tr['broadcast_usage'], parse_mode=ParseMode.HTML)

def signal_handler(signum, frame):
    logger.info("Получен сигнал завершения. Останавливаем бота...")
    scheduler.shutdown()
    raise SystemExit

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация команд с локализованными именами
    for cmd, names in command_names.items():
        for name in set(names.values()):
            handler_func = globals().get(cmd + '_command')
            if handler_func:
                application.add_handler(CommandHandler(name, handler_func))
    
    application.add_handler(CommandHandler("lang", lang_command))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    scheduler.start()
    
    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН!")
    logger.info("🤖 Модель: Gemini 1.5 Flash")
    logger.info("🗄️ БД: " + ("PostgreSQL ✓" if engine else "Local JSON"))
    logger.info("🖼️ Генерация: Pollinations AI")
    logger.info("🔍 Анализ: Gemini Vision")
    logger.info("=" * 50)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
