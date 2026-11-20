"""Recursos: tradução número->questão por caderno, decisão por questão/item, gabarito definitivo calculado
(a prova não muda), parecer só de quem pode, dados do candidato cifrados e isolamento."""
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from backend.app import recursos as rc
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Recurso
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

EV = "c2438719-23aa-4f7d-8e0f-e6a310c10440"

# dois cadernos com a mesma questão Q1 em posições e letras diferentes (alternativas embaralhadas)
GABS = {
    "Tipo 1": [
        {"numero_questao_exibido": 1, "id_questao": "q1", "tipo": "MULTIPLA_ESCOLHA", "gabarito_letra_exibida": "B",
         "mapa_letras": {"A": "B", "B": "D", "C": "A", "D": "C", "E": "E"}, "codigo_curto_questao": "Q-1"},
        {"numero_questao_exibido": 2, "id_questao": "q2", "tipo": "CERTO_ERRADO", "item": 1, "gabarito_letra_exibida": "C", "codigo_curto_questao": "Q-2"},
        {"numero_questao_exibido": 3, "id_questao": "q2", "tipo": "CERTO_ERRADO", "item": 2, "gabarito_letra_exibida": "E", "codigo_curto_questao": "Q-2"},
    ],
    "Tipo 2": [
        {"numero_questao_exibido": 1, "id_questao": "q2", "tipo": "CERTO_ERRADO", "item": 1, "gabarito_letra_exibida": "C", "codigo_curto_questao": "Q-2"},
        {"numero_questao_exibido": 2, "id_questao": "q2", "tipo": "CERTO_ERRADO", "item": 2, "gabarito_letra_exibida": "E", "codigo_curto_questao": "Q-2"},
        {"numero_questao_exibido": 3, "id_questao": "q1", "tipo": "MULTIPLA_ESCOLHA", "gabarito_letra_exibida": "E",
         "mapa_letras": {"A": "E", "B": "A", "C": "B", "D": "D", "E": "C"}, "codigo_curto_questao": "Q-1"},
    ],
}


def _d(decisao, nova=None):
    return SimpleNamespace(decisao=decisao, nova_correta=nova)


def test_number_translation_and_definitive_key_per_booklet():
    var, e = rc.localizar(GABS, "tipo 2", 3)
    assert var == "Tipo 2" and rc.chave(e) == ("q1", None)
    with pytest.raises(rc.ErroRecurso):
        rc.localizar(GABS, "Tipo 9", 1)
    with pytest.raises(rc.ErroRecurso):
        rc.localizar(GABS, "Tipo 1", 50)
    # alterar Q1 para a alternativa C do banco: vira A no Tipo 1 e B no Tipo 2
    dec = {("q1", None): _d("alterar", "C")}
    assert rc.definitivo(GABS["Tipo 1"][0], dec)[0] == "A"
    assert rc.definitivo(GABS["Tipo 2"][2], dec)[0] == "B"
    # anular só o item 2 da Q2 (Certo/Errado): item 1 continua
    dec = {("q2", 2): _d("anular")}
    assert rc.definitivo(GABS["Tipo 1"][2], dec)[0] == "ANULADA" and rc.definitivo(GABS["Tipo 1"][1], dec)[0] == "C"
    # manter e alternativa inexistente não mudam nada
    assert rc.definitivo(GABS["Tipo 1"][0], {("q1", None): _d("manter")})[0] == "B"
    letra, aviso = rc.definitivo(GABS["Tipo 1"][0], {("q1", None): _d("alterar", "F")})
    assert letra == "B" and aviso


@pytest.mark.asyncio
async def test_appeals_decision_opinion_rules_and_isolation(async_client):
    reset_rate_limits()
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    try:
        # cadastrar exige a senha do evento (traduz o número pelo gabarito)
        corpo = {"cargo_id": "x", "tipo_prova": "PADRÃO", "numero_questao": 1, "pedido": "anulacao"}
        assert (await async_client.post(f"/recursos/eventos/{EV}", headers=a1, json=corpo)).status_code == 403
        assert (await async_client.post(f"/recursos/eventos/{EV}", headers={**hp, "X-Senha-Evento": "1234"}, json=corpo)).status_code == 403
        reset_rate_limits()
        # recurso gravado (como o cadastro faria) sobre a questão do evento
        async with PlatformSessionLocal() as s:
            s.add(Recurso(tenant_id=1, evento_id=EV, cargo_id="c1", tipo_prova="PADRÃO", numero_questao=1, id_questao="ci-questao-1",
                          pedido="anulacao", status="pendente", criado_em=datetime.utcnow(), protocolo="PROT-777",
                          argumentacao="Candidato Fulano: a questão tem duas respostas"))
            await s.commit()
            cru = (await s.execute(text("SELECT protocolo, argumentacao FROM recursos"))).one()
        assert "PROT-777" not in cru[0] and "Fulano" not in cru[1]  # cifrados
        lista = (await async_client.get(f"/recursos/eventos/{EV}", headers=a1)).json()
        assert lista["total_recursos"] == 1 and lista["questoes"][0]["codigo"] == "Q-CI0001"
        rid = lista["questoes"][0]["recursos"][0]["id"]
        assert lista["questoes"][0]["recursos"][0]["protocolo"] == "PROT-777"
        # outra banca não vê nem decide
        assert (await async_client.get(f"/recursos/eventos/{EV}", headers=a2)).status_code in (403, 404)
        assert (await async_client.put(f"/recursos/{rid}/parecer", headers=a2, json={"parecer": "x"})).status_code == 404
        # professor que não elaborou não dá parecer; administrador dá
        assert (await async_client.put(f"/recursos/{rid}/parecer", headers=hp, json={"parecer": "x"})).status_code == 403
        assert (await async_client.put(f"/recursos/{rid}/parecer", headers=a1, json={"parecer": "Procede."})).status_code == 200
        # decisão: alterar exige a nova resposta; professor não decide
        url = f"/recursos/eventos/{EV}/questoes/ci-questao-1/decidir"
        assert (await async_client.post(url, headers=hp, json={"decisao": "anular", "justificativa": "Duas respostas."})).status_code == 403
        assert (await async_client.post(url, headers=a1, json={"decisao": "alterar", "justificativa": "Gabarito correto é C."})).status_code == 400
        r = await async_client.post(url, headers=a1, json={"decisao": "anular", "justificativa": "A questão admite duas respostas."})
        assert r.status_code == 200 and r.json()["status_recursos"] == "deferido"
        # mudar de ideia atualiza a mesma decisão
        r = await async_client.post(url, headers=a1, json={"decisao": "manter", "justificativa": "Não procede: só a alternativa A atende."})
        assert r.json()["status_recursos"] == "indeferido"
        g = (await async_client.get(f"/recursos/eventos/{EV}", headers=a1)).json()["questoes"][0]
        assert g["decisao"]["decisao"] == "manter" and g["recursos"][0]["status"] == "indeferido" and g["recursos"][0]["parecer"] == "Procede."
        # gabarito definitivo exige a senha do evento
        assert (await async_client.get(f"/recursos/eventos/{EV}/gabarito-definitivo", headers=a1)).status_code == 403
    finally:
        async with PlatformSessionLocal() as s:
            await s.execute(text("DELETE FROM recursos"))
            await s.execute(text("DELETE FROM decisoes_recurso"))
            await s.execute(text("DELETE FROM notificacoes"))
            await s.commit()
        reset_rate_limits()
