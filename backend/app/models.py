# backend/app/models.py (VERSÃO FINAL COMPLETA)

from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict, Any
from datetime import datetime, date

class Tenant(BaseModel):
    id: int
    name: str
    domain: str
    status: str
    tenant_type: str  # <-- Adicionado!
    created_at: datetime | None = None
    responsible_name: Optional[str] = None
    responsible_email: Optional[str] = None
    responsible_phone: Optional[str] = None
    plan_type: Optional[str] = None
    plan_expires_at: Optional[datetime] = None  # <-- Corrigido aqui!

    class Config:
        from_attributes = True

class TenantCreate(BaseModel):
    name: str
    domain: str
    status: str
    tenant_type: str
    responsible_name: Optional[str] = None
    responsible_email: Optional[str] = None
    responsible_phone: Optional[str] = None
    plan_type: Optional[str] = None
    plan_expires_at: Optional[str] = None 

    class Config:
        from_attributes = True

class TenantDashboard(BaseModel):
    id: int
    name: str
    domain: str
    status: str
    tenant_type: str  # <-- Adicionado!
    created_at: Optional[str]
    responsible_name: Optional[str]
    responsible_email: Optional[str]
    responsible_phone: Optional[str]
    plan_type: Optional[str]
    plan_expires_at: Optional[str]
    users_total: int
    users_by_role: dict
    questions_total: int
    exams_total: int
    events_total: int
    cargos_total: int
    frases_total: int
    admins_total: int
    blocked_users_total: int
    accesses_total_month: int
    last_access: Optional[str]
    percent_users_active: float
    percent_users_inactive: float
    avg_questions_per_exam: float
    avg_access_time_per_user: float
    recent_activities: list

    class Config:
        from_attributes = True

from datetime import datetime
from typing import Optional

class AuditLogGeracaoCreate(BaseModel):
    evento: Optional[str] = None
    cargo: Optional[str] = None
    acao: Optional[str] = None
    parametros: Optional[str] = None
    frases: Optional[str] = None
    seed: Optional[str] = None

class AuditLogGeracaoOut(BaseModel):
    id: int
    tenant_id: int
    timestamp: datetime
    usuario: str
    evento: Optional[str]
    cargo: Optional[str]
    acao: Optional[str]
    parametros: Optional[str]
    frases: Optional[str]
    seed: Optional[str]
    ip: Optional[str]
    user_agent: Optional[str]

    class Config:
        from_attributes = True

class Disciplina(BaseModel):
    id_disciplina: str
    id_evento_fk: Optional[str] = None
    nome_disciplina_na_prova: str
    codigo_disciplina: Optional[str] = None
    descricao: Optional[str] = None
    tenant_id: int   # <-- ESSENCIAL para multi-tenant!

    class Config:
        from_attributes = True

class DisciplinaProva(BaseModel):
    nome_disciplina: str = Field(..., alias="nome_disciplina_na_prova")
    qtd_questoes: int
    tipo_conhecimento: Optional[str] = "comum"
    peso_por_questao: float
    ordem_na_prova: int

    class Config:
        from_attributes = True

class Cargo(BaseModel):
    id_cargo: Optional[str] = None
    identificador_cargo: Optional[str] = None
    nome_cargo: str
    codigo_cargo: Optional[str] = None
    nivel: Optional[str] = None
    turno: Optional[str] = None
    vagas: Optional[int] = None
    salario: Optional[float] = None
    requisitos: Optional[str] = None
    tem_discursiva: Optional[bool] = None
    letterhead_pdf_path: Optional[str] = None
    cover_pdf_paths: Optional[List[str]] = Field(default=[])
    peso_total_prova: Optional[float] = None
    disciplinas_prova: List[DisciplinaProva] = Field(default=[])

    class Config:
        from_attributes = True

class CargoOut(BaseModel):
    id_cargo: str
    identificador_cargo: Optional[str] = None
    nome_cargo: str
    tenant_id: Optional[int] = None

    class Config:
        from_attributes = True  # <-- CORRETO para Pydantic v2+

# MODELO PARA CRIAÇÃO DE EVENTO (entrada do POST)
class EventoCreate(BaseModel):
    tenant_id: int  # Adicionado!
    nome_evento: str
    data_prova: date
    status: str
    numero_edital: Optional[str] = None
    senha_evento: str
    local_prova: Optional[str] = None
    observacoes: Optional[str] = None
    qtd_cargos: int
    identificador_evento: Optional[str] = None 
    senha_evento_cripto: Optional[str] = None 

class EventoUpdate(BaseModel):
    tenant_id: Optional[str] = None
    nome_evento: Optional[str] = None
    data_prova: Optional[date] = None
    status: Optional[str] = None
    numero_edital: Optional[str] = None
    senha_evento: Optional[str] = None
    local_prova: Optional[str] = None
    observacoes: Optional[str] = None
    qtd_cargos: Optional[int] = None

    class Config:
        from_attributes = True

class EventoOut(BaseModel):
    id_evento: str
    tenant_id: int
    nome_evento: str
    data_prova: date
    status: str
    numero_edital: Optional[str] = None
    local_prova: Optional[str] = None
    observacoes: Optional[str] = None
    cargos: List[CargoOut] = []
    qtd_cargos: int
    identificador_evento: str
    

    class Config:
        from_attributes = True  # <-- Troque aqui!
    

class User(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    institution: Optional[str] = None
    birth_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    specialty: Optional[str] = None
    pix_key: Optional[str] = None
    banco: Optional[str] = None           # <--- NOVO
    agencia: Optional[str] = None         # <--- NOVO
    conta_corrente: Optional[str] = None  # <--- NOVO
    terms_acceptance: Optional[str] = None
    role: str
    tenant_id: Optional[int] = None

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str
    tenant_id: int
    full_name: Optional[str] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    institution: Optional[str] = None
    birth_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    specialty: Optional[str] = None
    pix_key: Optional[str] = None
    banco: Optional[str] = None           # <--- NOVO
    agencia: Optional[str] = None         # <--- NOVO
    conta_corrente: Optional[str] = None  # <--- NOVO

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[int] = None
    full_name: Optional[str] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    institution: Optional[str] = None
    birth_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    specialty: Optional[str] = None
    pix_key: Optional[str] = None
    banco: Optional[str] = None           # <--- NOVO
    agencia: Optional[str] = None         # <--- NOVO
    conta_corrente: Optional[str] = None  # <--- NOVO

    class Config:
        from_attributes = True

class Frase(BaseModel):
    id: int
    id_local: int
    categoria: str
    texto_frase: str
    tenant_id: int
    ativo: bool
    identificador: Optional[str] = None

    class Config:
        from_attributes = True

class FraseCreate(BaseModel):
    categoria: str
    texto_frase: str
    tenant_id: int  # OBRIGATÓRIO

    class Config:
        from_attributes = True

class Company(BaseModel):
    id: int
    tenant_id: int
    company_name: str
    company_cnpj: str
    company_address: str
    company_phone: str
    company_email: str
    company_website: str
    company_logo_path: str

    class Config:
        orm_mode = True

class ConteudoCreate(BaseModel):
    nome_conteudo: str
    descricao: Optional[str] = ""
    id_disciplina_fk: Optional[str] = None
    disciplina: Optional[str] = None
    area_conhecimento: Optional[str] = None
    conteudo_pai_id: Optional[str] = None
    evento_id: str
    tenant_id: int  # NOVO!
    quantidade: int = 0  # NOVO!
    respondidas: int = 0          # respondidas
    turno: Optional[str] = None  # garantir que é enviado!
    nivel: Optional[str] = None
    metadados: Optional[Dict[str, Any]] = {}
    professor_id: Optional[str] = None

class ConteudoOut(BaseModel):
    id_conteudo: str
    identificador_conteudo: Optional[str] = None  # NOVO!
    nome_conteudo: str
    descricao: Optional[str] = ""
    disciplina: Optional[str] = None
    area_conhecimento: Optional[str] = None
    conteudo_pai_id: Optional[str] = None
    evento_id: str
    tenant_id: int
    quantidade: int = 0  # NOVO!
    respondidas: int = 0          # respondidas
    turno: Optional[str] = None
    nivel: Optional[str] = None
    is_deleted: bool = False
    metadados: Optional[Dict[str, Any]] = {}
    filhos: List["ConteudoOut"] = Field(default_factory=list)
    professor_id: Optional[str] = None

    model_config = dict(from_attributes=True)

class TextoReferenciaCreate(BaseModel):
    titulo: Optional[str] = None
    conteudo: Optional[str] = None
    tipo_conteudo: Optional[str] = None
    codigo_ref: Optional[str] = None
    legenda_texto: Optional[str] = None
    descricao_imagem: Optional[str] = None
    fonte_imagem: Optional[str] = None
    tags_imagem: Optional[List[str]] = None
    licenca_imagem: Optional[str] = None
    caminho_imagem_relativo: Optional[str] = None
    observacoes: Optional[str] = None
    ativo: Optional[bool] = True
    publico: Optional[bool] = True
    metadados_texto_ref: Optional[dict] = None
    questoes_vinculo: Optional[List[str]] = None
    evento_id: str
    conteudo_id: str
    tenant_id: int

class TextoReferenciaOut(TextoReferenciaCreate):
    id_texto_ref: str

class QuestaoOut(BaseModel):
    id_questao: str
    codigo_curto_questao: Optional[str] = None
    id_evento_fk: Optional[str] = None
    indicacao_conteudo: Optional[str] = None
    enunciado: Optional[str] = None
    enunciado_formatado: Optional[str] = None
    tipo: Optional[str] = None
    disciplina_banco: Optional[str] = None
    resposta_correta: Optional[str] = None
    gabarito_preliminar: Optional[str] = None
    gabarito_definitivo: Optional[str] = None
    nivel_dificuldade: Optional[str] = None
    tempo_esperado_resposta_segundos: Optional[int] = None
    tags_keywords: Optional[str] = None
    texto_referencia_vinculo: Optional[str] = None
    texto_referencia_direto: Optional[str] = None
    id_texto_ref_vinculado: Optional[str] = None
    status_revisao: Optional[str] = None
    observacao_revisor: Optional[str] = None 
    justificativa_anulacao: Optional[str] = None
    criador_id: Optional[str] = None
    metadados_questao: Optional[str] = None
    disciplina_id: Optional[str] = None
    conteudo_id: Optional[str] = None
    conteudo_nome: Optional[str] = None
    pontuacao: Optional[float] = None
    feedback_geral_questao: Optional[str] = None
    revisada: Optional[bool] = None
    autor_elaborador: Optional[str] = None
    data_criacao: Optional[datetime] = None
    data_modificacao: Optional[datetime] = None
    numero_questao_original_docx: Optional[str] = None
    hash_conteudo_questao: Optional[str] = None
    fonte_questao: Optional[str] = None
    anulada: Optional[bool] = None
    justificativa_anulacao_recurso: Optional[str] = None
    justificativa_anulacao_recurso_formatado: Optional[str] = None
    imagens_enunciado: Optional[str] = None
    imagens_enunciado_refs: Optional[str] = None
    caminho_imagem_relativo: Optional[str] = None
    textos_referencia_questao: Optional[str] = None
    tenant_id: Optional[int] = None

    # CAMPOS QUE DEVEM SER ADICIONADOS:
    alternativas: Optional[List['OpcaoQuestao']] = []
    itens_vf: Optional[List['ItemVerdadeiroFalso']] = []
    detalhes_discursiva: Optional['DetalhesQuestaoDiscursiva'] = None
    tags: Optional[List[str]] = []

    class Config:
        from_attributes = True

class OpcaoQuestao(BaseModel):
    id_opcao_questao: Optional[str]
    id_questao_fk: Optional[str]
    letra: Optional[str]
    texto_opcao: Optional[str]
    texto_opcao_formatado: Optional[str]
    ordem_original: Optional[int]
    correta: bool = False
    feedback_opcao: Optional[str]
    imagem_path_opcao: Optional[str]

    class Config:
        from_attributes = True

class ItemVerdadeiroFalso(BaseModel):
    id_item_vf: Optional[str]
    id_questao_fk: Optional[str]
    afirmacao: str
    valor_correto: bool
    feedback_item: Optional[str] = None
    ordem: Optional[int] = None

    class Config:
        from_attributes = True

class DetalhesQuestaoDiscursiva(BaseModel):
    id_detalhe_discursiva: Optional[str]
    id_questao_fk: Optional[str]
    resposta_esperada_texto: Optional[str] = None
    palavras_chave_resposta: Optional[List[str]] = Field(default_factory=list)
    numero_linhas_resposta: Optional[int] = None
    texto_subjetivo_orientacao: Optional[str] = None
    texto_subjetivo_nota_maxima: Optional[str] = None

    class Config:
        from_attributes = True

class BlocoQuestao(BaseModel):
    id_bloco: str
    nome_disciplina: str
    qtd_questoes: int
    peso: float
    ordem: int
    conhecimento_basico: bool

    class Config:
        from_attributes = True

class ProvaMontada(BaseModel):
    nome_prova_montada: str
    blocos_questoes: List[BlocoQuestao]

    class Config:
        from_attributes = True