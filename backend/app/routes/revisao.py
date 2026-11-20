# backend/app/routes/revisao.py
"""Fluxo de revisão: enviar questão para revisão, fila do revisor e resumo da banca."""
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import fluxo_revisao as fr
from backend.app.db_models import Conteudo, Evento, HistoricoRevisaoQuestao, QuestoesBanco, User
from backend.app.roles import UserRole
from backend.app.security import get_tenant_db, require_roles

router = APIRouter(prefix="/revisao", tags=["Revisão"])
_REVISORES = require_roles(UserRole.REVISOR, UserRole.ADMIN, UserRole.ADMIN_GERAL)


def _tenant(user) -> int:
    if user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Escolha um cliente no topo da tela.")
    return user.tenant_id


class EnviarIn(BaseModel):
    mensagem: str = Field("", max_length=2000)


@router.post("/questoes/{id_questao}/enviar")
async def enviar(id_questao: str, dados: Optional[EnviarIn] = None, db: AsyncSession = Depends(get_tenant_db),
                 current_user=Depends(require_roles(UserRole.PROFESSOR, UserRole.ADMIN, UserRole.ADMIN_GERAL))):
    tenant = _tenant(current_user)
    q = (await db.execute(select(QuestoesBanco).where(
        QuestoesBanco.id_questao == id_questao, QuestoesBanco.tenant_id == tenant))).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")
    await fr.enviar_para_revisao(db, q, current_user, (dados.mensagem if dados else ""))
    return {"status_revisao": fr.ENVIADA}


@router.get("/fila")
async def fila(status: str = fr.ENVIADA, evento_id: Optional[str] = None,
               db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_REVISORES)):
    """Questões da banca num estado (padrão: aguardando revisão), com evento, conteúdo e autor."""
    tenant = _tenant(current_user)
    status = status.upper()
    if status not in fr.ROTULOS:
        raise HTTPException(status_code=400, detail="Estado de revisão inválido.")
    q = select(QuestoesBanco).where(QuestoesBanco.tenant_id == tenant)
    if status == fr.RASCUNHO:
        q = q.where((QuestoesBanco.status_revisao.is_(None)) | (QuestoesBanco.status_revisao.in_(["", fr.RASCUNHO])))
    else:
        q = q.where(QuestoesBanco.status_revisao == status)
    if evento_id:
        q = q.where(QuestoesBanco.id_evento_fk == evento_id)
    questoes = (await db.execute(q.order_by(QuestoesBanco.data_modificacao.asc()).limit(500))).scalars().all()

    ids_ev = {x.id_evento_fk for x in questoes}
    ids_ct = {x.conteudo_id for x in questoes if x.conteudo_id}
    eventos = {e.id_evento: e.nome_evento for e in (await db.execute(select(Evento).where(Evento.id_evento.in_(ids_ev)))).scalars()} if ids_ev else {}
    conteudos = {c.id_conteudo: c for c in (await db.execute(select(Conteudo).where(Conteudo.id_conteudo.in_(ids_ct)))).scalars()} if ids_ct else {}
    nomes = {u.id: u.username for u in (await db.execute(select(User).where(User.tenant_id == tenant))).scalars()}
    envios = {}
    if questoes:
        for h in (await db.execute(select(HistoricoRevisaoQuestao).where(
                HistoricoRevisaoQuestao.id_questao_fk.in_([x.id_questao for x in questoes]),
                HistoricoRevisaoQuestao.status_revisao == fr.ENVIADA))).scalars():
            if h.id_questao_fk not in envios or h.data_revisao > envios[h.id_questao_fk].data_revisao:
                envios[h.id_questao_fk] = h

    itens = []
    for x in questoes:
        ct = conteudos.get(x.conteudo_id)
        autor = None
        for cand in (x.criador_id, ct.professor_id if ct else None):
            if cand and str(cand).isdigit() and int(cand) in nomes:
                autor = nomes[int(cand)]
                break
        envio = envios.get(x.id_questao)
        itens.append({
            "id_questao": x.id_questao, "codigo": x.codigo_curto_questao, "tipo": x.tipo, "status": fr.status_de(x),
            "evento_id": x.id_evento_fk, "evento": eventos.get(x.id_evento_fk), "conteudo_id": x.conteudo_id,
            "conteudo": ct.nome_conteudo if ct else None, "autor": autor,
            "enviada_em": envio.data_revisao.isoformat() if envio else None,
            "mensagem_envio": envio.observacao_revisor if envio else None,
            "alterada_em": x.data_modificacao.isoformat() if x.data_modificacao else None,
        })
    return {"status": status, "rotulo": fr.ROTULOS[status], "itens": itens}


@router.get("/resumo")
async def resumo(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_REVISORES)):
    """Quantas questões da banca em cada estado."""
    tenant = _tenant(current_user)
    linhas = (await db.execute(select(QuestoesBanco.status_revisao, func.count(QuestoesBanco.id_questao))
                               .where(QuestoesBanco.tenant_id == tenant).group_by(QuestoesBanco.status_revisao))).all()
    cont = Counter()
    for st, n in linhas:
        cont[(st or fr.RASCUNHO).upper() if (st or "").upper() in fr.ROTULOS else fr.RASCUNHO] += n
    return {s: {"rotulo": r, "quantidade": cont.get(s, 0)} for s, r in fr.ROTULOS.items()}
