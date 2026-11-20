"""Assistente de IA: liga/desliga, sigilo do que é enviado, limites, isolamento e chaves nunca expostas.
Nenhum teste chama um provedor de verdade: `chamar_provedor` é trocado por um falso que registra o pedido."""
import json

import pytest
from sqlalchemy import select, text

from backend.app import assistente_ia
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import UsoIA
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

CHAVE_FALSA = "sk-teste-" + "x" * 30 + "WXYZ"
SEGREDO_DO_ENUNCIADO = "ENUNCIADO-SIGILOSO-123"


class ProvedorFalso:
    def __init__(self):
        self.pedidos = []

    async def __call__(self, provedor, modelo, chave, sistema, mensagem, schema, max_tokens=8000):
        self.pedidos.append({"provedor": provedor, "modelo": modelo, "chave": chave, "sistema": sistema,
                             "mensagem": mensagem, "schema": schema})
        props = schema["properties"]
        if "enunciado" in props:  # gerar questão
            dados = {"enunciado": "Qual é a capital do Brasil?", "alternativas": [{"letra": L, "texto": t} for L, t in
                     zip("ABCDE", ["Brasília", "Rio de Janeiro", "São Paulo", "Salvador", "Recife"])],
                     "correta": "A", "itens": [], "palavras_chave": [], "padrao_resposta": "", "justificativa": "Brasília é a capital.", "avisos": []}
        elif "avaliacao" in props:
            dados = {"avaliacao": "ajustar", "resumo": "ok", "problemas": [], "gabarito_confere": True, "comentario_gabarito": "", "nivel_estimado": "MEDIO"}
        else:
            dados = {k: ([] if v.get("type") == "array" else True if v.get("type") == "boolean" else "texto") for k, v in props.items()}
        return assistente_ia.RespostaIA(dados, 100, 50)


async def _apagar_usos():
    async with PlatformSessionLocal() as s:
        await s.execute(text("DELETE FROM uso_ia"))
        await s.commit()


@pytest.mark.asyncio
async def test_ai_assistant_rules_secrecy_and_limits(async_client, monkeypatch):
    reset_rate_limits()
    await _apagar_usos()
    falso = ProvedorFalso()
    monkeypatch.setattr(assistente_ia, "chamar_provedor", falso)
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    a2 = auth_headers("admin2", UserRole.ADMIN, tenant_id=2)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    hd = auth_headers("vhugo1234", UserRole.DIAGRAMADOR, tenant_id=1)
    pedido = {"tipo": "MULTIPLA_ESCOLHA", "assunto": "Geografia do Brasil", "nivel": "FACIL",
              "instrucoes": "<p>Sobre capitais</p>", "texto_base": '<p>Texto</p><img src="data:image/png;base64,AAAABBBBCCCC">'}
    try:
        # 1) tudo desligado por padrão: nada sai para a IA
        assert (await async_client.post("/ia/questao/gerar", headers=hp, json=pedido)).status_code == 403
        assert (await async_client.get("/ia/status", headers=hp)).json()["disponivel"] is False

        # 2) plataforma liga + chave; a chave nunca volta para a tela
        r = await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": True, "provedor": "anthropic",
                                   "limite_diario_usuario": 3, "chaves": {"anthropic": CHAVE_FALSA}}})
        assert r.status_code == 200, r.text
        info = r.json()["ia"]["chaves"]["anthropic"]
        assert CHAVE_FALSA not in r.text and info["definida"] is True and info["final"].endswith("WXYZ")
        lido = await async_client.get("/config/plataforma", headers=ag)
        assert CHAVE_FALSA not in lido.text and "x" * 30 not in lido.text
        # a chave fica cifrada no banco
        async with PlatformSessionLocal() as s:
            cru = (await s.execute(text("SELECT dados FROM configuracoes WHERE tenant_id IS NULL"))).scalar_one()
        assert CHAVE_FALSA not in cru and "anthropic" not in cru

        # 3) a banca ainda não ligou
        assert (await async_client.post("/ia/questao/gerar", headers=hp, json=pedido)).status_code == 403
        # banca não pode passar do limite diário da plataforma
        assert (await async_client.put("/config/banca", headers=a1, json={"ia": {"limite_diario_usuario": 10}})).status_code == 400
        r = await async_client.put("/config/banca", headers=a1, json={"ia": {"habilitada": True, "orientacoes_banca": "Use o padrão ESTILO-BANCA-1."}})
        assert r.status_code == 200 and r.json()["ia"]["habilitada"] is True
        assert (await async_client.get("/ia/status", headers=hp)).json()["disponivel"] is True

        # 4) professor gera um rascunho; o que sai é só o que ele mandou, sem HTML nem imagem
        r = await async_client.post("/ia/questao/gerar", headers=hp, json=pedido)
        assert r.status_code == 200, r.text
        assert r.json()["correta"] == "A" and len(r.json()["alternativas"]) == 5
        enviado = falso.pedidos[-1]
        assert enviado["chave"] == CHAVE_FALSA and enviado["provedor"] == "anthropic" and enviado["modelo"] == "claude-opus-5-5"
        assert "Geografia do Brasil" in enviado["mensagem"] and "Sobre capitais" in enviado["mensagem"]
        assert "<p>" not in enviado["mensagem"] and "base64" not in enviado["mensagem"] and "AAAABBBB" not in enviado["mensagem"]
        assert "ESTILO-BANCA-1" in enviado["sistema"]
        # o schema é estrito (todos os campos obrigatórios, nada além deles) — exigência dos dois provedores
        assert enviado["schema"]["additionalProperties"] is False and set(enviado["schema"]["required"]) == set(enviado["schema"]["properties"])

        # 5) revisão: o enunciado vai, mas não fica gravado em lugar nenhum
        r = await async_client.post("/ia/questao/revisar", headers=hp, json={"tipo": "MULTIPLA_ESCOLHA", "enunciado": f"<p>{SEGREDO_DO_ENUNCIADO}</p>",
                                    "alternativas": [{"letra": "A", "texto": "<p>x</p>"}], "correta": "A"})
        assert r.status_code == 200 and r.json()["avaliacao"] == "ajustar"
        assert SEGREDO_DO_ENUNCIADO in falso.pedidos[-1]["mensagem"]
        async with PlatformSessionLocal() as s:
            linhas = (await s.execute(select(UsoIA))).scalars().all()
            crus = (await s.execute(text("SELECT detalhes FROM uso_ia"))).scalars().all()
        assert len(linhas) == 2 and all(l.tenant_id == 1 and l.sucesso and l.tokens_entrada == 100 for l in linhas)
        assert {l.detalhes["recurso"] for l in linhas} == {"gerar_questao", "revisar_questao"}
        assert all(SEGREDO_DO_ENUNCIADO not in json.dumps(l.detalhes) for l in linhas)
        assert all("revisar_questao" not in c and "gerar_questao" not in c for c in crus)  # cifrado

        # 6) limite diário por usuário (3)
        r = await async_client.post("/ia/texto/melhorar", headers=hp, json={"texto": "<p>texto</p>", "modo": "clareza"})
        assert r.status_code == 200
        r = await async_client.post("/ia/chat", headers=hp, json={"mensagem": "oi"})
        assert r.status_code == 429

        # 7) perfil e recurso: diagramador não usa; recurso desligado pela banca é recusado
        assert (await async_client.post("/ia/chat", headers=hd, json={"mensagem": "oi"})).status_code == 403
        assert (await async_client.put("/config/banca", headers=a1, json={"ia": {"recursos": {"chat": False}}})).status_code == 200
        assert (await async_client.post("/ia/chat", headers=a1, json={"mensagem": "oi"})).status_code == 403
        assert (await async_client.get("/ia/status", headers=a1)).json()["recursos"]["chat"] is False

        # 8) isolamento: a banca 2 não ligou a IA, não vê o uso da banca 1 e não herda nada dela
        assert (await async_client.post("/ia/chat", headers=a2, json={"mensagem": "oi"})).status_code == 403
        assert (await async_client.get("/ia/uso", headers=a2)).json()["total"] == 0
        uso1 = (await async_client.get("/ia/uso", headers=a1)).json()
        assert uso1["total"] == 3 and uso1["tokens_entrada"] == 300 and uso1["por_recurso"]["gerar_questao"] == 1
        assert (await async_client.get("/ia/uso", headers=hp)).status_code == 403

        # 9) erro do provedor: mensagem segura, uso registrado como falha
        async def quebrado(*a, **k):
            raise assistente_ia.ErroIA("Serviço de IA indisponível no momento.", 502)
        monkeypatch.setattr(assistente_ia, "chamar_provedor", quebrado)
        r = await async_client.post("/ia/questao/justificativa", headers=a1, json={"enunciado": "<p>e</p>"})
        assert r.status_code == 502 and r.json()["detail"] == "Serviço de IA indisponível no momento."

        # 10) plataforma desliga: vale para todas as bancas na hora
        assert (await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": False}})).status_code == 200
        assert (await async_client.post("/ia/questao/revisar", headers=a1, json={"enunciado": "x"})).status_code == 403
    finally:
        await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": False, "limite_diario_usuario": 60, "chaves": {"anthropic": None}}})
        await async_client.put("/config/banca", headers=a1, json={"ia": {"habilitada": False, "orientacoes_banca": "",
                                                                          "recursos": dict.fromkeys(["gerar_questao", "revisar_questao", "alternativas", "justificativa", "melhorar_texto", "chat"], True)}})
        await _apagar_usos()
        reset_rate_limits()


def test_ai_text_is_stripped_of_html_and_images():
    t = assistente_ia.texto_puro('<p>Olá&nbsp;<b>mundo</b></p><img src="data:image/png;base64,QUJD"><p><span data-type="math" data-latex="x^2">x</span></p>')
    assert "Olá mundo" in t and "[imagem]" in t and "$x^2$" in t and "QUJD" not in t and "<" not in t
    # textos longos são cortados por campo antes de sair
    pedido, _ = assistente_ia.montar_pedido("chat", {"mensagem": "a", "contexto": "b" * 50000})
    assert pedido.count("b") <= 8100


@pytest.mark.asyncio
async def test_ai_status_explains_every_reason_it_is_unavailable(async_client):
    reset_rate_limits()
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    hd = auth_headers("vhugo1234", UserRole.DIAGRAMADOR, tenant_id=1)
    chave = "sk-teste-" + "q" * 30
    codigos = lambda r: [c["codigo"] for c in r.json()["causas"]]
    try:
        # o caso real: IA desligada na plataforma E provedor escolhido sem chave (a chave é do outro) -> as duas causas
        assert (await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": False, "provedor": "anthropic",
                "chaves": {"openai": chave}}})).status_code == 200
        r = await async_client.get("/ia/status", headers=hp)
        assert r.json()["disponivel"] is False and codigos(r)[:2] == ["plataforma_desligada", "sem_chave"]
        assert "Anthropic" in r.json()["causas"][1]["texto"] and "Já existe chave para OpenAI" in r.json()["causas"][1]["texto"]
        assert chave not in r.text and "qqqq" not in r.text
        assert "banca_desligada" in codigos(r)
        # diagramador não usa IA: uma causa só, sem pedir para ninguém ligar nada
        assert codigos(await async_client.get("/ia/status", headers=hd)) == ["perfil"]
        # admin geral na visão global: precisa escolher um cliente
        assert "sem_cliente" in codigos(await async_client.get("/ia/status", headers=ag))
        # resolve tudo -> disponível, sem causas
        assert (await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": True, "provedor": "openai"}})).status_code == 200
        assert codigos(await async_client.get("/ia/status", headers=hp)) == ["banca_desligada"]
        assert (await async_client.put("/config/banca", headers=a1, json={"ia": {"habilitada": True}})).status_code == 200
        r = await async_client.get("/ia/status", headers=hp)
        assert r.json()["disponivel"] is True and r.json()["causas"] == [] and r.json()["motivo"] == ""
    finally:
        await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": False, "provedor": "anthropic", "chaves": {"openai": None}}})
        await async_client.put("/config/banca", headers=a1, json={"ia": {"habilitada": False}})
        reset_rate_limits()
