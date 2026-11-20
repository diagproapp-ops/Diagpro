# backend/app/routes/entregas.py
"""Entregas seguras: gestão (banca) e download público com código. Regras em backend/app/entregas.py."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import entregas
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Entrega, User
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.security import evento_autorizado, get_tenant_db, require_roles

router = APIRouter(tags=["Entregas"])
_QUEM_GERE = require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)


@router.get("/api/export/eventos/{evento_id}/entregas")
async def listar(evento_id: str, db: AsyncSession = Depends(get_tenant_db), evento=Depends(evento_autorizado),
                 current_user=Depends(_QUEM_GERE)):
    linhas = (await db.execute(select(Entrega).where(Entrega.evento_id == evento.id_evento).order_by(Entrega.criado_em.desc()))).scalars().all()
    ids = {e.criado_por for e in linhas if e.criado_por}
    nomes = {u.id: u.username for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars()} if ids else {}
    return [{**entregas.publico(e), "criado_por": nomes.get(e.criado_por)} for e in linhas]


@router.post("/api/export/entregas/{entrega_id}/revogar")
async def revogar(entrega_id: str, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_GERE)):
    e = (await db.execute(select(Entrega).where(Entrega.id == entrega_id[:32]))).scalar_one_or_none()  # RLS: só da banca
    if e is None:
        raise HTTPException(status_code=404, detail="Entrega não encontrada.")
    entregas.encerrar(e, "revogada")
    await db.commit()
    return entregas.publico(e)


@router.get("/entrega/{entrega_id}/info", dependencies=[Depends(rate_limit(30, 600, "entrega-info"))])
async def info_publica(entrega_id: str):
    """Público: só o necessário para a tela de download (nada de evento, banca ou cargos)."""
    async with PlatformSessionLocal() as db:
        e = (await db.execute(select(Entrega).where(Entrega.id == entrega_id[:32]))).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Link inválido.")
    sit = entregas.situacao(e)
    return {"situacao": sit, "expira_em": e.expira_em.isoformat() + "Z",
            "nome_arquivo": (e.detalhes or {}).get("nome_arquivo") if sit == "ativa" else None,
            "downloads_restantes": max(0, e.max_downloads - e.downloads) if sit == "ativa" else 0}


class CodigoIn(BaseModel):
    codigo: str = Field(..., min_length=4, max_length=40)


@router.post("/entrega/{entrega_id}/baixar", dependencies=[Depends(rate_limit(10, 600, "entrega-baixar"))])
async def baixar(entrega_id: str, dados: CodigoIn, request: Request):
    ip = request.client.host if request.client else ""
    try:
        conteudo, nome = await entregas.baixar(entrega_id[:32], dados.codigo, ip)
    except entregas.ErroEntrega as exc:
        raise HTTPException(status_code=exc.status, detail=exc.mensagem)
    return Response(content=conteudo, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{nome}"', "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff"})
