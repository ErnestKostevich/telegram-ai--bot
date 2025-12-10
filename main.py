#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import random
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import pytz
import requests
import io
from urllib.parse import quote as urlquote
import base64
import mimetypes
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx

# --- ИСПРАВЛЕННЫЕ ИМПОРТЫ SQLAlchemy ---
# 1. Добавлены inspect и sa_text
# 2. declarative_base перенесен в orm
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger, inspect, text as sa_text
from sqlalchemy.orm import sessionmaker, declarative_base
# ---------------------------------------

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

# Настройка Gemini 2.5 Flash (быстрая модель)
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 1,
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

# Модель Gemini 2.5 Flash (быстрая)
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="Ты — AI DISCO BOT, многофункциональный, очень умный и вежливый ассистент, основанный на Gemini 2.5. Всегда отвечай на том языке, на котором к тебе обращаются, используя дружелюбный и вовлекающий тон. Твои ответы должны быть структурированы, по возможности разделены на абзацы и никогда не превышать 4000 символов (ограничение Telegram). Твой создатель — @Ernest_Kostevich. Включай в ответы эмодзи, где это уместно."
)

# Модель для Vision (VIP)
vision_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# --- СТРОКИ ЛОКАЛИЗАЦИИ ---
# Добавляем все тексты для 3-х языков
localization_strings = {
    'ru': {
        'welcome': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "Привет, {first_name}! Я бот на <b>Gemini 2.5 Flash</b>.\n\n"
            "<b>🎯 Возможности:</b>\n"
            "💬 AI-чат с контекстом\n"
            "📝 Заметки и задачи\n"
            "🌍 Погода и время\n"
            "🎲 Развлечения\n"
            "📎 Анализ файлов (VIP)\n"
            "🔍 Анализ изображений (VIP)\n"
            "🖼️ Генерация изображений (VIP)\n\n"
            "<b>⚡ Команды:</b>\n"
            "/help - Все команды\n"
            "/language - Сменить язык\n"
            "/vip - Статус VIP\n\n"
            "<b>👨‍💻 Создатель:</b> @{creator}"
        ),
        'lang_changed': "✅ Язык изменен на Русский 🇷🇺",
        'lang_choose': "Выберите язык:",
        'main_keyboard': {
            'chat': "💬 AI Чат", 'notes': "📝 Заметки", 'weather': "🌍 Погода", 'time': "⏰ Время",
            'games': "🎲 Развлечения", 'info': "ℹ️ Инфо", 'vip_menu': "💎 VIP Меню",
            'admin_panel': "👑 Админ Панель", 'generate': "🖼️ Генерация"
        },
        'help_title': "📚 <b>Выберите раздел справки:</b>\n\nНажмите кнопку ниже для просмотра команд по теме.",
        'help_back': "🔙 Назад",
        'help_sections': {
            'help_basic': "🏠 Основные", 'help_ai': "💬 AI", 'help_memory': "🧠 Память",
            'help_notes': "📝 Заметки", 'help_todo': "📋 Задачи", 'help_utils': "🌍 Утилиты",
            'help_games': "🎲 Развлечения", 'help_vip': "💎 VIP", 'help_admin': "👑 Админ"
        },
        'help_text': {
            'help_basic': (
                "🏠 <b>Основные команды:</b>\n\n"
                "🚀 /start - Запуск бота и приветствие\n"
                "📖 /help - Полный список команд\n"
                "ℹ️ /info - Информация о боте\n"
                "📊 /status - Текущий статус и статистика\n"
                "👤 /profile - Профиль пользователя\n"
                "⏱ /uptime - Время работы бота\n"
                "🗣️ /language - Сменить язык"
            ),
            'help_ai': "💬 <b>AI команды:</b>\n\n🤖 /ai [вопрос] - Задать вопрос AI\n\n🧹 /clear - Очистить контекст чата",
            'help_memory': "🧠 <b>Память:</b>\n\n💾 /memorysave [ключ] [значение] - Сохранить в память\n\n🔍 /memoryget [ключ] - Получить из памяти\n\n📋 /memorylist - Список ключей\n\n🗑 /memorydel [ключ] - Удалить ключ",
            'help_notes': "📝 <b>Заметки:</b>\n\n➕ /note [текст] - Создать заметку\n\n📋 /notes - Список заметок\n\n🗑 /delnote [номер] - Удалить заметку",
            'help_todo': "📋 <b>Задачи:</b>\n\n➕ /todo add [текст] - Добавить задачу\n\n📋 /todo list - Список задач\n\n🗑 /todo del [номер] - Удалить задачу",
            'help_utils': "🌍 <b>Утилиты:</b>\n\n🕐 /time [город] - Текущее время\n\n☀️ /weather [город] - Погода\n\n🌐 /translate [язык] [текст] - Перевод\n\n🧮 /calc [выражение] - Калькулятор\n\n🔑 /password [длина] - Генератор пароля",
            'help_games': "🎲 <b>Развлечения:</b>\n\n🎲 /random [min] [max] - Случайное число\n\n🎯 /dice - Бросок кубика\n\n🪙 /coin - Монетка\n\n😄 /joke - Шутка\n\n💭 /quote - Цитата\n\n🔬 /fact - Факт",
            'help_vip': "💎 <b>VIP команды:</b>\n\n👑 /vip - Статус VIP\n\n🖼️ /generate [описание] - Генерация изображения\n\n⏰ /remind [минуты] [текст] - Напоминание\n\n📋 /reminders - Список напоминаний\n\n📎 Отправь файл - Анализ (VIP)\n\n📸 Отправь фото - Анализ (VIP)",
            'help_admin': (
                "👑 <b>Команды Создателя:</b>\n\n"
                "🎁 /grant_vip [id/@username] [срок] - Выдать VIP (week/month/year/forever)\n"
                "❌ /revoke_vip [id/@username] - Забрать VIP\n"
                "👥 /users - Список пользователей\n"
                "📢 /broadcast [текст] - Рассылка\n"
                "📈 /stats - Полная статистика\n"
                "💾 /backup - Резервная копия"
            )
        },
        'menu': {
            'chat': "🤖 <b>AI Чат</b>\n\nПросто пиши - я отвечу!\n/clear - очистить контекст",
            'notes': "📝 <b>Заметки</b>", 'notes_create': "➕ Создать", 'notes_list': "📋 Список",
            'weather': "🌍 <b>Погода</b>\n\n/weather [город]\nПример: /weather London",
            'time': "⏰ <b>Время</b>\n\n/time [город]\nПример: /time Tokyo",
            'games': "🎲 <b>Развлечения</b>", 'games_dice': "🎲 Кубик", 'games_coin': "🪙 Монета",
            'games_joke': "😄 Шутка", 'games_quote': "💭 Цитата", 'games_fact': "🔬 Факт",
            'vip': "💎 <b>VIP Меню</b>", 'vip_reminders': "⏰ Напоминания", 'vip_stats': "📊 Статистика",
            'admin': "👑 <b>Админ Панель</b>", 'admin_users': "👥 Пользователи", 'admin_stats': "📊 Статистика",
            'admin_broadcast': "📢 Рассылка",
            'generate': "🖼️ <b>Генерация (VIP)</b>\n\n/generate [описание]\n\nПримеры:\n• /generate закат\n• /generate город\n\n💡 Gemini Imagen"
        },
        'info': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "<b>Версия:</b> 3.1 (Multi-Language)\n"
            "<b>AI:</b> Gemini 2.5 Flash\n"
            "<b>Создатель:</b> @Ernest_Kostevich\n\n"
            "<b>⚡ Особенности:</b>\n"
            "• Быстрый AI-чат\n"
            "• PostgreSQL\n"
            "• VIP функции\n"
            "• Анализ файлов/фото (VIP)\n"
            "• Генерация изображений (Imagen 3)\n\n"
            "<b>💬 Поддержка:</b> @Ernest_Kostevich"
        ),
        'status': (
            "📊 <b>СТАТУС</b>\n\n"
            "👥 Пользователи: {users}\n"
            "💎 VIP: {vips}\n\n"
            "<b>📈 Активность:</b>\n"
            "• Сообщений: {msg_count}\n"
            "• Команд: {cmd_count}\n"
            "• AI запросов: {ai_count}\n\n"
            "<b>⏱ Работает:</b> {days}д {hours}ч\n\n"
            "<b>✅ Статус:</b> Онлайн\n"
            "<b>🤖 AI:</b> Gemini 2.5 ✓\n"
            "<b>🗄️ БД:</b> {db_status}"
        ),
        'profile': (
            "👤 <b>{first_name}</b>\n"
            "🆔 <code>{user_id}</code>\n"
            "{username_line}\n"
            "📅 {registered_date}\n"
            "📊 Сообщений: {msg_count}\n"
            "🎯 Команд: {cmd_count}\n"
            "📝 Заметок: {notes_count}"
        ),
        'profile_vip': "\n💎 VIP до: {date}",
        'profile_vip_forever': "\n💎 VIP: Навсегда ♾️",
        'uptime': (
            "⏱ <b>ВРЕМЯ РАБОТИ</b>\n\n"
            "🕐 Запущен: {start_time}\n"
            "⏰ Работает: {days}д {hours}ч {minutes}м\n\n"
            "✅ Онлайн"
        ),
        'vip_status_active': "💎 <b>VIP СТАТУС</b>\n\n✅ Активен!\n\n",
        'vip_status_until': "⏰ До: {date}\n\n",
        'vip_status_forever': "⏰ Навсегда ♾️\n\n",
        'vip_status_bonus': "<b>🎁 Преимущества:</b>\n• ⏰ Напоминания\n• 🖼️ Генерация изображений\n• 🔍 Анализ изображений\n• 📎 Анализ документов",
        'vip_status_inactive': "💎 <b>VIP СТАТУС</b>\n\n❌ Нет VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'vip_only': "💎 Эта функция доступна только для VIP.\n\nСвяжитесь с @Ernest_Kostevich",
        'admin_only': "❌ Только для создателя.",
        'gen_prompt_needed': "❓ /generate [описание]\n\nПример: /generate закат над океаном",
        'gen_in_progress': "🎨 Генерирую с Imagen 3...",
        'gen_caption': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Ошибка генерации изображения",
        'gen_error_api': "❌ Ошибка API: {error}",
        'ai_prompt_needed': "❓ /ai [вопрос]",
        'ai_typing': "typing",
        'ai_error': "😔 Ошибка AI, попробуйте снова.",
        'clear_context': "🧹 Контекст чата очищен!",
        'note_prompt_needed': "❓ /note [текст]",
        'note_saved': "✅ Заметка #{num} сохранена!\n\n📝 {text}",
        'notes_empty': "📭 У вас нет заметок.",
        'notes_list_title': "📝 <b>Заметки ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "❓ /delnote [номер]",
        'delnote_success': "✅ Заметка #{num} удалена:\n\n📝 {text}",
        'delnote_not_found': "❌ Заметка #{num} не найдена.",
        'delnote_invalid_num': "❌ Укажите корректный номер.",
        'todo_prompt_needed': "❓ /todo add [текст] | list | del [номер]",
        'todo_add_prompt_needed': "❓ /todo add [текст]",
        'todo_saved': "✅ Задача #{num} добавлена!\n\n📋 {text}",
        'todo_empty': "📭 У вас нет задач.",
        'todo_list_title': "📋 <b>Задачи ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "❓ /todo del [номер]",
        'todo_del_success': "✅ Задача #{num} удалена:\n\n📋 {text}",
        'todo_del_not_found': "❌ Задача #{num} не найдена.",
        'todo_del_invalid_num': "❌ Укажите корректный номер.",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 Время: {time}\n📅 Дата: {date}\n🌍 Пояс: {tz}",
        'time_city_not_found': "❌ Город '{city}' не найден или ошибка API.",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 Температура: {temp}°C\n🤔 Ощущается: {feels}°C\n☁️ {desc}\n💧 Влажность: {humidity}%\n💨 Ветер: {wind} км/ч",
        'weather_city_not_found': "❌ Город '{city}' не найден.",
        'weather_error': "❌ Ошибка получения погоды.",
        'translate_prompt_needed': "❓ /translate [язык] [текст]\n\nПример: /translate en Привет",
        'translate_error': "❌ Ошибка перевода.",
        'calc_prompt_needed': "❓ /calc [выражение]\n\nПример: /calc 2+2*5",
        'calc_result': "🧮 <b>Результат:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "❌ Ошибка вычисления. Используйте только цифры и операторы +, -, *, /.",
        'password_length_error': "❌ Длина пароля должна быть от 8 до 50.",
        'password_result': "🔑 <b>Ваш новый пароль:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "❌ Укажите корректную длину (число).",
        'random_result': "🎲 Случайное число от {min} до {max}:\n\n<b>{result}</b>",
        'random_invalid_range': "❌ Укажите корректный диапазон (числа).",
        'dice_result': "🎲 {emoji} Выпало: <b>{result}</b>",
        'coin_result': "🪙 {emoji} Выпало: <b>{result}</b>",
        'coin_heads': "Орёл", 'coin_tails': "Решка",
        'joke_title': "😄 <b>Шутка:</b>\n\n",
        'quote_title': "💭 <b>Цитата:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "🔬 <b>Факт:</b>\n\n",
        'remind_prompt_needed': "❓ /remind [минуты] [текст]",
        'remind_success': "⏰ Напоминание успешно создано!\n\n📝 {text}\n🕐 Через {minutes} минут",
        'remind_invalid_time': "❌ Укажите корректное время в минутах.",
        'reminders_empty': "📭 У вас нет активных напоминаний.",
        'reminders_list_title': "⏰ <b>Активные напоминания ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\n📝 {text}\n\n",
        'reminder_alert': "⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
        'grant_vip_prompt': "❓ /grant_vip [id/@username] [срок]\n\nСроки: week, month, year, forever",
        'grant_vip_user_not_found': "❌ Пользователь '{id}' не найден.",
        'grant_vip_invalid_duration': "❌ Неверный срок. Доступно: week, month, year, forever",
        'grant_vip_success': "✅ VIP статус выдан!\n\n🆔 <code>{id}</code>\n⏰ {duration_text}",
        'grant_vip_dm': "🎉 Поздравляем! Вам выдан VIP статус {duration_text}!",
        'duration_until': "до {date}",
        'duration_forever': "навсегда",
        'revoke_vip_prompt': "❓ /revoke_vip [id/@username]",
        'revoke_vip_success': "✅ VIP статус отозван у пользователя <code>{id}</code>.",
        'users_list_title': "👥 <b>ПОЛЬЗОВАТЕЛИ ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... и ещё {count}</i>",
        'broadcast_prompt': "❓ /broadcast [текст сообщения]",
        'broadcast_started': "📤 Начинаю рассылку...",
        'broadcast_finished': "✅ Рассылка завершена!\n\n✅ Успешно: {success}\n❌ Ошибок: {failed}",
        'broadcast_dm': "📢 <b>Сообщение от создателя:</b>\n\n{text}",
        'stats_admin_title': (
            "📊 <b>ПОЛНАЯ СТАТИСТИКА</b>\n\n"
            "<b>👥 Пользователи:</b> {users}\n"
            "<b>💎 VIP:</b> {vips}\n\n"
            "<b>📈 Активность:</b>\n"
            "• Сообщений: {msg_count}\n"
            "• Команд: {cmd_count}\n"
            "• AI запросов: {ai_count}"
        ),
        'backup_success': "✅ Создана резервная копия\n\n📅 {date}",
        'backup_error': "❌ Ошибка создания бэкапа: {error}",
        'file_received': "📥 Загружаю файл...",
        'file_analyzing': "📄 <b>Файл:</b> {filename}\n\n🤖 <b>Анализ:</b>\n\n{text}",
        'file_error': "❌ Ошибка обработки документа: {error}",
        'photo_analyzing': "🔍 Анализирую изображение...",
        'photo_result': "📸 <b>Анализ (Gemini Vision):</b>\n\n{text}\n\n💎 VIP",
        'photo_error': "❌ Ошибка обработки фото: {error}",
        'voice_transcribing': "🎙️ Распознаю голосовое сообщение...",
        'voice_result': "📝 <b>Транскрипция:</b>\n\n{text}",
        'voice_error': "❌ Ошибка обработки голосового сообщения: {error}",
        'error_generic': "❌ Произошла непредвиденная ошибка: {error}",
        'section_not_found': "❌ Раздел не найден."
    },
    'en': {
        'welcome': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "Hi, {first_name}! I'm a bot powered by <b>Gemini 2.5 Flash</b>.\n\n"
            "<b>🎯 Features:</b>\n"
            "💬 AI chat with context\n"
            "📝 Notes and To-Dos\n"
            "🌍 Weather and Time\n"
            "🎲 Entertainment\n"
            "📎 File Analysis (VIP)\n"
            "🔍 Image Analysis (VIP)\n"
            "🖼️ Image Generation (VIP)\n\n"
            "<b>⚡ Commands:</b>\n"
            "/help - All commands\n"
            "/language - Change language\n"
            "/vip - VIP Status\n\n"
            "<b>👨‍💻 Creator:</b> @{creator}"
        ),
        'lang_changed': "✅ Language changed to English 🇬🇧",
        'lang_choose': "Please select a language:",
        'main_keyboard': {
            'chat': "💬 AI Chat", 'notes': "📝 Notes", 'weather': "🌍 Weather", 'time': "⏰ Time",
            'games': "🎲 Games", 'info': "ℹ️ Info", 'vip_menu': "💎 VIP Menu",
            'admin_panel': "👑 Admin Panel", 'generate': "🖼️ Generate"
        },
        'help_title': "📚 <b>Choose a help section:</b>\n\nPress a button below to see commands for that topic.",
        'help_back': "🔙 Back",
        'help_sections': {
            'help_basic': "🏠 Basic", 'help_ai': "💬 AI", 'help_memory': "🧠 Memory",
            'help_notes': "📝 Notes", 'help_todo': "📋 To-Do", 'help_utils': "🌍 Utilities",
            'help_games': "🎲 Games", 'help_vip': "💎 VIP", 'help_admin': "👑 Admin"
        },
        'help_text': {
            'help_basic': (
                "🏠 <b>Basic Commands:</b>\n\n"
                "🚀 /start - Start the bot\n"
                "📖 /help - Full command list\n"
                "ℹ️ /info - Bot information\n"
                "📊 /status - Current status and stats\n"
                "👤 /profile - User profile\n"
                "⏱ /uptime - Bot uptime\n"
                "🗣️ /language - Change language"
            ),
            'help_ai': "💬 <b>AI Commands:</b>\n\n🤖 /ai [question] - Ask AI\n\n🧹 /clear - Clear chat context",
            'help_memory': "🧠 <b>Memory:</b>\n\n💾 /memorysave [key] [value] - Save to memory\n\n🔍 /memoryget [key] - Get from memory\n\n📋 /memorylist - List all keys\n\n🗑 /memorydel [key] - Delete key",
            'help_notes': "📝 <b>Notes:</b>\n\n➕ /note [text] - Create a note\n\n📋 /notes - List notes\n\n🗑 /delnote [number] - Delete a note",
            'help_todo': "📋 <b>To-Do:</b>\n\n➕ /todo add [text] - Add a task\n\n📋 /todo list - List tasks\n\n🗑 /todo del [number] - Delete a task",
            'help_utils': "🌍 <b>Utilities:</b>\n\n🕐 /time [city] - Current time\n\n☀️ /weather [city] - Weather forecast\n\n🌐 /translate [lang] [text] - Translate\n\n🧮 /calc [expression] - Calculator\n\n🔑 /password [length] - Password generator",
            'help_games': "🎲 <b>Games:</b>\n\n🎲 /random [min] [max] - Random number\n\n🎯 /dice - Roll a die\n\n🪙 /coin - Flip a coin\n\n😄 /joke - Random joke\n\n💭 /quote - Motivational quote\n\n🔬 /fact - Interesting fact",
            'help_vip': "💎 <b>VIP Commands:</b>\n\n👑 /vip - VIP status\n\n🖼️ /generate [prompt] - Generate image\n\n⏰ /remind [minutes] [text] - Set reminder\n\n📋 /reminders - List reminders\n\n📎 Send a file - Analyze (VIP)\n\n📸 Send a photo - Analyze (VIP)",
            'help_admin': (
                "👑 <b>Creator Commands:</b>\n\n"
                "🎁 /grant_vip [id/@username] [duration] - Grant VIP (week/month/year/forever)\n"
                "❌ /revoke_vip [id/@username] - Revoke VIP\n"
                "👥 /users - List users\n"
                "📢 /broadcast [text] - Broadcast message\n"
                "📈 /stats - Full statistics\n"
                "💾 /backup - Create backup"
            )
        },
        'menu': {
            'chat': "🤖 <b>AI Chat</b>\n\nJust type - I'll answer!\n/clear - clear context",
            'notes': "📝 <b>Notes</b>", 'notes_create': "➕ Create", 'notes_list': "📋 List",
            'weather': "🌍 <b>Weather</b>\n\n/weather [city]\nExample: /weather London",
            'time': "⏰ <b>Time</b>\n\n/time [city]\nExample: /time Tokyo",
            'games': "🎲 <b>Games</b>", 'games_dice': "🎲 Dice", 'games_coin': "🪙 Coin",
            'games_joke': "😄 Joke", 'games_quote': "💭 Quote", 'games_fact': "🔬 Fact",
            'vip': "💎 <b>VIP Menu</b>", 'vip_reminders': "⏰ Reminders", 'vip_stats': "📊 Stats",
            'admin': "👑 <b>Admin Panel</b>", 'admin_users': "👥 Users", 'admin_stats': "📊 Stats",
            'admin_broadcast': "📢 Broadcast",
            'generate': "🖼️ <b>Generation (VIP)</b>\n\n/generate [prompt]\n\nExamples:\n• /generate sunset\n• /generate city\n\n💡 Gemini Imagen"
        },
        'info': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "<b>Version:</b> 3.1 (Multi-Language)\n"
            "<b>AI:</b> Gemini 2.5 Flash\n"
            "<b>Creator:</b> @Ernest_Kostevich\n\n"
            "<b>⚡ Features:</b>\n"
            "• Fast AI Chat\n"
            "• PostgreSQL\n"
            "• VIP Features\n"
            "• File/Photo Analysis (VIP)\n"
            "• Image Generation (Imagen 3)\n\n"
            "<b>💬 Support:</b> @Ernest_Kostevich"
        ),
        'status': (
            "📊 <b>STATUS</b>\n\n"
            "👥 Users: {users}\n"
            "💎 VIPs: {vips}\n\n"
            "<b>📈 Activity:</b>\n"
            "• Messages: {msg_count}\n"
            "• Commands: {cmd_count}\n"
            "• AI Requests: {ai_count}\n\n"
            "<b>⏱ Uptime:</b> {days}d {hours}h\n\n"
            "<b>✅ Status:</b> Online\n"
            "<b>🤖 AI:</b> Gemini 2.5 ✓\n"
            "<b>🗄️ DB:</b> {db_status}"
        ),
        'profile': (
            "👤 <b>{first_name}</b>\n"
            "🆔 <code>{user_id}</code>\n"
            "{username_line}\n"
            "📅 {registered_date}\n"
            "📊 Messages: {msg_count}\n"
            "🎯 Commands: {cmd_count}\n"
            "📝 Notes: {notes_count}"
        ),
        'profile_vip': "\n💎 VIP until: {date}",
        'profile_vip_forever': "\n💎 VIP: Forever ♾️",
        'uptime': (
            "⏱ <b>UPTIME</b>\n\n"
            "🕐 Started: {start_time}\n"
            "⏰ Running: {days}d {hours}h {minutes}m\n\n"
            "✅ Online"
        ),
        'vip_status_active': "💎 <b>VIP STATUS</b>\n\n✅ Active!\n\n",
        'vip_status_until': "⏰ Until: {date}\n\n",
        'vip_status_forever': "⏰ Forever ♾️\n\n",
        'vip_status_bonus': "<b>🎁 Perks:</b>\n• ⏰ Reminders\n• 🖼️ Image Generation\n• 🔍 Image Analysis\n• 📎 Document Analysis",
        'vip_status_inactive': "💎 <b>VIP STATUS</b>\n\n❌ No VIP.\n\nContact @Ernest_Kostevich",
        'vip_only': "💎 This feature is for VIP users only.\n\nContact @Ernest_Kostevich",
        'admin_only': "❌ For creator only.",
        'gen_prompt_needed': "❓ /generate [prompt]\n\nExample: /generate sunset over the ocean",
        'gen_in_progress': "🎨 Generating with Imagen 3...",
        'gen_caption': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Image generation failed",
        'gen_error_api': "❌ API Error: {error}",
        'ai_prompt_needed': "❓ /ai [question]",
        'ai_typing': "typing",
        'ai_error': "😔 AI Error, please try again.",
        'clear_context': "🧹 Chat context cleared!",
        'note_prompt_needed': "❓ /note [text]",
        'note_saved': "✅ Note #{num} saved!\n\n📝 {text}",
        'notes_empty': "📭 You have no notes.",
        'notes_list_title': "📝 <b>Notes ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "❓ /delnote [number]",
        'delnote_success': "✅ Note #{num} deleted:\n\n📝 {text}",
        'delnote_not_found': "❌ Note #{num} not found.",
        'delnote_invalid_num': "❌ Please specify a valid number.",
        'todo_prompt_needed': "❓ /todo add [text] | list | del [number]",
        'todo_add_prompt_needed': "❓ /todo add [text]",
        'todo_saved': "✅ Task #{num} added!\n\n📋 {text}",
        'todo_empty': "📭 You have no tasks.",
        'todo_list_title': "📋 <b>Tasks ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "❓ /todo del [number]",
        'todo_del_success': "✅ Task #{num} deleted:\n\n📋 {text}",
        'todo_del_not_found': "❌ Task #{num} not found.",
        'todo_del_invalid_num': "❌ Please specify a valid number.",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 Time: {time}\n📅 Date: {date}\n🌍 Zone: {tz}",
        'time_city_not_found': "❌ City '{city}' not found or API error.",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 Temp: {temp}°C\n🤔 Feels: {feels}°C\n☁️ {desc}\n💧 Humidity: {humidity}%\n💨 Wind: {wind} km/h",
        'weather_city_not_found': "❌ City '{city}' not found.",
        'weather_error': "❌ Error fetching weather.",
        'translate_prompt_needed': "❓ /translate [lang] [text]\n\nExample: /translate en Hello",
        'translate_error': "❌ Translation error.",
        'calc_prompt_needed': "❓ /calc [expression]\n\nExample: /calc 2+2*5",
        'calc_result': "🧮 <b>Result:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "❌ Calculation error. Use only numbers and operators +, -, *, /.",
        'password_length_error': "❌ Password length must be 8-50.",
        'password_result': "🔑 <b>Your new password:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "❌ Please specify a valid length (number).",
        'random_result': "🎲 Random number from {min} to {max}:\n\n<b>{result}</b>",
        'random_invalid_range': "❌ Please specify a valid range (numbers).",
        'dice_result': "🎲 {emoji} You rolled a <b>{result}</b>",
        'coin_result': "🪙 {emoji} It's <b>{result}</b>",
        'coin_heads': "Heads", 'coin_tails': "Tails",
        'joke_title': "😄 <b>Joke:</b>\n\n",
        'quote_title': "💭 <b>Quote:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "🔬 <b>Fact:</b>\n\n",
        'remind_prompt_needed': "❓ /remind [minutes] [text]",
        'remind_success': "⏰ Reminder set successfully!\n\n📝 {text}\n🕐 In {minutes} minutes",
        'remind_invalid_time': "❌ Please specify a valid time in minutes.",
        'reminders_empty': "📭 You have no active reminders.",
        'reminders_list_title': "⏰ <b>Active Reminders ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\n📝 {text}\n\n",
        'reminder_alert': "⏰ <b>REMINDER</b>\n\n📝 {text}",
        'grant_vip_prompt': "❓ /grant_vip [id/@username] [duration]\n\nDurations: week, month, year, forever",
        'grant_vip_user_not_found': "❌ User '{id}' not found.",
        'grant_vip_invalid_duration': "❌ Invalid duration. Available: week, month, year, forever",
        'grant_vip_success': "✅ VIP status granted!\n\n🆔 <code>{id}</code>\n⏰ {duration_text}",
        'grant_vip_dm': "🎉 Congratulations! You have been granted VIP status {duration_text}!",
        'duration_until': "until {date}",
        'duration_forever': "forever",
        'revoke_vip_prompt': "❓ /revoke_vip [id/@username]",
        'revoke_vip_success': "✅ VIP status revoked for user <code>{id}</code>.",
        'users_list_title': "👥 <b>USERS ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... and {count} more</i>",
        'broadcast_prompt': "❓ /broadcast [message text]",
        'broadcast_started': "📤 Starting broadcast...",
        'broadcast_finished': "✅ Broadcast finished!\n\n✅ Success: {success}\n❌ Failed: {failed}",
        'broadcast_dm': "📢 <b>Message from the creator:</b>\n\n{text}",
        'stats_admin_title': (
            "📊 <b>FULL STATISTICS</b>\n\n"
            "<b>👥 Users:</b> {users}\n"
            "<b>💎 VIPs:</b> {vips}\n\n"
            "<b>📈 Activity:</b>\n"
            "• Messages: {msg_count}\n"
            "• Commands: {cmd_count}\n"
            "• AI Requests: {ai_count}"
        ),
        'backup_success': "✅ Backup created\n\n📅 {date}",
        'backup_error': "❌ Error creating backup: {error}",
        'file_received': "📥 Receiving file...",
        'file_analyzing': "📄 <b>File:</b> {filename}\n\n🤖 <b>Analysis:</b>\n\n{text}",
        'file_error': "❌ Error processing document: {error}",
        'photo_analyzing': "🔍 Analyzing image...",
        'photo_result': "📸 <b>Analysis (Gemini Vision):</b>\n\n{text}\n\n💎 VIP",
        'photo_error': "❌ Error processing photo: {error}",
        'voice_transcribing': "🎙️ Transcribing voice message...",
        'voice_result': "📝 <b>Transcription:</b>\n\n{text}",
        'voice_error': "❌ Error processing voice message: {error}",
        'error_generic': "❌ An unexpected error occurred: {error}",
        'section_not_found': "❌ Section not found."
    },
    'it': {
        'welcome': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "Ciao, {first_name}! Sono un bot basato su <b>Gemini 2.5 Flash</b>.\n\n"
            "<b>🎯 Funzionalità:</b>\n"
            "💬 Chat AI con contesto\n"
            "📝 Note e Impegni\n"
            "🌍 Meteo e Ora\n"
            "🎲 Intrattenimento\n"
            "📎 Analisi File (VIP)\n"
            "🔍 Analisi Immagini (VIP)\n"
            "🖼️ Generazione Immagini (VIP)\n\n"
            "<b>⚡ Comandi:</b>\n"
            "/help - Tutti i comandi\n"
            "/language - Cambia lingua\n"
            "/vip - Stato VIP\n\n"
            "<b>👨‍💻 Creatore:</b> @{creator}"
        ),
        'lang_changed': "✅ Lingua cambiata in Italiano 🇮🇹",
        'lang_choose': "Seleziona una lingua:",
        'main_keyboard': {
            'chat': "💬 Chat AI", 'notes': "📝 Note", 'weather': "🌍 Meteo", 'time': "⏰ Ora",
            'games': "🎲 Giochi", 'info': "ℹ️ Info", 'vip_menu': "💎 Menu VIP",
            'admin_panel': "👑 Pannello Admin", 'generate': "🖼️ Genera"
        },
        'help_title': "📚 <b>Scegli una sezione di aiuto:</b>\n\nPremi un pulsante qui sotto per vedere i comandi.",
        'help_back': "🔙 Indietro",
        'help_sections': {
            'help_basic': "🏠 Base", 'help_ai': "💬 AI", 'help_memory': "🧠 Memoria",
            'help_notes': "📝 Note", 'help_todo': "📋 Impegni", 'help_utils': "🌍 Utilità",
            'help_games': "🎲 Giochi", 'help_vip': "💎 VIP", 'help_admin': "👑 Admin"
        },
        'help_text': {
            'help_basic': (
                "🏠 <b>Comandi di Base:</b>\n\n"
                "🚀 /start - Avvia il bot\n"
                "📖 /help - Lista completa dei comandi\n"
                "ℹ️ /info - Informazioni sul bot\n"
                "📊 /status - Stato attuale e statistiche\n"
                "👤 /profile - Profilo utente\n"
                "⏱ /uptime - Tempo di attività del bot\n"
                "🗣️ /language - Cambia lingua"
            ),
            'help_ai': "💬 <b>Comandi AI:</b>\n\n🤖 /ai [domanda] - Chiedi all'AI\n\n🧹 /clear - Pulisci contesto chat",
            'help_memory': "🧠 <b>Memoria:</b>\n\n💾 /memorysave [chiave] [valore] - Salva in memoria\n\n🔍 /memoryget [chiave] - Ottieni dalla memoria\n\n📋 /memorylist - Lista chiavi\n\n🗑 /memorydel [chiave] - Elimina chiave",
            'help_notes': "📝 <b>Note:</b>\n\n➕ /note [testo] - Crea una nota\n\n📋 /notes - Lista note\n\n🗑 /delnote [numero] - Elimina una nota",
            'help_todo': "📋 <b>Impegni:</b>\n\n➕ /todo add [testo] - Aggiungi impegno\n\n📋 /todo list - Lista impegni\n\n🗑 /todo del [numero] - Elimina impegno",
            'help_utils': "🌍 <b>Utilità:</b>\n\n🕐 /time [città] - Ora attuale\n\n☀️ /weather [città] - Previsioni meteo\n\n🌐 /translate [lingua] [testo] - Traduci\n\n🧮 /calc [espressione] - Calcolatrice\n\n🔑 /password [lunghezza] - Generatore password",
            'help_games': "🎲 <b>Giochi:</b>\n\n🎲 /random [min] [max] - Numero casuale\n\n🎯 /dice - Lancia un dado\n\n🪙 /coin - Lancia una moneta\n\n😄 /joke - Battuta\n\n💭 /quote - Citazione\n\n🔬 /fact - Fatto interessante",
            'help_vip': "💎 <b>Comandi VIP:</b>\n\n👑 /vip - Stato VIP\n\n🖼️ /generate [prompt] - Genera immagine\n\n⏰ /remind [minuti] [testo] - Imposta promemoria\n\n📋 /reminders - Lista promemoria\n\n📎 Invia un file - Analizza (VIP)\n\n📸 Invia una foto - Analizza (VIP)",
            'help_admin': (
                "👑 <b>Comandi Creatore:</b>\n\n"
                "🎁 /grant_vip [id/@username] [durata] - Concedi VIP (week/month/year/forever)\n"
                "❌ /revoke_vip [id/@username] - Revoca VIP\n"
                "👥 /users - Lista utenti\n"
                "📢 /broadcast [testo] - Messaggio broadcast\n"
                "📈 /stats - Statistiche complete\n"
                "💾 /backup - Crea backup"
            )
        },
        'menu': {
            'chat': "🤖 <b>Chat AI</b>\n\nScrivi e basta - risponderò!\n/clear - pulisci contesto",
            'notes': "📝 <b>Note</b>", 'notes_create': "➕ Crea", 'notes_list': "📋 Lista",
            'weather': "🌍 <b>Meteo</b>\n\n/weather [città]\nEsempio: /weather Rome",
            'time': "⏰ <b>Ora</b>\n\n/time [città]\nEsempio: /time Tokyo",
            'games': "🎲 <b>Giochi</b>", 'games_dice': "🎲 Dado", 'games_coin': "🪙 Moneta",
            'games_joke': "😄 Battuta", 'games_quote': "💭 Citazione", 'games_fact': "🔬 Fatto",
            'vip': "💎 <b>Menu VIP</b>", 'vip_reminders': "⏰ Promemoria", 'vip_stats': "📊 Statistiche",
            'admin': "👑 <b>Pannello Admin</b>", 'admin_users': "👥 Utenti", 'admin_stats': "📊 Statistiche",
            'admin_broadcast': "📢 Broadcast",
            'generate': "🖼️ <b>Generazione (VIP)</b>\n\n/generate [prompt]\n\nEsempi:\n• /generate tramonto\n• /generate città\n\n💡 Gemini Imagen"
        },
        'info': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "<b>Versione:</b> 3.1 (Multi-Language)\n"
            "<b>AI:</b> Gemini 2.5 Flash\n"
            "<b>Creatore:</b> @Ernest_Kostevich\n\n"
            "<b>⚡ Caratteristiche:</b>\n"
            "• Chat AI Veloce\n"
            "• PostgreSQL\n"
            "• Funzioni VIP\n"
            "• Analisi File/Foto (VIP)\n"
            "• Generazione Immagini (Imagen 3)\n\n"
            "<b>💬 Supporto:</b> @Ernest_Kostevich"
        ),
        'status': (
            "📊 <b>STATO</b>\n\n"
            "👥 Utenti: {users}\n"
            "💎 VIP: {vips}\n\n"
            "<b>📈 Attività:</b>\n"
            "• Messaggi: {msg_count}\n"
            "• Comandi: {cmd_count}\n"
            "• Richieste AI: {ai_count}\n\n"
            "<b>⏱ Uptime:</b> {days}g {hours}o\n\n"
            "<b>✅ Stato:</b> Online\n"
            "<b>🤖 AI:</b> Gemini 2.5 ✓\n"
            "<b>🗄️ DB:</b> {db_status}"
        ),
        'profile': (
            "👤 <b>{first_name}</b>\n"
            "🆔 <code>{user_id}</code>\n"
            "{username_line}\n"
            "📅 {registered_date}\n"
            "📊 Messaggi: {msg_count}\n"
            "🎯 Comandi: {cmd_count}\n"
            "📝 Note: {notes_count}"
        ),
        'profile_vip': "\n💎 VIP fino al: {date}",
        'profile_vip_forever': "\n💎 VIP: Illimitato ♾️",
        'uptime': (
            "⏱ <b>TEMPO DI ATTIVITÀ</b>\n\n"
            "🕐 Avviato: {start_time}\n"
            "⏰ In esecuzione: {days}g {hours}o {minutes}m\n\n"
            "✅ Online"
        ),
        'vip_status_active': "💎 <b>STATO VIP</b>\n\n✅ Attivo!\n\n",
        'vip_status_until': "⏰ Fino al: {date}\n\n",
        'vip_status_forever': "⏰ Illimitato ♾️\n\n",
        'vip_status_bonus': "<b>🎁 Vantaggi:</b>\n• ⏰ Promemoria\n• 🖼️ Generazione Immagini\n• 🔍 Analisi Immagini\n• 📎 Analisi Documenti",
        'vip_status_inactive': "💎 <b>STATO VIP</b>\n\n❌ VIP non attivo.\n\nContatta @Ernest_Kostevich",
        'vip_only': "💎 Questa funzione è solo per utenti VIP.\n\nContatta @Ernest_Kostevich",
        'admin_only': "❌ Solo per il creatore.",
        'gen_prompt_needed': "❓ /generate [prompt]\n\nEsempio: /generate tramonto sull'oceano",
        'gen_in_progress': "🎨 Sto generando con Imagen 3...",
        'gen_caption': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Errore generazione immagine",
        'gen_error_api': "❌ Errore API: {error}",
        'ai_prompt_needed': "❓ /ai [domanda]",
        'ai_typing': "typing",
        'ai_error': "😔 Errore AI, riprova.",
        'clear_context': "🧹 Contesto chat pulito!",
        'note_prompt_needed': "❓ /note [testo]",
        'note_saved': "✅ Nota #{num} salvata!\n\n📝 {text}",
        'notes_empty': "📭 Non hai note.",
        'notes_list_title': "📝 <b>Note ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "❓ /delnote [numero]",
        'delnote_success': "✅ Nota #{num} eliminata:\n\n📝 {text}",
        'delnote_not_found': "❌ Nota #{num} non trovata.",
        'delnote_invalid_num': "❌ Specifica un numero valido.",
        'todo_prompt_needed': "❓ /todo add [testo] | list | del [numero]",
        'todo_add_prompt_needed': "❓ /todo add [testo]",
        'todo_saved': "✅ Impegno #{num} aggiunto!\n\n📋 {text}",
        'todo_empty': "📭 Non hai impegni.",
        'todo_list_title': "📋 <b>Impegni ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "❓ /todo del [numero]",
        'todo_del_success': "✅ Impegno #{num} eliminato:\n\n📋 {text}",
        'todo_del_not_found': "❌ Impegno #{num} non trovato.",
        'todo_del_invalid_num': "❌ Specifica un numero valido.",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 Ora: {time}\n📅 Data: {date}\n🌍 Fuso: {tz}",
        'time_city_not_found': "❌ Città '{city}' non trovata o errore API.",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 Temp: {temp}°C\n🤔 Percepita: {feels}°C\n☁️ {desc}\n💧 Umidità: {humidity}%\n💨 Vento: {wind} km/h",
        'weather_city_not_found': "❌ Città '{city}' non trovata.",
        'weather_error': "❌ Errore nel recupero del meteo.",
        'translate_prompt_needed': "❓ /translate [lingua] [testo]\n\nEsempio: /translate it Ciao",
        'translate_error': "❌ Errore di traduzione.",
        'calc_prompt_needed': "❓ /calc [espressione]\n\nEsempio: /calc 2+2*5",
        'calc_result': "🧮 <b>Risultato:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "❌ Errore di calcolo. Usa solo numeri e operatori +, -, *, /.",
        'password_length_error': "❌ Lunghezza password 8-50.",
        'password_result': "🔑 <b>La tua nuova password:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "❌ Specifica una lunghezza valida (numero).",
        'random_result': "🎲 Numero casuale da {min} a {max}:\n\n<b>{result}</b>",
        'random_invalid_range': "❌ Specifica un intervallo valido (numeri).",
        'dice_result': "🎲 {emoji} È uscito: <b>{result}</b>",
        'coin_result': "🪙 {emoji} È uscito: <b>{result}</b>",
        'coin_heads': "Testa", 'coin_tails': "Croce",
        'joke_title': "😄 <b>Battuta:</b>\n\n",
        'quote_title': "💭 <b>Citazione:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "🔬 <b>Fatto:</b>\n\n",
        'remind_prompt_needed': "❓ /remind [minuti] [testo]",
        'remind_success': "⏰ Promemoria impostato!\n\n📝 {text}\n🕐 Tra {minutes} minuti",
        'remind_invalid_time': "❌ Specifica un tempo valido in minuti.",
        'reminders_empty': "📭 Non hai promemoria attivi.",
        'reminders_list_title': "⏰ <b>Promemoria attivi ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\n📝 {text}\n\n",
        'reminder_alert': "⏰ <b>PROMEMORIA</b>\n\n📝 {text}",
        'grant_vip_prompt': "❓ /grant_vip [id/@username] [durata]\n\nDurata: week, month, year, forever",
        'grant_vip_user_not_found': "❌ Utente '{id}' non trovato.",
        'grant_vip_invalid_duration': "❌ Durata non valida. Disponibile: week, month, year, forever",
        'grant_vip_success': "✅ Stato VIP concesso!\n\n🆔 <code>{id}</code>\n⏰ {duration_text}",
        'grant_vip_dm': "🎉 Congratulazioni! Ti è stato concesso lo stato VIP {duration_text}!",
        'duration_until': "fino al {date}",
        'duration_forever': "per sempre",
        'revoke_vip_prompt': "❓ /revoke_vip [id/@username]",
        'revoke_vip_success': "✅ Stato VIP revocato per l'utente <code>{id}</code>.",
        'users_list_title': "👥 <b>UTENTI ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... e altri {count}</i>",
        'broadcast_prompt': "❓ /broadcast [testo messaggio]",
        'broadcast_started': "📤 Inizio broadcast...",
        'broadcast_finished': "✅ Broadcast terminato!\n\n✅ Successo: {success}\n❌ Falliti: {failed}",
        'broadcast_dm': "📢 <b>Messaggio dal creatore:</b>\n\n{text}",
        'stats_admin_title': (
            "📊 <b>STATISTICHE COMPLETE</b>\n\n"
            "<b>👥 Utenti:</b> {users}\n"
            "<b>💎 VIP:</b> {vips}\n\n"
            "<b>📈 Attività:</b>\n"
            "• Messaggi: {msg_count}\n"
            "• Comandi: {cmd_count}\n"
            "• Richieste AI: {ai_count}"
        ),
        'backup_success': "✅ Backup creato\n\n📅 {date}",
        'backup_error': "❌ Errore creazione backup: {error}",
        'file_received': "📥 Ricezione file...",
        'file_analyzing': "📄 <b>File:</b> {filename}\n\n🤖 <b>Analisi:</b>\n\n{text}",
        'file_error': "❌ Errore elaborazione documento: {error}",
        'photo_analyzing': "🔍 Analisi immagine...",
        'photo_result': "📸 <b>Analisi (Gemini Vision):</b>\n\n{text}\n\n💎 VIP",
        'photo_error': "❌ Errore elaborazione foto: {error}",
        'voice_transcribing': "🎙️ Trascrizione messaggio vocale...",
        'voice_result': "📝 <b>Trascrizione:</b>\n\n{text}",
        'voice_error': "❌ Errore elaborazione messaggio vocale: {error}",
        'error_generic': "❌ Si è verificato un errore imprevisto: {error}",
        'section_not_found': "❌ Sezione non trovata."
    }
}

# --- Хелперы локализации ---
def get_lang(user_id: int) -> str:
    """Получает язык пользователя, по умолчанию 'ru'."""
    user = storage.get_user(user_id)
    return user.get('language', 'ru')

def get_text(key: str, lang: str, **kwargs: Any) -> str:
    """Получает текст по ключу и языку, с поддержкой вложенных ключей и форматирования."""
    if lang not in localization_strings:
        lang = 'ru' # Фолбэк на русский

    try:
        # Поддержка вложенных ключей (напр. 'main_keyboard.chat')
        keys = key.split('.')
        text_template = localization_strings[lang]
        for k in keys:
            text_template = text_template[k]

        # Форматирование, если нужны аргументы
        if kwargs:
            return text_template.format(**kwargs)
        return text_template
    except KeyError:
        # Попытка найти в 'ru' или 'en' если в текущем языке нет
        try:
            fallback_lang = 'ru' if lang != 'ru' else 'en'
            text_template = localization_strings[fallback_lang]
            for k in keys:
                text_template = text_template[k]
            if kwargs:
                return text_template.format(**kwargs)
            return text_template
        except KeyError:
            logger.warning(f"Ключ локализации '{key}' не найден ни в '{lang}', ни в 'ru'/'en'.")
            return key # Возвращаем сам ключ как индикатор ошибки

# --- Карта кнопок меню ---
# Помогает определить, какая кнопка была нажата, независимо от языка
menu_button_map = {
    'chat': [get_text('main_keyboard.chat', lang) for lang in localization_strings],
    'notes': [get_text('main_keyboard.notes', lang) for lang in localization_strings],
    'weather': [get_text('main_keyboard.weather', lang) for lang in localization_strings],
    'time': [get_text('main_keyboard.time', lang) for lang in localization_strings],
    'games': [get_text('main_keyboard.games', lang) for lang in localization_strings],
    'info': [get_text('main_keyboard.info', lang) for lang in localization_strings],
    'vip_menu': [get_text('main_keyboard.vip_menu', lang) for lang in localization_strings],
    'admin_panel': [get_text('main_keyboard.admin_panel', lang) for lang in localization_strings],
    'generate': [get_text('main_keyboard.generate', lang) for lang in localization_strings],
}


# --- База данных PostgreSQL ---
Base = declarative_base() # Используем импорт из orm

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
    language = Column(String(5), default='ru') # Это поле вызывало ошибку

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

        # --- ИСПРАВЛЕНИЕ: Автоматическая миграция (Добавлено) ---
        # Этот блок проверит, существует ли колонка 'language' и добавит ее, если нет.
        # Это безопасно для существующих данных.
        try:
            inspector = inspect(engine)
            # Проверяем, существует ли таблица 'users'
            if inspector.has_table('users'):
                columns = [col['name'] for col in inspector.get_columns('users')]
                # Проверяем, отсутствует ли колонка 'language'
                if 'language' not in columns:
                    logger.warning("Обнаружена старая схема БД. Добавляю 'language' в 'users'...")
                    with engine.connect() as conn:
                        # Используем sa_text() для выполнения raw SQL
                        conn.execute(sa_text("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru'"))
                        conn.commit() # Применяем изменения
                    logger.info("✅ Поле 'language' успешно добавлено.")
            else:
                logger.info("Таблица 'users' не найдена, будет создана.")
        except Exception as migration_error:
            # Логируем ошибку, но не прерываем выполнение, create_all() попробует создать
            logger.error(f"❌ Ошибка во время проверки миграции: {migration_error}")
        # --- Конец миграции ---

        Base.metadata.create_all(engine) # Создаем все таблицы (включая users, если ее не было)
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
            self.users = {} # Не используем, т.к. работаем с БД
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
                # Этот запрос падал из-за отсутствия 'language'
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id, language='ru') # Устанавливаем язык по умолчанию
                    session.add(user)
                    session.commit()
                    # Перезапрашиваем, чтобы получить объект из БД
                    user = session.query(User).filter_by(id=user_id).first()

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
                    'language': user.language or 'ru' # Добавлено
                }
            except Exception as e:
                logger.error(f"Критическая ошибка get_user (id={user_id}): {e}")
                # Аварийный фолбэк, чтобы бот не падал в цикле
                return {'id': user_id, 'language': 'ru'}
            finally:
                session.close()
        else:
            if user_id not in self.users:
                self.users[user_id] = {
                    'id': user_id, 'username': '', 'first_name': '', 'vip': False, 'vip_until': None,
                    'notes': [], 'todos': [], 'memory': {}, 'reminders': [],
                    'registered': datetime.now().isoformat(), 'last_active': datetime.now().isoformat(),
                    'messages_count': 0, 'commands_count': 0, 'language': 'ru' # Добавлено
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
                logger.warning(f"Ошибка обновления пользователя (id={user_id}) в БД: {e}")
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

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    lang = get_lang(user_id)
    keyboard = [
        [KeyboardButton(get_text('main_keyboard.chat', lang)), KeyboardButton(get_text('main_keyboard.notes', lang))],
        [KeyboardButton(get_text('main_keyboard.weather', lang)), KeyboardButton(get_text('main_keyboard.time', lang))],
        [KeyboardButton(get_text('main_keyboard.games', lang)), KeyboardButton(get_text('main_keyboard.info', lang))]
    ]
    if storage.is_vip(user_id):
        keyboard.insert(0, [KeyboardButton(get_text('main_keyboard.vip_menu', lang)), KeyboardButton(get_text('main_keyboard.generate', lang))])
    if is_creator(user_id):
        keyboard.append([KeyboardButton(get_text('main_keyboard.admin_panel', lang))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_help_keyboard(lang: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(get_text('help_sections.help_basic', lang), callback_data="help_basic")],
        [InlineKeyboardButton(get_text('help_sections.help_ai', lang), callback_data="help_ai")],
        [InlineKeyboardButton(get_text('help_sections.help_memory', lang), callback_data="help_memory")],
        [InlineKeyboardButton(get_text('help_sections.help_notes', lang), callback_data="help_notes")],
        [InlineKeyboardButton(get_text('help_sections.help_todo', lang), callback_data="help_todo")],
        [InlineKeyboardButton(get_text('help_sections.help_utils', lang), callback_data="help_utils")],
        [InlineKeyboardButton(get_text('help_sections.help_games', lang), callback_data="help_games")],
        [InlineKeyboardButton(get_text('help_sections.help_vip', lang), callback_data="help_vip")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(get_text('help_sections.help_admin', lang), callback_data="help_admin")])
    # --- ИСПРАВЛЕНИЕ ---
    # Кнопка "Назад" не нужна в главном меню справки, она нужна только в подменю
    # keyboard.append([InlineKeyboardButton(get_text('help_back', lang), callback_data="help_back")])
    # ------------------
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'commands_count': user_data.get('commands_count', 0) + 1})
    is_admin = is_creator(user_id)
    await update.message.reply_text(
        get_text('help_title', lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(lang, is_admin)
    )

# Callback handlers for help sections
# --- ИСПРАВЛЕНО: Полностью переписана логика для корректной работы ---
async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = get_lang(user_id)
    is_admin = is_creator(user_id)

    if data == "help_back":
        # Если нажата "Назад", показываем главное меню справки
        await query.edit_message_text(
            get_text('help_title', lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(lang, is_admin)
        )
        return

    # Создаем клавиатуру "Назад" ОДИН РАЗ
    back_markup = InlineKeyboardMarkup([[InlineKeyboardButton(get_text('help_back', lang), callback_data="help_back")]])

    # Словарь с текстами для каждого раздела
    sections_text = {
        "help_basic": get_text('help_text.help_basic', lang),
        "help_ai": get_text('help_text.help_ai', lang),
        "help_memory": get_text('help_text.help_memory', lang),
        "help_notes": get_text('help_text.help_notes', lang),
        "help_todo": get_text('help_text.help_todo', lang),
        "help_utils": get_text('help_text.help_utils', lang),
        "help_games": get_text('help_text.help_games', lang),
        "help_vip": get_text('help_text.help_vip', lang),
    }

    text_to_show = None

    if data in sections_text:
        # Если это обычный раздел, берем текст
        text_to_show = sections_text[data]
    elif data == "help_admin" and is_admin:
        # Если это админский раздел (и пользователь админ), берем админский текст
        text_to_show = get_text('help_text.help_admin', lang)

    if text_to_show:
        # Показываем текст раздела и клавиатуру "Назад"
        await query.edit_message_text(
            text_to_show,
            parse_mode=ParseMode.HTML,
            reply_markup=back_markup
        )
    else:
        # Если раздел не найден (например, не-админ нажал "Админ" - хотя кнопки и не должно быть)
        await query.edit_message_text(
            get_text('help_title', lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(lang, is_admin)
        )
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


# --- НОВАЯ ФУНКЦИЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ ---
async def generate_image_imagen(prompt: str) -> Optional[bytes]:
    """
    Генерирует изображение с помощью Imagen 3 (imagen-3.0-generate-002)
    Возвращает байты изображения или None в случае ошибки.
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY (требуется для Imagen) не установлен.")
        return None

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"

    payload = {
        "instances": [
            {"prompt": prompt}
        ],
        "parameters": {
            "sampleCount": 1
        }
    }

    headers = {'Content-Type': 'application/json'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("predictions") and result["predictions"][0].get("bytesBase64Encoded"):
                        image_b64 = result["predictions"][0]["bytesBase64Encoded"]
                        return base64.b64decode(image_b64)
                    else:
                        logger.warning(f"Imagen API: Неожиданный ответ: {result}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"Imagen API: Ошибка {response.status}: {error_text}")
                    return None
    except Exception as e:
        logger.error(f"Imagen API: Исключение при запросе: {e}")
        return None

# Старая, нерабочая функция (оставлена для справки, но не используется)
async def generate_image_gemini_OLD(prompt: str) -> Optional[str]:
    # Эта функция была некорректной и заменена на generate_image_imagen
    pass

# ---

async def analyze_image_with_gemini(image_bytes: bytes, prompt: str = "Опиши подробно что изображено") -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = vision_model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка анализа изображения: {e}")
        return f"❌ Ошибка анализа: {str(e)}"

async def transcribe_audio_with_gemini(audio_bytes: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        uploaded_file = genai.upload_file(path=temp_path, mime_type="audio/ogg")
        response = model.generate_content(["Транскрибируй это аудио:", uploaded_file])
        os.remove(temp_path)
        return response.text
    except Exception as e:
        logger.warning(f"Ошибка транскрипции аудио: {e}")
        return f"❌ Ошибка транскрипции: {str(e)}"

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
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    document = update.message.document
    file_name = document.file_name or "file"
    await update.message.reply_text(get_text('file_received', lang))
    try:
        file_obj = await context.bot.get_file(document.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        extracted_text = await extract_text_from_document(bytes(file_bytes), file_name)
        if extracted_text.startswith("❌") or extracted_text.startswith("⚠️"):
            await update.message.reply_text(extracted_text)
            return
        analysis_prompt = f"Проанализируй файл '{file_name}':\n\n{extracted_text[:4000]}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(analysis_prompt)
        storage.save_chat(user_id, f"Файл {file_name}", response.text)
        await update.message.reply_text(get_text('file_analyzing', lang, filename=file_name, text=response.text), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки документа: {e}")
        await update.message.reply_text(get_text('file_error', lang, error=str(e)))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    photo = update.message.photo[-1]
    # Используем язык пользователя для промпта по умолчанию
    default_prompt = "Опиши что на картинке" if lang == 'ru' else "Describe what's in the picture"
    caption = update.message.caption or default_prompt

    await update.message.reply_text(get_text('photo_analyzing', lang))
    try:
        file_obj = await context.bot.get_file(photo.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        analysis = await analyze_image_with_gemini(bytes(file_bytes), caption)
        storage.save_chat(user_id, "Анализ фото", analysis)
        await update.message.reply_text(get_text('photo_result', lang, text=analysis), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка обработки фото: {e}")
        await update.message.reply_text(get_text('photo_error', lang, error=str(e)))

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    voice = update.message.voice
    await update.message.reply_text(get_text('voice_transcribing', lang))
    try:
        file_obj = await context.bot.get_file(voice.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        transcribed_text = await transcribe_audio_with_gemini(bytes(file_bytes))

        if transcribed_text.startswith("❌"):
            await update.message.reply_text(transcribed_text)
            return

        await update.message.reply_text(get_text('voice_result', lang, text=transcribed_text), parse_mode=ParseMode.HTML)
        # Отправляем распознанный текст на обработку AI
        await process_ai_message(update, transcribed_text, user_id, lang)
    except Exception as e:
        logger.warning(f"Ошибка обработки голосового сообщения: {e}")
        await update.message.reply_text(get_text('voice_error', lang, error=str(e)))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    identify_creator(user)
    # Эта функция (get_user) теперь безопасна, т.к. миграция прошла при запуске
    user_data = storage.get_user(user.id)

    storage.update_user(user.id, {
        'username': user.username or '', 
        'first_name': user.first_name or '', 
        'commands_count': user_data.get('commands_count', 0) + 1,
        'language': user_data.get('language', 'ru') # Устанавливаем язык
    })
    lang = get_lang(user.id)
    welcome_text = get_text('welcome', lang, first_name=user.first_name, creator=CREATOR_USERNAME)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id))

# Новая команда для смены языка
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    keyboard = [
        [InlineKeyboardButton("Русский 🇷🇺", callback_data="set_lang:ru")],
        [InlineKeyboardButton("English 🇬🇧", callback_data="set_lang:en")],
        [InlineKeyboardButton("Italiano 🇮🇹", callback_data="set_lang:it")],
    ]
    await update.message.reply_text(get_text('lang_choose', lang), reply_markup=InlineKeyboardMarkup(keyboard))

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only', lang))
        return

    if not context.args:
        await update.message.reply_text(get_text('gen_prompt_needed', lang))
        return

    prompt = ' '.join(context.args)
    await update.message.reply_text(get_text('gen_in_progress', lang))

    try:
        # Используем новую функцию
        image_bytes = await generate_image_imagen(prompt)

        if image_bytes:
            await update.message.reply_photo(
                photo=image_bytes, 
                caption=get_text('gen_caption', lang, prompt=prompt), 
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(get_text('gen_error', lang))
    except Exception as e:
        logger.warning(f"Ошибка generate_command: {e}")
        await update.message.reply_text(get_text('gen_error_api', lang, error=str(e)))


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if not context.args:
        await update.message.reply_text(get_text('ai_prompt_needed', lang))
        return
    await process_ai_message(update, ' '.join(context.args), user_id, lang)

async def process_ai_message(update: Update, text: str, user_id: int, lang: str):
    try:
        await update.message.chat.send_action(get_text('ai_typing', lang))
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(text)

        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response.text)

        await send_long_message(update.message, response.text)
    except Exception as e:
        logger.error(f"AI: {e}")
        await update.message.reply_text(get_text('ai_error', lang))

async def send_long_message(message: Message, text: str):
    if len(text) <= 4000:
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.5)  # Чтобы избежать флуда

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    storage.clear_chat_session(user_id)
    await update.message.reply_text(get_text('clear_context', lang))

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(get_text('info', lang), parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    stats = storage.stats
    all_users = storage.get_all_users()
    uptime = datetime.now() - BOT_START_TIME
    db_status = 'PostgreSQL ✓' if engine else 'JSON'

    status_text = get_text('status', lang,
        users=len(all_users),
        vips=sum(1 for u in all_users.values() if u.get('vip', False)),
        msg_count=stats.get('total_messages', 0),
        cmd_count=stats.get('total_commands', 0),
        ai_count=stats.get('ai_requests', 0),
        days=uptime.days,
        hours=uptime.seconds // 3600,
        db_status=db_status
    )
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user = storage.get_user(user_id)

    username_line = f"📱 @{user['username']}" if user.get('username') else ""
    reg_date = datetime.fromisoformat(user.get('registered', datetime.now().isoformat())).strftime('%d.%m.%Y')

    profile_text = get_text('profile', lang,
        first_name=user.get('first_name', 'User'),
        user_id=user.get('id'),
        username_line=username_line,
        registered_date=reg_date,
        msg_count=user.get('messages_count', 0),
        cmd_count=user.get('commands_count', 0),
        notes_count=len(user.get('notes', []))
    )

    if storage.is_vip(user_id):
        vip_until = user.get('vip_until')
        if vip_until:
            profile_text += get_text('profile_vip', lang, date=datetime.fromisoformat(vip_until).strftime('%d.%m.%Y'))
        else:
            profile_text += get_text('profile_vip_forever', lang)

    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML)

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    uptime = datetime.now() - BOT_START_TIME

    await update.message.reply_text(get_text('uptime', lang,
        start_time=BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S'),
        days=uptime.days,
        hours=uptime.seconds // 3600,
        minutes=(uptime.seconds % 3600) // 60
    ), parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user = storage.get_user(user_id)

    if storage.is_vip(user_id):
        vip_text = get_text('vip_status_active', lang)
        vip_until = user.get('vip_until')
        if vip_until:
            vip_text += get_text('vip_status_until', lang, date=datetime.fromisoformat(vip_until).strftime('%d.%m.%Y'))
        else:
            vip_text += get_text('vip_status_forever', lang)
        vip_text += get_text('vip_status_bonus', lang)
    else:
        vip_text = get_text('vip_status_inactive', lang)

    await update.message.reply_text(vip_text, parse_mode=ParseMode.HTML)

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if not context.args:
        await update.message.reply_text(get_text('note_prompt_needed', lang))
        return
    note_text = ' '.join(context.args)
    user = storage.get_user(user_id)
    note = {'text': note_text, 'created': datetime.now().isoformat()}
    notes = user.get('notes', [])
    notes.append(note)
    storage.update_user(user_id, {'notes': notes})
    await update.message.reply_text(get_text('note_saved', lang, num=len(notes), text=note_text))

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user = storage.get_user(user_id)
    notes = user.get('notes', [])
    if not notes:
        await update.message.reply_text(get_text('notes_empty', lang))
        return
    notes_text = get_text('notes_list_title', lang, count=len(notes))
    for i, note in enumerate(notes, 1):
        created = datetime.fromisoformat(note['created'])
        notes_text += get_text('notes_list_item', lang, i=i, date=created.strftime('%d.%m.%Y'), text=note['text'])
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if not context.args:
        await update.message.reply_text(get_text('delnote_prompt_needed', lang))
        return
    try:
        note_num = int(context.args[0])
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        if 1 <= note_num <= len(notes):
            deleted_note = notes.pop(note_num - 1)
            storage.update_user(user_id, {'notes': notes})
            await update.message.reply_text(get_text('delnote_success', lang, num=note_num, text=deleted_note['text']))
        else:
            await update.message.reply_text(get_text('delnote_not_found', lang, num=note_num))
    except ValueError:
        await update.message.reply_text(get_text('delnote_invalid_num', lang))

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if len(context.args) < 2:
        await update.message.reply_text(get_text('help_text.help_memory', lang).split('\n\n')[1]) # Показываем строку из help
        return
    key = context.args[0]
    value = ' '.join(context.args[1:])
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    memory[key] = value
    storage.update_user(user_id, {'memory': memory})
    await update.message.reply_text(f"✅ Сохранено:\n🔑 <b>{key}</b> = <code>{value}</code>", parse_mode=ParseMode.HTML)

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if not context.args:
        await update.message.reply_text(get_text('help_text.help_memory', lang).split('\n\n')[2])
        return
    key = context.args[0]
    user = storage.get_user(user_id)
    if key in user.get('memory', {}):
        await update.message.reply_text(f"🔍 <b>{key}</b> = <code>{user['memory'][key]}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден.")

async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    if not memory:
        await update.message.reply_text("📭 Память пуста.")
        return
    memory_text = "🧠 <b>Память:</b>\n\n"
    for key, value in memory.items():
        memory_text += f"🔑 <b>{key}</b>: <code>{value}</code>\n"
    await update.message.reply_text(memory_text, parse_mode=ParseMode.HTML)

async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if not context.args:
        await update.message.reply_text(get_text('help_text.help_memory', lang).split('\n\n')[4])
        return
    key = context.args[0]
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    if key in memory:
        del memory[key]
        storage.update_user(user_id, {'memory': memory})
        await update.message.reply_text(f"✅ Ключ '{key}' удалён.")
    else:
        await update.message.reply_text(f"❌ Ключ '{key}' не найден.")

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if not context.args:
        await update.message.reply_text(get_text('todo_prompt_needed', lang))
        return

    subcommand = context.args[0].lower()
    user = storage.get_user(user_id)

    if subcommand == 'add':
        if len(context.args) < 2:
            await update.message.reply_text(get_text('todo_add_prompt_needed', lang))
            return
        todo_text = ' '.join(context.args[1:])
        todo = {'text': todo_text, 'created': datetime.now().isoformat()}
        todos = user.get('todos', [])
        todos.append(todo)
        storage.update_user(user_id, {'todos': todos})
        await update.message.reply_text(get_text('todo_saved', lang, num=len(todos), text=todo_text))

    elif subcommand == 'list':
        todos = user.get('todos', [])
        if not todos:
            await update.message.reply_text(get_text('todo_empty', lang))
            return
        todos_text = get_text('todo_list_title', lang, count=len(todos))
        for i, todo in enumerate(todos, 1):
            created = datetime.fromisoformat(todo['created'])
            todos_text += get_text('todo_list_item', lang, i=i, date=created.strftime('%d.%m'), text=todo['text'])
        await update.message.reply_text(todos_text, parse_mode=ParseMode.HTML)

    elif subcommand == 'del':
        if len(context.args) < 2:
            await update.message.reply_text(get_text('todo_del_prompt_needed', lang))
            return
        try:
            todo_num = int(context.args[1])
            todos = user.get('todos', [])
            if 1 <= todo_num <= len(todos):
                deleted_todo = todos.pop(todo_num - 1)
                storage.update_user(user_id, {'todos': todos})
                await update.message.reply_text(get_text('todo_del_success', lang, num=todo_num, text=deleted_todo['text']))
            else:
                await update.message.reply_text(get_text('todo_del_not_found', lang, num=todo_num))
        except ValueError:
            await update.message.reply_text(get_text('todo_del_invalid_num', lang))
    else:
        await update.message.reply_text(get_text('todo_prompt_needed', lang))

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'

    # Расширенный список часовых поясов
    timezones = {
        'moscow': 'Europe/Moscow', 'москва': 'Europe/Moscow',
        'london': 'Europe/London', 'лондон': 'Europe/London',
        'new york': 'America/New_York', 'нью-йорк': 'America/New_York',
        'tokyo': 'Asia/Tokyo', 'токио': 'Asia/Tokyo',
        'paris': 'Europe/Paris', 'париж': 'Europe/Paris',
        'berlin': 'Europe/Berlin', 'берлин': 'Europe/Berlin',
        'dubai': 'Asia/Dubai', 'дубай': 'Asia/Dubai',
        'sydney': 'Australia/Sydney', 'сидней': 'Australia/Sydney',
        'los angeles': 'America/Los_Angeles', 'лос-анджелес': 'America/Los_Angeles',
        'rome': 'Europe/Rome', 'рим': 'Europe/Rome'
    }

    tz_name = timezones.get(city.lower(), None)

    # Если не нашли в словаре, пытаемся угадать
    if not tz_name:
        try:
            # Ищем подходящий часовой пояс
            matching_tz = [tz for tz in pytz.all_timezones if city.lower().replace(" ", "_") in tz.lower()]
            if matching_tz:
                tz_name = matching_tz[0]
            else:
                # Фолбэк на Москву, если ничего не найдено
                tz_name = 'Europe/Moscow' if not context.args else None
                if not tz_name:
                     await update.message.reply_text(get_text('time_city_not_found', lang, city=city))
                     return
        except Exception:
             await update.message.reply_text(get_text('time_city_not_found', lang, city=city))
             return

    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        await update.message.reply_text(get_text('time_result', lang,
            city=city.title(),
            time=current_time.strftime('%H:%M:%S'),
            date=current_time.strftime('%d.%m.%Y'),
            tz=tz_name
        ), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка времени: {e}")
        await update.message.reply_text(get_text('time_city_not_found', lang, city=city))

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    # Определяем язык для wttr.in
    wttr_lang = 'it' if lang == 'it' else 'en' if lang == 'en' else 'ru'
    city = ' '.join(context.args) if context.args else 'Moscow'

    try:
        async with aiohttp.ClientSession() as session:
            # Добавляем параметр 'lang' для wttr.in
            url = f"https://wttr.in/{urlquote(city)}?format=j1&lang={wttr_lang}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data['current_condition'][0]
                    temp_c = current['temp_C']
                    feels_like = current['FeelsLikeC']

                    # wttr.in предоставляет перевод в зависимости от 'lang'
                    description_key = f'weatherDesc_{wttr_lang}' if f'weatherDesc_{wttr_lang}' in current else 'weatherDesc'
                    description = current[description_key][0]['value']

                    humidity = current['humidity']
                    wind_speed = current['windspeedKmph']

                    weather_text = get_text('weather_result', lang,
                        city=city.title(),
                        temp=temp_c,
                        feels=feels_like,
                        desc=description,
                        humidity=humidity,
                        wind=wind_speed
                    )
                    await update.message.reply_text(weather_text, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(get_text('weather_city_not_found', lang, city=city))
    except Exception as e:
        logger.warning(f"Ошибка погоды: {e}")
        await update.message.reply_text(get_text('weather_error', lang))

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if len(context.args) < 2:
        await update.message.reply_text(get_text('translate_prompt_needed', lang))
        return

    target_lang = context.args[0]
    text_to_translate = ' '.join(context.args[1:])

    try:
        # Просим Gemini перевести
        prompt = f"Переведи на {target_lang} язык следующий текст: {text_to_translate}"
        chat = storage.get_chat_session(user_id)
        response = chat.send_message(prompt)
        await send_long_message(update.message, response.text)
    except Exception as e:
        logger.warning(f"Ошибка перевода: {e}")
        await update.message.reply_text(get_text('translate_error', lang))

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    if not context.args:
        await update.message.reply_text(get_text('calc_prompt_needed', lang))
        return

    expression = ' '.join(context.args)
    # Простая валидация: разрешаем только цифры, точки и операторы
    allowed_chars = "0123456789.+-*/() "
    if not all(char in allowed_chars for char in expression):
        await update.message.reply_text(get_text('calc_error', lang))
        return

    try:
        result = eval(expression, {"__builtins__": {}}, {})
        await update.message.reply_text(get_text('calc_result', lang, expr=expression, result=result), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка расчета: {e}")
        await update.message.reply_text(get_text('calc_error', lang))

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text(get_text('password_length_error', lang))
            return

        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(get_text('password_result', lang, password=password), parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(get_text('password_invalid_length', lang))

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    try:
        if len(context.args) >= 2:
            min_val = int(context.args[0])
            max_val = int(context.args[1])
        else:
            min_val = 1
            max_val = 100
        result = random.randint(min_val, max_val)
        await update.message.reply_text(get_text('random_result', lang, min=min_val, max=max_val, result=result), parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(get_text('random_invalid_range', lang))

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    result = random.randint(1, 6)
    dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
    await update.message.reply_text(get_text('dice_result', lang, emoji=dice_emoji, result=result), parse_mode=ParseMode.HTML)

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    result_key = random.choice(['coin_heads', 'coin_tails'])
    result_text = get_text(result_key, lang)
    emoji = '🦅' if result_key == 'coin_heads' else '💰' # (Орёл / Решка)
    await update.message.reply_text(get_text('coin_result', lang, emoji=emoji, result=result_text), parse_mode=ParseMode.HTML)

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    jokes = {
        'ru': [
            "Программист ложится спать. Жена: — Закрой окно, холодно! Программист: — И что, если я закрою окно, станет тепло? 😄",
            "— Почему программисты путают Хэллоуин и Рождество? — 31 OCT = 25 DEC! 🎃",
            "Зачем программисту очки? Чтобы лучше C++! 👓",
            "— Сколько программистов нужно, чтобы вкрутить лампочку? — Ни одного, это аппаратная проблема! 💡"
        ],
        'en': [
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "Why did the programmer quit his job? He didn't get arrays. 🤷‍♂️",
            "What's a programmer's favorite hangout spot? Foo bar. 🍻",
            "Why was the JavaScript developer sad? He didn't know how to 'null' his feelings. 💔"
        ],
        'it': [
            "Perché i programmatori confondono Halloween e Natale? Perché 31 OCT = 25 DEC! 🎃",
            "Come muore un programmatore? In un loop infinito. 🔄",
            "Qual è l'animale preferito di un programmatore? Il Python. 🐍",
            "Cosa dice un programmatore quando si sveglia? 'Hello, World!' ☀️"
        ]
    }
    await update.message.reply_text(f"{get_text('joke_title', lang)}{random.choice(jokes[lang])}", parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    quotes = {
        'ru': [
            "Единственный способ сделать великую работу — любить то, что вы делаете. — Стив Джобс",
            "Инновация отличает лидера от последователя. — Стив Джобс",
            "Программирование — это искусство превращать кофе в код. — Неизвестный",
            "Простота — залог надёжности. — Эдсгер Дейкстра"
        ],
        'en': [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "Programming is the art of turning coffee into code. - Unknown",
            "Simplicity is the soul of efficiency. - Edsger Dijkstra"
        ],
        'it': [
            "L'unico modo per fare un ottimo lavoro è amare quello che fai. - Steve Jobs",
            "L'innovazione distingue un leader da un seguace. - Steve Jobs",
            "Programmare è l'arte di trasformare il caffè in codice. - Sconosciuto",
            "La semplicità è la chiave dell'affidabilità. - Edsger Dijkstra"
        ]
    }
    await update.message.reply_text(f"{get_text('quote_title', lang)}{random.choice(quotes[lang])}{get_text('quote_title_end', lang)}", parse_mode=ParseMode.HTML)

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    facts = {
        'ru': [
            "🌍 Земля — единственная планета Солнечной системы, названная не в честь бога.",
            "🐙 У осьминогов три сердца и голубая кровь.",
            "🍯 Мёд не портится тысячи лет.",
            "💎 Алмазы формируются на глубине ~150 км.",
            "🧠 Мозг потребляет ~20% энергии тела.",
            "⚡ Молния в 5 раз горячее Солнца."
        ],
        'en': [
            "🌍 Earth is the only planet in our solar system not named after a god.",
            "🐙 Octopuses have three hearts and blue blood.",
            "🍯 Honey never spoils. Archaeologists have found pots of honey thousands of years old.",
            "💎 Diamonds form about 100 miles (160 km) below the Earth's surface.",
            "🧠 The human brain uses about 20% of the body's total energy.",
            "⚡ A bolt of lightning is five times hotter than the surface of the sun."
        ],
        'it': [
            "🌍 La Terra è l'unico pianeta del sistema solare a non avere il nome di una divinità.",
            "🐙 I polpi hanno tre cuori e il sangue blu.",
            "🍯 Il miele non scade mai. Può durare migliaia di anni.",
            "💎 I diamanti si formano a circa 150 km di profondità.",
            "🧠 Il cervello umano consuma circa il 20% dell'energia totale del corpo.",
            "⚡ Un fulmine è cinque volte più caldo della superficie del sole."
        ]
    }
    await update.message.reply_text(f"{get_text('fact_title', lang)}{random.choice(facts[lang])}", parse_mode=ParseMode.HTML)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only', lang))
        return

    if len(context.args) < 2:
        await update.message.reply_text(get_text('remind_prompt_needed', lang))
        return

    try:
        minutes = int(context.args[0])
        text = ' '.join(context.args[1:])
        remind_time = datetime.now() + timedelta(minutes=minutes)

        user = storage.get_user(user_id)
        reminder = {'text': text, 'time': remind_time.isoformat(), 'created': datetime.now().isoformat(), 'lang': lang} # Сохраняем язык
        reminders = user.get('reminders', [])
        reminders.append(reminder)
        storage.update_user(user_id, {'reminders': reminders})

        # Передаем язык в задачу
        scheduler.add_job(send_reminder, 'date', run_date=remind_time, args=[context.bot, user_id, text, lang])

        await update.message.reply_text(get_text('remind_success', lang, text=text, minutes=minutes))
    except ValueError:
        await update.message.reply_text(get_text('remind_invalid_time', lang))

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    if not storage.is_vip(user_id):
        await update.message.reply_text(get_text('vip_only', lang))
        return

    user = storage.get_user(user_id)
    reminders = user.get('reminders', [])

    if not reminders:
        await update.message.reply_text(get_text('reminders_empty', lang))
        return

    reminders_text = get_text('reminders_list_title', lang, count=len(reminders))
    for i, reminder in enumerate(reminders, 1):
        remind_time = datetime.fromisoformat(reminder['time'])
        reminders_text += get_text('reminders_list_item', lang,
            i=i,
            time=remind_time.strftime('%d.%m %H:%M'),
            text=reminder['text']
        )
    await update.message.reply_text(reminders_text, parse_mode=ParseMode.HTML)

async def send_reminder(bot, user_id: int, text: str, lang: str):
    """Отправляет напоминание на языке пользователя."""
    try:
        # Используем сохраненный язык
        reminder_text = get_text('reminder_alert', lang, text=text)
        await bot.send_message(chat_id=user_id, text=reminder_text, parse_mode=ParseMode.HTML)

        # Удаляем напоминание из БД
        user = storage.get_user(user_id)
        # Ищем по тексту и времени (на всякий случай, если текст совпадает)
        reminders = [r for r in user.get('reminders', []) if not (r['text'] == text and (datetime.now() - datetime.fromisoformat(r['time'])).total_seconds() > -60)]
        storage.update_user(user_id, {'reminders': reminders})
    except Exception as e:
        logger.warning(f"Ошибка отправки напоминания: {e}")

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    identify_creator(update.effective_user)

    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return

    if len(context.args) < 2:
        await update.message.reply_text(get_text('grant_vip_prompt', lang))
        return

    try:
        identifier = context.args[0]
        duration_key = context.args[1].lower()

        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(get_text('grant_vip_user_not_found', lang, id=identifier))
            return

        durations = {'week': timedelta(weeks=1), 'month': timedelta(days=30), 'year': timedelta(days=365), 'forever': None}
        if duration_key not in durations:
            await update.message.reply_text(get_text('grant_vip_invalid_duration', lang))
            return

        duration_delta = durations[duration_key]

        if duration_delta:
            vip_until = datetime.now() + duration_delta
            storage.update_user(target_id, {'vip': True, 'vip_until': vip_until.isoformat()})
            duration_text = get_text('duration_until', lang, date=vip_until.strftime('%d.%m.%Y'))
        else:
            storage.update_user(target_id, {'vip': True, 'vip_until': None})
            duration_text = get_text('duration_forever', lang)

        await update.message.reply_text(get_text('grant_vip_success', lang, id=target_id, duration_text=duration_text), parse_mode=ParseMode.HTML)

        try:
            # Отправляем уведомление пользователю на его языке
            target_lang = get_lang(target_id)
            dm_text = get_text('grant_vip_dm', target_lang, duration_text=get_text(f'duration_{duration_key}', target_lang, date=vip_until.strftime('%d.%m.%Y') if duration_delta else ''))
            await context.bot.send_message(chat_id=target_id, text=dm_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Ошибка уведомления о VIP: {e}")

    except Exception as e:
        logger.warning(f"Ошибка grant_vip: {e}")
        await update.message.reply_text(get_text('error_generic', lang, error=str(e)))

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    identify_creator(update.effective_user)

    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return

    if not context.args:
        await update.message.reply_text(get_text('revoke_vip_prompt', lang))
        return

    try:
        identifier = context.args[0]
        target_id = storage.get_user_id_by_identifier(identifier)
        if not target_id:
            await update.message.reply_text(get_text('grant_vip_user_not_found', lang, id=identifier))
            return

        storage.update_user(target_id, {'vip': False, 'vip_until': None})
        await update.message.reply_text(get_text('revoke_vip_success', lang, id=target_id), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Ошибка revoke_vip: {e}")
        await update.message.reply_text(get_text('error_generic', lang, error=str(e)))

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    identify_creator(update.effective_user)

    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return

    all_users = storage.get_all_users()
    users_text = get_text('users_list_title', lang, count=len(all_users))

    for i, (user_id, user) in enumerate(all_users.items()):
        if i >= 20: # Лимит 20 для Telegram
            users_text += get_text('users_list_more', lang, count=len(all_users) - 20)
            break

        vip_badge = "💎" if user.get('vip', False) else ""
        users_text += get_text('users_list_item', lang,
            vip_badge=vip_badge,
            id=user_id,
            name=user.get('first_name', 'Unknown'),
            username=user.get('username', '')
        )

    await update.message.reply_text(users_text, parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    identify_creator(update.effective_user)

    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return

    if not context.args:
        await update.message.reply_text(get_text('broadcast_prompt', lang))
        return

    message_text = ' '.join(context.args)
    success = 0
    failed = 0

    status_msg = await update.message.reply_text(get_text('broadcast_started', lang))
    all_users = storage.get_all_users()

    for user_id_target in all_users.keys():
        try:
            # Отправляем сообщение на языке пользователя
            target_lang = get_lang(user_id_target)
            broadcast_text = get_text('broadcast_dm', target_lang, text=message_text)
            await context.bot.send_message(chat_id=user_id_target, text=broadcast_text, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05) # Избегаем флуда
        except Exception as e:
            logger.warning(f"Ошибка рассылки пользователю {user_id_target}: {e}")
            failed += 1

    await status_msg.edit_text(get_text('broadcast_finished', lang, success=success, failed=failed))

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    identify_creator(update.effective_user)

    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return

    stats = storage.stats
    all_users = storage.get_all_users()

    stats_text = get_text('stats_admin_title', lang,
        users=len(all_users),
        vips=sum(1 for u in all_users.values() if u.get('vip', False)),
        msg_count=stats.get('total_messages', 0),
        cmd_count=stats.get('total_commands', 0),
        ai_count=stats.get('ai_requests', 0)
    )
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    identify_creator(update.effective_user)

    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return

    try:
        backup_data = {'users': storage.get_all_users(), 'stats': storage.stats, 'backup_date': datetime.now().isoformat()}
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        await update.message.reply_document(
            document=open(backup_filename, 'rb'), 
            caption=get_text('backup_success', lang, date=datetime.now().strftime('%d.%m.%Y %H:%M'))
        )
        os.remove(backup_filename)
    except Exception as e:
        logger.warning(f"Ошибка бэкапа: {e}")
        await update.message.reply_text(get_text('backup_error', lang, error=str(e)))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    text = update.message.text

    user = storage.get_user(user_id)
    lang = user.get('language', 'ru') # Получаем язык

    storage.update_user(user_id, {
        'messages_count': user.get('messages_count', 0) + 1, 
        'username': update.effective_user.username or '', 
        'first_name': update.effective_user.first_name or ''
    })

    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()

    # Кнопки меню (проверка по всем языкам)
    button_key = None
    for key, labels in menu_button_map.items():
        if text in labels:
            button_key = key
            break

    if button_key:
        await handle_menu_button(update, context, button_key, lang)
        return

    # В группах только по упоминанию
    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    # AI ответ
    if text:
        await process_ai_message(update, text, user_id, lang)

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_key: str, lang: str):
    user_id = update.effective_user.id

    if button_key == "chat":
        await update.message.reply_text(get_text('menu.chat', lang), parse_mode=ParseMode.HTML)
    elif button_key == "notes":
        keyboard = [
            [InlineKeyboardButton(get_text('menu.notes_create', lang), callback_data="note_create")], 
            [InlineKeyboardButton(get_text('menu.notes_list', lang), callback_data="note_list")]
        ]
        await update.message.reply_text(get_text('menu.notes', lang), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button_key == "weather":
        await update.message.reply_text(get_text('menu.weather', lang), parse_mode=ParseMode.HTML)
    elif button_key == "time":
        await update.message.reply_text(get_text('menu.time', lang), parse_mode=ParseMode.HTML)
    elif button_key == "games":
        keyboard = [
            [InlineKeyboardButton(get_text('menu.games_dice', lang), callback_data="game_dice"), 
             InlineKeyboardButton(get_text('menu.games_coin', lang), callback_data="game_coin")],
            [InlineKeyboardButton(get_text('menu.games_joke', lang), callback_data="game_joke"), 
             InlineKeyboardButton(get_text('menu.games_quote', lang), callback_data="game_quote")],
            [InlineKeyboardButton(get_text('menu.games_fact', lang), callback_data="game_fact")]
        ]
        await update.message.reply_text(get_text('menu.games', lang), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button_key == "info":
        await info_command(update, context)
    elif button_key == "vip_menu":
        if storage.is_vip(user_id):
            keyboard = [
                [InlineKeyboardButton(get_text('menu.vip_reminders', lang), callback_data="vip_reminders")], 
                [InlineKeyboardButton(get_text('menu.vip_stats', lang), callback_data="vip_stats")]
            ]
            await update.message.reply_text(get_text('menu.vip', lang), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await vip_command(update, context)
    elif button_key == "admin_panel":
        if is_creator(user_id):
            keyboard = [
                [InlineKeyboardButton(get_text('menu.admin_users', lang), callback_data="admin_users")], 
                [InlineKeyboardButton(get_text('menu.admin_stats', lang), callback_data="admin_stats")], 
                [InlineKeyboardButton(get_text('menu.admin_broadcast', lang), callback_data="admin_broadcast")]
            ]
            await update.message.reply_text(get_text('menu.admin', lang), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif button_key == "generate":
        if storage.is_vip(user_id):
            await update.message.reply_text(get_text('menu.generate', lang), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(get_text('vip_only', lang))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = get_lang(user_id) # Получаем язык для всех колбэков
    identify_creator(query.from_user)

    # --- НОВЫЙ ОБРАБОТЧИК СМЕНЫ ЯЗЫКА ---
    if data.startswith("set_lang:"):
        new_lang = data.split(":")[1]
        if new_lang in localization_strings:
            storage.update_user(user_id, {'language': new_lang})
            await query.edit_message_text(get_text('lang_changed', new_lang))

            # Отправляем новое приветственное сообщение с обновленной клавиатурой
            user = storage.get_user(user_id)
            welcome_text = get_text('welcome', new_lang, first_name=user.get('first_name', 'User'), creator=CREATOR_USERNAME)
            await query.message.reply_text(
                welcome_text, 
                parse_mode=ParseMode.HTML, 
                reply_markup=get_main_keyboard(user_id)
            )
        return

    # Help callbacks
    if data.startswith("help_"):
        await handle_help_callback(update, context)
        return

    # Note callbacks
    if data == "note_create":
        await query.edit_message_text(get_text('note_prompt_needed', lang), parse_mode=ParseMode.HTML)
    elif data == "note_list":
        user = storage.get_user(user_id)
        notes = user.get('notes', [])
        if not notes:
            await query.edit_message_text(get_text('notes_empty', lang))
            return
        notes_text = get_text('notes_list_title', lang, count=len(notes))
        for i, note in enumerate(notes, 1):
            created = datetime.fromisoformat(note['created'])
            notes_text += get_text('notes_list_item', lang, i=i, date=created.strftime('%d.%m'), text=note['text'])
        await query.edit_message_text(notes_text, parse_mode=ParseMode.HTML)

    # Game callbacks
    elif data == "game_dice":
        result = random.randint(1, 6)
        dice_emoji = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'][result - 1]
        await query.message.reply_text(get_text('dice_result', lang, emoji=dice_emoji, result=result), parse_mode=ParseMode.HTML)
    elif data == "game_coin":
        result_key = random.choice(['coin_heads', 'coin_tails'])
        result_text = get_text(result_key, lang)
        emoji = '🦅' if result_key == 'coin_heads' else '💰'
        await query.message.reply_text(get_text('coin_result', lang, emoji=emoji, result=result_text), parse_mode=ParseMode.HTML)
    elif data == "game_joke":
        await joke_command(query, context) # Используем команду, т.к. в ней уже есть логика
    elif data == "game_quote":
        await quote_command(query, context)
    elif data == "game_fact":
        await fact_command(query, context)

    # VIP callbacks
    elif data == "vip_reminders":
        # Создаем фейковый update, т.к. команда ожидает message
        fake_update = Update(update_id=update.update_id, message=query.message)
        await reminders_command(fake_update, context)
    elif data == "vip_stats":
        fake_update = Update(update_id=update.update_id, message=query.message)
        await profile_command(fake_update, context)

    # Admin callbacks
    elif data == "admin_users":
        if is_creator(user_id):
            fake_update = Update(update_id=update.update_id, message=query.message)
            await users_command(fake_update, context)
    elif data == "admin_stats":
        if is_creator(user_id):
            fake_update = Update(update_id=update.update_id, message=query.message)
            await stats_command(fake_update, context)
    elif data == "admin_broadcast":
        if is_creator(user_id):
            await query.edit_message_text(get_text('broadcast_prompt', lang), parse_mode=ParseMode.HTML)

def signal_handler(signum, frame):
    logger.info("Получен сигнал завершения. Останавливаем бота...")
    scheduler.shutdown()
    raise SystemExit

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("language", language_command)) # Новая команда
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

    application.add_handler(CommandHandler("todo", todo_command))

    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("password", password_command))

    application.add_handler(CommandHandler("random", random_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("fact", fact_command))

    application.add_handler(CommandHandler("vip", vip_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("generate", generate_command))

    application.add_handler(CommandHandler("grant_vip", grant_vip_command))
    application.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("backup", backup_command))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск scheduler
    scheduler.start()

    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT ЗАПУЩЕН!")
    logger.info("🤖 Модель: Gemini 2.5 Flash")
    logger.info("🗄️ БД: " + ("PostgreSQL ✓" if engine else "Local JSON"))
    logger.info("🖼️ Генерация: Imagen 3 (Fixed)") # Обновлено
    logger.info("🔍 Анализ: Gemini Vision")
    logger.info("🎙️ Транскрипция: Gemini 2.5 Flash")
    logger.info("🗣️ Языки: RU, EN, IT") # Добавлено
    logger.info("=" * 50)

    # Graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
