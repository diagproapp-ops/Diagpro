import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import get_current_user
from backend.app.db_models import QuestoesBanco
from backend.app.security import get_tenant_db, is_admin_geral
from backend.app.utils_crypto import safe_decrypt_pii

router = APIRouter()
logger = logging.getLogger("biblioteca")


class BibliotecaBuscaRequest(BaseModel):
    busca: str = Field(..., min_length=1, max_length=200)
    limite: int = Field(default=20, ge=1, le=50)


@router.post("/biblioteca")
async def biblioteca(
    payload: BibliotecaBuscaRequest,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    termo = payload.busca.strip().lower()
    if not termo:
        raise HTTPException(status_code=422, detail="Campo de busca não pode ser vazio.")

    stmt = select(QuestoesBanco)
    if not is_admin_geral(current_user):
        stmt = stmt.where(QuestoesBanco.tenant_id == current_user.tenant_id)

    rows = (await db.execute(stmt.limit(500))).scalars().all()

    results = []
    for q in rows:
        enunciado = safe_decrypt_pii(q.enunciado) or ""
        disciplina = q.disciplina_banco or ""
        if termo in enunciado.lower() or termo in disciplina.lower():
            results.append(
                {
                    "id": q.id_questao,
                    "codigo_curto": q.codigo_curto_questao,
                    "assunto": disciplina,
                    "enunciado": enunciado[:400],
                    "nivel": q.nivel_dificuldade,
                    "tipo": q.tipo,
                }
            )
            if len(results) >= payload.limite:
                break

    logger.info("Biblioteca: %d resultados encontrados para tenant=%s", len(results), current_user.tenant_id)
    return {"success": True, "total": len(results), "questoes": results}
