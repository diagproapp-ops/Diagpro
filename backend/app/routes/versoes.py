# backend/app/routes/versoes.py
"""Histórico de versões de uma questão e busca de questões parecidas na banca."""
import html
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import versoes_questao as vq
from backend.app.auth import get_current_user
from backend.app.db_models import Conteudo, Evento, QuestoesBanco, VersaoQuestao
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.security import evento_autorizado, get_tenant_db, require_roles

router = APIRouter(tags=["Versões e parecidas"])


async def _questao_do_evento(db, evento, conteudo_id: str, id_questao: str) -> QuestoesBanco:
    q = (await db.execute(select(QuestoesBanco).where(
        QuestoesBanco.id_questao == id_questao, QuestoesBanco.id_evento_fk == evento.id_evento,
        QuestoesBanco.conteudo_id == conteudo_id))).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")
    return q


def _resumo(snapshot: dict) -> str:
    """Enunciado em texto puro, curto (para listas)."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", snapshot.get("enunciado") or ""))
    t = " ".join(t.split())
    return t[:140] + ("…" if len(t) > 140 else "")


@router.get("/eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}/versoes")
async def listar_versoes(evento_id: str, conteudo_id: str, id_questao: str, db: AsyncSession = Depends(get_tenant_db),
                         evento=Depends(evento_autorizado), current_user=Depends(get_current_user)):
    await _questao_do_evento(db, evento, conteudo_id, id_questao)
    linhas = (await db.execute(select(VersaoQuestao).where(VersaoQuestao.id_questao_fk == id_questao)
                               .order_by(VersaoQuestao.versao.desc()))).scalars().all()
    return [{"versao": v.versao, "criada_em": v.criada_em.isoformat(), "motivo": v.motivo, "autor": v.autor,
             "resumo": _resumo(v.snapshot or {})} for v in linhas]


@router.get("/eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}/versoes/{versao}")
async def ver_versao(evento_id: str, conteudo_id: str, id_questao: str, versao: int, db: AsyncSession = Depends(get_tenant_db),
                     evento=Depends(evento_autorizado), current_user=Depends(get_current_user)):
    await _questao_do_evento(db, evento, conteudo_id, id_questao)
    v = (await db.execute(select(VersaoQuestao).where(VersaoQuestao.id_questao_fk == id_questao,
                                                      VersaoQuestao.versao == versao))).scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")
    return {"versao": v.versao, "criada_em": v.criada_em.isoformat(), "motivo": v.motivo, "autor": v.autor, "questao": v.snapshot}


class ParecidasIn(BaseModel):
    enunciado: str = Field(..., min_length=1, max_length=60000)
    excluir_id: Optional[str] = Field(None, max_length=64)


@router.post("/questoes/parecidas", dependencies=[Depends(rate_limit(30, 60, "parecidas"))])
async def procurar_parecidas(dados: ParecidasIn, db: AsyncSession = Depends(get_tenant_db),
                             current_user=Depends(require_roles(UserRole.PROFESSOR, UserRole.REVISOR, UserRole.ADMIN, UserRole.ADMIN_GERAL))):
    """Questões da banca com enunciado parecido. Professor vê detalhes só das questões dele; das outras, só o grau."""
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Escolha um cliente no topo da tela.")
    achadas = await vq.parecidas(db, current_user.tenant_id, dados.enunciado, dados.excluir_id)
    role = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    professor = role == UserRole.PROFESSOR.value
    ids_ct = {q.conteudo_id for _, q in achadas if q.conteudo_id}
    conteudos = {c.id_conteudo: c for c in (await db.execute(select(Conteudo).where(Conteudo.id_conteudo.in_(ids_ct)))).scalars()} if ids_ct else {}
    ids_ev = {q.id_evento_fk for _, q in achadas}
    eventos = {e.id_evento: e.nome_evento for e in (await db.execute(select(Evento).where(Evento.id_evento.in_(ids_ev)))).scalars()} if ids_ev else {}
    saida = []
    for s, q in achadas:
        ct = conteudos.get(q.conteudo_id)
        minha = str(current_user.id) in {str(q.criador_id or ""), str((ct.professor_id if ct else "") or "")}
        item = {"similaridade": round(s * 100)}
        if not professor or minha:
            item.update({"id_questao": q.id_questao, "codigo": q.codigo_curto_questao, "evento_id": q.id_evento_fk,
                         "evento": eventos.get(q.id_evento_fk), "conteudo_id": q.conteudo_id,
                         "conteudo": ct.nome_conteudo if ct else None, "status": q.status_revisao,
                         "trecho": _resumo({"enunciado": q.enunciado})})
        else:
            item["detalhes_ocultos"] = True  # questão de outro professor: só o aviso
        saida.append(item)
    return {"parecidas": saida}
