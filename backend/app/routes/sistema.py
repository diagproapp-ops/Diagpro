# backend/app/routes/sistema.py
"""Saúde do sistema, backups e estado de manutenção."""
from fastapi import APIRouter, Depends, HTTPException

from backend.app import backups, configuracoes, saude
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.security import require_roles

router = APIRouter(tags=["Sistema"])
_ADMIN_GERAL = require_roles(UserRole.ADMIN_GERAL)


@router.get("/status/manutencao")
async def status_manutencao():
    """Público: a tela de login mostra o aviso de manutenção."""
    man = (await configuracoes.ler_plataforma())["manutencao"]
    return {"ativa": man["ativa"], "mensagem": man["mensagem"] if man["ativa"] else ""}


@router.get("/admin/sistema/saude")
async def painel_saude(current_user=Depends(_ADMIN_GERAL)):
    return await saude.conferir()


@router.get("/admin/sistema/backups")
async def listar_backups(current_user=Depends(_ADMIN_GERAL)):
    return {"pasta": str(backups.pasta()), "itens": backups.listar(), "estado": backups.ESTADO,
            "config": (await configuracoes.ler_plataforma())["backup"]}


@router.post("/admin/sistema/backups", dependencies=[Depends(rate_limit(3, 300, "backup-manual"))])
async def backup_agora(current_user=Depends(_ADMIN_GERAL)):
    try:
        return await backups.fazer_backup("manual")
    except backups.ErroBackup as exc:
        raise HTTPException(status_code=409 if "andamento" in str(exc) else 500, detail=str(exc))
