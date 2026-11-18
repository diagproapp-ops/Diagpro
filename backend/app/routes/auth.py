import os
import requests
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.auth import verify_password, create_access_token, Token
from backend.app.database import get_auth_db
from backend.app.db_models import User as DBUser
from backend.app.rate_limit import rate_limit

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")

router = APIRouter()

async def get_user(db: AsyncSession, username: str):
    result = await db.execute(select(DBUser).filter(DBUser.username == username))
    return result.scalars().first()

def verify_recaptcha(token: str) -> bool:
    if not RECAPTCHA_SECRET_KEY or RECAPTCHA_SECRET_KEY == "SUA_CHAVE_SECRETA_VAI_AQUI":
        print("AVISO: Chave secreta do reCAPTCHA não configurada. Verificação ignorada.")
        return True

    data = {'secret': RECAPTCHA_SECRET_KEY, 'response': token}
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    result = r.json()
    return result.get('success', False)

@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit(10, 60, "login"))])
async def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    recaptcha_token: str = Form(...),
    db: AsyncSession = Depends(get_auth_db)
):
    if not verify_recaptcha(recaptcha_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verificação do reCAPTCHA falhou."
        )

    user = await get_user(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de utilizador ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or (user.status is not None and user.status.lower() == "inativo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo ou aguardando aprovação do administrador.",
        )
    
    token_data = {
        "sub": user.username,
        "role": user.role,
    }
    # Adiciona tenant_id somente se existir (admin geral não tem)
    if hasattr(user, "tenant_id") and user.tenant_id is not None:
        token_data["tenant_id"] = user.tenant_id

    access_token = create_access_token(data=token_data)

    response = {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
    }
    if hasattr(user, "tenant_id") and user.tenant_id is not None:
        response["tenant_id"] = user.tenant_id

    return response