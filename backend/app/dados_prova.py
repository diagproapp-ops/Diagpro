# backend/app/dados_prova.py
"""
Completa a cópia das questões guardada na montagem com o que a diagramação precisa e que montagens
antigas não guardavam: o tipo da questão, os itens de Certo/Errado (na ordem cadastrada) e a quantidade
de linhas de Subjetiva/Discursiva. Só preenche o que FALTA; o que já está na cópia nunca é trocado,
para não mudar provas já exportadas.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db_models import DetalhesQuestaoDiscursiva, ItensVerdadeiroFalso, QuestoesBanco

LINHAS_PADRAO_SUBJETIVA = 10


def _questoes(blocos):
    for bloco in blocos or []:
        if isinstance(bloco, dict):
            for q in bloco.get("questoes") or []:
                if isinstance(q, dict) and q.get("id_questao"):
                    yield q


async def completar_questoes(db: AsyncSession, blocos) -> None:
    questoes = list(_questoes(blocos))
    if not questoes:
        return
    ids = list({q["id_questao"] for q in questoes})
    tipos = {
        row.id_questao: (row.tipo or "MULTIPLA_ESCOLHA").upper()
        for row in (await db.execute(select(QuestoesBanco.id_questao, QuestoesBanco.tipo)
                                     .where(QuestoesBanco.id_questao.in_(ids)))).all()
    }
    for q in questoes:
        if not q.get("tipo"):
            q["tipo"] = tipos.get(q["id_questao"], "MULTIPLA_ESCOLHA")
        tipo = str(q["tipo"]).upper()

        if tipo == "CERTO_ERRADO" and not q.get("itens_vf"):
            itens = (await db.execute(
                select(ItensVerdadeiroFalso)
                .where(ItensVerdadeiroFalso.id_questao_fk == q["id_questao"])
                .order_by(ItensVerdadeiroFalso.ordem)
            )).scalars().all()
            q["itens_vf"] = [
                {"afirmacao": i.afirmacao, "valor_correto": bool(i.valor_correto),
                 **({"imagem_path_item": i.imagem_path_item} if i.imagem_path_item else {})}
                for i in itens
            ]

        if tipo in ("SUBJETIVA", "DISCURSIVA"):
            det = q.get("detalhes_discursiva") or {}
            if not det.get("numero_linhas_resposta"):
                row = (await db.execute(
                    select(DetalhesQuestaoDiscursiva).where(DetalhesQuestaoDiscursiva.id_questao_fk == q["id_questao"])
                )).scalar_one_or_none()
                if row and row.numero_linhas_resposta:
                    q["detalhes_discursiva"] = {**det, "numero_linhas_resposta": row.numero_linhas_resposta}
