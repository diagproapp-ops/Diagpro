# DiagProOFF/core/models.py (VERSÃO CORRIGIDA E COMPLETA)

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from typing import Dict, Any
import os
import sys
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from sqlalchemy.sql import func
from datetime import datetime



Base = declarative_base()
# -----------------------------------------------------------------------------
# Modelos de Dados para o Banco de Questões
# -----------------------------------------------------------------------------

@dataclass
class Opcao:
    """Representa uma única opção (alternativa) de uma questão de múltipla escolha."""
    id: Optional[int] = None
    id_questao: Optional[int] = None
    letra: str = ""  # Ex: "A", "B", "C"
    texto: str = ""
    is_correta: bool = False # Define se esta é a opção correta (gabarito)

@dataclass
class TextoReferencia:
    """Representa um texto de referência que pode ser associado a uma ou mais questões."""
    id: Optional[int] = None
    titulo: str = "Texto de Referência"
    conteudo: str = ""
    # Você pode adicionar um campo para vincular a uma disciplina ou prova específica se necessário
    # id_disciplina: Optional[int] = None

@dataclass
class Questao:
    """Representa uma questão completa, com seu enunciado, opções e gabarito."""
    id: Optional[int] = None
    enunciado: str = ""
    disciplina: Optional[str] = None # Ex: "Língua Portuguesa", "Informática"
    gabarito: Optional[str] = None # A letra da opção correta, ex: "C"
    
    # Relacionamentos
    opcoes: List[Opcao] = field(default_factory=list)
    id_texto_referencia: Optional[int] = None
    texto_referencia: Optional[TextoReferencia] = None # O objeto completo, se carregado

# -----------------------------------------------------------------------------
# Modelos de Dados para Gestão de Eventos e Provas
# -----------------------------------------------------------------------------

@dataclass
class Evento:
    """Representa um concurso ou processo seletivo."""
    id: int
    nome_evento: str
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    status: str = "Em elaboração"

@dataclass
class Cargo:
    """Representa um cargo dentro de um evento."""
    id: int
    id_evento: int
    nome_cargo: str
    codigo_cargo: Optional[str] = None

# -----------------------------------------------------------------------------
# Modelo de Usuário
# -----------------------------------------------------------------------------

@dataclass
class User:
    """
    Representa o modelo de dados de um usuário, sincronizado
    com a tabela 'users' do banco de dados.
    """
    id: int
    username: str
    password_hash: str  # <--- O CAMPO QUE FALTAVA
    role: str
    
    # O resto dos campos que podem ser nulos
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: int = 1
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None
    celular: Optional[str] = None
    endereco: Optional[str] = None
    cpf: Optional[str] = None
    cargo: Optional[str] = None

@dataclass
class ProvaMontada:
    """Representa uma prova que foi montada para um cargo específico."""
    id_prova_montada: str
    nome_prova_montada: str = "Prova Gerada"
    id_cargo_associado: str = ""
    # Agora que 'datetime' é a classe diretamente, usamos datetime.now
    data_criacao: datetime = field(default_factory=datetime.now) # Alterado de datetime.datetime para datetime
    data_modificacao: datetime = field(default_factory=datetime.now) # Alterado de datetime.datetime para datetime
    questoes_por_disciplina: Dict[str, List[str]] = field(default_factory=dict)
    ordem_disciplinas_na_prova: List[str] = field(default_factory=list)
    nome_cargo_associado: Optional[str] = None
    metadados_prova: Dict[str, Any] = field(default_factory=dict)

class TextoReferencia(Base):
    __tablename__ = 'textos_referencia'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    titulo = Column(String, default="Texto de Referência")
    conteudo = Column(Text, nullable=False)
    
    questoes = relationship("QuestoesBanco", back_populates="texto_referencia")

# --- CORREÇÃO DE ORDEM E RELACIONAMENTO ---

# 1. Defina a classe "filha" (OpcoesQuestoes) PRIMEIRO.
class OpcoesQuestoes(Base):
    __tablename__ = 'OpcoesQuestoes' # Nome exato da sua tabela
    
    id_opcao = Column(Integer, primary_key=True, autoincrement=True)
    letra = Column(String, nullable=False)
    texto_opcao = Column(Text, nullable=False)
    correta = Column(Boolean, default=False)
    
    # CORREÇÃO PRINCIPAL: Define a coluna de chave estrangeira com o nome exato do seu banco ('id_questao_fk')
    # e aponta para a coluna 'id_questao' da tabela 'QuestoesBanco'.
    id_questao_fk = Column(Integer, ForeignKey('QuestoesBanco.id_questao'), nullable=False)
    
    # A relação inversa para o SQLAlchemy saber quem é o "pai"
    questao = relationship("QuestoesBanco", back_populates="opcoes")
    
    def to_dict(self):
        """Converte a opção para um dicionário."""
        return {
            "id_opcao": self.id_opcao,
            "letra": self.letra,
            "texto_opcao": self.texto_opcao,
            "correta": self.correta
        }

# 2. Defina a classe "pai" (QuestoesBanco) DEPOIS.
class QuestoesBanco(Base):
    __tablename__ = 'QuestoesBanco' # Nome exato da sua tabela
    
    id_questao = Column(Integer, primary_key=True, autoincrement=True)
    enunciado = Column(Text, nullable=False)
    tipo_questao = Column("tipo", String, default="multipla_escolha")
    disciplina_banco = Column(String)
    gabarito = Column(String)
    
    id_texto_referencia = Column(Integer, ForeignKey('textos_referencia.id'))
    
    # Agora, quando o Python ler esta linha, ele já saberá o que é "OpcoesQuestoes".
    # O cascade="all, delete-orphan" garante que as opções sejam salvas e deletadas junto com a questão.
    opcoes = relationship("OpcoesQuestoes", back_populates="questao", cascade="all, delete-orphan")
    texto_referencia = relationship("TextoReferencia", back_populates="questoes")

    def to_dict_with_options(self):
        """Converte a questão e suas opções para um dicionário."""
        return {
            "id_questao": self.id_questao,
            "tipo_questao": self.tipo_questao,
            "disciplina_banco": self.disciplina_banco,
            "enunciado": self.enunciado,
            "gabarito": self.gabarito,
            "opcoes": [opcao.to_dict() for opcao in self.opcoes]
        }

class BancoFrases(Base):
    __tablename__ = 'banco_frases'  # Nome da tabela no banco

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String, nullable=False, index=True)
    texto_frase = Column(String, nullable=False)
    identificador = Column(String, unique=True, nullable=True, index=True)
    ativo = Column(Boolean, default=True)
    
    # Você pode adicionar outros campos que discutimos, como 'aplicacao', 'relevancia', etc.
    # aplicacao = Column(String)
    # relevancia = Column(Integer, default=100)

    def __repr__(self):
        return f"<BancoFrases(id={self.id}, categoria='{self.categoria}')>"
    

def create_all_tables_from_models(engine):
    """Cria todas as tabelas no banco de dados se elas não existirem."""
    Base.metadata.create_all(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String)
    full_name = Column(String)
    email = Column(String, unique=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime)
    celular = Column(String)
    endereco = Column(String)
    cpf = Column(String)
    cargo = Column(String)

class Events(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    nome_evento = Column(String, nullable=False)
    data_inicio = Column(String)
    data_fim = Column(String)
    status = Column(String)

class Cargos(Base):
    __tablename__ = 'cargos'
    id = Column(Integer, primary_key=True)
    id_evento = Column(Integer, ForeignKey('events.id'))
    nome_cargo = Column(String, nullable=False)
    codigo_cargo = Column(String)