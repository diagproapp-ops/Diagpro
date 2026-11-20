"""LGPD: termos com versão e aceite, exportação dos próprios dados (sem segredos), anonimização, registros e retenção."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from backend.app import dois_fatores as df
from backend.app import lgpd, sessoes
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Notificacao, RegistroLGPD, Sessao, User
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers


async def _usuario(nome):
    async with PlatformSessionLocal() as s:
        return next(u for u in (await s.execute(select(User))).scalars() if u.username == nome)


@pytest.mark.asyncio
async def test_lgpd_terms_export_anonymize_records_and_retention(async_client):
    reset_rate_limits()
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    try:
        # 1) termos públicos, aceite com versão
        docs = (await async_client.get("/lgpd/documentos")).json()
        assert docs["versao"] == "1" and "LGPD" in docs["politica"]
        assert (await async_client.get("/lgpd/status", headers=hp)).json()["aceita"] is False
        assert (await async_client.post("/lgpd/aceitar", headers=hp, json={"versao": "0"})).status_code == 409
        r = await async_client.post("/lgpd/aceitar", headers=hp, json={"versao": "1"})
        assert r.status_code == 200 and r.json()["aceite"]["versao"] == "1"
        assert (await async_client.get("/lgpd/status", headers=hp)).json()["aceita"] is True
        # nova versão dos termos: precisa aceitar de novo
        assert (await async_client.put("/config/plataforma", headers=ag, json={"lgpd": {"versao_termos": "2"}})).status_code == 200
        assert (await async_client.get("/lgpd/status", headers=hp)).json()["aceita"] is False

        # 2) exportação dos próprios dados: dados pessoais sim, segredos nunca
        prof = await _usuario("vhugo")
        await sessoes.abrir(prof, SimpleNamespace(client=SimpleNamespace(host="200.1.2.3"), headers={"user-agent": "Firefox/140"}))
        r = await async_client.get("/lgpd/meus-dados", headers=hp)
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        dados = r.json()
        assert dados["titular"]["email"] == "p1@example.com" and dados["acessos"][0]["ip"] == "200.1.2.3"
        texto = r.text
        assert "password_hash" not in texto and "totp_secret" not in texto and "codigos_recuperacao" not in texto
        assert prof.password_hash not in texto

        # 3) anonimização: só administrador da banca, nunca de si mesmo, irreversível
        r = await async_client.post("/users/", headers=a1, json={"username": "lgpd_alvo", "email": "alvo@example.com",
                                    "password": "Senha-Forte-2026!x", "role": "professor", "tenant_id": 1, "status": "ativo"})
        assert r.status_code in (200, 201), r.text
        alvo = await _usuario("lgpd_alvo")
        sid = await sessoes.abrir(alvo, SimpleNamespace(client=SimpleNamespace(host="10.0.0.9"), headers={"user-agent": "Chrome/157"}))
        h_alvo = {"Authorization": "Bearer " + df.criar_token_acesso(alvo, sid=sid)}
        assert (await async_client.get("/users/me", headers=h_alvo)).status_code == 200
        assert (await async_client.post(f"/lgpd/usuarios/{alvo.id}/anonimizar", headers=a2)).status_code == 404
        assert (await async_client.post(f"/lgpd/usuarios/{alvo.id}/anonimizar", headers=hp)).status_code == 403
        adm1 = await _usuario("admin1")
        assert (await async_client.post(f"/lgpd/usuarios/{adm1.id}/anonimizar", headers=a1)).status_code == 403
        r = await async_client.post(f"/lgpd/usuarios/{alvo.id}/anonimizar", headers=a1)
        assert r.status_code == 200 and r.json()["usuario"] == f"anonimizado-{alvo.id}"
        assert (await async_client.post(f"/lgpd/usuarios/{alvo.id}/anonimizar", headers=a1)).status_code == 409
        async with PlatformSessionLocal() as s:
            depois = await s.get(User, alvo.id)
            assert depois.email is None and depois.full_name is None and depois.is_active is False
            assert depois.username == f"anonimizado-{alvo.id}"
            assert (await s.execute(select(Sessao).where(Sessao.usuario_id == alvo.id))).scalars().all() == []
        assert (await async_client.get("/users/me", headers=h_alvo)).status_code in (401, 403)

        # 4) registros: a banca vê os dela; outra banca não
        regs = (await async_client.get("/lgpd/registros", headers=a1)).json()
        acoes = {r["acao"] for r in regs}
        assert {"aceite_termos", "exportacao", "anonimizacao"} <= acoes
        assert all(r["acao"] != "anonimizacao" for r in (await async_client.get("/lgpd/registros", headers=a2)).json())
        assert (await async_client.get("/lgpd/registros", headers=hp)).status_code == 403

        # 5) retenção: aviso antigo é apagado; recente fica
        async with PlatformSessionLocal() as s:
            for dias, titulo in ((400, "antigo"), (1, "recente")):
                s.add(Notificacao(tenant_id=1, usuario_id=prof.id, tipo="sistema", criado_em=datetime.utcnow() - timedelta(days=dias),
                                  conteudo={"titulo": titulo, "mensagem": "", "link": None}, email_estado="nao_enviar", email_tentativas=0))
            await s.commit()
        r = await lgpd.limpar_por_retencao()
        assert r["avisos"] >= 1
        async with PlatformSessionLocal() as s:
            titulos = [(n.conteudo or {}).get("titulo") for n in (await s.execute(select(Notificacao).where(Notificacao.usuario_id == prof.id))).scalars()]
        assert "antigo" not in titulos and "recente" in titulos
    finally:
        await async_client.put("/config/plataforma", headers=ag, json={"lgpd": {"versao_termos": "1"}})
        async with PlatformSessionLocal() as s:
            await s.execute(text("DELETE FROM notificacoes"))
            await s.execute(text("DELETE FROM sessoes"))
            await s.commit()
        reset_rate_limits()
