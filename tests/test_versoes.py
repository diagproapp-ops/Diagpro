"""Histórico de versões (criar, editar, revisar, questão antiga) e busca de parecidas com sigilo entre professores."""
import json

import pytest
from sqlalchemy import select, text

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import VersaoQuestao
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers, com_evento_liberado

EV, CT = "c2438719-23aa-4f7d-8e0f-e6a310c10440", "ci-conteudo-1"
BASE = f"/eventos/{EV}/conteudos/{CT}/questoes"
ALTS = json.dumps([{"letra": L, "texto": f"<p>{L}</p>", "correta": L == "A"} for L in "ABCDE"])
ENUNCIADO = ("<p>Considerando os princípios expressos da administração pública previstos no artigo trinta e sete da "
             "Constituição Federal, assinale a alternativa que apresenta corretamente um desses princípios.</p>")
COMUM = {"tipo": "MULTIPLA_ESCOLHA", "indicacao_conteudo": "1", "enunciado": ENUNCIADO, "alternativas": ALTS,
         "nivel_dificuldade": "MEDIO", "pontuacao": "1", "tags": "", "justificativa_questao": "", "justificativa_anulacao": "",
         "resposta_correta": "A", "texto_referencia_vinculo": "", "texto_referencia_direto": "", "tenant_id": "1", "anulada": "false"}


@pytest.mark.asyncio
async def test_question_versions_and_similar_questions(async_client):
    reset_rate_limits()
    a1 = await com_evento_liberado(async_client, "admin1", UserRole.ADMIN, 1)  # fila/revisão: só com a senha do evento
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    hd = auth_headers("vhugo1234", UserRole.DIAGRAMADOR, tenant_id=1)

    # 1) criar = versão 1; editar = versão 2 (a 1 guarda o texto antigo)
    r = await async_client.post(BASE, headers=a1, data=COMUM)
    assert r.status_code == 200, r.text
    qid = r.json()["id_questao"]
    r = await async_client.put(f"{BASE}/{qid}", headers=a1, data={**COMUM, "enunciado": "<p>Texto totalmente novo da questão.</p>"})
    assert r.status_code == 200, r.text
    versoes = (await async_client.get(f"{BASE}/{qid}/versoes", headers=a1)).json()
    assert [(v["versao"], v["motivo"], v["autor"]) for v in versoes] == [(2, "editada", "admin1"), (1, "criada", "admin1")]
    v1 = (await async_client.get(f"{BASE}/{qid}/versoes/1", headers=a1)).json()
    assert v1["questao"]["enunciado"] == ENUNCIADO and len(v1["questao"]["alternativas"]) == 5
    assert (await async_client.get(f"{BASE}/{qid}/versoes/99", headers=a1)).status_code == 404

    # 2) revisão também vira versão
    dados = json.dumps({"tipo": "MULTIPLA_ESCOLHA", "itens_comando": [""], "respostas_certo_errado": [""],
                        "enunciado": "<p>Texto revisado.</p>", "alternativas": json.loads(ALTS), "resposta_correta": "A"})
    rv = {"status_revisao": "APROVADA", "observacao_revisor": "", "usuario_revisor": "x", "tenant_id": "1", "dados_revisao": dados}
    assert (await async_client.patch(f"{BASE}/{qid}/revisao", headers=a1, data=rv)).status_code == 200
    versoes = (await async_client.get(f"{BASE}/{qid}/versoes", headers=a1)).json()
    assert versoes[0]["versao"] == 3 and versoes[0]["motivo"] == "revisada: aprovada" and versoes[0]["resumo"] == "Texto revisado."

    # 3) cópia cifrada no banco; outra banca não vê o histórico
    async with PlatformSessionLocal() as s:
        crus = (await s.execute(text("SELECT snapshot FROM versoes_questao WHERE id_questao_fk = :q"), {"q": qid})).scalars().all()
    assert crus and all("princípios" not in c and "Texto revisado" not in c for c in crus)
    assert (await async_client.get(f"{BASE}/{qid}/versoes", headers=a2)).status_code in (403, 404)

    # 4) questão antiga (sem histórico): a 1ª edição guarda o estado anterior como versão 1
    antiga = (await async_client.post(BASE, headers=a1, data={**COMUM, "enunciado": "<p>Questão antiga.</p>"})).json()["id_questao"]
    async with PlatformSessionLocal() as s:  # simula questão de antes do histórico existir
        await s.execute(text("DELETE FROM versoes_questao WHERE id_questao_fk = :q"), {"q": antiga})
        await s.commit()
    r = await async_client.put(f"{BASE}/{antiga}", headers=a1, data={**COMUM, "enunciado": "<p>Questão antiga com acréscimo.</p>"})
    assert r.status_code == 200, r.text
    versoes = (await async_client.get(f"{BASE}/{antiga}/versoes", headers=a1)).json()
    assert [v["motivo"] for v in versoes] == ["editada", "anterior"]
    assert (await async_client.get(f"{BASE}/{antiga}/versoes/1", headers=a1)).json()["questao"]["enunciado"] == "<p>Questão antiga.</p>"
    await async_client.delete(f"{BASE}/{antiga}", headers=a1)

    # 5) parecidas: texto quase igual aparece com alto grau, para quem pode ver
    r = await async_client.post(BASE, headers=a1, data=COMUM)
    q2 = r.json()["id_questao"]
    parecido = ENUNCIADO.replace("assinale a alternativa", "marque a opção")
    achadas = (await async_client.post("/questoes/parecidas", headers=a1, json={"enunciado": parecido})).json()["parecidas"]
    assert achadas and achadas[0]["id_questao"] == q2 and achadas[0]["similaridade"] >= 70 and achadas[0]["codigo"]
    # sem contar a própria questão
    achadas = (await async_client.post("/questoes/parecidas", headers=a1, json={"enunciado": ENUNCIADO, "excluir_id": q2})).json()["parecidas"]
    assert all(a.get("id_questao") != q2 for a in achadas)
    # professor que não elaborou: só o aviso e o grau, nunca o texto nem o código
    prof = (await async_client.post("/questoes/parecidas", headers=hp, json={"enunciado": parecido})).json()["parecidas"]
    assert prof and prof[0]["detalhes_ocultos"] is True and "trecho" not in prof[0] and "codigo" not in prof[0]
    # outra banca não encontra nada; diagramador não usa
    assert (await async_client.post("/questoes/parecidas", headers=a2, json={"enunciado": parecido})).json()["parecidas"] == []
    assert (await async_client.post("/questoes/parecidas", headers=hd, json={"enunciado": parecido})).status_code == 403

    # 6) excluir a questão apaga o histórico dela
    assert (await async_client.delete(f"{BASE}/{qid}", headers=a1)).status_code == 200
    async with PlatformSessionLocal() as s:
        assert (await s.execute(select(VersaoQuestao).where(VersaoQuestao.id_questao_fk == qid))).scalars().all() == []
    await async_client.delete(f"{BASE}/{q2}", headers=a1)
    reset_rate_limits()
