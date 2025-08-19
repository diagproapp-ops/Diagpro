from fastapi import APIRouter
from backend.app.models import Prova

router = APIRouter()

@router.get("/", response_model=list[Prova])
def list_provas():
    return [Prova(id=1, descricao="Prova Matemática")]