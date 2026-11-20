from bs4 import BeautifulSoup, NavigableString, Comment
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import base64
import binascii
import logging
import re
import io
from PIL import Image

logger = logging.getLogger(__name__)

# Largura máxima de imagem embutida no texto (cabe numa coluna A4 com margens comuns).
_LARGURA_MAX_IMAGEM = Inches(6)

_BLOCOS_INTERNOS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}


def _cor(valor):
    """'#RRGGBB', '#RGB' ou 'rgb(r, g, b)' -> RGBColor (None se não reconhecer)."""
    valor = (valor or "").strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{6})", valor)
    if m:
        return RGBColor.from_string(m.group(1).upper())
    m = re.fullmatch(r"#([0-9a-f]{3})", valor)
    if m:
        return RGBColor.from_string("".join(ch * 2 for ch in m.group(1)).upper())
    m = re.fullmatch(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*[\d.]+)?\s*\)", valor)
    if m:
        return RGBColor(*(min(int(x), 255) for x in m.groups()))
    return None


def html_to_docx(doc, html, fonte="Arial", tamanho=12, default_alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """
    Converte o HTML do editor (tiptap) para python-docx.
    - doc: objeto Document
    - html: string HTML
    - fonte: nome da fonte
    - tamanho: tamanho da fonte (int ou Pt)

    Formatação reproduzida (inclusive aninhada, ex.: negrito + itálico): negrito, itálico, sublinhado,
    tachado, marca-texto, sobrescrito, subscrito e cor; listas (com subníveis), citação, tabela,
    alinhamento e linha horizontal.

    Segurança: imagens só entram se vierem embutidas no próprio texto (data:image/...), lidas em
    memória — nada é gravado em disco e nenhum caminho/URL do HTML é aberto.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    tamanho = Pt(tamanho) if not isinstance(tamanho, Pt) else tamanho

    def set_alignment(p, align):
        if align == 'center':
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align == 'right':
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif align == 'left':
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif align == 'justify':
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        else:
            p.alignment = default_alignment

    def parse_style(style):
        # Checa por text-align no atributo style
        if not style:
            return None
        m = re.search(r'text-align\s*:\s*(left|right|center|justify)', style)
        return m.group(1) if m else None

    def add_img_to_docx(paragraph, tagimg):
        src = (tagimg.get("src") or "").strip()
        match = re.match(r'data:image/(png|jpeg|jpg|gif|bmp);base64,(.*)', src, re.S)
        if not match:
            if src:
                logger.warning("Imagem ignorada no texto: só imagens embutidas (data:image) são aceitas.")
            return
        try:
            img_data = base64.b64decode(match.group(2), validate=False)
            with Image.open(io.BytesIO(img_data)) as image:
                largura_px = image.width
                dpi = (image.info.get("dpi") or (96, 96))[0] or 96
            largura = Inches(largura_px / float(dpi))
            run = paragraph.add_run()
            run.add_picture(io.BytesIO(img_data), width=min(largura, _LARGURA_MAX_IMAGEM))
        except (binascii.Error, ValueError, OSError) as exc:
            logger.warning("Imagem inválida ignorada no texto: %s", exc)

    def aplicar(run, fmt):
        run.font.name = fonte
        run.font.size = tamanho
        if fmt.get("b"):
            run.bold = True
        if fmt.get("i"):
            run.italic = True
        if fmt.get("u"):
            run.underline = True
        if fmt.get("s"):
            run.font.strike = True
        if fmt.get("sup"):
            run.font.superscript = True
        if fmt.get("sub"):
            run.font.subscript = True
        if fmt.get("mark"):
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
        if fmt.get("cor") is not None:
            run.font.color.rgb = fmt["cor"]
        if fmt.get("link"):
            run.font.underline = True
            run.font.color.theme_color = 10  # "Hyperlink"

    def formato_de(tag, fmt):
        novo = dict(fmt)
        nome = tag.name
        if nome in ("strong", "b"):
            novo["b"] = True
        elif nome in ("em", "i"):
            novo["i"] = True
        elif nome == "u":
            novo["u"] = True
        elif nome in ("s", "strike", "del"):
            novo["s"] = True
        elif nome == "sup":
            novo["sup"] = True
        elif nome == "sub":
            novo["sub"] = True
        elif nome == "mark":
            novo["mark"] = True
        elif nome == "a":
            novo["link"] = True
        elif nome in ("th",):
            novo["b"] = True
        estilo = tag.get("style", "") or ""
        m = re.search(r'(?:^|;)\s*color\s*:\s*([^;]+)', estilo)
        if m:
            cor = _cor(m.group(1))
            if cor is not None:
                novo["cor"] = cor
        return novo

    def process_children(parent, paragraph, fmt=None):
        """Escreve o conteúdo de `parent` em `paragraph`, herdando a formatação dos ancestrais."""
        fmt = fmt or {}
        for child in parent.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                texto = str(child)
                if texto:
                    aplicar(paragraph.add_run(texto), fmt)
            elif child.name == "br":
                paragraph.add_run().add_break()
            elif child.name == "img":
                add_img_to_docx(paragraph, child)
            elif child.name in ("ul", "ol"):
                continue  # sublistas são tratadas por render_lista
            else:
                # vários parágrafos dentro de um item de lista / célula: quebra de linha entre eles
                if child.name in _BLOCOS_INTERNOS and paragraph.runs:
                    paragraph.add_run().add_break()
                process_children(child, paragraph, formato_de(child, fmt))
        return paragraph

    def paragrafo_lista(estilo_base, nivel):
        nomes = [f"{estilo_base} {nivel + 1}" if nivel else estilo_base, estilo_base]
        for nome in nomes:
            try:
                p = doc.add_paragraph(style=nome)
                break
            except KeyError:
                continue
        else:
            p = doc.add_paragraph()
        if nivel and p.style.name == estilo_base:
            p.paragraph_format.left_indent = Pt(18 * (nivel + 1))
        return p

    def render_lista(tag, nivel=0):
        estilo = "List Bullet" if tag.name == "ul" else "List Number"
        for li in tag.find_all("li", recursive=False):
            p = paragrafo_lista(estilo, min(nivel, 2))
            set_alignment(p, parse_style(li.get("style", "")) or "left")
            process_children(li, p)
            for sub in li.find_all(["ul", "ol"], recursive=False):
                render_lista(sub, nivel + 1)
            # sublistas dentro de <p> do item (HTML de outras origens)
            for bloco in li.find_all(_BLOCOS_INTERNOS, recursive=False):
                for sub in bloco.find_all(["ul", "ol"], recursive=False):
                    render_lista(sub, nivel + 1)

    def render_tabela(tag):
        rows = tag.find_all("tr")
        if not rows:
            return
        ncols = max((len(r.find_all(["td", "th"], recursive=False)) for r in rows), default=0)
        if not ncols:
            return
        table = doc.add_table(rows=len(rows), cols=ncols)
        try:
            table.style = "Table Grid"  # bordas visíveis na prova
        except (KeyError, ValueError):
            pass
        for i, row in enumerate(rows):
            for j, cell in enumerate(row.find_all(["td", "th"], recursive=False)):
                cell_par = table.cell(i, j).paragraphs[0]
                set_alignment(cell_par, parse_style(cell.get("style", "")) or "left")
                process_children(cell, cell_par, formato_de(cell, {}))

    # Blocos principais
    for tag in soup.children:
        if isinstance(tag, Comment):
            continue
        if tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            p = doc.add_paragraph()
            set_alignment(p, parse_style(tag.get("style", "")) or "center")
            process_children(tag, p, {"b": True})
            for run in p.runs:
                run.font.size = Pt(18 - (int(tag.name[1]) - 1) * 2)
        elif tag.name in ["p", "div"]:
            p = doc.add_paragraph()
            set_alignment(p, parse_style(tag.get("style", "")))
            process_children(tag, p)
        elif tag.name in ("ul", "ol"):
            render_lista(tag)
        elif tag.name == "table":
            render_tabela(tag)
        elif tag.name == "img":
            p = doc.add_paragraph()
            add_img_to_docx(p, tag)
        elif tag.name == "blockquote":
            p = doc.add_paragraph()
            set_alignment(p, None)
            process_children(tag, p)
            p.paragraph_format.left_indent = Pt(24)
        elif tag.name == "hr":
            p = doc.add_paragraph()
            p_par = p._p.get_or_add_pPr()
            p_bdr = OxmlElement('w:pBdr')
            p_par.append(p_bdr)
            bottom_bdr = OxmlElement('w:bottom')
            bottom_bdr.set(qn('w:val'), 'single')
            bottom_bdr.set(qn('w:sz'), '24')
            bottom_bdr.set(qn('w:space'), '1')
            bottom_bdr.set(qn('w:color'), 'auto')
            p_bdr.append(bottom_bdr)
        elif tag.name is None:
            # Texto solto fora de tag
            if str(tag).strip():
                p = doc.add_paragraph()
                set_alignment(p, None)
                aplicar(p.add_run(str(tag)), {})
        elif tag.name in ("strong", "b", "em", "i", "u", "s", "strike", "del", "sup", "sub", "mark", "span", "a"):
            # Trecho formatado solto fora de parágrafo
            p = doc.add_paragraph()
            set_alignment(p, None)
            process_children(tag, p, formato_de(tag, {}))
        else:
            p = doc.add_paragraph()
            set_alignment(p, None)
            process_children(tag, p)
