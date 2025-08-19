# backend/app/roles.py
from enum import Enum

class UserRole(str, Enum):
    ADMIN_GERAL = "administrador geral"
    ADMIN = "administrador"
    PROFESSOR = "professor"
    REVISOR = "revisor"
    DIAGRAMADOR = "diagramador"