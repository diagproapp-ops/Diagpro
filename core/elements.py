# core/elements.py
# O seu código original completo, com a única correção necessária na ordem dos campos.

import random
import datetime
from datetime import date, datetime
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
import json
import typing
from typing import Optional, List, Dict, Any, Union, ClassVar
from pydantic import root_validator

import logging

from pydantic import BaseModel, Field as PydanticField, field_validator, EmailStr, PositiveInt, NonNegativeInt, NonNegativeFloat, ValidationInfo
from datetime import datetime as DatetimeObject, date as DateObject

from .utils import sanitize_filename, resource_path, setup_logging, parse_iso_to_datetime

logger_elements = logging.getLogger(__name__)
try:
    setup_logging(logger_elements)
except Exception:
    logging.basicConfig(level=logging.WARNING)
    logger_elements.warning("Falha na configuração de logging em elements.py. Usando basicConfig.")


# --- Modelos de Configuração Pydantic (SEU CÓDIGO PRESERVADO) ---

class FormatOptionsType(BaseModel):
    """Opções de formatação para geração de provas (DOCX)."""
    title_font_name: str = PydanticField(default="Calibri")
    title_font_size_pt: int = PydanticField(default=14)
    header_info_font_name: str = PydanticField(default="Calibri")
    header_info_font_size_pt: int = PydanticField(default=10)
    instructions_title_font_name: str = PydanticField(default="Calibri")
    instructions_title_font_size_pt: int = PydanticField(default=12)
    instructions_font_name: str = PydanticField(default="Calibri")
    instructions_font_size_pt: int = PydanticField(default=10)
    question_font_name: str = PydanticField(default="Calibri")
    question_font_size_pt: int = PydanticField(default=11)
    option_font_name: str = PydanticField(default="Calibri")
    option_font_size_pt: int = PydanticField(default=11)
    footer_font_name: str = PydanticField(default="Calibri")
    footer_font_size_pt: int = PydanticField(default=9)
    title_space_after_pt: int = PydanticField(default=12)
    header_info_space_after_pt: int = PydanticField(default=10)
    instructions_title_space_after_pt: int = PydanticField(default=6)
    instructions_space_after_pt: int = PydanticField(default=12)
    question_space_after_pt: int = PydanticField(default=6)
    option_space_after_pt: int = PydanticField(default=3)
    option_indent_inches: float = PydanticField(default=0.25)
    option_image_indent_inches: float = PydanticField(default=0.5)
    image_width_inches_question: Optional[float] = PydanticField(default=3.0)
    image_width_inches_option: Optional[float] = PydanticField(default=2.0)
    alternative_labels: str = PydanticField(default="ABCDE")

    class Config:
        extra = 'ignore'

class AppConfigType(BaseModel):
    """ Modelo Pydantic para as configurações gerais da aplicação. """
    default_theme: str = PydanticField(default="System", description="Tema padrão da UI")
    default_ui_scaling: str = PydanticField(default="100%", description="Escala padrão da UI")
    db_path: str = PydanticField(default="diagprooff.db", description="Caminho para o banco de dados SQLite.")
    output_dir_base: str = PydanticField(default="ProvasGeradas", description="Diretório base para provas geradas.")
    media_files_base_dir: str = PydanticField(default="media_files", description="Diretório base para arquivos de mídia.")
    templates_base_dir: str = PydanticField(default="templates", description="Diretório base para templates.")
    log_level: str = PydanticField(default="INFO", description="Nível de logging (DEBUG, INFO, etc.).")
    format_options_default: FormatOptionsType = PydanticField(default_factory=FormatOptionsType, description="Opções de formatação padrão.")
    template_capa_prova_pdf: Optional[str] = PydanticField(default=None, description="Template PDF da folha de rosto.")
    template_prova_docx: Optional[str] = PydanticField(default=None, description="Template DOCX base da prova.")
    max_recent_files: PositiveInt = PydanticField(default=10)
    user_profile_id: Optional[str] = PydanticField(default=None)
    auto_save_interval_minutes: Optional[PositiveInt] = PydanticField(default=5)

    @field_validator('db_path', 'output_dir_base', 'media_files_base_dir', 'templates_base_dir', mode='before')
    @classmethod
    def resolve_paths_on_load(cls, value: str) -> str:
        if not value: return ""
        return value

    model_config = {
        "extra": 'ignore',
        "validate_assignment": True
    }


class UserSettingsType(BaseModel):
    """Configurações específicas do usuário."""
    theme: Optional[str] = PydanticField(default="System", description="Tema da UI escolhido pelo usuário.")
    language: Optional[str] = PydanticField(default="pt_BR", description="Idioma escolhido pelo usuário.")
    user_id: Optional[str] = PydanticField(default=None, description="ID do usuário logado, se houver.")
    show_tooltips: bool = PydanticField(default=True)

    model_config = {
        "extra": 'ignore',
        "validate_assignment": True
    }


class UserType(BaseModel):
    """Representa um usuário do sistema."""
    id: int
    username: str
    password_hash: Optional[str] = None
    role: str = "user"
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    created_at: DatetimeObject = PydanticField(default_factory=DatetimeObject.now)
    last_login_at: Optional[DatetimeObject] = None
    is_active: bool = True

    model_config = {
        "extra": 'ignore',
        "validate_assignment": True
    }


@dataclass
class FileReferenceType:
    file_name: str
    file_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    description: Optional[str] = None
    data_upload: DatetimeObject = field(default_factory=DatetimeObject.now)


# --- Modelos de Dados Principais ---

class TipoQuestao(str, Enum):
    MULTIPLA_ESCOLHA = "Múltipla Escolha"
    VERDADEIRO_FALSO = "Verdadeiro/Falso"
    DISCURSIVA = "Discursiva"
    PREENCHIMENTO_LACUNAS = "Preenchimento de Lacunas"

class NivelDificuldadeQuestao(str, Enum):
    MUITO_FACIL = "Muito Fácil"
    FACIL = "Fácil"
    MEDIO = "Médio"
    DIFICIL = "Difícil"
    MUITO_DIFICIL = "Muito Difícil"

class OpcaoMultiplaEscolha(BaseModel):
    id_opcao: uuid.UUID = PydanticField(default_factory=uuid.uuid4)
    letra: Optional[str] = None
    texto_opcao: Optional[str] = None
    texto_opcao_formatado: Optional[List[tuple]] = None  # <-- CAMPO NOVO!
    correta: bool = False
    feedback: Optional[str] = None
    imagem_path_opcao: Optional[str] = None
    imagem_ref: Optional[FileReferenceType] = None
    ordem_original: Optional[int] = None

    def __str__(self) -> str:
        return self.texto_opcao if self.texto_opcao is not None else ""

class DetalhesQuestaoDiscursiva(BaseModel):
    id_detalhe_discursiva: uuid.UUID = PydanticField(default_factory=uuid.uuid4)
    resposta_esperada_texto: Optional[str] = None
    palavras_chave_resposta: Optional[List[str]] = PydanticField(default_factory=list)
    numero_linhas_resposta: Optional[int] = None

class ItemVerdadeiroFalso(BaseModel):
    id_item_vf: uuid.UUID = PydanticField(default_factory=uuid.uuid4)
    afirmacao: str
    valor_correto: bool
    feedback_item: Optional[str] = None
    ordem: Optional[int] = None

@dataclass
class DisciplinaType:
    id_disciplina: str = field(default_factory=lambda: str(uuid.uuid4()))
    nome_disciplina: str = ""
    codigo_disciplina: Optional[str] = None
    descricao: Optional[str] = None

@dataclass
class ConteudoType:
    id_conteudo: str = field(default_factory=lambda: str(uuid.uuid4()))
    id_disciplina_pai: Optional[str] = None
    nome_conteudo: str = ""
    descricao: Optional[str] = None
    palavras_chave: List[str] = field(default_factory=list)


class TextoReferenciaType(BaseModel):
    id_texto_ref: str = PydanticField(default_factory=lambda: str(uuid.uuid4()))
    codigo_ref: str
    id_evento_origem: Optional[str] = None
    titulo: Optional[str] = None
    conteudo: Optional[str] = None
    tipo_conteudo: str = "texto"
    caminho_imagem_relativo: Optional[str] = None
    descricao_imagem: Optional[str] = None
    metadados_texto_ref: Dict[str, Any] = PydanticField(default_factory=dict)
    data_criacao: DatetimeObject = PydanticField(default_factory=DatetimeObject.now)
    data_modificacao: DatetimeObject = PydanticField(default_factory=DatetimeObject.now)
    conteudo_formatado: Optional[Union[Dict[str, Any], List[Any]]] = None


    @root_validator(pre=True)
    def validate_conteudo_formatado(cls, values):
        cf = values.get('conteudo_formatado')
        if cf is not None and not isinstance(cf, (dict, list)):
            values['conteudo_formatado'] = None
        return values


class QuestaoType(BaseModel):
    enunciado: str
    enunciado_formatado: Optional[List[tuple]] = None  # <-- Troque para lista de tuplas!
    id_questao: str = PydanticField(default_factory=lambda: f"Q{str(uuid.uuid4().int)[:3].upper()}{random.randint(100,999)}")
    tipo: TipoQuestao = TipoQuestao.MULTIPLA_ESCOLHA
    id_evento_origem: Optional[str] = None
    disciplina_banco: Optional[str] = None
    resposta_correta: Optional[str] = None
    gabarito_preliminar: Optional[str] = None
    gabarito_definitivo: Optional[str] = None
    nivel_dificuldade: Optional[NivelDificuldadeQuestao] = NivelDificuldadeQuestao.MEDIO
    tempo_esperado_resposta_segundos: Optional[PositiveInt] = None
    tags: Optional[List[str]] = PydanticField(default_factory=list)
    id_texto_ref_vinculado: Optional[str] = None
    texto_ref_direto_questao: Optional[str] = None
    status_revisao: Optional[str] = None
    justificativa_anulacao: Optional[str] = None
    criador_id: Optional[str] = None
    metadados_questao: Dict[str, Any] = PydanticField(default_factory=dict)
    opcoes: Optional[List[OpcaoMultiplaEscolha]] = PydanticField(default_factory=list)
    disciplina_id: Optional[str] = None
    conteudo_id: Optional[str] = None
    conteudo_nome: Optional[str] = None
    pontuacao: Optional[NonNegativeFloat] = 1.0
    detalhes_discursiva: Optional[DetalhesQuestaoDiscursiva] = None
    itens_verdadeiro_falso: Optional[List[ItemVerdadeiroFalso]] = PydanticField(default_factory=list)
    feedback_geral_questao: Optional[str] = None
    revisada: bool = False
    autor_elaborador: Optional[str] = None
    data_criacao: Optional[DatetimeObject] = PydanticField(default_factory=DatetimeObject.now)
    data_modificacao: Optional[DatetimeObject] = PydanticField(default_factory=DatetimeObject.now)
    numero_questao_original_docx: Optional[str] = None
    imagens_enunciado: List[Union[str, Any]] = PydanticField(default_factory=list)
    imagens_enunciado_refs: Optional[List[str]] = PydanticField(default_factory=list)
    textos_referencia_questao: Optional[List[str]] = PydanticField(default_factory=list)
    hash_conteudo_questao: Optional[str] = None
    fonte_questao: Optional[str] = None
    numero_questao_original: Optional[str] = None
    anulada: bool = PydanticField(default=False)
    justificativa_anulacao_recurso: Optional[str] = None
    justificativa_anulacao_recurso_formatado: Optional[List[tuple]] = None # <-- Troque para lista de tuplas!

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            uuid.UUID: lambda v: str(v),
            DatetimeObject: lambda v: v.isoformat() if v else None,
            DateObject: lambda v: v.isoformat() if v else None,
        }
    }

@dataclass
class BlocoQuestoesType:
    id_bloco: str = field(default_factory=lambda: str(uuid.uuid4()))
    titulo_bloco: Optional[str] = None
    instrucoes_bloco: Optional[str] = None
    disciplina_id_bloco: Optional[str] = None
    id_disciplina_base_fk: Optional[str] = None
    questoes: List['QuestaoType'] = field(default_factory=list)
    ordem_bloco: Optional[int] = None
    embaralhar_questoes_neste_bloco: Optional[bool] = None
    numero_questoes_sortear_do_bloco: Optional[int] = None
    nome_disciplina_prova: Optional[str] = None
    qtd_questoes: Optional[int] = None
    peso_questoes: Optional[float] = None
    conhecimento_basico: Optional[bool] = None
    agrupamento_banco: Optional[str] = None
    

@dataclass
class ConfiguracoesProvaType:
    id_config_prova: str = field(default_factory=lambda: str(uuid.uuid4()))
    embaralhar_questoes: bool = False
    embaralhar_alternativas: bool = False
    numero_variacoes_prova: int = 1
    instrucoes_gerais: Optional[str] = None
    texto_cabecalho_prova_docx: Optional[str] = None
    texto_cabecalho_prova_docx_corpo: Optional[str] = None
    incluir_folha_rascunho: bool = False
    tempo_total_prova_minutos: Optional[int] = None
    mostrar_pontuacao_questoes: bool = True
    template_pdf_folha_rosto: Optional[str] = None
    gerar_pdf_individual_com_folha_rosto: bool = False
    exportar_para_pdf: bool = True
    manter_arquivos_docx_individuais: bool = False
    criterio_aprovacao: Optional[str] = None
    permitir_consulta: bool = False
    format_options: FormatOptionsType = field(default_factory=FormatOptionsType)

# --- CORREÇÃO DEFINITIVA DA ORDEM DOS CAMPOS ---
@dataclass
class DisciplinaProvaType:
    nome_disciplina: str
    id_disciplina_prova: str = field(default_factory=lambda: str(uuid.uuid4()))
    id_cargo_fk: Optional[str] = None
    qtd_questoes: Optional[int] = None
    id_disciplina_base_fk: Optional[str] = None 
    peso_por_questao: Optional[float] = None
    observacoes: Optional[str] = None
    ordem_na_prova: Optional[int] = None
    disciplina_base_id: Optional[str] = None
    questoes_ids_selecionadas: List[str] = field(default_factory=list)


class CargoType(BaseModel):
    id_cargo: str = PydanticField(default_factory=lambda: str(uuid.uuid4()))
    id_evento: Optional[str] = None
    nome_cargo: str = ""
    codigo_cargo: Optional[str] = None
    nivel: Optional[str] = None
    turno: Optional[str] = None
    vagas: Optional[int] = None
    salario: Optional[NonNegativeFloat] = None
    requisitos: Optional[str] = None
    tem_discursiva: Optional[bool] = None
    letterhead_pdf_path: Optional[str] = None
    cover_pdf_paths: List[str] = PydanticField(default_factory=list)
    peso_total_prova: Optional[float] = None
    metadados_cargo: Dict[str, Any] = PydanticField(default_factory=dict)
    disciplinas_prova: Optional[List[DisciplinaProvaType]] = PydanticField(default_factory=list)
    provas_do_cargo_ids: List[str] = PydanticField(default_factory=list)
    data_criacao: datetime
    data_modificacao: datetime


@dataclass
class ProvaMontadaType:
    id_prova_montada: str
    id_evento: str
    id_cargo: str
    nome_prova_montada: str = "Nova Prova Montada"
    data_criacao: DatetimeObject = field(default_factory=DatetimeObject.now)
    data_modificacao: DatetimeObject = field(default_factory=DatetimeObject.now)
    observacoes: Optional[str] = None
    questoes_por_disciplina: Dict[str, List[QuestaoType]] = field(default_factory=dict)
    ordem_disciplinas_na_prova: List[str] = field(default_factory=list)
    metadados_prova: Dict[str, Any] = field(default_factory=dict)
    identificador_prova: Optional[str] = None
    responsavel_montagem: Optional[str] = None
    status_montagem: str = "Em Elaboração"
    titulo_prova: Optional[str] = None
    blocos_questoes: List[BlocoQuestoesType] = field(default_factory=list)
    textos_referencia_prova: List[TextoReferenciaType] = field(default_factory=list)
    configuracoes: ConfiguracoesProvaType = field(default_factory=ConfiguracoesProvaType)
    data_ultima_geracao: Optional[DatetimeObject] = None
    caminho_arquivo_gerado: Optional[str] = None
    hash_prova_gerada: Optional[str] = None
    frase_assinatura_folha_rosto: Optional[str] = None
    instrucoes_gerais: Optional[str] = None
    observacoes: Optional[str] = None
    data_ultima_geracao: Optional[DatetimeObject] = None
    caminho_arquivo_gerado: Optional[str] = None
    hash_prova_gerada: Optional[str] = None

        


class EventoType(BaseModel):
    id_evento: str = PydanticField(default_factory=lambda: str(uuid.uuid4()))
    nome_evento: str
    data_prova: Optional[Union[DateObject, str]] = None
    numero_edital: Optional[str] = None
    local_prova: Optional[str] = None
    instituicao_organizadora: Optional[str] = None
    logo_path: Optional[str] = None
    observacoes: Optional[str] = None
    status: str = PydanticField("Planejado")
    qtd_cargos_estimada: Optional[int] = None
    textos_referencia: Optional[Dict[str, 'TextoReferenciaType']] = PydanticField(default_factory=dict)
    cargos: Optional[List['CargoType']] = PydanticField(default_factory=list)
    provas_montadas: List[ProvaMontadaType] = PydanticField(default_factory=list)
    provas_montadas_por_cargo: Dict[str, ProvaMontadaType] = PydanticField(default_factory=dict)
    banco_questoes: Optional[Dict[str, List['QuestaoType']]] = PydanticField(default_factory=dict)
    questoes: List['QuestaoType'] = field(default_factory=list)
    data_criacao: Optional[DatetimeObject] = PydanticField(default_factory=DatetimeObject.now)
    data_modificacao: Optional[DatetimeObject] = PydanticField(default_factory=DatetimeObject.now)
    responsavel_criacao: Optional[str] = PydanticField(None)
    configuracoes_evento: Dict[str, Any] = PydanticField(default_factory=dict)
    nome_curto_evento: Optional[str] = PydanticField(None)
    identificador_unico_evento: Optional[str] = PydanticField(None)

    _logger: ClassVar[Optional[logging.Logger]] = None

    @classmethod
    def get_logger(cls) -> logging.Logger:
        if cls._logger is None:
            temp_logger_event = logging.getLogger(f"{__name__}.{cls.__name__}")
            try: 
                setup_logging(temp_logger_event) 
            except Exception as e_log_setup_event_cls:
                logging.basicConfig(level=logging.DEBUG)
                temp_logger_event.error(f"Falha ao configurar logger para EventoType: {e_log_setup_event_cls}", exc_info=True)
            cls._logger = temp_logger_event
        return cls._logger

    @field_validator('data_prova', 'data_criacao', 'data_modificacao', mode='before')
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[Union[DateObject, DatetimeObject]]:
        if value is None or isinstance(value, (DateObject, DatetimeObject)): return value
        if isinstance(value, str):
            try:
                return DatetimeObject.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                logger = EventoType.get_logger()
                logger.warning(f"Formato de data/datetime inválido '{value}' para EventoType, não pôde ser parseado.")
                return None
        return value

    class Config:
        validate_assignment = True
        extra = 'ignore'
        json_encoders = {
             uuid.UUID: lambda v: str(v),
             DatetimeObject: lambda v: v.isoformat() if v else None,
             DateObject: lambda v: v.isoformat() if v else None,
        }

@dataclass
class EventoSummaryType:
    id_evento: str
    nome_evento: str
    data_evento: Optional[str] = None # Alterado para str para corresponder ao DB
    status_evento: Optional[str] = None
    numero_edital: Optional[str] = None
    numero_cargos: int = 0
    numero_provas_montadas: int = 0

@dataclass
class MaterialEstudoType:
    nome: str
    tipo: str
    caminho_ou_link: str
    id_material: str = field(default_factory=lambda: str(uuid.uuid4()))
    cargo_id: Optional[str] = None
    descricao: Optional[str] = None
    disciplinas_associadas: List[str] = field(default_factory=list)
    data_adicao: DatetimeObject = field(default_factory=DatetimeObject.now)

class TipoProva(str, Enum):
    TIPO_A = "Tipo A"
    TIPO_B = "Tipo B"
    TIPO_C = "Tipo C"
    TIPO_D = "Tipo D"
    TIPO_E = "Tipo E"

    @classmethod
    def get_ordered_list(cls) -> List[str]:
        return [member.value for member in cls]

    @classmethod
    def get_display_name(cls, tag_value: str) -> str:
        return tag_value

@dataclass
class IteraveisParaProvaType:
    id_iteravel: str
    nome_display: str
    dados_especificos: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CandidatoType:
    id_candidato: str
    nome_completo: str
    cpf: Optional[str] = None
    email: Optional[EmailStr] = None
    data_nascimento: Optional[DateObject] = None
    telefone: Optional[str] = None
    cargo_inscrito_id: Optional[str] = None
    tipo_prova_atribuido: Optional[str] = None
    local_sala_prova: Optional[str] = None
    necessidades_especiais: List[str] = field(default_factory=list)
    dados_adicionais_candidato: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RespostaQuestaoProvaType:
    id_candidato: str
    id_questao_original: str
    numero_questao_na_prova: int
    id_resposta: str = field(default_factory=lambda: str(uuid.uuid4()))
    id_prova_aplicada: Optional[str] = None
    resposta_alternativa_selecionada_id: Optional[str] = None
    resposta_alternativa_selecionada_letra: Optional[str] = None
    resposta_texto_discursivo: Optional[str] = None
    respostas_verdadeiro_falso: Optional[List[Dict[str, bool]]] = None
    correta: Optional[bool] = None
    pontuacao_obtida: Optional[float] = None
    tempo_resposta_seg: Optional[int] = None
    data_hora_resposta: DatetimeObject = field(default_factory=DatetimeObject.now)
    justificativa_correcao_manual: Optional[str] = None

    class Meta:
        table_name = "respostas_questoes_provas"

if __name__ == '__main__':
    try:
        logger_elements.info("Teste de logging em elements.py iniciado.")

        # O seu bloco de testes __main__ permanece aqui, inalterado.
        
    except Exception as e_elements_test:
        logger_elements.error(f"Erro nos testes de elements.py: {e_elements_test}", exc_info=True)

@dataclass
class BancoFrasesType:
    """
    Representa uma única frase do banco de dados.
    """
    id: int
    categoria: str
    texto_frase: str
    ativo: bool
    identificador: str

    # O Pydantic ou dataclasses podem lidar com campos extras que não são definidos
    # mas para dataclass é mais limpo se você souber que não haverá campos extras.
    # Se o banco de dados puder retornar colunas extras que você deseja ignorar,
    # esta classe funcionará bem, pois o FraseManager usa **dict(row)
    # e o construtor do dataclass só pegará os campos que ele conhece.

