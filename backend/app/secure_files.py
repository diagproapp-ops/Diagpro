# backend/app/secure_files.py
"""
Armazenamento cifrado de arquivos do DiagPro (imagens de questões, avatares, logos, capas, templates,
CSV de candidatos).

- Cada arquivo é gravado cifrado com AES-256-GCM em blocos, com chave POR TENANT derivada da chave mestra
  (HKDF "diagpro/file/v1/tenant/{tenant}"). Nada fica em pasta pública.
- No banco guarda-se apenas uma referência opaca:  sf1:<tenant>:<id hex 32>.<ext>
  (as colunas de caminho já são cifradas pela camada de campos).
- O navegador recebe uma URL ASSINADA e de vida curta (HMAC + expiração), porque <img src> não envia o
  token Authorization:  api/files/<tenant>/<id>.<ext>?exp=<epoch>&sig=<hmac>
- Para o gerador de provas (python-docx, LibreOffice, Java), materialize() decifra só os arquivos
  necessários numa pasta temporária privada, apagada ao fim do uso.
- Valores vindos do cliente só são aceitos como referência válida do PRÓPRIO tenant (ref_from_client);
  qualquer outro caminho é descartado (impede ler arquivos arbitrários do servidor).
"""
from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import hmac
import json
import os
import re
import shutil
import struct
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.app import field_crypto as fc

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAGIC = b"DPF1\n"
CHUNK = 1024 * 1024
REF_RE = re.compile(r"sf1:(\d+):([0-9a-f]{32})\.([a-z0-9]{1,5})")
URL_RE = re.compile(r"api/files/(\d+)/([0-9a-f]{32})\.([a-z0-9]{1,5})\?exp=(\d+)&sig=([0-9a-f]{64})")
URL_TTL_SECONDS = int(os.getenv("DIAGPRO_FILE_URL_TTL", "300"))

# Campos que carregam caminhos de arquivo em dicionários enviados ao gerador ou vindos do cliente
PATH_KEYS = {
    "caminho_imagem_relativo", "imagem_path_opcao", "imagem_path_item", "caminho_imagem_justificativa",
    "company_logo_path", "letterhead_pdf_path", "cover_pdf_paths", "caminho_csv_candidatos", "avatar_url",
    "template_path",
}

KINDS = {
    "image": ({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}, 10 * 1024 * 1024),
    "pdf": ({".pdf"}, 20 * 1024 * 1024),
    "docx": ({".docx", ".dotx"}, 20 * 1024 * 1024),
    "template": ({".docx", ".dotx", ".pdf"}, 20 * 1024 * 1024),
    "csv": ({".csv"}, 20 * 1024 * 1024),
}
MEDIA_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp",
    "bmp": "image/bmp", "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "dotx": "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    "csv": "text/csv",
}


class SecureFileError(ValueError):
    pass


# --------------------------------------------------------------------------- chaves e caminhos
def files_root() -> Path:
    root = Path(os.getenv("DIAGPRO_FILES_DIR") or PROJECT_ROOT / "storage_data" / "files")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _scope(tenant_id: int | None) -> int:
    return fc.PLATFORM_TENANT if tenant_id is None else int(tenant_id)


def _file_key(scope: int) -> bytes:
    return fc._derive(f"diagpro/file/v1/tenant/{scope}")


def _url_key() -> bytes:
    return fc._derive("diagpro/file-url/v1")


def parse_ref(ref: str) -> tuple[int, str, str]:
    m = REF_RE.fullmatch(ref or "")
    if not m:
        raise SecureFileError("Referência de arquivo inválida.")
    return int(m.group(1)), m.group(2), m.group(3)


def is_ref(value: Any) -> bool:
    return isinstance(value, str) and REF_RE.fullmatch(value) is not None


def _blob_path(scope: int, fid: str) -> Path:
    return files_root() / str(scope) / f"{fid}.bin"


# --------------------------------------------------------------------------- cifra em blocos
def _aad(prefix: bytes, i: int, final: bool, scope: int, fid: str) -> bytes:
    return MAGIC + prefix + struct.pack(">I?", i, final) + f"|{scope}|{fid}".encode()


def _encrypt_to(dst, data: bytes, scope: int, fid: str) -> None:
    aes = AESGCM(_file_key(scope))
    prefix = os.urandom(8)
    dst.write(MAGIC + prefix)
    chunks = [data[i:i + CHUNK] for i in range(0, len(data), CHUNK)] or [b""]
    for i, chunk in enumerate(chunks):
        final = i == len(chunks) - 1
        ct = aes.encrypt(prefix + struct.pack(">I", i), chunk, _aad(prefix, i, final, scope, fid))
        dst.write(struct.pack(">I", len(ct)) + ct)


def _decrypt_from(src, scope: int, fid: str) -> bytes:
    aes = AESGCM(_file_key(scope))
    if src.read(len(MAGIC)) != MAGIC:
        raise SecureFileError("Arquivo cifrado com cabeçalho inválido.")
    prefix = src.read(8)
    out, i = [], 0
    while True:
        hdr = src.read(4)
        if len(hdr) != 4:
            raise SecureFileError("Arquivo cifrado truncado.")
        ct = src.read(struct.unpack(">I", hdr)[0])
        nonce = prefix + struct.pack(">I", i)
        try:
            out.append(aes.decrypt(nonce, ct, _aad(prefix, i, False, scope, fid)))
        except Exception:
            try:
                out.append(aes.decrypt(nonce, ct, _aad(prefix, i, True, scope, fid)))
            except Exception as exc:
                raise SecureFileError("Falha ao autenticar o arquivo cifrado (adulterado ou chave errada).") from exc
            if src.read(1):
                raise SecureFileError("Dados extras após o bloco final.")
            return b"".join(out)
        i += 1


# --------------------------------------------------------------------------- validação de conteúdo
def _check_magic(data: bytes, ext: str) -> None:
    e = ext.lower().lstrip(".")
    ok = {
        "png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": data.startswith(b"\xff\xd8\xff"), "jpeg": data.startswith(b"\xff\xd8\xff"),
        "gif": data[:6] in (b"GIF87a", b"GIF89a"),
        "webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        "bmp": data.startswith(b"BM"),
        "pdf": data.startswith(b"%PDF"),
        "docx": data.startswith(b"PK\x03\x04"), "dotx": data.startswith(b"PK\x03\x04"),
        "csv": b"\x00" not in data[:4096],
    }.get(e, False)
    if not ok:
        raise SecureFileError(f"O conteúdo do arquivo não corresponde a .{e}.")


def _validated_ext(filename: str | None, kind: str) -> str:
    allowed, _ = KINDS[kind]
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in allowed:
        raise SecureFileError(f"Tipo de arquivo não permitido. Use: {', '.join(sorted(allowed))}.")
    return ext.lstrip(".")


# --------------------------------------------------------------------------- API de armazenamento
def store_bytes(data: bytes, tenant_id: int | None, ext: str, *, validate: bool = True) -> str:
    ext = ext.lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9]{1,5}", ext):
        raise SecureFileError("Extensão inválida.")
    if validate:
        _check_magic(data, ext)
    scope, fid = _scope(tenant_id), uuid.uuid4().hex
    dest = _blob_path(scope, fid)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    with open(tmp, "xb") as f:
        _encrypt_to(f, data, scope, fid)
    os.replace(tmp, dest)
    return f"sf1:{scope}:{fid}.{ext}"


async def save_upload(upload, tenant_id: int | None, kind: str) -> str:
    """Valida extensão, tamanho e assinatura do conteúdo de um UploadFile e o grava cifrado."""
    ext = _validated_ext(getattr(upload, "filename", None), kind)
    _, max_bytes = KINDS[kind]
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise SecureFileError(f"Arquivo excede o limite de {max_bytes // (1024 * 1024)} MB.")
    return store_bytes(data, tenant_id, ext)


def read_bytes(ref: str, tenant_id: int | None, *, any_tenant: bool = False) -> bytes:
    scope, fid, _ = parse_ref(ref)
    if not any_tenant and scope != _scope(tenant_id):
        raise SecureFileError("Arquivo de outro cliente.")
    path = _blob_path(scope, fid)
    if not path.is_file():
        raise SecureFileError("Arquivo não encontrado.")
    with open(path, "rb") as f:
        return _decrypt_from(f, scope, fid)


def delete(ref: str | None) -> None:
    if not is_ref(ref):
        return
    scope, fid, _ = parse_ref(ref)
    with contextlib.suppress(FileNotFoundError):
        _blob_path(scope, fid).unlink()


# --------------------------------------------------------------------------- URLs assinadas
def _sign(scope: int, fid: str, ext: str, exp: int) -> str:
    return hmac.new(_url_key(), f"{scope}|{fid}|{ext}|{exp}".encode(), hashlib.sha256).hexdigest()


def signed_url(ref: str, ttl: int | None = None) -> str:
    scope, fid, ext = parse_ref(ref)
    exp = int(time.time()) + (ttl or URL_TTL_SECONDS)
    return f"api/files/{scope}/{fid}.{ext}?exp={exp}&sig={_sign(scope, fid, ext, exp)}"


def verify_signature(scope: int, fid: str, ext: str, exp: int, sig: str, *, check_expiry: bool = True) -> str:
    expected = _sign(scope, fid, ext, exp)
    if not hmac.compare_digest(expected, sig or ""):
        raise SecureFileError("Assinatura inválida.")
    if check_expiry and exp < int(time.time()):
        raise SecureFileError("Link expirado.")
    return f"sf1:{scope}:{fid}.{ext}"


def to_public(value: Any) -> Any:
    """Troca referências por URLs assinadas (para respostas da API). Outros valores ficam como estão."""
    if isinstance(value, str):
        return signed_url(value) if is_ref(value) else value
    if isinstance(value, list):
        return [to_public(v) for v in value]
    if isinstance(value, dict):
        return {k: to_public(v) for k, v in value.items()}
    return value


def ref_from_client(value: Any, tenant_id: int | None) -> str | None:
    """
    Converte o que o cliente devolveu (referência ou URL assinada que ele recebeu) em referência
    validada do PRÓPRIO tenant. Qualquer outro valor (caminho de disco, URL externa, ref de outro
    cliente, assinatura inválida) é descartado.
    """
    if not isinstance(value, str) or not value:
        return None
    scope = _scope(tenant_id)
    m = REF_RE.fullmatch(value)
    if m:
        ref = value
    else:
        u = URL_RE.search(value)
        if not u:
            return None
        try:
            ref = verify_signature(int(u.group(1)), u.group(2), u.group(3), int(u.group(4)), u.group(5),
                                   check_expiry=False)
        except SecureFileError:
            return None
    s, fid, _ = parse_ref(ref)
    if s != scope or not _blob_path(s, fid).is_file():
        return None
    return ref


def sanitize_client_paths(obj: Any, tenant_id: int | None) -> Any:
    """Aplica ref_from_client a todos os campos de caminho (PATH_KEYS) de uma estrutura vinda do cliente."""
    if isinstance(obj, list):
        return [sanitize_client_paths(v, tenant_id) for v in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in PATH_KEYS:
                out[k] = ([r for r in (ref_from_client(x, tenant_id) for x in v) if r] if isinstance(v, list)
                          else ref_from_client(v, tenant_id))
            else:
                out[k] = sanitize_client_paths(v, tenant_id)
        return out
    return obj


# --------------------------------------------------------------------------- uso pelo gerador
def request_workdir():
    """Dependência FastAPI: pasta temporária privada por requisição, apagada ao final (mesmo com erro)."""
    workdir = tempfile.mkdtemp(prefix="diagpro_req_")
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def materialize_into(obj: Any, tenant_id: int | None, workdir: str) -> Any:
    """
    Cópia de obj com referências trocadas por caminhos de arquivos decifrados dentro de workdir.
    Campos de caminho (PATH_KEYS) que não sejam referências válidas do tenant viram None (fail-closed).
    """
    cache: dict[str, str] = {}

    def resolve(ref: str) -> str | None:
        if ref not in cache:
            try:
                data = read_bytes(ref, tenant_id)
            except SecureFileError:
                return None
            _, fid, ext = parse_ref(ref)
            path = os.path.join(workdir, f"{fid}.{ext}")
            with open(path, "wb") as f:
                f.write(data)
            cache[ref] = path
        return cache[ref]

    def walk(o: Any, key: str | None = None) -> Any:
        if isinstance(o, dict):
            return {k: walk(v, k) for k, v in o.items()}
        if isinstance(o, list):
            items = [walk(v, key) for v in o]
            return [i for i in items if i is not None] if key in PATH_KEYS else items
        if isinstance(o, str):
            if is_ref(o):
                return resolve(o)
            if key in PATH_KEYS:
                return None  # caminho que não é referência cifrada válida: nunca é aberto
            return REF_RE.sub(lambda m: resolve(m.group(0)) or "", o) if "sf1:" in o else o
        return o

    return walk(copy.deepcopy(obj))


@contextlib.contextmanager
def materialize(obj: Any, tenant_id: int | None) -> Iterator[tuple[Any, str]]:
    """Versão em bloco `with` de materialize_into; a pasta temporária é apagada ao sair."""
    workdir = tempfile.mkdtemp(prefix="diagpro_")
    try:
        yield materialize_into(obj, tenant_id, workdir), workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# --------------------------------------------------------------------------- arquivos nomeados (templates)
# Testes e API de teste apontam DIAGPRO_TEMPLATES_DIR para uma pasta própria: nunca mexem nos templates reais.
TEMPLATES_ROOT = Path(os.getenv("DIAGPRO_TEMPLATES_DIR") or PROJECT_ROOT / "templates_eventos")


def _named_fid(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()[:32]


def _template_path(evento_id: str, nome: str) -> Path:
    from backend.app.security import caminho_dentro_de, nome_arquivo_seguro

    nome = nome_arquivo_seguro(nome, KINDS["template"][0])
    pasta = Path(caminho_dentro_de(str(TEMPLATES_ROOT), str(evento_id)))
    return Path(caminho_dentro_de(str(pasta), nome + ".enc"))


def _template_meta_path(path: Path) -> Path:
    """Informações do template (quem enviou, quando, tamanho) num arquivo cifrado ao lado: X.docx.meta.enc."""
    return path.with_name(path.name[:-len(".enc")] + ".meta.enc")


def write_template(evento_id: str, nome: str, data: bytes, tenant_id: int, enviado_por_id: int | None = None,
                   enviado_em: str | None = None) -> None:
    path = _template_path(evento_id, nome)
    _check_magic(data, os.path.splitext(nome)[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        _encrypt_to(f, data, _scope(tenant_id), _named_fid(f"template|{evento_id}|{os.path.basename(path)}"))
    os.replace(tmp, path)
    # só o id de quem enviou (o nome é lido do cadastro ao listar: anonimização LGPD vale aqui também)
    meta = json.dumps({"enviado_por_id": enviado_por_id,
                       "enviado_em": enviado_em or datetime.now().isoformat(timespec="seconds"),
                       "tamanho": len(data)}).encode("utf-8")
    mpath = _template_meta_path(path)
    mtmp = mpath.with_suffix(".tmp")
    with open(mtmp, "wb") as f:
        _encrypt_to(f, meta, _scope(tenant_id), _named_fid(f"template-meta|{evento_id}|{os.path.basename(path)}"))
    os.replace(mtmp, mpath)
    _template_thumb_path(path).unlink(missing_ok=True)  # template novo: a miniatura antiga não vale mais


def _template_thumb_path(path: Path) -> Path:
    """Miniatura da 1ª página (como sai na prova), cifrada: X.docx.thumb.enc."""
    return path.with_name(path.name[:-len(".enc")] + ".thumb.enc")


def read_template_thumb(evento_id: str, nome: str, tenant_id: int) -> bytes | None:
    path = _template_path(evento_id, nome)
    tpath = _template_thumb_path(path)
    if not path.is_file() or not tpath.is_file():
        return None
    try:
        with open(tpath, "rb") as f:
            return _decrypt_from(f, _scope(tenant_id), _named_fid(f"template-thumb|{evento_id}|{os.path.basename(path)}"))
    except SecureFileError:
        return None


def write_template_thumb(evento_id: str, nome: str, png: bytes, tenant_id: int) -> None:
    path = _template_path(evento_id, nome)
    if not path.is_file():
        raise SecureFileError("Template não encontrado.")
    tpath = _template_thumb_path(path)
    tmp = tpath.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        _encrypt_to(f, png, _scope(tenant_id), _named_fid(f"template-thumb|{evento_id}|{os.path.basename(path)}"))
    os.replace(tmp, tpath)


def info_template(evento_id: str, nome: str, tenant_id: int) -> dict:
    """{enviado_por_id, enviado_em, tamanho}; templates antigos (sem informações) usam a data do arquivo."""
    path = _template_path(evento_id, nome)
    if not path.is_file():
        raise SecureFileError("Template não encontrado.")
    mpath = _template_meta_path(path)
    if mpath.is_file():
        try:
            with open(mpath, "rb") as f:
                return json.loads(_decrypt_from(f, _scope(tenant_id), _named_fid(f"template-meta|{evento_id}|{os.path.basename(path)}")))
        except (SecureFileError, ValueError):
            pass
    st = path.stat()
    return {"enviado_por_id": None, "enviado_em": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "tamanho": None}


def dono_banca(tenant_id: int) -> str:
    """Pasta da BIBLIOTECA de templates da banca (Configurações > Templates). Ids de evento são UUIDs: não colidem."""
    return f"banca-{int(tenant_id)}"


def read_template(evento_id: str, nome: str, tenant_id: int) -> bytes:
    """
    Template pelo nome. Procura primeiro na pasta indicada (evento antigo ou a própria biblioteca) e, se não houver,
    na biblioteca da banca — assim a exportação e a pré-visualização, que pedem "o template do evento", encontram os
    templates da biblioteca sem mudança.
    """
    path = _template_path(evento_id, nome)
    if not path.is_file():
        biblioteca = dono_banca(tenant_id)
        if str(evento_id) != biblioteca and _template_path(biblioteca, nome).is_file():
            return read_template(biblioteca, nome, tenant_id)
        raise SecureFileError("Template não encontrado.")
    with open(path, "rb") as f:
        return _decrypt_from(f, _scope(tenant_id), _named_fid(f"template|{evento_id}|{os.path.basename(path)}"))


def list_templates(evento_id: str) -> list[str]:
    from backend.app.security import caminho_dentro_de

    pasta = Path(caminho_dentro_de(str(TEMPLATES_ROOT), str(evento_id)))
    if not pasta.is_dir():
        return []
    return sorted(p.name[:-4] for p in pasta.iterdir()
                  if p.is_file() and p.name.endswith(".enc") and not p.name.endswith((".meta.enc", ".thumb.enc")))


def delete_template(evento_id: str, nome: str) -> bool:
    path = _template_path(evento_id, nome)
    if path.is_file():
        path.unlink()
        _template_meta_path(path).unlink(missing_ok=True)
        _template_thumb_path(path).unlink(missing_ok=True)
        return True
    return False


def materialize_template(evento_id: str, nome: str | None, tenant_id: int, workdir: str) -> str | None:
    """Decifra o template do evento para o gerador. Nome inválido ou inexistente => None."""
    if not nome:
        return None
    try:
        data = read_template(evento_id, nome, tenant_id)
    except Exception:
        return None
    dest = os.path.join(workdir, "template_" + os.path.basename(_template_path(evento_id, nome))[:-4])
    with open(dest, "wb") as f:
        f.write(data)
    return dest


async def save_upload_http(upload, tenant_id: int | None, kind: str) -> str:
    """save_upload para rotas: erros de validação viram HTTP 400."""
    from fastapi import HTTPException

    try:
        return await save_upload(upload, tenant_id, kind)
    except SecureFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
