# backend/app/routes/lgpd.py
"""LGPD: termos/política, aceite, exportação dos próprios dados, anonimização e registros."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import configuracoes, lgpd
from backend.app.auth import get_admin_user, get_current_user
from backend.app.db_models import RegistroLGPD, User
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.routes.notificacoes import _sessao_do_usuario
from backend.app.routes.users import _buscar_usuario_gerenciavel
from backend.app.security import get_tenant_db, require_roles

router = APIRouter(prefix="/lgpd", tags=["LGPD"])


@router.get("/documentos")
async def documentos():
    """Público: termos de uso e política de privacidade vigentes."""
    lg = (await configuracoes.ler_plataforma())["lgpd"]
    return {"versao": lg["versao_termos"], "termos": lg["termos"], "politica": lg["politica"], "encarregado": lg["encarregado"]}


@router.get("/status")
async def status(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    versao = (await configuracoes.ler_plataforma())["lgpd"]["versao_termos"]
    async with _sessao_do_usuario(db, current_user) as s:
        user = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one()
        aceite = lgpd.aceite_de(user)
    return {"versao_atual": versao, "aceita": bool(aceite and aceite.get("versao") == versao), "aceite": aceite}


class AceiteIn(BaseModel):
    versao: str = Field(..., max_length=20)


@router.post("/aceitar")
async def aceitar(dados: AceiteIn, request: Request, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    versao = (await configuracoes.ler_plataforma())["lgpd"]["versao_termos"]
    if dados.versao != versao:
        raise HTTPException(status_code=409, detail="Os termos mudaram. Leia a versão atual e aceite de novo.")
    async with _sessao_do_usuario(db, current_user) as s:
        user = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one()
        aceite = {"versao": versao, "em": datetime.utcnow().isoformat() + "Z", "ip": request.client.host if request.client else ""}
        user.terms_acceptance = json.dumps(aceite)
        lgpd.registrar(s, user.tenant_id, user.id, user.id, "aceite_termos", {"versao": versao})
        await s.commit()
    return {"aceita": True, "aceite": aceite}


@router.get("/meus-dados", dependencies=[Depends(rate_limit(5, 300, "lgpd-export"))])
async def meus_dados(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    """Arquivo JSON com os dados pessoais de quem está logado."""
    async with _sessao_do_usuario(db, current_user) as s:
        user = (await s.execute(select(User).where(User.id == current_user.id))).scalar_one()
        dados = await lgpd.exportar(s, user)
        lgpd.registrar(s, user.tenant_id, user.id, user.id, "exportacao", {})
        await s.commit()
    corpo = json.dumps(dados, ensure_ascii=False, indent=2, default=str)
    return Response(content=corpo, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="meus-dados-diagpro.json"', "Cache-Control": "no-store"})


@router.post("/usuarios/{user_id}/anonimizar")
async def anonimizar(user_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), admin_user=Depends(get_admin_user)):
    """Elimina os dados pessoais de alguém da banca (irreversível). Ninguém anonimiza a si mesmo."""
    alvo = await _buscar_usuario_gerenciavel(db, user_id, admin_user)
    if alvo.id == admin_user.id:
        raise HTTPException(status_code=403, detail="Você não pode anonimizar a própria conta. Peça a outro administrador.")
    if (alvo.username or "").startswith("anonimizado-"):
        raise HTTPException(status_code=409, detail="Este usuário já foi anonimizado.")
    await lgpd.anonimizar(db, alvo, admin_user.id)
    return {"ok": True, "usuario": alvo.username}


@router.get("/registros")
async def registros(db: AsyncSession = Depends(get_tenant_db),
                    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))):
    """Prestação de contas da banca: pedidos e operações de LGPD."""
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Escolha um cliente no topo da tela.")
    linhas = (await db.execute(select(RegistroLGPD).where(RegistroLGPD.tenant_id == current_user.tenant_id)
                               .order_by(RegistroLGPD.id.desc()).limit(500))).scalars().all()
    ids = {i for r in linhas for i in (r.titular_id, r.autor_id) if i}
    nomes = {u.id: u.username for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars()} if ids else {}
    return [{"em": r.criado_em.isoformat() + "Z", "acao": r.acao, "titular": nomes.get(r.titular_id, r.titular_id),
             "autor": nomes.get(r.autor_id, r.autor_id), "detalhes": r.detalhes} for r in linhas]
