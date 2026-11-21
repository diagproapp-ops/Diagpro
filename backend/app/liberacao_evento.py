"""
Liberação de um evento por SESSÃO: quem digita a senha certa do evento passa a ver as questões dele, só naquele
acesso (cai junto com a sessão: saída, inatividade, limite de horas, troca de banca, desconexão remota).

Guardado dentro da própria sessão (tabela sessoes, campo cifrado `detalhes`), nunca a senha: só os ids liberados.
Usado na fila e nas telas de revisão; o administrador geral e o revisor também precisam dela para abrir uma
questão ou texto do evento (nem digitando o endereço direto).
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Sessao
from backend.app.roles import UserRole

CHAVE = "eventos_liberados"
_MAX = 200
# perfis que nunca abrem conteúdo de evento sem a senha dele (o resto do fluxo da banca segue como era)
PAPEIS_QUE_PRECISAM = {UserRole.ADMIN_GERAL.value, UserRole.REVISOR.value}


def _papel(user) -> str:
    r = getattr(user, "role", "")
    return r.value if isinstance(r, UserRole) else str(r)


def _sid(request: Request) -> str | None:
    sid = getattr(request.state, "sid", None)
    return sid if isinstance(sid, str) and sid else None


async def liberar(request: Request, user, evento_id: str) -> None:
    sid = _sid(request)
    if not sid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso antigo: entre novamente para liberar o evento.")
    async with PlatformSessionLocal() as db:
        s = (await db.execute(select(Sessao).where(Sessao.id == sid, Sessao.usuario_id == user.id,
                                                   Sessao.encerrada_em.is_(None)))).scalars().first()
        if s is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão encerrada. Entre novamente.")
        det = dict(s.detalhes or {})
        lista = [e for e in det.get(CHAVE, []) if e != evento_id][-(_MAX - 1):]
        det[CHAVE] = lista + [evento_id]
        s.detalhes = det  # objeto novo: o ORM grava (e cifra) de novo
        await db.commit()


async def liberados(request: Request, user) -> set[str]:
    sid = _sid(request)
    if not sid:
        return set()
    async with PlatformSessionLocal() as db:
        s = (await db.execute(select(Sessao).where(Sessao.id == sid, Sessao.usuario_id == user.id,
                                                   Sessao.encerrada_em.is_(None)))).scalars().first()
    return set((s.detalhes or {}).get(CHAVE, [])) if s else set()


async def esta_liberado(request: Request, user, evento_id: str) -> bool:
    return evento_id in await liberados(request, user)


async def exigir(request: Request, user, evento_id: str, todos: bool = False) -> None:
    """Recusa (403, código evento_bloqueado) se o evento não foi liberado nesta sessão.
    todos=False: só para os perfis que sempre precisam (admin geral e revisor)."""
    if not todos and _papel(user) not in PAPEIS_QUE_PRECISAM:
        return
    if not await esta_liberado(request, user, evento_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"codigo": "evento_bloqueado", "mensagem": "Digite a senha do evento para continuar."})


# ---------------------------------------------------------------- dependências para as rotas com {evento_id}
from fastapi import Depends  # noqa: E402

from backend.app.auth import get_current_user  # noqa: E402


async def exige_para_admin_geral_e_revisor(request: Request, evento_id: str, current_user=Depends(get_current_user)) -> None:
    """Abrir questão/texto do evento: admin geral e revisor só com o evento liberado nesta sessão."""
    await exigir(request, current_user, evento_id)


async def exige_para_todos(request: Request, evento_id: str, current_user=Depends(get_current_user)) -> None:
    """Salvar uma revisão: qualquer perfil, só com o evento liberado nesta sessão."""
    await exigir(request, current_user, evento_id, todos=True)
