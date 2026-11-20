# backend/app/notificacoes.py
"""
Avisos aos usuários: no sistema (sino) e, se a pessoa quiser, por e-mail.

Regras de sigilo:
- Um aviso NUNCA leva conteúdo de prova (enunciado, alternativas, gabarito): só o que aconteceu, o código curto
  da questão quando for o caso e um link para o DiagPro, onde o conteúdo continua protegido pelo login.
- Título/mensagem/link ficam cifrados no banco; a fila de e-mail guarda só estado e tentativas.
- A senha do servidor de e-mail fica cifrada nas configurações da plataforma e nunca volta para a tela.
- Avisos de segurança (novo acesso, senha alterada, 2FA resetado) não podem ser desligados.
"""
import asyncio
import html
import logging
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from sqlalchemy import select

from backend.app import configuracoes
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Notificacao, User

logger = logging.getLogger("notificacoes")

TIPOS = {
    "seguranca_novo_login": {"rotulo": "Novo acesso à minha conta", "obrigatorio": True},
    "seguranca_senha_alterada": {"rotulo": "Minha senha foi alterada", "obrigatorio": True},
    "seguranca_2fa_resetado": {"rotulo": "Minha verificação em duas etapas foi resetada", "obrigatorio": True},
    "revisao_recebida": {"rotulo": "Questão enviada para eu revisar", "obrigatorio": False},
    "revisao_devolvida": {"rotulo": "Minha questão voltou com ajustes", "obrigatorio": False},
    "revisao_aprovada": {"rotulo": "Minha questão foi aprovada", "obrigatorio": False},
    "sistema": {"rotulo": "Avisos gerais do sistema", "obrigatorio": False},
}
_ESPERA_MINUTOS = [1, 5, 30, 120]  # entre tentativas de e-mail; depois disso, "falhou"
_MAX_TENTATIVAS = len(_ESPERA_MINUTOS) + 1
_HOSTS_LOCAIS = ("localhost", "127.0.0.1", "::1")


# --------------------------------------------------------------------------- preferências
def preferencias_de(usuario: User) -> dict:
    """{tipo: quer_email}. Segurança é sempre True."""
    salvas = ((usuario.preferencias or {}) if isinstance(usuario.preferencias, dict) else {}).get("email", {})
    return {t: True if info["obrigatorio"] else bool(salvas.get(t, True)) for t, info in TIPOS.items()}


def validar_preferencias(dados: dict) -> dict:
    email = (dados or {}).get("email")
    if not isinstance(email, dict) or any(t not in TIPOS or not isinstance(v, bool) for t, v in email.items()):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Preferências inválidas.")
    return {"email": {t: (True if TIPOS[t]["obrigatorio"] else v) for t, v in email.items()}}


# --------------------------------------------------------------------------- criar aviso
async def notificar(usuario_id: int, tipo: str, titulo: str, mensagem: str, link: str | None = None) -> None:
    """Cria o aviso. Nunca derruba quem chamou: falha vira log (sem o conteúdo)."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo de aviso desconhecido: {tipo}")
    if link and not link.startswith("/"):
        raise ValueError("link do aviso deve ser um caminho interno")
    try:
        plataforma = await configuracoes.ler_plataforma()
        email_ligado = bool(plataforma["email"]["habilitado"])
        async with PlatformSessionLocal() as db:
            usuario = await db.get(User, usuario_id)
            if usuario is None:
                return
            quer_email = email_ligado and bool(usuario.email) and preferencias_de(usuario).get(tipo, False)
            db.add(Notificacao(
                tenant_id=usuario.tenant_id, usuario_id=usuario.id, tipo=tipo, criado_em=datetime.utcnow(),
                conteudo={"titulo": titulo[:200], "mensagem": mensagem[:2000], "link": link},
                email_estado="pendente" if quer_email else "nao_enviar", email_tentativas=0,
            ))
            await db.commit()
    except Exception as exc:
        logger.error("Falha ao criar aviso %s para o usuário %s: %s", tipo, usuario_id, type(exc).__name__)


async def notificar_varios(usuario_ids, tipo: str, titulo: str, mensagem: str, link: str | None = None) -> None:
    for uid in dict.fromkeys(usuario_ids):
        await notificar(uid, tipo, titulo, mensagem, link)


# --------------------------------------------------------------------------- e-mail
class ErroEmail(Exception):
    pass


def _montar_email(cfg: dict, para: str, titulo: str, mensagem: str, link: str | None) -> EmailMessage:
    url = (cfg["url_sistema"].rstrip("/") + link) if link else cfg["url_sistema"]
    assunto = "DiagPro: " + " ".join(titulo.split())[:150]
    texto = (f"{titulo}\n\n{mensagem}\n\nAcesse o DiagPro: {url}\n\n"
             "Este é um aviso automático. Por segurança, o conteúdo das provas nunca é enviado por e-mail.\n"
             "Você pode escolher quais avisos recebe em Minha conta.")
    esc = html.escape
    corpo_html = (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#0f172a;max-width:560px">'
        f'<h2 style="font-size:18px;margin:0 0 12px">{esc(titulo)}</h2>'
        f'<p style="white-space:pre-line;margin:0 0 18px">{esc(mensagem)}</p>'
        f'<p><a href="{esc(url, quote=True)}" style="background:#0284c7;color:#fff;padding:10px 18px;border-radius:6px;'
        'text-decoration:none;display:inline-block">Abrir o DiagPro</a></p>'
        '<p style="font-size:12px;color:#64748b;margin-top:24px">Aviso automático. Por segurança, o conteúdo das provas '
        'nunca é enviado por e-mail. Você pode escolher quais avisos recebe em Minha conta.</p></div>'
    )
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = formataddr((cfg["remetente_nome"] or "DiagPro", cfg["remetente_email"]))
    msg["To"] = para
    msg["Message-ID"] = make_msgid(domain=cfg["remetente_email"].split("@")[-1] or None)
    msg.set_content(texto)
    msg.add_alternative(corpo_html, subtype="html")
    return msg


def _enviar_smtp(cfg: dict, msg: EmailMessage) -> None:
    """Envio síncrono (roda numa thread). TLS obrigatório fora de servidor local."""
    host, porta, modo = cfg["host"], int(cfg["porta"]), cfg["seguranca"]
    if not host or not cfg["remetente_email"]:
        raise ErroEmail("Servidor de e-mail ou remetente não configurado.")
    if modo == "nenhuma" and host not in _HOSTS_LOCAIS:
        raise ErroEmail("Sem criptografia só é permitido com servidor local; use STARTTLS ou SSL.")
    contexto = ssl.create_default_context()
    try:
        if modo == "ssl":
            servidor = smtplib.SMTP_SSL(host, porta, timeout=30, context=contexto)
        else:
            servidor = smtplib.SMTP(host, porta, timeout=30)
        with servidor:
            if modo == "starttls":
                servidor.starttls(context=contexto)
            if cfg["usuario"] and cfg.get("senha"):
                servidor.login(cfg["usuario"], cfg["senha"])
            servidor.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ErroEmail("O servidor de e-mail recusou o usuário/senha.")
    except smtplib.SMTPRecipientsRefused:
        raise ErroEmail("O servidor de e-mail recusou o destinatário.")
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        raise ErroEmail(f"Falha ao falar com o servidor de e-mail ({type(exc).__name__}).")


async def enviar_email(cfg: dict, para: str, titulo: str, mensagem: str, link: str | None = None) -> None:
    msg = _montar_email(cfg, para, titulo, mensagem, link)
    await asyncio.to_thread(_enviar_smtp, cfg, msg)


async def processar_fila(limite: int = 25) -> dict:
    """Envia os e-mails pendentes. Usa SKIP LOCKED para não duplicar se houver mais de um processo."""
    plataforma = await configuracoes.ler_plataforma(forcar=True)
    cfg = plataforma["email"]
    agora = datetime.utcnow()
    resultado = {"enviados": 0, "falhas": 0}
    async with PlatformSessionLocal() as db:
        linhas = (await db.execute(
            select(Notificacao)
            .where(Notificacao.email_estado == "pendente")
            .where((Notificacao.email_proxima_tentativa.is_(None)) | (Notificacao.email_proxima_tentativa <= agora))
            .order_by(Notificacao.id).limit(limite).with_for_update(skip_locked=True)
        )).scalars().all()
        for n in linhas:
            if not cfg["habilitado"]:
                n.email_estado = "nao_enviar"
                continue
            usuario = await db.get(User, n.usuario_id)
            if usuario is None or not usuario.email or not usuario.is_active:
                n.email_estado = "nao_enviar"
                continue
            c = n.conteudo or {}
            try:
                await enviar_email(cfg, usuario.email, c.get("titulo", ""), c.get("mensagem", ""), c.get("link"))
                n.email_estado = "enviado"
                resultado["enviados"] += 1
            except ErroEmail as exc:
                n.email_tentativas = (n.email_tentativas or 0) + 1
                resultado["falhas"] += 1
                if n.email_tentativas >= _MAX_TENTATIVAS:
                    n.email_estado = "falhou"
                else:
                    n.email_proxima_tentativa = agora + timedelta(minutes=_ESPERA_MINUTOS[n.email_tentativas - 1])
                logger.warning("E-mail do aviso %s não enviado (tentativa %s): %s", n.id, n.email_tentativas, exc)
        await db.commit()
    return resultado


async def laco_da_fila(intervalo: int = 20) -> None:
    """Roda junto com a API (desligável com DIAGPRO_FILA_EMAIL=0)."""
    while True:
        try:
            await processar_fila()
        except Exception as exc:  # o laço nunca morre por uma falha pontual
            logger.error("Fila de e-mail: %s", type(exc).__name__)
        await asyncio.sleep(intervalo)


def fila_ligada() -> bool:
    return os.getenv("DIAGPRO_FILA_EMAIL", "1") != "0"
