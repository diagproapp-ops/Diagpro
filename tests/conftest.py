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

# Trava: os testes mexem em configurações, usuários e dados. Rodar o pytest direto carregava o .env e usava o
# banco REAL. Só seguem se TODAS as URLs de banco apontarem para um banco de teste (nome terminando em "_test").
from dotenv import load_dotenv as _load_dotenv  # noqa: E402

_load_dotenv()  # não sobrescreve o que o scripts/run_tests.py (ou o CI) já definiu
for _var in ("DATABASE_URL", "PLATFORM_DATABASE_URL"):
    _url = os.environ.get(_var, "")
    _nome_banco = _url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not _nome_banco.endswith("_test"):
        import pytest as _pytest
        _pytest.exit(f"{_var} aponta para o banco '{_nome_banco}', que não é de teste. Rode: python scripts/run_tests.py",
                     returncode=4)

# Os testes NUNCA gravam/apagam templates na pasta real do sistema (o evento de teste tem o mesmo id de um evento
# real): usam uma pasta temporária, definida antes de importar o app.
if not os.environ.get("DIAGPRO_TEMPLATES_DIR"):
    import tempfile as _tempfile
    os.environ["DIAGPRO_TEMPLATES_DIR"] = _tempfile.mkdtemp(prefix="diagpro_templates_teste_")
# a miniatura do template (LibreOffice) não é gerada a cada envio durante os testes
os.environ.setdefault("DIAGPRO_MINIATURA_AO_ENVIAR", "0")

from backend.app.auth import create_access_token, get_password_hash  # noqa: E402
from backend.app.database import PlatformSessionLocal  # noqa: E402
from backend.app.db_models import Company, Conteudo, Evento, QuestoesBanco, Tenant, User  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.roles import UserRole  # noqa: E402
from backend.app.utils_crypto import encrypt_text  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def ensure_ci_seed_data():
    """Popula dados sintéticos mínimos apenas quando o banco está vazio (ex.: GitHub Actions CI)."""
    # Seed com a role de plataforma (BYPASSRLS): a role de runtime não consegue inserir dados de vários tenants.
    async with PlatformSessionLocal() as session:
        async with session.begin():
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
    payload["mfa"] = True  # igual ao token real, emitido só depois do 2FA
    payload["auth_time"] = int(__import__("time").time())
    token = create_access_token(payload)
    return {"Authorization": f"Bearer {token}"}


EVENTO_TESTE = "c2438719-23aa-4f7d-8e0f-e6a310c10440"


async def com_evento_liberado(client, username: str, role: UserRole | str, tenant_id: int,
                              evento_id: str = EVENTO_TESTE, senha: str = "1234") -> dict[str, str]:
    """Cabeçalho de uma sessão REAL (com sid) que já digitou a senha do evento (fila/revisão exigem)."""
    from types import SimpleNamespace

    from sqlalchemy import select as _select

    from backend.app import sessoes
    from backend.app.field_crypto import blind_eq
    async with PlatformSessionLocal() as s:
        uid = (await s.execute(_select(User.id).where(blind_eq(User.username, username)))).scalar_one()
    sid = await sessoes.abrir(SimpleNamespace(id=uid, tenant_id=tenant_id), None, alertar=False)
    role_val = role.value if isinstance(role, UserRole) else role
    token = create_access_token({"sub": username, "role": role_val, "tenant_id": tenant_id, "mfa": True, "sid": sid,
                                 "auth_time": int(__import__("time").time())})
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(f"/revisao/eventos/{evento_id}/liberar", headers=h, json={"senha": senha})
    assert r.status_code == 200, r.text
    return h
