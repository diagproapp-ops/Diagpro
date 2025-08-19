# DiagProOFF/core/stubs.py
import datetime
import logging
import os
import tempfile # Importado para uso em stubs
from typing import List, Optional, Dict, Any, Tuple, Callable, Type

logger_stubs = logging.getLogger(f"core.{__name__}")

class _BaseStub:
    def __init__(self, *args: Any, **kwargs: Any):
        for key, value in kwargs.items():
            setattr(self, key, value)
        # logger_stubs.debug(f"STUB {self.__class__.__name__} __init__ args={args}, kwargs={kwargs}")

# --- Stubs para core.elements ---
class EventoTypeStub(_BaseStub):
    id_evento: str = "stub_event_id_elements"
    nome_evento: str = "Evento Elements Stub"
    sigla_evento: Optional[str] = "STB_ELM"
    data_prova: Optional[datetime.date] = None
    local_prova: Optional[str] = "Local Elements Stub"
    cargos: List[Any] = []
    provas_montadas: List[Any] = []
    textos_referencia: Dict[str, Any] = {}
    banco_questoes: Dict[str, List[Any]] = {}
    # Adicione outros campos que EventoType real tem e são acessados
    numero_edital: Optional[str] = "000/0000"
    instituicao: Optional[str] = "Instituicao Stub"
    logo_path: Optional[str] = None
    qtd_cargos_estimada: Optional[int] = 0

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # Garante que atributos de lista sejam inicializados se não vierem em kwargs
        if not hasattr(self, 'cargos'): self.cargos = []
        if not hasattr(self, 'provas_montadas'): self.provas_montadas = []
        if not hasattr(self, 'textos_referencia'): self.textos_referencia = {}
        if not hasattr(self, 'banco_questoes'): self.banco_questoes = {}


class CargoTypeStub(_BaseStub):
    id_cargo: str = "stub_cargo_id_elements"
    nome_cargo: str = "Cargo Elements Stub"
    disciplinas_prova: List[Any] = [] # Se CargoType tem disciplinas_prova
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if not hasattr(self, 'disciplinas_prova'): self.disciplinas_prova = []


class ProvaMontadaTypeStub(_BaseStub):
    id_prova_montada: str = "stub_pm_id_elements"
    id_cargo: Optional[str] = "stub_cargo_id_pm_elements"
    metadados_prova: Dict[str, Any] = {}
    questoes_por_disciplina: Dict[str, List[Any]] = {}
    ordem_disciplinas_na_prova: List[str] = []
    nome_cargo_associado: Optional[str] = "Cargo Stub PM" # Adicionado
    tipo_prova_tag: Optional[str] = "TIPO_A_STUB" # Adicionado

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if not hasattr(self, 'metadados_prova') or not self.metadados_prova:
            self.metadados_prova = {"definicao_geracao": {}}
        if not hasattr(self, 'questoes_por_disciplina'): self.questoes_por_disciplina = {}
        if not hasattr(self, 'ordem_disciplinas_na_prova'): self.ordem_disciplinas_na_prova = []

class TipoProvaStub: # Stub para o Enum
    TIPO_A = "TIPO_A_STUB_ELEMENTS"
    TIPO_B = "TIPO_B_STUB_ELEMENTS"
    # Adicione outros membros se seu código os acessa
    @classmethod
    def get_display_name(cls, tag_value: str) -> str: return str(tag_value)
    @classmethod
    def get_ordered_list(cls) -> list[str]: return [cls.TIPO_A, cls.TIPO_B]

class QuestaoTypeStub(_BaseStub):
    id_questao: str = "stub_q_id_elements"
    tipo: str = "multipla_escolha"
    opcoes_multipla_escolha: List[Any] = [] # Nome corrigido para corresponder ao EventoType
    enunciado: str = "Enunciado Stub"
    resposta_correta: Optional[str] = "A"
    # Adicione outros atributos mínimos que seu código espera
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if not hasattr(self, 'opcoes_multipla_escolha'): self.opcoes_multipla_escolha = []


class OpcaoMultiplaEscolhaStub(_BaseStub):
    letra: str = "A"
    texto: str = "Opção Elements Stub"
    correta: bool = False
    def __init__(self, **kwargs: Any): super().__init__(**kwargs)

class TextoReferenciaTypeStub(_BaseStub):
    id_texto_ref: str = "stub_tr_id_elements"
    def __init__(self, **kwargs: Any): super().__init__(**kwargs)

class DisciplinaProvaTypeStub(_BaseStub):
    nome_disciplina: str = "Disciplina Prova Stub"
    qtd_questoes_total_disciplina: int = 0
    questoes_ids_sorteadas: List[str] = []
    textos_ref_associados_ids: List[str] = []
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        if not hasattr(self, 'questoes_ids_sorteadas'): self.questoes_ids_sorteadas = []
        if not hasattr(self, 'textos_ref_associados_ids'): self.textos_ref_associados_ids = []

class DisciplinaTypeStub(_BaseStub):
    nome_disciplina: str = "Disciplina Stub"
    qtd_questoes: int = 0
    def __init__(self, **kwargs: Any): super().__init__(**kwargs)

class UserTypeStub(_BaseStub):
    username: str = "stub_user"
    def __init__(self, **kwargs: Any): super().__init__(**kwargs)

# --- Stub para core.event_manager ---
class EventManagerStub(_BaseStub):
    def __init__(self, db_path: Optional[str] = None, logger: Optional[logging.Logger] = None, app_controller: Optional[Any]=None, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs) # Passa *args e **kwargs para _BaseStub
        self.logger = logger if logger else logger_stubs.getChild(self.__class__.__name__)
        self.logger.info(f"STUB EventManager inicializado (db_path: {db_path})")

    def get_event_by_id(self, event_id: str) -> Optional[EventoTypeStub]:
        self.logger.debug(f"STUB EventManager.get_event_by_id({event_id})")
        cargo_stub = CargoTypeStub(id_cargo="stub_cargo_evm", nome_cargo="Cargo EVM Stub")
        pm_stub = ProvaMontadaTypeStub(id_prova_montada="stub_pm_evm", id_cargo="stub_cargo_evm")
        return EventoTypeStub(id_evento=event_id, nome_evento=f"Evento EVM Stub {event_id}", cargos=[cargo_stub], provas_montadas=[pm_stub])

    def get_user_by_username(self, username: str) -> Optional[UserTypeStub]:
        self.logger.debug(f"STUB EventManager.get_user_by_username({username})")
        return None # Ou um UserTypeStub se necessário para testes

    def close_db_connection(self):
        self.logger.debug("STUB EventManager.close_db_connection()")

    def salvar_prova_montada_para_evento_cargo(self, *args: Any, **kwargs: Any) -> bool:
        self.logger.debug(f"STUB EventManager.salvar_prova_montada_para_evento_cargo args={args} kwargs={kwargs}")
        return True

    def create_all_tables_if_not_exists(self, *args: Any, **kwargs: Any): # Adicionado para corresponder à chamada
        self.logger.debug("STUB EventManager.create_all_tables_if_not_exists chamada")


# --- Stub para core.docx_parser ---
class DocxParserStub(_BaseStub):
    def __init__(self, base_image_storage_dir: str, questao_model: Type[Any], opcao_model: Type[Any], texto_ref_model: Type[Any], logger: logging.Logger):
        super().__init__() # _BaseStub pode precisar de args/kwargs se você os usa lá
        self.logger = logger.getChild(self.__class__.__name__)
        self.logger.info("STUB DocxParser inicializado.")
    def parse_document(self, filepath: str, disciplina_bloco_destino: str) -> Tuple[List[Any], Dict[str, Any]]:
        self.logger.debug(f"STUB DocxParser.parse_document({filepath}, {disciplina_bloco_destino})")
        return [], {}

# --- Stubs para componentes de core.document_generator ---
class DocxProofGeneratorStub(_BaseStub):
    def __init__(self, prova_montada_obj: Any, evento_obj: Any, format_options: dict,
                 template_prova_path: Optional[str] = None, logger: Optional[logging.Logger] = None,
                 core_elements_module: Optional[Any] = None, **kwargs: Any): # Adicionado **kwargs
        super().__init__(**kwargs) # Passa kwargs
        self.logger = logger if logger else logger_stubs.getChild(self.__class__.__name__)
        self.logger.info("STUB DocxProofGenerator inicializado")
    def generate_docx_and_answer_key_data(self, *args: Any, **kwargs: Any) -> tuple[Optional[str], list[dict], list[str]]:
        self.logger.debug("STUB DocxProofGenerator.generate_docx_and_answer_key_data")
        return "dummy_proof.docx", [], []

class ArchiveManagerStub(_BaseStub):
    @staticmethod
    def fill_pdf_form(*args: Any, **kwargs: Any) -> Optional[str]: return "stub_filled.pdf"
    @staticmethod
    def merge_pdfs(*args: Any, **kwargs: Any) -> bool: return True
    @staticmethod
    def create_zip(*args: Any, **kwargs: Any) -> bool: return True

class AnswerKeyGeneratorStub(_BaseStub):
    @staticmethod
    def generate_answer_keys_for_mounted_proofs(*args: Any, **kwargs: Any) -> Tuple[Optional[str], Optional[str]]:
        logger_stubs.info("STUB: AnswerKeyGenerator.generate_answer_keys_for_mounted_proofs")
        path_completo = kwargs.get("path_gabarito_completo_csv")
        path_simples = kwargs.get("path_gabarito_simples_csv")
        # Simula a criação de arquivos para que PFEW não reclame
        if path_completo and isinstance(path_completo, str):
            try: open(path_completo, "w").write("dummy_gab_completo")
            except: pass
        if path_simples and isinstance(path_simples, str):
            try: open(path_simples, "w").write("dummy_gab_simples")
            except: pass
        return path_completo, path_simples
    @staticmethod
    def generate_complete_csv(*args: Any, **kwargs: Any): logger_stubs.info("STUB: generate_complete_csv")
    @staticmethod
    def generate_simple_csv_v2(*args: Any, **kwargs: Any): logger_stubs.info("STUB: generate_simple_csv_v2")

class PdfConverterStub(_BaseStub):
    @staticmethod
    def convert_to_pdf(docx_path: str, output_folder: str) -> Optional[str]:
        return os.path.join(output_folder, f"stub_{os.path.basename(docx_path)}_converted.pdf")

class DocumentGeneratorStub(_BaseStub):
    def __init__(self, templates_base_dir: str, event_manager: Any, logger: logging.Logger, core_elements: Any, config: Optional[Dict[str,Any]]=None, app_instance: Optional[Any]=None, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.logger = logger.getChild(self.__class__.__name__)
        self.logger.info(f"STUB DocumentGenerator inicializado (event_manager type: {type(event_manager)})")
    def gerar_pacote_provas_completo(self, *args: Any, **kwargs: Any) -> Tuple[Optional[str], list, list]:
        self.logger.debug("STUB DocumentGenerator.gerar_pacote_provas_completo")
        output_dir_lote_stub = kwargs.get('output_dir_base_lote', tempfile.mkdtemp(prefix="stub_dg_main_"))
        stub_zip_path = os.path.join(output_dir_lote_stub, "pacote_stub_main_dg.zip")
        try:
            with open(stub_zip_path, "w") as f: f.write("conteúdo do zip stub")
        except IOError: stub_zip_path = None
        return stub_zip_path, ["gabarito_stub_main.csv"], ["prova_stub_main.pdf"]
    def gerar_pacote_provas_com_capa_e_gabaritos(self, *args: Any, **kwargs: Any) -> Tuple[Optional[str], list, list]:
        return self.gerar_pacote_provas_completo(*args, **kwargs)

# --- Stubs para dependências de bibliotecas ---
class PdfWriterStubPyPDF2(_BaseStub):
    def __init__(self, *args: Any, **kwargs: Any): super().__init__(*args, **kwargs); self.root_object = None; self._root_object = None; self.pages: List[Any] = []
    def add_page(self, page: Any): self.pages.append(page)
    def write(self, stream: Any): pass
    def append(self, fileobj: Any): pass
    def update_page_form_field_values(self, page: Any, fields: Dict[str, Any], auto_regenerate: bool =True): pass
    def insert(self, index: int, fileobj: Any): pass
    def _build_ctx(self):
        if self._root_object is None:
            self._root_object = DictionaryObjectStubPyPDF2()
            self._root_object[NameObjectStubPyPDF2("/Type")] = NameObjectStubPyPDF2("/Catalog")
            self._root_object[NameObjectStubPyPDF2("/Pages")] = DictionaryObjectStubPyPDF2()
            self._root_object["/Pages"][NameObjectStubPyPDF2("/Type")] = NameObjectStubPyPDF2("/Pages")
            self._root_object["/Pages"][NameObjectStubPyPDF2("/Count")] = NumberObjectStubPyPDF2(0)
            self._root_object["/Pages"][NameObjectStubPyPDF2("/Kids")] = ArrayObjectStubPyPDF2()
class PdfReaderStubPyPDF2(_BaseStub):
    def __init__(self, stream: Any, *args: Any, **kwargs: Any): super().__init__(*args, **kwargs); self.pages: List[Any] = []; self.trailer: Dict[Any, Any] = {"/Root": DictionaryObjectStubPyPDF2({NameObjectStubPyPDF2("/AcroForm"): DictionaryObjectStubPyPDF2()})} if globals().get("NameObjectStubPyPDF2") and globals().get("DictionaryObjectStubPyPDF2") else {} # type: ignore
    def get_fields(self, tree: Any=None, retval: Any=None, fileobj: Any=None) -> Dict[Any, Any]: return {}
class NameObjectStubPyPDF2(str): pass
class BooleanObjectStubPyPDF2(bool): pass
class DictionaryObjectStubPyPDF2(dict): pass
class TextStringObjectStubPyPDF2(str): pass
class NumberObjectStubPyPDF2(int): pass
class ArrayObjectStubPyPDF2(list): pass

class rl_canvas_module_stub_RL:
    class Canvas(_BaseStub):
        def __init__(self, filename: str, pagesize: Any=None, *args: Any, **kwargs: Any): super().__init__(*args, **kwargs)
        def save(self): pass
        def drawString(self, x: float, y: float, text: str): pass
class A4Stub_RL: pass
class CmStub_RL: pass
class RlColorStub_RL: pass
class ParagraphRLStub_RL(_BaseStub):
    def __init__(self,t: str,s: Any, *args: Any, **kwargs: Any):super().__init__(*args, **kwargs)
    def wrapOn(self,c: Any,w: float,h: float):pass
    def drawOn(self,c: Any,x: float,y: float):pass
    @property
    def height(self) -> float: return 0.0
def getSampleStyleSheetRLStub_RL(): return {'Normal': type('S',(object,),{'fontName':'','fontSize':10,'leading':12,'alignment':0})()} # type: ignore
class TA_CENTER_STUB_RL: pass
class TA_JUSTIFY_STUB_RL: pass
class TA_LEFT_STUB_RL: pass
class TA_RIGHT_STUB_RL: pass

# --- CORREÇÕES DE SINTAXE E DEFINIÇÃO ABAIXO ---
class DocumentStub_Docx(_BaseStub): pass
class PtStub_Docx(_BaseStub): pass
class InchesStub_Docx(_BaseStub): pass
class DocxCmStub_Docx(_BaseStub): pass
class RGBColorStub_Docx(_BaseStub): pass

class WD_ALIGN_PARAGRAPH_STUB_Docx: # Não precisa herdar de _BaseStub
    CENTER=1
    JUSTIFY=3
    LEFT=0
    RIGHT=2

class WD_TAB_ALIGNMENT_STUB_Docx: # Não precisa herdar de _BaseStub
    LEFT=0

class WD_TAB_LEADER_STUB_Docx: # Não precisa herdar de _BaseStub
    SPACES=0

class WD_SECTION_START_STUB_Docx: # Não precisa herdar de _BaseStub
    NEW_PAGE=2

def qn_stub_Docx(tag: str) -> str: # Adicionada anotação de tipo
    return tag

class OxmlElementStub_Docx(_BaseStub):
    _name: str # Anotação de tipo para o atributo de instância
    _children: List[Any] # Anotação de tipo

    def __init__(self, name: str, *args: Any, **kwargs: Any): # Adicionado *args, **kwargs e tipo para name
        super().__init__(*args, **kwargs) # Passa todos os args para a base primeiro
        self._name = name # Define o atributo depois de chamar o super
        self._children = []

    def set(self, key: str, value: Any) -> None: # Adicionadas anotações de tipo
        pass

    def append(self, child: Any) -> None: # Adicionada anotação de tipo
        if not hasattr(self, '_children') or not isinstance(self._children, list):
            self._children = []
        self._children.append(child)

    def get_or_add_pPr(self) -> 'OxmlElementStub_Docx': # Retorna o próprio tipo
        return self

class DocxParagraphTypeInternalStub_Docx(_BaseStub): pass
# --- FIM DAS CORREÇÕES DE SINTAXE ---

logger_stubs.info("core/stubs.py carregado e stubs definidos.")