"""
Financeiro da PLATAFORMA (administrador geral x bancas): planos, propostas, contratos/termos, faturas e documentos.

Nada aqui toca a negociação da banca com os professores (fin_contratos, fin_parcelas...): isso é só da banca.
Sessão de plataforma (enxerga todas as bancas), mas cada consulta filtra pela banca do caminho.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import fin_pdf, notificacoes
from backend.app.auth import get_current_user
from backend.app.database import get_platform_db
from backend.app.db_models import FinDocumento, FinFatura, FinProposta, FinTermo, PlanoBanca, Tenant, User
from backend.app.fin_calculo import moeda, num
from backend.app.roles import UserRole
from backend.app.routes.financeiro import (
    _baixar, _guardar, _ler_arquivo, _plano_atual, saida_doc_plataforma, saida_fatura, saida_proposta, saida_termo,
)
from backend.app import secure_files

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plataforma/financeiro", tags=["Financeiro da plataforma"])
TIPOS_TERMO = {"contrato": "Contrato de prestação de serviços", "termos_uso": "Termos de uso", "lgpd": "Acordo de tratamento de dados (LGPD)",
               "aditivo": "Aditivo contratual", "outro": "Outro documento"}


def admin_geral(current_user=Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN_GERAL:
        raise HTTPException(status_code=403, detail="Somente administradores gerais.")
    return current_user


async def _banca(db: AsyncSession, tenant_id: int) -> Tenant:
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalars().first()
    if t is None:
        raise HTTPException(status_code=404, detail="Banca não encontrada.")
    return t


async def _avisar_banca(db: AsyncSession, tenant_id: int, titulo: str, msg: str) -> None:
    ids = [u.id for u in (await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == UserRole.ADMIN.value,
                                                              User.is_active.is_(True)))).scalars()]
    await notificacoes.notificar_varios(ids, "sistema", titulo, msg, "/financeiro", tenant_id=tenant_id)


# ------------------------------------------------------------------------------------------------ planos
class PlanoIn(BaseModel):
    codigo: str = Field(..., min_length=2, max_length=40)
    nome: str = Field(..., min_length=2, max_length=100)
    descricao: str = Field("", max_length=3000)
    valor_mensal: float = Field(0, ge=0)
    valor_anual: float = Field(0, ge=0)
    limite_eventos: Optional[int] = Field(None, ge=0)
    limite_usuarios: Optional[int] = Field(None, ge=0)
    limite_questoes: Optional[int] = Field(None, ge=0)
    ativo: bool = True


def _saida_plano(p: PlanoBanca) -> dict:
    return {"id": p.id, "codigo": p.codigo, "nome": p.nome, "descricao": p.descricao or "", "valor_mensal": p.valor_mensal,
            "valor_anual": p.valor_anual, "limite_eventos": p.limite_eventos, "limite_usuarios": p.limite_usuarios,
            "limite_questoes": p.limite_questoes, "ativo": p.ativo}


@router.get("/planos")
async def listar_planos(db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    return [_saida_plano(p) for p in (await db.execute(select(PlanoBanca).order_by(PlanoBanca.valor_mensal))).scalars().all()]


@router.post("/planos", status_code=201)
async def criar_plano(body: PlanoIn, db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    if (await db.execute(select(PlanoBanca.id).where(PlanoBanca.codigo == body.codigo.strip().lower()))).first():
        raise HTTPException(status_code=409, detail="Já existe um plano com esse código.")
    p = PlanoBanca(**{**body.model_dump(), "codigo": body.codigo.strip().lower()}, criado_em=datetime.utcnow())
    db.add(p)
    await db.commit()
    return _saida_plano(p)


@router.put("/planos/{plano_id}")
async def editar_plano(body: PlanoIn, plano_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    p = (await db.execute(select(PlanoBanca).where(PlanoBanca.id == plano_id))).scalars().first()
    if p is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")
    for k, v in body.model_dump().items():
        setattr(p, k, v.strip().lower() if k == "codigo" else v)
    await db.commit()
    return _saida_plano(p)


# ------------------------------------------------------------------------------------------------ bancas
@router.get("/bancas")
async def resumo_das_bancas(db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    saida = []
    hoje = date.today()
    for t in (await db.execute(select(Tenant).order_by(Tenant.id))).scalars().all():
        faturas = (await db.execute(select(FinFatura).where(FinFatura.tenant_id == t.id, FinFatura.status != "cancelada"))).scalars().all()
        aberto = [f for f in faturas if f.status in ("aberta", "em_analise")]
        saida.append({
            "id": t.id, "nome": t.name, "situacao": t.status, "plano": t.plan_type or "",
            "plano_vence_em": t.plan_expires_at.date().isoformat() if t.plan_expires_at else None,
            "em_aberto": round(sum(num((f.dados or {}).get("valor")) for f in aberto), 2),
            "atrasadas": sum(1 for f in aberto if f.status == "aberta" and f.vencimento < hoje),
            "em_analise": sum(1 for f in aberto if f.status == "em_analise"),
            "recebido": round(sum(num((f.dados or {}).get("valor")) for f in faturas if f.status == "paga"), 2),
            "propostas_pendentes": (await db.execute(select(func.count(FinProposta.id)).where(
                FinProposta.tenant_id == t.id, FinProposta.status == "enviada"))).scalar_one(),
            "termos_pendentes": (await db.execute(select(func.count(FinTermo.id)).where(
                FinTermo.tenant_id == t.id, FinTermo.status == "pendente"))).scalar_one(),
        })
    return saida


@router.get("/bancas/{tenant_id}")
async def detalhe_da_banca(tenant_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    t = await _banca(db, tenant_id)
    propostas = (await db.execute(select(FinProposta).where(FinProposta.tenant_id == t.id).order_by(FinProposta.id.desc()))).scalars().all()
    termos = (await db.execute(select(FinTermo).where(FinTermo.tenant_id == t.id).order_by(FinTermo.id.desc()))).scalars().all()
    faturas = (await db.execute(select(FinFatura).where(FinFatura.tenant_id == t.id).order_by(FinFatura.vencimento.desc()))).scalars().all()
    docs = (await db.execute(select(FinDocumento).where(FinDocumento.tenant_id == t.id, FinDocumento.escopo == "plataforma")
                             .order_by(FinDocumento.id.desc()))).scalars().all()
    return {"banca": {"id": t.id, "nome": t.name, "situacao": t.status, "responsavel": t.responsible_name or "",
                      "email": t.responsible_email or ""},
            "plano": await _plano_atual(t.id), "propostas": [saida_proposta(p) for p in propostas],
            "termos": [saida_termo(x) for x in termos], "faturas": [saida_fatura(f) for f in faturas],
            "documentos": [saida_doc_plataforma(d) for d in docs]}


# ------------------------------------------------------------------------------------------------ propostas
class PropostaIn(BaseModel):
    plano_id: int
    periodicidade: str = "mensal"  # mensal | anual
    valor: Optional[float] = Field(None, ge=0)
    desconto: float = Field(0, ge=0, le=100)
    condicoes: str = Field("", max_length=5000)
    itens: list[str] = []
    validade: Optional[date] = None


@router.post("/bancas/{tenant_id}/propostas", status_code=201)
async def enviar_proposta(body: PropostaIn, tenant_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    t = await _banca(db, tenant_id)
    plano = (await db.execute(select(PlanoBanca).where(PlanoBanca.id == body.plano_id))).scalars().first()
    if plano is None:
        raise HTTPException(status_code=400, detail="Plano inválido.")
    if body.periodicidade not in ("mensal", "anual"):
        raise HTTPException(status_code=400, detail="Periodicidade inválida.")
    valor = body.valor if body.valor is not None else (plano.valor_anual if body.periodicidade == "anual" else plano.valor_mensal)
    final = round(valor * (1 - body.desconto / 100), 2)
    anteriores = (await db.execute(select(FinProposta).where(FinProposta.tenant_id == t.id))).scalars().all()
    for a in anteriores:
        if a.status == "enviada":
            a.status = "substituida"  # vale só a última versão enviada
    versao = len(anteriores) + 1
    numero = f"P{t.id:03d}-{datetime.utcnow():%Y}"
    itens = [i.strip()[:300] for i in body.itens if i.strip()][:30]
    if not itens and plano.descricao:
        itens = [linha.strip("•- ").strip() for linha in plano.descricao.splitlines() if linha.strip()]
    pdf = fin_pdf.proposta({"banca": t.name, "numero": numero, "versao": versao, "plano": plano.nome,
                            "periodicidade": body.periodicidade, "valor": valor, "desconto": body.desconto, "valor_final": final,
                            "condicoes": body.condicoes, "validade": body.validade.strftime("%d/%m/%Y") if body.validade else None,
                            "itens": itens})
    p = FinProposta(tenant_id=t.id, numero=numero, versao=versao, status="enviada", validade=body.validade,
                    dados={"plano_id": plano.id, "plano": plano.nome, "periodicidade": body.periodicidade, "valor": valor,
                           "desconto": body.desconto, "valor_final": final, "condicoes": body.condicoes, "itens": itens},
                    documento_ref=_guardar(pdf, t.id, "pdf"), criado_em=datetime.utcnow(), criado_por=u.id)
    db.add(p)
    await db.commit()
    await _avisar_banca(db, t.id, "Nova proposta da plataforma",
                        f"Proposta {numero} (v{versao}): {plano.nome}, {body.periodicidade}, {moeda(final)}. Veja em Financeiro > Plataforma.")
    return saida_proposta(p)


@router.post("/propostas/{proposta_id}/cancelar")
async def cancelar_proposta(proposta_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    p = (await db.execute(select(FinProposta).where(FinProposta.id == proposta_id))).scalars().first()
    if p is None or p.status != "enviada":
        raise HTTPException(status_code=409, detail="Só uma proposta aguardando resposta pode ser cancelada.")
    p.status = "cancelada"
    await db.commit()
    return {"ok": True}


# ------------------------------------------------------------------------------------------------ contratos e termos
@router.post("/bancas/{tenant_id}/termos", status_code=201)
async def enviar_termo(tenant_id: int = Path(...), tipo: str = Form(...), titulo: str = Form(..., max_length=200),
                       descricao: str = Form("", max_length=2000), texto: str = Form("", max_length=60000),
                       arquivo: UploadFile | None = File(None), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    """Contrato, termos de uso, LGPD ou aditivo: um PDF enviado ou um texto (vira PDF). A banca aceita com a senha."""
    t = await _banca(db, tenant_id)
    if tipo not in TIPOS_TERMO:
        raise HTTPException(status_code=400, detail="Tipo inválido.")
    if arquivo is not None:
        dados, nome = await _ler_arquivo(arquivo)
        if not nome.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Envie o documento em PDF.")
    elif texto.strip():
        dados = fin_pdf.documento_de_texto(titulo, texto, f"DiagPro — {TIPOS_TERMO[tipo]} — {t.name}")
    else:
        raise HTTPException(status_code=400, detail="Envie o PDF ou escreva o texto do documento.")
    termo = FinTermo(tenant_id=t.id, tipo=tipo, status="pendente", dados={"titulo": titulo, "descricao": descricao},
                     documento_ref=_guardar(dados, t.id, "pdf"), documento_sha256=hashlib.sha256(dados).hexdigest(),
                     criado_em=datetime.utcnow(), criado_por=u.id)
    db.add(termo)
    await db.commit()
    await _avisar_banca(db, t.id, "Documento da plataforma para aceite", f"{titulo}: leia e aceite em Financeiro > Plataforma.")
    return saida_termo(termo)


@router.post("/termos/{termo_id}/cancelar")
async def cancelar_termo(termo_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    x = (await db.execute(select(FinTermo).where(FinTermo.id == termo_id))).scalars().first()
    if x is None or x.status != "pendente":
        raise HTTPException(status_code=409, detail="Só um documento pendente pode ser cancelado.")
    x.status = "cancelado"
    await db.commit()
    return {"ok": True}


# ------------------------------------------------------------------------------------------------ faturas
class FaturaIn(BaseModel):
    competencia: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    vencimento: date
    valor: Optional[float] = Field(None, ge=0)
    descricao: str = Field("", max_length=500)
    observacoes: str = Field("", max_length=2000)


@router.post("/bancas/{tenant_id}/faturas", status_code=201)
async def emitir_fatura(body: FaturaIn, tenant_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    """Sem valor: usa a última proposta aceita (o plano contratado)."""
    t = await _banca(db, tenant_id)
    valor, descricao = body.valor, body.descricao
    if valor is None:
        aceita = (await db.execute(select(FinProposta).where(FinProposta.tenant_id == t.id, FinProposta.status == "aceita")
                                   .order_by(FinProposta.id.desc()))).scalars().first()
        if aceita is None:
            raise HTTPException(status_code=400, detail="A banca não tem proposta aceita: informe o valor da fatura.")
        d = aceita.dados or {}
        valor = num(d.get("valor_final"))
        descricao = descricao or f"{d.get('plano', '')} ({d.get('periodicidade', '')}) — competência {body.competencia}"
    if (await db.execute(select(FinFatura.id).where(FinFatura.tenant_id == t.id, FinFatura.competencia == body.competencia,
                                                    FinFatura.status != "cancelada"))).first():
        raise HTTPException(status_code=409, detail="Já existe fatura desta competência para a banca.")
    n = (await db.execute(select(func.count(FinFatura.id)).where(FinFatura.tenant_id == t.id))).scalar_one() + 1
    f = FinFatura(tenant_id=t.id, numero=f"F{t.id:03d}-{n:05d}", competencia=body.competencia, vencimento=body.vencimento,
                  status="aberta", dados={"valor": round(valor, 2), "descricao": descricao or f"Competência {body.competencia}",
                                          "observacoes": body.observacoes},
                  criado_em=datetime.utcnow(), criado_por=u.id)
    db.add(f)
    await db.commit()
    await _avisar_banca(db, t.id, f"Fatura {f.numero}", f"{moeda(valor)} com vencimento em {body.vencimento.strftime('%d/%m/%Y')}.")
    return saida_fatura(f)


async def _fatura(db: AsyncSession, fatura_id: int) -> FinFatura:
    f = (await db.execute(select(FinFatura).where(FinFatura.id == fatura_id))).scalars().first()
    if f is None:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    return f


@router.post("/faturas/{fatura_id}/confirmar")
async def confirmar_pagamento(fatura_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    f = await _fatura(db, fatura_id)
    if f.status not in ("aberta", "em_analise"):
        raise HTTPException(status_code=409, detail="Fatura já paga ou cancelada.")
    f.status, f.paga_em = "paga", datetime.utcnow()
    await db.commit()
    await _avisar_banca(db, f.tenant_id, f"Fatura {f.numero} quitada", "O pagamento foi confirmado. Obrigado!")
    return {"ok": True}


class MotivoIn(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=1000)


@router.post("/faturas/{fatura_id}/devolver")
async def devolver_comprovante(body: MotivoIn, fatura_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    """Comprovante não confere: a fatura volta a ficar em aberto, com o motivo."""
    f = await _fatura(db, fatura_id)
    if f.status != "em_analise":
        raise HTTPException(status_code=409, detail="Só uma fatura em análise pode ser devolvida.")
    f.status, f.dados = "aberta", {**(f.dados or {}), "motivo_devolucao": body.motivo}
    await db.commit()
    await _avisar_banca(db, f.tenant_id, f"Comprovante da fatura {f.numero} devolvido", body.motivo)
    return {"ok": True}


@router.post("/faturas/{fatura_id}/cancelar")
async def cancelar_fatura(body: MotivoIn, fatura_id: int = Path(...), db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    f = await _fatura(db, fatura_id)
    if f.status == "paga":
        raise HTTPException(status_code=409, detail="Fatura paga não pode ser cancelada.")
    f.status, f.dados = "cancelada", {**(f.dados or {}), "motivo_cancelamento": body.motivo}
    await db.commit()
    return {"ok": True}


# ------------------------------------------------------------------------------------------------ documentos e arquivos
@router.post("/bancas/{tenant_id}/documentos", status_code=201)
async def anexar_documento(tenant_id: int = Path(...), descricao: str = Form("", max_length=500), arquivo: UploadFile = File(...),
                           db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    t = await _banca(db, tenant_id)
    dados, nome = await _ler_arquivo(arquivo)
    d = FinDocumento(tenant_id=t.id, escopo="plataforma", tipo="outro", dados={"nome": nome, "descricao": descricao},
                     arquivo_ref=_guardar(dados, t.id, nome.rsplit(".", 1)[-1]), sha256=hashlib.sha256(dados).hexdigest(),
                     enviado_por=u.id, enviado_em=datetime.utcnow())
    db.add(d)
    await db.commit()
    return saida_doc_plataforma(d)


@router.get("/arquivo/{tipo}/{item_id}")
async def baixar(tipo: str, item_id: int, db: AsyncSession = Depends(get_platform_db), u=Depends(admin_geral)):
    if tipo == "proposta":
        x = (await db.execute(select(FinProposta).where(FinProposta.id == item_id))).scalars().first()
        if x and x.documento_ref:
            return _baixar(secure_files.read_bytes(x.documento_ref, x.tenant_id), f"proposta-{x.numero}-v{x.versao}.pdf")
    elif tipo == "termo":
        x = (await db.execute(select(FinTermo).where(FinTermo.id == item_id))).scalars().first()
        if x:
            return _baixar(secure_files.read_bytes(x.documento_ref, x.tenant_id), f"{x.tipo}-{x.id}.pdf")
    elif tipo == "documento":
        # só documentos da relação com a plataforma (nunca os do professor)
        x = (await db.execute(select(FinDocumento).where(FinDocumento.id == item_id, FinDocumento.escopo == "plataforma"))).scalars().first()
        if x:
            return _baixar(secure_files.read_bytes(x.arquivo_ref, x.tenant_id), (x.dados or {}).get("nome") or "documento.pdf")
    raise HTTPException(status_code=404, detail="Arquivo não encontrado.")


@router.get("/tipos")
async def tipos(u=Depends(admin_geral)):
    return {"termos": TIPOS_TERMO}



@router.get("/relatorios/faturas.csv")
async def exportar_faturas(inicio: Optional[str] = None, fim: Optional[str] = None, db: AsyncSession = Depends(get_platform_db),
                           u=Depends(admin_geral)):
    """Receita da plataforma: todas as faturas (competência AAAA-MM entre início e fim)."""
    from backend.app.routes.financeiro import _csv
    bancas = {t.id: t.name for t in (await db.execute(select(Tenant))).scalars()}
    linhas = [["Fatura", "Banca", "Competência", "Vencimento", "Situação", "Valor", "Descrição", "Paga em"]]
    for f in (await db.execute(select(FinFatura).order_by(FinFatura.competencia, FinFatura.id))).scalars().all():
        if (inicio and f.competencia < inicio) or (fim and f.competencia > fim):
            continue
        s = saida_fatura(f)
        linhas.append([f.numero, bancas.get(f.tenant_id, ""), f.competencia, f.vencimento.strftime("%d/%m/%Y"), s["status"], s["valor"],
                       s["descricao"], f.paga_em.strftime("%d/%m/%Y") if f.paga_em else ""])
    return _csv(linhas, "faturas-plataforma.csv")


@router.get("/cobranca")
async def ler_cobranca(u=Depends(admin_geral)):
    from backend.app import configuracoes
    return (await configuracoes.ler_plataforma())["financeiro"]
