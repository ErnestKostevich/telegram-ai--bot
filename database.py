import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete, update, func
from models import Base, User, UserKey, UserSettings, ChatMessage, GroupChat
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = 'sqlite+aiosqlite:///bot.db'

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

class DBManager:
    async def get_user(self, user_id: int, username: str = None, first_name: str = None):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalar_one_or_none()
            if not user:
                user = User(id=user_id, username=username, first_name=first_name)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            elif username or first_name:
                user.username = username or user.username
                user.first_name = first_name or user.first_name
                await session.commit()
            return user

    async def update_user(self, user_id: int, **kwargs):
        async with AsyncSessionLocal() as session:
            await session.execute(update(User).filter_by(id=user_id).values(**kwargs))
            await session.commit()

    async def get_user_settings(self, user_id: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserSettings).filter_by(user_id=user_id))
            settings = result.scalar_one_or_none()
            if not settings:
                settings = UserSettings(user_id=user_id)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
            return settings

    async def update_user_settings(self, user_id: int, **kwargs):
        async with AsyncSessionLocal() as session:
            await session.execute(update(UserSettings).filter_by(user_id=user_id).values(**kwargs))
            await session.commit()

    async def get_active_key(self, user_id: int, provider: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserKey).filter_by(user_id=user_id, provider=provider))
            return result.scalar_one_or_none()

    async def update_user_key(self, user_id: int, provider: str, api_key: str, model: str = None):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserKey).filter_by(user_id=user_id, provider=provider))
            key = result.scalar_one_or_none()
            if key:
                key.api_key = api_key
                key.model = model
            else:
                key = UserKey(user_id=user_id, provider=provider, api_key=api_key, model=model)
                session.add(key)
            await session.commit()

    async def get_group(self, chat_id: int, title: str = None):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GroupChat).filter_by(id=chat_id))
            group = result.scalar_one_or_none()
            if not group:
                group = GroupChat(id=chat_id, title=title)
                session.add(group)
                await session.commit()
                await session.refresh(group)
            elif title:
                group.title = title
                await session.commit()
            return group

    async def update_group(self, chat_id: int, **kwargs):
        async with AsyncSessionLocal() as session:
            await session.execute(update(GroupChat).filter_by(id=chat_id).values(**kwargs))
            await session.commit()

    async def add_message(self, user_id: int, chat_id: int, role: str, content: str):
        async with AsyncSessionLocal() as session:
            msg = ChatMessage(user_id=user_id, chat_id=chat_id, role=role, content=content)
            session.add(msg)
            await session.commit()

    async def get_history(self, user_id: int, limit: int = 10):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ChatMessage)
                .filter_by(user_id=user_id)
                .order_by(ChatMessage.timestamp.desc())
                .limit(limit)
            )
            messages = result.scalars().all()
            return messages[::-1]

    async def clear_history(self, user_id: int):
        async with AsyncSessionLocal() as session:
            await session.execute(delete(ChatMessage).filter_by(user_id=user_id))
            await session.commit()

    async def get_stats(self):
        async with AsyncSessionLocal() as session:
            user_count = await session.execute(select(func.count(User.id)))
            group_count = await session.execute(select(func.count(GroupChat.id)))
            msg_count = await session.execute(select(func.count(ChatMessage.id)))
            return {
                "users": user_count.scalar(),
                "groups": group_count.scalar(),
                "messages": msg_count.scalar()
            }
