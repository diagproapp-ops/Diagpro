# backend/app/routes/revisao.py
"""Fluxo de revisão: enviar questão para revisão, fila do revisor e resumo da banca."""
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import fluxo_revisao as fr
from backend.app import liberacao_evento
from backend.app.rate_limit import rate_limit
from backend.app.db_models import Conteudo, Evento, HistoricoRevisaoQuestao, QuestoesBanco, User
from backend.app.roles import UserRole
from backend.app.security import carregar_evento_autorizado, conferir_senha_evento, get_tenant_db, require_roles

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


class SenhaIn(BaseModel):
    senha: str = Field(..., max_length=200)


@router.post("/eventos/{evento_id}/liberar", dependencies=[Depends(rate_limit(10, 60, "liberar-evento"))])
async def liberar_evento(evento_id: str, dados: SenhaIn, request: Request, db: AsyncSession = Depends(get_tenant_db),
                         current_user=Depends(require_roles(UserRole.REVISOR, UserRole.ADMIN, UserRole.ADMIN_GERAL,
                                                            UserRole.DIAGRAMADOR, UserRole.PROFESSOR))):
    """Senha do evento -> as questões dele ficam visíveis na fila e na revisão, só nesta sessão."""
    _tenant(current_user)
    evento = await carregar_evento_autorizado(evento_id, db, current_user)
    conferir_senha_evento(evento, dados.senha, current_user)  # tempo constante + bloqueio por falhas
    await liberacao_evento.liberar(request, current_user, evento_id)
    return {"ok": True, "evento_id": evento_id}


@router.get("/eventos/{evento_id}/liberado")
async def evento_liberado(evento_id: str, request: Request, current_user=Depends(require_roles(
        UserRole.REVISOR, UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR, UserRole.PROFESSOR))):
    return {"liberado": await liberacao_evento.esta_liberado(request, current_user, evento_id)}


@router.get("/fila")
async def fila(request: Request, status: str = fr.ENVIADA, evento_id: Optional[str] = None,
               db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_REVISORES)):
    """Questões da banca num estado, com evento, conteúdo e autor. Só de eventos liberados com a senha NESTA
    sessão; dos outros, apenas o nome do evento e quantas questões estão ali (sem nada das questões)."""
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
    todas = (await db.execute(q.order_by(QuestoesBanco.data_modificacao.asc()).limit(500))).scalars().all()
    abertos = await liberacao_evento.liberados(request, current_user)
    questoes = [x for x in todas if x.id_evento_fk in abertos]
    fechados = Counter(x.id_evento_fk for x in todas if x.id_evento_fk not in abertos)

    ids_ev = {x.id_evento_fk for x in todas}
    ids_ct = {x.conteudo_id for x in questoes if x.conteudo_id}
    eventos = {e.id_evento: e.nome_evento for e in (await db.execute(select(Evento).where(Evento.id_evento.in_(ids_ev)))).scalars()} if ids_ev else {}
    conteudos = {c.id_conteudo: c for c in (await db.execute(select(Conteudo).where(Conteudo.id_conteudo.in_(ids_ct)))).scalars()} if ids_ct else {}
    from backend.app import vinculos
    nomes = {u.id: u.username for u in (await db.execute(select(User).where(vinculos.membros_da_banca(tenant)))).scalars()}
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
    bloqueados = [{"evento_id": ev, "evento": eventos.get(ev), "quantidade": n} for ev, n in fechados.most_common()]
    return {"status": status, "rotulo": fr.ROTULOS[status], "itens": itens, "eventos_bloqueados": bloqueados}


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
