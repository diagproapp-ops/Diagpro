from datetime import date, datetime
import os
import sys
from pathlib import Path
import httpx
import pytest_asyncio
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.auth import create_access_token, get_password_hash  # noqa: E402
from backend.app.database import IS_SQLITE, SessionLocal, set_tenant_context  # noqa: E402
from backend.app.db_models import Company, Conteudo, Evento, QuestoesBanco, Tenant, User  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.roles import UserRole  # noqa: E402
from backend.app.utils_crypto import encrypt_text  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def ensure_ci_seed_data():
    """Popula dados sintéticos mínimos apenas quando o banco está vazio (ex.: GitHub Actions CI)."""
    async with SessionLocal() as session:
        async with session.begin():
            if not IS_SQLITE:
                await set_tenant_context(session, None, bypass_rls=True)
            count = (await session.execute(text("SELECT COUNT(*) FROM tenants"))).scalar()
            if count and count > 0:
                return

            t1 = Tenant(id=1, name="Banca Teste 1", domain="banca1.test", status="ativo", tenant_type="empresa_concurso", created_at=datetime.utcnow())
            t2 = Tenant(id=2, name="Banca Teste 2", domain="banca2.test", status="ativo", tenant_type="empresa_concurso", created_at=datetime.utcnow())
            session.add_all([t1, t2])
            await session.flush()

            pwd = get_password_hash("TestPassword123!")
            session.add_all([
                User(username="Victor Hugo", email="ag@example.com", password_hash=pwd, role=UserRole.ADMIN_GERAL.value, tenant_id=None, status="ativo", is_active=True),
                User(username="admin1", email="a1@example.com", password_hash=pwd, role=UserRole.ADMIN.value, tenant_id=1, status="ativo", is_active=True),
                User(username="admin2", email="a2@example.com", password_hash=pwd, role=UserRole.ADMIN.value, tenant_id=2, status="ativo", is_active=True),
                User(username="vhugo", email="p1@example.com", password_hash=pwd, role=UserRole.PROFESSOR.value, tenant_id=1, status="ativo", is_active=True),
                User(username="vhugo1234", email="d1@example.com", password_hash=pwd, role=UserRole.DIAGRAMADOR.value, tenant_id=1, status="ativo", is_active=True),
            ])
            session.add_all([
                Company(tenant_id=1, company_name="Banca Teste 1", company_cnpj="00000000000100", company_address="", company_phone="", company_email="", company_website="", company_logo_path=""),
                Company(tenant_id=2, company_name="Banca Teste 2", company_cnpj="00000000000200", company_address="", company_phone="", company_email="", company_website="", company_logo_path=""),
            ])
            ev_id = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
            session.add(
                Evento(
                    id_evento=ev_id,
                    tenant_id=1,
                    nome_evento="Evento CI Teste",
                    data_prova=date(2026, 12, 1),
                    status="Aberto",
                    senha_evento=pwd,
                    senha_evento_cripto=encrypt_text("1234"),
                    qtd_cargos=1,
                    identificador_evento="CI001",
                    is_deleted=False,
                )
            )
            session.add(
                Conteudo(
                    id_conteudo="ci-conteudo-1",
                    identificador_conteudo="CI-C01",
                    nome_conteudo="Conteudo CI",
                    evento_id=ev_id,
                    tenant_id=1,
                    is_deleted=False,
                    respondidas=0,
                    quantidade=1,
                )
            )
            session.add(
                QuestoesBanco(
                    id_questao="ci-questao-1",
                    codigo_curto_questao="Q-CI0001",
                    id_evento_fk=ev_id,
                    enunciado="Questao de matematica para teste automatizado",
                    disciplina_banco="Matematica",
                    tipo="MULTIPLA_ESCOLHA",
                    tenant_id=1,
                )
            )


@pytest_asyncio.fixture
async def async_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def auth_headers(username: str, role: UserRole | str, tenant_id: int | None = None) -> dict[str, str]:
    role_val = role.value if isinstance(role, UserRole) else role
    payload = {"sub": username, "role": role_val}
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    token = create_access_token(payload)
    return {"Authorization": f"Bearer {token}"}
