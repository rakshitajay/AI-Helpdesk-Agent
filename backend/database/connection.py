"""
database/connection.py
-----------------------
Async SQLAlchemy engine, session factory, and DB initialisation.
Uses aiosqlite for non-blocking SQLite access inside FastAPI's async context.
"""

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.config.settings import settings
from backend.database.models import Base
from backend.utils.logger import logger


# Ensure data directory exists before SQLite creates the file
Path("./data").mkdir(parents=True, exist_ok=True)

# ── Async engine ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # Log SQL statements in debug mode
    connect_args={"check_same_thread": False},
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """
    Create all tables defined in models.py if they don't already exist.
    Called once at application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised successfully.")


async def get_db():
    """
    FastAPI dependency that yields a database session per request
    and ensures it is closed after the response is sent.

    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
