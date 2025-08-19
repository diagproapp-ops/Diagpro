from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

# Importações do nosso projeto
from backend.app.database import get_db
from backend.app.db_models import User as DBUser
from backend.app.models import User as PydanticUser
from backend.app.auth import get_admin_user, get_password_hash, get_current_user  # PATCH: adicione get_current_user
from backend.app.roles import UserRole

router = APIRouter()

# --- Modelo Pydantic para criar um novo usuário ---
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole # Usa o nosso Enum para garantir que o papel é válido

# --- NOVA ROTA: /users/me ---
@router.get("/me", response_model=PydanticUser)
async def get_me(current_user: DBUser = Depends(get_current_user)):
    """
    Retorna informações do usuário autenticado.
    """
    return current_user

# --- ROTAS PROTEGIDAS PARA ADMINS ---

@router.get("/", response_model=List[PydanticUser])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(get_admin_user) # <-- Rota protegida para admins
):
    """
    Lista todos os usuários. Apenas acessível por administradores.
    """
    result = await db.execute(select(DBUser))
    users = result.scalars().all()
    return users

@router.post("/", response_model=PydanticUser, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    """
    Cria um novo usuário. Apenas acessível por administradores.
    """
    # Verifica se o username ou email já existem
    existing_user = await db.execute(select(DBUser).filter(DBUser.username == user_data.username))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username já registado")

    existing_email = await db.execute(select(DBUser).filter(DBUser.email == user_data.email))
    if existing_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email já registado")

    hashed_password = get_password_hash(user_data.password)
    new_user = DBUser(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=user_data.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user