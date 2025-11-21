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
import tempfile

# Telegram Imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# Gemini (Vision/Audio)
import google.generativeai as genai

# --- HUGGING FACE API (ЛЕГКИЙ КЛИЕНТ) ---
from huggingface_hub import InferenceClient

# Utils
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx

# SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger, inspect, text as sa_text
from sqlalchemy.orm import sessionmaker, declarative_base

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
HF_TOKEN = os.getenv('HF_TOKEN') 

# ID вашей модели на Hugging Face
# Используем базовую Llama 3.1 Instruct, так как API адаптеры (LoRA) поддерживает сложнее
# Если ваша модель Ernest1Kostevich1/ernest-ai-llama-8b публичная и merged, можно попробовать её
YOUR_MODEL_NAME = "meta-llama/Meta-Llama-3.1-8B-Instruct" 

CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверка переменных
if not BOT_TOKEN or not GEMINI_API_KEY or not HF_TOKEN:
    logger.error("❌ ОШИБКА: Не заданы BOT_TOKEN, GEMINI_API_KEY или HF_TOKEN")

# --- 1. НАСТРОЙКА GEMINI (VISION/AUDIO) ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    vision_model = genai.GenerativeModel(
        model_name='gemini-1.5-flash', # Используем стабильную версию
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )
else:
    vision_model = None

# --- 2. НАСТРОЙКА HF API КЛИЕНТА ---
# Это заменяет тяжелую загрузку модели
hf_client = InferenceClient(model=YOUR_MODEL_NAME, token=HF_TOKEN)

# --- ФУНКЦИЯ ГЕНЕРАЦИИ (API) ---
def generate_with_your_model(prompt: str, lang: str = 'ru', max_new_tokens: int = 512) -> str:
    if not HF_TOKEN:
        return "❌ Ошибка: HF_TOKEN не найден."
    
    try:
        # Системный промпт
        sys_prompt = "You are AI DISCO BOT, a helpful assistant created by @Ernest_Kostevich."
        if lang == 'ru':
            sys_prompt = "Ты — AI DISCO BOT, умный и вежливый ассистент. Твой создатель — @Ernest_Kostevich. Отвечай на русском языке."
        elif lang == 'it':
            sys_prompt = "Sei AI DISCO BOT, un assistente intelligente creato da @Ernest_Kostevich. Rispondi in italiano."

        # Формирование сообщений для Chat API
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Запрос к API Hugging Face (Serverless Inference)
        # Это не грузит память вашего сервера
        response = hf_client.chat_completion(
            messages, 
            max_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.9
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Ошибка API Hugging Face: {e}")
        # Fallback (если сервер перегружен, можно добавить повтор)
        if "429" in str(e): # Rate limit
            return "😔 Сервер перегружен (Rate Limit). Попробуйте через минуту."
        if "401" in str(e):
            return "❌ Ошибка авторизации HF_TOKEN."
        return f"😔 Ошибка нейросети: {str(e)[:100]}"

# --- ЛОКАЛИЗАЦИЯ ---
localization_strings = {
    'ru': {
        'welcome': (
            "🤖 <b>AI DISCO BOT</b>\n\n"
            "Привет, {first_name}! Я работаю через <b>Hugging Face API</b> (Llama 3.1).\n\n"
            "<b>🎯 Возможности:</b>\n"
            "💬 Умный чат\n"
            "📝 Заметки и задачи\n"
            "🌍 Погода и время\n"
            "📎 Анализ файлов\n"
            "🖼️ Генерация (Imagen 3)\n\n"
            "<b>⚡ Команды:</b> /help, /language, /vip\n"
            "<b>👨‍💻 Создатель:</b> @{creator}"
        ),
        'lang_changed': "✅ Язык изменен на Русский 🇷🇺",
        'lang_choose': "Выберите язык:",
        'main_keyboard': {
            'chat': "💬 AI Чат", 'notes': "📝 Заметки", 'weather': "🌍 Погода", 'time': "⏰ Время",
            'games': "🎲 Развлечения", 'info': "ℹ️ Инфо", 'vip_menu': "💎 VIP Меню",
            'admin_panel': "👑 Админ Панель", 'generate': "🖼️ Генерация"
        },
        'help_title': "📚 <b>Справка:</b>",
        'help_back': "🔙 Назад",
        'help_sections': {'help_basic': "🏠 Основные", 'help_ai': "💬 AI", 'help_memory': "🧠 Память", 'help_notes': "📝 Заметки", 'help_todo': "📋 Задачи", 'help_utils': "🌍 Утилиты", 'help_games': "🎲 Игры", 'help_vip': "💎 VIP", 'help_admin': "👑 Админ"},
        'help_text': {
            'help_basic': "🚀 /start, 📖 /help, ℹ️ /info, 📊 /status, 👤 /profile, 🗣️ /language",
            'help_ai': "💬 Просто пишите мне сообщения!\n🧹 /clear - Очистить контекст (логически)",
            'help_memory': "🧠 /memorysave, /memoryget, /memorylist, /memorydel",
            'help_notes': "📝 /note [текст], /notes, /delnote [номер]",
            'help_todo': "📋 /todo add [текст], /todo list, /todo del [номер]",
            'help_utils': "🌍 /time, /weather, /translate, /calc, /password",
            'help_games': "🎲 /dice, /coin, /joke, /quote, /fact",
            'help_vip': "💎 /vip, /generate, /remind, Файлы/Фото",
            'help_admin': "👑 /grant_vip, /revoke_vip, /users, /broadcast, /stats, /backup"
        },
        'menu': {'chat': "🤖 <b>AI Чат</b>\nПиши, я отвечу!", 'notes': "📝 Заметки", 'notes_create': "➕ Создать", 'notes_list': "📋 Список", 'weather': "🌍 /weather [город]", 'time': "⏰ /time [город]", 'games': "🎲 Развлечения", 'games_dice': "🎲", 'games_coin': "🪙", 'games_joke': "😄", 'games_quote': "💭", 'games_fact': "🔬", 'vip': "💎 VIP Меню", 'vip_reminders': "⏰ Напоминания", 'vip_stats': "📊 Статы", 'admin': "👑 Админ", 'admin_users': "👥", 'admin_stats': "📊", 'admin_broadcast': "📢", 'generate': "🖼️ /generate [промпт]"},
        'info': "🤖 <b>AI DISCO BOT 4.0</b>\n🧠 <b>AI:</b> Llama 3.1 (via API)\n👀 <b>Vision:</b> Gemini 1.5\n👨‍💻 @Ernest_Kostevich",
        'status': "📊 <b>Статус</b>\n👥 Юзеры: {users}\n💎 VIP: {vips}\n🤖 AI Модель: {db_status}",
        'profile': "👤 <b>{first_name}</b>\n🆔 <code>{user_id}</code>\n📊 Сообщений: {msg_count}",
        'profile_vip': "\n💎 VIP до: {date}", 'profile_vip_forever': "\n💎 VIP: Навсегда",
        'uptime': "⏱ Работаю: {days}д {hours}ч",
        'vip_status_active': "💎 VIP Активен!", 'vip_status_inactive': "💎 Нет VIP.", 'vip_only': "💎 Только для VIP.",
        'gen_prompt_needed': "❓ /generate [описание]", 'gen_in_progress': "🎨 Рисую (Imagen 3)...", 'gen_caption': "🖼️ {prompt}", 'gen_error': "❌ Ошибка генерации", 'gen_error_api': "❌ API Ошибка: {error}",
        'ai_typing': "typing", 'ai_error': "😔 Ошибка нейросети.",
        'note_prompt_needed': "❓ /note [текст]", 'note_saved': "✅ Заметка сохранена!", 'notes_empty': "📭 Пусто.", 'notes_list_title': "📝 Заметки:", 'notes_list_item': "#{i} {text}\n",
        'delnote_prompt_needed': "❓ /delnote [номер]", 'delnote_success': "✅ Удалено.", 'delnote_not_found': "❌ Нет такой.",
        'todo_prompt_needed': "❓ /todo add...", 'todo_saved': "✅ Задача добавлена.", 'todo_empty': "📭 Нет задач.", 'todo_list_title': "📋 Задачи:", 'todo_list_item': "#{i} {text}\n",
        'weather_result': "🌍 {city}: {temp}°C, {desc}", 'weather_city_not_found': "❌ Город не найден.",
        'time_result': "⏰ {city}: {time}", 'time_city_not_found': "❌ Не нашел город.",
        'translate_prompt_needed': "❓ /translate [язык] [текст]", 'translate_error': "❌ Ошибка.",
        'calc_result': "{expr} = {result}", 'calc_error': "❌ Ошибка.",
        'password_result': "🔑 <code>{password}</code>",
        'random_result': "🎲 {result}",
        'dice_result': "🎲 {result}", 'coin_result': "🪙 {result}", 'coin_heads': "Орел", 'coin_tails': "Решка",
        'joke_title': "😄 ", 'quote_title': "💭 ", 'fact_title': "🔬 ",
        'remind_success': "⏰ Напоминание через {minutes} мин.", 'reminder_alert': "⏰ <b>НАПОМИНАНИЕ:</b>\n{text}",
        'grant_vip_success': "✅ VIP выдан.", 'grant_vip_dm': "🎉 Вам выдан VIP!", 'duration_until': "до {date}", 'duration_forever': "навсегда",
        'revoke_vip_success': "✅ VIP снят.",
        'broadcast_started': "📤 Рассылка...", 'broadcast_finished': "✅ Готово.", 'broadcast_dm': "📢 <b>Объявление:</b>\n{text}",
        'backup_success': "✅ Бэкап создан.",
        'file_received': "📥 Читаю файл...", 'file_analyzing': "📄 <b>Файл:</b> {filename}\n\n🤖 {text}", 'file_error': "❌ Ошибка файла.",
        'photo_analyzing': "🔍 Смотрю фото...", 'photo_result': "📸 <b>Gemini Vision:</b>\n{text}", 'photo_error': "❌ Ошибка фото.",
        'voice_transcribing': "🎙️ Слушаю...", 'voice_result': "📝 <b>Текст:</b>\n{text}", 'voice_error': "❌ Ошибка аудио.",
        'error_generic': "❌ Ошибка: {error}", 'admin_only': "❌ Только создатель."
    },
    'en': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nHi {first_name}! Powered by <b>Llama 3.1 (API)</b>.\n\nCommands: /help\nCreator: @{creator}",
        'lang_changed': "✅ Language changed to English 🇬🇧", 'lang_choose': "Choose language:",
        'main_keyboard': {'chat': "💬 AI Chat", 'notes': "📝 Notes", 'weather': "🌍 Weather", 'time': "⏰ Time", 'games': "🎲 Games", 'info': "ℹ️ Info", 'vip_menu': "💎 VIP", 'admin_panel': "👑 Admin", 'generate': "🖼️ Gen"},
        'help_title': "📚 <b>Help:</b>", 'help_back': "🔙 Back",
        'help_sections': {'help_basic': "🏠 Basic", 'help_ai': "💬 AI", 'help_memory': "🧠 Memory", 'help_notes': "📝 Notes", 'help_todo': "📋 ToDo", 'help_utils': "🌍 Utils", 'help_games': "🎲 Games", 'help_vip': "💎 VIP", 'help_admin': "👑 Admin"},
        'help_text': {'help_basic': "/start, /help, /language", 'help_ai': "Just type!", 'help_memory': "/memorysave...", 'help_notes': "/note...", 'help_todo': "/todo...", 'help_utils': "/weather...", 'help_games': "/dice...", 'help_vip': "/vip...", 'help_admin': "/stats..."},
        'menu': {'chat': "🤖 AI Chat", 'notes': "📝 Notes", 'notes_create': "➕ New", 'notes_list': "📋 List", 'weather': "🌍 Weather", 'time': "⏰ Time", 'games': "🎲 Games", 'games_dice': "🎲", 'games_coin': "🪙", 'games_joke': "😄", 'games_quote': "💭", 'games_fact': "🔬", 'vip': "💎 VIP", 'vip_reminders': "⏰ Remind", 'vip_stats': "📊 Stats", 'admin': "👑 Admin", 'admin_users': "👥", 'admin_stats': "📊", 'admin_broadcast': "📢", 'generate': "🖼️ Gen"},
        'info': "🤖 AI DISCO BOT\nAI: Llama 3.1 (API)\nDev: @Ernest_Kostevich",
        'status': "📊 Status\nUsers: {users}\nVIP: {vips}\nDB: {db_status}",
        'profile': "👤 {first_name}\nMessages: {msg_count}", 'profile_vip': "\nVIP until: {date}", 'profile_vip_forever': "\nVIP: Forever",
        'uptime': "⏱ Uptime: {days}d {hours}h",
        'vip_status_active': "💎 VIP Active", 'vip_status_inactive': "💎 No VIP", 'vip_only': "💎 VIP Only",
        'gen_prompt_needed': "❓ /generate [prompt]", 'gen_in_progress': "🎨 Drawing...", 'gen_caption': "🖼️ {prompt}", 'gen_error': "❌ Error", 'gen_error_api': "❌ API Error: {error}",
        'ai_typing': "typing", 'ai_error': "😔 AI Error.",
        'note_prompt_needed': "❓ /note [text]", 'note_saved': "✅ Saved.", 'notes_empty': "📭 Empty.", 'notes_list_title': "📝 Notes:", 'notes_list_item': "#{i} {text}\n",
        'delnote_prompt_needed': "❓ /delnote [num]", 'delnote_success': "✅ Deleted.", 'delnote_not_found': "❌ Not found.",
        'todo_prompt_needed': "❓ /todo...", 'todo_saved': "✅ Added.", 'todo_empty': "📭 Empty.", 'todo_list_title': "📋 Tasks:", 'todo_list_item': "#{i} {text}\n",
        'weather_result': "🌍 {city}: {temp}°C", 'weather_city_not_found': "❌ Not found.",
        'time_result': "⏰ {city}: {time}", 'time_city_not_found': "❌ Not found.",
        'translate_prompt_needed': "❓ /translate [lang] [text]", 'translate_error': "❌ Error.",
        'calc_result': "{result}", 'calc_error': "❌ Error.",
        'password_result': "🔑 {password}", 'random_result': "🎲 {result}",
        'dice_result': "🎲 {result}", 'coin_result': "🪙 {result}", 'coin_heads': "Heads", 'coin_tails': "Tails",
        'joke_title': "😄 ", 'quote_title': "💭 ", 'fact_title': "🔬 ",
        'remind_success': "⏰ Set for {minutes} min.", 'reminder_alert': "⏰ REMINDER:\n{text}",
        'grant_vip_success': "✅ VIP granted.", 'grant_vip_dm': "🎉 You got VIP!", 'duration_until': "until {date}", 'duration_forever': "forever",
        'revoke_vip_success': "✅ VIP revoked.",
        'broadcast_started': "📤 Sending...", 'broadcast_finished': "✅ Done.", 'broadcast_dm': "📢 {text}",
        'backup_success': "✅ Backup done.",
        'file_received': "📥 Reading...", 'file_analyzing': "📄 File: {filename}\n\n{text}", 'file_error': "❌ Error.",
        'photo_analyzing': "🔍 Looking...", 'photo_result': "📸 Vision:\n{text}", 'photo_error': "❌ Error.",
        'voice_transcribing': "🎙️ Listening...", 'voice_result': "📝 Text:\n{text}", 'voice_error': "❌ Error.",
        'error_generic': "❌ Error: {error}", 'admin_only': "❌ Creator only."
    },
    'it': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nCiao {first_name}! Ora con <b>Llama 3.1 (API)</b>.\n\nCreatore: @{creator}",
        'lang_changed': "✅ Lingua: Italiano 🇮🇹", 'lang_choose': "Scegli lingua:",
        'main_keyboard': {'chat': "💬 Chat AI", 'notes': "📝 Note", 'weather': "🌍 Meteo", 'time': "⏰ Ora", 'games': "🎲 Giochi", 'info': "ℹ️ Info", 'vip_menu': "💎 VIP", 'admin_panel': "👑 Admin", 'generate': "🖼️ Gen"},
        'help_title': "📚 Aiuto:", 'help_back': "🔙 Indietro",
        'help_sections': {'help_basic': "🏠 Base", 'help_ai': "💬 AI", 'help_memory': "🧠 Memoria", 'help_notes': "📝 Note", 'help_todo': "📋 ToDo", 'help_utils': "🌍 Utilità", 'help_games': "🎲 Giochi", 'help_vip': "💎 VIP", 'help_admin': "👑 Admin"},
        'help_text': {'help_basic': "/start, /help", 'help_ai': "Scrivi e basta!", 'help_memory': "/memorysave...", 'help_notes': "/note...", 'help_todo': "/todo...", 'help_utils': "/weather...", 'help_games': "/dice...", 'help_vip': "/vip...", 'help_admin': "/stats..."},
        'menu': {'chat': "🤖 Chat", 'notes': "📝 Note", 'notes_create': "➕ Crea", 'notes_list': "📋 Lista", 'weather': "🌍 Meteo", 'time': "⏰ Ora", 'games': "🎲 Giochi", 'games_dice': "🎲", 'games_coin': "🪙", 'games_joke': "😄", 'games_quote': "💭", 'games_fact': "🔬", 'vip': "💎 VIP", 'vip_reminders': "⏰ Promemoria", 'vip_stats': "📊 Stat", 'admin': "👑 Admin", 'admin_users': "👥", 'admin_stats': "📊", 'admin_broadcast': "📢", 'generate': "🖼️ Gen"},
        'info': "🤖 AI DISCO BOT\nAI: Llama 3.1 (API)\nDev: @Ernest_Kostevich",
        'status': "📊 Stato\nUtenti: {users}\nVIP: {vips}\nDB: {db_status}",
        'profile': "👤 {first_name}\nMsg: {msg_count}", 'profile_vip': "\nVIP fino: {date}", 'profile_vip_forever': "\nVIP: Sempre",
        'uptime': "⏱ Online da: {days}g {hours}o",
        'vip_status_active': "💎 VIP Attivo", 'vip_status_inactive': "💎 No VIP", 'vip_only': "💎 Solo VIP",
        'gen_prompt_needed': "❓ /generate [prompt]", 'gen_in_progress': "🎨 Disegno...", 'gen_caption': "🖼️ {prompt}", 'gen_error': "❌ Errore", 'gen_error_api': "❌ Errore API: {error}",
        'ai_typing': "typing", 'ai_error': "😔 Errore AI.",
        'note_prompt_needed': "❓ /note [testo]", 'note_saved': "✅ Salvato.", 'notes_empty': "📭 Vuoto.", 'notes_list_title': "📝 Note:", 'notes_list_item': "#{i} {text}\n",
        'delnote_prompt_needed': "❓ /delnote [num]", 'delnote_success': "✅ Eliminato.", 'delnote_not_found': "❌ Non trovato.",
        'todo_prompt_needed': "❓ /todo...", 'todo_saved': "✅ Aggiunto.", 'todo_empty': "📭 Vuoto.", 'todo_list_title': "📋 ToDo:", 'todo_list_item': "#{i} {text}\n",
        'weather_result': "🌍 {city}: {temp}°C", 'weather_city_not_found': "❌ Non trovato.",
        'time_result': "⏰ {city}: {time}", 'time_city_not_found': "❌ Non trovato.",
        'translate_prompt_needed': "❓ /translate [lang] [text]", 'translate_error': "❌ Errore.",
        'calc_result': "{result}", 'calc_error': "❌ Errore.",
        'password_result': "🔑 {password}", 'random_result': "🎲 {result}",
        'dice_result': "🎲 {result}", 'coin_result': "🪙 {result}", 'coin_heads': "Testa", 'coin_tails': "Croce",
        'joke_title': "😄 ", 'quote_title': "💭 ", 'fact_title': "🔬 ",
        'remind_success': "⏰ Impostato {minutes} min.", 'reminder_alert': "⏰ PROMEMORIA:\n{text}",
        'grant_vip_success': "✅ VIP concesso.", 'grant_vip_dm': "🎉 Hai il VIP!", 'duration_until': "fino {date}", 'duration_forever': "sempre",
        'revoke_vip_success': "✅ VIP revocato.",
        'broadcast_started': "📤 Invio...", 'broadcast_finished': "✅ Finito.", 'broadcast_dm': "📢 {text}",
        'backup_success': "✅ Backup ok.",
        'file_received': "📥 Leggo...", 'file_analyzing': "📄 File: {filename}\n\n{text}", 'file_error': "❌ Errore.",
        'photo_analyzing': "🔍 Analisi...", 'photo_result': "📸 Vision:\n{text}", 'photo_error': "❌ Errore.",
        'voice_transcribing': "🎙️ Ascolto...", 'voice_result': "📝 Testo:\n{text}", 'voice_error': "❌ Errore.",
        'error_generic': "❌ Errore: {error}", 'admin_only': "❌ Solo creatore."
    }
}

# --- ПОМОЩНИКИ ЛОКАЛИЗАЦИИ ---
def get_lang(user_id: int) -> str:
    user = storage.get_user(user_id)
    return user.get('language', 'ru')

def get_text(key: str, lang: str, **kwargs: Any) -> str:
    if lang not in localization_strings: lang = 'ru'
    try:
        keys = key.split('.')
        val = localization_strings[lang]
        for k in keys: val = val[k]
        if kwargs: return val.format(**kwargs)
        return val
    except:
        if lang != 'ru': return get_text(key, 'ru', **kwargs)
        return key

menu_button_map = {
    'chat': [get_text('main_keyboard.chat', l) for l in localization_strings],
    'notes': [get_text('main_keyboard.notes', l) for l in localization_strings],
    'weather': [get_text('main_keyboard.weather', l) for l in localization_strings],
    'time': [get_text('main_keyboard.time', l) for l in localization_strings],
    'games': [get_text('main_keyboard.games', l) for l in localization_strings],
    'info': [get_text('main_keyboard.info', l) for l in localization_strings],
    'vip_menu': [get_text('main_keyboard.vip_menu', l) for l in localization_strings],
    'admin_panel': [get_text('main_keyboard.admin_panel', l) for l in localization_strings],
    'generate': [get_text('main_keyboard.generate', l) for l in localization_strings],
}

# --- БАЗА ДАННЫХ ---
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
    language = Column(String(5), default='ru')

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

engine = None
Session = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        # Миграция (добавление колонки language если нет)
        try:
            inspector = inspect(engine)
            if inspector.has_table('users'):
                cols = [c['name'] for c in inspector.get_columns('users')]
                if 'language' not in cols:
                    with engine.connect() as conn:
                        conn.execute(sa_text("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru'"))
                        conn.commit()
        except: pass
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("✅ PostgreSQL Подключен")
    except Exception as e:
        logger.warning(f"⚠️ БД Ошибка: {e}. Использую JSON.")
else:
    logger.warning("⚠️ БД URL нет. Использую JSON.")

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'stats.json'
        self.users = {} if engine else self.load_json(self.users_file)
        self.stats = self.load_stats()
        self.username_to_id = {}
        self.update_username_mapping()

    def load_json(self, fn):
        try:
            with open(fn, 'r', encoding='utf-8') as f: return {int(k):v for k,v in json.load(f).items()}
        except: return {}

    def load_stats(self):
        if engine:
            sess = Session()
            try:
                res = sess.query(Statistics).filter_by(key='global').first()
                return res.value if res else {}
            except: return {}
            finally: sess.close()
        return self.load_json(self.stats_file)

    def save_stats(self):
        if engine:
            sess = Session()
            try:
                sess.merge(Statistics(key='global', value=self.stats, updated_at=datetime.now()))
                sess.commit()
            except: sess.rollback()
            finally: sess.close()
        else:
            with open(self.stats_file, 'w', encoding='utf-8') as f: json.dump(self.stats, f)

    def update_username_mapping(self):
        self.username_to_id = {}
        if not engine:
            for user_id, user_data in self.users.items():
                username = user_data.get('username')
                if username:
                    self.username_to_id[username.lower()] = user_id

    def get_user(self, user_id):
        if engine:
            sess = Session()
            try:
                u = sess.query(User).filter_by(id=user_id).first()
                if not u:
                    u = User(id=user_id, language='ru')
                    sess.add(u)
                    sess.commit()
                    u = sess.query(User).filter_by(id=user_id).first()
                return {
                    'id': u.id, 'username': u.username, 'first_name': u.first_name,
                    'vip': u.vip, 'vip_until': u.vip_until.isoformat() if u.vip_until else None,
                    'notes': u.notes, 'todos': u.todos, 'memory': u.memory, 'reminders': u.reminders,
                    'language': u.language or 'ru',
                    'messages_count': u.messages_count
                }
            finally: sess.close()
        else:
            if user_id not in self.users:
                self.users[user_id] = {'id': user_id, 'vip': False, 'notes': [], 'language': 'ru'}
            return self.users[user_id]

    def update_user(self, user_id, data):
        if engine:
            sess = Session()
            try:
                u = sess.query(User).filter_by(id=user_id).first()
                if not u: u = User(id=user_id); sess.add(u)
                for k,v in data.items():
                    if k == 'vip_until' and v: v = datetime.fromisoformat(v) if isinstance(v, str) else v
                    setattr(u, k, v)
                u.last_active = datetime.now()
                sess.commit()
            finally: sess.close()
        else:
            self.users[user_id].update(data)
            self.update_username_mapping()
            with open(self.users_file, 'w', encoding='utf-8') as f: json.dump(self.users, f, default=str)

    def is_vip(self, user_id):
        u = self.get_user(user_id)
        if not u.get('vip'): return False
        if u.get('vip_until'):
             if datetime.now() > datetime.fromisoformat(u['vip_until']):
                 self.update_user(user_id, {'vip': False, 'vip_until': None})
                 return False
        return True

    def save_chat(self, user_id, msg, resp):
        if engine:
            sess = Session()
            try:
                sess.add(Chat(user_id=user_id, message=msg[:1000], response=resp[:1000]))
                sess.commit()
            except: pass
            finally: sess.close()

    def get_all_users(self):
        if engine:
            sess = Session()
            try:
                return {u.id: {'id': u.id, 'first_name': u.first_name, 'vip': u.vip, 'username': u.username} for u in sess.query(User).all()}
            finally: sess.close()
        return self.users

    def get_user_id_by_identifier(self, ident):
        ident = ident.strip().replace('@', '').lower()
        if ident.isdigit(): return int(ident)
        if engine:
            sess = Session()
            try:
                u = sess.query(User).filter(User.username.ilike(f"%{ident}%")).first()
                return u.id if u else None
            finally: sess.close()
        return self.username_to_id.get(ident)

storage = DataStorage()
scheduler = AsyncIOScheduler()

# --- ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ (IMAGEN) ---
async def generate_image_imagen(prompt: str) -> Optional[bytes]:
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
    payload = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers={'Content-Type': 'application/json'}) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    if "predictions" in res and res["predictions"]:
                        b64 = res["predictions"][0]["bytesBase64Encoded"]
                        return base64.b64decode(b64)
    except Exception as e: logger.error(f"Imagen Error: {e}")
    return None

# --- УТИЛИТЫ VISUAL/AUDIO ---
async def analyze_image(img_bytes, prompt):
    if not vision_model: return "Vision model not configured."
    try:
        img = Image.open(io.BytesIO(img_bytes))
        res = vision_model.generate_content([prompt, img])
        return res.text
    except Exception as e: return f"Error: {e}"

async def transcribe_audio(audio_bytes):
    if not vision_model: return "Audio model not configured."
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
           temp_file.write(audio_bytes)
           temp_path = temp_file.name
        uploaded_file = genai.upload_file(path=temp_path, mime_type="audio/ogg")
        # Ждем обработки файла гуглом
        import time
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1)
            uploaded_file = genai.get_file(uploaded_file.name)
            
        response = vision_model.generate_content(["Transcribe this audio", uploaded_file])
        os.remove(temp_path)
        return response.text
    except Exception as e: return f"Error: {e}"

async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    try:
        ext = filename.lower().split('.')[-1]
        if ext == 'txt':
            try: return file_bytes.decode('utf-8')
            except: return file_bytes.decode('cp1251', errors='ignore')
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
        logger.warning(f"Doc Error: {e}")
        return f"❌ Error: {str(e)}"

# --- COMMAND HANDLERS ---
def identify_creator(user):
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None: CREATOR_ID = user.id

def is_creator(uid): return uid == CREATOR_ID

def get_main_kb(uid):
    l = get_lang(uid)
    kb = [
        [KeyboardButton(get_text('main_keyboard.chat', l)), KeyboardButton(get_text('main_keyboard.notes', l))],
        [KeyboardButton(get_text('main_keyboard.weather', l)), KeyboardButton(get_text('main_keyboard.time', l))],
        [KeyboardButton(get_text('main_keyboard.games', l)), KeyboardButton(get_text('main_keyboard.info', l))]
    ]
    if storage.is_vip(uid): kb.insert(0, [KeyboardButton(get_text('main_keyboard.vip_menu', l)), KeyboardButton(get_text('main_keyboard.generate', l))])
    if is_creator(uid): kb.append([KeyboardButton(get_text('main_keyboard.admin_panel', l))])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    identify_creator(u)
    storage.update_user(u.id, {'username': u.username, 'first_name': u.first_name})
    l = get_lang(u.id)
    await update.message.reply_text(get_text('welcome', l, first_name=u.first_name, creator=CREATOR_USERNAME), parse_mode=ParseMode.HTML, reply_markup=get_main_kb(u.id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    kb = []
    keys = ['help_basic', 'help_ai', 'help_memory', 'help_notes', 'help_todo', 'help_utils', 'help_games', 'help_vip']
    if is_creator(update.effective_user.id): keys.append('help_admin')
    for k in keys: kb.append([InlineKeyboardButton(get_text(f'help_sections.{k}', l), callback_data=k)])
    await update.message.reply_text(get_text('help_title', l), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang:ru")], [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")], [InlineKeyboardButton("🇮🇹 Italiano", callback_data="set_lang:it")]]
    await update.message.reply_text("Language / Язык:", reply_markup=InlineKeyboardMarkup(kb))

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    await update.message.reply_text(get_text('info', l), parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    stats = storage.stats
    all_users = storage.get_all_users()
    db_status = 'PostgreSQL ✓' if engine else 'JSON'
    await update.message.reply_text(get_text('status', l, users=len(all_users), vips=sum(1 for u in all_users.values() if u.get('vip')), db_status=db_status), parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    u = storage.get_user(uid)
    text = get_text('profile', l, first_name=u['first_name'], user_id=uid, msg_count=u.get('messages_count', 0))
    if storage.is_vip(uid):
        vip_until = u.get('vip_until')
        if vip_until: text += get_text('profile_vip', l, date=datetime.fromisoformat(vip_until).strftime('%d.%m.%Y'))
        else: text += get_text('profile_vip_forever', l)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# --- CORE AI LOGIC (UPDATED FOR API) ---
async def process_ai_message(update: Update, text: str, user_id: int, lang: str):
    try:
        await update.message.chat.send_action("typing")
        
        # ИСПОЛЬЗУЕМ НОВУЮ API ФУНКЦИЮ
        response_text = generate_with_your_model(text, lang=lang)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        storage.save_chat(user_id, text, response_text)
        
        # Разбивка длинных сообщений
        if len(response_text) > 4000:
            for x in range(0, len(response_text), 4000):
                await update.message.reply_text(response_text[x:x+4000], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)
            
    except Exception as e:
        logger.error(f"AI Handler Error: {e}")
        await update.message.reply_text(get_text('ai_error', lang))

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    await process_ai_message(update, ' '.join(context.args), update.effective_user.id, get_lang(update.effective_user.id))

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Context cleared.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    if not text: return
    
    identify_creator(update.effective_user)
    l = get_lang(uid)
    storage.update_user(uid, {'messages_count': storage.get_user(uid).get('messages_count', 0)+1})
    
    # Проверка меню
    for key, labels in menu_button_map.items():
        if text in labels:
            await handle_menu_button(update, context, key, l)
            return

    # AI Чат
    await process_ai_message(update, text, uid, l)

async def handle_menu_button(update, context, key, l):
    uid = update.effective_user.id
    if key == 'chat': await update.message.reply_text(get_text('menu.chat', l), parse_mode=ParseMode.HTML)
    elif key == 'notes': await update.message.reply_text(get_text('menu.notes', l), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕", callback_data="note_create"), InlineKeyboardButton("📋", callback_data="note_list")]]))
    elif key == 'games': await update.message.reply_text(get_text('menu.games', l), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎲", callback_data="game_dice"), InlineKeyboardButton("🪙", callback_data="game_coin"), InlineKeyboardButton("😄", callback_data="game_joke")]]))
    elif key == 'vip_menu':
        if storage.is_vip(uid): await update.message.reply_text(get_text('menu.vip', l), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏰", callback_data="vip_reminders"), InlineKeyboardButton("📊", callback_data="vip_stats")]]))
        else: await update.message.reply_text(get_text('vip_only', l))
    elif key == 'admin_panel' and is_creator(uid):
         await update.message.reply_text("Admin", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥", callback_data="admin_users"), InlineKeyboardButton("📢", callback_data="admin_broadcast"), InlineKeyboardButton("📊", callback_data="admin_stats")]]))
    elif key == 'generate':
         if storage.is_vip(uid): await update.message.reply_text(get_text('menu.generate', l))
         else: await update.message.reply_text(get_text('vip_only', l))
    elif key == 'info': await update.message.reply_text(get_text('info', l), parse_mode=ParseMode.HTML)
    elif key == 'weather': await update.message.reply_text(get_text('menu.weather', l))
    elif key == 'time': await update.message.reply_text(get_text('menu.time', l))

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    if not storage.is_vip(uid): return await update.message.reply_text(get_text('vip_only', l))
    if not context.args: return await update.message.reply_text(get_text('gen_prompt_needed', l))
    
    prompt = ' '.join(context.args)
    await update.message.reply_text(get_text('gen_in_progress', l))
    img_bytes = await generate_image_imagen(prompt)
    if img_bytes: await update.message.reply_photo(img_bytes, caption=get_text('gen_caption', l, prompt=prompt))
    else: await update.message.reply_text(get_text('gen_error', l))

# --- FUNCTIONALITY HANDLERS ---
async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    if not context.args: return await update.message.reply_text(get_text('note_prompt_needed', l))
    txt = ' '.join(context.args)
    u = storage.get_user(uid)
    notes = u.get('notes', [])
    notes.append({'text': txt, 'created': datetime.now().isoformat()})
    storage.update_user(uid, {'notes': notes})
    await update.message.reply_text(get_text('note_saved', l))

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    u = storage.get_user(uid)
    notes = u.get('notes', [])
    if not notes: return await update.message.reply_text(get_text('notes_empty', l))
    msg = get_text('notes_list_title', l)
    for i, n in enumerate(notes, 1): msg += get_text('notes_list_item', l, i=i, text=n['text'])
    await update.message.reply_text(msg)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    if not context.args: return await update.message.reply_text(get_text('delnote_prompt_needed', l))
    try:
        idx = int(context.args[0]) - 1
        u = storage.get_user(uid)
        notes = u.get('notes', [])
        if 0 <= idx < len(notes):
            notes.pop(idx)
            storage.update_user(uid, {'notes': notes})
            await update.message.reply_text(get_text('delnote_success', l))
        else: await update.message.reply_text(get_text('delnote_not_found', l))
    except: await update.message.reply_text("Error")

async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    if not context.args: return await update.message.reply_text(get_text('todo_prompt_needed', l))
    cmd = context.args[0].lower()
    u = storage.get_user(uid)
    todos = u.get('todos', [])
    
    if cmd == 'add' and len(context.args) > 1:
        todos.append({'text': ' '.join(context.args[1:]), 'created': datetime.now().isoformat()})
        storage.update_user(uid, {'todos': todos})
        await update.message.reply_text(get_text('todo_saved', l))
    elif cmd == 'list':
        if not todos: return await update.message.reply_text(get_text('todo_empty', l))
        msg = get_text('todo_list_title', l)
        for i, t in enumerate(todos, 1): msg += get_text('todo_list_item', l, i=i, text=t['text'])
        await update.message.reply_text(msg)
    elif cmd == 'del' and len(context.args) > 1:
        try:
            idx = int(context.args[1]) - 1
            if 0 <= idx < len(todos):
                todos.pop(idx)
                storage.update_user(uid, {'todos': todos})
                await update.message.reply_text("Deleted.")
            else: await update.message.reply_text("Not found.")
        except: await update.message.reply_text("Error")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    wttr_lang = 'it' if l == 'it' else 'en' if l == 'en' else 'ru'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://wttr.in/{urlquote(city)}?format=j1&lang={wttr_lang}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cur = data['current_condition'][0]
                    desc = cur[f'weatherDesc_{wttr_lang}'][0]['value'] if f'weatherDesc_{wttr_lang}' in cur else cur['weatherDesc'][0]['value']
                    await update.message.reply_text(get_text('weather_result', l, city=city, temp=cur['temp_C'], desc=desc))
                else: await update.message.reply_text(get_text('weather_city_not_found', l))
    except: await update.message.reply_text("Error")

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    try:
        # Simple lookup logic (placeholder for complex timezone logic)
        tz = pytz.timezone('Europe/Moscow') 
        if 'london' in city.lower(): tz = pytz.timezone('Europe/London')
        elif 'new york' in city.lower(): tz = pytz.timezone('America/New_York')
        elif 'tokyo' in city.lower(): tz = pytz.timezone('Asia/Tokyo')
        
        curr = datetime.now(tz)
        await update.message.reply_text(get_text('time_result', l, city=city, time=curr.strftime('%H:%M')))
    except: await update.message.reply_text(get_text('time_city_not_found', l))

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    if len(context.args) < 2: return await update.message.reply_text(get_text('translate_prompt_needed', l))
    prompt = f"Translate to {context.args[0]}: {' '.join(context.args[1:])}"
    await process_ai_message(update, prompt, update.effective_user.id, l)

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    if not context.args: return
    expr = ''.join(context.args)
    allowed = "0123456789.+-*/()"
    if not all(c in allowed for c in expr): return await update.message.reply_text(get_text('calc_error', l))
    try:
        res = eval(expr, {"__builtins__": {}}, {})
        await update.message.reply_text(get_text('calc_result', l, expr=expr, result=res))
    except: await update.message.reply_text(get_text('calc_error', l))

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    length = int(context.args[0]) if context.args else 12
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(get_text('password_result', l, password=pwd), parse_mode=ParseMode.HTML)

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    r = random.randint(1, 6)
    await update.message.reply_text(get_text('dice_result', l, result=r))

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    r = random.choice(['coin_heads', 'coin_tails'])
    await update.message.reply_text(get_text('coin_result', l, result=get_text(r, l)))

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    await update.message.reply_text(get_text('joke_title', l) + "Why do programmers prefer dark mode? Because light attracts bugs!")

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    await update.message.reply_text(get_text('quote_title', l) + "Talk is cheap. Show me the code.")

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = get_lang(update.effective_user.id)
    await update.message.reply_text(get_text('fact_title', l) + "The first computer bug was an actual real bug (a moth).")

# --- VIP & ADMIN ---
async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    if not storage.is_vip(uid): return await update.message.reply_text(get_text('vip_only', l))
    if len(context.args) < 2: return
    try:
        mins = int(context.args[0])
        txt = ' '.join(context.args[1:])
        rem_time = datetime.now() + timedelta(minutes=mins)
        u = storage.get_user(uid)
        rems = u.get('reminders', [])
        rems.append({'text': txt, 'time': rem_time.isoformat(), 'lang': l})
        storage.update_user(uid, {'reminders': rems})
        scheduler.add_job(send_reminder, 'date', run_date=rem_time, args=[context.bot, uid, txt, l])
        await update.message.reply_text(get_text('remind_success', l, minutes=mins))
    except: await update.message.reply_text("Error")

async def send_reminder(bot, uid, txt, l):
    await bot.send_message(uid, get_text('reminder_alert', l, text=txt), parse_mode=ParseMode.HTML)

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    u = storage.get_user(uid)
    rems = u.get('reminders', [])
    if not rems: return await update.message.reply_text("No reminders.")
    msg = "Reminders:\n"
    for i, r in enumerate(rems, 1): msg += f"{i}. {r['text']} ({r['time']})\n"
    await update.message.reply_text(msg)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    status = get_text('vip_status_active', l) if storage.is_vip(uid) else get_text('vip_status_inactive', l)
    await update.message.reply_text(status)

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    try:
        target = int(context.args[0]) if context.args[0].isdigit() else storage.get_user_id_by_identifier(context.args[0])
        if target:
            storage.update_user(target, {'vip': True, 'vip_until': None})
            await update.message.reply_text(get_text('grant_vip_success', 'ru'))
            try: await context.bot.send_message(target, get_text('grant_vip_dm', get_lang(target)))
            except: pass
    except: await update.message.reply_text("Error")

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    try:
        target = int(context.args[0]) if context.args[0].isdigit() else storage.get_user_id_by_identifier(context.args[0])
        if target:
            storage.update_user(target, {'vip': False, 'vip_until': None})
            await update.message.reply_text(get_text('revoke_vip_success', 'ru'))
    except: await update.message.reply_text("Error")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    users = storage.get_all_users()
    msg = f"Users ({len(users)}):\n"
    for uid, u in users.items(): msg += f"{uid} - {u.get('first_name')} {'💎' if u.get('vip') else ''}\n"
    if len(msg) > 4000: msg = msg[:4000]
    await update.message.reply_text(msg)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    txt = ' '.join(context.args)
    if not txt: return
    await update.message.reply_text(get_text('broadcast_started', 'ru'))
    count = 0
    for uid in storage.get_all_users():
        try:
            await context.bot.send_message(uid, get_text('broadcast_dm', get_lang(uid), text=txt), parse_mode=ParseMode.HTML)
            count += 1
        except: pass
    await update.message.reply_text(get_text('broadcast_finished', 'ru') + f" ({count})")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    s = storage.stats
    await update.message.reply_text(f"AI Requests: {s.get('ai_requests', 0)}")

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update.effective_user.id): return
    try:
        fn = 'backup.json'
        with open(fn, 'w') as f: json.dump({'users': storage.get_all_users(), 'stats': storage.stats}, f)
        await update.message.reply_document(document=open(fn, 'rb'), caption=get_text('backup_success', 'ru'))
        os.remove(fn)
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id
    l = get_lang(uid)

    if data.startswith("set_lang:"):
        lang_code = data.split(":")[1]
        storage.update_user(uid, {'language': lang_code})
        await q.edit_message_text(get_text('lang_changed', lang_code))
        await q.message.reply_text(get_text('welcome', lang_code, first_name=q.from_user.first_name, creator=CREATOR_USERNAME), reply_markup=get_main_kb(uid), parse_mode=ParseMode.HTML)
        return

    if data in localization_strings['ru']['help_text']:
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_text('help_back', l), callback_data="help_back")]])
        await q.edit_message_text(get_text(f'help_text.{data}', l), reply_markup=back_kb)
    elif data == "help_back":
        await help_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    
    # Menu Button Handlers
    elif data == "note_create": await q.message.reply_text(get_text('note_prompt_needed', l))
    elif data == "note_list": await notes_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    
    elif data == "game_dice": await dice_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    elif data == "game_coin": await coin_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    elif data == "game_joke": await joke_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    
    elif data == "vip_reminders": await reminders_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    elif data == "vip_stats": await profile_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    
    elif data == "admin_users": await users_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)
    elif data == "admin_broadcast": await q.message.reply_text("/broadcast [text]")
    elif data == "admin_stats": await stats_command(Update(update.update_id, message=q.message, effective_user=q.from_user), context)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    if not storage.is_vip(uid): return await update.message.reply_text(get_text('vip_only', l))
    await update.message.reply_text(get_text('photo_analyzing', l))
    try:
        ph = await update.message.photo[-1].get_file()
        byte_arr = await ph.download_as_bytearray()
        res = await analyze_image(bytes(byte_arr), "Describe this image in detail")
        await update.message.reply_text(get_text('photo_result', l, text=res), parse_mode=ParseMode.HTML)
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    if not storage.is_vip(uid): return await update.message.reply_text(get_text('vip_only', l))
    await update.message.reply_text(get_text('file_received', l))
    try:
        doc = update.message.document
        f = await doc.get_file()
        byte_arr = await f.download_as_bytearray()
        text = await extract_text_from_document(bytes(byte_arr), doc.file_name)
        # Analyze with Llama (API)
        analysis = generate_with_your_model(f"Analyze this document content:\n\n{text[:2000]}", lang=l)
        await update.message.reply_text(get_text('file_analyzing', l, filename=doc.file_name, text=analysis), parse_mode=ParseMode.HTML)
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = get_lang(uid)
    await update.message.reply_text(get_text('voice_transcribing', l))
    try:
        v = await update.message.voice.get_file()
        byte_arr = await v.download_as_bytearray()
        text = await transcribe_audio(bytes(byte_arr))
        await update.message.reply_text(get_text('voice_result', l, text=text), parse_mode=ParseMode.HTML)
        # Send to Llama for response
        await process_ai_message(update, text, uid, l)
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) < 2: return
    k, v = context.args[0], ' '.join(context.args[1:])
    u = storage.get_user(uid)
    mem = u.get('memory', {})
    mem[k] = v
    storage.update_user(uid, {'memory': mem})
    await update.message.reply_text(f"Saved: {k}")

async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args: return
    k = context.args[0]
    u = storage.get_user(uid)
    val = u.get('memory', {}).get(k, "Not found")
    await update.message.reply_text(f"{k}: {val}")

async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = storage.get_user(uid)
    mem = u.get('memory', {})
    msg = "Memory:\n" + "\n".join([f"{k}: {v}" for k,v in mem.items()])
    await update.message.reply_text(msg)

async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args: return
    k = context.args[0]
    u = storage.get_user(uid)
    mem = u.get('memory', {})
    if k in mem:
        del mem[k]
        storage.update_user(uid, {'memory': mem})
        await update.message.reply_text("Deleted")
    else: await update.message.reply_text("Not found")

# --- MAIN ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Core Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("profile", profile_command))
    
    # AI
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("clear", clear_command))
    
    # Utils
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("delnote", delnote_command))
    app.add_handler(CommandHandler("todo", todo_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("translate", translate_command))
    app.add_handler(CommandHandler("calc", calc_command))
    app.add_handler(CommandHandler("password", password_command))
    
    # Memory
    app.add_handler(CommandHandler("memorysave", memory_save_command))
    app.add_handler(CommandHandler("memoryget", memory_get_command))
    app.add_handler(CommandHandler("memorylist", memory_list_command))
    app.add_handler(CommandHandler("memorydel", memory_del_command))

    # Games
    app.add_handler(CommandHandler("dice", dice_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("joke", joke_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("fact", fact_command))

    # VIP
    app.add_handler(CommandHandler("vip", vip_command))
    app.add_handler(CommandHandler("generate", generate_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))

    # Admin
    app.add_handler(CommandHandler("grant_vip", grant_vip_command))
    app.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("backup", backup_command))

    # Messages & Files
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_callback))

    scheduler.start()
    
    logger.info("🚀 БОТ ЗАПУЩЕН (Hugging Face API + Gemini Vision)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
