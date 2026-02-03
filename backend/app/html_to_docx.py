from bs4 import BeautifulSoup
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import base64
import re
import io
from PIL import Image

def html_to_docx(doc, html, fonte="Arial", tamanho=12, default_alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """
    Converte HTML básico (gerado por editores como tiptap) para python-docx formatado.
    - doc: objeto Document
    - html: string HTML
    - fonte: nome da fonte
    - tamanho: tamanho da fonte (int ou Pt)
    """
    soup = BeautifulSoup(html, "html.parser")
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
        src = tagimg.get("src", "")
        if src.startswith("data:image"):
            # Imagem base64 inline
            match = re.match(r'data:image/(png|jpeg|jpg);base64,(.*)', src)
            if match:
                img_data = base64.b64decode(match.group(2))
                image = Image.open(io.BytesIO(img_data))
                # Ajusta tamanho se quiser (ex: width=Pt(300))
                image.save('temp_img.png')
                run = paragraph.add_run()
                run.add_picture('temp_img.png')
        elif src:
            # Imagem por URL ou caminho local
            run = paragraph.add_run()
            run.add_picture(src)

    def handle_inline(run, tag):
        # Aplica negrito, itálico, sublinhado, cor
        if tag.name == "strong" or tag.name == "b":
            run.bold = True
        if tag.name == "em" or tag.name == "i":
            run.italic = True
        if tag.name == "u":
            run.underline = True
        if tag.name == "span":
            style = tag.get("style", "")
            colorm = re.search(r'color\s*:\s*([^;]+)', style)
            if colorm:
                from docx.shared import RGBColor
                colorval = colorm.group(1)
                # Suporta cores tipo #RRGGBB
                if colorval.startswith("#"):
                    rgb = tuple(int(colorval[i:i+2], 16) for i in (1, 3, 5))
                    run.font.color.rgb = RGBColor(*rgb)
        if tag.name == "sub":
            run.font.subscript = True
        if tag.name == "sup":
            run.font.superscript = True

    def process_children(parent, paragraph, run_props={}):
        for child in parent.children:
            if isinstance(child, str):
                run = paragraph.add_run(child)
                run.font.name = fonte
                run.font.size = tamanho
                for prop, value in run_props.items():
                    setattr(run.font, prop, value)
            elif child.name == "br":
                paragraph = doc.add_paragraph()
            elif child.name == "img":
                add_img_to_docx(paragraph, child)
            elif child.name == "a":
                run = paragraph.add_run(child.get_text())
                run.font.name = fonte
                run.font.size = tamanho
                run.font.underline = True
                run.font.color.theme_color = 10  # "Hyperlink"
            elif child.name in ["strong", "b", "em", "i", "u", "span", "sub", "sup"]:
                run = paragraph.add_run(child.get_text())
                run.font.name = fonte
                run.font.size = tamanho
                handle_inline(run, child)
            else:
                # Para aninhar mais, recursivo!
                process_children(child, paragraph, run_props)
        return paragraph

    # Blocos principais
    for tag in soup.children:
        if tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            p = doc.add_paragraph()
            run = p.add_run(tag.get_text())
            run.font.name = fonte
            run.font.size = Pt(18 - (int(tag.name[1]) - 1) * 2)
            run.bold = True
            set_alignment(p, parse_style(tag.get("style", "")) or "center")
        elif tag.name in ["p", "div"]:
            p = doc.add_paragraph()
            set_alignment(p, parse_style(tag.get("style", "")))
            process_children(tag, p)
        elif tag.name == "ul":
            for li in tag.find_all("li", recursive=False):
                p = doc.add_paragraph(style="List Bullet")
                process_children(li, p)
        elif tag.name == "ol":
            for li in tag.find_all("li", recursive=False):
                p = doc.add_paragraph(style="List Number")
                process_children(li, p)
        elif tag.name == "table":
            rows = tag.find_all("tr")
            ncols = max(len(r.find_all(["td", "th"])) for r in rows)
            table = doc.add_table(rows=len(rows), cols=ncols)
            for i, row in enumerate(rows):
                cells = row.find_all(["td", "th"])
                for j, cell in enumerate(cells):
                    cell_par = table.cell(i, j).paragraphs[0]
                    process_children(cell, cell_par)
        elif tag.name == "img":
            p = doc.add_paragraph()
            add_img_to_docx(p, tag)
        elif tag.name == "blockquote":
            p = doc.add_paragraph()
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
            p = doc.add_paragraph()
            run = p.add_run(tag.string)
            run.font.name = fonte
            run.font.size = tamanho
        # Expanda conforme necessário!
