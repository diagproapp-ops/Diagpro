"""Capa do cargo: guia dos campos, prévia preenchida como na exportação, campos reconhecidos e capa antiga."""
import base64
import io
import shutil

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.app import campos_capa
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import EVENTO_TESTE, auth_headers

A1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
A2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
HP = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)


def _pdf_com_campos(*nomes) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 800, "CAPA DE TESTE")
    for i, nome in enumerate(nomes):
        c.acroForm.textfield(name=nome, x=72, y=740 - i * 40, width=400, height=24, value="")
    c.save()
    return buf.getvalue()


async def _enviar(client, pdf: bytes) -> str:
    r = await client.post(f"/eventos/{EVENTO_TESTE}/cargos/upload-capa-pdf", headers=A1,
                          files={"file": ("capa.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["cover_pdf_paths"][0]


async def test_cover_guide_preview_fields_and_legacy_path(async_client):
    reset_rate_limits()
    # guia: só quem monta prova; todos os campos automáticos que o preenchimento realmente envia
    assert (await async_client.get("/cargos/capa/guia", headers=HP)).status_code == 403
    guia = (await async_client.get("/cargos/capa/guia", headers=A1)).json()["campos"]
    automaticos = {g["campo"] for g in guia if g["origem"] == "automatico"}
    enviados = campos_capa.montar_dados_capa({}, None, None, None, "", "Tipo A", "", "", "", letra_tipo="A")
    assert automaticos <= set(enviados) and {"NomeEvento", "NomeCargo", "LetraTipo", "Empresa"} <= automaticos
    assert all(isinstance(v, str) for v in enviados.values())  # o PDFBox só aceita texto

    url = f"/eventos/{EVENTO_TESTE}/cargos/capa/previa"
    ref = await _enviar(async_client, _pdf_com_campos("NomeEvento", "NomeCargo", "LetraTipo", "CampoInventado"))
    assert (await async_client.post(url, headers=HP, json={"ref": ref})).status_code == 403
    assert (await async_client.post(f"/eventos/{EVENTO_TESTE}/cargos/capa/previa", headers=A2, json={"ref": ref})).status_code in (403, 404)
    r = await async_client.post(url, headers=A1, json={"ref": ref, "nome_cargo": "Analista", "codigo_cargo": "AN-01"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["legado"] is False and d["sem_formulario"] is False
    assert set(d["reconhecidos"]) == {"NomeEvento", "NomeCargo", "LetraTipo"} and d["desconhecidos"] == ["CampoInventado"]
    img = Image.open(io.BytesIO(base64.b64decode(d["imagem"].split(",", 1)[1])))
    assert img.format == "PNG" and img.width > 800
    if shutil.which("java"):
        assert d["preenchida"] is True  # mesmo preenchimento (PDFBox) da exportação

    # PDF sem formulário: mostra como está e avisa
    sem = await _enviar(async_client, _pdf_com_campos())
    d = (await async_client.post(url, headers=A1, json={"ref": sem})).json()
    assert d["sem_formulario"] is True and d["preenchida"] is False and d["campos_no_pdf"] == []

    # capa antiga (caminho de pasta do computador): pede para importar de novo, sem ler o disco
    d = (await async_client.post(url, headers=A1, json={"ref": "C:/Users/alguem/Capas/Capa 2.pdf"})).json()
    assert d["legado"] is True and "Importar" in d["mensagem"]
    assert (await async_client.post(url, headers=A1, json={"ref": "qualquer-coisa"})).status_code == 400
    reset_rate_limits()
