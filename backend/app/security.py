# backend/app/security.py
"""Helpers de autorização e de manipulação segura de arquivos."""

import hmac
import json
import logging
import os
import re

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.auth import get_current_user
from backend.app.database import SessionLocal, PlatformSessionLocal, set_tenant_context
from backend.app.db_models import Evento as DBEvento
from backend.app.rate_limit import checar_bloqueio_por_falhas, registrar_falha
from backend.app.roles import UserRole

_log = logging.getLogger(__name__)


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
    - administrador geral com cliente escolhido (X-Tenant-Id): a MESMA role de runtime, sob o RLS
      daquele cliente — enxerga e grava só nele, exatamente como um usuário do cliente;
    - administrador geral na visão global: role de plataforma (BYPASSRLS), única credencial multi-tenant.
    Falha fechada se um usuário comum não tiver tenant_id.
    """
    if is_admin_geral(current_user) and current_user.tenant_id is None:
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


_TOKEN_CIFRADO = re.compile(r"gAAAAA[\w-]{40,}={0,2}|\be1\.\d+\.[\w-]{20,}")


def exigir_texto_claro(dados, contexto: str = "prova") -> None:
    """
    Trava do gerador: recusa montar prova/gabarito se algum texto ainda estiver no formato cifrado
    (Fernet legado ou e1). Melhor falhar com mensagem clara do que imprimir lixo cifrado na prova.
    Não registra o conteúdo, só a quantidade.
    """
    texto = json.dumps(dados, ensure_ascii=False, default=str)
    achados = len(_TOKEN_CIFRADO.findall(texto))
    if achados:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"A {contexto} contém {achados} texto(s) ainda cifrado(s) e não pode ser gerada. "
                    "Salve a montagem da prova novamente ou avise o suporte."),
        )


SENHA_EVENTO_HEADER = "X-Senha-Evento"
_MAX_FALHAS_SENHA = 5
_JANELA_FALHAS_SENHA = 600  # segundos


def conferir_senha_evento(evento: DBEvento, senha: str | None, current_user) -> None:
    """
    Regra do DiagPro: prova pronta e gabarito só para quem tem a senha do evento.
    Comparação em tempo constante; erros contam para bloqueio (5 em 10 min por usuário/evento).
    """
    chave = f"senha-evento:{getattr(current_user, 'id', '?')}:{evento.id_evento}"
    checar_bloqueio_por_falhas(chave, _MAX_FALHAS_SENHA, _JANELA_FALHAS_SENHA)
    if not senha:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Informe a senha do evento.")
    guardada = evento.senha_evento_cripto or ""  # o ORM já entrega decifrada
    if not guardada or not hmac.compare_digest(senha.encode(), guardada.encode()):
        registrar_falha(chave)
        _log.warning("Senha do evento inválida (evento %s, usuário %s)", evento.id_evento, getattr(current_user, "id", "?"))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Senha do evento inválida.")


async def evento_com_senha(
    evento: DBEvento = Depends(evento_autorizado),
    current_user=Depends(get_current_user),
    x_senha_evento: str | None = Header(None, alias=SENHA_EVENTO_HEADER),
) -> DBEvento:
    """Dependência: evento do cliente do usuário E senha do evento correta no cabeçalho X-Senha-Evento."""
    conferir_senha_evento(evento, x_senha_evento, current_user)
    return evento


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
