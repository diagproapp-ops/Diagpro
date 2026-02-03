# backend/app/auth.py

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


# Importações da nossa aplicação
from backend.app.database import get_db
from backend.app.db_models import User as DBUser
from backend.app.models import User as PydanticUser
from backend.app.roles import UserRole

# --- Modelo Pydantic para o Token ---
class Token(BaseModel):
    access_token: str
    token_type: str

# --- Configuração do JWT ---
SECRET_KEY = "sua-chave-secreta-supersegura"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Criptografia de Senha ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Esquema OAuth2 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- Funções ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais de autenticação inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar as credenciais",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- FUNÇÃO CORRIGIDA E ADICIONADA ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> PydanticUser:   # <-- Retorna Pydantic agora
    """
    Descodifica o token, obtém o username e busca o usuário no banco de dados.
    """
    username = decode_access_token(token)
    result = await db.execute(select(DBUser).filter(DBUser.username == username))
    user = result.scalars().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Converte ORM -> Pydantic para evitar lazy load
    return PydanticUser.from_orm(user)

def get_admin_user(current_user: DBUser = Depends(get_current_user)):
    """
    Dependência que verifica se o usuário atual é um admin ou admin geral.
    Se não for, levanta uma exceção HTTP 403 (Forbidden).
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.ADMIN_GERAL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Permissão de administrador necessária."
        )
    return current_user