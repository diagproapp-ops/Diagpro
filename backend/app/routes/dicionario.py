from fastapi import APIRouter, Request, HTTPException, Depends
import requests
import re
import logging
from backend.app.auth import get_current_user

router = APIRouter()
logger = logging.getLogger("dicionario")

@router.post("/dicionario")
async def dicionario(request: Request, current_user=Depends(get_current_user)):
    try:
        data = await request.json()
        termo = (data.get("termo") or "").strip()
        if not termo:
            raise HTTPException(status_code=422, detail="Termo de busca não pode ser vazio.")
        url = f"https://www.dicio.com.br/{termo.lower().replace(' ', '-')}/"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            # regex mais flexível para diferentes classes
            m = re.search(r'<p[^>]+class=["\']significado.*?["\'][^>]*>(.*?)</p>', r.text, flags=re.S)
            if m:
                definicao = re.sub("<.*?>", "", m.group(1)).strip()
                logger.info(f"Dicionário: definição encontrada para '{termo}'")
                return {"success": True, "definicao": definicao}
            # LOG para depuração do HTML real
            logger.warning(f"Dicionário HTML para '{termo}': {r.text[:1200]}")
        logger.warning(f"Dicionário: termo '{termo}' não encontrado.")
        return {"success": False, "definicao": "Não encontrado."}
    except Exception as e:
        logger.error(f"Erro no dicionário: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na busca do dicionário: {str(e)}")