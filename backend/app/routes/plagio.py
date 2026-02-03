from fastapi import APIRouter, Request, HTTPException
import requests
import os
import logging

router = APIRouter()
BING_KEY = os.getenv("BING_API_KEY")
logger = logging.getLogger("plagio")

@router.post("/check-plagio")
async def check_plagio(request: Request):
    try:
        data = await request.json()
        texto = data.get("texto", "").strip()
        if not texto:
            raise HTTPException(status_code=422, detail="Texto não pode ser vazio.")
        headers = {"Ocp-Apim-Subscription-Key": BING_KEY}
        params = {"q": texto, "count": 5}
        r = requests.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params, timeout=10)
        fontes = []
        if r.status_code == 200:
            for item in r.json().get("webPages", {}).get("value", []):
                fontes.append({
                    "url": item["url"],
                    "trecho": item.get("snippet", ""),
                    "titulo": item.get("name", "")
                })
            percent = min(100, len(fontes) * 20)
        else:
            logger.error(f"Bing erro HTTP: {r.status_code}")
            percent = 0
        logger.info(f"Plágio: {len(fontes)} fontes encontradas.")
        return {"success": True, "percentual": percent, "fontes": fontes}
    except Exception as e:
        logger.error(f"Erro ao verificar plágio: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao verificar plágio: {str(e)}")