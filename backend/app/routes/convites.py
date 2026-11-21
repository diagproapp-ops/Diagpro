"""
Convites por link: o administrador NÃO cria senha nem preenche dados de ninguém. Ele gera um link de uso único
(e o sistema envia por e-mail, se o e-mail estiver configurado); a pessoa:

- sem conta: se cadastra com os próprios dados, senha e foto (obrigatória) -> fica PENDENTE;
- com conta em outra banca (professores e revisores atendem várias): entra com login, senha e 2FA para aceitar
  o vínculo -> vínculo PENDENTE;
- tipo 'senha': cria uma nova senha (substitui a senha definida pelo administrador).

Nada libera acesso sozinho: o administrador da banca aprova (conferindo a foto). Só o hash do token fica no banco;
o link vale 7 dias (senha: 24 h) e uma única vez. O administrador nunca fica sabendo se o e-mail já tinha conta.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import configuracoes, notificacoes, politica_senha, sessoes, vinculos
from backend.app import dois_fatores as df
from backend.app.auth import get_admin_user, get_password_hash, verify_password
from backend.app.database import PlatformSessionLocal, get_auth_db
from backend.app.db_models import Convite, Tenant, User, VinculoBanca
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import checar_bloqueio_por_falhas, rate_limit, registrar_falha
from backend.app.roles import UserRole
from backend.app.routes.users import _buscar_usuario_gerenciavel, _de_outra_banca, _is_admin_geral, guardar_foto
from backend.app.security import get_tenant_db
from backend.app.utils_crypto import encrypt_pii

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Convites"])

VALIDADE_CADASTRO = timedelta(days=7)
VALIDADE_SENHA = timedelta(hours=24)
PAPEIS = {"administrador", "professor", "revisor", "diagramador"}
_MAX_FALHAS, _JANELA_FALHAS = 5, 900


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _mascarar(email: str) -> str:
    nome, _, dominio = (email or "").partition("@")
    return (nome[:2] + "***@" + dominio) if dominio else "***"


def _estado(c: Convite) -> str:
    if c.usado_em:
        return "usado"
    if c.cancelado_em:
        return "cancelado"
    if c.expira_em <= datetime.utcnow():
        return "expirado"
    return "pendente"


async def _url_do_link(token: str) -> tuple[str, dict]:
    cfg = (await configuracoes.ler_plataforma())["email"]
    return f"{cfg['url_sistema'].rstrip('/')}/convite/{token}", cfg


async def _enviar(cfg: dict, para: str, titulo: str, mensagem: str, token: str) -> bool:
    """Envia na hora (sem fila: o link não pode ficar guardado em texto). Sem e-mail configurado = o admin copia."""
    if not cfg.get("habilitado"):
        return False
    try:
        await notificacoes.enviar_email(cfg, para, titulo, mensagem, f"/convite/{token}")
        return True
    except notificacoes.ErroEmail as exc:
        logger.warning("Convite não enviado por e-mail: %s", exc)
        return False


NOME_PLATAFORMA = "Plataforma DiagPro (administração geral)"


async def _nome_da_banca(db: AsyncSession, tenant_id: int | None) -> str:
    if tenant_id is None:  # convite de administrador geral
        return NOME_PLATAFORMA
    # a tabela de clientes é da plataforma (a sessão da banca não a lê); a linha inteira: o ORM decifra o nome
    async with PlatformSessionLocal() as pdb:
        t = (await pdb.execute(select(Tenant).where(Tenant.id == tenant_id))).scalars().first()
    return (t.name if t else "") or ""


def _exigir_banca(admin_user) -> int:
    if admin_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Escolha um cliente no topo da tela.")
    return admin_user.tenant_id


def _saida(c: Convite) -> dict:
    return {"id": c.id, "tipo": c.tipo, "email": c.email, "nome": c.nome, "role": c.role,
            "criado_em": c.criado_em.isoformat() + "Z", "expira_em": c.expira_em.isoformat() + "Z", "estado": _estado(c)}


# ------------------------------------------------------------------------------------------ administrador
class NovoConvite(BaseModel):
    email: EmailStr
    role: str
    nome: Optional[str] = None


@router.post("/convites", dependencies=[Depends(rate_limit(30, 60, "convites"))])
async def criar_convite(body: NovoConvite, db: AsyncSession = Depends(get_tenant_db), admin_user=Depends(get_admin_user)):
    t = _exigir_banca(admin_user)
    role = body.role.strip().lower()
    if role not in PAPEIS:
        raise HTTPException(status_code=400, detail="Função inválida.")
    email = body.email.strip().lower()
    # quem já trabalha nesta banca não precisa de convite (a lista de usuários desta banca o administrador já vê)
    membro = (await db.execute(select(User.id).where(blind_eq(User.email, email), vinculos.membros_da_banca(t)))).first()
    if membro:
        raise HTTPException(status_code=409, detail="Esta pessoa já é usuária desta banca.")
    agora = datetime.utcnow()
    for antigo in (await db.execute(select(Convite).where(
            Convite.tenant_id == t, Convite.tipo == "cadastro", Convite.usado_em.is_(None),
            Convite.cancelado_em.is_(None)))).scalars():
        if (antigo.email or "").lower() == email:
            antigo.cancelado_em = agora  # um convite valendo por pessoa: o novo substitui o anterior
    token = secrets.token_urlsafe(32)
    c = Convite(tenant_id=t, token_hash=_hash(token), tipo="cadastro", email=email, nome=(body.nome or "").strip() or None,
                role=role, criado_por=admin_user.id, criado_em=agora, expira_em=agora + VALIDADE_CADASTRO)
    db.add(c)
    await db.commit()
    url, cfg = await _url_do_link(token)
    banca = await _nome_da_banca(db, t) or "a banca"
    enviado = await _enviar(cfg, email, f"Convite para trabalhar com {banca}",
                            f"Você foi convidado(a) para atuar como {role} em {banca} no DiagPro.\n"
                            "Abra o link para se cadastrar com os seus dados, a sua senha e a sua foto. Se você já usa o "
                            "DiagPro em outra banca, entre com a sua conta para aceitar. O link vale 7 dias e uma única vez.\n"
                            "Depois disso, o administrador da banca confere o cadastro e libera o acesso.", token)
    logger.warning("Convite %s criado na banca %s por %s", c.id, t, admin_user.id)
    return {**_saida(c), "link": url, "enviado_por_email": enviado}


@router.get("/convites")
async def listar_convites(db: AsyncSession = Depends(get_tenant_db), admin_user=Depends(get_admin_user)):
    t = _exigir_banca(admin_user)
    desde = datetime.utcnow() - timedelta(days=30)
    linhas = (await db.execute(select(Convite).where(Convite.tenant_id == t, Convite.criado_em >= desde)
                               .order_by(Convite.id.desc()).limit(200))).scalars().all()
    return [_saida(c) for c in linhas]


@router.delete("/convites/{convite_id}")
async def cancelar_convite(convite_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                           admin_user=Depends(get_admin_user)):
    t = _exigir_banca(admin_user)
    c = (await db.execute(select(Convite).where(Convite.id == convite_id, Convite.tenant_id == t))).scalars().first()
    if c is None:
        raise HTTPException(status_code=404, detail="Convite não encontrado.")
    if _estado(c) == "pendente":
        c.cancelado_em = datetime.utcnow()
        await db.commit()
    return _saida(c)


@router.post("/users/{user_id}/link-senha", dependencies=[Depends(rate_limit(10, 60, "link-senha"))])
async def link_de_nova_senha(user_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                             admin_user=Depends(get_admin_user)):
    """Esqueceu a senha: o administrador envia um link; a própria pessoa cria a nova senha (o 2FA continua valendo)."""
    t = _exigir_banca(admin_user)
    user = await _buscar_usuario_gerenciavel(db, user_id, admin_user)
    if _de_outra_banca(user, admin_user) and not _is_admin_geral(admin_user):
        raise HTTPException(status_code=403, detail="O link de nova senha desta pessoa é enviado pela banca de origem dela.")
    if not user.email or not user.is_active:
        raise HTTPException(status_code=400, detail="Conta sem e-mail ou desativada.")
    agora = datetime.utcnow()
    for antigo in (await db.execute(select(Convite).where(
            Convite.tenant_id == t, Convite.tipo == "senha", Convite.user_id == user.id,
            Convite.usado_em.is_(None), Convite.cancelado_em.is_(None)))).scalars():
        antigo.cancelado_em = agora
    token = secrets.token_urlsafe(32)
    c = Convite(tenant_id=t, token_hash=_hash(token), tipo="senha", email=user.email, user_id=user.id,
                criado_por=admin_user.id, criado_em=agora, expira_em=agora + VALIDADE_SENHA)
    db.add(c)
    await db.commit()
    url, cfg = await _url_do_link(token)
    enviado = await _enviar(cfg, user.email, "Crie uma nova senha",
                            "O administrador da sua banca enviou um link para você criar uma nova senha no DiagPro. "
                            "O link vale 24 horas e uma única vez. Se você não pediu, avise a sua banca.", token)
    await notificacoes.notificar(user.id, "seguranca_senha_alterada", "Link de nova senha enviado",
                                 "Um administrador gerou um link para você criar uma nova senha. Se você não pediu, avise a sua banca.",
                                 "/minha-conta")
    logger.warning("Link de nova senha para o usuário %s gerado por %s", user.id, admin_user.id)
    return {**_saida(c), "link": url, "enviado_por_email": enviado}


# ------------------------------------------------------------------------------------------ público (link)
async def _convite_valido(db: AsyncSession, token: str, tipo: str | None = None) -> Convite:
    c = (await db.execute(select(Convite).where(Convite.token_hash == _hash(token or "")))).scalars().first()
    if c is None or _estado(c) != "pendente" or (tipo and c.tipo != tipo):
        raise HTTPException(status_code=410, detail="Este link expirou ou já foi usado. Peça um novo ao administrador da banca.")
    return c


async def _conta_do_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(blind_eq(User.email, email)))).scalars().first()


async def _avisar_admins(db: AsyncSession, tenant_id: int | None, quem: str) -> None:
    if tenant_id is None:  # novo administrador geral: quem aprova são os administradores gerais
        admins = [u.id for u in (await db.execute(select(User).where(
            User.tenant_id.is_(None), User.role == UserRole.ADMIN_GERAL.value, User.is_active.is_(True)))).scalars()]
        await notificacoes.notificar_varios(
            admins, "sistema", "Administrador geral aguardando aprovação",
            f"{quem} respondeu ao convite de administrador geral. Confira a foto e os dados em Configurações > "
            "Administradores da plataforma.", "/settings?secao=plataforma_admins")
        return
    admins = [u.id for u in (await db.execute(select(User).where(
        User.tenant_id == tenant_id, User.role == UserRole.ADMIN.value, User.is_active.is_(True)))).scalars()]
    await notificacoes.notificar_varios(
        admins, "sistema", "Cadastro aguardando aprovação",
        f"{quem} respondeu ao convite e aguarda a sua aprovação. Confira a foto e os dados em Configurações > Usuários.",
        "/settings?secao=users", tenant_id=tenant_id)


@router.get("/convites/publico/{token}", dependencies=[Depends(rate_limit(30, 60, "convite-publico"))])
async def ver_convite(token: str, db: AsyncSession = Depends(get_auth_db)):
    c = await _convite_valido(db, token)
    banca = await _nome_da_banca(db, c.tenant_id)
    cfg = (await configuracoes.ler_plataforma())["seguranca"]
    dados = {"tipo": c.tipo, "banca": banca, "role": c.role, "email": _mascarar(c.email), "nome": c.nome,
             "expira_em": c.expira_em.isoformat() + "Z", "regras_senha": politica_senha.regras(cfg)}
    if c.tipo == "cadastro":
        # o link foi enviado para este e-mail: dizer se já existe conta só a quem abriu o link
        dados["conta_existente"] = (await _conta_do_email(db, c.email)) is not None
    return dados


def _exigir_termos(conf: bool, vazamento: bool) -> None:
    if not conf or not vazamento:
        raise HTTPException(status_code=400, detail="É obrigatório aceitar os dois termos.")


@router.post("/convites/publico/{token}/cadastro", status_code=201,
             dependencies=[Depends(rate_limit(5, 60, "convite-cadastro"))])
async def cadastrar_pelo_convite(
    token: str,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    phone: Optional[str] = Form(None),
    cpf: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    institution: Optional[str] = Form(None),
    specialty: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    accepted_confidentiality: bool = Form(...),
    accepted_data_leak: bool = Form(...),
    foto: UploadFile = File(...),
    db: AsyncSession = Depends(get_auth_db),
):
    """Pessoa sem conta: cadastro com os próprios dados, senha e foto. Fica pendente até a aprovação."""
    c = await _convite_valido(db, token, "cadastro")
    _exigir_termos(accepted_confidentiality, accepted_data_leak)
    username, full_name = username.strip(), " ".join(full_name.split())
    if len(username) < 3 or len(full_name) < 3:
        raise HTTPException(status_code=400, detail="Preencha o nome completo e um usuário com pelo menos 3 caracteres.")
    if await _conta_do_email(db, c.email):
        raise HTTPException(status_code=409, detail="Este e-mail já tem conta: entre com ela para aceitar o convite.")
    if (await db.execute(select(User.id).where(blind_eq(User.username, username)))).first():
        raise HTTPException(status_code=409, detail="Este nome de usuário já existe. Escolha outro.")
    cfg = (await configuracoes.ler_plataforma())["seguranca"]
    erros = politica_senha.problemas(password, username, c.email, cfg)
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "A senha não atende à política.", "problemas": erros})
    avatar = await guardar_foto(foto, c.tenant_id)
    agora = datetime.utcnow()
    user = User(username=username, email=c.email, password_hash=get_password_hash(password), senha_alterada_em=agora,
                role=c.role, tenant_id=c.tenant_id, full_name=full_name, phone=phone, cpf=encrypt_pii(cpf),
                birth_date=birth_date, institution=institution, specialty=specialty, address=address,
                avatar_url=avatar, status=vinculos.PENDENTE, is_active=True,
                terms_acceptance=f"confidencialidade+vazamento aceitos em {agora.isoformat()}Z")
    db.add(user)
    c.usado_em = agora
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Usuário ou e-mail já registrado.")
    logger.warning("Cadastro pelo convite %s (usuário %s, banca %s)", c.id, user.id, c.tenant_id)
    await _avisar_admins(db, c.tenant_id, full_name)
    return {"ok": True, "mensagem": "Cadastro enviado! O administrador da banca vai conferir e liberar o seu acesso."}


@router.post("/convites/publico/{token}/aceitar", dependencies=[Depends(rate_limit(5, 60, "convite-aceitar"))])
async def aceitar_convite(
    token: str,
    username: str = Form(...),
    password: str = Form(...),
    codigo: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_auth_db),
):
    """Quem já tem conta (de outra banca) aceita o vínculo com login, senha e 2FA. Vínculo pendente até a aprovação."""
    c = await _convite_valido(db, token, "cadastro")
    if c.tenant_id is None:
        raise HTTPException(status_code=400, detail="Administrador geral precisa de uma conta própria: use \"Ainda não tenho conta\".")
    chave = f"convite:{c.id}"
    checar_bloqueio_por_falhas(chave, _MAX_FALHAS, _JANELA_FALHAS)
    user = (await db.execute(select(User).where(blind_eq(User.username, username.strip())))).scalars().first()
    if (user is None or not verify_password(password, user.password_hash)
            or (user.email or "").lower() != (c.email or "").lower()):
        registrar_falha(chave)
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos, ou esta conta não é a do e-mail convidado.")
    if user.totp_ativo:
        passo = df.conferir_totp(user.totp_secret, codigo or "", user.totp_ultimo_passo)
        if passo is None:
            registrar_falha(chave)
            raise HTTPException(status_code=400, detail="Código do autenticador inválido.")
        user.totp_ultimo_passo = passo
    if not user.is_active or user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Esta conta não pode aceitar convites. Fale com a banca.")
    if user.tenant_id == c.tenant_id:
        raise HTTPException(status_code=409, detail="Você já é usuário desta banca.")
    if c.role not in vinculos.PAPEIS_CONVIDAVEIS:
        raise HTTPException(status_code=400, detail="Este convite é para administrador: ele precisa de uma conta própria "
                                                    "desta banca. Peça ao administrador um convite com outra função.")
    if foto is not None:
        user.avatar_url = await guardar_foto(foto, user.tenant_id)
    if not user.avatar_url:
        raise HTTPException(status_code=400, detail="A foto é obrigatória: envie a sua foto para aceitar o convite.")
    await vinculos.criar_vinculo(db, c.tenant_id, user.id, c.role, c.criado_por)
    c.usado_em = datetime.utcnow()
    await db.commit()
    logger.warning("Convite %s aceito: vínculo do usuário %s com a banca %s (pendente)", c.id, user.id, c.tenant_id)
    await _avisar_admins(db, c.tenant_id, user.full_name or user.username)
    return {"ok": True, "mensagem": "Convite aceito! Assim que o administrador da banca aprovar, ela aparece para você "
                                    "escolher ao entrar no DiagPro."}


class NovaSenhaBody(BaseModel):
    nova_senha: str


@router.post("/convites/publico/{token}/senha", dependencies=[Depends(rate_limit(5, 60, "convite-senha"))])
async def nova_senha_pelo_link(token: str, body: NovaSenhaBody, db: AsyncSession = Depends(get_auth_db)):
    """A própria pessoa cria a nova senha. Os acessos abertos caem; o 2FA continua valendo no próximo login."""
    from backend.app.routes.auth import _validar_nova_senha

    c = await _convite_valido(db, token, "senha")
    user = (await db.execute(select(User).where(User.id == c.user_id))).scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=410, detail="Este link expirou ou já foi usado. Peça um novo ao administrador da banca.")
    cfg = await _validar_nova_senha(user, body.nova_senha)
    politica_senha.aplicar_nova_senha(user, body.nova_senha, cfg=cfg)
    c.usado_em = datetime.utcnow()
    await db.commit()
    await sessoes.encerrar_do_usuario(user.id, "senha_alterada")
    await notificacoes.notificar(user.id, "seguranca_senha_alterada", "Sua senha foi alterada",
                                 "A senha da sua conta no DiagPro foi criada pelo link de nova senha. Se não foi você, "
                                 "avise o administrador da sua banca imediatamente.", "/minha-conta")
    return {"ok": True, "mensagem": "Senha criada! Entre no DiagPro com a nova senha."}
