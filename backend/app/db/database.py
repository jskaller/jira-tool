from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from ..core.config import get_settings

Base = declarative_base()

_engine = None
_sessionmaker = None

def _make_dsn() -> str:
    settings = get_settings()
    return f"sqlite+aiosqlite:///{settings.sqlite_path}"

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(_make_dsn(), echo=False, future=True)
    return _engine

def get_sessionmaker():
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _sessionmaker

async def init_db():
    # Import models to register metadata
    from . import models  # noqa
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
