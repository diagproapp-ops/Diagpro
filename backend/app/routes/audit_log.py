from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime

from backend.app.database import get_db
from backend.app.db_models import AuditLogGeracao
from backend.app.models import AuditLogGeracaoCreate, AuditLogGeracaoOut

router = APIRouter(prefix="/admin/logs/geracao", tags=["Auditoria"])

def get_current_user():
    # Troque por sua autenticação real!
    return {"username": "admin", "tenant_id": 1, "is_superadmin": True}

@router.get("/", response_model=List[AuditLogGeracaoOut])
async def list_audit_logs(
    usuario: Optional[str] = None,
    acao: Optional[str] = None,
    evento: Optional[str] = None,
    cargo: Optional[str] = None,
    tenant_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    filters = []
    if not current_user.get("is_superadmin"):
        filters.append(AuditLogGeracao.tenant_id == current_user["tenant_id"])
    elif tenant_id:
        filters.append(AuditLogGeracao.tenant_id == tenant_id)
    if usuario:
        filters.append(AuditLogGeracao.usuario == usuario)
    if acao:
        filters.append(AuditLogGeracao.acao == acao)
    if evento:
        filters.append(AuditLogGeracao.evento == evento)
    if cargo:
        filters.append(AuditLogGeracao.cargo == cargo)
    stmt = select(AuditLogGeracao).where(and_(*filters)).order_by(AuditLogGeracao.timestamp.desc()).limit(200)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=AuditLogGeracaoOut, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    log: AuditLogGeracaoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_log = AuditLogGeracao(
        tenant_id=current_user["tenant_id"],
        timestamp=datetime.utcnow(),
        usuario=current_user["username"],
        evento=log.evento,
        cargo=log.cargo,
        acao=log.acao,
        parametros=log.parametros,
        frases=log.frases,
        seed=log.seed,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent", "")[:255]
    )
    db.add(db_log)
    await db.commit()
    await db.refresh(db_log)
    return db_log