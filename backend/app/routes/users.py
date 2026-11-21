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

from backend.app import configuracoes, notificacoes, politica_senha, sessoes, vinculos
from backend.app.db_models import VinculoBanca

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

    # 3. Foto obrigatória (segurança: o administrador confere quem é antes de aprovar)
    avatar_url = await guardar_foto(avatar_file, tenant_id)

    # 4. Cria usuário (sempre inativo até aprovação do administrador); senha dentro da política
    await _exigir_politica(password, username, email)
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
        status=vinculos.PENDENTE,  # entra só depois da aprovação do administrador da banca
        is_active=True,
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

# ------------ FOTO ------------
FOTO_MAX_BYTES = 5 * 1024 * 1024


def preparar_foto(dados: bytes) -> bytes:
    """Regrava a foto como JPEG (sem EXIF/GPS, no máx. 800 px): o que fica guardado é só a imagem."""
    from io import BytesIO
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not dados or len(dados) > FOTO_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Envie uma foto de até 5 MB.")
    try:
        img = Image.open(BytesIO(dados))
        if img.width * img.height > 40_000_000:
            raise HTTPException(status_code=400, detail="Foto grande demais.")
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Arquivo de foto inválido. Use JPG, PNG ou WEBP.")
    if min(img.size) < 80:
        raise HTTPException(status_code=400, detail="Foto pequena demais: o rosto precisa aparecer com nitidez.")
    img.thumbnail((800, 800))
    saida = BytesIO()
    img.save(saida, format="JPEG", quality=85)
    return saida.getvalue()


async def guardar_foto(arquivo: UploadFile | None, tenant_id: int | None) -> str:
    """Foto obrigatória: valida, limpa e guarda cifrada com a chave da banca de origem."""
    if arquivo is None:
        raise HTTPException(status_code=400, detail="A foto é obrigatória.")
    dados = await arquivo.read(FOTO_MAX_BYTES + 1)
    try:
        return secure_files.store_bytes(preparar_foto(dados), tenant_id, ".jpg")
    except secure_files.SecureFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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


async def _exigir_politica(senha: str, username: str, email: str) -> dict:
    cfg = (await configuracoes.ler_plataforma())["seguranca"]
    erros = politica_senha.problemas(senha, username, email, cfg)
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "A senha não atende à política.", "problemas": erros})
    return cfg


async def _buscar_usuario_gerenciavel(db: AsyncSession, user_id: int, admin_user) -> DBUser:
    """
    Retorna o usuário-alvo se o admin puder gerenciá-lo:
    - admin geral na visão global gerencia qualquer usuário;
    - na banca: quem é da banca (origem) ou tem vínculo com ela; nunca um admin geral.
    Responde 404 para não revelar usuários de outros clientes.
    """
    query = select(DBUser).filter(DBUser.id == user_id)
    if not (_is_admin_geral(admin_user) and admin_user.tenant_id is None):
        query = query.where(vinculos.membros_da_banca(admin_user.tenant_id))
    user = (await db.execute(query)).scalars().first()
    if not user or (user.role == UserRole.ADMIN_GERAL.value and not _is_admin_geral(admin_user)):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


def _de_outra_banca(user, admin_user) -> bool:
    """A pessoa é de outra banca de origem (só tem vínculo com esta): os dados pessoais não são desta banca."""
    if _is_admin_geral(admin_user) and admin_user.tenant_id is None:
        return False
    return user.tenant_id != admin_user.tenant_id


async def _vinculo(db: AsyncSession, user, admin_user) -> VinculoBanca | None:
    return (await db.execute(select(VinculoBanca).where(
        VinculoBanca.user_id == user.id, VinculoBanca.tenant_id == admin_user.tenant_id))).scalars().first()


def _exigir_foto(user) -> None:
    if not user.avatar_url:
        raise HTTPException(status_code=400, detail="Sem foto: a pessoa precisa enviar a foto antes de ser aprovada.")


def _anonimizado(user) -> bool:
    return (user.username or "").startswith("anonimizado-")

# ------------ ROTA DE PERFIL ------------

@router.get("/me", response_model=PydanticUser)
async def get_me(current_user: DBUser = Depends(get_current_user)):
    return current_user


@router.put("/me/foto", response_model=PydanticUser, dependencies=[Depends(rate_limit(10, 60, "minha-foto"))])
async def enviar_minha_foto(
    foto: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """A própria pessoa envia/troca a foto (obrigatória). Guardada cifrada com a chave da banca de origem."""
    query = select(DBUser).where(blind_eq(DBUser.username, current_user.username))
    if _is_admin_geral(current_user):
        query = query.where(DBUser.tenant_id.is_(None))
    else:
        query = query.where(DBUser.tenant_id.is_not(None))
    user = (await db.execute(query)).scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.avatar_url = await guardar_foto(foto, user.tenant_id)
    await db.commit()
    await db.refresh(user)
    out = _serialize_user(user)
    out.role, out.tenant_id, out.status = current_user.role, current_user.tenant_id, current_user.status
    return out

# ------------ ROTAS DE ADMIN ------------

# de outra banca: esta banca vê só o necessário para trabalhar com a pessoa (nada financeiro nem documento)
_CAMPOS_SO_DA_ORIGEM = ("cpf", "pix_key", "banco", "agencia", "conta_corrente", "address", "birth_date", "notes",
                        "terms_acceptance")


def _serialize_user(user_orm: DBUser, papel: tuple[str, str, bool] | None = None, tenant_id: int | None = None) -> PydanticUser:
    user_out = PydanticUser.from_orm(user_orm)
    for field in PII_FIELDS:
        val = getattr(user_out, field, None)
        if val:
            setattr(user_out, field, safe_decrypt_pii(val))
    if papel is not None:
        role, status_banca, origem = papel
        user_out.role, user_out.status, user_out.outra_banca = role, status_banca, not origem
        user_out.tenant_id = tenant_id
        if not origem:
            for campo in _CAMPOS_SO_DA_ORIGEM:
                setattr(user_out, campo, None)
    return user_out


@router.get("/", response_model=List[PydanticUser])
async def list_users(
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    query = select(DBUser).order_by(DBUser.tenant_id.nulls_first(), DBUser.id)
    # Admin geral na visão global vê os usuários de todos os clientes; com um cliente escolhido (ou sendo
    # usuário de cliente), só quem é da banca ou tem vínculo com ela — o RLS da sessão também garante isso.
    if _is_admin_geral(admin_user) and admin_user.tenant_id is None:
        return [_serialize_user(u) for u in (await db.execute(query)).scalars().all()]
    t = admin_user.tenant_id
    lista = await vinculos.vinculos_da_banca(db, t)
    users = (await db.execute(query.where(vinculos.membros_da_banca(t)))).scalars().all()
    return [_serialize_user(u, vinculos.papel_e_status(u, lista, t), t) for u in users]

@router.post("/", response_model=PydanticUser, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    # Na banca, ninguém cria conta com senha escolhida por outra pessoa: o administrador envia o convite e a
    # pessoa se cadastra com os próprios dados, senha e foto (ver routes/convites.py).
    if not _is_admin_geral(admin_user):
        raise HTTPException(status_code=403, detail="Convide a pessoa por link: ela cria a própria senha e envia a foto.")
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
    await _exigir_politica(user_data.password, user_data.username, user_data.email)
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
    if update_data.get("password"):
        # ninguém define a senha de outra pessoa: o administrador envia o link de nova senha
        raise HTTPException(status_code=400, detail='A senha é criada pela própria pessoa: use "Enviar link de nova senha".')
    update_data.pop("password", None)

    if _de_outra_banca(user, admin_user):
        # pessoa de outra banca de origem: aqui só se controla o vínculo (função e situação)
        if set(update_data) - {"role", "status"}:
            raise HTTPException(status_code=403, detail="Os dados pessoais desta pessoa são alterados por ela mesma. "
                                                        "Aqui você muda só a função e a situação do vínculo.")
        v = await _vinculo(db, user, admin_user)
        if v is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        if update_data.get("role") is not None:
            role = _normalizar_role(update_data["role"])
            if role not in vinculos.PAPEIS_CONVIDAVEIS:
                raise HTTPException(status_code=403, detail="Para quem é de outra banca: professor, revisor ou diagramador.")
            v.role = role
        novo = (update_data.get("status") or "").lower()
        if novo:
            if novo not in (vinculos.ATIVO, vinculos.INATIVO):
                raise HTTPException(status_code=400, detail="Situação inválida.")
            if novo == vinculos.ATIVO and v.status != vinculos.ATIVO:
                _exigir_foto(user)
                v.aprovado_por, v.aprovado_em = admin_user.id, datetime.utcnow()
            v.status = novo
        await db.commit()
        if novo == vinculos.INATIVO:
            await sessoes.encerrar_do_usuario(user.id, "vinculo_desativado", tenant_id=admin_user.tenant_id)
        return _serialize_user(user, (v.role, v.status, False), admin_user.tenant_id)

    novo_status = (update_data.get("status") or "").lower()
    if novo_status == vinculos.ATIVO and (vinculos.status_origem(user) != vinculos.ATIVO or not user.is_active):
        _exigir_foto(user)
        if not user.is_active and not _anonimizado(user):
            user.is_active = True  # aprovação de quem se cadastrou (cadastros antigos ficavam com a conta inativa)

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
        if key == "role":
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
    if admin_user.tenant_id is not None:
        return _serialize_user(user, vinculos.papel_e_status(user, {}, admin_user.tenant_id), admin_user.tenant_id)
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
    if _de_outra_banca(user, admin_user):
        raise HTTPException(status_code=403, detail="O 2FA desta pessoa só pode ser resetado pela banca de origem dela.")
    user.totp_secret = None
    user.totp_ativo = False
    user.totp_ultimo_passo = None
    user.codigos_recuperacao = None
    await db.commit()
    logger.warning("2FA resetado (usuário %s por administrador %s)", user.id, admin_user.id)
    await sessoes.encerrar_do_usuario(user.id, "2fa_resetado")
    await notificacoes.notificar(user.id, "seguranca_2fa_resetado", "Sua verificação em duas etapas foi resetada",
                                 "Um administrador resetou o autenticador da sua conta. No próximo acesso você vai "
                                 "cadastrar o autenticador de novo. Se você não pediu isso, avise a sua banca.", "/minha-conta")


@router.post("/{user_id}/sessoes/encerrar")
async def desconectar_usuario(
    user_id: int = Path(..., description="ID do usuário"),
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user),
):
    """Administrador desconecta todos os acessos de alguém da banca (ex.: computador perdido, saída da equipe)."""
    user = await _buscar_usuario_gerenciavel(db, user_id, admin_user)
    # de outra banca: derruba só os acessos a ESTA banca
    tenant = admin_user.tenant_id if _de_outra_banca(user, admin_user) else None
    n = await sessoes.encerrar_do_usuario(user.id, "encerrada_pelo_administrador", tenant_id=tenant)
    logger.warning("Administrador %s desconectou o usuário %s (%s acesso(s))", admin_user.id, user.id, n)
    return {"encerradas": n}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int = Path(..., description="ID do usuário"),
    db: AsyncSession = Depends(get_tenant_db),
    admin_user: DBUser = Depends(get_admin_user)
):
    user = await _buscar_usuario_gerenciavel(db, user_id, admin_user)
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir o próprio usuário.")
    if _de_outra_banca(user, admin_user):
        # de outra banca: remove só o vínculo com esta banca (a conta continua sendo da pessoa)
        v = await _vinculo(db, user, admin_user)
        if v is not None:
            await db.delete(v)
            await db.commit()
        await sessoes.encerrar_do_usuario(user.id, "vinculo_removido", tenant_id=admin_user.tenant_id)
        return None
    if not _is_admin_geral(admin_user):
        if await vinculos.trabalha_para_outras_bancas(user.id):
            raise HTTPException(status_code=409, detail="Esta pessoa também trabalha para outras bancas: desative o "
                                                        "acesso dela aqui em vez de excluir a conta.")
    await db.delete(user)
    await db.commit()
    return None