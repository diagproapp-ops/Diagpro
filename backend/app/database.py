# backend/app/database.py
import os
import ssl
from dotenv import load_dotenv
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, Session

load_dotenv()

# O DiagPro opera exclusivamente em PostgreSQL (multi-tenant com RLS). Não há fallback:
# sem uma URL PostgreSQL válida a aplicação não inicia (fail-closed).
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError(
        "DATABASE_URL ausente ou inválida: o DiagPro exige PostgreSQL "
        "(postgresql+asyncpg://diagpro_runtime:...@host:porta/banco)."
    )

# Mantido por compatibilidade com código existente; sempre False.
IS_SQLITE = False

# TLS na conexão com o banco. Padrão: verify-full (valida CA e nome do servidor).
#   DB_SSLMODE=verify-full -> exige DB_SSL_ROOT_CERT (CA que assinou o certificado do servidor)
#   DB_SSLMODE=require     -> cifra o canal sem validar o certificado (evitar)
#   DB_SSLMODE=disable     -> apenas para CI/contêiner efêmero; nunca em ambiente com dados reais
DB_SSLMODE = os.getenv("DB_SSLMODE", "verify-full").strip().lower()
DB_SSL_ROOT_CERT = os.getenv("DB_SSL_ROOT_CERT", "").strip()


def _build_ssl_context():
    if DB_SSLMODE == "disable":
        return False
    if DB_SSLMODE == "require":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if DB_SSLMODE == "verify-full":
        if not DB_SSL_ROOT_CERT or not os.path.isfile(DB_SSL_ROOT_CERT):
            raise RuntimeError("DB_SSLMODE=verify-full exige DB_SSL_ROOT_CERT apontando para o certificado da CA.")
        ctx = ssl.create_default_context(cafile=DB_SSL_ROOT_CERT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx
    raise RuntimeError(f"DB_SSLMODE inválido: {DB_SSLMODE!r} (use verify-full, require ou disable).")


def sync_ssl_query() -> str:
    """Parâmetros de TLS equivalentes para drivers síncronos (psycopg2: Alembic e scripts)."""
    if DB_SSLMODE == "disable":
        return "sslmode=disable"
    if DB_SSLMODE == "require":
        return "sslmode=require"
    return f"sslmode=verify-full&sslrootcert={DB_SSL_ROOT_CERT}"


engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
    "connect_args": {"ssl": _build_ssl_context()},
}

# Role de runtime (diagpro_runtime): NOSUPERUSER, NOBYPASSRLS. Usada em toda requisição de tenant.
engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# Role de plataforma (diagpro_platform): NOSUPERUSER, BYPASSRLS. É a ÚNICA forma de enxergar dados de
# mais de um tenant. Usada apenas em login, cadastro público, resolução do administrador geral e jobs
# do administrador geral. A liberação do RLS depende desta credencial, e não de variável de sessão.
PLATFORM_DATABASE_URL = os.getenv("PLATFORM_DATABASE_URL", "").strip()
if not PLATFORM_DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError(
        "PLATFORM_DATABASE_URL ausente ou inválida (postgresql+asyncpg://diagpro_platform:...@host:porta/banco)."
    )
if PLATFORM_DATABASE_URL == DATABASE_URL:
    raise RuntimeError("PLATFORM_DATABASE_URL não pode ser igual a DATABASE_URL: as roles devem ser distintas.")

platform_engine = create_async_engine(
    PLATFORM_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_PLATFORM_POOL_SIZE", "3")),
    max_overflow=int(os.getenv("DB_PLATFORM_MAX_OVERFLOW", "5")),
    connect_args={"ssl": _build_ssl_context()},
)

_session_opts = dict(autocommit=False, autoflush=False, class_=AsyncSession, expire_on_commit=False)
SessionLocal = sessionmaker(bind=engine, **_session_opts)
# info['platform'] libera o carregamento de linhas de qualquer tenant na camada de cifra (field_crypto)
PlatformSessionLocal = sessionmaker(bind=platform_engine, info={"platform": True}, **_session_opts)

Base = declarative_base()


@event.listens_for(Session, "after_begin")
def _apply_rls_on_after_begin(session: Session, transaction, connection) -> None:
    """Reaplica o contexto de tenant (SET LOCAL) no início de cada transação (ex.: após commit + refresh)."""
    if not session.info.get("rls_configured"):
        return
    tid = session.info.get("tenant_id")
    if tid is None:
        raise RuntimeError("Contexto de tenant obrigatório: tenant_id ausente (fail-closed).")
    connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(int(tid))},
    )


async def set_tenant_context(session: AsyncSession, tenant_id: int) -> None:
    """
    Define o tenant da transação atual (set_config(..., true) = SET LOCAL) para o RLS.
    Não existe modo de bypass: para acesso multi-tenant use PlatformSessionLocal (role própria).
    """
    if tenant_id is None:
        raise RuntimeError("Contexto de tenant obrigatório: tenant_id ausente (fail-closed).")
    session.info["rls_configured"] = True
    session.info["tenant_id"] = int(tenant_id)
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(int(tenant_id))},
    )
    # quem é de outra banca de origem e tem vínculo com esta (o RLS de vinculos_banca só devolve os desta banca):
    # a camada de cifra só aceita carregar a identidade dessas pessoas fora do tenant da sessão
    linhas = await session.execute(text("SELECT user_id FROM vinculos_banca"))
    session.info["membros_outra_banca"] = frozenset(r[0] for r in linhas)


async def get_db():
    """Sessão de runtime SEM contexto de tenant: sob RLS, não enxerga dados de nenhum tenant."""
    async with SessionLocal() as session:
        yield session


async def get_platform_db():
    """Sessão com a role de plataforma (BYPASSRLS). Usar somente em login/cadastro e fluxos do admin geral."""
    async with PlatformSessionLocal() as session:
        yield session


# Nome antigo mantido para os fluxos pré-autenticação já existentes.
get_auth_db = get_platform_db
