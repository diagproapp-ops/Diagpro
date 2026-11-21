"""
Pessoa x banca. Uma conta (login, senha, 2FA, foto, dados pessoais) pode trabalhar para várias bancas:

- banca de ORIGEM = users.tenant_id: o vínculo é o próprio cadastro (users.role / users.status);
- OUTRAS bancas = linhas em vinculos_banca, cada uma com função e aprovação próprias.

Só a banca de origem altera os dados da pessoa (o RLS de escrita de users não mudou); as outras leem a
identidade de quem está vinculado a elas (política `membros_da_banca`) e controlam apenas o vínculo.
users.is_active é a CONTA (anonimização/bloqueio geral); users.status é o vínculo com a banca de origem.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Tenant, User, VinculoBanca

ATIVO, PENDENTE, INATIVO = "ativo", "pendente", "inativo"
# funções que uma banca pode dar a quem é de outra banca de origem (administração nunca é emprestada)
PAPEIS_CONVIDAVEIS = {"professor", "revisor", "diagramador"}


def conta_ativa(user) -> bool:
    return bool(getattr(user, "is_active", False))


def status_origem(user) -> str:
    s = (getattr(user, "status", None) or ATIVO).lower()
    return s if s in (ATIVO, PENDENTE, INATIVO) else ATIVO


def origem_ativa(user) -> bool:
    return conta_ativa(user) and status_origem(user) == ATIVO


class UsuarioNaBanca:
    """A conta vista DENTRO de uma banca: mesma pessoa, função e banca do vínculo. Só leitura."""

    def __init__(self, user, tenant_id: int, role: str):
        object.__setattr__(self, "_user", user)
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "role", role)

    def __getattr__(self, nome):
        return getattr(self._user, nome)

    def __setattr__(self, nome, valor):  # nunca grava no cadastro por engano (troca de banca/função)
        raise AttributeError("UsuarioNaBanca é somente leitura")


@dataclass
class Banca:
    tenant_id: int
    nome: str
    role: str
    origem: bool


async def bancas_da_pessoa(user) -> list[Banca]:
    """Bancas em que a pessoa pode entrar agora (vínculo ativo). Sessão de plataforma: uso só no login."""
    if not conta_ativa(user):
        return []
    papeis: dict[int, tuple[str, bool]] = {}
    if user.tenant_id is not None and origem_ativa(user):
        papeis[user.tenant_id] = (user.role, True)
    async with PlatformSessionLocal() as db:
        for v in (await db.execute(select(VinculoBanca).where(
                VinculoBanca.user_id == user.id, VinculoBanca.status == ATIVO))).scalars():
            papeis.setdefault(v.tenant_id, (v.role, False))
        if not papeis:
            return []
        nomes = {t.id: t.name for t in (await db.execute(select(Tenant).where(Tenant.id.in_(list(papeis))))).scalars()}
    return sorted((Banca(tid, nomes.get(tid) or f"Banca {tid}", role, origem) for tid, (role, origem) in papeis.items()),
                  key=lambda b: (not b.origem, b.nome.lower()))


async def trabalha_para_outras_bancas(user_id: int) -> bool:
    """Se a pessoa tem vínculo com alguma outra banca. A sessão da banca não enxerga vínculos alheios (RLS):
    consulta de existência na plataforma, sem devolver qual banca."""
    async with PlatformSessionLocal() as db:
        return (await db.execute(select(VinculoBanca.id).where(VinculoBanca.user_id == user_id).limit(1))).first() is not None


async def papel_na_banca(db: AsyncSession, user, tenant_id: int) -> tuple[str, str] | None:
    """(função, status) da pessoa na banca, ou None se não tem vínculo. `db` já sob o RLS dessa banca."""
    if user.tenant_id == tenant_id:
        return user.role, status_origem(user)
    v = (await db.execute(select(VinculoBanca).where(
        VinculoBanca.user_id == user.id, VinculoBanca.tenant_id == tenant_id))).scalars().first()
    return (v.role, v.status) if v else None


def membros_da_banca(tenant_id: int):
    """Filtro SQL: quem é da banca (origem) ou tem vínculo com ela."""
    return or_(User.tenant_id == tenant_id,
               User.id.in_(select(VinculoBanca.user_id).where(VinculoBanca.tenant_id == tenant_id)))


async def vinculos_da_banca(db: AsyncSession, tenant_id: int) -> dict[int, VinculoBanca]:
    return {v.user_id: v for v in (await db.execute(
        select(VinculoBanca).where(VinculoBanca.tenant_id == tenant_id))).scalars()}


def papel_e_status(user, vinculos: dict[int, VinculoBanca], tenant_id: int) -> tuple[str, str, bool]:
    """(função, status, é_da_banca_de_origem) da pessoa nesta banca."""
    if user.tenant_id == tenant_id:
        return user.role, status_origem(user), True
    v = vinculos.get(user.id)
    if v is None:
        return user.role, INATIVO, False
    return v.role, v.status, False


async def usuarios_da_banca(db: AsyncSession, tenant_id: int, roles: set[str] | None = None,
                            somente_ativos: bool = True) -> list[tuple[User, str]]:
    """[(usuário, função na banca)] de quem é da banca ou tem vínculo com ela."""
    vinculos = await vinculos_da_banca(db, tenant_id)
    saida = []
    for u in (await db.execute(select(User).where(membros_da_banca(tenant_id)))).scalars().all():
        role, status, _origem = papel_e_status(u, vinculos, tenant_id)
        if somente_ativos and (status != ATIVO or not conta_ativa(u)):
            continue
        if roles is not None and role not in roles:
            continue
        saida.append((u, role))
    return saida


async def criar_vinculo(db: AsyncSession, tenant_id: int, user_id: int, role: str, convidado_por: int | None) -> VinculoBanca:
    """Vínculo PENDENTE (o administrador da banca aprova). Idempotente: devolve o existente."""
    atual = (await db.execute(select(VinculoBanca).where(
        VinculoBanca.user_id == user_id, VinculoBanca.tenant_id == tenant_id))).scalars().first()
    if atual:
        return atual
    v = VinculoBanca(tenant_id=tenant_id, user_id=user_id, role=role, status=PENDENTE,
                     criado_em=datetime.utcnow(), convidado_por=convidado_por)
    db.add(v)
    return v
