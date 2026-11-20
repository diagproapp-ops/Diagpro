"""Entrega segura de pacotes: código obrigatório, bloqueio por erros, limite, validade, revogação, isolamento e avisos."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text

from backend.app import entregas, secure_files
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Entrega, Notificacao, User
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

EV = "c2438719-23aa-4f7d-8e0f-e6a310c10440"
ZIP_FALSO = b"PK\x03\x04" + b"conteudo-sigiloso-da-prova" * 50


async def _criar(horas=24, max_dl=2):
    async with PlatformSessionLocal() as s:
        adm = next(u for u in (await s.execute(select(User))).scalars() if u.username == "admin1")
        e, codigo = entregas.criar(s, 1, EV, adm.id, ZIP_FALSO, "Provas_Teste.zip", horas, max_dl, "Gráfica Exemplo", ["Cargo A"])
        await s.commit()
        return e.id, codigo, adm.id


@pytest.mark.asyncio
async def test_secure_delivery_link_code_limits_expiry_and_revocation(async_client):
    reset_rate_limits()
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    try:
        # 1) validação na exportação: antes de gerar qualquer coisa
        base = {"cargos_id": ["x"], "senha": "1234"}
        url = f"/api/export/eventos/{EV}/cargos/gerar-arquivos-multiplos"
        r = await async_client.post(url, headers=a1, json={**base, "entrega": {"horas": 100, "max_downloads": 1, "destinatario": "G"}})
        assert r.status_code == 400
        r = await async_client.post(url, headers=a1, json={**base, "exibir_gabarito_marcado": True,
                                                         "entrega": {"horas": 2, "max_downloads": 1, "destinatario": "G"}})
        assert r.status_code == 400 and "gabarito marcado" in r.json()["detail"]
        reset_rate_limits()

        # 2) arquivo guardado cifrado; código só como hash
        eid, codigo, adm_id = await _criar()
        async with PlatformSessionLocal() as s:
            e = await s.get(Entrega, eid)
            ref = e.arquivo
            cru = (await s.execute(text("SELECT codigo_hash, arquivo, detalhes FROM entregas WHERE id = :i"), {"i": eid})).one()
        assert codigo not in "".join(cru) and "Gráfica" not in cru[2]
        blob = secure_files._blob_path(*secure_files.parse_ref(ref)[:2]).read_bytes()
        assert b"conteudo-sigiloso" not in blob

        # 3) página pública mostra o mínimo; sem código não baixa
        info = (await async_client.get(f"/entrega/{eid}/info")).json()
        assert info["situacao"] == "ativa" and info["downloads_restantes"] == 2 and "cargos" not in info
        assert (await async_client.post(f"/entrega/{eid}/baixar", json={"codigo": "AAAA-BBBB-CCCC"})).status_code == 403
        # código certo (com minúsculas/sem hífen também vale): baixa e conta
        r = await async_client.post(f"/entrega/{eid}/baixar", json={"codigo": codigo.replace("-", "").lower()})
        assert r.status_code == 200 and r.content == ZIP_FALSO and "Provas_Teste.zip" in r.headers["content-disposition"]
        # quem criou é avisado
        async with PlatformSessionLocal() as s:
            assert any((n.conteudo or {}).get("titulo") == "Pacote de prova baixado" for n in (await s.execute(
                select(Notificacao).where(Notificacao.usuario_id == adm_id))).scalars())
        # 2º download esgota e apaga o arquivo
        assert (await async_client.post(f"/entrega/{eid}/baixar", json={"codigo": codigo})).status_code == 200
        r = await async_client.post(f"/entrega/{eid}/baixar", json={"codigo": codigo})
        assert r.status_code == 410
        async with PlatformSessionLocal() as s:
            e = await s.get(Entrega, eid)
            assert e.arquivo is None and e.motivo_encerramento == "esgotada" and len(e.detalhes["log"]) == 2
        assert not secure_files._blob_path(*secure_files.parse_ref(ref)[:2]).exists()
        reset_rate_limits()

        # 4) 5 códigos errados bloqueiam o link
        eid2, codigo2, _ = await _criar()
        for i in range(5):
            assert (await async_client.post(f"/entrega/{eid2}/baixar", json={"codigo": f"ERRADO-{i}xxxxx"})).status_code == 403
        reset_rate_limits()
        assert (await async_client.post(f"/entrega/{eid2}/baixar", json={"codigo": codigo2})).status_code == 410

        # 5) revogação: só a banca dona; outra banca nem vê
        eid3, codigo3, _ = await _criar()
        assert (await async_client.post(f"/api/export/entregas/{eid3}/revogar", headers=a2)).status_code == 404
        assert (await async_client.post(f"/api/export/entregas/{eid3}/revogar", headers=hp)).status_code == 403
        assert (await async_client.post(f"/api/export/entregas/{eid3}/revogar", headers=a1)).json()["situacao"] == "revogada"
        assert (await async_client.post(f"/entrega/{eid3}/baixar", json={"codigo": codigo3})).status_code == 410
        lista = (await async_client.get(f"/api/export/eventos/{EV}/entregas", headers=a1)).json()
        assert {x["id"] for x in lista} >= {eid, eid2, eid3} and all("codigo" not in x for x in lista)
        assert (await async_client.get(f"/api/export/eventos/{EV}/entregas", headers=a2)).status_code in (403, 404)

        # 6) validade: vencida não baixa e a limpeza apaga o arquivo
        eid4, codigo4, _ = await _criar(horas=1)
        async with PlatformSessionLocal() as s:
            e = await s.get(Entrega, eid4)
            e.expira_em = datetime.utcnow() - timedelta(minutes=1)
            ref4 = e.arquivo
            await s.commit()
        assert await entregas.limpar_vencidas() >= 1
        assert not secure_files._blob_path(*secure_files.parse_ref(ref4)[:2]).exists()
        assert (await async_client.post(f"/entrega/{eid4}/baixar", json={"codigo": codigo4})).status_code == 410
        assert (await async_client.get("/entrega/naoexiste/info")).status_code == 404
    finally:
        async with PlatformSessionLocal() as s:
            for e in (await s.execute(select(Entrega))).scalars():
                secure_files.delete(e.arquivo)
            await s.execute(text("DELETE FROM entregas"))
            await s.execute(text("DELETE FROM notificacoes"))
            await s.commit()
        reset_rate_limits()


def test_delivery_code_format():
    c = entregas.novo_codigo()
    assert len(c) == 14 and c[4] == "-" and c[9] == "-" and not set(c.replace("-", "")) & set("01OI")
    assert entregas._normalizar(c.replace("-", "").lower()) == c
