"""Estatísticas pós-prova (análise de itens com dados sintéticos) e painel da banca."""
import random

import pytest

from backend.app import estatisticas
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

EV = "c2438719-23aa-4f7d-8e0f-e6a310c10440"


def _gabarito(letras, prefixo="Q"):
    return [{"numero_questao_exibido": i + 1, "gabarito_letra_exibida": l, "codigo_curto_questao": f"{prefixo}{i + 1}"}
            for i, l in enumerate(letras)]


NORMAIS = "BCDE" * 5  # 20 questões normais


def _respostas_sinteticas(n=100, semente=7):
    """Q1 fácil; Q2..Q21 normais (quem é melhor acerta mais); Q22 com GABARITO ERRADO (a letra 'certa' é a que
    os melhores evitam); Q23 anulada."""
    rnd = random.Random(semente)
    linhas = []
    for i in range(n):
        habilidade = i / n
        r = ["A"]
        for certa in NORMAIS:
            r.append(certa if rnd.random() < 0.15 + 0.8 * habilidade else "A")
        r.append("E" if rnd.random() < 0.15 + 0.8 * habilidade else "A")  # gabarito diz A, mas os bons marcam E
        r.append("C")
        linhas.append(("PADRAO", "".join(r)))
    return linhas


def test_item_analysis_flags_wrong_key_easy_item_and_ignores_annulled():
    gab = {"PADRÃO": _gabarito(["A", *NORMAIS, "A", "ANULADA"])}
    res = estatisticas.analisar(gab, _respostas_sinteticas())
    itens = {i["codigo"]: i for i in res["itens"]}
    assert res["candidatos"] == 100 and res["questoes"] == 22 and res["anuladas"] == ["Q23"] and "Q23" not in itens
    assert itens["Q22"]["discriminacao"] < 0 and any("negativa" in a for a in itens["Q22"]["alertas"])
    assert itens["Q1"]["acerto"] == 100.0 and any("fácil demais" in a for a in itens["Q1"]["alertas"])
    assert sum(itens[f"Q{k}"]["discriminacao"] > 0.2 for k in range(2, 22)) >= 18  # as normais discriminam bem
    assert res["itens"][0]["codigo"] == "Q22"  # o pior problema aparece primeiro
    assert res["kr20"] > 0.7


def test_csv_reading_ignores_personal_columns_and_validates():
    csv_ = "inscricao;nome;tipo_prova;respostas\n" + "\n".join(f"{1000 + i};Fulano {i};PADRÃO;ABCD" for i in range(30))
    linhas = estatisticas.ler_csv(csv_.encode("utf-8"))
    assert linhas[0] == ("PADRÃO", "ABCD") and all(len(l) == 2 for l in linhas)  # só variação e respostas
    res = estatisticas.analisar({"PADRÃO": _gabarito("ABCD")}, linhas + [("PADRÃO", "AB")])
    assert "Fulano" not in str(res) and "1000" not in str(res)
    assert res["linhas_ignoradas"] == 1 and "2 respostas" in res["problemas"][0]
    with pytest.raises(estatisticas.ErroAnalise):
        estatisticas.ler_csv(b"inscricao;resp\n1;ABC")
    with pytest.raises(estatisticas.ErroAnalise, match="10 candidatos"):
        estatisticas.analisar({"PADRÃO": _gabarito("AB")}, [("PADRÃO", "AB")] * 5)
    # variações com e sem acento / número
    gab = {"Tipo 1": _gabarito("AB"), "Tipo 2": _gabarito("BA")}
    res = estatisticas.analisar(gab, [("1", "AB")] * 6 + [("tipo 2", "BA")] * 6)
    assert res["candidatos"] == 12 and all(i["acerto"] == 100.0 for i in res["itens"])


@pytest.mark.asyncio
async def test_analysis_endpoint_rules_and_bank_dashboard(async_client):
    reset_rate_limits()
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    arquivo = {"arquivo": ("respostas.csv", b"tipo_prova;respostas\nPADRAO;AB\n", "text/csv")}
    url = f"/estatisticas/eventos/{EV}/cargos/nao-existe/analisar"
    # sem a senha do evento: nada
    assert (await async_client.post(url, headers=a1, files=arquivo)).status_code == 403
    # professor não analisa; outra banca não acha o evento
    assert (await async_client.post(url, headers={**hp, "X-Senha-Evento": "1234"}, files=arquivo)).status_code == 403
    assert (await async_client.post(url, headers={**a2, "X-Senha-Evento": "1234"}, files=arquivo)).status_code == 404
    # com senha, cargo inexistente
    assert (await async_client.post(url, headers={**a1, "X-Senha-Evento": "1234"}, files=arquivo)).status_code == 404
    reset_rate_limits()
    # painel da banca
    p = (await async_client.get("/painel/banca", headers=a1)).json()
    assert p["eventos"] >= 1 and "por_estado" in p["questoes"] and p["por_evento"][0]["nome"]
    assert (await async_client.get("/painel/banca", headers=hp)).status_code == 403
    assert all(e["nome"] != "Evento CI Teste" for e in (await async_client.get("/painel/banca", headers=a2)).json()["por_evento"])
