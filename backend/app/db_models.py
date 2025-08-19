# backend/app/db_models.py (VERSÃO FINAL COM RELACIONAMENTOS)

from sqlalchemy import Column, Integer, String, ForeignKey, TEXT, BOOLEAN, TIMESTAMP, REAL
from sqlalchemy.orm import declarative_base, relationship # Importe o relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(TEXT, unique=True, nullable=False)
    password_hash = Column(TEXT, nullable=False)
    role = Column(String) # <-- ADICIONE ESTA LINHA
    # ... (resto das colunas do User)

class Evento(Base):
    __tablename__ = "Eventos"
    id_evento = Column(TEXT, primary_key=True)
    nome_evento = Column(TEXT, nullable=False)
    data_prova = Column(TEXT)
    # --- ADICIONE ESTA LINHA ---
    # Diz ao SQLAlchemy: "Um evento tem uma lista de cargos"
    cargos = relationship("Cargo", back_populates="evento")

class Cargo(Base):
    __tablename__ = "Cargos"
    id_cargo = Column(TEXT, primary_key=True)
    id_evento_fk = Column(TEXT, ForeignKey("Eventos.id_evento"))
    nome_cargo = Column(TEXT, nullable=False)
    # --- ADICIONE ESTA LINHA ---
    # Diz ao SQLAlchemy: "Um cargo pertence a um evento"
    evento = relationship("Evento", back_populates="cargos")