from fastapi import APIRouter, Request, HTTPException
import logging

router = APIRouter()
logger = logging.getLogger("biblioteca")

# Simulação; troque por banco real depois!
QUESTOES_FAKE = [
    {
        "id": 1,
        "assunto": "Matemática",
        "enunciado": "Qual a soma de 2 + 2?",
        "comentario": "Questão de cálculo simples.",
        "nivel": "Fácil"
    },
    {
        "id": 2,
        "assunto": "Português",
        "enunciado": "O que é um substantivo?",
        "comentario": "Exemplo clássico de gramática.",
        "nivel": "Médio"
    }
]

@router.post("/biblioteca")
async def biblioteca(request: Request):
    try:
        data = await request.json()
        busca = (data.get("busca") or "").lower()
        if not busca:
            raise HTTPException(status_code=422, detail="Campo de busca não pode ser vazio.")
        results = []
        for q in QUESTOES_FAKE:
            if busca in q["enunciado"].lower() or busca in q.get("assunto", "").lower():
                results.append(q)
        logger.info(f"Biblioteca: {len(results)} resultados para '{busca}'")
        return {"success": True, "total": len(results), "questoes": results}
    except Exception as e:
        logger.error(f"Erro na biblioteca: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na busca da biblioteca: {str(e)}")