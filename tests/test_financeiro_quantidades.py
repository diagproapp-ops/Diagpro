"""Quantidades do contrato sem digitar: vêm dos conteúdos do professor no evento e do que ele já elaborou."""
import json

from sqlalchemy import select, text

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import User
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import reset_rate_limits
from tests.conftest import EVENTO_TESTE
from tests.test_financeiro import A1, AG1, HP, _limpar

BASE = f"/eventos/{EVENTO_TESTE}/conteudos/ci-conteudo-1/questoes"
ALTS = json.dumps([{"letra": L, "texto": f"<p>{L}</p>", "correta": L == "A"} for L in "ABCDE"])
COMUM = {"tipo": "MULTIPLA_ESCOLHA", "indicacao_conteudo": "1", "enunciado": "<p>Questão do contrato</p>", "alternativas": ALTS,
         "nivel_dificuldade": "MEDIO", "pontuacao": "1", "tags": "", "justificativa_questao": "", "justificativa_anulacao": "",
         "resposta_correta": "A", "texto_referencia_vinculo": "", "texto_referencia_direto": "", "tenant_id": "1", "anulada": "false"}


async def test_contract_quantities_come_from_contents_and_batch(async_client):
    reset_rate_limits()
    await _limpar()
    async with PlatformSessionLocal() as s:
        pid = (await s.execute(select(User.id).where(blind_eq(User.username, "vhugo")))).scalar_one()
        original = tuple((await s.execute(text("SELECT professor_id, quantidade FROM conteudos WHERE id_conteudo = 'ci-conteudo-1'"))).one())
        await s.execute(text("UPDATE conteudos SET professor_id = :p, quantidade = 5 WHERE id_conteudo = 'ci-conteudo-1'"), {"p": str(pid)})
        await s.commit()
    qid = None
    try:
        r = await async_client.post(BASE, headers=HP, data=COMUM)
        assert r.status_code == 200, r.text
        qid = r.json()["id_questao"]

        # sugestão: 5 pedidas no conteúdo, 1 já elaborada -> 5 de múltipla escolha
        sug = (await async_client.get("/financeiro/sugestao", headers=A1, params={"professor_id": pid, "evento_id": EVENTO_TESTE})).json()
        assert sug["pedidas"] == 5 and sug["elaboradas"] >= 1 and sug["quantidades"]["MULTIPLA_ESCOLHA"] >= 5
        assert sug["conteudos"][0]["quantidade"] == 5
        assert (await async_client.get("/financeiro/sugestao", headers=AG1, params={"professor_id": pid, "evento_id": EVENTO_TESTE})).status_code == 403

        # contrato sem quantidades: preenchidas sozinhas
        cid = (await async_client.post("/financeiro/contratos", headers=A1, json={"professor_id": pid, "evento_id": EVENTO_TESTE})).json()["id"]
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["dados"]["quantidades"]["MULTIPLA_ESCOLHA"] == sug["quantidades"]["MULTIPLA_ESCOLHA"]
        assert c["totais"]["previsto"] == round(c["dados"]["precos"]["MULTIPLA_ESCOLHA"] * sug["quantidades"]["MULTIPLA_ESCOLHA"], 2)

        # lote: quem já tem contrato em andamento fica de fora; sem contrato, ganha um rascunho
        r = (await async_client.post("/financeiro/contratos/lote", headers=A1, json={"evento_id": EVENTO_TESTE})).json()
        assert r["criados"] == 0 and r["ja_tinham_contrato"] == 1
        await async_client.post(f"/financeiro/contratos/{cid}/cancelar", headers=A1, json={"motivo": "teste"})
        r = (await async_client.post("/financeiro/contratos/lote", headers=A1, json={"evento_id": EVENTO_TESTE})).json()
        assert r["criados"] == 1
        novo = (await async_client.get(f"/financeiro/contratos/{r['ids'][0]}", headers=A1)).json()
        assert novo["status"] == "rascunho" and novo["dados"]["quantidades"]["MULTIPLA_ESCOLHA"] >= 5
        assert (await async_client.post("/financeiro/contratos/lote", headers=AG1, json={"evento_id": EVENTO_TESTE})).status_code == 403
    finally:
        reset_rate_limits()
        if qid:
            await async_client.delete(f"{BASE}/{qid}", headers=A1)
        async with PlatformSessionLocal() as s:
            await s.execute(text("UPDATE conteudos SET professor_id = :p, quantidade = :q WHERE id_conteudo = 'ci-conteudo-1'"),
                            {"p": original[0], "q": original[1]})
            await s.commit()
        await _limpar()
