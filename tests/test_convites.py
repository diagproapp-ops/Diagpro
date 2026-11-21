"""Convite por link, foto obrigatória, aprovação, uma conta em várias bancas e auditoria só para administradores."""
import io

import pyotp
from PIL import Image
from sqlalchemy import select

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import User, VinculoBanca
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

A1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
A2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
DIAG = auth_headers("vhugo1234", UserRole.DIAGRAMADOR, tenant_id=1)
SENHA = "Senha-Do-Professor-77"


def _foto(tamanho=(240, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", tamanho, (30, 120, 160)).save(buf, format="PNG")
    return buf.getvalue()


def _token(link: str) -> str:
    return link.rsplit("/convite/", 1)[1]


async def _codigo(totp, username="novo_prof") -> str:
    """O servidor recusa reusar o passo de 30 s; o teste faz vários logins seguidos, então libera o passo."""
    from backend.app.field_crypto import blind_eq
    async with PlatformSessionLocal() as s:
        u = (await s.execute(select(User).where(blind_eq(User.username, username)))).scalars().first()
        u.totp_ultimo_passo = None
        await s.commit()
    return totp.now()


async def _login(client, username, senha, totp=None):
    """Login real: senha -> 2FA (cadastra o autenticador na 1ª vez). Devolve (resposta final, totp)."""
    r = await client.post("/auth/login", data={"username": username, "password": senha, "recaptcha_token": "x"})
    if r.status_code != 200:
        return r, totp
    d = r.json()
    if d["etapa"] == "cadastro_2fa":
        cad = (await client.post("/auth/2fa/cadastro/iniciar", json={"token_2fa": d["token_2fa"]})).json()
        totp = pyotp.TOTP(cad["segredo"])
        r = await client.post("/auth/2fa/cadastro/confirmar", json={"token_2fa": d["token_2fa"], "codigo": totp.now()})
    else:
        r = await client.post("/auth/2fa/verificar", json={"token_2fa": d["token_2fa"], "codigo": await _codigo(totp, username)})
    return r, totp


async def _apagar(username):
    async with PlatformSessionLocal() as s:
        from backend.app.field_crypto import blind_eq
        u = (await s.execute(select(User).where(blind_eq(User.username, username)))).scalars().first()
        if u:
            for v in (await s.execute(select(VinculoBanca).where(VinculoBanca.user_id == u.id))).scalars():
                await s.delete(v)
            await s.delete(u)
            await s.commit()


async def test_invite_signup_photo_approval_and_multi_banca(async_client):
    reset_rate_limits()
    try:
        # ---- só o administrador convida; banca não cria conta com senha
        assert (await async_client.post("/convites", headers=DIAG, json={"email": "x@example.com", "role": "professor"})).status_code == 403
        r = await async_client.post("/users/", headers=A1, json={"username": "z", "email": "z@example.com", "password": SENHA,
                                                                  "role": "professor", "tenant_id": 1})
        assert r.status_code == 403
        r = await async_client.post("/convites", headers=A1, json={"email": "Novo.Prof@Example.com", "role": "professor", "nome": "Novo Prof"})
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["estado"] == "pendente" and "/convite/" in c["link"] and c["email"] == "novo.prof@example.com"
        token = _token(c["link"])
        # já é da banca: convite desnecessário
        assert (await async_client.post("/convites", headers=A1, json={"email": "p1@example.com", "role": "professor"})).status_code == 409

        # ---- página pública do link: e-mail mascarado, sem conta ainda
        info = (await async_client.get(f"/convites/publico/{token}")).json()
        assert info["banca"] == "Banca Teste 1" and info["email"].startswith("no***@") and info["conta_existente"] is False
        assert (await async_client.get("/convites/publico/token-invalido")).status_code == 410

        # ---- cadastro com os próprios dados: foto obrigatória e válida
        dados = {"username": "novo_prof", "password": SENHA, "full_name": "Novo Prof", "accepted_confidentiality": "true",
                 "accepted_data_leak": "true"}
        assert (await async_client.post(f"/convites/publico/{token}/cadastro", data=dados)).status_code == 422
        r = await async_client.post(f"/convites/publico/{token}/cadastro", data=dados,
                                    files={"foto": ("x.png", b"<script>", "image/png")})
        assert r.status_code == 400
        r = await async_client.post(f"/convites/publico/{token}/cadastro", data={**dados, "password": "fraca"},
                                    files={"foto": ("f.png", _foto(), "image/png")})
        assert r.status_code == 400
        r = await async_client.post(f"/convites/publico/{token}/cadastro", data=dados, files={"foto": ("f.png", _foto(), "image/png")})
        assert r.status_code == 201, r.text
        # link de uso único
        assert (await async_client.post(f"/convites/publico/{token}/cadastro", data=dados,
                                         files={"foto": ("f.png", _foto(), "image/png")})).status_code == 410

        # ---- pendente até o administrador aprovar
        r, _ = await _login(async_client, "novo_prof", SENHA)
        assert r.status_code == 403
        lista = (await async_client.get("/users/", headers=A1)).json()
        novo = next(u for u in lista if u["username"] == "novo_prof")
        assert novo["status"] == "pendente" and novo["tem_foto"] and novo["avatar_url"].startswith("api/files/")
        assert novo["role"] == "professor" and novo["outra_banca"] is False
        # foto guardada sem metadados, como JPEG
        async with PlatformSessionLocal() as s:
            from backend.app import secure_files
            u = (await s.execute(select(User).where(User.id == novo["id"]))).scalars().first()
            img = Image.open(io.BytesIO(secure_files.read_bytes(u.avatar_url, 1)))
            assert img.format == "JPEG" and not img.getexif()
        # o administrador não define a senha de ninguém
        assert (await async_client.patch(f"/users/{novo['id']}", headers=A1, json={"password": "Outra-Senha-Forte-1"})).status_code == 400
        assert (await async_client.patch(f"/users/{novo['id']}", headers=A1, json={"status": "ativo"})).status_code == 200
        r, totp_novo = await _login(async_client, "novo_prof", SENHA)
        assert r.status_code == 200 and r.json()["role"] == "professor" and r.json()["tenant_id"] == 1

        # ---- a mesma pessoa é convidada por OUTRA banca: aceita com a conta que já tem
        r = await async_client.post("/convites", headers=A2, json={"email": "novo.prof@example.com", "role": "revisor"})
        token2 = _token(r.json()["link"])
        assert (await async_client.get(f"/convites/publico/{token2}")).json()["conta_existente"] is True
        reset_rate_limits()  # o cadastro aceita 5 tentativas por minuto
        # cadastro novo com e-mail que já tem conta: não
        assert (await async_client.post(f"/convites/publico/{token2}/cadastro", data={**dados, "username": "outro"},
                                         files={"foto": ("f.png", _foto(), "image/png")})).status_code == 409
        errado = await async_client.post(f"/convites/publico/{token2}/aceitar", data={"username": "novo_prof", "password": "errada"})
        assert errado.status_code == 400
        sem_2fa = await async_client.post(f"/convites/publico/{token2}/aceitar", data={"username": "novo_prof", "password": SENHA,
                                                                                         "codigo": "000000"})
        assert sem_2fa.status_code == 400
        # outra conta (de outro e-mail) não aceita o convite de alguém
        assert (await async_client.post(f"/convites/publico/{token2}/aceitar",
                                         data={"username": "vhugo", "password": "TestPassword123!"})).status_code == 400
        reset_rate_limits()
        ok = await async_client.post(f"/convites/publico/{token2}/aceitar",
                                     data={"username": "novo_prof", "password": SENHA, "codigo": await _codigo(totp_novo)})
        assert ok.status_code == 200, ok.text

        # banca 2 vê a pessoa como vínculo pendente, sem dados financeiros/documentos, e não altera dados pessoais
        lista2 = (await async_client.get("/users/", headers=A2)).json()
        p2 = next(u for u in lista2 if u["username"] == "novo_prof")
        assert p2["outra_banca"] is True and p2["status"] == "pendente" and p2["role"] == "revisor" and p2["cpf"] is None
        assert (await async_client.patch(f"/users/{p2['id']}", headers=A2, json={"full_name": "Hacker"})).status_code == 403
        assert (await async_client.patch(f"/users/{p2['id']}", headers=A2, json={"role": "administrador"})).status_code == 403
        assert (await async_client.post(f"/users/{p2['id']}/2fa/resetar", headers=A2)).status_code == 403
        assert (await async_client.post(f"/lgpd/usuarios/{p2['id']}/anonimizar", headers=A2)).status_code == 403
        # banca 1 (origem) não vê nada da banca 2
        assert not any(u["username"] == "admin2" for u in (await async_client.get("/users/", headers=A1)).json())
        assert (await async_client.patch(f"/users/{p2['id']}", headers=A2, json={"status": "ativo"})).status_code == 200
        # a banca de origem não exclui a conta de quem trabalha para outras bancas
        assert (await async_client.delete(f"/users/{p2['id']}", headers=A1)).status_code == 409

        # ---- login: escolhe a banca; cada token só vale para a banca escolhida, com a função de lá
        r = await async_client.post("/auth/login", data={"username": "novo_prof", "password": SENHA, "recaptcha_token": "x"})
        r = await async_client.post("/auth/2fa/verificar", json={"token_2fa": r.json()["token_2fa"], "codigo": await _codigo(totp_novo)})
        d = r.json()
        assert d["etapa"] == "escolher_banca" and "access_token" not in d
        assert {(b["tenant_id"], b["role"]) for b in d["bancas"]} == {(1, "professor"), (2, "revisor")}
        assert (await async_client.post("/auth/2fa/escolher-banca", json={"token_2fa": d["token_2fa"], "tenant_id": 99})).status_code == 403
        r = await async_client.post("/auth/2fa/escolher-banca", json={"token_2fa": d["token_2fa"], "tenant_id": 2})
        assert r.status_code == 200 and r.json()["role"] == "revisor" and r.json()["banca"] == "Banca Teste 2"
        h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
        me = (await async_client.get("/users/me", headers=h2)).json()
        assert me["tenant_id"] == 2 and me["role"] == "revisor"
        # dentro da banca 2, nada da banca 1 (o evento de teste é da banca 1)
        assert all(e.get("tenant_id", 2) == 2 for e in (await async_client.get("/eventos/", headers=h2)).json())
        assert (await async_client.get("/eventos/c2438719-23aa-4f7d-8e0f-e6a310c10440", headers=h2)).status_code in (403, 404)
        bancas = (await async_client.get("/auth/bancas", headers=h2)).json()
        assert bancas["atual"] == 2 and len(bancas["bancas"]) == 2
        # troca de banca sem sair: o acesso anterior cai
        r = await async_client.post("/auth/trocar-banca", headers=h2, json={"tenant_id": 1})
        assert r.status_code == 200 and r.json()["role"] == "professor"
        h1 = {"Authorization": f"Bearer {r.json()['access_token']}"}
        assert (await async_client.get("/users/me", headers=h2)).status_code == 401
        assert (await async_client.get("/users/me", headers=h1)).json()["tenant_id"] == 1

        # ---- banca 2 desativa o vínculo: some o acesso a ela na hora; a banca 1 continua
        r = await async_client.post("/auth/trocar-banca", headers=h1, json={"tenant_id": 2})
        h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
        assert (await async_client.patch(f"/users/{p2['id']}", headers=A2, json={"status": "inativo"})).status_code == 200
        assert (await async_client.get("/users/me", headers=h2)).status_code in (401, 403)
        r, _ = await _login(async_client, "novo_prof", SENHA, totp_novo)
        assert r.status_code == 200 and r.json()["tenant_id"] == 1  # só uma banca ativa: entra direto
        # banca 2 remove o vínculo: a conta continua sendo da pessoa (banca 1)
        assert (await async_client.delete(f"/users/{p2['id']}", headers=A2)).status_code == 204
        assert not any(u["username"] == "novo_prof" for u in (await async_client.get("/users/", headers=A2)).json())
        assert any(u["username"] == "novo_prof" for u in (await async_client.get("/users/", headers=A1)).json())

        # ---- administrador não vem de outra banca
        r = await async_client.post("/convites", headers=A2, json={"email": "novo.prof@example.com", "role": "administrador"})
        reset_rate_limits()
        r = await async_client.post(f"/convites/publico/{_token(r.json()['link'])}/aceitar",
                                    data={"username": "novo_prof", "password": SENHA, "codigo": await _codigo(totp_novo)})
        assert r.status_code == 400

        # ---- esqueceu a senha: link para a própria pessoa criar a nova
        r = await async_client.post(f"/users/{novo['id']}/link-senha", headers=A1)
        assert r.status_code == 200
        tok = _token(r.json()["link"])
        assert (await async_client.get(f"/convites/publico/{tok}")).json()["tipo"] == "senha"
        assert (await async_client.post(f"/convites/publico/{tok}/senha", json={"nova_senha": "fraca"})).status_code == 400
        nova = "Nova-Senha-Pelo-Link-42"
        assert (await async_client.post(f"/convites/publico/{tok}/senha", json={"nova_senha": nova})).status_code == 200
        assert (await async_client.post(f"/convites/publico/{tok}/senha", json={"nova_senha": nova + "x"})).status_code == 410
        reset_rate_limits()
        r, _ = await _login(async_client, "novo_prof", nova, totp_novo)
        assert r.status_code == 200
        # outra banca não manda link de senha de quem não é dela
        assert (await async_client.post(f"/users/{novo['id']}/link-senha", headers=A2)).status_code == 404

        # ---- convites: lista e cancelamento só da própria banca
        r = await async_client.post("/convites", headers=A1, json={"email": "cancelar@example.com", "role": "revisor"})
        cid, tok = r.json()["id"], _token(r.json()["link"])
        assert (await async_client.delete(f"/convites/{cid}", headers=A2)).status_code == 404
        assert (await async_client.delete(f"/convites/{cid}", headers=A1)).json()["estado"] == "cancelado"
        assert (await async_client.get(f"/convites/publico/{tok}")).status_code == 410
        assert all(c["email"] != "cancelar@example.com" for c in (await async_client.get("/convites", headers=A2)).json())

        # ---- a própria pessoa troca a foto
        h = {"Authorization": f"Bearer {r.json().get('access_token', '')}"}
        r, _ = await _login(async_client, "novo_prof", nova, totp_novo)
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        assert (await async_client.put("/users/me/foto", headers=h, files={"foto": ("a.png", _foto((40, 40)), "image/png")})).status_code == 400
        r = await async_client.put("/users/me/foto", headers=h, files={"foto": ("a.png", _foto(), "image/png")})
        assert r.status_code == 200 and r.json()["tem_foto"]
    finally:
        reset_rate_limits()
        await _apagar("novo_prof")


async def test_audit_only_for_admins_of_own_banca(async_client):
    assert (await async_client.get("/admin/logs/geracao/", headers=DIAG)).status_code == 403
    assert (await async_client.get("/admin/logs/geracao/", headers=auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1))).status_code == 403
    r = await async_client.get("/admin/logs/geracao/", headers=A1, params={"tenant_id": 2})
    assert r.status_code == 200 and all(l["tenant_id"] == 1 for l in r.json())  # pedir outra banca não adianta
