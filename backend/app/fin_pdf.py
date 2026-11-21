"""PDFs do financeiro: contrato de elaboração (com termo de cessão e sigilo), recibo, proposta e registro de aceite."""
from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.fin_calculo import GATILHOS, PRECOS, moeda

_EST = getSampleStyleSheet()
TITULO = ParagraphStyle("t", parent=_EST["Title"], fontSize=15, spaceAfter=6)
SUB = ParagraphStyle("s", parent=_EST["Heading2"], fontSize=11.5, spaceBefore=10, spaceAfter=4)
TXT = ParagraphStyle("p", parent=_EST["BodyText"], fontSize=9.5, leading=13)
PEQ = ParagraphStyle("pq", parent=TXT, fontSize=8, textColor=colors.HexColor("#475569"))
CENTRO = ParagraphStyle("c", parent=TXT, alignment=TA_CENTER)


def _p(texto: str, estilo=TXT) -> Paragraph:
    return Paragraph(escape(str(texto or "")).replace("\n", "<br/>"), estilo)


def _tabela(linhas, larguras, cabecalho=True) -> Table:
    t = Table([[_p(c) if not isinstance(c, Paragraph) else c for c in linha] for linha in linhas], colWidths=larguras)
    estilo = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if cabecalho:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")))
    t.setStyle(TableStyle(estilo))
    return t


def _rodape(texto: str):
    def desenhar(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(2 * cm, 1.2 * cm, texto[:150])
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"página {doc.page}")
        canvas.restoreState()
    return desenhar


def _montar(elementos, rodape: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="DiagPro", author="DiagPro")
    doc.build(elementos, onFirstPage=_rodape(rodape), onLaterPages=_rodape(rodape))
    return buf.getvalue()


def preencher(texto: str, variaveis: dict) -> str:
    for k, v in variaveis.items():
        texto = texto.replace("{" + k + "}", str(v))
    return texto


def contrato(info: dict) -> bytes:
    """info: banca, contratante{}, professor{nome,cpf,email}, evento{nome,edital,data}, numero, modalidade, dados{},
    parcelas[{descricao,percentual,valor_fixo,gatilho,data_prevista}], previsto, clausulas_contrato, clausulas_cessao, codigo."""
    d, ct, prof, ev = info["dados"], info.get("contratante") or {}, info["professor"], info["evento"]
    var = {"BANCA": info["banca"], "PROFESSOR": prof.get("nome", ""), "CPF": prof.get("cpf") or "não informado",
           "EVENTO": ev.get("nome", ""), "VALOR_TOTAL": moeda(info["previsto"]),
           "PRAZO_ENTREGA": d.get("prazo_entrega") or "a data combinada pela banca", "DATA": datetime.now().strftime("%d/%m/%Y")}
    el = [_p(f"CONTRATO DE ELABORAÇÃO DE QUESTÕES Nº {info['numero']}", TITULO),
          _p(f"Código de verificação: {info['codigo']}", PEQ), Spacer(1, 6),
          _p("PARTES", SUB),
          _p(f"CONTRATANTE: {ct.get('razao_social') or info['banca']}"
             f"{' — CNPJ ' + ct['cnpj'] if ct.get('cnpj') else ''}{' — ' + ct['endereco'] if ct.get('endereco') else ''}."),
          _p(f"CONTRATADO: {prof.get('nome', '')} — CPF {var['CPF']} — {prof.get('email') or ''}."),
          _p("EVENTO", SUB),
          _p(f"{ev.get('nome', '')}{' — Edital ' + ev['edital'] if ev.get('edital') else ''}"
             f"{' — prova em ' + ev['data'] if ev.get('data') else ''}."),
          _p("REMUNERAÇÃO", SUB)]
    if info["modalidade"] == "valor_fechado":
        el.append(_p(f"Valor fechado: {moeda(d.get('valor_fechado'))}."))
    else:
        linhas = [["Tipo", "Preço unitário", "Quantidade contratada", "Subtotal"]]
        for k, rot in PRECOS.items():
            preco, qtd = float(d.get("precos", {}).get(k) or 0), float(d.get("quantidades", {}).get(k) or 0)
            if preco or qtd:
                linhas.append([rot, moeda(preco), f"{qtd:g}", moeda(preco * qtd)])
        linhas.append(["Total estimado", "", "", moeda(info["previsto"])])
        el += [_tabela(linhas, [6.5 * cm, 3.2 * cm, 3.6 * cm, 3.7 * cm]),
               _p("O valor final é calculado sobre as questões aprovadas na revisão.", PEQ)]
    el.append(_p("PARCELAS E CONDIÇÕES DE PAGAMENTO", SUB))
    linhas = [["#", "Descrição", "Valor", "Condição para liberar"]]
    for i, p in enumerate(info["parcelas"], 1):
        valor = moeda(p["valor_fixo"]) if p.get("valor_fixo") not in (None, "") else f"{float(p.get('percentual') or 0):g}% do total"
        cond = GATILHOS.get(p["gatilho"], p["gatilho"])
        if p["gatilho"] == "data" and p.get("data_prevista"):
            cond += f" ({datetime.fromisoformat(p['data_prevista']).strftime('%d/%m/%Y')})"
        linhas.append([str(i), p.get("descricao", ""), valor, cond])
    el.append(_tabela(linhas, [0.8 * cm, 6.2 * cm, 3.2 * cm, 6.8 * cm]))
    if d.get("observacoes"):
        el += [_p("OBSERVAÇÕES", SUB), _p(d["observacoes"])]
    el += [_p("CLÁUSULAS", SUB), _p(preencher(info["clausulas_contrato"], var)),
           PageBreak(), _p("TERMO DE CESSÃO DE DIREITOS AUTORAIS E DE SIGILO", TITULO), Spacer(1, 4),
           _p(preencher(info["clausulas_cessao"], var)), Spacer(1, 18),
           _p("O aceite eletrônico no DiagPro (com senha pessoal, data, hora, endereço IP e o código de verificação deste "
              "documento) vale como assinatura das partes, nos termos da MP 2.200-2/2001, art. 10, § 2º.", PEQ)]
    return _montar(el, f"DiagPro — Contrato {info['numero']} — código {info['codigo']}")


def recibo(info: dict) -> bytes:
    """info: banca, professor{nome,cpf}, numero_contrato, evento, parcela{ordem,descricao}, valor, data, forma, codigo."""
    prof = info["professor"]
    el = [_p("RECIBO DE PAGAMENTO", TITULO), _p(f"Código: {info['codigo']}", PEQ), Spacer(1, 10),
          _p(f"Recebi de {info['banca']} a importância de {moeda(info['valor'])},"),
          _p(f"referente à parcela {info['parcela']['ordem']} ({info['parcela'].get('descricao', '')}) do contrato "
             f"nº {info['numero_contrato']} — {info['evento']}."),
          Spacer(1, 8),
          _tabela([["Professor", prof.get("nome", "")], ["CPF", prof.get("cpf") or "não informado"],
                   ["Data do pagamento", info["data"]], ["Forma", info.get("forma") or "—"]], [5 * cm, 12 * cm], cabecalho=False),
          Spacer(1, 14), _p("Documento gerado pelo DiagPro a partir do pagamento registrado pela banca.", PEQ)]
    return _montar(el, f"DiagPro — Recibo {info['codigo']}")


def proposta(info: dict) -> bytes:
    """info: banca, numero, versao, plano, periodicidade, valor, desconto, valor_final, condicoes, validade, itens[]."""
    el = [_p(f"PROPOSTA COMERCIAL Nº {info['numero']} (versão {info['versao']})", TITULO),
          _p(f"Para: {info['banca']}", TXT), Spacer(1, 6),
          _tabela([["Plano", info["plano"]], ["Periodicidade", info["periodicidade"]], ["Valor de tabela", moeda(info["valor"])],
                   ["Desconto", f"{info['desconto']:g}%"], ["Valor proposto", moeda(info["valor_final"])],
                   ["Válida até", info.get("validade") or "—"]], [5 * cm, 12 * cm], cabecalho=False)]
    if info.get("itens"):
        el += [_p("O QUE ESTÁ INCLUÍDO", SUB)] + [_p("• " + i) for i in info["itens"]]
    if info.get("condicoes"):
        el += [_p("CONDIÇÕES", SUB), _p(info["condicoes"])]
    el += [Spacer(1, 12), _p("O aceite é feito pelo administrador da banca no DiagPro, com a senha pessoal; data, hora e "
                             "IP ficam registrados.", PEQ)]
    return _montar(el, f"DiagPro — Proposta {info['numero']} v{info['versao']}")


def documento_de_texto(titulo: str, texto: str, rodape: str) -> bytes:
    return _montar([_p(titulo, TITULO), Spacer(1, 6), _p(texto)], rodape)


def anexar_registro(pdf: bytes, titulo: str, linhas: list[tuple[str, str]]) -> bytes:
    """Acrescenta ao PDF original uma página com o registro do aceite eletrônico (o original fica intacto)."""
    from pypdf import PdfReader, PdfWriter

    pagina = _montar([_p(titulo, TITULO), Spacer(1, 8), _tabela([[k, v] for k, v in linhas], [5 * cm, 12 * cm], cabecalho=False)],
                     "DiagPro — registro de aceite eletrônico")
    w = PdfWriter()
    for r in (PdfReader(io.BytesIO(pdf)), PdfReader(io.BytesIO(pagina))):
        for pg in r.pages:
            w.add_page(pg)
    saida = io.BytesIO()
    w.write(saida)
    return saida.getvalue()
