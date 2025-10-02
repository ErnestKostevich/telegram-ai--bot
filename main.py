import asyncio
import logging
import json
import random
import datetime
import requests
import os
import sys
import sqlite3
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import nest_asyncio
from flask import Flask
import pytz

nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

try:
import google.generativeai as genai
GENAI_AVAILABLE = True
except ImportError:
GENAI_AVAILABLE = False

logging.basicConfig(
format=’%(asctime)s - %(name)s - %(levelname)s - %(message)s’,
level=logging.INFO,
handlers=[logging.FileHandler(‘bot.log’), logging.StreamHandler()]
)
logger = logging.getLogger(**name**)

# Конфигурация

BOT_TOKEN = os.getenv(“BOT_TOKEN”)
GEMINI_API_KEY = os.getenv(“GEMINI_API_KEY”)
OPENWEATHER_API_KEY = os.getenv(“OPENWEATHER_API_KEY”)

CREATOR_ID = 7108255346
CREATOR_USERNAME = “@Ernest_Kostevich”
BOT_USERNAME = “@AI_DISCO_BOT”

if GEMINI_API_KEY and GENAI_AVAILABLE:
genai.configure(api_key=GEMINI_API_KEY)
MODEL = “gemini-2.0-flash-exp”

RENDER_URL = os.getenv(“RENDER_EXTERNAL_URL”, “https://telegram-ai–bot.onrender.com”)

DB_PATH = “bot_database.db”
CONVERSATIONS_PATH = “conversations.json”
Path(“backups”).mkdir(exist_ok=True)

# Переводы

TRANSLATIONS = {
‘ru’: {
‘welcome’: ‘🤖 Привет, {name}!\nЯ AI-бот с 50+ функциями!\n\nИспользуйте кнопки или /help’,
‘help’: ‘📋 Помощь’,
‘notes’: ‘📝 Заметки’,
‘stats’: ‘📊 Статистика’,
‘time’: ‘⏰ Время’,
‘language’: ‘🌐 Язык’,
‘ai_chat’: ‘💬 AI Чат’,
‘current_time’: ‘⏰ МИРОВОЕ ВРЕМЯ’
},
‘en’: {
‘welcome’: ‘🤖 Hello, {name}!\nI am an AI bot with 50+ features!\n\nUse buttons or /help’,
‘help’: ‘📋 Help’,
‘notes’: ‘📝 Notes’,
‘stats’: ‘📊 Stats’,
‘time’: ‘⏰ Time’,
‘language’: ‘🌐 Language’,
‘ai_chat’: ‘💬 AI Chat’,
‘current_time’: ‘⏰ WORLD TIME’
}
}

LANGUAGE_NAMES = {
‘ru’: ‘🇷🇺 Русский’,
‘en’: ‘🇺🇸 English’,
‘es’: ‘🇪🇸 Español’,
‘fr’: ‘🇫🇷 Français’,
‘it’: ‘🇮🇹 Italiano’,
‘de’: ‘🇩🇪 Deutsch’
}

class Database:
def **init**(self):
self.db_path = DB_PATH
self.init_db()

def get_connection(self):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(self):
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        is_vip INTEGER DEFAULT 0,
        vip_expires TEXT,
        language TEXT DEFAULT 'ru',
        level INTEGER DEFAULT 1,
        experience INTEGER DEFAULT 0,
        last_activity TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def get_user(self, user_id):
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_user(self, user_data):
    conn = self.get_connection()
    cursor = conn.cursor()
    user_data['last_activity'] = datetime.datetime.now().isoformat()
    
    if self.get_user(user_data['user_id']):
        cursor.execute('''UPDATE users SET username=?, first_name=?, is_vip=?, 
            language=?, level=?, experience=?, last_activity=? WHERE user_id=?''',
            (user_data.get('username',''), user_data.get('first_name',''),
            user_data.get('is_vip',0), user_data.get('language','ru'),
            user_data.get('level',1), user_data.get('experience',0),
            user_data['last_activity'], user_data['user_id']))
    else:
        cursor.execute('''INSERT INTO users (user_id, username, first_name, is_vip,
            language, level, experience, last_activity) VALUES (?,?,?,?,?,?,?,?)''',
            (user_data['user_id'], user_data.get('username',''), user_data.get('first_name',''),
            user_data.get('is_vip',0), user_data.get('language','ru'),
            user_data.get('level',1), user_data.get('experience',0), user_data['last_activity']))
    conn.commit()
    conn.close()

def get_all_users(self):
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_note(self, user_id, note):
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notes (user_id, note) VALUES (?, ?)", (user_id, note))
    conn.commit()
    conn.close()

def get_notes(self, user_id):
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_note(self, note_id, user_id):
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

class ConversationMemory:
def **init**(self):
self.filepath = CONVERSATIONS_PATH
self.conversations = self._load()

def _load(self):
    if os.path.exists(self.filepath):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save(self):
    try:
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.conversations, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save error: {e}")

def add_message(self, user_id, role, content):
    uid = str(user_id)
    if uid not in self.conversations:
        self.conversations[uid] = {'messages': []}
    self.conversations[uid]['messages'].append({'role': role, 'content': content})
    if len(self.conversations[uid]['messages']) % 10 == 0:
        self._save()

def get_context(self, user_id, limit=50):
    uid = str(user_id)
    if uid not in self.conversations:
        return []
    messages = self.conversations[uid]['messages']
    return messages[-limit:] if len(messages) > limit else messages

def clear_history(self, user_id):
    uid = str(user_id)
    if uid in self.conversations:
        del self.conversations[uid]
        self._save()

def save(self):
    self._save()
    
class TelegramBot:
def **init**(self):
self.db = Database()
self.memory = ConversationMemory()
self.gemini_model = None

    if GEMINI_API_KEY and GENAI_AVAILABLE:
        try:
            self.gemini_model = genai.GenerativeModel(MODEL)
            logger.info("Gemini OK")
        except Exception as e:
            logger.error(f"Gemini error: {e}")
    
    self.scheduler = AsyncIOScheduler()

def t(self, key, lang='ru', **kwargs):
    text = TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, key)
    return text.format(**kwargs) if kwargs else text

async def get_user_data(self, update):
    user = update.effective_user
    user_data = self.db.get_user(user.id)
    
    if not user_data:
        user_data = {
            'user_id': user.id,
            'username': user.username or "",
            'first_name': user.first_name or "",
            'is_vip': 1 if user.id == CREATOR_ID else 0,
            'language': 'ru',
            'level': 1,
            'experience': 0
        }
        self.db.save_user(user_data)
    return user_data

def get_keyboard(self, lang='ru'):
    keyboard = [
        [KeyboardButton(self.t('ai_chat', lang)), KeyboardButton(self.t('help', lang))],
        [KeyboardButton(self.t('notes', lang)), KeyboardButton(self.t('stats', lang))],
        [KeyboardButton(self.t('time', lang)), KeyboardButton(self.t('language', lang))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def is_creator(self, user_id):
    return user_id == CREATOR_ID

async def add_exp(self, user_data, points=1):
    user_data['experience'] = user_data.get('experience', 0) + points
    req = user_data.get('level', 1) * 100
    if user_data['experience'] >= req:
        user_data['level'] = user_data.get('level', 1) + 1
        user_data['experience'] = 0
    self.db.save_user(user_data)

async def start_command(self, update, context):
    user_data = await self.get_user_data(update)
    lang = user_data.get('language', 'ru')
    message = self.t('welcome', lang, name=user_data['first_name'])
    await update.message.reply_text(message, reply_markup=self.get_keyboard(lang))
    await self.add_exp(user_data, 1)

async def help_command(self, update, context):
    user_data = await self.get_user_data(update)
    help_text = """📋 СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start /help /info /status

💬 AI: /ai [вопрос] /clearhistory

📝 ЗАМЕТКИ: /note [текст] /notes /delnote [№]

⏰ ВРЕМЯ: /time /date

🎮 ИГРЫ: /joke /fact /quote /coin /dice /8ball

🔢 МАТЕМАТИКА: /math /calculate

🛠️ УТИЛИТЫ: /password /qr /weather /translate

📊 ДРУГОЕ: /rank /stats /language”””

    if self.is_creator(user_data['user_id']):
        help_text += "\n\n👑 СОЗДАТЕЛЬ:\n/grant_vip /broadcast /users /backup"
    
    await update.message.reply_text(help_text)
    await self.add_exp(user_data, 1)

async def info_command(self, update, context):
    user_data = await self.get_user_data(update)
    info = f"""🤖 О БОТЕ

Версия: 2.1
Создатель: Ernest {CREATOR_USERNAME}
Бот: {BOT_USERNAME}

🔧 AI: {“✅ Gemini 2.0” if self.gemini_model else “❌”}
💾 База: SQLite ✅
🌐 Языков: 6

👥 Пользователей: {len(self.db.get_all_users())}”””
await update.message.reply_text(info)
await self.add_exp(user_data, 1)

async def status_command(self, update, context):
    user_data = await self.get_user_data(update)
    status = f"""⚡ СТАТУС

🟢 Онлайн: Работает
📅 Версия: 2.1
⏰ {datetime.datetime.now().strftime(’%d.%m.%Y %H:%M’)}

👥 Пользователей: {len(self.db.get_all_users())}
🧠 AI: {“✅” if self.gemini_model else “❌”}”””
await update.message.reply_text(status)
await self.add_exp(user_data, 1)

async def time_command(self, update, context):
    user_data = await self.get_user_data(update)
    lang = user_data.get('language', 'ru')
    
    now_utc = datetime.datetime.now(pytz.utc)
    
    timezones = [
        ('GMT (Лондон)', 'Europe/London'),
        ('CEST (Берлин)', 'Europe/Berlin'),
        ('CEST (Париж)', 'Europe/Paris'),
        ('MSK (Москва)', 'Europe/Moscow'),
        ('EST (Вашингтон)', 'America/New_York'),
        ('PST (Лос-Анджелес)', 'America/Los_Angeles'),
        ('CST (Чикаго)', 'America/Chicago'),
        ('JST (Токио)', 'Asia/Tokyo'),
        ('CST (Пекин)', 'Asia/Shanghai'),
        ('IST (Дели)', 'Asia/Kolkata')
    ]
    
    text = f"{self.t('current_time', lang)}\n\n"
    for city, tz_name in timezones:
        try:
            tz = pytz.timezone(tz_name)
            local_time = now_utc.astimezone(tz)
            text += f"🌍 {city}: {local_time.strftime('%H:%M:%S')}\n"
        except:
            pass
    
    text += f"\n📅 {now_utc.strftime('%d.%m.%Y')}"
    await update.message.reply_text(text)
    await self.add_exp(user_data, 1)

async def date_command(self, update, context):
    user_data = await self.get_user_data(update)
    now = datetime.datetime.now()
    days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    text = f"""📅 СЕГОДНЯ

🗓️ {days_ru[now.weekday()]}
📆 {now.strftime(’%d.%m.%Y’)}
⏰ {now.strftime(’%H:%M:%S’)}”””
await update.message.reply_text(text)
await self.add_exp(user_data, 1)

async def language_command(self, update, context):
    user_data = await self.get_user_data(update)
    
    if context.args and context.args[0].lower() in LANGUAGE_NAMES:
        lang = context.args[0].lower()
        user_data['language'] = lang
        self.db.save_user(user_data)
        await update.message.reply_text(
            f"✅ Язык изменён на {LANGUAGE_NAMES[lang]}",
            reply_markup=self.get_keyboard(lang)
        )
        return
    
    keyboard = [[InlineKeyboardButton(name, callback_data=f"lang_{code}")] 
               for code, name in LANGUAGE_NAMES.items()]
    await update.message.reply_text(
        "🌐 Выберите язык:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def ai_command(self, update, context):
    user_data = await self.get_user_data(update)
    
    if not context.args:
        await update.message.reply_text("🤖 Пример: /ai Расскажи о космосе")
        return
    
    if not self.gemini_model:
        await update.message.reply_text("❌ AI недоступен")
        return
    
    query = " ".join(context.args)
    
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        history = self.memory.get_context(user_data['user_id'], limit=10)
        context_str = "\n".join([f"{m['role']}: {m['content'][:50]}" for m in history[-3:]])
        prompt = f"{context_str}\n\nВопрос: {query}\n\nОтветь кратко."
        response = self.gemini_model.generate_content(prompt)
        
        self.memory.add_message(user_data['user_id'], 'user', query)
        self.memory.add_message(user_data['user_id'], 'assistant', response.text)
        
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")
        logger.error(f"AI error: {e}")
    
    await self.add_exp(user_data, 2)

async def clearhistory_command(self, update, context):
    user_data = await self.get_user_data(update)
    self.memory.clear_history(user_data['user_id'])
    await update.message.reply_text("🗑️ История очищена!")

async def handle_message(self, update, context):
    user_data = await self.get_user_data(update)
    message = update.message.text
    lang = user_data.get('language', 'ru')
    
    # Обработка кнопок
    if message == self.t('help', lang):
        return await self.help_command(update, context)
    elif message == self.t('notes', lang):
        return await self.notes_command(update, context)
    elif message == self.t('stats', lang):
        return await self.stats_command(update, context)
    elif message == self.t('time', lang):
        return await self.time_command(update, context)
    elif message == self.t('language', lang):
        return await self.language_command(update, context)
    elif message == self.t('ai_chat', lang):
        await update.message.reply_text("💬 AI готов! Напишите вопрос.")
        return
    
    # AI чат
    if not self.gemini_model:
        return
    
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        history = self.memory.get_context(user_data['user_id'], limit=10)
        context_str = "\n".join([f"{m['role']}: {m['content'][:50]}" for m in history[-3:]])
        prompt = f"{context_str}\n\nПользователь: {message}\n\nОтветь полезно."
        response = self.gemini_model.generate_content(prompt)
        
        self.memory.add_message(user_data['user_id'], 'user', message)
        self.memory.add_message(user_data['user_id'], 'assistant', response.text)
        
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Message error: {e}")
    
    await self.add_exp(user_data, 1)

async def note_command(self, update, context):
    user_data = await self.get_user_data(update)
    if not context.args:
        await update.message.reply_text("📝 Пример: /note Купить молоко")
        return
    note = " ".join(context.args)
    self.db.add_note(user_data['user_id'], note)
    await update.message.reply_text(f"✅ Сохранено!\n\n📝 {note}")
    await self.add_exp(user_data, 1)

async def notes_command(self, update, context):
    user_data = await self.get_user_data(update)
    notes = self.db.get_notes(user_data['user_id'])
    
    if not notes:
        await update.message.reply_text("❌ Нет заметок!\n/note [текст]")
        return
    
    text = "📝 ЗАМЕТКИ:\n\n"
    for i, note in enumerate(notes[:20], 1):
        text += f"{i}. {note['note']}\n"
    await update.message.reply_text(text)
    await self.add_exp(user_data, 1)

async def delnote_command(self, update, context):
    user_data = await self.get_user_data(update)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Пример: /delnote 1")
        return
    
    notes = self.db.get_notes(user_data['user_id'])
    index = int(context.args[0]) - 1
    
    if 0 <= index < len(notes):
        self.db.delete_note(notes[index]['id'], user_data['user_id'])
        await update.message.reply_text(f"✅ Заметка #{index+1} удалена!")
    else:
        await update.message.reply_text(f"❌ Нет заметки #{index+1}")
    await self.add_exp(user_data, 1)

async def joke_command(self, update, context):
    jokes = [
        "Почему программисты путают Хэллоуин и Рождество? Oct 31 == Dec 25!",
        "Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
        "- Доктор, я компьютерный вирус!\n- Примите антивирус!"
    ]
    await update.message.reply_text(random.choice(jokes))

async def fact_command(self, update, context):
    facts = [
        "🧠 Мозг содержит 86 миллиардов нейронов!",
        "🐙 У осьминогов три сердца!",
        "🦈 Акулы старше деревьев - 400+ млн лет!"
    ]
    await update.message.reply_text(random.choice(facts))

async def quote_command(self, update, context):
    quotes = [
        "💫 'Будь собой. Остальные роли заняты.' - Оскар Уайльд",
        "🚀 'Любите то, что делаете.' - Стив Джобс"
    ]
    await update.message.reply_text(random.choice(quotes))

async def coin_command(self, update, context):
    await update.message.reply_text(random.choice(["🪙 Орёл!", "🪙 Решка!"]))

async def dice_command(self, update, context):
    result = random.randint(1, 6)
    faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    await update.message.reply_text(f"🎲 {faces[result-1]} = {result}")

async def eightball_command(self, update, context):
    if not context.args:
        await update.message.reply_text("🔮 Задайте вопрос!\n/8ball Стоит ли?")
        return
    answers = ["✅ Да!", "🤔 Возможно", "❌ Нет"]
    await update.message.reply_text(f"🔮 {random.choice(answers)}")

async def math_command(self, update, context):
    if not context.args:
        await update.message.reply_text("🔢 Пример: /math 15 + 25 * 2")
        return
    expr = " ".join(context.args)
    try:
        if all(c in '0123456789+-*/()., ' for c in expr):
            result = eval(expr)
            await update.message.reply_text(f"🔢 {expr} = {result}")
        else:
            await update.message.reply_text("❌ Только: цифры, +, -, *, /, ()")
    except:
        await update.message.reply_text("❌ Ошибка вычисления")

async def calculate_command(self, update, context):
    if not context.args:
        await update.message.reply_text("🧮 Функции: sqrt, sin, cos, pi\n/calculate sqrt(16)")
        return
    expr = " ".join(context.args)
    try:
        import math
        safe = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "pi": math.pi, "e": math.e}
        result = eval(expr, {"__builtins__": {}}, safe)
        await update.message.reply_text(f"🧮 {expr} = {result}")
    except:
        await update.message.reply_text("❌ Ошибка")

async def password_command(self, update, context):
    import string
    length = 12
    if context.args and context.args[0].isdigit():
        length = min(int(context.args[0]), 50)
    chars = string.ascii_letters + string.digits + "!@#$%"
    pwd = ''.join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(f"🔐 ПАРОЛЬ:\n\n`{pwd}`", parse_mode='Markdown')

async def qr_command(self, update, context):
    if not context.args:
        await update.message.reply_text("📱 Пример: /qr https://google.com")
        return
    text = " ".join(context.args)
    url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={requests.utils.quote(text)}"
    try:
        await context.bot.send_photo(update.effective_chat.id, url)
    except:
        await update.message.reply_text("❌ Ошибка QR")

async def weather_command(self, update, context):
    if not context.args:
        await update.message.reply_text("🌤️ Пример: /weather Москва")
        return
    city = " ".join(context.args)
    
    if OPENWEATHER_API_KEY:
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
            r = requests.get(url, timeout=10).json()
            if r.get("cod") == 200:
                text = f"""🌤️ {city.upper()}
```

🌡️ {round(r[“main”][“temp”])}°C
☁️ {r[“weather”][0][“description”]}
💧 {r[“main”][“humidity”]}%”””
await update.message.reply_text(text)
return
except:
pass

    try:
        url = f"https://wttr.in/{city}?format=%C+%t&lang=ru"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            await update.message.reply_text(f"🌤️ {city.upper()}\n\n{r.text.strip()}")
    except:
        await update.message.reply_text("❌ Ошибка погоды")

async def translate_command(self, update, context):
    if len(context.args) < 2:
        await update.message.reply_text("🌐 /translate en Привет!")
        return
    if not self.gemini_model:
        await update.message.reply_text("❌ AI недоступен")
        return
    lang = context.args[0]
    text = " ".join(context.args[1:])
    try:
        prompt = f"Переведи на {lang}: {text}"
        r = self.gemini_model.generate_content(prompt)
        await update.message.reply_text(f"🌐 {r.text}")
    except:
        await update.message.reply_text("❌ Ошибка перевода")

async def rank_command(self, update, context):
    user_data = await self.get_user_data(update)
    level = user_data.get('level', 1)
    exp = user_data.get('experience', 0)
    req = level * 100
    progress = (exp / req) * 100
    bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
    
    text = f"""🏅 УРОВЕНЬ

👤 {user_data[‘first_name’]}
🆙 Уровень: {level}
⭐ Опыт: {exp}/{req}
📊 {bar} {progress:.0f}%”””
await update.message.reply_text(text)

async def stats_command(self, update, context):
    user_data = await self.get_user_data(update)
    notes = self.db.get_notes(user_data['user_id'])
    
    text = f"""📊 СТАТИСТИКА

👤 {user_data[‘first_name’]}
🆙 Уровень: {user_data.get(‘level’, 1)}
⭐ Опыт: {user_data.get(‘experience’, 0)}
📝 Заметок: {len(notes)}
🌐 {LANGUAGE_NAMES.get(user_data.get(‘language’, ‘ru’))}”””
await update.message.reply_text(text)

```
async def button_callback(self, update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("lang_"):
        lang = query.data.split("_")[1]
        user_data = await self.get_user_data(update)
        user_data['language'] = lang
        self.db.save_user(user_data)
        await query.edit_message_text(f"✅ {LANGUAGE_NAMES[lang]}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅",
            reply_markup=self.get_keyboard(lang)
        )

async def grant_vip_command(self, update, context):
    if not self.is_creator(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("💎 /grant_vip [user_id] [week/month/year/permanent]")
        return
    try:
        target_id = int(context.args[0])
        duration = context.args[1].lower()
        user = self.db.get_user(target_id)
        if not user:
            await update.message.reply_text("❌ Не найден")
            return
        user['is_vip'] = 1
        if duration == "week":
            user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(weeks=1)).isoformat()
        elif duration == "month":
            user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
        elif duration == "permanent":
            user['vip_expires'] = None
        self.db.save_user(user)
        await update.message.reply_text(f"✅ VIP выдан {target_id}")
    except:
        await update.message.reply_text("❌ Ошибка")

async def broadcast_command(self, update, context):
    if not self.is_creator(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("📢 /broadcast [текст]")
        return
    msg = " ".join(context.args)
    users = self.db.get_all_users()
    sent = 0
    for user in users:
        try:
            await context.bot.send_message(user['user_id'], f"📢 {msg}")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ Отправлено: {sent}/{len(users)}")

async def users_command(self, update, context):
    if not self.is_creator(update.effective_user.id):
        return
    users = self.db.get_all_users()
    text = f"👥 ПОЛЬЗОВАТЕЛЕЙ: {len(users)}\n\n"
    for user in users[:15]:
        text += f"👤 {user['first_name']} (ID: {user['user_id']})\n"
    if len(users) > 15:
        text += f"\n... и ещё {len(users) - 15}"
    await update.message.reply_text(text)

async def backup_command(self, update, context):
    if not self.is_creator(update.effective_user.id):
        return
    try:
        self.memory.save()
        await update.message.reply_text(f"✅ Бэкап создан!\n👥 {len(self.db.get_all_users())}")
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def self_ping(self):
    try:
        requests.get(RENDER_URL, timeout=10)
        logger.info("Ping OK")
    except:
        pass

async def run_bot(self):
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found!")
        return
    
    logger.info("Starting bot v2.1...")
    
    app = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).build()
    
    async def error_handler(update, context):
        logger.error(f"Error: {context.error}")
    
    app.add_error_handler(error_handler)
    
    # Все команды
    commands = [
        ("start", self.start_command),
        ("help", self.help_command),
        ("info", self.info_command),
        ("status", self.status_command),
        ("time", self.time_command),
        ("date", self.date_command),
        ("language", self.language_command),
        ("ai", self.ai_command),
        ("clearhistory", self.clearhistory_command),
        ("note", self.note_command),
        ("notes", self.notes_command),
        ("delnote", self.delnote_command),
        ("joke", self.joke_command),
        ("fact", self.fact_command),
        ("quote", self.quote_command),
        ("coin", self.coin_command),
        ("dice", self.dice_command),
        ("8ball", self.eightball_command),
        ("math", self.math_command),
        ("calculate", self.calculate_command),
        ("password", self.password_command),
        ("qr", self.qr_command),
        ("weather", self.weather_command),
        ("translate", self.translate_command),
        ("rank", self.rank_command),
        ("stats", self.stats_command),
        ("grant_vip", self.grant_vip_command),
        ("broadcast", self.broadcast_command),
        ("users", self.users_command),
        ("backup", self.backup_command)
    ]
    
    for cmd, handler in commands:
        app.add_handler(CommandHandler(cmd, handler))
    
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        self.handle_message
    ))
    
    app.add_handler(CallbackQueryHandler(self.button_callback))
    
    # Scheduler
    loop = asyncio.get_running_loop()
    self.scheduler.configure(event_loop=loop)
    self.scheduler.start()
    self.scheduler.add_job(self.self_ping, 'interval', minutes=14)
    
    logger.info("Bot started!")
    logger.info(f"Users: {len(self.db.get_all_users())}")
    
    await app.run_polling(drop_pending_updates=True)

async def main():
bot = TelegramBot()
await bot.run_bot()

# Flask

app = Flask(**name**)

@app.route(’/’)
def home():
return f”””<html>

<head><title>Telegram AI Bot v2.1</title>
<style>
body {{font-family: Arial; background: linear-gradient(135deg, #667eea, #764ba2); 
      color: white; padding: 50px; text-align: center;}}
.container {{background: rgba(255,255,255,0.1); border-radius: 20px; 
            padding: 30px; max-width: 600px; margin: 0 auto;}}
h1 {{font-size: 48px;}}
.status {{color: #00ff88; font-weight: bold;}}
</style>
</head>
<body>
<div class="container">
<h1>🤖 Telegram AI Bot</h1>
<p class="status">✅ РАБОТАЕТ</p>
<p>📅 v2.1</p>
<p>⏰ {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
<p>Бот: {BOT_USERNAME}</p>
</div>
</body>
</html>"""

@app.route(’/health’)
def health():
return {“status”: “ok”, “time”: datetime.datetime.now().isoformat()}

if **name** == “**main**”:
from threading import Thread

port = int(os.getenv("PORT", 8080))
flask_thread = Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port, 'debug': False, 'use_reloader': False})
flask_thread.daemon = True
flask_thread.start()

logger.info(f"Flask started on port {port}")

try:
    asyncio.run(main())
except KeyboardInterrupt:
    logger.info("Stopped")
except Exception as e:
    logger.error(f"Fatal error: {e}")
    sys.exit(1)
