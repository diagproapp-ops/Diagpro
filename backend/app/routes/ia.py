# backend/app/routes/ia.py
"""Assistente de IA: rascunhos e revisões a pedido do usuário. Regras de sigilo em backend/app/assistente_ia.py."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import assistente_ia, configuracoes, equacoes
from backend.app.auth import get_current_user
from backend.app.db_models import UsoIA, User
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.security import get_tenant_db, require_roles

router = APIRouter(prefix="/ia", tags=["Assistente de IA"])

# diagramador não elabora conteúdo; os demais perfis usam a IA da banca
_QUEM_USA = require_roles(UserRole.PROFESSOR, UserRole.REVISOR, UserRole.ADMIN, UserRole.ADMIN_GERAL)
_LIMITE_MINUTO = Depends(rate_limit(20, 60, "ia"))

Tipo = Literal["MULTIPLA_ESCOLHA", "CERTO_ERRADO", "DISCURSIVA", "SUBJETIVA"]
Nivel = Literal["MUITO_FACIL", "FACIL", "MEDIO", "DIFICIL", "MUITO_DIFICIL"]


class Alternativa(BaseModel):
    letra: str = Field("", max_length=3)
    texto: str = Field("", max_length=20000)


class ItemCE(BaseModel):
    afirmacao: str = Field("", max_length=20000)
    certo: Optional[bool] = None


class QuestaoIA(BaseModel):
    tipo: Tipo = "MULTIPLA_ESCOLHA"
    assunto: str = Field("", max_length=500)
    nivel: Optional[Nivel] = None
    enunciado: str = Field(..., min_length=1, max_length=60000)
    alternativas: list[Alternativa] = Field(default_factory=list, max_length=10)
    correta: str = Field("", max_length=3)
    itens: list[ItemCE] = Field(default_factory=list, max_length=20)
    padrao_resposta: str = Field("", max_length=20000)


class GerarQuestaoIn(BaseModel):
    tipo: Tipo
    assunto: str = Field(..., min_length=2, max_length=500)
    disciplina: str = Field("", max_length=200)
    nivel: Nivel = "MEDIO"
    instrucoes: str = Field("", max_length=4000)
    texto_base: str = Field("", max_length=60000)
    num_alternativas: int = Field(5, ge=2, le=6)
    quantidade_itens: int = Field(1, ge=1, le=10)


class AlternativasIn(QuestaoIA):
    quantidade: int = Field(4, ge=1, le=6)


class MelhorarTextoIn(BaseModel):
    texto: str = Field(..., min_length=1, max_length=60000)
    modo: Literal["revisar_portugues", "clareza", "simplificar", "formalizar"] = "revisar_portugues"


class EquacaoIn(BaseModel):
    descricao: str = Field(..., min_length=1, max_length=1000)
    latex_atual: str = Field("", max_length=4000)


class ChatIn(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=2000)
    contexto: str = Field("", max_length=60000)


@router.get("/status")
async def status_ia(db: AsyncSession = Depends(get_tenant_db), current_user=Depends(get_current_user)):
    """O que a tela precisa para mostrar (ou esconder) os botões de IA. Não revela chaves."""
    plataforma = await configuracoes.ler_plataforma()
    ia_p = plataforma["ia"]
    role = current_user.role.value if isinstance(current_user.role, UserRole) else current_user.role
    base = {"disponivel": False, "recursos": dict.fromkeys(configuracoes.RECURSOS_IA, False),
            "provedor": ia_p["provedor"], "motivo": ""}
    if not ia_p["habilitada"]:
        return {**base, "motivo": "O assistente de IA está desligado na plataforma."}
    if current_user.tenant_id is None:
        return {**base, "motivo": "Escolha um cliente para usar a IA."}
    if role == UserRole.DIAGRAMADOR.value:
        return {**base, "motivo": "O perfil diagramador não usa o assistente de IA."}
    ia_b = (await configuracoes.ler_banca(db, current_user.tenant_id))["ia"]
    if not ia_b["habilitada"]:
        return {**base, "motivo": "O assistente de IA não está ligado para esta banca."}
    if not configuracoes.chave_do_provedor(plataforma, ia_p["provedor"]):
        return {**base, "motivo": "A chave do provedor de IA não foi configurada."}
    return {**base, "disponivel": True, "recursos": ia_b["recursos"]}


@router.post("/questao/gerar", dependencies=[_LIMITE_MINUTO])
async def gerar_questao(dados: GerarQuestaoIn, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_USA)):
    return await assistente_ia.executar(db, current_user, "gerar_questao", dados.model_dump())


@router.post("/questao/revisar", dependencies=[_LIMITE_MINUTO])
async def revisar_questao(dados: QuestaoIA, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_USA)):
    return await assistente_ia.executar(db, current_user, "revisar_questao", dados.model_dump())


@router.post("/questao/alternativas", dependencies=[_LIMITE_MINUTO])
async def sugerir_alternativas(dados: AlternativasIn, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_USA)):
    return await assistente_ia.executar(db, current_user, "alternativas", dados.model_dump())


@router.post("/questao/justificativa", dependencies=[_LIMITE_MINUTO])
async def justificar(dados: QuestaoIA, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_USA)):
    return await assistente_ia.executar(db, current_user, "justificativa", dados.model_dump())


@router.post("/texto/melhorar", dependencies=[_LIMITE_MINUTO])
async def melhorar_texto(dados: MelhorarTextoIn, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_USA)):
    return await assistente_ia.executar(db, current_user, "melhorar_texto", dados.model_dump())


@router.post("/equacao", dependencies=[_LIMITE_MINUTO])
async def criar_equacao(dados: EquacaoIn, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_USA)):
    """Equação a partir de uma descrição. O LaTeX devolvido já vem conferido pela mesma conversão da prova."""
    resposta = await assistente_ia.executar(db, current_user, "equacao", dados.model_dump())
    latex = str(resposta.get("latex") or "").strip()
    return {"latex": latex, "explicacao": str(resposta.get("explicacao") or ""), "erro": equacoes.validar(latex)}


@router.post("/chat", dependencies=[_LIMITE_MINUTO])
async def chat(dados: ChatIn, db: AsyncSession = Depends(get_tenant_db), current_user=Depends(_QUEM_USA)):
    return await assistente_ia.executar(db, current_user, "chat", dados.model_dump())


class TesteIn(BaseModel):
    provedor: Optional[Literal["anthropic", "openai"]] = None


@router.post("/testar", dependencies=[Depends(rate_limit(5, 60, "ia-teste"))])
async def testar_conexao(dados: TesteIn, current_user=Depends(require_roles(UserRole.ADMIN_GERAL))):
    """Admin geral: confere chave e modelo com um pedido mínimo (não envia nenhum conteúdo)."""
    plataforma = await configuracoes.ler_plataforma(forcar=True)
    provedor = dados.provedor or plataforma["ia"]["provedor"]
    modelo = plataforma["ia"][f"modelo_{provedor}"]
    chave = configuracoes.chave_do_provedor(plataforma, provedor)
    if not chave:
        raise HTTPException(status_code=400, detail="Nenhuma chave configurada para este provedor.")
    pedido, max_tokens = assistente_ia.montar_pedido("teste", {})
    try:
        resp = await assistente_ia.chamar_provedor(provedor, modelo, chave, "Responda apenas no formato pedido.",
                                                   pedido, assistente_ia.SCHEMAS["teste"], max_tokens)
    except assistente_ia.ErroIA as exc:
        await assistente_ia.registrar_uso(None, current_user, "teste", provedor, modelo, None, exc.mensagem)
        raise HTTPException(status_code=exc.status, detail=exc.mensagem)
    await assistente_ia.registrar_uso(None, current_user, "teste", provedor, modelo, resp, None)
    return {"ok": True, "provedor": provedor, "modelo": modelo,
            "tokens": resp.tokens_entrada + resp.tokens_saida}


@router.get("/uso")
async def uso_da_banca(
    dias: int = 30,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL)),
):
    """Resumo do uso da IA pela banca (sem nenhum texto): por recurso, por pessoa e por dia."""
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Escolha um cliente no topo da tela.")
    dias = max(1, min(dias, 90))
    desde = datetime.now() - timedelta(days=dias)
    linhas = (await db.execute(select(UsoIA).where(UsoIA.tenant_id == current_user.tenant_id, UsoIA.criado_em >= desde))).scalars().all()
    ids = {l.usuario_id for l in linhas}
    nomes = {}
    if ids:
        for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all():
            nomes[u.id] = u.username
    por_recurso, por_usuario, por_dia = defaultdict(int), defaultdict(int), defaultdict(int)
    tokens_e = tokens_s = falhas = 0
    for l in linhas:
        det = l.detalhes if isinstance(l.detalhes, dict) else {}
        por_recurso[det.get("recurso", "?")] += 1
        por_usuario[nomes.get(l.usuario_id, f"usuário {l.usuario_id}")] += 1
        por_dia[l.criado_em.date().isoformat()] += 1
        tokens_e += l.tokens_entrada or 0
        tokens_s += l.tokens_saida or 0
        falhas += 0 if l.sucesso else 1
    return {
        "dias": dias, "total": len(linhas), "falhas": falhas,
        "tokens_entrada": tokens_e, "tokens_saida": tokens_s,
        "por_recurso": dict(por_recurso),
        "por_usuario": sorted(({"usuario": k, "usos": v} for k, v in por_usuario.items()), key=lambda x: -x["usos"]),
        "por_dia": dict(sorted(por_dia.items())),
    }
