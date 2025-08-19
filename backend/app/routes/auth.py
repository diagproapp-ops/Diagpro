# backend/app/routes/auth.py

import requests
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Importações do nosso projeto
from backend.app.auth import verify_password, create_access_token, Token
from backend.app.database import get_db
from backend.app.db_models import User as DBUser

# --- CONFIGURAÇÃO DO RECAPTCHA ---
# Cole aqui a sua Chave Secreta (Secret Key) do Google reCAPTCHA
RECAPTCHA_SECRET_KEY = "6LcTjaorAAAAANA6QLQI3n4TQBK90Djc1Ucxr0kn" 

router = APIRouter()

async def get_user(db: AsyncSession, username: str):
    result = await db.execute(select(DBUser).filter(DBUser.username == username))
    return result.scalars().first()

def verify_recaptcha(token: str) -> bool:
    """Verifica o token do reCAPTCHA com os servidores do Google."""
    if not RECAPTCHA_SECRET_KEY or RECAPTCHA_SECRET_KEY == "SUA_CHAVE_SECRETA_VAI_AQUI":
        print("AVISO: Chave secreta do reCAPTCHA não configurada. Verificação ignorada.")
        return True

    data = {'secret': RECAPTCHA_SECRET_KEY, 'response': token}
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    result = r.json()
    return result.get('success', False)

@router.post("/login", response_model=Token)
async def login_for_access_token(
    # --- MUDANÇA PRINCIPAL AQUI ---
    # Em vez de OAuth2PasswordRequestForm, definimos cada campo manualmente.
    username: str = Form(...),
    password: str = Form(...),
    recaptcha_token: str = Form(...), # O nosso novo campo!
    db: AsyncSession = Depends(get_db)
):
    # 1. Primeiro, verificar se o utilizador é humano
    if not verify_recaptcha(recaptcha_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verificação do reCAPTCHA falhou."
        )

    # 2. Se for humano, o resto do código continua igual
    user = await get_user(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de utilizador ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}