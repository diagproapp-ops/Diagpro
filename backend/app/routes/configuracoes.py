# backend/app/routes/configuracoes.py
"""Configurações da plataforma (admin geral) e da banca (administrador do cliente)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import configuracoes
from backend.app.auth import get_current_user
from backend.app.roles import UserRole
from backend.app.security import get_tenant_db, is_admin_geral, require_roles

router = APIRouter(prefix="/config", tags=["Configurações"])
logger = logging.getLogger(__name__)


def _tenant_da_banca(current_user) -> int:
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Escolha um cliente no topo da tela para ver as configurações da banca.")
    return current_user.tenant_id


@router.get("/plataforma")
async def ler_plataforma(current_user=Depends(require_roles(UserRole.ADMIN_GERAL))):
    return await configuracoes.ler_plataforma(forcar=True)


@router.put("/plataforma")
async def salvar_plataforma(request: Request, current_user=Depends(require_roles(UserRole.ADMIN_GERAL))):
    if current_user.tenant_id is not None:
        raise HTTPException(status_code=400, detail="Volte para a visão global para alterar a plataforma.")
    dados = await configuracoes.salvar_plataforma(await request.json(), current_user.username)
    logger.warning("Configurações da plataforma alteradas por %s", current_user.id)
    return dados


@router.get("/banca")
async def ler_banca(
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL)),
):
    tenant = _tenant_da_banca(current_user)
    banca = await configuracoes.ler_banca(db, tenant)
    plataforma = await configuracoes.ler_plataforma()
    return {**banca, "limites": {"sessao_inatividade_minutos_maximo": plataforma["seguranca"]["sessao_inatividade_minutos"]}}


@router.put("/banca")
async def salvar_banca(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL)),
):
    tenant = _tenant_da_banca(current_user)
    dados = await configuracoes.salvar_banca(db, tenant, await request.json(), current_user.username)
    logger.warning("Configurações da banca %s alteradas por %s", tenant, current_user.id)
    return dados


@router.get("/sessao")
async def config_sessao(current_user=Depends(get_current_user)):
    """O que vale para a sessão de quem está logado (a tela usa para o aviso de inatividade)."""
    plataforma = await configuracoes.ler_plataforma()
    tenant = None if is_admin_geral(current_user) and current_user.tenant_id is None else current_user.tenant_id
    return {"inatividade_minutos": await configuracoes.inatividade_do_usuario(tenant),
            "sessao_maxima_horas": plataforma["seguranca"]["sessao_maxima_horas"]}


@router.get("/regras-questoes")
async def regras_questoes(
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    """Tipos de questão que a banca usa (telas de criar/editar questão)."""
    if current_user.tenant_id is None:
        return configuracoes.PADRAO_BANCA["regras_questoes"]
    return (await configuracoes.ler_banca(db, current_user.tenant_id))["regras_questoes"]
