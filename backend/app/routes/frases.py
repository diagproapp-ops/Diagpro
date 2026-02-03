from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from typing import List
import csv
import io

from backend.app.database import get_db
from backend.app.db_models import BancoFrases
from backend.app.auth import get_current_user, get_admin_user
from backend.app.models import Frase, FraseCreate

router = APIRouter()

@router.get("/", response_model=List[Frase])
async def list_frases(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(BancoFrases).where(BancoFrases.tenant_id == current_user.tenant_id))
    frases = result.scalars().all()
    return frases

@router.post("/import/", status_code=status.HTTP_201_CREATED)
async def import_frases_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin_user=Depends(get_admin_user)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Apenas arquivos CSV são permitidos.")

    tenant_id = admin_user.tenant_id

    try:
        content = await file.read()
        text_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(text_content), delimiter=';')
        
        result = await db.execute(select(func.max(BancoFrases.id_local)).where(BancoFrases.tenant_id == tenant_id))
        max_id_local = result.scalar() or 0
        next_id_local = max_id_local + 1

        phrases_to_insert = []
        for row in csv_reader:
            if 'categoria' in row and 'texto_frase' in row:
                phrases_to_insert.append({
                    'categoria': row['categoria'].strip(),
                    'texto_frase': row['texto_frase'].strip(),
                    'ativo': True,
                    'tenant_id': tenant_id,
                    'id_local': next_id_local,
                    'identificador': row.get('identificador', '').strip() or None
                })
                next_id_local += 1

        if not phrases_to_insert:
            raise HTTPException(status_code=400, detail="Nenhuma frase válida encontrada no arquivo CSV. Verifique as colunas 'categoria' e 'texto_frase'.")
        await db.execute(
            sqlite_insert(BancoFrases).values(phrases_to_insert).on_conflict_do_nothing()
        )
        await db.commit()
        return {"message": f"{len(phrases_to_insert)} frases importadas com sucesso!"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar o arquivo: {e}"
        )

@router.post("/", response_model=Frase, status_code=status.HTTP_201_CREATED)
async def create_frase(
    frase_data: FraseCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if not frase_data.tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id é obrigatório!")

    result = await db.execute(select(func.max(BancoFrases.id_local)).where(BancoFrases.tenant_id == frase_data.tenant_id))
    max_id_local = result.scalar() or 0
    next_id_local = max_id_local + 1

    nova_frase = BancoFrases(
        categoria=frase_data.categoria,
        texto_frase=frase_data.texto_frase,
        tenant_id=frase_data.tenant_id,
        id_local=next_id_local,
        ativo=True
    )
    db.add(nova_frase)
    await db.commit()
    await db.refresh(nova_frase)
    return nova_frase

@router.put("/{frase_id}", response_model=Frase)
async def update_frase(
    frase_id: int,
    frase_data: FraseCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(BancoFrases).where(BancoFrases.id == frase_id))
    frase_existente = result.scalars().first()

    if not frase_existente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frase com ID {frase_id} não encontrada."
        )
    
    frase_existente.categoria = frase_data.categoria
    frase_existente.texto_frase = frase_data.texto_frase
    frase_existente.tenant_id = frase_data.tenant_id
    # Não altere id_local!
    await db.commit()
    await db.refresh(frase_existente)
    return frase_existente

@router.delete("/{frase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_frase(
    frase_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(BancoFrases).where(BancoFrases.id == frase_id))
    frase_para_remover = result.scalars().first()

    if not frase_para_remover:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frase com ID {frase_id} não encontrada."
        )
    
    await db.delete(frase_para_remover)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)