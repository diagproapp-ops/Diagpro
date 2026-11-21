# backend/app/dois_fatores.py
"""
2FA (TOTP, RFC 6238) obrigatório para todos os usuários.

- O segredo do autenticador e os códigos de recuperação ficam cifrados no banco (field_crypto).
- Códigos de recuperação: guardados só como HMAC (com chave derivada da chave mestra); cada um vale uma vez.
- Anti-reuso: o mesmo código de 6 dígitos não é aceito duas vezes (totp_ultimo_passo).
- O login com senha correta devolve só um passe de 2FA (JWT de 5 min com "scope"); o token de acesso
  (com "mfa": true) só sai depois do segundo fator.
"""
import base64
import hashlib
import hmac
import io
import secrets
import time
from datetime import timedelta

import pyotp
import qrcode

from backend.app.auth import create_access_token, decode_token_payload
from backend.app.field_crypto import _derive

EMISSOR = "DiagPro"
PASSO_SEGUNDOS = 30
JANELA = 1  # aceita o código do passo anterior/seguinte (relógio do celular adiantado/atrasado)
VALIDADE_PASSE = timedelta(minutes=5)
SCOPE_VERIFICAR = "2fa"
SCOPE_CADASTRO = "2fa_cadastro"
SCOPE_TROCA_SENHA = "troca_senha"
SCOPE_ESCOLHER_BANCA = "escolher_banca"  # 2FA ok; a pessoa trabalha para mais de uma banca
SESSAO_MAXIMA_SEGUNDOS = 12 * 3600  # mesmo em uso contínuo, depois disso precisa entrar de novo
QTD_CODIGOS_RECUPERACAO = 10


def novo_segredo() -> str:
    return pyotp.random_base32()


def uri_autenticador(segredo: str, conta: str) -> str:
    return pyotp.TOTP(segredo).provisioning_uri(name=conta, issuer_name=EMISSOR)


def qr_png_data_uri(uri: str) -> str:
    img = qrcode.make(uri, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def conferir_totp(segredo: str, codigo: str, ultimo_passo: int | None) -> int | None:
    """Devolve o passo aceito (para gravar como último) ou None. Recusa reuso do mesmo passo."""
    codigo = "".join(ch for ch in str(codigo or "") if ch.isdigit())
    if len(codigo) != 6 or not segredo:
        return None
    totp = pyotp.TOTP(segredo)
    agora = int(time.time()) // PASSO_SEGUNDOS
    for passo in range(agora - JANELA, agora + JANELA + 1):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(totp.at(passo * PASSO_SEGUNDOS), codigo):
            return passo
    return None


def _hash_recuperacao(codigo: str) -> str:
    chave = _derive("diagpro/2fa/recuperacao/v1")
    normalizado = codigo.replace("-", "").replace(" ", "").upper()
    return hmac.new(chave, normalizado.encode(), hashlib.sha256).hexdigest()


def gerar_codigos_recuperacao() -> tuple[list[str], list[str]]:
    """(códigos para mostrar UMA vez ao usuário, hashes para guardar)"""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I
    codigos = []
    for _ in range(QTD_CODIGOS_RECUPERACAO):
        bruto = "".join(secrets.choice(alfabeto) for _ in range(10))
        codigos.append(f"{bruto[:5]}-{bruto[5:]}")
    return codigos, [_hash_recuperacao(c) for c in codigos]


def consumir_codigo_recuperacao(hashes: list[str] | None, codigo: str) -> list[str] | None:
    """Se o código vale, devolve a lista SEM ele (cada código vale uma vez); senão None."""
    alvo = _hash_recuperacao(str(codigo or ""))
    for h in hashes or []:
        if hmac.compare_digest(h, alvo):
            return [x for x in hashes if x != h]
    return None


def criar_passe(user, scope: str, **extra) -> str:
    dados = {"sub": user.username, "scope": scope, **extra}
    if user.tenant_id is not None:
        dados["tenant_id"] = user.tenant_id
    return create_access_token(dados, expires_delta=VALIDADE_PASSE)


def ler_passe(passe: str, scopes: tuple[str, ...]) -> dict:
    from fastapi import HTTPException, status
    payload = decode_token_payload(passe)
    if payload.get("scope") not in scopes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Passe de verificação inválido.")
    return payload


def criar_token_acesso(user, auth_time: int | None = None, minutos: int | None = None, sid: str | None = None) -> str:
    """auth_time = momento do login (mantido nas renovações). minutos = inatividade que derruba a sessão.
    sid = id da sessão (tabela sessoes): encerrada a sessão, o token deixa de valer na hora."""
    dados = {"sub": user.username, "role": user.role, "mfa": True, "auth_time": auth_time or int(time.time())}
    if sid:
        dados["sid"] = sid
    if user.tenant_id is not None:
        dados["tenant_id"] = user.tenant_id
    return create_access_token(dados, expires_delta=timedelta(minutes=minutos) if minutos else None)
