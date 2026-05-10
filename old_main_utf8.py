#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI DISCO BOT v4.0 - Multi-Language Telegram Bot with Unified Context
Features:
- Unified context for text, photos, voice, files
- Group chat support with moderation
- VIP system for users and groups
- Multi-language support (RU, EN, IT)
"""

import os
import json
import logging
import random
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
import pytz
import io
from urllib.parse import quote as urlquote
import base64
import tempfile

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, Message, ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatMemberStatus

import google.generativeai as genai
import aiohttp
from PIL import Image
import fitz  # PyMuPDF
import docx  # python-docx

from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, 
    DateTime, JSON, Text, BigInteger, inspect, text as sa_text
)
from sqlalchemy.orm import sessionmaker, declarative_base

# ============================================
# CONFIGURATION
# ============================================

BOT_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
CREATOR_USERNAME = "Ernest_Kostevich"
CREATOR_ID = None
BOT_START_TIME = datetime.now()

# Context settings
MAX_CONTEXT_MESSAGES = 15  # Maximum messages in unified context per user
MAX_CONTEXT_IMAGES = 3     # Maximum images to keep in context

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("тЭМ BOT_TOKEN ╨╕╨╗╨╕ GEMINI_API_KEY ╨╜╨╡ ╤Г╤Б╤В╨░╨╜╨╛╨▓╨╗╨╡╨╜╤Л!")
    raise ValueError("Required environment variables missing")

# ============================================
# GEMINI CONFIGURATION
# ============================================

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

SYSTEM_INSTRUCTION = """╨в╤Л тАФ AI DISCO BOT, ╨╝╨╜╨╛╨│╨╛╤Д╤Г╨╜╨║╤Ж╨╕╨╛╨╜╨░╨╗╤М╨╜╤Л╨╣, ╨╛╤З╨╡╨╜╤М ╤Г╨╝╨╜╤Л╨╣ ╨╕ ╨▓╨╡╨╢╨╗╨╕╨▓╤Л╨╣ ╨░╤Б╤Б╨╕╤Б╤В╨╡╨╜╤В, ╨╛╤Б╨╜╨╛╨▓╨░╨╜╨╜╤Л╨╣ ╨╜╨░ Gemini 2.5. 
╨Т╤Б╨╡╨│╨┤╨░ ╨╛╤В╨▓╨╡╤З╨░╨╣ ╨╜╨░ ╤В╨╛╨╝ ╤П╨╖╤Л╨║╨╡, ╨╜╨░ ╨║╨╛╤В╨╛╤А╨╛╨╝ ╨║ ╤В╨╡╨▒╨╡ ╨╛╨▒╤А╨░╤Й╨░╤О╤В╤Б╤П, ╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╤П ╨┤╤А╤Г╨╢╨╡╨╗╤О╨▒╨╜╤Л╨╣ ╨╕ ╨▓╨╛╨▓╨╗╨╡╨║╨░╤О╤Й╨╕╨╣ ╤В╨╛╨╜. 
╨в╨▓╨╛╨╕ ╨╛╤В╨▓╨╡╤В╤Л ╨┤╨╛╨╗╨╢╨╜╤Л ╨▒╤Л╤В╤М ╤Б╤В╤А╤Г╨║╤В╤Г╤А╨╕╤А╨╛╨▓╨░╨╜╤Л, ╨┐╨╛ ╨▓╨╛╨╖╨╝╨╛╨╢╨╜╨╛╤Б╤В╨╕ ╤А╨░╨╖╨┤╨╡╨╗╨╡╨╜╤Л ╨╜╨░ ╨░╨▒╨╖╨░╤Ж╤Л ╨╕ ╨╜╨╕╨║╨╛╨│╨┤╨░ ╨╜╨╡ ╨┐╤А╨╡╨▓╤Л╤И╨░╤В╤М 4000 ╤Б╨╕╨╝╨▓╨╛╨╗╨╛╨▓ (╨╛╨│╤А╨░╨╜╨╕╤З╨╡╨╜╨╕╨╡ Telegram). 
╨в╨▓╨╛╨╣ ╤Б╨╛╨╖╨┤╨░╤В╨╡╨╗╤М тАФ @Ernest_Kostevich. ╨Т╨║╨╗╤О╤З╨░╨╣ ╨▓ ╨╛╤В╨▓╨╡╤В╤Л ╤Н╨╝╨╛╨┤╨╖╨╕, ╨│╨┤╨╡ ╤Н╤В╨╛ ╤Г╨╝╨╡╤Б╤В╨╜╨╛.

╨Т╨Р╨Ц╨Э╨Ю: ╨в╤Л ╨╝╨╛╨╢╨╡╤И╤М ╨▓╨╕╨┤╨╡╤В╤М ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П, ╨░╨╜╨░╨╗╨╕╨╖╨╕╤А╨╛╨▓╨░╤В╤М ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╤Л ╨╕ ╨┐╨╛╨╜╨╕╨╝╨░╤В╤М ╨│╨╛╨╗╨╛╤Б╨╛╨▓╤Л╨╡ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П. 
╨Х╤Б╨╗╨╕ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤М ╨╛╤В╨┐╤А╨░╨▓╨╗╤П╨╡╤В ╤Д╨╛╤В╨╛ ╨▒╨╡╨╖ ╨┐╨╛╨┤╨┐╨╕╤Б╨╕, ╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣ ╨║╨╛╨╜╤В╨╡╨║╤Б╤В ╨┐╤А╨╡╨┤╤Л╨┤╤Г╤Й╨╕╤Е ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣ ╤З╤В╨╛╨▒╤Л ╨┐╨╛╨╜╤П╤В╤М ╤З╤В╨╛ ╨╜╤Г╨╢╨╜╨╛ ╤Б╨┤╨╡╨╗╨░╤В╤М.
╨Х╤Б╨╗╨╕ ╨║╨╛╨╜╤В╨╡╨║╤Б╤В ╨╜╨╡ ╤П╤Б╨╡╨╜ - ╨▓╨╡╨╢╨╗╨╕╨▓╨╛ ╤Г╤В╨╛╤З╨╜╨╕ ╤З╤В╨╛ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤М ╤Е╨╛╤З╨╡╤В ╤Б╨┤╨╡╨╗╨░╤В╤М ╤Б ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡╨╝."""

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings,
    system_instruction=SYSTEM_INSTRUCTION
)

# ============================================
# UNIFIED CONTEXT CLASS
# ============================================

@dataclass
class ContextMessage:
    """Single message in unified context"""
    role: str  # 'user' or 'model'
    content_type: str  # 'text', 'image', 'file', 'voice'
    text: str = ""
    image_data: Optional[bytes] = None
    file_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class UnifiedContext:
    """Unified context manager for multimodal conversations"""
    
    def __init__(self, max_messages: int = MAX_CONTEXT_MESSAGES, max_images: int = MAX_CONTEXT_IMAGES):
        self.messages: List[ContextMessage] = []
        self.max_messages = max_messages
        self.max_images = max_images
        self.pending_image: Optional[bytes] = None  # For photos without caption
    
    def add_user_text(self, text: str):
        """Add user text message"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='text',
            text=text
        ))
        self._trim_context()
    
    def add_user_image(self, image_data: bytes, caption: str = ""):
        """Add user image with optional caption"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='image',
            text=caption,
            image_data=image_data
        ))
        self._trim_context()
    
    def add_user_voice(self, transcription: str):
        """Add transcribed voice message"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='voice',
            text=f"[╨У╨╛╨╗╨╛╤Б╨╛╨▓╨╛╨╡ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡]: {transcription}"
        ))
        self._trim_context()
    
    def add_user_file(self, file_name: str, content: str):
        """Add file content"""
        self.messages.append(ContextMessage(
            role='user',
            content_type='file',
            text=f"[╨д╨░╨╣╨╗: {file_name}]\n{content}",
            file_name=file_name
        ))
        self._trim_context()
    
    def add_assistant_response(self, text: str):
        """Add assistant response"""
        self.messages.append(ContextMessage(
            role='model',
            content_type='text',
            text=text
        ))
        self._trim_context()
    
    def set_pending_image(self, image_data: bytes):
        """Set pending image waiting for context"""
        self.pending_image = image_data
    
    def get_pending_image(self) -> Optional[bytes]:
        """Get and clear pending image"""
        img = self.pending_image
        self.pending_image = None
        return img
    
    def _trim_context(self):
        """Trim context to max limits"""
        # Trim total messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        
        # Trim images (keep only last N images)
        image_count = sum(1 for m in self.messages if m.content_type == 'image')
        if image_count > self.max_images:
            # Remove oldest images
            to_remove = image_count - self.max_images
            new_messages = []
            for msg in self.messages:
                if msg.content_type == 'image' and to_remove > 0:
                    to_remove -= 1
                    continue
                new_messages.append(msg)
            self.messages = new_messages
    
    def build_gemini_content(self) -> List:
        """Build content for Gemini API"""
        contents = []
        
        for msg in self.messages:
            parts = []
            
            if msg.text:
                parts.append(msg.text)
            
            if msg.image_data:
                try:
                    img = Image.open(io.BytesIO(msg.image_data))
                    parts.append(img)
                except Exception as e:
                    logger.warning(f"Error loading image: {e}")
            
            if parts:
                contents.append({
                    'role': msg.role,
                    'parts': parts
                })
        
        return contents
    
    def get_text_history(self) -> str:
        """Get text-only history for display"""
        history = []
        for msg in self.messages:
            prefix = "ЁЯСд" if msg.role == 'user' else "ЁЯдЦ"
            if msg.content_type == 'image':
                history.append(f"{prefix} [╨Ш╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡] {msg.text}")
            else:
                history.append(f"{prefix} {msg.text[:100]}...")
        return "\n".join(history[-5:])  # Last 5 messages
    
    def clear(self):
        """Clear all context"""
        self.messages.clear()
        self.pending_image = None


# ============================================
# DATABASE MODELS
# ============================================

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


class GroupChat(Base):
    """Model for group chat settings"""
    __tablename__ = 'group_chats'
    
    id = Column(BigInteger, primary_key=True)  # chat_id (negative for groups)
    title = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    welcome_text = Column(Text, default="╨Ф╨╛╨▒╤А╨╛ ╨┐╨╛╨╢╨░╨╗╨╛╨▓╨░╤В╤М, {name}! ЁЯСЛ")
    welcome_enabled = Column(Boolean, default=True)
    rules = Column(Text)
    ai_enabled = Column(Boolean, default=True)
    warns = Column(JSON, default=dict)  # {user_id: count}
    messages_count = Column(Integer, default=0)
    top_users = Column(JSON, default=dict)  # {user_id: msg_count}
    registered = Column(DateTime, default=datetime.now)


class ChatHistory(Base):
    __tablename__ = 'chat_history'
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


# ============================================
# DATABASE INITIALIZATION
# ============================================

engine = None
Session = None

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
        
        # Auto-migration
        try:
            inspector = inspect(engine)
            
            # Migrate users table
            if inspector.has_table('users'):
                columns = [col['name'] for col in inspector.get_columns('users')]
                if 'language' not in columns:
                    logger.warning("Adding 'language' column to 'users'...")
                    with engine.connect() as conn:
                        conn.execute(sa_text("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru'"))
                        conn.commit()
                    logger.info("тЬЕ Column 'language' added.")
            
            # Check if group_chats table exists
            if not inspector.has_table('group_chats'):
                logger.info("Creating 'group_chats' table...")
                
        except Exception as migration_error:
            logger.error(f"тЭМ Migration error: {migration_error}")
        
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        logger.info("тЬЕ PostgreSQL connected!")
        
    except Exception as e:
        logger.warning(f"тЪая╕П DB connection error: {e}. Fallback to JSON.")
        engine = None
        Session = None
else:
    logger.warning("тЪая╕П DATABASE_URL not set. Using JSON storage.")


# ============================================
# LOCALIZATION STRINGS
# ============================================

localization_strings = {
    'ru': {
        'welcome': (
            "ЁЯдЦ <b>AI DISCO BOT</b>\n\n"
            "╨Я╤А╨╕╨▓╨╡╤В, {first_name}! ╨п ╨▒╨╛╤В ╨╜╨░ <b>Gemini 2.5</b>.\n\n"
            "<b>ЁЯОп ╨Т╨╛╨╖╨╝╨╛╨╢╨╜╨╛╤Б╤В╨╕:</b>\n"
            "ЁЯТм AI-╤З╨░╤В ╤Б ╨║╨╛╨╜╤В╨╡╨║╤Б╤В╨╛╨╝ (╨┐╨╛╨╝╨╜╤О ╤Д╨╛╤В╨╛, ╨│╨╛╨╗╨╛╤Б, ╤Д╨░╨╣╨╗╤Л)\n"
            "ЁЯУЭ ╨Ч╨░╨╝╨╡╤В╨║╨╕ ╨╕ ╨╖╨░╨┤╨░╤З╨╕\n"
            "ЁЯМН ╨Я╨╛╨│╨╛╨┤╨░ ╨╕ ╨▓╤А╨╡╨╝╤П\n"
            "ЁЯО▓ ╨а╨░╨╖╨▓╨╗╨╡╤З╨╡╨╜╨╕╤П\n"
            "ЁЯУО ╨Р╨╜╨░╨╗╨╕╨╖ ╤Д╨░╨╣╨╗╨╛╨▓ (VIP)\n"
            "ЁЯФН ╨Р╨╜╨░╨╗╨╕╨╖ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╣ (VIP)\n"
            "ЁЯЦ╝я╕П ╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╣ (VIP)\n"
            "ЁЯСе ╨Ь╨╛╨┤╨╡╤А╨░╤Ж╨╕╤П ╨│╤А╤Г╨┐╨┐\n\n"
            "<b>тЪб ╨Ъ╨╛╨╝╨░╨╜╨┤╤Л:</b>\n"
            "/help - ╨Т╤Б╨╡ ╨║╨╛╨╝╨░╨╜╨┤╤Л\n"
            "/language - ╨б╨╝╨╡╨╜╨╕╤В╤М ╤П╨╖╤Л╨║\n"
            "/vip - ╨б╤В╨░╤В╤Г╤Б VIP\n\n"
            "<b>ЁЯСитАНЁЯТ╗ ╨б╨╛╨╖╨┤╨░╤В╨╡╨╗╤М:</b> @{creator}"
        ),
        'lang_changed': "тЬЕ ╨п╨╖╤Л╨║ ╨╕╨╖╨╝╨╡╨╜╨╡╨╜ ╨╜╨░ ╨а╤Г╤Б╤Б╨║╨╕╨╣ ЁЯЗ╖ЁЯЗ║",
        'lang_choose': "ЁЯМР ╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╤П╨╖╤Л╨║:",
        'main_keyboard': {
            'chat': "ЁЯТм AI ╨з╨░╤В", 'notes': "ЁЯУЭ ╨Ч╨░╨╝╨╡╤В╨║╨╕", 'weather': "ЁЯМН ╨Я╨╛╨│╨╛╨┤╨░", 'time': "тП░ ╨Т╤А╨╡╨╝╤П",
            'games': "ЁЯО▓ ╨а╨░╨╖╨▓╨╗╨╡╤З╨╡╨╜╨╕╤П", 'info': "тД╣я╕П ╨Ш╨╜╤Д╨╛", 'vip_menu': "ЁЯТО VIP ╨Ь╨╡╨╜╤О",
            'admin_panel': "ЁЯСС ╨Р╨┤╨╝╨╕╨╜ ╨Я╨░╨╜╨╡╨╗╤М", 'generate': "ЁЯЦ╝я╕П ╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П"
        },
        'help_title': "ЁЯУЪ <b>╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡ ╤А╨░╨╖╨┤╨╡╨╗ ╤Б╨┐╤А╨░╨▓╨║╨╕:</b>\n\n╨Э╨░╨╢╨╝╨╕╤В╨╡ ╨║╨╜╨╛╨┐╨║╤Г ╨╜╨╕╨╢╨╡ ╨┤╨╗╤П ╨┐╤А╨╛╤Б╨╝╨╛╤В╤А╨░ ╨║╨╛╨╝╨░╨╜╨┤ ╨┐╨╛ ╤В╨╡╨╝╨╡.",
        'help_back': "ЁЯФЩ ╨Э╨░╨╖╨░╨┤",
        'help_sections': {
            'help_basic': "ЁЯПа ╨Ю╤Б╨╜╨╛╨▓╨╜╤Л╨╡", 'help_ai': "ЁЯТм AI", 'help_memory': "ЁЯза ╨Я╨░╨╝╤П╤В╤М",
            'help_notes': "ЁЯУЭ ╨Ч╨░╨╝╨╡╤В╨║╨╕", 'help_todo': "ЁЯУЛ ╨Ч╨░╨┤╨░╤З╨╕", 'help_utils': "ЁЯМН ╨г╤В╨╕╨╗╨╕╤В╤Л",
            'help_games': "ЁЯО▓ ╨а╨░╨╖╨▓╨╗╨╡╤З╨╡╨╜╨╕╤П", 'help_vip': "ЁЯТО VIP", 'help_admin': "ЁЯСС ╨Р╨┤╨╝╨╕╨╜",
            'help_groups': "ЁЯСе ╨У╤А╤Г╨┐╨┐╤Л"
        },
        'help_text': {
            'help_basic': (
                "ЁЯПа <b>╨Ю╤Б╨╜╨╛╨▓╨╜╤Л╨╡ ╨║╨╛╨╝╨░╨╜╨┤╤Л:</b>\n\n"
                "ЁЯЪА /start - ╨Ч╨░╨┐╤Г╤Б╨║ ╨▒╨╛╤В╨░\n"
                "ЁЯУЦ /help - ╨б╨┐╨╕╤Б╨╛╨║ ╨║╨╛╨╝╨░╨╜╨┤\n"
                "тД╣я╕П /info - ╨Ш╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╤П ╨╛ ╨▒╨╛╤В╨╡\n"
                "ЁЯУК /status - ╨б╤В╨░╤В╤Г╤Б ╨╕ ╤Б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨░\n"
                "ЁЯСд /profile - ╨Я╤А╨╛╤Д╨╕╨╗╤М\n"
                "тП▒ /uptime - ╨Т╤А╨╡╨╝╤П ╤А╨░╨▒╨╛╤В╤Л\n"
                "ЁЯЧгя╕П /language - ╨б╨╝╨╡╨╜╨╕╤В╤М ╤П╨╖╤Л╨║"
            ),
            'help_ai': (
                "ЁЯТм <b>AI ╨║╨╛╨╝╨░╨╜╨┤╤Л:</b>\n\n"
                "ЁЯдЦ /ai [╨▓╨╛╨┐╤А╨╛╤Б] - ╨Ч╨░╨┤╨░╤В╤М ╨▓╨╛╨┐╤А╨╛╤Б AI\n"
                "ЁЯз╣ /clear - ╨Ю╤З╨╕╤Б╤В╨╕╤В╤М ╨║╨╛╨╜╤В╨╡╨║╤Б╤В\n\n"
                "ЁЯТб <b>╨Я╨╛╨┤╤Б╨║╨░╨╖╨║╨░:</b> ╨С╨╛╤В ╨┐╨╛╨╝╨╜╨╕╤В ╨║╨╛╨╜╤В╨╡╨║╤Б╤В ╤А╨░╨╖╨│╨╛╨▓╨╛╤А╨░, ╨▓╨║╨╗╤О╤З╨░╤П ╤Д╨╛╤В╨╛ ╨╕ ╨│╨╛╨╗╨╛╤Б╨╛╨▓╤Л╨╡!"
            ),
            'help_memory': "ЁЯза <b>╨Я╨░╨╝╤П╤В╤М:</b>\n\nЁЯТ╛ /memorysave [╨║╨╗╤О╤З] [╨╖╨╜╨░╤З╨╡╨╜╨╕╨╡]\nЁЯФН /memoryget [╨║╨╗╤О╤З]\nЁЯУЛ /memorylist\nЁЯЧС /memorydel [╨║╨╗╤О╤З]",
            'help_notes': "ЁЯУЭ <b>╨Ч╨░╨╝╨╡╤В╨║╨╕:</b>\n\nтЮХ /note [╤В╨╡╨║╤Б╤В]\nЁЯУЛ /notes\nЁЯЧС /delnote [╨╜╨╛╨╝╨╡╤А]",
            'help_todo': "ЁЯУЛ <b>╨Ч╨░╨┤╨░╤З╨╕:</b>\n\nтЮХ /todo add [╤В╨╡╨║╤Б╤В]\nЁЯУЛ /todo list\nЁЯЧС /todo del [╨╜╨╛╨╝╨╡╤А]",
            'help_utils': "ЁЯМН <b>╨г╤В╨╕╨╗╨╕╤В╤Л:</b>\n\nЁЯХР /time [╨│╨╛╤А╨╛╨┤]\nтШАя╕П /weather [╨│╨╛╤А╨╛╨┤]\nЁЯМР /translate [╤П╨╖╤Л╨║] [╤В╨╡╨║╤Б╤В]\nЁЯзо /calc [╨▓╤Л╤А╨░╨╢╨╡╨╜╨╕╨╡]\nЁЯФС /password [╨┤╨╗╨╕╨╜╨░]",
            'help_games': "ЁЯО▓ <b>╨а╨░╨╖╨▓╨╗╨╡╤З╨╡╨╜╨╕╤П:</b>\n\nЁЯО▓ /random [min] [max]\nЁЯОп /dice\nЁЯкЩ /coin\nЁЯШД /joke\nЁЯТн /quote\nЁЯФм /fact",
            'help_vip': (
                "ЁЯТО <b>VIP ╨║╨╛╨╝╨░╨╜╨┤╤Л:</b>\n\n"
                "ЁЯСС /vip - ╨б╤В╨░╤В╤Г╤Б VIP\n"
                "ЁЯЦ╝я╕П /generate [╨╛╨┐╨╕╤Б╨░╨╜╨╕╨╡] - ╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П\n"
                "тП░ /remind [╨╝╨╕╨╜╤Г╤В╤Л] [╤В╨╡╨║╤Б╤В] - ╨Э╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╨╡\n"
                "ЁЯУЛ /reminders - ╨б╨┐╨╕╤Б╨╛╨║ ╨╜╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╨╣\n"
                "ЁЯУО ╨Ю╤В╨┐╤А╨░╨▓╤М ╤Д╨░╨╣╨╗ - ╨Р╨╜╨░╨╗╨╕╨╖\n"
                "ЁЯУ╕ ╨Ю╤В╨┐╤А╨░╨▓╤М ╤Д╨╛╤В╨╛ - ╨Р╨╜╨░╨╗╨╕╨╖"
            ),
            'help_admin': (
                "ЁЯСС <b>╨Ъ╨╛╨╝╨░╨╜╨┤╤Л ╨б╨╛╨╖╨┤╨░╤В╨╡╨╗╤П:</b>\n\n"
                "ЁЯОБ /grant_vip [id] [╤Б╤А╨╛╨║] - ╨Т╤Л╨┤╨░╤В╤М VIP\n"
                "тЭМ /revoke_vip [id] - ╨Ч╨░╨▒╤А╨░╤В╤М VIP\n"
                "ЁЯСе /users - ╨б╨┐╨╕╤Б╨╛╨║ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╨╡╨╣\n"
                "ЁЯУв /broadcast [╤В╨╡╨║╤Б╤В] - ╨а╨░╤Б╤Б╤Л╨╗╨║╨░\n"
                "ЁЯУИ /stats - ╨б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨░\n"
                "ЁЯТ╛ /backup - ╨а╨╡╨╖╨╡╤А╨▓╨╜╨░╤П ╨║╨╛╨┐╨╕╤П"
            ),
            'help_groups': (
                "ЁЯСе <b>╨Ъ╨╛╨╝╨░╨╜╨┤╤Л ╨┤╨╗╤П ╨│╤А╤Г╨┐╨┐:</b>\n\n"
                "<b>╨Ь╨╛╨┤╨╡╤А╨░╤Ж╨╕╤П:</b>\n"
                "ЁЯЪл /ban - ╨Ч╨░╨▒╨░╨╜╨╕╤В╤М (╨╛╤В╨▓╨╡╤В╨╛╨╝)\n"
                "тЬЕ /unban [id] - ╨а╨░╨╖╨▒╨░╨╜╨╕╤В╤М\n"
                "ЁЯСв /kick - ╨Ъ╨╕╨║╨╜╤Г╤В╤М\n"
                "ЁЯФЗ /mute [╨╝╨╕╨╜] - ╨Ч╨░╨╝╤Г╤В╨╕╤В╤М\n"
                "ЁЯФК /unmute - ╨а╨░╨╖╨╝╤Г╤В╨╕╤В╤М\n"
                "тЪая╕П /warn - ╨Я╤А╨╡╨┤╤Г╨┐╤А╨╡╨╢╨┤╨╡╨╜╨╕╨╡\n"
                "тЬЕ /unwarn - ╨б╨╜╤П╤В╤М ╨▓╨░╤А╨╜\n"
                "ЁЯУЛ /warns - ╨б╨┐╨╕╤Б╨╛╨║ ╨▓╨░╤А╨╜╨╛╨▓\n\n"
                "<b>╨Э╨░╤Б╤В╤А╨╛╨╣╨║╨╕:</b>\n"
                "ЁЯСЛ /setwelcome [╤В╨╡╨║╤Б╤В] - ╨Я╤А╨╕╨▓╨╡╤В╤Б╤В╨▓╨╕╨╡\n"
                "ЁЯЪл /welcomeoff - ╨Т╤Л╨║╨╗. ╨┐╤А╨╕╨▓╨╡╤В╤Б╤В╨▓╨╕╨╡\n"
                "ЁЯУЬ /setrules [╤В╨╡╨║╤Б╤В] - ╨Я╤А╨░╨▓╨╕╨╗╨░\n"
                "ЁЯУЦ /rules - ╨Я╨╛╨║╨░╨╖╨░╤В╤М ╨┐╤А╨░╨▓╨╕╨╗╨░\n"
                "ЁЯдЦ /setai [on/off] - ╨Т╨║╨╗/╨▓╤Л╨║╨╗ AI\n"
                "тД╣я╕П /chatinfo - ╨Ш╨╜╤Д╨╛ ╨╛ ╤З╨░╤В╨╡\n"
                "ЁЯПЖ /top - ╨в╨╛╨┐ ╨░╨║╤В╨╕╨▓╨╜╤Л╤Е"
            )
        },
        'menu': {
            'chat': "ЁЯдЦ <b>AI ╨з╨░╤В</b>\n\n╨Я╤А╨╛╤Б╤В╨╛ ╨┐╨╕╤И╨╕ - ╤П ╨╛╤В╨▓╨╡╤З╤Г!\n╨Ю╤В╨┐╤А╨░╨▓╤М ╤Д╨╛╤В╨╛ ╨╕╨╗╨╕ ╨│╨╛╨╗╨╛╤Б╨╛╨▓╨╛╨╡ - ╤П ╨┐╨╛╨╣╨╝╤Г!\n/clear - ╨╛╤З╨╕╤Б╤В╨╕╤В╤М ╨║╨╛╨╜╤В╨╡╨║╤Б╤В",
            'notes': "ЁЯУЭ <b>╨Ч╨░╨╝╨╡╤В╨║╨╕</b>", 'notes_create': "тЮХ ╨б╨╛╨╖╨┤╨░╤В╤М", 'notes_list': "ЁЯУЛ ╨б╨┐╨╕╤Б╨╛╨║",
            'weather': "ЁЯМН <b>╨Я╨╛╨│╨╛╨┤╨░</b>\n\n/weather [╨│╨╛╤А╨╛╨┤]\n╨Я╤А╨╕╨╝╨╡╤А: /weather London",
            'time': "тП░ <b>╨Т╤А╨╡╨╝╤П</b>\n\n/time [╨│╨╛╤А╨╛╨┤]\n╨Я╤А╨╕╨╝╨╡╤А: /time Tokyo",
            'games': "ЁЯО▓ <b>╨а╨░╨╖╨▓╨╗╨╡╤З╨╡╨╜╨╕╤П</b>", 'games_dice': "ЁЯО▓ ╨Ъ╤Г╨▒╨╕╨║", 'games_coin': "ЁЯкЩ ╨Ь╨╛╨╜╨╡╤В╨░",
            'games_joke': "ЁЯШД ╨и╤Г╤В╨║╨░", 'games_quote': "ЁЯТн ╨ж╨╕╤В╨░╤В╨░", 'games_fact': "ЁЯФм ╨д╨░╨║╤В",
            'vip': "ЁЯТО <b>VIP ╨Ь╨╡╨╜╤О</b>", 'vip_reminders': "тП░ ╨Э╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╤П", 'vip_stats': "ЁЯУК ╨б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨░",
            'admin': "ЁЯСС <b>╨Р╨┤╨╝╨╕╨╜ ╨Я╨░╨╜╨╡╨╗╤М</b>", 'admin_users': "ЁЯСе ╨Я╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╨╕", 'admin_stats': "ЁЯУК ╨б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨░",
            'admin_broadcast': "ЁЯУв ╨а╨░╤Б╤Б╤Л╨╗╨║╨░",
            'generate': "ЁЯЦ╝я╕П <b>╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П (VIP)</b>\n\n/generate [╨╛╨┐╨╕╤Б╨░╨╜╨╕╨╡]\n\n╨Я╤А╨╕╨╝╨╡╤А╤Л:\nтАв /generate ╨╖╨░╨║╨░╤В\nтАв /generate ╨│╨╛╤А╨╛╨┤\n\nЁЯТб Gemini Imagen"
        },
        'info': (
            "ЁЯдЦ <b>AI DISCO BOT v4.0</b>\n\n"
            "<b>╨Т╨╡╤А╤Б╨╕╤П:</b> 4.0 (Unified Context)\n"
            "<b>AI:</b> Gemini 2.5 Flash\n"
            "<b>╨б╨╛╨╖╨┤╨░╤В╨╡╨╗╤М:</b> @Ernest_Kostevich\n\n"
            "<b>тЪб ╨Ю╤Б╨╛╨▒╨╡╨╜╨╜╨╛╤Б╤В╨╕:</b>\n"
            "тАв ╨Х╨┤╨╕╨╜╤Л╨╣ ╨║╨╛╨╜╤В╨╡╨║╤Б╤В (╤В╨╡╨║╤Б╤В+╤Д╨╛╤В╨╛+╨│╨╛╨╗╨╛╤Б)\n"
            "тАв PostgreSQL\n"
            "тАв VIP ╨┤╨╗╤П ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╨╡╨╣ ╨╕ ╨│╤А╤Г╨┐╨┐\n"
            "тАв ╨Ь╨╛╨┤╨╡╤А╨░╤Ж╨╕╤П ╨│╤А╤Г╨┐╨┐\n"
            "тАв ╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╣\n\n"
            "<b>ЁЯТм ╨Я╨╛╨┤╨┤╨╡╤А╨╢╨║╨░:</b> @Ernest_Kostevich"
        ),
        'status': (
            "ЁЯУК <b>╨б╨в╨Р╨в╨г╨б</b>\n\n"
            "ЁЯСе ╨Я╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╨╕: {users}\n"
            "ЁЯТО VIP: {vips}\n"
            "ЁЯСе ╨У╤А╤Г╨┐╨┐: {groups}\n\n"
            "<b>ЁЯУИ ╨Р╨║╤В╨╕╨▓╨╜╨╛╤Б╤В╤М:</b>\n"
            "тАв ╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣: {msg_count}\n"
            "тАв ╨Ъ╨╛╨╝╨░╨╜╨┤: {cmd_count}\n"
            "тАв AI ╨╖╨░╨┐╤А╨╛╤Б╨╛╨▓: {ai_count}\n\n"
            "<b>тП▒ ╨а╨░╨▒╨╛╤В╨░╨╡╤В:</b> {days}╨┤ {hours}╤З\n\n"
            "<b>тЬЕ ╨б╤В╨░╤В╤Г╤Б:</b> ╨Ю╨╜╨╗╨░╨╣╨╜\n"
            "<b>ЁЯдЦ AI:</b> Gemini 2.5 тЬУ\n"
            "<b>ЁЯЧДя╕П ╨С╨Ф:</b> {db_status}"
        ),
        'profile': (
            "ЁЯСд <b>{first_name}</b>\n"
            "ЁЯЖФ <code>{user_id}</code>\n"
            "{username_line}\n"
            "ЁЯУЕ {registered_date}\n"
            "ЁЯУК ╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣: {msg_count}\n"
            "ЁЯОп ╨Ъ╨╛╨╝╨░╨╜╨┤: {cmd_count}\n"
            "ЁЯУЭ ╨Ч╨░╨╝╨╡╤В╨╛╨║: {notes_count}"
        ),
        'profile_vip': "\nЁЯТО VIP ╨┤╨╛: {date}",
        'profile_vip_forever': "\nЁЯТО VIP: ╨Э╨░╨▓╤Б╨╡╨│╨┤╨░ тЩ╛я╕П",
        'uptime': "тП▒ <b>╨Р╨Я╨в╨Р╨Щ╨Ь</b>\n\nЁЯХР ╨Ч╨░╨┐╤Г╤Й╨╡╨╜: {start_time}\nтП░ ╨а╨░╨▒╨╛╤В╨░╨╡╤В: {days}╨┤ {hours}╤З {minutes}╨╝\n\nтЬЕ ╨Ю╨╜╨╗╨░╨╣╨╜",
        'vip_status_active': "ЁЯТО <b>VIP ╨б╨в╨Р╨в╨г╨б</b>\n\nтЬЕ ╨Р╨║╤В╨╕╨▓╨╡╨╜!\n\n",
        'vip_status_until': "тП░ ╨Ф╨╛: {date}\n\n",
        'vip_status_forever': "тП░ ╨Э╨░╨▓╤Б╨╡╨│╨┤╨░ тЩ╛я╕П\n\n",
        'vip_status_bonus': "<b>ЁЯОБ ╨Я╤А╨╡╨╕╨╝╤Г╤Й╨╡╤Б╤В╨▓╨░:</b>\nтАв тП░ ╨Э╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╤П\nтАв ЁЯЦ╝я╕П ╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╣\nтАв ЁЯФН ╨Р╨╜╨░╨╗╨╕╨╖ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╣\nтАв ЁЯУО ╨Р╨╜╨░╨╗╨╕╨╖ ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В╨╛╨▓",
        'vip_status_inactive': "ЁЯТО <b>VIP ╨б╨в╨Р╨в╨г╨б</b>\n\nтЭМ ╨Э╨╡╤В VIP.\n\n╨б╨▓╤П╨╢╨╕╤В╨╡╤Б╤М ╤Б @Ernest_Kostevich",
        'vip_only': "ЁЯТО ╨н╤В╨░ ╤Д╤Г╨╜╨║╤Ж╨╕╤П ╨┤╨╛╤Б╤В╤Г╨┐╨╜╨░ ╤В╨╛╨╗╤М╨║╨╛ ╨┤╨╗╤П VIP.\n\n╨б╨▓╤П╨╢╨╕╤В╨╡╤Б╤М ╤Б @Ernest_Kostevich",
        'admin_only': "тЭМ ╨в╨╛╨╗╤М╨║╨╛ ╨┤╨╗╤П ╤Б╨╛╨╖╨┤╨░╤В╨╡╨╗╤П.",
        'gen_prompt_needed': "тЭУ /generate [╨╛╨┐╨╕╤Б╨░╨╜╨╕╨╡]\n\n╨Я╤А╨╕╨╝╨╡╤А: /generate ╨╖╨░╨║╨░╤В ╨╜╨░╨┤ ╨╛╨║╨╡╨░╨╜╨╛╨╝",
        'gen_in_progress': "ЁЯОи ╨У╨╡╨╜╨╡╤А╨╕╤А╤Г╤О ╤Б Imagen 3...",
        'gen_caption': "ЁЯЦ╝я╕П <b>{prompt}</b>\n\nЁЯТО VIP | Imagen 3",
        'gen_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨│╨╡╨╜╨╡╤А╨░╤Ж╨╕╨╕ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╤П",
        'gen_error_api': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ API: {error}",
        'ai_prompt_needed': "тЭУ /ai [╨▓╨╛╨┐╤А╨╛╤Б]",
        'ai_error': "ЁЯШФ ╨Ю╤И╨╕╨▒╨║╨░ AI, ╨┐╨╛╨┐╤А╨╛╨▒╤Г╨╣╤В╨╡ ╤Б╨╜╨╛╨▓╨░.",
        'clear_context': "ЁЯз╣ ╨Ъ╨╛╨╜╤В╨╡╨║╤Б╤В ╤З╨░╤В╨░ ╨╛╤З╨╕╤Й╨╡╨╜!",
        'note_prompt_needed': "тЭУ /note [╤В╨╡╨║╤Б╤В]",
        'note_saved': "тЬЕ ╨Ч╨░╨╝╨╡╤В╨║╨░ #{num} ╤Б╨╛╤Е╤А╨░╨╜╨╡╨╜╨░!\n\nЁЯУЭ {text}",
        'notes_empty': "ЁЯУн ╨г ╨▓╨░╤Б ╨╜╨╡╤В ╨╖╨░╨╝╨╡╤В╨╛╨║.",
        'notes_list_title': "ЁЯУЭ <b>╨Ч╨░╨╝╨╡╤В╨║╨╕ ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "тЭУ /delnote [╨╜╨╛╨╝╨╡╤А]",
        'delnote_success': "тЬЕ ╨Ч╨░╨╝╨╡╤В╨║╨░ #{num} ╤Г╨┤╨░╨╗╨╡╨╜╨░:\n\nЁЯУЭ {text}",
        'delnote_not_found': "тЭМ ╨Ч╨░╨╝╨╡╤В╨║╨░ #{num} ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜╨░.",
        'delnote_invalid_num': "тЭМ ╨г╨║╨░╨╢╨╕╤В╨╡ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨╜╨╛╨╝╨╡╤А.",
        'todo_prompt_needed': "тЭУ /todo add [╤В╨╡╨║╤Б╤В] | list | del [╨╜╨╛╨╝╨╡╤А]",
        'todo_add_prompt_needed': "тЭУ /todo add [╤В╨╡╨║╤Б╤В]",
        'todo_saved': "тЬЕ ╨Ч╨░╨┤╨░╤З╨░ #{num} ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨░!\n\nЁЯУЛ {text}",
        'todo_empty': "ЁЯУн ╨г ╨▓╨░╤Б ╨╜╨╡╤В ╨╖╨░╨┤╨░╤З.",
        'todo_list_title': "ЁЯУЛ <b>╨Ч╨░╨┤╨░╤З╨╕ ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "тЭУ /todo del [╨╜╨╛╨╝╨╡╤А]",
        'todo_del_success': "тЬЕ ╨Ч╨░╨┤╨░╤З╨░ #{num} ╤Г╨┤╨░╨╗╨╡╨╜╨░:\n\nЁЯУЛ {text}",
        'todo_del_not_found': "тЭМ ╨Ч╨░╨┤╨░╤З╨░ #{num} ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜╨░.",
        'todo_del_invalid_num': "тЭМ ╨г╨║╨░╨╢╨╕╤В╨╡ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨╜╨╛╨╝╨╡╤А.",
        'time_result': "тП░ <b>{city}</b>\n\nЁЯХР ╨Т╤А╨╡╨╝╤П: {time}\nЁЯУЕ ╨Ф╨░╤В╨░: {date}\nЁЯМН ╨Я╨╛╤П╤Б: {tz}",
        'time_city_not_found': "тЭМ ╨У╨╛╤А╨╛╨┤ '{city}' ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.",
        'weather_result': "ЁЯМН <b>{city}</b>\n\nЁЯМб ╨в╨╡╨╝╨┐╨╡╤А╨░╤В╤Г╤А╨░: {temp}┬░C\nЁЯдФ ╨Ю╤Й╤Г╤Й╨░╨╡╤В╤Б╤П: {feels}┬░C\nтШБя╕П {desc}\nЁЯТз ╨Т╨╗╨░╨╢╨╜╨╛╤Б╤В╤М: {humidity}%\nЁЯТи ╨Т╨╡╤В╨╡╤А: {wind} ╨║╨╝/╤З",
        'weather_city_not_found': "тЭМ ╨У╨╛╤А╨╛╨┤ '{city}' ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.",
        'weather_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨╕╤П ╨┐╨╛╨│╨╛╨┤╤Л.",
        'translate_prompt_needed': "тЭУ /translate [╤П╨╖╤Л╨║] [╤В╨╡╨║╤Б╤В]\n\n╨Я╤А╨╕╨╝╨╡╤А: /translate en ╨Я╤А╨╕╨▓╨╡╤В",
        'translate_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨┐╨╡╤А╨╡╨▓╨╛╨┤╨░.",
        'calc_prompt_needed': "тЭУ /calc [╨▓╤Л╤А╨░╨╢╨╡╨╜╨╕╨╡]\n\n╨Я╤А╨╕╨╝╨╡╤А: /calc 2+2*5",
        'calc_result': "ЁЯзо <b>╨а╨╡╨╖╤Г╨╗╤М╤В╨░╤В:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨▓╤Л╤З╨╕╤Б╨╗╨╡╨╜╨╕╤П.",
        'password_length_error': "тЭМ ╨Ф╨╗╨╕╨╜╨░ ╨┐╨░╤А╨╛╨╗╤П ╨┤╨╛╨╗╨╢╨╜╨░ ╨▒╤Л╤В╤М ╨╛╤В 8 ╨┤╨╛ 50.",
        'password_result': "ЁЯФС <b>╨Т╨░╤И ╨┐╨░╤А╨╛╨╗╤М:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "тЭМ ╨г╨║╨░╨╢╨╕╤В╨╡ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Г╤О ╨┤╨╗╨╕╨╜╤Г.",
        'random_result': "ЁЯО▓ ╨б╨╗╤Г╤З╨░╨╣╨╜╨╛╨╡ ╤З╨╕╤Б╨╗╨╛ ╨╛╤В {min} ╨┤╨╛ {max}:\n\n<b>{result}</b>",
        'random_invalid_range': "тЭМ ╨г╨║╨░╨╢╨╕╤В╨╡ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Л╨╣ ╨┤╨╕╨░╨┐╨░╨╖╨╛╨╜.",
        'dice_result': "ЁЯО▓ {emoji} ╨Т╤Л╨┐╨░╨╗╨╛: <b>{result}</b>",
        'coin_result': "ЁЯкЩ {emoji} ╨Т╤Л╨┐╨░╨╗╨╛: <b>{result}</b>",
        'coin_heads': "╨Ю╤А╤С╨╗", 'coin_tails': "╨а╨╡╤И╨║╨░",
        'joke_title': "ЁЯШД <b>╨и╤Г╤В╨║╨░:</b>\n\n",
        'quote_title': "ЁЯТн <b>╨ж╨╕╤В╨░╤В╨░:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "ЁЯФм <b>╨д╨░╨║╤В:</b>\n\n",
        'remind_prompt_needed': "тЭУ /remind [╨╝╨╕╨╜╤Г╤В╤Л] [╤В╨╡╨║╤Б╤В]",
        'remind_success': "тП░ ╨Э╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╨╡ ╤Б╨╛╨╖╨┤╨░╨╜╨╛!\n\nЁЯУЭ {text}\nЁЯХР ╨з╨╡╤А╨╡╨╖ {minutes} ╨╝╨╕╨╜",
        'remind_invalid_time': "тЭМ ╨г╨║╨░╨╢╨╕╤В╨╡ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╨╛╨╡ ╨▓╤А╨╡╨╝╤П.",
        'reminders_empty': "ЁЯУн ╨Э╨╡╤В ╨░╨║╤В╨╕╨▓╨╜╤Л╤Е ╨╜╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╨╣.",
        'reminders_list_title': "тП░ <b>╨Э╨░╨┐╨╛╨╝╨╕╨╜╨░╨╜╨╕╤П ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\nЁЯУЭ {text}\n\n",
        'reminder_alert': "тП░ <b>╨Э╨Р╨Я╨Ю╨Ь╨Ш╨Э╨Р╨Э╨Ш╨Х</b>\n\nЁЯУЭ {text}",
        'grant_vip_prompt': "тЭУ /grant_vip [id/@username] [╤Б╤А╨╛╨║]\n\n╨б╤А╨╛╨║╨╕: week, month, year, forever",
        'grant_vip_user_not_found': "тЭМ ╨Я╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤М/╤З╨░╤В '{id}' ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.",
        'grant_vip_invalid_duration': "тЭМ ╨Э╨╡╨▓╨╡╤А╨╜╤Л╨╣ ╤Б╤А╨╛╨║. ╨Ф╨╛╤Б╤В╤Г╨┐╨╜╨╛: week, month, year, forever",
        'grant_vip_success': "тЬЕ VIP ╤Б╤В╨░╤В╤Г╤Б ╨▓╤Л╨┤╨░╨╜!\n\nЁЯЖФ <code>{id}</code>\nтП░ {duration_text}",
        'grant_vip_dm': "ЁЯОЙ ╨Т╨░╨╝ ╨▓╤Л╨┤╨░╨╜ VIP ╤Б╤В╨░╤В╤Г╤Б {duration_text}!",
        'duration_until': "╨┤╨╛ {date}",
        'duration_forever': "╨╜╨░╨▓╤Б╨╡╨│╨┤╨░",
        'revoke_vip_prompt': "тЭУ /revoke_vip [id/@username]",
        'revoke_vip_success': "тЬЕ VIP ╤Б╤В╨░╤В╤Г╤Б ╨╛╤В╨╛╨╖╨▓╨░╨╜ ╤Г <code>{id}</code>.",
        'users_list_title': "ЁЯСе <b>╨Я╨Ю╨Ы╨м╨Ч╨Ю╨Т╨Р╨в╨Х╨Ы╨Ш ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... ╨╕ ╨╡╤Й╤С {count}</i>",
        'broadcast_prompt': "тЭУ /broadcast [╤В╨╡╨║╤Б╤В ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╤П]",
        'broadcast_started': "ЁЯУд ╨Э╨░╤З╨╕╨╜╨░╤О ╤А╨░╤Б╤Б╤Л╨╗╨║╤Г...",
        'broadcast_finished': "тЬЕ ╨а╨░╤Б╤Б╤Л╨╗╨║╨░ ╨╖╨░╨▓╨╡╤А╤И╨╡╨╜╨░!\n\nтЬЕ ╨г╤Б╨┐╨╡╤И╨╜╨╛: {success}\nтЭМ ╨Ю╤И╨╕╨▒╨╛╨║: {failed}",
        'broadcast_dm': "ЁЯУв <b>╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╨╛╤В ╤Б╨╛╨╖╨┤╨░╤В╨╡╨╗╤П:</b>\n\n{text}",
        'stats_admin_title': "ЁЯУК <b>╨б╨в╨Р╨в╨Ш╨б╨в╨Ш╨Ъ╨Р</b>\n\n<b>ЁЯСе ╨Я╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╨╕:</b> {users}\n<b>ЁЯТО VIP:</b> {vips}\n\n<b>ЁЯУИ ╨Р╨║╤В╨╕╨▓╨╜╨╛╤Б╤В╤М:</b>\nтАв ╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣: {msg_count}\nтАв ╨Ъ╨╛╨╝╨░╨╜╨┤: {cmd_count}\nтАв AI ╨╖╨░╨┐╤А╨╛╤Б╨╛╨▓: {ai_count}",
        'backup_success': "тЬЕ ╨С╤Н╨║╨░╨┐ ╤Б╨╛╨╖╨┤╨░╨╜\n\nЁЯУЕ {date}",
        'backup_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨▒╤Н╨║╨░╨┐╨░: {error}",
        'file_received': "ЁЯУе ╨Ч╨░╨│╤А╤Г╨╢╨░╤О ╤Д╨░╨╣╨╗...",
        'file_analyzing': "ЁЯУД <b>╨д╨░╨╣╨╗:</b> {filename}\n\nЁЯдЦ <b>╨Р╨╜╨░╨╗╨╕╨╖:</b>\n\n{text}",
        'file_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨╕: {error}",
        'photo_analyzing': "ЁЯФН ╨Р╨╜╨░╨╗╨╕╨╖╨╕╤А╤Г╤О ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡...",
        'photo_result': "ЁЯУ╕ <b>╨Р╨╜╨░╨╗╨╕╨╖:</b>\n\n{text}\n\nЁЯТО VIP",
        'photo_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨╕ ╤Д╨╛╤В╨╛: {error}",
        'photo_no_caption': "ЁЯУ╕ ╨Я╨╛╨╗╤Г╤З╨╕╨╗ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡. ╨з╤В╨╛ ╨╝╨╜╨╡ ╤Б ╨╜╨╕╨╝ ╤Б╨┤╨╡╨╗╨░╤В╤М?\n\nЁЯТб ╨Я╨╛╨┤╤Б╨║╨░╨╖╨║╨░: ╨╛╤В╨┐╤А╨░╨▓╤М╤В╨╡ ╤В╨╡╨║╤Б╤В ╤Б ╨▓╨╛╨┐╤А╨╛╤Б╨╛╨╝ ╨╛╨▒ ╤Н╤В╨╛╨╝ ╤Д╨╛╤В╨╛.",
        'voice_transcribing': "ЁЯОЩя╕П ╨а╨░╤Б╨┐╨╛╨╖╨╜╨░╤О ╨│╨╛╨╗╨╛╤Б...",
        'voice_result': "ЁЯУЭ <b>╨в╤А╨░╨╜╤Б╨║╤А╨╕╨┐╤Ж╨╕╤П:</b>\n\n{text}",
        'voice_error': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨╕ ╨│╨╛╨╗╨╛╤Б╨░: {error}",
        'error_generic': "тЭМ ╨Ю╤И╨╕╨▒╨║╨░: {error}",
        'section_not_found': "тЭМ ╨а╨░╨╖╨┤╨╡╨╗ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.",
        
        # Group moderation strings
        'need_admin': "тЭМ ╨Э╤Г╨╢╨╜╤Л ╨┐╤А╨░╨▓╨░ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░.",
        'need_reply': "тЭМ ╨Ю╤В╨▓╨╡╤В╤М╤В╨╡ ╨╜╨░ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П.",
        'bot_need_admin': "тЭМ ╨С╨╛╤В ╨┤╨╛╨╗╨╢╨╡╨╜ ╨▒╤Л╤В╤М ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨╛╨╝.",
        'cant_self': "тЭМ ╨Э╨╡╨╗╤М╨╖╤П ╨┐╤А╨╕╨╝╨╡╨╜╨╕╤В╤М ╨║ ╤Б╨╡╨▒╨╡.",
        'cant_admin': "тЭМ ╨Э╨╡╨╗╤М╨╖╤П ╨┐╤А╨╕╨╝╨╡╨╜╨╕╤В╤М ╨║ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╤Г.",
        'user_banned': "ЁЯЪл <b>{name}</b> ╨╖╨░╨▒╨░╨╜╨╡╨╜.\n\n╨Я╤А╨╕╤З╨╕╨╜╨░: {reason}",
        'user_unbanned': "тЬЕ ╨Я╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤М <code>{id}</code> ╤А╨░╨╖╨▒╨░╨╜╨╡╨╜.",
        'user_kicked': "ЁЯСв <b>{name}</b> ╨║╨╕╨║╨╜╤Г╤В.",
        'user_muted': "ЁЯФЗ <b>{name}</b> ╨╖╨░╨╝╤Г╤З╨╡╨╜ ╨╜╨░ {minutes} ╨╝╨╕╨╜.",
        'user_unmuted': "ЁЯФК <b>{name}</b> ╤А╨░╨╖╨╝╤Г╤З╨╡╨╜.",
        'user_warned': "тЪая╕П <b>{name}</b> ╨┐╨╛╨╗╤Г╤З╨╕╨╗ ╨┐╤А╨╡╨┤╤Г╨┐╤А╨╡╨╢╨┤╨╡╨╜╨╕╨╡ ({count}/3).\n\n╨Я╤А╨╕╤З╨╕╨╜╨░: {reason}",
        'user_warned_ban': "ЁЯЪл <b>{name}</b> ╨╖╨░╨▒╨░╨╜╨╡╨╜ (3/3 ╨▓╨░╤А╨╜╨╛╨▓).",
        'user_unwarned': "тЬЕ ╨Т╨░╤А╨╜ ╤Б╨╜╤П╤В ╤Б <b>{name}</b> ({count}/3).",
        'warns_list': "тЪая╕П <b>╨Т╨░╤А╨╜╤Л {name}:</b> {count}/3",
        'warns_empty': "тЬЕ ╨г <b>{name}</b> ╨╜╨╡╤В ╨▓╨░╤А╨╜╨╛╨▓.",
        'welcome_set': "тЬЕ ╨Я╤А╨╕╨▓╨╡╤В╤Б╤В╨▓╨╕╨╡ ╤Г╤Б╤В╨░╨╜╨╛╨▓╨╗╨╡╨╜╨╛!\n\n{text}",
        'welcome_off': "тЬЕ ╨Я╤А╨╕╨▓╨╡╤В╤Б╤В╨▓╨╕╨╡ ╨▓╤Л╨║╨╗╤О╤З╨╡╨╜╨╛.",
        'rules_set': "тЬЕ ╨Я╤А╨░╨▓╨╕╨╗╨░ ╤Г╤Б╤В╨░╨╜╨╛╨▓╨╗╨╡╨╜╤Л!",
        'rules_text': "ЁЯУЬ <b>╨Я╤А╨░╨▓╨╕╨╗╨░ ╤З╨░╤В╨░:</b>\n\n{rules}",
        'rules_empty': "ЁЯУЬ ╨Я╤А╨░╨▓╨╕╨╗╨░ ╨╜╨╡ ╤Г╤Б╤В╨░╨╜╨╛╨▓╨╗╨╡╨╜╤Л.",
        'ai_enabled': "тЬЕ AI ╨▓╨║╨╗╤О╤З╨╡╨╜ ╨▓ ╤Н╤В╨╛╨╝ ╤З╨░╤В╨╡.",
        'ai_disabled': "тЭМ AI ╨▓╤Л╨║╨╗╤О╤З╨╡╨╜ ╨▓ ╤Н╤В╨╛╨╝ ╤З╨░╤В╨╡.",
        'chat_info': (
            "тД╣я╕П <b>╨Ш╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╤П ╨╛ ╤З╨░╤В╨╡</b>\n\n"
            "ЁЯУЫ ╨Э╨░╨╖╨▓╨░╨╜╨╕╨╡: {title}\n"
            "ЁЯЖФ ID: <code>{id}</code>\n"
            "ЁЯТО VIP: {vip_status}\n"
            "ЁЯдЦ AI: {ai_status}\n"
            "ЁЯСЛ ╨Я╤А╨╕╨▓╨╡╤В╤Б╤В╨▓╨╕╨╡: {welcome_status}\n"
            "ЁЯУК ╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣: {messages}"
        ),
        'top_users': "ЁЯПЖ <b>╨в╨╛╨┐ ╨░╨║╤В╨╕╨▓╨╜╤Л╤Е:</b>\n\n",
        'top_users_item': "{medal} <b>{name}</b> - {count} ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣\n",
        'top_empty': "ЁЯУн ╨Я╨╛╨║╨░ ╨╜╨╡╤В ╤Б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨╕.",
        'new_member_welcome': "ЁЯСЛ ╨Ф╨╛╨▒╤А╨╛ ╨┐╨╛╨╢╨░╨╗╨╛╨▓╨░╤В╤М, <b>{name}</b>!",
        'group_help': "ЁЯСе ╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣╤В╨╡ /help ╨╕ ╨▓╤Л╨▒╨╡╤А╨╕╤В╨╡ ╤А╨░╨╖╨┤╨╡╨╗ '╨У╤А╤Г╨┐╨┐╤Л' ╨┤╨╗╤П ╤Б╨┐╨╕╤Б╨║╨░ ╨║╨╛╨╝╨░╨╜╨┤ ╨╝╨╛╨┤╨╡╤А╨░╤Ж╨╕╨╕.",
    },
    'en': {
        'welcome': (
            "ЁЯдЦ <b>AI DISCO BOT</b>\n\n"
            "Hi, {first_name}! I'm a bot powered by <b>Gemini 2.5</b>.\n\n"
            "<b>ЁЯОп Features:</b>\n"
            "ЁЯТм AI chat with context (remembers photos, voice, files)\n"
            "ЁЯУЭ Notes and To-Dos\n"
            "ЁЯМН Weather and Time\n"
            "ЁЯО▓ Entertainment\n"
            "ЁЯУО File Analysis (VIP)\n"
            "ЁЯФН Image Analysis (VIP)\n"
            "ЁЯЦ╝я╕П Image Generation (VIP)\n"
            "ЁЯСе Group moderation\n\n"
            "<b>тЪб Commands:</b>\n"
            "/help - All commands\n"
            "/language - Change language\n"
            "/vip - VIP Status\n\n"
            "<b>ЁЯСитАНЁЯТ╗ Creator:</b> @{creator}"
        ),
        'lang_changed': "тЬЕ Language changed to English ЁЯЗмЁЯЗз",
        'lang_choose': "ЁЯМР Please select a language:",
        'main_keyboard': {
            'chat': "ЁЯТм AI Chat", 'notes': "ЁЯУЭ Notes", 'weather': "ЁЯМН Weather", 'time': "тП░ Time",
            'games': "ЁЯО▓ Games", 'info': "тД╣я╕П Info", 'vip_menu': "ЁЯТО VIP Menu",
            'admin_panel': "ЁЯСС Admin Panel", 'generate': "ЁЯЦ╝я╕П Generate"
        },
        'help_title': "ЁЯУЪ <b>Choose a help section:</b>\n\nPress a button below to see commands.",
        'help_back': "ЁЯФЩ Back",
        'help_sections': {
            'help_basic': "ЁЯПа Basic", 'help_ai': "ЁЯТм AI", 'help_memory': "ЁЯза Memory",
            'help_notes': "ЁЯУЭ Notes", 'help_todo': "ЁЯУЛ To-Do", 'help_utils': "ЁЯМН Utilities",
            'help_games': "ЁЯО▓ Games", 'help_vip': "ЁЯТО VIP", 'help_admin': "ЁЯСС Admin",
            'help_groups': "ЁЯСе Groups"
        },
        'help_text': {
            'help_basic': "ЁЯПа <b>Basic Commands:</b>\n\nЁЯЪА /start - Start bot\nЁЯУЦ /help - Commands\nтД╣я╕П /info - Bot info\nЁЯУК /status - Status\nЁЯСд /profile - Profile\nтП▒ /uptime - Uptime\nЁЯЧгя╕П /language - Language",
            'help_ai': "ЁЯТм <b>AI Commands:</b>\n\nЁЯдЦ /ai [question] - Ask AI\nЁЯз╣ /clear - Clear context\n\nЁЯТб Bot remembers context including photos and voice!",
            'help_memory': "ЁЯза <b>Memory:</b>\n\nЁЯТ╛ /memorysave [key] [value]\nЁЯФН /memoryget [key]\nЁЯУЛ /memorylist\nЁЯЧС /memorydel [key]",
            'help_notes': "ЁЯУЭ <b>Notes:</b>\n\nтЮХ /note [text]\nЁЯУЛ /notes\nЁЯЧС /delnote [number]",
            'help_todo': "ЁЯУЛ <b>To-Do:</b>\n\nтЮХ /todo add [text]\nЁЯУЛ /todo list\nЁЯЧС /todo del [number]",
            'help_utils': "ЁЯМН <b>Utilities:</b>\n\nЁЯХР /time [city]\nтШАя╕П /weather [city]\nЁЯМР /translate [lang] [text]\nЁЯзо /calc [expr]\nЁЯФС /password [length]",
            'help_games': "ЁЯО▓ <b>Games:</b>\n\nЁЯО▓ /random [min] [max]\nЁЯОп /dice\nЁЯкЩ /coin\nЁЯШД /joke\nЁЯТн /quote\nЁЯФм /fact",
            'help_vip': "ЁЯТО <b>VIP Commands:</b>\n\nЁЯСС /vip - Status\nЁЯЦ╝я╕П /generate [prompt]\nтП░ /remind [min] [text]\nЁЯУЛ /reminders\nЁЯУО Send file - Analyze\nЁЯУ╕ Send photo - Analyze",
            'help_admin': "ЁЯСС <b>Creator Commands:</b>\n\nЁЯОБ /grant_vip [id] [duration]\nтЭМ /revoke_vip [id]\nЁЯСе /users\nЁЯУв /broadcast [text]\nЁЯУИ /stats\nЁЯТ╛ /backup",
            'help_groups': "ЁЯСе <b>Group Commands:</b>\n\n<b>Moderation:</b>\nЁЯЪл /ban - Ban (reply)\nтЬЕ /unban [id]\nЁЯСв /kick\nЁЯФЗ /mute [min]\nЁЯФК /unmute\nтЪая╕П /warn\nтЬЕ /unwarn\nЁЯУЛ /warns\n\n<b>Settings:</b>\nЁЯСЛ /setwelcome [text]\nЁЯЪл /welcomeoff\nЁЯУЬ /setrules [text]\nЁЯУЦ /rules\nЁЯдЦ /setai [on/off]\nтД╣я╕П /chatinfo\nЁЯПЖ /top"
        },
        'menu': {
            'chat': "ЁЯдЦ <b>AI Chat</b>\n\nJust type - I'll answer!\nSend photo or voice - I understand!\n/clear - clear context",
            'notes': "ЁЯУЭ <b>Notes</b>", 'notes_create': "тЮХ Create", 'notes_list': "ЁЯУЛ List",
            'weather': "ЁЯМН <b>Weather</b>\n\n/weather [city]",
            'time': "тП░ <b>Time</b>\n\n/time [city]",
            'games': "ЁЯО▓ <b>Games</b>", 'games_dice': "ЁЯО▓ Dice", 'games_coin': "ЁЯкЩ Coin",
            'games_joke': "ЁЯШД Joke", 'games_quote': "ЁЯТн Quote", 'games_fact': "ЁЯФм Fact",
            'vip': "ЁЯТО <b>VIP Menu</b>", 'vip_reminders': "тП░ Reminders", 'vip_stats': "ЁЯУК Stats",
            'admin': "ЁЯСС <b>Admin Panel</b>", 'admin_users': "ЁЯСе Users", 'admin_stats': "ЁЯУК Stats",
            'admin_broadcast': "ЁЯУв Broadcast",
            'generate': "ЁЯЦ╝я╕П <b>Generation (VIP)</b>\n\n/generate [prompt]"
        },
        'info': "ЁЯдЦ <b>AI DISCO BOT v4.0</b>\n\n<b>Version:</b> 4.0 (Unified Context)\n<b>AI:</b> Gemini 2.5 Flash\n<b>Creator:</b> @Ernest_Kostevich\n\n<b>тЪб Features:</b>\nтАв Unified context (text+photo+voice)\nтАв PostgreSQL\nтАв VIP for users and groups\nтАв Group moderation\nтАв Image generation\n\n<b>ЁЯТм Support:</b> @Ernest_Kostevich",
        'status': "ЁЯУК <b>STATUS</b>\n\nЁЯСе Users: {users}\nЁЯТО VIPs: {vips}\nЁЯСе Groups: {groups}\n\n<b>ЁЯУИ Activity:</b>\nтАв Messages: {msg_count}\nтАв Commands: {cmd_count}\nтАв AI Requests: {ai_count}\n\n<b>тП▒ Uptime:</b> {days}d {hours}h\n\n<b>тЬЕ Status:</b> Online\n<b>ЁЯдЦ AI:</b> Gemini 2.5 тЬУ\n<b>ЁЯЧДя╕П DB:</b> {db_status}",
        'profile': "ЁЯСд <b>{first_name}</b>\nЁЯЖФ <code>{user_id}</code>\n{username_line}\nЁЯУЕ {registered_date}\nЁЯУК Messages: {msg_count}\nЁЯОп Commands: {cmd_count}\nЁЯУЭ Notes: {notes_count}",
        'profile_vip': "\nЁЯТО VIP until: {date}",
        'profile_vip_forever': "\nЁЯТО VIP: Forever тЩ╛я╕П",
        'uptime': "тП▒ <b>UPTIME</b>\n\nЁЯХР Started: {start_time}\nтП░ Running: {days}d {hours}h {minutes}m\n\nтЬЕ Online",
        'vip_status_active': "ЁЯТО <b>VIP STATUS</b>\n\nтЬЕ Active!\n\n",
        'vip_status_until': "тП░ Until: {date}\n\n",
        'vip_status_forever': "тП░ Forever тЩ╛я╕П\n\n",
        'vip_status_bonus': "<b>ЁЯОБ Perks:</b>\nтАв тП░ Reminders\nтАв ЁЯЦ╝я╕П Image Generation\nтАв ЁЯФН Image Analysis\nтАв ЁЯУО Document Analysis",
        'vip_status_inactive': "ЁЯТО <b>VIP STATUS</b>\n\nтЭМ No VIP.\n\nContact @Ernest_Kostevich",
        'vip_only': "ЁЯТО VIP only feature.\n\nContact @Ernest_Kostevich",
        'admin_only': "тЭМ Creator only.",
        'gen_prompt_needed': "тЭУ /generate [prompt]",
        'gen_in_progress': "ЁЯОи Generating with Imagen 3...",
        'gen_caption': "ЁЯЦ╝я╕П <b>{prompt}</b>\n\nЁЯТО VIP | Imagen 3",
        'gen_error': "тЭМ Image generation failed",
        'gen_error_api': "тЭМ API Error: {error}",
        'ai_prompt_needed': "тЭУ /ai [question]",
        'ai_error': "ЁЯШФ AI Error, try again.",
        'clear_context': "ЁЯз╣ Chat context cleared!",
        'note_prompt_needed': "тЭУ /note [text]",
        'note_saved': "тЬЕ Note #{num} saved!\n\nЁЯУЭ {text}",
        'notes_empty': "ЁЯУн No notes.",
        'notes_list_title': "ЁЯУЭ <b>Notes ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "тЭУ /delnote [number]",
        'delnote_success': "тЬЕ Note #{num} deleted:\n\nЁЯУЭ {text}",
        'delnote_not_found': "тЭМ Note #{num} not found.",
        'delnote_invalid_num': "тЭМ Invalid number.",
        'todo_prompt_needed': "тЭУ /todo add [text] | list | del [number]",
        'todo_add_prompt_needed': "тЭУ /todo add [text]",
        'todo_saved': "тЬЕ Task #{num} added!\n\nЁЯУЛ {text}",
        'todo_empty': "ЁЯУн No tasks.",
        'todo_list_title': "ЁЯУЛ <b>Tasks ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "тЭУ /todo del [number]",
        'todo_del_success': "тЬЕ Task #{num} deleted:\n\nЁЯУЛ {text}",
        'todo_del_not_found': "тЭМ Task #{num} not found.",
        'todo_del_invalid_num': "тЭМ Invalid number.",
        'time_result': "тП░ <b>{city}</b>\n\nЁЯХР Time: {time}\nЁЯУЕ Date: {date}\nЁЯМН Zone: {tz}",
        'time_city_not_found': "тЭМ City '{city}' not found.",
        'weather_result': "ЁЯМН <b>{city}</b>\n\nЁЯМб Temp: {temp}┬░C\nЁЯдФ Feels: {feels}┬░C\nтШБя╕П {desc}\nЁЯТз Humidity: {humidity}%\nЁЯТи Wind: {wind} km/h",
        'weather_city_not_found': "тЭМ City '{city}' not found.",
        'weather_error': "тЭМ Weather error.",
        'translate_prompt_needed': "тЭУ /translate [lang] [text]",
        'translate_error': "тЭМ Translation error.",
        'calc_prompt_needed': "тЭУ /calc [expression]",
        'calc_result': "ЁЯзо <b>Result:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "тЭМ Calculation error.",
        'password_length_error': "тЭМ Password length 8-50.",
        'password_result': "ЁЯФС <b>Password:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "тЭМ Invalid length.",
        'random_result': "ЁЯО▓ Random {min}-{max}:\n\n<b>{result}</b>",
        'random_invalid_range': "тЭМ Invalid range.",
        'dice_result': "ЁЯО▓ {emoji} Rolled: <b>{result}</b>",
        'coin_result': "ЁЯкЩ {emoji} It's <b>{result}</b>",
        'coin_heads': "Heads", 'coin_tails': "Tails",
        'joke_title': "ЁЯШД <b>Joke:</b>\n\n",
        'quote_title': "ЁЯТн <b>Quote:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "ЁЯФм <b>Fact:</b>\n\n",
        'remind_prompt_needed': "тЭУ /remind [minutes] [text]",
        'remind_success': "тП░ Reminder set!\n\nЁЯУЭ {text}\nЁЯХР In {minutes} min",
        'remind_invalid_time': "тЭМ Invalid time.",
        'reminders_empty': "ЁЯУн No reminders.",
        'reminders_list_title': "тП░ <b>Reminders ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\nЁЯУЭ {text}\n\n",
        'reminder_alert': "тП░ <b>REMINDER</b>\n\nЁЯУЭ {text}",
        'grant_vip_prompt': "тЭУ /grant_vip [id] [duration]\n\nDurations: week, month, year, forever",
        'grant_vip_user_not_found': "тЭМ User/chat '{id}' not found.",
        'grant_vip_invalid_duration': "тЭМ Invalid duration.",
        'grant_vip_success': "тЬЕ VIP granted!\n\nЁЯЖФ <code>{id}</code>\nтП░ {duration_text}",
        'grant_vip_dm': "ЁЯОЙ VIP granted {duration_text}!",
        'duration_until': "until {date}",
        'duration_forever': "forever",
        'revoke_vip_prompt': "тЭУ /revoke_vip [id]",
        'revoke_vip_success': "тЬЕ VIP revoked for <code>{id}</code>.",
        'users_list_title': "ЁЯСе <b>USERS ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... and {count} more</i>",
        'broadcast_prompt': "тЭУ /broadcast [message]",
        'broadcast_started': "ЁЯУд Broadcasting...",
        'broadcast_finished': "тЬЕ Done!\n\nтЬЕ Success: {success}\nтЭМ Failed: {failed}",
        'broadcast_dm': "ЁЯУв <b>From creator:</b>\n\n{text}",
        'stats_admin_title': "ЁЯУК <b>STATISTICS</b>\n\n<b>ЁЯСе Users:</b> {users}\n<b>ЁЯТО VIPs:</b> {vips}\n\n<b>ЁЯУИ Activity:</b>\nтАв Messages: {msg_count}\nтАв Commands: {cmd_count}\nтАв AI: {ai_count}",
        'backup_success': "тЬЕ Backup created\n\nЁЯУЕ {date}",
        'backup_error': "тЭМ Backup error: {error}",
        'file_received': "ЁЯУе Loading file...",
        'file_analyzing': "ЁЯУД <b>File:</b> {filename}\n\nЁЯдЦ <b>Analysis:</b>\n\n{text}",
        'file_error': "тЭМ Error: {error}",
        'photo_analyzing': "ЁЯФН Analyzing...",
        'photo_result': "ЁЯУ╕ <b>Analysis:</b>\n\n{text}\n\nЁЯТО VIP",
        'photo_error': "тЭМ Photo error: {error}",
        'photo_no_caption': "ЁЯУ╕ Got image. What should I do with it?\n\nЁЯТб Tip: send a text with your question about this photo.",
        'voice_transcribing': "ЁЯОЩя╕П Transcribing...",
        'voice_result': "ЁЯУЭ <b>Transcription:</b>\n\n{text}",
        'voice_error': "тЭМ Voice error: {error}",
        'error_generic': "тЭМ Error: {error}",
        'section_not_found': "тЭМ Section not found.",
        'need_admin': "тЭМ Admin rights required.",
        'need_reply': "тЭМ Reply to a user's message.",
        'bot_need_admin': "тЭМ Bot must be admin.",
        'cant_self': "тЭМ Can't apply to yourself.",
        'cant_admin': "тЭМ Can't apply to admin.",
        'user_banned': "ЁЯЪл <b>{name}</b> banned.\n\nReason: {reason}",
        'user_unbanned': "тЬЕ User <code>{id}</code> unbanned.",
        'user_kicked': "ЁЯСв <b>{name}</b> kicked.",
        'user_muted': "ЁЯФЗ <b>{name}</b> muted for {minutes} min.",
        'user_unmuted': "ЁЯФК <b>{name}</b> unmuted.",
        'user_warned': "тЪая╕П <b>{name}</b> warned ({count}/3).\n\nReason: {reason}",
        'user_warned_ban': "ЁЯЪл <b>{name}</b> banned (3/3 warns).",
        'user_unwarned': "тЬЕ Warn removed from <b>{name}</b> ({count}/3).",
        'warns_list': "тЪая╕П <b>Warns for {name}:</b> {count}/3",
        'warns_empty': "тЬЕ <b>{name}</b> has no warns.",
        'welcome_set': "тЬЕ Welcome message set!\n\n{text}",
        'welcome_off': "тЬЕ Welcome disabled.",
        'rules_set': "тЬЕ Rules set!",
        'rules_text': "ЁЯУЬ <b>Chat rules:</b>\n\n{rules}",
        'rules_empty': "ЁЯУЬ No rules set.",
        'ai_enabled': "тЬЕ AI enabled in this chat.",
        'ai_disabled': "тЭМ AI disabled in this chat.",
        'chat_info': "тД╣я╕П <b>Chat Info</b>\n\nЁЯУЫ Title: {title}\nЁЯЖФ ID: <code>{id}</code>\nЁЯТО VIP: {vip_status}\nЁЯдЦ AI: {ai_status}\nЁЯСЛ Welcome: {welcome_status}\nЁЯУК Messages: {messages}",
        'top_users': "ЁЯПЖ <b>Top active:</b>\n\n",
        'top_users_item': "{medal} <b>{name}</b> - {count} messages\n",
        'top_empty': "ЁЯУн No stats yet.",
        'new_member_welcome': "ЁЯСЛ Welcome, <b>{name}</b>!",
        'group_help': "ЁЯСе Use /help and select 'Groups' section for moderation commands.",
    },
    'it': {
        'welcome': (
            "ЁЯдЦ <b>AI DISCO BOT</b>\n\n"
            "Ciao, {first_name}! Sono un bot basato su <b>Gemini 2.5</b>.\n\n"
            "<b>ЁЯОп Funzionalit├а:</b>\n"
            "ЁЯТм Chat AI con contesto (ricorda foto, voce, file)\n"
            "ЁЯУЭ Note e Impegni\n"
            "ЁЯМН Meteo e Ora\n"
            "ЁЯО▓ Intrattenimento\n"
            "ЁЯУО Analisi File (VIP)\n"
            "ЁЯФН Analisi Immagini (VIP)\n"
            "ЁЯЦ╝я╕П Generazione Immagini (VIP)\n"
            "ЁЯСе Moderazione gruppi\n\n"
            "<b>тЪб Comandi:</b>\n"
            "/help - Comandi\n"
            "/language - Lingua\n"
            "/vip - Stato VIP\n\n"
            "<b>ЁЯСитАНЁЯТ╗ Creatore:</b> @{creator}"
        ),
        'lang_changed': "тЬЕ Lingua: Italiano ЁЯЗоЁЯЗ╣",
        'lang_choose': "ЁЯМР Seleziona una lingua:",
        'main_keyboard': {
            'chat': "ЁЯТм Chat AI", 'notes': "ЁЯУЭ Note", 'weather': "ЁЯМН Meteo", 'time': "тП░ Ora",
            'games': "ЁЯО▓ Giochi", 'info': "тД╣я╕П Info", 'vip_menu': "ЁЯТО Menu VIP",
            'admin_panel': "ЁЯСС Pannello Admin", 'generate': "ЁЯЦ╝я╕П Genera"
        },
        'help_title': "ЁЯУЪ <b>Scegli una sezione:</b>",
        'help_back': "ЁЯФЩ Indietro",
        'help_sections': {
            'help_basic': "ЁЯПа Base", 'help_ai': "ЁЯТм AI", 'help_memory': "ЁЯза Memoria",
            'help_notes': "ЁЯУЭ Note", 'help_todo': "ЁЯУЛ Impegni", 'help_utils': "ЁЯМН Utilit├а",
            'help_games': "ЁЯО▓ Giochi", 'help_vip': "ЁЯТО VIP", 'help_admin': "ЁЯСС Admin",
            'help_groups': "ЁЯСе Gruppi"
        },
        'help_text': {
            'help_basic': "ЁЯПа <b>Comandi Base:</b>\n\nЁЯЪА /start\nЁЯУЦ /help\nтД╣я╕П /info\nЁЯУК /status\nЁЯСд /profile\nтП▒ /uptime\nЁЯЧгя╕П /language",
            'help_ai': "ЁЯТм <b>Comandi AI:</b>\n\nЁЯдЦ /ai [domanda]\nЁЯз╣ /clear\n\nЁЯТб Il bot ricorda il contesto!",
            'help_memory': "ЁЯза <b>Memoria:</b>\n\nЁЯТ╛ /memorysave [chiave] [valore]\nЁЯФН /memoryget [chiave]\nЁЯУЛ /memorylist\nЁЯЧС /memorydel [chiave]",
            'help_notes': "ЁЯУЭ <b>Note:</b>\n\nтЮХ /note [testo]\nЁЯУЛ /notes\nЁЯЧС /delnote [numero]",
            'help_todo': "ЁЯУЛ <b>Impegni:</b>\n\nтЮХ /todo add [testo]\nЁЯУЛ /todo list\nЁЯЧС /todo del [numero]",
            'help_utils': "ЁЯМН <b>Utilit├а:</b>\n\nЁЯХР /time [citt├а]\nтШАя╕П /weather [citt├а]\nЁЯМР /translate [lingua] [testo]\nЁЯзо /calc [expr]\nЁЯФС /password [lunghezza]",
            'help_games': "ЁЯО▓ <b>Giochi:</b>\n\nЁЯО▓ /random [min] [max]\nЁЯОп /dice\nЁЯкЩ /coin\nЁЯШД /joke\nЁЯТн /quote\nЁЯФм /fact",
            'help_vip': "ЁЯТО <b>Comandi VIP:</b>\n\nЁЯСС /vip\nЁЯЦ╝я╕П /generate [prompt]\nтП░ /remind [min] [testo]\nЁЯУЛ /reminders",
            'help_admin': "ЁЯСС <b>Comandi Creatore:</b>\n\nЁЯОБ /grant_vip [id] [durata]\nтЭМ /revoke_vip [id]\nЁЯСе /users\nЁЯУв /broadcast [testo]\nЁЯУИ /stats\nЁЯТ╛ /backup",
            'help_groups': "ЁЯСе <b>Comandi Gruppo:</b>\n\n<b>Moderazione:</b>\nЁЯЪл /ban\nтЬЕ /unban [id]\nЁЯСв /kick\nЁЯФЗ /mute [min]\nЁЯФК /unmute\nтЪая╕П /warn\nтЬЕ /unwarn\nЁЯУЛ /warns\n\n<b>Impostazioni:</b>\nЁЯСЛ /setwelcome [testo]\nЁЯЪл /welcomeoff\nЁЯУЬ /setrules [testo]\nЁЯУЦ /rules\nЁЯдЦ /setai [on/off]\nтД╣я╕П /chatinfo\nЁЯПЖ /top"
        },
        'menu': {
            'chat': "ЁЯдЦ <b>Chat AI</b>\n\nScrivi - rispondo!\nInvia foto o vocale - capisco!\n/clear - pulisci",
            'notes': "ЁЯУЭ <b>Note</b>", 'notes_create': "тЮХ Crea", 'notes_list': "ЁЯУЛ Lista",
            'weather': "ЁЯМН <b>Meteo</b>\n\n/weather [citt├а]",
            'time': "тП░ <b>Ora</b>\n\n/time [citt├а]",
            'games': "ЁЯО▓ <b>Giochi</b>", 'games_dice': "ЁЯО▓ Dado", 'games_coin': "ЁЯкЩ Moneta",
            'games_joke': "ЁЯШД Battuta", 'games_quote': "ЁЯТн Citazione", 'games_fact': "ЁЯФм Fatto",
            'vip': "ЁЯТО <b>Menu VIP</b>", 'vip_reminders': "тП░ Promemoria", 'vip_stats': "ЁЯУК Stats",
            'admin': "ЁЯСС <b>Pannello Admin</b>", 'admin_users': "ЁЯСе Utenti", 'admin_stats': "ЁЯУК Stats",
            'admin_broadcast': "ЁЯУв Broadcast",
            'generate': "ЁЯЦ╝я╕П <b>Generazione (VIP)</b>\n\n/generate [prompt]"
        },
        'info': "ЁЯдЦ <b>AI DISCO BOT v4.0</b>\n\n<b>Versione:</b> 4.0\n<b>AI:</b> Gemini 2.5 Flash\n<b>Creatore:</b> @Ernest_Kostevich\n\n<b>ЁЯТм Supporto:</b> @Ernest_Kostevich",
        'status': "ЁЯУК <b>STATO</b>\n\nЁЯСе Utenti: {users}\nЁЯТО VIP: {vips}\nЁЯСе Gruppi: {groups}\n\n<b>ЁЯУИ Attivit├а:</b>\nтАв Messaggi: {msg_count}\nтАв Comandi: {cmd_count}\nтАв AI: {ai_count}\n\n<b>тП▒ Uptime:</b> {days}g {hours}h\n\n<b>тЬЕ Stato:</b> Online\n<b>ЁЯЧДя╕П DB:</b> {db_status}",
        'profile': "ЁЯСд <b>{first_name}</b>\nЁЯЖФ <code>{user_id}</code>\n{username_line}\nЁЯУЕ {registered_date}\nЁЯУК Messaggi: {msg_count}\nЁЯОп Comandi: {cmd_count}\nЁЯУЭ Note: {notes_count}",
        'profile_vip': "\nЁЯТО VIP fino: {date}",
        'profile_vip_forever': "\nЁЯТО VIP: Illimitato тЩ╛я╕П",
        'uptime': "тП▒ <b>UPTIME</b>\n\nЁЯХР Avviato: {start_time}\nтП░ Attivo: {days}g {hours}h {minutes}m\n\nтЬЕ Online",
        'vip_status_active': "ЁЯТО <b>STATO VIP</b>\n\nтЬЕ Attivo!\n\n",
        'vip_status_until': "тП░ Fino: {date}\n\n",
        'vip_status_forever': "тП░ Illimitato тЩ╛я╕П\n\n",
        'vip_status_bonus': "<b>ЁЯОБ Vantaggi:</b>\nтАв тП░ Promemoria\nтАв ЁЯЦ╝я╕П Generazione\nтАв ЁЯФН Analisi immagini\nтАв ЁЯУО Analisi documenti",
        'vip_status_inactive': "ЁЯТО <b>STATO VIP</b>\n\nтЭМ Non VIP.\n\nContatta @Ernest_Kostevich",
        'vip_only': "ЁЯТО Solo VIP.\n\nContatta @Ernest_Kostevich",
        'admin_only': "тЭМ Solo creatore.",
        'gen_prompt_needed': "тЭУ /generate [prompt]",
        'gen_in_progress': "ЁЯОи Generando...",
        'gen_caption': "ЁЯЦ╝я╕П <b>{prompt}</b>\n\nЁЯТО VIP | Imagen 3",
        'gen_error': "тЭМ Errore generazione",
        'gen_error_api': "тЭМ Errore API: {error}",
        'ai_prompt_needed': "тЭУ /ai [domanda]",
        'ai_error': "ЁЯШФ Errore AI, riprova.",
        'clear_context': "ЁЯз╣ Contesto pulito!",
        'note_prompt_needed': "тЭУ /note [testo]",
        'note_saved': "тЬЕ Nota #{num} salvata!\n\nЁЯУЭ {text}",
        'notes_empty': "ЁЯУн Nessuna nota.",
        'notes_list_title': "ЁЯУЭ <b>Note ({count}):</b>\n\n",
        'notes_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'delnote_prompt_needed': "тЭУ /delnote [numero]",
        'delnote_success': "тЬЕ Nota #{num} eliminata:\n\nЁЯУЭ {text}",
        'delnote_not_found': "тЭМ Nota #{num} non trovata.",
        'delnote_invalid_num': "тЭМ Numero non valido.",
        'todo_prompt_needed': "тЭУ /todo add [testo] | list | del [numero]",
        'todo_add_prompt_needed': "тЭУ /todo add [testo]",
        'todo_saved': "тЬЕ Impegno #{num} aggiunto!\n\nЁЯУЛ {text}",
        'todo_empty': "ЁЯУн Nessun impegno.",
        'todo_list_title': "ЁЯУЛ <b>Impegni ({count}):</b>\n\n",
        'todo_list_item': "<b>#{i}</b> ({date})\n{text}\n\n",
        'todo_del_prompt_needed': "тЭУ /todo del [numero]",
        'todo_del_success': "тЬЕ Impegno #{num} eliminato:\n\nЁЯУЛ {text}",
        'todo_del_not_found': "тЭМ Impegno #{num} non trovato.",
        'todo_del_invalid_num': "тЭМ Numero non valido.",
        'time_result': "тП░ <b>{city}</b>\n\nЁЯХР Ora: {time}\nЁЯУЕ Data: {date}\nЁЯМН Fuso: {tz}",
        'time_city_not_found': "тЭМ Citt├а '{city}' non trovata.",
        'weather_result': "ЁЯМН <b>{city}</b>\n\nЁЯМб Temp: {temp}┬░C\nЁЯдФ Percepita: {feels}┬░C\nтШБя╕П {desc}\nЁЯТз Umidit├а: {humidity}%\nЁЯТи Vento: {wind} km/h",
        'weather_city_not_found': "тЭМ Citt├а '{city}' non trovata.",
        'weather_error': "тЭМ Errore meteo.",
        'translate_prompt_needed': "тЭУ /translate [lingua] [testo]",
        'translate_error': "тЭМ Errore traduzione.",
        'calc_prompt_needed': "тЭУ /calc [espressione]",
        'calc_result': "ЁЯзо <b>Risultato:</b>\n\n{expr} = <b>{result}</b>",
        'calc_error': "тЭМ Errore calcolo.",
        'password_length_error': "тЭМ Lunghezza 8-50.",
        'password_result': "ЁЯФС <b>Password:</b>\n\n<code>{password}</code>",
        'password_invalid_length': "тЭМ Lunghezza non valida.",
        'random_result': "ЁЯО▓ Casuale {min}-{max}:\n\n<b>{result}</b>",
        'random_invalid_range': "тЭМ Range non valido.",
        'dice_result': "ЁЯО▓ {emoji} Uscito: <b>{result}</b>",
        'coin_result': "ЁЯкЩ {emoji} ├И uscito: <b>{result}</b>",
        'coin_heads': "Testa", 'coin_tails': "Croce",
        'joke_title': "ЁЯШД <b>Battuta:</b>\n\n",
        'quote_title': "ЁЯТн <b>Citazione:</b>\n\n<i>",
        'quote_title_end': "</i>",
        'fact_title': "ЁЯФм <b>Fatto:</b>\n\n",
        'remind_prompt_needed': "тЭУ /remind [minuti] [testo]",
        'remind_success': "тП░ Promemoria impostato!\n\nЁЯУЭ {text}\nЁЯХР Tra {minutes} min",
        'remind_invalid_time': "тЭМ Tempo non valido.",
        'reminders_empty': "ЁЯУн Nessun promemoria.",
        'reminders_list_title': "тП░ <b>Promemoria ({count}):</b>\n\n",
        'reminders_list_item': "<b>#{i}</b> ({time})\nЁЯУЭ {text}\n\n",
        'reminder_alert': "тП░ <b>PROMEMORIA</b>\n\nЁЯУЭ {text}",
        'grant_vip_prompt': "тЭУ /grant_vip [id] [durata]",
        'grant_vip_user_not_found': "тЭМ Utente/chat '{id}' non trovato.",
        'grant_vip_invalid_duration': "тЭМ Durata non valida.",
        'grant_vip_success': "тЬЕ VIP concesso!\n\nЁЯЖФ <code>{id}</code>\nтП░ {duration_text}",
        'grant_vip_dm': "ЁЯОЙ VIP concesso {duration_text}!",
        'duration_until': "fino {date}",
        'duration_forever': "per sempre",
        'revoke_vip_prompt': "тЭУ /revoke_vip [id]",
        'revoke_vip_success': "тЬЕ VIP revocato per <code>{id}</code>.",
        'users_list_title': "ЁЯСе <b>UTENTI ({count}):</b>\n\n",
        'users_list_item': "{vip_badge} <code>{id}</code> - {name} @{username}\n",
        'users_list_more': "\n<i>... e altri {count}</i>",
        'broadcast_prompt': "тЭУ /broadcast [messaggio]",
        'broadcast_started': "ЁЯУд Invio...",
        'broadcast_finished': "тЬЕ Fatto!\n\nтЬЕ Successo: {success}\nтЭМ Falliti: {failed}",
        'broadcast_dm': "ЁЯУв <b>Dal creatore:</b>\n\n{text}",
        'stats_admin_title': "ЁЯУК <b>STATISTICHE</b>\n\n<b>ЁЯСе Utenti:</b> {users}\n<b>ЁЯТО VIP:</b> {vips}\n\n<b>ЁЯУИ Attivit├а:</b>\nтАв Messaggi: {msg_count}\nтАв Comandi: {cmd_count}\nтАв AI: {ai_count}",
        'backup_success': "тЬЕ Backup creato\n\nЁЯУЕ {date}",
        'backup_error': "тЭМ Errore backup: {error}",
        'file_received': "ЁЯУе Caricando...",
        'file_analyzing': "ЁЯУД <b>File:</b> {filename}\n\nЁЯдЦ <b>Analisi:</b>\n\n{text}",
        'file_error': "тЭМ Errore: {error}",
        'photo_analyzing': "ЁЯФН Analizzando...",
        'photo_result': "ЁЯУ╕ <b>Analisi:</b>\n\n{text}\n\nЁЯТО VIP",
        'photo_error': "тЭМ Errore foto: {error}",
        'photo_no_caption': "ЁЯУ╕ Foto ricevuta. Cosa devo fare?\n\nЁЯТб Suggerimento: invia un testo con la tua domanda.",
        'voice_transcribing': "ЁЯОЩя╕П Trascrivendo...",
        'voice_result': "ЁЯУЭ <b>Trascrizione:</b>\n\n{text}",
        'voice_error': "тЭМ Errore voce: {error}",
        'error_generic': "тЭМ Errore: {error}",
        'section_not_found': "тЭМ Sezione non trovata.",
        'need_admin': "тЭМ Servono diritti admin.",
        'need_reply': "тЭМ Rispondi a un messaggio.",
        'bot_need_admin': "тЭМ Il bot deve essere admin.",
        'cant_self': "тЭМ Non puoi applicarlo a te stesso.",
        'cant_admin': "тЭМ Non puoi applicarlo a un admin.",
        'user_banned': "ЁЯЪл <b>{name}</b> bannato.\n\nMotivo: {reason}",
        'user_unbanned': "тЬЕ Utente <code>{id}</code> sbannato.",
        'user_kicked': "ЁЯСв <b>{name}</b> espulso.",
        'user_muted': "ЁЯФЗ <b>{name}</b> mutato per {minutes} min.",
        'user_unmuted': "ЁЯФК <b>{name}</b> smutato.",
        'user_warned': "тЪая╕П <b>{name}</b> avvisato ({count}/3).\n\nMotivo: {reason}",
        'user_warned_ban': "ЁЯЪл <b>{name}</b> bannato (3/3 avvisi).",
        'user_unwarned': "тЬЕ Avviso rimosso da <b>{name}</b> ({count}/3).",
        'warns_list': "тЪая╕П <b>Avvisi {name}:</b> {count}/3",
        'warns_empty': "тЬЕ <b>{name}</b> non ha avvisi.",
        'welcome_set': "тЬЕ Benvenuto impostato!\n\n{text}",
        'welcome_off': "тЬЕ Benvenuto disabilitato.",
        'rules_set': "тЬЕ Regole impostate!",
        'rules_text': "ЁЯУЬ <b>Regole chat:</b>\n\n{rules}",
        'rules_empty': "ЁЯУЬ Nessuna regola.",
        'ai_enabled': "тЬЕ AI abilitato.",
        'ai_disabled': "тЭМ AI disabilitato.",
        'chat_info': "тД╣я╕П <b>Info Chat</b>\n\nЁЯУЫ Titolo: {title}\nЁЯЖФ ID: <code>{id}</code>\nЁЯТО VIP: {vip_status}\nЁЯдЦ AI: {ai_status}\nЁЯСЛ Benvenuto: {welcome_status}\nЁЯУК Messaggi: {messages}",
        'top_users': "ЁЯПЖ <b>Top attivi:</b>\n\n",
        'top_users_item': "{medal} <b>{name}</b> - {count} messaggi\n",
        'top_empty': "ЁЯУн Nessuna statistica.",
        'new_member_welcome': "ЁЯСЛ Benvenuto, <b>{name}</b>!",
        'group_help': "ЁЯСе Usa /help e seleziona 'Gruppi' per i comandi di moderazione.",
    }
}


# ============================================
# LOCALIZATION HELPERS
# ============================================

def get_lang(user_id: int) -> str:
    """Get user language, default 'ru'"""
    user = storage.get_user(user_id)
    return user.get('language', 'ru')


def get_text(key: str, lang: str, **kwargs: Any) -> str:
    """Get localized text by key"""
    if lang not in localization_strings:
        lang = 'ru'
    
    try:
        keys = key.split('.')
        text_template = localization_strings[lang]
        for k in keys:
            text_template = text_template[k]
        
        if kwargs:
            return text_template.format(**kwargs)
        return text_template
    except KeyError:
        try:
            fallback_lang = 'ru' if lang != 'ru' else 'en'
            text_template = localization_strings[fallback_lang]
            for k in keys:
                text_template = text_template[k]
            if kwargs:
                return text_template.format(**kwargs)
            return text_template
        except KeyError:
            logger.warning(f"Localization key '{key}' not found")
            return key


# Button map for menu detection
menu_button_map = {}
for lang in localization_strings:
    for btn_key in ['chat', 'notes', 'weather', 'time', 'games', 'info', 'vip_menu', 'admin_panel', 'generate']:
        if btn_key not in menu_button_map:
            menu_button_map[btn_key] = []
        try:
            menu_button_map[btn_key].append(localization_strings[lang]['main_keyboard'][btn_key])
        except:
            pass


# ============================================
# DATA STORAGE CLASS
# ============================================

class DataStorage:
    def __init__(self):
        self.users_file = 'users.json'
        self.stats_file = 'statistics.json'
        self.unified_contexts: Dict[int, UnifiedContext] = {}
        self.username_to_id = {}
        
        if not engine:
            self.users = self._load_json(self.users_file, {})
            self.stats = self._load_json(self.stats_file, {
                'total_messages': 0, 'total_commands': 0, 
                'ai_requests': 0, 'start_date': datetime.now().isoformat()
            })
            self._update_username_mapping()
        else:
            self.users = {}
            self.stats = self._get_stats_from_db()
    
    def _load_json(self, filename: str, default: Any) -> Any:
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {int(k) if k.lstrip('-').isdigit() else k: v for k, v in data.items()}
            return default
        except Exception as e:
            logger.warning(f"Error loading {filename}: {e}")
            return default
    
    def _save_json(self, filename: str, data: Any):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error saving {filename}: {e}")
    
    def _update_username_mapping(self):
        self.username_to_id = {}
        for user_id, user_data in self.users.items():
            username = user_data.get('username')
            if username:
                self.username_to_id[username.lower()] = user_id
    
    def _get_stats_from_db(self) -> Dict:
        if not engine:
            return {}
        session = Session()
        try:
            stat = session.query(Statistics).filter_by(key='global').first()
            return stat.value if stat else {
                'total_messages': 0, 'total_commands': 0, 
                'ai_requests': 0, 'start_date': datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"Error loading stats: {e}")
            return {'total_messages': 0, 'total_commands': 0, 'ai_requests': 0}
        finally:
            session.close()
    
    def save_stats(self):
        if engine:
            session = Session()
            try:
                session.merge(Statistics(key='global', value=self.stats, updated_at=datetime.now()))
                session.commit()
            except Exception as e:
                logger.warning(f"Error saving stats: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            self._save_json(self.stats_file, self.stats)
    
    # ============================================
    # USER METHODS
    # ============================================
    
    def get_user_id_by_identifier(self, identifier: str) -> Optional[int]:
        """Get user/chat ID by username or ID string"""
        identifier = identifier.strip()
        if identifier.startswith('@'):
            identifier = identifier[1:]
        
        # Support negative IDs for groups
        if identifier.lstrip('-').isdigit():
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
        """Get user data"""
        if engine:
            session = Session()
            try:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    user = User(id=user_id, language='ru')
                    session.add(user)
                    session.commit()
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
                    'language': user.language or 'ru'
                }
            except Exception as e:
                logger.error(f"Error get_user ({user_id}): {e}")
                return {'id': user_id, 'language': 'ru'}
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
                self._save_json(self.users_file, self.users)
            return self.users[user_id]
    
    def update_user(self, user_id: int, data: Dict):
        """Update user data"""
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
                logger.warning(f"Error updating user {user_id}: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            user = self.get_user(user_id)
            user.update(data)
            user['last_active'] = datetime.now().isoformat()
            self._save_json(self.users_file, self.users)
            self._update_username_mapping()
    
    def is_vip(self, user_id: int) -> bool:
        """Check if user has VIP status"""
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
    
    def get_all_users(self) -> Dict:
        """Get all users"""
        if engine:
            session = Session()
            try:
                users = session.query(User).all()
                return {u.id: {
                    'id': u.id, 'username': u.username, 
                    'first_name': u.first_name, 'vip': u.vip, 
                    'language': u.language
                } for u in users}
            finally:
                session.close()
        return self.users
    
    # ============================================
    # GROUP CHAT METHODS
    # ============================================
    
    def get_chat(self, chat_id: int) -> Dict:
        """Get group chat settings"""
        if engine:
            session = Session()
            try:
                chat = session.query(GroupChat).filter_by(id=chat_id).first()
                if not chat:
                    chat = GroupChat(id=chat_id)
                    session.add(chat)
                    session.commit()
                    chat = session.query(GroupChat).filter_by(id=chat_id).first()
                
                return {
                    'id': chat.id,
                    'title': chat.title or '',
                    'vip': chat.vip,
                    'vip_until': chat.vip_until.isoformat() if chat.vip_until else None,
                    'welcome_text': chat.welcome_text or "╨Ф╨╛╨▒╤А╨╛ ╨┐╨╛╨╢╨░╨╗╨╛╨▓╨░╤В╤М, {name}! ЁЯСЛ",
                    'welcome_enabled': chat.welcome_enabled,
                    'rules': chat.rules or '',
                    'ai_enabled': chat.ai_enabled,
                    'warns': chat.warns or {},
                    'messages_count': chat.messages_count or 0,
                    'top_users': chat.top_users or {}
                }
            except Exception as e:
                logger.error(f"Error get_chat ({chat_id}): {e}")
                return {'id': chat_id, 'ai_enabled': True, 'vip': False}
            finally:
                session.close()
        else:
            # JSON fallback
            key = f"chat_{chat_id}"
            if key not in self.users:
                self.users[key] = {
                    'id': chat_id, 'title': '', 'vip': False, 'vip_until': None,
                    'welcome_text': "╨Ф╨╛╨▒╤А╨╛ ╨┐╨╛╨╢╨░╨╗╨╛╨▓╨░╤В╤М, {name}! ЁЯСЛ",
                    'welcome_enabled': True, 'rules': '', 'ai_enabled': True,
                    'warns': {}, 'messages_count': 0, 'top_users': {}
                }
                self._save_json(self.users_file, self.users)
            return self.users[key]
    
    def update_chat(self, chat_id: int, data: Dict):
        """Update group chat settings"""
        if engine:
            session = Session()
            try:
                chat = session.query(GroupChat).filter_by(id=chat_id).first()
                if not chat:
                    chat = GroupChat(id=chat_id)
                    session.add(chat)
                
                for key, value in data.items():
                    if key == 'vip_until' and value:
                        value = datetime.fromisoformat(value) if isinstance(value, str) else value
                    setattr(chat, key, value)
                
                session.commit()
            except Exception as e:
                logger.warning(f"Error updating chat {chat_id}: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            chat = self.get_chat(chat_id)
            chat.update(data)
            self._save_json(self.users_file, self.users)
    
    def is_chat_vip(self, chat_id: int) -> bool:
        """Check if chat has VIP status"""
        chat = self.get_chat(chat_id)
        if not chat.get('vip', False):
            return False
        
        vip_until = chat.get('vip_until')
        if vip_until is None:
            return True
        
        try:
            vip_until_dt = datetime.fromisoformat(vip_until)
            if datetime.now() > vip_until_dt:
                self.update_chat(chat_id, {'vip': False, 'vip_until': None})
                return False
            return True
        except:
            return True
    
    def add_chat_message(self, chat_id: int, user_id: int):
        """Increment message counter for chat statistics"""
        chat = self.get_chat(chat_id)
        top_users = chat.get('top_users', {})
        user_id_str = str(user_id)
        top_users[user_id_str] = top_users.get(user_id_str, 0) + 1
        self.update_chat(chat_id, {
            'messages_count': chat.get('messages_count', 0) + 1,
            'top_users': top_users
        })
    
    def get_all_chats(self) -> Dict:
        """Get all group chats"""
        if engine:
            session = Session()
            try:
                chats = session.query(GroupChat).all()
                return {c.id: {'id': c.id, 'title': c.title, 'vip': c.vip} for c in chats}
            finally:
                session.close()
        return {k: v for k, v in self.users.items() if str(k).startswith('chat_')}
    
    # ============================================
    # UNIFIED CONTEXT METHODS
    # ============================================
    
    def get_context(self, user_id: int) -> UnifiedContext:
        """Get or create unified context for user"""
        if user_id not in self.unified_contexts:
            self.unified_contexts[user_id] = UnifiedContext()
        return self.unified_contexts[user_id]
    
    def clear_context(self, user_id: int):
        """Clear user's context"""
        if user_id in self.unified_contexts:
            self.unified_contexts[user_id].clear()
    
    # ============================================
    # CHAT HISTORY
    # ============================================
    
    def save_chat_history(self, user_id: int, message: str, response: str):
        """Save chat to history"""
        if not engine:
            return
        
        session = Session()
        try:
            chat = ChatHistory(user_id=user_id, message=message[:1000], response=response[:1000])
            session.add(chat)
            session.commit()
        except Exception as e:
            logger.warning(f"Error saving chat history: {e}")
        finally:
            session.close()


# Initialize storage
storage = DataStorage()


# ============================================
# HELPER FUNCTIONS
# ============================================

def identify_creator(user):
    """Identify creator by username"""
    global CREATOR_ID
    if user.username == CREATOR_USERNAME and CREATOR_ID is None:
        CREATOR_ID = user.id
        logger.info(f"Creator identified: {user.id}")


def is_creator(user_id: int) -> bool:
    """Check if user is creator"""
    return user_id == CREATOR_ID


async def is_user_admin(chat_id: int, user_id: int, bot) -> bool:
    """Check if user is admin in chat"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False


async def is_bot_admin(chat_id: int, bot) -> bool:
    """Check if bot is admin in chat"""
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False


def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Get main keyboard for user"""
    lang = get_lang(user_id)
    keyboard = [
        [KeyboardButton(get_text('main_keyboard.chat', lang)), KeyboardButton(get_text('main_keyboard.notes', lang))],
        [KeyboardButton(get_text('main_keyboard.weather', lang)), KeyboardButton(get_text('main_keyboard.time', lang))],
        [KeyboardButton(get_text('main_keyboard.games', lang)), KeyboardButton(get_text('main_keyboard.info', lang))]
    ]
    
    if storage.is_vip(user_id):
        keyboard.insert(0, [
            KeyboardButton(get_text('main_keyboard.vip_menu', lang)), 
            KeyboardButton(get_text('main_keyboard.generate', lang))
        ])
    
    if is_creator(user_id):
        keyboard.append([KeyboardButton(get_text('main_keyboard.admin_panel', lang))])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_help_keyboard(lang: str, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Get help keyboard"""
    keyboard = [
        [InlineKeyboardButton(get_text('help_sections.help_basic', lang), callback_data="help_basic")],
        [InlineKeyboardButton(get_text('help_sections.help_ai', lang), callback_data="help_ai")],
        [InlineKeyboardButton(get_text('help_sections.help_memory', lang), callback_data="help_memory")],
        [InlineKeyboardButton(get_text('help_sections.help_notes', lang), callback_data="help_notes")],
        [InlineKeyboardButton(get_text('help_sections.help_todo', lang), callback_data="help_todo")],
        [InlineKeyboardButton(get_text('help_sections.help_utils', lang), callback_data="help_utils")],
        [InlineKeyboardButton(get_text('help_sections.help_games', lang), callback_data="help_games")],
        [InlineKeyboardButton(get_text('help_sections.help_vip', lang), callback_data="help_vip")],
        [InlineKeyboardButton(get_text('help_sections.help_groups', lang), callback_data="help_groups")],
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton(get_text('help_sections.help_admin', lang), callback_data="help_admin")])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================
# AI FUNCTIONS
# ============================================

async def generate_with_context(user_id: int, new_content: str = None, image_data: bytes = None) -> str:
    """Generate response using unified context"""
    context = storage.get_context(user_id)
    
    # Add new content to context
    if image_data and new_content:
        context.add_user_image(image_data, new_content)
    elif image_data:
        # Check for pending context
        pending = context.get_pending_image()
        if pending:
            # Previous image, now with text
            context.add_user_image(pending, new_content or "╨Ю╨┐╨╕╤И╨╕ ╤Н╤В╨╛ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡")
        else:
            context.set_pending_image(image_data)
            return None  # Signal to ask user
    elif new_content:
        # Check if there's a pending image
        pending = context.get_pending_image()
        if pending:
            context.add_user_image(pending, new_content)
        else:
            context.add_user_text(new_content)
    
    try:
        # Build content for Gemini
        contents = context.build_gemini_content()
        
        if not contents:
            return "╨Я╨╛╨╢╨░╨╗╤Г╨╣╤Б╤В╨░, ╨╜╨░╨┐╨╕╤И╨╕╤В╨╡ ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡."
        
        # Generate response
        response = model.generate_content(contents)
        response_text = response.text
        
        # Add response to context
        context.add_assistant_response(response_text)
        
        # Update stats
        storage.stats['ai_requests'] = storage.stats.get('ai_requests', 0) + 1
        storage.save_stats()
        
        # Save to history
        storage.save_chat_history(user_id, new_content or "[image/voice]", response_text)
        
        return response_text
        
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return f"╨Ю╤И╨╕╨▒╨║╨░ AI: {str(e)}"


async def generate_image_imagen(prompt: str) -> Optional[bytes]:
    """Generate image with Imagen 3"""
    if not GEMINI_API_KEY:
        return None
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
    
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("predictions") and result["predictions"][0].get("bytesBase64Encoded"):
                        return base64.b64decode(result["predictions"][0]["bytesBase64Encoded"])
                else:
                    error_text = await response.text()
                    logger.error(f"Imagen API error {response.status}: {error_text}")
    except Exception as e:
        logger.error(f"Imagen API exception: {e}")
    
    return None


async def transcribe_audio_with_gemini(audio_bytes: bytes) -> str:
    """Transcribe audio with Gemini"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        uploaded_file = genai.upload_file(path=temp_path, mime_type="audio/ogg")
        response = model.generate_content(["╨в╤А╨░╨╜╤Б╨║╤А╨╕╨▒╨╕╤А╤Г╨╣ ╤Н╤В╨╛ ╨░╤Г╨┤╨╕╨╛:", uploaded_file])
        
        os.remove(temp_path)
        return response.text
    except Exception as e:
        logger.warning(f"Transcription error: {e}")
        return f"╨Ю╤И╨╕╨▒╨║╨░ ╤В╤А╨░╨╜╤Б╨║╤А╨╕╨┐╤Ж╨╕╨╕: {str(e)}"


async def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    """Extract text from document"""
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
        logger.warning(f"Text extraction error: {e}")
        return f"╨Ю╤И╨╕╨▒╨║╨░: {str(e)}"


async def send_long_message(message: Message, text: str):
    """Send long message in chunks"""
    if len(text) <= 4000:
        await message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.3)


# ============================================
# COMMAND HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    identify_creator(user)
    
    user_data = storage.get_user(user.id)
    storage.update_user(user.id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'commands_count': user_data.get('commands_count', 0) + 1
    })
    
    lang = get_lang(user.id)
    welcome_text = get_text('welcome', lang, first_name=user.first_name, creator=CREATOR_USERNAME)
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=get_main_keyboard(user.id)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    identify_creator(update.effective_user)
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {'commands_count': user_data.get('commands_count', 0) + 1})
    
    await update.message.reply_text(
        get_text('help_title', lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_help_keyboard(lang, is_creator(user_id))
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    keyboard = [
        [InlineKeyboardButton("╨а╤Г╤Б╤Б╨║╨╕╨╣ ЁЯЗ╖ЁЯЗ║", callback_data="set_lang:ru")],
        [InlineKeyboardButton("English ЁЯЗмЁЯЗз", callback_data="set_lang:en")],
        [InlineKeyboardButton("Italiano ЁЯЗоЁЯЗ╣", callback_data="set_lang:it")],
    ]
    
    await update.message.reply_text(
        get_text('lang_choose', lang), 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /info command"""
    lang = get_lang(update.effective_user.id)
    await update.message.reply_text(get_text('info', lang), parse_mode=ParseMode.HTML)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    lang = get_lang(update.effective_user.id)
    stats = storage.stats
    all_users = storage.get_all_users()
    all_chats = storage.get_all_chats()
    uptime = datetime.now() - BOT_START_TIME
    db_status = 'PostgreSQL тЬУ' if engine else 'JSON'
    
    await update.message.reply_text(
        get_text('status', lang,
            users=len(all_users),
            vips=sum(1 for u in all_users.values() if u.get('vip', False)),
            groups=len(all_chats),
            msg_count=stats.get('total_messages', 0),
            cmd_count=stats.get('total_commands', 0),
            ai_count=stats.get('ai_requests', 0),
            days=uptime.days,
            hours=uptime.seconds // 3600,
            db_status=db_status
        ), 
        parse_mode=ParseMode.HTML
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    user = storage.get_user(user_id)
    
    username_line = f"ЁЯУ▒ @{user['username']}" if user.get('username') else ""
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
    """Handle /uptime command"""
    lang = get_lang(update.effective_user.id)
    uptime = datetime.now() - BOT_START_TIME
    
    await update.message.reply_text(
        get_text('uptime', lang,
            start_time=BOT_START_TIME.strftime('%d.%m.%Y %H:%M:%S'),
            days=uptime.days,
            hours=uptime.seconds // 3600,
            minutes=(uptime.seconds % 3600) // 60
        ), 
        parse_mode=ParseMode.HTML
    )


async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vip command"""
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


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ai command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not context.args:
        await update.message.reply_text(get_text('ai_prompt_needed', lang))
        return
    
    text = ' '.join(context.args)
    await update.message.chat.send_action('typing')
    
    response = await generate_with_context(user_id, text)
    if response:
        await send_long_message(update.message, response)
    else:
        await update.message.reply_text(get_text('ai_error', lang))


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    storage.clear_context(user_id)
    await update.message.reply_text(get_text('clear_context', lang))


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /generate command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    chat_id = update.message.chat.id
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP (user or chat)
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    if not context.args:
        await update.message.reply_text(get_text('gen_prompt_needed', lang))
        return
    
    prompt = ' '.join(context.args)
    await update.message.reply_text(get_text('gen_in_progress', lang))
    
    try:
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
        logger.warning(f"Generate error: {e}")
        await update.message.reply_text(get_text('gen_error_api', lang, error=str(e)))


# ============================================
# NOTES & TODO HANDLERS
# ============================================

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /note command"""
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
    """Handle /notes command"""
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
        notes_text += get_text('notes_list_item', lang, i=i, date=created.strftime('%d.%m'), text=note['text'])
    
    await update.message.reply_text(notes_text, parse_mode=ParseMode.HTML)


async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /delnote command"""
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


async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /todo command"""
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


# ============================================
# MEMORY HANDLERS
# ============================================

async def memory_save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text("тЭУ /memorysave [╨║╨╗╤О╤З] [╨╖╨╜╨░╤З╨╡╨╜╨╕╨╡]")
        return
    
    key = context.args[0]
    value = ' '.join(context.args[1:])
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    memory[key] = value
    storage.update_user(user_id, {'memory': memory})
    
    await update.message.reply_text(f"тЬЕ ╨б╨╛╤Е╤А╨░╨╜╨╡╨╜╨╛:\nЁЯФС <b>{key}</b> = <code>{value}</code>", parse_mode=ParseMode.HTML)


async def memory_get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("тЭУ /memoryget [╨║╨╗╤О╤З]")
        return
    
    key = context.args[0]
    user = storage.get_user(user_id)
    
    if key in user.get('memory', {}):
        await update.message.reply_text(f"ЁЯФН <b>{key}</b> = <code>{user['memory'][key]}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"тЭМ ╨Ъ╨╗╤О╤З '{key}' ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.")


async def memory_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    
    if not memory:
        await update.message.reply_text("ЁЯУн ╨Я╨░╨╝╤П╤В╤М ╨┐╤Г╤Б╤В╨░.")
        return
    
    memory_text = "ЁЯза <b>╨Я╨░╨╝╤П╤В╤М:</b>\n\n"
    for key, value in memory.items():
        memory_text += f"ЁЯФС <b>{key}</b>: <code>{value}</code>\n"
    
    await update.message.reply_text(memory_text, parse_mode=ParseMode.HTML)


async def memory_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("тЭУ /memorydel [╨║╨╗╤О╤З]")
        return
    
    key = context.args[0]
    user = storage.get_user(user_id)
    memory = user.get('memory', {})
    
    if key in memory:
        del memory[key]
        storage.update_user(user_id, {'memory': memory})
        await update.message.reply_text(f"тЬЕ ╨Ъ╨╗╤О╤З '{key}' ╤Г╨┤╨░╨╗╤С╨╜.")
    else:
        await update.message.reply_text(f"тЭМ ╨Ъ╨╗╤О╤З '{key}' ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜.")


# ============================================
# UTILITY HANDLERS
# ============================================

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /time command"""
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    
    timezones = {
        'moscow': 'Europe/Moscow', '╨╝╨╛╤Б╨║╨▓╨░': 'Europe/Moscow',
        'london': 'Europe/London', '╨╗╨╛╨╜╨┤╨╛╨╜': 'Europe/London',
        'new york': 'America/New_York', '╨╜╤М╤О-╨╣╨╛╤А╨║': 'America/New_York',
        'tokyo': 'Asia/Tokyo', '╤В╨╛╨║╨╕╨╛': 'Asia/Tokyo',
        'paris': 'Europe/Paris', '╨┐╨░╤А╨╕╨╢': 'Europe/Paris',
        'berlin': 'Europe/Berlin', '╨▒╨╡╤А╨╗╨╕╨╜': 'Europe/Berlin',
        'dubai': 'Asia/Dubai', '╨┤╤Г╨▒╨░╨╣': 'Asia/Dubai',
        'sydney': 'Australia/Sydney', '╤Б╨╕╨┤╨╜╨╡╨╣': 'Australia/Sydney',
        'los angeles': 'America/Los_Angeles',
        'rome': 'Europe/Rome', '╤А╨╕╨╝': 'Europe/Rome', 'roma': 'Europe/Rome'
    }
    
    tz_name = timezones.get(city.lower())
    
    if not tz_name:
        matching_tz = [tz for tz in pytz.all_timezones if city.lower() in tz.lower()]
        tz_name = matching_tz[0] if matching_tz else 'Europe/Moscow'
    
    try:
        tz = pytz.timezone(tz_name)
        current_time = datetime.now(tz)
        await update.message.reply_text(
            get_text('time_result', lang,
                city=city.title(),
                time=current_time.strftime('%H:%M:%S'),
                date=current_time.strftime('%d.%m.%Y'),
                tz=tz_name
            ), 
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Time error: {e}")
        await update.message.reply_text(get_text('time_city_not_found', lang, city=city))


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /weather command"""
    lang = get_lang(update.effective_user.id)
    city = ' '.join(context.args) if context.args else 'Moscow'
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{urlquote(city)}?format=j1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data['current_condition'][0]
                    
                    await update.message.reply_text(
                        get_text('weather_result', lang,
                            city=city.title(),
                            temp=current['temp_C'],
                            feels=current['FeelsLikeC'],
                            desc=current['weatherDesc'][0]['value'],
                            humidity=current['humidity'],
                            wind=current['windspeedKmph']
                        ), 
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await update.message.reply_text(get_text('weather_city_not_found', lang, city=city))
    except Exception as e:
        logger.warning(f"Weather error: {e}")
        await update.message.reply_text(get_text('weather_error', lang))


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /translate command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if len(context.args) < 2:
        await update.message.reply_text(get_text('translate_prompt_needed', lang))
        return
    
    target_lang = context.args[0]
    text_to_translate = ' '.join(context.args[1:])
    
    try:
        response = await generate_with_context(user_id, f"╨Я╨╡╤А╨╡╨▓╨╡╨┤╨╕ ╨╜╨░ {target_lang}: {text_to_translate}")
        await send_long_message(update.message, response)
    except Exception as e:
        logger.warning(f"Translation error: {e}")
        await update.message.reply_text(get_text('translate_error', lang))


async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /calc command"""
    lang = get_lang(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text(get_text('calc_prompt_needed', lang))
        return
    
    expression = ' '.join(context.args)
    allowed_chars = "0123456789.+-*/() "
    
    if not all(char in allowed_chars for char in expression):
        await update.message.reply_text(get_text('calc_error', lang))
        return
    
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        await update.message.reply_text(
            get_text('calc_result', lang, expr=expression, result=result), 
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await update.message.reply_text(get_text('calc_error', lang))


async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /password command"""
    lang = get_lang(update.effective_user.id)
    
    try:
        length = 12 if not context.args else int(context.args[0])
        if length < 8 or length > 50:
            await update.message.reply_text(get_text('password_length_error', lang))
            return
        
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*_-+='
        password = ''.join(random.choice(chars) for _ in range(length))
        await update.message.reply_text(get_text('password_result', lang, password=password), parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(get_text('password_invalid_length', lang))


# ============================================
# GAMES HANDLERS
# ============================================

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    try:
        min_val = int(context.args[0]) if len(context.args) >= 1 else 1
        max_val = int(context.args[1]) if len(context.args) >= 2 else 100
        result = random.randint(min_val, max_val)
        await update.message.reply_text(
            get_text('random_result', lang, min=min_val, max=max_val, result=result), 
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text(get_text('random_invalid_range', lang))


async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    result = random.randint(1, 6)
    dice_emoji = ['тЪА', 'тЪБ', 'тЪВ', 'тЪГ', 'тЪД', 'тЪЕ'][result - 1]
    await update.message.reply_text(get_text('dice_result', lang, emoji=dice_emoji, result=result), parse_mode=ParseMode.HTML)


async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    result_key = random.choice(['coin_heads', 'coin_tails'])
    result_text = get_text(result_key, lang)
    emoji = 'ЁЯжЕ' if result_key == 'coin_heads' else 'ЁЯТ░'
    await update.message.reply_text(get_text('coin_result', lang, emoji=emoji, result=result_text), parse_mode=ParseMode.HTML)


async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    jokes = {
        'ru': [
            "╨Я╤А╨╛╨│╤А╨░╨╝╨╝╨╕╤Б╤В ╨╗╨╛╨╢╨╕╤В╤Б╤П ╤Б╨┐╨░╤В╤М. ╨Ц╨╡╨╜╨░: тАФ ╨Ч╨░╨║╤А╨╛╨╣ ╨╛╨║╨╜╨╛, ╤Е╨╛╨╗╨╛╨┤╨╜╨╛! ╨Я╤А╨╛╨│╤А╨░╨╝╨╝╨╕╤Б╤В: тАФ ╨Ш ╤З╤В╨╛, ╤Б╤В╨░╨╜╨╡╤В ╤В╨╡╨┐╨╗╨╛? ЁЯШД",
            "тАФ ╨Я╨╛╤З╨╡╨╝╤Г ╨┐╤А╨╛╨│╤А╨░╨╝╨╝╨╕╤Б╤В╤Л ╨┐╤Г╤В╨░╤О╤В ╨е╤Н╨╗╨╗╨╛╤Г╨╕╨╜ ╨╕ ╨а╨╛╨╢╨┤╨╡╤Б╤В╨▓╨╛? тАФ 31 OCT = 25 DEC! ЁЯОГ",
            "╨Ч╨░╤З╨╡╨╝ ╨┐╤А╨╛╨│╤А╨░╨╝╨╝╨╕╤Б╤В╤Г ╨╛╤З╨║╨╕? ╨з╤В╨╛╨▒╤Л ╨╗╤Г╤З╤И╨╡ C++! ЁЯСУ",
        ],
        'en': [
            "Why do programmers prefer dark mode? Because light attracts bugs! ЁЯРЫ",
            "Why did the programmer quit his job? He didn't get arrays. ЁЯд╖тАНтЩВя╕П",
            "What's a programmer's favorite hangout spot? Foo bar. ЁЯН╗",
        ],
        'it': [
            "Perch├й i programmatori confondono Halloween e Natale? Perch├й 31 OCT = 25 DEC! ЁЯОГ",
            "Come muore un programmatore? In un loop infinito. ЁЯФД",
            "Qual ├и l'animale preferito di un programmatore? Il Python. ЁЯРН",
        ]
    }
    await update.message.reply_text(f"{get_text('joke_title', lang)}{random.choice(jokes.get(lang, jokes['en']))}", parse_mode=ParseMode.HTML)


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    quotes = {
        'ru': [
            "╨Х╨┤╨╕╨╜╤Б╤В╨▓╨╡╨╜╨╜╤Л╨╣ ╤Б╨┐╨╛╤Б╨╛╨▒ ╤Б╨┤╨╡╨╗╨░╤В╤М ╨▓╨╡╨╗╨╕╨║╤Г╤О ╤А╨░╨▒╨╛╤В╤Г тАФ ╨╗╤О╨▒╨╕╤В╤М ╤В╨╛, ╤З╤В╨╛ ╨▓╤Л ╨┤╨╡╨╗╨░╨╡╤В╨╡. тАФ ╨б╤В╨╕╨▓ ╨Ф╨╢╨╛╨▒╤Б",
            "╨Ш╨╜╨╜╨╛╨▓╨░╤Ж╨╕╤П ╨╛╤В╨╗╨╕╤З╨░╨╡╤В ╨╗╨╕╨┤╨╡╤А╨░ ╨╛╤В ╨┐╨╛╤Б╨╗╨╡╨┤╨╛╨▓╨░╤В╨╡╨╗╤П. тАФ ╨б╤В╨╕╨▓ ╨Ф╨╢╨╛╨▒╤Б",
            "╨Я╤А╨╛╤Б╤В╨╛╤В╨░ тАФ ╨╖╨░╨╗╨╛╨│ ╨╜╨░╨┤╤С╨╢╨╜╨╛╤Б╤В╨╕. тАФ ╨н╨┤╤Б╨│╨╡╤А ╨Ф╨╡╨╣╨║╤Б╤В╤А╨░"
        ],
        'en': [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "Simplicity is the soul of efficiency. - Edsger Dijkstra"
        ],
        'it': [
            "L'unico modo per fare un ottimo lavoro ├и amare quello che fai. - Steve Jobs",
            "L'innovazione distingue un leader da un seguace. - Steve Jobs",
            "La semplicit├а ├и la chiave dell'affidabilit├а. - Edsger Dijkstra"
        ]
    }
    await update.message.reply_text(
        f"{get_text('quote_title', lang)}{random.choice(quotes.get(lang, quotes['en']))}{get_text('quote_title_end', lang)}", 
        parse_mode=ParseMode.HTML
    )


async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    facts = {
        'ru': [
            "ЁЯМН ╨Ч╨╡╨╝╨╗╤П тАФ ╨╡╨┤╨╕╨╜╤Б╤В╨▓╨╡╨╜╨╜╨░╤П ╨┐╨╗╨░╨╜╨╡╤В╨░ ╨б╨╛╨╗╨╜╨╡╤З╨╜╨╛╨╣ ╤Б╨╕╤Б╤В╨╡╨╝╤Л, ╨╜╨░╨╖╨▓╨░╨╜╨╜╨░╤П ╨╜╨╡ ╨▓ ╤З╨╡╤Б╤В╤М ╨▒╨╛╨│╨░.",
            "ЁЯРЩ ╨г ╨╛╤Б╤М╨╝╨╕╨╜╨╛╨│╨╛╨▓ ╤В╤А╨╕ ╤Б╨╡╤А╨┤╤Ж╨░ ╨╕ ╨│╨╛╨╗╤Г╨▒╨░╤П ╨║╤А╨╛╨▓╤М.",
            "ЁЯНп ╨Ь╤С╨┤ ╨╜╨╡ ╨┐╨╛╤А╤В╨╕╤В╤Б╤П ╤В╤Л╤Б╤П╤З╨╕ ╨╗╨╡╤В.",
        ],
        'en': [
            "ЁЯМН Earth is the only planet in our solar system not named after a god.",
            "ЁЯРЩ Octopuses have three hearts and blue blood.",
            "ЁЯНп Honey never spoils. Archaeologists have found pots of honey thousands of years old.",
        ],
        'it': [
            "ЁЯМН La Terra ├и l'unico pianeta del sistema solare a non avere il nome di una divinit├а.",
            "ЁЯРЩ I polpi hanno tre cuori e il sangue blu.",
            "ЁЯНп Il miele non scade mai. Pu├▓ durare migliaia di anni.",
        ]
    }
    await update.message.reply_text(f"{get_text('fact_title', lang)}{random.choice(facts.get(lang, facts['en']))}", parse_mode=ParseMode.HTML)


# ============================================
# REMINDER HANDLERS
# ============================================

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remind command"""
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
        reminder = {'text': text, 'time': remind_time.isoformat(), 'created': datetime.now().isoformat(), 'lang': lang}
        reminders = user.get('reminders', [])
        reminders.append(reminder)
        storage.update_user(user_id, {'reminders': reminders})
        
        # Schedule reminder using job_queue
        context.job_queue.run_once(
            send_reminder_job,
            when=timedelta(minutes=minutes),
            data={'user_id': user_id, 'text': text, 'lang': lang},
            name=f"reminder_{user_id}_{remind_time.timestamp()}"
        )
        
        await update.message.reply_text(get_text('remind_success', lang, text=text, minutes=minutes))
    except ValueError:
        await update.message.reply_text(get_text('remind_invalid_time', lang))


async def send_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """Send reminder from job queue"""
    job_data = context.job.data
    user_id = job_data['user_id']
    text = job_data['text']
    lang = job_data['lang']
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=get_text('reminder_alert', lang, text=text),
            parse_mode=ParseMode.HTML
        )
        
        # Remove reminder from storage
        user = storage.get_user(user_id)
        reminders = [r for r in user.get('reminders', []) if r['text'] != text]
        storage.update_user(user_id, {'reminders': reminders})
    except Exception as e:
        logger.warning(f"Reminder send error: {e}")


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reminders command"""
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
    
    text = get_text('reminders_list_title', lang, count=len(reminders))
    for i, rem in enumerate(reminders, 1):
        rem_time = datetime.fromisoformat(rem['time'])
        text += get_text('reminders_list_item', lang, i=i, time=rem_time.strftime('%d.%m %H:%M'), text=rem['text'])
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ============================================
# GROUP MODERATION HANDLERS
# ============================================

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context.bot):
        await update.message.reply_text(get_text('bot_need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    reason = ' '.join(context.args) if context.args else "╨Э╨╡ ╤Г╨║╨░╨╖╨░╨╜╨░"
    
    try:
        await context.bot.ban_chat_member(chat_id, target_user.id)
        await update.message.reply_text(
            get_text('user_banned', lang, name=target_user.full_name, reason=reason),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Ban error: {e}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("тЭУ /unban [user_id]")
        return
    
    try:
        target_id = int(context.args[0])
        await context.bot.unban_chat_member(chat_id, target_id, only_if_banned=True)
        await update.message.reply_text(get_text('user_unbanned', lang, id=target_id), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Unban error: {e}")


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kick command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context.bot):
        await update.message.reply_text(get_text('bot_need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    try:
        await context.bot.ban_chat_member(chat_id, target_user.id)
        await context.bot.unban_chat_member(chat_id, target_user.id)
        await update.message.reply_text(
            get_text('user_kicked', lang, name=target_user.full_name),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Kick error: {e}")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mute command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not await is_bot_admin(chat_id, context.bot):
        await update.message.reply_text(get_text('bot_need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    minutes = 15
    if context.args:
        try:
            minutes = int(context.args[0])
        except ValueError:
            pass
    
    until_date = datetime.now() + timedelta(minutes=minutes)
    
    try:
        await context.bot.restrict_chat_member(
            chat_id, 
            target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        await update.message.reply_text(
            get_text('user_muted', lang, name=target_user.full_name, minutes=minutes),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Mute error: {e}")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmute command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    try:
        await context.bot.restrict_chat_member(
            chat_id,
            target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await update.message.reply_text(
            get_text('user_unmuted', lang, name=target_user.full_name),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Unmute error: {e}")


async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warn command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    if target_user.id == user_id:
        await update.message.reply_text(get_text('cant_self', lang))
        return
    
    if await is_user_admin(chat_id, target_user.id, context.bot):
        await update.message.reply_text(get_text('cant_admin', lang))
        return
    
    reason = ' '.join(context.args) if context.args else "╨Э╨╡ ╤Г╨║╨░╨╖╨░╨╜╨░"
    
    chat = storage.get_chat(chat_id)
    warns = chat.get('warns', {})
    user_id_str = str(target_user.id)
    warns[user_id_str] = warns.get(user_id_str, 0) + 1
    storage.update_chat(chat_id, {'warns': warns})
    
    if warns[user_id_str] >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target_user.id)
            await update.message.reply_text(
                get_text('user_warned_ban', lang, name=target_user.full_name),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Warn-ban error: {e}")
    else:
        await update.message.reply_text(
            get_text('user_warned', lang, name=target_user.full_name, count=warns[user_id_str], reason=reason),
            parse_mode=ParseMode.HTML
        )


async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unwarn command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    chat = storage.get_chat(chat_id)
    warns = chat.get('warns', {})
    user_id_str = str(target_user.id)
    
    if user_id_str in warns and warns[user_id_str] > 0:
        warns[user_id_str] -= 1
        storage.update_chat(chat_id, {'warns': warns})
    
    await update.message.reply_text(
        get_text('user_unwarned', lang, name=target_user.full_name, count=warns.get(user_id_str, 0)),
        parse_mode=ParseMode.HTML
    )


async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warns command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(get_text('need_reply', lang))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    chat = storage.get_chat(chat_id)
    warns = chat.get('warns', {})
    user_id_str = str(target_user.id)
    count = warns.get(user_id_str, 0)
    
    if count > 0:
        await update.message.reply_text(
            get_text('warns_list', lang, name=target_user.full_name, count=count),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            get_text('warns_empty', lang, name=target_user.full_name),
            parse_mode=ParseMode.HTML
        )


async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setwelcome command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("тЭУ /setwelcome [╤В╨╡╨║╤Б╤В]\n\n╨Ш╤Б╨┐╨╛╨╗╤М╨╖╤Г╨╣╤В╨╡ {name} ╨┤╨╗╤П ╨╕╨╝╨╡╨╜╨╕ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П")
        return
    
    welcome_text = ' '.join(context.args)
    storage.update_chat(chat_id, {'welcome_text': welcome_text, 'welcome_enabled': True})
    
    await update.message.reply_text(
        get_text('welcome_set', lang, text=welcome_text),
        parse_mode=ParseMode.HTML
    )


async def welcomeoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /welcomeoff command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    storage.update_chat(chat_id, {'welcome_enabled': False})
    await update.message.reply_text(get_text('welcome_off', lang))


async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setrules command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("тЭУ /setrules [╤В╨╡╨║╤Б╤В ╨┐╤А╨░╨▓╨╕╨╗]")
        return
    
    rules_text = ' '.join(context.args)
    storage.update_chat(chat_id, {'rules': rules_text})
    
    await update.message.reply_text(get_text('rules_set', lang))


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rules command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    rules = chat.get('rules', '')
    
    if rules:
        await update.message.reply_text(
            get_text('rules_text', lang, rules=rules),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(get_text('rules_empty', lang))


async def setai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setai command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_user_admin(chat_id, user_id, context.bot):
        await update.message.reply_text(get_text('need_admin', lang))
        return
    
    if not context.args:
        await update.message.reply_text("тЭУ /setai [on/off]")
        return
    
    setting = context.args[0].lower()
    
    if setting in ['on', '1', 'yes', '╨┤╨░', '╨▓╨║╨╗']:
        storage.update_chat(chat_id, {'ai_enabled': True})
        await update.message.reply_text(get_text('ai_enabled', lang))
    elif setting in ['off', '0', 'no', '╨╜╨╡╤В', '╨▓╤Л╨║╨╗']:
        storage.update_chat(chat_id, {'ai_enabled': False})
        await update.message.reply_text(get_text('ai_disabled', lang))
    else:
        await update.message.reply_text("тЭУ /setai [on/off]")


async def chatinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chatinfo command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    chat_obj = update.message.chat
    
    vip_status = "тЬЕ" if storage.is_chat_vip(chat_id) else "тЭМ"
    ai_status = "тЬЕ" if chat.get('ai_enabled', True) else "тЭМ"
    welcome_status = "тЬЕ" if chat.get('welcome_enabled', True) else "тЭМ"
    
    await update.message.reply_text(
        get_text('chat_info', lang,
            title=chat_obj.title or "Unknown",
            id=chat_id,
            vip_status=vip_status,
            ai_status=ai_status,
            welcome_status=welcome_status,
            messages=chat.get('messages_count', 0)
        ),
        parse_mode=ParseMode.HTML
    )


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /top command"""
    chat_id = update.message.chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    top_users = chat.get('top_users', {})
    
    if not top_users:
        await update.message.reply_text(get_text('top_empty', lang))
        return
    
    # Sort by message count
    sorted_users = sorted(top_users.items(), key=lambda x: x[1], reverse=True)[:10]
    
    text = get_text('top_users', lang)
    medals = ['ЁЯеЗ', 'ЁЯеИ', 'ЁЯеЙ', '4я╕ПтГг', '5я╕ПтГг', '6я╕ПтГг', '7я╕ПтГг', '8я╕ПтГг', '9я╕ПтГг', 'ЁЯФЯ']
    
    for i, (uid, count) in enumerate(sorted_users):
        try:
            member = await context.bot.get_chat_member(chat_id, int(uid))
            name = member.user.full_name
        except:
            name = f"User {uid}"
        
        text += get_text('top_users_item', lang, medal=medals[i], name=name, count=count)
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new chat members"""
    chat_id = update.message.chat.id
    
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    
    chat = storage.get_chat(chat_id)
    
    if not chat.get('welcome_enabled', True):
        return
    
    welcome_text = chat.get('welcome_text', "╨Ф╨╛╨▒╤А╨╛ ╨┐╨╛╨╢╨░╨╗╨╛╨▓╨░╤В╤М, {name}! ЁЯСЛ")
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        personalized_welcome = welcome_text.replace('{name}', member.full_name)
        
        try:
            await update.message.reply_text(personalized_welcome, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Welcome message error: {e}")


# ============================================
# ADMIN HANDLERS
# ============================================

async def grant_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /grant_vip command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(get_text('grant_vip_prompt', lang))
        return
    
    identifier = context.args[0]
    duration = context.args[1].lower()
    
    target_id = storage.get_user_id_by_identifier(identifier)
    
    if target_id is None:
        await update.message.reply_text(get_text('grant_vip_user_not_found', lang, id=identifier))
        return
    
    # Determine if it's a group (negative ID) or user
    is_group = target_id < 0
    
    durations = {
        'week': timedelta(days=7),
        'month': timedelta(days=30),
        'year': timedelta(days=365),
        'forever': None
    }
    
    if duration not in durations:
        await update.message.reply_text(get_text('grant_vip_invalid_duration', lang))
        return
    
    if durations[duration]:
        vip_until = datetime.now() + durations[duration]
        duration_text = get_text('duration_until', lang, date=vip_until.strftime('%d.%m.%Y'))
    else:
        vip_until = None
        duration_text = get_text('duration_forever', lang)
    
    if is_group:
        storage.update_chat(target_id, {
            'vip': True, 
            'vip_until': vip_until.isoformat() if vip_until else None
        })
    else:
        storage.update_user(target_id, {
            'vip': True, 
            'vip_until': vip_until.isoformat() if vip_until else None
        })
    
    await update.message.reply_text(
        get_text('grant_vip_success', lang, id=target_id, duration_text=duration_text),
        parse_mode=ParseMode.HTML
    )
    
    # Notify user (not group)
    if not is_group:
        try:
            await context.bot.send_message(
                target_id,
                get_text('grant_vip_dm', lang, duration_text=duration_text),
                parse_mode=ParseMode.HTML
            )
        except:
            pass


async def revoke_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /revoke_vip command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    if not context.args:
        await update.message.reply_text(get_text('revoke_vip_prompt', lang))
        return
    
    identifier = context.args[0]
    target_id = storage.get_user_id_by_identifier(identifier)
    
    if target_id is None:
        await update.message.reply_text(get_text('grant_vip_user_not_found', lang, id=identifier))
        return
    
    is_group = target_id < 0
    
    if is_group:
        storage.update_chat(target_id, {'vip': False, 'vip_until': None})
    else:
        storage.update_user(target_id, {'vip': False, 'vip_until': None})
    
    await update.message.reply_text(
        get_text('revoke_vip_success', lang, id=target_id),
        parse_mode=ParseMode.HTML
    )


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /users command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    all_users = storage.get_all_users()
    
    text = get_text('users_list_title', lang, count=len(all_users))
    
    users_list = list(all_users.values())[:50]
    
    for user in users_list:
        vip_badge = "ЁЯТО" if user.get('vip', False) else "ЁЯСд"
        text += get_text('users_list_item', lang,
            vip_badge=vip_badge,
            id=user.get('id', 0),
            name=user.get('first_name', 'Unknown'),
            username=user.get('username', 'none')
        )
    
    if len(all_users) > 50:
        text += get_text('users_list_more', lang, count=len(all_users) - 50)
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    if not context.args:
        await update.message.reply_text(get_text('broadcast_prompt', lang))
        return
    
    text = ' '.join(context.args)
    await update.message.reply_text(get_text('broadcast_started', lang))
    
    all_users = storage.get_all_users()
    success = 0
    failed = 0
    
    for uid in all_users.keys():
        try:
            user_lang = all_users[uid].get('language', 'ru')
            await context.bot.send_message(
                uid,
                get_text('broadcast_dm', user_lang, text=text),
                parse_mode=ParseMode.HTML
            )
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await update.message.reply_text(
        get_text('broadcast_finished', lang, success=success, failed=failed)
    )


async def stats_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (admin)"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    all_users = storage.get_all_users()
    stats = storage.stats
    
    await update.message.reply_text(
        get_text('stats_admin_title', lang,
            users=len(all_users),
            vips=sum(1 for u in all_users.values() if u.get('vip', False)),
            msg_count=stats.get('total_messages', 0),
            cmd_count=stats.get('total_commands', 0),
            ai_count=stats.get('ai_requests', 0)
        ),
        parse_mode=ParseMode.HTML
    )


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /backup command"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if not is_creator(user_id):
        await update.message.reply_text(get_text('admin_only', lang))
        return
    
    try:
        all_users = storage.get_all_users()
        all_chats = storage.get_all_chats()
        
        backup_data = {
            'users': {str(k): v for k, v in all_users.items()},
            'chats': {str(k): v for k, v in all_chats.items()},
            'stats': storage.stats,
            'backup_date': datetime.now().isoformat()
        }
        
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        
        await update.message.reply_document(
            document=io.BytesIO(backup_json.encode('utf-8')),
            filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            caption=get_text('backup_success', lang, date=datetime.now().strftime('%d.%m.%Y %H:%M'))
        )
    except Exception as e:
        await update.message.reply_text(get_text('backup_error', lang, error=str(e)))


# ============================================
# MESSAGE HANDLERS
# ============================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages"""
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    # Check AI enabled in group
    if is_group:
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        
        caption = update.message.caption or ""
        
        if caption:
            # Photo with caption - analyze immediately
            await update.message.reply_text(get_text('photo_analyzing', lang))
            response = await generate_with_context(user_id, caption, bytes(file_bytes))
            if response:
                await send_long_message(update.message, response)
        else:
            # Photo without caption - set as pending and ask
            ctx = storage.get_context(user_id)
            ctx.set_pending_image(bytes(file_bytes))
            await update.message.reply_text(get_text('photo_no_caption', lang))
    
    except Exception as e:
        logger.warning(f"Photo error: {e}")
        await update.message.reply_text(get_text('photo_error', lang, error=str(e)))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages"""
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    # Check AI enabled in group
    if is_group:
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    try:
        await update.message.reply_text(get_text('voice_transcribing', lang))
        
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Transcribe
        transcription = await transcribe_audio_with_gemini(bytes(file_bytes))
        
        # Add to context and generate response
        ctx = storage.get_context(user_id)
        ctx.add_user_voice(transcription)
        
        response = await generate_with_context(user_id, transcription)
        
        result_text = get_text('voice_result', lang, text=transcription)
        if response:
            result_text += f"\n\nЁЯдЦ <b>╨Ю╤В╨▓╨╡╤В:</b>\n\n{response}"
        
        await send_long_message(update.message, result_text)
    
    except Exception as e:
        logger.warning(f"Voice error: {e}")
        await update.message.reply_text(get_text('voice_error', lang, error=str(e)))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages"""
    user_id = update.effective_user.id
    chat_id = update.message.chat.id
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Check VIP
    if not storage.is_vip(user_id) and not (is_group and storage.is_chat_vip(chat_id)):
        await update.message.reply_text(get_text('vip_only', lang))
        return
    
    # Check AI enabled in group
    if is_group:
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    try:
        await update.message.reply_text(get_text('file_received', lang))
        
        document = update.message.document
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Extract text
        content = await extract_text_from_document(bytes(file_bytes), document.file_name)
        
        # Add to context
        ctx = storage.get_context(user_id)
        ctx.add_user_file(document.file_name, content[:5000])  # Limit content
        
        # Generate analysis
        prompt = update.message.caption or f"╨Я╤А╨╛╨░╨╜╨░╨╗╨╕╨╖╨╕╤А╤Г╨╣ ╤Н╤В╨╛╤В ╨┤╨╛╨║╤Г╨╝╨╡╨╜╤В: {document.file_name}"
        response = await generate_with_context(user_id, prompt)
        
        await send_long_message(
            update.message, 
            get_text('file_analyzing', lang, filename=document.file_name, text=response)
        )
    
    except Exception as e:
        logger.warning(f"Document error: {e}")
        await update.message.reply_text(get_text('file_error', lang, error=str(e)))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    identify_creator(user)
    
    user_id = user.id
    chat_id = update.message.chat.id
    text = update.message.text
    lang = get_lang(user_id)
    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Update stats
    user_data = storage.get_user(user_id)
    storage.update_user(user_id, {
        'username': user.username or '',
        'first_name': user.first_name or '',
        'messages_count': user_data.get('messages_count', 0) + 1
    })
    
    storage.stats['total_messages'] = storage.stats.get('total_messages', 0) + 1
    storage.save_stats()
    
    # Track group stats
    if is_group:
        storage.add_chat_message(chat_id, user_id)
        storage.update_chat(chat_id, {'title': update.message.chat.title})
        
        chat = storage.get_chat(chat_id)
        if not chat.get('ai_enabled', True):
            return
    
    # Handle menu buttons
    for btn_key, btn_texts in menu_button_map.items():
        if text in btn_texts:
            await handle_menu_button(update, context, btn_key)
            return
    
    # In groups, only respond to replies or mentions
    if is_group:
        bot_username = (await context.bot.get_me()).username
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        is_mention = f"@{bot_username}" in text
        
        if not is_reply_to_bot and not is_mention:
            return
        
        # Remove mention from text
        text = text.replace(f"@{bot_username}", "").strip()
    
    # Generate AI response
    await update.message.chat.send_action('typing')
    
    response = await generate_with_context(user_id, text)
    
    if response is None:
        # Pending image - already handled
        return
    
    await send_long_message(update.message, response)


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_key: str):
    """Handle menu button presses"""
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    if button_key == 'chat':
        await update.message.reply_text(get_text('menu.chat', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'notes':
        keyboard = [
            [InlineKeyboardButton(get_text('menu.notes_create', lang), callback_data="notes_create")],
            [InlineKeyboardButton(get_text('menu.notes_list', lang), callback_data="notes_list")]
        ]
        await update.message.reply_text(
            get_text('menu.notes', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'weather':
        await update.message.reply_text(get_text('menu.weather', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'time':
        await update.message.reply_text(get_text('menu.time', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'games':
        keyboard = [
            [InlineKeyboardButton(get_text('menu.games_dice', lang), callback_data="game_dice"),
             InlineKeyboardButton(get_text('menu.games_coin', lang), callback_data="game_coin")],
            [InlineKeyboardButton(get_text('menu.games_joke', lang), callback_data="game_joke"),
             InlineKeyboardButton(get_text('menu.games_quote', lang), callback_data="game_quote")],
            [InlineKeyboardButton(get_text('menu.games_fact', lang), callback_data="game_fact")]
        ]
        await update.message.reply_text(
            get_text('menu.games', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'info':
        await update.message.reply_text(get_text('info', lang), parse_mode=ParseMode.HTML)
    
    elif button_key == 'vip_menu':
        keyboard = [
            [InlineKeyboardButton(get_text('menu.vip_reminders', lang), callback_data="vip_reminders")],
            [InlineKeyboardButton(get_text('menu.vip_stats', lang), callback_data="vip_stats")]
        ]
        await update.message.reply_text(
            get_text('menu.vip', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'admin_panel':
        if not is_creator(user_id):
            await update.message.reply_text(get_text('admin_only', lang))
            return
        
        keyboard = [
            [InlineKeyboardButton(get_text('menu.admin_users', lang), callback_data="admin_users")],
            [InlineKeyboardButton(get_text('menu.admin_stats', lang), callback_data="admin_stats")],
            [InlineKeyboardButton(get_text('menu.admin_broadcast', lang), callback_data="admin_broadcast")]
        ]
        await update.message.reply_text(
            get_text('menu.admin', lang), 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif button_key == 'generate':
        await update.message.reply_text(get_text('menu.generate', lang), parse_mode=ParseMode.HTML)


# ============================================
# CALLBACK QUERY HANDLER
# ============================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_lang(user_id)
    data = query.data
    
    # Language selection
    if data.startswith('set_lang:'):
        new_lang = data.split(':')[1]
        storage.update_user(user_id, {'language': new_lang})
        await query.edit_message_text(get_text('lang_changed', new_lang))
        return
    
    # Help sections# Help back button - ╨Я╨Х╨а╨Т╨л╨Ь!
    if data == 'help_back':
        await query.edit_message_text(
            get_text('help_title', lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_help_keyboard(lang, is_creator(user_id))
        )
        return
    
    if data.startswith('help_'):
        section = data
        help_text = get_text(f'help_text.{section}', lang)
        keyboard = [[InlineKeyboardButton(get_text('help_back', lang), callback_data="help_back")]]
        await query.edit_message_text(
            help_text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    
    # Notes
    if data == 'notes_create':
        await query.edit_message_text(get_text('note_prompt_needed', lang))
        return
    
    if data == 'notes_list':
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
        return
    
    # Games
    if data == 'game_dice':
        result = random.randint(1, 6)
        dice_emoji = ['тЪА', 'тЪБ', 'тЪВ', 'тЪГ', 'тЪД', 'тЪЕ'][result - 1]
        await query.edit_message_text(
            get_text('dice_result', lang, emoji=dice_emoji, result=result), 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_coin':
        result_key = random.choice(['coin_heads', 'coin_tails'])
        result_text = get_text(result_key, lang)
        emoji = 'ЁЯжЕ' if result_key == 'coin_heads' else 'ЁЯТ░'
        await query.edit_message_text(
            get_text('coin_result', lang, emoji=emoji, result=result_text), 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_joke':
        jokes = {
            'ru': ["╨Я╤А╨╛╨│╤А╨░╨╝╨╝╨╕╤Б╤В ╨╗╨╛╨╢╨╕╤В╤Б╤П ╤Б╨┐╨░╤В╤М. ╨Ц╨╡╨╜╨░: тАФ ╨Ч╨░╨║╤А╨╛╨╣ ╨╛╨║╨╜╨╛, ╤Е╨╛╨╗╨╛╨┤╨╜╨╛! ╨Я╤А╨╛╨│╤А╨░╨╝╨╝╨╕╤Б╤В: тАФ ╨Ш ╤З╤В╨╛, ╤Б╤В╨░╨╜╨╡╤В ╤В╨╡╨┐╨╗╨╛? ЁЯШД"],
            'en': ["Why do programmers prefer dark mode? Because light attracts bugs! ЁЯРЫ"],
            'it': ["Perch├й i programmatori confondono Halloween e Natale? Perch├й 31 OCT = 25 DEC! ЁЯОГ"]
        }
        await query.edit_message_text(
            f"{get_text('joke_title', lang)}{random.choice(jokes.get(lang, jokes['en']))}", 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_quote':
        quotes = {
            'ru': ["╨Х╨┤╨╕╨╜╤Б╤В╨▓╨╡╨╜╨╜╤Л╨╣ ╤Б╨┐╨╛╤Б╨╛╨▒ ╤Б╨┤╨╡╨╗╨░╤В╤М ╨▓╨╡╨╗╨╕╨║╤Г╤О ╤А╨░╨▒╨╛╤В╤Г тАФ ╨╗╤О╨▒╨╕╤В╤М ╤В╨╛, ╤З╤В╨╛ ╨▓╤Л ╨┤╨╡╨╗╨░╨╡╤В╨╡. тАФ ╨б╤В╨╕╨▓ ╨Ф╨╢╨╛╨▒╤Б"],
            'en': ["The only way to do great work is to love what you do. - Steve Jobs"],
            'it': ["L'unico modo per fare un ottimo lavoro ├и amare quello che fai. - Steve Jobs"]
        }
        await query.edit_message_text(
            f"{get_text('quote_title', lang)}{random.choice(quotes.get(lang, quotes['en']))}{get_text('quote_title_end', lang)}", 
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'game_fact':
        facts = {
            'ru': ["ЁЯМН ╨Ч╨╡╨╝╨╗╤П тАФ ╨╡╨┤╨╕╨╜╤Б╤В╨▓╨╡╨╜╨╜╨░╤П ╨┐╨╗╨░╨╜╨╡╤В╨░ ╨б╨╛╨╗╨╜╨╡╤З╨╜╨╛╨╣ ╤Б╨╕╤Б╤В╨╡╨╝╤Л, ╨╜╨░╨╖╨▓╨░╨╜╨╜╨░╤П ╨╜╨╡ ╨▓ ╤З╨╡╤Б╤В╤М ╨▒╨╛╨│╨░."],
            'en': ["ЁЯМН Earth is the only planet in our solar system not named after a god."],
            'it': ["ЁЯМН La Terra ├и l'unico pianeta del sistema solare a non avere il nome di una divinit├а."]
        }
        await query.edit_message_text(
            f"{get_text('fact_title', lang)}{random.choice(facts.get(lang, facts['en']))}", 
            parse_mode=ParseMode.HTML
        )
        return
    
    # VIP menu
    if data == 'vip_reminders':
        if not storage.is_vip(user_id):
            await query.edit_message_text(get_text('vip_only', lang))
            return
        
        user = storage.get_user(user_id)
        reminders = user.get('reminders', [])
        
        if not reminders:
            await query.edit_message_text(get_text('reminders_empty', lang))
            return
        
        text = get_text('reminders_list_title', lang, count=len(reminders))
        for i, rem in enumerate(reminders, 1):
            rem_time = datetime.fromisoformat(rem['time'])
            text += get_text('reminders_list_item', lang, i=i, time=rem_time.strftime('%d.%m %H:%M'), text=rem['text'])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        return
    
    if data == 'vip_stats':
        if not storage.is_vip(user_id):
            await query.edit_message_text(get_text('vip_only', lang))
            return
        
        user = storage.get_user(user_id)
        await query.edit_message_text(
            f"ЁЯУК <b>╨Т╨░╤И╨░ ╤Б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨░:</b>\n\n"
            f"ЁЯУи ╨б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╣: {user.get('messages_count', 0)}\n"
            f"ЁЯОп ╨Ъ╨╛╨╝╨░╨╜╨┤: {user.get('commands_count', 0)}\n"
            f"ЁЯУЭ ╨Ч╨░╨╝╨╡╤В╨╛╨║: {len(user.get('notes', []))}\n"
            f"ЁЯУЛ ╨Ч╨░╨┤╨░╤З: {len(user.get('todos', []))}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Admin menu
    if data == 'admin_users':
        if not is_creator(user_id):
            await query.edit_message_text(get_text('admin_only', lang))
            return
        
        all_users = storage.get_all_users()
        text = get_text('users_list_title', lang, count=len(all_users))
        
        for user in list(all_users.values())[:20]:
            vip_badge = "ЁЯТО" if user.get('vip', False) else "ЁЯСд"
            text += f"{vip_badge} <code>{user.get('id', 0)}</code> - {user.get('first_name', 'Unknown')}\n"
        
        if len(all_users) > 20:
            text += f"\n<i>... ╨╕ ╨╡╤Й╤С {len(all_users) - 20}</i>"
        
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        return
    
    if data == 'admin_stats':
        if not is_creator(user_id):
            await query.edit_message_text(get_text('admin_only', lang))
            return
        
        all_users = storage.get_all_users()
        stats = storage.stats
        
        await query.edit_message_text(
            get_text('stats_admin_title', lang,
                users=len(all_users),
                vips=sum(1 for u in all_users.values() if u.get('vip', False)),
                msg_count=stats.get('total_messages', 0),
                cmd_count=stats.get('total_commands', 0),
                ai_count=stats.get('ai_requests', 0)
            ),
            parse_mode=ParseMode.HTML
        )
        return
    
    if data == 'admin_broadcast':
        if not is_creator(user_id):
            await query.edit_message_text(get_text('admin_only', lang))
            return
        
        await query.edit_message_text(get_text('broadcast_prompt', lang))
        return


# ============================================
# MAIN FUNCTION
# ============================================

def main():
    """Main function"""
    logger.info("ЁЯЪА Starting AI DISCO BOT v4.0...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Basic commands
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('language', language_command))
    application.add_handler(CommandHandler('info', info_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('profile', profile_command))
    application.add_handler(CommandHandler('uptime', uptime_command))
    application.add_handler(CommandHandler('vip', vip_command))
    
    # AI commands
    application.add_handler(CommandHandler('ai', ai_command))
    application.add_handler(CommandHandler('clear', clear_command))
    application.add_handler(CommandHandler('generate', generate_command))
    
    # Notes & Todo
    application.add_handler(CommandHandler('note', note_command))
    application.add_handler(CommandHandler('notes', notes_command))
    application.add_handler(CommandHandler('delnote', delnote_command))
    application.add_handler(CommandHandler('todo', todo_command))
    
    # Memory
    application.add_handler(CommandHandler('memorysave', memory_save_command))
    application.add_handler(CommandHandler('memoryget', memory_get_command))
    application.add_handler(CommandHandler('memorylist', memory_list_command))
    application.add_handler(CommandHandler('memorydel', memory_del_command))
    
    # Utilities
    application.add_handler(CommandHandler('time', time_command))
    application.add_handler(CommandHandler('weather', weather_command))
    application.add_handler(CommandHandler('translate', translate_command))
    application.add_handler(CommandHandler('calc', calc_command))
    application.add_handler(CommandHandler('password', password_command))
    
    # Games
    application.add_handler(CommandHandler('random', random_command))
    application.add_handler(CommandHandler('dice', dice_command))
    application.add_handler(CommandHandler('coin', coin_command))
    application.add_handler(CommandHandler('joke', joke_command))
    application.add_handler(CommandHandler('quote', quote_command))
    application.add_handler(CommandHandler('fact', fact_command))
    
    # Reminders (VIP)
    application.add_handler(CommandHandler('remind', remind_command))
    application.add_handler(CommandHandler('reminders', reminders_command))
    
    # Group moderation
    application.add_handler(CommandHandler('ban', ban_command))
    application.add_handler(CommandHandler('unban', unban_command))
    application.add_handler(CommandHandler('kick', kick_command))
    application.add_handler(CommandHandler('mute', mute_command))
    application.add_handler(CommandHandler('unmute', unmute_command))
    application.add_handler(CommandHandler('warn', warn_command))
    application.add_handler(CommandHandler('unwarn', unwarn_command))
    application.add_handler(CommandHandler('warns', warns_command))
    application.add_handler(CommandHandler('setwelcome', setwelcome_command))
    application.add_handler(CommandHandler('welcomeoff', welcomeoff_command))
    application.add_handler(CommandHandler('setrules', setrules_command))
    application.add_handler(CommandHandler('rules', rules_command))
    application.add_handler(CommandHandler('setai', setai_command))
    application.add_handler(CommandHandler('chatinfo', chatinfo_command))
    application.add_handler(CommandHandler('top', top_command))
    
    # Admin commands
    application.add_handler(CommandHandler('grant_vip', grant_vip_command))
    application.add_handler(CommandHandler('revoke_vip', revoke_vip_command))
    application.add_handler(CommandHandler('users', users_command))
    application.add_handler(CommandHandler('broadcast', broadcast_command))
    application.add_handler(CommandHandler('stats', stats_admin_command))
    application.add_handler(CommandHandler('backup', backup_command))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("тЬЕ Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

