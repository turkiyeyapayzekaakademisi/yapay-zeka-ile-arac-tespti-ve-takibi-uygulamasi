"""
Adımlar:
    1. Gerekli kütüphanelerin import edilmesi
    2. Async SQLAlchemy engine oluşturmak
    3. Async session factoryi tanımlamak
    4. Base class oluşturmak
    5. get_db dependencyi yazmak

Kurulum
    1. requirements.txtye gerekli kütüphanelerin eklenmesi:
        sqlalchemy[asyncio]
        asyncpg
    2. Bağımlılıkların yüklenmesi
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.core.config import settings

engine = create_async_engine(
    settings.async_database_url,
    pool_size = 5,
    max_overflow = 10,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

Base = declarative_base()

async def _create_database_if_not_exists():
    db_url = settings.async_database_url
    db_name = db_url.rsplit("/", 1)[-1]
    base_url = db_url.rsplit("/", 1)[0] + "/postgres"

    temp_engine = create_async_engine(base_url, isolation_level="AUTOCOMMIT")

    try:
        async with temp_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name}
            )
            if not result.scalar():
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await temp_engine.dispose()

async def init_db(engine_override=None):
    await _create_database_if_not_exists()
    use_engine = engine_override or engine
    async with use_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

if __name__ == "__main__":

    import asyncio

    async def _test():
        print("1) init_db çalıştırılıyor")
        await init_db()
        print(" init_db tamamlandı")

        print("2) get_db testi")
        async for session in get_db():
            print(f"Session alındı: {session}")
        print("session kapandı")

        print("Tüm testler başarılı")
    
    asyncio.run(_test())