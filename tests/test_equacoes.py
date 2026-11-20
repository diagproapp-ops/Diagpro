"""Equações do editor -> equações nativas do Word na prova (e recusa do que sairia errado no papel)."""
import pytest
from docx import Document
from lxml import etree

from backend.app import equacoes
from backend.app.html_to_docx import html_to_docx
from backend.app.roles import UserRole
from backend.app.verificacao_prova import _equacoes_com_problema, _texto
from tests.conftest import auth_headers

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def _tags(el):
    return [etree.QName(x).localname for x in el.iter() if isinstance(x.tag, str)]


def _prop(el, tag):
    achados = el.findall(f".//{M}{tag}")
    return [a.get(f"{M}val") for a in achados]


@pytest.mark.parametrize("latex, esperado", [
    (r"x=\frac{-b\pm\sqrt{b^2-4ac}}{2a}", {"f", "rad", "sSup"}),
    (r"\sqrt[3]{x}", {"rad", "deg"}),
    (r"\int_0^1 x^2\,dx", {"nary"}),
    (r"\sum_{i=1}^{n} i", {"nary"}),
    (r"\lim_{x\to 0}\frac{\sin x}{x}", {"func", "limLow", "f"}),
    (r"\begin{pmatrix}1&2\\3&4\end{pmatrix}", {"d", "m", "mr"}),
    (r"\begin{cases}x+y=2\\x-y=0\end{cases}", {"d", "eqArr"}),
    (r"\begin{aligned}a&=b+c\\d&=e\end{aligned}", {"eqArr"}),
    (r"\vec{v}+\hat{u}", {"acc"}),
    (r"\overline{AB}", {"bar"}),
    (r"\overbrace{a+b}^{n}", {"groupChr"}),
    (r"\binom{n}{k}", {"d", "f"}),
    (r"\left|x-1\right|", {"d"}),
])
def test_structures_become_native_word_math(latex, esperado):
    omml = equacoes.latex_para_omml(latex)
    assert etree.QName(omml).localname == "oMath"
    assert esperado <= set(_tags(omml)), (latex, sorted(set(_tags(omml))))


def test_details_that_keep_the_printed_exam_right():
    # integral com limites ao lado, somatório com limites em cima/embaixo
    assert "subSup" in _prop(equacoes.latex_para_omml(r"\int_0^1 f"), "limLoc")
    assert "undOvr" in _prop(equacoes.latex_para_omml(r"\sum_{i=1}^n i"), "limLoc")
    # barras de módulo como delimitador (solto, o LibreOffice lê "|" como "ou")
    d = equacoes.latex_para_omml(r"|x|<1")
    assert _prop(d, "begChr") == ["|"] and _prop(d, "endChr") == ["|"]
    # \mid dentro de chaves vira separador
    assert _prop(equacoes.latex_para_omml(r"\{x\mid x>0\}"), "sepChr") == ["|"]
    # intervalo semiaberto
    i = equacoes.latex_para_omml(r"[0,1)")
    assert _prop(i, "begChr") == ["["] and _prop(i, "endChr") == [")"]
    # letras retas (\mathrm, sin) usam m:nor; cor preta explícita em todo pedaço (tema escuro = fórmula branca)
    q = equacoes.latex_para_omml(r"\mathrm{H_2O}+\sin x", tamanho_pt=11)
    assert q.findall(f".//{M}nor")
    cores = q.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color")
    assert cores and all(c.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") == "000000" for c in cores)
    assert all(s.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") == "22"
               for s in q.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz"))
    # letras matemáticas especiais (\mathbf gera 𝐅) viram letras comuns
    assert "F" in "".join(equacoes.latex_para_omml(r"\mathbf{F}").itertext())
    # bloco = parágrafo de equação centralizado
    bloco = equacoes.latex_para_omml(r"E=mc^2", bloco=True)
    assert etree.QName(bloco).localname == "oMathPara" and _prop(bloco, "jc") == ["center"]


@pytest.mark.parametrize("latex, trecho", [
    ("", "vazia"),
    (r"\frac{a}", "incompleta"),
    (r"\comandoinexistente{x}", "desconhecido"),
    (r"x^", "expoente"),
    (r"\begin{matrix}1&2", "\\end"),
    (r"{x", "chave"),
    (r"x}", "chave"),
    (r"a & b", "&"),
    (r"\ce{H2O}", "mathrm"),
    (r"\boxed{x}", "PDF"),
    (r"\cancel{x}", "PDF"),
    ("x" * (equacoes.LIMITE_LATEX + 1), "longa"),
    (r"\frac{}{}", "vazia"),
    (r"\frac{a}{}", "denominador"),
    (r"\sqrt{}", "raiz"),
    (r"x^{}", "vazia"),
    (r"\sum_{}^{n} i", "limite"),
    (r"\lim_{} x", "limite"),
    (r"\overline{}", "vazia"),
    (r"\frac{\placeholder{}}{\placeholder{}}", "lacunas"),
])
def test_what_would_print_wrong_is_refused_with_a_clear_message(latex, trecho):
    erro = equacoes.validar(latex)
    assert erro and trecho.lower() in erro.lower(), (latex, erro)


def test_editor_html_equations_go_to_docx_inline_and_block():
    doc = Document()
    html_to_docx(doc, (
        '<p>Resolva <span data-type="inline-math" data-latex="x^2=4"></span> agora.</p>'
        '<div data-type="block-math" data-latex="\\int_0^1 x\\,dx"></div>'
        '<p>Formato antigo: <span data-type="math" data-latex="\\frac{1}{2}"></span></p>'
        '<p>Com erro: <span data-type="inline-math" data-latex="\\frac{a}"></span></p>'
    ), tamanho=12)
    corpo = doc.element.body
    assert len(corpo.findall(f".//{M}oMath")) >= 3
    assert len(corpo.findall(f".//{M}oMathPara")) == 1
    assert "Resolva" in doc.paragraphs[0].text and "agora." in doc.paragraphs[0].text
    # a equação inválida não some em silêncio (a checagem antes de exportar bloqueia a prova)
    assert "\\frac{a}" in doc.paragraphs[-1].text


def test_precheck_counts_equation_as_content_and_blocks_bad_ones_without_leaking_it():
    so_equacao = '<p><span data-type="inline-math" data-latex="\\sqrt{2}"></span></p>'
    assert _texto(so_equacao)  # alternativa só com equação não é "vazia"
    assert not _texto("<p></p>")
    q = {"enunciado": '<p>Calcule <span data-type="inline-math" data-latex="\\comandoSecreto{42}"></span></p>',
         "opcoes": [{"texto_opcao": so_equacao}, {"texto_opcao": '<p><span data-type="inline-math" data-latex="x^"></span></p>'}],
         "itens_vf": []}
    locais = _equacoes_com_problema(q)
    assert locais == ["enunciado (equação 1)", "alternativa B (equação 1)"]
    assert not any("Secreto" in l or "42" in l for l in locais), "a checagem não pode devolver conteúdo da prova"


def test_pdf_converter_forces_light_theme_profile(tmp_path):
    from core.document_generator import _forcar_tema_claro
    _forcar_tema_claro(str(tmp_path))
    xcu = (tmp_path / "user" / "registrymodifications.xcu").read_text(encoding="utf-8")
    assert "ApplicationAppearance" in xcu and "<value>1</value>" in xcu


async def test_equation_validation_endpoint(async_client):
    h = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    ok = await async_client.post("/editor/equacao/validar", json={"latex": r"\frac{1}{2}"}, headers=h)
    assert ok.status_code == 200 and ok.json() == {"ok": True, "erro": None}
    ruim = await async_client.post("/editor/equacao/validar", json={"latex": r"\frac{1}"}, headers=h)
    assert ruim.status_code == 200 and ruim.json()["ok"] is False and "incompleta" in ruim.json()["erro"]
    sem_login = await async_client.post("/editor/equacao/validar", json={"latex": "x"})
    assert sem_login.status_code == 401


def _modelos_da_paleta():
    """Lê os modelos de frontend/src/components/editor/modelosEquacao.ts (m('latex', ...) e ['latex', ...])."""
    import re
    from pathlib import Path
    fonte = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "components" / "editor" / "modelosEquacao.ts").read_text(encoding="utf-8")
    texto_js = r"'((?:[^'\\]|\\.)*)'"
    achados = re.findall(r"(?:\bm\(|\[)\s*" + texto_js + r"\s*,", fonte)
    return [re.sub(r"\\(.)", r"\1", s) for s in achados]


def test_every_palette_template_prints():
    modelos = _modelos_da_paleta()
    assert len(modelos) > 200
    falhas = {lx: equacoes.validar(lx.replace("#?", "x")) for lx in modelos}
    falhas = {k: v for k, v in falhas.items() if v}
    assert not falhas, falhas


async def test_ai_equation_from_description_is_checked_before_returning(async_client, monkeypatch):
    from backend.app import assistente_ia
    from backend.app.rate_limit import reset_rate_limits
    from sqlalchemy import text as sql
    from backend.app.database import PlatformSessionLocal

    pedidos = []
    respostas = iter([
        {"latex": r"x=\frac{-b\pm\sqrt{b^2-4ac}}{2a}", "explicacao": "Fórmula de Bhaskara."},
        {"latex": r"\boxed{x}", "explicacao": "x em destaque."},
    ])

    async def falso(provedor, modelo, chave, sistema, mensagem, schema, max_tokens=8000):
        pedidos.append(mensagem)
        assert set(schema["properties"]) == {"latex", "explicacao"}
        return assistente_ia.RespostaIA(next(respostas), 10, 5)

    monkeypatch.setattr(assistente_ia, "chamar_provedor", falso)
    reset_rate_limits()
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    try:
        assert (await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": True, "provedor": "anthropic",
                "chaves": {"anthropic": "sk-teste-" + "y" * 30}}})).status_code == 200
        assert (await async_client.put("/config/banca", headers=a1, json={"ia": {"habilitada": True}})).status_code == 200
        assert (await async_client.get("/ia/status", headers=hp)).json()["recursos"]["equacao"] is True

        r = await async_client.post("/ia/equacao", headers=hp, json={"descricao": "fórmula de Bhaskara"})
        assert r.status_code == 200, r.text
        assert r.json()["erro"] is None and r"\frac" in r.json()["latex"]
        assert "fórmula de Bhaskara" in pedidos[-1]  # vai só o que o professor escreveu

        # o que a IA devolver e não sair na prova chega com o problema apontado (o editor não deixa inserir)
        r = await async_client.post("/ia/equacao", headers=hp, json={"descricao": "x numa caixa", "latex_atual": "x"})
        assert r.status_code == 200 and "PDF" in (r.json()["erro"] or "")

        # a banca pode desligar só este recurso
        assert (await async_client.put("/config/banca", headers=a1, json={"ia": {"recursos": {"equacao": False}}})).status_code == 200
        assert (await async_client.post("/ia/equacao", headers=hp, json={"descricao": "pi"})).status_code == 403
    finally:
        await async_client.put("/config/plataforma", headers=ag, json={"ia": {"habilitada": False, "chaves": {"anthropic": None}}})
        await async_client.put("/config/banca", headers=a1, json={"ia": {"habilitada": False, "recursos": {"equacao": True}}})
        async with PlatformSessionLocal() as s:
            await s.execute(sql("DELETE FROM uso_ia"))
            await s.commit()
        reset_rate_limits()
