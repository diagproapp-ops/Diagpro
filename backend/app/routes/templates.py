import base64
import html
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import secure_files
from backend.app.db_models import User
from backend.app.roles import UserRole
from backend.app.security import evento_autorizado, get_tenant_db, require_roles

router = APIRouter()

TAMANHO_MAX_TEMPLATE = secure_files.KINDS["template"][1]

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_V_NS = "{urn:schemas-microsoft-com:vml}"
_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

_IMG_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
}


# Limites da pré-visualização: um DOCX enviado não pode travar o servidor (bomba de compressão/entidades)
_MAX_XML_BYTES = 8 * 1024 * 1024
_MAX_IMAGEM_BYTES = 4 * 1024 * 1024
_MAX_IMAGENS_TOTAL = 12 * 1024 * 1024


class _DocxSuspeito(ValueError):
    pass


def _ler_xml(zf: zipfile.ZipFile, nome: str) -> ET.Element:
    """Lê uma parte XML do DOCX recusando DOCTYPE/entidades (DOCX legítimo não tem) e tamanhos absurdos."""
    if zf.getinfo(nome).file_size > _MAX_XML_BYTES:
        raise _DocxSuspeito("Parte do DOCX grande demais.")
    dados = zf.read(nome)
    if b"<!DOCTYPE" in dados or b"<!ENTITY" in dados:
        raise _DocxSuspeito("DOCX com declarações de entidades não é aceito.")
    return ET.fromstring(dados)


def _carregar_rels_imagens(zf: zipfile.ZipFile, part_path: str, orcamento: list[int]) -> dict[str, str]:
    """Mapeia rId -> data:image/...;base64,... para a parte XML do DOCX (com limite de tamanho por imagem e no total)."""
    part_dir, _, part_name = part_path.rpartition("/")
    rels_path = f"{part_dir}/_rels/{part_name}.rels" if part_dir else f"_rels/{part_name}.rels"
    if rels_path not in zf.namelist():
        return {}
    mapa: dict[str, str] = {}
    root = _ler_xml(zf, rels_path)
    for rel in root.findall(f"{_REL_NS}Relationship"):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if not rid or not target:
            continue
        norm = target.lstrip("/")
        if norm.startswith("../"):
            norm = "word/" + norm.replace("../", "", 1)
        elif not norm.startswith("word/") and part_dir:
            norm = f"{part_dir}/{norm}"
        if norm not in zf.namelist():
            continue
        ext = norm.rsplit(".", 1)[-1].lower()
        mime = _IMG_MIME.get(ext)
        if not mime:
            continue
        tamanho = zf.getinfo(norm).file_size
        if tamanho > _MAX_IMAGEM_BYTES or tamanho > orcamento[0]:
            continue  # imagem grande demais para a pré-visualização (o template continua valendo na exportação)
        orcamento[0] -= tamanho
        b64 = base64.b64encode(zf.read(norm)).decode("ascii")
        mapa[rid] = f"data:{mime};base64,{b64}"
    return mapa


def _render_paragraph(p: ET.Element, imgs: dict[str, str]) -> str:
    p_pr = p.find(f"{_W_NS}pPr")
    align = ""
    if p_pr is not None:
        jc = p_pr.find(f"{_W_NS}jc")
        if jc is not None:
            val = jc.attrib.get(f"{_W_NS}val", "")
            if val in ("center", "right", "left", "both"):
                align = "justify" if val == "both" else val

    partes: list[str] = []
    # Imagens dentro de drawing / pict
    seen_rids: set[str] = set()
    for blip in p.iter(f"{_A_NS}blip"):
        rid = blip.attrib.get(f"{_R_NS}embed") or blip.attrib.get(f"{_R_NS}link")
        if rid and rid in imgs and rid not in seen_rids:
            seen_rids.add(rid)
            partes.append(f'<img src="{imgs[rid]}" alt="Imagem do template" style="max-width:100%;max-height:150px;height:auto;vertical-align:middle;" />')
    for vimg in p.iter(f"{_V_NS}imagedata"):
        rid = vimg.attrib.get(f"{_R_NS}id")
        if rid and rid in imgs and rid not in seen_rids:
            seen_rids.add(rid)
            partes.append(f'<img src="{imgs[rid]}" alt="Imagem do template" style="max-width:100%;max-height:150px;height:auto;vertical-align:middle;" />')

    # Runs de texto
    for run in p.findall(f".//{_W_NS}r"):
        textos = [t.text or "" for t in run.findall(f"{_W_NS}t")]
        txt = html.escape("".join(textos))
        if not txt:
            continue
        r_pr = run.find(f"{_W_NS}rPr")
        styles: list[str] = []
        if r_pr is not None:
            if r_pr.find(f"{_W_NS}b") is not None:
                styles.append("font-weight:700")
            if r_pr.find(f"{_W_NS}i") is not None:
                styles.append("font-style:italic")
            color_el = r_pr.find(f"{_W_NS}color")
            if color_el is not None:
                cval = color_el.attrib.get(f"{_W_NS}val", "")
                if len(cval) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in cval):
                    styles.append(f"color:#{cval}")
            sz_el = r_pr.find(f"{_W_NS}sz")
            if sz_el is not None and (sz_el.attrib.get(f"{_W_NS}val") or "").isdigit():
                pt = max(8, min(28, int(sz_el.attrib[f"{_W_NS}val"]) // 2))
                styles.append(f"font-size:{pt}pt")
        style_attr = f' style="{";".join(styles)}"' if styles else ""
        partes.append(f"<span{style_attr}>{txt}</span>")

    if not partes:
        return ""
    align_style = f"text-align:{align};" if align else ""
    return f'<p style="margin:0 0 6px 0;{align_style}">{"".join(partes)}</p>'


def _render_part_xml(zf: zipfile.ZipFile, part_path: str, orcamento: list[int]) -> str:
    if part_path not in zf.namelist():
        return ""
    imgs = _carregar_rels_imagens(zf, part_path, orcamento)
    root = _ler_xml(zf, part_path)
    container = root.find(f"{_W_NS}body")
    if container is None:
        container = root

    blocos: list[str] = []
    for child in list(container):
        tag = child.tag
        if tag == f"{_W_NS}p":
            h = _render_paragraph(child, imgs)
            if h:
                blocos.append(h)
        elif tag == f"{_W_NS}tbl":
            linhas: list[str] = []
            for tr in child.findall(f"{_W_NS}tr"):
                celulas: list[str] = []
                for tc in tr.findall(f"{_W_NS}tc"):
                    ps = [_render_paragraph(p, imgs) for p in tc.findall(f"{_W_NS}p")]
                    conteudo_tc = "".join(x for x in ps if x) or "&nbsp;"
                    celulas.append(f'<td style="padding:4px 8px;vertical-align:middle;">{conteudo_tc}</td>')
                if celulas:
                    linhas.append(f"<tr>{''.join(celulas)}</tr>")
            if linhas:
                blocos.append(f'<table style="width:100%;border-collapse:collapse;margin-bottom:6px;">{"".join(linhas)}</table>')
    return "".join(blocos)


def _extrair_preview_docx(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        nomes = sorted(zf.namelist())
        headers = [n for n in nomes if n.startswith("word/header") and n.endswith(".xml")]
        footers = [n for n in nomes if n.startswith("word/footer") and n.endswith(".xml")]
        orcamento = [_MAX_IMAGENS_TOTAL]
        header_html = "".join(_render_part_xml(zf, h, orcamento) for h in headers)
        body_html = _render_part_xml(zf, "word/document.xml", orcamento)
        footer_html = "".join(_render_part_xml(zf, f, orcamento) for f in footers)
    return {
        "header_html": header_html,
        "body_html": body_html,
        "footer_html": footer_html,
    }


@router.get("/eventos/{evento_id}/templates", response_model=List[dict])
async def listar_templates(evento=Depends(evento_autorizado), db: AsyncSession = Depends(get_tenant_db)):
    """Templates do evento com quando foi enviado, por quem (nome lido do cadastro) e tamanho."""
    evento_id = evento.id_evento
    itens = []
    for nome in secure_files.list_templates(evento_id):
        try:
            info = secure_files.info_template(evento_id, nome, evento.tenant_id)
        except secure_files.SecureFileError:
            continue
        itens.append({"nome_arquivo": nome, "url": f"/api/eventos/{evento_id}/templates/{nome}", "descricao": "",
                      "enviado_em": info.get("enviado_em"), "tamanho": info.get("tamanho"),
                      "_por": info.get("enviado_por_id")})
    ids = {i["_por"] for i in itens if isinstance(i["_por"], int)}
    nomes: dict[int, str] = {}
    if ids:
        for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars():
            nomes[u.id] = u.full_name or u.username
    for i in itens:
        i["enviado_por"] = nomes.get(i.pop("_por"))
    # mais recentes primeiro
    return sorted(itens, key=lambda i: i.get("enviado_em") or "", reverse=True)


@router.get("/eventos/{evento_id}/templates/{nome_arquivo}/preview")
def preview_template(nome_arquivo: str, evento=Depends(evento_autorizado)):
    if not nome_arquivo.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Preview disponível apenas para arquivos .docx.")
    try:
        data = secure_files.read_template(evento.id_evento, nome_arquivo, evento.tenant_id)
        preview = _extrair_preview_docx(data)
    except secure_files.SecureFileError:
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        raise HTTPException(status_code=400, detail="Arquivo .docx inválido ou corrompido.")
    except _DocxSuspeito as exc:
        raise HTTPException(status_code=400, detail=f"Não foi possível pré-visualizar: {exc}")
    return {"nome_arquivo": nome_arquivo, **preview}


@router.get("/eventos/{evento_id}/templates/{nome_arquivo}")
def baixar_template(nome_arquivo: str, evento=Depends(evento_autorizado)):
    try:
        data = secure_files.read_template(evento.id_evento, nome_arquivo, evento.tenant_id)
    except secure_files.SecureFileError:
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    ext = nome_arquivo.rsplit(".", 1)[-1].lower()
    return Response(
        content=data,
        media_type=secure_files.MEDIA_TYPES.get(ext, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{nome_arquivo}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/eventos/{evento_id}/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    conteudo = await file.read(TAMANHO_MAX_TEMPLATE + 1)
    if len(conteudo) > TAMANHO_MAX_TEMPLATE:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 20 MB.")
    try:
        secure_files.write_template(evento.id_evento, file.filename or "", conteudo, evento.tenant_id,
                                    enviado_por_id=getattr(current_user, "id", None))
    except secure_files.SecureFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "nome_arquivo": file.filename}


@router.delete("/eventos/{evento_id}/templates/{nome_arquivo}")
def deletar_template(
    nome_arquivo: str,
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    if not secure_files.delete_template(evento.id_evento, nome_arquivo):
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    return {"ok": True}
