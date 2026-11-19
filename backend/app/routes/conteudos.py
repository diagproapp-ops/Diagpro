import logging as _diag_logging
_diag_print_logger = _diag_logging.getLogger(__name__)


def print(*args, **kwargs):  # noqa: A001
    """Prints de depuração viram log DEBUG: não expõem conteúdo de prova em produção (DIAGPRO_LOG_LEVEL)."""
    _diag_print_logger.debug(" ".join(str(a) for a in args))


from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.field_crypto import blind_eq
from backend.app.security import get_tenant_db, require_roles
from backend.app.roles import UserRole
from backend.app.db_models import Conteudo as DBConteudo, User as DBUser, QuestoesBanco
from backend.app.models import ConteudoCreate, ConteudoOut
from backend.app.auth import get_current_user
from typing import List
import csv
import json
import uuid

from pydantic import BaseModel

# >>> MODELO DE RESPOSTA PARA O SWAGGER <<<
class ImportResult(BaseModel):
    importados: List[str]
    erros: List[str]

router = APIRouter()

async def gerar_identificador_conteudo(nome_conteudo: str, db: AsyncSession):
    letras = ''.join([c for c in nome_conteudo if c.isalpha()]).upper()[:2]
    if len(letras) < 2:
        letras = letras.ljust(2, 'X')
    prefix = f"{letras}"
    result = await db.execute(
        select(func.count(DBConteudo.identificador_conteudo))
        .where(DBConteudo.identificador_conteudo.like(f"{prefix}%"))
    )
    count = result.scalar_one() or 0
    numero = str(count + 1).zfill(3)
    return f"{prefix}{numero}"

# LISTA conteúdos (com respondidas calculado dinamicamente)
@router.get("/eventos/{evento_id}/conteudos", response_model=List[ConteudoOut])
async def list_conteudos(
    evento_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    query = select(DBConteudo).where(
        DBConteudo.evento_id == evento_id,
        DBConteudo.is_deleted == False,
        DBConteudo.tenant_id == current_user.tenant_id
    )
    if current_user.role == "professor":
        query = query.where(DBConteudo.professor_id == str(current_user.id))  # professor_id é texto no banco
    result = await db.execute(query)
    conteudos = result.scalars().all()

    lista = []
    for c in conteudos:
        d = c.__dict__.copy()
        # Metadados como dict
        if 'metadados' in d and isinstance(d['metadados'], str):
            try:
                d['metadados'] = json.loads(d['metadados'])
            except Exception:
                d['metadados'] = {}

        # CALCULA respondidas dinamicamente!
        q_result = await db.execute(
            select(func.count(QuestoesBanco.id_questao)).where(
                QuestoesBanco.conteudo_id == c.id_conteudo,
                QuestoesBanco.tenant_id == current_user.tenant_id
            )
        )
        d['respondidas'] = q_result.scalar() or 0

        lista.append(ConteudoOut.model_validate(d))
    return lista

# CRIA conteúdo
@router.post("/eventos/{evento_id}/conteudos", response_model=ConteudoOut)
async def create_conteudo(
    evento_id: str,
    conteudo: ConteudoCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))
):
    data = conteudo.model_dump()
    data['evento_id'] = evento_id
    data['tenant_id'] = current_user.tenant_id
    data['identificador_conteudo'] = await gerar_identificador_conteudo(data['nome_conteudo'], db)
    if 'metadados' in data and isinstance(data['metadados'], dict):
        data['metadados'] = json.dumps(data['metadados'])
    if 'id_conteudo' not in data or not data['id_conteudo']:
        data['id_conteudo'] = str(uuid.uuid4())
    db_conteudo = DBConteudo(**data)
    db.add(db_conteudo)
    await db.commit()
    await db.refresh(db_conteudo)
    conteudo_dict = db_conteudo.__dict__.copy()
    if 'metadados' in conteudo_dict and isinstance(conteudo_dict['metadados'], str):
        try:
            conteudo_dict['metadados'] = json.loads(conteudo_dict['metadados'])
        except Exception:
            conteudo_dict['metadados'] = {}
    return ConteudoOut.model_validate(conteudo_dict)

# ATUALIZA conteúdo
@router.put("/{conteudo_id}", response_model=ConteudoOut)
async def update_conteudo(
    conteudo_id: str,
    conteudo: ConteudoCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    query = select(DBConteudo).where(
        DBConteudo.id_conteudo == conteudo_id,
        DBConteudo.tenant_id == current_user.tenant_id,
        DBConteudo.is_deleted == False,
    )
    # Restrição para professor
    if current_user.role == "professor":
        query = query.where(DBConteudo.professor_id == str(current_user.id))  # professor_id é texto no banco
    result = await db.execute(query)
    db_conteudo = result.scalar_one_or_none()
    if not db_conteudo:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
    for key, value in conteudo.model_dump(exclude_unset=True).items():
        if key == "metadados" and isinstance(value, dict):
            value = json.dumps(value)
        setattr(db_conteudo, key, value)
    await db.commit()
    await db.refresh(db_conteudo)
    conteudo_dict = db_conteudo.__dict__.copy()
    if 'metadados' in conteudo_dict and isinstance(conteudo_dict['metadados'], str):
        try:
            conteudo_dict['metadados'] = json.loads(conteudo_dict['metadados'])
        except Exception:
            conteudo_dict['metadados'] = {}
    return ConteudoOut.model_validate(conteudo_dict)

# DELETA conteúdo
@router.delete("/{conteudo_id}", response_model=dict)
async def delete_conteudo(
    conteudo_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))
):
    result = await db.execute(
        select(DBConteudo).where(
            DBConteudo.id_conteudo == conteudo_id,
            DBConteudo.tenant_id == current_user.tenant_id,
            DBConteudo.is_deleted == False,
        )
    )
    db_conteudo = result.scalar_one_or_none()
    if not db_conteudo:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
    db_conteudo.is_deleted = True
    await db.commit()
    return {"ok": True}

# Função auxiliar para buscar id do professor pelo nome
async def get_professor_id_by_name(prof_name: str, db: AsyncSession, tenant_id: int) -> int | None:
    result = await db.execute(
        select(DBUser.id)
        .where(
            blind_eq(DBUser.full_name, prof_name, tenant_id),
            DBUser.role == "professor",
            DBUser.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()

# IMPORTAÇÃO via CSV
@router.post("/eventos/{evento_id}/conteudos/csv", response_model=ImportResult)
async def import_conteudos_csv(
    evento_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))
):
    print(">>> Iniciando importação via CSV <<<")
    content = await file.read()
    print("Arquivo lido, tamanho:", len(content))
    reader = csv.DictReader(content.decode("utf-8-sig").splitlines(), delimiter=';')
    print("Cabeçalho do CSV:", reader.fieldnames)
    imported = []
    errors = []

    for row in reader:
        print("Linha lida:", row)
        try:
            nome_conteudo = row.get("nome_conteudo", "").strip()
            descricao = row.get("descricao", "").strip()
            area_conhecimento = row.get("area_conhecimento", "").strip()
            turno = row.get("turno", "").strip()
            nivel = row.get("nivel", "").strip()
            quantidade = int(row.get("quantidade", "0"))
            professor_nome = row.get("professor", "").strip()

            prof_id = await get_professor_id_by_name(professor_nome, db, current_user.tenant_id)
            print(f"Buscando professor: '{professor_nome}' | tenant: {current_user.tenant_id} | ID encontrado: {prof_id}")
            if prof_id is None:
                errors.append(f"Professor '{professor_nome}' não encontrado para conteúdo '{nome_conteudo}'")
                continue

            data = {
                "nome_conteudo": nome_conteudo,
                "descricao": descricao,
                "area_conhecimento": area_conhecimento,
                "turno": turno,
                "nivel": nivel,
                "quantidade": quantidade,
                "professor_id": prof_id,
                "tenant_id": current_user.tenant_id,
                "evento_id": evento_id,
                "identificador_conteudo": await gerar_identificador_conteudo(nome_conteudo, db),
                "id_conteudo": str(uuid.uuid4()),
            }

            db_conteudo = DBConteudo(**data)
            db.add(db_conteudo)
            imported.append(nome_conteudo)
        except Exception as e:
            print(f"Erro ao importar '{row.get('nome_conteudo', '')}': {str(e)}")
            errors.append(f"Erro ao importar '{row.get('nome_conteudo', '')}': {str(e)}")

    print("Importados até agora:", imported)
    print("Erros até agora:", errors)
    await db.commit()
    return {"importados": imported, "erros": errors}

# LISTA só os conteúdos do usuário (meus)
@router.get("/meus", response_model=List[ConteudoOut])
async def list_meus_conteudos(
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    query = select(DBConteudo).where(
        DBConteudo.is_deleted == False,
        DBConteudo.tenant_id == current_user.tenant_id
    )
    if current_user.role == "professor":
        query = query.where(DBConteudo.professor_id == str(current_user.id))  # professor_id é texto no banco
    result = await db.execute(query)
    conteudos = result.scalars().all()

    lista = []
    for c in conteudos:
        d = c.__dict__.copy()
        # Metadados como dict
        if 'metadados' in d and isinstance(d['metadados'], str):
            try:
                d['metadados'] = json.loads(d['metadados'])
            except Exception:
                d['metadados'] = {}

        # CALCULA respondidas dinamicamente!
        q_result = await db.execute(
            select(func.count(QuestoesBanco.id_questao)).where(
                QuestoesBanco.conteudo_id == c.id_conteudo,
                QuestoesBanco.tenant_id == current_user.tenant_id
            )
        )
        d['respondidas'] = q_result.scalar() or 0

        lista.append(ConteudoOut.model_validate(d))
    return lista