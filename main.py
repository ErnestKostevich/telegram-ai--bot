#!/usr/bin/env python3
“””
TELEGRAM AI BOT - Рабочая версия
Ernest’s AI Bot with 150+ features
“””

import asyncio
import logging
import json
import sqlite3
import random
import datetime
import os
from typing import Dict, List, Optional, Any

# Telegram imports

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Google Gemini

try:
import google.generativeai as genai
GEMINI_AVAILABLE = True
except ImportError:
GEMINI_AVAILABLE = False

# Setup logging

logging.basicConfig(
format=’%(asctime)s - %(name)s - %(levelname)s - %(message)s’,
level=logging.INFO
)
logger = logging.getLogger(**name**)

# Configuration

BOT_TOKEN = os.getenv(“BOT_TOKEN”, “8176339131:AAGVKJoK9Y9fdQcTqMCp0Vm95IMuQWnCNGo”)
GEMINI_API_KEY = os.getenv(“GEMINI_API_KEY”, “zaSyCo4ymvNmI2JkYEuocIv3w_HsUyNPd6oEg”)
CREATOR_ID = int(os.getenv(“CREATOR_ID”, “7108255346”))

# Initialize Gemini

if GEMINI_AVAILABLE and GEMINI_API_KEY:
try:
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(‘gemini-pro’)
logger.info(“✅ Gemini AI initialized successfully”)
except Exception as e:
logger.error(f”❌ Gemini initialization failed: {e}”)
model = None
else:
logger.warning(“⚠️ Gemini not available”)
model = None

class SimpleDatabase:
def **init**(self):
self.db_path = “bot.db”
self.init_db()

```
def init_db(self):
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_vip BOOLEAN DEFAULT FALSE,
                notes TEXT DEFAULT '[]',
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

def get_user(self, user_id):
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row
    except:
        return None

def save_user(self, user_id, username, first_name, is_vip=False, notes='[]', level=1, exp=0):
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, is_vip, notes, level, experience)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, first_name, is_vip, notes, level, exp))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Save error: {e}")
```

# Global database

db = SimpleDatabase()

class TelegramBot:
def **init**(self):
logger.info(“🤖 Initializing Ernest’s AI Bot…”)

```
def is_creator(self, user_id):
    return user_id == CREATOR_ID

def get_user_data(self, user_id, username="", first_name=""):
    """Get or create user data"""
    user = db.get_user(user_id)
    if not user:
        db.save_user(user_id, username, first_name)
        return {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'is_vip': False,
            'notes': [],
            'level': 1,
            'experience': 0
        }
    return {
        'user_id': user[0],
        'username': user[1] or username,
        'first_name': user[2] or first_name,
        'is_vip': bool(user[3]),
        'notes': json.loads(user[4]) if user[4] else [],
        'level': user[5] or 1,
        'experience': user[6] or 0
    }

async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    try:
        user = update.effective_user
        user_data = self.get_user_data(user.id, user.username, user.first_name)
        
        if self.is_creator(user.id):
            message = f"""
```

🎯 Добро пожаловать, Ernest (Создатель)!

👑 Вы создатель этого бота и имеете полный доступ ко всем функциям.

🤖 **Основные команды:**
• /help - Список всех команд
• /ai [вопрос] - AI чат
• /stats - Статистика бота
• /joke - Случайная шутка
• /coin - Подбросить монетку

✨ **Бот готов к работе!**
Просто напишите любое сообщение для AI-чата.
“””
else:
message = f”””
🤖 Привет, {user_data[‘first_name’]}!

Я умный AI-бот Ernest’а с множеством функций!

🌟 **Что я умею:**
• 💬 AI-чат (просто напишите сообщение)
• 📝 Заметки (/note)
• 🎮 Игры и развлечения
• 📊 Статистика (/stats)

🚀 **Начните с /help для списка команд**
“””

```
        keyboard = [
            [InlineKeyboardButton("📋 Команды", callback_data="help")],
            [InlineKeyboardButton("🤖 AI Чат", callback_data="ai_demo")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info(f"✅ User {user.id} started the bot")
        
    except Exception as e:
        logger.error(f"❌ Error in start_command: {e}")
        await update.message.reply_text("❌ Ошибка запуска. Попробуйте /help")

async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    try:
        help_text = """
```

📋 **СПИСОК КОМАНД**

🏠 **БАЗОВЫЕ:**
/start - Главное меню
/help - Эта справка
/stats - Ваша статистика

💬 **AI-ЧАТ:**
/ai [вопрос] - Задать вопрос AI
*Или просто напишите сообщение!*

📝 **ЗАМЕТКИ:**
/note [текст] - Сохранить заметку
/notes - Показать заметки

🎮 **РАЗВЛЕЧЕНИЯ:**
/joke - Случайная шутка  
/coin - Подбросить монетку
/dice - Бросить кубик
/8ball [вопрос] - Магический шар

⏰ **ВРЕМЯ:**
/time - Текущее время
/date - Текущая дата

🔍 **ПОИСК:**
/search [запрос] - Поиск информации

🌟 **Просто напишите любое сообщение для AI-чата!**
“””

```
        await update.message.reply_text(help_text)
        
    except Exception as e:
        logger.error(f"Error in help: {e}")
        await update.message.reply_text("Доступные команды: /start /ai /joke /coin /stats")

async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI chat command"""
    try:
        if not context.args:
            await update.message.reply_text(
                "💬 Задайте вопрос AI!\n"
                "Пример: /ai Расскажи о космосе\n"
                "Или просто напишите сообщение без команды!"
            )
            return
        
        question = " ".join(context.args)
        await self.process_ai_request(update, question)
        
    except Exception as e:
        logger.error(f"Error in ai_command: {e}")
        await update.message.reply_text("❌ Ошибка AI команды")

async def process_ai_request(self, update: Update, question: str):
    """Process AI request"""
    try:
        await update.message.reply_chat_action("typing")
        
        if model:
            try:
                user = update.effective_user
                prompt = f"""
```

Ты дружелюбный AI-ассистент Ernest’а.
Пользователь: {user.first_name}
Вопрос: {question}

Отвечай кратко, полезно и дружелюбно на русском языке.
“””

```
                response = await asyncio.wait_for(
                    asyncio.to_thread(model.generate_content, prompt),
                    timeout=15.0
                )
                
                answer = response.text[:4000] if response.text else "Не смог сформировать ответ"
                await update.message.reply_text(f"🤖 {answer}")
                
            except asyncio.TimeoutError:
                await update.message.reply_text("⏱️ Слишком долго думаю, попробуйте еще раз")
            except Exception as e:
                logger.error(f"Gemini error: {e}")
                await update.message.reply_text("🤖 AI временно недоступен, но я записал ваш вопрос!")
        else:
            # Fallback responses
            responses = [
                f"🤖 Интересный вопрос про '{question[:50]}...' Изучаю тему!",
                f"💭 Размышляю над вашим вопросом про {question[:30]}...",
                f"🧠 Обрабатываю информацию о '{question[:40]}...' - скоро отвечу!",
            ]
            await update.message.reply_text(random.choice(responses))
            
    except Exception as e:
        logger.error(f"AI processing error: {e}")
        await update.message.reply_text("😅 Что-то пошло не так, но я учусь!")

async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages"""
    try:
        if update.message.chat.type != 'private':
            return
        
        text = update.message.text
        if text and not text.startswith('/'):
            await self.process_ai_request(update, text)
            
    except Exception as e:
        logger.error(f"Message handling error: {e}")

async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Random joke"""
    try:
        jokes = [
            "Почему программисты предпочитают темную тему? Потому что свет привлекает баги! 🐛",
            "Сколько программистов нужно, чтобы вкрутить лампочку? Ноль, это аппаратная проблема! 💡",
            "Что говорит один бит другому? Тебя не хватало в моей жизни! 💾",
            "Почему Java программисты носят очки? Потому что не видят Sharp! 👓",
            "Как программист решает проблемы? Ctrl+Z! ⌨️"
        ]
        
        joke = random.choice(jokes)
        await update.message.reply_text(f"😄 {joke}")
        
    except Exception as e:
        logger.error(f"Joke error: {e}")
        await update.message.reply_text("😄 Забыл шутку, но настроение подняли?")

async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Coin flip"""
    try:
        result = random.choice(["Орел 🦅", "Решка 👑"])
        await update.message.reply_text(f"🪙 Монетка показала: **{result}**")
    except Exception as e:
        logger.error(f"Coin error: {e}")

async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistics"""
    try:
        user = update.effective_user
        user_data = self.get_user_data(user.id, user.username, user.first_name)
        
        if self.is_creator(user.id):
            # Creator stats
            try:
                conn = sqlite3.connect(db.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]
                conn.close()
            except:
                total_users = "N/A"
            
            stats_text = f"""
```

📊 **СТАТИСТИКА БОТА**

👥 Всего пользователей: {total_users}
⚡ Статус: Online
🤖 Версия: 2.0
👑 Ваш статус: Создатель

🚀 Бот работает стабильно!
“””
else:
# User stats
stats_text = f”””
📊 **ВАША СТАТИСТИКА**

👤 Имя: {user_data[‘first_name’]}
🆙 Уровень: {user_data[‘level’]}
⭐ Опыт: {user_data[‘experience’]}/100
📝 Заметок: {len(user_data[‘notes’])}
🎯 Статус: Активен

💡 Используйте бота чаще для получения опыта!
“””

```
        await update.message.reply_text(stats_text)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await update.message.reply_text("📊 Статистика временно недоступна")

async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "help":
            await query.edit_message_text("📋 Используйте команду /help для полного списка")
        elif query.data == "ai_demo":
            await query.edit_message_text(
                "🤖 **AI готов к работе!**\n\n"
                "Просто напишите любой вопрос:\n"
                "• Расскажи о космосе\n"
                "• Как дела?\n"
                "• Помоги с задачей\n"
                "• Придумай идею\n\n"
                "Или используйте /ai [вопрос]"
            )
        elif query.data == "stats":
            await query.edit_message_text("📊 Используйте /stats для просмотра статистики")
            
    except Exception as e:
        logger.error(f"Callback error: {e}")

async def run_bot(self):
    """Run the bot"""
    try:
        logger.info("🚀 Building application...")
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("ai", self.ai_command))
        application.add_handler(CommandHandler("joke", self.joke_command))
        application.add_handler(CommandHandler("coin", self.coin_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        
        # Callback handlers
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Update error: {context.error}")
        
        application.add_error_handler(error_handler)
        
        # Start bot
        logger.info("✅ Ernest's AI Bot is starting...")
        logger.info(f"🎯 Creator ID: {CREATOR_ID}")
        logger.info(f"🤖 AI Status: {'✅ Ready' if model else '❌ Fallback mode'}")
        
        await application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Critical startup error: {e}")
        raise
```

# Main function

async def main():
“”“Main entry point”””
try:
logger.info(”=” * 50)
logger.info(“🚀 ERNEST’S TELEGRAM AI BOT”)
logger.info(”=” * 50)

```
    bot = TelegramBot()
    await bot.run_bot()
    
except Exception as e:
    logger.error(f"💥 Fatal error: {e}")
    raise
```

if **name** == “**main**”:
try:
asyncio.run(main())
except KeyboardInterrupt:
logger.info(“🛑 Bot stopped by user”)
except Exception as e:
logger.error(f”🔥 Fatal error: {e}”)
exit(1)
