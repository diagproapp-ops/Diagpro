import re
import random
import string
from sqlalchemy import select

async def gerar_codigo_curto(tipo, tenant_id, db):
    """
    Gera um código curto único por tenant e tipo de questão.
    Formato: Q-AB0001, D-XY0001, etc.
    """
    from backend.app.db_models import QuestoesBanco

    prefixos = {
        "MULTIPLA_ESCOLHA": "Q",
        "DISCURSIVA": "D",
        "SUBJETIVA": "S",
        "CERTO_ERRADO": "I",
    }
    prefixo = prefixos.get(tipo, "X")
    letras = ''.join(random.choices(string.ascii_uppercase, k=2))

    # Busca todos os códigos já usados para o tenant e tipo
    result = await db.execute(
        select(QuestoesBanco.codigo_curto_questao)
        .where(
            QuestoesBanco.tenant_id == tenant_id,
            QuestoesBanco.tipo == tipo
        )
    )
    codigos = [c for c in result.scalars().all() if c]
    # Extrai o número final de todos os codigos (ex: Q-AB0123 => 123)
    numbers = []
    for c in codigos:
        m = re.match(rf"{prefixo}-[A-Z]{{2}}(\d{{4}})$", c)
        if m:
            try:
                numbers.append(int(m.group(1)))
            except Exception:
                pass
    next_num = (max(numbers) if numbers else 0) + 1
    return f"{prefixo}-{letras}{next_num:04d}"