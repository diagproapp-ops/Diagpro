# backend/app/models.py (VERSÃO FINAL COMPLETA)

from pydantic import BaseModel
from typing import Optional, List

# Modelo para um único Cargo
class Cargo(BaseModel):
    id_cargo: str
    nome_cargo: str

    class Config:
        from_attributes = True

# Modelo para um único Evento, incluindo uma lista de seus Cargos
class Evento(BaseModel):
    id_evento: str
    nome_evento: str
    data_prova: Optional[str] = None
    status: Optional[str] = None
    cargos: List[Cargo] = []

    class Config:
        from_attributes = True

# Modelo para um Usuário (usado na rota /users/)
class User(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str  # <-- ADICIONE ESTA LINHA

    class Config:
        from_attributes = True

# --- MODELO QUE FALTAVA ---
class Prova(BaseModel):
    id: int # Mantenha como está por agora, vamos conectar à BD depois
    descricao: str

    class Config:
        from_attributes = True