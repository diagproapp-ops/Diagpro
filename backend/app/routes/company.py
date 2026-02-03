from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import os

from backend.app.database import get_db
from backend.app.db_models import Company
from backend.app.models import Company as CompanyModel
from backend.app.auth import get_current_user

router = APIRouter()

@router.get("/company", response_model=CompanyModel)
async def get_company(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    tenant_id = current_user.tenant_id
    result = await db.execute(select(Company).where(Company.tenant_id == tenant_id))
    company = result.scalars().first()
    if not company:
        return CompanyModel(
            id=0,
            tenant_id=tenant_id if tenant_id is not None else 0,
            company_name="", company_cnpj="", company_address="",
            company_phone="", company_email="", company_website="", company_logo_path=""
        )
    return company

@router.put("/company", response_model=CompanyModel)
async def update_company(
    company_name: str = Form(...),
    company_cnpj: str = Form(...),
    company_address: str = Form(...),
    company_phone: str = Form(...),
    company_email: str = Form(...),
    company_website: str = Form(...),
    logo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    tenant_id = current_user.tenant_id
    result = await db.execute(select(Company).where(Company.tenant_id == tenant_id))
    company = result.scalars().first()
    logo_path = None

    if logo:
        folder = "static/logos"
        os.makedirs(folder, exist_ok=True)
        # Nome do arquivo inclui tenant_id para evitar conflitos
        logo_filename = f"logo_{tenant_id}_{logo.filename}"
        logo_path = os.path.join(folder, logo_filename)
        with open(logo_path, "wb") as f:
            f.write(await logo.read())
        logo_path = "/" + logo_path  # caminho relativo para servir

    if not company:
        company = Company(
            tenant_id=tenant_id,
            company_name=company_name,
            company_cnpj=company_cnpj,
            company_address=company_address,
            company_phone=company_phone,
            company_email=company_email,
            company_website=company_website,
            company_logo_path=logo_path or "",
        )
        db.add(company)
    else:
        company.company_name = company_name
        company.company_cnpj = company_cnpj
        company.company_address = company_address
        company.company_phone = company_phone
        company.company_email = company_email
        company.company_website = company_website
        if logo_path:
            company.company_logo_path = logo_path
    await db.commit()
    await db.refresh(company)
    return company