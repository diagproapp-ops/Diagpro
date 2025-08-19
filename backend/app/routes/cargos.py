from fastapi import APIRouter
from backend.app.models import Cargo

router = APIRouter()

@router.get("/", response_model=list[Cargo])
def list_cargos():
    return [Cargo(id=1, nome="Professor"), Cargo(id=2, nome="Aluno")]