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

from backend.app import equacoes

logger = logging.getLogger(__name__)

# Largura máxima de imagem embutida no texto (cabe numa coluna A4 com margens comuns).
_LARGURA_MAX_IMAGEM = Inches(6)

_BLOCOS_INTERNOS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}
_INLINE_FORMATO = ("strong", "b", "em", "i", "u", "s", "strike", "del", "sup", "sub", "mark", "span", "a")

# Cores de marca-texto que o Word aceita (o DOCX não tem marca-texto de cor livre)
_MARCA_TEXTO = {
    WD_COLOR_INDEX.YELLOW: (255, 255, 0), WD_COLOR_INDEX.BRIGHT_GREEN: (0, 255, 0),
    WD_COLOR_INDEX.TURQUOISE: (0, 255, 255), WD_COLOR_INDEX.PINK: (255, 0, 255),
    WD_COLOR_INDEX.BLUE: (0, 0, 255), WD_COLOR_INDEX.RED: (255, 0, 0),
    WD_COLOR_INDEX.GRAY_25: (192, 192, 192), WD_COLOR_INDEX.GRAY_50: (128, 128, 128),
    WD_COLOR_INDEX.TEAL: (0, 128, 128), WD_COLOR_INDEX.GREEN: (0, 128, 0),
    WD_COLOR_INDEX.VIOLET: (128, 0, 128), WD_COLOR_INDEX.DARK_YELLOW: (128, 128, 0),
}


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


def _marca_texto_mais_proxima(valor):
    cor = _cor(valor)
    if cor is None:
        return WD_COLOR_INDEX.YELLOW
    r, g, b = cor[0], cor[1], cor[2]
    return min(_MARCA_TEXTO, key=lambda k: sum((a - c) ** 2 for a, c in zip(_MARCA_TEXTO[k], (r, g, b))))


def _tamanho_pt(valor):
    """'14pt', '16px', '1.2em' -> pontos (None se não reconhecer)."""
    m = re.fullmatch(r"\s*([\d.]+)\s*(pt|px|em|rem)?\s*", valor or "")
    if not m:
        return None
    n = float(m.group(1))
    unidade = m.group(2) or "pt"
    if unidade == "px":
        n = n * 0.75
    elif unidade in ("em", "rem"):
        n = n * 12
    return n if 4 <= n <= 96 else None


def _estilo(tag, prop):
    m = re.search(r'(?:^|;)\s*' + re.escape(prop) + r'\s*:\s*([^;]+)', tag.get("style", "") or "")
    return m.group(1).strip() if m else None


def html_to_docx(doc, html, fonte="Arial", tamanho=12, default_alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """
    Converte o HTML do editor (tiptap) para python-docx.
    - doc: objeto Document
    - html: string HTML
    - fonte: nome da fonte
    - tamanho: tamanho da fonte (int ou Pt)

    Reproduz (inclusive combinado, ex.: negrito + itálico): negrito, itálico, sublinhado, tachado, marca-texto
    (cor mais próxima das que o Word aceita), sobrescrito, subscrito, cor, fonte e tamanho; equações (nativas do
    Word, editáveis); listas com subníveis, citação, títulos, tabela (com células mescladas), alinhamento,
    espaçamento entre linhas, recuos e linha horizontal.

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

    def formatar_paragrafo(p, tag, alinhamento_padrao=None):
        """Alinhamento, espaçamento entre linhas e recuos vindos do editor."""
        set_alignment(p, parse_style(tag.get("style", "")) or alinhamento_padrao)
        altura = _estilo(tag, "line-height")
        if altura:
            try:
                valor = float(altura.rstrip("%")) / (100 if altura.endswith("%") else 1)
                if 0.8 <= valor <= 4:
                    p.paragraph_format.line_spacing = valor
            except ValueError:
                pass
        recuo = _estilo(tag, "margin-left") or _estilo(tag, "padding-left")
        if recuo:
            pts = _tamanho_pt(recuo)
            if pts:
                p.paragraph_format.left_indent = Pt(min(pts, 200))
        primeira = _estilo(tag, "text-indent")
        if primeira:
            pts = _tamanho_pt(primeira)
            if pts:
                p.paragraph_format.first_line_indent = Pt(min(pts, 100))

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
            # largura escolhida no editor (style="width: 50%") = fração da largura útil
            pct = _estilo(tagimg, "width")
            m = re.fullmatch(r"([\d.]+)\s*%", pct or "")
            if m and 5 <= float(m.group(1)) <= 100:
                largura = int(_LARGURA_MAX_IMAGEM * float(m.group(1)) / 100)
            run = paragraph.add_run()
            run.add_picture(io.BytesIO(img_data), width=min(largura, _LARGURA_MAX_IMAGEM))
        except (binascii.Error, ValueError, OSError) as exc:
            logger.warning("Imagem inválida ignorada no texto: %s", exc)

    def add_equacao(paragraph, tag, bloco=False):
        latex = tag.get("data-latex") or ""
        try:
            paragraph._p.append(equacoes.latex_para_omml(latex, bloco=bloco, tamanho_pt=tamanho.pt))
        except equacoes.EquacaoInvalida as exc:
            # a checagem antes de exportar já bloqueia; aqui só não deixa a equação sumir em silêncio
            logger.warning("Equação não convertida (%s): %s", exc, latex[:80])
            run = paragraph.add_run(latex)
            run.italic = True
            run.font.name = fonte
            run.font.size = tamanho

    def eh_equacao(tag):
        return getattr(tag, "name", None) in ("span", "div") and tag.get("data-type") in ("inline-math", "block-math", "math")

    def aplicar(run, fmt):
        run.font.name = fmt.get("fonte") or fonte
        run.font.size = Pt(fmt["tamanho"]) if fmt.get("tamanho") else tamanho
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
            run.font.highlight_color = fmt["mark"]
        if fmt.get("cor") is not None:
            run.font.color.rgb = fmt["cor"]
        if fmt.get("link"):
            run.font.underline = True
            run.font.color.theme_color = 10  # "Hyperlink"

    def formato_de(tag, fmt):
        novo = dict(fmt)
        nome = tag.name
        if nome in ("strong", "b", "th"):
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
            novo["mark"] = _marca_texto_mais_proxima(tag.get("data-color") or _estilo(tag, "background-color"))
        elif nome == "a":
            novo["link"] = True
        cor = _estilo(tag, "color")
        if cor and _cor(cor) is not None:
            novo["cor"] = _cor(cor)
        fundo = _estilo(tag, "background-color")
        if fundo and nome != "mark" and nome not in ("td", "th"):
            novo["mark"] = _marca_texto_mais_proxima(fundo)
        familia = _estilo(tag, "font-family")
        if familia:
            nome_fonte = familia.split(",")[0].strip().strip("'\"")
            if nome_fonte and len(nome_fonte) <= 60:
                novo["fonte"] = nome_fonte
        tam = _estilo(tag, "font-size")
        if tam and _tamanho_pt(tam):
            novo["tamanho"] = _tamanho_pt(tam)
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
            elif eh_equacao(child):
                add_equacao(paragraph, child, bloco=False)
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
            formatar_paragrafo(p, li, "left")
            process_children(li, p)
            for sub in li.find_all(["ul", "ol"], recursive=False):
                render_lista(sub, nivel + 1)
            # sublistas dentro de <p> do item (HTML de outras origens)
            for bloco in li.find_all(_BLOCOS_INTERNOS, recursive=False):
                for sub in bloco.find_all(["ul", "ol"], recursive=False):
                    render_lista(sub, nivel + 1)

    def render_tabela(tag):
        """Tabela com bordas; células mescladas (colspan/rowspan) viram células mescladas no Word."""
        linhas = tag.find_all("tr")
        if not linhas:
            return
        ocupadas = set()
        posicoes = []  # (linha, coluna, colspan, rowspan, célula)
        ncols = 0
        for i, tr in enumerate(linhas):
            j = 0
            for cel in tr.find_all(["td", "th"], recursive=False):
                while (i, j) in ocupadas:
                    j += 1
                try:
                    cs = max(1, min(int(cel.get("colspan") or 1), 50))
                    rs = max(1, min(int(cel.get("rowspan") or 1), 200))
                except ValueError:
                    cs = rs = 1
                rs = min(rs, len(linhas) - i)
                posicoes.append((i, j, cs, rs, cel))
                for di in range(rs):
                    for dj in range(cs):
                        ocupadas.add((i + di, j + dj))
                j += cs
                ncols = max(ncols, j)
        if not ncols:
            return
        table = doc.add_table(rows=len(linhas), cols=ncols)
        try:
            table.style = "Table Grid"  # bordas visíveis na prova
        except (KeyError, ValueError):
            pass
        for i, j, cs, rs, cel in posicoes:
            alvo = table.cell(i, j)
            if cs > 1 or rs > 1:
                alvo = alvo.merge(table.cell(i + rs - 1, j + cs - 1))
            cell_par = alvo.paragraphs[0]
            set_alignment(cell_par, parse_style(cel.get("style", "")) or "left")
            process_children(cel, cell_par, formato_de(cel, {}))

    # Blocos principais
    for tag in soup.children:
        if isinstance(tag, Comment):
            continue
        if eh_equacao(tag):
            p = doc.add_paragraph()
            set_alignment(p, "center" if tag.get("data-type") == "block-math" else None)
            add_equacao(p, tag, bloco=tag.get("data-type") == "block-math")
        elif tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            p = doc.add_paragraph()
            formatar_paragrafo(p, tag, "center")
            process_children(tag, p, {"b": True, "tamanho": 18 - (int(tag.name[1]) - 1) * 2})
        elif tag.name in ["p", "div"]:
            p = doc.add_paragraph()
            formatar_paragrafo(p, tag)
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
            formatar_paragrafo(p, tag)
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
        elif tag.name in _INLINE_FORMATO:
            # Trecho formatado solto fora de parágrafo
            p = doc.add_paragraph()
            set_alignment(p, None)
            process_children(tag, p, formato_de(tag, {}))
        else:
            p = doc.add_paragraph()
            set_alignment(p, None)
            process_children(tag, p)
