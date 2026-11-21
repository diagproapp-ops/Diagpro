from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from typing import List
import uuid
from datetime import datetime

from backend.app import limites_plano
from backend.app.security import conferir_senha_evento, get_tenant_db, is_admin_geral, require_roles
from backend.app.roles import UserRole
from backend.app.db_models import Evento as DBEvento, Tenant as DBTenant
from backend.app.models import (
    EventoCreate as PydanticEventoCreate,
    EventoUpdate as PydanticEventoUpdate,
    EventoOut as PydanticEventoOut,
    CargoOut,
)
from backend.app.auth import get_current_user, get_password_hash, verify_password

# ==== IMPORTA AQUI SUA CRIPTOGRAFIA REVERSÍVEL ====
from backend.app.utils_crypto import encrypt_text

router = APIRouter()

# Função para gerar identificador legível e sequencial para o evento
async def gerar_identificador_evento(nome_evento: str, db: AsyncSession):
    letras = ''.join([c for c in nome_evento if c.isalpha()]).upper()[:2]
    if len(letras) < 2:
        letras = letras.ljust(2, 'X')
    prefix = f"{letras}"

    result = await db.execute(
        select(DBEvento.identificador_evento)
        .filter(DBEvento.identificador_evento.like(f"{prefix}%"))
    )
    max_num = 0
    for ident in result.scalars().all():
        if ident and ident.startswith(prefix):
            try:
                num = int(ident[len(prefix):])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
    numero = str(max_num + 1).zfill(3)
    return f"{letras}{numero}"

@router.get("/", response_model=List[PydanticEventoOut])
async def list_eventos(
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    stmt = (
        select(DBEvento)
        .options(selectinload(DBEvento.cargos))
        .filter(DBEvento.is_deleted == False)
    )
    if not is_admin_geral(current_user):
        stmt = stmt.filter(DBEvento.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    eventos = result.scalars().all()

    eventos_out = []
    for evento in eventos:
        cargos_out = [CargoOut.from_orm(cargo) for cargo in getattr(evento, "cargos", [])]
        eventos_out.append(
            PydanticEventoOut(
                id_evento=evento.id_evento,
                tenant_id=evento.tenant_id,
                nome_evento=evento.nome_evento,
                data_prova=evento.data_prova,
                status=evento.status,
                numero_edital=evento.numero_edital,
                local_prova=evento.local_prova,
                observacoes=evento.observacoes,
                cargos=cargos_out,
                qtd_cargos=getattr(evento, "qtd_cargos", len(cargos_out)),
                identificador_evento=getattr(evento, "identificador_evento", None),
            )
        )
    return eventos_out

# NOVO: detalhes protegidos por senha
@router.get("/{event_id}/detalhes", response_model=PydanticEventoOut)
async def get_evento_details(
    event_id: str,
    senha: str = Query(..., description="Senha do evento"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    stmt = (
        select(DBEvento)
        .options(selectinload(DBEvento.cargos))
        .filter(
            DBEvento.id_evento == event_id,
            DBEvento.is_deleted == False
        )
    )
    if not is_admin_geral(current_user):
        stmt = stmt.filter(DBEvento.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    evento = result.scalars().first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    # 403 (não 401): senha errada do evento não é sessão expirada e não deve deslogar o usuário
    if evento.senha_evento_cripto:
        conferir_senha_evento(evento, senha, current_user)  # mesma regra da exportação, com bloqueio por falhas
    elif not verify_password(senha, evento.senha_evento):
        raise HTTPException(status_code=403, detail="Senha do evento inválida.")
    cargos_out = [CargoOut.from_orm(cargo) for cargo in getattr(evento, "cargos", [])]
    return PydanticEventoOut(
        id_evento=evento.id_evento,
        tenant_id=evento.tenant_id,
        nome_evento=evento.nome_evento,
        data_prova=evento.data_prova,
        status=evento.status,
        numero_edital=evento.numero_edital,
        local_prova=evento.local_prova,
        observacoes=evento.observacoes,
        cargos=cargos_out,
        qtd_cargos=getattr(evento, "qtd_cargos", len(cargos_out)),
        identificador_evento=getattr(evento, "identificador_evento", None),
    )

# NOVO: dados para editar/cadastrar evento (sem senha)
@router.get("/{event_id}", response_model=PydanticEventoOut)
async def get_evento_for_edit(
    event_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    stmt = (
        select(DBEvento)
        .options(selectinload(DBEvento.cargos))
        .filter(
            DBEvento.id_evento == event_id,
            DBEvento.is_deleted == False
        )
    )
    if not is_admin_geral(current_user):
        stmt = stmt.filter(DBEvento.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    evento = result.scalars().first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    cargos_out = [CargoOut.from_orm(cargo) for cargo in getattr(evento, "cargos", [])]
    return PydanticEventoOut(
        id_evento=evento.id_evento,
        tenant_id=evento.tenant_id,
        nome_evento=evento.nome_evento,
        data_prova=evento.data_prova,
        status=evento.status,
        numero_edital=evento.numero_edital,
        local_prova=evento.local_prova,
        observacoes=evento.observacoes,
        cargos=cargos_out,
        qtd_cargos=getattr(evento, "qtd_cargos", len(cargos_out)),
        identificador_evento=getattr(evento, "identificador_evento", None),
    )

@router.post("/", response_model=PydanticEventoOut, dependencies=[Depends(limites_plano.dependencia("eventos"))])
async def create_evento(
    evento_data: PydanticEventoCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))
):
    evento_dict = evento_data.dict()
    senha_pura = evento_dict["senha_evento"]
    evento_dict["senha_evento"] = get_password_hash(senha_pura)
    evento_dict["senha_evento_cripto"] = encrypt_text(senha_pura)  # <-- NOVO CAMPO CRIPTOGRAFADO REVERSÍVEL
    if is_admin_geral(current_user) and current_user.tenant_id is None:
        # Admin geral na visão global: precisa dizer para qual cliente cria o evento, e o cliente tem de
        # existir. Nunca há cliente "padrão". (Com um cliente em gestão, cai no ramo de baixo.)
        alvo = evento_dict.get("tenant_id")
        existe = alvo is not None and (await db.execute(select(DBTenant.id).where(DBTenant.id == alvo))).first()
        if not existe:
            raise HTTPException(status_code=400, detail="Informe um cliente (tenant_id) válido para criar o evento.")
        evento_dict["tenant_id"] = int(alvo)
    else:
        # usuário de cliente (ou admin geral gerenciando um cliente): sempre esse cliente, ignorando o corpo
        evento_dict["tenant_id"] = current_user.tenant_id
    evento_dict["id_evento"] = str(uuid.uuid4())
    evento_dict["qtd_cargos"] = int(evento_dict.get("qtd_cargos", 1))
    evento_dict["identificador_evento"] = await gerar_identificador_evento(evento_dict["nome_evento"], db)
    evento_dict["is_deleted"] = False  # Sempre cria como ativo
    evento_dict["deleted_at"] = None
    novo_evento = DBEvento(**evento_dict)
    db.add(novo_evento)
    await db.commit()
    await db.refresh(novo_evento)
    return PydanticEventoOut(
        id_evento=novo_evento.id_evento,
        tenant_id=novo_evento.tenant_id,
        nome_evento=novo_evento.nome_evento,
        data_prova=novo_evento.data_prova,
        status=novo_evento.status,
        numero_edital=novo_evento.numero_edital,
        local_prova=novo_evento.local_prova,
        observacoes=novo_evento.observacoes,
        cargos=[],
        qtd_cargos=novo_evento.qtd_cargos,
        identificador_evento=novo_evento.identificador_evento,
    )

@router.put("/{event_id}", response_model=PydanticEventoOut)
async def update_evento(
    event_id: str,
    evento_data: PydanticEventoUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))
):
    stmt = (
        select(DBEvento)
        .options(selectinload(DBEvento.cargos))
        .filter(
            DBEvento.id_evento == event_id,
            DBEvento.is_deleted == False
        )
    )
    if not is_admin_geral(current_user):
        stmt = stmt.filter(DBEvento.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    evento = result.scalars().first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    update_data = evento_data.dict(exclude_unset=True)
    if "senha_evento" in update_data and update_data["senha_evento"]:
        senha_pura = update_data["senha_evento"]
        update_data["senha_evento"] = get_password_hash(senha_pura)
        update_data["senha_evento_cripto"] = encrypt_text(senha_pura)  # <-- NOVO CAMPO CRIPTOGRAFADO REVERSÍVEL
    update_data.pop("tenant_id", None)
    for key, value in update_data.items():
        setattr(evento, key, value)
    await db.commit()
    await db.refresh(evento)
    cargos_out = [CargoOut.from_orm(cargo) for cargo in getattr(evento, "cargos", [])]
    return PydanticEventoOut(
        id_evento=evento.id_evento,
        tenant_id=evento.tenant_id,
        nome_evento=evento.nome_evento,
        data_prova=evento.data_prova,
        status=evento.status,
        numero_edital=evento.numero_edital,
        local_prova=evento.local_prova,
        observacoes=evento.observacoes,
        cargos=cargos_out,
        qtd_cargos=getattr(evento, "qtd_cargos", len(cargos_out)),
        identificador_evento=getattr(evento, "identificador_evento", None),
    )

@router.delete("/{event_id}", status_code=204)
async def delete_evento(
    event_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL))
):
    stmt = select(DBEvento).filter(
        DBEvento.id_evento == event_id,
        DBEvento.is_deleted == False
    )
    if not is_admin_geral(current_user):
        stmt = stmt.filter(DBEvento.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    evento = result.scalars().first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    evento.is_deleted = True
    evento.deleted_at = datetime.utcnow()
    db.add(evento)
    await db.commit()
    return None  # status_code=204 já retorna resposta vazia