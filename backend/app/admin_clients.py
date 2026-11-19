from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.field_crypto import blind_eq
from backend.app.database import get_platform_db
from backend.app.db_models import Tenant, User, ProvaMontada, BancoFrases, Evento, Cargo
from backend.app.models import Tenant as PydanticTenant, TenantCreate, TenantDashboard
from backend.app.auth import get_password_hash, get_current_user
from backend.app.roles import UserRole
from datetime import datetime
import secrets

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
    tenants = (await db.execute(select(Tenant))).scalars().all()
    dashboards = []
    for tenant in tenants:
        users = (await db.execute(
            select(User).where(User.tenant_id == tenant.id)
        )).scalars().all()
        users_total = len(users)
        users_by_role = {}
        admins_total = 0
        blocked_users_total = 0
        active_users = 0
        inactive_users = 0

        for user in users:
            users_by_role[user.role] = users_by_role.get(user.role, 0) + 1
            if user.role == "administrador":
                admins_total += 1
            if user.status == "bloqueado":
                blocked_users_total += 1
            if user.status == "ativo":
                active_users += 1
            if user.status == "inativo":
                inactive_users += 1

        percent_users_active = (active_users / users_total) * 100 if users_total else 0
        percent_users_inactive = (inactive_users / users_total) * 100 if users_total else 0

        frases_total = (await db.execute(
            select(func.count(BancoFrases.id)).where(BancoFrases.tenant_id == tenant.id)
        )).scalar_one()

        questions_total = (await db.execute(
            select(func.count(BancoFrases.id)).where(BancoFrases.tenant_id == tenant.id)
        )).scalar_one()

        exams = (await db.execute(
            select(ProvaMontada).where(ProvaMontada.tenant_id == tenant.id)
        )).scalars().all()
        exams_total = len(exams)
        avg_questions_per_exam = questions_total / exams_total if exams_total else 0

        events = (await db.execute(
            select(Evento).where(Evento.tenant_id == tenant.id)
        )).scalars().all()
        events_total = len(events)

        cargos_total = (await db.execute(
            select(func.count(Cargo.id_cargo)).where(Cargo.tenant_id == tenant.id)
        )).scalar_one()

        accesses_total_month = 42  # Simulação
        last_access = "2025-08-20T14:32:00"  # Simulação
        avg_access_time_per_user = 7.2  # Simulação

        recent_activities = [
            {"type": "login", "user": "admin1", "timestamp": "2025-08-19T09:00:00"},
            {"type": "criação_prova", "user": "prof1", "timestamp": "2025-08-18T15:40:00"},
        ]

        dashboards.append(TenantDashboard(
            id=tenant.id,
            name=tenant.name,
            domain=tenant.domain,
            status=tenant.status,
            tenant_type=tenant.tenant_type,    # <-- Adicionado!
            created_at=str(tenant.created_at) if tenant.created_at else None,
            responsible_name=tenant.responsible_name,
            responsible_email=tenant.responsible_email,
            responsible_phone=tenant.responsible_phone,
            plan_type=tenant.plan_type,
            plan_expires_at=str(tenant.plan_expires_at) if tenant.plan_expires_at else None,
            users_total=users_total,
            users_by_role=users_by_role,
            questions_total=questions_total,
            exams_total=exams_total,
            events_total=events_total,
            cargos_total=cargos_total,
            frases_total=frases_total,
            admins_total=admins_total,
            blocked_users_total=blocked_users_total,
            accesses_total_month=accesses_total_month,
            last_access=last_access,
            percent_users_active=percent_users_active,
            percent_users_inactive=percent_users_inactive,
            avg_questions_per_exam=avg_questions_per_exam,
            avg_access_time_per_user=avg_access_time_per_user,
            recent_activities=recent_activities
        ))

    return dashboards

# POST: cria um admin para o cliente - apenas admin geral
@router.post("/admin/clients/{client_id}/create-admin")
async def create_admin_for_client(
    client_id: int,
    db: AsyncSession = Depends(get_platform_db),
    admin_geral: User = Depends(get_admin_geral_user)
):
    # Busca o cliente
    tenant = await db.get(Tenant, client_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Crie dados do admin (customize conforme desejar)
    username = f"admin{client_id}"
    email = f"admin{client_id}@{tenant.domain}.com"
    # senha forte e aleatória, exibida uma única vez ao administrador geral (nunca uma senha fixa)
    from backend.app import politica_senha
    password = secrets.token_urlsafe(14)
    while politica_senha.problemas(password, username, email):
        password = secrets.token_urlsafe(14)
    password_hash = get_password_hash(password)

    # Verifica se já existe admin para esse cliente
    existing_admin = await db.execute(
        select(User)
        .where(User.tenant_id == client_id)
        .where(User.role == "administrador")
    )
    if existing_admin.scalars().first():
        raise HTTPException(status_code=400, detail="Já existe admin para esse cliente.")

    # Cria o usuário admin (sem client_id)
    new_admin = User(
        username=username,
        email=email,
        password_hash=password_hash,
        senha_alterada_em=datetime.utcnow(),
        deve_trocar_senha=True,  # senha provisória: troca obrigatória no primeiro acesso
        role="administrador",
        full_name=f"Administrador {tenant.name}",
        tenant_id=client_id,          # <-- só tenant_id!
        status="ativo",
        is_active=True,
        institution=tenant.name
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    # Retorne a senha apenas em ambiente seguro!
    return {
        "msg": "Admin criado!",
        "admin": {
            "id": new_admin.id,
            "username": new_admin.username,
            "email": new_admin.email,
            "password": password  # Retorne a senha só se for seguro!
        }
    }

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