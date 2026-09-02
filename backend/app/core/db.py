import os
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

def database_url() -> str:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    host = os.getenv("DB_HOST")
    password = os.getenv("DB_PASSWORD")
    if host and password:
        user = quote_plus(os.getenv("DB_USER", "postgres"))
        encoded_password = quote_plus(password)
        port = os.getenv("DB_PORT", "5432")
        name = quote_plus(os.getenv("DB_NAME", "scholarship"))
        return f"postgresql+asyncpg://{user}:{encoded_password}@{host}:{port}/{name}"
    return "postgresql+asyncpg://postgres:postgres@db:5432/scholarship"


DATABASE_URL = database_url()

engine: AsyncEngine = create_async_engine(DATABASE_URL, future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
