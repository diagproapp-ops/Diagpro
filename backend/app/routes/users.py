from fastapi import (
    APIRouter, Depends, HTTPException, status, Path,
    UploadFile, File, Form
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from backend.app.database import get_auth_db
from backend.app.security import get_tenant_db
from backend.app.rate_limit import rate_limit
from backend.app.utils_crypto import PII_FIELDS, encrypt_pii, safe_decrypt_pii
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

@router.post("/register", status_code=201, dependencies=[Depends(rate_limit(5, 60, "register"))])
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
    db: AsyncSession = Depends(get_auth_db)
):
    # 1. Validação dos termos e do perfil solicitado (impede escalação de privilégio)
    if not accepted_confidentiality or not accepted_data_leak:
        raise HTTPException(status_code=400, detail="É obrigatório aceitar ambos os termos.")

    allowed_public_roles = {
        UserRole.PROFESSOR.value,
        UserRole.REVISOR.value,
        UserRole.DIAGRAMADOR.value,
    }
    if role not in allowed_public_roles:
        raise HTTPException(
            status_code=403,
            detail="Perfil não permitido para cadastro público."
        )

    # 2. Verifica duplicidade de username/email
    existing_user = await db.execute(select(DBUser).filter(DBUser.username == username))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username já registrado")

    existing_email = await db.execute(select(DBUser).filter(DBUser.email == email))
    if existing_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email já registrado")

    # 3. Salva avatar (obrigatório, com validação de extensão e tamanho)
    UPLOAD_DIR = "avatars"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
    _, ext = os.path.splitext((avatar_file.filename or "").lower())
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Formato de imagem inválido. Use JPG, PNG ou WEBP.")
    avatar_bytes = await avatar_file.read()
    if len(avatar_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem excede o limite de 5 MB.")
    filename = f"{uuid4().hex}{ext}"
    file_location = os.path.join(UPLOAD_DIR, filename)
    with open(file_location, "wb") as f:
        f.write(avatar_bytes)
    avatar_url = file_location

    # 4. Cria usuário (sempre inativo até aprovação do administrador)
    hashed_password = get_password_hash(password)
    new_user = DBUser(
        username=username,
        email=email,
        password_hash=hashed_password,
        role=role,
        tenant_id=tenant_id,
        full_name=full_name,
        cpf=cpf,
        phone=phone,
        department=department,
        institution=institution,
        birth_date=birth_date,
        status="inativo",
        is_active=False,
        notes=notes,
        address=address,
        avatar_url=avatar_url,
        specialty=specialty,
        pix_key=encrypt_pii(pix_key),
        banco=encrypt_pii(banco),
        agencia=encrypt_pii(agencia),
        conta_corrente=encrypt_pii(conta_corrente),
        terms_acceptance=terms_acceptance,
    )
    new_user.cpf = encrypt_pii(cpf)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"ok": True, "msg": "Cadastro enviado! Aguarde a aprovação do administrador."}

# ------------ REGRAS DE PERMISSÃO ------------

def _is_admin_geral(user) -> bool:
    return getattr(user, "role", None) == UserRole.ADMIN_GERAL


def _normalizar_role(role) -> str:
    valor = role.value if isinstance(role, UserRole) else role
    return "administrador" if valor == "admin" else valor


def _verificar_role_permitida(admin_user, role) -> None:
    """Somente o admin geral pode criar/promover outro admin geral."""
    if _normalizar_role(role) == UserRole.ADMIN_GERAL.value and not _is_admin_geral(admin_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas o administrador geral pode atribuir esse perfil.",
        )


async def _buscar_usuario_gerenciavel(db: AsyncSession, user_id: int, admin_user) -> DBUser:
    """
    Retorna o usuário-alvo se o admin puder gerenciá-lo:
    - admin geral gerencia qualquer usuário;
    - admin de cliente só gerencia usuários do próprio cliente e nunca um admin geral.
    Responde 404 para não revelar usuários de outros clientes.
    """
    query = select(DBUser).filter(DBUser.id == user_id)
    if not _is_admin_geral(admin_user):
        query = query.where(DBUser.tenant_id == admin_user.tenant_id)
    user = (await db.execute(query)).scalars().first()
    if not user or (user.role == UserRole.ADMIN_GERAL.value and not _is_admin_geral(admin_user)):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user

# ------------ ROTA DE PERFIL ------------

@router.get("/me", response_model=PydanticUser)
async def get_me(current_user: DBUser = Depends(get_current_user)):
    return current_user

# ------------ ROTAS DE ADMIN ------------

def _serialize_user(user_orm: DBUser) -> PydanticUser:
    user_out = PydanticUser.from_orm(user_orm)
    for field in PII_FIELDS:
        val = getattr(user_out, field, None)
        if val:
            setattr(user_out, field, safe_decrypt_pii(val))
    return user_out


@router.get("/", response_model=List[PydanticUser])
async def list_users(
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    result = await db.execute(select(DBUser).where(DBUser.tenant_id == admin_user.tenant_id))
    users = result.scalars().all()
    return [_serialize_user(u) for u in users]

@router.post("/", response_model=PydanticUser, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    existing_user = await db.execute(select(DBUser).filter(DBUser.username == user_data.username))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username já registado")

    existing_email = await db.execute(select(DBUser).filter(DBUser.email == user_data.email))
    if existing_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email já registado")

    _verificar_role_permitida(admin_user, user_data.role)
    role_value = _normalizar_role(user_data.role)

    # Admin de cliente só cria usuários no próprio cliente, independente do que vier no corpo
    tenant_id = user_data.tenant_id if _is_admin_geral(admin_user) else admin_user.tenant_id

    hashed_password = get_password_hash(user_data.password)

    new_user = DBUser(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=role_value,
        tenant_id=tenant_id,
        full_name=user_data.full_name,
        cpf=encrypt_pii(user_data.cpf),
        phone=user_data.phone,
        department=user_data.department,
        institution=user_data.institution,
        birth_date=user_data.birth_date,
        status=user_data.status,
        notes=user_data.notes,
        address=user_data.address,
        avatar_url=user_data.avatar_url,
        specialty=user_data.specialty,
        pix_key=encrypt_pii(user_data.pix_key),
        agencia=encrypt_pii(user_data.agencia),
        conta_corrente=encrypt_pii(user_data.conta_corrente),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return _serialize_user(new_user)

@router.patch("/{user_id}", response_model=PydanticUser)
async def update_user(
    user_id: int = Path(..., description="ID do usuário"),
    user_data: UserUpdate = None,
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    user = await _buscar_usuario_gerenciavel(db, user_id, admin_user)
    if user_data is None:
        raise HTTPException(status_code=422, detail="Nenhum dado para atualizar.")

    update_data = user_data.dict(exclude_unset=True)

    # client_id = troca de cliente (tenant): permitido apenas ao admin geral
    novo_tenant = update_data.pop("client_id", None)
    if novo_tenant is not None:
        if not _is_admin_geral(admin_user):
            raise HTTPException(status_code=403, detail="Apenas o administrador geral pode mover usuários entre clientes.")
        user.tenant_id = novo_tenant

    for key, value in update_data.items():
        if key == "password":
            if value:
                user.password_hash = get_password_hash(value)
        elif key == "role":
            if value is not None:
                _verificar_role_permitida(admin_user, value)
                user.role = _normalizar_role(value)
        elif key in PII_FIELDS:
            setattr(user, key, encrypt_pii(value))
        else:
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return _serialize_user(user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int = Path(..., description="ID do usuário"),
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    user = await _buscar_usuario_gerenciavel(db, user_id, admin_user)
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir o próprio usuário.")
    await db.delete(user)
    await db.commit()
    return None