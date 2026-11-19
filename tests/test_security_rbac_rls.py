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


# --------------------------------------------------------------------------- integridade de tenant e admin geral
@pytest.mark.asyncio
async def test_tenant_change_without_reencryption_is_blocked_by_database():
    import uuid
    from sqlalchemy.exc import DBAPIError
    from backend.app.db_models import Disciplina
    did = "ci-disc-" + uuid.uuid4().hex[:8]
    async with PlatformSessionLocal() as p:
        p.add(Disciplina(id_disciplina=did, nome_disciplina="Física", descricao="x", tenant_id=1))
        await p.commit()
        # SQL direto mantendo a cifra antiga: o banco recusa
        with pytest.raises(DBAPIError) as exc:
            await p.execute(text('UPDATE "Disciplinas" SET tenant_id = 2 WHERE id_disciplina = :i'), {"i": did})
        assert "sem recifrar" in str(exc.value)
        await p.rollback()
        # pelo ORM a troca recifra tudo e é aceita; o valor continua legível no novo cliente
        d = (await p.execute(select(Disciplina).where(Disciplina.id_disciplina == did))).scalars().first()
        d.tenant_id = 2
        await p.commit()
    async with SessionLocal() as s:
        async with s.begin():
            await set_tenant_context(s, 2)
            d2 = (await s.execute(select(Disciplina).where(Disciplina.id_disciplina == did))).scalars().first()
            assert d2 is not None and d2.nome_disciplina == "Física"
            await s.delete(d2)


@pytest.mark.asyncio
async def test_admin_geral_must_choose_valid_tenant_to_create_event(async_client):
    h = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    base = {"nome_evento": "Evento AG", "data_prova": "2027-03-01", "status": "Aberto",
            "senha_evento": "x1", "qtd_cargos": 1}
    assert (await async_client.post("/eventos/", headers=h, json={**base, "tenant_id": 999})).status_code == 400
    ok = await async_client.post("/eventos/", headers=h, json={**base, "tenant_id": 2})
    assert ok.status_code == 200 and ok.json()["tenant_id"] == 2
    me = await async_client.get("/users/me", headers=h)
    assert me.status_code == 200 and me.json()["tenant_id"] is None   # admin geral não vira cliente 1
    # admin de cliente continua preso ao próprio cliente, mesmo pedindo outro
    h1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    r = await async_client.post("/eventos/", headers=h1, json={**base, "nome_evento": "Evento T1", "tenant_id": 2})
    assert r.status_code == 200 and r.json()["tenant_id"] == 1


@pytest.mark.asyncio
async def test_admin_geral_global_view_and_managed_client_isolation(async_client):
    """Admin geral: visão global enxerga tudo; com um cliente em gestão, vê e grava só nele (sob RLS)."""
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)

    # visão global: usuários de todos os clientes
    todos = await async_client.get("/users/", headers=ag)
    assert todos.status_code == 200
    assert {1, 2} <= {u["tenant_id"] for u in todos.json()}

    # cliente em gestão = 2: só dados do cliente 2, e /users/me reflete o cliente escolhido
    ag2 = {**ag, "X-Tenant-Id": "2"}
    me = await async_client.get("/users/me", headers=ag2)
    assert me.status_code == 200 and me.json()["tenant_id"] == 2
    usuarios = await async_client.get("/users/", headers=ag2)
    assert usuarios.status_code == 200 and {u["tenant_id"] for u in usuarios.json()} == {2}
    eventos = await async_client.get("/eventos/", headers=ag2)
    assert eventos.status_code == 200 and all(e["tenant_id"] == 2 for e in eventos.json())
    # o evento do cliente 1 não existe para quem está gerenciando o cliente 2
    ev1 = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
    assert (await async_client.get(f"/eventos/{ev1}", headers=ag2)).status_code == 404

    # criar com cliente em gestão vai sempre para ele, mesmo que o corpo peça outro
    base = {"nome_evento": "Evento Gestao", "data_prova": "2027-04-01", "status": "Aberto",
            "senha_evento": "x1", "qtd_cargos": 1}
    r = await async_client.post("/eventos/", headers=ag2, json={**base, "tenant_id": 1})
    assert r.status_code == 200 and r.json()["tenant_id"] == 2

    # cliente inexistente ou inválido no cabeçalho: recusado, nunca cai num cliente padrão
    for ruim in ("999", "abc", "0", "-1"):
        assert (await async_client.get("/users/me", headers={**ag, "X-Tenant-Id": ruim})).status_code == 400

    # o cabeçalho não dá nada a quem não é admin geral: admin do cliente 1 continua no cliente 1
    a1 = {**auth_headers("admin1", UserRole.ADMIN, tenant_id=1), "X-Tenant-Id": "2"}
    me1 = await async_client.get("/users/me", headers=a1)
    assert me1.status_code == 200 and me1.json()["tenant_id"] == 1
    assert {u["tenant_id"] for u in (await async_client.get("/users/", headers=a1)).json()} == {1}
    assert (await async_client.get("/admin/clients", headers=a1)).status_code == 403

    # gestão de clientes é sempre global, mesmo com um cliente escolhido
    clientes = await async_client.get("/admin/clients", headers=ag2)
    assert clientes.status_code == 200 and {1, 2} <= {c["id"] for c in clientes.json()}
    # usuário de cliente lê só o próprio cliente (antes quebrava com 500 na camada de cifra)
    assert (await async_client.get("/admin/clients/1", headers=a1)).status_code == 200
    assert (await async_client.get("/admin/clients/2", headers=a1)).status_code == 403


@pytest.mark.asyncio
async def test_question_types_create_edit_review_and_professor_contents(async_client):
    """Regressão: Certo/Errado (com imagem no item), Discursiva/Subjetiva e revisão falhavam com 500."""
    import json as _json, struct, zlib

    def _png():
        def ch(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                + ch(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + ch(b"IEND", b""))

    h = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    ev, ct = "c2438719-23aa-4f7d-8e0f-e6a310c10440", "ci-conteudo-1"
    base = f"/eventos/{ev}/conteudos/{ct}/questoes"
    alts = _json.dumps([{"letra": L, "texto": f"<p>{L}</p>", "correta": L == "A"} for L in "ABCDE"])
    comum = {"indicacao_conteudo": "1", "enunciado": "<p>e</p>", "alternativas": alts, "nivel_dificuldade": "MEDIO",
             "pontuacao": "1", "tags": "", "justificativa_questao": "", "justificativa_anulacao": "", "resposta_correta": "A",
             "texto_referencia_vinculo": "", "texto_referencia_direto": "", "tenant_id": "1"}

    # Certo/Errado com imagem no item: cria, devolve itens e imagem (URL assinada)
    itens = _json.dumps([{"afirmacao": "<p>i1</p>", "valor_correto": True}, {"afirmacao": "<p>i2</p>", "valor_correto": False}])
    r = await async_client.post(base, headers=h, data={**comum, "tipo": "CERTO_ERRADO", "anulada": "false", "itens_vf": itens},
                                files={"item_imagem_0": ("i.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    qce = r.json()["id_questao"]
    d = (await async_client.get(f"{base}/{qce}", headers=h)).json()
    assert [i["valor_correto"] for i in d["itens_vf"]] == [True, False]
    assert str(d["itens_vf"][0]["imagem_path_item"]).startswith("api/files/1/")

    # revisão de Certo/Errado mantém itens e imagem
    dados = {"tipo": "CERTO_ERRADO", "itens_comando": ["<p>i1</p>", "<p>i2</p>"], "respostas_certo_errado": ["CERTO", "ERRADO"],
             "alternativas": [], "enunciado": "<p>e</p>"}
    rv = {"status_revisao": "APROVADA", "observacao_revisor": "", "usuario_revisor": "admin1", "tenant_id": "1"}
    assert (await async_client.patch(f"{base}/{qce}/revisao", headers=h, data={**rv, "dados_revisao": _json.dumps(dados)})).status_code == 200
    d = (await async_client.get(f"{base}/{qce}", headers=h)).json()
    assert len(d["itens_vf"]) == 2 and d["itens_vf"][0]["imagem_path_item"]

    # Discursiva e Subjetiva: criar e revisar (num_linhas vazio na subjetiva não pode derrubar)
    for tipo, det in (("DISCURSIVA", {"palavras_chave_resposta": ["a", "b"], "numero_linhas_resposta": 15}),
                      ("SUBJETIVA", {"palavras_chave_resposta": [], "texto_subjetivo_orientacao": "o", "texto_subjetivo_nota_maxima": "10"})):
        r = await async_client.post(base, headers=h, data={**comum, "tipo": tipo, "detalhes_discursiva": _json.dumps(det)})
        assert r.status_code == 200, r.text
        q = r.json()["id_questao"]
        dados = {"tipo": tipo, "itens_comando": [""], "palavras_chave_discursiva": "a, b" if tipo == "DISCURSIVA" else "",
                 "num_linhas_discursiva": 15 if tipo == "DISCURSIVA" else "", "texto_subjetivo_orientacao": det.get("texto_subjetivo_orientacao", ""),
                 "texto_subjetivo_nota_maxima": det.get("texto_subjetivo_nota_maxima", ""), "alternativas": []}
        assert (await async_client.patch(f"{base}/{q}/revisao", headers=h, data={**rv, "dados_revisao": _json.dumps(dados)})).status_code == 200
        dd = (await async_client.get(f"{base}/{q}", headers=h)).json()["detalhes_discursiva"]
        if tipo == "DISCURSIVA":
            assert dd["palavras_chave_resposta"] == ["a", "b"] and dd["numero_linhas_resposta"] == 15

    # revisar uma múltipla escolha (a tela manda itens_comando [""]) não cria itens Certo/Errado
    r = await async_client.post(base, headers=h, data={**comum, "tipo": "MULTIPLA_ESCOLHA", "anulada": "false"})
    qme = r.json()["id_questao"]
    dados = {"tipo": "MULTIPLA_ESCOLHA", "itens_comando": [""], "respostas_certo_errado": [""], "alternativas": [], "enunciado": "<p>e</p>"}
    assert (await async_client.patch(f"{base}/{qme}/revisao", headers=h, data={**rv, "dados_revisao": _json.dumps(dados)})).status_code == 200
    assert (await async_client.get(f"{base}/{qme}", headers=h)).json()["itens_vf"] == []

    # professor: "Meus Conteúdos" e conteúdos do evento (professor_id é texto no banco)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    assert (await async_client.get("/conteudos/meus", headers=hp)).status_code == 200
    assert (await async_client.get(f"/conteudos/eventos/{ev}/conteudos", headers=hp)).status_code == 200


@pytest.mark.asyncio
async def test_finished_exam_and_answer_key_require_event_password(async_client):
    """Prova pronta e gabarito: só com a senha do evento (cabeçalho), com bloqueio após erros."""
    reset_rate_limits()
    ev = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
    h = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    cargos = (await async_client.get(f"/eventos/{ev}/cargos", headers=h)).json()
    cargo = cargos[0]["id_cargo"] if cargos else "qualquer"
    url_gab = f"/api/gabarito/eventos/{ev}/cargos/{cargo}/gabarito"

    # sem senha / senha errada: recusado (403); a senha não vale mais na URL
    assert (await async_client.get(url_gab, headers=h)).status_code == 403
    assert (await async_client.get(url_gab, headers={**h, "X-Senha-Evento": "errada"})).status_code == 403
    assert (await async_client.post(f"/api/gabarito/eventos/{ev}/exportar-gabaritos-zip?senha=1234", headers=h)).status_code == 403
    for rota in (f"/api/export/download?evento_id={ev}&cargo_id={cargo}&tipo=gabarito",):
        assert (await async_client.get(rota, headers=h)).status_code == 403
    for rota in (f"/api/export/eventos/{ev}/cargos/{cargo}/exportar-gabarito", f"/api/export/eventos/{ev}/cargos/{cargo}/gerar-arquivos"):
        assert (await async_client.post(rota, headers=h, json={})).status_code == 403
    # senha certa: passa da trava (o resultado depende de haver prova montada, mas nunca é 403)
    r = await async_client.get(url_gab, headers={**h, "X-Senha-Evento": "1234"})
    assert r.status_code != 403, r.text
    assert (await async_client.post(f"/api/export/eventos/{ev}/validar-senha", headers=h, json={"senha": "1234"})).json() == {"valida": True}

    # detalhes do evento: senha errada = 403 (nunca 401, que o app trata como sessão expirada e desloga)
    assert (await async_client.get(f"/eventos/{ev}/detalhes?senha=errada", headers=h)).status_code == 403
    r = await async_client.get(f"/eventos/{ev}/detalhes?senha=1234", headers=h)
    assert r.status_code == 200 and r.json()["nome_evento"] == "Evento CI Teste", r.text

    # outro cliente nunca chega à senha (evento não existe para ele)
    h2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    assert (await async_client.get(url_gab, headers={**h2, "X-Senha-Evento": "1234"})).status_code == 404

    # bloqueio: 5 erros em 10 min travam até a senha certa (por usuário + evento)
    reset_rate_limits()
    for _ in range(5):
        assert (await async_client.get(url_gab, headers={**h, "X-Senha-Evento": "x"})).status_code == 403
    assert (await async_client.get(url_gab, headers={**h, "X-Senha-Evento": "1234"})).status_code == 429
    reset_rate_limits()


def test_generator_refuses_ciphertext():
    from fastapi import HTTPException as _HTTPExc
    from backend.app.security import exigir_texto_claro
    exigir_texto_claro([{"questoes": [{"enunciado": "<p>Quanto é 2+2?</p>"}]}])
    for lixo in ("gAAAAA" + "B" * 60 + "==", "e1.1." + "x" * 40):
        with pytest.raises(_HTTPExc) as exc:
            exigir_texto_claro([{"questoes": [{"enunciado": lixo}]}])
        assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_cors_preflight_allows_app_custom_headers(async_client):
    """O navegador só envia X-Senha-Evento / X-Tenant-Id se o pré-voo CORS os permitir."""
    for metodo, rota in (("GET", "/api/gabarito/eventos/x/cargos/y/gabarito"), ("POST", "/api/gabarito/eventos/x/exportar-gabaritos-zip"), ("GET", "/users/me")):
        r = await async_client.options(rota, headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": metodo,
                                                      "Access-Control-Request-Headers": "authorization,x-senha-evento,x-tenant-id"})
        assert r.status_code == 200, (rota, r.status_code, r.text)


def test_exam_seed_is_secret_reproducible_and_legacy_compatible():
    """Semente: com segredo gravado é imprevisível e estável; sem segredo, mantém a fórmula antiga."""
    import logging as _lg
    from core.document_generator import DocxProofGenerator, rotulo_variacao

    def gerador(meta):
        g = DocxProofGenerator.__new__(DocxProofGenerator)
        g.prova_montada = {"metadados_prova": meta}
        g.logger = _lg.getLogger("t")
        return g

    antigo = gerador({})
    assert antigo._semente("1-TOTAL") == "1-TOTAL"  # prova antiga: idêntica ao que já foi exportado
    s1, s2 = gerador({"semente_gabarito": "a" * 64}), gerador({"semente_gabarito": "b" * 64})
    seq = lambda g: g.gerar_gabarito_balanceado(30, seed=g._semente("1-TOTAL"))
    assert seq(s1) == seq(s1)                      # mesma prova: sempre igual
    assert seq(s1) != seq(s2)                      # provas diferentes: gabaritos diferentes
    assert seq(s1) != seq(antigo)                  # não é a sequência previsível antiga
    assert gerador('{"semente_gabarito": "' + "a" * 64 + '"}')._semente("x") == s1._semente("x")  # JSON em texto
    assert rotulo_variacao(1, 1) == "PADRÃO" and rotulo_variacao(2, 3) == "Tipo B"


@pytest.mark.asyncio
async def test_export_preferences_and_precheck_endpoints(async_client):
    ev = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
    h = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    r = await async_client.put(f"/api/export/eventos/{ev}/preferencias", headers=h,
                               json={"fonte": "Arial", "tamanhoFonte": 20, "duasColunas": True, "exibir_gabarito_marcado": True})
    assert r.status_code == 200 and r.json() == {"fonte": "Arial", "tamanhoFonte": 20, "duasColunas": True}
    assert (await async_client.get(f"/api/export/eventos/{ev}/preferencias", headers=h)).json()["tamanhoFonte"] == 20
    for ruim in ({"tamanhoFonte": 500}, {"tamanhoFonte": "12"}, {"duasColunas": "sim"}, {"fonte": ""}):
        assert (await async_client.put(f"/api/export/eventos/{ev}/preferencias", headers=h, json=ruim)).status_code == 400
    # professor não mexe no padrão; outro cliente não enxerga o evento
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    assert (await async_client.get(f"/api/export/eventos/{ev}/preferencias", headers=hp)).status_code == 403
    h2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    assert (await async_client.get(f"/api/export/eventos/{ev}/preferencias", headers=h2)).status_code == 404
    # checagem: exige cargos; cargo sem prova montada aparece como bloqueio
    assert (await async_client.post(f"/api/export/eventos/{ev}/verificar", headers=h, json={"cargos_id": []})).status_code == 400
    r = await async_client.post(f"/api/export/eventos/{ev}/verificar", headers=h, json={"cargos_id": ["inexistente"]})
    assert r.status_code == 200 and r.json()[0]["bloqueios"]


def test_generator_renders_editor_html_inline_and_answer_lines():
    """Alternativas/itens do editor (HTML) saem sem tags e com formatação; Subjetiva tem N linhas."""
    import logging as _lg
    from docx import Document as _Doc
    from docx.oxml.ns import qn as _qn
    from core.document_generator import DocxProofGenerator

    g = DocxProofGenerator.__new__(DocxProofGenerator)
    g.format_options, g.logger, g.prova_montada = {}, _lg.getLogger("t"), {}
    doc = _Doc()
    p = doc.add_paragraph("A)\t")
    g._add_html_inline(p, "<p>Texto <strong>forte</strong> e H<sub>2</sub>O</p><p>segunda</p>")
    assert "<" not in p.text and "Texto forte e H2O" in p.text and "segunda" in p.text
    assert any(r.bold and r.text == "forte" for r in p.runs)
    assert any(r.font.subscript and r.text == "2" for r in p.runs)
    assert g._texto_simples("<p></p>") == ""            # alternativa só com imagem = sem texto
    antes = len(doc.paragraphs)
    g._add_linhas_resposta(doc, 7)
    novas = doc.paragraphs[antes:]
    assert sum(1 for q in novas if q._p.pPr is not None and q._p.pPr.find(_qn("w:pBdr")) is not None) == 7


@pytest.mark.asyncio
async def test_two_factor_is_mandatory_for_everyone(async_client):
    """Senha certa não libera acesso; 2FA obrigatório (cadastro, verificação, reuso, recuperação, bloqueio, reset)."""
    import pyotp
    from backend.app.auth import create_access_token as _cat
    reset_rate_limits()
    login = lambda: async_client.post("/auth/login", data={"username": "vhugo1234", "password": "TestPassword123!", "recaptcha_token": "x"})

    r = (await login()).json()
    assert r["etapa"] == "cadastro_2fa" and "access_token" not in r
    passe = r["token_2fa"]
    # o passe de 2FA não abre nada
    assert (await async_client.get("/users/me", headers={"Authorization": f"Bearer {passe}"})).status_code == 401
    # token antigo (sem a marca de 2FA) também não
    velho = _cat({"sub": "vhugo1234", "role": "diagramador", "tenant_id": 1})
    assert (await async_client.get("/users/me", headers={"Authorization": f"Bearer {velho}"})).status_code == 401

    cad = (await async_client.post("/auth/2fa/cadastro/iniciar", json={"token_2fa": passe})).json()
    assert cad["qr_code"].startswith("data:image/png;base64,")
    totp = pyotp.TOTP(cad["segredo"])
    assert (await async_client.post("/auth/2fa/cadastro/confirmar", json={"token_2fa": passe, "codigo": "000000"})).status_code == 400
    codigo_usado = totp.now()
    ok = (await async_client.post("/auth/2fa/cadastro/confirmar", json={"token_2fa": passe, "codigo": codigo_usado})).json()
    assert len(ok["codigos_recuperacao"]) == 10 and ok["access_token"]
    h = {"Authorization": f"Bearer {ok['access_token']}"}
    me = (await async_client.get("/users/me", headers=h)).json()
    assert me["totp_ativo"] is True and "totp_secret" not in me and "codigos_recuperacao" not in me

    # próximo login pede o código; o mesmo código não vale duas vezes
    r = (await login()).json()
    assert r["etapa"] == "2fa"
    reuso = await async_client.post("/auth/2fa/verificar", json={"token_2fa": r["token_2fa"], "codigo": codigo_usado})
    assert reuso.status_code == 400
    # código de recuperação: vale uma vez
    cod = ok["codigos_recuperacao"][0]
    v = (await async_client.post("/auth/2fa/verificar", json={"token_2fa": r["token_2fa"], "codigo": cod})).json()
    assert v["access_token"] and v["codigos_recuperacao_restantes"] == 9
    assert (await async_client.post("/auth/2fa/verificar", json={"token_2fa": r["token_2fa"], "codigo": cod})).status_code == 400

    # bloqueio depois de erros seguidos
    reset_rate_limits()
    r = (await login()).json()
    for _ in range(5):
        assert (await async_client.post("/auth/2fa/verificar", json={"token_2fa": r["token_2fa"], "codigo": "123456"})).status_code == 400
    assert (await async_client.post("/auth/2fa/verificar", json={"token_2fa": r["token_2fa"], "codigo": totp.now()})).status_code == 429
    reset_rate_limits()

    # reset pelo administrador do cliente; ninguém reseta o próprio
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    usuarios = (await async_client.get("/users/", headers=a1)).json()
    alvo = next(u for u in usuarios if u["username"] == "vhugo1234")
    eu = next(u for u in usuarios if u["username"] == "admin1")
    assert (await async_client.post(f"/users/{eu['id']}/2fa/resetar", headers=a1)).status_code == 403
    assert (await async_client.post(f"/users/{alvo['id']}/2fa/resetar", headers=a1)).status_code == 204
    assert (await login()).json()["etapa"] == "cadastro_2fa"
    # admin de outro cliente não alcança o usuário
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    assert (await async_client.post(f"/users/{alvo['id']}/2fa/resetar", headers=a2)).status_code == 404
    reset_rate_limits()


def test_password_policy_rules():
    from backend.app import politica_senha as ps
    assert ps.problemas("Curta1!") and ps.problemas("somenteminusculas") and ps.problemas("Senha123!@#")
    assert ps.problemas("Joaozinho#2026x", username="joaozinho")          # contém o usuário
    assert ps.problemas("Abc123456789!")                                   # sequência
    assert not ps.problemas("Verde-Montanha-77", username="maria", email="maria@x.com")


@pytest.mark.asyncio
async def test_forced_password_change_session_renewal_and_recaptcha(async_client, monkeypatch):
    import pyotp, time
    from backend.app.auth import create_access_token as _cat
    from backend.app.routes import auth as rauth
    reset_rate_limits()
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    base = {"username": "novo_prof", "email": "novo_prof@example.com", "role": "professor", "tenant_id": 1, "status": "ativo"}
    # senha fraca recusada já na criação
    r = await async_client.post("/users/", headers=a1, json={**base, "password": "fraca123"})
    assert r.status_code == 400 and r.json()["detail"]["problemas"]
    provisoria = "Provisoria-Forte-48"
    assert (await async_client.post("/users/", headers=a1, json={**base, "password": provisoria})).status_code == 201

    login = lambda s: async_client.post("/auth/login", data={"username": "novo_prof", "password": s, "recaptcha_token": "x"})
    r = (await login(provisoria)).json()
    cad = (await async_client.post("/auth/2fa/cadastro/iniciar", json={"token_2fa": r["token_2fa"]})).json()
    totp = pyotp.TOTP(cad["segredo"])
    ok = (await async_client.post("/auth/2fa/cadastro/confirmar", json={"token_2fa": r["token_2fa"], "codigo": totp.now()})).json()
    # 2FA ok, mas a senha é provisória: troca antes de entrar (sem token de acesso ainda)
    assert ok["etapa"] == "trocar_senha" and "access_token" not in ok and len(ok["codigos_recuperacao"]) == 10
    passe = ok["token_2fa"]
    assert (await async_client.get("/users/me", headers={"Authorization": f"Bearer {passe}"})).status_code == 401
    assert (await async_client.post("/auth/senha/trocar", json={"token_2fa": passe, "nova_senha": "fraca"})).status_code == 400
    assert (await async_client.post("/auth/senha/trocar", json={"token_2fa": passe, "nova_senha": provisoria})).status_code == 400  # repetida
    nova = "Nova-Senha-Segura-91"
    t = (await async_client.post("/auth/senha/trocar", json={"token_2fa": passe, "nova_senha": nova})).json()
    assert t["access_token"]
    # senha antiga não entra mais; a nova entra direto no 2FA (sem nova troca)
    assert (await login(provisoria)).status_code == 401
    assert "trocar" not in str((await login(nova)).json())

    # trocar a própria senha exige a senha atual E o código do autenticador
    h = {"Authorization": f"Bearer {t['access_token']}"}
    r = await async_client.post("/auth/senha/minha", headers=h, json={"senha_atual": "errada", "nova_senha": "Outra-Senha-Boa-55", "codigo": "000000"})
    assert r.status_code == 400

    # renovação da sessão: mantém o login; passa de 12 h, cai
    r = await async_client.post("/auth/renovar", headers=h)
    assert r.status_code == 200 and r.json()["access_token"]
    velho = _cat({"sub": "novo_prof", "role": "professor", "tenant_id": 1, "mfa": True, "auth_time": int(time.time()) - 13 * 3600})
    assert (await async_client.post("/auth/renovar", headers={"Authorization": f"Bearer {velho}"})).status_code == 401

    # reCAPTCHA falha fechada: sem chave, login recusado
    monkeypatch.setattr(rauth, "RECAPTCHA_DESATIVADO", False)
    monkeypatch.setattr(rauth, "RECAPTCHA_SECRET_KEY", "")
    assert (await login(nova)).status_code == 400
    reset_rate_limits()


@pytest.mark.asyncio
async def test_platform_and_bank_settings_take_effect(async_client):
    import json as _json
    reset_rate_limits()
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    ev = "c2438719-23aa-4f7d-8e0f-e6a310c10440"

    # plataforma: só admin geral; limites validados
    assert (await async_client.get("/config/plataforma", headers=a1)).status_code == 403
    r = await async_client.put("/config/plataforma", headers=ag, json={"seguranca": {"senha_tamanho_minimo": 4}})
    assert r.status_code == 400 and r.json()["detail"]["problemas"]
    r = await async_client.put("/config/plataforma", headers=ag, json={"seguranca": {"senha_tamanho_minimo": 16, "sessao_inatividade_minutos": 20}})
    assert r.status_code == 200 and r.json()["seguranca"]["senha_tamanho_minimo"] == 16
    try:
        assert (await async_client.get("/auth/senha/regras")).json()["tamanho_minimo"] == 16
        r = await async_client.post("/users/", headers=a1, json={"username": "cfg_u", "email": "cfg_u@example.com", "password": "Doze-Chars-9x",
                                                                 "role": "professor", "tenant_id": 1, "status": "ativo"})
        assert r.status_code == 400  # 13 caracteres < 16 configurado
        # banca: não pode passar do teto da plataforma; pode encurtar
        assert (await async_client.put("/config/banca", headers=a1, json={"seguranca": {"sessao_inatividade_minutos": 45}})).status_code == 400
        assert (await async_client.put("/config/banca", headers=a1, json={"seguranca": {"sessao_inatividade_minutos": 10}})).status_code == 200
        assert (await async_client.get("/config/sessao", headers=a1)).json()["inatividade_minutos"] == 10
        assert (await async_client.post("/auth/renovar", headers=a1)).json()["inatividade_minutos"] == 10
        # outro cliente não enxerga nem herda a configuração do cliente 1
        assert (await async_client.get("/config/sessao", headers=a2)).json()["inatividade_minutos"] == 20
        assert (await async_client.get("/config/banca", headers=a2)).json()["seguranca"]["sessao_inatividade_minutos"] is None
        # professor não altera a banca
        hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
        assert (await async_client.put("/config/banca", headers=hp, json={})).status_code == 403

        # regras: tipo desabilitado é recusado; revisão obrigatória vira bloqueio na checagem
        assert (await async_client.put("/config/banca", headers=a1, json={"regras_questoes": {"tipos_permitidos": ["MULTIPLA_ESCOLHA"], "revisao_obrigatoria": True}})).status_code == 200
        assert (await async_client.get("/config/regras-questoes", headers=hp)).json()["tipos_permitidos"] == ["MULTIPLA_ESCOLHA"]
        base = {"indicacao_conteudo": "1", "enunciado": "<p>e</p>", "alternativas": "[]", "nivel_dificuldade": "MEDIO", "pontuacao": "1",
                "tags": "", "justificativa_questao": "", "justificativa_anulacao": "", "resposta_correta": "", "texto_referencia_vinculo": "",
                "texto_referencia_direto": "", "tenant_id": "1", "anulada": "false",
                "itens_vf": _json.dumps([{"afirmacao": "<p>i</p>", "valor_correto": True}])}
        r = await async_client.post(f"/eventos/{ev}/conteudos/ci-conteudo-1/questoes", headers=a1, data={**base, "tipo": "CERTO_ERRADO"})
        assert r.status_code == 400

        # identidade da prova: validação das regras de instrução
        r = await async_client.put("/config/banca", headers=a1, json={"identidade_prova": {"instrucoes_por_bloco": [{"contem": "", "instrucoes": []}]}})
        assert r.status_code == 400
        r = await async_client.put("/config/banca", headers=a1, json={"identidade_prova": {"instrucoes_por_bloco": [{"contem": "português", "instrucoes": ["Leia com atenção."]}], "instrucoes_discursiva": []}})
        assert r.status_code == 200 and r.json()["identidade_prova"]["instrucoes_por_bloco"][0]["contem"] == "português"
    finally:
        await async_client.put("/config/plataforma", headers=ag, json={"seguranca": {"senha_tamanho_minimo": 12, "sessao_inatividade_minutos": 30}})
        await async_client.put("/config/banca", headers=a1, json={"seguranca": {"sessao_inatividade_minutos": None},
                                                                  "regras_questoes": {"tipos_permitidos": ["MULTIPLA_ESCOLHA", "CERTO_ERRADO", "DISCURSIVA", "SUBJETIVA"], "revisao_obrigatoria": False}})
        reset_rate_limits()
