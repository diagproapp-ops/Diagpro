"""Conversão do HTML do editor de questões para a prova (DOCX): formatação fiel e nada gravado em disco."""
import base64
import io
import os

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from PIL import Image

from backend.app.html_to_docx import html_to_docx


def _runs(doc):
    return [r for p in doc.paragraphs for r in p.runs if r.text]


def _run(doc, texto):
    return next(r for r in _runs(doc) if r.text == texto)


def test_nested_marks_strike_highlight_and_color():
    doc = Document()
    html_to_docx(doc, (
        '<p>Normal <strong>negrito <em>negrito-italico</em></strong> '
        '<u>sub</u> <s>tachado</s> <mark>marcado</mark> <sup>2</sup><sub>3</sub> '
        '<span style="color: rgb(255, 0, 0)">vermelho</span></p>'
    ))
    assert _run(doc, "negrito ").bold and not _run(doc, "negrito ").italic
    ni = _run(doc, "negrito-italico")
    assert ni.bold and ni.italic, "formatação aninhada tem de somar"
    assert _run(doc, "sub").underline
    assert _run(doc, "tachado").font.strike
    assert _run(doc, "marcado").font.highlight_color == WD_COLOR_INDEX.YELLOW
    assert _run(doc, "2").font.superscript and _run(doc, "3").font.subscript
    assert str(_run(doc, "vermelho").font.color.rgb) == "FF0000"
    assert not _run(doc, "Normal ").bold


def test_lists_with_sublevel_quote_and_table_with_borders():
    doc = Document()
    html_to_docx(doc, (
        '<ul><li><p>item <strong>um</strong></p><ul><li><p>subitem</p></li></ul></li><li><p>dois</p></li></ul>'
        '<ol><li><p>primeiro</p></li></ol>'
        '<blockquote><p>texto de apoio</p></blockquote>'
        '<table><tbody><tr><th><p>Cab</p></th><th><p>B</p></th></tr><tr><td><p>x</p></td><td><p><em>y</em></p></td></tr></tbody></table>'
    ))
    estilos = {p.text: p.style.name for p in doc.paragraphs if p.text}
    assert estilos["item um"] == "List Bullet"
    assert estilos["subitem"] == "List Bullet 2"
    assert estilos["dois"] == "List Bullet"
    assert estilos["primeiro"] == "List Number"
    assert _run(doc, "um").bold
    citacao = next(p for p in doc.paragraphs if p.text == "texto de apoio")
    assert citacao.paragraph_format.left_indent is not None
    tabela = doc.tables[0]
    assert tabela.style.name == "Table Grid"
    assert tabela.cell(0, 0).text == "Cab" and tabela.cell(0, 0).paragraphs[0].runs[0].bold
    assert tabela.cell(1, 1).paragraphs[0].runs[0].italic


def test_embedded_image_stays_in_memory_and_local_paths_are_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "red").save(buf, format="PNG")
    data = base64.b64encode(buf.getvalue()).decode()

    segredo = tmp_path / "segredo.png"
    Image.new("RGB", (10, 10), "blue").save(segredo)

    doc = Document()
    html_to_docx(doc, f'<p>antes<img src="data:image/png;base64,{data}">depois</p><img src="{segredo}"><p><img src="file:///{segredo}"></p>')

    assert len(doc.inline_shapes) == 1, "só a imagem embutida entra; caminho local nunca é aberto"
    assert sorted(os.listdir(tmp_path)) == ["segredo.png"], "nada pode ser gravado em disco (antes: temp_img.png)"


def test_invalid_image_is_ignored_without_breaking_export():
    doc = Document()
    html_to_docx(doc, '<p>texto<img src="data:image/png;base64,naoeimagem"></p>')
    assert doc.paragraphs[0].text == "texto"
    assert len(doc.inline_shapes) == 0
