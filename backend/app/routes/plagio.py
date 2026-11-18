import logging
import os

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.auth import get_current_user
from backend.app.rate_limit import rate_limit

router = APIRouter()
logger = logging.getLogger("plagio")


class PlagioRequest(BaseModel):
    texto: str = Field(..., min_length=1, max_length=1500)


@router.post("/check-plagio", dependencies=[Depends(rate_limit(20, 60, "check-plagio"))])
async def check_plagio(payload: PlagioRequest, current_user=Depends(get_current_user)):
    bing_key = os.getenv("BING_API_KEY", "").strip()
    if not bing_key:
        raise HTTPException(status_code=503, detail="Integração Bing Search não configurada no ambiente.")

    texto = payload.texto.strip()
    if not texto:
        raise HTTPException(status_code=422, detail="Texto não pode ser vazio.")

    try:
        headers = {"Ocp-Apim-Subscription-Key": bing_key}
        params = {"q": texto, "count": 5}
        r = requests.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params, timeout=10)
        fontes = []
        if r.status_code == 200:
            for item in r.json().get("webPages", {}).get("value", []):
                fontes.append(
                    {
                        "url": item["url"],
                        "trecho": item.get("snippet", ""),
                        "titulo": item.get("name", ""),
                    }
                )
            percent = min(100, len(fontes) * 20)
        else:
            logger.warning("Bing Search retornou status %s", r.status_code)
            percent = 0
        logger.info("Verificação de similaridade: %d fontes para tenant=%s", len(fontes), current_user.tenant_id)
        return {
            "success": True,
            "percentual": percent,
            "nota": "Indicador de similaridade sujeito à análise humana.",
            "fontes": fontes,
        }
    except Exception as exc:
        logger.error("Erro ao verificar similaridade: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Serviço de busca externa temporariamente indisponível.")
