# backend/app/routes/estatisticas.py
"""Estatísticas pós-prova (análise de itens) e painel da banca."""
import asyncio
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import estatisticas, fluxo_revisao
from backend.app.dados_prova import completar_questoes
from backend.app.db_models import (
    AnaliseProva, AuditLogGeracao, Cargo, Conteudo, Entrega, Evento, ProvaMontada, QuestoesBanco, UsoIA, User,
)
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.routes.gabarito import document_generator, normalize_prova_montada
from backend.app.security import evento_autorizado, evento_com_senha, get_tenant_db, require_roles
from backend.app.verificacao_prova import verificar_prova

router = APIRouter(tags=["Estatísticas e painel"])
_ADMINS = require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL)
_MAX_CSV = 20 * 1024 * 1024


async def _gabaritos(db: AsyncSession, evento: Evento, cargo_id: str) -> tuple[Cargo, dict]:
    cargo = (await db.execute(select(Cargo).where(Cargo.id_cargo == cargo_id, Cargo.id_evento_fk == evento.id_evento))).scalar_one_or_none()
    if cargo is None:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")
    prova = (await db.execute(select(ProvaMontada).where(ProvaMontada.id_evento_fk == evento.id_evento,
                                                         ProvaMontada.id_cargo_fk == cargo_id))).scalar_one_or_none()
    if prova is None:
        raise HTTPException(status_code=404, detail="Este cargo não tem prova montada.")
    prova = normalize_prova_montada(prova)
    prova.evento, prova.cargo = evento, cargo
    await completar_questoes(db, prova.blocos_questoes)
    checagem = await verificar_prova(db, cargo, prova, prova.blocos_questoes)
    if checagem["bloqueios"]:
        raise HTTPException(status_code=409, detail="A prova tem problemas que deixariam o gabarito errado; corrija antes da análise.")
    gabs = await asyncio.to_thread(document_generator.gerar_gabaritos_balanceados_por_variacao, prova)
    return cargo, gabs


@router.post("/estatisticas/eventos/{evento_id}/cargos/{cargo_id}/analisar", dependencies=[Depends(rate_limit(10, 300, "analise"))])
async def analisar(evento_id: str, cargo_id: str, arquivo: UploadFile = File(...), db: AsyncSession = Depends(get_tenant_db),
                   evento=Depends(evento_com_senha), current_user=Depends(_ADMINS)):
    """Lê o CSV só em memória (inscrições e nomes são ignorados) e guarda apenas os agregados por questão."""
    conteudo = await arquivo.read(_MAX_CSV + 1)
    if len(conteudo) > _MAX_CSV:
        raise HTTPException(status_code=413, detail="Arquivo maior que 20 MB.")
    try:
        linhas = estatisticas.ler_csv(conteudo)
    except estatisticas.ErroAnalise as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        del conteudo
    cargo, gabaritos = await _gabaritos(db, evento, cargo_id)
    try:
        resultado = estatisticas.analisar(gabaritos, linhas)
    except estatisticas.ErroAnalise as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        del linhas
    resultado["cargo"] = f"{cargo.codigo_cargo or ''} {cargo.nome_cargo or ''}".strip()
    db.add(AnaliseProva(tenant_id=evento.tenant_id, evento_id=evento.id_evento, cargo_id=cargo_id, criada_em=datetime.utcnow(),
                        criada_por=current_user.id, n_candidatos=resultado["candidatos"], resultado=resultado))
    await db.commit()
    return resultado


@router.get("/estatisticas/eventos/{evento_id}/cargos/{cargo_id}")
async def ultima_analise(evento_id: str, cargo_id: str, db: AsyncSession = Depends(get_tenant_db),
                         evento=Depends(evento_autorizado), current_user=Depends(_ADMINS)):
    a = (await db.execute(select(AnaliseProva).where(AnaliseProva.evento_id == evento.id_evento, AnaliseProva.cargo_id == cargo_id)
                          .order_by(AnaliseProva.id.desc()).limit(1))).scalar_one_or_none()
    if a is None:
        return None
    return {**(a.resultado or {}), "analisada_em": a.criada_em.isoformat() + "Z"}


@router.get("/painel/banca")
async def painel_banca(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_ADMINS)):
    """Resumo da banca para o administrador (números; nenhum conteúdo de prova)."""
    t = current_user.tenant_id
    if t is None:
        raise HTTPException(status_code=400, detail="Escolha um cliente no topo da tela.")
    eventos = (await db.execute(select(Evento).where(Evento.tenant_id == t, Evento.is_deleted.is_(False)))).scalars().all()
    ev_ids = [e.id_evento for e in eventos]
    conteudos = (await db.execute(select(Conteudo).where(Conteudo.tenant_id == t))).scalars().all() if ev_ids else []
    status_rev = Counter()
    tipos = Counter()
    for st, tp, n in (await db.execute(select(QuestoesBanco.status_revisao, QuestoesBanco.tipo, func.count(QuestoesBanco.id_questao))
                                       .where(QuestoesBanco.tenant_id == t).group_by(QuestoesBanco.status_revisao, QuestoesBanco.tipo))).all():
        status_rev[(st or fluxo_revisao.RASCUNHO).upper()] += n
        tipos[tp or "?"] += n
    cargos = (await db.execute(select(func.count(Cargo.id_cargo)).where(Cargo.tenant_id == t))).scalar_one()
    montadas = (await db.execute(select(func.count(ProvaMontada.id_prova_montada)).where(ProvaMontada.tenant_id == t))).scalar_one()
    desde = datetime.utcnow() - timedelta(days=30)
    exportacoes = (await db.execute(select(func.count(AuditLogGeracao.id)).where(AuditLogGeracao.tenant_id == t,
                                                                                AuditLogGeracao.timestamp >= desde))).scalar_one()
    entregas_ativas = sum(1 for e in (await db.execute(select(Entrega).where(Entrega.tenant_id == t, Entrega.encerrada_em.is_(None)))).scalars()
                          if e.expira_em > datetime.utcnow() and e.downloads < e.max_downloads)
    ia_30 = (await db.execute(select(func.count(UsoIA.id)).where(UsoIA.tenant_id == t, UsoIA.criado_em >= desde))).scalar_one()
    papeis = Counter(u.role for u in (await db.execute(select(User).where(User.tenant_id == t, User.is_active.is_(True)))).scalars())
    por_evento = []
    for e in eventos:
        cts = [c for c in conteudos if c.evento_id == e.id_evento]
        meta = sum(c.quantidade or 0 for c in cts)
        feitas = sum(min(c.respondidas or 0, c.quantidade or 0) for c in cts)
        por_evento.append({"id": e.id_evento, "nome": e.nome_evento, "data_prova": e.data_prova.isoformat() if e.data_prova else None,
                           "status": e.status, "conteudos": len(cts), "questoes_meta": meta, "questoes_feitas": feitas,
                           "progresso": round(100 * feitas / meta) if meta else None})
    por_evento.sort(key=lambda x: x["data_prova"] or "9999")
    return {
        "eventos": len(eventos), "cargos": cargos, "provas_montadas": montadas,
        "questoes": {"total": sum(status_rev.values()), "por_estado": dict(status_rev), "por_tipo": dict(tipos)},
        "fila_revisao": status_rev.get(fluxo_revisao.ENVIADA, 0), "exportacoes_30d": exportacoes,
        "entregas_ativas": entregas_ativas, "usos_ia_30d": ia_30, "equipe": dict(papeis), "por_evento": por_evento,
    }
