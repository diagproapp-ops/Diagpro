# backend/app/auth.py

import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


# Importações da nossa aplicação
from backend.app.field_crypto import blind_eq
from backend.app.database import SessionLocal, PlatformSessionLocal, set_tenant_context
from backend.app.db_models import Tenant as DBTenant, User as DBUser
from backend.app.models import User as PydanticUser
from backend.app.roles import UserRole
from backend.app.utils_crypto import PII_FIELDS, safe_decrypt_pii

# --- Modelo Pydantic para o Token ---
class Token(BaseModel):
    access_token: str
    token_type: str

# --- Configuração do JWT ---
SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("A variável de ambiente JWT_SECRET_KEY não está definida.")
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

def decode_token_payload(token: str) -> dict:
    """Valida assinatura/expiração (algoritmo fixo HS256) e devolve o payload com `sub` obrigatório."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais de autenticação inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar as credenciais",
            headers={"WWW-Authenticate": "Bearer"},
        )

def decode_access_token(token: str) -> str:
    return decode_token_payload(token)["sub"]


_UNAUTHORIZED = dict(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Usuário não encontrado",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _load_user_from_token(payload: dict) -> DBUser | None:
    """
    Resolve o usuário do token com o menor privilégio possível:
    - token com tenant_id (assinado pelo servidor): role de runtime, sob RLS daquele tenant;
    - token sem tenant_id: role de plataforma, aceito SOMENTE para administrador geral.
    """
    username = payload["sub"]
    tenant_id = payload.get("tenant_id")
    if tenant_id is not None:
        try:
            tenant_id = int(tenant_id)
        except (TypeError, ValueError):
            return None
        async with SessionLocal() as db:
            async with db.begin():
                await set_tenant_context(db, tenant_id)
                result = await db.execute(
                    select(DBUser).where(blind_eq(DBUser.username, username), DBUser.tenant_id == tenant_id)
                )
                return result.scalars().first()
    async with PlatformSessionLocal() as db:
        result = await db.execute(
            select(DBUser).where(
                blind_eq(DBUser.username, username),
                DBUser.tenant_id.is_(None),
                DBUser.role == UserRole.ADMIN_GERAL.value,
            )
        )
        return result.scalars().first()


CLIENTE_EM_GESTAO_HEADER = "X-Tenant-Id"


async def _cliente_em_gestao(request: Request) -> int | None:
    """
    Cliente que o administrador geral escolheu gerenciar nesta requisição (cabeçalho X-Tenant-Id).
    Sem cabeçalho = visão global. Com cabeçalho, o cliente tem de existir; nunca há cliente padrão.
    """
    raw = (request.headers.get(CLIENTE_EM_GESTAO_HEADER) or "").strip()
    if not raw:
        return None
    try:
        tid = int(raw)
    except ValueError:
        tid = 0
    if tid > 0:
        async with PlatformSessionLocal() as db:
            if (await db.execute(select(DBTenant.id).where(DBTenant.id == tid))).first():
                return tid
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cliente selecionado inválido.")


async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> PydanticUser:
    """Valida o token e carrega o usuário (ver _load_user_from_token)."""
    payload = decode_token_payload(token)
    # 2FA obrigatório: só vale token emitido DEPOIS do segundo fator. Passes de 2FA (com "scope") e
    # tokens antigos (sem "mfa") não dão acesso a nada.
    if payload.get("scope") or payload.get("mfa") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão sem verificação em duas etapas. Faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sid = payload.get("sid")
    if sid is not None:
        from backend.app import sessoes  # import tardio: sessoes -> notificacoes -> configuracoes
        if not isinstance(sid, str) or not await sessoes.valida(sid):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Este acesso foi encerrado. Entre novamente.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    request.state.sid = sid
    user = await _load_user_from_token(payload)

    if user is None:
        raise HTTPException(**_UNAUTHORIZED)

    if not user.is_active or (user.status is not None and user.status.lower() == "inativo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo ou aguardando aprovação.",
        )

    # Converte ORM -> Pydantic e descriptografa PII sem mutar a sessão ORM
    # O administrador geral NÃO pertence a nenhum cliente (tenant_id nulo no banco). Ele só passa a
    # atuar num cliente quando escolhe explicitamente qual (X-Tenant-Id); aí a requisição inteira roda
    # sob o RLS daquele cliente (ver security.get_tenant_db). Nunca há cliente padrão.
    user_out = PydanticUser.from_orm(user)
    if user.role == UserRole.ADMIN_GERAL.value and user.tenant_id is None:
        user_out.tenant_id = await _cliente_em_gestao(request)
    for field in PII_FIELDS:
        val = getattr(user_out, field, None)
        if val:
            setattr(user_out, field, safe_decrypt_pii(val))
    return user_out

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