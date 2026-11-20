# backend/app/configuracoes.py
"""
Configurações em dois escopos guardados (o terceiro, "pessoal", é a página Minha conta):

- PLATAFORMA (tenant_id nulo, só admin geral): política de senha e sessão para todos.
- BANCA (por cliente, RLS): sessão mais curta, identidade da prova, regras das questões.

IA: a plataforma escolhe o provedor/modelo e guarda as chaves (cifradas, nunca devolvidas à tela);
a banca decide se liga e quais recursos usa. Vale só se as DUAS ligarem.

Os padrões reproduzem o comportamento anterior; a validação impõe limites seguros (ninguém consegue,
por exemplo, baixar a senha mínima para 4 caracteres). Tudo é cifrado no banco.
"""
import copy
import os
import re
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Configuracao
from core.instrucoes_padrao import INSTRUCOES_DISCURSIVA, INSTRUCOES_POR_BLOCO

TIPOS_QUESTAO = ["MULTIPLA_ESCOLHA", "CERTO_ERRADO", "DISCURSIVA", "SUBJETIVA"]

TERMOS_PADRAO = (
    "Ao usar o DiagPro você concorda em utilizá-lo somente para as atividades da sua banca, manter em sigilo "
    "todo conteúdo de prova a que tiver acesso, não compartilhar sua senha nem seu autenticador e avisar a banca "
    "imediatamente sobre qualquer acesso indevido. Todas as ações ficam registradas para auditoria."
)
POLITICA_PADRAO = (
    "O DiagPro trata dados pessoais (nome, usuário, e-mail, telefone e dados de acesso como IP e navegador) "
    "somente para identificar quem usa o sistema, proteger as contas e cumprir as obrigações da banca. Os dados "
    "ficam cifrados, separados por banca, e não são vendidos nem compartilhados. Você pode baixar seus dados em "
    "Minha conta e pedir à sua banca a correção ou a eliminação deles (LGPD, art. 18)."
)

PADRAO_PLATAFORMA = {
    "seguranca": {
        "senha_tamanho_minimo": 12,
        "senha_tipos_minimos": 3,
        "senha_historico": 5,
        "senha_validade_dias": 180,
        "sessao_inatividade_minutos": 30,
        "sessao_maxima_horas": 12,
    },
    "ia": {
        "habilitada": False,
        "provedor": "anthropic",
        "modelo_anthropic": "claude-opus-5-5",
        "modelo_openai": "gpt-5",
        "limite_diario_usuario": 60,
        "limite_diario_banca": 1500,
        "chaves": {"anthropic": "", "openai": ""},  # segredo: nunca sai do servidor
    },
    "email": {
        "habilitado": False,
        "host": "",
        "porta": 587,
        "seguranca": "starttls",  # starttls | ssl | nenhuma (só servidor local)
        "usuario": "",
        "senha": "",              # segredo: nunca sai do servidor
        "remetente_nome": "DiagPro",
        "remetente_email": "",
        "url_sistema": "http://localhost:3000",  # base dos links nos e-mails
    },
    "backup": {
        "automatico": True,
        "hora": 2,      # hora do dia (0-23) do backup automático
        "manter": 14,   # quantos backups automáticos guardar
    },
    "manutencao": {
        "ativa": False,
        "mensagem": "O DiagPro está em manutenção. Volte em alguns minutos.",
    },
    "lgpd": {
        "versao_termos": "1",
        "termos": TERMOS_PADRAO,
        "politica": POLITICA_PADRAO,
        "encarregado": "",  # contato do encarregado (DPO) mostrado na política
        "retencao_dias": {"notificacoes": 180, "sessoes": 90, "uso_ia": 365},
    },
}

SEGURANCA_EMAIL = ("starttls", "ssl", "nenhuma")
_EMAIL_OK = re.compile(r"^[^@\s<>\"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
_HOST_OK = re.compile(r"^[A-Za-z0-9.-]{1,253}$")
_URL_OK = re.compile(r"^https?://[A-Za-z0-9.:\-]{1,200}(/[A-Za-z0-9._~/\-]*)?$")

PROVEDORES_IA = ("anthropic", "openai")
RECURSOS_IA = ("gerar_questao", "revisar_questao", "alternativas", "justificativa", "melhorar_texto", "chat")
_VAR_AMBIENTE = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

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
    "ia": {
        "habilitada": False,
        "recursos": dict.fromkeys(RECURSOS_IA, True),
        "orientacoes_banca": "",          # estilo da banca, entra em toda instrução à IA
        "limite_diario_usuario": None,    # None = o da plataforma; só pode ser MENOR
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


_MODELO_OK = re.compile(r"^[A-Za-z0-9._:\-]{2,80}$")
_CHAVE_OK = re.compile(r"^\S{20,400}$")


def _validar_ia_plataforma(ia: dict, erros: list) -> dict:
    out = {}
    if "habilitada" in ia:
        if not isinstance(ia["habilitada"], bool):
            erros.append("ia.habilitada: use sim ou não.")
        out["habilitada"] = bool(ia["habilitada"])
    if "provedor" in ia:
        if ia["provedor"] not in PROVEDORES_IA:
            erros.append("ia.provedor: escolha anthropic ou openai.")
        out["provedor"] = ia["provedor"]
    for campo in ("modelo_anthropic", "modelo_openai"):
        if campo in ia:
            if not isinstance(ia[campo], str) or not _MODELO_OK.match(ia[campo].strip()):
                erros.append(f"ia.{campo}: nome de modelo inválido.")
            else:
                out[campo] = ia[campo].strip()
    for campo, (mi, ma) in {"limite_diario_usuario": (1, 1000), "limite_diario_banca": (1, 100000)}.items():
        if campo in ia:
            _int(ia[campo], f"ia.{campo}", mi, ma, erros)
            out[campo] = ia[campo]
    chaves = ia.get("chaves")
    if chaves is not None:
        if not isinstance(chaves, dict):
            erros.append("ia.chaves: formato inválido.")
        else:
            out["chaves"] = {}
            for prov, valor in chaves.items():
                if prov not in PROVEDORES_IA:
                    erros.append(f"ia.chaves: provedor desconhecido ({prov}).")
                elif valor is None or valor == "":
                    out["chaves"][prov] = ""  # remover a chave
                elif not isinstance(valor, str) or not _CHAVE_OK.match(valor.strip()):
                    erros.append(f"ia.chaves.{prov}: chave em formato inválido.")
                else:
                    out["chaves"][prov] = valor.strip()
    return out


def validar_plataforma(dados: dict) -> dict:
    erros = []
    seg = (dados or {}).get("seguranca") or {}
    for campo, (mi, ma) in _LIMITES_PLATAFORMA.items():
        if campo in seg:
            _int(seg[campo], campo, mi, ma, erros)
    out = {"seguranca": {k: seg[k] for k in _LIMITES_PLATAFORMA if k in seg}}
    ia = (dados or {}).get("ia")
    if ia is not None:
        if not isinstance(ia, dict):
            erros.append("ia: formato inválido.")
        else:
            out["ia"] = _validar_ia_plataforma(ia, erros)
    bk = (dados or {}).get("backup")
    if bk is not None:
        out["backup"] = {}
        if "automatico" in bk:
            if not isinstance(bk["automatico"], bool):
                erros.append("backup.automatico: use sim ou não.")
            out["backup"]["automatico"] = bool(bk["automatico"])
        for campo, (mi, ma) in {"hora": (0, 23), "manter": (3, 365)}.items():
            if campo in bk:
                _int(bk[campo], f"backup.{campo}", mi, ma, erros)
                out["backup"][campo] = bk[campo]
    man = (dados or {}).get("manutencao")
    if man is not None:
        out["manutencao"] = {}
        if "ativa" in man:
            if not isinstance(man["ativa"], bool):
                erros.append("manutencao.ativa: use sim ou não.")
            out["manutencao"]["ativa"] = bool(man["ativa"])
        if "mensagem" in man:
            msg = str(man["mensagem"] or "").strip()
            if not msg or len(msg) > 300:
                erros.append("manutencao.mensagem: de 1 a 300 caracteres.")
            out["manutencao"]["mensagem"] = msg
    lg = (dados or {}).get("lgpd")
    if lg is not None:
        out["lgpd"] = {}
        if "versao_termos" in lg:
            v = str(lg["versao_termos"] or "").strip()
            if not re.fullmatch(r"[0-9A-Za-z.\-]{1,20}", v):
                erros.append("lgpd.versao_termos: use até 20 letras, números, ponto ou hífen.")
            out["lgpd"]["versao_termos"] = v
        for campo, limite in (("termos", 20000), ("politica", 20000), ("encarregado", 300)):
            if campo in lg:
                texto = str(lg[campo] or "").strip()
                if len(texto) > limite or (campo != "encarregado" and not texto):
                    erros.append(f"lgpd.{campo}: até {limite} caracteres" + ("" if campo == "encarregado" else ", não pode ficar vazio") + ".")
                out["lgpd"][campo] = texto
        if "retencao_dias" in lg:
            rd = lg["retencao_dias"] or {}
            out["lgpd"]["retencao_dias"] = {}
            for campo, (mi, ma) in {"notificacoes": (30, 3650), "sessoes": (30, 3650), "uso_ia": (90, 3650)}.items():
                if campo in rd:
                    _int(rd[campo], f"lgpd.retencao_dias.{campo}", mi, ma, erros)
                    out["lgpd"]["retencao_dias"][campo] = rd[campo]
    em = (dados or {}).get("email")
    if em is not None:
        if not isinstance(em, dict):
            erros.append("email: formato inválido.")
        else:
            out["email"] = _validar_email_plataforma(em, erros)
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "Configuração inválida.", "problemas": erros})
    return out


def _validar_email_plataforma(em: dict, erros: list) -> dict:
    out = {}
    if "habilitado" in em:
        if not isinstance(em["habilitado"], bool):
            erros.append("email.habilitado: use sim ou não.")
        out["habilitado"] = bool(em["habilitado"])
    if "host" in em:
        host = str(em["host"] or "").strip()
        if host and not _HOST_OK.match(host):
            erros.append("email.host: servidor inválido.")
        out["host"] = host
    if "porta" in em:
        _int(em["porta"], "email.porta", 1, 65535, erros)
        out["porta"] = em["porta"]
    if "seguranca" in em:
        if em["seguranca"] not in SEGURANCA_EMAIL:
            erros.append("email.seguranca: use starttls, ssl ou nenhuma.")
        out["seguranca"] = em["seguranca"]
    if "usuario" in em:
        usuario = str(em["usuario"] or "").strip()
        if len(usuario) > 254 or any(c.isspace() for c in usuario):
            erros.append("email.usuario: usuário inválido.")
        out["usuario"] = usuario
    if "senha" in em:  # None/"" = remover; ausente = manter
        senha = em["senha"]
        if senha in (None, ""):
            out["senha"] = ""
        elif not isinstance(senha, str) or len(senha) > 512:
            erros.append("email.senha: senha inválida.")
        else:
            out["senha"] = senha
    if "remetente_nome" in em:
        nome = str(em["remetente_nome"] or "").strip()
        if len(nome) > 80 or any(c in nome for c in "\r\n<>\""):
            erros.append("email.remetente_nome: até 80 caracteres, sem quebras de linha.")
        out["remetente_nome"] = nome
    if "remetente_email" in em:
        rem = str(em["remetente_email"] or "").strip()
        if rem and not _EMAIL_OK.match(rem):
            erros.append("email.remetente_email: e-mail inválido.")
        out["remetente_email"] = rem
    if "url_sistema" in em:
        url = str(em["url_sistema"] or "").strip().rstrip("/")
        if not _URL_OK.match(url):
            erros.append("email.url_sistema: informe o endereço do DiagPro (http:// ou https://).")
        out["url_sistema"] = url
    return out


def plataforma_publica(dados: dict) -> dict:
    """O que a tela pode ver: as chaves viram só 'definida' + os 4 últimos caracteres."""
    out = copy.deepcopy(dados)
    ia = out.get("ia") or {}
    chaves = ia.pop("chaves", {}) or {}
    ia["chaves"] = {
        prov: {"definida": bool(chaves.get(prov)),
               "final": ("…" + chaves[prov][-4:]) if chaves.get(prov) else "",
               "no_ambiente": bool(os.getenv(_VAR_AMBIENTE[prov], "").strip())}
        for prov in PROVEDORES_IA
    }
    em = out.get("email") or {}
    em["senha_definida"] = bool(em.pop("senha", ""))
    return out


def chave_do_provedor(plataforma: dict, provedor: str) -> str:
    """Chave salva na tela (cifrada no banco) ou, se não houver, a variável de ambiente do servidor."""
    salva = (((plataforma.get("ia") or {}).get("chaves") or {}).get(provedor) or "").strip()
    return salva or os.getenv(_VAR_AMBIENTE[provedor], "").strip()


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
    ia = (dados or {}).get("ia")
    if ia is not None:
        out["ia"] = _validar_ia_banca(ia, plataforma, erros)
    if erros:
        raise HTTPException(status_code=400, detail={"mensagem": "Configuração inválida.", "problemas": erros})
    return out


def _validar_ia_banca(ia: dict, plataforma: dict, erros: list) -> dict:
    if not isinstance(ia, dict):
        erros.append("ia: formato inválido.")
        return {}
    out = {}
    if "habilitada" in ia:
        if not isinstance(ia["habilitada"], bool):
            erros.append("ia.habilitada: use sim ou não.")
        out["habilitada"] = bool(ia["habilitada"])
    if "recursos" in ia:
        rec = ia["recursos"]
        if not isinstance(rec, dict) or any(k not in RECURSOS_IA or not isinstance(v, bool) for k, v in rec.items()):
            erros.append("ia.recursos: formato inválido.")
        else:
            out["recursos"] = {k: rec.get(k, True) for k in RECURSOS_IA}
    if "orientacoes_banca" in ia:
        texto = ia["orientacoes_banca"]
        if not isinstance(texto, str) or len(texto) > 3000:
            erros.append("ia.orientacoes_banca: até 3000 caracteres.")
        else:
            out["orientacoes_banca"] = texto.strip()
    if "limite_diario_usuario" in ia:
        teto = plataforma["ia"]["limite_diario_usuario"]
        if ia["limite_diario_usuario"] is not None:
            _int(ia["limite_diario_usuario"], "ia.limite_diario_usuario", 1, teto, erros)
        out["limite_diario_usuario"] = ia["limite_diario_usuario"]
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
