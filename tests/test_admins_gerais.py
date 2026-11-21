"""Vários administradores gerais: convite por link, foto obrigatória, aprovação por outro administrador geral."""
import io

from PIL import Image
from sqlalchemy import select

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import User
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

AG = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
A1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
SENHA = "Senha-Do-Suporte-2026"


def _foto() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (240, 240), (90, 60, 140)).save(buf, format="PNG")
    return buf.getvalue()


async def test_multiple_platform_admins_by_invite_and_approval(async_client):
    reset_rate_limits()
    try:
        # só administrador geral
        assert (await async_client.get("/plataforma/administradores", headers=A1)).status_code == 403
        assert (await async_client.post("/plataforma/administradores/convites", headers=A1, json={"email": "x@example.com"})).status_code == 403
        # e-mail que já tem conta não vira administrador geral
        assert (await async_client.post("/plataforma/administradores/convites", headers=AG, json={"email": "a1@example.com"})).status_code == 409

        r = await async_client.post("/plataforma/administradores/convites", headers=AG, json={"email": "suporte2@example.com", "nome": "Suporte Dois"})
        assert r.status_code == 200, r.text
        token = r.json()["link"].rsplit("/convite/", 1)[1]
        assert any(c["email"] == "suporte2@example.com" for c in (await async_client.get("/plataforma/administradores/convites", headers=AG)).json())
        info = (await async_client.get(f"/convites/publico/{token}")).json()
        assert info["banca"].startswith("Plataforma DiagPro") and info["role"] == "administrador geral" and info["conta_existente"] is False
        # conta de banca não "aceita" virar administrador geral
        assert (await async_client.post(f"/convites/publico/{token}/aceitar", data={"username": "vhugo", "password": "TestPassword123!"})).status_code == 400

        dados = {"username": "suporte2", "password": SENHA, "full_name": "Suporte Dois", "accepted_confidentiality": "true",
                 "accepted_data_leak": "true"}
        r = await async_client.post(f"/convites/publico/{token}/cadastro", data=dados, files={"foto": ("f.png", _foto(), "image/png")})
        assert r.status_code == 201, r.text
        async with PlatformSessionLocal() as s:
            novo = (await s.execute(select(User).where(blind_eq(User.username, "suporte2")))).scalars().first()
            assert novo.tenant_id is None and novo.role == "administrador geral" and novo.status == "pendente"

        # pendente não entra
        login = lambda: async_client.post("/auth/login", data={"username": "suporte2", "password": SENHA, "recaptcha_token": "x"})
        assert (await login()).status_code == 403
        lista = (await async_client.get("/plataforma/administradores", headers=AG)).json()
        assert {u["username"] for u in lista} >= {"Victor Hugo", "suporte2"}
        alvo = next(u for u in lista if u["username"] == "suporte2")
        assert alvo["tem_foto"] and alvo["status"] == "pendente"

        # aprovação por outro administrador geral; ninguém muda a própria situação
        eu = next(u for u in lista if u["username"] == "Victor Hugo")
        assert (await async_client.patch(f"/plataforma/administradores/{eu['id']}", headers=AG, json={"status": "inativo"})).status_code == 403
        assert (await async_client.patch(f"/plataforma/administradores/{alvo['id']}", headers=AG, json={"status": "ativo"})).status_code == 200
        r = await login()
        assert r.status_code == 200 and r.json()["etapa"] == "cadastro_2fa"  # 2FA obrigatório no primeiro acesso

        # o novo administrador geral trabalha (lista) e pode ser desativado por outro
        ag2 = auth_headers("suporte2", UserRole.ADMIN_GERAL)
        assert (await async_client.get("/plataforma/administradores", headers=ag2)).status_code == 200
        assert (await async_client.patch(f"/plataforma/administradores/{alvo['id']}", headers=AG, json={"status": "inativo"})).status_code == 200
        assert (await login()).status_code == 403
        assert (await async_client.get("/plataforma/administradores", headers=ag2)).status_code == 403
        # administrador de banca não aparece nem é alterado por aqui
        a1_id = (await async_client.get("/users/me", headers=A1)).json()["id"]
        assert (await async_client.patch(f"/plataforma/administradores/{a1_id}", headers=AG, json={"status": "inativo"})).status_code == 404
    finally:
        reset_rate_limits()
        async with PlatformSessionLocal() as s:
            u = (await s.execute(select(User).where(blind_eq(User.username, "suporte2")))).scalars().first()
            if u:
                await s.delete(u)
                await s.commit()
