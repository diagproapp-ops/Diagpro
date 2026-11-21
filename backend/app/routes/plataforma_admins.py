"""
Administradores gerais da plataforma (suporte às bancas). Pode haver vários: um administrador geral convida outro
por link (a pessoa cria a própria senha, envia a foto e cadastra o 2FA no primeiro acesso) e um administrador geral
aprova. Ninguém se desativa a si mesmo e sempre sobra pelo menos um ativo.

Lembrando: ser administrador geral NÃO abre questões de evento sem a senha do evento (ver liberacao_evento).
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import sessoes
from backend.app.auth import get_current_user
from backend.app.database import get_platform_db
from backend.app.db_models import Convite, User
from backend.app.field_crypto import blind_eq
from backend.app.models import User as PydanticUser
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.routes.convites import VALIDADE_CADASTRO, _enviar, _estado, _hash, _saida, _url_do_link
from backend.app.routes.users import _serialize_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plataforma/administradores", tags=["Administradores da plataforma"])
ADMIN_GERAL = UserRole.ADMIN_GERAL.value


def _so_admin_geral(current_user=Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN_GERAL:
        raise HTTPException(status_code=403, detail="Somente administradores gerais.")
    return current_user


def _admins_gerais():
    return select(User).where(User.tenant_id.is_(None), User.role == ADMIN_GERAL)


@router.get("", response_model=list[PydanticUser])
async def listar(db: AsyncSession = Depends(get_platform_db), eu=Depends(_so_admin_geral)):
    return [_serialize_user(u) for u in (await db.execute(_admins_gerais().order_by(User.id))).scalars().all()]


class NovoAdmin(BaseModel):
    email: EmailStr
    nome: Optional[str] = None


@router.post("/convites", dependencies=[Depends(rate_limit(10, 60, "convite-admin-geral"))])
async def convidar(body: NovoAdmin, db: AsyncSession = Depends(get_platform_db), eu=Depends(_so_admin_geral)):
    email = body.email.strip().lower()
    if (await db.execute(select(User.id).where(blind_eq(User.email, email)))).first():
        # e-mail com conta (de banca ou não): administrador geral precisa de conta própria e separada
        raise HTTPException(status_code=409, detail="Este e-mail já tem conta. O administrador geral precisa de um e-mail só para isso.")
    agora = datetime.utcnow()
    for antigo in (await db.execute(select(Convite).where(Convite.tenant_id.is_(None), Convite.usado_em.is_(None),
                                                          Convite.cancelado_em.is_(None)))).scalars():
        if (antigo.email or "").lower() == email:
            antigo.cancelado_em = agora
    token = secrets.token_urlsafe(32)
    c = Convite(tenant_id=None, token_hash=_hash(token), tipo="cadastro", email=email, nome=(body.nome or "").strip() or None,
                role=ADMIN_GERAL, criado_por=eu.id, criado_em=agora, expira_em=agora + VALIDADE_CADASTRO)
    db.add(c)
    await db.commit()
    url, cfg = await _url_do_link(token)
    enviado = await _enviar(cfg, email, "Convite para administrador geral do DiagPro",
                            "Você foi convidado(a) para ser administrador(a) geral da plataforma DiagPro (suporte às bancas).\n"
                            "Abra o link para se cadastrar com os seus dados, a sua senha e a sua foto. O link vale 7 dias e uma "
                            "única vez. Depois, um administrador geral confere e libera o acesso.", token)
    logger.warning("Convite de administrador geral %s criado por %s", c.id, eu.id)
    return {**_saida(c), "link": url, "enviado_por_email": enviado}


@router.get("/convites")
async def listar_convites(db: AsyncSession = Depends(get_platform_db), eu=Depends(_so_admin_geral)):
    linhas = (await db.execute(select(Convite).where(Convite.tenant_id.is_(None)).order_by(Convite.id.desc()).limit(100))).scalars().all()
    return [_saida(c) for c in linhas if _estado(c) == "pendente"]


@router.delete("/convites/{convite_id}")
async def cancelar_convite(convite_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), eu=Depends(_so_admin_geral)):
    c = (await db.execute(select(Convite).where(Convite.id == convite_id, Convite.tenant_id.is_(None)))).scalars().first()
    if c is None:
        raise HTTPException(status_code=404, detail="Convite não encontrado.")
    if _estado(c) == "pendente":
        c.cancelado_em = datetime.utcnow()
        await db.commit()
    return _saida(c)


class Situacao(BaseModel):
    status: str


@router.patch("/{user_id}", response_model=PydanticUser)
async def mudar_situacao(dados: Situacao, user_id: int = Path(...), db: AsyncSession = Depends(get_platform_db),
                         eu=Depends(_so_admin_geral)):
    """Aprovar (ativo) ou desativar (inativo) um administrador geral."""
    novo = (dados.status or "").lower()
    if novo not in ("ativo", "inativo"):
        raise HTTPException(status_code=400, detail="Situação inválida.")
    alvo = (await db.execute(_admins_gerais().where(User.id == user_id))).scalars().first()
    if alvo is None:
        raise HTTPException(status_code=404, detail="Administrador não encontrado.")
    if alvo.id == eu.id:
        raise HTTPException(status_code=403, detail="Você não pode mudar a sua própria situação. Peça a outro administrador geral.")
    if novo == "ativo":
        if not alvo.avatar_url:
            raise HTTPException(status_code=400, detail="Sem foto: a pessoa precisa enviar a foto antes de ser aprovada.")
        alvo.is_active = True
    else:
        ativos = [u for u in (await db.execute(_admins_gerais())).scalars().all()
                  if u.is_active and (u.status or "ativo").lower() == "ativo" and u.id != alvo.id]
        if not ativos:
            raise HTTPException(status_code=409, detail="A plataforma precisa de pelo menos um administrador geral ativo.")
    alvo.status = novo
    await db.commit()
    await db.refresh(alvo)
    if novo == "inativo":
        await sessoes.encerrar_do_usuario(alvo.id, "desativado_pelo_administrador")
    logger.warning("Administrador geral %s ficou %s (por %s)", alvo.id, novo, eu.id)
    return _serialize_user(alvo)
