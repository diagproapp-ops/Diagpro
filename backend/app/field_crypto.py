# backend/app/field_crypto.py
"""
Cifragem de campos do DiagPro (camada única, aplicada no ORM).

Hierarquia de chaves
--------------------
- Chave mestra (32 bytes): arquivo FORA do projeto e do banco
  (DIAGPRO_MASTER_KEY_FILE ou %LOCALAPPDATA%\\DiagPro\\secrets\\master.key). Nunca vai para o banco.
- Chave de dados por tenant: HKDF-SHA256(mestra, info="diagpro/field/v{versão}/tenant/{tenant}").
  Dados de tenants diferentes usam chaves diferentes; o tenant 0 é o escopo de plataforma
  (tabela `tenants` e usuários sem tenant, como o administrador geral).
- Chave de índice cego: HKDF(mestra, info="diagpro/bidx/v1/{escopo}"), com escopo global
  (login, e-mail, nome/domínio do cliente) ou por tenant (demais buscas exatas).

Formato do valor cifrado
------------------------
  e1.<versão da chave>.<base64url(nonce de 12 bytes || ciphertext || tag)>
AES-256-GCM com AAD = "diagpro|e1|<tabela>|<coluna>|<tenant>|<versão>": um valor cifrado não pode ser
copiado para outra coluna, outra tabela ou outro tenant sem falhar a autenticação.

Integração (install_orm_encryption)
-----------------------------------
- before_flush: cifra os atributos registrados de objetos novos/alterados e calcula os índices cegos.
- after_flush_postexec: devolve o texto claro aos objetos em memória.
- load/refresh: decifra ao carregar. Em sessões da role de runtime, carregar uma linha de outro
  tenant levanta erro (defesa caso o contexto de RLS seja adulterado por SQL).
- Tipo Ciphertext: recusa gravar/comparar texto claro em coluna cifrada (pega SQL direto esquecido).
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import threading
import weakref
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import Text, event
from sqlalchemy.orm import Session, attributes
from sqlalchemy.types import TypeDecorator

PREFIX = "e1."
PLATFORM_TENANT = 0
CURRENT_KEY_VERSION = int(os.getenv("DIAGPRO_FIELD_KEY_VERSION", "1"))


class FieldCryptoError(RuntimeError):
    """Falha de cifragem/decifragem ou violação de política de cifra (fail-closed)."""


# --------------------------------------------------------------------------- chaves
_lock = threading.Lock()
_master: bytes | None = None
_derived: dict[str, bytes] = {}


def master_key_path() -> Path:
    env = os.getenv("DIAGPRO_MASTER_KEY_FILE")
    if env:
        return Path(env)
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "DiagPro" / "secrets" / "master.key"


def _load_master() -> bytes:
    global _master
    if _master is None:
        with _lock:
            if _master is None:
                p = master_key_path()
                if not p.is_file():
                    raise FieldCryptoError(f"Chave mestra não encontrada em {p} (DIAGPRO_MASTER_KEY_FILE).")
                key = base64.b64decode(p.read_text().strip())
                if len(key) != 32:
                    raise FieldCryptoError("Chave mestra inválida: esperado 32 bytes em base64.")
                _master = key
    return _master


def _derive(info: str) -> bytes:
    key = _derived.get(info)
    if key is None:
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info.encode()).derive(_load_master())
        _derived[info] = key
    return key


def _tenant_scope(tenant_id: int | None) -> int:
    return PLATFORM_TENANT if tenant_id is None else int(tenant_id)


def data_key(tenant_id: int | None, version: int) -> bytes:
    return _derive(f"diagpro/field/v{version}/tenant/{_tenant_scope(tenant_id)}")


def _aad(table: str, column: str, tenant: int, version: int) -> bytes:
    return f"diagpro|e1|{table}|{column}|{tenant}|{version}".encode()


# --------------------------------------------------------------------------- valores
def is_encrypted(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def serialize(value: Any, kind: str) -> str:
    if kind == "text":
        return value if isinstance(value, str) else str(value)
    return json.dumps(value, ensure_ascii=False)  # "json" (inclui booleanos)


def deserialize(raw: str, kind: str) -> Any:
    return raw if kind == "text" else json.loads(raw)


def encrypt_value(plain: str, *, table: str, column: str, tenant_id: int | None) -> str:
    tenant = _tenant_scope(tenant_id)
    ver = CURRENT_KEY_VERSION
    nonce = os.urandom(12)
    ct = AESGCM(data_key(tenant, ver)).encrypt(nonce, plain.encode("utf-8"), _aad(table, column, tenant, ver))
    return f"{PREFIX}{ver}.{base64.urlsafe_b64encode(nonce + ct).decode().rstrip('=')}"


def decrypt_value(token: str, *, table: str, column: str, tenant_id: int | None) -> str:
    if not is_encrypted(token):
        raise FieldCryptoError(f"{table}.{column}: valor em texto claro onde se exigia cifra.")
    try:
        _, ver_s, body = token.split(".", 2)
        ver = int(ver_s)
        blob = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        tenant = _tenant_scope(tenant_id)
        return AESGCM(data_key(tenant, ver)).decrypt(blob[:12], blob[12:], _aad(table, column, tenant, ver)).decode("utf-8")
    except FieldCryptoError:
        raise
    except Exception as exc:  # InvalidTag, base64, etc.: nunca devolver dado não autenticado
        raise FieldCryptoError(f"{table}.{column}: falha ao autenticar/decifrar o valor.") from exc


# --------------------------------------------------------------------------- índice cego
def _norm_exact(v: str) -> str:
    return v.strip()


def _norm_lower(v: str) -> str:
    return v.strip().lower()


def _norm_name(v: str) -> str:
    return " ".join(v.split()).casefold()


NORMALIZERS: dict[str, Callable[[str], str]] = {"exact": _norm_exact, "lower": _norm_lower, "name": _norm_name}


def blind_index(value: str | None, *, scope: str, purpose: str, normalizer: str = "exact") -> str | None:
    """HMAC-SHA256 do valor normalizado. scope: 'global' ou f'tenant/{id}'."""
    if value is None:
        return None
    norm = NORMALIZERS[normalizer](str(value))
    key = _derive(f"diagpro/bidx/v1/{scope}")
    return hmac.new(key, f"{purpose}\x1f{norm}".encode("utf-8"), hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- política
# tabela -> {coluna: tipo}. Tudo que não está aqui fica em claro: chaves (PK/FK), tenant_id,
# códigos técnicos gerados (identificador_*, codigo_*), papéis/estados/tipos usados em autorização
# e fluxo, datas, números, booleanos não sensíveis e hashes de senha.
ENCRYPTED: dict[str, dict[str, str]] = {
    "tenants": dict.fromkeys(["name", "domain", "responsible_name", "responsible_email", "responsible_phone"], "text"),
    "users": {**dict.fromkeys(["username", "email", "full_name", "cpf", "phone", "department", "institution",
                               "birth_date", "notes", "address", "avatar_url", "specialty", "pix_key", "banco",
                               "agencia", "conta_corrente", "terms_acceptance", "totp_secret"], "text"),
              "codigos_recuperacao": "json", "senha_historico": "json"},
    "company_data": dict.fromkeys(["company_name", "company_cnpj", "company_address", "company_phone",
                                   "company_email", "company_website", "company_logo_path"], "text"),
    "audit_log_geracao": dict.fromkeys(["usuario", "evento", "cargo", "parametros", "frases", "seed", "ip",
                                        "user_agent"], "text"),
    "Eventos": {**dict.fromkeys(["nome_evento", "numero_edital", "senha_evento_cripto", "local_prova", "observacoes"], "text"),
                "preferencias_exportacao": "json"},
    "Cargos": {**dict.fromkeys(["nome_cargo", "nivel", "turno", "requisitos", "letterhead_pdf_path"], "text"),
               "cover_pdf_paths": "json"},
    "Disciplinas": dict.fromkeys(["nome_disciplina", "descricao"], "text"),
    "DisciplinasDaProva": dict.fromkeys(["nome_disciplina_na_prova", "observacoes"], "text"),
    "conteudos": {**dict.fromkeys(["nome_conteudo", "descricao", "disciplina", "turno", "nivel",
                                   "area_conhecimento"], "text"), "metadados": "json"},
    "banco_frases": dict.fromkeys(["categoria", "texto_frase"], "text"),
    "QuestoesBanco": dict.fromkeys([
        "enunciado", "enunciado_formatado", "indicacao_conteudo", "disciplina_banco", "resposta_correta",
        "gabarito_preliminar", "gabarito_definitivo", "nivel_dificuldade", "tags_keywords",
        "texto_referencia_vinculo", "texto_referencia_direto", "justificativa_anulacao", "metadados_questao",
        "conteudo_nome", "feedback_geral_questao", "justificativa_questao", "autor_elaborador",
        "numero_questao_original_docx", "hash_conteudo_questao", "fonte_questao", "justificativa_anulacao_recurso",
        "justificativa_anulacao_recurso_formatado", "imagens_enunciado", "imagens_enunciado_refs",
        "caminho_imagem_justificativa", "textos_referencia_questao", "caminho_imagem_relativo", "observacao_revisor",
    ], "text"),
    "OpcoesQuestao": {**dict.fromkeys(["texto_opcao", "texto_opcao_formatado", "feedback_opcao",
                                       "imagem_path_opcao"], "text"), "correta": "json"},
    "ItensVerdadeiroFalso": {**dict.fromkeys(["afirmacao", "feedback_item", "imagem_path_item"], "text"), "valor_correto": "json"},
    "DetalhesQuestaoDiscursiva": dict.fromkeys(["resposta_esperada_texto", "palavras_chave_resposta",
                                                "texto_subjetivo_orientacao", "texto_subjetivo_nota_maxima"], "text"),
    "TextosReferenciaGeral": dict.fromkeys([
        "titulo", "conteudo", "legenda_texto", "descricao_imagem", "fonte_imagem", "tags_imagem", "licenca_imagem",
        "caminho_imagem_relativo", "observacoes", "metadados_texto_ref", "questoes_vinculo", "conteudo_formatado",
    ], "text"),
    "HistoricoRevisaoQuestao": dict.fromkeys(["usuario_revisor", "observacao_revisor", "dados_revisao"], "text"),
    "ProvasMontadas": {**dict.fromkeys(["nome_prova_montada", "titulo_prova", "responsavel_montagem",
                                        "textos_referencia_prova_json"], "text"),
                       "blocos_questoes": "json", "metadados_prova": "json"},
}

# tabela -> {coluna_bidx: (colunas_origem, escopo 'global'|'tenant', normalizador)}
BLIND_INDEXES: dict[str, dict[str, tuple[tuple[str, ...], str, str]]] = {
    "tenants": {"name_bidx": (("name",), "global", "exact"), "domain_bidx": (("domain",), "global", "lower")},
    "users": {"username_bidx": (("username",), "global", "exact"), "email_bidx": (("email",), "global", "lower"),
              "full_name_bidx": (("full_name",), "tenant", "name")},
    "banco_frases": {"categoria_bidx": (("categoria",), "tenant", "exact"),
                     "frase_bidx": (("categoria", "texto_frase"), "tenant", "exact")},
    "Disciplinas": {"nome_disciplina_bidx": (("nome_disciplina",), "tenant", "exact")},
    "audit_log_geracao": {"usuario_bidx": (("usuario",), "tenant", "exact"),
                          "evento_bidx": (("evento",), "tenant", "exact"),
                          "cargo_bidx": (("cargo",), "tenant", "exact")},
}


def row_tenant(table: str, tenant_id: int | None) -> int | None:
    """Tenant usado na chave: `tenants` e linhas sem tenant usam o escopo de plataforma."""
    return None if table == "tenants" else tenant_id


def compute_blind_indexes(table: str, values: dict[str, Any], tenant_id: int | None) -> dict[str, str | None]:
    out = {}
    for bcol, (sources, scope, normalizer) in BLIND_INDEXES.get(table, {}).items():
        parts = [values.get(s) for s in sources]
        if any(p is None for p in parts):
            out[bcol] = None
            continue
        sc = "global" if scope == "global" else f"tenant/{_tenant_scope(row_tenant(table, tenant_id))}"
        joined = "\x1f".join(NORMALIZERS[normalizer](str(p)) for p in parts)
        out[bcol] = blind_index(joined, scope=sc, purpose=f"{table}.{bcol}", normalizer="exact")
    return out


def blind_eq(column_attr, value: Any, tenant_id: int | None = None):
    """
    Expressão SQL de busca exata sobre coluna cifrada com índice cego:
        select(User).where(blind_eq(User.username, "fulano"))
    Para índices por tenant, informe o tenant_id do contexto.
    """
    table = column_attr.class_.__table__.name
    col = column_attr.key
    for bcol, (sources, scope, _n) in BLIND_INDEXES.get(table, {}).items():
        if sources == (col,):
            if scope == "tenant" and tenant_id is None and table != "tenants":
                raise FieldCryptoError(f"Busca por {table}.{col} exige tenant_id (índice cego por tenant).")
            digest = compute_blind_indexes(table, {col: value}, tenant_id)[bcol]
            return getattr(column_attr.class_, bcol) == digest
    raise FieldCryptoError(f"{table}.{col} não possui índice cego: não é possível buscar por igualdade.")


def encrypt_row(table: str, values: dict[str, Any], tenant_id: int | None) -> dict[str, Any]:
    """Para INSERT/UPDATE em SQL direto (Core): cifra colunas registradas e preenche índices cegos."""
    out = dict(values)
    out.update(compute_blind_indexes(table, values, tenant_id))
    key_tenant = row_tenant(table, tenant_id)
    for col, kind in ENCRYPTED.get(table, {}).items():
        v = out.get(col)
        if v is not None and not is_encrypted(v):
            out[col] = encrypt_value(serialize(v, kind), table=table, column=col, tenant_id=key_tenant)
    return out


# --------------------------------------------------------------------------- tipo SQL
class Ciphertext(TypeDecorator):
    """Coluna cifrada: aceita apenas valores no formato e1.* (ou NULL) ao gravar/comparar."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or is_encrypted(value):
            return value
        raise FieldCryptoError("Tentativa de gravar/comparar texto claro em coluna cifrada (use o ORM ou encrypt_row/blind_eq).")


# --------------------------------------------------------------------------- integração ORM
# Objetos cujos atributos cifrados já estão em texto claro NA MEMÓRIA (decifrados por nós ou restaurados
# após o flush). Um evento de carga sobre eles pode encontrar esses valores; somente para esses objetos
# o texto claro é aceito. Qualquer texto claro vindo do banco continua sendo recusado.
_PLAIN_IN_MEMORY: "weakref.WeakSet" = weakref.WeakSet()


def _mark_plain(obj) -> None:
    _PLAIN_IN_MEMORY.add(obj)
def _table_of(obj) -> str | None:
    t = getattr(obj, "__table__", None)
    return t.name if t is not None else None


def _tenant_of(obj, table: str) -> int | None:
    return row_tenant(table, getattr(obj, "tenant_id", None))


def _encrypt_instance(obj, session) -> None:
    table = _table_of(obj)
    spec = ENCRYPTED.get(table)
    if not spec:
        return
    state = attributes.instance_state(obj)
    tenant = _tenant_of(obj, table)
    tenant_changed = "tenant_id" in state.attrs and state.attrs.tenant_id.history.has_changes()
    is_new = state.key is None
    restore = session.info.setdefault("_fc_restore", [])

    # padrões de colunas cifradas são aplicados aqui (antes da cifra), nunca pelo banco
    if is_new:
        columns = obj.__table__.c
        for col in spec:
            if col in columns and "plain_default" in columns[col].info and getattr(obj, col) is None:
                default = columns[col].info["plain_default"]
                setattr(obj, col, default() if callable(default) else copy.deepcopy(default))

    # índices cegos a partir do texto claro atual
    if table in BLIND_INDEXES:
        current = {c: getattr(obj, c) for c in {s for v in BLIND_INDEXES[table].values() for s in v[0]}}
        if any(is_encrypted(v) for v in current.values()):
            raise FieldCryptoError(f"{table}: índice cego calculado sobre valor já cifrado.")
        for bcol, digest in compute_blind_indexes(table, current, getattr(obj, "tenant_id", None)).items():
            if getattr(obj, bcol) != digest:
                setattr(obj, bcol, digest)

    for col, kind in spec.items():
        attr = state.attrs[col]
        if not (is_new or tenant_changed or attr.history.has_changes()):
            continue
        plain = attr.value
        if plain is None:
            continue
        if is_encrypted(plain):
            raise FieldCryptoError(f"{table}.{col}: valor já cifrado atribuído ao objeto (dupla cifra).")
        setattr(obj, col, encrypt_value(serialize(plain, kind), table=table, column=col, tenant_id=tenant))
        restore.append((obj, col, plain))


def _decrypt_instance(obj, context) -> None:
    table = _table_of(obj)
    spec = ENCRYPTED.get(table)
    if not spec:
        return
    session = getattr(context, "session", None)
    info = session.info if session is not None else {}
    if not info.get("platform"):
        expected = info.get("tenant_id")
        row_tid = getattr(obj, "tenant_id", None)
        if table == "tenants" or expected is None or row_tid != expected:
            raise FieldCryptoError(
                f"Linha de {table} fora do tenant da sessão: carregamento bloqueado (possível adulteração de contexto)."
            )
    tenant = _tenant_of(obj, table)
    state = attributes.instance_state(obj)
    already_plain = obj in _PLAIN_IN_MEMORY
    for col, kind in spec.items():
        if col not in state.dict:
            continue
        raw = state.dict[col]
        if raw is None:
            continue
        if not is_encrypted(raw) and already_plain:
            continue  # valor já decifrado/restaurado por esta camada nesta sessão
        plain = deserialize(decrypt_value(raw, table=table, column=col, tenant_id=tenant), kind)
        attributes.set_committed_value(obj, col, plain)
    _mark_plain(obj)


def install_orm_encryption(base) -> None:
    """Registra os eventos de cifra para todos os modelos de `base` com colunas em ENCRYPTED."""
    mapped = [m.class_ for m in base.registry.mappers if m.local_table.name in ENCRYPTED]
    missing = [
        f"{t}.{c}" for t, cols in ENCRYPTED.items() for c in cols
        if t in base.metadata.tables and c not in base.metadata.tables[t].c
    ]
    if missing:
        raise FieldCryptoError(f"Colunas da política de cifra inexistentes no modelo: {missing}")
    for t, cols in ENCRYPTED.items():
        if t in base.metadata.tables:
            for c in cols:
                if not isinstance(base.metadata.tables[t].c[c].type, Ciphertext):
                    raise FieldCryptoError(f"{t}.{c} precisa ser declarada com o tipo Ciphertext.")

    for cls in mapped:
        event.listen(cls, "load", lambda target, context: _decrypt_instance(target, context))
        event.listen(cls, "refresh", lambda target, context, attrs: _decrypt_instance(target, context))


@event.listens_for(Session, "before_flush")
def _before_flush(session, flush_context, instances) -> None:
    for obj in list(session.new) + list(session.dirty):
        _encrypt_instance(obj, session)


@event.listens_for(Session, "after_flush_postexec")
def _after_flush(session, flush_context) -> None:
    for obj, col, plain in session.info.pop("_fc_restore", []):
        attributes.set_committed_value(obj, col, plain)
        _mark_plain(obj)


@event.listens_for(Session, "after_soft_rollback")
def _after_rollback(session, previous_transaction) -> None:
    session.info.pop("_fc_restore", None)


def generate_master_key() -> Path:
    """Cria a chave mestra (32 bytes aleatórios). Nunca sobrescreve uma chave existente."""
    p = master_key_path()
    if p.exists():
        raise FieldCryptoError(f"Já existe uma chave mestra em {p}; não sobrescrevo.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(base64.b64encode(os.urandom(32)).decode())
    return p


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["genkey"]:
        print(f"Chave mestra criada em {generate_master_key()}. Guarde uma cópia OFFLINE: sem ela os dados são irrecuperáveis.")
    else:
        print("Uso: python -m backend.app.field_crypto genkey")
