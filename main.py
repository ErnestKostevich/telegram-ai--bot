#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM AI BOT v2.0 - Полностью переработанная версия
С долговременной памятью, актуальными данными и улучшенной архитектурой
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
import sqlite3
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from newsapi import NewsApiClient
import nest_asyncio
from flask import Flask
import pytz
from github import Github
from collections import defaultdict

nest_asyncio.apply()

# Telegram Bot API
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ChatType
from telegram.error import Conflict, TimedOut, NetworkError

# Google Gemini
import google.generativeai as genai

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# API ключи
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CURRENCY_API_KEY = os.getenv("FREECURRENCY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# GitHub для бэкапов
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "ErnestKostevich/telegram-ai--bot"

# Константы
CREATOR_ID = 7108255346
CREATOR_USERNAME = "@Ernest_Kostevich"
DAD_USERNAME = "@mkostevich"
DAD_BIRTHDAY = "10-03"  # Формат MM-DD
BOT_USERNAME = "@AI_DISCO_BOT"

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL = os.getenv("MODEL", "gemini-2.0-flash-exp")

# Render URL
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-ai--bot.onrender.com")

# Пути к файлам
DB_PATH = "bot_database.db"
CONVERSATIONS_PATH = "conversations.json"
BACKUP_PATH = "backups"

# Создаём директорию для бэкапов
Path(BACKUP_PATH).mkdir(exist_ok=True)

# ============================================================================
# БАЗА ДАННЫХ SQLite
# ============================================================================

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()
        logger.info("База данных инициализирована")
    
    def get_connection(self):
        """Создать подключение к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_vip INTEGER DEFAULT 0,
                vip_expires TEXT,
                language TEXT DEFAULT 'ru',
                birthday TEXT,
                nickname TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                theme TEXT DEFAULT 'default',
                color TEXT DEFAULT 'blue',
                sound_notifications INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_activity TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заметок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица напоминаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reminder_text TEXT,
                reminder_time TEXT,
                job_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица памяти пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                key TEXT,
                value TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, key)
            )
        ''')
        
        # Таблица достижений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                achievement TEXT,
                earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица логов команд
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT,
                message TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица статистики команд
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_stats (
                command TEXT PRIMARY KEY,
                usage_count INTEGER DEFAULT 0,
                last_used TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить данные пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def save_user(self, user_data: Dict):
        """Сохранить/обновить пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        user_data['last_activity'] = datetime.datetime.now().isoformat()
        
        existing = self.get_user(user_data['user_id'])
        
        if existing:
            cursor.execute('''
                UPDATE users SET 
                    username=?, first_name=?, is_vip=?, vip_expires=?,
                    language=?, birthday=?, nickname=?, level=?, experience=?,
                    theme=?, color=?, sound_notifications=?, last_activity=?
                WHERE user_id=?
            ''', (
                user_data.get('username', ''),
                user_data.get('first_name', ''),
                user_data.get('is_vip', 0),
                user_data.get('vip_expires'),
                user_data.get('language', 'ru'),
                user_data.get('birthday'),
                user_data.get('nickname'),
                user_data.get('level', 1),
                user_data.get('experience', 0),
                user_data.get('theme', 'default'),
                user_data.get('color', 'blue'),
                user_data.get('sound_notifications', 1),
                user_data['last_activity'],
                user_data['user_id']
            ))
        else:
            cursor.execute('''
                INSERT INTO users (
                    user_id, username, first_name, is_vip, vip_expires,
                    language, birthday, nickname, level, experience,
                    theme, color, sound_notifications, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['user_id'],
                user_data.get('username', ''),
                user_data.get('first_name', ''),
                user_data.get('is_vip', 0),
                user_data.get('vip_expires'),
                user_data.get('language', 'ru'),
                user_data.get('birthday'),
                user_data.get('nickname'),
                user_data.get('level', 1),
                user_data.get('experience', 0),
                user_data.get('theme', 'default'),
                user_data.get('color', 'blue'),
                user_data.get('sound_notifications', 1),
                user_data['last_activity']
            ))
        
        conn.commit()
        conn.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Найти пользователя по юзернейму"""
        conn = self.get_connection()
        cursor = conn.cursor()
        username_clean = username.lstrip('@').lower()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = ?", (username_clean,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def log_command(self, user_id: int, command: str, message: str = ""):
        """Логировать выполнение команды"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Добавить лог
        cursor.execute('''
            INSERT INTO command_logs (user_id, command, message, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, command, message, datetime.datetime.now().isoformat()))
        
        # Обновить статистику
        cursor.execute('''
            INSERT INTO command_stats (command, usage_count, last_used)
            VALUES (?, 1, ?)
            ON CONFLICT(command) DO UPDATE SET
                usage_count = usage_count + 1,
                last_used = ?
        ''', (command, datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY last_activity DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_vip_users(self) -> List[Dict]:
        """Получить VIP пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE is_vip = 1")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_popular_commands(self, limit: int = 10) -> List[tuple]:
        """Получить популярные команды"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT command, usage_count, last_used 
            FROM command_stats 
            ORDER BY usage_count DESC 
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [(row['command'], {'usage_count': row['usage_count'], 'last_used': row['last_used']}) for row in rows]
    
    # Методы для заметок
    def add_note(self, user_id: int, note: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (user_id, note) VALUES (?, ?)", (user_id, note))
        conn.commit()
        conn.close()
    
    def get_notes(self, user_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def delete_note(self, note_id: int, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def clear_notes(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    # Методы для памяти
    def save_memory(self, user_id: int, key: str, value: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO memory (user_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value = ?, created_at = CURRENT_TIMESTAMP
        ''', (user_id, key, value, value))
        conn.commit()
        conn.close()
    
    def get_memory(self, user_id: int, key: str) -> Optional[str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM memory WHERE user_id = ? AND key = ?", (user_id, key))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None
    
    def get_all_memory(self, user_id: int) -> Dict[str, str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM memory WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in rows}
    
    def delete_memory(self, user_id: int, key: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory WHERE user_id = ? AND key = ?", (user_id, key))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    # Методы для напоминаний
    def add_reminder(self, user_id: int, text: str, reminder_time: str, job_id: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reminders (user_id, reminder_text, reminder_time, job_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, text, reminder_time, job_id))
        conn.commit()
        conn.close()
    
    def get_reminders(self, user_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reminders WHERE user_id = ? ORDER BY reminder_time", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    # Методы для достижений
    def add_achievement(self, user_id: int, achievement: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO achievements (user_id, achievement) VALUES (?, ?)
        ''', (user_id, achievement))
        conn.commit()
        conn.close()
    
    def get_achievements(self, user_id: int) -> List[str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT achievement FROM achievements WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [row['achievement'] for row in rows]

# ============================================================================
# СИСТЕМА ДОЛГОВРЕМЕННОЙ ПАМЯТИ РАЗГОВОРОВ
# ============================================================================

class ConversationMemory:
    def __init__(self, filepath: str = CONVERSATIONS_PATH):
        self.filepath = filepath
        self.conversations = self._load_conversations()
        logger.info("Система памяти разговоров инициализирована")
    
    def _load_conversations(self) -> Dict:
        """Загрузить историю разговоров"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Загружено {len(data)} разговоров")
                    return data
            except Exception as e:
                logger.error(f"Ошибка загрузки разговоров: {e}")
                return {}
        return {}
    
    def _save_conversations(self):
        """Сохранить историю разговоров"""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.conversations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения разговоров: {e}")
    
    def add_message(self, user_id: int, role: str, content: str):
        """Добавить сообщение в историю"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.conversations:
            self.conversations[user_id_str] = {
                'messages': [],
                'created_at': datetime.datetime.now().isoformat(),
                'last_updated': datetime.datetime.now().isoformat()
            }
        
        self.conversations[user_id_str]['messages'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        self.conversations[user_id_str]['last_updated'] = datetime.datetime.now().isoformat()
        
        # Автосохранение каждые 10 сообщений
        if len(self.conversations[user_id_str]['messages']) % 10 == 0:
            self._save_conversations()
    
    def get_context(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Получить последние N сообщений для контекста"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.conversations:
            return []
        
        messages = self.conversations[user_id_str]['messages']
        return messages[-limit:] if len(messages) > limit else messages
    
    def get_full_history(self, user_id: int) -> List[Dict]:
        """Получить всю историю разговора"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.conversations:
            return []
        
        return self.conversations[user_id_str]['messages']
    
    def clear_history(self, user_id: int):
        """Очистить историю пользователя"""
        user_id_str = str(user_id)
        
        if user_id_str in self.conversations:
            del self.conversations[user_id_str]
            self._save_conversations()
    
    def save(self):
        """Принудительно сохранить все разговоры"""
        self._save_conversations()
    
    def get_stats(self) -> Dict:
        """Получить статистику разговоров"""
        total_users = len(self.conversations)
        total_messages = sum(len(conv['messages']) for conv in self.conversations.values())
        
        return {
            'total_users': total_users,
            'total_messages': total_messages,
            'avg_messages_per_user': total_messages / total_users if total_users > 0 else 0
        }

# ============================================================================
# ОСНОВНОЙ КЛАСС БОТА
# ============================================================================

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.conversation_memory = ConversationMemory()
        self.gemini_model = None
        
        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(MODEL)
                logger.info("Gemini модель инициализирована")
            except Exception as e:
                logger.error(f"Ошибка инициализации Gemini: {e}")
        
        self.scheduler = AsyncIOScheduler()
        self.news_api = NewsApiClient(api_key=NEWSAPI_KEY) if NEWSAPI_KEY else None
        self.maintenance_mode = False
        
        # GitHub для бэкапов
        self.github = None
        if GITHUB_TOKEN:
            try:
                self.github = Github(GITHUB_TOKEN)
                self.repo = self.github.get_repo(GITHUB_REPO)
                logger.info("GitHub подключен для бэкапов")
            except Exception as e:
                logger.error(f"Ошибка подключения GitHub: {e}")
    
    async def get_user_data(self, update: Update) -> Dict:
        """Получить или создать данные пользователя"""
        user = update.effective_user
        user_data = self.db.get_user(user.id)
        
        if not user_data:
            user_data = {
                'user_id': user.id,
                'username': user.username or "",
                'first_name': user.first_name or "",
                'is_vip': 0,
                'vip_expires': None,
                'language': 'ru',
                'birthday': None,
                'nickname': None,
                'level': 1,
                'experience': 0,
                'theme': 'default',
                'color': 'blue',
                'sound_notifications': 1
            }
            
            # Автоматический VIP для создателя
            if self.is_creator(user.id):
                user_data['is_vip'] = 1
                user_data['vip_expires'] = None
                logger.info(f"Создатель получил VIP: {user.id}")
            
            self.db.save_user(user_data)
            logger.info(f"Создан новый пользователь: {user.id} ({user.first_name})")
        
        return user_data
    
    def is_creator(self, user_id: int) -> bool:
        """Проверка создателя"""
        return user_id == CREATOR_ID
    
    def is_vip(self, user_data: Dict) -> bool:
        """Проверка VIP статуса"""
        if not user_data.get('is_vip'):
            return False
        
        if user_data.get('vip_expires'):
            try:
                expires_date = datetime.datetime.fromisoformat(user_data['vip_expires'])
                if datetime.datetime.now() > expires_date:
                    user_data['is_vip'] = 0
                    user_data['vip_expires'] = None
                    self.db.save_user(user_data)
                    return False
            except:
                return False
        
        return True
    
    async def add_experience(self, user_data: Dict, points: int = 1):
        """Добавить опыт пользователю"""
        user_data['experience'] = user_data.get('experience', 0) + points
        
        required_exp = user_data.get('level', 1) * 100
        if user_data['experience'] >= required_exp:
            user_data['level'] = user_data.get('level', 1) + 1
            user_data['experience'] = 0
            
            achievement = f"Достигнут {user_data['level']} уровень!"
            achievements = self.db.get_achievements(user_data['user_id'])
            if achievement not in achievements:
                self.db.add_achievement(user_data['user_id'], achievement)
        
        self.db.save_user(user_data)
    
    async def send_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        """Отправить уведомление"""
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления {user_id}: {e}")
    
    async def check_birthdays(self, context: ContextTypes.DEFAULT_TYPE):
        """Проверка дней рождения"""
        today = datetime.datetime.now().strftime("%m-%d")
        
        # Проверка дня рождения папы
        if today == DAD_BIRTHDAY:
            dad_user = self.db.get_user_by_username("mkostevich")
            if dad_user:
                try:
                    await context.bot.send_message(
                        dad_user['user_id'],
                        "🎉🎂 С Днём Рождения, папа! 🎂🎉\n\n"
                        "Желаю здоровья, счастья и исполнения всех желаний!\n"
                        "Пусть этот год принесёт много радости и успехов!\n\n"
                        "С любовью, твой сын Ernest ❤️"
                    )
                    logger.info("Отправлено поздравление папе!")
                except Exception as e:
                    logger.error(f"Ошибка отправки поздравления: {e}")
        
        # Проверка дней рождения других пользователей
        all_users = self.db.get_all_users()
        for user in all_users:
            if user.get('birthday') and user['birthday'][5:] == today:  # Формат YYYY-MM-DD
                try:
                    await context.bot.send_message(
                        user['user_id'],
                        f"🎉🎂 С Днём Рождения, {user['first_name']}! 🎂🎉\n\n"
                        "Желаем счастья, здоровья и исполнения всех желаний!"
                    )
                    logger.info(f"Отправлено поздравление пользователю {user['user_id']}")
                except:
                    pass
    
    # ========================================================================
    # БАЗОВЫЕ КОМАНДЫ
    # ========================================================================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/start")
        
        if self.is_creator(user_data['user_id']):
            message = """
🎯 Добро пожаловать, Создатель!

👑 Команды создателя:
• /grant_vip - Выдать VIP
• /revoke_vip - Отозвать VIP
• /stats - Полная статистика
• /broadcast - Рассылка
• /users - Список пользователей
• /maintenance - Режим обслуживания
• /backup - Резервная копия

🤖 Используйте /help для полного списка команд.
            """
        elif self.is_vip(user_data):
            nickname = user_data.get('nickname') or user_data['first_name']
            expires_text = 'бессрочно'
            if user_data.get('vip_expires'):
                try:
                    expires_date = datetime.datetime.fromisoformat(user_data['vip_expires'])
                    expires_text = expires_date.strftime('%d.%m.%Y')
                except:
                    pass
            
            message = f"""
💎 Добро пожаловать, {nickname}!
VIP статус до: {expires_text}

⭐ VIP возможности:
• /remind - Напоминания
• /reminders - Список напоминаний
• /nickname - Установить никнейм
• /profile - Ваш профиль

🤖 Используйте /help для полного списка команд.
            """
        else:
            message = f"""
🤖 Привет, {user_data['first_name']}!
Я AI-бот с 50+ функциями!

🌟 Основное:
• 💬 AI-чат с Gemini 2.0
• 📝 Заметки и память
• 🌤️ Погода и новости
• 🎮 Игры и развлечения
• 💰 Курсы валют
• 🌐 Переводы и утилиты

💎 Хотите VIP? Спросите о возможностях!
🤖 Используйте /help для списка команд.
            """
        
        keyboard = [
            [InlineKeyboardButton("📋 Помощь", callback_data="help"),
             InlineKeyboardButton("💎 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🤖 AI чат", callback_data="ai_demo"),
             InlineKeyboardButton("📊 Статистика", callback_data="my_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        await self.add_experience(user_data, 1)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/help")
        
        help_text = """
📋 СПИСОК КОМАНД

🏠 БАЗОВЫЕ:
/start - Главное меню
/help - Эта справка
/info - О боте
/status - Статус системы
/uptime - Время работы

💬 AI-ЧАТ:
/ai [вопрос] - Задать вопрос
/clearhistory - Очистить историю
Просто пишите - бот запомнит весь разговор!

📝 ЗАМЕТКИ:
/note [текст] - Создать заметку
/notes - Показать заметки
/delnote [номер] - Удалить заметку
/findnote [слово] - Поиск в заметках
/clearnotes - Очистить все

⏰ ВРЕМЯ:
/time - Текущее время
/date - Текущая дата

🎮 РАЗВЛЕЧЕНИЯ:
/joke - Шутка
/fact - Факт
/quote - Цитата
/quiz - Викторина
/coin - Монетка
/dice - Кубик
/8ball [вопрос] - Магический шар

🔢 МАТЕМАТИКА:
/math [выражение] - Простые вычисления
/calculate [выражение] - Калькулятор

🛠️ УТИЛИТЫ:
/password [длина] - Генератор паролей
/qr [текст] - QR-код
/shorturl [ссылка] - Сократить URL
/ip - Информация об IP
/weather [город] - Погода
/currency [из] [в] - Конвертер валют
/translate [язык] [текст] - Перевод

🧠 ПАМЯТЬ:
/memorysave [ключ] [значение]
/memoryget [ключ]
/memorylist - Список
/memorydel [ключ]

📊 ПРОГРЕСС:
/rank - Ваш уровень
        """
        
        if self.is_vip(user_data):
            help_text += """
💎 VIP КОМАНДЫ:
/vip - VIP информация
/remind [минуты] [текст] - Напоминание
/reminders - Список напоминаний
/delreminder [номер] - Удалить
/nickname [имя] - Никнейм
/profile - Профиль
            """
        
        if self.is_creator(user_data['user_id']):
            help_text += """
👑 СОЗДАТЕЛЬ:
/grant_vip [user_id/@username] [week/month/year/permanent]
/revoke_vip [user_id/@username]
/broadcast [текст] - Рассылка
/users - Список пользователей
/stats - Полная статистика
/maintenance [on/off]
/backup - Резервная копия
            """
        
        await update.message.reply_text(help_text)
        await self.add_experience(user_data, 1)
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /info"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/info")
        
        conv_stats = self.conversation_memory.get_stats()
        
        info_text = f"""
🤖 О БОТЕ

Версия: 2.0 (Переработанная)
Создатель: Ernest {CREATOR_USERNAME}
Папа бота: {DAD_USERNAME}
Бот: {BOT_USERNAME}

🔧 Технологии:
• AI: {"Gemini 2.0 ✅" if self.gemini_model else "❌"}
• База: SQLite ✅
• Память: conversations.json ✅
• Хостинг: Render ✅

📊 Статистика памяти:
• Пользователей с историей: {conv_stats['total_users']}
• Всего сообщений: {conv_stats['total_messages']}
• В среднем: {conv_stats['avg_messages_per_user']:.1f} сообщений/юзер

⚡ Работает 24/7 с автопингом
        """
        await update.message.reply_text(info_text)
        await self.add_experience(user_data, 1)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/status")
        
        all_users = self.db.get_all_users()
        vip_users = self.db.get_vip_users()
        
        status_text = f"""
⚡ СТАТУС БОТА

Онлайн: ✅ Работает
Версия: 2.0
Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

👥 Пользователей: {len(all_users)}
💎 VIP: {len(vip_users)}

🔧 Системы:
• Gemini AI: {"✅" if self.gemini_model else "❌"}
• База данных: ✅ SQLite
• Память чата: ✅ conversations.json
• GitHub бэкапы: {"✅" if self.github else "❌"}
• Maintenance: {"🔧 Вкл" if self.maintenance_mode else "✅ Выкл"}
        """
        await update.message.reply_text(status_text)
        await self.add_experience(user_data, 1)
    
    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /uptime"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/uptime")
        
        all_users = self.db.get_all_users()
        conv_stats = self.conversation_memory.get_stats()
        
        uptime_text = f"""
⏱️ ВРЕМЯ РАБОТЫ БОТА

📅 Текущая дата: {datetime.datetime.now().strftime('%d.%m.%Y')}
🕐 Текущее время: {datetime.datetime.now().strftime('%H:%M:%S')}

📊 Статистика:
• 👥 Пользователей: {len(all_users)}
• 💬 Сообщений в памяти: {conv_stats['total_messages']}
• 📝 Заметок в базе: {sum(len(self.db.get_notes(u['user_id'])) for u in all_users)}

⚡ Бот работает 24/7 на Render!
        """
        await update.message.reply_text(uptime_text)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # AI ЧАТ С ДОЛГОВРЕМЕННОЙ ПАМЯТЬЮ
    # ========================================================================
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /ai с вопросом"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/ai")
        
        if not context.args:
            await update.message.reply_text("🤖 Задайте вопрос после /ai!\nПример: /ai Расскажи о космосе")
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI недоступен. Gemini API не настроен.")
            return
        
        query = " ".join(context.args)
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            # Получаем контекст из долговременной памяти
            history = self.conversation_memory.get_context(user_data['user_id'], limit=30)
            
            # Формируем промпт с контекстом
            context_str = ""
            if history:
                context_str = "История разговора:\n"
                for msg in history[-10:]:  # Последние 10 для контекста
                    role = "Пользователь" if msg['role'] == 'user' else "Ассистент"
                    context_str += f"{role}: {msg['content']}\n"
                context_str += "\n"
            
            prompt = f"""{context_str}Текущий вопрос пользователя: {query}

Ответь полезно и дружелюбно, учитывая предыдущий контекст разговора."""
            
            # Генерируем ответ
            response = self.gemini_model.generate_content(prompt)
            
            # Сохраняем в долговременную память
            self.conversation_memory.add_message(user_data['user_id'], 'user', query)
            self.conversation_memory.add_message(user_data['user_id'], 'assistant', response.text)
            
            await update.message.reply_text(response.text)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка AI: {str(e)}")
            logger.error(f"Ошибка Gemini: {e}")
        
        await self.add_experience(user_data, 2)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений (AI чат)"""
        if self.maintenance_mode and not self.is_creator(update.effective_user.id):
            await update.message.reply_text("🛠 Бот на обслуживании. Попробуйте позже.")
            return
        
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "message")
        
        if not self.gemini_model:
            await update.message.reply_text("❌ AI-чат недоступен. Используйте команды из /help")
            return
        
        message = update.message.text
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            # Получаем полную историю из долговременной памяти
            history = self.conversation_memory.get_context(user_data['user_id'], limit=50)
            
            # Формируем контекст для AI
            context_str = ""
            if history:
                context_str = "История разговора (последние 20 сообщений):\n"
                for msg in history[-20:]:
                    role = "👤 Пользователь" if msg['role'] == 'user' else "🤖 Ассистент"
                    context_str += f"{role}: {msg['content'][:200]}...\n" if len(msg['content']) > 200 else f"{role}: {msg['content']}\n"
                context_str += "\n"
            
            prompt = f"""Ты дружелюбный AI-ассистент в Telegram боте.

{context_str}
👤 Пользователь сейчас: {message}

Ответь полезно, учитывая весь предыдущий контекст разговора. Если пользователь ссылается на что-то из прошлого разговора, используй эту информацию."""
            
            # Генерируем ответ
            response = self.gemini_model.generate_content(prompt)
            
            # Сохраняем в долговременную память
            self.conversation_memory.add_message(user_data['user_id'], 'user', message)
            self.conversation_memory.add_message(user_data['user_id'], 'assistant', response.text)
            
            await update.message.reply_text(response.text)
            
        except Exception as e:
            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения.")
            logger.error(f"Ошибка обработки сообщения: {e}")
        
        await self.add_experience(user_data, 1)
    
    async def clearhistory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /clearhistory - очистить историю разговора"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/clearhistory")
        
        history = self.conversation_memory.get_full_history(user_data['user_id'])
        msg_count = len(history)
        
        self.conversation_memory.clear_history(user_data['user_id'])
        
        await update.message.reply_text(f"🗑️ История очищена!\nУдалено сообщений: {msg_count}")
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # ЗАМЕТКИ
    # ========================================================================
    
    async def note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /note - создать заметку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/note")
        
        if not context.args:
            await update.message.reply_text("📝 Укажите текст заметки!\nПример: /note Купить молоко")
            return
        
        note = " ".join(context.args)
        self.db.add_note(user_data['user_id'], note)
        
        await update.message.reply_text(f"✅ Заметка сохранена!\n\n📝 {note}")
        await self.add_experience(user_data, 1)
    
    async def notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /notes - показать все заметки"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/notes")
        
        notes = self.db.get_notes(user_data['user_id'])
        
        if not notes:
            await update.message.reply_text("❌ У вас нет заметок!\nСоздайте: /note [текст]")
            return
        
        notes_text = "📝 ВАШИ ЗАМЕТКИ:\n\n"
        for i, note in enumerate(notes, 1):
            created = datetime.datetime.fromisoformat(note['created_at']).strftime('%d.%m %H:%M')
            notes_text += f"{i}. {note['note']}\n   📅 {created}\n\n"
        
        if len(notes_text) > 4000:
            notes_text = notes_text[:4000] + "\n... (список обрезан)"
        
        await update.message.reply_text(notes_text)
        await self.add_experience(user_data, 1)
    
    async def delnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /delnote - удалить заметку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/delnote")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер заметки!\nПример: /delnote 1")
            return
        
        notes = self.db.get_notes(user_data['user_id'])
        index = int(context.args[0]) - 1
        
        if 0 <= index < len(notes):
            note_id = notes[index]['id']
            deleted = self.db.delete_note(note_id, user_data['user_id'])
            
            if deleted:
                await update.message.reply_text(f"✅ Заметка #{index+1} удалена!")
            else:
                await update.message.reply_text("❌ Ошибка удаления заметки!")
        else:
            await update.message.reply_text(f"❌ Заметки с номером {index+1} не существует!")
        
        await self.add_experience(user_data, 1)
    
    async def findnote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /findnote - поиск в заметках"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/findnote")
        
        if not context.args:
            await update.message.reply_text("🔍 Укажите ключевое слово!\nПример: /findnote работа")
            return
        
        keyword = " ".join(context.args).lower()
        notes = self.db.get_notes(user_data['user_id'])
        
        found = [(i+1, note) for i, note in enumerate(notes) if keyword in note['note'].lower()]
        
        if found:
            notes_text = f"🔍 Найдено ({len(found)}):\n\n"
            for i, note in found:
                created = datetime.datetime.fromisoformat(note['created_at']).strftime('%d.%m %H:%M')
                notes_text += f"{i}. {note['note']}\n   📅 {created}\n\n"
            
            await update.message.reply_text(notes_text)
        else:
            await update.message.reply_text(f"❌ Ничего не найдено по запросу: {keyword}")
        
        await self.add_experience(user_data, 1)
    
    async def clearnotes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /clearnotes - очистить все заметки"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/clearnotes")
        
        notes = self.db.get_notes(user_data['user_id'])
        count = len(notes)
        
        self.db.clear_notes(user_data['user_id'])
        
        await update.message.reply_text(f"🗑️ Очищено {count} заметок!")
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # ВРЕМЯ И ДАТА (АКТУАЛЬНЫЕ!)
    # ========================================================================
    
    async def time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /time - текущее время"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/time")
        
        # Текущее время в разных часовых поясах
        moscow_tz = pytz.timezone('Europe/Moscow')
        london_tz = pytz.timezone('Europe/London')
        ny_tz = pytz.timezone('America/New_York')
        tokyo_tz = pytz.timezone('Asia/Tokyo')
        
        now_utc = datetime.datetime.now(pytz.utc)
        
        moscow_time = now_utc.astimezone(moscow_tz)
        london_time = now_utc.astimezone(london_tz)
        ny_time = now_utc.astimezone(ny_tz)
        tokyo_time = now_utc.astimezone(tokyo_tz)
        
        time_text = f"""
⏰ ТЕКУЩЕЕ ВРЕМЯ

🇷🇺 Москва: {moscow_time.strftime('%H:%M:%S')}
🇬🇧 Лондон: {london_time.strftime('%H:%M:%S')}
🇺🇸 Нью-Йорк: {ny_time.strftime('%H:%M:%S')}
🇯🇵 Токио: {tokyo_time.strftime('%H:%M:%S')}

📅 Дата: {moscow_time.strftime('%d.%m.%Y')}
        """
        
        await update.message.reply_text(time_text)
        await self.add_experience(user_data, 1)
    
    async def date_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /date - текущая дата"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/date")
        
        now = datetime.datetime.now()
        
        # Названия дней недели и месяцев на русском
        days_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        months_ru = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                     'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
        
        day_of_week = days_ru[now.weekday()]
        month_name = months_ru[now.month - 1]
        
        date_text = f"""
📅 СЕГОДНЯ

🗓️ {day_of_week}
📆 {now.day} {month_name} {now.year} года
⏰ Время: {now.strftime('%H:%M:%S')}

📊 День года: {now.timetuple().tm_yday}/365
📈 Неделя: {now.isocalendar()[1]}/52
        """
        
        await update.message.reply_text(date_text)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # РАЗВЛЕЧЕНИЯ
    # ========================================================================
    
    async def joke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /joke - случайная шутка"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/joke")
        
        jokes = [
            "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 == Dec 25!",
            "Заходит программист в бар, заказывает 1 пиво. Заказывает 0 пива. Заказывает 999999 пива. Заказывает -1 пиво. Заказывает ящерицу...",
            "- Доктор, я думаю, что я компьютерный вирус!\n- Не волнуйтесь, примите эту таблетку.\n- А что это?\n- Антивирус!",
            "Почему Python программисты предпочитают Linux? Потому что Windows их сводит с ума!",
            "Есть 10 типов людей: те, кто понимает двоичную систему, и те, кто нет.",
            "Как программист моет посуду? Не моет - это не баг, это фича!",
            "Жена программиста просит: 'Сходи в магазин, купи батон хлеба. Если будут яйца - возьми десяток'. Он возвращается с 10 батонами...",
        ]
        
        await update.message.reply_text(f"😄 {random.choice(jokes)}")
        await self.add_experience(user_data, 1)
    
    async def fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /fact - интересный факт"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/fact")
        
        facts = [
            "🧠 Человеческий мозг содержит около 86 миллиардов нейронов!",
            "🌊 В океане больше исторических артефактов, чем во всех музеях мира вместе взятых!",
            "🐙 У осьминогов три сердца и голубая кровь!",
            "🌍 Если бы Земля была размером с яблоко, атмосфера была бы тоньше его кожуры!",
            "💻 Первый компьютерный вирус был создан в 1971 году и назывался 'Creeper'!",
            "🦈 Акулы существуют дольше, чем деревья - более 400 миллионов лет!",
            "🌙 Луна удаляется от Земли на 3.8 см каждый год!",
            "🐝 Пчела должна собрать нектар с 2 миллионов цветов, чтобы сделать 450 грамм мёда!",
        ]
        
        await update.message.reply_text(random.choice(facts))
        await self.add_experience(user_data, 1)
    
    async def quote_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /quote - вдохновляющая цитата"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/quote")
        
        quotes = [
            "💫 'Будь собой. Остальные роли уже заняты.' - Оскар Уайльд",
            "🚀 'Единственный способ сделать великую работу - любить то, что делаешь.' - Стив Джобс",
            "🎯 'Не бойтесь совершать ошибки - бойтесь не учиться на них.' - Неизвестный",
            "🌟 'Лучшее время посадить дерево было 20 лет назад. Второе лучшее время - сейчас.' - Китайская пословица",
            "💪 'Успех - это способность идти от неудачи к неудаче, не теряя энтузиазма.' - Уинстон Черчилль",
            "🎨 'Креативность - это интеллект, который веселится.' - Альберт Эйнштейн",
            "🔥 'Начни с того места, где ты сейчас. Используй то, что у тебя есть. Делай то, что можешь.' - Артур Эш",
        ]
        
        await update.message.reply_text(random.choice(quotes))
        await self.add_experience(user_data, 1)
    
    async def quiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /quiz - викторина"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/quiz")
        
        questions = [
            {"q": "Сколько дней в високосном году?", "a": "366"},
            {"q": "Столица Австралии?", "a": "Канберра"},
            {"q": "Самый большой океан?", "a": "Тихий"},
            {"q": "Сколько планет в Солнечной системе?", "a": "8"},
            {"q": "Самая длинная река в мире?", "a": "Амазонка"},
            {"q": "Сколько континентов на Земле?", "a": "7"},
        ]
        
        question = random.choice(questions)
        await update.message.reply_text(f"❓ ВИКТОРИНА\n\n{question['q']}\n\n💡 Напишите ответ!")
        await self.add_experience(user_data, 1)
    
    async def coin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /coin - подбросить монетку"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/coin")
        
        result = random.choice(["🪙 Орёл!", "🪙 Решка!"])
        await update.message.reply_text(result)
        await self.add_experience(user_data, 1)
    
    async def dice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /dice - бросить кубик"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/dice")
        
        result = random.randint(1, 6)
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        await update.message.reply_text(f"🎲 {dice_faces[result-1]} Выпало: {result}")
        await self.add_experience(user_data, 1)
    
    async def eightball_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /8ball - магический шар"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/8ball")
        
        if not context.args:
            await update.message.reply_text("🔮 Задайте вопрос!\nПример: /8ball Стоит ли мне учить Python?")
            return
        
        answers = [
            "✅ Да, определённо!",
            "✅ Можешь быть уверен!",
            "✅ Бесспорно!",
            "🤔 Возможно...",
            "🤔 Спроси позже",
            "🤔 Сейчас нельзя сказать",
            "❌ Мой ответ - нет",
            "❌ Очень сомнительно",
            "❌ Не рассчитывай на это"
        ]
        
        question = " ".join(context.args)
        await update.message.reply_text(f"🔮 Вопрос: {question}\n\n{random.choice(answers)}")
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # МАТЕМАТИКА
    # ========================================================================
    
    async def math_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /math - простые вычисления"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/math")
        
        if not context.args:
            await update.message.reply_text("🔢 Введите выражение!\nПример: /math 15 + 25 * 2")
            return
        
        expression = " ".join(context.args)
        
        try:
            # Проверка на разрешённые символы
            allowed_chars = set('0123456789+-*/()., ')
            if not all(c in allowed_chars for c in expression):
                await update.message.reply_text("❌ Разрешены только: цифры, +, -, *, /, ()")
                return
            
            result = eval(expression)
            await update.message.reply_text(f"🔢 {expression} = {result}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка вычисления! Проверьте выражение.")
        
        await self.add_experience(user_data, 1)
    
    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /calculate - продвинутый калькулятор"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/calculate")
        
        if not context.args:
            await update.message.reply_text(
                "🧮 КАЛЬКУЛЯТОР\n\n"
                "Функции: sqrt, sin, cos, tan, log, pi, e\n\n"
                "Примеры:\n"
                "• /calculate sqrt(16)\n"
                "• /calculate sin(pi/2)\n"
                "• /calculate log(100)"
            )
            return
        
        expression = " ".join(context.args)
        
        try:
            import math
            
            # Безопасные функции
            safe_dict = {
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "log": math.log,
                "log10": math.log10,
                "exp": math.exp,
                "pi": math.pi,
                "e": math.e,
                "pow": pow,
                "abs": abs
            }
            
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            await update.message.reply_text(f"🧮 {expression} = {result}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка вычисления!\nПроверьте формулу.")
        
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # УТИЛИТЫ
    # ========================================================================
    
    async def password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /password - генератор паролей"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/password")
        
        length = 12
        if context.args and context.args[0].isdigit():
            length = min(int(context.args[0]), 50)
        
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choice(chars) for _ in range(length))
        
        await update.message.reply_text(
            f"🔐 ПАРОЛЬ ({length} символов):\n\n`{password}`\n\n"
            "💡 Скопируйте и сохраните в безопасном месте!",
            parse_mode='Markdown'
        )
        await self.add_experience(user_data, 1)
    
    async def qr_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /qr - создать QR-код"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/qr")
        
        if not context.args:
            await update.message.reply_text("📱 Укажите текст или ссылку!\nПример: /qr https://google.com")
            return
        
        text = " ".join(context.args)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={requests.utils.quote(text)}"
        
        try:
            await update.message.reply_text("📱 Генерирую QR-код...")
            await context.bot.send_photo(update.effective_chat.id, qr_url)
        except Exception as e:
            await update.message.reply_text("❌ Ошибка генерации QR-кода")
        
        await self.add_experience(user_data, 1)
    
    async def shorturl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /shorturl - сократить URL"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/shorturl")
        
        if not context.args:
            await update.message.reply_text("🔗 Укажите URL!\nПример: /shorturl https://very-long-url.com")
            return
        
        url = context.args[0]
        if not url.startswith('http'):
            url = 'https://' + url
        
        try:
            response = requests.get(f"https://is.gd/create.php?format=simple&url={url}", timeout=10)
            
            if response.status_code == 200:
                await update.message.reply_text(f"🔗 Сокращённый URL:\n{response.text.strip()}")
            else:
                await update.message.reply_text("❌ Ошибка сокращения URL")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка подключения к сервису")
        
        await self.add_experience(user_data, 1)
    
    async def ip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /ip - информация об IP"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/ip")
        
        try:
            response = requests.get('https://httpbin.org/ip', timeout=5)
            ip = response.json().get('origin', 'Неизвестно')
            
            # Получаем дополнительную информацию
            try:
                info_response = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
                info = info_response.json()
                
                ip_text = f"""
🌍 ИНФОРМАЦИЯ ОБ IP

📍 IP: {ip}
🗺️ Страна: {info.get('country', 'N/A')}
🏙️ Город: {info.get('city', 'N/A')}
🌐 Провайдер: {info.get('isp', 'N/A')}
⏰ Часовой пояс: {info.get('timezone', 'N/A')}
                """
            except:
                ip_text = f"🌍 Ваш IP: {ip}"
            
            await update.message.reply_text(ip_text)
        except:
            await update.message.reply_text("❌ Не удалось получить IP")
        
        await self.add_experience(user_data, 1)
    
    async def weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /weather - погода (исправлена!)"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/weather")
        
        if not context.args:
            await update.message.reply_text("🌤️ Укажите город!\nПример: /weather Москва")
            return
        
        city = " ".join(context.args)
        
        # Попытка с OpenWeather API
        if OPENWEATHER_API_KEY:
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
                response = requests.get(url, timeout=10).json()
                
                if response.get("cod") == 200:
                    weather = response["weather"][0]["description"]
                    temp = round(response["main"]["temp"])
                    feels_like = round(response["main"]["feels_like"])
                    humidity = response["main"]["humidity"]
                    pressure = response["main"]["pressure"]
                    wind_speed = response["wind"]["speed"]
                    
                    weather_text = f"""
🌤️ ПОГОДА В {city.upper()}

🌡️ Температура: {temp}°C
🤔 Ощущается как: {feels_like}°C
☁️ Описание: {weather.capitalize()}
💧 Влажность: {humidity}%
🌪️ Ветер: {wind_speed} м/с
🔽 Давление: {pressure} мм рт.ст.

⏰ Обновлено: {datetime.datetime.now().strftime('%H:%M')}
                    """
                    await update.message.reply_text(weather_text)
                    await self.add_experience(user_data, 2)
                    return
            except Exception as e:
                logger.error(f"Ошибка OpenWeather: {e}")
        
        # Fallback: используем wttr.in
        try:
            url = f"https://wttr.in/{city}?format=%C+%t+💧%h+🌪️%w&lang=ru"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                weather_info = response.text.strip()
                
                weather_text = f"""
🌤️ ПОГОДА В {city.upper()}

{weather_info}

⏰ Обновлено: {datetime.datetime.now().strftime('%H:%M')}
💡 Данные предоставлены wttr.in
                """
                await update.message.reply_text(weather_text)
            else:
                await update.message.reply_text(f"❌ Город '{city}' не найден!")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка получения погоды. Попробуйте позже.")
            logger.error(f"Ошибка погоды: {e}")
        
        await self.add_experience(user_data, 2)
    
    async def currency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /currency - конвертер валют"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/currency")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "💰 КОНВЕРТЕР ВАЛЮТ\n\n"
                "Использование: /currency [из] [в] [сумма]\n\n"
                "Примеры:\n"
                "• /currency USD RUB\n"
                "• /currency EUR USD 100"
            )
            return
        
        from_cur = context.args[0].upper()
        to_cur = context.args[1].upper()
        amount = 1
        
        if len(context.args) >= 3 and context.args[2].replace('.', '').isdigit():
            amount = float(context.args[2])
        
        try:
            # Попытка с FreeCurrency API
            if CURRENCY_API_KEY:
                url = f"https://api.freecurrencyapi.com/v1/latest?apikey={CURRENCY_API_KEY}&currencies={to_cur}&base_currency={from_cur}"
                response = requests.get(url, timeout=10).json()
                rate = response.get("data", {}).get(to_cur)
                
                if rate:
                    result = amount * rate
                    await update.message.reply_text(
                        f"💰 КОНВЕРТАЦИЯ\n\n"
                        f"{amount} {from_cur} = {result:.2f} {to_cur}\n\n"
                        f"📊 Курс: 1 {from_cur} = {rate:.4f} {to_cur}\n"
                        f"⏰ {datetime.datetime.now().strftime('%H:%M')}"
                    )
                    await self.add_experience(user_data, 2)
                    return
            
            # Fallback: используем exchangerate-api
            url = f"https://api.exchangerate-api.com/v4/latest/{from_cur}"
            response = requests.get(url, timeout=10).json()
            
            if to_cur in response.get('rates', {}):
                rate = response['rates'][to_cur]
                result = amount * rate
                
                await update.message.reply_text(
                    f"💰 КОНВЕРТАЦИЯ\n\n"
                    f"{amount} {from_cur} = {result:.2f} {to_cur}\n\n"
                    f"📊 Курс: 1 {from_cur} = {rate:.4f} {to_cur}\n"
                    f"⏰ {datetime.datetime.now().strftime('%H:%M')}"
                )
            else:
                await update.message.reply_text("❌ Валюта не найдена!")
                
        except Exception as e:
            await update.message.reply_text("❌ Ошибка конвертации. Попробуйте позже.")
            logger.error(f"Ошибка currency: {e}")
        
        await self.add_experience(user_data, 2)
    
    async def translate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /translate - перевод текста"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/translate")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "🌐 ПЕРЕВОДЧИК\n\n"
                "Использование: /translate [язык] [текст]\n\n"
                "Примеры:\n"
                "• /translate en Привет, мир!\n"
                "• /translate es Hello, world!\n"
                "• /translate ru Bonjour!"
            )
            return
        
        if not self.gemini_model:
            await update.message.reply_text("❌ Перевод недоступен (AI не настроен)")
            return
        
        target_lang = context.args[0]
        text = " ".join(context.args[1:])
        
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            prompt = f"Переведи следующий текст на {target_lang}. Верни ТОЛЬКО перевод без дополнительных пояснений:\n\n{text}"
            response = self.gemini_model.generate_content(prompt)
            
            await update.message.reply_text(f"🌐 Перевод на {target_lang}:\n\n{response.text}")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка перевода")
            logger.error(f"Ошибка translate: {e}")
        
        await self.add_experience(user_data, 2)
    
    # ========================================================================
    # ПАМЯТЬ ПОЛЬЗОВАТЕЛЯ
    # ========================================================================
    
    async def memorysave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /memorysave - сохранить в память"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memorysave")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "🧠 СОХРАНИТЬ В ПАМЯТЬ\n\n"
                "Использование: /memorysave [ключ] [значение]\n\n"
                "Примеры:\n"
                "• /memorysave телефон +79991234567\n"
                "• /memorysave день_рождения 15.03.1990"
            )
            return
        
        key = context.args[0]
        value = " ".join(context.args[1:])
        
        self.db.save_memory(user_data['user_id'], key, value)
        
        await update.message.reply_text(f"🧠 Сохранено!\n\n{key} = {value}")
        await self.add_experience(user_data, 1)
    
    async def memoryget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /memoryget - получить из памяти"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memoryget")
        
        if not context.args:
            await update.message.reply_text("🧠 Укажите ключ!\nПример: /memoryget телефон")
            return
        
        key = context.args[0]
        value = self.db.get_memory(user_data['user_id'], key)
        
        if value:
            await update.message.reply_text(f"🧠 {key}:\n\n{value}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден в памяти!")
        
        await self.add_experience(user_data, 1)
    
    async def memorylist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /memorylist - список памяти"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memorylist")
        
        memory = self.db.get_all_memory(user_data['user_id'])
        
        if not memory:
            await update.message.reply_text("🧠 Память пуста!\nСохраните что-нибудь: /memorysave")
            return
        
        memory_text = "🧠 ВАША ПАМЯТЬ:\n\n"
        for key, value in memory.items():
            memory_text += f"• {key}: {value}\n"
        
        await update.message.reply_text(memory_text)
        await self.add_experience(user_data, 1)
    
    async def memorydel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /memorydel - удалить из памяти"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/memorydel")
        
        if not context.args:
            await update.message.reply_text("🧠 Укажите ключ для удаления!\nПример: /memorydel телефон")
            return
        
        key = context.args[0]
        deleted = self.db.delete_memory(user_data['user_id'], key)
        
        if deleted:
            await update.message.reply_text(f"🗑️ Удалено из памяти: {key}")
        else:
            await update.message.reply_text(f"❌ Ключ '{key}' не найден!")
        
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # ПРОГРЕСС
    # ========================================================================
    
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /rank - уровень пользователя"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/rank")
        
        level = user_data.get('level', 1)
        experience = user_data.get('experience', 0)
        required_exp = level * 100
        progress = (experience / required_exp) * 100
        
        # Прогресс-бар
        filled = int(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        achievements = self.db.get_achievements(user_data['user_id'])
        
        rank_text = f"""
🏅 ВАШ УРОВЕНЬ

👤 {user_data.get('nickname') or user_data['first_name']}
🆙 Уровень: {level}
⭐ Опыт: {experience}/{required_exp}

📊 Прогресс: {progress:.1f}%
{bar}

💎 VIP: {"✅ Активен" if self.is_vip(user_data) else "❌ Нет"}
🏆 Достижений: {len(achievements)}
        """
        
        if achievements:
            rank_text += "\n\n🏆 Последние достижения:\n"
            for ach in achievements[-3:]:
                rank_text += f"• {ach}\n"
        
        await update.message.reply_text(rank_text)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # VIP КОМАНДЫ
    # ========================================================================
    
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /vip - информация о VIP"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/vip")
        
        if not self.is_vip(user_data):
            vip_text = """
💎 VIP СТАТУС

У вас нет VIP статуса.

⭐ VIP возможности:
• ⏰ Напоминания (/remind)
• 👤 Свой никнейм (/nickname)
• 📊 Расширенный профиль (/profile)
• 🎨 Персонализация бота
• ⚡ Приоритетная поддержка

💰 Для получения VIP свяжитесь с:
@Ernest_Kostevich
            """
        else:
            expires_text = 'бессрочно'
            if user_data.get('vip_expires'):
                try:
                    expires_date = datetime.datetime.fromisoformat(user_data['vip_expires'])
                    expires_text = expires_date.strftime('%d.%m.%Y')
                    days_left = (expires_date - datetime.datetime.now()).days
                    if days_left > 0:
                        expires_text += f" ({days_left} дней)"
                except:
                    pass
            
            vip_text = f"""
💎 VIP СТАТУС АКТИВЕН

Действует до: {expires_text}

⭐ Доступные команды:
• /remind [минуты] [текст] - Напоминание
• /reminders - Список напоминаний
• /delreminder [номер] - Удалить напоминание
• /nickname [имя] - Установить никнейм
• /profile - Ваш профиль

✨ Спасибо за поддержку!
            """
        
        await update.message.reply_text(vip_text)
        await self.add_experience(user_data, 1)
    
    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /remind - создать напоминание (VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!\nИспользуйте /vip")
            return
        
        self.db.log_command(user_data['user_id'], "/remind")
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "⏰ НАПОМИНАНИЕ\n\n"
                "Использование: /remind [минуты] [текст]\n\n"
                "Примеры:\n"
                "• /remind 30 Позвонить маме\n"
                "• /remind 60 Встреча с клиентом"
            )
            return
        
        try:
            minutes = int(context.args[0])
            text = " ".join(context.args[1:])
            
            if minutes <= 0:
                await update.message.reply_text("❌ Время должно быть больше 0!")
                return
            
            if minutes > 10080:  # Максимум неделя
                await update.message.reply_text("❌ Максимум 10080 минут (неделя)!")
                return
            
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            job_id = f"reminder_{user_data['user_id']}_{int(time.time())}"
            
            # Добавляем задачу в планировщик
            job = self.scheduler.add_job(
                self.send_notification,
                trigger=DateTrigger(run_date=run_date),
                args=[context, user_data['user_id'], f"🔔 Напоминание:\n\n{text}"],
                id=job_id
            )
            
            # Сохраняем в БД
            self.db.add_reminder(
                user_data['user_id'],
                text,
                run_date.isoformat(),
                job_id
            )
            
            await update.message.reply_text(
                f"⏰ Напоминание установлено!\n\n"
                f"📝 {text}\n"
                f"🕐 Через {minutes} минут ({run_date.strftime('%d.%m %H:%M')})"
            )
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат времени! Укажите число минут.")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка создания напоминания")
            logger.error(f"Ошибка remind: {e}")
        
        await self.add_experience(user_data, 2)
    
    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /reminders - список напоминаний (VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data['user_id'], "/reminders")
        
        reminders = self.db.get_reminders(user_data['user_id'])
        
        if not reminders:
            await update.message.reply_text("❌ Нет активных напоминаний!\nСоздайте: /remind")
            return
        
        reminders_text = "⏰ ВАШИ НАПОМИНАНИЯ:\n\n"
        for i, rem in enumerate(reminders, 1):
            try:
                rem_time = datetime.datetime.fromisoformat(rem['reminder_time'])
                time_str = rem_time.strftime('%d.%m %H:%M')
                reminders_text += f"{i}. {rem['reminder_text']}\n   🕐 {time_str}\n\n"
            except:
                reminders_text += f"{i}. {rem['reminder_text']}\n\n"
        
        await update.message.reply_text(reminders_text)
        await self.add_experience(user_data, 1)
    
    async def delreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /delreminder - удалить напоминание (VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data['user_id'], "/delreminder")
        
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Укажите номер напоминания!\nПример: /delreminder 1")
            return
        
        reminders = self.db.get_reminders(user_data['user_id'])
        index = int(context.args[0]) - 1
        
        if 0 <= index < len(reminders):
            reminder = reminders[index]
            
            # Удаляем из планировщика
            try:
                self.scheduler.remove_job(reminder['job_id'])
            except:
                pass
            
            # Удаляем из БД
            self.db.delete_reminder(reminder['id'], user_data['user_id'])
            
            await update.message.reply_text(f"🗑️ Напоминание #{index+1} удалено!")
        else:
            await update.message.reply_text(f"❌ Напоминания #{index+1} не существует!")
        
        await self.add_experience(user_data, 1)
    
    async def nickname_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /nickname - установить никнейм (VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data['user_id'], "/nickname")
        
        if not context.args:
            current = user_data.get('nickname') or "Не установлен"
            await update.message.reply_text(
                f"👤 НИКНЕЙМ\n\n"
                f"Текущий: {current}\n\n"
                f"Установить: /nickname [имя]\n"
                f"Пример: /nickname Супермен"
            )
            return
        
        nickname = " ".join(context.args)
        
        if len(nickname) > 50:
            await update.message.reply_text("❌ Максимум 50 символов!")
            return
        
        user_data['nickname'] = nickname
        self.db.save_user(user_data)
        
        await update.message.reply_text(f"✅ Никнейм установлен: {nickname}")
        await self.add_experience(user_data, 1)
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /profile - профиль пользователя (VIP)"""
        user_data = await self.get_user_data(update)
        
        if not self.is_vip(user_data):
            await update.message.reply_text("💎 Только для VIP!")
            return
        
        self.db.log_command(user_data['user_id'], "/profile")
        
        notes = self.db.get_notes(user_data['user_id'])
        memory = self.db.get_all_memory(user_data['user_id'])
        reminders = self.db.get_reminders(user_data['user_id'])
        achievements = self.db.get_achievements(user_data['user_id'])
        
        history = self.conversation_memory.get_full_history(user_data['user_id'])
        
        expires_text = 'бессрочно'
        if user_data.get('vip_expires'):
            try:
                expires_date = datetime.datetime.fromisoformat(user_data['vip_expires'])
                expires_text = expires_date.strftime('%d.%m.%Y')
            except:
                pass
        
        profile_text = f"""
👤 ВАШ ПРОФИЛЬ

📛 Имя: {user_data['first_name']}
🎭 Никнейм: {user_data.get('nickname') or "Не установлен"}
🆔 ID: {user_data['user_id']}
💎 VIP: Активен до {expires_text}

📊 СТАТИСТИКА:
🆙 Уровень: {user_data.get('level', 1)}
⭐ Опыт: {user_data.get('experience', 0)}/{user_data.get('level', 1) * 100}
📝 Заметок: {len(notes)}
🧠 Памяти: {len(memory)}
⏰ Напоминаний: {len(reminders)}
💬 Сообщений в истории: {len(history)}
🏆 Достижений: {len(achievements)}

🌐 Язык: {user_data.get('language', 'ru').upper()}
🎨 Тема: {user_data.get('theme', 'default')}
🎨 Цвет: {user_data.get('color', 'blue')}
        """
        
        await update.message.reply_text(profile_text)
        await self.add_experience(user_data, 1)
    
    # ========================================================================
    # КОМАНДЫ СОЗДАТЕЛЯ
    # ========================================================================
    
    async def grant_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /grant_vip - выдать VIP (создатель)"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "💎 ВЫДАТЬ VIP\n\n"
                "Использование: /grant_vip [user_id или @username] [week/month/year/permanent]\n\n"
                "Примеры:\n"
                "• /grant_vip 123456789 week\n"
                "• /grant_vip @username month\n"
                "• /grant_vip 123456789 permanent"
            )
            return
        
        try:
            target = context.args[0]
            duration = context.args[1].lower()
            
            # Найти пользователя
            if target.startswith('@'):
                username = target[1:]
                target_user = self.db.get_user_by_username(username)
                if not target_user:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден в базе!")
                    return
            else:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
                if not target_user:
                    await update.message.reply_text("❌ Пользователь с таким ID не найден!")
                    return
            
            # Установить VIP
            target_user['is_vip'] = 1
            
            if duration == "week":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(weeks=1)).isoformat()
            elif duration == "month":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
            elif duration == "year":
                target_user['vip_expires'] = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
            elif duration == "permanent":
                target_user['vip_expires'] = None
            else:
                await update.message.reply_text("❌ Неверная длительность! Используйте: week/month/year/permanent")
                return
            
            self.db.save_user(target_user)
            
            await update.message.reply_text(
                f"✅ VIP выдан!\n\n"
                f"👤 {target_user['first_name']}\n"
                f"🆔 {target_user['user_id']}\n"
                f"⏰ Длительность: {duration}"
            )
            
            # Уведомить пользователя
            try:
                await context.bot.send_message(
                    target_user['user_id'],
                    f"🎉 Поздравляем!\n\n"
                    f"Вы получили VIP статус!\n"
                    f"⏰ Длительность: {duration}\n\n"
                    f"Используйте /vip для просмотра возможностей."
                )
            except:
                pass
            
        except ValueError:
            await update.message.reply_text("❌ Неверный ID! Используйте число или @username")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            logger.error(f"Ошибка grant_vip: {e}")
    
    async def revoke_vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /revoke_vip - отозвать VIP (создатель)"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "💎 ОТОЗВАТЬ VIP\n\n"
                "Использование: /revoke_vip [user_id или @username]\n\n"
                "Примеры:\n"
                "• /revoke_vip 123456789\n"
                "• /revoke_vip @username"
            )
            return
        
        try:
            target = context.args[0]
            
            if target.startswith('@'):
                username = target[1:]
                target_user = self.db.get_user_by_username(username)
                if not target_user:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
                    return
            else:
                target_id = int(target)
                target_user = self.db.get_user(target_id)
                if not target_user:
                    await update.message.reply_text("❌ Пользователь не найден!")
                    return
            
            if not target_user.get('is_vip'):
                await update.message.reply_text(f"❌ Пользователь {target_user['first_name']} не VIP!")
                return
            
            target_user['is_vip'] = 0
            target_user['vip_expires'] = None
            self.db.save_user(target_user)
            
            await update.message.reply_text(
                f"✅ VIP отозван!\n\n"
                f"👤 {target_user['first_name']}\n"
                f"🆔 {target_user['user_id']}"
            )
            
            # Уведомить пользователя
            try:
                await context.bot.send_message(
                    target_user['user_id'],
                    "💎 Ваш VIP статус был отозван администратором."
                )
            except:
                pass
            
        except ValueError:
            await update.message.reply_text("❌ Неверный ID!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /users - список пользователей (создатель)"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        all_users = self.db.get_all_users()
        
        if not all_users:
            await update.message.reply_text("👥 Пользователей пока нет!")
            return
        
        users_text = f"👥 ПОЛЬЗОВАТЕЛЕЙ: {len(all_users)}\n\n"
        
        for user in all_users[:30]:
            vip_icon = "💎" if user.get('is_vip') else "👤"
            level = user.get('level', 1)
            users_text += f"{vip_icon} {user['first_name']} (ID: {user['user_id']}) - Ур.{level}\n"
        
        if len(all_users) > 30:
            users_text += f"\n... и ещё {len(all_users) - 30} пользователей"
        
        await update.message.reply_text(users_text)
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /broadcast - рассылка (создатель)"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📢 РАССЫЛКА\n\n"
                "Использование: /broadcast [сообщение]\n\n"
                "Пример:\n"
                "/broadcast Обновление бота завершено!"
            )
            return
        
        message = " ".join(context.args)
        all_users = self.db.get_all_users()
        
        sent = 0
        failed = 0
        
        await update.message.reply_text(f"📢 Начинаю рассылку для {len(all_users)} пользователей...")
        
        for user in all_users:
            try:
                await context.bot.send_message(
                    user['user_id'],
                    f"📢 Сообщение от создателя:\n\n{message}"
                )
                sent += 1
                await asyncio.sleep(0.05)  # Антиспам
            except Exception as e:
                failed += 1
                logger.warning(f"Не удалось отправить {user['user_id']}: {e}")
        
        await update.message.reply_text(
            f"✅ Рассылка завершена!\n\n"
            f"✅ Отправлено: {sent}\n"
            f"❌ Неудачно: {failed}"
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - статистика бота"""
        user_data = await self.get_user_data(update)
        self.db.log_command(user_data['user_id'], "/stats")
        
        if self.is_creator(user_data['user_id']):
            # Полная статистика для создателя
            all_users = self.db.get_all_users()
            vip_users = self.db.get_vip_users()
            popular_commands = self.db.get_popular_commands(5)
            conv_stats = self.conversation_memory.get_stats()
            
            total_notes = sum(len(self.db.get_notes(u['user_id'])) for u in all_users)
            total_reminders = sum(len(self.db.get_reminders(u['user_id'])) for u in all_users)
            
            stats_text = f"""
📊 ПОЛНАЯ СТАТИСТИКА БОТА

👥 ПОЛЬЗОВАТЕЛИ:
• Всего: {len(all_users)}
• VIP: {len(vip_users)}
• Активных сегодня: {sum(1 for u in all_users if u.get('last_activity', '')[:10] == datetime.datetime.now().strftime('%Y-%m-%d'))}

💬 ПАМЯТЬ ЧАТА:
• Пользователей с историей: {conv_stats['total_users']}
• Всего сообщений: {conv_stats['total_messages']}
• Среднее на юзера: {conv_stats['avg_messages_per_user']:.1f}

📝 ДАННЫЕ:
• Заметок: {total_notes}
• Напоминаний: {total_reminders}
• Команд в логах: {len(self.db.get_popular_commands(100))}

🔥 ТОП-5 КОМАНД:
"""
            for cmd, data in popular_commands:
                stats_text += f"• {cmd}: {data['usage_count']} раз\n"
            
            stats_text += f"\n⏰ Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            
        else:
            # Личная статистика
            notes = self.db.get_notes(user_data['user_id'])
            memory = self.db.get_all_memory(user_data['user_id'])
            achievements = self.db.get_achievements(user_data['user_id'])
            history = self.conversation_memory.get_full_history(user_data['user_id'])
            
            stats_text = f"""
📊 ВАША СТАТИСТИКА

👤 {user_data.get('nickname') or user_data['first_name']}
🆙 Уровень: {user_data.get('level', 1)}
⭐ Опыт: {user_data.get('experience', 0)}/{user_data.get('level', 1) * 100}

💎 VIP: {"✅ Активен" if self.is_vip(user_data) else "❌ Нет"}

📈 АКТИВНОСТЬ:
• 📝 Заметок: {len(notes)}
• 🧠 Памяти: {len(memory)}
• 💬 Сообщений: {len(history)}
• 🏆 Достижений: {len(achievements)}

⏰ Последняя активность: {user_data.get('last_activity', 'Неизвестно')[:19]}
            """
        
        await update.message.reply_text(stats_text)
        await self.add_experience(user_data, 1)
    
    async def maintenance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /maintenance - режим обслуживания (создатель)"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        if not context.args:
            status = "включен" if self.maintenance_mode else "выключен"
            await update.message.reply_text(
                f"🛠 РЕЖИМ ОБСЛУЖИВАНИЯ\n\n"
                f"Статус: {status}\n\n"
                f"Использование:\n"
                f"• /maintenance on - Включить\n"
                f"• /maintenance off - Выключить"
            )
            return
        
        mode = context.args[0].lower()
        
        if mode in ['on', 'вкл', 'включить']:
            self.maintenance_mode = True
            await update.message.reply_text("🛠 Режим обслуживания ВКЛЮЧЕН\n\nПользователи не смогут использовать бота.")
        elif mode in ['off', 'выкл', 'выключить']:
            self.maintenance_mode = False
            await update.message.reply_text("✅ Режим обслуживания ВЫКЛЮЧЕН\n\nБот работает в обычном режиме.")
        else:
            await update.message.reply_text("❌ Используйте: on/off")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /backup - создать резервную копию (создатель)"""
        if not self.is_creator(update.effective_user.id):
            await update.message.reply_text("❌ Только для создателя!")
            return
        
        try:
            await update.message.reply_text("💾 Создаю резервную копию...")
            
            # Принудительно сохраняем conversations
            self.conversation_memory.save()
            
            # Создаём бэкап
            backup_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'users_count': len(self.db.get_all_users()),
                'vip_count': len(self.db.get_vip_users()),
                'conversation_stats': self.conversation_memory.get_stats(),
                'database_path': DB_PATH,
                'conversations_path': CONVERSATIONS_PATH
            }
            
            # Сохраняем в файл
            backup_filename = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_filepath = os.path.join(BACKUP_PATH, backup_filename)
            
            with open(backup_filepath, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # Загружаем в GitHub если доступен
            if self.github:
                try:
                    with open(backup_filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    github_path = f"backups/{backup_filename}"
                    try:
                        file = self.repo.get_contents(github_path)
                        self.repo.update_file(github_path, f"Backup {backup_filename}", content, file.sha)
                    except:
                        self.repo.create_file(github_path, f"Backup {backup_filename}", content)
                    
                    backup_data['github_uploaded'] = True
                except Exception as e:
                    logger.error(f"Ошибка загрузки в GitHub: {e}")
                    backup_data['github_uploaded'] = False
            
            await update.message.reply_text(
                f"✅ Резервная копия создана!\n\n"
                f"📁 Файл: {backup_filename}\n"
                f"👥 Пользователей: {backup_data['users_count']}\n"
                f"💎 VIP: {backup_data['vip_count']}\n"
                f"💬 Сообщений в памяти: {backup_data['conversation_stats']['total_messages']}\n"
                f"☁️ GitHub: {'✅' if backup_data.get('github_uploaded') else '❌'}"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка создания бэкапа: {str(e)}")
            logger.error(f"Ошибка backup: {e}")
    
    # ========================================================================
    # ОБРАБОТЧИКИ CALLBACK
    # ========================================================================
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        fake_message = query.message
        fake_message.from_user = user
        fake_update = Update(update_id=update.update_id, message=fake_message)
        
        if query.data == "help":
            await self.help_command(fake_update, context)
        elif query.data == "vip_info":
            await self.vip_command(fake_update, context)
        elif query.data == "ai_demo":
            await query.edit_message_text(
                "🤖 AI-ЧАТ ГОТОВ!\n\n"
                "Просто напишите мне сообщение, и я отвечу!\n"
                "Я запоминаю весь разговор благодаря долговременной памяти.\n\n"
                "Примеры:\n"
                "• Расскажи о космосе\n"
                "• Помоги решить задачу\n"
                "• Объясни квантовую физику\n\n"
                "Или используйте: /ai [вопрос]"
            )
        elif query.data == "my_stats":
            await self.stats_command(fake_update, context)
    
    # ========================================================================
    # СИСТЕМНЫЕ ФУНКЦИИ
    # ========================================================================
    
    async def self_ping(self):
        """Автопинг для Render"""
        try:
            response = requests.get(RENDER_URL, timeout=10)
            logger.info(f"Self-ping успешен: {response.status_code}")
        except Exception as e:
            logger.warning(f"Self-ping неудачен: {e}")
    
    async def save_all_data(self):
        """Периодическое сохранение всех данных"""
        try:
            self.conversation_memory.save()
            logger.info("Данные сохранены успешно")
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
    
    # ========================================================================
    # ЗАПУСК БОТА
    # ========================================================================
    
    async def run_bot(self):
        """Главная функция запуска бота"""
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не найден!")
            return
        
        logger.info("Запуск бота...")
        
        # Создаём приложение
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30)
            .pool_timeout(30)
            .build()
        )
        
        # Обработчик ошибок
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            logger.error(f"Ошибка: {context.error}")
            
            if isinstance(context.error, Conflict):
                logger.error("Конфликт: несколько экземпляров бота")
                await asyncio.sleep(30)
        
        application.add_error_handler(error_handler)
        
        # Регистрация всех команд
        commands = [
            ("start", self.start_command),
            ("help", self.help_command),
            ("info", self.info_command),
            ("status", self.status_command),
            ("uptime", self.uptime_command),
            ("ai", self.ai_command),
            ("clearhistory", self.clearhistory_command),
            ("note", self.note_command),
            ("notes", self.notes_command),
            ("delnote", self.delnote_command),
            ("findnote", self.findnote_command),
            ("clearnotes", self.clearnotes_command),
            ("time", self.time_command),
            ("date", self.date_command),
            ("joke", self.joke_command),
            ("fact", self.fact_command),
            ("quote", self.quote_command),
            ("quiz", self.quiz_command),
            ("coin", self.coin_command),
            ("dice", self.dice_command),
            ("8ball", self.eightball_command),
            ("math", self.math_command),
            ("calculate", self.calculate_command),
            ("password", self.password_command),
            ("qr", self.qr_command),
            ("shorturl", self.shorturl_command),
            ("ip", self.ip_command),
            ("weather", self.weather_command),
            ("currency", self.currency_command),
            ("translate", self.translate_command),
            ("memorysave", self.memorysave_command),
            ("memoryget", self.memoryget_command),
            ("memorylist", self.memorylist_command),
            ("memorydel", self.memorydel_command),
            ("rank", self.rank_command),
            ("vip", self.vip_command),
            ("remind", self.remind_command),
            ("reminders", self.reminders_command),
            ("delreminder", self.delreminder_command),
            ("nickname", self.nickname_command),
            ("profile", self.profile_command),
            ("grant_vip", self.grant_vip_command),
            ("revoke_vip", self.revoke_vip_command),
            ("users", self.users_command),
            ("broadcast", self.broadcast_command),
            ("stats", self.stats_command),
            ("maintenance", self.maintenance_command),
            ("backup", self.backup_command),
        ]
        
        for cmd, handler in commands:
            application.add_handler(CommandHandler(cmd, handler))
        
        # Обработчик обычных сообщений (AI чат)
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                self.handle_message
            )
        )
        
        # Обработчик кнопок
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Запуск планировщика
        loop = asyncio.get_running_loop()
        self.scheduler.configure(event_loop=loop)
        self.scheduler.start()
        
        # Автопинг каждые 14 минут
        self.scheduler.add_job(
            self.self_ping,
            'interval',
            minutes=14,
            id='self_ping'
        )
        
        # Сохранение данных каждые 30 минут
        self.scheduler.add_job(
            self.save_all_data,
            'interval',
            minutes=30,
            id='auto_save'
        )
        
        # Проверка дней рождения каждый день в 9:00
        self.scheduler.add_job(
            self.check_birthdays,
            CronTrigger(hour=9, minute=0),
            args=[application],
            id='birthday_check'
        )
        
        logger.info("🤖 Бот запущен успешно!")
        logger.info(f"📊 Пользователей в базе: {len(self.db.get_all_users())}")
        logger.info(f"💬 Разговоров в памяти: {self.conversation_memory.get_stats()['total_users']}")
        
        try:
            await application.run_polling(
                drop_pending_updates=True,
                timeout=30,
                bootstrap_retries=3
            )
        except Exception as e:
            logger.error(f"Критическая ошибка бота: {e}")
            raise
        finally:
            # Сохраняем все данные при остановке
            self.conversation_memory.save()
            logger.info("Бот остановлен, данные сохранены")

# ============================================================================
# ЗАПУСК
# ============================================================================

async def main():
    """Главная функция"""
    bot = TelegramBot()
    await bot.run_bot()

# Flask для Render (веб-сервер)
app = Flask(__name__)

@app.route('/')
def home():
    """Главная страница"""
    return f"""
    <html>
    <head>
        <title>Telegram AI Bot v2.0</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 50px;
                text-align: center;
            }}
            .container {{
                background: rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 30px;
                max-width: 600px;
                margin: 0 auto;
            }}
            h1 {{ font-size: 48px; margin-bottom: 10px; }}
            .status {{ color: #00ff88; font-weight: bold; }}
            .info {{ font-size: 18px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Telegram AI Bot</h1>
            <p class="status">✅ РАБОТАЕТ</p>
            <div class="info">
                <p>📅 Версия: 2.0 (Улучшенная)</p>
                <p>⏰ Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
                <p>🔧 База: SQLite + conversations.json</p>
                <p>🧠 AI: Gemini 2.0 Flash</p>
                <p>💬 Память: Долговременная</p>
            </div>
            <p>Бот создан: {CREATOR_USERNAME}</p>
            <p>Telegram: {BOT_USERNAME}</p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Проверка здоровья"""
    return {
        "status": "ok",
        "time": datetime.datetime.now().isoformat(),
        "version": "2.0"
    }

@app.route('/stats')
def web_stats():
    """Веб-статистика"""
    try:
        db = Database()
        conv_memory = ConversationMemory()
        
        all_users = db.get_all_users()
        vip_users = db.get_vip_users()
        conv_stats = conv_memory.get_stats()
        
        return {
            "status": "ok",
            "users_total": len(all_users),
            "vip_total": len(vip_users),
            "conversations": conv_stats['total_users'],
            "messages_total": conv_stats['total_messages'],
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

if __name__ == "__main__":
    import sys
    from threading import Thread
    
    # Запуск Flask в отдельном потоке
    port = int(os.getenv("PORT", 8080))
    flask_thread = Thread(
        target=app.run,
        kwargs={
            'host': '0.0.0.0',
            'port': port,
            'debug': False,
            'use_reloader': False
        }
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info(f"🌐 Flask запущен на порту {port}")
    
    # Запуск бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        sys.exit(1)
