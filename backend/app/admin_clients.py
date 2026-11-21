from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.field_crypto import blind_eq
from backend.app.database import get_platform_db
from backend.app.db_models import (
    AuditLogGeracao, BancoFrases, Cargo, Evento, ProvaMontada, QuestoesBanco, Sessao, Tenant, User, VinculoBanca,
)
from backend.app import vinculos
from backend.app.models import Tenant as PydanticTenant, TenantCreate, TenantDashboard
from backend.app.auth import get_password_hash, get_current_user
from backend.app.roles import UserRole
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def get_admin_geral_user(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN_GERAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Permissão de administrador geral necessária."
        )
    return current_user

@router.get("/admin/clients", response_model=list[PydanticTenant])
async def list_admin_clients(
    db: AsyncSession = Depends(get_platform_db),
    admin_geral: User = Depends(get_admin_geral_user)
):
    result = await db.execute(select(Tenant))
    tenants = result.scalars().all()
    return tenants

@router.post("/admin/clients", response_model=PydanticTenant)
async def create_admin_client(
    tenant: TenantCreate,
    db: AsyncSession = Depends(get_platform_db),
    admin_geral: User = Depends(get_admin_geral_user)
):
    # Normaliza domínio para evitar duplicidade por maiúsculas/espacos
    domain = tenant.domain.lower().strip()
    exist_domain = await db.execute(select(Tenant).where(blind_eq(Tenant.domain, domain)))
    if exist_domain.scalars().first():
        raise HTTPException(status_code=400, detail="Domínio já registrado.")
    exist_name = await db.execute(select(Tenant).where(blind_eq(Tenant.name, tenant.name)))
    if exist_name.scalars().first():
        raise HTTPException(status_code=400, detail="Nome de cliente já registrado.")

    tenant_dict = tenant.dict()
    tenant_dict["domain"] = domain

    # Converte plan_expires_at para datetime se vier como string
    plan_expires_at = tenant_dict.get("plan_expires_at")
    if plan_expires_at:
        try:
            # Aceita formatos ISO (YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS)
            tenant_dict["plan_expires_at"] = datetime.fromisoformat(plan_expires_at)
        except Exception:
            tenant_dict["plan_expires_at"] = None
    else:
        tenant_dict["plan_expires_at"] = None

    # Preenche created_at com o momento atual
    tenant_dict["created_at"] = datetime.now()

    db_tenant = Tenant(**tenant_dict)
    db.add(db_tenant)
    await db.commit()
    await db.refresh(db_tenant)

    # Converte datetimes para string no retorno
    response_dict = db_tenant.__dict__.copy()
    if response_dict.get("created_at"):
        response_dict["created_at"] = response_dict["created_at"].isoformat()
    if response_dict.get("plan_expires_at"):
        response_dict["plan_expires_at"] = response_dict["plan_expires_at"].isoformat() if response_dict["plan_expires_at"] else None

    return response_dict

@router.get("/admin/clients/dashboard", response_model=list[TenantDashboard])
async def list_admin_clients_dashboard(
    db: AsyncSession = Depends(get_platform_db),
    admin_geral: User = Depends(get_admin_geral_user)
):
    """Visão do administrador geral: números REAIS de cada cliente (sem conteúdo de prova)."""
    desde = datetime.utcnow() - timedelta(days=30)
    dashboards = []
    for tenant in (await db.execute(select(Tenant).order_by(Tenant.id))).scalars().all():
        t = tenant.id
        # pessoas da banca: as da origem + quem tem vínculo (professores/revisores de outras bancas)
        vinc = {v.user_id: v for v in (await db.execute(select(VinculoBanca).where(VinculoBanca.tenant_id == t))).scalars()}
        users = (await db.execute(select(User).where(
            (User.tenant_id == t) | (User.id.in_(list(vinc) or [0]))))).scalars().all()
        users_by_role: dict[str, int] = {}
        ativos = pendentes = inativos = admins = 0
        for u in users:
            role, situacao, _origem = vinculos.papel_e_status(u, vinc, t)
            if not u.is_active:
                situacao = "inativo"
            users_by_role[role] = users_by_role.get(role, 0) + 1
            admins += role == "administrador"
            ativos += situacao == "ativo"
            pendentes += situacao == "pendente"
            inativos += situacao == "inativo"
        total = len(users)

        def contar(coluna, *filtros):
            return select(func.count(coluna)).where(*filtros)

        questions_total = (await db.execute(contar(QuestoesBanco.id_questao, QuestoesBanco.tenant_id == t))).scalar_one()
        exams_total = (await db.execute(contar(ProvaMontada.id_prova_montada, ProvaMontada.tenant_id == t))).scalar_one()
        events_total = (await db.execute(contar(Evento.id_evento, Evento.tenant_id == t))).scalar_one()
        cargos_total = (await db.execute(contar(Cargo.id_cargo, Cargo.tenant_id == t))).scalar_one()
        frases_total = (await db.execute(contar(BancoFrases.id, BancoFrases.tenant_id == t))).scalar_one()
        acessos_mes = (await db.execute(contar(Sessao.id, Sessao.tenant_id == t, Sessao.criada_em >= desde))).scalar_one()
        ultimo = (await db.execute(select(func.max(Sessao.ultimo_uso_em)).where(Sessao.tenant_id == t))).scalar_one()
        recentes = (await db.execute(select(AuditLogGeracao).where(AuditLogGeracao.tenant_id == t)
                                     .order_by(AuditLogGeracao.timestamp.desc()).limit(3))).scalars().all()

        dashboards.append(TenantDashboard(
            id=t,
            name=tenant.name,
            domain=tenant.domain,
            status=tenant.status,
            tenant_type=tenant.tenant_type,
            created_at=tenant.created_at.isoformat() if tenant.created_at else None,
            responsible_name=tenant.responsible_name,
            responsible_email=tenant.responsible_email,
            responsible_phone=tenant.responsible_phone,
            plan_type=tenant.plan_type,
            plan_expires_at=tenant.plan_expires_at.date().isoformat() if tenant.plan_expires_at else None,
            users_total=total,
            users_by_role=users_by_role,
            questions_total=questions_total,
            exams_total=exams_total,
            events_total=events_total,
            cargos_total=cargos_total,
            frases_total=frases_total,
            admins_total=admins,
            blocked_users_total=inativos,
            pending_users_total=pendentes,
            accesses_total_month=acessos_mes,
            last_access=(ultimo.isoformat() + "Z") if ultimo else None,
            percent_users_active=(ativos / total) * 100 if total else 0,
            percent_users_inactive=(inativos / total) * 100 if total else 0,
            avg_questions_per_exam=(questions_total / exams_total) if exams_total else 0,
            avg_access_time_per_user=0,
            recent_activities=[{"type": a.acao, "user": a.usuario, "timestamp": a.timestamp.isoformat() + "Z"} for a in recentes],
        ))
    return dashboards


@router.put("/admin/clients/{client_id}", response_model=PydanticTenant)
async def update_client(
    client_id: int,
    dados: TenantCreate,
    db: AsyncSession = Depends(get_platform_db),
    admin_geral: User = Depends(get_admin_geral_user)
):
    tenant = await db.get(Tenant, client_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    nome, dominio = dados.name.strip(), dados.domain.lower().strip()
    if not nome or not dominio:
        raise HTTPException(status_code=400, detail="Nome e domínio são obrigatórios.")
    if dados.status not in STATUS_CLIENTE:
        raise HTTPException(status_code=400, detail="Situação inválida.")
    outro = (await db.execute(select(Tenant).where(blind_eq(Tenant.domain, dominio), Tenant.id != client_id))).scalars().first()
    if outro:
        raise HTTPException(status_code=400, detail="Domínio já registrado.")
    outro = (await db.execute(select(Tenant).where(blind_eq(Tenant.name, nome), Tenant.id != client_id))).scalars().first()
    if outro:
        raise HTTPException(status_code=400, detail="Nome de cliente já registrado.")
    bloqueando = dados.status != "ativo" and tenant.status == "ativo"
    tenant.name, tenant.domain, tenant.status, tenant.tenant_type = nome, dominio, dados.status, dados.tenant_type
    tenant.responsible_name = dados.responsible_name or None
    tenant.responsible_email = dados.responsible_email or None
    tenant.responsible_phone = dados.responsible_phone or None
    tenant.plan_type = dados.plan_type or None
    tenant.plan_expires_at = _data(dados.plan_expires_at)
    await db.commit()
    await db.refresh(tenant)
    if bloqueando:
        await _derrubar_acessos(client_id, "cliente_bloqueado")
    logger.warning("Cliente %s alterado pelo administrador geral %s", client_id, admin_geral.id)
    return tenant


@router.post("/admin/clients/{client_id}/bloquear")
async def bloquear_cliente(client_id: int, db: AsyncSession = Depends(get_platform_db),
                           admin_geral: User = Depends(get_admin_geral_user)):
    """Bloqueia o cliente: ninguém entra nele e quem está dentro sai na hora."""
    tenant = await db.get(Tenant, client_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    tenant.status = "bloqueado"
    await db.commit()
    n = await _derrubar_acessos(client_id, "cliente_bloqueado")
    logger.warning("Cliente %s bloqueado pelo administrador geral %s (%s acesso(s) encerrado(s))", client_id, admin_geral.id, n)
    return {"ok": True, "status": "bloqueado", "acessos_encerrados": n}


@router.post("/admin/clients/{client_id}/desbloquear")
async def desbloquear_cliente(client_id: int, db: AsyncSession = Depends(get_platform_db),
                              admin_geral: User = Depends(get_admin_geral_user)):
    tenant = await db.get(Tenant, client_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    tenant.status = "ativo"
    await db.commit()
    logger.warning("Cliente %s desbloqueado pelo administrador geral %s", client_id, admin_geral.id)
    return {"ok": True, "status": "ativo"}


@router.get("/admin/clients/{client_id}/logs")
async def atividade_do_cliente(client_id: int, db: AsyncSession = Depends(get_platform_db),
                               admin_geral: User = Depends(get_admin_geral_user)):
    """Últimas ações registradas na auditoria do cliente (quem, o quê, quando). Sem conteúdo de prova."""
    linhas = (await db.execute(select(AuditLogGeracao).where(AuditLogGeracao.tenant_id == client_id)
                               .order_by(AuditLogGeracao.timestamp.desc()).limit(100))).scalars().all()
    return [{"type": a.acao, "user": a.usuario, "timestamp": a.timestamp.isoformat() + "Z"} for a in linhas]


# O administrador do cliente entra por CONVITE (cria a própria senha e envia a foto): POST /convites com o
# cliente escolhido (X-Tenant-Id). Este atalho antigo inventava uma senha e a mostrava na tela.
@router.post("/admin/clients/{client_id}/create-admin")
async def create_admin_for_client(client_id: int, admin_geral: User = Depends(get_admin_geral_user)):
    raise HTTPException(status_code=410, detail="Use \"Convidar administrador\": a pessoa cria a própria senha e envia a foto.")


STATUS_CLIENTE = {"ativo", "inativo", "bloqueado"}


def _data(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor)[:19])
    except ValueError:
        raise HTTPException(status_code=400, detail="Data de vencimento inválida.")


async def _derrubar_acessos(tenant_id: int, motivo: str) -> int:
    from sqlalchemy import update
    from backend.app.database import PlatformSessionLocal
    async with PlatformSessionLocal() as s:
        r = await s.execute(update(Sessao).where(Sessao.tenant_id == tenant_id, Sessao.encerrada_em.is_(None))
                            .values(encerrada_em=datetime.utcnow(), motivo_encerramento=motivo))
        await s.commit()
    return r.rowcount


@router.get("/admin/clients/{client_id}", response_model=PydanticTenant)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_platform_db),
    current_user: User = Depends(get_current_user)
):
    # Só o administrador geral consulta qualquer cliente; os demais, apenas o próprio (o id vem do token,
    # então a sessão de plataforma aqui nunca lê outro cliente). A checagem vem ANTES da leitura.
    if current_user.role != UserRole.ADMIN_GERAL and current_user.tenant_id != client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    tenant = await db.get(Tenant, client_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return tenant