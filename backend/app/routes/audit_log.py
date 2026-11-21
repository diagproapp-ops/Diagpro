from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime

from backend.app.field_crypto import blind_eq
from backend.app.database import get_db
from backend.app.db_models import AuditLogGeracao
from backend.app.models import AuditLogGeracaoCreate, AuditLogGeracaoOut
from backend.app.auth import get_current_user
from backend.app.security import is_admin_geral, get_tenant_db, require_roles
from backend.app.roles import UserRole

router = APIRouter(prefix="/admin/logs/geracao", tags=["Auditoria"])

@router.get("/", response_model=List[AuditLogGeracaoOut])
async def list_audit_logs(
    usuario: Optional[str] = None,
    acao: Optional[str] = None,
    evento: Optional[str] = None,
    cargo: Optional[str] = None,
    tenant_id: Optional[int] = None,
    db: AsyncSession = Depends(get_tenant_db),
    # auditoria: só administradores. O da banca vê só a própria banca; o geral vê todas (ou a do cliente escolhido)
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))
):
    filters = []
    if not is_admin_geral(current_user):
        tenant_id = current_user.tenant_id
    if tenant_id:
        filters.append(AuditLogGeracao.tenant_id == tenant_id)
    if (usuario or evento or cargo) and not tenant_id:
        # índices cegos são por tenant: o administrador geral precisa informar o cliente para filtrar
        raise HTTPException(status_code=400, detail="Informe tenant_id para filtrar por usuário, evento ou cargo.")
    if usuario:
        filters.append(blind_eq(AuditLogGeracao.usuario, usuario, tenant_id))
    if acao:
        filters.append(AuditLogGeracao.acao == acao)
    if evento:
        filters.append(blind_eq(AuditLogGeracao.evento, evento, tenant_id))
    if cargo:
        filters.append(blind_eq(AuditLogGeracao.cargo, cargo, tenant_id))
    stmt = select(AuditLogGeracao).where(and_(*filters)).order_by(AuditLogGeracao.timestamp.desc()).limit(200)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=AuditLogGeracaoOut, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    log: AuditLogGeracaoCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Logs de geração exigem um usuário vinculado a um cliente.")
    db_log = AuditLogGeracao(
        tenant_id=current_user.tenant_id,
        timestamp=datetime.utcnow(),
        usuario=current_user.username,
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