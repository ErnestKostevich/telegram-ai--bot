import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, UserKey, UserSettings, ChatMessage, GroupChat
from datetime import datetime

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')
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
