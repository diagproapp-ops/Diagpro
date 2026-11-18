import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from alembic import context

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importa Base e todos os modelos para autogenerate
from backend.app.database import Base  # noqa: E402
import backend.app.db_models  # noqa: E402, F401

target_metadata = Base.metadata


def get_sync_url() -> str:
    url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL não configurada no ambiente/.env para executar o Alembic.")
    # Converte driver assíncrono para síncrono para o Alembic
    return (
        url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
           .replace("sqlite+aiosqlite:///", "sqlite:///")
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_sync_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
