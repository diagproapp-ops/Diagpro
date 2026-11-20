"""Fluxo de revisão: enviar, fila, devolver, aprovar, reabrir quando alterada, avisos e isolamento."""
import json

import pytest
from sqlalchemy import select, text

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import HistoricoRevisaoQuestao, Notificacao, User
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

EV, CT = "c2438719-23aa-4f7d-8e0f-e6a310c10440", "ci-conteudo-1"
BASE = f"/eventos/{EV}/conteudos/{CT}/questoes"
ALTS = json.dumps([{"letra": L, "texto": f"<p>{L}</p>", "correta": L == "A"} for L in "ABCDE"])
COMUM = {"tipo": "MULTIPLA_ESCOLHA", "indicacao_conteudo": "1", "enunciado": "<p>Questão do fluxo</p>", "alternativas": ALTS,
         "nivel_dificuldade": "MEDIO", "pontuacao": "1", "tags": "", "justificativa_questao": "", "justificativa_anulacao": "",
         "resposta_correta": "A", "texto_referencia_vinculo": "", "texto_referencia_direto": "", "tenant_id": "1", "anulada": "false"}
DADOS_REV = json.dumps({"tipo": "MULTIPLA_ESCOLHA", "itens_comando": [""], "respostas_certo_errado": [""], "enunciado": "<p>Questão do fluxo</p>",
                        "alternativas": [{"letra": L, "texto": f"<p>{L}</p>", "correta": L == "A"} for L in "ABCDE"], "resposta_correta": "A"})


async def _avisos(usuario_id):
    async with PlatformSessionLocal() as s:
        return [(n.tipo, (n.conteudo or {}).get("titulo")) for n in (await s.execute(
            select(Notificacao).where(Notificacao.usuario_id == usuario_id).order_by(Notificacao.id))).scalars()]


@pytest.mark.asyncio
async def test_review_workflow_send_queue_return_approve_reopen(async_client):
    reset_rate_limits()
    async with PlatformSessionLocal() as s:
        await s.execute(text("DELETE FROM notificacoes"))
        await s.commit()
        ids = {u.username: u.id for u in (await s.execute(select(User))).scalars()}
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hd = auth_headers("vhugo1234", UserRole.DIAGRAMADOR, tenant_id=1)
    try:
        # 1) professor cria: fica em elaboração, com o autor registrado pelo servidor
        r = await async_client.post(BASE, headers=hp, data=COMUM)
        assert r.status_code == 200, r.text
        qid = r.json()["id_questao"]
        codigo = r.json()["codigo_curto_questao"]
        assert r.json()["status_revisao"] == "RASCUNHO"

        # 2) envia para revisão (com recado); a fila do revisor mostra a questão com o autor
        r = await async_client.post(f"/revisao/questoes/{qid}/enviar", headers=hp, json={"mensagem": "Confira a alternativa C"})
        assert r.status_code == 200 and r.json()["status_revisao"] == "ENVIADA"
        assert (await async_client.post(f"/revisao/questoes/{qid}/enviar", headers=hp)).status_code == 409
        fila = (await async_client.get("/revisao/fila", headers=a1)).json()["itens"]
        item = next(i for i in fila if i["id_questao"] == qid)
        assert item["autor"] == "vhugo" and item["mensagem_envio"] == "Confira a alternativa C" and item["evento"] == "Evento CI Teste"
        # sem revisor cadastrado na banca, o aviso vai para o administrador
        assert ("revisao_recebida", f"Questão {codigo} aguardando revisão") in await _avisos(ids["admin1"])

        # 3) perfis e isolamento: diagramador não envia; outra banca não vê a fila nem a questão
        assert (await async_client.post(f"/revisao/questoes/{qid}/enviar", headers=hd)).status_code == 403
        assert (await async_client.get("/revisao/fila", headers=hp)).status_code == 403
        assert all(i["id_questao"] != qid for i in (await async_client.get("/revisao/fila", headers=a2)).json()["itens"])
        assert (await async_client.post(f"/revisao/questoes/{qid}/enviar", headers=a2)).status_code == 404

        # 4) revisor pede ajustes; o nome do revisor vem do login (não do formulário)
        rv = {"observacao_revisor": "Alternativa C ambígua", "usuario_revisor": "nome-falso", "tenant_id": "1", "dados_revisao": DADOS_REV}
        assert (await async_client.patch(f"{BASE}/{qid}/revisao", headers=a1, data={**rv, "status_revisao": "QUALQUER"})).status_code == 400
        assert (await async_client.patch(f"{BASE}/{qid}/revisao", headers=a1, data={**rv, "status_revisao": "AJUSTES"})).status_code == 200
        async with PlatformSessionLocal() as s:
            revisores = [h.usuario_revisor for h in (await s.execute(select(HistoricoRevisaoQuestao).where(
                HistoricoRevisaoQuestao.id_questao_fk == qid, HistoricoRevisaoQuestao.status_revisao == "AJUSTES"))).scalars()]
        assert revisores == ["admin1"]
        assert ("revisao_devolvida", f"Questão {codigo} voltou da revisão") in await _avisos(ids["vhugo"])
        assert (await async_client.get(f"{BASE}/{qid}", headers=hp)).json()["observacao_revisor"] == "Alternativa C ambígua"

        # 5) professor corrige, reenvia e o revisor aprova
        assert (await async_client.post(f"/revisao/questoes/{qid}/enviar", headers=hp)).status_code == 200
        assert (await async_client.patch(f"{BASE}/{qid}/revisao", headers=a1, data={**rv, "status_revisao": "APROVADA"})).status_code == 200
        assert ("revisao_aprovada", f"Questão {codigo} aprovada") in await _avisos(ids["vhugo"])
        assert (await async_client.post(f"/revisao/questoes/{qid}/enviar", headers=hp)).status_code == 409  # já aprovada
        resumo = (await async_client.get("/revisao/resumo", headers=a1)).json()
        assert resumo["APROVADA"]["quantidade"] >= 1

        # 6) alterar uma questão aprovada a devolve para elaboração (precisa de nova revisão)
        r = await async_client.put(f"{BASE}/{qid}", headers=hp, data={**COMUM, "enunciado": "<p>Questão do fluxo (alterada)</p>"})
        assert r.status_code == 200, r.text
        assert r.json()["status_revisao"] == "RASCUNHO"
        historico = (await async_client.get(f"{BASE}/{qid}/revisoes", headers=a1)).json()
        assert [h["status_revisao"] for h in historico] == ["ENVIADA", "AJUSTES", "ENVIADA", "APROVADA", "RASCUNHO"]
        assert historico[-1]["usuario_revisor"] == "vhugo"
    finally:
        async with PlatformSessionLocal() as s:
            await s.execute(text("DELETE FROM notificacoes"))
            await s.commit()
        reset_rate_limits()
