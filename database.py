import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, UserKey, UserSettings, ChatMessage, GroupChat
from datetime import datetime

DATABASE_URL = os.getenv('DATABASE_URL')

# Render provides split variables if DATABASE_URL is not set directly
if not DATABASE_URL:
    pg_user = os.getenv('PG_USER')
    pg_pass = os.getenv('PG_PASSWORD')
    pg_host = os.getenv('PG_HOST')
    pg_port = os.getenv('PG_PORT', '5432')
    pg_db = os.getenv('PG_DATABASE')
    if all([pg_user, pg_pass, pg_host, pg_db]):
        DATABASE_URL = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    else:
        DATABASE_URL = 'sqlite:///bot.db'

# SQLAlchemy requires 'postgresql://' instead of 'postgres://' which Render might provide
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

class DBManager:
    def __init__(self):
        self.session = Session()

    def get_user(self, user_id: int):
        user = self.session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(id=user_id)
            self.session.add(user)
            self.session.commit()
        return user

    def get_user_settings(self, user_id: int):
        settings = self.session.query(UserSettings).filter_by(user_id=user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            self.session.add(settings)
            self.session.commit()
        return settings

    def update_user_key(self, user_id: int, provider: str, api_key: str, model: str = None):
        key = self.session.query(UserKey).filter_by(user_id=user_id, provider=provider).first()
        if key:
            key.api_key = api_key
            key.model = model
        else:
            key = UserKey(user_id=user_id, provider=provider, api_key=api_key, model=model)
            self.session.add(key)
        self.session.commit()

    def get_active_key(self, user_id: int, provider: str):
        return self.session.query(UserKey).filter_by(user_id=user_id, provider=provider).first()

    def add_message(self, user_id: int, role: str, content: str):
        msg = ChatMessage(user_id=user_id, role=role, content=content)
        self.session.add(msg)
        self.session.commit()

    def get_history(self, user_id: int, limit: int = 10):
        return self.session.query(ChatMessage).filter_by(user_id=user_id).order_by(ChatMessage.timestamp.desc()).limit(limit).all()[::-1]

    def clear_history(self, user_id: int):
        self.session.query(ChatMessage).filter_by(user_id=user_id).delete()
        self.session.commit()

    def get_group(self, chat_id: int):
        group = self.session.query(GroupChat).filter_by(id=chat_id).first()
        if not group:
            group = GroupChat(id=chat_id)
            self.session.add(group)
            self.session.commit()
        return group

    def update_group(self, chat_id: int, **kwargs):
        group = self.get_group(chat_id)
        for key, value in kwargs.items():
            setattr(group, key, value)
        self.session.commit()

    def add_warn(self, chat_id: int, user_id: int):
        group = self.get_group(chat_id)
        warns = dict(group.user_warns or {})
        uid_str = str(user_id)
        warns[uid_str] = warns.get(uid_str, 0) + 1
        group.user_warns = warns
        self.session.commit()
        return warns[uid_str]

    def reset_warns(self, chat_id: int, user_id: int):
        group = self.get_group(chat_id)
        warns = dict(group.user_warns or {})
        uid_str = str(user_id)
        if uid_str in warns:
            del warns[uid_str]
        group.user_warns = warns
        self.session.commit()
