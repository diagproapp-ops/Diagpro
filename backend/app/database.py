# backend/app/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, Session

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SQLITE_PATH = os.path.join(PROJECT_ROOT, "diagprooff.db")

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}"
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine_kwargs = {}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


@event.listens_for(Session, "after_begin")
def _apply_rls_on_after_begin(session: Session, transaction, connection) -> None:
    """Reaplica SET LOCAL automaticamente no início de cada transação (ex.: após commit + refresh)."""
    if IS_SQLITE or not session.info.get("rls_configured"):
        return
    if session.info.get("bypass_rls"):
        connection.execute(text("SET LOCAL app.bypass_rls = 'on'"))
        connection.execute(text("SET LOCAL app.current_tenant_id = ''"))
    else:
        tid = session.info.get("tenant_id")
        if tid is None:
            raise RuntimeError("Contexto de tenant obrigatório: tenant_id ausente (fail-closed).")
        connection.execute(text("SET LOCAL app.bypass_rls = 'off'"))
        connection.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(int(tid))},
        )


async def set_tenant_context(
    session: AsyncSession,
    tenant_id: int | None,
    bypass_rls: bool = False,
) -> None:
    """Define variáveis de sessão transacionais (SET LOCAL) para RLS no PostgreSQL (fail-closed)."""
    if IS_SQLITE:
        return
    if not bypass_rls and tenant_id is None:
        raise RuntimeError("Contexto de tenant obrigatório: tenant_id ausente (fail-closed).")

    session.info["rls_configured"] = True
    session.info["bypass_rls"] = bool(bypass_rls)
    session.info["tenant_id"] = int(tenant_id) if tenant_id is not None else None

    if bypass_rls:
        await session.execute(text("SET LOCAL app.bypass_rls = 'on'"))
        await session.execute(text("SET LOCAL app.current_tenant_id = ''"))
    else:
        await session.execute(text("SET LOCAL app.bypass_rls = 'off'"))
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(int(tenant_id))},
        )


async def get_db():
    async with SessionLocal() as session:
        yield session


async def get_auth_db():
    """Sessão explícita para fluxos pré-autenticação (login/cadastro) com bypass controlado por transação."""
    async with SessionLocal() as session:
        if not IS_SQLITE:
            await set_tenant_context(session, None, bypass_rls=True)
        yield session
