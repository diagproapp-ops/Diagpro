import logging as _diag_logging
_diag_print_logger = _diag_logging.getLogger(__name__)


def print(*args, **kwargs):  # noqa: A001
    """Prints de depuração viram log DEBUG: não expõem conteúdo de prova em produção (DIAGPRO_LOG_LEVEL)."""
    _diag_print_logger.debug(" ".join(str(a) for a in args))


import os
import requests
from fastapi import APIRouter, Depends, HTTPException, status, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.field_crypto import blind_eq
from backend.app.auth import get_current_user, verify_password
from backend.app.roles import UserRole
from backend.app import dois_fatores as df
from backend.app import politica_senha
from backend.app import configuracoes
from backend.app.auth import oauth2_scheme, decode_token_payload
from backend.app.database import get_auth_db
from backend.app.db_models import User as DBUser
from backend.app.rate_limit import checar_bloqueio_por_falhas, rate_limit, registrar_falha

logger = _diag_logging.getLogger(__name__)

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")

router = APIRouter()

async def get_user(db: AsyncSession, username: str):
    result = await db.execute(select(DBUser).filter(blind_eq(DBUser.username, username)))
    return result.scalars().first()

# Só para testes automatizados/desenvolvimento: NUNCA em produção.
RECAPTCHA_DESATIVADO = os.getenv("DIAGPRO_RECAPTCHA_DESATIVADO", "") == "1"
if RECAPTCHA_DESATIVADO:
    _diag_logging.getLogger(__name__).warning("reCAPTCHA DESATIVADO por DIAGPRO_RECAPTCHA_DESATIVADO=1 (apenas para testes).")


def verify_recaptcha(token: str) -> bool:
    """Falha fechada: sem chave, sem resposta do Google ou com erro, o login é recusado."""
    if RECAPTCHA_DESATIVADO:
        return True
    if not RECAPTCHA_SECRET_KEY or RECAPTCHA_SECRET_KEY == "SUA_CHAVE_SECRETA_VAI_AQUI":
        logger.error("RECAPTCHA_SECRET_KEY não configurada: login recusado.")
        return False
    try:
        r = requests.post('https://www.google.com/recaptcha/api/siteverify',
                          data={'secret': RECAPTCHA_SECRET_KEY, 'response': token}, timeout=5)
        return bool(r.json().get('success', False))
    except Exception:  # noqa: BLE001 - sem resposta do Google = não verificado
        logger.error("Verificação do reCAPTCHA indisponível: login recusado.")
        return False

@router.post("/login", dependencies=[Depends(rate_limit(10, 60, "login"))])
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
    
    # Senha correta NÃO libera acesso: só um passe de 5 min para o segundo fator (2FA obrigatório).
    # troca obrigatória (provisória, vencida ou fora da política): pedida DEPOIS do 2FA, antes do acesso
    cfg = (await configuracoes.ler_plataforma())["seguranca"]
    extra = {"trocar": True} if politica_senha.precisa_trocar(user, password, cfg) else {}
    if user.totp_ativo:
        return {"etapa": "2fa", "token_2fa": df.criar_passe(user, df.SCOPE_VERIFICAR, **extra)}
    return {"etapa": "cadastro_2fa", "token_2fa": df.criar_passe(user, df.SCOPE_CADASTRO, **extra)}


# ---------------------------------------------------------------- 2FA ---
_MAX_FALHAS_2FA, _JANELA_FALHAS_2FA = 5, 600


class PasseBody(BaseModel):
    token_2fa: str


class CodigoBody(PasseBody):
    codigo: str


async def _usuario_do_passe(db: AsyncSession, payload: dict) -> DBUser:
    query = select(DBUser).where(blind_eq(DBUser.username, payload["sub"]))
    tid = payload.get("tenant_id")
    query = query.where(DBUser.tenant_id == int(tid)) if tid is not None else query.where(DBUser.tenant_id.is_(None))
    user = (await db.execute(query)).scalars().first()
    if not user or not user.is_active or (user.status or "").lower() == "inativo":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado ou inativo.")
    return user


def _role(user) -> str:
    r = getattr(user, "role", "")
    return r.value if isinstance(r, UserRole) else str(r)


async def _resposta_acesso(user, extra: dict | None = None, payload: dict | None = None) -> dict:
    if payload and payload.get("trocar"):
        # 2FA ok, mas a senha precisa ser trocada antes de entrar
        cfg = (await configuracoes.ler_plataforma())["seguranca"]
        resposta = {"etapa": "trocar_senha", "token_2fa": df.criar_passe(user, df.SCOPE_TROCA_SENHA),
                    "regras": politica_senha.regras(cfg)}
        resposta.update(extra or {})
        return resposta
    minutos = await configuracoes.inatividade_do_usuario(user.tenant_id)
    resposta = {"access_token": df.criar_token_acesso(user, minutos=minutos), "token_type": "bearer",
                "role": user.role, "inatividade_minutos": minutos}
    if user.tenant_id is not None:
        resposta["tenant_id"] = user.tenant_id
    resposta.update(extra or {})
    return resposta


@router.post("/2fa/cadastro/iniciar", dependencies=[Depends(rate_limit(10, 60, "2fa-cadastro"))])
async def iniciar_cadastro_2fa(body: PasseBody, db: AsyncSession = Depends(get_auth_db)):
    """Gera o segredo (ainda inativo) e o QR Code para o aplicativo autenticador."""
    user = await _usuario_do_passe(db, df.ler_passe(body.token_2fa, (df.SCOPE_CADASTRO,)))
    if user.totp_ativo:
        raise HTTPException(status_code=409, detail="A verificação em duas etapas já está ativa. Faça login de novo.")
    segredo = df.novo_segredo()
    user.totp_secret = segredo
    user.totp_ultimo_passo = None
    await db.commit()
    uri = df.uri_autenticador(segredo, user.email or user.username)
    return {"qr_code": df.qr_png_data_uri(uri), "segredo": segredo, "emissor": df.EMISSOR}


@router.post("/2fa/cadastro/confirmar")
async def confirmar_cadastro_2fa(body: CodigoBody, db: AsyncSession = Depends(get_auth_db)):
    """Primeiro código certo ativa o 2FA, devolve os códigos de recuperação (uma única vez) e o acesso."""
    payload = df.ler_passe(body.token_2fa, (df.SCOPE_CADASTRO,))
    chave = f"2fa:{payload['sub']}:{payload.get('tenant_id')}"
    checar_bloqueio_por_falhas(chave, _MAX_FALHAS_2FA, _JANELA_FALHAS_2FA)
    user = await _usuario_do_passe(db, payload)
    if user.totp_ativo:
        raise HTTPException(status_code=409, detail="A verificação em duas etapas já está ativa. Faça login de novo.")
    passo = df.conferir_totp(user.totp_secret, body.codigo, None)
    if passo is None:
        registrar_falha(chave)
        raise HTTPException(status_code=400, detail="Código inválido. Confira o horário do celular e tente de novo.")
    codigos, hashes = df.gerar_codigos_recuperacao()
    user.totp_ativo = True
    user.totp_ultimo_passo = passo
    user.codigos_recuperacao = hashes
    await db.commit()
    logger.warning("2FA ativado (usuário %s)", user.id)
    return await _resposta_acesso(user, {"codigos_recuperacao": codigos}, payload)


@router.post("/2fa/verificar")
async def verificar_2fa(body: CodigoBody, db: AsyncSession = Depends(get_auth_db)):
    """Código do aplicativo (6 dígitos) ou um código de recuperação (uso único)."""
    payload = df.ler_passe(body.token_2fa, (df.SCOPE_VERIFICAR,))
    chave = f"2fa:{payload['sub']}:{payload.get('tenant_id')}"
    checar_bloqueio_por_falhas(chave, _MAX_FALHAS_2FA, _JANELA_FALHAS_2FA)
    user = await _usuario_do_passe(db, payload)
    if not user.totp_ativo:
        raise HTTPException(status_code=409, detail="Verificação em duas etapas não cadastrada. Faça login de novo.")
    passo = df.conferir_totp(user.totp_secret, body.codigo, user.totp_ultimo_passo)
    extra = {}
    if passo is not None:
        user.totp_ultimo_passo = passo
    else:
        restantes = df.consumir_codigo_recuperacao(user.codigos_recuperacao, body.codigo)
        if restantes is None:
            registrar_falha(chave)
            raise HTTPException(status_code=400, detail="Código inválido.")
        user.codigos_recuperacao = restantes
        extra["codigos_recuperacao_restantes"] = len(restantes)
        logger.warning("Login com código de recuperação (usuário %s, restam %d)", user.id, len(restantes))
    await db.commit()
    return await _resposta_acesso(user, extra, payload)


@router.post("/2fa/codigos-recuperacao")
async def novos_codigos_recuperacao(
    body: dict,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Gera novos códigos de recuperação (invalida os antigos). Exige um código atual do aplicativo."""
    # admin geral gerenciando um cliente continua sem cliente no banco
    tenant = None if _role(current_user) == UserRole.ADMIN_GERAL.value else current_user.tenant_id
    query = select(DBUser).where(blind_eq(DBUser.username, current_user.username))
    query = query.where(DBUser.tenant_id == tenant) if tenant is not None else query.where(DBUser.tenant_id.is_(None))
    user = (await db.execute(query)).scalars().first()
    if not user or not user.totp_ativo:
        raise HTTPException(status_code=409, detail="Verificação em duas etapas não está ativa.")
    chave = f"2fa:{user.username}:{user.tenant_id}"
    checar_bloqueio_por_falhas(chave, _MAX_FALHAS_2FA, _JANELA_FALHAS_2FA)
    passo = df.conferir_totp(user.totp_secret, body.get("codigo"), user.totp_ultimo_passo)
    if passo is None:
        registrar_falha(chave)
        raise HTTPException(status_code=400, detail="Código inválido.")
    codigos, hashes = df.gerar_codigos_recuperacao()
    user.totp_ultimo_passo = passo
    user.codigos_recuperacao = hashes
    await db.commit()
    return {"codigos_recuperacao": codigos}


# ------------------------------------------------------- senha e sessão ---
class TrocaSenhaBody(PasseBody):
    nova_senha: str


class MinhaSenhaBody(BaseModel):
    senha_atual: str
    nova_senha: str
    codigo: str


async def _validar_nova_senha(user, nova: str) -> dict:
    cfg = (await configuracoes.ler_plataforma())["seguranca"]
    erros = politica_senha.problemas(nova, user.username, user.email or "", cfg)
    if politica_senha.repetida(nova, user.password_hash, user.senha_historico):
        erros.append(f"A nova senha não pode repetir nenhuma das últimas {cfg['senha_historico']} senhas.")
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "A senha não atende à política.", "problemas": erros})
    return cfg


@router.get("/senha/regras")
async def regras_da_senha():
    cfg = (await configuracoes.ler_plataforma())["seguranca"]
    return {"regras": politica_senha.regras(cfg), "tamanho_minimo": cfg["senha_tamanho_minimo"],
            "tipos_minimos": cfg["senha_tipos_minimos"]}


@router.post("/senha/trocar", dependencies=[Depends(rate_limit(10, 60, "troca-senha"))])
async def trocar_senha_obrigatoria(body: TrocaSenhaBody, db: AsyncSession = Depends(get_auth_db)):
    """Troca obrigatória logo depois do 2FA (senha provisória, vencida ou fora da política)."""
    user = await _usuario_do_passe(db, df.ler_passe(body.token_2fa, (df.SCOPE_TROCA_SENHA,)))
    cfg = await _validar_nova_senha(user, body.nova_senha)
    politica_senha.aplicar_nova_senha(user, body.nova_senha, cfg=cfg)
    await db.commit()
    logger.warning("Senha trocada no login (usuário %s)", user.id)
    return await _resposta_acesso(user)


@router.post("/senha/minha", dependencies=[Depends(rate_limit(10, 60, "minha-senha"))])
async def trocar_minha_senha(
    body: MinhaSenhaBody,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """O próprio usuário troca a senha: exige a senha atual E um código atual do autenticador."""
    tenant = None if _role(current_user) == UserRole.ADMIN_GERAL.value else current_user.tenant_id
    query = select(DBUser).where(blind_eq(DBUser.username, current_user.username))
    query = query.where(DBUser.tenant_id == tenant) if tenant is not None else query.where(DBUser.tenant_id.is_(None))
    user = (await db.execute(query)).scalars().first()
    chave = f"2fa:{user.username}:{user.tenant_id}"
    checar_bloqueio_por_falhas(chave, _MAX_FALHAS_2FA, _JANELA_FALHAS_2FA)
    passo = df.conferir_totp(user.totp_secret, body.codigo, user.totp_ultimo_passo)
    if not verify_password(body.senha_atual, user.password_hash) or passo is None:
        registrar_falha(chave)
        raise HTTPException(status_code=400, detail="Senha atual ou código do autenticador incorretos.")
    cfg = await _validar_nova_senha(user, body.nova_senha)
    user.totp_ultimo_passo = passo
    politica_senha.aplicar_nova_senha(user, body.nova_senha, cfg=cfg)
    await db.commit()
    return {"ok": True}


@router.post("/renovar")
async def renovar_sessao(token: str = Depends(oauth2_scheme), current_user=Depends(get_current_user)):
    """
    Renova o token enquanto a pessoa está usando o sistema (a tela chama só se houve atividade).
    Sem uso, o token vence em 30 min e a sessão cai. Limite absoluto de 12 h desde o login.
    """
    import time as _t
    payload = decode_token_payload(token)
    auth_time = payload.get("auth_time")
    maximo = (await configuracoes.ler_plataforma())["seguranca"]["sessao_maxima_horas"] * 3600
    if not auth_time or _t.time() - int(auth_time) > maximo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão encerrada. Entre novamente.",
                            headers={"WWW-Authenticate": "Bearer"})
    dados = {"sub": payload["sub"], "role": payload.get("role"), "mfa": True, "auth_time": int(auth_time)}
    if payload.get("tenant_id") is not None:
        dados["tenant_id"] = payload["tenant_id"]
    from backend.app.auth import create_access_token
    from datetime import timedelta as _td
    minutos = await configuracoes.inatividade_do_usuario(payload.get("tenant_id"))
    return {"access_token": create_access_token(dados, expires_delta=_td(minutes=minutos)), "token_type": "bearer",
            "inatividade_minutos": minutos}
