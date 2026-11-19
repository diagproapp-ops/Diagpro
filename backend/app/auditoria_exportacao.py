# backend/app/auditoria_exportacao.py
"""
Registro de quem exportou prova pronta ou gabarito: quando, de onde, quais cargos, com quais opções e a
impressão digital (SHA-256) de cada arquivo entregue. Fica em audit_log_geracao (colunas cifradas).

Falha fechada: se não for possível registrar, a exportação é recusada (o chamador deixa a exceção subir).
Nunca registra a senha do evento nem conteúdo de prova.
"""
import hashlib
import json
from datetime import datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db_models import AuditLogGeracao


def _sha256(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


async def registrar_exportacao(
    db: AsyncSession,
    request: Request,
    current_user,
    evento,
    acao: str,
    cargos: list[str],
    parametros: dict,
    arquivos: list[tuple[str, str]] | None = None,
) -> None:
    """arquivos: [(nome dentro do pacote, caminho local)]"""
    impressoes = [{"arquivo": nome, "sha256": _sha256(caminho)} for nome, caminho in (arquivos or [])]
    log = AuditLogGeracao(
        tenant_id=evento.tenant_id,
        timestamp=datetime.utcnow(),
        usuario=getattr(current_user, "username", None) or str(getattr(current_user, "id", "?")),
        evento=getattr(evento, "nome_evento", "") or "",
        cargo=", ".join(cargos)[:2000],
        acao=acao,
        parametros=json.dumps({**parametros, "arquivos": impressoes}, ensure_ascii=False, default=str),
        ip=request.client.host if request.client else "",
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(log)
    await db.commit()
