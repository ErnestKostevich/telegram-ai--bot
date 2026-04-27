from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text, BigInteger, Float
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255))
    vip = Column(Boolean, default=False)
    vip_until = Column(DateTime)
    language = Column(String(5), default='ru')
    registered = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    messages_count = Column(Integer, default=0)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    rep = Column(Integer, default=0)
    daily_last_claim = Column(DateTime)
    
    # Personal Data
    notes = Column(JSON, default=list)
    todos = Column(JSON, default=list)
    memory = Column(JSON, default=dict)
    reminders = Column(JSON, default=list)
    
    # Relationships
    keys = relationship("UserKey", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserKey(Base):
    __tablename__ = 'user_keys'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    provider = Column(String(50))
    api_key = Column(String(255))
    model = Column(String(100))
    user = relationship("User", back_populates="keys")

class UserSettings(Base):
    __tablename__ = 'user_settings'
    user_id = Column(BigInteger, ForeignKey('users.id'), primary_key=True)
    active_provider = Column(String(50))
    ai_enabled = Column(Boolean, default=True)
    user = relationship("User", back_populates="settings")

class GroupChat(Base):
    __tablename__ = 'group_chats'
    id = Column(BigInteger, primary_key=True)
    title = Column(String(255))
    ai_enabled = Column(Boolean, default=True)
    welcome_enabled = Column(Boolean, default=False)
    welcome_text = Column(Text)
    goodbye_enabled = Column(Boolean, default=False)
    rules = Column(Text)
    
    # Security/Moderation
    antilink = Column(Boolean, default=False)
    antispam = Column(Boolean, default=False)
    caps_filter = Column(Boolean, default=False)
    ai_guardian = Column(Boolean, default=False)
    disco_mode = Column(Boolean, default=False)
    slowmode = Column(Integer, default=0)
    
    # Stats
    messages_count = Column(Integer, default=0)
    warns = Column(JSON, default=dict) # {user_id: count}

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    chat_id = Column(BigInteger)
    role = Column(String(20))
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)
