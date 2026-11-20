# backend/app/recursos.py
"""
Recursos dos candidatos.

- O candidato recorre de "questão N do caderno Tipo X": o número é traduzido para a questão real pelo gabarito
  daquela variação (mesmo gerador e mesma semente da prova aplicada).
- A decisão é por questão (ou por item de Certo/Errado): manter, anular ou alterar o gabarito.
- A prova montada NUNCA é alterada (mudaria o caderno já impresso). O gabarito definitivo é calculado: o
  preliminar de cada variação com as decisões aplicadas; numa alteração, a nova alternativa (letra do banco) vira
  a letra impressa em cada caderno pelo mapa que o gerador expõe.
- Do candidato só ficam o protocolo e a argumentação, cifrados.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db_models import Cargo, DecisaoRecurso, ProvaMontada

PEDIDOS = ("anulacao", "alteracao", "outro")
DECISOES = ("manter", "anular", "alterar")


class ErroRecurso(Exception):
    pass


async def gabaritos_do_evento(db: AsyncSession, evento, gerar) -> dict[str, dict]:
    """{cargo_id: {"cargo": Cargo, "gabaritos": {variação: [entradas]}}} para os cargos com prova montada."""
    cargos = (await db.execute(select(Cargo).join(ProvaMontada, ProvaMontada.id_cargo_fk == Cargo.id_cargo)
                               .where(Cargo.id_evento_fk == evento.id_evento))).scalars().all()
    saida = {}
    for c in cargos:
        _, gabs = await gerar(db, evento, c.id_cargo)
        saida[c.id_cargo] = {"cargo": c, "gabaritos": gabs}
    return saida


def variacao(nome: str, disponiveis) -> str | None:
    from backend.app.estatisticas import _normalizar_variacao
    return _normalizar_variacao(nome, list(disponiveis))


def localizar(gabaritos: dict, tipo_prova: str, numero: int) -> tuple[str, dict]:
    var = variacao(tipo_prova, gabaritos.keys())
    if var is None:
        raise ErroRecurso(f"Tipo de prova '{tipo_prova}' não existe neste cargo.")
    entrada = next((e for e in gabaritos[var] if int(e.get("numero_questao_exibido") or 0) == int(numero)), None)
    if entrada is None or not entrada.get("id_questao"):
        raise ErroRecurso(f"A questão {numero} não existe no caderno {var}.")
    return var, entrada


def chave(entrada: dict) -> tuple[str, int | None]:
    return entrada.get("id_questao"), entrada.get("item")


def definitivo(entrada: dict, decisoes: dict) -> tuple[str, str | None]:
    """(letra definitiva, aviso). decisoes: {(id_questao, item): DecisaoRecurso}"""
    preliminar = str(entrada.get("gabarito_letra_exibida") or "")
    d = decisoes.get(chave(entrada))
    if d is None or d.decisao == "manter":
        return preliminar, None
    if d.decisao == "anular":
        return "ANULADA", None
    if entrada.get("tipo") == "CERTO_ERRADO":
        return (d.nova_correta or preliminar), None
    mapa = entrada.get("mapa_letras") or {}
    if d.nova_correta not in mapa:
        return preliminar, f"Alternativa {d.nova_correta} não existe nesta questão; gabarito mantido."
    return mapa[d.nova_correta], None


async def decisoes_do_evento(db: AsyncSession, evento_id: str) -> dict:
    return {(d.id_questao, d.item): d for d in (await db.execute(
        select(DecisaoRecurso).where(DecisaoRecurso.evento_id == evento_id))).scalars()}
