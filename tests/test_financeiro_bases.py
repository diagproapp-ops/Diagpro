"""Cada negociação do seu jeito: base do pagamento (aprovadas, entregues ou integral) no contrato e em cada parcela,
liberação na assinatura, na entrega (aprovada ou não) e liberação manual com outro valor combinado."""
import io

from pypdf import PdfReader
from sqlalchemy import select, text

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import User
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import reset_rate_limits
from tests.conftest import EVENTO_TESTE
from tests.test_financeiro import A1, HP, SENHA, _limpar
from tests.test_financeiro_quantidades import BASE, COMUM


async def _status(qid: str, status: str) -> None:
    async with PlatformSessionLocal() as s:
        await s.execute(text('UPDATE "QuestoesBanco" SET status_revisao = :s WHERE id_questao = :q'), {"s": status, "q": qid})
        await s.commit()


async def _contrato(client, pid, **extra) -> dict:
    corpo = {"professor_id": pid, "evento_id": EVENTO_TESTE, "precos": {"MULTIPLA_ESCOLHA": 100}, "quantidades": {"MULTIPLA_ESCOLHA": 10}}
    corpo.update(extra)
    r = await client.post("/financeiro/contratos", headers=A1, json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


async def _aceitar(client, cid) -> dict:
    assert (await client.post(f"/financeiro/contratos/{cid}/enviar", headers=A1)).status_code == 200
    r = await client.post(f"/financeiro/meu/contratos/{cid}/aceitar", headers=HP, json={"senha": SENHA})
    assert r.status_code == 200, r.text
    return (await client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()


async def test_payment_bases_triggers_and_manual_value(async_client):
    reset_rate_limits()
    await _limpar()
    async with PlatformSessionLocal() as s:
        pid = (await s.execute(select(User.id).where(blind_eq(User.username, "vhugo")))).scalar_one()
    qids = []
    try:
        # ---- configuração: bases disponíveis e a padrão
        cfg = (await async_client.get("/financeiro/config", headers=A1)).json()
        assert set(cfg["bases"]) == {"aprovadas", "entregues", "integral"} and cfg["base_pagamento_padrao"] == "aprovadas"
        assert {"aceite", "entrega"} <= set(cfg["gatilhos"])

        # ---- INTEGRAL: 50% na assinatura + 50% integral nos recursos; sem nenhuma questão aprovada
        parcelas = [{"descricao": "Na assinatura", "percentual": 50, "gatilho": "aceite"},
                    {"descricao": "Após recursos", "percentual": 50, "gatilho": "recursos_respondidos"}]
        cid = (await _contrato(async_client, pid, base_pagamento="integral", parcelas=parcelas))["id"]
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["base_pagamento"] == "integral" and c["totais"]["apurado"] == 1000.0
        c = await _aceitar(async_client, cid)
        p1, p2 = c["parcelas"]
        assert p1["status"] == "liberada" and p1["a_pagar"] == 500.0, p1  # liberou sozinha na assinatura, valor integral
        assert p2["status"] == "prevista" and p2["valor_base"] == 500.0
        pdf = (await async_client.get(f"/financeiro/contratos/{cid}/pdf", headers=A1)).content
        txt = " ".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf)).pages)
        assert "valor integral contratado" in txt and "só questões aprovadas" not in txt

        # ---- liberação manual com outro valor combinado (fica registrado o calculado)
        r = await async_client.post(f"/financeiro/parcelas/{p2['id']}/liberar", headers=A1,
                                    json={"justificativa": "Acordo: antecipação parcial", "valor": 320.5})
        assert r.status_code == 200, r.text
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["parcelas"][1]["a_pagar"] == 320.5 and c["totais"]["liberado"] == 820.5
        await async_client.post(f"/financeiro/contratos/{cid}/cancelar", headers=A1, json={"motivo": "teste"})

        # ---- ENTREGUES + parcela com base própria (integral) + gatilho "entrega"
        for _ in range(2):
            r = await async_client.post(BASE, headers=HP, data=COMUM)
            assert r.status_code == 200, r.text
            qids.append(r.json()["id_questao"])
        await _status(qids[0], "ENVIADA")
        await _status(qids[1], "RASCUNHO")
        parcelas = [{"descricao": "Entrega", "percentual": 60, "gatilho": "entrega"},
                    {"descricao": "Final", "percentual": 40, "gatilho": "manual", "base": "integral"}]
        cid = (await _contrato(async_client, pid, base_pagamento="entregues", quantidades={"MULTIPLA_ESCOLHA": 2}, parcelas=parcelas))["id"]
        c = await _aceitar(async_client, cid)
        assert c["totais"]["apurado_base"] == 100.0  # 1 entregue (a outra é rascunho) x R$ 100
        p1, p2 = c["parcelas"]
        assert p1["status"] == "prevista" and "1 de 2 questões entregues" in p1["explicacao"]
        assert p2["base"] == "integral" and p2["valor_base"] == 80.0  # 40% de 2 x 100 contratadas
        await _status(qids[1], "AJUSTES")  # entregue (voltou com ajustes): conta, mesmo sem aprovação
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["parcelas"][0]["status"] == "liberada" and c["parcelas"][0]["a_pagar"] == 120.0  # 60% de 2 entregues x 100
        await async_client.post(f"/financeiro/contratos/{cid}/cancelar", headers=A1, json={"motivo": "teste"})

        # ---- APROVADAS continua igual (padrão): entregues não contam
        cid = (await _contrato(async_client, pid, quantidades={"MULTIPLA_ESCOLHA": 2}))["id"]
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["base_pagamento"] == "aprovadas" and c["totais"]["apurado"] == 0.0
        await _status(qids[0], "APROVADA")
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["totais"]["apurado"] == 100.0

        # ---- base inválida é recusada
        r = await async_client.put(f"/financeiro/contratos/{cid}", headers=A1, json={
            "professor_id": pid, "evento_id": EVENTO_TESTE,
            "parcelas": [{"descricao": "x", "percentual": 100, "gatilho": "manual", "base": "tudo"}]})
        assert r.status_code == 400
    finally:
        reset_rate_limits()
        for q in qids:
            await async_client.delete(f"{BASE}/{q}", headers=A1)
        await _limpar()
