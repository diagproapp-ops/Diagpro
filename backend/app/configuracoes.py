# backend/app/configuracoes.py
"""
Configurações em dois escopos guardados (o terceiro, "pessoal", é a página Minha conta):

- PLATAFORMA (tenant_id nulo, só admin geral): política de senha e sessão para todos.
- BANCA (por cliente, RLS): sessão mais curta, identidade da prova, regras das questões.

Os padrões reproduzem o comportamento anterior; a validação impõe limites seguros (ninguém consegue,
por exemplo, baixar a senha mínima para 4 caracteres). Tudo é cifrado no banco.
"""
import copy
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Configuracao
from core.instrucoes_padrao import INSTRUCOES_DISCURSIVA, INSTRUCOES_POR_BLOCO

TIPOS_QUESTAO = ["MULTIPLA_ESCOLHA", "CERTO_ERRADO", "DISCURSIVA", "SUBJETIVA"]

PADRAO_PLATAFORMA = {
    "seguranca": {
        "senha_tamanho_minimo": 12,
        "senha_tipos_minimos": 3,
        "senha_historico": 5,
        "senha_validade_dias": 180,
        "sessao_inatividade_minutos": 30,
        "sessao_maxima_horas": 12,
    },
}

PADRAO_BANCA = {
    "seguranca": {
        "sessao_inatividade_minutos": None,  # None = usa o da plataforma; só pode ser MAIS curto
    },
    "identidade_prova": {
        "instrucoes_por_bloco": INSTRUCOES_POR_BLOCO,
        "instrucoes_discursiva": INSTRUCOES_DISCURSIVA,
    },
    "regras_questoes": {
        "tipos_permitidos": TIPOS_QUESTAO,
        "revisao_obrigatoria": False,
    },
}

_LIMITES_PLATAFORMA = {
    "senha_tamanho_minimo": (8, 64),
    "senha_tipos_minimos": (2, 4),
    "senha_historico": (1, 24),
    "senha_validade_dias": (30, 730),
    "sessao_inatividade_minutos": (5, 240),
    "sessao_maxima_horas": (1, 24),
}

_CACHE_PLATAFORMA: dict = {"em": 0.0, "dados": None}
_CACHE_SEGUNDOS = 30


def _mesclar(padrao: dict, salvo: dict | None) -> dict:
    out = copy.deepcopy(padrao)
    for chave, valor in (salvo or {}).items():
        if isinstance(valor, dict) and isinstance(out.get(chave), dict):
            out[chave] = _mesclar(out[chave], valor)
        elif chave in out:
            out[chave] = valor
    return out


def _int(valor, nome, minimo, maximo, erros):
    if isinstance(valor, bool) or not isinstance(valor, int) or not (minimo <= valor <= maximo):
        erros.append(f"{nome}: use um número inteiro entre {minimo} e {maximo}.")


def validar_plataforma(dados: dict) -> dict:
    erros = []
    seg = (dados or {}).get("seguranca") or {}
    for campo, (mi, ma) in _LIMITES_PLATAFORMA.items():
        if campo in seg:
            _int(seg[campo], campo, mi, ma, erros)
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "Configuração inválida.", "problemas": erros})
    return {"seguranca": {k: seg[k] for k in _LIMITES_PLATAFORMA if k in seg}}


def validar_banca(dados: dict, plataforma: dict) -> dict:
    erros = []
    out = {}
    seg = (dados or {}).get("seguranca")
    if seg is not None:
        minutos = seg.get("sessao_inatividade_minutos")
        teto = plataforma["seguranca"]["sessao_inatividade_minutos"]
        if minutos is not None:
            _int(minutos, "sessao_inatividade_minutos", 5, teto, erros)
        out["seguranca"] = {"sessao_inatividade_minutos": minutos}

    ident = (dados or {}).get("identidade_prova")
    if ident is not None:
        blocos = ident.get("instrucoes_por_bloco", [])
        if not isinstance(blocos, list) or len(blocos) > 30:
            erros.append("instrucoes_por_bloco: até 30 regras.")
            blocos = []
        limpos = []
        for i, b in enumerate(blocos, start=1):
            contem = str((b or {}).get("contem") or "").strip()
            textos = [str(t).strip() for t in ((b or {}).get("instrucoes") or []) if str(t).strip()]
            if not contem or len(contem) > 80:
                erros.append(f"Regra {i}: informe a palavra do título do bloco (até 80 caracteres).")
            if not textos or len(textos) > 15 or any(len(t) > 1500 for t in textos):
                erros.append(f"Regra {i}: de 1 a 15 instruções, cada uma com até 1500 caracteres.")
            limpos.append({"contem": contem, "instrucoes": textos})
        disc = [str(t).strip() for t in (ident.get("instrucoes_discursiva") or []) if str(t).strip()]
        if len(disc) > 20 or any(len(t) > 1500 for t in disc):
            erros.append("instrucoes_discursiva: até 20 instruções de até 1500 caracteres.")
        out["identidade_prova"] = {"instrucoes_por_bloco": limpos, "instrucoes_discursiva": disc}

    regras = (dados or {}).get("regras_questoes")
    if regras is not None:
        tipos = regras.get("tipos_permitidos") or []
        if not isinstance(tipos, list) or not tipos or any(t not in TIPOS_QUESTAO for t in tipos):
            erros.append("tipos_permitidos: escolha ao menos um tipo válido.")
        if not isinstance(regras.get("revisao_obrigatoria", False), bool):
            erros.append("revisao_obrigatoria: use sim ou não.")
        out["regras_questoes"] = {"tipos_permitidos": [t for t in TIPOS_QUESTAO if t in tipos],
                                  "revisao_obrigatoria": bool(regras.get("revisao_obrigatoria", False))}
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "Configuração inválida.", "problemas": erros})
    return out


async def ler_plataforma(forcar: bool = False) -> dict:
    agora = time.monotonic()
    if not forcar and _CACHE_PLATAFORMA["dados"] is not None and agora - _CACHE_PLATAFORMA["em"] < _CACHE_SEGUNDOS:
        return copy.deepcopy(_CACHE_PLATAFORMA["dados"])
    async with PlatformSessionLocal() as db:
        linha = (await db.execute(select(Configuracao).where(Configuracao.tenant_id.is_(None)))).scalar_one_or_none()
    dados = _mesclar(PADRAO_PLATAFORMA, linha.dados if linha else None)
    _CACHE_PLATAFORMA.update(em=agora, dados=dados)
    return copy.deepcopy(dados)


async def salvar_plataforma(novos: dict, usuario: str) -> dict:
    validos = validar_plataforma(novos)
    async with PlatformSessionLocal() as db:
        linha = (await db.execute(select(Configuracao).where(Configuracao.tenant_id.is_(None)))).scalar_one_or_none()
        atual = _mesclar(PADRAO_PLATAFORMA, linha.dados if linha else None)
        dados = _mesclar(atual, validos)
        if linha is None:
            db.add(Configuracao(tenant_id=None, dados=dados, atualizado_em=datetime.utcnow(), atualizado_por=usuario))
        else:
            linha.dados, linha.atualizado_em, linha.atualizado_por = dados, datetime.utcnow(), usuario
        await db.commit()
    _CACHE_PLATAFORMA.update(em=0.0, dados=None)
    return await ler_plataforma(forcar=True)


async def ler_banca(db: AsyncSession, tenant_id: int) -> dict:
    linha = (await db.execute(select(Configuracao).where(Configuracao.tenant_id == tenant_id))).scalar_one_or_none()
    return _mesclar(PADRAO_BANCA, linha.dados if linha else None)


async def salvar_banca(db: AsyncSession, tenant_id: int, novos: dict, usuario: str) -> dict:
    validos = validar_banca(novos, await ler_plataforma())
    linha = (await db.execute(select(Configuracao).where(Configuracao.tenant_id == tenant_id))).scalar_one_or_none()
    dados = _mesclar(_mesclar(PADRAO_BANCA, linha.dados if linha else None), validos)
    if linha is None:
        db.add(Configuracao(tenant_id=tenant_id, dados=dados, atualizado_em=datetime.utcnow(), atualizado_por=usuario))
    else:
        linha.dados, linha.atualizado_em, linha.atualizado_por = dados, datetime.utcnow(), usuario
    await db.commit()
    return await ler_banca(db, tenant_id)


def inatividade_efetiva(plataforma: dict, banca: dict | None) -> int:
    """A banca só pode deixar a sessão MAIS curta que a plataforma."""
    teto = plataforma["seguranca"]["sessao_inatividade_minutos"]
    proprio = ((banca or {}).get("seguranca") or {}).get("sessao_inatividade_minutos")
    return min(teto, proprio) if isinstance(proprio, int) and proprio > 0 else teto


async def inatividade_do_usuario(tenant_id: int | None) -> int:
    """Minutos de inatividade valendo para um usuário (lê a banca pela role de plataforma, sem depender do RLS)."""
    plataforma = await ler_plataforma()
    banca = None
    if tenant_id is not None:
        async with PlatformSessionLocal() as db:
            linha = (await db.execute(select(Configuracao).where(Configuracao.tenant_id == tenant_id))).scalar_one_or_none()
            banca = linha.dados if linha else None
    return inatividade_efetiva(plataforma, banca)
