from sqlalchemy import select
from backend.app.db_models import QuestoesBanco, TextoReferenciaGeral
from backend.app.utils_crypto import encrypt_text, decrypt_text

async def sincronizar_vinculo_texto_questao(db, id_texto_ref, lista_ids_questao):
    """
    Garante que:
    - O texto de referência (TextoReferenciaGeral) tenha a lista correta de questões (questoes_vinculo)
    - Todas as questões em lista_ids_questao tenham o campo texto_referencia_vinculo preenchido corretamente
    """
    # Atualiza o texto de referência
    texto_ref_result = await db.execute(
        select(TextoReferenciaGeral).where(TextoReferenciaGeral.id_texto_ref == id_texto_ref)
    )
    texto_ref = texto_ref_result.scalar_one_or_none()
    if texto_ref:
        questoes_vinculo = set(filter(None, (texto_ref.questoes_vinculo or "").split(",")))
        for id_questao in lista_ids_questao:
            questoes_vinculo.add(id_questao)
        texto_ref.questoes_vinculo = ",".join(questoes_vinculo)
        db.add(texto_ref)
        await db.commit()

    # Atualiza todas as questões desse texto
    for id_questao in lista_ids_questao:
        questao_result = await db.execute(
            select(QuestoesBanco).where(QuestoesBanco.id_questao == id_questao)
        )
        questao = questao_result.scalar_one_or_none()
        if questao:
            valor_db = questao.texto_referencia_vinculo
            # Se usa criptografia, garanta criptografar aqui
            valor_esperado = encrypt_text(id_texto_ref)
            if not valor_db or valor_db != valor_esperado:
                questao.texto_referencia_vinculo = valor_esperado
                db.add(questao)
    await db.commit()