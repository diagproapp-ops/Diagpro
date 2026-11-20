# backend/app/versoes_questao.py
"""
Histórico de versões e detecção de questões parecidas.

Versões: a cada criação, edição e revisão guardamos a questão completa (decifrada pelo ORM e recifrada na
coluna `snapshot`). Na primeira alteração de uma questão antiga, o estado anterior vira a versão 1.

Parecidas: comparação local (nada sai do servidor) por trigramas de palavras do enunciado normalizado
(sem HTML, acentos, pontuação e maiúsculas), com coeficiente de Dice. Só dentro da mesma banca (RLS).
"""
import html
import re
import unicodedata
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db_models import QuestoesBanco, VersaoQuestao

_CAMPOS_VOLATEIS = ("data_modificacao",)


async def proxima_versao(db: AsyncSession, id_questao: str) -> int:
    atual = (await db.execute(select(func.max(VersaoQuestao.versao)).where(VersaoQuestao.id_questao_fk == id_questao))).scalar()
    return (atual or 0) + 1


async def salvar(db: AsyncSession, questao_out, tenant_id: int, motivo: str, autor: str | None, commit: bool = True) -> int:
    """questao_out: QuestaoOut (o mesmo que a tela recebe). Grava e devolve o número da versão."""
    dados = questao_out.model_dump(mode="json") if hasattr(questao_out, "model_dump") else dict(questao_out)
    for c in _CAMPOS_VOLATEIS:
        dados.pop(c, None)
    n = await proxima_versao(db, dados["id_questao"])
    db.add(VersaoQuestao(tenant_id=tenant_id, id_questao_fk=dados["id_questao"], versao=n, criada_em=datetime.now(),
                         motivo=motivo[:30], autor=autor, snapshot=dados))
    if commit:
        await db.commit()
    else:
        await db.flush()
    return n


async def guardar_estado_anterior(db: AsyncSession, questao_out, tenant_id: int) -> None:
    """Questão sem histórico (anterior a esta função): o estado antes da 1ª alteração vira a versão 1."""
    if not await tem_versoes(db, questao_out.id_questao):
        await salvar(db, questao_out, tenant_id, "anterior", None, commit=False)


async def tem_versoes(db: AsyncSession, id_questao: str) -> bool:
    return (await db.execute(select(VersaoQuestao.id).where(VersaoQuestao.id_questao_fk == id_questao).limit(1))).first() is not None


# --------------------------------------------------------------------------- parecidas
_TAG = re.compile(r"<[^>]+>")
_NAO_PALAVRA = re.compile(r"[^a-z0-9]+")


def normalizar(texto: str | None) -> list[str]:
    s = html.unescape(_TAG.sub(" ", texto or ""))
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return [p for p in _NAO_PALAVRA.sub(" ", s).split() if p]


def trigramas(palavras: list[str]) -> set:
    if len(palavras) < 3:
        return {" ".join(palavras)} if palavras else set()
    return {" ".join(palavras[i:i + 3]) for i in range(len(palavras) - 2)}


def similaridade(a: set, b: set) -> float:
    """Coeficiente de Dice sobre trigramas (0 a 1): tolera trocas de poucas palavras."""
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


async def parecidas(db: AsyncSession, tenant_id: int, enunciado: str, excluir_id: str | None = None,
                    minimo: float = 0.5, limite: int = 5) -> list[tuple[float, QuestoesBanco]]:
    alvo = trigramas(normalizar(enunciado))
    if len(alvo) < 2:  # texto curto demais para comparar com segurança
        return []
    q = select(QuestoesBanco).where(QuestoesBanco.tenant_id == tenant_id)
    if excluir_id:
        q = q.where(QuestoesBanco.id_questao != excluir_id)
    achadas = []
    for questao in (await db.execute(q.limit(20000))).scalars():
        s = similaridade(alvo, trigramas(normalizar(questao.enunciado)))
        if s >= minimo:
            achadas.append((s, questao))
    achadas.sort(key=lambda x: -x[0])
    return achadas[:limite]
