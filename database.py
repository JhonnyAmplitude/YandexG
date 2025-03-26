import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()
# Строка подключения к базе данных
DATABASE_URL = os.getenv("DB_URL")

# Создание асинхронного движка
engine = create_async_engine(DATABASE_URL, echo=True)

# Создание сессии
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Создание базового класса для моделей
Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session
