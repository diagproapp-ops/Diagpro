# backend/app/routes/notificacoes.py
"""Avisos do usuário logado (sino), preferências de e-mail e teste do servidor de e-mail."""
import contextlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import configuracoes, notificacoes
from backend.app.auth import get_current_user
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Notificacao, User
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.security import get_tenant_db, is_admin_geral, require_roles

router = APIRouter(tags=["Notificações"])


@contextlib.asynccontextmanager
async def _sessao_do_usuario(db: AsyncSession, current_user):
    """Usuário de banca: sessão RLS da requisição. Admin geral (avisos sem tenant): sessão de plataforma.
    Em ambos os casos toda consulta filtra por usuario_id == quem está logado."""
    if is_admin_geral(current_user):
        async with PlatformSessionLocal() as pdb:
            yield pdb
    else:
        yield db


def _saida(n: Notificacao) -> dict:
    c = n.conteudo or {}
    return {"id": n.id, "tipo": n.tipo, "titulo": c.get("titulo", ""), "mensagem": c.get("mensagem", ""),
            "link": c.get("link"), "criado_em": n.criado_em.isoformat() + "Z", "lida": n.lida_em is not None}


@router.get("/notificacoes")
async def listar(somente_nao_lidas: bool = False, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    async with _sessao_do_usuario(db, current_user) as s:
        q = select(Notificacao).where(Notificacao.usuario_id == current_user.id)
        if somente_nao_lidas:
            q = q.where(Notificacao.lida_em.is_(None))
        linhas = (await s.execute(q.order_by(Notificacao.id.desc()).limit(50))).scalars().all()
        nao_lidas = (await s.execute(select(func.count(Notificacao.id)).where(
            Notificacao.usuario_id == current_user.id, Notificacao.lida_em.is_(None)))).scalar_one()
    return {"nao_lidas": nao_lidas, "itens": [_saida(n) for n in linhas]}


@router.get("/notificacoes/contagem")
async def contagem(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    async with _sessao_do_usuario(db, current_user) as s:
        n = (await s.execute(select(func.count(Notificacao.id)).where(
            Notificacao.usuario_id == current_user.id, Notificacao.lida_em.is_(None)))).scalar_one()
    return {"nao_lidas": n}


@router.post("/notificacoes/{notificacao_id}/lida")
async def marcar_lida(notificacao_id: int, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    async with _sessao_do_usuario(db, current_user) as s:
        # não existe, já lida ou é de outra pessoa: mesma resposta (não revela nada)
        await s.execute(update(Notificacao).where(
            Notificacao.id == notificacao_id, Notificacao.usuario_id == current_user.id, Notificacao.lida_em.is_(None)
        ).values(lida_em=datetime.utcnow()))
        await s.commit()
    return {"ok": True}


@router.post("/notificacoes/marcar-todas")
async def marcar_todas(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    async with _sessao_do_usuario(db, current_user) as s:
        await s.execute(update(Notificacao).where(
            Notificacao.usuario_id == current_user.id, Notificacao.lida_em.is_(None)).values(lida_em=datetime.utcnow()))
        await s.commit()
    return {"ok": True}


@router.get("/notificacoes/preferencias")
async def ler_preferencias(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    async with _sessao_do_usuario(db, current_user) as s:
        usuario = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one()
        prefs = notificacoes.preferencias_de(usuario)
    plataforma = await configuracoes.ler_plataforma()
    return {
        "email_da_plataforma_ligado": bool(plataforma["email"]["habilitado"]),
        "tipos": [{"tipo": t, "rotulo": info["rotulo"], "obrigatorio": info["obrigatorio"], "email": prefs[t]}
                  for t, info in notificacoes.TIPOS.items()],
    }


@router.put("/notificacoes/preferencias")
async def salvar_preferencias(request: Request, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    novas = notificacoes.validar_preferencias(await request.json())
    async with _sessao_do_usuario(db, current_user) as s:
        usuario = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one()
        atuais = usuario.preferencias if isinstance(usuario.preferencias, dict) else {}
        usuario.preferencias = {**atuais, "email": {**(atuais.get("email") or {}), **novas["email"]}}
        await s.commit()
    return await ler_preferencias(db, current_user)


@router.post("/config/email/testar", dependencies=[Depends(rate_limit(5, 60, "email-teste"))])
async def testar_email(current_user=Depends(require_roles(UserRole.ADMIN_GERAL))):
    """Manda um e-mail de teste para o próprio admin geral (nunca para um endereço digitado)."""
    plataforma = await configuracoes.ler_plataforma(forcar=True)
    async with PlatformSessionLocal() as s:
        usuario = await s.get(User, current_user.id)
        destino = usuario.email if usuario else None
    if not destino:
        raise HTTPException(status_code=400, detail="Seu usuário não tem e-mail cadastrado.")
    try:
        await notificacoes.enviar_email(plataforma["email"], destino, "Teste do servidor de e-mail",
                                        "Se você recebeu esta mensagem, o envio de avisos do DiagPro está funcionando.", "/")
    except notificacoes.ErroEmail as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"ok": True, "para": destino[:2] + "…@" + destino.split("@")[-1]}
