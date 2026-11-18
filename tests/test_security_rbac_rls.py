import pytest
from sqlalchemy import text

from backend.app.database import IS_SQLITE, SessionLocal, set_tenant_context
from backend.app.jobs import create_job
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from backend.app.storage import LocalStorageBackend
from backend.app.utils_crypto import encrypt_pii, mask_pii, safe_decrypt_pii
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_unauthenticated_endpoints_return_401(async_client):
    for method, path in [
        ("GET", "/eventos/"),
        ("GET", "/admin/clients"),
        ("GET", "/admin/logs/geracao/"),
        ("POST", "/api/ia-chat"),
        ("POST", "/api/check-plagio"),
        ("POST", "/api/dicionario"),
        ("POST", "/api/biblioteca"),
        ("POST", "/api/export/eventos/123/validar-senha"),
    ]:
        resp = await async_client.request(method, path, json={})
        assert resp.status_code == 401, f"{method} {path} retornou {resp.status_code}"


@pytest.mark.asyncio
async def test_public_register_blocks_admin_escalation_and_bad_uploads(async_client):
    for forbidden_role in [UserRole.ADMIN_GERAL.value, UserRole.ADMIN.value]:
        resp = await async_client.post(
            "/users/register",
            data={
                "username": "synthetic_attacker",
                "email": "attacker@example.com",
                "password": "StrongPassword123!",
                "role": forbidden_role,
                "tenant_id": "1",
                "accepted_confidentiality": "true",
                "accepted_data_leak": "true",
            },
            files={"avatar_file": ("avatar.png", b"fake-png", "image/png")},
        )
        assert resp.status_code == 403, f"Role {forbidden_role} deveria ser bloqueada: {resp.status_code}"

    bad_upload = await async_client.post(
        "/users/register",
        data={
            "username": "synthetic_bad_file",
            "email": "badfile@example.com",
            "password": "StrongPassword123!",
            "role": UserRole.PROFESSOR.value,
            "tenant_id": "1",
            "accepted_confidentiality": "true",
            "accepted_data_leak": "true",
        },
        files={"avatar_file": ("payload.html", b"<script>alert(1)</script>", "text/html")},
    )
    assert bad_upload.status_code == 400


@pytest.mark.asyncio
async def test_rbac_matrix_five_roles(async_client):
    h_admin_geral = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    h_admin = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    h_prof = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    h_rev = auth_headers("revisor_synth", UserRole.REVISOR, tenant_id=1)
    h_diag = auth_headers("vhugo1234", UserRole.DIAGRAMADOR, tenant_id=1)

    # /admin/clients: apenas ADMIN_GERAL
    assert (await async_client.get("/admin/clients", headers=h_admin_geral)).status_code == 200
    for h in (h_admin, h_prof, h_diag):
        assert (await async_client.get("/admin/clients", headers=h)).status_code == 403

    # POST /eventos/: apenas ADMIN e ADMIN_GERAL (enviando payload mínimo para checar 403 antes da validação/gravação ou 422 se permitido)
    for h in (h_prof, h_diag):
        assert (await async_client.post("/eventos/", headers=h, json={})).status_code == 403
    assert (await async_client.post("/eventos/", headers=h_admin, json={})).status_code == 422

    # PUT /company: apenas ADMIN e ADMIN_GERAL
    for h in (h_prof, h_diag):
        assert (await async_client.put("/company", headers=h)).status_code == 403

    # GET /admin/logs/geracao/: ADMIN, ADMIN_GERAL, DIAGRAMADOR (bloqueado para PROFESSOR)
    assert (await async_client.get("/admin/logs/geracao/", headers=h_prof)).status_code == 403
    assert (await async_client.get("/admin/logs/geracao/", headers=h_diag)).status_code == 200
    assert (await async_client.get("/admin/logs/geracao/", headers=h_admin)).status_code == 200

    # POST /frases/: bloqueado para PROFESSOR
    assert (await async_client.post("/frases/", headers=h_prof, json={})).status_code == 403

    # POST /eventos/{id}/provas/definir-geracao: bloqueado para PROFESSOR
    assert (
        await async_client.post("/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/provas/definir-geracao", headers=h_prof)
    ).status_code == 403

    # Cargos, Conteúdos, Provas, Exportação e Gabarito: bloqueados para PROFESSOR
    assert (
        await async_client.post("/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/cargos", headers=h_prof, json={})
    ).status_code == 403
    assert (
        await async_client.post("/conteudos/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/conteudos", headers=h_prof, json={})
    ).status_code == 403
    assert (
        await async_client.post("/provas/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/provas-montadas/123", headers=h_prof, json={})
    ).status_code == 403
    assert (
        await async_client.post("/api/export/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/validar-senha", headers=h_prof, json={"senha": "x"})
    ).status_code == 403
    assert (
        await async_client.post("/api/gabarito/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/exportar-gabaritos-zip?senha=x", headers=h_prof)
    ).status_code == 403

    # Revisão de questão: bloqueada para PROFESSOR e DIAGRAMADOR (permitida para REVISOR/ADMIN)
    for h in (h_prof, h_diag):
        assert (
            await async_client.patch(
                "/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/conteudos/123/questoes/456/revisao",
                headers=h,
            )
        ).status_code == 403

    # Nota: usuário sintético inexistente no banco retorna 401 em get_current_user
    assert (await async_client.get("/eventos/", headers=h_rev)).status_code == 401


@pytest.mark.asyncio
async def test_http_tenant_isolation_between_tenant_1_and_tenant_2(async_client):
    h_t1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    h_t2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)

    ev1 = await async_client.get("/eventos/", headers=h_t1)
    assert ev1.status_code == 200 and len(ev1.json()) >= 1
    target_event_id = ev1.json()[0]["id_evento"]

    ev2 = await async_client.get("/eventos/", headers=h_t2)
    assert ev2.status_code == 200
    assert all(e["tenant_id"] == 2 for e in ev2.json())

    # Tenant 2 tentando acessar evento do Tenant 1 -> 404
    cross = await async_client.get(f"/eventos/{target_event_id}", headers=h_t2)
    assert cross.status_code == 404


@pytest.mark.asyncio
async def test_postgres_rls_isolation_and_pool_non_leakage():
    if IS_SQLITE:
        pytest.skip("Teste específico para PostgreSQL com RLS ativo.")

    # Fail-closed sem contexto
    async with SessionLocal() as s:
        async with s.begin():
            cnt = (await s.execute(text('SELECT COUNT(*) FROM "QuestoesBanco"'))).scalar()
            assert cnt == 0

    # Tenant 1 vs Tenant 2 na mesma pool
    async with SessionLocal() as s1:
        async with s1.begin():
            await set_tenant_context(s1, 1, bypass_rls=False)
            c1 = (await s1.execute(text("SELECT COUNT(*) FROM company_data"))).scalar()
            assert c1 == 1
            upd = await s1.execute(text("UPDATE company_data SET company_name = 'X' WHERE tenant_id = 2"))
            assert upd.rowcount == 0

    async with SessionLocal() as s2:
        async with s2.begin():
            await set_tenant_context(s2, 2, bypass_rls=False)
            q2 = (await s2.execute(text('SELECT COUNT(*) FROM "QuestoesBanco"'))).scalar()
            c2 = (await s2.execute(text("SELECT COUNT(*) FROM company_data"))).scalar()
            assert q2 == 0 and c2 == 1

    # Sem vazamento na conexão seguinte
    async with SessionLocal() as s3:
        async with s3.begin():
            c3 = (await s3.execute(text("SELECT COUNT(*) FROM company_data"))).scalar()
            assert c3 == 0


@pytest.mark.asyncio
async def test_security_headers_and_rate_limiting(async_client):
    reset_rate_limits()
    h_admin = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)

    me = await async_client.get("/users/me", headers=h_admin)
    assert me.status_code == 200
    assert me.headers.get("X-Content-Type-Options") == "nosniff"
    assert me.headers.get("X-Frame-Options") == "DENY"
    assert me.headers.get("Cache-Control") == "no-store"

    # 5 tentativas permitidas na rota validar-senha; 6ª deve retornar 429
    for _ in range(5):
        r = await async_client.post(
            "/api/export/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/validar-senha",
            headers=h_admin,
            json={"senha": "errada"},
        )
        assert r.status_code == 200
    r6 = await async_client.post(
        "/api/export/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440/validar-senha",
        headers=h_admin,
        json={"senha": "errada"},
    )
    assert r6.status_code == 429
    assert "Retry-After" in r6.headers
    reset_rate_limits()


def test_lgpd_pii_encryption_and_masking():
    raw_cpf = "12345678901"
    enc = encrypt_pii(raw_cpf)
    assert enc is not None and enc != raw_cpf and enc.startswith("gAAAAA")
    # Não deve criptografar duas vezes
    assert encrypt_pii(enc) == enc
    assert safe_decrypt_pii(enc) == raw_cpf
    # Compatibilidade com legado em texto claro
    assert safe_decrypt_pii("legado_plain") == "legado_plain"
    assert mask_pii(raw_cpf, keep_last=2) == "*********01"


@pytest.mark.asyncio
async def test_health_request_id_and_biblioteca_tenant_isolation(async_client):
    h_resp = await async_client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["database"] == "ready"
    assert "X-Request-ID" in h_resp.headers

    # Biblioteca real: Tenant 1 tem questões, Tenant 2 tem 0 questões
    h_t1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    h_t2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)

    b1 = await async_client.post("/api/biblioteca", headers=h_t1, json={"busca": "a", "limite": 5})
    assert b1.status_code == 200 and b1.json()["success"] is True and b1.json()["total"] >= 1

    b2 = await async_client.post("/api/biblioteca", headers=h_t2, json={"busca": "a", "limite": 5})
    assert b2.status_code == 200 and b2.json()["total"] == 0


@pytest.mark.asyncio
async def test_storage_path_traversal_and_export_jobs_tenant_isolation(async_client, tmp_path):
    store = LocalStorageBackend(str(tmp_path))
    store.save_bytes("tenant_1/prova.txt", b"conteudo")
    assert store.read_bytes("tenant_1/prova.txt") == b"conteudo"
    with pytest.raises(ValueError):
        store.resolve_path("../escape.txt")

    job = create_job(tenant_id=1, user="admin1", tipo="teste", params={})
    h_t1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    h_t2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    h_prof = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)

    assert (await async_client.get(f"/api/export/jobs/{job['job_id']}", headers=h_t1)).status_code == 200
    assert (await async_client.get(f"/api/export/jobs/{job['job_id']}", headers=h_t2)).status_code == 404
    assert (await async_client.get(f"/api/export/jobs/{job['job_id']}", headers=h_prof)).status_code == 403
