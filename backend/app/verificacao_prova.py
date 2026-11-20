# backend/app/verificacao_prova.py
"""
Checagem da prova montada ANTES de diagramar/exportar.

- bloqueios: a prova sairia errada (ex.: alternativa sem texto vira "<<ALTERNATIVA SEM TEXTO>>" impresso,
  questão sem alternativa correta, questão repetida). A exportação é recusada até corrigir.
- avisos: a prova sai, mas alguém precisa saber (questão não aprovada na revisão, editada depois da montagem,
  tipo que a diagramação ainda não imprime, quantidade diferente da prevista no cargo).

Não devolve conteúdo de prova: só número, código curto, disciplina e o tipo do problema.
"""
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import configuracoes, equacoes
from backend.app.dados_prova import LINHAS_PADRAO_SUBJETIVA, completar_questoes
from backend.app.db_models import DisciplinaDaProva, QuestoesBanco

_TAGS = re.compile(r"<[^>]+>")


def _texto(html) -> str:
    """Texto visível; uma equação conta como conteúdo (o texto dela fica no atributo data-latex)."""
    texto = _TAGS.sub("", str(html or "")).replace("&nbsp;", " ").strip()
    if not texto and any(lx.strip() for lx in equacoes.equacoes_no_html(html)):
        return "[equação]"
    return texto


def _equacoes_com_problema(q: dict) -> list[str]:
    """Onde há equação que não pode ser impressa (sem expor o conteúdo da equação)."""
    locais = []
    def checar(html, onde):
        for k, lx in enumerate(equacoes.equacoes_no_html(html), start=1):
            if equacoes.validar(lx):
                locais.append(f"{onde} (equação {k})")
    checar(q.get("enunciado"), "enunciado")
    for i, o in enumerate(q.get("opcoes") or []):
        checar(o.get("texto_opcao"), f"alternativa {chr(ord('A') + i)}")
    for i, it in enumerate(q.get("itens_vf") or [], start=1):
        checar(it.get("afirmacao"), f"item {i}")
    return locais


async def verificar_prova(db: AsyncSession, cargo, prova_montada, blocos: list) -> dict:
    bloqueios: list[dict] = []
    avisos: list[dict] = []
    await completar_questoes(db, blocos)
    tenant_cargo = getattr(cargo, "tenant_id", None)
    revisao_obrigatoria = bool(tenant_cargo) and (await configuracoes.ler_banca(db, tenant_cargo))["regras_questoes"]["revisao_obrigatoria"]
    itens = [(b, q) for b in (blocos or []) if isinstance(b, dict) for q in (b.get("questoes") or [])]
    ids = [q.get("id_questao") for _, q in itens if q.get("id_questao")]
    no_banco = {}
    if ids:
        for q in (await db.execute(select(QuestoesBanco).where(QuestoesBanco.id_questao.in_(ids)))).scalars():
            no_banco[q.id_questao] = q

    montada_em = getattr(prova_montada, "data_modificacao", None) or getattr(prova_montada, "data_criacao", None)
    vistos = set()
    for numero, (bloco, q) in enumerate(itens, start=1):
        id_q = q.get("id_questao")
        atual = no_banco.get(id_q)
        codigo = q.get("codigo_curto_questao") or getattr(atual, "codigo_curto_questao", None) or f"nº {numero}"
        disciplina = bloco.get("nome_disciplina_na_prova") or bloco.get("nome_disciplina") or ""

        def add(lista, problema):
            lista.append({"questao": numero, "codigo": codigo, "disciplina": disciplina, "problema": problema})

        if id_q in vistos:
            add(bloqueios, "Questão repetida na prova.")
        vistos.add(id_q)

        tipo = str(getattr(atual, "tipo", None) or q.get("tipo") or "MULTIPLA_ESCOLHA").upper()
        for local in _equacoes_com_problema(q):
            add(bloqueios, f"Equação que não pode ser impressa no {local}: abra a questão no editor para corrigir.")
        if not _texto(q.get("enunciado")) and not q.get("caminho_imagem_relativo"):
            add(bloqueios, "Enunciado vazio.")

        if tipo == "CERTO_ERRADO":
            itens_vf = q.get("itens_vf") or []
            if not itens_vf:
                add(bloqueios, "Questão Certo/Errado sem itens.")
            for pos, it in enumerate(itens_vf, start=1):
                if not _texto(it.get("afirmacao")) and not it.get("imagem_path_item"):
                    add(bloqueios, f"Item {pos} da Certo/Errado sem texto nem imagem.")
                if not isinstance(it.get("valor_correto"), bool):
                    add(bloqueios, f"Item {pos} da Certo/Errado sem resposta (Certo ou Errado).")
        elif tipo == "SUBJETIVA":
            if not (q.get("detalhes_discursiva") or {}).get("numero_linhas_resposta"):
                add(avisos, f"Subjetiva sem quantidade de linhas definida: sairá com {LINHAS_PADRAO_SUBJETIVA} linhas.")
        elif "DISCURSIVA" in tipo:
            if "discursiva" not in disciplina.lower():
                add(avisos, "Questão Discursiva fora de um bloco \"Discursiva\": a diagramação não a imprime.")
        else:
            opcoes = q.get("opcoes") or []
            if not opcoes:
                add(bloqueios, "Questão sem alternativas.")
            else:
                corretas = sum(1 for o in opcoes if o.get("correta"))
                if corretas == 0:
                    add(bloqueios, "Nenhuma alternativa marcada como correta.")
                elif corretas > 1:
                    add(bloqueios, f"{corretas} alternativas marcadas como corretas.")
                vazias = [chr(ord("A") + i) for i, o in enumerate(opcoes)
                          if not _texto(o.get("texto_opcao")) and not o.get("imagem_path_opcao")]
                if vazias:
                    add(bloqueios, f"Alternativa(s) sem texto nem imagem (posição original {', '.join(vazias)}).")

        if atual is None:
            add(avisos, "A questão foi excluída do banco; a prova usa a cópia guardada na montagem.")
        else:
            status = (atual.status_revisao or "").upper()
            if status != "APROVADA":
                # a banca pode exigir revisão aprovada (Configurações > Regras das questões)
                add(bloqueios if revisao_obrigatoria else avisos,
                    f"Não aprovada na revisão ({status.title() if status else 'sem revisão'}).")
            if getattr(atual, "anulada", False):
                add(avisos, "Questão marcada como anulada.")
            alterada = getattr(atual, "data_modificacao", None)
            if alterada and montada_em and alterada > montada_em:
                add(avisos, "Editada depois da montagem: a prova usa a versão da montagem (remonte para atualizar).")

    previsto = (await db.execute(
        select(func.coalesce(func.sum(DisciplinaDaProva.qtd_questoes), 0))
        .where(DisciplinaDaProva.id_cargo_fk == cargo.id_cargo)
    )).scalar() or 0
    gerais = []
    if previsto and previsto != len(itens):
        gerais.append(f"A prova tem {len(itens)} questão(ões); o cargo prevê {previsto}.")

    return {
        "id_cargo": cargo.id_cargo,
        "cargo": f"{cargo.codigo_cargo or ''} - {cargo.nome_cargo or ''}".strip(" -"),
        "total_questoes": len(itens),
        "bloqueios": bloqueios,
        "avisos": avisos,
        "avisos_gerais": gerais,
    }
