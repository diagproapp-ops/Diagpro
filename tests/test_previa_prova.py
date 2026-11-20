"""Pré-visualização da prova real: mesma geração da exportação, páginas como imagens, senha e auditoria."""
import base64
import io

from sqlalchemy import select

from backend.app.database import PlatformSessionLocal
from backend.app.db_models import AuditLogGeracao
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

EV = "c2438719-23aa-4f7d-8e0f-e6a310c10440"


async def test_real_exam_preview_uses_export_generation_and_is_protected(async_client):
    from core.document_generator import PdfConverter
    from PIL import Image

    reset_rate_limits()
    h = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    import json as _json
    alts = [{"letra": L, "texto": f"<p>Alternativa {L}</p>", "correta": L == "C"} for L in "ABCDE"]
    r = await async_client.post(f"/eventos/{EV}/conteudos/ci-conteudo-1/questoes", headers=h, data={
        "tipo": "MULTIPLA_ESCOLHA", "indicacao_conteudo": "1", "enunciado": "<p>Questão da pré-visualização</p>",
        "alternativas": _json.dumps(alts), "nivel_dificuldade": "MEDIO", "pontuacao": "1", "tags": "", "anulada": "false",
        "justificativa_questao": "", "justificativa_anulacao": "", "resposta_correta": "C",
        "texto_referencia_vinculo": "", "texto_referencia_direto": "", "tenant_id": "1"})
    assert r.status_code == 200, r.text
    id_questao = r.json()["id_questao"]
    r = await async_client.post(f"/eventos/{EV}/cargos", headers=h, json={
        "nome_cargo": "Cargo Previa Teste", "codigo_cargo": "PVT-01", "nivel": "Médio", "turno": "Manhã",
        "disciplinas_prova": [{"nome_disciplina": "Conteudo CI", "qtd_questoes": 1, "peso_por_questao": 1, "ordem_na_prova": 1,
                               "tipo_conhecimento": "comum"}]})
    assert r.status_code == 201, r.text
    cargo = r.json()["id_cargo"]
    r = await async_client.post(f"/provas/eventos/{EV}/provas-montadas/{cargo}", headers=h, json={
        "nome_prova_montada": "Prova Previa", "blocos_questoes": [
            {"id_bloco": "b1", "nome_disciplina": "Conteudo CI", "qtd_questoes": 1, "peso": 1, "ordem": 1, "conhecimento_basico": True}]})
    assert r.status_code == 200, r.text
    url = f"/api/export/eventos/{EV}/preview-prova"
    corpo = {"cargo_id": cargo, "fonte": "Arial", "tamanhoFonte": 11, "duasColunas": False, "quebraBloco": True}
    try:
        assert (await async_client.post(url, headers=h, json={**corpo, "senha": "errada"})).status_code == 403
        assert (await async_client.post(url, headers=h, json={"senha": "1234"})).status_code == 400
        assert (await async_client.post(url, headers=hp, json={**corpo, "senha": "1234"})).status_code == 403
        r = await async_client.post(url, headers=h, json={**corpo, "senha": "1234"})
        if not PdfConverter().soffice_path:  # CI sem LibreOffice: falha clara, sem vazar detalhes
            assert r.status_code == 500 and "detail" in r.json()
            return
        assert r.status_code == 200, r.text
        dados = r.json()
        assert dados["tipo"] == "PADRÃO" and dados["total_paginas"] >= 1 and dados["num_variacoes"] == 1
        # imagens JPEG (não o PDF): a prévia não vira arquivo da prova
        primeira = dados["paginas"][0]
        assert primeira.startswith("data:image/jpeg;base64,") and "application/pdf" not in r.text
        img = Image.open(io.BytesIO(base64.b64decode(primeira.split(",", 1)[1])))
        assert img.format == "JPEG" and img.width > 800
        # quem viu a prova fica registrado
        async with PlatformSessionLocal() as s:
            acoes = (await s.execute(select(AuditLogGeracao.acao).where(AuditLogGeracao.tenant_id == 1))).scalars().all()
        assert "previsualizacao_prova" in acoes
    finally:
        await async_client.delete(f"/eventos/{EV}/cargos/{cargo}", headers=h)
        await async_client.delete(f"/eventos/{EV}/conteudos/ci-conteudo-1/questoes/{id_questao}", headers=h)
