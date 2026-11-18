import os
import pytest
from sqlalchemy import text

from backend.app.database import PlatformSessionLocal, SessionLocal, set_tenant_context
from backend.app.jobs import create_job
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from backend.app.storage import LocalStorageBackend
from backend.app.utils_crypto import mask_pii
from backend.app import field_crypto as fc
from backend.app.field_crypto import blind_eq
from backend.app.db_models import Company, User
from sqlalchemy import select, update
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
    # Fail-closed sem contexto
    async with SessionLocal() as s:
        async with s.begin():
            cnt = (await s.execute(text('SELECT COUNT(*) FROM "QuestoesBanco"'))).scalar()
            assert cnt == 0

    # Tenant 1 vs Tenant 2 na mesma pool
    async with SessionLocal() as s1:
        async with s1.begin():
            await set_tenant_context(s1, 1)
            c1 = (await s1.execute(text("SELECT COUNT(*) FROM company_data"))).scalar()
            assert c1 == 1
            upd = await s1.execute(text("UPDATE company_data SET company_name = 'X' WHERE tenant_id = 2"))
            assert upd.rowcount == 0

    async with SessionLocal() as s2:
        async with s2.begin():
            await set_tenant_context(s2, 2)
            q2 = (await s2.execute(text('SELECT COUNT(*) FROM "QuestoesBanco"'))).scalar()
            c2 = (await s2.execute(text("SELECT COUNT(*) FROM company_data"))).scalar()
            assert q2 == 0 and c2 == 1

    # Sem vazamento na conexão seguinte
    async with SessionLocal() as s3:
        async with s3.begin():
            c3 = (await s3.execute(text("SELECT COUNT(*) FROM company_data"))).scalar()
            assert c3 == 0


@pytest.mark.asyncio
async def test_runtime_role_cannot_bypass_rls_via_session_variable():
    """Regressão: antes, `SET app.bypass_rls = 'on'` liberava todos os tenants para a role de runtime."""
    async with SessionLocal() as s:
        async with s.begin():
            role = (await s.execute(text("SELECT current_user"))).scalar()
            bypass = (await s.execute(text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user"))).scalar()
            assert bypass is False, f"{role} não pode ter BYPASSRLS"
            await set_tenant_context(s, 2)
            await s.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
            tenants = (await s.execute(text("SELECT count(DISTINCT tenant_id) FROM company_data"))).scalar()
            outros = (await s.execute(text("SELECT count(*) FROM company_data WHERE tenant_id <> 2"))).scalar()
            assert tenants == 1 and outros == 0

            # Escrita em outro tenant também é barrada (WITH CHECK)
            upd = await s.execute(text("UPDATE company_data SET company_name = company_name WHERE tenant_id = 1"))
            assert upd.rowcount == 0

    async with PlatformSessionLocal() as p:
        bypass = (await p.execute(text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user"))).scalar()
        total = (await p.execute(text("SELECT count(DISTINCT tenant_id) FROM company_data"))).scalar()
        assert bypass is True and total >= 2


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


def test_field_crypto_roundtrip_binding_and_blind_index():
    tok = fc.encrypt_value("12345678901", table="users", column="cpf", tenant_id=1)
    assert tok.startswith("e1.") and "12345678901" not in tok
    assert fc.decrypt_value(tok, table="users", column="cpf", tenant_id=1) == "12345678901"
    # nonce aleatório: mesmo valor gera cifras diferentes
    assert tok != fc.encrypt_value("12345678901", table="users", column="cpf", tenant_id=1)
    # valor não pode ser movido de tenant, coluna ou tabela, nem adulterado
    for kw in ({"table": "users", "column": "cpf", "tenant_id": 2},
               {"table": "users", "column": "pix_key", "tenant_id": 1},
               {"table": "company_data", "column": "cpf", "tenant_id": 1}):
        with pytest.raises(fc.FieldCryptoError):
            fc.decrypt_value(tok, **kw)
    tampered = tok[:-2] + ("A" if tok[-2] != "A" else "B") + tok[-1]
    with pytest.raises(fc.FieldCryptoError):
        fc.decrypt_value(tampered, table="users", column="cpf", tenant_id=1)
    # índice cego por tenant: o mesmo valor em clientes diferentes não é correlacionável
    b1 = fc.compute_blind_indexes("Disciplinas", {"nome_disciplina": "Matemática"}, 1)["nome_disciplina_bidx"]
    b2 = fc.compute_blind_indexes("Disciplinas", {"nome_disciplina": "Matemática"}, 2)["nome_disciplina_bidx"]
    assert b1 and b2 and b1 != b2
    assert mask_pii("12345678901", keep_last=2) == "*********01"


@pytest.mark.asyncio
async def test_database_stores_only_ciphertext_and_orm_returns_plaintext():
    checks = [("users", "username"), ("users", "email"), ("QuestoesBanco", "enunciado"),
              ("company_data", "company_name"), ("Eventos", "nome_evento"), ("Eventos", "senha_evento_cripto")]
    async with PlatformSessionLocal() as p:
        for table, col in checks:
            plain = (await p.execute(text(
                f"SELECT count(*) FROM \"{table}\" WHERE \"{col}\" IS NOT NULL AND \"{col}\" NOT LIKE 'e1.%'"))).scalar()
            total = (await p.execute(text(f'SELECT count(*) FROM "{table}" WHERE "{col}" IS NOT NULL'))).scalar()
            assert total > 0 and plain == 0, f"{table}.{col}: {plain} valores em texto claro"
        raw = (await p.execute(text("SELECT username FROM users WHERE tenant_id = 1 LIMIT 1"))).scalar()
        assert raw.startswith("e1.")
        user = (await p.execute(select(User).where(blind_eq(User.username, "admin1")))).scalars().first()
        assert user is not None and user.username == "admin1"


@pytest.mark.asyncio
async def test_plaintext_write_to_encrypted_column_is_blocked():
    async with PlatformSessionLocal() as p:
        with pytest.raises(Exception) as exc:
            await p.execute(update(Company).where(Company.tenant_id == 1).values(company_name="texto claro"))
        assert "texto claro" in str(exc.value) or "FieldCryptoError" in repr(exc.value)
        await p.rollback()


@pytest.mark.asyncio
async def test_runtime_session_refuses_rows_of_other_tenant_even_with_tampered_context():
    async with SessionLocal() as s:
        async with s.begin():
            await set_tenant_context(s, 1)
            # simula uma injeção de SQL trocando o tenant do RLS dentro da transação
            await s.execute(text("SELECT set_config('app.current_tenant_id', '2', true)"))
            with pytest.raises(fc.FieldCryptoError):
                (await s.execute(select(Company))).scalars().all()


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


# --------------------------------------------------------------------------- arquivos cifrados (fase 2)
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000100e221bc330000000049454e44ae426082"
)


def test_secure_files_store_sign_and_isolation(tmp_path, monkeypatch):
    from backend.app import secure_files as sf
    monkeypatch.setenv("DIAGPRO_FILES_DIR", str(tmp_path))
    ref = sf.store_bytes(PNG_1PX, 1, "png")
    scope, fid, _ = sf.parse_ref(ref)
    blob = (tmp_path / str(scope) / f"{fid}.bin").read_bytes()
    assert b"IHDR" not in blob and PNG_1PX not in blob          # disco guarda só cifra
    assert sf.read_bytes(ref, 1) == PNG_1PX
    with pytest.raises(sf.SecureFileError):
        sf.read_bytes(ref, 2)                                     # outro tenant não lê
    with pytest.raises(sf.SecureFileError):
        sf.store_bytes(b"<html><script>alert(1)</script>", 1, "png")  # conteúdo não é PNG
    url = sf.signed_url(ref)
    assert sf.ref_from_client(url, 1) == ref                      # URL assinada volta a ser referência
    assert sf.ref_from_client(url, 2) is None                     # mas não para outro tenant
    for forjado in ("static/../../.env", "C:/Windows/win.ini", ref.replace(":1:", ":2:"), "https://x/y.png"):
        assert sf.ref_from_client(forjado, 1) is None
    with sf.materialize({"caminho_imagem_relativo": "../../.env", "imagem_path_opcao": ref,
                         "cover_pdf_paths": ["/etc/passwd", ref]}, 1) as (m, workdir):
        assert m["caminho_imagem_relativo"] is None                # caminho arbitrário nunca chega ao gerador
        assert open(m["imagem_path_opcao"], "rb").read() == PNG_1PX
        assert len(m["cover_pdf_paths"]) == 1
    assert not os.path.exists(workdir)                             # pasta temporária apagada


@pytest.mark.asyncio
async def test_upload_returns_signed_url_and_public_folders_are_gone(async_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DIAGPRO_FILES_DIR", str(tmp_path))
    h = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    data = {"company_name": "B", "company_cnpj": "1", "company_address": "", "company_phone": "",
            "company_email": "", "company_website": ""}
    bad = await async_client.put("/company", headers=h, data=data,
                                 files={"logo": ("logo.png", b"<svg onload=alert(1)>", "image/png")})
    assert bad.status_code == 400
    ok = await async_client.put("/company", headers=h, data=data, files={"logo": ("logo.png", PNG_1PX, "image/png")})
    assert ok.status_code == 200
    url = ok.json()["company_logo_path"]
    assert url.startswith("api/files/1/") and "sig=" in url
    r = await async_client.get("/" + url)
    assert r.status_code == 200 and r.content == PNG_1PX and r.headers["cache-control"] == "private, no-store"
    assert (await async_client.get("/" + url[:-1] + ("0" if url[-1] != "0" else "1"))).status_code == 404
    assert (await async_client.get("/static/x.png")).status_code == 404
    assert (await async_client.get("/avatars/x.png")).status_code == 404


# --------------------------------------------------------------------------- saídas e logs (fase 2b)
def test_log_redaction_masks_secrets_paths_and_exam_file_names():
    from backend.app.log_redaction import redact
    linha = ('POST /api/gabarito/eventos/x/exportar-gabaritos-zip?senha=Segredo123 HTTP/1.1 '
             'GET /api/files/1/abc.png?exp=1&sig=deadbeef Bearer eyJ.abc.def '
             r"Erro ao converter 'PROVA_Concurso_X_Cargo_Y_TIPO_1.docx' em C:\Users\u\AppData\Local\Temp\d\a.pdf")
    out = redact(linha)
    for segredo in ("Segredo123", "deadbeef", "eyJ.abc.def", "Concurso_X", "Cargo_Y", "AppData"):
        assert segredo not in out, segredo
    assert redact("GET /eventos/ HTTP/1.1 200 OK") == "GET /eventos/ HTTP/1.1 200 OK"


@pytest.mark.asyncio
async def test_debug_and_disk_persisting_export_routes_were_removed(async_client):
    h = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    ev = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
    assert (await async_client.get("/debug_ping")).status_code == 404
    assert (await async_client.get("/api/export/debug_export_ping", headers=h)).status_code == 404
    assert (await async_client.get(f"/api/export/download-zip?evento_id={ev}", headers=h)).status_code == 404
    assert (await async_client.post(f"/api/export/eventos/{ev}/cargos/x/gerar-arquivos-async", headers=h)).status_code in (404, 405)
