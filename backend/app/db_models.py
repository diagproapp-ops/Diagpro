# backend/app/db_models.py (VERSÃO FINAL COM RELACIONAMENTOS)

from sqlalchemy import Column, Integer, String, ForeignKey, Text, BOOLEAN, TIMESTAMP, REAL, UniqueConstraint, DateTime, Boolean, Date, Float, JSON
from sqlalchemy.orm import relationship
from backend.app.database import Base
from backend.app.field_crypto import Ciphertext, install_orm_encryption
import uuid
from datetime import datetime, date

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(Ciphertext, nullable=False)
    domain = Column(Ciphertext, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime)
    responsible_name = Column(Ciphertext, nullable=True)
    responsible_email = Column(Ciphertext, nullable=True)
    responsible_phone = Column(Ciphertext, nullable=True)
    plan_type = Column(String, nullable=True)
    plan_expires_at = Column(DateTime, nullable=True)
    tenant_type = Column(String, nullable=False, default="empresa_concurso")  
    name_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    domain_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    users = relationship("User", back_populates="tenant")
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(Ciphertext, nullable=False)
    password_hash = Column(Text, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    role = Column(String)
    email = Column(Ciphertext)
    full_name = Column(Ciphertext, nullable=True)
    cpf = Column(Ciphertext, nullable=True)
    phone = Column(Ciphertext, nullable=True)
    department = Column(Ciphertext, nullable=True)
    institution = Column(Ciphertext, nullable=True)
    birth_date = Column(Ciphertext, nullable=True)  # formato YYYY-MM-DD
    status = Column(String, nullable=True)    # "ativo" ou "inativo"
    notes = Column(Ciphertext, nullable=True)
    address = Column(Ciphertext, nullable=True)
    avatar_url = Column(Ciphertext, nullable=True)  # URL ou caminho da foto
    specialty = Column(Ciphertext, nullable=True)
    pix_key = Column(Ciphertext, nullable=True)
    banco = Column(Ciphertext, nullable=True)              # <--- NOVO
    agencia = Column(Ciphertext, nullable=True)            # <--- NOVO
    conta_corrente = Column(Ciphertext, nullable=True)     # <--- NOVO
    is_active = Column(Boolean, default=True)
    terms_acceptance = Column(Ciphertext, nullable=True)
    username_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    email_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    full_name_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    tenant = relationship("Tenant", back_populates="users")

    __table_args__ = (
        UniqueConstraint('username_bidx', name='uq_users_username_bidx'),
        UniqueConstraint('email_bidx', name='uq_users_email_bidx'),
    )

class AuditLogGeracao(Base):
    __tablename__ = "audit_log_geracao"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)  # <-- ESSA LINHA CORRIGE!
    timestamp = Column(DateTime, nullable=False)
    usuario = Column(Ciphertext, nullable=False)
    evento = Column(Ciphertext)
    cargo = Column(Ciphertext)
    acao = Column(String)
    parametros = Column(Ciphertext)
    frases = Column(Ciphertext)
    seed = Column(Ciphertext)
    ip = Column(Ciphertext)
    user_agent = Column(Ciphertext)
    usuario_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    evento_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    cargo_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)

    tenant = relationship("Tenant")

class Evento(Base):
    __tablename__ = "Eventos"
    __table_args__ = (UniqueConstraint('tenant_id', 'identificador_evento', name='uq_eventos_tenant_identificador_evento'),)

    id_evento = Column(String, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    nome_evento = Column(Ciphertext, nullable=False)
    data_prova = Column(Date, nullable=False)
    status = Column(String, nullable=False)
    numero_edital = Column(Ciphertext, nullable=True)
    senha_evento = Column(String, nullable=False)
    senha_evento_cripto = Column(Ciphertext, nullable=True)
    local_prova = Column(Ciphertext, nullable=True)
    observacoes = Column(Ciphertext, nullable=True)
    qtd_cargos = Column(Integer, nullable=False, default=1) 
    identificador_evento = Column(String, nullable=False)  # único por cliente (ver __table_args__)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, default=None, nullable=True)

    cargos = relationship("Cargo", back_populates="evento")

class Cargo(Base):
    __tablename__ = "Cargos"
    __table_args__ = (UniqueConstraint('tenant_id', 'identificador_cargo', name='uq_cargos_tenant_identificador_cargo'),)
    id_cargo = Column(Text, primary_key=True)
    identificador_cargo = Column(Text, nullable=True)  # único por cliente (ver __table_args__)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id_evento_fk = Column(Text, ForeignKey("Eventos.id_evento"))
    nome_cargo = Column(Ciphertext, nullable=False)
    codigo_cargo = Column(Text, nullable=True)
    nivel = Column(Ciphertext, nullable=True)
    turno = Column(Ciphertext, nullable=True)
    vagas = Column(Integer, nullable=True)
    salario = Column(Float, nullable=True)
    requisitos = Column(Ciphertext, nullable=True)
    tem_discursiva = Column(Boolean, default=False)
    letterhead_pdf_path = Column(Ciphertext, nullable=True)
    cover_pdf_paths = Column(Ciphertext, info={"plain_default": []})
    peso_total_prova = Column(Float, nullable=True)
    disciplinas_relacionadas = relationship("DisciplinaDaProva", back_populates="cargo")
    evento = relationship("Evento", back_populates="cargos")
    tenant = relationship("Tenant")

class DisciplinaDaProva(Base):
    __tablename__ = "DisciplinasDaProva"
    id_disciplina_prova = Column(Text, primary_key=True)
    id_cargo_fk = Column(Text, ForeignKey("Cargos.id_cargo"))
    id_disciplina_base_fk = Column(Text, ForeignKey("Disciplinas.id_disciplina"))  # <-- CORRIGIDO!
    nome_disciplina_na_prova = Column(Ciphertext, nullable=False)
    qtd_questoes = Column(Integer, nullable=True)
    peso_por_questao = Column(Float, nullable=True)
    tipo_conhecimento = Column(String, default="comum")
    observacoes = Column(Ciphertext, nullable=True)
    ordem_na_prova = Column(Integer, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    cargo = relationship("Cargo", back_populates="disciplinas_relacionadas")
    disciplina_base = relationship("Disciplina", back_populates="provas_relacionadas")

class Disciplina(Base):
    __tablename__ = "Disciplinas"
    id_disciplina = Column(Text, primary_key=True)
    id_evento_fk = Column(Text, ForeignKey("Eventos.id_evento"), nullable=True)
    nome_disciplina = Column(Ciphertext, nullable=False)
    codigo_disciplina = Column(Text, nullable=True)
    descricao = Column(Ciphertext, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)  # <-- ADICIONE ESTA LINHA!
    nome_disciplina_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)

    provas_relacionadas = relationship("DisciplinaDaProva", back_populates="disciplina_base")

class ProvaMontada(Base):
    __tablename__ = "ProvasMontadas"
    id_prova_montada = Column(String, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id_evento_fk = Column(String, ForeignKey("Eventos.id_evento"))
    id_cargo_fk = Column(String, ForeignKey("Cargos.id_cargo"))
    nome_prova_montada = Column(Ciphertext, nullable=False)
    identificador_prova = Column(String)
    titulo_prova = Column(Ciphertext)
    status_montagem = Column(String)
    responsavel_montagem = Column(Ciphertext)
    data_criacao = Column(DateTime)
    data_modificacao = Column(DateTime)
    blocos_questoes = Column(Ciphertext, nullable=True)  # <--- Adicione este campo!
    metadados_prova = Column(Ciphertext, nullable=True)
    textos_referencia_prova_json = Column(Ciphertext, nullable=True)
    tenant = relationship("Tenant")
    
    def __repr__(self):
        return f"<ProvaMontada(id={self.id_prova_montada}, nome='{self.nome_prova_montada}')>"

class BancoFrases(Base):
    __tablename__ = 'banco_frases'
    id = Column(Integer, primary_key=True)
    id_local = Column(Integer, nullable=False)  # <-- Novo campo!
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    categoria = Column(Ciphertext, nullable=False)
    texto_frase = Column(Ciphertext, nullable=False)  # <-- minúsculo!
    ativo = Column(BOOLEAN, nullable=False)
    identificador = Column(Text, nullable=True)
    categoria_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    frase_bidx = Column(String(64), nullable=True, index=True)  # índice cego (HMAC)
    tenant = relationship("Tenant")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'frase_bidx', name='_tenant_frase_bidx_uc'),
    )

    def __repr__(self):
        return f"<BancoFrases(id={self.id}, categoria='{self.categoria}')>"

class QuestoesBanco(Base):
    __tablename__ = "QuestoesBanco"
    __table_args__ = (UniqueConstraint('tenant_id', 'codigo_curto_questao', name='uq_questoesbanco_tenant_codigo_curto_questao'),)

    id_questao = Column(String, primary_key=True)
    codigo_curto_questao = Column(String, nullable=True)  # único por cliente (ver __table_args__)
    id_evento_fk = Column(String, ForeignKey("Eventos.id_evento"))
    enunciado = Column(Ciphertext, nullable=True)
    enunciado_formatado = Column(Ciphertext, nullable=True)
    indicacao_conteudo = Column(Ciphertext, nullable=True)
    tipo = Column(String, nullable=True)
    disciplina_banco = Column(Ciphertext, nullable=True)
    resposta_correta = Column(Ciphertext, nullable=True)
    gabarito_preliminar = Column(Ciphertext, nullable=True)
    gabarito_definitivo = Column(Ciphertext, nullable=True)
    nivel_dificuldade = Column(Ciphertext, nullable=True)
    tempo_esperado_resposta_segundos = Column(Integer, nullable=True)
    tags_keywords = Column(Ciphertext, nullable=True)
    texto_referencia_vinculo = Column(Ciphertext, nullable=True)
    texto_referencia_direto = Column(Ciphertext, nullable=True)
    id_texto_ref_vinculado = Column(String, nullable=True)
    status_revisao = Column(String, nullable=True)
    justificativa_anulacao = Column(Ciphertext, nullable=True)
    criador_id = Column(String, nullable=True)
    metadados_questao = Column(Ciphertext, nullable=True)
    disciplina_id = Column(String, nullable=True)
    conteudo_id = Column(String, nullable=True)
    conteudo_nome = Column(Ciphertext, nullable=True)
    pontuacao = Column(Float, nullable=True)
    feedback_geral_questao = Column(Ciphertext, nullable=True)
    justificativa_questao = Column(Ciphertext, nullable=True)
    revisada = Column(Boolean, nullable=True)
    autor_elaborador = Column(Ciphertext, nullable=True)
    data_criacao = Column(DateTime, default=datetime.now)
    data_modificacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    numero_questao_original_docx = Column(Ciphertext, nullable=True)
    hash_conteudo_questao = Column(Ciphertext, nullable=True)
    fonte_questao = Column(Ciphertext, nullable=True)
    anulada = Column(Boolean, nullable=True)
    justificativa_anulacao_recurso = Column(Ciphertext, nullable=True)
    justificativa_anulacao_recurso_formatado = Column(Ciphertext, nullable=True)
    imagens_enunciado = Column(Ciphertext, nullable=True)
    imagens_enunciado_refs = Column(Ciphertext, nullable=True)
    caminho_imagem_justificativa = Column(Ciphertext, nullable=True)
    textos_referencia_questao = Column(Ciphertext, nullable=True)
    caminho_imagem_relativo = Column(Ciphertext, nullable=True)
    status_revisao = Column(String, nullable=True)
    observacao_revisor = Column(Ciphertext, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

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
    texto_opcao = Column(Ciphertext, nullable=True)
    texto_opcao_formatado = Column(Ciphertext, nullable=True)
    ordem_original = Column(Integer, nullable=True)
    correta = Column(Ciphertext, info={"plain_default": False})
    feedback_opcao = Column(Ciphertext, nullable=True)
    imagem_path_opcao = Column(Ciphertext, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    questao = relationship("QuestoesBanco", backref="opcoes")

# Itens de verdadeiro/falso (certo/errado)
class ItensVerdadeiroFalso(Base):
    __tablename__ = "ItensVerdadeiroFalso"

    id_item_vf = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_questao_fk = Column(String, ForeignKey("QuestoesBanco.id_questao", ondelete="CASCADE"), nullable=False)
    afirmacao = Column(Ciphertext, nullable=False)
    valor_correto = Column(Ciphertext, nullable=False)
    feedback_item = Column(Ciphertext, nullable=True)
    ordem = Column(Integer, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    questao = relationship("QuestoesBanco", backref="itens_vf")

# Detalhes de questões discursivas
class DetalhesQuestaoDiscursiva(Base):
    __tablename__ = "DetalhesQuestaoDiscursiva"
    id_detalhe_discursiva = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    id_questao_fk = Column(String, ForeignKey("QuestoesBanco.id_questao", ondelete="CASCADE"), nullable=False, unique=True)
    resposta_esperada_texto = Column(Ciphertext, nullable=True)
    palavras_chave_resposta = Column(Ciphertext, nullable=True) # Salve como JSON string
    numero_linhas_resposta = Column(Integer, nullable=True)
    texto_subjetivo_orientacao = Column(Ciphertext, nullable=True)    # Para subjetiva
    texto_subjetivo_nota_maxima = Column(Ciphertext, nullable=True)   # Para subjetiva
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    questao = relationship("QuestoesBanco", backref="detalhes_discursiva")

  
class Company(Base):
    __tablename__ = "company_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    company_name = Column(Ciphertext, nullable=False, info={"plain_default": ""})
    company_cnpj = Column(Ciphertext, nullable=False, info={"plain_default": ""})
    company_address = Column(Ciphertext, nullable=False, info={"plain_default": ""})
    company_phone = Column(Ciphertext, nullable=False, info={"plain_default": ""})
    company_email = Column(Ciphertext, nullable=False, info={"plain_default": ""})
    company_website = Column(Ciphertext, nullable=False, info={"plain_default": ""})
    company_logo_path = Column(Ciphertext, nullable=False, info={"plain_default": ""})

    tenant = relationship("Tenant")

class Conteudo(Base):
    __tablename__ = 'conteudos'
    __table_args__ = (UniqueConstraint('tenant_id', 'identificador_conteudo', name='uq_conteudos_tenant_identificador_conteudo'),)
    id_conteudo = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identificador_conteudo = Column(String, nullable=True)  # único por cliente (ver __table_args__)
    nome_conteudo = Column(Ciphertext, nullable=False)
    descricao = Column(Ciphertext)
    disciplina = Column(Ciphertext)
    id_disciplina_fk = Column(String, nullable=True)
    turno = Column(Ciphertext)
    nivel = Column(Ciphertext)
    professor_id = Column(String)
    area_conhecimento = Column(Ciphertext)
    conteudo_pai_id = Column(String)
    evento_id = Column(String, nullable=False)
    is_deleted = Column(Boolean, default=False)
    metadados = Column(Ciphertext, nullable=True, info={"plain_default": dict})
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)  # NOVO!
    respondidas = Column(Integer, nullable=False, default=0)  # NOVO!
    quantidade = Column(Integer, nullable=False, default=0)    # Total de questões

class TextoReferenciaGeral(Base):
    __tablename__ = "TextosReferenciaGeral"
    id_texto_ref = Column(String, primary_key=True)
    id_evento_fk = Column(String, ForeignKey("Eventos.id_evento"))
    id_conteudo_fk = Column(String, ForeignKey("conteudos.id_conteudo"), nullable=False)  # Vínculo correto!
    codigo_ref = Column(String)  # Código amigável do texto de referência
    titulo = Column(Ciphertext, nullable=True)
    conteudo = Column(Ciphertext)
    tipo_conteudo = Column(String)
    legenda_texto = Column(Ciphertext)
    descricao_imagem = Column(Ciphertext)
    fonte_imagem = Column(Ciphertext)
    tags_imagem = Column(Ciphertext)
    licenca_imagem = Column(Ciphertext)
    caminho_imagem_relativo = Column(Ciphertext)
    observacoes = Column(Ciphertext)
    ativo = Column(Boolean, default=True)
    publico = Column(Boolean, default=True)
    metadados_texto_ref = Column(Ciphertext)
    questoes_vinculo = Column(Ciphertext)
    conteudo_formatado = Column(Ciphertext)
    data_criacao = Column(String)
    data_modificacao = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

class HistoricoRevisaoQuestao(Base):
    __tablename__ = "HistoricoRevisaoQuestao"
    id = Column(String, primary_key=True)  # UUID
    id_questao_fk = Column(String, ForeignKey("QuestoesBanco.id_questao"), nullable=False)
    usuario_revisor = Column(Ciphertext, nullable=False)
    data_revisao = Column(DateTime, default=datetime.now)
    status_revisao = Column(String, nullable=False)
    observacao_revisor = Column(Ciphertext)
    dados_revisao = Column(Ciphertext)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    questao = relationship("QuestoesBanco", backref="historico_revisoes")
    tenant = relationship("Tenant")


# Liga a cifragem de campos a todos os modelos (ver backend/app/field_crypto.py)
install_orm_encryption(Base)
