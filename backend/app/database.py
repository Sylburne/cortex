from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.config import settings

# Neon free tier allows ~10 concurrent connections; keep pool small
engine = create_async_engine(
    settings.asyncpg_url,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,   # detect dropped connections after Render spin-down
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
