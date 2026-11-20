"""Templates de prova: informações do cartão (quando, quem, tamanho), arquivos cifrados e pré-visualização segura."""
import io
import zipfile

from docx import Document

from backend.app import secure_files
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

EV = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
BASE = f"/api/eventos/{EV}/templates"


def _docx(texto_cabecalho="CABECALHO-TIMBRADO", texto_corpo="Area util"):
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = texto_cabecalho
    doc.add_paragraph(texto_corpo)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _docx_com_entidade():
    """DOCX com DOCTYPE/entidades (ataque de expansão): a pré-visualização tem de recusar."""
    bom = _docx()
    entrada = zipfile.ZipFile(io.BytesIO(bom))
    saida_buf = io.BytesIO()
    with zipfile.ZipFile(saida_buf, "w", zipfile.ZIP_DEFLATED) as saida:
        for item in entrada.infolist():
            dados = entrada.read(item.filename)
            if item.filename == "word/document.xml":
                dados = dados.replace(b"?>", b'?><!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>', 1)
            saida.writestr(item, dados)
    return saida_buf.getvalue()


def test_tests_never_touch_the_real_templates_folder():
    from pathlib import Path
    real = (Path(__file__).resolve().parents[1] / "templates_eventos").resolve()
    assert Path(secure_files.TEMPLATES_ROOT).resolve() != real


async def test_template_cards_show_when_who_and_size_and_files_stay_encrypted(async_client):
    reset_rate_limits()
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    arquivo = _docx()
    try:
        r = await async_client.post(f"{BASE}/upload", headers=a1,
                                    files={"file": ("ZZTesteCartao.docx", arquivo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert r.status_code == 200, r.text
        lista = (await async_client.get(BASE, headers=a1)).json()
        nomes = [t["nome_arquivo"] for t in lista]
        item = next(t for t in lista if t["nome_arquivo"] == "ZZTesteCartao.docx")
        assert not any(n.endswith(".meta") for n in nomes), "o arquivo de informações não pode aparecer como template"
        assert item["tamanho"] == len(arquivo) and item["enviado_em"] and item["enviado_por"]
        # tudo cifrado no disco: nem o conteúdo nem as informações aparecem em claro
        pasta = secure_files.TEMPLATES_ROOT / EV
        for arq in pasta.iterdir():
            bruto = arq.read_bytes()
            assert b"CABECALHO-TIMBRADO" not in bruto and b"enviado_por_id" not in bruto and b"word/document.xml" not in bruto
        # pré-visualização mostra o cabeçalho
        prev = await async_client.get(f"{BASE}/{item['nome_arquivo']}/preview", headers=a1)
        assert prev.status_code == 200 and "CABECALHO-TIMBRADO" in prev.json()["header_html"]
        # outra banca não vê nem acessa o evento
        assert (await async_client.get(BASE, headers=a2)).status_code in (403, 404)
        # excluir remove o template e as informações dele
        assert (await async_client.delete(f"{BASE}/{item['nome_arquivo']}", headers=a1)).status_code == 200
        assert not [a for a in pasta.iterdir() if a.name.startswith("ZZTesteCartao")]
    finally:
        for t in (await async_client.get(BASE, headers=a1)).json():
            if t["nome_arquivo"] in ("ZZTesteCartao.docx", "ZZTesteMalicioso.docx"):
                await async_client.delete(f"{BASE}/{t['nome_arquivo']}", headers=a1)


async def test_template_preview_refuses_entity_expansion(async_client):
    reset_rate_limits()
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    try:
        r = await async_client.post(f"{BASE}/upload", headers=a1,
                                    files={"file": ("ZZTesteMalicioso.docx", _docx_com_entidade(), "application/octet-stream")})
        assert r.status_code == 200, r.text
        prev = await async_client.get(f"{BASE}/ZZTesteMalicioso.docx/preview", headers=a1)
        assert prev.status_code == 400 and "entidades" in prev.json()["detail"]
    finally:
        await async_client.delete(f"{BASE}/ZZTesteMalicioso.docx", headers=a1)


async def test_template_thumbnail_is_rendered_cached_encrypted_and_invalidated(async_client):
    from core.document_generator import PdfConverter

    reset_rate_limits()
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    nome = "ZZTesteMiniatura.docx"
    try:
        r = await async_client.post(f"{BASE}/upload", headers=a1, files={"file": (nome, _docx(), "application/octet-stream")})
        assert r.status_code == 200 and r.json()["nome_arquivo"] == nome
        r = await async_client.get(f"{BASE}/{nome}/miniatura", headers=a1)
        if not PdfConverter().soffice_path:  # CI sem LibreOffice: resposta clara, e a tela usa a pré-visualização em HTML
            assert r.status_code == 503
            return
        assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert "no-store" in r.headers["cache-control"]
        pasta = secure_files.TEMPLATES_ROOT / EV
        thumb = pasta / f"{nome}.thumb.enc"
        assert thumb.is_file() and b"\x89PNG" not in thumb.read_bytes()  # guardada cifrada
        assert nome + ".thumb" not in [t["nome_arquivo"] for t in (await async_client.get(BASE, headers=a1)).json()]
        # reenviar o template invalida a miniatura antiga
        assert (await async_client.post(f"{BASE}/upload", headers=a1, files={"file": (nome, _docx("OUTRO"), "application/octet-stream")})).status_code == 200
        assert not thumb.exists()
        # excluir apaga tudo
        assert (await async_client.get(f"{BASE}/{nome}/miniatura", headers=a1)).status_code == 200 and thumb.exists()
        assert (await async_client.delete(f"{BASE}/{nome}", headers=a1)).status_code == 200
        assert not [a for a in pasta.iterdir() if a.name.startswith("ZZTesteMiniatura")]
    finally:
        await async_client.delete(f"{BASE}/{nome}", headers=a1)
