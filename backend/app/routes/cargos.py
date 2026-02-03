from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import uuid
from sqlalchemy import func, asc
import os

from backend.app.database import get_db
from backend.app.db_models import Cargo as DBCargo, DisciplinaDaProva as DBDisciplinaDaProva, Disciplina as DBDisciplina
from backend.app.models import Cargo as PydanticCargo, DisciplinaProva as PydanticDisciplinaProva
from backend.app.auth import get_current_user

router = APIRouter()

async def gerar_identificador_cargo_global(nome_cargo: str, db: AsyncSession):
    letras = ''.join([c for c in nome_cargo if c.isalpha()]).upper()[:2]
    if len(letras) < 2:
        letras = letras.ljust(2, 'X')
    prefix = f"{letras}"
    # Busca todos os identificadores com este prefixo em toda a tabela
    result = await db.execute(
        select(DBCargo.identificador_cargo)
        .filter(DBCargo.identificador_cargo.like(f"{prefix}%"))
    )
    existentes = [ident for ident in result.scalars().all()]
    # Encontra o maior número já usado para o prefixo
    max_num = 0
    for ident in existentes:
        if ident and ident.startswith(prefix):
            try:
                num = int(ident[len(prefix):])
                if num > max_num:
                    max_num = num
            except Exception:
                continue
    numero = str(max_num + 1).zfill(3)
    return f"{prefix}{numero}"

@router.get("/eventos/{event_id}/cargos", response_model=List[PydanticCargo])
async def list_cargos_by_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(DBCargo)
        .where(DBCargo.id_evento_fk == event_id)
        .where(DBCargo.tenant_id == current_user.tenant_id)
    )
    cargos = result.scalars().all()
    response = []
    for db_cargo in cargos:
        disc_result = await db.execute(
            select(DBDisciplinaDaProva)
            .where(DBDisciplinaDaProva.id_cargo_fk == db_cargo.id_cargo)
            .where(DBDisciplinaDaProva.tenant_id == current_user.tenant_id)
            .order_by(asc(DBDisciplinaDaProva.ordem_na_prova))
        )
        disciplinas = disc_result.scalars().all()
        pyd_disc = [PydanticDisciplinaProva.from_orm(d) for d in disciplinas]
        cargo_data = PydanticCargo.from_orm(db_cargo)
        cargo_data.disciplinas_prova = pyd_disc
        response.append(cargo_data)
    return response

@router.post("/eventos/{event_id}/cargos", response_model=PydanticCargo, status_code=status.HTTP_201_CREATED)
async def create_cargo_for_event(
    event_id: str,
    cargo: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    required_fields = ["nome_cargo", "nivel", "turno"]
    for field in required_fields:
        if not cargo.get(field):
            raise HTTPException(status_code=400, detail=f"Campo obrigatório ausente: {field}")

    new_id = str(uuid.uuid4())
    identificador_cargo = await gerar_identificador_cargo_global(cargo["nome_cargo"], db)

    cover_pdf_paths = cargo.get("cover_pdf_paths", [])
    if isinstance(cover_pdf_paths, str):
        cover_pdf_paths = [cover_pdf_paths]
    elif not isinstance(cover_pdf_paths, list):
        cover_pdf_paths = []

    db_cargo = DBCargo(
        id_cargo=new_id,
        identificador_cargo=identificador_cargo,
        tenant_id=current_user.tenant_id,
        id_evento_fk=event_id,
        nome_cargo=cargo["nome_cargo"],
        codigo_cargo=cargo.get("codigo_cargo"),
        nivel=cargo.get("nivel"),
        turno=cargo.get("turno"),
        vagas=cargo.get("vagas", 0),
        salario=cargo.get("salario", 0.0),
        requisitos=cargo.get("requisitos"),
        tem_discursiva=bool(cargo.get("tem_discursiva")),
        letterhead_pdf_path=cargo.get("letterhead_pdf_path"),
        cover_pdf_paths=cover_pdf_paths,
        peso_total_prova=cargo.get("peso_total_prova", 0.0),
    )
    db.add(db_cargo)
    await db.commit()
    await db.refresh(db_cargo)

    for disc in cargo.get("disciplinas_prova", []):
        disc_base_id = disc.get("disciplina_base_id")
        nome_disciplina = disc.get("nome_disciplina") or disc.get("nome_disciplina_na_prova")
        if not disc_base_id:
            result = await db.execute(
                select(DBDisciplina)
                .where(DBDisciplina.nome_disciplina == nome_disciplina)
                .where(DBDisciplina.id_evento_fk == event_id)
            )
            db_disc = result.scalar_one_or_none()
            if db_disc:
                disc_base_id = db_disc.id_disciplina
            else:
                disc_base_id = str(uuid.uuid4())
                db_disc_new = DBDisciplina(
                    id_disciplina=disc_base_id,
                    id_evento_fk=event_id,
                    nome_disciplina=nome_disciplina,
                )
                db.add(db_disc_new)
                await db.commit()
        db_disc_prova = DBDisciplinaDaProva(
            id_disciplina_prova=str(uuid.uuid4()),
            id_cargo_fk=new_id,
            id_disciplina_base_fk=disc_base_id,
            nome_disciplina_na_prova=nome_disciplina,
            qtd_questoes=disc.get("qtd_questoes"),
            peso_por_questao=disc.get("peso_por_questao"),
            ordem_na_prova=disc.get("ordem_na_prova"),
            observacoes=disc.get("observacoes"),
            tipo_conhecimento=disc.get("tipo_conhecimento", "comum"),
            tenant_id=current_user.tenant_id,
        )
        db.add(db_disc_prova)
    await db.commit()

    saved_cargo_id = db_cargo.id_cargo

    disc_result = await db.execute(
        select(DBDisciplinaDaProva)
        .where(DBDisciplinaDaProva.id_cargo_fk == saved_cargo_id)
        .where(DBDisciplinaDaProva.tenant_id == current_user.tenant_id)
        .order_by(asc(DBDisciplinaDaProva.ordem_na_prova))
    )
    disciplinas = disc_result.scalars().all()
    pyd_disc = [PydanticDisciplinaProva.from_orm(d) for d in disciplinas]
    cargo_data = PydanticCargo.from_orm(db_cargo)
    cargo_data.disciplinas_prova = pyd_disc
    return cargo_data

@router.put("/cargos/{cargo_id}", response_model=PydanticCargo)
async def update_cargo(
    cargo_id: str,
    cargo: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(DBCargo)
        .where(DBCargo.id_cargo == cargo_id)
        .where(DBCargo.tenant_id == current_user.tenant_id)
    )
    db_cargo = result.scalar_one_or_none()
    if not db_cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")

    cover_pdf_paths = cargo.get("cover_pdf_paths", [])
    if isinstance(cover_pdf_paths, str):
        cover_pdf_paths = [cover_pdf_paths]
    elif not isinstance(cover_pdf_paths, list):
        cover_pdf_paths = []

    event_id = db_cargo.id_evento_fk
    saved_cargo_id = db_cargo.id_cargo

    # Salve os dados ANTES do commit/refresh
    cargo_dict = {
        "id_cargo": db_cargo.id_cargo,
        "identificador_cargo": db_cargo.identificador_cargo,
        "nome_cargo": cargo.get("nome_cargo", db_cargo.nome_cargo),
        "codigo_cargo": cargo.get("codigo_cargo", db_cargo.codigo_cargo),
        "nivel": cargo.get("nivel", db_cargo.nivel),
        "turno": cargo.get("turno", db_cargo.turno),
        "vagas": cargo.get("vagas", db_cargo.vagas),
        "salario": cargo.get("salario", db_cargo.salario),
        "requisitos": cargo.get("requisitos", db_cargo.requisitos),
        "tem_discursiva": cargo.get("tem_discursiva", db_cargo.tem_discursiva),
        "letterhead_pdf_path": cargo.get("letterhead_pdf_path", db_cargo.letterhead_pdf_path),
        "cover_pdf_paths": cover_pdf_paths,
        "peso_total_prova": cargo.get("peso_total_prova", db_cargo.peso_total_prova),
        "disciplinas_prova": []  # Preencher depois
    }

    for key, value in cargo.items():
        if key == "cover_pdf_paths":
            setattr(db_cargo, key, cover_pdf_paths)
        elif hasattr(db_cargo, key) and key != "disciplinas_prova":
            setattr(db_cargo, key, value)
    await db.commit()
    await db.refresh(db_cargo)

    await db.execute(
        DBDisciplinaDaProva.__table__.delete()
        .where(DBDisciplinaDaProva.id_cargo_fk == cargo_id)
        .where(DBDisciplinaDaProva.tenant_id == current_user.tenant_id)
    )
    await db.commit()
    for disc in cargo.get("disciplinas_prova", []):
        disc_base_id = disc.get("disciplina_base_id")
        nome_disciplina = disc.get("nome_disciplina") or disc.get("nome_disciplina_na_prova")
        if not disc_base_id:
            result = await db.execute(
                select(DBDisciplina)
                .where(DBDisciplina.nome_disciplina == nome_disciplina)
                .where(DBDisciplina.id_evento_fk == event_id)
            )
            db_disc = result.scalar_one_or_none()
            if db_disc:
                disc_base_id = db_disc.id_disciplina
            else:
                disc_base_id = str(uuid.uuid4())
                db_disc_new = DBDisciplina(
                    id_disciplina=disc_base_id,
                    id_evento_fk=event_id,
                    nome_disciplina=nome_disciplina,
                )
                db.add(db_disc_new)
                await db.commit()
        db_disc_prova = DBDisciplinaDaProva(
            id_disciplina_prova=str(uuid.uuid4()),
            id_cargo_fk=cargo_id,
            id_disciplina_base_fk=disc_base_id,
            nome_disciplina_na_prova=nome_disciplina,
            qtd_questoes=disc.get("qtd_questoes"),
            peso_por_questao=disc.get("peso_por_questao"),
            ordem_na_prova=disc.get("ordem_na_prova"),
            observacoes=disc.get("observacoes"),
            tipo_conhecimento=disc.get("tipo_conhecimento", "comum"),
            tenant_id=current_user.tenant_id,
        )
        db.add(db_disc_prova)
    await db.commit()

    disc_result = await db.execute(
        select(DBDisciplinaDaProva)
        .where(DBDisciplinaDaProva.id_cargo_fk == saved_cargo_id)
        .where(DBDisciplinaDaProva.tenant_id == current_user.tenant_id)
        .order_by(asc(DBDisciplinaDaProva.ordem_na_prova))
    )
    disciplinas = disc_result.scalars().all()
    pyd_disc = [PydanticDisciplinaProva.from_orm(d) for d in disciplinas]
    cargo_dict["disciplinas_prova"] = pyd_disc

    # Retorne usando o dict, não o ORM expirado
    return PydanticCargo(**cargo_dict)

@router.delete("/cargos/{cargo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cargo_by_id(
    cargo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    await db.execute(
        DBDisciplinaDaProva.__table__.delete().where(
            (DBDisciplinaDaProva.id_cargo_fk == cargo_id) &
            (DBDisciplinaDaProva.tenant_id == current_user.tenant_id)
        )
    )
    await db.commit()

    await db.execute(
        DBCargo.__table__.delete().where(
            (DBCargo.id_cargo == cargo_id) &
            (DBCargo.tenant_id == current_user.tenant_id)
        )
    )
    await db.commit()

    return None

@router.post("/eventos/{event_id}/cargos/upload-capa-pdf")
async def upload_capa_pdf(event_id: str, file: UploadFile = File(...)):
    out_dir = "static/capas"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{event_id}_{file.filename}")
    with open(out_path, "wb") as f:
        f.write(await file.read())
    return {"cover_pdf_paths": [out_path]}