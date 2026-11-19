from fastapi import (
    APIRouter, Depends, HTTPException, status, Path,
    UploadFile, File, Form
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from typing import List, Optional

from backend.app import secure_files
from backend.app.field_crypto import blind_eq
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
import logging
from datetime import datetime

from backend.app import politica_senha

logger = logging.getLogger(__name__)

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
    existing_user = await db.execute(select(DBUser).filter(blind_eq(DBUser.username, username)))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username já registrado")

    existing_email = await db.execute(select(DBUser).filter(blind_eq(DBUser.email, email)))
    if existing_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email já registrado")

    # 3. Salva avatar (obrigatório, com validação de extensão e tamanho)
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
    _, ext = os.path.splitext((avatar_file.filename or "").lower())
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Formato de imagem inválido. Use JPG, PNG ou WEBP.")
    avatar_bytes = await avatar_file.read(5 * 1024 * 1024 + 1)
    if len(avatar_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem excede o limite de 5 MB.")
    try:
        # cifrado com a chave do tenant informado no cadastro; nunca em pasta pública
        avatar_url = secure_files.store_bytes(avatar_bytes, tenant_id, ext)
    except secure_files.SecureFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 4. Cria usuário (sempre inativo até aprovação do administrador); senha dentro da política
    _exigir_politica(password, username, email)
    hashed_password = get_password_hash(password)
    new_user = DBUser(
        username=username,
        email=email,
        password_hash=hashed_password,
        senha_alterada_em=datetime.utcnow(),
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

# ------------ ARQUIVOS ------------

def _avatar_seguro(value, tenant_id):
    """Aceita só referência cifrada válida do próprio cliente ou URL externa https; o resto é descartado."""
    if isinstance(value, str) and value.lower().startswith("https://") and len(value) < 2048:
        return value
    return secure_files.ref_from_client(value, tenant_id)


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


def _exigir_politica(senha: str, username: str, email: str) -> None:
    erros = politica_senha.problemas(senha, username, email)
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "A senha não atende à política.", "problemas": erros})


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
    query = select(DBUser).order_by(DBUser.tenant_id.nulls_first(), DBUser.id)
    # Admin geral na visão global vê os usuários de todos os clientes; com um cliente escolhido (ou sendo
    # usuário de cliente), só os daquele cliente — o RLS da sessão também garante isso.
    if not (_is_admin_geral(admin_user) and admin_user.tenant_id is None):
        query = query.where(DBUser.tenant_id == admin_user.tenant_id)
    users = (await db.execute(query)).scalars().all()
    return [_serialize_user(u) for u in users]

@router.post("/", response_model=PydanticUser, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    existing_user = await db.execute(select(DBUser).filter(blind_eq(DBUser.username, user_data.username)))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username já registado")

    existing_email = await db.execute(select(DBUser).filter(blind_eq(DBUser.email, user_data.email)))
    if existing_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email já registado")

    _verificar_role_permitida(admin_user, user_data.role)
    role_value = _normalizar_role(user_data.role)

    # Admin de cliente só cria usuários no próprio cliente, independente do que vier no corpo
    # Admin geral: na visão global escolhe o cliente no corpo; com um cliente em gestão, é sempre esse.
    if _is_admin_geral(admin_user) and admin_user.tenant_id is None:
        tenant_id = user_data.tenant_id
    else:
        tenant_id = admin_user.tenant_id
    if tenant_id is None and role_value != UserRole.ADMIN_GERAL.value:
        raise HTTPException(status_code=400, detail="Informe o cliente do usuário.")

    # senha definida pelo administrador é PROVISÓRIA: troca obrigatória no primeiro acesso
    _exigir_politica(user_data.password, user_data.username, user_data.email)
    hashed_password = get_password_hash(user_data.password)

    new_user = DBUser(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        senha_alterada_em=datetime.utcnow(),
        deve_trocar_senha=True,
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
        avatar_url=_avatar_seguro(user_data.avatar_url, tenant_id),
        specialty=user_data.specialty,
        pix_key=encrypt_pii(user_data.pix_key),
        agencia=encrypt_pii(user_data.agencia),
        conta_corrente=encrypt_pii(user_data.conta_corrente),
    )
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        # login e e-mail são únicos no sistema inteiro (índices cegos globais), mesmo entre clientes
        await db.rollback()
        raise HTTPException(status_code=400, detail="Username ou e-mail já registado.")
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
        if admin_user.tenant_id is not None and int(novo_tenant) != admin_user.tenant_id:
            raise HTTPException(status_code=400, detail="Para mover usuários entre clientes, use a visão global.")
        # ao trocar o tenant o ORM recifra todos os campos com a chave do novo cliente
        user.tenant_id = int(novo_tenant)

    for key, value in update_data.items():
        if key == "password":
            if value:
                # redefinida pelo administrador: provisória (troca no próximo login)
                _exigir_politica(value, user.username, user.email or "")
                politica_senha.aplicar_nova_senha(user, value, provisoria=True)
        elif key == "role":
            if value is not None:
                _verificar_role_permitida(admin_user, value)
                user.role = _normalizar_role(value)
        elif key == "avatar_url":
            user.avatar_url = _avatar_seguro(value, user.tenant_id)
        elif key in PII_FIELDS:
            setattr(user, key, encrypt_pii(value))
        else:
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return _serialize_user(user)

@router.post("/{user_id}/2fa/resetar", status_code=status.HTTP_204_NO_CONTENT)
async def resetar_2fa(
    user_id: int = Path(..., description="ID do usuário"),
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user),
):
    """
    Celular perdido: apaga o autenticador e os códigos de recuperação do usuário; no próximo login ele
    cadastra de novo. Ninguém reseta o próprio 2FA (uma sessão roubada não troca o autenticador).
    """
    user = await _buscar_usuario_gerenciavel(db, user_id, admin_user)
    if user.id == admin_user.id:
        raise HTTPException(status_code=403, detail="Peça a outro administrador para resetar o seu 2FA.")
    user.totp_secret = None
    user.totp_ativo = False
    user.totp_ultimo_passo = None
    user.codigos_recuperacao = None
    await db.commit()
    logger.warning("2FA resetado (usuário %s por administrador %s)", user.id, admin_user.id)


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