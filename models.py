from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, BigInteger, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
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
    
    # Relationships
    keys = relationship("UserKey", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserKey(Base):
    __tablename__ = 'user_keys'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    provider = Column(String(50))  # openai, anthropic, gemini, etc.
    api_key = Column(String(512))
    model = Column(String(100))
    
    user = relationship("User", back_populates="keys")

class UserSettings(Base):
    __tablename__ = 'user_settings'
    user_id = Column(BigInteger, ForeignKey('users.id'), primary_key=True)
    active_provider = Column(String(50), default='gemini')
    active_model = Column(String(100))
    system_prompt = Column(Text)
    
    user = relationship("User", back_populates="settings")

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    role = Column(String(20))  # user, assistant, system
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)

class GroupChat(Base):
    __tablename__ = 'group_chats'
    id = Column(BigInteger, primary_key=True)
    title = Column(String(255))
    ai_enabled = Column(Boolean, default=True)
    welcome_enabled = Column(Boolean, default=True)
    welcome_text = Column(Text, default="Привет, {name}! Добро пожаловать в чат!")
    rules = Column(Text)
    warns_limit = Column(Integer, default=3)
    user_warns = Column(JSON, default=dict) # {user_id: count}
