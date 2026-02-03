# Arquivo: core/docx_parser.py

import os
import sys
import uuid
import docx
from docx.document import Document as DocxDocument
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.table import Table as DocxTable, _Cell
from docx.oxml.ns import qn
import re
from typing import List, Dict, Tuple, Optional, Any
import datetime
import logging
import random
import string
import json

current_script_path_parser = os.path.abspath(__file__)
core_directory_parser = os.path.dirname(current_script_path_parser)
project_root_parser = os.path.dirname(core_directory_parser)
if project_root_parser not in sys.path:
    sys.path.insert(0, project_root_parser)

try:
    from .elements import QuestaoType as RealQuestaoType, OpcaoMultiplaEscolha as RealOpcaoMultiplaEscolha
    from .elements import TextoReferenciaType as RealTextoReferenciaType
    from .elements import TipoQuestao # <<<--- ADICIONADO PARA USAR A ENUMERAÇÃO
    
    elements_QuestaoType = RealQuestaoType
    elements_OpcaoMultiplaEscolha = RealOpcaoMultiplaEscolha
    elements_TextoReferenciaType = RealTextoReferenciaType
    elements_TipoQuestao = TipoQuestao # <<<--- ADICIONADO PARA USAR A ENUMERAÇÃO
    print("INFO (DocxParser Legado): Usando modelos REAIS de .elements.")
except ImportError as e_elements:
    print(f"AVISO (DocxParser Legado): Falha ao importar modelos de .elements ({e_elements}). Usando Stubs internos.")
    
    # ... (Stubs como estavam antes, se necessário para fallback) ...
    class OpcaoMultiplaEscolhaStub:
        def __init__(self, letra: str, texto: str, correta: bool = False, texto_opcao_formatado: Optional[str] = None, imagem_path_opcao: Optional[str] = None, **kwargs):
            self.letra = letra
            self.texto = texto
            self.correta = correta
            self.texto_opcao_formatado = texto_opcao_formatado
            self.imagem_path_opcao = imagem_path_opcao
        def to_dict(self): return self.__dict__

    class QuestaoStub:
        def __init__(self, id_questao: str, tipo: str, enunciado: str, disciplina_banco: str, 
                    opcoes: Optional[List[Any]] = None, 
                    resposta_correta: Optional[str] = None, 
                    metadados_questao: Optional[Dict[str, Any]] = None, 
                    nivel_dificuldade: str = "Médio",
                    pontuacao: float = 1.0,
                    id_texto_ref_vinculado: Optional[str] = None,
                    feedback_geral_questao: str = "", 
                    tags: Optional[List[str]] = None, 
                    data_criacao: Optional[datetime.datetime] = None,
                    data_modificacao: Optional[datetime.datetime] = None,
                    enunciado_formatado: Optional[str] = None,   # <<< ADICIONADO
                    **kwargs): 
            self.id_questao = id_questao
            self.tipo = tipo if tipo is not None else "dissertativa"
            self.enunciado = enunciado if enunciado is not None else ""
            self.enunciado_formatado = enunciado_formatado            # <<< ADICIONADO
            self.disciplina_banco = disciplina_banco 
            self.opcoes: List[OpcaoMultiplaEscolhaStub] = [] 
            if opcoes: 
                for i, opt_text_obj in enumerate(opcoes): self.opcoes.append(opt_text_obj) 
            self.resposta_correta = resposta_correta 
            if self.tipo == "multipla_escolha" and self.opcoes and resposta_correta is None: self.resposta_correta = "A" 
            self.metadados_questao = metadados_questao if metadados_questao is not None else {}
            self.nivel_dificuldade = nivel_dificuldade
            self.pontuacao = pontuacao
            self.id_texto_ref_vinculado = id_texto_ref_vinculado
            self.feedback_geral_questao = feedback_geral_questao
            self.tags = tags if tags is not None else [] 
            self.data_criacao = data_criacao if data_criacao else datetime.datetime.now()
            self.data_modificacao = data_modificacao if data_modificacao else datetime.datetime.now()
            self.gabarito_preliminar = kwargs.get('gabarito_preliminar', self.resposta_correta)
            self.gabarito_definitivo = kwargs.get('gabarito_definitivo', self.resposta_correta) 
            self.justificativa_anulacao = kwargs.get('justificativa_anulacao', "") 
        def __str__(self): return f"ID:{self.id_questao} Disc:{self.disciplina_banco} Enun:{self.enunciado[:20]}..." 
        def to_dict(self): return self.__dict__ 
        def obter_questao_formatada(self, embaralhar_opcoes=False): return f"Questão Formatada Stub: {self.enunciado}"

    class TextoReferenciaStub:
        def __init__(self, 
                    id_texto_ref: str, 
                    titulo_texto_ref: str, 
                    conteudo_texto_ref: str, 
                    tipo_conteudo: str = "texto", 
                    conteudo_formatado: Optional[dict] = None,
                    **kwargs):
            self.id_texto_ref = id_texto_ref
            self.titulo_texto_ref = titulo_texto_ref
            self.conteudo_texto_ref = conteudo_texto_ref
            self.tipo_conteudo = tipo_conteudo
            self.conteudo_formatado = conteudo_formatado  # <<< AQUI ESTÁ O CAMPO FALTANDO
            self.id_evento_fk = kwargs.get("id_evento_fk")
            self.caminho_imagem_ref = kwargs.get("caminho_imagem_ref")

        def to_dict(self):
            return self.__dict__

    elements_QuestaoType = QuestaoStub
    elements_OpcaoMultiplaEscolha = OpcaoMultiplaEscolhaStub
    elements_TextoReferenciaType = TextoReferenciaStub
    # Fallback para TipoQuestao se a importação real falhar
    class TipoQuestaoStubEnum: # Simula a enumeração
        MULTIPLA_ESCOLHA = "MULTIPLA_ESCOLHA" # Deve corresponder ao elements.py real
        DISCURSIVA = "DISCURSIVA"       # Deve corresponder ao elements.py real
        CERTO_ERRADO = "CERTO_ERRADO" # <<<--- ADICIONE ESTA LINHA
    elements_TipoQuestao = TipoQuestaoStubEnum


# Suas constantes de marcadores
MAX_ALTERNATIVAS_PARSER = 5 
MARCADOR_TEXTO_REF_INICIO = "###TEXTO_REFERENCIA_INICIO###"
MARCADOR_TEXTO_REF_FIM = "###TEXTO_REFERENCIA_FIM###"
MARCADOR_TEXTO_REF_IMG_INICIO = "###TEXTO_REFERENCIA_IMAGEM_INICIO###"
MARCADOR_TEXTO_REF_IMG_FIM = "###TEXTO_REFERENCIA_IMAGEM_FIM###"
PADRAO_USA_TEXTO_REF = re.compile(r"\[USA_TEXTO_REF:\s*([^\]]+?)\s*\]", re.IGNORECASE) 

# NOVOS Padrões para Metadados da Questão
PADRAO_NIVEL = re.compile(r"\[NIVEL:\s*([^\]]+?)\s*\]", re.IGNORECASE)
PADRAO_PONTOS = re.compile(r"\[PONTOS:\s*([\d\.,]+?)\s*\]", re.IGNORECASE) 
PADRAO_TAGS = re.compile(r"\[TAGS:\s*([^\]]+?)\s*\]", re.IGNORECASE)
PADRAO_COMENTARIOS = re.compile(r"\[COMENTARIOS:\s*([^\]]+?)\s*\]", re.IGNORECASE)
PADRAO_TIPO = re.compile(r"\[TIPO:\s*([^\]]+?)\s*\]", re.IGNORECASE)  

def extract_text_with_formatting(paragraph):
    """
    Extrai o texto do parágrafo com tags avançadas de formatação.
    Retorna uma lista de tuplas (tag, value, idx).
    """
    result = []
    idx = 0

    # Detecta estilos de parágrafo (título, listas, alinhamento)
    style = paragraph.style.name if paragraph.style else ""
    if style.startswith("Heading"):
        result.append(('tagon', 'heading', style))
    elif "List" in style or style.lower() in ["bullet", "numbered"]:
        list_type = "bullet" if "Bullet" in style else "numbered"
        result.append(('tagon', 'list', list_type))

    # Alinhamento
    align = paragraph.alignment
    if align is not None:
        align_map = {0:"left", 1:"center", 2:"right", 3:"justify"}
        result.append(('tagon', 'align', align_map.get(align, "left")))

    for run in paragraph.runs:
        if run.bold:
            result.append(('tagon', 'bold', str(idx)))
        if run.italic:
            result.append(('tagon', 'italic', str(idx)))
        if run.underline:
            result.append(('tagon', 'underline', str(idx)))
        if run.font.strike:
            result.append(('tagon', 'strike', str(idx)))
        if run.font.superscript:
            result.append(('tagon', 'superscript', str(idx)))
        if run.font.subscript:
            result.append(('tagon', 'subscript', str(idx)))
        if run.font.color and run.font.color.rgb:
            result.append(('tagon', 'color', str(run.font.color.rgb)))
        if run.font.size:
            result.append(('tagon', 'font_size', str(run.font.size.pt)))
        if run.font.name:
            result.append(('tagon', 'font_name', str(run.font.name)))
        # Hyperlink: checagem básica
        if hasattr(run, "_element") and run._element.tag.endswith('hyperlink'):
            result.append(('tagon', 'hyperlink', run.text))

        if run.text:
            result.append(('text', run.text, str(idx)))

        if run.bold:
            result.append(('tagoff', 'bold', str(idx)))
        if run.italic:
            result.append(('tagoff', 'italic', str(idx)))
        if run.underline:
            result.append(('tagoff', 'underline', str(idx)))
        if run.font.strike:
            result.append(('tagoff', 'strike', str(idx)))
        if run.font.superscript:
            result.append(('tagoff', 'superscript', str(idx)))
        if run.font.subscript:
            result.append(('tagoff', 'subscript', str(idx)))
        if run.font.color and run.font.color.rgb:
            result.append(('tagoff', 'color', str(run.font.color.rgb)))
        if run.font.size:
            result.append(('tagoff', 'font_size', str(run.font.size.pt)))
        if run.font.name:
            result.append(('tagoff', 'font_name', str(run.font.name)))
        if hasattr(run, "_element") and run._element.tag.endswith('hyperlink'):
            result.append(('tagoff', 'hyperlink', run.text))
        idx += 1

    if style.startswith("Heading"):
        result.append(('tagoff', 'heading', style))
    elif "List" in style or style.lower() in ["bullet", "numbered"]:
        list_type = "bullet" if "Bullet" in style else "numbered"
        result.append(('tagoff', 'list', list_type))
    if align is not None:
        result.append(('tagoff', 'align', align_map.get(align, "left")))

    result.append(('text', '\n', None))
    return result


def extract_table_with_formatting(table):
    """
    Extrai uma tabela como uma sequência estruturada de tags.
    """
    result = [('table_start', None, None)]
    for row_idx, row in enumerate(table.rows):
        result.append(('row_start', row_idx, None))
        for cell_idx, cell in enumerate(row.cells):
            result.append(('cell_start', cell_idx, None))
            for paragraph in cell.paragraphs:
                result.extend(extract_text_with_formatting(paragraph))
            result.append(('cell_end', cell_idx, None))
        result.append(('row_end', row_idx, None))
    result.append(('table_end', None, None))
    return result

def tags_to_plain_text(tags_list):
        """
        Converte uma lista de tags [('text', ...), ...] para texto plano.
        """
        return "".join([x[1] for x in tags_list if x[0] == "text"]).strip()

def gerar_formatado(conteudo_simples):
    return {"ops": [{"insert": conteudo_simples}]}


class DocxParser:
    def __init__(self, base_media_dir: str, questao_model: type, opcao_model: type, texto_ref_model: type, logger: Optional[logging.Logger] = None):
        self.logger = logger if logger else logging.getLogger(__name__)
        self.QuestaoType_Parser = questao_model 
        self.OpcaoMultiplaEscolha_Parser = opcao_model 
        self.TextoReferenciaType_Parser = texto_ref_model 

        self.base_media_dir = base_media_dir 
        if not os.path.exists(self.base_media_dir):
            try:
                os.makedirs(self.base_media_dir, exist_ok=True)
                self.logger.info(f"Diretório de mídia base criado/verificado: {self.base_media_dir}")
            except OSError as e:
                self.logger.error(f"Não foi possível criar o diretório de mídia base '{self.base_media_dir}': {e}")
        
        self.padrao_alternativa_prefixo = re.compile(r"^\s*\(?([a-zA-Z])[\.\)]\s*")
        self.padrao_titulo_enunciado = re.compile(r"^\s*Enunciado\s*$", re.IGNORECASE)
        self.logger.info("DocxParser (versão legada adaptada) inicializado.")

    def _generate_short_id(self) -> str:
        letras = ''.join(random.choices(string.ascii_uppercase, k=2))
        numeros = ''.join(random.choices(string.digits, k=3))
        return f"{letras}{numeros}"

    def _get_text_from_cell(self, cell: _Cell) -> str: 
        return "\n".join([p.text.strip() for p in cell.paragraphs if p.text and p.text.strip()]).strip()

    def _ensure_subfolder_for_item(self, item_identifier: str) -> str:
        safe_name = re.sub(r'[^\w\s-]', '', item_identifier).strip().replace(' ', '_')
        safe_name = re.sub(r'[-\s]+', '-', safe_name) 
        if not safe_name: 
            safe_name = f"item_{self._generate_short_id()}"
        
        item_image_path = os.path.join(self.base_media_dir, safe_name) 
        if not os.path.exists(item_image_path):
            try:
                os.makedirs(item_image_path, exist_ok=True)
                self.logger.debug(f"Subdiretório de mídia criado: {item_image_path}")
            except OSError as e:
                self.logger.error(f"AVISO (DocxParser): Não criou dir '{item_image_path}': {e}")
                return self.base_media_dir 
        return item_image_path
    
    

    def parse_docx_with_tables_and_formatting(docx_document):
        """
        Exemplo de uso: percorre o docx e extrai tudo com formatação e tabelas.
        """
        result = []
        # Percorre parágrafos fora de tabela
        for paragraph in docx_document.paragraphs:
            result.extend(extract_text_with_formatting(paragraph))
        # Percorre tabelas
        for table in docx_document.tables:
            result.extend(extract_table_with_formatting(table))
        return result

    def _remover_endereco_imagem(self, texto):
        import re
        # Remove marcadores do tipo [IMAGEM: ...]
        texto = re.sub(r'\[IMAGEM:.*?\]', '', texto)
        # Remove nomes de arquivos de imagens que possam ter sobrado
        texto = re.sub(r'[^\s]+\.(png|jpg|jpeg|gif)', '', texto, flags=re.IGNORECASE)
        return texto.strip()

    def _extract_images_from_paragraph_runs(self, paragraph: DocxParagraph, document_part, image_save_dir: str, item_prefix: str) -> list:
        image_paths_found = []
        for run in paragraph.runs:
            for drawing_elm in run.element.iterfind(qn('w:drawing')): 
                for blip_elm in drawing_elm.iterdescendants(qn('a:blip')):
                    embed_id = blip_elm.get(qn('r:embed')) 
                    if embed_id and document_part.rels and embed_id in document_part.rels:
                        try:
                            image_part = document_part.rels[embed_id].target_part
                            image_bytes = image_part.blob
                            
                            content_type = image_part.content_type
                            image_ext = "png" 
                            if content_type and '/' in content_type:
                                potential_ext = content_type.split('/')[-1].lower()
                                if potential_ext in ["jpeg", "jpg", "png", "gif", "bmp", "tiff", "tif"]:
                                    image_ext = "jpg" if potential_ext == "jpeg" else ("tif" if potential_ext == "tiff" else potential_ext)
                            
                            img_filename = f"{item_prefix}_img_{self._generate_short_id()}.{image_ext}"
                            relative_img_path = os.path.relpath(os.path.join(image_save_dir, img_filename), self.base_media_dir).replace("\\","/")
                            full_img_save_path = os.path.join(image_save_dir, img_filename)

                            with open(full_img_save_path, 'wb') as f_img:
                                f_img.write(image_bytes)
                            image_paths_found.append(relative_img_path)
                            self.logger.debug(f"Imagem extraída: {full_img_save_path} (Relativo: {relative_img_path})")
                        except AttributeError as e_attr:
                            self.logger.warning(f"AttributeError ao processar imagem '{embed_id}': {e_attr}")
                        except Exception as e_img:
                            self.logger.warning(f"Erro genérico ao extrair/salvar imagem '{embed_id}': {e_img}")
        return image_paths_found

    def _get_text_and_images_from_cell_content(self, cell: _Cell, document_part, image_save_dir: str, item_prefix: str) -> tuple[list, list]:
        cell_formatado_parts = []
        cell_image_paths = []
        for paragraph in cell.paragraphs:
            formatado = extract_text_with_formatting(paragraph)
            cell_formatado_parts.extend(formatado)
            img_paths_in_para = self._extract_images_from_paragraph_runs(paragraph, document_part, image_save_dir, item_prefix)
            cell_image_paths.extend(img_paths_in_para)
            if img_paths_in_para:
                for p in img_paths_in_para:
                    cell_formatado_parts.append(('img', p, None))
            cell_formatado_parts.append(('text', '\n', None))
        # Se a célula inclui tabelas aninhadas:
        if hasattr(cell, 'tables'):
            for table in cell.tables:
                cell_formatado_parts.extend(extract_table_with_formatting(table))
        return cell_formatado_parts, cell_image_paths

    
    def _extract_reference_texts(self, document: DocxDocument, disciplina_bloco_destino_para_imagens: str) -> List[Dict[str, Any]]:
        self.logger.debug("Iniciando extração de textos de referência (MÉTODO CORRIGIDO).")
        parsed_texts_list = []
        paragrafos_doc = list(document.paragraphs)
        num_paragrafos = len(paragrafos_doc)
        idx = 0

        while idx < num_paragrafos:
            par = paragrafos_doc[idx]
            texto_par_strip = par.text.strip()

            is_text_ref = texto_par_strip == MARCADOR_TEXTO_REF_INICIO
            is_image_ref = texto_par_strip == MARCADOR_TEXTO_REF_IMG_INICIO

            if not is_text_ref and not is_image_ref:
                idx += 1
                continue

            # Avança o índice para depois do marcador de início
            idx += 1

            # A próxima linha é o TÍTULO
            if idx >= num_paragrafos:
                self.logger.warning(f"Fim inesperado do documento após marcador '{texto_par_strip}'.")
                break
            
            parsed_title = paragrafos_doc[idx].text.strip()
            idx += 1
            if not parsed_title or parsed_title.startswith("###TEXTO_REFERENCIA_"):
                self.logger.warning(f"Título ausente ou inválido após marcador '{texto_par_strip}' na linha ~{idx}. Pulando este bloco.")
                continue

            # Coleta os parágrafos de conteúdo até encontrar o marcador de fim
            content_paragraphs: List[DocxParagraph] = []
            while idx < num_paragrafos:
                par_conteudo = paragrafos_doc[idx]
                texto_conteudo_strip = par_conteudo.text.strip()

                end_marker_found = (is_text_ref and texto_conteudo_strip == MARCADOR_TEXTO_REF_FIM) or \
                                   (is_image_ref and texto_conteudo_strip == MARCADOR_TEXTO_REF_IMG_FIM)

                if end_marker_found:
                    idx += 1  # Pula o marcador de fim
                    break
                
                # Prevenção contra blocos aninhados sem fim
                if texto_conteudo_strip.startswith("###TEXTO_REFERENCIA_") and texto_conteudo_strip.endswith("_INICIO###"):
                    self.logger.warning(f"Novo marcador de INÍCIO encontrado durante coleta para título '{parsed_title}'. Finalizando bloco atual.")
                    break
                
                content_paragraphs.append(par_conteudo)
                idx += 1

            # Agora, processa os parágrafos coletados
            conteudo_formatado_tags = []
            conteudo_simples_parts = []
            image_path_for_ref: Optional[str] = None
            ref_item_image_save_dir = self._ensure_subfolder_for_item(os.path.join(disciplina_bloco_destino_para_imagens, f"ref_{parsed_title[:20]}"))

            for par_content in content_paragraphs:
                # Extrai o conteúdo formatado em tags
                conteudo_formatado_tags.extend(extract_text_with_formatting(par_content))
                # Extrai o texto simples
                conteudo_simples_parts.append(par_content.text)
                
                # Se for uma imagem, extrai o arquivo
                if is_image_ref and not image_path_for_ref:
                    img_paths = self._extract_images_from_paragraph_runs(
                        par_content, document.part, ref_item_image_save_dir,
                        f"ref_{''.join(filter(str.isalnum, parsed_title[:10]))}"
                    )
                    if img_paths:
                        image_path_for_ref = img_paths[0]

            conteudo_simples_final = "\n".join(conteudo_simples_parts).strip()

            if is_text_ref:
                parsed_texts_list.append({
                    "titulo_parser": parsed_title,
                    "tipo_conteudo": "texto",
                    "conteudo_parser": conteudo_simples_final,
                    "conteudo_formatado_parser": conteudo_formatado_tags
                })
                self.logger.debug(f"Texto de referência (tipo texto) '{parsed_title}' extraído COM FORMATAÇÃO.")

            elif is_image_ref:
                if image_path_for_ref:
                    parsed_texts_list.append({
                        "titulo_parser": parsed_title,
                        "tipo_conteudo": "imagem",
                        "caminho_imagem_relativo": image_path_for_ref,
                        "descricao_imagem_parser": conteudo_simples_final,
                        "conteudo_formatado_parser": conteudo_formatado_tags
                    })
                    self.logger.debug(f"Texto de referência (imagem) '{parsed_title}' extraído com imagem: {image_path_for_ref}.")
                else:
                    self.logger.warning(f"Bloco de referência de imagem '{parsed_title}' não continha uma imagem, mas foi salvo como texto.")
                    parsed_texts_list.append({
                        "titulo_parser": parsed_title,
                        "tipo_conteudo": "texto",
                        "conteudo_parser": conteudo_simples_final,
                        "conteudo_formatado_parser": conteudo_formatado_tags
                    })

        self.logger.info(f"{len(parsed_texts_list)} textos de referência extraídos (com formatação).")
        return parsed_texts_list

    def _parse_metadata_from_enunciado(self, enunciado_txt: str) -> Tuple[str, Dict[str, Any]]:
        metadados_extraidos = {}
        enunciado_limpo = enunciado_txt

        # Extrai [TIPO: ...]
        match_tipo = PADRAO_TIPO.search(enunciado_limpo)
        if match_tipo:
            # Armazena o tipo extraído para decisão posterior
            metadados_extraidos["tipo_tag_parser"] = match_tipo.group(1).strip()
            enunciado_limpo = PADRAO_TIPO.sub("", enunciado_limpo).strip()
            self.logger.debug(f"Metadado TIPO extraído: {metadados_extraidos['tipo_tag_parser']}")

        match_nivel = PADRAO_NIVEL.search(enunciado_limpo)
        if match_nivel:
            metadados_extraidos["nivel_dificuldade"] = match_nivel.group(1).strip()
            enunciado_limpo = PADRAO_NIVEL.sub("", enunciado_limpo).strip() 
            self.logger.debug(f"Metadado NÍVEL extraído: {metadados_extraidos['nivel_dificuldade']}")

        match_pontos = PADRAO_PONTOS.search(enunciado_limpo)
        if match_pontos:
            pontos_str = match_pontos.group(1).replace(",", ".").strip() 
            try:
                metadados_extraidos["pontuacao"] = float(pontos_str)
                enunciado_limpo = PADRAO_PONTOS.sub("", enunciado_limpo).strip() 
                self.logger.debug(f"Metadado PONTOS extraído: {metadados_extraidos['pontuacao']}")
            except ValueError:
                self.logger.warning(f"Valor de PONTOS inválido: '{match_pontos.group(1)}'. Usando default.")
        
        match_tags = PADRAO_TAGS.search(enunciado_limpo)
        if match_tags:
            tags_str = match_tags.group(1).strip()
            metadados_extraidos["tags_keywords"] = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            enunciado_limpo = PADRAO_TAGS.sub("", enunciado_limpo).strip() 
            self.logger.debug(f"Metadado TAGS extraído: {metadados_extraidos['tags_keywords']}")

        match_ref = PADRAO_USA_TEXTO_REF.search(enunciado_limpo)
        if match_ref:
            titulo_texto_ref_tag = match_ref.group(1).strip() 
            metadados_extraidos["titulo_texto_ref_tag_parser"] = titulo_texto_ref_tag 
            enunciado_limpo = PADRAO_USA_TEXTO_REF.sub("", enunciado_limpo).strip() 
            self.logger.debug(f"Tag USA_TEXTO_REF (título) extraída: {titulo_texto_ref_tag}")
        
        match_comentarios = PADRAO_COMENTARIOS.search(enunciado_limpo) 
        if match_comentarios:
            metadados_extraidos["feedback_geral_questao"] = match_comentarios.group(1).strip()
            enunciado_limpo = PADRAO_COMENTARIOS.sub("", enunciado_limpo).strip()
            self.logger.debug(f"Metadado COMENTARIOS extraído: {metadados_extraidos['feedback_geral_questao']}")


        return enunciado_limpo.strip(), metadados_extraidos

    # ... (mantém o início do arquivo igual)

    def _parse_question_tables_legado(self, document: DocxDocument, 
                                  disciplina_param: str,
                                  textos_referencia_disponiveis: dict, 
                                  image_save_dir_for_discipline: str) -> list:
        questoes_extraidas = []
        idx = 0
        num_tables = len(document.tables)
        
        while idx < num_tables:
            tabela_enunciado_candidata = document.tables[idx]
            enunciado_bruto_com_metadados = ""
            opcoes_atuais_info: List[dict] = []
            metadados_da_questao: Dict[str, Any] = {}
            gabarito_letra_para_modelo: Optional[str] = None
            
            if len(tabela_enunciado_candidata.rows) == 1 and len(tabela_enunciado_candidata.columns) == 1:
                q_id_temp_prefix = f"{disciplina_param}_q{len(questoes_extraidas) + 1}_{self._generate_short_id()}"
                
                texto_celula_bruto_tags, imagens_enunciado = self._get_text_and_images_from_cell_content(
                    tabela_enunciado_candidata.cell(0,0),
                    document.part,
                    image_save_dir_for_discipline,
                    q_id_temp_prefix
                )
                texto_celula_bruto = tags_to_plain_text(texto_celula_bruto_tags)
                
                if texto_celula_bruto and not self.padrao_titulo_enunciado.match(texto_celula_bruto):
                    enunciado_bruto_com_metadados = texto_celula_bruto
                    if imagens_enunciado:
                        metadados_da_questao["caminho_imagem_enunciado"] = imagens_enunciado[0]
                    
                    enunciado_final_limpo, metadados_das_tags = self._parse_metadata_from_enunciado(enunciado_bruto_com_metadados)
                    enunciado_final_limpo = self._remover_endereco_imagem(enunciado_final_limpo)
                    metadados_da_questao.update(metadados_das_tags)

                    id_ref_tag_from_meta = metadados_da_questao.get("id_texto_ref_vinculado_tag")
                    if id_ref_tag_from_meta and id_ref_tag_from_meta not in textos_referencia_disponiveis:
                        self.logger.warning(f"Enunciado '{enunciado_final_limpo[:30]}...' usa texto de ref. ID/Tag '{id_ref_tag_from_meta}' que não foi encontrado.")
                else:
                    idx += 1
                    continue
            else:
                idx += 1
                continue
            
            idx_tabela_alternativas = idx + 1

            if idx_tabela_alternativas < num_tables:
                tabela_alt_potencial = document.tables[idx_tabela_alternativas]
                if len(tabela_alt_potencial.columns) == 1 and len(tabela_alt_potencial.rows) > 0:
                    # Checagem inicial da primeira célula para evitar tabelas de enunciado perdidas
                    primeira_celula_alt_texto_tags, _ = self._get_text_and_images_from_cell_content(
                        tabela_alt_potencial.cell(0,0), document.part, image_save_dir_for_discipline, "alt_temp"
                    )
                    if not self.padrao_titulo_enunciado.match(tags_to_plain_text(primeira_celula_alt_texto_tags)):
                        for row_alt_idx, row_alt in enumerate(tabela_alt_potencial.rows):
                            if row_alt.cells:
                                # <<< CORREÇÃO 1: Renomeada variável para clareza
                                texto_opcao_tags, lista_imgs_opcao = self._get_text_and_images_from_cell_content(
                                    row_alt.cells[0],
                                    document.part,
                                    image_save_dir_for_discipline,
                                    f"{q_id_temp_prefix}_opt{row_alt_idx}"
                                )
                                
                                # <<< CORREÇÃO 2: A condição IF agora usa tags_to_plain_text
                                if tags_to_plain_text(texto_opcao_tags) or lista_imgs_opcao:
                                    if len(opcoes_atuais_info) < MAX_ALTERNATIVAS_PARSER:
                                        opcoes_atuais_info.append({
                                            "texto": tags_to_plain_text(texto_opcao_tags),
                                            "texto_formatado": texto_opcao_tags,
                                            "imagem_path_opcao": lista_imgs_opcao[0] if lista_imgs_opcao else None
                                        })
                                        
                                    else:
                                        self.logger.warning(
                                            f"Máximo de {MAX_ALTERNATIVAS_PARSER} alternativas atingido para questão com enunciado '{enunciado_final_limpo[:30]}...'."
                                        )
                                        break
                        
                        # Se alternativas foram encontradas, avança o índice principal para depois da tabela de alternativas
                        if opcoes_atuais_info:
                            idx = idx_tabela_alternativas
            
            # --- MODIFICAÇÃO PARA USAR ENUM TipoQuestao ---
            tipo_q_final_para_modelo = None
            tipo_extraido_da_tag = metadados_da_questao.get("tipo_tag_parser", "").lower()

            if "certo" in tipo_extraido_da_tag or "errado" in tipo_extraido_da_tag:
                tipo_q_final_para_modelo = elements_TipoQuestao.CERTO_ERRADO.value
            elif "discursiva" in tipo_extraido_da_tag or "dissertativa" in tipo_extraido_da_tag:
                tipo_q_final_para_modelo = elements_TipoQuestao.DISCURSIVA.value
            elif "multipla" in tipo_extraido_da_tag or "múltipla" in tipo_extraido_da_tag:
                 tipo_q_final_para_modelo = elements_TipoQuestao.MULTIPLA_ESCOLHA.value
            
            if tipo_q_final_para_modelo is None:
                if opcoes_atuais_info:
                    tipo_q_final_para_modelo = elements_TipoQuestao.MULTIPLA_ESCOLHA.value
                else:
                    tipo_q_final_para_modelo = elements_TipoQuestao.DISCURSIVA.value
            
            opcoes_para_modelo: Optional[List[Any]] = []

            if tipo_q_final_para_modelo == elements_TipoQuestao.MULTIPLA_ESCOLHA.value:
                if not opcoes_atuais_info:
                    self.logger.warning(f"Questão com enunciado '{enunciado_final_limpo[:30]}...' foi marcada como múltipla escolha mas não tem alternativas. Tratando como discursiva.")
                    tipo_q_final_para_modelo = elements_TipoQuestao.DISCURSIVA.value
                    opcoes_para_modelo = None
                    gabarito_letra_para_modelo = None
                else:
                    gabarito_letra_para_modelo = "A" # Assume A como correta por padrão se não especificado
                    for i, opt in enumerate(opcoes_atuais_info):
                        letra_opcao = chr(65 + i)
                        texto_da_opcao_plano = self._remover_endereco_imagem(opt["texto"])
                        texto_da_opcao_formatado = opt["texto_formatado"] if "texto_formatado" in opt else []
                        imagem_path_opcao = opt.get("imagem_path_opcao")
                        opcoes_para_modelo.append(
                            self.OpcaoMultiplaEscolha_Parser(
                                letra=letra_opcao,
                                texto_opcao=texto_da_opcao_plano,
                                texto_opcao_formatado=texto_da_opcao_formatado,
                                imagem_path_opcao=imagem_path_opcao,
                                correta=(i == 0)
                            )
                        )

            else:
                opcoes_para_modelo = None
                gabarito_letra_para_modelo = None

            q_id_final = self._generate_short_id()
            
            if "caminho_imagem_enunciado" in metadados_da_questao:
                old_img_relative_path = metadados_da_questao["caminho_imagem_enunciado"]
                old_filename = os.path.basename(old_img_relative_path)
                new_filename = old_filename.replace(q_id_temp_prefix, f"q_{q_id_final}", 1)
                new_img_relative_path_for_db = os.path.join(os.path.basename(image_save_dir_for_discipline), new_filename).replace("\\", "/")
                old_img_full_path = os.path.join(image_save_dir_for_discipline, old_filename)
                new_img_full_path = os.path.join(image_save_dir_for_discipline, new_filename)

                if os.path.exists(old_img_full_path):
                    try:
                        if old_img_full_path != new_img_full_path :
                           os.rename(old_img_full_path, new_img_full_path)
                        metadados_da_questao["caminho_imagem_enunciado"] = new_img_relative_path_for_db
                        self.logger.debug(f"Imagem do enunciado renomeada/confirmada para questão {q_id_final}: '{new_img_relative_path_for_db}'")
                    except OSError as e_rename:
                        self.logger.warning(f"Falha ao renomear imagem do enunciado '{old_img_full_path}' para '{new_img_full_path}': {e_rename}")
                        metadados_da_questao["caminho_imagem_enunciado"] = old_img_relative_path
                else:
                    self.logger.warning(f"Arquivo de imagem original do enunciado não encontrado para renomear: {old_img_full_path}")
            
            enunciado_formatado = texto_celula_bruto_tags  # lista de tuplas [('text', ...), ('img', ...)]
            enunciado_puro = tags_to_plain_text(enunciado_formatado)

            # Pega a primeira imagem do enunciado (se houver)
            caminho_imagem_enunciado = None
            for tag in enunciado_formatado:
                if tag[0] == 'img' and tag[1]:
                    caminho_imagem_enunciado = tag[1]
                    break

            nova_questao = self.QuestaoType_Parser(
                id_questao=q_id_final,
                tipo=tipo_q_final_para_modelo,
                enunciado=enunciado_final_limpo,
                enunciado_formatado=enunciado_formatado,           # Passe a lista direta!
                disciplina_banco=disciplina_param,
                opcoes=opcoes_para_modelo,
                resposta_correta=gabarito_letra_para_modelo,
                metadados_questao=metadados_da_questao,
                nivel_dificuldade=metadados_da_questao.get("nivel_dificuldade", "Médio"),
                pontuacao=float(metadados_da_questao.get("pontuacao", 1.0)),  
                id_texto_ref_vinculado=metadados_da_questao.get("id_texto_ref_vinculado_tag"),
                feedback_geral_questao=metadados_da_questao.get("feedback_geral_questao", ""),
                tags=metadados_da_questao.get("tags_keywords", []),
                data_criacao=datetime.datetime.now(),
                data_modificacao=datetime.datetime.now()
            )
            print("DEBUG PARSER QUESTAO:", nova_questao.id_questao, nova_questao.enunciado, nova_questao.enunciado_formatado)
            questoes_extraidas.append(nova_questao)
            self.logger.debug(f"Questão '{q_id_final}' (tipo: {tipo_q_final_para_modelo}) processada com {len(opcoes_para_modelo) if opcoes_para_modelo else 0} opções.")
            
            idx += 1
        
        self.logger.info(f"{len(questoes_extraidas)} questões (legado) extraídas para '{disciplina_param}'.")
        return questoes_extraidas

# ... (o resto do arquivo permanece igual)

    def parse_document(self, filepath: str, disciplina_bloco_destino: str) -> Tuple[List[Any], Dict[str, Any]]:
        if not os.path.exists(filepath):
            self.logger.error(f"Arquivo '{filepath}' não encontrado.")
            return [], {} 
        
        self.logger.info(f"Iniciando parse (método legado) do documento '{filepath}' para disciplina/bloco '{disciplina_bloco_destino}'")
        try:
            document: DocxDocument = docx.Document(filepath)
            
            image_save_dir_for_discipline_items = self._ensure_subfolder_for_item(disciplina_bloco_destino)

            textos_ref_extraidos_dict = self._extract_reference_texts(document, disciplina_bloco_destino) 
            self.logger.debug(f"{len(textos_ref_extraidos_dict)} textos de referência (legado) extraídos.")

            questoes = self._parse_question_tables_legado(document, disciplina_bloco_destino, textos_ref_extraidos_dict, image_save_dir_for_discipline_items)
            self.logger.info(f"{len(questoes)} questões (legado) extraídas para o bloco '{disciplina_bloco_destino}'.")

            return questoes, textos_ref_extraidos_dict 
        
        except Exception as e:
            self.logger.exception(f"Falha crítica ao processar o documento '{filepath}' (método legado): {e}")
            return [], {}