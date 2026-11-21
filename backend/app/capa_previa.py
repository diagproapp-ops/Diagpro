"""
Pré-visualização da capa do cargo: o MESMO preenchimento da exportação (PDFBox, campos de formulário do PDF)
com dados de exemplo, desenhado como imagem. Também lista os campos que o PDF tem, para o guia mostrar quais o
DiagPro reconhece. Tudo numa pasta temporária apagada no fim; nada fica no disco.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_CLASSPATH = os.pathsep.join(str(RAIZ / p) for p in ("backend/app/pdfbox-app-3.0.5.jar", "backend/app/json.jar", "backend/app"))
LIMITE_PAGINAS = 1


class CapaInvalida(Exception):
    pass


def campos_do_pdf(dados: bytes) -> list[str] | None:
    """Nomes dos campos de formulário do PDF; None se o PDF não tem formulário."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        leitor = PdfReader(io.BytesIO(dados))
        if leitor.is_encrypted:
            raise CapaInvalida("O PDF da capa está protegido por senha.")
        campos = leitor.get_fields()
    except PdfReadError:
        raise CapaInvalida("Arquivo PDF inválido ou corrompido.")
    if not campos:
        return None
    return sorted(campos.keys())


def _desenhar(pdf: bytes) -> bytes:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        if len(doc) == 0:
            raise CapaInvalida("O PDF da capa não tem páginas.")
        img = doc[0].render(scale=1.6).to_pil().convert("RGB")
    finally:
        doc.close()
    saida = io.BytesIO()
    img.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def gerar_previa(dados: bytes, valores: dict[str, str], tem_formulario: bool) -> tuple[bytes, bool]:
    """(PNG da 1ª página, se os campos foram preenchidos). Sem formulário: mostra o PDF como está."""
    if not tem_formulario:
        return _desenhar(dados), False
    with tempfile.TemporaryDirectory(prefix="diagpro_capa_") as tmp:
        modelo = os.path.join(tmp, "modelo.pdf")
        json_dados = os.path.join(tmp, "dados.json")
        saida = os.path.join(tmp, "saida")
        with open(modelo, "wb") as f:
            f.write(dados)
        with open(json_dados, "w", encoding="utf-8") as f:
            json.dump([{**valores, "Inscricao": "previa"}], f, ensure_ascii=False)
        try:
            subprocess.run(["java", "-cp", _CLASSPATH, "PreencheCapaPDF_JSON_PDFBox", modelo, json_dados, saida],
                           capture_output=True, timeout=90, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return _desenhar(dados), False
        preenchida = os.path.join(saida, "previa_capa.pdf")
        if not os.path.exists(preenchida):
            return _desenhar(dados), False
        with open(preenchida, "rb") as f:
            return _desenhar(f.read()), True
