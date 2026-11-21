"""
Financeiro da banca:
 - banca x professor (contratos, parcelas com gatilho, ajustes, documentos, aceite eletrônico, extrato);
 - a visão da banca sobre a plataforma (plano, propostas, termos, faturas, documentos).

O ADMINISTRADOR GERAL NÃO ENTRA AQUI: a negociação da banca com os professores é só da banca (mesmo com um cliente
escolhido no topo, as rotas recusam). O lado da plataforma do administrador geral fica em financeiro_plataforma.py.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import fin_calculo as fc
from backend.app import fin_pdf, notificacoes, secure_files, vinculos
from backend.app.auth import get_current_user, verify_password
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import (
    Company, Evento, FinAjuste, FinConfig, FinContrato, FinDocumento, FinFatura, FinParcela, FinProposta, FinTermo, Tenant,
    User,
)
from backend.app.field_crypto import blind_eq
from backend.app.rate_limit import checar_bloqueio_por_falhas, rate_limit, registrar_falha
from backend.app.roles import UserRole
from backend.app.security import get_tenant_db
from backend.app.utils_crypto import safe_decrypt_pii

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/financeiro", tags=["Financeiro da banca"])

TIPOS_DOC_PROFESSOR = {"nota_fiscal": "Nota fiscal", "rpa": "RPA", "comprovante": "Comprovante de pagamento",
                       "recibo": "Recibo", "outro": "Outro documento"}
MAX_ARQUIVO = 15 * 1024 * 1024


def _papel(u) -> str:
    r = getattr(u, "role", "")
    return r.value if isinstance(r, UserRole) else str(r)


def admin_da_banca(current_user=Depends(get_current_user)):
    """Só o administrador DA BANCA. O administrador geral nunca vê a negociação com professores."""
    if _papel(current_user) != UserRole.ADMIN.value or current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="O financeiro com os professores é só da banca (administrador da banca).")
    return current_user


def professor(current_user=Depends(get_current_user)):
    if _papel(current_user) != UserRole.PROFESSOR.value or current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Área do professor.")
    return current_user


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


async def _senha_confere(request: Request, user, senha: str, chave: str) -> None:
    """Aceite eletrônico: a senha pessoal confirma que é a própria pessoa (5 erros em 15 min bloqueiam)."""
    checar_bloqueio_por_falhas(chave, 5, 900)
    async with PlatformSessionLocal() as pdb:
        q = select(User).where(blind_eq(User.username, user.username), User.tenant_id.is_not(None))
        conta = (await pdb.execute(q)).scalars().first()
    if conta is None or not verify_password(senha or "", conta.password_hash):
        registrar_falha(chave)
        raise HTTPException(status_code=400, detail="Senha incorreta.")


def _registro_aceite(request: Request, user, sha: str | None, codigo: str | None) -> dict:
    return {"por_id": user.id, "por": user.full_name or user.username, "usuario": user.username,
            "em": datetime.utcnow().isoformat() + "Z", "ip": _ip(request),
            "navegador": (request.headers.get("user-agent") or "")[:200], "sha256": sha, "codigo": codigo}


async def _ler_arquivo(arquivo: UploadFile) -> tuple[bytes, str]:
    dados = await arquivo.read(MAX_ARQUIVO + 1)
    if not dados or len(dados) > MAX_ARQUIVO:
        raise HTTPException(status_code=400, detail="Envie um arquivo de até 15 MB.")
    nome = (arquivo.filename or "arquivo").replace("\\", "/").rsplit("/", 1)[-1][:120]
    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if ext not in ("pdf", "png", "jpg", "jpeg", "xml"):
        raise HTTPException(status_code=400, detail="Use PDF, PNG, JPG ou XML.")
    return dados, nome


def _guardar(dados: bytes, tenant_id: int, ext: str) -> str:
    try:
        return secure_files.store_bytes(dados, tenant_id, ext)
    except secure_files.SecureFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _baixar(dados: bytes, nome: str) -> Response:
    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else "pdf"
    tipo = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "xml": "application/xml"}.get(ext, "application/octet-stream")
    seguro = "".join(ch for ch in nome if ch.isalnum() or ch in "._- ")[:100] or "arquivo"
    return Response(content=dados, media_type=tipo, headers={
        "Content-Disposition": f'attachment; filename="{seguro}"', "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff"})


async def _nome_banca(db: AsyncSession, tenant_id: int) -> str:
    emp = (await db.execute(select(Company).where(Company.tenant_id == tenant_id))).scalars().first()
    if emp and emp.company_name:
        return emp.company_name
    async with PlatformSessionLocal() as pdb:
        t = (await pdb.execute(select(Tenant).where(Tenant.id == tenant_id))).scalars().first()
    return (t.name if t else "") or "Banca"


async def _avisar_admins(db: AsyncSession, tenant_id: int, titulo: str, msg: str, link: str = "/financeiro") -> None:
    ids = [u.id for u in (await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == UserRole.ADMIN.value,
                                                              User.is_active.is_(True)))).scalars()]
    await notificacoes.notificar_varios(ids, "sistema", titulo, msg, link, tenant_id=tenant_id)


# =========================================================================================== configuração
async def ler_config(db: AsyncSession, tenant_id: int) -> dict:
    cfg = (await db.execute(select(FinConfig).where(FinConfig.tenant_id == tenant_id))).scalars().first()
    base = {**fc.CONFIG_PADRAO, "precos": dict(fc.CONFIG_PADRAO["precos"]), "contratante": dict(fc.CONFIG_PADRAO["contratante"])}
    if cfg:
        base.update(cfg.dados or {})
    else:
        emp = (await db.execute(select(Company).where(Company.tenant_id == tenant_id))).scalars().first()
        if emp:
            base["contratante"] = {"razao_social": emp.company_name or "", "cnpj": emp.company_cnpj or "",
                                   "endereco": emp.company_address or "", "cidade": ""}
    return base


class ItemCronograma(BaseModel):
    descricao: str = Field(..., max_length=200)
    percentual: Optional[float] = Field(None, ge=0, le=100)
    valor_fixo: Optional[float] = Field(None, ge=0)
    gatilho: str
    data_prevista: Optional[date] = None


def _validar_cronograma(itens: list[ItemCronograma], exigir_100: bool) -> None:
    if not itens:
        raise HTTPException(status_code=400, detail="Inclua pelo menos uma parcela.")
    for it in itens:
        if it.gatilho not in fc.GATILHOS:
            raise HTTPException(status_code=400, detail=f"Condição inválida: {it.gatilho}")
        if it.gatilho == "data" and not it.data_prevista and exigir_100:
            raise HTTPException(status_code=400, detail="Parcela por data precisa da data.")
        if it.valor_fixo is None and it.percentual is None:
            raise HTTPException(status_code=400, detail="Cada parcela precisa de percentual ou valor fixo.")
    pct = [it.percentual for it in itens if it.valor_fixo is None]
    if exigir_100 and pct and abs(sum(pct) - 100) > 0.01 and all(it.valor_fixo is None for it in itens):
        raise HTTPException(status_code=400, detail=f"Os percentuais somam {sum(pct):g}%: precisam somar 100%.")


class ConfigIn(BaseModel):
    precos: dict[str, float]
    cronograma: list[ItemCronograma]
    clausulas_contrato: str = Field(..., max_length=20000)
    clausulas_cessao: str = Field(..., max_length=20000)
    contratante: dict[str, str] = {}
    observacoes_padrao: str = Field("", max_length=5000)


@router.get("/config")
async def obter_config(db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    return {**(await ler_config(db, u.tenant_id)), "rotulos_precos": fc.PRECOS, "gatilhos": fc.GATILHOS,
            "variaveis": ["BANCA", "PROFESSOR", "CPF", "EVENTO", "VALOR_TOTAL", "PRAZO_ENTREGA", "DATA"]}


@router.put("/config")
async def salvar_config(body: ConfigIn, db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    _validar_cronograma(body.cronograma, exigir_100=False)
    precos = {k: max(0.0, fc.num(body.precos.get(k))) for k in fc.PRECOS}
    dados = {"precos": precos, "cronograma": [it.model_dump(mode="json") for it in body.cronograma],
             "clausulas_contrato": body.clausulas_contrato, "clausulas_cessao": body.clausulas_cessao,
             "contratante": {k: str(v)[:300] for k, v in (body.contratante or {}).items()},
             "observacoes_padrao": body.observacoes_padrao}
    cfg = (await db.execute(select(FinConfig).where(FinConfig.tenant_id == u.tenant_id))).scalars().first()
    if cfg is None:
        db.add(FinConfig(tenant_id=u.tenant_id, dados=dados, atualizado_em=datetime.utcnow(), atualizado_por=u.id))
    else:
        cfg.dados, cfg.atualizado_em, cfg.atualizado_por = dados, datetime.utcnow(), u.id
    await db.commit()
    return {"ok": True}


# =========================================================================================== contratos
async def _contrato(db: AsyncSession, contrato_id: int, tenant_id: int) -> FinContrato:
    c = (await db.execute(select(FinContrato).where(FinContrato.id == contrato_id, FinContrato.tenant_id == tenant_id))).scalars().first()
    if c is None:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    return c


async def _professor_da_banca(db: AsyncSession, tenant_id: int, professor_id: int) -> User:
    for u, role in await vinculos.usuarios_da_banca(db, tenant_id, roles={"professor"}, somente_ativos=False):
        if u.id == professor_id:
            return u
    raise HTTPException(status_code=400, detail="Professor não encontrado nesta banca.")


async def _nomes(db: AsyncSession, tenant_id: int) -> tuple[dict[int, str], dict[str, str]]:
    pessoas = {u.id: (u.full_name or u.username) for u in (await db.execute(select(User).where(vinculos.membros_da_banca(tenant_id)))).scalars()}
    eventos = {e.id_evento: e.nome_evento for e in (await db.execute(select(Evento).where(Evento.tenant_id == tenant_id))).scalars()}
    return pessoas, eventos


class ContratoIn(BaseModel):
    professor_id: int
    evento_id: str
    modalidade: str = "por_questao"
    precos: dict[str, float] = {}
    quantidades: dict[str, float] = {}
    valor_fechado: Optional[float] = Field(None, ge=0)
    prazo_entrega: Optional[str] = Field(None, max_length=60)
    observacoes: str = Field("", max_length=5000)
    parcelas: list[ItemCronograma] = []


def _dados_contrato(body: ContratoIn) -> dict:
    if body.modalidade not in fc.MODALIDADES:
        raise HTTPException(status_code=400, detail="Modalidade inválida.")
    if body.modalidade == "valor_fechado" and not body.valor_fechado:
        raise HTTPException(status_code=400, detail="Informe o valor fechado.")
    return {"precos": {k: max(0.0, fc.num(body.precos.get(k))) for k in fc.PRECOS},
            "quantidades": {k: max(0.0, fc.num(body.quantidades.get(k))) for k in fc.PRECOS},
            "valor_fechado": fc.num(body.valor_fechado) if body.valor_fechado is not None else None,
            "prazo_entrega": body.prazo_entrega or "", "observacoes": body.observacoes}


async def _gravar_parcelas(db: AsyncSession, c: FinContrato, itens: list[ItemCronograma]) -> None:
    for p in (await db.execute(select(FinParcela).where(FinParcela.contrato_id == c.id))).scalars().all():
        await db.delete(p)
    await db.flush()
    for i, it in enumerate(itens, 1):
        db.add(FinParcela(tenant_id=c.tenant_id, contrato_id=c.id, ordem=i, gatilho=it.gatilho, status="prevista",
                          data_prevista=it.data_prevista,
                          dados={"descricao": it.descricao, "percentual": it.percentual, "valor_fixo": it.valor_fixo}))


@router.get("/visao")
async def visao_geral(evento_id: Optional[str] = None, db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    """Professores da banca com o contrato de cada evento e os totais (previsto, apurado, liberado, pago)."""
    t = u.tenant_id
    pessoas, eventos = await _nomes(db, t)
    q = select(FinContrato).where(FinContrato.tenant_id == t)
    if evento_id:
        q = q.where(FinContrato.evento_id == evento_id)
    contratos = []
    for c in (await db.execute(q.order_by(FinContrato.id.desc()))).scalars().all():
        cc = await fc.contrato_completo(db, c)
        contratos.append({**{k: cc[k] for k in ("id", "numero", "status", "modalidade", "evento_id", "professor_id", "totais", "producao")},
                          "professor": pessoas.get(c.professor_id, "—"), "evento": eventos.get(c.evento_id, "—"),
                          "parcelas": [{k: p[k] for k in ("ordem", "status", "a_pagar", "gatilho_rotulo")} for p in cc["parcelas"]]})
    sem_contrato = []
    if evento_id:
        com = {c["professor_id"] for c in contratos}
        for prof, _role in await vinculos.usuarios_da_banca(db, t, roles={"professor"}):
            if prof.id not in com:
                prod = await fc.producao(db, t, evento_id, prof.id)
                if prod["total"]:
                    sem_contrato.append({"professor_id": prof.id, "professor": pessoas.get(prof.id, prof.username),
                                         "producao": {k: v for k, v in prod.items() if k != "ids"}})
    tot = {k: round(sum(c["totais"][k] for c in contratos if c["status"] not in ("cancelado", "recusado")), 2)
           for k in ("previsto", "apurado", "liberado", "pago", "a_receber")}
    professores = [{"id": p.id, "nome": pessoas.get(p.id, p.username)}
                   for p, _r in await vinculos.usuarios_da_banca(db, t, roles={"professor"}, somente_ativos=False)]
    return {"contratos": contratos, "sem_contrato": sem_contrato, "totais": tot,
            "eventos": [{"id": k, "nome": v} for k, v in eventos.items()], "professores": professores}


@router.post("/contratos", status_code=201)
async def criar_contrato(body: ContratoIn, db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    t = u.tenant_id
    await _professor_da_banca(db, t, body.professor_id)
    if not (await db.execute(select(Evento.id_evento).where(Evento.id_evento == body.evento_id, Evento.tenant_id == t))).first():
        raise HTTPException(status_code=400, detail="Evento não encontrado.")
    ativo = (await db.execute(select(FinContrato.id).where(
        FinContrato.tenant_id == t, FinContrato.professor_id == body.professor_id, FinContrato.evento_id == body.evento_id,
        FinContrato.status.in_(["rascunho", "enviado", "aceito"])))).first()
    if ativo:
        raise HTTPException(status_code=409, detail="Este professor já tem um contrato em andamento neste evento.")
    cfg = await ler_config(db, t)
    parcelas = body.parcelas or [ItemCronograma(**p) for p in cfg["cronograma"]]
    _validar_cronograma(parcelas, exigir_100=False)
    if not body.precos:
        body.precos = cfg["precos"]
    dados = _dados_contrato(body)
    if not dados["observacoes"]:
        dados["observacoes"] = cfg.get("observacoes_padrao", "")
    for tentativa in range(5):
        ano = datetime.utcnow().year
        n = (await db.execute(select(func.count(FinContrato.id)).where(FinContrato.tenant_id == t))).scalar_one() + 1 + tentativa
        c = FinContrato(tenant_id=t, professor_id=body.professor_id, evento_id=body.evento_id, numero=f"{ano}-{n:04d}",
                        status="rascunho", modalidade=body.modalidade, dados=dados, criado_em=datetime.utcnow(), criado_por=u.id)
        db.add(c)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
    else:
        raise HTTPException(status_code=409, detail="Tente de novo.")
    await _gravar_parcelas(db, c, parcelas)
    await db.commit()
    return {"id": c.id, "numero": c.numero}


async def _detalhe(db: AsyncSession, c: FinContrato, para_professor: bool = False) -> dict:
    cc = await fc.contrato_completo(db, c)
    pessoas, eventos = await _nomes(db, c.tenant_id)
    docs = (await db.execute(select(FinDocumento).where(FinDocumento.contrato_id == c.id).order_by(FinDocumento.id))).scalars().all()
    cc["professor"] = pessoas.get(c.professor_id, "—")
    cc["evento"] = eventos.get(c.evento_id, "—")
    cc["documentos"] = [{"id": d.id, "tipo": d.tipo, "tipo_rotulo": TIPOS_DOC_PROFESSOR.get(d.tipo, d.tipo),
                         "nome": (d.dados or {}).get("nome", ""), "parcela_id": d.parcela_id, "enviado_em": fc._iso(d.enviado_em),
                         "enviado_por": pessoas.get(d.enviado_por, "—"), "sha256": d.sha256} for d in docs]
    if para_professor:
        cc["dados"] = {k: v for k, v in cc["dados"].items()}
    return cc


@router.get("/contratos/{contrato_id}")
async def obter_contrato(contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    return await _detalhe(db, await _contrato(db, contrato_id, u.tenant_id))


@router.put("/contratos/{contrato_id}")
async def editar_contrato(body: ContratoIn, contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                          u=Depends(admin_da_banca)):
    c = await _contrato(db, contrato_id, u.tenant_id)
    if c.status not in ("rascunho", "enviado", "recusado"):
        raise HTTPException(status_code=409, detail="Contrato aceito não se edita: registre ajustes nas parcelas ou faça outro contrato.")
    if body.professor_id != c.professor_id or body.evento_id != c.evento_id:
        raise HTTPException(status_code=400, detail="Professor e evento não mudam: crie outro contrato.")
    _validar_cronograma(body.parcelas, exigir_100=False)
    c.modalidade, c.dados = body.modalidade, _dados_contrato(body)
    # mudou depois de enviado: volta a rascunho (o PDF antigo deixa de valer)
    c.status, c.documento_ref, c.documento_sha256, c.codigo_verificacao, c.enviado_em = "rascunho", None, None, None, None
    await _gravar_parcelas(db, c, body.parcelas)
    await db.commit()
    return {"ok": True}


async def _gerar_documento(db: AsyncSession, c: FinContrato) -> bytes:
    cfg = await ler_config(db, c.tenant_id)
    prof = await _professor_da_banca(db, c.tenant_id, c.professor_id)
    ev = (await db.execute(select(Evento).where(Evento.id_evento == c.evento_id))).scalars().first()
    parcelas = (await db.execute(select(FinParcela).where(FinParcela.contrato_id == c.id).order_by(FinParcela.ordem))).scalars().all()
    dados = c.dados or {}
    return fin_pdf.contrato({
        "banca": await _nome_banca(db, c.tenant_id), "contratante": cfg.get("contratante") or {},
        "professor": {"nome": prof.full_name or prof.username, "email": prof.email or "",
                      "cpf": safe_decrypt_pii(prof.cpf) if (prof.tenant_id == c.tenant_id and prof.cpf) else ""},
        "evento": {"nome": ev.nome_evento if ev else "", "edital": (ev.numero_edital if ev else "") or "",
                   "data": ev.data_prova.strftime("%d/%m/%Y") if ev and ev.data_prova else ""},
        "numero": c.numero, "modalidade": c.modalidade, "dados": dados,
        "parcelas": [{**(p.dados or {}), "gatilho": p.gatilho, "data_prevista": p.data_prevista.isoformat() if p.data_prevista else None}
                     for p in parcelas],
        "previsto": fc.total_previsto(c.modalidade, dados),
        "clausulas_contrato": cfg["clausulas_contrato"], "clausulas_cessao": cfg["clausulas_cessao"],
        "codigo": c.codigo_verificacao,
    })


@router.post("/contratos/{contrato_id}/enviar")
async def enviar_contrato(contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    """Gera o PDF (contrato + termo de cessão e sigilo) e manda para o professor aceitar."""
    c = await _contrato(db, contrato_id, u.tenant_id)
    if c.status not in ("rascunho", "recusado"):
        raise HTTPException(status_code=409, detail="Só um rascunho (ou um contrato recusado e revisado) pode ser enviado.")
    c.codigo_verificacao = secrets.token_hex(5).upper()
    pdf = await _gerar_documento(db, c)
    c.documento_ref = _guardar(pdf, c.tenant_id, "pdf")
    c.documento_sha256 = hashlib.sha256(pdf).hexdigest()
    c.status, c.enviado_em, c.aceite = "enviado", datetime.utcnow(), None
    await db.commit()
    await notificacoes.notificar(c.professor_id, "sistema", f"Contrato {c.numero} para você aceitar",
                                 "A banca enviou o seu contrato de elaboração. Confira valores, parcelas e o termo de cessão "
                                 "e sigilo em Financeiro, e aceite com a sua senha.", "/financeiro", tenant_id=c.tenant_id)
    return {"ok": True, "codigo_verificacao": c.codigo_verificacao}


class MotivoIn(BaseModel):
    motivo: str = Field("", max_length=2000)


@router.post("/contratos/{contrato_id}/cancelar")
async def cancelar_contrato(body: MotivoIn, contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                            u=Depends(admin_da_banca)):
    c = await _contrato(db, contrato_id, u.tenant_id)
    pagas = (await db.execute(select(FinParcela.id).where(FinParcela.contrato_id == c.id,
                                                          FinParcela.status.in_(["paga", "confirmada"])))).first()
    if pagas:
        raise HTTPException(status_code=409, detail="Há parcelas pagas: encerre o contrato em vez de cancelar.")
    c.status, c.encerrado_em = "cancelado", datetime.utcnow()
    c.dados = {**(c.dados or {}), "motivo_cancelamento": body.motivo}
    await db.commit()
    return {"ok": True}


@router.post("/contratos/{contrato_id}/encerrar")
async def encerrar_contrato(contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    c = await _contrato(db, contrato_id, u.tenant_id)
    if c.status != "aceito":
        raise HTTPException(status_code=409, detail="Só um contrato aceito pode ser encerrado.")
    c.status, c.encerrado_em = "encerrado", datetime.utcnow()
    await db.commit()
    return {"ok": True}


@router.get("/contratos/{contrato_id}/pdf")
async def pdf_do_contrato(request: Request, contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                          current_user=Depends(get_current_user)):
    """O contrato enviado; depois do aceite, com a página do registro de aceite eletrônico."""
    c = await _contrato(db, contrato_id, current_user.tenant_id or -1)
    papel = _papel(current_user)
    if not ((papel == UserRole.ADMIN.value) or (papel == UserRole.PROFESSOR.value and c.professor_id == current_user.id)):
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    if not c.documento_ref:
        raise HTTPException(status_code=404, detail="O contrato ainda não foi enviado.")
    pdf = secure_files.read_bytes(c.documento_ref, c.tenant_id)
    if c.aceite and c.status in ("aceito", "encerrado"):
        a = c.aceite
        pdf = fin_pdf.anexar_registro(pdf, "Registro de aceite eletrônico", [
            ("Contrato", c.numero), ("Aceito por", f"{a.get('por')} ({a.get('usuario')})"), ("Data e hora (UTC)", a.get("em", "")),
            ("Endereço IP", a.get("ip", "")), ("Navegador", a.get("navegador", "")[:90]),
            ("Código de verificação", a.get("codigo", "")), ("SHA-256 do documento aceito", a.get("sha256", "")),
        ])
    return _baixar(pdf, f"contrato-{c.numero}.pdf")


# =========================================================================================== parcelas e ajustes
async def _parcela(db: AsyncSession, parcela_id: int, tenant_id: int) -> tuple[FinParcela, FinContrato]:
    p = (await db.execute(select(FinParcela).where(FinParcela.id == parcela_id, FinParcela.tenant_id == tenant_id))).scalars().first()
    if p is None:
        raise HTTPException(status_code=404, detail="Parcela não encontrada.")
    return p, await _contrato(db, p.contrato_id, tenant_id)


class AjusteIn(BaseModel):
    parcela_id: int
    tipo: str
    valor: float = Field(..., gt=0)
    motivo: str = Field(..., min_length=3, max_length=1000)


@router.post("/contratos/{contrato_id}/ajustes", status_code=201)
async def criar_ajuste(body: AjusteIn, contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                       u=Depends(admin_da_banca)):
    if body.tipo not in fc.TIPOS_AJUSTE:
        raise HTTPException(status_code=400, detail="Tipo de ajuste inválido.")
    c = await _contrato(db, contrato_id, u.tenant_id)
    p, _ = await _parcela(db, body.parcela_id, u.tenant_id)
    if p.contrato_id != c.id:
        raise HTTPException(status_code=400, detail="A parcela é de outro contrato.")
    if p.status in ("paga", "confirmada", "cancelada"):
        raise HTTPException(status_code=409, detail="Parcela já paga: lance o ajuste numa parcela em aberto.")
    a = FinAjuste(tenant_id=u.tenant_id, contrato_id=c.id, parcela_id=p.id, tipo=body.tipo,
                  dados={"valor": round(body.valor, 2), "motivo": body.motivo}, criado_em=datetime.utcnow(), criado_por=u.id)
    db.add(a)
    await db.commit()
    rot = {"desconto": "Desconto", "acrescimo": "Acréscimo", "adiantamento": "Adiantamento"}[body.tipo]
    await notificacoes.notificar(c.professor_id, "sistema", f"{rot} no contrato {c.numero}",
                                 f"{rot} de {fc.moeda(body.valor)} na parcela {p.ordem}: {body.motivo}", "/financeiro",
                                 tenant_id=c.tenant_id)
    return {"id": a.id}


@router.delete("/ajustes/{ajuste_id}")
async def remover_ajuste(ajuste_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    a = (await db.execute(select(FinAjuste).where(FinAjuste.id == ajuste_id, FinAjuste.tenant_id == u.tenant_id))).scalars().first()
    if a is None:
        raise HTTPException(status_code=404, detail="Ajuste não encontrado.")
    p, _ = await _parcela(db, a.parcela_id, u.tenant_id)
    if p.status in ("paga", "confirmada"):
        raise HTTPException(status_code=409, detail="Parcela já paga: o ajuste não pode mais ser removido.")
    await db.delete(a)
    await db.commit()
    return {"ok": True}


class LiberarIn(BaseModel):
    justificativa: str = Field(..., min_length=3, max_length=1000)


@router.post("/parcelas/{parcela_id}/liberar")
async def liberar_parcela(body: LiberarIn, parcela_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                          u=Depends(admin_da_banca)):
    """Liberação manual (gatilho manual, fase de recursos sem recursos, antecipação), sempre com justificativa."""
    p, c = await _parcela(db, parcela_id, u.tenant_id)
    if c.status != "aceito":
        raise HTTPException(status_code=409, detail="O contrato precisa estar aceito pelo professor.")
    if p.status != "prevista":
        raise HTTPException(status_code=409, detail="A parcela já foi liberada.")
    cc = await fc.contrato_completo(db, c, persistir=False)
    ref = cc["totais"]["apurado"] or cc["totais"]["previsto"]
    dp = dict(p.dados or {})
    dp["valor_liberado"] = fc.valor_base_parcela(dp, ref)
    dp["liberacao"] = f"manual por {u.full_name or u.username}: {body.justificativa}"
    p.dados, p.status, p.liberada_em = dp, "liberada", datetime.utcnow()
    await db.commit()
    await notificacoes.notificar(c.professor_id, "sistema", f"Parcela {p.ordem} liberada",
                                 f"A parcela {p.ordem} do contrato {c.numero} foi liberada para pagamento.", "/financeiro",
                                 tenant_id=c.tenant_id)
    return {"ok": True}


@router.post("/parcelas/{parcela_id}/pagar")
async def pagar_parcela(parcela_id: int = Path(...), valor_pago: float = Form(..., gt=0), data_pagamento: date = Form(...),
                        forma: str = Form("", max_length=60), comprovante: UploadFile | None = File(None),
                        db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    """Registra o pagamento (com o comprovante) e gera o recibo; o professor confirma o recebimento."""
    p, c = await _parcela(db, parcela_id, u.tenant_id)
    if p.status != "liberada":
        raise HTTPException(status_code=409, detail="Só uma parcela liberada pode ser paga.")
    agora = datetime.utcnow()
    if comprovante is not None:
        dados, nome = await _ler_arquivo(comprovante)
        db.add(FinDocumento(tenant_id=c.tenant_id, escopo="professor", tipo="comprovante", contrato_id=c.id, parcela_id=p.id,
                            professor_id=c.professor_id, dados={"nome": nome}, arquivo_ref=_guardar(dados, c.tenant_id, nome.rsplit(".", 1)[-1]),
                            sha256=hashlib.sha256(dados).hexdigest(), enviado_por=u.id, enviado_em=agora))
    prof = await _professor_da_banca(db, c.tenant_id, c.professor_id)
    pessoas, eventos = await _nomes(db, c.tenant_id)
    codigo = secrets.token_hex(5).upper()
    recibo = fin_pdf.recibo({
        "banca": await _nome_banca(db, c.tenant_id), "codigo": codigo, "numero_contrato": c.numero, "evento": eventos.get(c.evento_id, ""),
        "professor": {"nome": prof.full_name or prof.username,
                      "cpf": safe_decrypt_pii(prof.cpf) if (prof.tenant_id == c.tenant_id and prof.cpf) else ""},
        "parcela": {"ordem": p.ordem, "descricao": (p.dados or {}).get("descricao", "")}, "valor": valor_pago,
        "data": data_pagamento.strftime("%d/%m/%Y"), "forma": forma})
    db.add(FinDocumento(tenant_id=c.tenant_id, escopo="professor", tipo="recibo", contrato_id=c.id, parcela_id=p.id,
                        professor_id=c.professor_id, dados={"nome": f"recibo-{c.numero}-parcela-{p.ordem}.pdf"},
                        arquivo_ref=_guardar(recibo, c.tenant_id, "pdf"), sha256=hashlib.sha256(recibo).hexdigest(),
                        enviado_por=u.id, enviado_em=agora))
    dp = dict(p.dados or {})
    dp["valor_pago"] = round(valor_pago, 2)
    dp["pagamento"] = {"data": data_pagamento.isoformat(), "forma": forma, "registrado_por": u.full_name or u.username,
                       "codigo_recibo": codigo}
    p.dados, p.status, p.paga_em = dp, "paga", agora
    await db.commit()
    await notificacoes.notificar(c.professor_id, "sistema", f"Pagamento da parcela {p.ordem}",
                                 f"A banca registrou o pagamento de {fc.moeda(valor_pago)} (contrato {c.numero}). Confira e "
                                 "confirme o recebimento em Financeiro.", "/financeiro", tenant_id=c.tenant_id)
    return {"ok": True}


@router.post("/contratos/{contrato_id}/documentos", status_code=201)
async def anexar_documento(contrato_id: int = Path(...), tipo: str = Form("outro"), parcela_id: int | None = Form(None),
                           arquivo: UploadFile = File(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    c = await _contrato(db, contrato_id, u.tenant_id)
    if tipo not in TIPOS_DOC_PROFESSOR:
        raise HTTPException(status_code=400, detail="Tipo de documento inválido.")
    dados, nome = await _ler_arquivo(arquivo)
    d = FinDocumento(tenant_id=c.tenant_id, escopo="professor", tipo=tipo, contrato_id=c.id, parcela_id=parcela_id,
                     professor_id=c.professor_id, dados={"nome": nome}, arquivo_ref=_guardar(dados, c.tenant_id, nome.rsplit(".", 1)[-1]),
                     sha256=hashlib.sha256(dados).hexdigest(), enviado_por=u.id, enviado_em=datetime.utcnow())
    db.add(d)
    await db.commit()
    return {"id": d.id}


@router.get("/documentos/{doc_id}/arquivo")
async def baixar_documento(doc_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    """Banca (administrador) ou o próprio professor do contrato; documentos da plataforma só pelo administrador."""
    d = (await db.execute(select(FinDocumento).where(FinDocumento.id == doc_id,
                                                     FinDocumento.tenant_id == (current_user.tenant_id or -1)))).scalars().first()
    papel = _papel(current_user)
    permitido = d is not None and (
        papel == UserRole.ADMIN.value
        or (papel == UserRole.PROFESSOR.value and d.escopo == "professor" and d.professor_id == current_user.id))
    if not permitido:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return _baixar(secure_files.read_bytes(d.arquivo_ref, d.tenant_id), (d.dados or {}).get("nome") or "documento.pdf")


# =========================================================================================== professor
def _visao_professor(cc: dict) -> dict:
    """O que o professor vê do contrato: tudo dele (inclui a explicação do que falta para cada parcela)."""
    return cc


@router.get("/meu")
async def meu_financeiro(db: AsyncSession = Depends(get_tenant_db), u=Depends(professor)):
    cs = (await db.execute(select(FinContrato).where(FinContrato.tenant_id == u.tenant_id, FinContrato.professor_id == u.id,
                                                     FinContrato.status.in_(["enviado", "aceito", "recusado", "encerrado"]))
                           .order_by(FinContrato.id.desc()))).scalars().all()
    contratos = [_visao_professor(await _detalhe(db, c, para_professor=True)) for c in cs]
    vivos = [c for c in contratos if c["status"] in ("aceito", "encerrado")]
    tot = {k: round(sum(c["totais"][k] for c in vivos), 2) for k in ("previsto", "apurado", "liberado", "pago", "a_receber")}
    return {"contratos": contratos, "totais": tot, "pendentes_aceite": sum(1 for c in contratos if c["status"] == "enviado")}


class SenhaIn(BaseModel):
    senha: str = Field(..., max_length=200)


@router.post("/meu/contratos/{contrato_id}/aceitar", dependencies=[Depends(rate_limit(10, 60, "fin-aceite"))])
async def aceitar_contrato(body: SenhaIn, request: Request, contrato_id: int = Path(...),
                           db: AsyncSession = Depends(get_tenant_db), u=Depends(professor)):
    c = await _contrato(db, contrato_id, u.tenant_id)
    if c.professor_id != u.id:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    if c.status != "enviado":
        raise HTTPException(status_code=409, detail="Este contrato não está aguardando aceite.")
    await _senha_confere(request, u, body.senha, f"fin-aceite:{u.id}")
    pdf = secure_files.read_bytes(c.documento_ref, c.tenant_id)
    sha = hashlib.sha256(pdf).hexdigest()
    if sha != c.documento_sha256:
        raise HTTPException(status_code=409, detail="O documento mudou. Peça à banca para reenviar o contrato.")
    c.aceite = _registro_aceite(request, u, sha, c.codigo_verificacao)
    c.status, c.respondido_em = "aceito", datetime.utcnow()
    await db.commit()
    logger.warning("Contrato %s aceito pelo professor %s", c.id, u.id)
    await _avisar_admins(db, c.tenant_id, f"Contrato {c.numero} aceito",
                         f"{u.full_name or u.username} aceitou o contrato {c.numero}.")
    return {"ok": True}


@router.post("/meu/contratos/{contrato_id}/recusar")
async def recusar_contrato(body: MotivoIn, contrato_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(professor)):
    c = await _contrato(db, contrato_id, u.tenant_id)
    if c.professor_id != u.id or c.status != "enviado":
        raise HTTPException(status_code=409, detail="Este contrato não está aguardando resposta.")
    c.status, c.respondido_em = "recusado", datetime.utcnow()
    c.dados = {**(c.dados or {}), "motivo_recusa": body.motivo}
    await db.commit()
    await _avisar_admins(db, c.tenant_id, f"Contrato {c.numero} recusado",
                         f"{u.full_name or u.username} recusou o contrato {c.numero}: {body.motivo or 'sem motivo informado'}.")
    return {"ok": True}


@router.post("/meu/parcelas/{parcela_id}/nota-fiscal", status_code=201)
async def enviar_nota(parcela_id: int = Path(...), tipo: str = Form("nota_fiscal"), arquivo: UploadFile = File(...),
                      db: AsyncSession = Depends(get_tenant_db), u=Depends(professor)):
    p, c = await _parcela(db, parcela_id, u.tenant_id)
    if c.professor_id != u.id:
        raise HTTPException(status_code=404, detail="Parcela não encontrada.")
    if tipo not in ("nota_fiscal", "rpa", "outro"):
        raise HTTPException(status_code=400, detail="Tipo inválido.")
    dados, nome = await _ler_arquivo(arquivo)
    db.add(FinDocumento(tenant_id=c.tenant_id, escopo="professor", tipo=tipo, contrato_id=c.id, parcela_id=p.id, professor_id=u.id,
                        dados={"nome": nome}, arquivo_ref=_guardar(dados, c.tenant_id, nome.rsplit(".", 1)[-1]),
                        sha256=hashlib.sha256(dados).hexdigest(), enviado_por=u.id, enviado_em=datetime.utcnow()))
    await db.commit()
    await _avisar_admins(db, c.tenant_id, f"{TIPOS_DOC_PROFESSOR[tipo]} recebido(a)",
                         f"{u.full_name or u.username} enviou {TIPOS_DOC_PROFESSOR[tipo].lower()} da parcela {p.ordem} do contrato {c.numero}.")
    return {"ok": True}


@router.post("/meu/parcelas/{parcela_id}/confirmar")
async def confirmar_recebimento(parcela_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(professor)):
    p, c = await _parcela(db, parcela_id, u.tenant_id)
    if c.professor_id != u.id:
        raise HTTPException(status_code=404, detail="Parcela não encontrada.")
    if p.status != "paga":
        raise HTTPException(status_code=409, detail="Só um pagamento registrado pode ser confirmado.")
    p.status, p.confirmada_em = "confirmada", datetime.utcnow()
    await db.commit()
    return {"ok": True}


# =========================================================================================== banca x plataforma
def _estado_fatura(f: FinFatura) -> str:
    if f.status == "aberta" and f.vencimento < date.today():
        return "atrasada"
    return f.status


def saida_fatura(f: FinFatura) -> dict:
    d = f.dados or {}
    return {"id": f.id, "numero": f.numero, "competencia": f.competencia, "vencimento": f.vencimento.isoformat(),
            "status": _estado_fatura(f), "valor": fc.num(d.get("valor")), "descricao": d.get("descricao", ""),
            "observacoes": d.get("observacoes", ""), "motivo_devolucao": d.get("motivo_devolucao", ""),
            "informada_em": fc._iso(f.informada_em), "paga_em": fc._iso(f.paga_em)}


def saida_proposta(p: FinProposta) -> dict:
    d = p.dados or {}
    return {"id": p.id, "numero": p.numero, "versao": p.versao, "status": p.status, "validade": p.validade.isoformat() if p.validade else None,
            "expirada": bool(p.validade and p.validade < date.today() and p.status == "enviada"),
            "plano": d.get("plano", ""), "periodicidade": d.get("periodicidade", ""), "valor": fc.num(d.get("valor")),
            "desconto": fc.num(d.get("desconto")), "valor_final": fc.num(d.get("valor_final")), "condicoes": d.get("condicoes", ""),
            "itens": d.get("itens", []), "motivo_recusa": d.get("motivo_recusa", ""), "aceite": p.aceite,
            "criado_em": fc._iso(p.criado_em), "respondido_em": fc._iso(p.respondido_em)}


def saida_termo(t: FinTermo) -> dict:
    d = t.dados or {}
    return {"id": t.id, "tipo": t.tipo, "titulo": d.get("titulo", ""), "descricao": d.get("descricao", ""), "status": t.status,
            "aceite": t.aceite, "motivo_recusa": d.get("motivo_recusa", ""), "criado_em": fc._iso(t.criado_em),
            "respondido_em": fc._iso(t.respondido_em), "sha256": t.documento_sha256}


def saida_doc_plataforma(d: FinDocumento) -> dict:
    return {"id": d.id, "tipo": d.tipo, "nome": (d.dados or {}).get("nome", ""), "descricao": (d.dados or {}).get("descricao", ""),
            "enviado_em": fc._iso(d.enviado_em), "referencia_id": d.referencia_id}


async def _plano_atual(tenant_id: int) -> dict:
    async with PlatformSessionLocal() as pdb:
        t = (await pdb.execute(select(Tenant).where(Tenant.id == tenant_id))).scalars().first()
    return {"plano": (t.plan_type if t else None) or "", "vence_em": t.plan_expires_at.date().isoformat() if t and t.plan_expires_at else None,
            "situacao": t.status if t else ""}


@router.get("/plataforma")
async def minha_relacao_com_a_plataforma(db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    t = u.tenant_id
    propostas = (await db.execute(select(FinProposta).where(FinProposta.tenant_id == t).order_by(FinProposta.id.desc()))).scalars().all()
    termos = (await db.execute(select(FinTermo).where(FinTermo.tenant_id == t, FinTermo.status != "cancelado")
                               .order_by(FinTermo.id.desc()))).scalars().all()
    faturas = (await db.execute(select(FinFatura).where(FinFatura.tenant_id == t, FinFatura.status != "cancelada")
                                .order_by(FinFatura.vencimento.desc()))).scalars().all()
    docs = (await db.execute(select(FinDocumento).where(FinDocumento.tenant_id == t, FinDocumento.escopo == "plataforma")
                             .order_by(FinDocumento.id.desc()))).scalars().all()
    return {"plano": await _plano_atual(t), "propostas": [saida_proposta(p) for p in propostas if p.status != "cancelada"],
            "termos": [saida_termo(x) for x in termos], "faturas": [saida_fatura(f) for f in faturas],
            "documentos": [saida_doc_plataforma(d) for d in docs]}


async def _avisar_plataforma(titulo: str, msg: str) -> None:
    async with PlatformSessionLocal() as pdb:
        ids = [x.id for x in (await pdb.execute(select(User).where(User.tenant_id.is_(None), User.role == UserRole.ADMIN_GERAL.value,
                                                                     User.is_active.is_(True)))).scalars()]
    await notificacoes.notificar_varios(ids, "sistema", titulo, msg, "/financeiro")


@router.post("/plataforma/propostas/{proposta_id}/aceitar", dependencies=[Depends(rate_limit(10, 60, "fin-aceite"))])
async def aceitar_proposta(body: SenhaIn, request: Request, proposta_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                           u=Depends(admin_da_banca)):
    p = (await db.execute(select(FinProposta).where(FinProposta.id == proposta_id, FinProposta.tenant_id == u.tenant_id))).scalars().first()
    if p is None or p.status != "enviada":
        raise HTTPException(status_code=409, detail="Esta proposta não está aguardando resposta.")
    if p.validade and p.validade < date.today():
        raise HTTPException(status_code=409, detail="A proposta venceu. Peça uma nova à plataforma.")
    await _senha_confere(request, u, body.senha, f"fin-aceite:{u.id}")
    sha = hashlib.sha256(secure_files.read_bytes(p.documento_ref, p.tenant_id)).hexdigest() if p.documento_ref else None
    p.aceite, p.status, p.respondido_em = _registro_aceite(request, u, sha, p.numero), "aceita", datetime.utcnow()
    d = p.dados or {}
    await db.commit()
    # o plano da banca passa a ser o da proposta aceita (tabela de clientes = plataforma)
    meses = 12 if d.get("periodicidade") == "anual" else 1
    async with PlatformSessionLocal() as pdb:
        t = (await pdb.execute(select(Tenant).where(Tenant.id == u.tenant_id))).scalars().first()
        if t:
            t.plan_type = (d.get("plano") or "")[:100]
            t.plan_expires_at = datetime.utcnow() + timedelta(days=31 * meses)
            await pdb.commit()
    await _avisar_plataforma("Proposta aceita", f"A banca aceitou a proposta {p.numero} (v{p.versao}).")
    return {"ok": True}


@router.post("/plataforma/propostas/{proposta_id}/recusar")
async def recusar_proposta(body: MotivoIn, proposta_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    p = (await db.execute(select(FinProposta).where(FinProposta.id == proposta_id, FinProposta.tenant_id == u.tenant_id))).scalars().first()
    if p is None or p.status != "enviada":
        raise HTTPException(status_code=409, detail="Esta proposta não está aguardando resposta.")
    p.status, p.respondido_em = "recusada", datetime.utcnow()
    p.dados = {**(p.dados or {}), "motivo_recusa": body.motivo}
    await db.commit()
    await _avisar_plataforma("Proposta recusada", f"A banca recusou a proposta {p.numero} (v{p.versao}): {body.motivo or 'sem motivo'}.")
    return {"ok": True}


@router.post("/plataforma/termos/{termo_id}/aceitar", dependencies=[Depends(rate_limit(10, 60, "fin-aceite"))])
async def aceitar_termo(body: SenhaIn, request: Request, termo_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db),
                        u=Depends(admin_da_banca)):
    t = (await db.execute(select(FinTermo).where(FinTermo.id == termo_id, FinTermo.tenant_id == u.tenant_id))).scalars().first()
    if t is None or t.status != "pendente":
        raise HTTPException(status_code=409, detail="Este documento não está aguardando aceite.")
    await _senha_confere(request, u, body.senha, f"fin-aceite:{u.id}")
    sha = hashlib.sha256(secure_files.read_bytes(t.documento_ref, t.tenant_id)).hexdigest()
    if sha != t.documento_sha256:
        raise HTTPException(status_code=409, detail="O documento mudou. Peça à plataforma para reenviar.")
    t.aceite, t.status, t.respondido_em = _registro_aceite(request, u, sha, f"T{t.id}"), "aceito", datetime.utcnow()
    await db.commit()
    await _avisar_plataforma("Documento aceito pela banca", f"A banca aceitou: {(t.dados or {}).get('titulo', '')}.")
    return {"ok": True}


@router.post("/plataforma/termos/{termo_id}/recusar")
async def recusar_termo(body: MotivoIn, termo_id: int = Path(...), db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    t = (await db.execute(select(FinTermo).where(FinTermo.id == termo_id, FinTermo.tenant_id == u.tenant_id))).scalars().first()
    if t is None or t.status != "pendente":
        raise HTTPException(status_code=409, detail="Este documento não está aguardando resposta.")
    t.status, t.respondido_em = "recusado", datetime.utcnow()
    t.dados = {**(t.dados or {}), "motivo_recusa": body.motivo}
    await db.commit()
    await _avisar_plataforma("Documento recusado pela banca", f"{(t.dados or {}).get('titulo', '')}: {body.motivo or 'sem motivo'}.")
    return {"ok": True}


@router.post("/plataforma/faturas/{fatura_id}/comprovante")
async def informar_pagamento(fatura_id: int = Path(...), arquivo: UploadFile = File(...), db: AsyncSession = Depends(get_tenant_db),
                             u=Depends(admin_da_banca)):
    f = (await db.execute(select(FinFatura).where(FinFatura.id == fatura_id, FinFatura.tenant_id == u.tenant_id))).scalars().first()
    if f is None or f.status != "aberta":
        raise HTTPException(status_code=409, detail="Esta fatura não está em aberto.")
    dados, nome = await _ler_arquivo(arquivo)
    db.add(FinDocumento(tenant_id=f.tenant_id, escopo="plataforma", tipo="comprovante", referencia_id=f.id, dados={"nome": nome},
                        arquivo_ref=_guardar(dados, f.tenant_id, nome.rsplit(".", 1)[-1]), sha256=hashlib.sha256(dados).hexdigest(),
                        enviado_por=u.id, enviado_em=datetime.utcnow()))
    f.status, f.informada_em = "em_analise", datetime.utcnow()
    await db.commit()
    await _avisar_plataforma("Comprovante de fatura recebido", f"A banca enviou o comprovante da fatura {f.numero}.")
    return {"ok": True}


@router.get("/plataforma/arquivo/{tipo}/{item_id}")
async def baixar_da_plataforma(tipo: str, item_id: int, db: AsyncSession = Depends(get_tenant_db), u=Depends(admin_da_banca)):
    if tipo == "proposta":
        x = (await db.execute(select(FinProposta).where(FinProposta.id == item_id, FinProposta.tenant_id == u.tenant_id))).scalars().first()
        if x and x.documento_ref:
            return _baixar(secure_files.read_bytes(x.documento_ref, x.tenant_id), f"proposta-{x.numero}-v{x.versao}.pdf")
    elif tipo == "termo":
        x = (await db.execute(select(FinTermo).where(FinTermo.id == item_id, FinTermo.tenant_id == u.tenant_id))).scalars().first()
        if x:
            return _baixar(secure_files.read_bytes(x.documento_ref, x.tenant_id), f"{x.tipo}-{x.id}.pdf")
    elif tipo == "documento":
        x = (await db.execute(select(FinDocumento).where(FinDocumento.id == item_id, FinDocumento.tenant_id == u.tenant_id,
                                                         FinDocumento.escopo == "plataforma"))).scalars().first()
        if x:
            return _baixar(secure_files.read_bytes(x.arquivo_ref, x.tenant_id), (x.dados or {}).get("nome") or "documento.pdf")
    raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
