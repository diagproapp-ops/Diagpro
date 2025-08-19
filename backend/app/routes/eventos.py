# backend/app/routes/eventos.py (VERSÃO CORRIGIDA E FINAL)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from backend.app.database import get_db
# Usamos os modelos SQLAlchemy que são um espelho da sua BD
from backend.app.db_models import Evento as DBEvento
# Usamos os modelos Pydantic que definem a resposta da API
from backend.app.models import Evento as PydanticEvento
from backend.app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[PydanticEvento])
async def list_eventos(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Busca todos os eventos e os cargos associados a cada um.
    """
    # A opção selectinload(DBEvento.cargos) carrega os cargos de forma eficiente
    result = await db.execute(
        select(DBEvento).options(selectinload(DBEvento.cargos))
    )
    eventos = result.scalars().all()
    return eventos # O Pydantic converte automaticamente!

# --- ADICIONE ESTA NOVA ROTA ---
@router.get("/{event_id}", response_model=PydanticEvento)
async def get_evento_details(
    event_id: str, # O ID do evento virá da URL
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(DBEvento)
        .options(selectinload(DBEvento.cargos)) # Carrega os cargos junto
        .filter(DBEvento.id_evento == event_id)
    )
    evento = result.scalars().first()

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    return evento # O Pydantic faz a conversão automática