"""Painel de clientes do administrador geral: números reais, edição, bloqueio que vale na hora e admin por convite."""
from datetime import datetime

from sqlalchemy import select

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Sessao, User
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

AG = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
A1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)


async def test_client_panel_real_numbers_edit_block_and_invite_admin(async_client):
    reset_rate_limits()
    # só o administrador geral
    assert (await async_client.get("/admin/clients/dashboard", headers=A1)).status_code == 403
    assert (await async_client.put("/admin/clients/2", headers=A1, json={})).status_code == 403
    assert (await async_client.post("/admin/clients/2/bloquear", headers=A1)).status_code == 403

    # números reais (nada simulado): acessos vêm das sessões, último acesso também
    async with PlatformSessionLocal() as s:
        admin2 = (await s.execute(select(User).where(User.tenant_id == 2, User.role == "administrador"))).scalars().first()
        s.add(Sessao(id="s" * 32, tenant_id=2, usuario_id=admin2.id, criada_em=datetime.utcnow(),
                     ultimo_uso_em=datetime.utcnow(), detalhes={"ip": "", "navegador": "", "sistema": ""}))
        await s.commit()
    painel = {c["id"]: c for c in (await async_client.get("/admin/clients/dashboard", headers=AG)).json()}
    c2 = painel[2]
    assert c2["accesses_total_month"] >= 1 and c2["last_access"] and not c2["last_access"].startswith("2025")
    assert all(a["user"] != "prof1" for c in painel.values() for a in c["recent_activities"])  # sem exemplos fixos
    assert c2["users_by_role"].get("administrador", 0) >= 1 and c2["admins_total"] >= 1

    original = (await async_client.get("/admin/clients/2", headers=AG)).json()
    try:
        # editar
        corpo = {"name": "Banca Teste 2", "domain": original["domain"], "status": "ativo", "tenant_type": "empresa_concurso",
                 "responsible_name": "Resp", "responsible_email": "resp@example.com", "plan_type": "Anual",
                 "plan_expires_at": "2027-01-31"}
        r = await async_client.put("/admin/clients/2", headers=AG, json=corpo)
        assert r.status_code == 200 and r.json()["plan_type"] == "Anual"
        assert (await async_client.put("/admin/clients/2", headers=AG, json={**corpo, "name": "Banca Teste 1"})).status_code == 400
        assert (await async_client.put("/admin/clients/2", headers=AG, json={**corpo, "status": "qualquer"})).status_code == 400

        # bloquear: ninguém entra e quem está dentro sai na hora
        r = await async_client.post("/admin/clients/2/bloquear", headers=AG)
        assert r.status_code == 200 and r.json()["acessos_encerrados"] >= 1
        login = await async_client.post("/auth/login", data={"username": "admin2", "password": "TestPassword123!", "recaptcha_token": "x"})
        assert login.status_code == 403
        assert (await async_client.post("/admin/clients/2/desbloquear", headers=AG)).status_code == 200
        login = await async_client.post("/auth/login", data={"username": "admin2", "password": "TestPassword123!", "recaptcha_token": "x"})
        assert login.status_code == 200

        # administrador do cliente: por convite (sem senha inventada)
        assert (await async_client.post("/admin/clients/2/create-admin", headers=AG)).status_code == 410
        r = await async_client.post("/convites", headers={**AG, "X-Tenant-Id": "2"},
                                    json={"email": "novo.admin@example.com", "role": "administrador"})
        assert r.status_code == 200 and "/convite/" in r.json()["link"]
        assert (await async_client.delete(f"/convites/{r.json()['id']}", headers={**AG, "X-Tenant-Id": "2"})).status_code == 200

        # atividade do cliente: só da auditoria dele
        assert (await async_client.get("/admin/clients/2/logs", headers=AG)).status_code == 200
    finally:
        await async_client.put("/admin/clients/2", headers=AG, json={
            "name": original["name"], "domain": original["domain"], "status": "ativo", "tenant_type": original["tenant_type"],
            "responsible_name": original.get("responsible_name"), "responsible_email": original.get("responsible_email"),
            "plan_type": original.get("plan_type"), "plan_expires_at": original.get("plan_expires_at")})
        reset_rate_limits()
