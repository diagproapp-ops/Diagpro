from fastapi import (
    APIRouter, Depends, HTTPException, status, Path,
    UploadFile, File, Form
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from backend.app.database import get_db
from backend.app.db_models import User as DBUser
from backend.app.models import User as PydanticUser
from backend.app.auth import get_admin_user, get_password_hash, get_current_user
from backend.app.roles import UserRole
from pydantic import BaseModel, EmailStr

import os
from uuid import uuid4

router = APIRouter()

# ------------ MODELOS ------------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole
    tenant_id: int
    full_name: Optional[str] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    institution: Optional[str] = None
    birth_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    specialty: Optional[str] = None
    pix_key: Optional[str] = None
    banco: Optional[str] = None
    agencia: Optional[str] = None
    conta_corrente: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    client_id: Optional[int] = None
    full_name: Optional[str] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    institution: Optional[str] = None
    birth_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    specialty: Optional[str] = None
    pix_key: Optional[str] = None
    agencia: Optional[str] = None
    conta_corrente: Optional[str] = None

# ------------ ROTAS PÚBLICAS: CADASTRO EXTERNO ------------

@router.post("/register", status_code=201)
async def public_register(
    username: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    role: str = Form(...),               # <--- PATCH: agora recebe do formulário
    tenant_id: int = Form(...),
    full_name: Optional[str] = Form(None),
    cpf: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    institution: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    specialty: Optional[str] = Form(None),
    pix_key: Optional[str] = Form(None),
    banco: Optional[str] = Form(None),
    agencia: Optional[str] = Form(None),
    conta_corrente: Optional[str] = Form(None),
    accepted_confidentiality: bool = Form(...),
    accepted_data_leak: bool = Form(...),
    avatar_file: UploadFile = File(...),  # agora obrigatório!
    terms_acceptance: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # 1. Validação dos termos
    if not accepted_confidentiality or not accepted_data_leak:
        raise HTTPException(status_code=400, detail="É obrigatório aceitar ambos os termos.")

    # 2. Verifica duplicidade de username/email
    existing_user = await db.execute(select(DBUser).filter(DBUser.username == username))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username já registrado")

    existing_email = await db.execute(select(DBUser).filter(DBUser.email == email))
    if existing_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email já registrado")

    # 3. Salva avatar (obrigatório)
    UPLOAD_DIR = "avatars"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = avatar_file.filename.split('.')[-1]
    filename = f"{uuid4().hex}_{username}.{ext}"
    file_location = os.path.join(UPLOAD_DIR, filename)
    with open(file_location, "wb") as f:
        f.write(await avatar_file.read())
    avatar_url = file_location

    # 4. Cria usuário (sempre inativo, role do formulário)
    hashed_password = get_password_hash(password)
    new_user = DBUser(
        username=username,
        email=email,
        password_hash=hashed_password,
        role=role,        # <--- PATCH: salva o valor correto recebido!
        tenant_id=tenant_id,
        full_name=full_name,
        cpf=cpf,
        phone=phone,
        department=department,
        institution=institution,
        birth_date=birth_date,
        status="inativo",
        notes=notes,
        address=address,
        avatar_url=avatar_url,
        specialty=specialty,
        pix_key=pix_key,
        banco=banco,
        agencia=agencia,
        conta_corrente=conta_corrente,
        terms_acceptance=terms_acceptance,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"ok": True, "msg": "Cadastro enviado! Aguarde a aprovação do administrador."}

# ------------ ROTA DE PERFIL ------------

@router.get("/me", response_model=PydanticUser)
async def get_me(current_user: DBUser = Depends(get_current_user)):
    return current_user

# ------------ ROTAS DE ADMIN ------------

@router.get("/", response_model=List[PydanticUser])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    result = await db.execute(select(DBUser).where(DBUser.tenant_id == admin_user.tenant_id))
    users = result.scalars().all()
    return users

@router.post("/", response_model=PydanticUser, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    existing_user = await db.execute(select(DBUser).filter(DBUser.username == user_data.username))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username já registado")

    existing_email = await db.execute(select(DBUser).filter(DBUser.email == user_data.email))
    if existing_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email já registado")

    hashed_password = get_password_hash(user_data.password)

    role_value = user_data.role
    if role_value == "admin":
        role_value = "administrador"

    new_user = DBUser(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=role_value,
        tenant_id=user_data.tenant_id,
        full_name=user_data.full_name,
        cpf=user_data.cpf,
        phone=user_data.phone,
        department=user_data.department,
        institution=user_data.institution,
        birth_date=user_data.birth_date,
        status=user_data.status,
        notes=user_data.notes,
        address=user_data.address,
        avatar_url=user_data.avatar_url,
        specialty=user_data.specialty,
        pix_key=user_data.pix_key,
        agencia=user_data.agencia,
        conta_corrente=user_data.conta_corrente,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.patch("/{user_id}", response_model=PydanticUser)
async def update_user(
    user_id: int = Path(..., description="ID do usuário"),
    user_data: UserUpdate = None,
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    result = await db.execute(select(DBUser).filter(DBUser.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    update_data = user_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key == "password" and value is not None:
            user.password_hash = get_password_hash(value)
        elif key == "role" and value is not None:
            user.role = "administrador" if value == "admin" else value
        else:
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int = Path(..., description="ID do usuário"),
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    result = await db.execute(select(DBUser).filter(DBUser.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    await db.delete(user)
    await db.commit()
    return None