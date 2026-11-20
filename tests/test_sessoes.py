"""Acessos (sessões): saída de verdade, saída remota, troca de senha/2FA derrubam acessos, alerta de novo aparelho,
isolamento entre bancas e dados do aparelho cifrados."""
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from backend.app import dois_fatores as df
from backend.app import sessoes
from backend.app.database import PlatformSessionLocal, SessionLocal, set_tenant_context
from backend.app.db_models import Notificacao, Sessao, User
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0 Safari/537.36"
FIREFOX_ANDROID = "Mozilla/5.0 (Android 14; Mobile; rv:140.0) Gecko/140.0 Firefox/140.0"


def _req(ip, ua):
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers={"user-agent": ua})


async def _usuarios():
    async with PlatformSessionLocal() as s:
        return {u.username: u for u in (await s.execute(select(User))).scalars().all()}


async def _limpar():
    async with PlatformSessionLocal() as s:
        await s.execute(text("DELETE FROM sessoes"))
        await s.execute(text("DELETE FROM notificacoes"))
        await s.commit()


async def _token(user, ip="200.10.20.30", ua=CHROME_WIN):
    sid = await sessoes.abrir(user, _req(ip, ua))
    return sid, {"Authorization": "Bearer " + df.criar_token_acesso(user, sid=sid)}


@pytest.mark.asyncio
async def test_sessions_logout_remote_signout_and_new_device_alert(async_client):
    reset_rate_limits()
    await _limpar()
    us = await _usuarios()
    prof, adm1, adm2 = us["vhugo"], us["admin1"], us["admin2"]
    try:
        # 1) primeiro acesso: sem alerta; mesmo aparelho/rede de novo: sem alerta
        sid_a, h_a = await _token(prof)
        sid_b, h_b = await _token(prof, ip="200.10.20.99")
        async with PlatformSessionLocal() as s:
            assert (await s.execute(select(Notificacao))).scalars().all() == []
            cru = (await s.execute(text("SELECT detalhes FROM sessoes LIMIT 1"))).scalar_one()
        assert "200.10.20" not in cru and "Chrome" not in cru  # IP e navegador cifrados

        # 2) aparelho novo: aviso de segurança no sino
        sid_c, h_c = await _token(prof, ip="177.5.6.7", ua=FIREFOX_ANDROID)
        avisos = (await async_client.get("/notificacoes", headers=h_a)).json()["itens"]
        assert len(avisos) == 1 and avisos[0]["tipo"] == "seguranca_novo_login" and "Firefox no Android" in avisos[0]["mensagem"]

        # 3) lista de acessos: os 3, com o atual marcado
        lista = (await async_client.get("/auth/sessoes", headers=h_a)).json()["itens"]
        assert len(lista) == 3 and [x["id"] for x in lista if x["atual"]] == [sid_a]

        # 4) encerrar um acesso específico derruba só ele
        assert (await async_client.post(f"/auth/sessoes/{sid_c}/encerrar", headers=h_a)).status_code == 200
        assert (await async_client.get("/users/me", headers=h_c)).status_code == 401
        assert (await async_client.get("/users/me", headers=h_b)).status_code == 200

        # 5) ninguém encerra acesso de outra pessoa (nem sabendo o id)
        sid_adm, h_adm = await _token(adm1)
        assert (await async_client.post(f"/auth/sessoes/{sid_b}/encerrar", headers=h_adm)).status_code == 404
        assert (await async_client.get("/users/me", headers=h_b)).status_code == 200

        # 6) sair encerra no servidor: o token copiado não vale mais
        assert (await async_client.post("/auth/sair", headers=h_b)).status_code == 200
        assert (await async_client.get("/users/me", headers=h_b)).status_code == 401

        # 7) renovar mantém o mesmo acesso
        r = await async_client.post("/auth/renovar", headers=h_a)
        novo = r.json()["access_token"]
        from backend.app.auth import decode_token_payload
        assert decode_token_payload(novo)["sid"] == sid_a
        assert (await async_client.get("/users/me", headers={"Authorization": "Bearer " + novo})).status_code == 200

        # 8) administrador de OUTRA banca não desconecta; o da banca desconecta todos os acessos
        _, h_adm2 = await _token(adm2)
        assert (await async_client.post(f"/users/{prof.id}/sessoes/encerrar", headers=h_adm2)).status_code in (403, 404)
        assert (await async_client.get("/users/me", headers=h_a)).status_code == 200
        r = await async_client.post(f"/users/{prof.id}/sessoes/encerrar", headers=h_adm)
        assert r.status_code == 200 and r.json()["encerradas"] == 1
        assert (await async_client.get("/users/me", headers=h_a)).status_code == 401

        # 9) reset do 2FA derruba todos os acessos da pessoa
        _, h_d = await _token(prof)
        assert (await async_client.post(f"/users/{prof.id}/2fa/resetar", headers=h_adm)).status_code == 204
        assert (await async_client.get("/users/me", headers=h_d)).status_code == 401

        # 10) "encerrar todos os outros" mantém o atual
        _, h_e = await _token(adm1)
        _, h_f = await _token(adm1)
        assert (await async_client.post("/auth/sessoes/encerrar-outras", headers=h_e)).json()["encerradas"] == 2
        assert (await async_client.get("/users/me", headers=h_e)).status_code == 200
        assert (await async_client.get("/users/me", headers=h_f)).status_code == 401

        # 11) RLS: a banca 2 não enxerga os acessos da banca 1
        async with SessionLocal() as s:
            async with s.begin():
                await set_tenant_context(s, 2)
                assert (await s.execute(select(Sessao).where(Sessao.tenant_id == 1))).scalars().all() == []

        # 12) token antigo (sem sid) passa a ter um acesso ao renovar
        legado = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
        r = await async_client.post("/auth/renovar", headers=legado)
        assert r.status_code == 200
        sid_novo = decode_token_payload(r.json()["access_token"]).get("sid")
        assert sid_novo and await sessoes.valida(sid_novo)
    finally:
        await _limpar()
        reset_rate_limits()


def test_browser_summary():
    assert sessoes.resumo_navegador(CHROME_WIN) == ("Chrome", "Windows")
    assert sessoes.resumo_navegador(FIREFOX_ANDROID) == ("Firefox", "Android")
    assert sessoes.resumo_navegador("Mozilla/5.0 (Windows NT 10.0) Chrome/157.0 Safari/537.36 Edg/157.0") == ("Edge", "Windows")
