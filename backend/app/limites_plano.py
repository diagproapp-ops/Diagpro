"""
Limites do plano contratado pela banca (eventos, usuários, questões). Banca sem plano ou plano sem limite = livre.
O administrador geral (suporte) não é barrado. A mensagem diz o uso e o limite, sem expor nada de outra banca.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import get_current_user
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Evento, PlanoBanca, QuestoesBanco, Tenant, User, VinculoBanca
from backend.app.roles import UserRole
from backend.app.security import get_tenant_db

RECURSOS = {"eventos": "eventos", "usuarios": "usuários", "questoes": "questões"}


async def plano_da_banca(tenant_id: int) -> PlanoBanca | None:
    async with PlatformSessionLocal() as db:
        t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalars().first()
        nome = (t.plan_type or "").strip() if t else ""
        if not nome:
            return None
        return (await db.execute(select(PlanoBanca).where(or_(PlanoBanca.nome == nome, PlanoBanca.codigo == nome.lower())))).scalars().first()


async def uso(db: AsyncSession, tenant_id: int) -> dict[str, int]:
    """Uso atual (sessão da banca). Usuários = contas ativas ou aguardando aprovação + vínculos (exceto inativos)."""
    eventos = (await db.execute(select(func.count(Evento.id_evento)).where(
        Evento.tenant_id == tenant_id, Evento.is_deleted.is_(False)))).scalar_one()
    questoes = (await db.execute(select(func.count(QuestoesBanco.id_questao)).where(QuestoesBanco.tenant_id == tenant_id))).scalar_one()
    proprios = (await db.execute(select(func.count(User.id)).where(
        User.tenant_id == tenant_id, User.is_active.is_(True), func.coalesce(User.status, "ativo") != "inativo"))).scalar_one()
    vinc = (await db.execute(select(func.count(VinculoBanca.id)).where(
        VinculoBanca.tenant_id == tenant_id, VinculoBanca.status != "inativo"))).scalar_one()
    return {"eventos": int(eventos), "usuarios": int(proprios + vinc), "questoes": int(questoes)}


async def situacao(db: AsyncSession, tenant_id: int) -> dict:
    plano = await plano_da_banca(tenant_id)
    atual = await uso(db, tenant_id)
    limites = {"eventos": plano.limite_eventos, "usuarios": plano.limite_usuarios, "questoes": plano.limite_questoes} if plano else {}
    return {"plano": plano.nome if plano else None,
            "itens": [{"recurso": k, "rotulo": RECURSOS[k], "uso": atual[k], "limite": limites.get(k)} for k in RECURSOS]}


async def exigir(db: AsyncSession, current_user, recurso: str, novos: int = 1) -> None:
    if current_user.role == UserRole.ADMIN_GERAL or current_user.tenant_id is None:
        return
    plano = await plano_da_banca(current_user.tenant_id)
    if plano is None:
        return
    limite = {"eventos": plano.limite_eventos, "usuarios": plano.limite_usuarios, "questoes": plano.limite_questoes}[recurso]
    if limite is None:
        return
    atual = (await uso(db, current_user.tenant_id))[recurso]
    if atual + novos > limite:
        raise HTTPException(status_code=403, detail={
            "codigo": "limite_plano",
            "mensagem": f"Limite do plano {plano.nome} atingido: {atual} de {limite} {RECURSOS[recurso]}. "
                        "Fale com a plataforma (Financeiro > Minha conta na plataforma) para mudar de plano."})


def dependencia(recurso: str):
    async def _verificar(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)) -> None:
        await exigir(db, current_user, recurso)
    return _verificar
