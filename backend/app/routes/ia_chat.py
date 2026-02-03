from fastapi import APIRouter, Request, HTTPException
import openai
import os
import logging

router = APIRouter()
openai.api_key = os.getenv("OPENAI_API_KEY")
logger = logging.getLogger("ia_chat")

@router.post("/ia-chat")
async def ia_chat(request: Request):
    try:
        data = await request.json()
        msg = data.get("message", "").strip()
        contexto = data.get("contexto", "").strip()
        if not msg:
            raise HTTPException(status_code=422, detail="Mensagem não pode ser vazia.")
        prompt = f"""Você é um assistente educacional experiente. 
Questão/contexto: 
{contexto}
---
Mensagem do usuário:
{msg}
Por favor, responda de forma clara, objetiva e didática."""
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=600, timeout=20
        )
        answer = resp.choices[0].message.content.strip()
        logger.info(f"Chat IA: sucesso para mensagem: {msg[:40]}...")
        return {"success": True, "reply": answer}
    except Exception as e:
        logger.error(f"Erro no Chat IA: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no Chat IA: {str(e)}")