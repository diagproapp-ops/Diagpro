"""Avisos (sino e e-mail): fila, preferências, isolamento, senha do SMTP nunca exposta. Nenhum e-mail real sai:
o envio SMTP é trocado por um falso que guarda a mensagem."""
import pytest
from sqlalchemy import select, text

from backend.app import notificacoes
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Notificacao, User
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

SENHA_SMTP = "senha-smtp-SECRETA-987"
_ENVIO_REAL = notificacoes._enviar_smtp  # guardado antes de qualquer troca nos testes


async def _ids():
    async with PlatformSessionLocal() as s:
        return {u.username: u.id for u in (await s.execute(select(User))).scalars().all()}


async def _limpar():
    async with PlatformSessionLocal() as s:
        await s.execute(text("DELETE FROM notificacoes"))
        await s.commit()


@pytest.mark.asyncio
async def test_notifications_queue_preferences_and_isolation(async_client, monkeypatch):
    reset_rate_limits()
    await _limpar()
    enviados = []
    monkeypatch.setattr(notificacoes, "_enviar_smtp", lambda cfg, msg: enviados.append(msg))
    ids = await _ids()
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    try:
        # 1) e-mail desligado: o aviso aparece no sino, mas não entra na fila de e-mail
        assert (await async_client.post(f"/users/{ids['vhugo']}/2fa/resetar", headers=a1)).status_code == 204
        r = (await async_client.get("/notificacoes", headers=hp)).json()
        assert r["nao_lidas"] == 1 and r["itens"][0]["tipo"] == "seguranca_2fa_resetado" and r["itens"][0]["link"] == "/minha-conta"
        async with PlatformSessionLocal() as s:
            assert (await s.execute(select(Notificacao.email_estado))).scalars().all() == ["nao_enviar"]
            cru = (await s.execute(text("SELECT conteudo FROM notificacoes"))).scalar_one()
        assert "resetou" not in cru and "minha-conta" not in cru  # cifrado no banco

        # 2) isolamento: outra banca e outro usuário não leem nem marcam o aviso
        nid = r["itens"][0]["id"]
        assert (await async_client.get("/notificacoes", headers=a2)).json()["itens"] == []
        assert (await async_client.get("/notificacoes", headers=a1)).json()["itens"] == []
        await async_client.post(f"/notificacoes/{nid}/lida", headers=a2)
        await async_client.post(f"/notificacoes/{nid}/lida", headers=a1)
        assert (await async_client.get("/notificacoes/contagem", headers=hp)).json()["nao_lidas"] == 1
        assert (await async_client.post(f"/notificacoes/{nid}/lida", headers=hp)).status_code == 200
        assert (await async_client.get("/notificacoes/contagem", headers=hp)).json()["nao_lidas"] == 0

        # 3) plataforma configura o e-mail; a senha nunca volta e fica cifrada
        r = await async_client.put("/config/plataforma", headers=ag, json={"email": {
            "habilitado": True, "host": "smtp.exemplo.com", "porta": 587, "seguranca": "starttls", "usuario": "diagpro",
            "senha": SENHA_SMTP, "remetente_email": "avisos@exemplo.com", "url_sistema": "https://diagpro.exemplo.com"}})
        assert r.status_code == 200 and SENHA_SMTP not in r.text and r.json()["email"]["senha_definida"] is True
        assert SENHA_SMTP not in (await async_client.get("/config/plataforma", headers=ag)).text
        async with PlatformSessionLocal() as s:
            assert SENHA_SMTP not in (await s.execute(text("SELECT dados FROM configuracoes WHERE tenant_id IS NULL"))).scalar_one()
        # injeção de cabeçalho no nome do remetente é recusada
        r = await async_client.put("/config/plataforma", headers=ag, json={"email": {"remetente_nome": "X\r\nBcc: a@b.com"}})
        assert r.status_code == 400

        # 4) preferências: aviso opcional pode ser desligado; segurança não
        r = await async_client.put("/notificacoes/preferencias", headers=hp, json={"email": {"sistema": False, "seguranca_novo_login": False}})
        tipos = {t["tipo"]: t for t in r.json()["tipos"]}
        assert tipos["sistema"]["email"] is False and tipos["seguranca_novo_login"]["email"] is True
        assert (await async_client.put("/notificacoes/preferencias", headers=hp, json={"email": {"inventado": True}})).status_code == 400

        await notificacoes.notificar(ids["vhugo"], "sistema", "Aviso opcional", "texto", "/")
        await notificacoes.notificar(ids["vhugo"], "seguranca_novo_login", "Novo acesso", "Acesso de 1.2.3.4", "/minha-conta")
        async with PlatformSessionLocal() as s:
            estados = {n.tipo: n.email_estado for n in (await s.execute(select(Notificacao))).scalars().all()}
        assert estados["sistema"] == "nao_enviar" and estados["seguranca_novo_login"] == "pendente"

        # 5) a fila envia; o e-mail tem só o aviso e o link, e o destinatário é o e-mail da pessoa
        assert (await notificacoes.processar_fila())["enviados"] == 1
        msg = enviados[-1]
        assert msg["To"] == "p1@example.com" and msg["Subject"] == "DiagPro: Novo acesso"
        corpo = msg.get_body(("plain",)).get_content()
        assert "https://diagpro.exemplo.com/minha-conta" in corpo and "conteúdo das provas nunca é enviado" in corpo
        assert (await notificacoes.processar_fila())["enviados"] == 0  # não reenvia

        # 6) falha no servidor: tenta de novo mais tarde e, depois de 5 vezes, desiste
        def quebrado(cfg, msg):
            raise notificacoes.ErroEmail("Falha ao falar com o servidor de e-mail (OSError).")
        monkeypatch.setattr(notificacoes, "_enviar_smtp", quebrado)
        await notificacoes.notificar(ids["vhugo"], "seguranca_senha_alterada", "Senha alterada", "x", "/minha-conta")
        for _ in range(5):
            await notificacoes.processar_fila()
            async with PlatformSessionLocal() as s:
                await s.execute(text("UPDATE notificacoes SET email_proxima_tentativa = NULL WHERE tipo = 'seguranca_senha_alterada'"))
                await s.commit()
        async with PlatformSessionLocal() as s:
            n = (await s.execute(select(Notificacao).where(Notificacao.tipo == "seguranca_senha_alterada"))).scalar_one()
        assert n.email_estado == "falhou" and n.email_tentativas == 5

        # 7) sem criptografia só com servidor local
        cfg = {"host": "smtp.exemplo.com", "porta": 25, "seguranca": "nenhuma", "remetente_email": "a@exemplo.com", "usuario": "", "senha": ""}
        with pytest.raises(notificacoes.ErroEmail, match="servidor local"):
            _ENVIO_REAL(cfg, None)  # a função verdadeira recusa antes de abrir conexão

        # 8) admin geral (sem banca) também recebe e lê os próprios avisos
        await notificacoes.notificar(ids["Victor Hugo"], "sistema", "Aviso do admin", "x", "/settings")
        assert (await async_client.get("/notificacoes", headers=ag)).json()["nao_lidas"] == 1
        assert (await async_client.get("/notificacoes", headers=a1)).json()["itens"] == []
    finally:
        await async_client.put("/config/plataforma", headers=ag, json={"email": {"habilitado": False, "host": "", "usuario": "", "senha": None, "remetente_email": "", "url_sistema": "http://localhost:3000"}})
        await async_client.put("/notificacoes/preferencias", headers=hp, json={"email": {"sistema": True}})
        await _limpar()
        reset_rate_limits()


