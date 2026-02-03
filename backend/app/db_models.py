# backend/app/db_models.py (VERSÃO FINAL COM RELACIONAMENTOS)

from sqlalchemy import Column, Integer, String, ForeignKey, Text, BOOLEAN, TIMESTAMP, REAL, UniqueConstraint, DateTime, Boolean, Date, Float, JSON
from sqlalchemy.orm import declarative_base, relationship # Importe o relationship
from backend.app.database import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, date

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime)
    responsible_name = Column(String, nullable=True)
    responsible_email = Column(String, nullable=True)
    responsible_phone = Column(String, nullable=True)
    plan_type = Column(String, nullable=True)
    plan_expires_at = Column(DateTime, nullable=True)
    tenant_type = Column(String, nullable=False, default="empresa_concurso")  
    users = relationship("User", back_populates="tenant")
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    role = Column(String)
    email = Column(Text, unique=True)
    full_name = Column(Text, nullable=True)
    cpf = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    department = Column(Text, nullable=True)
    institution = Column(Text, nullable=True)
    birth_date = Column(Text, nullable=True)  # formato YYYY-MM-DD
    status = Column(String, nullable=True)    # "ativo" ou "inativo"
    notes = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)  # URL ou caminho da foto
    specialty = Column(Text, nullable=True)
    pix_key = Column(Text, nullable=True)
    banco = Column(Text, nullable=True)              # <--- NOVO
    agencia = Column(Text, nullable=True)            # <--- NOVO
    conta_corrente = Column(Text, nullable=True)     # <--- NOVO
    is_active = Column(Boolean, default=True)
    terms_acceptance = Column(Text, nullable=True)
    tenant = relationship("Tenant", back_populates="users")

class AuditLogGeracao(Base):
    __tablename__ = "audit_log_geracao"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # <-- ESSA LINHA CORRIGE!
    timestamp = Column(DateTime, nullable=False)
    usuario = Column(String, nullable=False)
    evento = Column(String)
    cargo = Column(String)
    acao = Column(String)
    parametros = Column(Text)
    frases = Column(Text)
    seed = Column(String)
    ip = Column(String)
    user_agent = Column(String)

    tenant = relationship("Tenant")

class Evento(Base):
    __tablename__ = "Eventos"

    id_evento = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)  
    nome_evento = Column(String, nullable=False)
    data_prova = Column(Date, nullable=False)
    status = Column(String, nullable=False)
    numero_edital = Column(String, nullable=True)
    senha_evento = Column(String, nullable=False)
    senha_evento_cripto = Column(Text, nullable=True)
    local_prova = Column(String, nullable=True)
    observacoes = Column(Text, nullable=True)
    qtd_cargos = Column(Integer, nullable=False, default=1) 
    identificador_evento = Column(String, unique=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, default=None, nullable=True)

    cargos = relationship("Cargo", back_populates="evento")

class Cargo(Base):
    __tablename__ = "Cargos"
    id_cargo = Column(Text, primary_key=True)
    identificador_cargo = Column(Text, unique=True, nullable=True)  # <-- ADICIONE ESTA LINHA!
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    id_evento_fk = Column(Text, ForeignKey("Eventos.id_evento"))
    nome_cargo = Column(Text, nullable=False)
    codigo_cargo = Column(Text, nullable=True)
    nivel = Column(Text, nullable=True)
    turno = Column(Text, nullable=True)
    vagas = Column(Integer, nullable=True)
    salario = Column(Float, nullable=True)
    requisitos = Column(Text, nullable=True)
    tem_discursiva = Column(Boolean, default=False)
    letterhead_pdf_path = Column(Text, nullable=True)
    cover_pdf_paths = Column(JSON, default=[])
    peso_total_prova = Column(Float, nullable=True)
    disciplinas_relacionadas = relationship("DisciplinaDaProva", back_populates="cargo")
    evento = relationship("Evento", back_populates="cargos")
    tenant = relationship("Tenant")

class DisciplinaDaProva(Base):
    __tablename__ = "DisciplinasDaProva"
    id_disciplina_prova = Column(Text, primary_key=True)
    id_cargo_fk = Column(Text, ForeignKey("Cargos.id_cargo"))
    id_disciplina_base_fk = Column(Text, ForeignKey("Disciplinas.id_disciplina"))  # <-- CORRIGIDO!
    nome_disciplina_na_prova = Column(Text, nullable=False)
    qtd_questoes = Column(Integer, nullable=True)
    peso_por_questao = Column(Float, nullable=True)
    tipo_conhecimento = Column(String, default="comum")
    observacoes = Column(Text, nullable=True)
    ordem_na_prova = Column(Integer, nullable=True)
    tenant_id = Column(Integer, nullable=True)

    cargo = relationship("Cargo", back_populates="disciplinas_relacionadas")
    disciplina_base = relationship("Disciplina", back_populates="provas_relacionadas")

class Disciplina(Base):
    __tablename__ = "Disciplinas"
    id_disciplina = Column(Text, primary_key=True)
    id_evento_fk = Column(Text, ForeignKey("Eventos.id_evento"), nullable=True)
    nome_disciplina = Column(Text, nullable=False)
    codigo_disciplina = Column(Text, nullable=True)
    descricao = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # <-- ADICIONE ESTA LINHA!

    provas_relacionadas = relationship("DisciplinaDaProva", back_populates="disciplina_base")

class ProvaMontada(Base):
    __tablename__ = "ProvasMontadas"
    id_prova_montada = Column(String, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    id_evento_fk = Column(String, ForeignKey("Eventos.id_evento"))
    id_cargo_fk = Column(String, ForeignKey("Cargos.id_cargo"))
    nome_prova_montada = Column(String, nullable=False)
    identificador_prova = Column(String)
    titulo_prova = Column(String)
    status_montagem = Column(String)
    responsavel_montagem = Column(String)
    data_criacao = Column(DateTime)
    data_modificacao = Column(DateTime)
    blocos_questoes = Column(JSON, nullable=True)  # <--- Adicione este campo!
    metadados_prova = Column(JSON, nullable=True)
    textos_referencia_prova_json = Column(Text, nullable=True)
    tenant = relationship("Tenant")
    
    def __repr__(self):
        return f"<ProvaMontada(id={self.id_prova_montada}, nome='{self.nome_prova_montada}')>"

class BancoFrases(Base):
    __tablename__ = 'banco_frases'
    id = Column(Integer, primary_key=True)
    id_local = Column(Integer, nullable=False)  # <-- Novo campo!
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    categoria = Column(Text, nullable=False)
    texto_frase = Column(Text, nullable=False)  # <-- minúsculo!
    ativo = Column(BOOLEAN, nullable=False)
    identificador = Column(Text, nullable=True)
    tenant = relationship("Tenant")

    __table_args__ = (
        UniqueConstraint('categoria', 'texto_frase', name='_categoria_texto_frase_uc'),  # <-- minúsculo!
    )

    def __repr__(self):
        return f"<BancoFrases(id={self.id}, categoria='{self.categoria}')>"

class QuestoesBanco(Base):
    __tablename__ = "QuestoesBanco"

    id_questao = Column(String, primary_key=True)
    codigo_curto_questao = Column(String, unique=True, nullable=True)
    id_evento_fk = Column(String, ForeignKey("Eventos.id_evento"))
    enunciado = Column(Text, nullable=True)
    enunciado_formatado = Column(Text, nullable=True)
    indicacao_conteudo = Column(Text, nullable=True)
    tipo = Column(String, nullable=True)
    disciplina_banco = Column(String, nullable=True)
    resposta_correta = Column(String, nullable=True)
    gabarito_preliminar = Column(String, nullable=True)
    gabarito_definitivo = Column(String, nullable=True)
    nivel_dificuldade = Column(String, nullable=True)
    tempo_esperado_resposta_segundos = Column(Integer, nullable=True)
    tags_keywords = Column(Text, nullable=True)
    texto_referencia_vinculo = Column(String, nullable=True)
    texto_referencia_direto = Column(String, nullable=True)
    id_texto_ref_vinculado = Column(String, nullable=True)
    status_revisao = Column(String, nullable=True)
    justificativa_anulacao = Column(Text, nullable=True)
    criador_id = Column(String, nullable=True)
    metadados_questao = Column(Text, nullable=True)
    disciplina_id = Column(String, nullable=True)
    conteudo_id = Column(String, nullable=True)
    conteudo_nome = Column(Text, nullable=True)
    pontuacao = Column(Float, nullable=True)
    feedback_geral_questao = Column(Text, nullable=True)
    justificativa_questao = Column(String, nullable=True)
    revisada = Column(Boolean, nullable=True)
    autor_elaborador = Column(Text, nullable=True)
    data_criacao = Column(DateTime, default=datetime.now)
    data_modificacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    numero_questao_original_docx = Column(Text, nullable=True)
    hash_conteudo_questao = Column(Text, nullable=True)
    fonte_questao = Column(Text, nullable=True)
    anulada = Column(Boolean, nullable=True)
    justificativa_anulacao_recurso = Column(Text, nullable=True)
    justificativa_anulacao_recurso_formatado = Column(Text, nullable=True)
    imagens_enunciado = Column(Text, nullable=True)
    imagens_enunciado_refs = Column(Text, nullable=True)
    caminho_imagem_justificativa = Column(Text, nullable=True)
    textos_referencia_questao = Column(Text, nullable=True)
    caminho_imagem_relativo = Column(Text, nullable=True)
    status_revisao = Column(String, nullable=True)
    observacao_revisor = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    # Relacionamentos (exemplo, ajuste conforme os nomes das classes/modelos)
    tenant = relationship("Tenant")
    evento = relationship("Evento", backref="questoes", foreign_keys=[id_evento_fk])

    def __repr__(self):
        return f"<QuestoesBanco(id_questao={self.id_questao}, tipo={self.tipo})>"

class OpcoesQuestao(Base):
    __tablename__ = "OpcoesQuestao"

    id_opcao_questao = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_questao_fk = Column(String, ForeignKey("QuestoesBanco.id_questao", ondelete="CASCADE"), nullable=False)
    letra = Column(String, nullable=True)
    texto_opcao = Column(Text, nullable=True)
    texto_opcao_formatado = Column(Text, nullable=True)
    ordem_original = Column(Integer, nullable=True)
    correta = Column(Boolean, default=False)
    feedback_opcao = Column(Text, nullable=True)
    imagem_path_opcao = Column(Text, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    questao = relationship("QuestoesBanco", backref="opcoes")

# Itens de verdadeiro/falso (certo/errado)
class ItensVerdadeiroFalso(Base):
    __tablename__ = "ItensVerdadeiroFalso"

    id_item_vf = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_questao_fk = Column(String, ForeignKey("QuestoesBanco.id_questao", ondelete="CASCADE"), nullable=False)
    afirmacao = Column(Text, nullable=False)
    valor_correto = Column(Boolean, nullable=False)
    feedback_item = Column(Text, nullable=True)
    ordem = Column(Integer, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    questao = relationship("QuestoesBanco", backref="itens_vf")

# Detalhes de questões discursivas
class DetalhesQuestaoDiscursiva(Base):
    __tablename__ = "DetalhesQuestaoDiscursiva"
    id_detalhe_discursiva = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_questao_fk = Column(String, ForeignKey("QuestoesBanco.id_questao", ondelete="CASCADE"), nullable=False, unique=True)
    resposta_esperada_texto = Column(Text, nullable=True)
    palavras_chave_resposta = Column(Text, nullable=True) # Salve como JSON string
    numero_linhas_resposta = Column(Integer, nullable=True)
    texto_subjetivo_orientacao = Column(Text, nullable=True)    # Para subjetiva
    texto_subjetivo_nota_maxima = Column(Text, nullable=True)   # Para subjetiva
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    questao = relationship("QuestoesBanco", backref="detalhes_discursiva")

  
class Company(Base):
    __tablename__ = "company_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    company_name = Column(String, nullable=False, default="")
    company_cnpj = Column(String, nullable=False, default="")
    company_address = Column(String, nullable=False, default="")
    company_phone = Column(String, nullable=False, default="")
    company_email = Column(String, nullable=False, default="")
    company_website = Column(String, nullable=False, default="")
    company_logo_path = Column(String, nullable=False, default="")

    tenant = relationship("Tenant")

class Conteudo(Base):
    __tablename__ = 'conteudos'
    id_conteudo = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identificador_conteudo = Column(String, unique=True, nullable=True)  # NOVO!
    nome_conteudo = Column(String, nullable=False)
    descricao = Column(Text)
    disciplina = Column(String)
    id_disciplina_fk = Column(String, nullable=True)
    turno = Column(String)
    nivel = Column(String)
    professor_id = Column(String)
    area_conhecimento = Column(String)
    conteudo_pai_id = Column(String)
    evento_id = Column(String, nullable=False)
    is_deleted = Column(Boolean, default=False)
    metadados = Column(JSON, nullable=True, default=dict)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)  # NOVO!
    respondidas = Column(Integer, nullable=False, default=0)  # NOVO!
    quantidade = Column(Integer, nullable=False, default=0)    # Total de questões

class TextoReferenciaGeral(Base):
    __tablename__ = "TextosReferenciaGeral"
    id_texto_ref = Column(String, primary_key=True)
    id_evento_fk = Column(String, ForeignKey("Eventos.id_evento"))
    id_conteudo_fk = Column(String, ForeignKey("conteudos.id_conteudo"), nullable=False)  # Vínculo correto!
    codigo_ref = Column(String)  # Código amigável do texto de referência
    titulo = Column(String, nullable=True)
    conteudo = Column(Text)
    tipo_conteudo = Column(String)
    legenda_texto = Column(String)
    descricao_imagem = Column(String)
    fonte_imagem = Column(String)
    tags_imagem = Column(Text)
    licenca_imagem = Column(String)
    caminho_imagem_relativo = Column(String)
    observacoes = Column(Text)
    ativo = Column(Boolean, default=True)
    publico = Column(Boolean, default=True)
    metadados_texto_ref = Column(Text)
    questoes_vinculo = Column(Text)
    conteudo_formatado = Column(Text)
    data_criacao = Column(String)
    data_modificacao = Column(String)
    tenant_id = Column(Integer, nullable=True)

class HistoricoRevisaoQuestao(Base):
    __tablename__ = "HistoricoRevisaoQuestao"
    id = Column(String, primary_key=True)  # UUID
    id_questao_fk = Column(String, ForeignKey("QuestoesBanco.id_questao"), nullable=False)
    usuario_revisor = Column(String, nullable=False)
    data_revisao = Column(DateTime, default=datetime.now)
    status_revisao = Column(String, nullable=False)
    observacao_revisor = Column(Text)
    dados_revisao = Column(Text)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    questao = relationship("QuestoesBanco", backref="historico_revisoes")
    tenant = relationship("Tenant")