"""Fila de revisão: nenhuma questão aparece nem abre sem a senha do evento (inclusive para o administrador geral).
A liberação vale só para aquela sessão."""
import time
from types import SimpleNamespace

from sqlalchemy import select

from backend.app import sessoes
from backend.app.auth import create_access_token
from backend.app.database import PlatformSessionLocal
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from backend.app.db_models import User
from tests.conftest import auth_headers, com_evento_liberado
from tests.test_revisao import BASE, COMUM, DADOS_REV, EV


async def _sessao_admin_geral(client, cliente: int) -> dict:
    """Admin geral com sessão real (sid) e o cliente escolhido no topo (X-Tenant-Id)."""
    async with PlatformSessionLocal() as s:
        uid = (await s.execute(select(User.id).where(blind_eq(User.username, "Victor Hugo")))).scalar_one()
    sid = await sessoes.abrir(SimpleNamespace(id=uid, tenant_id=None), None, alertar=False)
    token = create_access_token({"sub": "Victor Hugo", "role": "administrador geral", "mfa": True, "sid": sid,
                                 "auth_time": int(time.time())})
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(cliente)}


async def test_review_queue_and_question_need_event_password_per_session(async_client):
    reset_rate_limits()
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    r = await async_client.post(BASE, headers=hp, data={**COMUM, "enunciado": "<p>Questão sigilosa da fila</p>"})
    assert r.status_code == 200, r.text
    qid, codigo = r.json()["id_questao"], r.json()["codigo_curto_questao"]
    q = f"{BASE}/{qid}"
    try:
        assert (await async_client.post(f"/revisao/questoes/{qid}/enviar", headers=hp)).status_code == 200

        # ---- sem a senha: a fila não traz NADA da questão, só que há questões naquele evento
        r = await async_client.get("/revisao/fila", headers=a1)
        dados = r.json()
        assert r.status_code == 200 and all(i["id_questao"] != qid for i in dados["itens"])
        assert codigo not in r.text and qid not in r.text
        bloq = {b["evento_id"]: b for b in dados["eventos_bloqueados"]}
        assert bloq[EV]["quantidade"] >= 1 and bloq[EV]["evento"]
        # e não salva revisão
        rv = {"status_revisao": "APROVADA", "observacao_revisor": "", "usuario_revisor": "x", "dados_revisao": DADOS_REV}
        r = await async_client.patch(f"{q}/revisao", headers=a1, data=rv)
        assert r.status_code == 403 and r.json()["detail"]["codigo"] == "evento_bloqueado"

        # ---- administrador geral: nem digitando o endereço abre questão, lista ou texto do evento
        ag = await _sessao_admin_geral(async_client, 1)
        for url in (q, BASE, f"{q}/revisoes", f"{q}/versoes", f"/eventos/{EV}/conteudos/ci-conteudo-1/textos-referencia"):
            r = await async_client.get(url, headers=ag)
            assert r.status_code == 403 and r.json()["detail"]["codigo"] == "evento_bloqueado", url
        assert (await async_client.post(BASE, headers=ag, data=COMUM)).status_code == 403
        assert (await async_client.delete(q, headers=ag)).status_code == 403
        assert (await async_client.get(f"/revisao/eventos/{EV}/liberado", headers=ag)).json()["liberado"] is False
        # senha errada não libera (e conta para bloqueio)
        assert (await async_client.post(f"/revisao/eventos/{EV}/liberar", headers=ag, json={"senha": "errada"})).status_code == 403
        # acesso sem sessão (token antigo) não consegue liberar
        assert (await async_client.post(f"/revisao/eventos/{EV}/liberar", headers={**auth_headers("Victor Hugo", UserRole.ADMIN_GERAL), "X-Tenant-Id": "1"},
                                         json={"senha": "1234"})).status_code == 403
        # com a senha certa: libera só esta sessão
        assert (await async_client.post(f"/revisao/eventos/{EV}/liberar", headers=ag, json={"senha": "1234"})).status_code == 200
        assert (await async_client.get(q, headers=ag)).status_code == 200
        assert any(i["id_questao"] == qid for i in (await async_client.get("/revisao/fila", headers=ag)).json()["itens"])
        outra = await _sessao_admin_geral(async_client, 1)  # outro acesso da mesma pessoa: precisa da senha de novo
        assert (await async_client.get(q, headers=outra)).status_code == 403

        # ---- revisor da banca: mesma regra
        rev = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
        lib = await com_evento_liberado(async_client, "admin1", UserRole.ADMIN, 1)
        assert any(i["id_questao"] == qid for i in (await async_client.get("/revisao/fila", headers=lib)).json()["itens"])
        assert (await async_client.patch(f"{q}/revisao", headers=lib, data=rv)).status_code == 200
        assert (await async_client.patch(f"{q}/revisao", headers=rev, data=rv)).status_code == 403

        # ---- o resto do fluxo da banca não muda: professor e administrador abrem a questão como antes
        assert (await async_client.get(q, headers=hp)).status_code == 200
        assert (await async_client.get(q, headers=a1)).status_code == 200

        # ---- a liberação cai com a sessão
        sid = __import__("jose").jwt.get_unverified_claims(ag["Authorization"].split()[1])["sid"]
        async with PlatformSessionLocal() as s:
            uid = (await s.execute(select(User.id).where(blind_eq(User.username, "Victor Hugo")))).scalar_one()
        await sessoes.encerrar(sid, uid, "teste")
        assert (await async_client.get(q, headers=ag)).status_code == 401
    finally:
        await async_client.delete(q, headers=a1)
        reset_rate_limits()
