# backend/app/routes/recursos.py
"""Recursos dos candidatos: cadastro/importação, parecer, decisão por questão e gabarito definitivo."""
import csv
import io
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import fluxo_revisao, notificacoes, recursos as rc
from backend.app.auth import get_current_user
from backend.app.db_models import DecisaoRecurso, OpcoesQuestao, QuestoesBanco, Recurso, User
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.routes.estatisticas import _gabaritos
from backend.app.security import evento_autorizado, evento_com_senha, get_tenant_db, require_roles

router = APIRouter(prefix="/recursos", tags=["Recursos"])
_ADMINS = require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL)


def _texto(html_ou_texto) -> str:
    import html
    import re
    t = html.unescape(re.sub(r"<[^>]+>", " ", str(html_ou_texto or "")))
    return " ".join(t.split())


class RecursoIn(BaseModel):
    cargo_id: str = Field(..., max_length=64)
    tipo_prova: str = Field(..., max_length=30)
    numero_questao: int = Field(..., ge=1, le=1000)
    pedido: Literal["anulacao", "alteracao", "outro"] = "anulacao"
    protocolo: str = Field("", max_length=60)
    argumentacao: str = Field("", max_length=20000)


async def _criar(db, evento, user, gabs_cargo: dict, dados: RecursoIn) -> Recurso:
    var, entrada = rc.localizar(gabs_cargo, dados.tipo_prova, dados.numero_questao)
    r = Recurso(tenant_id=evento.tenant_id, evento_id=evento.id_evento, cargo_id=dados.cargo_id, tipo_prova=var,
                numero_questao=dados.numero_questao, id_questao=entrada["id_questao"], item=entrada.get("item"),
                pedido=dados.pedido, status="pendente", criado_em=datetime.utcnow(), criado_por=user.id,
                protocolo=dados.protocolo.strip() or None, argumentacao=dados.argumentacao.strip() or None)
    db.add(r)
    return r


@router.post("/eventos/{evento_id}", dependencies=[Depends(rate_limit(60, 60, "recurso"))])
async def cadastrar(evento_id: str, dados: RecursoIn, db: AsyncSession = Depends(get_tenant_db),
                    evento=Depends(evento_com_senha), current_user=Depends(_ADMINS)):
    _, gabs = await _gabaritos(db, evento, dados.cargo_id)
    try:
        r = await _criar(db, evento, current_user, gabs, dados)
    except rc.ErroRecurso as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"id": r.id, "id_questao": r.id_questao, "item": r.item, "tipo_prova": r.tipo_prova}


@router.post("/eventos/{evento_id}/importar", dependencies=[Depends(rate_limit(5, 300, "recurso-importar"))])
async def importar(evento_id: str, arquivo: UploadFile = File(...), db: AsyncSession = Depends(get_tenant_db),
                   evento=Depends(evento_com_senha), current_user=Depends(_ADMINS)):
    """CSV: cargo (código ou nome), tipo_prova, questao, pedido, protocolo, argumentacao. Outras colunas são ignoradas."""
    bruto = await arquivo.read(10 * 1024 * 1024 + 1)
    if len(bruto) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo maior que 10 MB.")
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    delim = ";" if texto[:2000].count(";") >= texto[:2000].count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delim)
    campos = {(c or "").strip().lower(): c for c in (leitor.fieldnames or [])}
    if not {"cargo", "tipo_prova", "questao"} <= set(campos):
        raise HTTPException(status_code=400, detail="O arquivo precisa das colunas cargo, tipo_prova e questao.")
    gabs_evento = await rc.gabaritos_do_evento(db, evento, _gabaritos)
    por_nome = {}
    for cid, info in gabs_evento.items():
        c = info["cargo"]
        for k in (c.codigo_cargo, c.nome_cargo, f"{c.codigo_cargo} - {c.nome_cargo}"):
            if k:
                por_nome[str(k).strip().upper()] = cid
    criados, problemas = 0, []
    for n, linha in enumerate(leitor, start=2):
        g = lambda k: (linha.get(campos.get(k, ""), "") or "").strip()  # noqa: E731
        cid = por_nome.get(g("cargo").upper())
        if not cid:
            problemas.append(f"Linha {n}: cargo '{g('cargo')[:40]}' não encontrado ou sem prova montada.")
            continue
        pedido = g("pedido").lower() or "anulacao"
        pedido = {"anulação": "anulacao", "alteração": "alteracao"}.get(pedido, pedido)
        try:
            dados = RecursoIn(cargo_id=cid, tipo_prova=g("tipo_prova"), numero_questao=int(g("questao") or 0),
                              pedido=pedido if pedido in rc.PEDIDOS else "outro", protocolo=g("protocolo")[:60],
                              argumentacao=g("argumentacao")[:20000])
            await _criar(db, evento, current_user, gabs_evento[cid]["gabaritos"], dados)
            criados += 1
        except (rc.ErroRecurso, ValueError) as exc:
            problemas.append(f"Linha {n}: {str(exc)[:150]}")
        if n > 50000:
            break
    await db.commit()
    return {"importados": criados, "problemas": problemas[:50], "total_problemas": len(problemas)}


@router.get("/eventos/{evento_id}")
async def listar(evento_id: str, db: AsyncSession = Depends(get_tenant_db), evento=Depends(evento_autorizado),
                 current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.REVISOR))):
    """Recursos agrupados por questão (e item), com a decisão já tomada."""
    lista = (await db.execute(select(Recurso).where(Recurso.evento_id == evento.id_evento).order_by(Recurso.id))).scalars().all()
    decisoes = await rc.decisoes_do_evento(db, evento.id_evento)
    ids = {r.id_questao for r in lista}
    questoes = {q.id_questao: q for q in (await db.execute(select(QuestoesBanco).where(QuestoesBanco.id_questao.in_(ids)))).scalars()} if ids else {}
    opcoes = {}
    if ids:
        for o in (await db.execute(select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk.in_(ids)))).scalars():
            opcoes.setdefault(o.id_questao_fk, []).append(o)
    nomes = {u.id: u.username for u in (await db.execute(select(User).where(User.tenant_id == evento.tenant_id))).scalars()}
    grupos = {}
    for r in lista:
        k = (r.id_questao, r.item)
        if k not in grupos:
            q = questoes.get(r.id_questao)
            d = decisoes.get(k)
            grupos[k] = {
                "id_questao": r.id_questao, "item": r.item, "codigo": q.codigo_curto_questao if q else None,
                "tipo": q.tipo if q else None, "enunciado": _texto(q.enunciado)[:600] if q else "",
                "alternativas": [{"letra": o.letra, "texto": _texto(o.texto_opcao)[:300], "correta": str(o.correta).strip().lower() in ("true", "1", "sim")}
                                 for o in sorted(opcoes.get(r.id_questao, []), key=lambda o: o.letra or "")],
                "decisao": None if d is None else {"decisao": d.decisao, "nova_correta": d.nova_correta,
                                                    "justificativa": d.justificativa, "em": d.decidido_em.isoformat() + "Z",
                                                    "por": nomes.get(d.decidido_por)},
                "recursos": [],
            }
        grupos[k]["recursos"].append({"id": r.id, "cargo_id": r.cargo_id, "tipo_prova": r.tipo_prova, "numero": r.numero_questao,
                                      "pedido": r.pedido, "status": r.status, "protocolo": r.protocolo,
                                      "argumentacao": r.argumentacao, "parecer": r.parecer, "parecer_por": nomes.get(r.parecer_por)})
    itens = sorted(grupos.values(), key=lambda g: (g["decisao"] is not None, -len(g["recursos"])))
    return {"total_recursos": len(lista), "questoes": itens}


class ParecerIn(BaseModel):
    parecer: str = Field(..., min_length=1, max_length=20000)


@router.put("/{recurso_id}/parecer")
async def dar_parecer(recurso_id: int, dados: ParecerIn, db: AsyncSession = Depends(get_tenant_db),
                      current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.REVISOR, UserRole.PROFESSOR))):
    r = (await db.execute(select(Recurso).where(Recurso.id == recurso_id))).scalar_one_or_none()  # RLS: só da banca
    if r is None:
        raise HTTPException(status_code=404, detail="Recurso não encontrado.")
    role = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    if role == UserRole.PROFESSOR.value:
        q = (await db.execute(select(QuestoesBanco).where(QuestoesBanco.id_questao == r.id_questao))).scalar_one_or_none()
        if q is None or await fluxo_revisao.autor_id(db, q) != current_user.id:
            raise HTTPException(status_code=403, detail="Só quem elaborou a questão pode dar parecer.")
    r.parecer, r.parecer_por = dados.parecer.strip(), current_user.id
    await db.commit()
    return {"ok": True}


class DecisaoIn(BaseModel):
    item: Optional[int] = Field(None, ge=1, le=50)
    decisao: Literal["manter", "anular", "alterar"]
    nova_correta: Optional[str] = Field(None, max_length=1)
    justificativa: str = Field(..., min_length=5, max_length=20000)


@router.post("/eventos/{evento_id}/questoes/{id_questao}/decidir")
async def decidir(evento_id: str, id_questao: str, dados: DecisaoIn, db: AsyncSession = Depends(get_tenant_db),
                  evento=Depends(evento_autorizado), current_user=Depends(_ADMINS)):
    q = (await db.execute(select(QuestoesBanco).where(QuestoesBanco.id_questao == id_questao,
                                                      QuestoesBanco.id_evento_fk == evento.id_evento))).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Questão não encontrada neste evento.")
    nova = (dados.nova_correta or "").upper() or None
    if dados.decisao == "alterar":
        validas = ("C", "E") if (q.tipo or "").upper() == "CERTO_ERRADO" else ("A", "B", "C", "D", "E", "F")
        if nova not in validas:
            raise HTTPException(status_code=400, detail=f"Informe a nova resposta correta ({', '.join(validas)}).")
    else:
        nova = None
    d = (await db.execute(select(DecisaoRecurso).where(DecisaoRecurso.evento_id == evento.id_evento, DecisaoRecurso.id_questao == id_questao,
                                                       (DecisaoRecurso.item == dados.item) if dados.item else DecisaoRecurso.item.is_(None)))).scalar_one_or_none()
    if d is None:
        d = DecisaoRecurso(tenant_id=evento.tenant_id, evento_id=evento.id_evento, id_questao=id_questao, item=dados.item)
        db.add(d)
    d.decisao, d.nova_correta, d.justificativa = dados.decisao, nova, dados.justificativa.strip()
    d.decidido_em, d.decidido_por = datetime.utcnow(), current_user.id
    novo_status = "indeferido" if dados.decisao == "manter" else "deferido"
    for r in (await db.execute(select(Recurso).where(Recurso.evento_id == evento.id_evento, Recurso.id_questao == id_questao,
                                                     (Recurso.item == dados.item) if dados.item else Recurso.item.is_(None)))).scalars():
        r.status = novo_status
    await db.commit()
    autor = await fluxo_revisao.autor_id(db, q)
    if autor:
        texto = {"manter": "gabarito mantido", "anular": "questão anulada", "alterar": f"gabarito alterado para {nova}"}[dados.decisao]
        await notificacoes.notificar(autor, "sistema", f"Recursos da questão {q.codigo_curto_questao or ''} decididos",
                                     f"Decisão: {texto}.", f"/eventos/{evento.id_evento}/candidatos/recursos")
    return {"ok": True, "status_recursos": novo_status}


@router.get("/eventos/{evento_id}/gabarito-definitivo")
async def gabarito_definitivo(evento_id: str, db: AsyncSession = Depends(get_tenant_db), evento=Depends(evento_com_senha),
                              current_user=Depends(_ADMINS)):
    """Preliminar x definitivo por cargo e caderno (a prova aplicada nunca muda)."""
    gabs_evento = await rc.gabaritos_do_evento(db, evento, _gabaritos)
    decisoes = await rc.decisoes_do_evento(db, evento.id_evento)
    saida = []
    for cid, info in gabs_evento.items():
        c = info["cargo"]
        for var, entradas in info["gabaritos"].items():
            linhas = []
            for e in sorted(entradas, key=lambda x: int(x.get("numero_questao_exibido") or 0)):
                letra, aviso = rc.definitivo(e, decisoes)
                linhas.append({"numero": e.get("numero_questao_exibido"), "codigo": e.get("codigo_curto_questao"),
                               "preliminar": e.get("gabarito_letra_exibida"), "definitivo": letra,
                               "alterada": letra != e.get("gabarito_letra_exibida"), "aviso": aviso})
            saida.append({"cargo_id": cid, "cargo": f"{c.codigo_cargo or ''} {c.nome_cargo or ''}".strip(), "tipo_prova": var, "questoes": linhas})
    return saida
