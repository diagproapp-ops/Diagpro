from dotenv import load_dotenv
load_dotenv()

import asyncio
from sqlalchemy.future import select
from backend.app.database import SessionLocal  # Seu SessionLocal retorna AsyncSession
from backend.app.db_models import Evento
from backend.app.utils_crypto import encrypt_text

evento_id = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
nova_senha = "1234"
senha_cripto = encrypt_text(nova_senha)

async def main():
    async with SessionLocal() as db:
        result = await db.execute(select(Evento).where(Evento.id_evento == evento_id))
        evento = result.scalar_one_or_none()
        if not evento:
            print("Evento não encontrado!")
        else:
            print("Antes:", evento.senha_evento_cripto)
            evento.senha_evento_cripto = senha_cripto
            await db.commit()
            await db.refresh(evento)
            print("Depois:", evento.senha_evento_cripto)

asyncio.run(main())