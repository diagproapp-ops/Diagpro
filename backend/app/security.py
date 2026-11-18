# backend/app/security.py
"""Helpers de autorização e de manipulação segura de arquivos."""

import os

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.auth import get_current_user
from backend.app.database import SessionLocal, PlatformSessionLocal, set_tenant_context
from backend.app.db_models import Evento as DBEvento
from backend.app.roles import UserRole


def is_admin_geral(user) -> bool:
    return getattr(user, "role", None) == UserRole.ADMIN_GERAL


def require_roles(*allowed_roles: UserRole):
    """Dependência RBAC reutilizável que restringe o endpoint aos perfis informados."""
    allowed = {r.value for r in allowed_roles}

    def _checker(current_user=Depends(get_current_user)):
        role_val = current_user.role.value if isinstance(current_user.role, UserRole) else current_user.role
        if role_val not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado. Permissão insuficiente para o seu perfil.",
            )
        return current_user

    return _checker


async def get_tenant_db(current_user=Depends(get_current_user)):
    """
    Sessão de banco para a requisição:
    - usuário de tenant: role de runtime (sem BYPASSRLS) com o tenant do usuário autenticado (SET LOCAL);
    - administrador geral: role de plataforma (BYPASSRLS), única credencial com visão multi-tenant.
    Falha fechada se um usuário comum não tiver tenant_id.
    """
    if is_admin_geral(current_user):
        async with PlatformSessionLocal() as db:
            yield db
        return
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem cliente (tenant) associado.",
        )
    async with SessionLocal() as db:
        await set_tenant_context(db, current_user.tenant_id)
        yield db


async def carregar_evento_autorizado(evento_id: str, db: AsyncSession, current_user) -> DBEvento:
    """
    Retorna o evento se ele pertencer ao tenant do usuário (admin geral acessa todos).
    Responde 404 (e não 403) para não revelar a existência de eventos de outros clientes.
    """
    query = select(DBEvento).where(DBEvento.id_evento == evento_id)
    if not is_admin_geral(current_user):
        if current_user.tenant_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário sem cliente associado.")
        query = query.where(DBEvento.tenant_id == current_user.tenant_id)
    evento = (await db.execute(query)).scalars().first()
    if not evento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado.")
    return evento


async def evento_autorizado(
    evento_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
) -> DBEvento:
    """Dependência para rotas com o parâmetro de caminho {evento_id}."""
    return await carregar_evento_autorizado(evento_id, db, current_user)


def nome_arquivo_seguro(nome: str | None, extensoes_permitidas: set[str] | None = None) -> str:
    """
    Reduz um nome de arquivo vindo do cliente ao seu nome base, rejeitando
    componentes de caminho (/, \\, ..) e, opcionalmente, extensões não permitidas.
    """
    nome = (nome or "").strip()
    base = os.path.basename(nome.replace("\\", "/"))
    if not base or base in (".", "..") or base != nome or "\x00" in base:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de arquivo inválido.")
    if extensoes_permitidas is not None:
        ext = os.path.splitext(base)[1].lower()
        if ext not in extensoes_permitidas:
            permitidas = ", ".join(sorted(extensoes_permitidas))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de arquivo não permitido. Use: {permitidas}.",
            )
    return base


def caminho_dentro_de(base_dir: str, nome_arquivo: str) -> str:
    """Monta base_dir/nome_arquivo e garante que o resultado não escapa de base_dir."""
    base_real = os.path.realpath(base_dir)
    destino = os.path.realpath(os.path.join(base_real, nome_arquivo))
    if os.path.commonpath([base_real, destino]) != base_real or destino == base_real:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Caminho de arquivo inválido.")
    return destino
