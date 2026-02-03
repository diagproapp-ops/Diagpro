# backend/app/database.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Constrói um caminho absoluto para a raiz do projeto
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "diagprooff.db")

# O caminho para a sua base de dados SQLite
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Cria uma classe de sessão que iremos usar para interagir com a BD
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  # <-- ESSENCIAL!
)

# Uma classe base para os nossos modelos da BD (as tabelas)
Base = declarative_base()

# Função para obter uma sessão da BD em cada pedido
async def get_db():
    async with SessionLocal() as session:
        yield session