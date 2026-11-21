"""Financeiro (automações): lembretes, atraso e suspensão, limites do plano, bônus por qualidade, relatórios e RPA."""
import io
from datetime import date, datetime, timedelta

from pypdf import PdfReader
from sqlalchemy import delete, select, update

from backend.app import configuracoes, fin_calculo, fin_retencoes, fin_rotinas
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import FinContrato, FinFatura, Notificacao, PlanoBanca, Tenant, User
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import reset_rate_limits
from tests.conftest import EVENTO_TESTE
from tests.test_financeiro import A1, AG, AG1, HP, SENHA, _limpar


async def test_automations_reminders_limits_bonus_reports_and_rpa(async_client):
    reset_rate_limits()
    await _limpar()
    async with PlatformSessionLocal() as s:
        pid = (await s.execute(select(User.id).where(blind_eq(User.username, "vhugo")))).scalar_one()
    try:
        # ---- bônus por qualidade (cálculo)
        prod = {"aprovadas": 10, "aprovadas_primeira": 8}
        assert fin_calculo.bonus({"bonus": {"tipo": "por_questao", "valor": 5}}, prod, 1000) == 40
        assert fin_calculo.bonus({"bonus": {"tipo": "percentual", "valor": 10}}, prod, 1000) == 80
        assert fin_calculo.bonus({}, prod, 1000) == 0

        # ---- retenções do RPA (com o redutor do IRRF)
        r = fin_retencoes.calcular(6000, fin_retencoes.config({}))
        assert r["inss"] == 660 and r["irrf"] == 380.02 and r["liquido"] == 4959.98
        assert fin_retencoes.calcular(4000, fin_retencoes.config({}))["irrf"] == 0  # até R$ 5 mil: isento pelo redutor
        assert fin_retencoes.calcular(20000, fin_retencoes.config({}))["inss"] == 897.32  # teto

        # ---- contrato pessoa física: pagamento gera RPA e o recibo com o líquido
        cfg = (await async_client.get("/financeiro/config", headers=A1)).json()
        assert cfg["retencoes"]["inss_percentual"] == 11 and "pf_rpa" in cfg["tipos_pessoa"]
        corpo = {"professor_id": pid, "evento_id": EVENTO_TESTE, "modalidade": "valor_fechado", "valor_fechado": 12000,
                 "tipo_pessoa": "pf_rpa", "bonus": {"tipo": "por_questao", "valor": 10}}
        cid = (await async_client.post("/financeiro/contratos", headers=A1, json=corpo)).json()["id"]
        await async_client.post(f"/financeiro/contratos/{cid}/enviar", headers=A1)
        assert (await async_client.post(f"/financeiro/meu/contratos/{cid}/aceitar", headers=HP, json={"senha": SENHA})).status_code == 200
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert c["dados"]["bonus"] == {"tipo": "por_questao", "valor": 10.0} and c["dados"]["tipo_pessoa"] == "pf_rpa"
        p1 = c["parcelas"][0]
        rl = await async_client.post(f"/financeiro/parcelas/{p1['id']}/liberar", headers=A1, json={"justificativa": "Entrega conferida"})
        assert rl.status_code == 200, rl.text
        prev = (await async_client.get(f"/financeiro/parcelas/{p1['id']}/retencoes", headers=A1, params={"valor": 6000})).json()
        assert prev["aplica"] and prev["liquido"] == 4959.98
        r = await async_client.post(f"/financeiro/parcelas/{p1['id']}/pagar", headers=A1,
                                    data={"valor_pago": "6000", "data_pagamento": "2026-11-21", "forma": "PIX"})
        assert r.status_code == 200, r.text
        c = (await async_client.get(f"/financeiro/contratos/{cid}", headers=A1)).json()
        assert {d["tipo"] for d in c["documentos"]} >= {"rpa", "recibo"}
        assert c["parcelas"][0]["retencoes"]["liquido"] == 4959.98 and c["parcelas"][0]["pagamento"]["liquido"] == 4959.98
        rpa = next(d for d in c["documentos"] if d["tipo"] == "rpa")
        texto = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(
            (await async_client.get(f"/financeiro/documentos/{rpa['id']}/arquivo", headers=HP)).content)).pages)
        assert "RPA" in texto and "4.959,98" in texto

        # ---- relatórios
        res = (await async_client.get("/financeiro/relatorios/resumo", headers=A1)).json()["eventos"]
        assert res[0]["pago"] == 6000 and res[0]["retido"] == 1040.02
        csv = await async_client.get("/financeiro/relatorios/pagamentos.csv", headers=A1)
        assert csv.headers["content-type"].startswith("text/csv") and csv.content.startswith(b"\xef\xbb\xbf")
        conteudo = csv.content.decode("utf-8-sig")
        assert "Bruto;INSS;IRRF;ISS;Líquido" in conteudo and "6000,00;660,00;380,02;0,00;4959,98" in conteudo
        assert (await async_client.get("/financeiro/relatorios/contratos.csv", headers=AG1)).status_code == 403
        assert (await async_client.get("/plataforma/financeiro/relatorios/faturas.csv", headers=AG)).status_code == 200

        # ---- limites do plano: evento além do limite é recusado; uso aparece para a banca
        async with PlatformSessionLocal() as s:
            s.add(PlanoBanca(codigo="teste-limite", nome="Plano Teste Limite", valor_mensal=1, valor_anual=10, limite_eventos=1,
                             limite_usuarios=None, limite_questoes=None, ativo=True, criado_em=datetime.utcnow()))
            await s.execute(update(Tenant).where(Tenant.id == 1).values(plan_type="Plano Teste Limite"))
            await s.commit()
        vis = (await async_client.get("/financeiro/plataforma", headers=A1)).json()
        ev = next(i for i in vis["uso"]["itens"] if i["recurso"] == "eventos")
        assert vis["uso"]["plano"] == "Plano Teste Limite" and ev["limite"] == 1 and ev["uso"] >= 1
        r = await async_client.post("/eventos/", headers=A1, json={"nome_evento": "Excede", "data_prova": "2027-01-01", "senha_evento": "1234"})
        assert r.status_code == 403 and r.json()["detail"]["codigo"] == "limite_plano"

        # ---- rotinas: fatura vencendo, atraso com suspensão automática, contrato sem aceite
        async with PlatformSessionLocal() as s:
            await s.execute(delete(Notificacao))
            hoje = date.today()
            s.add(FinFatura(tenant_id=1, numero="F-TESTE-1", competencia="2026-12", vencimento=hoje + timedelta(days=2), status="aberta",
                            dados={"valor": 100.0, "descricao": "x"}, criado_em=datetime.utcnow()))
            s.add(FinFatura(tenant_id=2, numero="F-TESTE-2", competencia="2026-10", vencimento=hoje - timedelta(days=10), status="aberta",
                            dados={"valor": 200.0, "descricao": "y"}, criado_em=datetime.utcnow()))
            s.add(FinContrato(tenant_id=1, professor_id=pid, evento_id=EVENTO_TESTE, numero="9999-0001", status="enviado",
                              modalidade="valor_fechado", dados={"valor_fechado": 1}, criado_em=datetime.utcnow(),
                              enviado_em=datetime.utcnow() - timedelta(days=8)))
            await s.commit()
        assert (await async_client.put("/config/plataforma", headers=AG, json={"financeiro": {"suspender_apos_dias": 5}})).status_code == 200
        configuracoes._CACHE_PLATAFORMA["dados"] = None
        r = await fin_rotinas.executar()
        assert r["vencendo"] == 1 and r["atraso"] == 1 and r["suspensas"] == 1 and r["aceite"] == 1, r
        r2 = await fin_rotinas.executar()  # nada se repete no mesmo dia
        assert r2["vencendo"] == 0 and r2["atraso"] == 0 and r2["aceite"] == 0
        async with PlatformSessionLocal() as s:
            assert (await s.execute(select(Tenant.status).where(Tenant.id == 2))).scalar_one() == "bloqueado"
            titulos = [(n.conteudo or {}).get("titulo", "") for n in (await s.execute(select(Notificacao))).scalars()]
        assert any("vence em 2" in t for t in titulos) and any("em atraso" in t for t in titulos)
        assert any("aguardando o seu aceite" in t for t in titulos) and any("sem aceite" in t for t in titulos)
    finally:
        reset_rate_limits()
        await async_client.put("/config/plataforma", headers=AG, json={"financeiro": {"suspender_apos_dias": 0}})
        configuracoes._CACHE_PLATAFORMA["dados"] = None
        async with PlatformSessionLocal() as s:
            await s.execute(update(Tenant).where(Tenant.id.in_([1, 2])).values(status="ativo", plan_type=None))
            await s.execute(delete(PlanoBanca).where(PlanoBanca.codigo == "teste-limite"))
            await s.commit()
        await _limpar()
