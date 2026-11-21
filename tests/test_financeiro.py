"""Financeiro: contrato do professor (aceite com senha, parcelas, ajustes, pagamento, recibo, nota) e a plataforma
(propostas, termos, faturas). O administrador geral nunca vê a negociação da banca com os professores."""
import io

from pypdf import PdfReader
from sqlalchemy import delete, select, update

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import FinConfig, FinContrato, FinDocumento, FinFatura, FinProposta, FinTermo, Tenant, User
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import EVENTO_TESTE, auth_headers

A1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
A2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
HP = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
HD = auth_headers("vhugo1234", UserRole.DIAGRAMADOR, tenant_id=1)
AG = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
AG1 = {**AG, "X-Tenant-Id": "1"}
SENHA = "TestPassword123!"


def _pdf_simples() -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "comprovante")
    c.save()
    return buf.getvalue()


async def _limpar():
    async with PlatformSessionLocal() as s:
        for m in (FinDocumento, FinFatura, FinTermo, FinProposta):
            await s.execute(delete(m).where(m.tenant_id.in_([1, 2])))
        await s.execute(delete(FinContrato).where(FinContrato.tenant_id.in_([1, 2])))
        await s.execute(delete(FinConfig).where(FinConfig.tenant_id.in_([1, 2])))
        await s.execute(update(Tenant).where(Tenant.id == 1).values(plan_type=None, plan_expires_at=None))
        await s.commit()


async def test_professor_contract_installments_documents_and_no_admin_geral(async_client):
    reset_rate_limits()
    await _limpar()
    try:
        # ---- o administrador geral NÃO vê a negociação da banca com os professores (nem com o cliente escolhido)
        for h in (AG, AG1):
            assert (await async_client.get("/financeiro/visao", headers=h)).status_code == 403
            assert (await async_client.get("/financeiro/config", headers=h)).status_code == 403
        assert (await async_client.get("/financeiro/visao", headers=HD)).status_code == 403
        assert (await async_client.get("/financeiro/meu", headers=A1)).status_code == 403

        # ---- configuração da banca: preços, cronograma padrão 50/50, modelos de cláusulas
        cfg = (await async_client.get("/financeiro/config", headers=A1)).json()
        assert [p["percentual"] for p in cfg["cronograma"]] == [50.0, 50.0] and "{EVENTO}" in cfg["clausulas_contrato"]
        cfg["precos"]["MULTIPLA_ESCOLHA"] = 30
        assert (await async_client.put("/financeiro/config", headers=A1, json={k: cfg[k] for k in (
            "precos", "cronograma", "clausulas_contrato", "clausulas_cessao", "contratante", "observacoes_padrao")})).status_code == 200
        assert (await async_client.get("/financeiro/config", headers=A1)).json()["precos"]["MULTIPLA_ESCOLHA"] == 30

        # ---- contrato: negociação própria do professor (valor fechado, parcelas 50% entrega / 50% recursos)
        async with PlatformSessionLocal() as s:
            pid = (await s.execute(select(User.id).where(blind_eq(User.username, "vhugo")))).scalar_one()
        corpo = {"professor_id": pid, "evento_id": EVENTO_TESTE, "modalidade": "valor_fechado", "valor_fechado": 1000,
                 "prazo_entrega": "15/12/2026"}
        r = await async_client.post("/financeiro/contratos", headers=A1, json=corpo)
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        assert (await async_client.post("/financeiro/contratos", headers=A1, json=corpo)).status_code == 409  # um em andamento
        assert (await async_client.get(f"/financeiro/contratos/{cid}", headers=A2)).status_code == 404  # outra banca
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["status"] == "rascunho" and c["totais"]["previsto"] == 1000 and len(c["parcelas"]) == 2
        # o professor não vê rascunho
        assert all(x["id"] != cid for x in (await async_client.get("/financeiro/meu", headers=HP)).json()["contratos"])

        # ---- envio: gera o PDF (contrato + termo de cessão e sigilo); o professor aceita com a senha
        r = await async_client.post(f"/financeiro/contratos/{cid}/enviar", headers=A1)
        assert r.status_code == 200 and r.json()["codigo_verificacao"]
        meu = (await async_client.get("/financeiro/meu", headers=HP)).json()
        assert meu["pendentes_aceite"] == 1
        pdf = (await async_client.get(f"/financeiro/contratos/{cid}/pdf", headers=HP)).content
        paginas_original = len(PdfReader(io.BytesIO(pdf)).pages)
        texto = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf)).pages)
        assert "CESSÃO DE DIREITOS" in texto and "Evento CI Teste" in texto
        assert (await async_client.post(f"/financeiro/meu/contratos/{cid}/aceitar", headers=HP, json={"senha": "errada"})).status_code == 400
        # parcela não libera antes do aceite
        assert all(p["status"] == "prevista" for p in c["parcelas"])
        assert (await async_client.post(f"/financeiro/meu/contratos/{cid}/aceitar", headers=HP, json={"senha": SENHA})).status_code == 200
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["status"] == "aceito" and c["aceite"]["sha256"] and c["aceite"]["ip"] is not None
        pdf2 = (await async_client.get(f"/financeiro/contratos/{cid}/pdf", headers=A1)).content
        assert len(PdfReader(io.BytesIO(pdf2)).pages) == paginas_original + 1  # página do registro de aceite
        # aceito não se edita
        assert (await async_client.put(f"/financeiro/contratos/{cid}", headers=A1, json={**corpo, "parcelas": []})).status_code == 409

        # ---- parcela 2 (recursos): sem recursos, explica o que falta; a banca libera manualmente com justificativa
        p1, p2 = c["parcelas"]
        assert p2["gatilho"] == "recursos_respondidos" and p2["status"] == "prevista" and "recurso" in p2["explicacao"].lower()
        r = await async_client.post(f"/financeiro/parcelas/{p1['id']}/liberar", headers=A1, json={"justificativa": "Entrega conferida"})
        assert r.status_code == 200
        # ajuste: desconto com motivo (ex.: questão anulada por erro)
        r = await async_client.post(f"/financeiro/contratos/{cid}/ajustes", headers=A1,
                                    json={"parcela_id": p1["id"], "tipo": "desconto", "valor": 100, "motivo": "Questão 12 anulada por erro"})
        assert r.status_code == 201
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        p1 = c["parcelas"][0]
        assert p1["status"] == "liberada" and p1["valor_base"] == 500 and p1["a_pagar"] == 400
        assert c["totais"]["liberado"] == 400

        # ---- pagamento com comprovante; recibo gerado; o professor confirma; nota fiscal da parcela
        r = await async_client.post(f"/financeiro/parcelas/{p1['id']}/pagar", headers=A1,
                                    data={"valor_pago": "400", "data_pagamento": "2026-11-21", "forma": "PIX"},
                                    files={"comprovante": ("comprovante.pdf", _pdf_simples(), "application/pdf")})
        assert r.status_code == 200, r.text
        assert (await async_client.post(f"/financeiro/contratos/{cid}/ajustes", headers=A1,
                                         json={"parcela_id": p1["id"], "tipo": "acrescimo", "valor": 1, "motivo": "teste"})).status_code == 409
        meu = (await async_client.get("/financeiro/meu", headers=HP)).json()
        cm = next(x for x in meu["contratos"] if x["id"] == cid)
        recibo = next(d for d in cm["documentos"] if d["tipo"] == "recibo")
        assert (await async_client.get(f"/financeiro/documentos/{recibo['id']}/arquivo", headers=HP)).content[:4] == b"%PDF"
        assert (await async_client.post(f"/financeiro/meu/parcelas/{p1['id']}/confirmar", headers=HP)).status_code == 200
        r = await async_client.post(f"/financeiro/meu/parcelas/{p2['id']}/nota-fiscal", headers=HP, data={"tipo": "nota_fiscal"},
                                    files={"arquivo": ("nf.pdf", _pdf_simples(), "application/pdf")})
        assert r.status_code == 201
        assert (await async_client.post(f"/financeiro/meu/parcelas/{p2['id']}/nota-fiscal", headers=HP, data={"tipo": "nota_fiscal"},
                                         files={"arquivo": ("x.exe", b"MZ", "application/octet-stream")})).status_code == 400
        meu = (await async_client.get("/financeiro/meu", headers=HP)).json()
        assert meu["totais"]["pago"] == 400 and meu["totais"]["liberado"] == 400
        visao = (await async_client.get("/financeiro/visao", headers=A1)).json()
        assert visao["totais"]["pago"] == 400

        # ---- o administrador geral não baixa documento do professor (nem pela rota da plataforma)
        assert (await async_client.get(f"/plataforma/financeiro/arquivo/documento/{recibo['id']}", headers=AG)).status_code == 404
        assert (await async_client.get(f"/financeiro/documentos/{recibo['id']}/arquivo", headers=AG1)).status_code == 404
        # cancelar com parcela paga: não (encerrar sim)
        assert (await async_client.post(f"/financeiro/contratos/{cid}/cancelar", headers=A1, json={"motivo": "x"})).status_code == 409
        assert (await async_client.post(f"/financeiro/contratos/{cid}/encerrar", headers=A1)).status_code == 200
    finally:
        reset_rate_limits()
        await _limpar()


async def test_platform_plans_proposals_terms_and_invoices(async_client):
    reset_rate_limits()
    await _limpar()
    try:
        assert (await async_client.get("/plataforma/financeiro/bancas", headers=A1)).status_code == 403
        planos = (await async_client.get("/plataforma/financeiro/planos", headers=AG)).json()
        assert len(planos) >= 1
        plano = planos[0]

        # proposta com desconto; nova versão substitui a anterior
        r = await async_client.post("/plataforma/financeiro/bancas/1/propostas", headers=AG,
                                    json={"plano_id": plano["id"], "periodicidade": "mensal", "desconto": 10, "condicoes": "Pagamento até o dia 10"})
        assert r.status_code == 201, r.text
        r = await async_client.post("/plataforma/financeiro/bancas/1/propostas", headers=AG,
                                    json={"plano_id": plano["id"], "periodicidade": "mensal", "desconto": 20})
        prop = r.json()
        assert prop["versao"] == 2 and prop["valor_final"] == round(plano["valor_mensal"] * 0.8, 2)
        vis = (await async_client.get("/financeiro/plataforma", headers=A1)).json()
        assert [p["status"] for p in vis["propostas"]] == ["enviada", "substituida"]
        assert (await async_client.get("/financeiro/plataforma", headers=A2)).json()["propostas"] == []  # outra banca não vê
        assert (await async_client.get(f"/financeiro/plataforma/arquivo/proposta/{prop['id']}", headers=A1)).content[:4] == b"%PDF"
        assert (await async_client.post(f"/financeiro/plataforma/propostas/{prop['id']}/aceitar", headers=A1, json={"senha": "x"})).status_code == 400
        assert (await async_client.post(f"/financeiro/plataforma/propostas/{prop['id']}/aceitar", headers=A1, json={"senha": SENHA})).status_code == 200
        assert (await async_client.post(f"/financeiro/plataforma/propostas/{prop['id']}/aceitar", headers=A2, json={"senha": SENHA})).status_code == 409
        vis = (await async_client.get("/financeiro/plataforma", headers=A1)).json()
        assert vis["plano"]["plano"] == plano["nome"] and vis["plano"]["vence_em"]

        # termo (texto vira PDF) aceito pela banca
        r = await async_client.post("/plataforma/financeiro/bancas/1/termos", headers=AG,
                                    data={"tipo": "lgpd", "titulo": "Acordo de tratamento de dados", "texto": "Cláusula 1..."})
        termo = r.json()
        assert r.status_code == 201 and termo["status"] == "pendente"
        assert (await async_client.post(f"/financeiro/plataforma/termos/{termo['id']}/aceitar", headers=A1, json={"senha": SENHA})).status_code == 200

        # fatura a partir da proposta aceita; comprovante -> análise -> devolvido -> de novo -> confirmado
        r = await async_client.post("/plataforma/financeiro/bancas/1/faturas", headers=AG, json={"competencia": "2026-12", "vencimento": "2026-12-10"})
        assert r.status_code == 201, r.text
        fat = r.json()
        assert fat["valor"] == prop["valor_final"] and fat["status"] == "aberta"
        assert (await async_client.post("/plataforma/financeiro/bancas/1/faturas", headers=AG,
                                         json={"competencia": "2026-12", "vencimento": "2026-12-10"})).status_code == 409
        arq = {"arquivo": ("comp.pdf", _pdf_simples(), "application/pdf")}
        assert (await async_client.post(f"/financeiro/plataforma/faturas/{fat['id']}/comprovante", headers=A1, files=arq)).status_code == 200
        assert (await async_client.post(f"/plataforma/financeiro/faturas/{fat['id']}/devolver", headers=AG, json={"motivo": "Valor diferente"})).status_code == 200
        vis = (await async_client.get("/financeiro/plataforma", headers=A1)).json()
        assert vis["faturas"][0]["status"] == "aberta" and vis["faturas"][0]["motivo_devolucao"] == "Valor diferente"
        assert (await async_client.post(f"/financeiro/plataforma/faturas/{fat['id']}/comprovante", headers=A1, files=arq)).status_code == 200
        assert (await async_client.post(f"/plataforma/financeiro/faturas/{fat['id']}/confirmar", headers=AG)).status_code == 200
        bancas = {b["id"]: b for b in (await async_client.get("/plataforma/financeiro/bancas", headers=AG)).json()}
        assert bancas[1]["recebido"] == prop["valor_final"] and bancas[1]["termos_pendentes"] == 0
        # vencida e em aberto aparece como atrasada
        r = await async_client.post("/plataforma/financeiro/bancas/1/faturas", headers=AG,
                                    json={"competencia": "2025-01", "vencimento": "2025-01-10", "valor": 50})
        assert r.json()["status"] == "atrasada"
        # banca e professor não mexem na plataforma
        assert (await async_client.post(f"/plataforma/financeiro/faturas/{fat['id']}/confirmar", headers=A1)).status_code == 403
        assert (await async_client.get("/financeiro/plataforma", headers=HP)).status_code == 403
    finally:
        reset_rate_limits()
        await _limpar()
