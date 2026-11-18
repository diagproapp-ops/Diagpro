import logging
import os

import openai
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.auth import get_current_user
from backend.app.rate_limit import rate_limit

router = APIRouter()
logger = logging.getLogger("ia_chat")


class IAChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    contexto: str = Field(default="", max_length=4000)


@router.post("/ia-chat", dependencies=[Depends(rate_limit(20, 60, "ia-chat"))])
async def ia_chat(payload: IAChatRequest, current_user=Depends(get_current_user)):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Integração OpenAI não configurada no ambiente.")

    msg = payload.message.strip()
    contexto = payload.contexto.strip()
    if not msg:
        raise HTTPException(status_code=422, detail="Mensagem não pode ser vazia.")

    prompt = (
        "Você é um assistente educacional experiente.\n"
        f"Questão/contexto:\n{contexto}\n---\n"
        f"Mensagem do usuário:\n{msg}\n"
        "Por favor, responda de forma clara, objetiva e didática."
    )
    try:
        openai.api_key = api_key
        resp = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600,
            timeout=20,
        )
        answer = resp.choices[0].message.content.strip()
        logger.info("Chat IA concluído para tenant=%s", current_user.tenant_id)
        return {"success": True, "reply": answer}
    except Exception as exc:
        logger.error("Erro no Chat IA: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Serviço de IA temporariamente indisponível.")
