# backend/app/routes/editor.py
"""Apoio ao editor de questões: confere se uma equação vai sair na prova (Word/PDF)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app import equacoes
from backend.app.auth import get_current_user
from backend.app.rate_limit import rate_limit

router = APIRouter(prefix="/editor", tags=["Editor"])


class PedidoEquacao(BaseModel):
    latex: str = Field(..., max_length=equacoes.LIMITE_LATEX + 100)


@router.post("/equacao/validar", dependencies=[Depends(rate_limit(120, 60, "editor-equacao"))])
async def validar_equacao(pedido: PedidoEquacao, current_user=Depends(get_current_user)):
    """
    Converte a equação como a exportação faz, só em memória, e diz se ela pode ir para a prova.
    Nada é gravado nem registrado (a equação é conteúdo de prova).
    """
    erro = equacoes.validar(pedido.latex)
    return {"ok": erro is None, "erro": erro}
