#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI DISCO BOT v3.3 - EXTENDED
Новое:
1. Единый контекст для текста/фото/голоса/документов
2. Расширенные функции для групп и каналов
3. VIP для чатов
4. Модерация и управление группами
"""

import os, json, logging, random, asyncio, io, base64, tempfile
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
import pytz
from urllib.parse import quote as urlquote

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ChatMemberHandler
from telegram.constants import ParseMode, ChatMemberStatus

import google.generativeai as genai
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PIL import Image
import fitz
import docx

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger, inspect, text as sa_text
from sqlalchemy.orm import sessionmaker, declarative_base

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("BOT_TOKEN или GEMINI_API_KEY не установлены!")

# === GEMINI ===
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {"temperature": 1, "top_p": 0.95, "top_k": 40, "max_output_tokens": 2048}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

text_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction="Ты — AI DISCO BOT на Gemini 2.5. Отвечай на языке пользователя, дружелюбно. Максимум 4000 символов. Создатель: @Ernest_Kostevich"
)

vision_model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings
)

scheduler = AsyncIOScheduler()


# === ЕДИНЫЙ КОНТЕКСТ ===
class UnifiedContext:
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.sessions: Dict[int, List[Dict]] = {}
    
    def get_history(self, user_id: int) -> List[Dict]:
        if user_id not in self.sessions:
            self.sessions[user_id] = []
        return self.sessions[user_id]
    
    def add_user_message(self, user_id: int, content: Any):
        history = self.get_history(user_id)
        parts = content if isinstance(content, list) else [content]
        history.append({"role": "user", "parts": parts})
        if len(history) > self.max_history * 2:
            self.sessions[user_id] = history[-self.max_history * 2:]
    
    def add_bot_message(self, user_id: int, content: str):
        self.get_history(user_id).append({"role": "model", "parts": [content]})
    
    def clear(self, user_id: int):
        if user_id in self.sessions:
            del self.sessions[user_id]
    
    def get_text_history(self, user_id: int) -> List[Dict]:
        history = self.get_history(user_id)
        result = []
        for i, msg in enumerate(history):
            if i < len(history) - 4:
                text_parts = [p for p in msg["parts"] if isinstance(p, str)]
                if text_parts:
                    result.append({"role": msg["role"], "parts": text_parts})
            else:
                result.append(msg)
        return result

unified_ctx = UnifiedContext()


# === НАСТРОЙКИ ГРУПП ===
group_settings: Dict[int, Dict] = {}  # chat_id -> settings


# === ЛОКАЛИЗАЦИЯ ===
L = {
    'ru': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nПривет, {name}! Я бот на <b>Gemini 2.5</b>.\n\n<b>Возможности:</b>\n💬 AI-чат с контекстом\n📝 Заметки\n🌍 Погода/время\n🎲 Развлечения\n📎 Анализ файлов (VIP)\n🔍 Анализ фото (VIP)\n🖼️ Генерация картинок (VIP)\n\n/help - команды\n/language - язык\n\n👨‍💻 @{creator}",
        'lang_changed': "✅ Язык: Русский 🇷🇺",
        'lang_choose': "Выберите язык:",
        'help': "📚 <b>Команды:</b>\n\n<b>Основные:</b>\n/start /help /info /status /profile\n/language /clear\n\n<b>AI:</b>\n/ai [вопрос] - спросить AI\nПросто пишите - бот ответит\n\n<b>Заметки:</b>\n/note [текст] /notes /delnote [№]\n\n<b>Утилиты:</b>\n/time [город] /weather [город]\n/calc [выражение] /password [длина]\n\n<b>Игры:</b>\n/dice /coin /joke /quote /fact /random\n\n<b>VIP:</b>\n/vip /generate [описание]\n/remind [мин] [текст] /reminders\n📎 Отправь файл/фото - анализ\n\n<b>Группы:</b>\n/grouphelp - команды для групп\n\n<b>Админ:</b>\n/grant_vip /revoke_vip /users /broadcast /stats",
        'info': "🤖 <b>AI DISCO BOT v3.3</b>\n\nAI: Gemini 2.5 Flash\nКонтекст: Единый (текст+фото+голос)\nБД: {db}\n\n👨‍💻 @Ernest_Kostevich",
        'status': "📊 <b>Статус</b>\n\n👥 Юзеров: {users}\n💎 VIP: {vips}\n📨 Сообщений: {msgs}\n🤖 AI запросов: {ai}\n⏱ Аптайм: {days}д {hours}ч\n✅ Онлайн",
        'profile': "👤 <b>{name}</b>\n🆔 <code>{id}</code>\n📊 Сообщений: {msgs}\n📝 Заметок: {notes}",
        'profile_vip': "\n💎 VIP до: {date}",
        'profile_vip_forever': "\n💎 VIP: Навсегда ♾️",
        'vip_active': "💎 <b>VIP активен!</b>\n\n{until}\n\n🎁 Бонусы:\n• Анализ фото/файлов\n• Генерация картинок\n• Напоминания\n• AI в группах без ограничений",
        'vip_until': "⏰ До: {date}",
        'vip_forever': "⏰ Навсегда ♾️",
        'vip_inactive': "💎 <b>VIP не активен</b>\n\nСвяжитесь с @Ernest_Kostevich",
        'vip_only': "💎 Только для VIP. Свяжитесь с @Ernest_Kostevich",
        'admin_only': "❌ Только для создателя",
        'clear': "🧹 Контекст очищен!",
        'ai_error': "😔 Ошибка AI, попробуйте снова",
        'photo_analyzing': "🔍 Анализирую...",
        'photo_result': "📸 <b>Ответ:</b>\n\n{text}",
        'photo_error': "❌ Ошибка: {e}",
        'voice_transcribing': "🎙️ Распознаю голос...",
        'voice_result': "🎙️ <b>Вы:</b> <i>{text}</i>\n\n🤖 <b>Ответ:</b>\n\n{response}",
        'voice_error': "❌ Ошибка голоса: {e}",
        'file_analyzing': "📥 Анализирую файл...",
        'file_result': "📄 <b>{name}</b>\n\n🤖 {text}",
        'file_error': "❌ Ошибка файла: {e}",
        'gen_prompt': "❓ /generate [описание]\n\nПример: /generate закат над океаном",
        'gen_progress': "🎨 Генерирую...",
        'gen_done': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Ошибка генерации",
        'note_saved': "✅ Заметка #{n} сохранена",
        'note_prompt': "❓ /note [текст]",
        'notes_empty': "📭 Нет заметок",
        'notes_list': "📝 <b>Заметки ({n}):</b>\n\n{list}",
        'delnote_ok': "✅ Заметка #{n} удалена",
        'delnote_err': "❌ Заметка не найдена",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 {time}\n📅 {date}\n🌍 {tz}",
        'time_error': "❌ Город не найден",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 {temp}°C (ощущается {feels}°C)\n☁️ {desc}\n💧 {humidity}%\n💨 {wind} км/ч",
        'weather_error': "❌ Ошибка погоды",
        'calc_result': "🧮 {expr} = <b>{result}</b>",
        'calc_error': "❌ Ошибка вычисления",
        'password_result': "🔑 <code>{pwd}</code>",
        'random_result': "🎲 {min}-{max}: <b>{r}</b>",
        'dice_result': "🎲 Выпало: <b>{r}</b>",
        'coin_heads': "Орёл 🦅",
        'coin_tails': "Решка 💰",
        'remind_ok': "⏰ Напоминание через {m} мин:\n📝 {text}",
        'remind_prompt': "❓ /remind [минуты] [текст]",
        'remind_alert': "⏰ <b>НАПОМИНАНИЕ</b>\n\n📝 {text}",
        'reminders_empty': "📭 Нет напоминаний",
        'reminders_list': "⏰ <b>Напоминания ({n}):</b>\n\n{list}",
        'grant_ok': "✅ VIP выдан: {id}\n⏰ {dur}",
        'grant_prompt': "❓ /grant_vip [id/@username/chat_id] [week/month/year/forever]",
        'revoke_ok': "✅ VIP отозван: {id}",
        'users_list': "👥 <b>Юзеры ({n}):</b>\n\n{list}",
        'broadcast_start': "📤 Рассылка...",
        'broadcast_done': "✅ Отправлено: {ok}, ошибок: {err}",
        'broadcast_prompt': "❓ /broadcast [текст]",
        'joke': "😄 <b>Шутка:</b>\n\n{text}",
        'quote': "💭 <b>Цитата:</b>\n\n<i>{text}</i>",
        'fact': "🔬 <b>Факт:</b>\n\n{text}",
        'menu_chat': "💬 Чат",
        'menu_notes': "📝 Заметки",
        'menu_weather': "🌍 Погода",
        'menu_time': "⏰ Время",
        'menu_games': "🎲 Игры",
        'menu_info': "ℹ️ Инфо",
        'menu_vip': "💎 VIP",
        'menu_gen': "🖼️ Генерация",
        'menu_admin': "👑 Админ",
        # Групповые сообщения
        'group_help': "👥 <b>Команды для групп:</b>\n\n<b>Модерация (админы):</b>\n/ban - забанить (ответом)\n/unban - разбанить\n/kick - кикнуть\n/mute [мин] - мут\n/unmute - размут\n/warn - предупреждение\n/unwarn - снять варн\n/warns - список варнов\n\n<b>Настройки (админы):</b>\n/setwelcome [текст] - приветствие\n/welcomeoff - выкл. приветствие\n/setrules [текст] - правила\n/setai [on/off] - вкл/выкл AI\n\n<b>Инфо:</b>\n/rules - правила\n/chatinfo - инфо о чате\n/top - топ активных\n\n<b>AI:</b>\n@{bot} [вопрос] - спросить AI\n/ai [вопрос] - спросить AI",
        'group_welcome': "👋 Добро пожаловать, {name}!\n\n{custom}",
        'group_welcome_default': "Я AI DISCO BOT - умный помощник для этого чата!",
        'chat_vip_active': "💎 <b>VIP чат!</b>\n\nAI доступен всем участникам без ограничений.",
        'chat_vip_inactive': "ℹ️ Для безлимитного AI в группе нужен VIP.\n\nАдмин может получить VIP: @Ernest_Kostevich",
        'user_banned': "🚫 {name} забанен!",
        'user_unbanned': "✅ Пользователь разбанен!",
        'user_kicked': "👢 {name} кикнут!",
        'user_muted': "🔇 {name} замьючен на {mins} мин!",
        'user_unmuted': "🔊 {name} размьючен!",
        'user_warned': "⚠️ {name} получил предупреждение!\nВсего: {count}/3",
        'user_warn_removed': "✅ Предупреждение снято с {name}\nОсталось: {count}",
        'user_warn_ban': "🚫 {name} забанен за 3 предупреждения!",
        'warns_list': "⚠️ <b>Предупреждения {name}:</b> {count}/3",
        'warns_empty': "✅ У {name} нет предупреждений",
        'rules_set': "✅ Правила установлены!",
        'rules_text': "📜 <b>Правила чата:</b>\n\n{rules}",
        'rules_empty': "📜 Правила не установлены",
        'welcome_set': "✅ Приветствие установлено!",
        'welcome_off': "✅ Приветствие выключено",
        'ai_enabled': "✅ AI включен для группы",
        'ai_disabled': "❌ AI выключен для группы",
        'need_admin': "❌ Нужны права админа!",
        'need_reply': "❌ Ответьте на сообщение пользователя!",
        'chat_info': "📊 <b>Информация о чате</b>\n\n🆔 ID: <code>{id}</code>\n📛 Название: {title}\n👥 Участников: {members}\n💎 VIP: {vip}\n🤖 AI: {ai}",
        'top_users': "🏆 <b>Топ активных:</b>\n\n{list}",
    },
    'en': {
        'welcome': "🤖 <b>AI DISCO BOT</b>\n\nHi, {name}! I'm a <b>Gemini 2.5</b> bot.\n\n<b>Features:</b>\n💬 AI chat with context\n📝 Notes\n🌍 Weather/time\n🎲 Games\n📎 File analysis (VIP)\n🔍 Photo analysis (VIP)\n🖼️ Image generation (VIP)\n\n/help - commands\n/language - language\n\n👨‍💻 @{creator}",
        'lang_changed': "✅ Language: English 🇬🇧",
        'lang_choose': "Choose language:",
        'help': "📚 <b>Commands:</b>\n\n<b>Basic:</b>\n/start /help /info /status /profile\n/language /clear\n\n<b>AI:</b>\n/ai [question] - ask AI\nJust type - bot will answer\n\n<b>Notes:</b>\n/note [text] /notes /delnote [#]\n\n<b>Utils:</b>\n/time [city] /weather [city]\n/calc [expr] /password [len]\n\n<b>Games:</b>\n/dice /coin /joke /quote /fact /random\n\n<b>VIP:</b>\n/vip /generate [prompt]\n/remind [min] [text] /reminders\n📎 Send file/photo - analysis\n\n<b>Groups:</b>\n/grouphelp - group commands\n\n<b>Admin:</b>\n/grant_vip /revoke_vip /users /broadcast /stats",
        'info': "🤖 <b>AI DISCO BOT v3.3</b>\n\nAI: Gemini 2.5 Flash\nContext: Unified (text+photo+voice)\nDB: {db}\n\n👨‍💻 @Ernest_Kostevich",
        'status': "📊 <b>Status</b>\n\n👥 Users: {users}\n💎 VIP: {vips}\n📨 Messages: {msgs}\n🤖 AI requests: {ai}\n⏱ Uptime: {days}d {hours}h\n✅ Online",
        'profile': "👤 <b>{name}</b>\n🆔 <code>{id}</code>\n📊 Messages: {msgs}\n📝 Notes: {notes}",
        'profile_vip': "\n💎 VIP until: {date}",
        'profile_vip_forever': "\n💎 VIP: Forever ♾️",
        'vip_active': "💎 <b>VIP active!</b>\n\n{until}\n\n🎁 Perks:\n• Photo/file analysis\n• Image generation\n• Reminders\n• Unlimited AI in groups",
        'vip_until': "⏰ Until: {date}",
        'vip_forever': "⏰ Forever ♾️",
        'vip_inactive': "💎 <b>No VIP</b>\n\nContact @Ernest_Kostevich",
        'vip_only': "💎 VIP only. Contact @Ernest_Kostevich",
        'admin_only': "❌ Creator only",
        'clear': "🧹 Context cleared!",
        'ai_error': "😔 AI error, try again",
        'photo_analyzing': "🔍 Analyzing...",
        'photo_result': "📸 <b>Response:</b>\n\n{text}",
        'photo_error': "❌ Error: {e}",
        'voice_transcribing': "🎙️ Transcribing...",
        'voice_result': "🎙️ <b>You:</b> <i>{text}</i>\n\n🤖 <b>Response:</b>\n\n{response}",
        'voice_error': "❌ Voice error: {e}",
        'file_analyzing': "📥 Analyzing file...",
        'file_result': "📄 <b>{name}</b>\n\n🤖 {text}",
        'file_error': "❌ File error: {e}",
        'gen_prompt': "❓ /generate [prompt]\n\nExample: /generate sunset over ocean",
        'gen_progress': "🎨 Generating...",
        'gen_done': "🖼️ <b>{prompt}</b>\n\n💎 VIP | Imagen 3",
        'gen_error': "❌ Generation error",
        'note_saved': "✅ Note #{n} saved",
        'note_prompt': "❓ /note [text]",
        'notes_empty': "📭 No notes",
        'notes_list': "📝 <b>Notes ({n}):</b>\n\n{list}",
        'delnote_ok': "✅ Note #{n} deleted",
        'delnote_err': "❌ Note not found",
        'time_result': "⏰ <b>{city}</b>\n\n🕐 {time}\n📅 {date}\n🌍 {tz}",
        'time_error': "❌ City not found",
        'weather_result': "🌍 <b>{city}</b>\n\n🌡 {temp}°C (feels {feels}°C)\n☁️ {desc}\n💧 {humidity}%\n💨 {wind} km/h",
        'weather_error': "❌ Weather error",
        'calc_result': "🧮 {expr} = <b>{result}</b>",
        'calc_error': "❌ Calc error",
        'password_result': "🔑 <code>{pwd}</code>",
        'random_result': "🎲 {min}-{max}: <b>{r}</b>",
        'dice_result': "🎲 Rolled: <b>{r}</b>",
        'coin_heads': "Heads 🦅",
        'coin_tails': "Tails 💰",
        'remind_ok': "⏰ Reminder in {m} min:\n📝 {text}",
        'remind_prompt': "❓ /remind [minutes] [text]",
        'remind_alert': "⏰ <b>REMINDER</b>\n\n📝 {text}",
        'reminders_empty': "📭 No reminders",
        'reminders_list': "⏰ <b>Reminders ({n}):</b>\n\n{list}",
        'grant_ok': "✅ VIP granted: {id}\n⏰ {dur}",
        'grant_prompt': "❓ /grant_vip [id/@username/chat_id] [week/month/year/forever]",
        'revoke_ok': "✅ VIP revoked: {id}",
        'users_list': "👥 <b>Users ({n}):</b>\n\n{list}",
        'broadcast_start': "📤 Broadcasting...",
        'broadcast_done': "✅ Sent: {ok}, errors: {err}",
        'broadcast_prompt': "❓ /broadcast [text]",
        'joke': "😄 <b>Joke:</b>\n\n{text}",
        'quote': "💭 <b>Quote:</b>\n\n<i>{text}</i>",
        'fact': "🔬 <b>Fact:</b>\n\n{text}",
        'menu_chat': "💬 Chat",
        'menu_notes': "📝 Notes",
        'menu_weather': "🌍 Weather",
        'menu_time': "⏰ Time",
        'menu_games': "🎲 Games",
        'menu_info': "ℹ️ Info",
        'menu_vip': "💎 VIP",
        'menu_gen': "🖼️ Generate",
        'menu_admin': "👑 Admin",
        # Group messages
        'group_help': "👥 <b>Group commands:</b>\n\n<b>Moderation (admins):</b>\n/ban - ban (reply)\n/unban - unban\n/kick - kick\n/mute [min] - mute\n/unmute - unmute\n/warn - warning\n/unwarn - remove warn\n/warns - warns list\n\n<b>Settings (admins):</b>\n/setwelcome [text] - welcome msg\n/welcomeoff - disable welcome\n/setrules [text] - rules\n/setai [on/off] - enable/disable AI\n\n<b>Info:</b>\n/rules - rules\n/chatinfo - chat info\n/top - top active\n\n<b>AI:</b>\n@{bot} [question] - ask AI\n/ai [question] - ask AI",
        'group_welcome': "👋 Welcome, {name}!\n\n{custom}",
        'group_welcome_default': "I'm AI DISCO BOT - smart assistant for this chat!",
        'chat_vip_active': "💎 <b>VIP chat!</b>\n\nAI available for all members without limits.",
        'chat_vip_inactive': "ℹ️ For unlimited AI in group you need VIP.\n\nAdmin can get VIP: @Ernest_Kostevich",
        'user_banned': "🚫 {name} banned!",
        'user_unbanned': "✅ User unbanned!",
        'user_kicked': "👢 {name} kicked!",
        'user_muted': "🔇 {name} muted for {mins} min!",
        'user_unmuted': "🔊 {name} unmuted!",
        'user_warned': "⚠️ {name} warned!\nTotal: {count}/3",
        'user_warn_removed': "✅ Warning removed from {name}\nLeft: {count}",
        'user_warn_ban': "🚫 {name} banned for 3 warnings!",
        'warns_list': "⚠️ <b>Warnings {name}:</b> {count}/3",
        'warns_empty': "✅ {name} has no warnings",
        'rules_set': "✅ Rules set!",
        'rules_text': "📜 <b>Chat rules:</b>\n\n{rules}",
        'rules_empty': "📜 No rules set",
        'welcome_set': "✅ Welcome message set!",
        'welcome_off': "✅ Welcome disabled",
        'ai_enabled': "✅ AI enabled for group",
        'ai_disabled': "❌ AI disabled for group",
        'need_admin': "❌ Admin rights required!",
        'need_reply': "❌ Reply to user's message!",
        'chat_info': "📊 <b>Chat Info</b>\n\n🆔 ID: <code>{id}</code>\n📛 Title: {title}\n👥 Members: {members}\n💎 VIP: {vip}\n🤖 AI: {ai}",
        'top_users': "🏆 <b>Top active:</b>\n\n{list}",
    }
}

def t(key: str, lang: str, **kw) -> str:
    txt = L.get(lang, L['ru']).get(key, L['ru'].get(key, key))
    return txt.format(**kw) if kw else txt


# === БАЗА ДАННЫХ ===
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    notes = Column(JSON, default=list)
    reminders = Column(JSON, default=list)
    memory = Column(JSON, default=dict)
    registered = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    messages_count = Column(Integer, default=0)
    commands_count = Column(Integer, default=0)
    language = Column(String(5), default='ru')

class Chat(Base):
    __tablename__ = 'chats'
    id = Column(BigInteger, primary_key=True)
    title = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    welcome_text = Column(Text)
    welcome_enabled = Column(Boolean, default=True)
    rules = Column(Text)
    ai_enabled = Column(Boolean, default=True)
    warns = Column(JSON, default=dict)  # user_id -> count
    settings = Column(JSON, default=dict)
    messages_count = Column(Integer, default=0)
    top_users = Column(JSON, default=dict)  # user_id -> count

class Statistics(Base):
    __tablename__ = 'statistics'
    key = Column(String(50), primary_key=True)
    value = Column(JSON)

engine = None
Session = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
        try:
            insp = inspect(engine)
            if insp.has_table('users'):
                cols = [c['name'] for c in insp.get_columns('users')]
                if 'language' not in cols:
                    with engine.connect() as conn:
                        conn.execute(sa_text("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru'"))
                        conn.commit()
        except: pass
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("✅ PostgreSQL подключен!")
    except Exception as e:
        logger.warning(f"⚠️ DB error: {e}")
        engine = None


# === ХРАНИЛИЩЕ ===
class Storage:
    def __init__(self):
        self.stats = self._load_stats()
    
    def _load_stats(self):
        if engine:
            try:
                s = Session()
                st = s.query(Statistics).filter_by(key='global').first()
                s.close()
                return st.value if st else {}
            except: pass
        return {'total_messages': 0, 'ai_requests': 0}
    
    def save_stats(self):
        if engine:
            try:
                s = Session()
                s.merge(Statistics(key='global', value=self.stats))
                s.commit()
                s.close()
            except: pass
    
    def get_user(self, uid: int) -> Dict:
        if engine:
            s = Session()
            try:
                u = s.query(User).filter_by(id=uid).first()
                if not u:
                    u = User(id=uid)
                    s.add(u)
                    s.commit()
                return {
                    'id': u.id, 'username': u.username or '', 'first_name': u.first_name or '',
                    'vip': u.vip, 'vip_until': u.vip_until.isoformat() if u.vip_until else None,
                    'notes': u.notes or [], 'reminders': u.reminders or [], 'memory': u.memory or {},
                    'messages_count': u.messages_count or 0, 'language': u.language or 'ru'
                }
            except: return {'id': uid, 'language': 'ru'}
            finally: s.close()
        return {'id': uid, 'language': 'ru', 'notes': [], 'reminders': [], 'messages_count': 0}
    
    def update_user(self, uid: int, data: Dict):
        if engine:
            s = Session()
            try:
                u = s.query(User).filter_by(id=uid).first()
                if not u:
                    u = User(id=uid)
                    s.add(u)
                for k, v in data.items():
                    if k == 'vip_until' and v and isinstance(v, str):
                        v = datetime.fromisoformat(v)
                    setattr(u, k, v)
                u.last_active = datetime.now()
                s.commit()
            except: s.rollback()
            finally: s.close()
    
    def is_vip(self, uid: int) -> bool:
        u = self.get_user(uid)
        if not u.get('vip'): return False
        vu = u.get('vip_until')
        if not vu: return True
        try:
            if datetime.now() > datetime.fromisoformat(vu):
                self.update_user(uid, {'vip': False, 'vip_until': None})
                return False
            return True
        except: return True
    
    # === ЧАТЫ ===
    def get_chat(self, chat_id: int) -> Dict:
        if engine:
            s = Session()
            try:
                c = s.query(Chat).filter_by(id=chat_id).first()
                if not c:
                    c = Chat(id=chat_id)
                    s.add(c)
                    s.commit()
                return {
                    'id': c.id, 'title': c.title or '',
                    'vip': c.vip, 'vip_until': c.vip_until.isoformat() if c.vip_until else None,
                    'welcome_text': c.welcome_text, 'welcome_enabled': c.welcome_enabled,
                    'rules': c.rules, 'ai_enabled': c.ai_enabled,
                    'warns': c.warns or {}, 'settings': c.settings or {},
                    'messages_count': c.messages_count or 0, 'top_users': c.top_users or {}
                }
            except: return {'id': chat_id, 'ai_enabled': True}
            finally: s.close()
        return {'id': chat_id, 'ai_enabled': True, 'warns': {}, 'top_users': {}}
    
    def update_chat(self, chat_id: int, data: Dict):
        if engine:
            s = Session()
            try:
                c = s.query(Chat).filter_by(id=chat_id).first()
                if not c:
                    c = Chat(id=chat_id)
                    s.add(c)
                for k, v in data.items():
                    if k == 'vip_until' and v and isinstance(v, str):
                        v = datetime.fromisoformat(v)
                    setattr(c, k, v)
                s.commit()
            except: s.rollback()
            finally: s.close()
    
    def is_chat_vip(self, chat_id: int) -> bool:
        c = self.get_chat(chat_id)
        if not c.get('vip'): return False
        vu = c.get('vip_until')
        if not vu: return True
        try:
            if datetime.now() > datetime.fromisoformat(vu):
                self.update_chat(chat_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except: return True
    
    def add_chat_message(self, chat_id: int, user_id: int):
        """Учитываем сообщение в статистике чата"""
        if engine:
            c = self.get_chat(chat_id)
            top = c.get('top_users', {})
            top[str(user_id)] = top.get(str(user_id), 0) + 1
            self.update_chat(chat_id, {
                'messages_count': c.get('messages_count', 0) + 1,
                'top_users': top
            })
    
    def get_all_users(self) -> Dict:
        if engine:
            s = Session()
            try:
                users = s.query(User).all()
                return {u.id: {'id': u.id, 'username': u.username or '', 'first_name': u.first_name or '', 'vip': u.vip, 'language': u.language or 'ru'} for u in users}
            finally: s.close()
        return {}
    
    def get_user_by_identifier(self, ident: str) -> Optional[int]:
        """Поддержка отрицательных ID для чатов"""
        ident = ident.strip().lstrip('@')
        # Проверяем отрицательные числа (ID чатов)
        if ident.startswith('-') and ident[1:].isdigit():
            return int(ident)
        if ident.isdigit():
            return int(ident)
        if engine:
            s = Session()
            try:
                u = s.query(User).filter(User.username.ilike(f"%{ident}%")).first()
                return u.id if u else None
            finally: s.close()
        return None

storage = Storage()


# === ХЕЛПЕРЫ ===
def identify_creator(user):
    global CREATOR_ID
    if user and user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id

def is_creator(uid: int) -> bool:
    return uid == CREATOR_ID

def get_lang(uid: int) -> str:
    return storage.get_user(uid).get('language', 'ru')

def get_keyboard(uid: int) -> ReplyKeyboardMarkup:
    lang = get_lang(uid)
    kb = [
        [KeyboardButton(t('menu_chat', lang)), KeyboardButton(t('menu_notes', lang))],
        [KeyboardButton(t('menu_weather', lang)), KeyboardButton(t('menu_time', lang))],
        [KeyboardButton(t('menu_games', lang)), KeyboardButton(t('menu_info', lang))]
    ]
    if storage.is_vip(uid):
        kb.insert(0, [KeyboardButton(t('menu_vip', lang)), KeyboardButton(t('menu_gen', lang))])
    if is_creator(uid):
        kb.append([KeyboardButton(t('menu_admin', lang))])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

async def send_long(msg: Message, text: str):
    for i in range(0, len(text), 4000):
        await msg.reply_text(text[i:i+4000], parse_mode=ParseMode.HTML)
        if i + 4000 < len(text): await asyncio.sleep(0.3)

async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверка является ли пользователь админом чата"""
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def is_bot_admin(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверка является ли бот админом"""
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        return bot_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
async def extract_text_from_doc(data: bytes, name: str) -> str:
    try:
        ext = name.lower().split('.')[-1]
        if ext == 'txt':
            try: return data.decode('utf-8')
            except: return data.decode('cp1251', errors='ignore')
        elif ext == 'pdf':
            doc = fitz.open(stream=io.BytesIO(data), filetype="pdf")
            text = "".join([p.get_text() for p in doc])
            doc.close()
            return text
        elif ext in ['doc', 'docx']:
            d = docx.Document(io.BytesIO(data))
            return "\n".join([p.text for p in d.paragraphs])
        return data.decode('utf-8', errors='ignore')
    except Exception as e:
        return f"❌ {e}"

async def transcribe_audio(data: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            f.write(data)
            path = f.name
        uploaded = genai.upload_file(path=path, mime_type="audio/ogg")
        resp = text_model.generate_content(["Транскрибируй аудио. Только текст:", uploaded])
        os.remove(path)
        return resp.text.strip()
    except Exception as e:
        return f"❌ {e}"

async def generate_imagen(prompt: str) -> Optional[bytes]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}, timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 200:
                    res = await r.json()
                    if res.get("predictions"):
                        return base64.b64decode(res["predictions"][0]["bytesBase64Encoded"])
    except: pass
    return None


# === ГЛАВНЫЕ ОБРАБОТЧИКИ ===

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    
    uid = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(uid)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Проверка VIP (пользователь или чат)
    if not storage.is_vip(uid) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(t('vip_only', lang))
        return
    
    photo = update.message.photo[-1]
    caption = update.message.caption or ("Что на картинке?" if lang == 'ru' else "What's in this image?")
    
    await update.message.reply_text(t('photo_analyzing', lang))
    
    try:
        f = await context.bot.get_file(photo.file_id)
        data = await f.download_as_bytearray()
        img = Image.open(io.BytesIO(bytes(data)))
        
        unified_ctx.add_user_message(uid, [caption, img])
        resp = vision_model.generate_content([caption, img])
        text = resp.text
        unified_ctx.add_bot_message(uid, text)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        await send_long(update.message, t('photo_result', lang, text=text))
    except Exception as e:
        await update.message.reply_text(t('photo_error', lang, e=str(e)))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not update.message.voice:
        return
    
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    await update.message.reply_text(t('voice_transcribing', lang))
    
    try:
        f = await context.bot.get_file(update.message.voice.file_id)
        data = await f.download_as_bytearray()
        
        transcription = await transcribe_audio(bytes(data))
        if transcription.startswith("❌"):
            await update.message.reply_text(transcription)
            return
        
        unified_ctx.add_user_message(uid, f"[Голосовое]: {transcription}")
        
        history = unified_ctx.get_text_history(uid)
        chat = text_model.start_chat(history=history[:-1] if len(history) > 1 else [])
        resp = chat.send_message(transcription)
        text = resp.text
        
        unified_ctx.add_bot_message(uid, text)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        await send_long(update.message, t('voice_result', lang, text=transcription, response=text))
    except Exception as e:
        await update.message.reply_text(t('voice_error', lang, e=str(e)))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not update.message.document:
        return
    
    uid = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(uid)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    if not storage.is_vip(uid) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(t('vip_only', lang))
        return
    
    doc = update.message.document
    name = doc.file_name or "file"
    caption = update.message.caption
    
    await update.message.reply_text(t('file_analyzing', lang))
    
    try:
        f = await context.bot.get_file(doc.file_id)
        data = await f.download_as_bytearray()
        
        doc_text = await extract_text_from_doc(bytes(data), name)
        if doc_text.startswith("❌"):
            await update.message.reply_text(doc_text)
            return
        
        prompt = f"Файл '{name}'. {caption or 'Проанализируй:'}\n\n{doc_text[:3000]}"
        
        unified_ctx.add_user_message(uid, prompt)
        
        history = unified_ctx.get_text_history(uid)
        chat = text_model.start_chat(history=history[:-1] if len(history) > 1 else [])
        resp = chat.send_message(prompt)
        text = resp.text
        
        unified_ctx.add_bot_message(uid, text)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        await send_long(update.message, t('file_result', lang, name=name, text=text))
    except Exception as e:
        await update.message.reply_text(t('file_error', lang, e=str(e)))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not update.message.text:
        return
    
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    text = update.message.text
    lang = get_lang(uid)
    chat_id = update.message.chat.id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Обновляем статистику
    u = storage.get_user(uid)
    storage.update_user(uid, {
        'messages_count': u.get('messages_count', 0) + 1,
        'username': update.effective_user.username or '',
        'first_name': update.effective_user.first_name or ''
    })
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # Статистика чата
    if is_group:
        storage.add_chat_message(chat_id, uid)
    
    # Проверка кнопок меню (только в личке)
    if not is_group:
        menu_map = {}
        for lng in ['ru', 'en']:
            for key in ['menu_chat', 'menu_notes', 'menu_weather', 'menu_time', 'menu_games', 'menu_info', 'menu_vip', 'menu_gen', 'menu_admin']:
                menu_map[t(key, lng)] = key.replace('menu_', '')
        
        if text in menu_map:
            await handle_menu(update, context, menu_map[text], lang)
            return
    
    # В группах проверяем упоминание или AI включен
    if is_group:
        chat_data = storage.get_chat(chat_id)
        bot_un = context.bot.username
        
        # Если упомянули бота
        if f"@{bot_un}" in text:
            text = text.replace(f"@{bot_un}", "").strip()
        # Если AI выключен и не упомянули - игнорируем
        elif not chat_data.get('ai_enabled', True):
            return
        # Если не VIP чат и не VIP юзер - проверяем лимиты
        elif not storage.is_chat_vip(chat_id) and not storage.is_vip(uid):
            # В обычных чатах AI работает только по @mention
            return
    
    if not text:
        return
    
    await update.message.chat.send_action("typing")
    
    try:
        unified_ctx.add_user_message(uid, text)
        
        history = unified_ctx.get_text_history(uid)
        chat = text_model.start_chat(history=history[:-1] if len(history) > 1 else [])
        resp = chat.send_message(text)
        response = resp.text
        
        unified_ctx.add_bot_message(uid, response)
        
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        await send_long(update.message, response)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text(t('ai_error', lang))


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, lang: str):
    uid = update.effective_user.id
    if action == 'chat':
        await update.message.reply_text("💬 Просто пиши - отвечу!\n/clear - очистить контекст" if lang == 'ru' else "💬 Just type - I'll answer!\n/clear - clear context")
    elif action == 'notes':
        await notes_command(update, context)
    elif action == 'weather':
        await update.message.reply_text("/weather [город]" if lang == 'ru' else "/weather [city]")
    elif action == 'time':
        await update.message.reply_text("/time [город]" if lang == 'ru' else "/time [city]")
    elif action == 'games':
        kb = [[InlineKeyboardButton("🎲", callback_data="dice"), InlineKeyboardButton("🪙", callback_data="coin")],
              [InlineKeyboardButton("😄", callback_data="joke"), InlineKeyboardButton("💭", callback_data="quote")]]
        await update.message.reply_text("🎲 Игры:" if lang == 'ru' else "🎲 Games:", reply_markup=InlineKeyboardMarkup(kb))
    elif action == 'info':
        await info_command(update, context)
    elif action == 'vip':
        await vip_command(update, context)
    elif action == 'gen':
        await update.message.reply_text(t('gen_prompt', lang))
    elif action == 'admin' and is_creator(uid):
        await update.message.reply_text("👑 /users /stats /broadcast /grant_vip /revoke_vip")


# === ПРИВЕТСТВИЕ НОВЫХ УЧАСТНИКОВ ===
async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие новых участников"""
    if not update.message or not update.message.new_chat_members:
        return
    
    chat_id = update.message.chat.id
    chat_data = storage.get_chat(chat_id)
    
    if not chat_data.get('welcome_enabled', True):
        return
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        name = member.first_name or member.username or "User"
        custom = chat_data.get('welcome_text') or t('group_welcome_default', 'ru')
        
        welcome_text = t('group_welcome', 'ru', name=name, custom=custom)
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


# === КОМАНДЫ ДЛЯ ГРУПП ===

async def grouphelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    bot_username = context.bot.username
    await update.message.reply_text(t('group_help', lang, bot=bot_username), parse_mode=ParseMode.HTML)

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context):
        await update.message.reply_text("❌ Бот не админ!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await update.message.reply_text(t('user_banned', lang, name=target.first_name or target.username))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("❓ /unban [user_id]")
        return
    
    try:
        target_id = int(context.args[0])
        await context.bot.unban_chat_member(chat_id, target_id)
        await update.message.reply_text(t('user_unbanned', lang))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context):
        await update.message.reply_text("❌ Бот не админ!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await context.bot.unban_chat_member(chat_id, target.id)
        await update.message.reply_text(t('user_kicked', lang, name=target.first_name or target.username))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context):
        await update.message.reply_text("❌ Бот не админ!")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    mins = int(context.args[0]) if context.args and context.args[0].isdigit() else 15
    target = update.message.reply_to_message.from_user
    
    try:
        until = datetime.now() + timedelta(minutes=mins)
        await context.bot.restrict_chat_member(
            chat_id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await update.message.reply_text(t('user_muted', lang, name=target.first_name or target.username, mins=mins))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    
    try:
        await context.bot.restrict_chat_member(
            chat_id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_invite_users=True
            )
        )
        await update.message.reply_text(t('user_unmuted', lang, name=target.first_name or target.username))
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    chat_data = storage.get_chat(chat_id)
    warns = chat_data.get('warns', {})
    
    target_warns = warns.get(str(target.id), 0) + 1
    warns[str(target.id)] = target_warns
    storage.update_chat(chat_id, {'warns': warns})
    
    if target_warns >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.message.reply_text(t('user_warn_ban', lang, name=target.first_name or target.username))
            warns[str(target.id)] = 0
            storage.update_chat(chat_id, {'warns': warns})
        except:
            pass
    else:
        await update.message.reply_text(t('user_warned', lang, name=target.first_name or target.username, count=target_warns))

async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(t('need_reply', lang))
        return
    
    target = update.message.reply_to_message.from_user
    chat_data = storage.get_chat(chat_id)
    warns = chat_data.get('warns', {})
    
    target_warns = max(0, warns.get(str(target.id), 0) - 1)
    warns[str(target.id)] = target_warns
    storage.update_chat(chat_id, {'warns': warns})
    
    await update.message.reply_text(t('user_warn_removed', lang, name=target.first_name or target.username, count=target_warns))

async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = update.effective_user
    
    chat_data = storage.get_chat(chat_id)
    warns = chat_data.get('warns', {})
    count = warns.get(str(target.id), 0)
    
    if count > 0:
        await update.message.reply_text(t('warns_list', lang, name=target.first_name or target.username, count=count))
    else:
        await update.message.reply_text(t('warns_empty', lang, name=target.first_name or target.username))

async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("❓ /setwelcome [текст приветствия]")
        return
    
    welcome_text = ' '.join(context.args)
    storage.update_chat(chat_id, {'welcome_text': welcome_text, 'welcome_enabled': True})
    await update.message.reply_text(t('welcome_set', lang))

async def welcomeoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    storage.update_chat(chat_id, {'welcome_enabled': False})
    await update.message.reply_text(t('welcome_off', lang))

async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("❓ /setrules [текст правил]")
        return
    
    rules = ' '.join(context.args)
    storage.update_chat(chat_id, {'rules': rules})
    await update.message.reply_text(t('rules_set', lang))

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    chat_data = storage.get_chat(chat_id)
    rules = chat_data.get('rules')
    
    if rules:
        await update.message.reply_text(t('rules_text', lang, rules=rules), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t('rules_empty', lang))

async def setai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    uid = update.effective_user.id
    lang = get_lang(uid)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, uid, context) and not is_creator(uid):
        await update.message.reply_text(t('need_admin', lang))
        return
    
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.message.reply_text("❓ /setai [on/off]")
        return
    
    enabled = context.args[0].lower() == 'on'
    storage.update_chat(chat_id, {'ai_enabled': enabled})
    await update.message.reply_text(t('ai_enabled' if enabled else 'ai_disabled', lang))

async def chatinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat_data = storage.get_chat(chat_id)
    
    try:
        members = await context.bot.get_chat_member_count(chat_id)
    except:
        members = "?"
    
    vip_status = "✅" if storage.is_chat_vip(chat_id) else "❌"
    ai_status = "✅" if chat_data.get('ai_enabled', True) else "❌"
    
    await update.message.reply_text(
        t('chat_info', lang, 
          id=chat_id, 
          title=update.message.chat.title or "?",
          members=members,
          vip=vip_status,
          ai=ai_status),
        parse_mode=ParseMode.HTML
    )

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    
    chat_id = update.message.chat.id
    lang = get_lang(update.effective_user.id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat_data = storage.get_chat(chat_id)
    top_users = chat_data.get('top_users', {})
    
    if not top_users:
        await update.message.reply_text("📊 Статистика пока пуста")
        return
    
    # Сортируем по количеству сообщений
    sorted_users = sorted(top_users.items(), key=lambda x: x[1], reverse=True)[:10]
    
    lines = []
    for i, (user_id, count) in enumerate(sorted_users, 1):
        user_data = storage.get_user(int(user_id))
        name = user_data.get('first_name') or user_data.get('username') or user_id
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} {name} — {count} сообщ.")
    
    await update.message.reply_text(t('top_users', lang, list='\n'.join(lines)), parse_mode=ParseMode.HTML)


# === ОСНОВНЫЕ КОМАНДЫ ===

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    storage.update_user(uid, {'username': update.effective_user.username or '', 'first_name': update.effective_user.first_name or ''})
    lang = get_lang(uid)
    
    # Если в группе - другое приветствие
    if update.message.chat.type in ['group', 'supergroup']:
        chat_id = update.message.chat.id
        storage.update_chat(chat_id, {'title': update.message.chat.title})
        await update.message.reply_text(
            f"👋 Привет! Я <b>AI DISCO BOT</b>.\n\n"
            f"🤖 Упомяните меня @{context.bot.username} чтобы задать вопрос\n"
            f"📚 /grouphelp — команды для группы\n"
            f"💎 VIP дает безлимитный AI для всего чата!",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(t('welcome', lang, name=update.effective_user.first_name or 'User', creator=CREATOR_USERNAME), parse_mode=ParseMode.HTML, reply_markup=get_keyboard(uid))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    await update.message.reply_text(t('help', get_lang(update.effective_user.id)), parse_mode=ParseMode.HTML)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    kb = [[InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru")], [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")]]
    await update.message.reply_text(t('lang_choose', get_lang(update.effective_user.id)), reply_markup=InlineKeyboardMarkup(kb))

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    unified_ctx.clear(uid)
    await update.message.reply_text(t('clear', get_lang(uid)))

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    db = "PostgreSQL ✓" if engine else "JSON"
    await update.message.reply_text(t('info', lang, db=db), parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    users = storage.get_all_users()
    up = datetime.now() - BOT_START_TIME
    await update.message.reply_text(t('status', lang, users=len(users), vips=sum(1 for u in users.values() if u.get('vip')), msgs=storage.stats.get('total_messages', 0), ai=storage.stats.get('ai_requests', 0), days=up.days, hours=up.seconds // 3600), parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    lang = get_lang(uid)
    u = storage.get_user(uid)
    txt = t('profile', lang, name=u.get('first_name') or 'User', id=uid, msgs=u.get('messages_count', 0), notes=len(u.get('notes', [])))
    if storage.is_vip(uid):
        vu = u.get('vip_until')
        txt += t('profile_vip', lang, date=datetime.fromisoformat(vu).strftime('%d.%m.%Y')) if vu else t('profile_vip_forever', lang)
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    lang = get_lang(uid)
    chat_id = update.message.chat.id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Проверка VIP чата
    if is_group:
        if storage.is_chat_vip(chat_id):
            chat_data = storage.get_chat(chat_id)
            vu = chat_data.get('vip_until')
            until = f"До: {datetime.fromisoformat(vu).strftime('%d.%m.%Y')}" if vu else "Навсегда ♾️"
            await update.message.reply_text(f"💎 <b>VIP чат!</b>\n\n⏰ {until}\n\n🤖 AI доступен всем!", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(t('chat_vip_inactive', lang), parse_mode=ParseMode.HTML)
        return
    
    # Личный VIP
    if storage.is_vip(uid):
        u = storage.get_user(uid)
        vu = u.get('vip_until')
        until = t('vip_until', lang, date=datetime.fromisoformat(vu).strftime('%d.%m.%Y')) if vu else t('vip_forever', lang)
        await update.message.reply_text(t('vip_active', lang, until=until), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t('vip_inactive', lang), parse_mode=ParseMode.HTML)

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message: return
    if not context.args:
        await update.message.reply_text("❓ /ai [вопрос]")
        return
    update.message.text = ' '.join(context.args)
    await handle_message(update, context)

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(uid)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    if not storage.is_vip(uid) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(t('vip_only', lang))
        return
    if not context.args:
        await update.message.reply_text(t('gen_prompt', lang))
        return
    prompt = ' '.join(context.args)
    await update.message.reply_text(t('gen_progress', lang))
    img = await generate_imagen(prompt)
    if img:
        await update.message.reply_photo(photo=img, caption=t('gen_done', lang, prompt=prompt), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(t('gen_error', lang))


# === ЗАМЕТКИ ===

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args:
        await update.message.reply_text(t('note_prompt', lang))
        return
    txt = ' '.join(context.args)
    u = storage.get_user(uid)
    notes = u.get('notes', [])
    notes.append({'text': txt, 'date': datetime.now().isoformat()})
    storage.update_user(uid, {'notes': notes})
    await update.message.reply_text(t('note_saved', lang, n=len(notes)))

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    lang = get_lang(uid)
    notes = storage.get_user(uid).get('notes', [])
    if not notes:
        await update.message.reply_text(t('notes_empty', lang))
        return
    lst = "\n".join([f"<b>#{i+1}</b> {n['text'][:50]}" for i, n in enumerate(notes)])
    await update.message.reply_text(t('notes_list', lang, n=len(notes), list=lst), parse_mode=ParseMode.HTML)

async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❓ /delnote [номер]")
        return
    n = int(context.args[0])
    notes = storage.get_user(uid).get('notes', [])
    if 1 <= n <= len(notes):
        notes.pop(n - 1)
        storage.update_user(uid, {'notes': notes})
        await update.message.reply_text(t('delnote_ok', lang, n=n))
    else:
        await update.message.reply_text(t('delnote_err', lang))


# === УТИЛИТЫ ===

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    tzs = {'moscow': 'Europe/Moscow', 'москва': 'Europe/Moscow', 'london': 'Europe/London', 'лондон': 'Europe/London', 'new york': 'America/New_York', 'tokyo': 'Asia/Tokyo', 'paris': 'Europe/Paris', 'berlin': 'Europe/Berlin'}
    tz_name = tzs.get(city.lower())
    if not tz_name:
        match = [z for z in pytz.all_timezones if city.lower().replace(" ", "_") in z.lower()]
        tz_name = match[0] if match else 'Europe/Moscow'
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        await update.message.reply_text(t('time_result', lang, city=city.title(), time=now.strftime('%H:%M:%S'), date=now.strftime('%d.%m.%Y'), tz=tz_name), parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(t('time_error', lang))

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://wttr.in/{urlquote(city)}?format=j1", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    d = await r.json()
                    c = d['current_condition'][0]
                    await update.message.reply_text(t('weather_result', lang, city=city.title(), temp=c['temp_C'], feels=c['FeelsLikeC'], desc=c['weatherDesc'][0]['value'], humidity=c['humidity'], wind=c['windspeedKmph']), parse_mode=ParseMode.HTML)
                    return
    except: pass
    await update.message.reply_text(t('weather_error', lang))

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("❓ /calc [выражение]")
        return
    expr = ' '.join(context.args)
    if not all(c in "0123456789.+-*/() " for c in expr):
        await update.message.reply_text(t('calc_error', lang))
        return
    try:
        result = eval(expr, {"__builtins__": {}}, {})
        await update.message.reply_text(t('calc_result', lang, expr=expr, result=result), parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text(t('calc_error', lang))

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    length = int(context.args[0]) if context.args and context.args[0].isdigit() else 12
    length = max(8, min(50, length))
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    pwd = ''.join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(t('password_result', lang, pwd=pwd), parse_mode=ParseMode.HTML)


# === ИГРЫ ===

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    try:
        mn, mx = (int(context.args[0]), int(context.args[1])) if len(context.args) >= 2 else (1, 100)
    except:
        mn, mx = 1, 100
    await update.message.reply_text(t('random_result', lang, min=mn, max=mx, r=random.randint(mn, mx)), parse_mode=ParseMode.HTML)

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    await update.message.reply_text(t('dice_result', get_lang(update.effective_user.id), r=random.randint(1, 6)), parse_mode=ParseMode.HTML)

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(t('coin_heads' if random.choice([True, False]) else 'coin_tails', lang))

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    jokes = {'ru': ["Программист: — Закрой окно! — И что, станет тепло? 😄", "31 OCT = 25 DEC 🎃", "Зачем очки? Чтобы лучше C++ 👓"], 'en': ["Why dark mode? Light attracts bugs! 🐛", "Why quit? Didn't get arrays 🤷", "Favorite spot? Foo bar 🍻"]}
    await update.message.reply_text(t('joke', lang, text=random.choice(jokes.get(lang, jokes['en']))), parse_mode=ParseMode.HTML)

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    quotes = {'ru': ["Единственный способ делать великую работу — любить её. — Джобс", "Инновация отличает лидера. — Джобс"], 'en': ["The only way to do great work is to love it. - Jobs", "Innovation distinguishes leaders. - Jobs"]}
    await update.message.reply_text(t('quote', lang, text=random.choice(quotes.get(lang, quotes['en']))), parse_mode=ParseMode.HTML)

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    lang = get_lang(update.effective_user.id)
    facts = {'ru': ["🌍 Земля — единственная планета не в честь бога", "🐙 У осьминога 3 сердца и голубая кровь"], 'en': ["🌍 Earth is the only planet not named after a god", "🐙 Octopuses have 3 hearts and blue blood"]}
    await update.message.reply_text(t('fact', lang, text=random.choice(facts.get(lang, facts['en']))), parse_mode=ParseMode.HTML)


# === НАПОМИНАНИЯ ===

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not storage.is_vip(uid):
        await update.message.reply_text(t('vip_only', lang))
        return
    if len(context.args) < 2:
        await update.message.reply_text(t('remind_prompt', lang))
        return
    try:
        mins = int(context.args[0])
        txt = ' '.join(context.args[1:])
        when = datetime.now() + timedelta(minutes=mins)
        u = storage.get_user(uid)
        rems = u.get('reminders', [])
        rems.append({'text': txt, 'time': when.isoformat(), 'lang': lang})
        storage.update_user(uid, {'reminders': rems})
        scheduler.add_job(send_reminder, 'date', run_date=when, args=[context.bot, uid, txt, lang])
        await update.message.reply_text(t('remind_ok', lang, m=mins, text=txt))
    except:
        await update.message.reply_text(t('remind_prompt', lang))

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not storage.is_vip(uid):
        await update.message.reply_text(t('vip_only', lang))
        return
    rems = storage.get_user(uid).get('reminders', [])
    if not rems:
        await update.message.reply_text(t('reminders_empty', lang))
        return
    lst = "\n".join([f"<b>#{i+1}</b> {datetime.fromisoformat(r['time']).strftime('%d.%m %H:%M')} - {r['text'][:30]}" for i, r in enumerate(rems)])
    await update.message.reply_text(t('reminders_list', lang, n=len(rems), list=lst), parse_mode=ParseMode.HTML)

async def send_reminder(bot, uid: int, txt: str, lang: str):
    try:
        await bot.send_message(chat_id=uid, text=t('remind_alert', lang, text=txt), parse_mode=ParseMode.HTML)
        u = storage.get_user(uid)
        rems = [r for r in u.get('reminders', []) if r['text'] != txt]
        storage.update_user(uid, {'reminders': rems})
    except Exception as e:
        logger.warning(f"Remind error: {e}")


# === АДМИН КОМАНДЫ ===

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    if len(context.args) < 2:
        await update.message.reply_text(t('grant_prompt', lang))
        return
    
    target = storage.get_user_by_identifier(context.args[0])
    if not target:
        await update.message.reply_text("❌ User/Chat not found")
        return
    
    dur = context.args[1].lower()
    durations = {'week': timedelta(weeks=1), 'month': timedelta(days=30), 'year': timedelta(days=365), 'forever': None}
    if dur not in durations:
        await update.message.reply_text(t('grant_prompt', lang))
        return
    
    delta = durations[dur]
    is_chat = target < 0  # Отрицательный ID = чат
    
    if delta:
        until = datetime.now() + delta
        if is_chat:
            storage.update_chat(target, {'vip': True, 'vip_until': until.isoformat()})
        else:
            storage.update_user(target, {'vip': True, 'vip_until': until.isoformat()})
        dur_txt = until.strftime('%d.%m.%Y')
    else:
        if is_chat:
            storage.update_chat(target, {'vip': True, 'vip_until': None})
        else:
            storage.update_user(target, {'vip': True, 'vip_until': None})
        dur_txt = "Forever ♾️"
    
    target_type = "Chat" if is_chat else "User"
    await update.message.reply_text(f"✅ VIP granted to {target_type}: <code>{target}</code>\n⏰ {dur_txt}", parse_mode=ParseMode.HTML)
    
    try:
        await context.bot.send_message(chat_id=target, text=f"🎉 VIP granted! {dur_txt}")
    except: pass

async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    if not context.args:
        await update.message.reply_text("❓ /revoke_vip [id/@username/chat_id]")
        return
    
    target = storage.get_user_by_identifier(context.args[0])
    if target:
        is_chat = target < 0
        if is_chat:
            storage.update_chat(target, {'vip': False, 'vip_until': None})
        else:
            storage.update_user(target, {'vip': False, 'vip_until': None})
        await update.message.reply_text(t('revoke_ok', lang, id=target), parse_mode=ParseMode.HTML)

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    users = storage.get_all_users()
    lst = "\n".join([f"{'💎' if u.get('vip') else ''} <code>{i}</code> {(u.get('first_name') or 'Unknown')[:15]}" for i, u in list(users.items())[:20]])
    await update.message.reply_text(t('users_list', lang, n=len(users), list=lst), parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await status_command(update, context)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user: return
    identify_creator(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not is_creator(uid):
        await update.message.reply_text(t('admin_only', lang))
        return
    if not context.args:
        await update.message.reply_text(t('broadcast_prompt', lang))
        return
    txt = ' '.join(context.args)
    await update.message.reply_text(t('broadcast_start', lang))
    users = storage.get_all_users()
    ok, err = 0, 0
    for target in users.keys():
        try:
            await context.bot.send_message(chat_id=target, text=f"📢 <b>Broadcast:</b>\n\n{txt}", parse_mode=ParseMode.HTML)
            ok += 1
            await asyncio.sleep(0.05)
        except:
            err += 1
    await update.message.reply_text(t('broadcast_done', lang, ok=ok, err=err))


# === CALLBACKS ===

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.from_user: return
    await q.answer()
    data = q.data
    uid = q.from_user.id
    lang = get_lang(uid)
    if data.startswith("lang:"):
        new_lang = data.split(":")[1]
        storage.update_user(uid, {'language': new_lang})
        await q.edit_message_text(t('lang_changed', new_lang))
        await q.message.reply_text(t('welcome', new_lang, name=q.from_user.first_name or 'User', creator=CREATOR_USERNAME), parse_mode=ParseMode.HTML, reply_markup=get_keyboard(uid))
        return
    if data == "dice":
        await q.message.reply_text(t('dice_result', lang, r=random.randint(1, 6)), parse_mode=ParseMode.HTML)
    elif data == "coin":
        await q.message.reply_text(t('coin_heads' if random.choice([True, False]) else 'coin_tails', lang))
    elif data == "joke":
        jokes = ["Программист: — Закрой окно! 😄", "31 OCT = 25 DEC 🎃"] if lang == 'ru' else ["Dark mode? Light attracts bugs! 🐛"]
        await q.message.reply_text(t('joke', lang, text=random.choice(jokes)), parse_mode=ParseMode.HTML)
    elif data == "quote":
        quotes = ["Любите то, что делаете. — Джобс"] if lang == 'ru' else ["Love what you do. - Jobs"]
        await q.message.reply_text(t('quote', lang, text=random.choice(quotes)), parse_mode=ParseMode.HTML)


# === POST_INIT ===
async def post_init(application):
    scheduler.start()
    logger.info("✅ Scheduler запущен!")


# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Основные
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("generate", generate_command))
    
    # Заметки
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("delnote", delnote_command))
    
    # Утилиты
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("calc", calc_command))
    app.add_handler(CommandHandler("password", password_command))
    
    # Игры
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("dice", dice_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("joke", joke_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("fact", fact_command))
    
    # VIP
    app.add_handler(CommandHandler("vip", vip_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    
    # Группы - модерация
    app.add_handler(CommandHandler("grouphelp", grouphelp_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("kick", kick_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("unwarn", unwarn_command))
    app.add_handler(CommandHandler("warns", warns_command))
    
    # Группы - настройки
    app.add_handler(CommandHandler("setwelcome", setwelcome_command))
    app.add_handler(CommandHandler("welcomeoff", welcomeoff_command))
    app.add_handler(CommandHandler("setrules", setrules_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("setai", setai_command))
    app.add_handler(CommandHandler("chatinfo", chatinfo_command))
    app.add_handler(CommandHandler("top", top_command))
    
    # Админ
    app.add_handler(CommandHandler("grant_vip", grant_vip_command))
    app.add_handler(CommandHandler("revoke_vip", revoke_vip_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Обработчики
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("=" * 50)
    logger.info("✅ AI DISCO BOT v3.3 ЗАПУЩЕН!")
    logger.info("🤖 Gemini 2.5 Flash")
    logger.info("🔄 ЕДИНЫЙ контекст (текст+фото+голос)")
    logger.info("👥 Расширенная поддержка групп")
    logger.info("🗄️ " + ("PostgreSQL ✓" if engine else "JSON"))
    logger.info("=" * 50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
