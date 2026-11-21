"""
Financeiro banca x professor: produção apurada, valores do contrato, gatilhos das parcelas e extrato.

Regras (o administrador da banca pode sempre ajustar à mão, com justificativa):
- produção = questões do professor no evento (criador da questão ou professor do conteúdo), contadas por tipo;
  só entram as APROVADAS na revisão; questões anuladas aparecem como sugestão de desconto, nunca descontam sozinhas;
- total apurado = preço x produção aprovada (por questão) ou o valor fechado; total previsto = preço x quantidade
  contratada (ou o valor fechado);
- parcela = valor fixo ou percentual do total (apurado; enquanto nada foi aprovado, mostra a estimativa pelo previsto);
  na liberação o valor fica congelado; ajustes (desconto, acréscimo, adiantamento) entram na parcela escolhida.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db_models import (
    Conteudo, FinAjuste, FinContrato, FinParcela, HistoricoRevisaoQuestao, ItensVerdadeiroFalso, QuestoesBanco, Recurso,
)

PRECOS = {
    "MULTIPLA_ESCOLHA": "Múltipla escolha (por questão)",
    "CERTO_ERRADO_ITEM": "Certo/Errado (por item)",
    "CERTO_ERRADO_BASE": "Certo/Errado (por questão-base)",
    "DISCURSIVA": "Discursiva (por questão)",
    "SUBJETIVA": "Subjetiva (por questão)",
}
GATILHOS = {
    "entrega_aprovada": "Entrega das questões aprovadas na revisão",
    "recursos_respondidos": "Recursos das questões respondidos",
    "data": "Na data combinada",
    "manual": "Liberação manual pela banca",
}
MODALIDADES = {"por_questao": "Por questão elaborada", "valor_fechado": "Valor fechado"}
TIPOS_AJUSTE = {"desconto": -1, "adiantamento": -1, "acrescimo": 1}

CLAUSULAS_CONTRATO = """1. OBJETO. O CONTRATADO elaborará questões inéditas para o evento {EVENTO}, conforme as quantidades, os tipos e os prazos deste contrato, seguindo o edital e as orientações da {BANCA}.
2. ENTREGA E REVISÃO. As questões serão entregues pelo DiagPro até {PRAZO_ENTREGA}. Questões devolvidas pela revisão devem ser corrigidas no prazo combinado; só questões aprovadas contam para a remuneração.
3. REMUNERAÇÃO. O valor total estimado é de {VALOR_TOTAL}, pago nas parcelas e nas condições descritas neste documento, mediante a nota fiscal ou o RPA correspondente.
4. RECURSOS. O CONTRATADO se compromete a elaborar os pareceres sobre os recursos interpostos às suas questões, no prazo indicado pela {BANCA}.
5. QUALIDADE. Questões anuladas por erro de elaboração podem gerar desconto proporcional, sempre informado e justificado no DiagPro.
6. VIGÊNCIA. Este contrato vale do aceite até a conclusão da fase de recursos do evento."""

CLAUSULAS_CESSAO = """1. CESSÃO DE DIREITOS. O CONTRATADO cede à {BANCA}, de forma total, definitiva e exclusiva, os direitos patrimoniais de autor sobre as questões elaboradas, que poderão ser utilizadas, publicadas e adaptadas pela {BANCA}.
2. INEDITISMO. O CONTRATADO declara que as questões são inéditas, de sua autoria, e não violam direitos de terceiros.
3. SIGILO. O CONTRATADO manterá sigilo absoluto sobre as questões, as provas e qualquer informação do evento, antes e depois da aplicação, não podendo divulgá-las, guardá-las fora do DiagPro ou utilizá-las em outros trabalhos.
4. RESPONSABILIDADE. O vazamento de qualquer conteúdo sujeita o CONTRATADO às responsabilidades civil e criminal previstas em lei.
5. DADOS PESSOAIS. Os dados pessoais do CONTRATADO são tratados apenas para a execução deste contrato, conforme a LGPD."""

CONFIG_PADRAO = {
    "precos": {k: 0.0 for k in PRECOS},
    "cronograma": [
        {"descricao": "Entrega das questões aprovadas", "percentual": 50.0, "gatilho": "entrega_aprovada"},
        {"descricao": "Após a resposta aos recursos", "percentual": 50.0, "gatilho": "recursos_respondidos"},
    ],
    "clausulas_contrato": CLAUSULAS_CONTRATO,
    "clausulas_cessao": CLAUSULAS_CESSAO,
    "contratante": {"razao_social": "", "cnpj": "", "endereco": "", "cidade": ""},
    "observacoes_padrao": "",
    # bônus por qualidade: questões aprovadas na PRIMEIRA revisão (sem devolução com ajustes nem reprovação)
    "bonus_padrao": {"tipo": "nenhum", "valor": 0.0},
    "tipo_pessoa_padrao": "pf_rpa",
}
TIPOS_BONUS = {"nenhum": "Sem bônus", "por_questao": "R$ por questão aprovada de primeira",
               "percentual": "% sobre o valor das questões aprovadas de primeira"}
TIPOS_PESSOA = {"pf_rpa": "Pessoa física (RPA, com retenções)", "pj_nf": "Pessoa jurídica / MEI (nota fiscal)"}


def moeda(v: float) -> str:
    s = f"{abs(float(v or 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if (v or 0) < 0 else "R$ ") + s


def num(v, padrao: float = 0.0) -> float:
    try:
        x = float(v)
        return x if x == x and abs(x) < 1e12 else padrao
    except (TypeError, ValueError):
        return padrao


# ------------------------------------------------------------------------------------------------ produção
async def questoes_do_professor(db: AsyncSession, tenant_id: int, evento_id: str, professor_id: int) -> list[QuestoesBanco]:
    conteudos = [c.id_conteudo for c in (await db.execute(select(Conteudo).where(
        Conteudo.tenant_id == tenant_id, Conteudo.evento_id == evento_id,
        Conteudo.professor_id == str(professor_id)))).scalars()]
    q = select(QuestoesBanco).where(QuestoesBanco.tenant_id == tenant_id, QuestoesBanco.id_evento_fk == evento_id)
    cond = QuestoesBanco.criador_id == str(professor_id)
    if conteudos:
        cond = cond | QuestoesBanco.conteudo_id.in_(conteudos)
    return list((await db.execute(q.where(cond))).scalars().all())


async def producao(db: AsyncSession, tenant_id: int, evento_id: str, professor_id: int) -> dict:
    questoes = await questoes_do_professor(db, tenant_id, evento_id, professor_id)
    aprovadas = [x for x in questoes if (x.status_revisao or "").upper() == "APROVADA"]
    por_tipo: dict[str, dict] = {}
    for x in questoes:
        t = (x.tipo or "MULTIPLA_ESCOLHA").upper()
        d = por_tipo.setdefault(t, {"total": 0, "aprovadas": 0})
        d["total"] += 1
        d["aprovadas"] += (x in aprovadas)
    devolvidas = set()
    if aprovadas:
        devolvidas = {h for h in (await db.execute(select(HistoricoRevisaoQuestao.id_questao_fk).where(
            HistoricoRevisaoQuestao.id_questao_fk.in_([x.id_questao for x in aprovadas]),
            HistoricoRevisaoQuestao.status_revisao.in_(["AJUSTES", "REPROVADA"])))).scalars()}
    primeira = [x for x in aprovadas if x.id_questao not in devolvidas]
    ids_ce = [x.id_questao for x in aprovadas if (x.tipo or "").upper() == "CERTO_ERRADO"]
    itens_ce = 0
    if ids_ce:
        itens_ce = (await db.execute(select(func.count(ItensVerdadeiroFalso.id_item_vf)).where(
            ItensVerdadeiroFalso.id_questao_fk.in_(ids_ce)))).scalar_one()
    return {
        "total": len(questoes),
        "aprovadas": len(aprovadas),
        "aprovadas_primeira": len(primeira),
        "pendentes": len(questoes) - len(aprovadas),
        "por_tipo": por_tipo,
        "itens_ce_aprovados": int(itens_ce),
        "anuladas": [x.codigo_curto_questao or x.id_questao for x in questoes if x.anulada],
        "ids": [x.id_questao for x in questoes],
    }


def unidades_aprovadas(prod: dict) -> dict[str, int]:
    pt = prod.get("por_tipo", {})
    return {
        "MULTIPLA_ESCOLHA": pt.get("MULTIPLA_ESCOLHA", {}).get("aprovadas", 0),
        "CERTO_ERRADO_ITEM": prod.get("itens_ce_aprovados", 0),
        "CERTO_ERRADO_BASE": pt.get("CERTO_ERRADO", {}).get("aprovadas", 0),
        "DISCURSIVA": pt.get("DISCURSIVA", {}).get("aprovadas", 0),
        "SUBJETIVA": pt.get("SUBJETIVA", {}).get("aprovadas", 0),
    }


def total_previsto(modalidade: str, dados: dict) -> float:
    if modalidade == "valor_fechado":
        return round(num(dados.get("valor_fechado")), 2)
    precos, qtd = dados.get("precos", {}), dados.get("quantidades", {})
    return round(sum(num(precos.get(k)) * num(qtd.get(k)) for k in PRECOS), 2)


def total_apurado(modalidade: str, dados: dict, prod: dict) -> float:
    if modalidade == "valor_fechado":
        return round(num(dados.get("valor_fechado")), 2)
    precos, uni = dados.get("precos", {}), unidades_aprovadas(prod)
    return round(sum(num(precos.get(k)) * uni.get(k, 0) for k in PRECOS), 2)


def bonus(dados: dict, prod: dict, apurado: float) -> float:
    """Bônus por qualidade (questões aprovadas de primeira). Percentual: sobre a parte do apurado dessas questões."""
    b = dados.get("bonus") or {}
    tipo, valor = b.get("tipo", "nenhum"), num(b.get("valor"))
    primeira, aprovadas = prod.get("aprovadas_primeira", 0), prod.get("aprovadas", 0)
    if tipo == "por_questao":
        return round(valor * primeira, 2)
    if tipo == "percentual" and aprovadas:
        return round(apurado * (primeira / aprovadas) * valor / 100.0, 2)
    return 0.0


async def recursos(db: AsyncSession, tenant_id: int, evento_id: str, ids_questoes: list[str]) -> dict:
    if not ids_questoes:
        return {"total": 0, "pendentes": 0}
    linhas = (await db.execute(select(Recurso.status).where(
        Recurso.tenant_id == tenant_id, Recurso.evento_id == evento_id, Recurso.id_questao.in_(ids_questoes)))).scalars().all()
    return {"total": len(linhas), "pendentes": sum(1 for s in linhas if (s or "").lower() == "pendente")}


# ------------------------------------------------------------------------------------------------ parcelas
def avaliar_gatilho(gatilho: str, data_prevista: date | None, contrato: FinContrato, dados_contrato: dict,
                    prod: dict, rec: dict, hoje: date) -> tuple[bool, str]:
    """(cumprido, explicação do que falta) — o texto aparece para a banca e para o professor."""
    if contrato.status not in ("aceito", "encerrado"):
        return False, "O contrato ainda não foi aceito pelo professor."
    if gatilho == "entrega_aprovada":
        contratadas = int(sum(num(v) for k, v in (dados_contrato.get("quantidades") or {}).items() if k != "CERTO_ERRADO_ITEM"))
        if prod["total"] == 0:
            return False, "Nenhuma questão entregue ainda."
        if contratadas and prod["aprovadas"] < contratadas:
            return False, f"{prod['aprovadas']} de {contratadas} questões aprovadas."
        if prod["pendentes"]:
            return False, f"{prod['pendentes']} questão(ões) ainda em elaboração ou revisão."
        return True, f"{prod['aprovadas']} questões aprovadas."
    if gatilho == "recursos_respondidos":
        if rec["total"] == 0:
            return False, "Nenhum recurso registrado nas questões até agora. A banca libera quando encerrar a fase de recursos."
        if rec["pendentes"]:
            return False, f"{rec['pendentes']} de {rec['total']} recursos ainda sem decisão."
        return True, f"Todos os {rec['total']} recursos decididos."
    if gatilho == "data":
        if not data_prevista:
            return False, "Data não definida."
        if hoje < data_prevista:
            return False, f"Libera em {data_prevista.strftime('%d/%m/%Y')}."
        return True, f"Data {data_prevista.strftime('%d/%m/%Y')} atingida."
    return False, "Aguardando liberação pela banca."


def valor_base_parcela(dp: dict, total_ref: float) -> float:
    if dp.get("valor_fixo") not in (None, ""):
        return round(num(dp.get("valor_fixo")), 2)
    return round(total_ref * num(dp.get("percentual")) / 100.0, 2)


def efeito_ajuste(a: FinAjuste) -> float:
    return TIPOS_AJUSTE.get(a.tipo, 0) * num((a.dados or {}).get("valor"))


async def contrato_completo(db: AsyncSession, c: FinContrato, persistir: bool = True) -> dict:
    """Contrato com produção, totais, parcelas (gatilhos avaliados; liberação automática quando cumpridos)."""
    dados = c.dados or {}
    prod = await producao(db, c.tenant_id, c.evento_id, c.professor_id)
    rec = await recursos(db, c.tenant_id, c.evento_id, prod["ids"])
    previsto = total_previsto(c.modalidade, dados)
    apurado_base = total_apurado(c.modalidade, dados, prod)
    valor_bonus = bonus(dados, prod, apurado_base)
    apurado = round(apurado_base + valor_bonus, 2)
    referencia = apurado if apurado > 0 else previsto
    liberadas_agora = []
    parcelas = (await db.execute(select(FinParcela).where(FinParcela.contrato_id == c.id).order_by(FinParcela.ordem))).scalars().all()
    ajustes = (await db.execute(select(FinAjuste).where(FinAjuste.contrato_id == c.id).order_by(FinAjuste.id))).scalars().all()
    hoje, mudou = date.today(), False
    saida_parcelas, liberado, pago = [], 0.0, 0.0
    for p in parcelas:
        dp = dict(p.dados or {})
        cumprido, explicacao = avaliar_gatilho(p.gatilho, p.data_prevista, c, dados, prod, rec, hoje)
        if persistir and p.status == "prevista" and cumprido:
            dp["valor_liberado"] = valor_base_parcela(dp, apurado if apurado > 0 else previsto)
            dp["liberacao"] = "automática: " + explicacao
            p.status, p.liberada_em, p.dados, mudou = "liberada", datetime.utcnow(), dp, True
            liberadas_agora.append((p.ordem, dp["valor_liberado"]))
        base = num(dp["valor_liberado"]) if dp.get("valor_liberado") is not None else valor_base_parcela(dp, referencia)
        meus = [a for a in ajustes if a.parcela_id == p.id]
        a_pagar = round(base + sum(efeito_ajuste(a) for a in meus), 2)
        if p.status in ("liberada", "paga", "confirmada"):
            liberado += a_pagar
        if p.status in ("paga", "confirmada"):
            pago += num(dp.get("valor_pago"), a_pagar)
        saida_parcelas.append({
            "id": p.id, "ordem": p.ordem, "descricao": dp.get("descricao", ""), "gatilho": p.gatilho,
            "gatilho_rotulo": GATILHOS.get(p.gatilho, p.gatilho), "percentual": dp.get("percentual"),
            "valor_fixo": dp.get("valor_fixo"), "data_prevista": p.data_prevista.isoformat() if p.data_prevista else None,
            "status": p.status, "valor_base": base, "estimado": dp.get("valor_liberado") is None, "a_pagar": a_pagar,
            "valor_pago": dp.get("valor_pago"), "gatilho_cumprido": cumprido, "explicacao": explicacao,
            "liberacao": dp.get("liberacao"), "pagamento": dp.get("pagamento"), "retencoes": dp.get("retencoes"),
            "liberada_em": _iso(p.liberada_em), "paga_em": _iso(p.paga_em), "confirmada_em": _iso(p.confirmada_em),
            "ajustes": [{"id": a.id, "tipo": a.tipo, "valor": num((a.dados or {}).get("valor")),
                         "motivo": (a.dados or {}).get("motivo", ""), "criado_em": _iso(a.criado_em)} for a in meus],
        })
    if mudou:
        await db.commit()
        await _avisar_liberacao(db, c, liberadas_agora)
    return {
        "id": c.id, "numero": c.numero, "status": c.status, "modalidade": c.modalidade, "evento_id": c.evento_id,
        "professor_id": c.professor_id, "dados": dados, "codigo_verificacao": c.codigo_verificacao,
        "tem_documento": bool(c.documento_ref), "aceite": c.aceite,
        "criado_em": _iso(c.criado_em), "enviado_em": _iso(c.enviado_em), "respondido_em": _iso(c.respondido_em),
        "encerrado_em": _iso(c.encerrado_em),
        "producao": {k: v for k, v in prod.items() if k != "ids"}, "recursos": rec,
        "totais": {"previsto": previsto, "apurado": apurado, "apurado_base": apurado_base, "bonus": valor_bonus,
                   "liberado": round(liberado, 2), "pago": round(pago, 2),
                   "a_receber": round(liberado - pago, 2),
                   "ajustes": round(sum(efeito_ajuste(a) for a in ajustes), 2)},
        "parcelas": saida_parcelas,
    }


async def _avisar_liberacao(db: AsyncSession, c: FinContrato, liberadas: list) -> None:
    """Parcela liberada sozinha (gatilho cumprido): avisa o professor e os administradores da banca."""
    from backend.app import notificacoes
    from backend.app.db_models import User
    for ordem, valor in liberadas:
        await notificacoes.notificar(c.professor_id, "sistema", f"Parcela {ordem} liberada",
                                     f"A parcela {ordem} do contrato {c.numero} ({moeda(valor)}) foi liberada: a condição foi cumprida.",
                                     "/financeiro", tenant_id=c.tenant_id)
    admins = [u.id for u in (await db.execute(select(User).where(User.tenant_id == c.tenant_id, User.role == "administrador",
                                                                 User.is_active.is_(True)))).scalars()]
    for ordem, valor in liberadas:
        await notificacoes.notificar_varios(admins, "sistema", f"Parcela {ordem} do contrato {c.numero} liberada",
                                            f"Condição cumprida: {moeda(valor)} a pagar.", "/financeiro", tenant_id=c.tenant_id)


def _iso(d) -> str | None:
    if d is None:
        return None
    return d.isoformat() + ("Z" if isinstance(d, datetime) else "")
