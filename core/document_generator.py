"""
Módulo para geração de documentos (provas, gabaritos, pacotes).
"""
import logging
import os
import shutil
import tempfile
import subprocess
import csv
import random
import zipfile
import typing
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple, Callable, Type # Garanta Type e Callable
import traceback # Mantido do seu arquivo
import tempfile  # Mantido do seu arquivo
import sys
import io
from pypdf import PdfWriter, PdfReader
from pypdf.generic import NameObject, BooleanObject
import re
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL, WD_ROW_HEIGHT
from docx.oxml import OxmlElement
import json
import unicodedata
from core.utils import parse_enunciado_formatado
from backend.app.utils_crypto import decrypt_text
from backend.app.html_to_docx import html_to_docx
from cryptography.fernet import InvalidToken

logger_dg = logging.getLogger(f"core.{__name__}")

# --- Flags de Disponibilidade ---
PYTHON_DOCX_AVAILABLE = False
PDF_MERGE_AVAILABLE = False
PDF_FORM_FILLING_AVAILABLE = False
REPORTLAB_AVAILABLE = False


# Tentativa de importação das bibliotecas opcionais
try:
    from docx import Document; from docx.shared import Pt, Inches, Cm as DocxCmImported, RGBColor # type: ignore
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER # type: ignore
    from docx.enum.section import WD_SECTION_START # type: ignore
    from docx.oxml.ns import qn; from docx.oxml import OxmlElement # type: ignore
    from docx.text.paragraph import Paragraph as DocxParagraphTypeInternal # type: ignore
    PYTHON_DOCX_AVAILABLE = True; DocxCm = DocxCmImported # type: ignore
    logger_dg.debug("DG: python-docx REAL carregado.")
except ImportError:
    logger_dg.warning("AVISO DG: python-docx não encontrado. Usando stubs.")
    from .stubs import ( DocumentStub_Docx as Document, PtStub_Docx as Pt, InchesStub_Docx as Inches, DocxCmStub_Docx as DocxCm, RGBColorStub_Docx as RGBColor, # type: ignore
                         WD_ALIGN_PARAGRAPH_STUB_Docx as WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT_STUB_Docx as WD_TAB_ALIGNMENT, # type: ignore
                         WD_TAB_LEADER_STUB_Docx as WD_TAB_LEADER, WD_SECTION_START_STUB_Docx as WD_SECTION_START, # type: ignore
                         qn_stub_Docx as qn, OxmlElementStub_Docx as OxmlElement, DocxParagraphTypeInternalStub_Docx as DocxParagraphTypeInternal) # type: ignore


try:
    PDF_MERGE_AVAILABLE = True; 
    PDF_FORM_FILLING_AVAILABLE = True
    logger_dg.debug("DG: PyPDF2 REAL carregado.")
except ImportError:
    logger_dg.warning("AVISO DG: PyPDF2 não encontrado. Usando stubs.");
    from .stubs import ( PdfWriterStubPyPDF2 as PdfWriter, PdfReaderStubPyPDF2 as PdfReader, # type: ignore
                         NameObjectStubPyPDF2 as NameObject, BooleanObjectStubPyPDF2 as BooleanObject, # type: ignore
                         DictionaryObjectStubPyPDF2 as DictionaryObject, TextStringObjectStubPyPDF2 as TextStringObject, # type: ignore
                         NumberObjectStubPyPDF2 as NumberObject, ArrayObjectStubPyPDF2 as ArrayObject ) # type: ignore
# ... (Blocos try-except similares para reportlab e python-docx, importando de .stubs no except)

try:
    from reportlab.lib.pagesizes import A4; from reportlab.lib.units import cm # type: ignore
    from reportlab.pdfgen import canvas as rl_canvas_module; from reportlab.lib.colors import Color as RlColor # type: ignore
    from reportlab.platypus import Paragraph; from reportlab.lib.styles import getSampleStyleSheet # type: ignore
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT # type: ignore
    REPORTLAB_AVAILABLE = True; logger_dg.debug("DG: ReportLab REAL carregado.")
except ImportError:
    logger_dg.warning("AVISO DG: ReportLab não encontrado. Usando stubs.")
    from .stubs import ( rl_canvas_module_stub_RL as rl_canvas_module, A4Stub_RL as A4, CmStub_RL as cm, # type: ignore
                         RlColorStub_RL as RlColor, ParagraphRLStub_RL as Paragraph, # type: ignore
                         getSampleStyleSheetRLStub_RL as getSampleStyleSheet, # type: ignore
                         TA_CENTER_STUB_RL as TA_CENTER, TA_JUSTIFY_STUB_RL as TA_JUSTIFY, # type: ignore
                         TA_LEFT_STUB_RL as TA_LEFT, TA_RIGHT_STUB_RL as TA_RIGHT ) # type: ignore

try:
    from .utils import resource_path, sanitize_filename
except ImportError as e_util_dg_core_local: # Nome da exceção mais específico
    logger_dg.critical(f"Falha crítica ao importar de .utils em document_generator: {e_util_dg_core_local}.", exc_info=True)
    def resource_path(p: str) -> str: return p # type: ignore
    def sanitize_filename(f: str) -> str: return str(f) # type: ignore

# --- Flags de Disponibilidade ---
# Estas flags são re-declaradas aqui no arquivo original. Isso é redundante,
# pois já foram definidas acima. Pode ser uma fonte de confusão, mas não um erro de sintaxe.
# PYTHON_DOCX_AVAILABLE = False
# PDF_MERGE_AVAILABLE = False
# PDF_FORM_FILLING_AVAILABLE = False
# REPORTLAB_AVAILABLE = False

# --- Importar dependências com fallback para stubs ---

try:
    from .elements import (
        EventoType, ProvaMontadaType, QuestaoType, CargoType, TipoProva, DisciplinaProvaType,
        OpcaoMultiplaEscolha, TextoReferenciaType, DisciplinaType
    )
    from .event_manager import EventManager as EventManagerTypeInternal
    
    # --- BLOCO DE IMPORTAÇÃO CORRIGIDO E UNIFICADO ---
    # Importa todas as constantes necessárias diretamente do arquivo, sem usar 'K'
    from .frase_manager import FraseManager
    from .constants import (
        PDF_FIELD_NOME_CANDIDATO, PDF_FIELD_INSCRICAO, PDF_FIELD_CARGO_TIPO, PDF_FIELD_FRASE,
        COLUNA_ID_CANDIDATO_CSV, COLUNA_NOME_COMPLETO_CSV, COLUNA_TIPO_PROVA_CSV,
        CSV_DELIMITER, GABARITO_QUESTAO_NUM, GABARITO_DISCIPLINA, GABARITO_CONTEUDO,
        GABARITO_RESPOSTA_CORRETA, GABARITO_TEXTO_RESPOSTA_CORRETA, 
        GABARITO_TIPO_QUESTAO, GABARITO_PONTUACAO
    )
    # --- FIM DA CORREÇÃO ---

    logger_dg.debug("DG: Tipos de .elements, .event_manager e .constants REAIS carregados.")
except ImportError as e_dg_core_types_local:
    logger_dg.error(f"ERRO DG: Falha ao importar tipos internos: {e_dg_core_types_local}. Usando Stubs de core.stubs.", exc_info=True)
    from .stubs import (
        EventoTypeStub as EventoType, ProvaMontadaTypeStub as ProvaMontadaType, # type: ignore
        QuestaoTypeStub as QuestaoType, CargoTypeStub as CargoType, # type: ignore
        TipoProvaStub as TipoProva, DisciplinaProvaTypeStub as DisciplinaProvaType, # type: ignore
        OpcaoMultiplaEscolhaStub as OpcaoMultiplaEscolha, TextoReferenciaTypeStub as TextoReferenciaType, # type: ignore
        DisciplinaTypeStub as DisciplinaType, EventManagerStub as EventManagerTypeInternal # type: ignore
    )
    # Stubs para constantes
    PDF_FIELD_NOME_CANDIDATO = "STUB_Nome" # type: ignore
    PDF_FIELD_INSCRICAO = "STUB_Inscricao" # type: ignore
    PDF_FIELD_CARGO_TIPO = "STUB_Cargo_Tipo" # type: ignore
    PDF_FIELD_FRASE = "STUB_Frase" # type: ignore
    COLUNA_ID_CANDIDATO_CSV = "STUB_ID_Candidato_CSV" # type: ignore
    COLUNA_NOME_COMPLETO_CSV = "STUB_Nome_Completo_CSV" # type: ignore
    COLUNA_TIPO_PROVA_CSV = "STUB_Tipo_Prova_CSV" # type: ignore
    # ... (defina stubs para TODAS as outras constantes importadas)
    # from .stubs import KStub as K # Se K for usado

def remover_tags_metadados(texto):
        # Remove tudo entre colchetes [TEXTO: ...] ou [NIVEL: ...] ou [PONTOS: ...] ou [TAGS: ...] etc.
        return re.sub(r'\[.*?\]', '', texto).strip()

def filtrar_tags_lista_formatada(lista):
    nova_lista = []
    for item in lista:
        # Remove itens 'text' que são só tags/metadados, exemplo: ["text", "[NIVEL: Médio]", ...]
        if item[0] == 'text' and re.match(r'^\[[^]]+\]$', str(item[1]).strip()):
            continue
        nova_lista.append(item)
    return nova_lista

def filtrar_tags_lista_formatada_robusto(lista):
    """
    Remove todos os trechos entre [ e ] mesmo se fragmentados.
    Junta o texto dos itens, remove os metadados, depois reconstrói a lista formatada.
    """
    # Juntar todos os textos dos itens 'text', marcando posição
    textos = []
    outros = []
    for idx, item in enumerate(lista):
        if item[0] == 'text':
            textos.append((idx, item[1]))
        else:
            outros.append((idx, item))
    # Juntar todos os textos em uma única string para processar os metadados
    texto_total = "".join([t[1] for t in textos])
    # Remover todos os metadados entre colchetes
    texto_limpo = re.sub(r'\[[^\[\]]*\]', '', texto_total)
    # Reconstruir lista de 'text', preservando os índices para manter a ordem dos outros itens
    novos_textos = []
    texto_atual = texto_limpo
    for idx, orig_text in textos:
        if not texto_atual:
            novos_textos.append((idx, ""))  # vazio no resto
        else:
            # Pega tantos caracteres quanto o texto original
            parte = texto_atual[:len(orig_text)]
            novos_textos.append((idx, parte))
            texto_atual = texto_atual[len(orig_text):]
    # Remontar a lista formatada original, mas agora com os textos limpos
    nova_lista = []
    texto_indices = {idx: txt for idx, txt in novos_textos}
    for i in range(len(lista)):
        if lista[i][0] == 'text':
            t = texto_indices.get(i, "")
            # Só adiciona se restou texto visível
            if t.strip() != "":
                nova_lista.append(['text', t])
        else:
            nova_lista.append(lista[i])
    return nova_lista

from docx.enum.text import WD_ALIGN_PARAGRAPH

def export_to_docx_from_editor_dump(doc, dump):
    """
    doc: python-docx Document
    dump: resultado de text.dump("1.0", END, text=True, tag=True, ...)
    """
    current_tags = set()
    current_line = ""
    for item in dump:
        if item[0] == "text":
            current_line += item[1]
        elif item[0] == "tag":
            if item[1] == "sel":
                continue
            if item[2] == "start":
                current_tags.add(item[1])
            elif item[2] == "end":
                current_tags.discard(item[1])
        elif item[0] == "mark" and item[1] == "insert" and "\n" in current_line:
            # Fim de linha
            line = current_line.rstrip("\n")
            p = doc.add_paragraph(line)
            # Detecta marcador ou número
            if line.lstrip().startswith("• "):
                p.style = "List Bullet"
            elif line.lstrip()[:2].isdigit() and line.lstrip()[2:4] == ". ":
                p.style = "List Number"
            # Alinhamento
            if "center_align" in current_tags:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif "right_align" in current_tags:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            current_line = ""
    # Última linha
    if current_line.strip():
        p = doc.add_paragraph(current_line)
        # Mesma lógica de cima para estilo e alinhamento...

def unir_itens_texto_formatado(lista):
    """
    Une apenas runs consecutivos de texto, garantindo que haja espaço entre palavras,
    mas mantendo tags de formatação no lugar.
    """
    result = []
    last_text = None
    for item in lista:
        if item[0] == "text":
            if last_text is not None:
                # Garantir espaço entre textos, sem duplicar
                if not last_text.endswith(" ") and not str(item[1]).startswith(" "):
                    last_text += " " + str(item[1])
                else:
                    last_text += str(item[1])
            else:
                last_text = str(item[1])
        else:
            if last_text is not None:
                result.append(["text", last_text])
                last_text = None
            result.append(item)
    if last_text is not None:
        result.append(["text", last_text])
    return result

def resolve_logo_path(logo_path_from_db):
    if not logo_path_from_db:
        return None
    # Troca / e \ para o separador correto do sistema operacional
    path = logo_path_from_db.replace("/", os.sep).replace("\\", os.sep)
    path = path.lstrip(os.sep)  # Remove barra inicial, se houver
    abs_path = os.path.abspath(path)
    if os.path.exists(abs_path):
        return abs_path
    return None

def safe_decrypt(val):
    if not val:
        return ""
    try:
        return decrypt_text(val)
    except InvalidToken:
        print(f"[ATENÇÃO] Valor não criptografado ou corrompido ao descriptografar: {repr(val)}")
        return val
    except Exception as e:
        print(f"[ATENÇÃO] Outro erro ao descriptografar: {e}")
        return val

class DocxProofGenerator:
    """
    Gera o corpo principal da prova em formato DOCX e os dados do gabarito.
    """
    def __init__(self,
                 prova_montada_obj: ProvaMontadaType,
                 evento_obj: EventoType,
                 cargo_obj: CargoType, # Adicionado cargo_obj explicitamente
                 format_options: dict,
                 image_storage_base_dir: str, # Diretório base para salvar imagens das questões
                 template_prova_path: Optional[str] = None,
                 logger: Optional[logging.Logger] = None,
                 core_elements_module: Optional[Any] = None,
                 app_instance: Optional[Any] = None, # Para logging na UI
                 K_consts: Optional[Any] = None,
                 logo_path_override: Optional[str] = None,
                 **kwargs: Any): 
        # super().__init__(**kwargs) if hasattr(super(), '__init__') else None # Chamada super segura

        self.logger = logger if logger else logger_dg.getChild(self.__class__.__name__)
        self.prova_montada = prova_montada_obj
        self.evento = evento_obj
        self.cargo = cargo_obj # Armazena o cargo
        self.format_options = format_options
        self.template_prova_path = template_prova_path
        self.core_elements = core_elements_module if core_elements_module else sys.modules.get('core.elements')
        self.app_instance = app_instance # Para log na UI
        self.K = K_consts
        self.logo_path_override = logo_path_override
        
        self.image_storage_base_dir = image_storage_base_dir

        self.QuestaoTypeModel: Type[QuestaoType] = getattr(self.core_elements, 'QuestaoType', QuestaoType) # type: ignore
        self.OpcaoModel: Type[OpcaoMultiplaEscolha] = getattr(self.core_elements, 'OpcaoMultiplaEscolha', OpcaoMultiplaEscolha) # type: ignore

        # Referência global para a flag de disponibilidade, usada nos métodos internos.
        # Isso evita ter que passar PYTHON_DOCX_AVAILABLE para cada método.
        global PYTHON_DOCX_AVAILABLE_DG_FLAG 
        PYTHON_DOCX_AVAILABLE_DG_FLAG = PYTHON_DOCX_AVAILABLE

        if not PYTHON_DOCX_AVAILABLE_DG_FLAG:
            self.logger.warning("DocxProofGenerator: python-docx não disponível.")
        self.logger.info(f"DocxProofGenerator instanciado para prova: {getattr(prova_montada_obj, 'nome_prova_montada', 'N/A')}")

    def _log_ui(self, message: str, level: str = "info"):
        if self.app_instance and hasattr(self.app_instance, 'log_message'):
            self.app_instance.log_message(message, level)
        else:
            log_func = getattr(self.logger, level, self.logger.info)
            log_func(message)
    
    def _get_field(self, obj, field, default=""):
        if isinstance(obj, dict):
            return obj.get(field, default)
        return getattr(obj, field, default)
    
    def renderizar_conteudo_formatado(self, document, conteudo_formatado, fonte="Arial", tamanho=Pt(12)):
        """
        Renderiza o conteúdo formatado (lista de comandos) como parágrafos no DOCX.
        Quebras de parágrafo são reconhecidas por "\n" ou "\n\n".
        """
        if not conteudo_formatado:
            return []

        par_format = {}
        par_style = None
        cor_atual = None
        alinhamento_atual = None
        bold = False
        italic = False
        underline = False

        paragrafos_criados = []
        p = document.add_paragraph()
        paragrafos_criados.append(p)

        for bloco in conteudo_formatado:
            tipo = bloco[0]
            valor = bloco[1] if len(bloco) > 1 else None

            if tipo == "text":
                if valor in ["\n", "\n\n"]:
                    p = document.add_paragraph()
                    paragrafos_criados.append(p)
                    continue
                run = p.add_run(valor or "")
                run.font.name = fonte
                run.font.size = tamanho
                run.bold = bold
                run.italic = italic
                run.underline = underline
                if cor_atual:
                    run.font.color.rgb = RGBColor.from_string(cor_atual)

            elif tipo == "tagon":
                if valor == "bold":
                    bold = True
                elif valor == "italic":
                    italic = True
                elif valor == "underline":
                    underline = True
                elif valor == "color":
                    cor_atual = bloco[2]
                elif valor == "align":
                    alinhamento_atual = bloco[2]  # ex: "center", "right", "left"
                    if alignment_map := {
                        "center": WD_ALIGN_PARAGRAPH.CENTER,
                        "right": WD_ALIGN_PARAGRAPH.RIGHT,
                        "left": WD_ALIGN_PARAGRAPH.LEFT,
                        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY
                    }:
                        p.alignment = alignment_map.get(alinhamento_atual.lower(), WD_ALIGN_PARAGRAPH.LEFT)

            elif tipo == "tagoff":
                if valor == "bold":
                    bold = False
                elif valor == "italic":
                    italic = False
                elif valor == "underline":
                    underline = False
                elif valor == "color":
                    cor_atual = None
                elif valor == "align":
                    alinhamento_atual = None

        return paragrafos_criados

    def _add_text_with_images(self, document, texto, questao: "QuestaoType", largura_cm=8.0) -> List[DocxParagraphTypeInternal]:
        """
        Adiciona texto do enunciado e imagens. Aplica recuo de 1cm SOMENTE
        se a questão for do tipo Discursiva.
        """
        padrao = r"!\[.*?\]\((.*?)\)"
        partes = re.split(padrao, texto)
        paragrafos_criados = []

        for idx, parte in enumerate(partes):
            if idx % 2 == 1:
                # Lógica da imagem (inalterada)
                caminho_imagem = os.path.join(self.image_storage_base_dir, parte)
                if os.path.exists(caminho_imagem):
                    p_img = document.add_paragraph()
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    self._add_image_to_paragraph(p_img, caminho_imagem, doc=document)
                    paragrafos_criados.append(p_img)
            else:
                # Lógica do texto
                linhas_do_texto = parte.split('\n')
                
                for linha in linhas_do_texto:
                    if linha.strip(): 
                        p_texto = document.add_paragraph(linha.strip())
                        
                        # --- INÍCIO DA CORREÇÃO ---
                        # Aplica o recuo de 1cm SOMENTE se a questão for discursiva.
                        if getattr(questao, 'tipo', '').strip().lower() == 'discursiva':
                            p_texto.paragraph_format.first_line_indent = Cm(1.0)
                        # --- FIM DA CORREÇÃO ---
                        
                        paragrafos_criados.append(p_texto)
                
        return paragrafos_criados
    

    
    def _add_paragraph_formatting(self,
                              paragraph, # No type hint for Paragraph due to conditional import
                              alignment: Optional[Any] = None, # WD_ALIGN_PARAGRAPH
                              font_name: str = 'Calibri',
                              font_size: Optional[Any] = None, # Pt
                              bold: bool = False,
                              italic: bool = False,
                              underline: bool = False,
                              font_color_rgb: Optional[Any] = None, # RGBColor
                              line_spacing_rule: Optional[Any] = None, # WD_LINE_SPACING
                              line_spacing: Optional[float] = None,
                              space_before_pt: Optional[float] = None,
                              space_after_pt: Optional[float] = None,
                              keep_with_next: bool = False,
                              keep_lines_together: bool = False,
                              indent_left_inches: Optional[float] = None,
                              first_line_indent_cm: Optional[float] = None,  # <-- NOVO!
                              shading_fill: Optional[str] = None): # NOVO PARÂMETRO
        """Aplica formatação a um parágrafo e seus runs, incluindo sombreamento e recuo de primeira linha."""
        if not PYTHON_DOCX_AVAILABLE_DG_FLAG:
            return

        if alignment is not None:
            paragraph.alignment = alignment

        p_format = paragraph.paragraph_format
        if line_spacing is not None:
            p_format.line_spacing = line_spacing
        if space_before_pt is not None:
            p_format.space_before = Pt(space_before_pt)
        if space_after_pt is not None:
            p_format.space_after = Pt(space_after_pt)
        if indent_left_inches is not None:
            p_format.left_indent = Inches(indent_left_inches)
        if first_line_indent_cm is not None:
            from docx.shared import Cm
            p_format.first_line_indent = Cm(first_line_indent_cm)

        p_format.keep_with_next = keep_with_next
        p_format.keep_together = keep_lines_together
        
        # --- LÓGICA DE SOMBREAMENTO (NOVO) ---
        if shading_fill:
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            pPr = paragraph._p.get_or_add_pPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), shading_fill) # Ex: "D9D9D9" para cinza claro
            pPr.append(shd)
        # --- FIM DA LÓGICA DE SOMBREAMENTO ---

        for run in paragraph.runs:
            run.font.name = font_name
            if font_size is not None:
                run.font.size = font_size
            run.font.bold = bold
            run.font.italic = italic
            run.font.underline = underline
            if font_color_rgb is not None:
                run.font.color.rgb = font_color_rgb
    
    
    @staticmethod
    def inserir_texto_formatado_docx(document_or_paragraph,
                                     lista_formatada,
                                     correta=False,
                                     first_line_indent_cm: Optional[float] = None,
                                     mostrar_gabarito: bool = False,
                                     base_font_size_pt: int = 12):
        """
        Ponto de entrada principal. Utiliza o _FormattedTextParser para renderizar
        o conteúdo formatado de forma otimizada e robusta.
        """
        # A função principal agora simplesmente delega o trabalho para o parser.
        parser = DocxProofGenerator._FormattedTextParser(
            document_or_paragraph,
            first_line_indent_cm,
            correta,
            mostrar_gabarito,
            base_font_size_pt
        )
        parser.render(lista_formatada)


    class _FormattedTextParser:
        """
        Classe interna e auxiliar para processar e renderizar a lista de texto formatado.
        Encapsula a lógica e o estado para uma renderização limpa e otimizada.
        """
        def __init__(self, doc_or_para, indent_cm, is_correct_answer, mostrar_gabarito, base_font_size_pt): # <-- RECEBE A INFORMAÇÃO
            from docx.shared import Cm, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.shared import Pt

            self.Pt = Pt
            self.Cm = Cm
            self.RGBColor = RGBColor
            self.WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH
            
            self.is_doc = hasattr(doc_or_para, "add_paragraph")
            self.doc = doc_or_para if self.is_doc else doc_or_para.part.document
            
            # A variável 'p' começa como None, como definimos.
            self.p = None if self.is_doc else doc_or_para
            
            self.indent_cm = indent_cm
            self.is_correct_answer = is_correct_answer
            self.mostrar_gabarito = mostrar_gabarito 
            
            self.buffer = ""
            self.format_state = {
                'bold': False, 'italic': False, 'underline': False, 'color': None
            }
            self.alignment = self.WD_ALIGN_PARAGRAPH.JUSTIFY
            self.base_font_size_pt = base_font_size_pt
            self.is_formatting_caption = False

        def _flush_buffer(self):
            """
            Cria um 'run' com o texto acumulado. Agora também cria o primeiro
            parágrafo sob demanda.
            """
            if self.buffer:
                # --- CORREÇÃO AQUI ---
                # Se nenhum parágrafo foi criado ainda, cria o primeiro agora.
                if self.p is None and self.is_doc:
                    self.p = self.doc.add_paragraph()
                    self.p.alignment = self.alignment
                    if self.indent_cm is not None:
                        self.p.paragraph_format.first_line_indent = self.Cm(self.indent_cm)
                
                # --- LÓGICA DA LEGENDA APRIMORADA ---
                
                # 1. ATIVA A MEMÓRIA: Se ainda não estamos no modo legenda e o
                #    texto atual começa com "legenda", ativamos a flag.
                if not self.is_formatting_caption and self.buffer.strip().lower().startswith('legenda'):
                    self.is_formatting_caption = True

                # 2. APLICA A FORMATAÇÃO: Se a memória estiver ativa para este parágrafo...
                if self.is_formatting_caption:
                    self.p.alignment = self.WD_ALIGN_PARAGRAPH.RIGHT

                run = self.p.add_run(self.buffer)
                run.bold = self.format_state['bold']
                run.italic = self.format_state['italic']
                run.underline = self.format_state['underline']

                # --- LÓGICA DE TAMANHO DA FONTE PARA LEGENDA ---
                # Aplica o tamanho da fonte se a memória estiver ativa
                if self.is_formatting_caption and self.base_font_size_pt:
                    run.font.size = self.Pt(int(self.base_font_size_pt * 0.8))

                if self.mostrar_gabarito:
                    # Se for a resposta correta, pinta de vermelho
                    if self.is_correct_answer:
                        run.font.color.rgb = self.RGBColor(255, 0, 0)
                    # Se não for a resposta correta, mas tiver cor embutida, aplica a cor
                    elif self.format_state['color']:
                        run.font.color.rgb = self.format_state['color']
                
                self.buffer = ""

        def _create_new_paragraph(self):
            """Finaliza o parágrafo atual (se existir) e cria um novo."""
            if not self.is_doc: return
            
            # A chamada para _flush_buffer() foi movida para o método render
            # para dar mais controle sobre o fluxo.

            self.is_formatting_caption = False # Reseta a flag para o novo parágrafo
            
            self.p = self.doc.add_paragraph()
            self.p.alignment = self.alignment
            if self.indent_cm is not None:
                self.p.paragraph_format.first_line_indent = self.Cm(self.indent_cm)

        def _update_state(self, tag, value, extra):
            """Atualiza o dicionário de estado de formatação com lógica corrigida."""
            self._flush_buffer() # Sempre que a formatação muda, cria o run anterior

            # --- INÍCIO DA CORREÇÃO ---
            # Define explicitamente quais tags são flags booleanas
            boolean_flags = ['bold', 'italic', 'underline']

            if tag == 'tagon':
                # Agora, este 'if' só será verdadeiro para bold, italic, ou underline
                if value in boolean_flags:
                    self.format_state[value] = True
                elif value == 'color':
                    self.format_state['color'] = self.RGBColor.from_string(extra) if extra else None
                elif value == 'align':
                    align_map = {'right': self.WD_ALIGN_PARAGRAPH.RIGHT, 'center': self.WD_ALIGN_PARAGRAPH.CENTER, 'justify': self.WD_ALIGN_PARAGRAPH.JUSTIFY}
                    if extra is not None:
                        self.alignment = align_map.get(extra.lower(), self.WD_ALIGN_PARAGRAPH.LEFT)
                    else:
                        self.alignment = self.WD_ALIGN_PARAGRAPH.LEFT
                    self.p.alignment = self.alignment

            elif tag == 'tagoff':
                # E este também
                if value in boolean_flags:
                    self.format_state[value] = False
                elif value == 'color':
                    self.format_state['color'] = None
                elif value == 'align':
                    self.alignment = self.WD_ALIGN_PARAGRAPH.JUSTIFY
                    self.p.alignment = self.alignment
            # --- FIM DA CORREÇÃO ---

        
        def render(self, lista_formatada):
            """
            Renderiza cada item da lista_formatada exatamente como está,
            respeitando runs de espaço e tags.
            """
            for item in lista_formatada:
                tag = item[0]
                value = item[1] if len(item) > 1 else ''
                extra = item[2] if len(item) > 2 else None

                if tag == 'text':
                    lines = value.split('\n')
                    for i, line in enumerate(lines):
                        if i > 0:
                            self._flush_buffer()
                            self._create_new_paragraph()
                        self.buffer += line
                else:
                    self._update_state(tag, value, extra)
            self._flush_buffer()
            if self.p:
                self.p.alignment = self.alignment

    def _add_formatted_paragraph(self,
                                    document: Document,
                                    text: str = "",
                                    style_name: Optional[str] = None,
                                    html_content: bool = False,
                                    **kwargs) -> list:
        """
        Adiciona UM ÚNICO parágrafo formatado ao documento.
        A separação do texto em múltiplos parágrafos deve ser feita ANTES de chamar esta função.
        """
        if not text.strip():
            return [] # Não adiciona parágrafos para texto vazio ou em branco

        style_to_apply = kwargs.pop('style', style_name)

        # Cria um único parágrafo com o texto fornecido
        p = document.add_paragraph(text=text.strip(), style=style_to_apply)

        # Aplica a formatação e o recuo a esse parágrafo
        self._add_paragraph_formatting(p, **kwargs)

        # Lógica de recuo que já tínhamos
        if 'first_line_indent_cm' in kwargs and kwargs['first_line_indent_cm'] is not None:
            p.paragraph_format.first_line_indent = Cm(kwargs['first_line_indent_cm'])
        
        return [p] # Retorna o parágrafo criado em uma lista
    
    def _adicionar_questao_ao_docx(
        self,
        document,
        questao_obj,
        num_questao_na_prova,
        definicao_geracao: dict,
        id_prova_montada: str,
        variacao_num: int,
        textos_map=None
    ):
        # Adiciona o número da questão em negrito
        p_enunciado = document.add_paragraph()
        p_enunciado.add_run(f"{num_questao_na_prova}. ").bold = True

        # PRINT DE DIAGNÓSTICO DO ENUNCIADO FORMATADO
        print(f"\n== DEBUG enunciado_formatado Q{num_questao_na_prova} ==\n", getattr(questao_obj, "enunciado_formatado", None), "\n")

        # Insere o enunciado formatado, se existir, ou texto puro
        if hasattr(questao_obj, "enunciado_formatado") and questao_obj.enunciado_formatado:
            lista_formatada = [
                [item[0], item[1].rstrip('\n')] if item[0] == 'text' else item
                for item in questao_obj.enunciado_formatado
                if item and item[0] in ("text", "tagon", "tagoff")
            ]
            self.inserir_texto_formatado_docx(p_enunciado, lista_formatada)
        else:
            p_enunciado.add_run(getattr(questao_obj, 'enunciado', ''))

        metadados = getattr(questao_obj, 'metadados_questao', {})
        # ... outros campos ...

        # Alternativas de múltipla escolha
        if getattr(questao_obj, 'tipo', '') == 'Múltipla Escolha':
            opcoes = list(getattr(questao_obj, 'opcoes', []))
            for i, opcao in enumerate(opcoes):
                letra_opcao = chr(ord('A') + i)
                texto_da_opcao = getattr(opcao, 'texto_opcao', '<<Opção Vazia>>')

                p_opcao = document.add_paragraph(style='List Paragraph')
                run_letra = p_opcao.add_run(f"{letra_opcao})\t")
                run_letra.bold = True

                # PRINT DE DIAGNÓSTICO DA ALTERNATIVA FORMATADA
                print(f"\n== DEBUG texto_opcao_formatado {letra_opcao} Q{num_questao_na_prova} ==\n", getattr(opcao, "texto_opcao_formatado", None), "\n")

                # Insere alternativa formatada, se existir, ou texto puro
                if hasattr(opcao, "texto_opcao_formatado") and opcao.texto_opcao_formatado:
                    self.inserir_texto_formatado_docx(p_opcao, opcao.texto_opcao_formatado)
                else:
                    p_opcao.add_run(texto_da_opcao)

                if hasattr(p_opcao.paragraph_format, 'left_indent'):
                    from docx.shared import Inches
                    p_opcao.paragraph_format.left_indent = Inches(0.25)
        document.add_paragraph()

        # PRINT DE DIAGNÓSTICO DA REFERÊNCIA FORMATADA
        print(f"\n== DEBUG conteudo_formatado Q{num_questao_na_prova} ==\n", getattr(questao_obj, "conteudo_formatado", None), "\n")

        codigo_ref = None
        if hasattr(questao_obj, "id_texto_ref_vinculado"):
            codigo_ref = getattr(questao_obj, "id_texto_ref_vinculado")
        elif isinstance(getattr(questao_obj, "metadados_questao", None), dict):
            codigo_ref = questao_obj.metadados_questao.get("codigo_ref_vinculado_gerado")

        texto_ref = textos_map.get(codigo_ref) if codigo_ref else None

        # 2. Insira o texto de referência formatado, se houver
        if texto_ref and getattr(texto_ref, "conteudo_formatado", None):
            p_ref = document.add_paragraph()
            self.inserir_texto_formatado_docx(p_ref, texto_ref.conteudo_formatado)
        elif texto_ref and getattr(texto_ref, "conteudo", None):
            p_ref = document.add_paragraph()
            p_ref.add_run(getattr(texto_ref, "conteudo", ""))

    
    
    from docx.shared import Inches, Pt
    

    def _add_header_footer(self, document):
        """
        Adiciona cabeçalho e rodapé ao documento DOCX,
        com logo dinâmico (do banco), tipo de prova e info do cargo/evento.
        Funciona para objetos OU dicionários!
        """
        if not PYTHON_DOCX_AVAILABLE_DG_FLAG:
            return

        section = document.sections[0]

        # --- LOGO ---
        print("LOGO_PATH (input):", self.logo_path_override)
        logo_path = self.logo_path_override
        if logo_path:
            logo_path = logo_path.lstrip("/\\")
            if not os.path.isabs(logo_path):
                logo_path = os.path.abspath(logo_path)
        print("LOGO_PATH (final):", logo_path)
        print("LOGO_PATH EXISTS:", os.path.exists(logo_path) if logo_path else False)

        # ----- CABEÇALHO -----
        header = section.header

        nome_evento = self._get_field(self.evento, "nome_evento", "NOME DO EVENTO")

        if header.tables:
            table = header.tables[0]
            cell_nome = table.cell(0, 0)
            for p in cell_nome.paragraphs:
                p.clear()
            cell_nome.paragraphs[0].add_run(nome_evento)
            self._add_paragraph_formatting(cell_nome.paragraphs[0], alignment=WD_ALIGN_PARAGRAPH.LEFT, font_size=Pt(11), bold=True)

            cell_logo = table.cell(0, 1)
            for p in cell_logo.paragraphs:
                p.clear()
            if logo_path and os.path.exists(logo_path):
                run = cell_logo.paragraphs[0].add_run()
                run.add_picture(logo_path, height=Cm(1.5))
                self._add_paragraph_formatting(cell_logo.paragraphs[0], alignment=WD_ALIGN_PARAGRAPH.RIGHT)
            else:
                cell_logo.text = ""
        else:
            for para in header.paragraphs:
                para.clear()
            table = header.add_table(rows=1, cols=2, width=Inches(6.5))
            table.allow_autofit = True
            table.columns[0].width = Pt(350)
            table.columns[1].width = Pt(130)

            p_evento = table.cell(0, 0).paragraphs[0]
            p_evento.text = nome_evento
            self._add_paragraph_formatting(p_evento, alignment=WD_ALIGN_PARAGRAPH.LEFT, font_size=Pt(11), bold=True)

            cell_dir = table.cell(0, 1)
            for p in cell_dir.paragraphs:
                p.clear()
            if logo_path and os.path.exists(logo_path):
                run = cell_dir.paragraphs[0].add_run()
                run.add_picture(logo_path, height=Cm(1.5))
                self._add_paragraph_formatting(cell_dir.paragraphs[0], alignment=WD_ALIGN_PARAGRAPH.RIGHT)
            else:
                cell_dir.text = ""

            tbl = table._tbl
            for border in tbl.xpath(".//w:tblBorders"):
                border.getparent().remove(border)

        # ----- RODAPÉ -----
        footer = section.footer

        tipo_prova = self._get_field(self.prova_montada, "identificador_prova", "").strip()
        if not tipo_prova:
            tipo_prova = "PADRÃO"  # ou "Tipo A", "Tipo B", etc, se quiser personalizar

        codigo_cargo = self._get_field(self.cargo, "codigo_cargo", "")
        nome_cargo = self._get_field(self.cargo, "nome_cargo", "")

        # Evita duplicidade: só mostra o código se não está incluso no nome
        if codigo_cargo and codigo_cargo in nome_cargo:
            texto_rodape = f"{nome_cargo} - {tipo_prova}"
        else:
            texto_rodape = f"{codigo_cargo} - {nome_cargo} - {tipo_prova}"


        if footer.tables:
            tablef = footer.tables[0]
            cellf_esq = tablef.cell(0, 0)
            for p in cellf_esq.paragraphs:
                p.clear()
            pf_esq = cellf_esq.paragraphs[0]
            pf_esq.text = texto_rodape
            self._add_paragraph_formatting(pf_esq, alignment=WD_ALIGN_PARAGRAPH.LEFT, font_size=Pt(9))

            # Página X de Y (direita)
            cellf_dir = tablef.cell(0, 1)
            for p in cellf_dir.paragraphs:
                p.clear()
            pf_dir = cellf_dir.paragraphs[0]
            pf_dir.text = "Página "
            run = pf_dir.add_run()
            fldChar = OxmlElement('w:fldChar')
            fldChar.set(qn('w:fldCharType'), 'begin')
            run._r.append(fldChar)

            instrText = OxmlElement('w:instrText')
            instrText.set(qn('xml:space'), 'preserve')
            instrText.text = 'PAGE'
            run._r.append(instrText)

            fldChar_sep = OxmlElement('w:fldChar')
            fldChar_sep.set(qn('w:fldCharType'), 'separate')
            run._r.append(fldChar_sep)
            fldChar_end = OxmlElement('w:fldChar')
            fldChar_end.set(qn('w:fldCharType'), 'end')
            run._r.append(fldChar_end)

            pf_dir.add_run(" de ")

            run_total = pf_dir.add_run()
            fldChar_total_begin = OxmlElement('w:fldChar')
            fldChar_total_begin.set(qn('w:fldCharType'), 'begin')
            run_total._r.append(fldChar_total_begin)

            instrText_total = OxmlElement('w:instrText')
            instrText_total.set(qn('xml:space'), 'preserve')
            instrText_total.text = 'NUMPAGES'
            run_total._r.append(instrText_total)

            fldChar_total_sep = OxmlElement('w:fldChar')
            fldChar_total_sep.set(qn('w:fldCharType'), 'separate')
            run_total._r.append(fldChar_total_sep)
            fldChar_total_end = OxmlElement('w:fldChar')
            fldChar_total_end.set(qn('w:fldCharType'), 'end')
            run_total._r.append(fldChar_total_end)

            self._add_paragraph_formatting(pf_dir, alignment=WD_ALIGN_PARAGRAPH.RIGHT, font_size=Pt(9))
        else:
            for para in footer.paragraphs:
                para.clear()
            tablef = footer.add_table(rows=1, cols=2, width=Inches(6.5))
            tablef.allow_autofit = True
            tablef.columns[0].width = Pt(350)
            tablef.columns[1].width = Pt(130)

            cellf_esq = tablef.cell(0, 0)
            pf_esq = cellf_esq.paragraphs[0]
            pf_esq.text = texto_rodape
            self._add_paragraph_formatting(pf_esq, alignment=WD_ALIGN_PARAGRAPH.LEFT, font_size=Pt(9))

            cellf_dir = tablef.cell(0, 1)
            pf_dir = cellf_dir.paragraphs[0]
            pf_dir.text = "Página "
            run = pf_dir.add_run()
            fldChar = OxmlElement('w:fldChar')
            fldChar.set(qn('w:fldCharType'), 'begin')
            run._r.append(fldChar)

            instrText = OxmlElement('w:instrText')
            instrText.set(qn('xml:space'), 'preserve')
            instrText.text = 'PAGE'
            run._r.append(instrText)

            fldChar_sep = OxmlElement('w:fldChar')
            fldChar_sep.set(qn('w:fldCharType'), 'separate')
            run._r.append(fldChar_sep)
            fldChar_end = OxmlElement('w:fldChar')
            fldChar_end.set(qn('w:fldCharType'), 'end')
            run._r.append(fldChar_end)

            pf_dir.add_run(" de ")

            run_total = pf_dir.add_run()
            fldChar_total_begin = OxmlElement('w:fldChar')
            fldChar_total_begin.set(qn('w:fldCharType'), 'begin')
            run_total._r.append(fldChar_total_begin)

            instrText_total = OxmlElement('w:instrText')
            instrText_total.set(qn('xml:space'), 'preserve')
            instrText_total.text = 'NUMPAGES'
            run_total._r.append(instrText_total)

            fldChar_total_sep = OxmlElement('w:fldChar')
            fldChar_total_sep.set(qn('w:fldCharType'), 'separate')
            run_total._r.append(fldChar_total_sep)
            fldChar_total_end = OxmlElement('w:fldChar')
            fldChar_total_end.set(qn('w:fldCharType'), 'end')
            run_total._r.append(fldChar_total_end)

            self._add_paragraph_formatting(pf_dir, alignment=WD_ALIGN_PARAGRAPH.RIGHT, font_size=Pt(9))

            tblf = tablef._tbl
            for border in tblf.xpath(".//w:tblBorders"):
                border.getparent().remove(border)
    
    # Adicione este novo método à classe DocxProofGenerator
    def _add_separator(self, document):
        """Adiciona um parágrafo com uma borda inferior para criar uma linha horizontal."""
        p = document.add_paragraph()
        p_pr = p._p.get_or_add_pPr()
        p_bdr = OxmlElement('w:pBdr')
        p_pr.append(p_bdr)
        bottom_bdr = OxmlElement('w:bottom')
        bottom_bdr.set(qn('w:val'), 'single')
        bottom_bdr.set(qn('w:sz'), '4')
        bottom_bdr.set(qn('w:sp'), '1')
        bottom_bdr.set(qn('w:color'), 'auto')
        p_bdr.append(bottom_bdr)


    
    def _add_image_to_paragraph(self, paragraph, image_path, width_cm=None, doc=None, is_texto_referencia=False):
        """
        Insere uma imagem em um parágrafo, com largura opcional.
        Se is_texto_referencia=True, aplica redimensionamento proporcional adequado ao layout.
        Para imagens de alternativas, aplica limites de largura/altura conforme o layout de colunas.
        """
        import os
        from PIL import Image
        from docx.shared import Cm as DocxCm

        if not image_path:
            return

        # Remove prefixo 'static/' se já estiver no caminho salvo no banco
        norm_path = os.path.normpath(image_path)
        if norm_path.startswith("static" + os.sep):
            norm_path = norm_path[len("static" + os.sep):]
        elif norm_path.startswith("static/"):
            norm_path = norm_path[len("static/"):]
        elif norm_path.startswith("static\\"):
            norm_path = norm_path[len("static\\"):]

        # Tenta static primeiro, depois media_files (compatibilidade legada)
        candidate_paths = [
            os.path.normpath(os.path.join("static", norm_path)),
            os.path.normpath(os.path.join("media_files", norm_path)),
        ]

        for try_path in candidate_paths:
            if os.path.exists(try_path):
                image_path = try_path
                break
        else:
            self.logger.warning(f"Imagem não encontrada em nenhum caminho: {candidate_paths}")
            return

        try:
            if is_texto_referencia:
                with Image.open(image_path) as img:
                    dpi_tuple = img.info.get("dpi", (96, 96))
                    dpi = dpi_tuple[0] if isinstance(dpi_tuple, (tuple, list)) and dpi_tuple else 96
                    width_cm_img = img.width * 2.54 / dpi
                    height_cm_img = img.height * 2.54 / dpi
                    aspect_ratio = img.width / img.height

                    is_two_columns = self.format_options.get("duas_colunas", False)
                    max_width_cm = 9.0 if is_two_columns else 12.0
                    max_height_cm = 6.0 if is_two_columns else 8.0

                    width = min(width_cm_img, max_width_cm)
                    height = width / aspect_ratio

                    if height > max_height_cm:
                        height = max_height_cm
                        width = height * aspect_ratio

                    final_width_cm = width
            else:
                with Image.open(image_path) as img:
                    dpi_tuple = img.info.get("dpi", (96, 96))
                    dpi = dpi_tuple[0] if isinstance(dpi_tuple, (tuple, list)) and dpi_tuple else 96
                    width_cm_img = img.width * 2.54 / dpi
                    height_cm_img = img.height * 2.54 / dpi
                    aspect_ratio = img.width / img.height

                    if width_cm == 6.0:
                        max_width = 6.0
                        max_height = 3.0
                    elif width_cm == 12.0:
                        max_width = 12.0
                        max_height = 6.0
                    else:
                        max_width = width_cm if width_cm else width_cm_img
                        max_height = height_cm_img

                    escala_w = max_width / width_cm_img
                    escala_h = max_height / height_cm_img
                    escala = min(escala_w, escala_h, 1.0)

                    final_width_cm = width_cm_img * escala

            paragraph.add_run().add_picture(image_path, width=DocxCm(final_width_cm))
            self.logger.info(f"Imagem inserida: {image_path} com largura final de {final_width_cm:.2f} cm")

        except Exception as e:
            self.logger.warning(f"Erro ao inserir imagem '{image_path}': {e}")



    
    
    def _add_runs_and_images_to_paragraph(self, paragraph, text_with_imgs, doc=None, largura_cm=8.0, fonte="Calibri", tamanho_fonte=None, color=None, context=None):
        import os
        import re
        from docx.shared import Cm as DocxCm, Pt
        from PIL import Image

        padrao = r"!\[.*?\]\((.*?)\)"
        partes = re.split(padrao, text_with_imgs)

        for idx, parte in enumerate(partes):
            if idx % 2 == 1:
                caminho_imagem = os.path.normpath(
                    parte if os.path.isabs(parte) else os.path.join(self.image_storage_base_dir, parte)
                )
                if os.path.exists(caminho_imagem):
                    try:
                        with Image.open(caminho_imagem) as img:
                            largura_px, altura_px = img.size
                            dpi = img.info.get("dpi", (96,))[0] or 96
                            largura_cm_real = largura_px * 2.54 / dpi
                            altura_cm_real = altura_px * 2.54 / dpi
                            proporcao = largura_cm_real / altura_cm_real if altura_cm_real else 1

                            # DEBUG: Print info
                            print(f"DEBUG IMG: {parte} -> {largura_cm_real:.2f} x {altura_cm_real:.2f} cm")

                            if context == "alternativa":
                                if self.format_options.get("duas_colunas"):
                                    max_largura = 6.0
                                    max_altura = 3.0
                                else:
                                    max_largura = 12.0
                                    max_altura = 6.0
                                escala_largura = max_largura / largura_cm_real
                                escala_altura = max_altura / altura_cm_real
                                escala = min(escala_largura, escala_altura, 1.0)
                                final_width = largura_cm_real * escala
                                # DEBUG: Print info
                                print(f"   ESCALA_L={escala_largura:.2f}, ESCALA_A={escala_altura:.2f}, ESCOLHIDA={escala:.2f}, FINAL_W={final_width:.2f}")
                            else:
                                final_width = largura_cm_real

                        run = paragraph.add_run()
                        run.add_picture(caminho_imagem, width=DocxCm(final_width))

                    except Exception as e:
                        self.logger.warning(f"Erro ao inserir imagem da alternativa: {e}")
            else:
                if re.match(r".*\.(jpg|jpeg|png|gif)$", parte.strip(), re.IGNORECASE):
                    continue
                if parte.strip():
                    run = paragraph.add_run(parte)
                    if fonte:
                        run.font.name = fonte
                    if tamanho_fonte:
                        run.font.size = tamanho_fonte
                    if color:
                        run.font.color.rgb = color



        
    def gerar_gabarito_balanceado(self, n_questoes, seed, alternativas=('A','B','C','D','E'), max_repet=2):
        """
        Gera uma lista de letras corretas balanceada e sem mais de 'max_repet' repetições seguidas.
        """
        n_alt = len(alternativas)
        base = n_questoes // n_alt
        sobra = n_questoes % n_alt
        letras = [alt for alt in alternativas for _ in range(base)] + list(alternativas)[:sobra]

        rng = random.Random(seed)
        max_tentativas = 1000 # Adiciona um limite de tentativas para evitar loops infinitos
        for _ in range(max_tentativas):
            rng.shuffle(letras)
            ok = True
            # A verificação de repetição pode ser ajustada ou simplificada se necessário
            for i in range(len(letras) - max_repet):
                if len(set(letras[i:i+max_repet+1])) == 1:
                    ok = False
                    break
            if ok:
                self.logger.info(f"Gabarito balanceado e sem repetição gerado com sucesso.")
                return letras
                
        self.logger.warning(f"Não foi possível gerar gabarito sem repetições após {max_tentativas} tentativas. Usando a última versão embaralhada.")
        return letras
    
    @staticmethod
    def set_table_style_safe(table, doc, style_name='Table Grid', fallback='Normal'):
        table_styles = [s for s in doc.styles if getattr(s, "type", None) == 3]
        table_style_names = [s.name for s in table_styles]
        if style_name in table_style_names:
            table.style = style_name
        elif fallback in table_style_names:
            table.style = fallback
        elif table_styles:
            table.style = table_styles[0].name

    @staticmethod
    def add_gray_shading(cell, color="D9D9D9"):
        """
        Adiciona fundo cinza (ou outra cor hexadecimal) à célula de uma tabela do python-docx.
        """
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), color)
        tcPr.append(shd)

    def adicionar_rascunho_discursiva(self, doc, total_linhas=85, titulo="RASCUNHO DA PROVA DISCURSIVA"):
        altura_linha_cm = 0.75
        linhas_por_pagina = 30

        for bloco in range(0, total_linhas, linhas_por_pagina):
            linhas_esta_pagina = min(linhas_por_pagina, total_linhas - bloco)
            if bloco > 0:
                doc.add_page_break()

            # TÍTULO em todas as páginas
            p_titulo = doc.add_paragraph()
            p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p_titulo.add_run(titulo)
            run.bold = True
            run.font.size = Pt(14)
            run.font.name = "Arial"

            doc.add_paragraph()

            tabela = doc.add_table(rows=linhas_esta_pagina, cols=2)
            tabela.autofit = False
            tabela.allow_autofit = False
            tabela.alignment = WD_TABLE_ALIGNMENT.CENTER
            tabela.columns[0].width = Cm(1.1)
            tabela.columns[1].width = Cm(17)

            # Bordas externas e internas
            tbl = tabela._tbl
            tblPr = tbl.tblPr
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
                tbl.append(tblPr)
            tblBorders = OxmlElement('w:tblBorders')
            for border_name in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
                border = OxmlElement(f'w:{border_name}')
                border.set(qn('w:val'), 'single')
                border.set(qn('w:sz'), '8')
                border.set(qn('w:space'), '0')
                border.set(qn('w:color'), '000000')
                tblBorders.append(border)
            tblPr.append(tblBorders)

            for row_idx, row in enumerate(tabela.rows):
                row.height = Cm(altura_linha_cm)
                row.height_rule = WD_ROW_HEIGHT.EXACTLY
                idx = bloco + row_idx
                cell_num = row.cells[0]
                cell_resp = row.cells[1]
                cell_num.width = Cm(1.1)
                cell_resp.width = Cm(17)

                # Numeração só na 1, 5, 10, 15...
                if (idx+1) % 5 == 0 or (idx == 0):
                    par = cell_num.paragraphs[0]
                    run = par.add_run(str(idx+1))
                    run.font.size = Pt(10)
                    run.font.bold = True
                    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cell_num.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    self.add_gray_shading(cell_num)
                else:
                    cell_num.text = ""
                    cell_num.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

                cell_resp.text = ""
                cell_resp.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

                for par in cell_num.paragraphs + cell_resp.paragraphs:
                    pf = par.paragraph_format
                    pf.keep_with_next = False
                    pf.keep_together = False
                    pf.space_before = Pt(0)
                    pf.space_after = Pt(0)
                    pf.left_indent = Cm(0)


    def add_column_break(paragraph):
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        run = paragraph.add_run()
        br = OxmlElement('w:br')
        br.set(qn('w:type'), 'column')
        run._r.append(br)

    def generate_docx_and_answer_key_data(self, output_dir: str, base_filename: str, variacao_num: int = 1, num_linhas_rascunho: int = 30, textos_ja_impressos=None):
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from copy import deepcopy
        import random
        from PIL import Image
        from docx.shared import Inches, Pt

        def add_gray_shading(paragraph, color="DDDDDD"):
            pPr = paragraph._p.get_or_add_pPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), color)
            pPr.append(shd)

        def insert_column_break(paragraph):
            run = paragraph.add_run()
            br = OxmlElement('w:br')
            br.set(qn('w:type'), 'column')
            run._r.append(br)

        def apply_keep_together(paragraph):
            pPr = paragraph._element.get_or_add_pPr()
            keepLines = OxmlElement('w:keepLines')
            keepNext = OxmlElement('w:keepNext')
            pPr.append(keepLines)
            pPr.append(keepNext)
        
        def set_table_style_safe(table, doc, style_name='Table Grid', fallback='Normal'):
            table_styles = [s for s in doc.styles if s.type == 3]  # 3 == WD_STYLE_TYPE.TABLE
            table_style_names = [s.name for s in table_styles]
            if style_name in table_style_names:
                table.style = style_name
            elif table_styles:
                table.style = table_styles[0].name

        # Helper to get field from dict/object
        def get_field(obj, field, default=None):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)

        if not PYTHON_DOCX_AVAILABLE_DG_FLAG:
            self.logger.warning("DocxProofGenerator: Geração abortada pois python-docx não está disponível.")
            return None, [], []
        if not all([self.prova_montada, self.evento, self.cargo]):
            self._log_ui("Dados essenciais (prova, evento, cargo) não carregados para geração de DOCX.", "error")
            return None, [], []

        doc = Document(self.template_prova_path) if self.template_prova_path and os.path.exists(self.template_prova_path) else Document()

        if self.format_options.get("duas_colunas"):
            try:
                section = doc.sections[0]
                sectPr = section._sectPr
                cols = OxmlElement('w:cols')
                cols.set(qn('w:num'), '2')
                cols.set(qn('w:space'), str(int(0.5 * 567)))
                cols.set(qn('w:sep'), 'true')
                sectPr.append(cols)
            except Exception as e_cols:
                self.logger.error(f"Erro ao aplicar layout de duas colunas: {e_cols}", exc_info=True)

        style = doc.styles['Normal']
        font = style.font
        fonte_principal = self.format_options.get("fonte_principal", "Arial")
        tamanho_fonte_principal = Pt(self.format_options.get("tamanho_fonte_principal", 12))
        font.name = fonte_principal
        font.size = tamanho_fonte_principal

        paragraph_format = style.paragraph_format
        paragraph_format.line_spacing = 1.0
        paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph_format.space_before = Pt(0)
        paragraph_format.space_after = Pt(0)

        self._add_header_footer(doc)

        primeiro_elemento_adicionado = False
        titulo_prova = get_field(self.prova_montada, "titulo_prova", "")
        if titulo_prova:
            if doc.paragraphs and doc.paragraphs[0].text == "" and not doc.paragraphs[0].runs:
                p_titulo = doc.paragraphs[0]
                p_titulo.add_run(titulo_prova).bold = True
            else:
                p_titulo = doc.add_paragraph()
                p_titulo.add_run(titulo_prova).bold = True
            p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
            primeiro_elemento_adicionado = True
            apply_keep_together(p_titulo)

        config_obj = get_field(self.prova_montada, "configuracoes", {})
        instrucoes_gerais = get_field(config_obj, "instrucoes_gerais", "")
        if instrucoes_gerais:
            if primeiro_elemento_adicionado:
                doc.add_paragraph()
            p_inst_titulo = doc.add_paragraph()
            p_inst_titulo.add_run("INSTRUÇÕES GERAIS").bold = True
            doc.add_paragraph(instrucoes_gerais)
            doc.add_paragraph()

        answer_key_data = []
        ordered_question_ids = []
        textos_referencia = get_field(self.prova_montada, "textos_referencia_prova", [])
        # Monta o map de textos de referência
        textos_referencia_map = {}
        print("IDs do questoes_vinculo do texto:")
        for tr in textos_referencia:
            tr_id = get_field(tr, "id_texto_ref", None)
            if tr_id:
                textos_referencia_map[tr_id] = tr

        textos_ja_impressos = set()
        blocos_questoes = get_field(self.prova_montada, "blocos_questoes", [])
        blocos_ordenados = sorted(
            blocos_questoes,
            key=lambda b: get_field(b, "ordem_bloco", 999)
        )
        total_questoes = sum(len(get_field(bloco, "questoes", [])) for bloco in blocos_ordenados)
        letras_gabarito_total = self.gerar_gabarito_balanceado(total_questoes, seed=f"{variacao_num}-TOTAL")
        idx_global_gabarito = 0
        bloco_discursivo = None
        nova_secao = None

        for bloco_idx, bloco in enumerate(blocos_ordenados):
            # Aceita ambos os campos para máxima compatibilidade de backend
            titulo_disciplina = (
                get_field(bloco, 'nome_disciplina_na_prova')
                or get_field(bloco, 'nome_disciplina_prova')
                or get_field(bloco, 'nome_disciplina')
                or 'Questões'
            ).upper()
            questoes_do_bloco = get_field(bloco, "questoes", [])
            print(f"BLOCO: {titulo_disciplina} — QTD QUESTOES: {len(questoes_do_bloco)}")
            
            if "discursiva" in titulo_disciplina.lower():
                bloco_discursivo = bloco
                continue

            if bloco_idx == 0 and doc.paragraphs and doc.paragraphs[0].text == "" and not doc.paragraphs[0].runs:
                p_titulo_bloco = doc.paragraphs[0]
            else:
                p_titulo_bloco = doc.add_paragraph()

            p_titulo_bloco.paragraph_format.space_before = Pt(0)
            run = p_titulo_bloco.add_run(titulo_disciplina)
            run.bold = True
            p_titulo_bloco.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_gray_shading(p_titulo_bloco)
            doc.add_paragraph()

            # INSTRUÇÕES PARA INFORMÁTICA
            if "informática" in titulo_disciplina.lower():
                instrucoes_informatica = [
                    "Nas questões que abordarem conteúdos de informática e/ou tecnologia da informação, presume-se que todos os programas citados estão configurados em seus padrões originais, sem quaisquer limitações de acesso, funcionamento ou uso em relação aos softwares, arquivos, pastas, recursos e dispositivos mencionados.",
                ]
                style_name = 'List Bullet'
                if style_name not in doc.styles:
                    style_name = None
                for instrucao in instrucoes_informatica:
                    if style_name:
                        p = doc.add_paragraph(instrucao, style=style_name)
                    else:
                        p = doc.add_paragraph()
                        p.add_run(text="•\t").bold = True
                        p.add_run(instrucao)
                        p.paragraph_format.left_indent = Inches(0.5)
                        p.paragraph_format.first_line_indent = Inches(-0.25)
                    p.paragraph_format.space_after = Pt(6)
                doc.add_paragraph()

            questoes_do_bloco = get_field(bloco, "questoes", [])
            print(f"BLOCO: {titulo_disciplina} — QTD QUESTOES: {len(questoes_do_bloco)}")
            textos_referencia = get_field(self.prova_montada, "textos_referencia_prova", [])
            textos_referencia_map = {}
            map_texto_questoes = {}
            print("IDs do questoes_vinculo do texto:")
            for tr in textos_referencia:
                print("id_texto_ref:", tr.get("id_texto_ref"))
                print("questoes_vinculo:", tr.get("questoes_vinculo"))
                print("LISTA IDS:", [q.strip() for q in (tr.get("questoes_vinculo") or "").split(",") if q.strip()])
                id_texto = get_field(tr, "id_texto_ref", None)
                questoes_vinculo = set(q.strip() for q in (get_field(tr, "questoes_vinculo", "") or "").split(",") if q.strip())
                textos_referencia_map[id_texto] = tr
                map_texto_questoes[id_texto] = questoes_vinculo

            # Agrupa as questões do bloco por texto de referência
            
            grupos = {}
            print("QUESTOES DO BLOCO:")
            for questao in questoes_do_bloco:
                id_ref = questao.get("id_referencia_vinculo")
                grupos.setdefault(id_ref, []).append(questao)

            # ORDENA OS GRUPOS (referências primeiro, depois questões sem referência)
            for id_ref in sorted(grupos.keys(), key=lambda x: (x is None, x)):
                questoes_grupo = grupos[id_ref][:]
                rng = random.Random(f"{bloco_idx}-{id_ref}-{variacao_num}")
                rng.shuffle(questoes_grupo)

                # IMPRIME O TEXTO OU IMAGEM DE REFERÊNCIA (APENAS UMA VEZ)
                if id_ref and id_ref not in textos_ja_impressos:
                    texto_ref = textos_referencia_map.get(id_ref)
                    numeros_questoes_grupo = list(range(
                        ordered_question_ids[-1] + 1 if ordered_question_ids else 1,
                        (ordered_question_ids[-1] if ordered_question_ids else 0) + len(questoes_grupo) + 1
                    ))
                    prefixo = "Imagem" if texto_ref and texto_ref.get("tipo_conteudo", "").lower() == "imagem" else "Texto"

                    # Cabeçalho (MANTENHA!)
                    if len(numeros_questoes_grupo) == 1:
                        cabecalho = f"{prefixo} para a questão {numeros_questoes_grupo[0]}."
                    elif len(numeros_questoes_grupo) <= 4:
                        cabecalho = f"{prefixo} para as questões " + ", ".join(map(str, numeros_questoes_grupo[:-1])) + f" e {numeros_questoes_grupo[-1]}."
                    else:
                        cabecalho = f"{prefixo} para as questões de {min(numeros_questoes_grupo)} a {max(numeros_questoes_grupo)}."

                    if ordered_question_ids:
                        doc.add_paragraph()
                    self._add_formatted_paragraph(
                        doc,
                        text=cabecalho,
                        bold=True,
                        alignment=WD_ALIGN_PARAGRAPH.LEFT,
                        font_name=fonte_principal,
                        font_size=tamanho_fonte_principal,
                        first_line_indent_cm=0.0
                    )
                    doc.add_paragraph()

                    # ----------- IMPRESSÃO DO TEXTO DE REFERÊNCIA (título/corpo/legenda) ----------
                    titulo = texto_ref.get("titulo") if texto_ref else ""
                    conteudo = str(texto_ref.get("conteudo", "")).strip() if texto_ref else ""
                    legenda_texto = texto_ref.get("legenda_texto") if texto_ref else ""
                    tipo_conteudo = texto_ref.get("tipo_conteudo", "") if texto_ref else ""

                    if titulo:
                        titulo = decrypt_text(titulo)
                    if conteudo:
                        conteudo = safe_decrypt(conteudo)
                    if legenda_texto:
                        legenda_texto = decrypt_text(legenda_texto)

                    def _strip_html_tags(text):
                        import re
                        return re.sub(r'<.*?>', '', text or '').strip()

                    duplica_titulo = False
                    titulo_str = (titulo or '').strip().lower()
                    conteudo_inicio = conteudo[:300].strip().lower()
                    conteudo_inicio_plain = _strip_html_tags(conteudo_inicio)
                    if titulo_str:
                        if (titulo_str == conteudo_inicio_plain or titulo_str in conteudo_inicio_plain[:len(titulo_str)+10]):
                            duplica_titulo = True

                    # Título do texto de referência (NÃO duplicado)
                    if titulo and not duplica_titulo:
                        if '<' in titulo:
                            html_to_docx(doc, titulo, fonte_principal, tamanho_fonte_principal)
                        else:
                            p_titulo = doc.add_paragraph()
                            p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            run = p_titulo.add_run(titulo)
                            run.bold = True
                            run.italic = True
                        doc.add_paragraph()

                    # Corpo do texto de referência
                    if tipo_conteudo.lower() == "imagem" or conteudo.lower().endswith(('.png', '.jpg', '.jpeg')):
                        caminho_imagem = texto_ref.get('caminho_imagem_relativo') or conteudo.replace("![](", "").replace(")", "").strip()
                        if caminho_imagem:
                            p_img_ref = doc.add_paragraph()
                            p_img_ref.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            self._add_image_to_paragraph(p_img_ref, caminho_imagem, doc=doc, is_texto_referencia=True)
                    elif conteudo:
                        if '<' in conteudo:
                            html_to_docx(doc, conteudo, fonte_principal, tamanho_fonte_principal)
                        else:
                            for paragrafo in conteudo.split('\n'):
                                if paragrafo.strip():
                                    p = doc.add_paragraph(paragrafo)
                                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                                    p.paragraph_format.first_line_indent = Cm(1.0)

                    # Legenda do texto de referência (se houver)
                    if legenda_texto:
                        if '<' in legenda_texto:
                            html_to_docx(doc, legenda_texto, fonte_principal, tamanho_fonte_principal)
                        else:
                            p_legenda = doc.add_paragraph()
                            p_legenda.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                            run = p_legenda.add_run(f"Legenda: {legenda_texto}")
                            run.italic = True

                    self._add_separator(doc)
                    textos_ja_impressos.add(id_ref)

                # IMPRIME AS QUESTÕES DO GRUPO NORMALMENTE
                for questao in questoes_grupo:
                    current_question_display_number = (ordered_question_ids[-1] + 1) if ordered_question_ids else 1
                    ordered_question_ids.append(current_question_display_number)
                    letra_correta = letras_gabarito_total[idx_global_gabarito]
                    idx_global_gabarito += 1

                    alternativas_orig = list(get_field(questao, "opcoes", []))
                    if not alternativas_orig:
                        self.logger.warning(f"Questão ID {get_field(questao, 'id_questao', '?')} não possui alternativas, pulando.")
                        continue

                    alternativa_correta = next((alt for alt in alternativas_orig if get_field(alt, "correta", False)), None)
                    semente_alt = f"{get_field(questao, 'id_questao', '?')}-VAR{variacao_num}-ALTS"
                    rng_alt = random.Random(semente_alt)
                    alternativas_final = list(alternativas_orig)
                    rng_alt.shuffle(alternativas_final)

                    idx_correta_real = next(i for i, alt in enumerate(alternativas_final) if get_field(alt, "correta", False))
                    idx_balanceado = ord(letra_correta) - ord('A')

                    if idx_correta_real != idx_balanceado:
                        alternativas_final[idx_correta_real], alternativas_final[idx_balanceado] = (
                            alternativas_final[idx_balanceado], alternativas_final[idx_correta_real],
                        )
                        idx_correta_real = idx_balanceado

                    letra_correta_final = chr(ord('A') + idx_correta_real)
                    questao_embaralhada = deepcopy(questao)
                    if isinstance(questao_embaralhada, dict):
                        questao_embaralhada["opcoes"] = alternativas_final
                    else:
                        questao_embaralhada.opcoes = alternativas_final

                    self._add_question_to_doc(
                        doc, questao_embaralhada, current_question_display_number, [],
                        variacao_num=variacao_num,
                        textos_map=textos_referencia_map
                    )
                    if get_field(questao, "anulada", False):
                        gabarito_exibido = "ANULADA"
                    elif get_field(questao, "gabarito_definitivo", None):
                        gabarito_exibido = get_field(questao, "gabarito_definitivo", "").strip().upper()
                    else:
                        gabarito_exibido = letra_correta_final

                    codigo_curto = (
                        get_field(questao, "codigo_curto_questao", "")
                        or get_field(questao, "codigo_curto", "")
                        or get_field(get_field(questao, "metadados_questao", {}), "codigo_curto_questao", "")
                        or get_field(get_field(questao, "metadados_questao", {}), "codigo_curto", "")
                    )

                    # Descriptografa texto da alternativa correta
                    texto_opcao_correta = get_field(alternativa_correta, "texto_opcao", "") if alternativa_correta else ""
                    if texto_opcao_correta:
                        try:
                            texto_opcao_correta = decrypt_text(texto_opcao_correta)
                        except Exception:
                            pass  # já pode estar descriptografado ou não precisar descriptografar

                    answer_key_data.append({
                        "numero_questao_exibido": current_question_display_number,
                        "gabarito_letra_exibida": gabarito_exibido,
                        "disciplina_nome": (
                            get_field(bloco, 'nome_disciplina_na_prova', '') or
                            get_field(bloco, 'nome_disciplina_prova', '') or
                            get_field(bloco, 'nome_disciplina', '') or
                            'N/A'
                        ),
                        "texto_opcao_correta_original": texto_opcao_correta,
                        "codigo_curto_questao": get_field(questao, "codigo_curto_questao", ""),
                    })

            # Quebra de bloco
            is_last_block = (bloco_idx == len(blocos_ordenados) - 1)
            if not is_last_block:
                next_bloco = blocos_ordenados[bloco_idx + 1]
                is_next_discursive = "discursiva" in get_field(next_bloco, 'nome_disciplina_prova', '').lower()
                if not is_next_discursive:
                    if self.format_options.get("quebra_de_pagina_por_bloco"):
                        if self.format_options.get("duas_colunas"):
                            last_paragraph = doc.paragraphs[-1]
                            DocxProofGenerator.add_column_break(last_paragraph)
                        else:
                            doc.add_page_break()

        # Discursiva
        if bloco_discursivo is not None:
            nova_secao = doc.add_section(WD_SECTION_START.NEW_PAGE)
            sectPr = nova_secao._sectPr
            for el in sectPr.xpath('./w:cols'):
                sectPr.remove(el)
            cols = OxmlElement('w:cols')
            cols.set(qn('w:num'), '1')
            sectPr.append(cols)
            self.logger.info("Nova seção criada em layout de uma coluna para discursiva.")

            titulo_discursiva = get_field(bloco_discursivo, 'nome_disciplina_prova', 'PROVA DISCURSIVA').upper()
            p_titulo_discursiva = doc.add_paragraph()
            run_titulo_discursiva = p_titulo_discursiva.add_run(titulo_discursiva)
            run_titulo_discursiva.bold = True
            p_titulo_discursiva.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_gray_shading(p_titulo_discursiva)
            doc.add_paragraph()

            instrucoes_discursiva = [
                "Nesta prova, faça o que se pede, usando, caso deseje, o espaço para rascunho indicado no presente caderno. Em seguida, transcreva o texto para o respectivo Caderno de Texto Definitivo, no local apropriado, pois não serão avaliados fragmentos de texto escritos em locais indevidos. A resposta deverá conter a extensão mínima e máxima de linhas para o texto conforme o edital.",
                "Qualquer fragmento de texto que ultrapassar a extensão máxima de linhas será desconsiderado. Também será desconsiderado o texto que não for escrito no Caderno de Texto Definitivo.",
                "O texto deverá ser manuscrito, em letra legível, com caneta esferográfica de tinta azul ou preta, fabricada com material transparente.",
                "Será admitida a assinatura apenas no campo apropriado.",
                "O Caderno de Texto Definitivo será o único documento válido para avaliação da prova discursiva."
            ]

            style_name = 'List Bullet'
            if style_name not in doc.styles:
                self.logger.warning(f"O estilo '{style_name}' não foi encontrado. Usando formatação manual de marcadores.")
                style_name = None

            for instrucao in instrucoes_discursiva:
                if style_name:
                    p = doc.add_paragraph(instrucao, style=style_name)
                else:
                    p = doc.add_paragraph()
                    p.add_run(text="•\t").bold = True
                    p.add_run(instrucao)
                    p.paragraph_format.left_indent = Inches(0.5)
                    p.paragraph_format.first_line_indent = Inches(-0.25)
                p.paragraph_format.space_after = Pt(6)

            self._add_separator(doc)
            doc.add_paragraph()
            
            questoes_discursivas = get_field(bloco_discursivo, "questoes", [])
            num_questoes_disc = len(questoes_discursivas)
            for idx, questao in enumerate(questoes_discursivas, start=1):
                questao_number_display = idx if num_questoes_disc > 1 else None
                self._add_question_to_doc(doc, questao, questao_number_display, [], variacao_num)
                answer_key_data.append({
                    "numero_questao_exibido": idx,
                    "gabarito_letra_exibida": "",
                    "disciplina_nome": titulo_discursiva,
                    "texto_opcao_correta_original": "",
                    "questao_id_original": get_field(questao, "id_questao", None)
                })
            ordered_question_ids.extend(list(range(
                (ordered_question_ids[-1] + 1) if ordered_question_ids else 1,
                (ordered_question_ids[-1] + 1) if ordered_question_ids else 1 + len(questoes_discursivas)
            )))

        if bloco_discursivo is not None:
            self.logger.info("Adicionando folha de rascunho pautada...")
            doc.add_page_break()
            questoes_discursivas = get_field(bloco_discursivo, "questoes", [])
            for idx, questao in enumerate(questoes_discursivas, start=1):
                detalhes = None
                # Procure o campo detalhes_discursiva ou detalhes_discursiva_model
                if isinstance(questao, dict):
                    detalhes = questao.get("detalhes_discursiva") or questao.get("detalhes_discursiva_model")
                else:
                    detalhes = getattr(questao, "detalhes_discursiva", None) or getattr(questao, "detalhes_discursiva_model", None)
                num_linhas = 30  # valor padrão
                if detalhes:
                    if isinstance(detalhes, dict):
                        num_linhas = int(detalhes.get("numero_linhas_resposta") or 30)
                    else:
                        num_linhas = int(getattr(detalhes, "numero_linhas_resposta", 30) or 30)
                self.adicionar_rascunho_discursiva(doc, total_linhas=num_linhas, titulo=f"RASCUNHO DA QUESTÃO DISCURSIVA {idx}")

        config_obj = get_field(self.prova_montada, "configuracoes", {})
        incluir_folha_rascunho = get_field(config_obj, "incluir_folha_rascunho", False)
        if incluir_folha_rascunho:
            doc.add_page_break()
            self._add_formatted_paragraph(doc, "FOLHA DE RASCUNHO", alignment=WD_ALIGN_PARAGRAPH.CENTER, font_size=Pt(14), bold=True)

        output_path = os.path.join(output_dir, f"{base_filename}.docx")
        try:
            doc.save(output_path)
            print("VOU SALVAR O DOCX AGORA EM:", output_path)
            return output_path, answer_key_data, ordered_question_ids
        except Exception as e:
            self.logger.error(f"Erro ao salvar arquivo DOCX '{output_path}': {e}", exc_info=True)
            return None, [], []

    
    def _remover_endereco_imagem(self, texto):
        import re
        texto = re.sub(r'\[IMAGEM:.*?\]', '', texto)
        texto = re.sub(r'[^\s]+\.(png|jpg|jpeg|gif)', '', texto, flags=re.IGNORECASE)
        return texto.strip()

    def _corrigir_formato_imagem_marcada(self, texto):
        """
        Corrige tags mal formatadas como: ![IMAGEM: nome.png] para o formato padrão ![](nome.png)
        """
        return re.sub(r'!\[.*?:\s*(.*?)\]', r'![](\1)', texto)
    
    def _create_tbl_width_element(self, w: int, type: str = "dxa"):
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        tbl_width = OxmlElement("w:tcW")
        tbl_width.set(qn("w:w"), str(int(w)))
        tbl_width.set(qn("w:type"), type)
        return tbl_width

       
    # SUBSTITUA O MÉTODO PELA VERSÃO FINAL COM O ATRIBUTO CORRETO
    def _add_question_to_doc(
        self,
        document: "Document",
        questao: "QuestaoType",
        questao_number_display: int,
        letras_ja_usadas: list,
        variacao_num: int = 1,
        alternative_labels: str = "ABCDE",
        textos_map=None
    ):
        from docx.shared import Cm, Pt, RGBColor
        from backend.app.html_to_docx import html_to_docx

        def get_field(obj, field, default=None):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)

        fonte = self.format_options.get("fonte_principal", "Calibri")
        tamanho_fonte = Pt(self.format_options.get("tamanho_fonte_principal", 11))
        mostrar_codigo_curto = self.format_options.get("exibir_codigo_curto_questao", False)

        tipo_questao_raw = get_field(questao, 'tipo', '')
        tipo_questao = str(tipo_questao_raw).strip().lower()
        is_discursive = 'discursiva' in tipo_questao
        print("DEBUG QUESTAO:", get_field(questao, "id_questao", None), "| tipo:", repr(tipo_questao), "| is_discursive:", is_discursive)

        questao_paragraphs = []

        # TÍTULO DA QUESTÃO
        if questao_number_display is not None:
            texto_titulo = f"Questão {questao_number_display}"
            if mostrar_codigo_curto:
                codigo_curto = (
                    get_field(questao, 'codigo_curto_questao', '') or
                    get_field(questao, 'codigo_curto', '') or
                    get_field(get_field(questao, 'metadados_questao', {}), 'codigo_curto_questao', '') or
                    get_field(get_field(questao, 'metadados_questao', {}), 'codigo_curto', '')
                )
                if codigo_curto:
                    texto_titulo += f" [{codigo_curto}]"

            p_titulo = document.add_paragraph()
            questao_paragraphs.append(p_titulo)
            run_titulo = p_titulo.add_run(texto_titulo)
            run_titulo.bold = True
            run_titulo.font.name = fonte
            run_titulo.font.size = tamanho_fonte
            p_titulo.paragraph_format.space_after = Pt(6)

        # ENUNCIADO
        dados_formatados_brutos = get_field(questao, 'enunciado_formatado', None)
        dados_limpos = []
        if isinstance(dados_formatados_brutos, list):
            for item in dados_formatados_brutos:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    dados_limpos.append([item[0], item[1]])

        if dados_limpos:
            recuo_a_aplicar = 1.0 if is_discursive else None
            p_enunciado = document.add_paragraph()
            questao_paragraphs.append(p_enunciado)
            self.inserir_texto_formatado_docx(
                p_enunciado,
                filtrar_tags_lista_formatada_robusto(dados_limpos),
                first_line_indent_cm=recuo_a_aplicar,
                mostrar_gabarito=False
            )
            p_enunciado.paragraph_format.space_after = Pt(6)
        else:
            enunciado_val = get_field(questao, 'enunciado', '') or ''
            enunciado_val = decrypt_text(enunciado_val) if enunciado_val else ''
            if enunciado_val.strip():
                if '<' in enunciado_val:
                    html_to_docx(document, enunciado_val, fonte, tamanho_fonte)
                    for p in document.paragraphs[-1:]:
                        questao_paragraphs.append(p)
                else:
                    parags = self._add_text_with_images(document, enunciado_val, questao, largura_cm=8.0)
                    questao_paragraphs.extend(parags)

        caminho_img = get_field(questao, 'caminho_imagem_relativo', None)
        if caminho_img:
            norm_path = os.path.normpath(caminho_img)
            if norm_path.startswith("static" + os.sep):
                norm_path = norm_path[len("static" + os.sep):]
            elif norm_path.startswith("static/"):
                norm_path = norm_path[len("static/"):]
            elif norm_path.startswith("static\\"):
                norm_path = norm_path[len("static\\"):]

            is_two_columns = self.format_options.get("duas_colunas", False)
            image_width_cm = 8.5 if is_two_columns else 16.0

            p_img = document.add_paragraph()
            questao_paragraphs.append(p_img)
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._add_image_to_paragraph(
                p_img,
                norm_path,
                width_cm=image_width_cm
            )

        # PATCH: NÃO IMPRIME ALTERNATIVAS PARA DISCURSIVA
        if is_discursive:
            print("DEBUG: Entrou no bloco da discursiva, NÃO imprimindo alternativas!")
            self._add_separator(document)
            return "?"

        # --- DAQUI PRA BAIXO SEGUE NORMAL PARA MULTIPLA ESCOLHA E OUTROS TIPOS ---
        opcoes_para_imprimir = list(get_field(questao, "opcoes", []))
        print("DEBUG: opcoes_para_imprimir =", opcoes_para_imprimir)
        if not opcoes_para_imprimir:
            self.logger.warning(f"Questão ID {get_field(questao, 'id_questao', '?')} não possui opções para processar.")
            return "?"

        correct_option_display_label = "?"
        if self.format_options.get("duas_colunas"):
            largura_maxima_alternativa = 6.0
        else:
            largura_maxima_alternativa = 12.0

        p_espaco = document.add_paragraph()
        questao_paragraphs.append(p_espaco)

        alternativa_paragraphs = []
        for i, opcao_obj in enumerate(opcoes_para_imprimir):
            texto_opcao_val = get_field(opcao_obj, 'texto_opcao', '') or ''
            texto_opcao_val = decrypt_text(texto_opcao_val) if texto_opcao_val else ''
            letra = alternative_labels[i]

            texto_opcao_vazio = not texto_opcao_val.strip()
            imagem_opcao = get_field(opcao_obj, 'imagem_path_opcao', None)
            is_correta = get_field(opcao_obj, 'correta', False)
            cor_gabarito = RGBColor(255, 0, 0) if is_correta else None

            if texto_opcao_vazio and imagem_opcao:
                from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT
                tabela = document.add_table(rows=1, cols=2)
                tabela.alignment = WD_TABLE_ALIGNMENT.LEFT
                tabela.autofit = False
                tabela.rows[0].height_rule = WD_ROW_HEIGHT.AT_LEAST
                tabela.rows[0].height = Cm(0.5)
                largura_col_letra = Cm(1.0)
                largura_col_imagem = Cm(8.0)
                tabela.columns[0].width = largura_col_letra
                tabela.columns[1].width = largura_col_imagem
                celula_letra = tabela.cell(0, 0)
                celula_letra.width = largura_col_letra
                celula_letra.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p_letra = celula_letra.paragraphs[0]
                p_letra.paragraph_format.left_indent = Cm(-0.3)
                p_letra.alignment = WD_ALIGN_PARAGRAPH.LEFT
                run_letra = p_letra.add_run(f"{letra})")
                run_letra.bold = True
                run_letra.font.name = fonte
                run_letra.font.size = tamanho_fonte
                if cor_gabarito:
                    run_letra.font.color.rgb = cor_gabarito
                alternativa_paragraphs.append(p_letra)
                celula_imagem = tabela.cell(0, 1)
                p_img = celula_imagem.paragraphs[0]
                p_img.alignment = WD_ALIGN_PARAGRAPH.LEFT
                self._add_image_to_paragraph(
                    p_img,
                    imagem_opcao,
                    doc=document,
                    width_cm=largura_maxima_alternativa
                )
                alternativa_paragraphs.append(p_img)
            else:
                p_opcao = document.add_paragraph()
                alternativa_paragraphs.append(p_opcao)
                p_opcao.paragraph_format.left_indent = Cm(0.8)
                p_opcao.paragraph_format.first_line_indent = Cm(-0.8)

                run_letra = p_opcao.add_run(f"{letra})\t")
                run_letra.font.name = fonte
                run_letra.font.size = tamanho_fonte
                run_letra.bold = True
                if cor_gabarito:
                    run_letra.font.color.rgb = cor_gabarito

                texto_opcao_formatado = get_field(opcao_obj, "texto_opcao_formatado", None)
                if texto_opcao_formatado:
                    self.inserir_texto_formatado_docx(
                        p_opcao,
                        texto_opcao_formatado,
                        correta=is_correta,
                        mostrar_gabarito=False
                    )
                else:
                    if texto_opcao_val.strip():
                        run_txt = p_opcao.add_run(texto_opcao_val)
                        if cor_gabarito:
                            run_txt.font.color.rgb = cor_gabarito
                    else:
                        texto_opcao_limpo = f"<<ALTERNATIVA SEM TEXTO: {get_field(opcao_obj, 'id_opcao_questao', '')}>>"
                        run_txt = p_opcao.add_run(texto_opcao_limpo)
                        if cor_gabarito:
                            run_txt.font.color.rgb = cor_gabarito

                if imagem_opcao:
                    p_img_op = document.add_paragraph()
                    p_img_op.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    self._add_image_to_paragraph(
                        p_img_op,
                        imagem_opcao,
                        doc=document,
                        width_cm=largura_maxima_alternativa
                    )
                    alternativa_paragraphs.append(p_img_op)

            if is_correta:
                correct_option_display_label = letra

        for idx, p in enumerate(alternativa_paragraphs):
            p.paragraph_format.keep_together = True
            if idx < len(alternativa_paragraphs) - 1:
                p.paragraph_format.keep_with_next = True

        for idx, p in enumerate(questao_paragraphs):
            p.paragraph_format.keep_together = True
            if idx < len(questao_paragraphs) - 1 or alternativa_paragraphs:
                p.paragraph_format.keep_with_next = True

        conteudo_formatado = get_field(questao, "conteudo_formatado", None)
        if conteudo_formatado:
            p_ref = document.add_paragraph()
            p_ref.paragraph_format.left_indent = Cm(1.0)
            p_ref.paragraph_format.keep_together = True
            lista_formatada = [
                [item[0], (item[1] or '').rstrip('\n')] if item[0] == 'text' else item
                for item in conteudo_formatado
            ]
            lista_formatada_sem_tags = filtrar_tags_lista_formatada(lista_formatada)
            self.inserir_texto_formatado_docx(p_ref, lista_formatada_sem_tags)
        elif get_field(questao, "referencia", None):
            p_ref = document.add_paragraph()
            p_ref.paragraph_format.left_indent = Cm(1.0)
            p_ref.paragraph_format.keep_together = True
            ref_val = get_field(questao, "referencia", "") or ""
            if '<' in ref_val:
                html_to_docx(document, ref_val, fonte, tamanho_fonte)
            else:
                ref_limpa = remover_tags_metadados(str(ref_val).rstrip('\n'))
                p_ref.add_run(ref_limpa)

        self._add_separator(document)
        return correct_option_display_label

        



class ArchiveManager:
    """Gerencia operações de arquivamento como preenchimento de PDF, merge e ZIP."""
    def __init__(self, app_instance: Optional[Any] = None, logger_param: Optional[logging.Logger] = None):
        self.app_instance = app_instance
        self.logger = logger_param if logger_param else logger_dg.getChild(self.__class__.__name__)

    def _log_ui(self, message: str, level: str = "info"):
        if self.app_instance and hasattr(self.app_instance, 'log_message'):
            self.app_instance.log_message(message, level)
        else:
            log_func = getattr(self.logger, level, self.logger.info)
            log_func(message)

    # Substitua a função de preenchimento/carimbo anterior por esta
    def fill_pdf_form(self, template_pdf_path: str, output_pdf_path: str, data_dict: dict) -> bool:
        from pypdf.generic import NameObject, BooleanObject, DictionaryObject, IndirectObject
        """
        Preenche um formulário PDF replicando a lógica de baixo nível do script
        'app_preenchedor_provas.py' para máxima compatibilidade.
        """
        self.logger.info(f"Preenchendo '{os.path.basename(template_pdf_path)}' com lógica transplantada.")

        try:
            reader = PdfReader(template_pdf_path)
            writer = PdfWriter()

            # Adiciona as páginas do template ao novo arquivo
            for page in reader.pages:
                writer.add_page(page)

            # Lógica de baixo nível para copiar a estrutura do formulário e garantir a visibilidade
            # Esta é a parte crucial, adaptada do seu script funcional
            if reader.trailer.get("/Root") and reader.trailer["/Root"].get_object().get("/AcroForm"):
                acroform_ref = reader.trailer["/Root"].get_object().raw_get("/AcroForm")
                writer._root_object[NameObject("/AcroForm")] = acroform_ref
                
                if "/AcroForm" in writer._root_object:
                    acro_dict = writer._root_object["/AcroForm"].get_object()
                    if isinstance(acro_dict, DictionaryObject):
                        acro_dict.update({NameObject("/NeedAppearances"): BooleanObject(True)})
                        self.logger.info("Estrutura /AcroForm copiada e flag /NeedAppearances definida.")
            else:
                self.logger.warning(f"Template '{os.path.basename(template_pdf_path)}' não contém /AcroForm. O preenchimento provavelmente falhará.")
                # Se não há formulário, não há o que preencher, mas salvamos uma cópia para não quebrar o fluxo.
                with open(output_pdf_path, "wb") as f_out:
                    writer.write(f_out)
                return True # Retorna sucesso pois não havia o que fazer

            # Preenche os campos do formulário
            if writer.pages:
                writer.update_page_form_field_values(writer.pages[0], fields=data_dict)
            
            # ######################################################################
            # ## PASSO FINAL: GARANTA QUE A LINHA ABAIXO ESTEJA ATIVA E PRESENTE ##
            # ######################################################################
            # "Achata" o resultado para máxima compatibilidade visual
            if hasattr(writer, 'flatten_annotations'):
                writer.flatten_annotations()
                self.logger.info("Campos do formulário achatados (flattened) com sucesso.")

            # Salva o arquivo final
            with open(output_pdf_path, "wb") as fp_output:
                writer.write(fp_output)
        
            self.logger.info(f"Formulário PDF processado com sucesso e salvo em: {output_pdf_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"ERRO CRÍTICO ao processar formulário com lógica transplantada: {e}", exc_info=True)
            return False




    def merge_pdfs(self, pdf_paths: List[str], output_path: str, cover_page_path: Optional[str] = None) -> bool:
        """Mescla múltiplos arquivos PDF em um único arquivo. Adiciona uma capa se fornecida."""
        global PDF_MERGE_AVAILABLE # Acessa a flag global
        if not PDF_MERGE_AVAILABLE: # Usa a flag global
            self.logger.warning("PyPDF2 (para merge) não está disponível. Mesclagem de PDF abortada.")
            return False

        merger = PdfWriter()
        try:
            if cover_page_path and os.path.exists(cover_page_path):
                try:
                    merger.append(cover_page_path)
                    self.logger.info(f"Adicionada capa '{cover_page_path}' ao PDF mesclado.")
                except Exception as e_cover:
                    self.logger.error(f"Erro ao adicionar capa '{cover_page_path}': {e_cover}. Continuando sem capa.")
            
            for pdf_file in pdf_paths:
                if os.path.exists(pdf_file):
                    try:
                        merger.append(pdf_file)
                    except Exception as e_append:
                        self.logger.error(f"Erro ao adicionar PDF '{pdf_file}' à mesclagem: {e_append}. Pulando arquivo.")
                else:
                    self.logger.warning(f"Arquivo PDF não encontrado para mesclagem: {pdf_file}")

            if len(merger.pages) > 0:
                with open(output_path, "wb") as f_out:
                    merger.write(f_out)
                self.logger.info(f"PDFs mesclados com sucesso em: {output_path}")
                return True
            else:
                self.logger.warning("Nenhum PDF válido para mesclar. Arquivo de saída não gerado.")
                return False
        except Exception as e:
            self.logger.error(f"Erro durante a mesclagem de PDFs para '{output_path}': {e}", exc_info=True)
            return False
        finally:
            try:
                merger.close() 
            except Exception:
                pass 

    def create_zip(self, file_paths: List[str], output_zip_path: str) -> bool:
        """Cria um arquivo ZIP contendo os arquivos fornecidos."""
        if not file_paths:
            self.logger.warning("Nenhum arquivo fornecido para adicionar ao ZIP. Arquivo ZIP não criado.")
            return False
        try:
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        arcname = os.path.basename(file_path) 
                        zipf.write(file_path, arcname=arcname)
                        self.logger.debug(f"Adicionado '{file_path}' como '{arcname}' ao ZIP.")
                    else:
                        self.logger.warning(f"Arquivo não encontrado para adicionar ao ZIP: {file_path}")
            self.logger.info(f"Arquivo ZIP criado com sucesso: {output_zip_path}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao criar arquivo ZIP '{output_zip_path}': {e}", exc_info=True)
            return False

# Em document_generator.py (ou onde a classe estiver)

class AnswerKeyGenerator:
    """Gera gabaritos em formato CSV em diferentes layouts."""
    def __init__(self, app_instance: Optional[Any] = None, logger_param: Optional[logging.Logger] = None):
        self.app_instance = app_instance
        self.logger = logger_param if logger_param else logging.getLogger(self.__class__.__name__)

    def _write_csv(self, filepath: str, data: List[Dict[str, Any]], headers: List[str]) -> bool:
        """Método auxiliar para escrever dados em um arquivo CSV."""
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                # Usando ponto e vírgula como delimitador padrão
                writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter=';')
                writer.writeheader()
                # Escreve apenas os dados para os cabeçalhos que existem
                for row_data in data:
                    writer.writerow({h: row_data.get(h, "") for h in headers})
            self.logger.info(f"Arquivo CSV '{filepath}' gerado com sucesso.")
            return True
        except Exception as e:
            self.logger.error(f"Erro inesperado ao gerar CSV '{filepath}': {e}", exc_info=True)
            return False

    def generate_complete_csv(self, filepath: str, gabaritos_por_variacao: Dict[str, List[Dict]]) -> bool:
        """
        Gera um CSV completo, com uma linha por questão e uma coluna extra 'Tipo de Prova'.
        """
        if not gabaritos_por_variacao: return False
        
        # Define os cabeçalhos, incluindo a nova coluna no início
        headers = [
            "Tipo de Prova",
            "numero_questao_exibido",
            "disciplina_nome",
            "gabarito_letra_exibida",
            "texto_opcao_correta_original",
            "questao_id_original"
        ]
        
        all_rows = []
        # Itera sobre cada variação de prova (Tipo A, Tipo B, etc.)
        for nome_variacao, dados_gabarito in gabaritos_por_variacao.items():
            for item in dados_gabarito:
                new_row = item.copy()
                new_row["Tipo de Prova"] = nome_variacao # Adiciona a informação do tipo de prova
                all_rows.append(new_row)
        
        # Ordena o resultado final pelo tipo de prova e depois pelo número da questão
        all_rows.sort(key=lambda row: (row.get("Tipo de Prova", ""), row.get("numero_questao_exibido", 0)))
        
        return self._write_csv(filepath, all_rows, headers)

    def generate_simple_row_based_csv(self, filepath: str, cargo_obj: "CargoType", gabaritos_por_variacao: Dict[str, List[Dict]]) -> bool:
        """
        Gera um CSV simples, com uma linha por TIPO de prova, e as respostas em colunas (Q1, Q2...).
        """
        if not gabaritos_por_variacao: return False

        # Determina o número máximo de questões para criar os cabeçalhos Q1, Q2, etc.
        num_questoes = len(next(iter(gabaritos_por_variacao.values()), []))
        question_headers = [f"Q{i+1}" for i in range(num_questoes)]
        
        # Define os cabeçalhos finais do CSV, conforme seu pedido
        headers = ['Código do Cargo', 'Cargo', 'Tipo de Prova'] + question_headers

        output_data = []
        # Itera sobre cada variação de prova para criar uma linha no CSV
        for nome_variacao, dados_gabarito in gabaritos_por_variacao.items():
            row_dict = {
                'Código do Cargo': getattr(cargo_obj, 'codigo_cargo', 'N/A'),
                'Cargo': getattr(cargo_obj, 'nome_cargo', 'N/A'),
                'Tipo de Prova': nome_variacao
            }
            # Preenche as colunas Q1, Q2, ... com as respostas
            for item in dados_gabarito:
                q_num = item.get("numero_questao_exibido")
                if q_num and q_num <= num_questoes:
                    row_dict[f"Q{q_num}"] = item.get("gabarito_letra_exibida")
            
            output_data.append(row_dict)
        
        return self._write_csv(filepath, output_data, headers)


class PdfConverter:
    """Converte arquivos DOCX para PDF usando LibreOffice/soffice."""
    def __init__(self, app_instance: Optional[Any] = None, logger_param: Optional[logging.Logger] = None): # Adicionado logger_param
        self.app_instance = app_instance
        self.logger = logger_param if logger_param else logger_dg.getChild(self.__class__.__name__) # Usar logger_dg como fallback
        self.soffice_path = self._find_soffice()

    def _log_ui(self, message: str, level: str = "info"):
        if self.app_instance and hasattr(self.app_instance, 'log_message'):
            self.app_instance.log_message(message, level)
        else:
            log_func = getattr(self.logger, level, self.logger.info)
            log_func(message)

    def _find_soffice(self) -> Optional[str]:
        """Tenta encontrar o executável do LibreOffice (soffice)."""
        common_paths = [
            "/usr/bin/soffice", 
            "/usr/bin/libreoffice", 
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe", 
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe", 
            "/Applications/LibreOffice.app/Contents/MacOS/soffice" 
        ]
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                self.logger.info(f"LibreOffice encontrado em: {path}")
                return path
        
        soffice_cmd = "soffice" if os.name != 'nt' else "soffice.exe"
        path_from_env = shutil.which(soffice_cmd)
        if path_from_env:
            self.logger.info(f"LibreOffice encontrado no PATH: {path_from_env}")
            return path_from_env

        self.logger.warning("LibreOffice (soffice) não encontrado nos caminhos comuns ou no PATH.")
        self._log_ui("LibreOffice (soffice) não encontrado. Conversão para PDF pode falhar.", "warning")
        return None

    def convert_to_pdf(self, docx_path: str, output_dir: str) -> Optional[str]: # Tornar output_dir minúsculo
        """Converte um arquivo DOCX para PDF."""
        if not self.soffice_path:
            self._log_ui("Executável do LibreOffice não configurado. Conversão para PDF abortada.", "error")
            return None
        if not os.path.exists(docx_path):
            self.logger.error(f"Arquivo DOCX não encontrado para conversão: {docx_path}")
            return None

        pdf_filename = f"{os.path.splitext(os.path.basename(docx_path))[0]}.pdf"
        expected_pdf_path_in_outdir = os.path.join(output_dir, pdf_filename)
        
        abs_docx_path = os.path.abspath(docx_path)
        abs_output_dir = os.path.abspath(output_dir) # Usar output_dir (parâmetro corrigido)

        command = [
            self.soffice_path,
            "--headless",            
            "--convert-to", "pdf",   
            "--outdir", abs_output_dir,  
            abs_docx_path            
        ]
        
        self.logger.info(f"Executando conversão para PDF: {' '.join(command)}")
        self._log_ui(f"Convertendo '{os.path.basename(docx_path)}' para PDF...", "info")

        try:
            process = subprocess.run(command, timeout=120, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
            
            if process.returncode != 0:
                self.logger.error(f"Falha na conversão para PDF (código {process.returncode}): STDOUT: {process.stdout} STDERR: {process.stderr}")
                self._log_ui(f"Erro ao converter '{os.path.basename(docx_path)}' para PDF. Veja logs para detalhes.", "error")
                return None

            if os.path.exists(expected_pdf_path_in_outdir):
                self.logger.info(f"PDF gerado com sucesso: {expected_pdf_path_in_outdir}")
                return expected_pdf_path_in_outdir
            else:
                pdf_path_in_source_dir = os.path.join(os.path.dirname(abs_docx_path), pdf_filename)
                if os.path.exists(pdf_path_in_source_dir):
                    self.logger.info(f"PDF gerado no diretório de origem: {pdf_path_in_source_dir}. Movendo para {abs_output_dir}.")
                    try:
                        shutil.move(pdf_path_in_source_dir, expected_pdf_path_in_outdir)
                        self.logger.info(f"PDF movido para: {expected_pdf_path_in_outdir}")
                        return expected_pdf_path_in_outdir
                    except Exception as e_move:
                        self.logger.error(f"Erro ao mover PDF gerado para o diretório de saída: {e_move}")
                        return None
                else:
                    self.logger.error(f"Arquivo PDF não encontrado em '{expected_pdf_path_in_outdir}' ou '{pdf_path_in_source_dir}' após conversão. STDOUT: {process.stdout}, STDERR: {process.stderr}")
                    self._log_ui(f"Arquivo PDF não encontrado após tentativa de conversão de '{os.path.basename(docx_path)}'.", "error")
                    return None

        except subprocess.TimeoutExpired:
            self.logger.error("Conversão para PDF excedeu o tempo limite (timeout).")
            self._log_ui(f"Conversão de '{os.path.basename(docx_path)}' para PDF demorou demais.", "error")
            return None
        except Exception as e:
            self.logger.error(f"Erro inesperado durante a conversão para PDF: {e}", exc_info=True)
            self._log_ui(f"Erro inesperado ao converter '{os.path.basename(docx_path)}' para PDF: {e}", "error")
            return None


class DocumentGenerator:
    """
    Classe principal para orquestrar a geração de documentos de prova.
    """
    def __init__(self, templates_base_dir: str,
                 logger: logging.Logger,
                 core_elements_module: Any, # Módulo elements
                 config: Optional[dict] = None, 
                 app_instance: Optional[Any] = None):
        
        self.logger = logger.getChild(self.__class__.__name__)
        self.templates_base_dir = templates_base_dir
        self.core_elements = core_elements_module 
        self.config = config if config else {} 
        self.app_instance = app_instance

        self.image_storage_base_dir = self.config.get("media_files_base_dir", "media_files")

        self.output_dir_base = self.config.get("default_export_directory", os.path.join(os.getcwd(), "ProvasGeradas_DG"))
        os.makedirs(self.output_dir_base, exist_ok=True)
        
        self.evento_atual: Optional[EventoType] = None
        self.cargo_atual: Optional[CargoType] = None
        self.prova_montada_atual: Optional[ProvaMontadaType] = None
        
        # Instanciar sub-geradores passando o logger e app_instance
        common_logger = self.logger # Logger base para os sub-geradores
        self.docx_proof_generator: Optional[DocxProofGenerator] = None # Será instanciado em _atualizar_contexto
        self.archive_manager = ArchiveManager(app_instance=self.app_instance, logger_param=common_logger.getChild("ArchiveManager"))
        self.answer_key_generator = AnswerKeyGenerator(app_instance=self.app_instance, logger_param=common_logger.getChild("AnswerKeyGenerator"))
        self.pdf_converter = PdfConverter(app_instance=self.app_instance, logger_param=common_logger.getChild("PdfConverter"))

        self.output_dir_lote: Optional[str] = None
        self.logger.info("DocumentGenerator instanciado.")

    def _log_ui(self, message: str, level: str = "info", progress: Optional[int] = None):
        if self.app_instance:
            if hasattr(self.app_instance, 'log_message'):
                self.app_instance.log_message(message, level)
            if progress is not None and hasattr(self.app_instance, 'update_progress_bar_info'):
                # Ajustar chamada conforme a assinatura real de update_progress_bar_info
                if hasattr(self.app_instance, 'update_progress_bar_info_full'): # Se existir uma função mais completa
                     self.app_instance.update_progress_bar_info_full(progress_value=progress, text_before=message, text_after="")
                else: # Fallback para uma chamada mais simples
                    self.app_instance.update_progress_bar_info(progress_value=progress) 
        else:
            log_func = getattr(self.logger, level, self.logger.info)
            log_func(message)

    def _update_progress(self, current_step: int, total_steps: int, message_suffix: str = ""):
        if self.app_instance and hasattr(self.app_instance, 'update_progress_bar_info'):
            progress_percentage = int((current_step / total_steps) * 100)
            msg = f"Progresso: {current_step}/{total_steps} {message_suffix}"
            
            if hasattr(self.app_instance, 'update_progress_bar_info_full'):
                 self.app_instance.update_progress_bar_info_full(
                    progress_value=progress_percentage,
                    text_before=msg,
                    text_after=f"Etapa {current_step} de {total_steps}" 
                )
            else:
                 self.app_instance.update_progress_bar_info(progress_value=progress_percentage, text_before_progress=msg)
        self.logger.info(f"Progresso: {current_step}/{total_steps} {message_suffix}")


    def _atualizar_contexto_geradores(self, evento_id: str, cargo_id: str, prova_montada_id: Optional[str] = None,
                                     format_options_override: Optional[dict] = None,
                                     template_prova_path_override: Optional[str] = None) -> bool:
        self.logger.debug(f"Atualizando contexto para Evento ID: {evento_id}, Cargo ID: {cargo_id}, Prova Montada ID: {prova_montada_id}")
        
        try:
            self.evento_atual = self.event_manager.get_event_by_id(evento_id)
            if not self.evento_atual: 
                raise ValueError(f"Evento ID {evento_id} não encontrado.")

            cargos_do_evento = getattr(self.evento_atual, 'cargos', [])
            self.cargo_atual = next((c for c in cargos_do_evento if getattr(c, 'id_cargo', None) == cargo_id), None)
            if not self.cargo_atual: 
                raise ValueError(f"Cargo ID {cargo_id} não encontrado no evento.")
            
            # --- INÍCIO DA CORREÇÃO ---
            # 1. Busca no atributo correto: 'provas_montadas_por_cargo' (um dicionário)
            provas_por_cargo_map = getattr(self.evento_atual, 'provas_montadas_por_cargo', {})

            if prova_montada_id:
                # Se um ID específico foi passado, busca pelo ID nos valores do dicionário
                self.prova_montada_atual = next((pm for pm in provas_por_cargo_map.values() if getattr(pm, 'id_prova_montada', None) == prova_montada_id), None)
            else:
                # Senão, busca a prova diretamente pela chave (ID do cargo)
                self.prova_montada_atual = provas_por_cargo_map.get(cargo_id)
            # --- FIM DA CORREÇÃO ---

            if not self.prova_montada_atual: 
                # A mensagem de erro agora usa o ID da prova montada, se disponível, para ser mais precisa
                id_log = prova_montada_id if prova_montada_id else f'para cargo {cargo_id}'
                self.logger.error(f"ERRO: Prova Montada (ID: {id_log}) não encontrada.")
                raise ValueError("Prova Montada não encontrada.")

            current_format_options = format_options_override if format_options_override else self.config.get("format_options_default", {})

            # --- INÍCIO DA CORREÇÃO ---
            # Prioriza o override explícito, mas busca o caminho do template dentro do dicionário de opções.
            final_template_path = template_prova_path_override or current_format_options.get("template_path") or os.path.join(self.templates_base_dir, "modelo_padrao.docx")
            # --- FIM DA CORREÇÃO ---
            
            # O nome da chave da configuração de mídia
            media_dir_key = getattr(self.core_elements, 'CONFIG_KEY_MEDIA_DIR', 'media_files_base_dir')
            image_storage_for_proof_gen = self.config.get(media_dir_key, "media_files")

            self.docx_proof_generator = DocxProofGenerator(
                prova_montada_obj=self.prova_montada_atual, 
                evento_obj=self.evento_atual, 
                cargo_obj=self.cargo_atual,
                format_options=current_format_options, 
                template_prova_path=final_template_path, 
                logger=self.logger.getChild("DocxProofGenCtx"), 
                core_elements_module=self.core_elements,
                image_storage_base_dir=image_storage_for_proof_gen,
                app_instance=self.app_instance,
                # <--- ADICIONE ESTE NOVO PARÂMETRO
            )
            self.logger.debug("Contexto dos geradores atualizado com sucesso para DocumentGenerator.")
            return True
        except ValueError as ve:
            self._log_ui(str(ve), "error")
            return False
        except Exception as e_ctx:
            self.logger.error(f"Erro inesperado ao atualizar contexto: {e_ctx}", exc_info=True)
            self._log_ui(f"Erro ao carregar dados: {e_ctx}", "error")
            return False
    

    def gerar_prova_docx(
        self,
        prova_montada: 'ProvaMontadaType',
        nome_cargo: str,
        variacao_num: int,
        output_folder: str,
        format_options: dict,
        textos_map: dict
    ) -> Optional[str]:
        """
        Gera um único arquivo DOCX para uma variação de prova usando o motor centralizado
        (generate_docx_and_answer_key_data), com todos os recursos avançados.
        """
        import traceback

        print("\n=== [DEBUG] INICIANDO gerar_prova_docx ===")
        print("prova_montada keys:", list(prova_montada.keys()) if isinstance(prova_montada, dict) else type(prova_montada))
        print("nome_cargo:", nome_cargo)
        print("variacao_num:", variacao_num)
        print("output_folder:", output_folder)
        print("format_options:", format_options)
        print("template_path:", format_options.get("template_path"))
        print("image_storage_base_dir:", self.image_storage_base_dir)
        print("textos_map:", f"{len(textos_map) if textos_map else 0} textos")
        print("prova_montada['evento']:", prova_montada.get('evento'))
        print("prova_montada['cargo']:", prova_montada.get('cargo'))
        print("== FIM DOS PRINTS DE CONTEXTO ==\n")

        evento_obj = prova_montada.get("evento")
        cargo_obj = prova_montada.get("cargo")
        assert evento_obj is not None, "Evento não presente em prova_montada!"
        assert cargo_obj is not None, "Cargo não presente em prova_montada!"

        # --- PATCH LOGO ---
        company = None

        print("cargo_obj:", cargo_obj)
        if isinstance(cargo_obj, dict):
            # Verifica se o campo 'company' existe no dict
            company = cargo_obj.get("company")
            print("cargo_obj.get('company'):", company)
            if company and isinstance(company, dict):
                print("cargo_obj['company'].get('company_logo_path'):", company.get("company_logo_path"))
        else:
            company = getattr(cargo_obj, "company", None)
            print("getattr(cargo_obj, 'company', None):", company)
            if company:
                print("getattr(company, 'company_logo_path', None):", getattr(company, "company_logo_path", None))

        # Se não estiver dentro do cargo, tente buscar de outra fonte aqui, se necessário

        logo_path_db = None
        if company:
            if isinstance(company, dict):
                logo_path_db = company.get("company_logo_path", None)
            else:
                logo_path_db = getattr(company, "company_logo_path", None)

        print("logo_path_db:", logo_path_db)

        logo_path = resolve_logo_path(logo_path_db)
        print("LOGO_PATH_ABS:", logo_path, "EXISTS:", os.path.exists(logo_path) if logo_path else False)
        # --- FIM PATCH LOGO ---

        nome_base = sanitize_filename(
            f"PROVA_{evento_obj['nome_evento']}_{nome_cargo}_TIPO_{variacao_num}"
        )

        try:
            docx_proof_gen = DocxProofGenerator(
                prova_montada_obj=prova_montada,
                evento_obj=evento_obj,
                cargo_obj=cargo_obj,
                format_options=format_options,
                image_storage_base_dir="static",
                template_prova_path=format_options.get("template_path"),
                logger=self.logger,
                core_elements_module=self.core_elements,
                app_instance=self.app_instance,
                logo_path_override=logo_path,  # <-- ESSENCIAL!
            )

            print("[DEBUG] Instanciado DocxProofGenerator.")

            output_path, answer_key_data, ordered_questions = docx_proof_gen.generate_docx_and_answer_key_data(
                output_dir=output_folder,
                base_filename=nome_base,
                variacao_num=variacao_num,
                num_linhas_rascunho=format_options.get("num_linhas_rascunho", 30),
                # textos_ja_impressos pode ser passado se necessário
            )

            print(f"[DEBUG] Retorno do generate_docx_and_answer_key_data: output_path={output_path}")
            if not output_path:
                print("[ERRO] Não foi possível gerar o DOCX.")
                return None

            print(f"[SUCESSO] DOCX GERADO EM: {output_path}")
            return output_path

        except Exception as e:
            print("ERRO AO EXPORTAR PROVA:", e)
            traceback.print_exc()
            return None
    
    def exporta_dados_capas_completos(
        self,
        candidatos: list,
        output_json: str,
        frase_para_capa: str,
        sufixo_tipo: str,
        extra_fields: dict = None
    ):
        """
        Exporta todos os dados relevantes para cada candidato/capa para um arquivo JSON,
        incluindo dados do candidato, cargo, evento, prova e campos customizados.
        """
        lista = []
        for candidato in candidatos:
            dados = {}

            # --- Dados do candidato ---
            for k, v in candidato.items():
                dados[k] = v

            # --- Dados do cargo ---
            if self.cargo_atual:
                dados["CodigoCargo"] = getattr(self.cargo_atual, "codigo_cargo", "")
                dados["NomeCargo"] = getattr(self.cargo_atual, "nome_cargo", "")
                dados["CargoTipo"] = f'{getattr(self.cargo_atual, "nome_cargo", "")} ({sufixo_tipo.replace("_", " ")})'
                dados["CargoTipoCompleto"] = f'{getattr(self.cargo_atual, "codigo_cargo", "")} - {getattr(self.cargo_atual, "nome_cargo", "")} - {sufixo_tipo.replace("_Tipo_", "")}'

            # --- Dados do evento ---
            if self.evento_atual:
                dados["NomeEvento"] = getattr(self.evento_atual, "nome_evento", "")
                dados["DataEvento"] = getattr(self.evento_atual, "data_evento", "")
                dados["LocalEvento"] = getattr(self.evento_atual, "local_evento", "")

            # --- Dados da prova montada ---
            if self.prova_montada_atual:
                dados["NomeProva"] = getattr(self.prova_montada_atual, "nome_prova_montada", "")
                dados["IdentificadorProva"] = getattr(self.prova_montada_atual, "identificador_prova", "")
                dados["TipoProva"] = sufixo_tipo.replace("_Tipo_", "")

            # --- Campos customizados ---
            dados["Frase"] = frase_para_capa
            dados["DataProva"] = datetime.now().strftime("%d/%m/%Y")

            # --- Extras opcionais ---
            if extra_fields:
                dados.update(extra_fields)

            lista.append(dados)

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Arquivo JSON de dados da capa exportado: {output_json}")
        return output_json


    def _criar_pagina_capa_pdf(self, output_path: str, textos_capa: List[Dict[str, Any]]) -> bool:
        """
        Cria uma página de capa em PDF dinamicamente com base nos textos fornecidos.
        textos_capa: Lista de dicionários, cada um com 'texto', 'pos_x_cm', 'pos_y_cm_from_top', 'fonte', 'tamanho', 'cor_hex', 'align'.
        As posições são em cm.
        """
        global REPORTLAB_AVAILABLE # Acessa a flag global
        if not REPORTLAB_AVAILABLE: # Usa a flag global
            self.logger.warning("ReportLab não está disponível. Geração de capa PDF dinâmica abortada.")
            return False

        try:
            # Importar ParagraphStyle e HexColor aqui para garantir que estão no escopo se ReportLab estiver disponível
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.colors import HexColor
            from reportlab.lib.units import cm as rl_cm # Unidade cm do reportlab

            canvas_rl = rl_canvas_module.Canvas(output_path, pagesize=A4)
            styles = getSampleStyleSheet() # Obter estilos padrão
            
            if self.evento_atual:
                canvas_rl.setTitle(f"Capa - {self.evento_atual.nome_evento}")
            
            # Adicionar imagem de fundo/timbrado (Exemplo)
            # template_imagem_capa_key = getattr(self.core_elements.K, "CONFIG_KEY_TEMPLATE_IMAGEM_CAPA_PDF", "template_imagem_capa_pdf")
            # template_imagem_capa = self.config.get(template_imagem_capa_key)
            # if template_imagem_capa and os.path.exists(resource_path(template_imagem_capa)):
            #     try:
            #         canvas_rl.drawImage(resource_path(template_imagem_capa), 0, 0, width=A4[0], height=A4[1], preserveAspectRatio=True, anchor='c', mask='auto')
            #     except Exception as e_drawimg:
            #         self.logger.error(f"Erro ao desenhar imagem de capa PDF: {e_drawimg}")


            for item_idx, item in enumerate(textos_capa):
                texto = item.get('texto', '')
                pos_x_cm = item.get('pos_x_cm', 1) 
                pos_y_cm_from_top = item.get('pos_y_cm_from_top', 1) 
                fonte = item.get('fonte', 'Helvetica')
                tamanho = item.get('tamanho', 12)
                cor_hex = item.get('cor_hex', '#000000')
                align_text = item.get('align', 'LEFT').upper() 
                
                # Converter posições para pontos do ReportLab (Y é de baixo para cima)
                x_coord = pos_x_cm * rl_cm
                y_coord = A4[1] - (pos_y_cm_from_top * rl_cm) # Ajusta Y de cima para baixo e converte para pontos

                style = ParagraphStyle(
                    f'CapaTextStyle_{item_idx}', # Nome único para o estilo
                    parent=styles['Normal'],
                    fontName=fonte,
                    fontSize=tamanho,
                    textColor=HexColor(cor_hex),
                    leading=tamanho * 1.2, 
                )
                if align_text == 'CENTER': style.alignment = TA_CENTER
                elif align_text == 'RIGHT': style.alignment = TA_RIGHT
                elif align_text == 'JUSTIFY': style.alignment = TA_JUSTIFY
                else: style.alignment = TA_LEFT # Default

                p = Paragraph(texto, style)
                
                # Define a largura máxima do parágrafo (ex: largura da página menos margens)
                # e altura máxima (ex: altura restante na página)
                available_width = A4[0] - x_coord - (1*rl_cm) # Exemplo: margem direita de 1cm
                available_height = y_coord # Altura disponível de y_coord até a base da página

                p_width, p_height = p.wrapOn(canvas_rl, available_width, available_height) 
                
                # Desenha o parágrafo. y_coord é a base da primeira linha.
                # Para alinhar corretamente, o y_coord para drawOn deve ser o canto inferior esquerdo do parágrafo.
                canvas_rl.drawText(p) # drawOn(canvas_rl, x_coord, y_coord - p_height)


            canvas_rl.showPage()
            canvas_rl.save()
            self.logger.info(f"Página de capa PDF criada dinamicamente em: {output_path}")
            return True
        except ImportError: # Caso ParagraphStyle ou HexColor não sejam importados por ReportLab não estar completo
            self.logger.error("Erro ao importar componentes do ReportLab para capa PDF. Verifique a instalação.", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Erro ao criar página de capa PDF dinâmica: {e}", exc_info=True)
            return False


    def gerar_pacote_provas_completo(self, 
                                    evento_id_str: str,
                                    provas_montadas_selecionadas_map: Dict[str, ProvaMontadaType],
                                    candidatos_data_por_cargo: Dict[str, List[Dict[str,str]]],
                                    output_dir_base_lote_param: str,
                                    format_options_gerais: dict,
                                    gerar_pdf_final_global: bool,
                                    manter_docx_corpo_global: bool,
                                    gerar_zip_final_global: bool,
                                    gerar_gabarito_simplificado_global: bool,
                                    template_prova_path_override: Optional[str] = None,
                                    template_capa_pacote_override: Optional[str] = None,
                                    app_progress_callback: Optional[Callable] = None,
                                    num_linhas_rascunho: int = 30,
                                    **kwargs
                                    ) -> Tuple[Optional[str], List[str], Dict]:
        """
        Gera um pacote completo de provas para um evento, processando múltiplos cargos e suas provas montadas.
        Retorna: caminho do ZIP/diretório final, lista de ARQUIVOS de prova gerados, DICIONÁRIO com dados de gabaritos.
        """

         # --- CORREÇÃO DEFINITIVA PARA COMPORTAMENTO INCONSISTENTE ---
        # Este bloco limpa TODAS as configurações locais problemáticas de cada prova,
        # forçando o sistema a usar as configurações globais da tela para TODOS os cargos.
        # =================================================================================
        self.logger.info("Forçando o uso das configurações globais para todos os cargos...")
        for id_cargo, prova_obj in provas_montadas_selecionadas_map.items():
            if hasattr(prova_obj, 'metadados_prova') and "definicao_geracao" in prova_obj.metadados_prova:
                
                # Lista de configurações que DEVEM obedecer à tela final, e não a valores antigos
                chaves_a_ignorar = ["manter_arquivos_docx_individuais", "exportar_para_pdf"] 
                
                for chave in chaves_a_ignorar:
                    if chave in prova_obj.metadados_prova["definicao_geracao"]:
                        # Apaga a chave do dicionário de metadados
                        del prova_obj.metadados_prova["definicao_geracao"][chave]
                        self.logger.debug(f"Removida config local '{chave}' do Cargo ID {id_cargo} para usar a global.")
        # --- FIM DA CORREÇÃO DEFINITIVA ---


        import subprocess
        import unicodedata
        import os
        import shutil
        import json
        from datetime import datetime

        self.app_progress_callback = app_progress_callback 

        self._log_ui(f"Iniciando geração de pacote completo para Evento ID: {evento_id_str}", "info", progress=0)
        os.makedirs(output_dir_base_lote_param, exist_ok=True)
        self.output_dir_lote = output_dir_base_lote_param

        todos_arquivos_finais_gerados_no_lote: List[str] = []
        gabaritos_dados_agregados_lote: Dict[str, Any] = {}
        erros_ocorridos: List[str] = []

        total_steps = 0
        for prova in provas_montadas_selecionadas_map.values():
            num_variacoes = prova.metadados_prova.get("definicao_geracao", {}).get("num_variacoes", 1)
            total_steps += num_variacoes * 2 
            total_steps += len(provas_montadas_selecionadas_map) 
        if gerar_zip_final_global:
            total_steps += 1 

        current_step = 0
        
        total_cargos_a_processar = len(provas_montadas_selecionadas_map)
        cargo_processado_count = 0

        def resolve_capa_template_path(cover_pdf_paths):
            # Se vier como string de lista, parse
            if isinstance(cover_pdf_paths, str):
                try:
                    paths = json.loads(cover_pdf_paths)
                    if isinstance(paths, str):
                        paths = [paths]
                except Exception:
                    paths = [cover_pdf_paths]
            elif isinstance(cover_pdf_paths, list):
                paths = cover_pdf_paths
            else:
                paths = []

            if paths:
                template_path = os.path.normpath(paths[0])
                if not os.path.isabs(template_path):
                    template_path = os.path.abspath(template_path)
                return template_path
            return None

        def preencher_capas_java(template_pdf, dados_json, saida_dir):
            os.makedirs(saida_dir, exist_ok=True)
            comando = [
                "java",
                "-cp",
                "pdfbox-app-3.0.5.jar;json.jar;.",
                "PreencheCapaPDF_JSON_PDFBox",
                template_pdf,
                dados_json,
                saida_dir
            ]
            try:
                resultado = subprocess.run(comando, capture_output=True, text=True, check=True)
                print(resultado.stdout)
                return True
            except subprocess.CalledProcessError as e:
                print("Erro ao rodar Java:", e.stderr)
                return False
        
        print("\n\nDEBUG: Cargos recebidos para processamento:", list(provas_montadas_selecionadas_map.keys()))


        for cargo_id_str, prova_montada_obj_selecionada in provas_montadas_selecionadas_map.items():
        
                      
            cargo_processado_count += 1
            self.logger.info(f"Processando Cargo ID: {cargo_id_str} ({cargo_processado_count}/{total_cargos_a_processar})")
            self._update_progress(cargo_processado_count, total_cargos_a_processar, f"Processando Cargo ID: {cargo_id_str}")

            prova_montada_id_especifica = getattr(prova_montada_obj_selecionada, 'id_prova_montada', None)
            if not self._atualizar_contexto_geradores(
                evento_id_str, 
                cargo_id_str, 
                prova_montada_id=prova_montada_id_especifica, 
                format_options_override=format_options_gerais,
                template_prova_path_override=template_prova_path_override
            ):
                msg_erro_ctx = f"Falha ao atualizar contexto para Cargo ID {cargo_id_str}. Pulando este cargo."
                self.logger.error(msg_erro_ctx)
                self._log_ui(msg_erro_ctx, "error")
                erros_ocorridos.append(msg_erro_ctx)
                continue 

            if not self.docx_proof_generator or not self.evento_atual or not self.cargo_atual or not self.prova_montada_atual:
                msg_erro_comp = f"Componentes de geração não inicializados corretamente para Cargo ID {cargo_id_str} após atualização de contexto. Pulando."
                self.logger.critical(msg_erro_comp)
                self._log_ui(msg_erro_comp, "critical")
                erros_ocorridos.append(msg_erro_comp)
                continue

            print(f"\nDEBUG: >>> INICIANDO processamento do cargo: {self.cargo_atual.nome_cargo} <<<\n")
            print(f"DIAGNÓSTICO PARA O CARGO: {self.cargo_atual.nome_cargo} (ID: {cargo_id_str})")
            
            # Usamos self.prova_montada_atual para acessar os metadados
            if hasattr(self.prova_montada_atual, 'metadados_prova') and self.prova_montada_atual.metadados_prova:
                import json
                print("DADOS SALVOS PARA ESTE CARGO (METADADOS):")
                print(json.dumps(self.prova_montada_atual.metadados_prova, indent=2, ensure_ascii=False))
            else:
                print("Este cargo não possui metadados salvos.")
            print("-" * 60)

            nome_cargo_sanitizado = sanitize_filename(self.cargo_atual.nome_cargo if self.cargo_atual else f"cargo_{cargo_id_str}")
            dir_saida_cargo = self.output_dir_lote

            definicoes_geracao = prova_montada_obj_selecionada.metadados_prova.get("definicao_geracao", {})
            gerar_pdf_final_local = definicoes_geracao.get('exportar_para_pdf', gerar_pdf_final_global)
            manter_docx_corpo_local = definicoes_geracao.get('manter_arquivos_docx_individuais', manter_docx_corpo_global)
            num_variacoes_prova = definicoes_geracao.get('num_variacoes', 1)
            
            if not hasattr(prova_montada_obj_selecionada, 'configuracoes'):
                prova_montada_obj_selecionada.configuracoes = self.core_elements.ConfiguracoesProvaType()

            prova_montada_obj_selecionada.configuracoes.embaralhar_questoes = definicoes_geracao.get('embaralhar_questoes', False)
            prova_montada_obj_selecionada.configuracoes.embaralhar_alternativas = definicoes_geracao.get('embaralhar_alternativas', False)

            lista_corpos_docx_gerados_para_cargo: List[str] = []
            # ### INÍCIO DA CORREÇÃO 2, PARTE A: Inicializar a lista de PDFs ###
            lista_corpos_pdf_gerados_para_cargo: List[str] = []
            # ### FIM DA CORREÇÃO 2, PARTE A ###
            gabaritos_por_variacao: Dict[str, List[Dict[str, Any]]] = {}
            questoes_ordenadas_para_cargo: List[str] = [] 

            cover_pdf_paths = getattr(self.cargo_atual, 'cover_pdf_paths', None)
            template_folha_rosto_pdf = resolve_capa_template_path(cover_pdf_paths)
            identificador_base = getattr(self.prova_montada_atual, "identificador_prova", None) or "PADRAO"

            for variacao_num in range(1, num_variacoes_prova + 1):
                codigo_cargo = self.cargo_atual.codigo_cargo if self.cargo_atual else "S_COD"
                nome_cargo_original = self.cargo_atual.nome_cargo if self.cargo_atual else "S_NOME"
                nome_cargo_sem_acento = "".join(c for c in unicodedata.normalize('NFD', nome_cargo_original) if unicodedata.category(c) != 'Mn')
                sufixo_tipo = f"_Tipo_{chr(ord('A') + variacao_num - 1)}" if num_variacoes_prova > 1 else ""
                nome_base_final = sanitize_filename(f"{codigo_cargo}_{nome_cargo_sem_acento}{sufixo_tipo}")
                base_filename_docx_variacao = nome_base_final

                current_step += 1
                self._update_progress(current_step, total_steps, f"Gerando DOCX: {nome_base_final}")
                self.docx_proof_generator.prova_montada.identificador_prova = sufixo_tipo.replace("_", " ") if sufixo_tipo else "Prova Padrão"

                self._log_ui(f"Gerando DOCX variação '{nome_base_final}'...", "debug")
                import copy
                docx_proof_gen = DocxProofGenerator(
                    prova_montada_obj=copy.deepcopy(self.prova_montada_atual),
                    evento_obj=self.evento_atual,
                    cargo_obj=self.cargo_atual,
                    format_options=format_options_gerais,
                    template_prova_path=self.docx_proof_generator.template_prova_path,
                    logger=self.docx_proof_generator.logger,
                    core_elements_module=self.docx_proof_generator.core_elements,
                    image_storage_base_dir=self.docx_proof_generator.image_storage_base_dir,
                    app_instance=self.docx_proof_generator.app_instance,
                )

                docx_path_variacao, gabarito_data_variacao, q_ids_ordenados_variacao = docx_proof_gen.generate_docx_and_answer_key_data(
                    output_dir=dir_saida_cargo,
                    base_filename=base_filename_docx_variacao,
                    variacao_num=variacao_num,
                    num_linhas_rascunho=num_linhas_rascunho
                )

                if docx_path_variacao:
                    lista_corpos_docx_gerados_para_cargo.append(docx_path_variacao)
                    nome_variacao = f"Tipo {chr(ord('A') + variacao_num - 1)}"
                    gabaritos_por_variacao[nome_variacao] = gabarito_data_variacao
                    self._log_ui(f"DOCX '{os.path.basename(docx_path_variacao)}' gerado.", "info")
                else:
                    msg_erro_docx_var = f"Falha ao gerar DOCX variação '{nome_base_final}'. Pulando esta variação."
                    self.logger.error(msg_erro_docx_var)
                    self._log_ui(msg_erro_docx_var, "error")
                    erros_ocorridos.append(msg_erro_docx_var)
                    continue
            
            if gabaritos_por_variacao:
                gabaritos_dados_agregados_lote[cargo_id_str] = {
                    "nome_cargo": self.cargo_atual.nome_cargo,
                    "dados": gabaritos_por_variacao
                }
            
            candidatos_do_cargo_atual = candidatos_data_por_cargo.get(cargo_id_str, [])
            template_folha_rosto_pdf = getattr(self.cargo_atual, 'cover_pdf_paths', None)

            if gerar_pdf_final_local:
                for idx_variacao, docx_corpo_path in enumerate(lista_corpos_docx_gerados_para_cargo):
                    sufixo_tipo = f"_Tipo_{chr(ord('A') + idx_variacao)}" if num_variacoes_prova > 1 else ""
                    nome_base_final = sanitize_filename(f"{self.cargo_atual.codigo_cargo}_{self.cargo_atual.nome_cargo}{sufixo_tipo}")

                    self._log_ui(f"Convertendo DOCX '{os.path.basename(docx_corpo_path)}' para PDF...", "debug")
                    pdf_corpo_path = self.pdf_converter.convert_to_pdf(docx_corpo_path, dir_saida_cargo)
                    
                    # ### INÍCIO DA CORREÇÃO 2, PARTE B: Guardar o caminho do PDF na lista ###
                    if pdf_corpo_path:
                        lista_corpos_pdf_gerados_para_cargo.append(pdf_corpo_path)
                    else:
                        msg_erro_pdf_conv = f"Falha ao converter DOCX '{os.path.basename(docx_corpo_path)}' para PDF. Pulando PDFs para esta variação."
                        self.logger.error(msg_erro_pdf_conv)
                        self._log_ui(msg_erro_pdf_conv, "error")
                        erros_ocorridos.append(msg_erro_pdf_conv)
                        continue 
                    # ### FIM DA CORREÇÃO 2, PARTE B ###

                    path_pdf_final_variacao = "" 

                    tipo_prova_para_frase = "PADRAO"
                    if "_Tipo_" in nome_base_final:
                        try:
                            tipo_letra = nome_base_final.split('_Tipo_')[-1]
                            if len(tipo_letra) == 1 and tipo_letra.isalpha():
                                tipo_prova_para_frase = f"Tipo {tipo_letra}"
                            else:
                                tipo_prova_para_frase = "PADRAO"
                        except IndexError:
                            tipo_prova_para_frase = "PADRAO"
                    elif num_variacoes_prova == 1:
                        tipo_prova_para_frase = "PADRAO"

                    frase_para_capa = self.prova_montada_atual.metadados_prova.get('frases_por_tipo_prova', {}).get(tipo_prova_para_frase, "")
                    
                    if not frase_para_capa:
                        self.logger.warning(f"Não foi possível obter uma frase pré-selecionada para a categoria '{tipo_prova_para_frase}'. Capa pode ser gerada sem frase.")

                    dir_capas_java = os.path.join(dir_saida_cargo, "CapasPreenchidas")
                    os.makedirs(dir_capas_java, exist_ok=True)

                    if candidatos_do_cargo_atual and template_folha_rosto_pdf and os.path.exists(resource_path(template_folha_rosto_pdf)):
                        json_path = os.path.join(dir_capas_java, f"dados_capas_{nome_base_final}.json")
                        self.exporta_dados_capas_completos(candidatos_do_cargo_atual, json_path, frase_para_capa, sufixo_tipo)
                        preencher_capas_java(resource_path(template_folha_rosto_pdf), json_path, dir_capas_java)

                        self._log_ui(f"Mesclando corpo da prova com capas geradas via Java para {len(candidatos_do_cargo_atual)} candidatos ({nome_base_final})...", "info")
                        for candidato_data in candidatos_do_cargo_atual:
                            nome_candidato = candidato_data.get(COLUNA_NOME_COMPLETO_CSV, "NOME_NAO_ENCONTRADO")
                            id_candidato = candidato_data.get(COLUNA_ID_CANDIDATO_CSV, "ID_NAO_ENCONTRADO")
                            nome_pdf_final_candidato = sanitize_filename(f"{nome_base_final}_{id_candidato}_{nome_candidato}.pdf")
                            path_pdf_final_candidato = os.path.join(dir_saida_cargo, nome_pdf_final_candidato)
                            path_capa_java = os.path.join(dir_capas_java, f"{id_candidato}_capa.pdf")
                            if not os.path.exists(path_capa_java):
                                erros_ocorridos.append(f"Capa não gerada para {nome_candidato} ({nome_base_final}).")
                                continue
                            if self.archive_manager.merge_pdfs([path_capa_java, pdf_corpo_path], path_pdf_final_candidato):
                                todos_arquivos_finais_gerados_no_lote.append(path_pdf_final_candidato)
                            else:
                                erros_ocorridos.append(f"Falha ao mesclar folha de rosto e corpo PDF para {nome_candidato} ({nome_base_final}).")
                    else:
                        codigo = getattr(self.cargo_atual, "codigo_cargo", "")
                        cargo = getattr(self.cargo_atual, "nome_cargo", "")
                        tipo = sufixo_tipo.replace('_Tipo_', '')
                        campo_codigo_cargo = f"{codigo} - {cargo}"
                        campo_codigo_cargo_tipo = f"{codigo} - {cargo} - {tipo}"
                        campo_tipo_somente_letra = tipo
                        campo_frase = frase_para_capa

                        dados_para_preencher = {
                            "Inscricao": nome_base_final,
                            "CodigoCargo": campo_codigo_cargo,
                            "CodigoCargoTipo": campo_codigo_cargo_tipo,
                            "Tipo": campo_tipo_somente_letra,
                            PDF_FIELD_CARGO_TIPO: f"{campo_codigo_cargo} - Tipo {tipo}",
                            PDF_FIELD_FRASE: campo_frase,
                            "Data": datetime.now().strftime("%d/%m/%Y"),
                            "Evento": self.evento_atual.nome_evento,
                        }
                        json_capa_path = os.path.join(dir_capas_java, f"dados_capa_{nome_base_final}.json")
                        with open(json_capa_path, "w", encoding="utf-8") as f:
                            json.dump([dados_para_preencher], f, ensure_ascii=False, indent=2)

                        preencher_capas_java(resource_path(template_folha_rosto_pdf), json_capa_path, dir_capas_java)

                        capa_java_gerada = os.path.join(dir_capas_java, f"{nome_base_final}_capa.pdf")
                        if not os.path.exists(capa_java_gerada):
                            erros_ocorridos.append(f"Capa genérica não gerada para {nome_base_final}.")
                        else:
                            nome_pdf_final = f"{nome_base_final}.pdf"
                            path_pdf_final = os.path.join(dir_saida_cargo, nome_pdf_final)
                            if self.archive_manager.merge_pdfs(pdf_paths=[pdf_corpo_path], output_path=path_pdf_final, cover_page_path=capa_java_gerada):
                                todos_arquivos_finais_gerados_no_lote.append(path_pdf_final)
                            else:
                                erros_ocorridos.append(f"Falha ao mesclar PDF para {nome_base_final}.")
            
            # ### INÍCIO DA CORREÇÃO 2, PARTE C: Deletar os PDFs intermediários ###
            if not manter_docx_corpo_local:
                self.logger.info(f"Limpando arquivos intermediários para o cargo {cargo_id_str}...")
                # Deleta os PDFs intermediários - só remove PDFs que NÃO são finais!
                for pdf_path_a_remover in lista_corpos_pdf_gerados_para_cargo:
                    if pdf_path_a_remover not in todos_arquivos_finais_gerados_no_lote:
                        if os.path.exists(pdf_path_a_remover):
                            try:
                                os.remove(pdf_path_a_remover)
                                self.logger.debug(f"PDF intermediário '{os.path.basename(pdf_path_a_remover)}' removido.")
                            except OSError as e_rem_pdf:
                                self.logger.warning(f"Não foi possível remover PDF intermediário '{os.path.basename(pdf_path_a_remover)}': {e_rem_pdf}")

                # Deleta os DOCX intermediários (esta parte já existia)
                for docx_path_a_remover in lista_corpos_docx_gerados_para_cargo:
                    if os.path.exists(docx_path_a_remover):
                        try:
                            os.remove(docx_path_a_remover)
                            self.logger.debug(f"DOCX corpo '{os.path.basename(docx_path_a_remover)}' removido.")
                        except OSError as e_rem_docx:
                            self.logger.warning(f"Não foi possível remover DOCX corpo '{os.path.basename(docx_path_a_remover)}': {e_rem_docx}")

                # Deleta a pasta temporária de capas
                dir_capas_java = os.path.join(dir_saida_cargo, "CapasPreenchidas")
                if os.path.exists(dir_capas_java):
                    try:
                        shutil.rmtree(dir_capas_java)
                        self.logger.debug(f"Pasta de capas removida: {dir_capas_java}")
                    except Exception as e_rem_capas:
                        self.logger.warning(f"Não foi possível remover pasta de capas '{dir_capas_java}': {e_rem_capas}")
            else: 
                todos_arquivos_finais_gerados_no_lote.extend(lista_corpos_docx_gerados_para_cargo)
                print(f"\nDEBUG: === FINALIZANDO processamento do cargo: {self.cargo_atual.nome_cargo} ({cargo_id_str}) ===\n")
                print(f"\nDEBUG: >>> CONCLUÍDO processamento do cargo: {self.cargo_atual.nome_cargo} <<<\n")

        self._log_ui(f"Processamento de todos os cargos concluído. Erros: {len(erros_ocorridos)}", "info", progress=90)
        if erros_ocorridos:
            self.logger.warning(f"Resumo dos erros no lote: \n" + "\n".join(erros_ocorridos))
            self._log_ui("Alguns erros ocorreram durante a geração do lote. Verifique os logs.", "warning")
        
        if template_capa_pacote_override and os.path.exists(resource_path(template_capa_pacote_override)):
            self._log_ui("Adicionando capa geral ao pacote...", "info")
            nome_evento_curto = getattr(self.evento_atual, 'nome_curto_evento', 'EVENTO')
            nome_arquivo_capa = f"00_CAPA_DO_PACOTE_{nome_evento_curto}.pdf"
            caminho_final_capa_pacote = os.path.join(self.output_dir_lote, nome_arquivo_capa)
            
            try:
                shutil.copy(resource_path(template_capa_pacote_override), caminho_final_capa_pacote)
                todos_arquivos_finais_gerados_no_lote.insert(0, caminho_final_capa_pacote)
                self.logger.info(f"Capa do pacote adicionada com sucesso em: {caminho_final_capa_pacote}")
            except Exception as e_copy_capa:
                self.logger.error(f"Erro ao copiar a capa do pacote: {e_copy_capa}")
                self._log_ui("Erro ao adicionar a capa geral do pacote.", "error")

        caminho_final_pacote = self.output_dir_lote
        if gerar_zip_final_global and todos_arquivos_finais_gerados_no_lote:
            nome_zip_lote = f"{os.path.basename(self.output_dir_lote)}.zip"
            path_zip_final_lote = os.path.join(os.path.dirname(self.output_dir_lote), nome_zip_lote) 
            
            self._log_ui(f"Criando arquivo ZIP do lote: {nome_zip_lote}...", "info")
            if self.archive_manager.create_zip(todos_arquivos_finais_gerados_no_lote, path_zip_final_lote):
                self._log_ui(f"Pacote ZIP do lote gerado: {path_zip_final_lote}", "info", progress=100)
                caminho_final_pacote = path_zip_final_lote
            else:
                self._log_ui(f"Falha ao criar ZIP do lote. Arquivos permanecem em '{self.output_dir_lote}'.", "error", progress=100)
        elif not todos_arquivos_finais_gerados_no_lote:
            self._log_ui("Nenhum arquivo gerado no lote para adicionar ao ZIP.", "warning", progress=100)

        return caminho_final_pacote, todos_arquivos_finais_gerados_no_lote, gabaritos_dados_agregados_lote
    

    def gerar_gabaritos_balanceados_por_variacao(self, prova_montada, num_linhas_rascunho=30):
        """
        Gera o dicionário de gabaritos balanceados por variação (Tipo A, Tipo B, ...) para uma prova montada específica.
        Retorna: {'Tipo A': [...], 'Tipo B': [...], ...}
        """
        if not prova_montada:
            self.logger.error("Nenhuma prova montada recebida para geração de gabaritos.")
            return {}

        definicao_geracao = getattr(prova_montada, 'metadados_prova', {}).get("definicao_geracao", {})
        num_variacoes_prova = definicao_geracao.get("num_variacoes", 1)

        # Recupere evento_obj e cargo_obj se eles existirem como atributo ou chave no dict
        evento_obj = getattr(prova_montada, 'evento', None)
        if evento_obj is None and isinstance(prova_montada, dict):
            evento_obj = prova_montada.get('evento')

        cargo_obj = getattr(prova_montada, 'cargo', None)
        if cargo_obj is None and isinstance(prova_montada, dict):
            cargo_obj = prova_montada.get('cargo')

        gabaritos_por_variacao = {}
        for variacao_num in range(1, num_variacoes_prova + 1):
            nome_variacao = f"Tipo {chr(ord('A') + variacao_num - 1)}"
            # Instancia um gerador para cada variação
            docx_gen = DocxProofGenerator(
                prova_montada_obj=prova_montada,
                evento_obj=evento_obj,
                cargo_obj=cargo_obj,
                format_options=definicao_geracao,
                image_storage_base_dir=self.image_storage_base_dir,
                logger=self.logger,
                core_elements_module=self.core_elements
            )
            # Gera apenas os dados do gabarito sem salvar arquivos reais
            _, gabarito_data_variacao, _ = docx_gen.generate_docx_and_answer_key_data(
                output_dir=tempfile.gettempdir(),
                base_filename="dummy",
                variacao_num=variacao_num,
                num_linhas_rascunho=num_linhas_rascunho
            )
            gabaritos_por_variacao[nome_variacao] = gabarito_data_variacao

        return gabaritos_por_variacao
    
    def gerar_apenas_gabaritos(self,
                               gabaritos_data: Dict[str, Any],
                               output_dir: str,
                               nome_base_cargo: str,
                               gerar_simplificado: bool):
        """
        Gera apenas os arquivos de gabarito (CSV) a partir dos dados pré-gerados.
        """
        self.logger.info(f"Iniciando geração apenas de gabaritos para: {nome_base_cargo}")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # Gera o gabarito completo
            path_completo = self.answer_key_generator.generate_complete_csv(
                output_dir=output_dir,
                base_filename=f"GABARITO_COMPLETO_{nome_base_cargo}",
                gabaritos_por_variacao=gabaritos_data
            )
            self.logger.info(f"Gabarito completo gerado em: {path_completo}")

            # Gera o gabarito simplificado, se solicitado
            if gerar_simplificado:
                path_simplificado = self.answer_key_generator.generate_simple_row_based_csv(
                    output_dir=output_dir,
                    base_filename=f"GABARITO_SIMPLIFICADO_{nome_base_cargo}",
                    gabaritos_por_variacao=gabaritos_data
                )
                self.logger.info(f"Gabarito simplificado gerado em: {path_simplificado}")
            
            return True, "Gabaritos gerados com sucesso!"
        except Exception as e:
            self.logger.error(f"Erro ao gerar arquivos de gabarito: {e}", exc_info=True)
            return False, str(e)


    def _update_progress(self, current_step: int, total_steps: int, message_suffix: str = ""):
        """
        Método corrigido para ser um método da classe e usar o callback armazenado em 'self'.
        """
        # Verifica se um callback foi armazenado na instância
        if hasattr(self, 'app_progress_callback') and self.app_progress_callback:
            progress_percentage = int((current_step / total_steps) * 100)
            msg = f"Progresso: {current_step}/{total_steps} {message_suffix}"
            
            try:
                # Chama o callback que está em 'self'
                self.app_progress_callback(
                    progress_value=progress_percentage,
                    text_before=msg,
                    text_after=f"Etapa {current_step} de {total_steps}"
                )
            except Exception as e:
                self.logger.error(f"Erro ao chamar o callback de progresso: {e}")

        self.logger.info(f"Progresso: {current_step}/{total_steps} {message_suffix}")