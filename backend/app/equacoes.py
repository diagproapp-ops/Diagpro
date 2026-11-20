"""
Equações do editor (LaTeX) -> equações nativas do Word (OMML), para a prova DOCX/PDF.

Caminho: LaTeX --latex2mathml--> MathML --(este módulo)--> OMML. A equação sai editável no Word e, no PDF
(gerado pelo LibreOffice, que importa OMML), nítida e vetorial. Tudo em memória; nada é gravado em disco.

As escolhas de estrutura seguem o que o Word E o LibreOffice desenham corretamente (conferido no PDF):
delimitadores como <m:d> (crescem com o conteúdo; "|" solto o LibreOffice lê como "ou"), "lim/max/min" como
função com limite embaixo, sistemas/alinhados como <m:eqArr>, letras retas com <m:nor/>.

Se uma equação não puder ser convertida, `EquacaoInvalida` é levantada: a checagem antes de exportar bloqueia a
prova (melhor do que imprimir uma fórmula errada) e o editor avisa no momento em que a equação é criada.
"""
from __future__ import annotations

import html as _html
import re
import unicodedata
from typing import Iterable, Optional

from lxml import etree

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMAP = {"m": M_NS, "w": W_NS}

LIMITE_LATEX = 4000  # equação de prova não precisa de mais que isso; evita abuso no conversor


class EquacaoInvalida(ValueError):
    """A equação não pôde ser convertida para a prova."""


def _m(tag: str) -> str:
    return f"{{{M_NS}}}{tag}"


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def _novo(tag: str) -> etree._Element:
    """Elemento com os prefixos padrão (m:, w:)."""
    return etree.Element(tag, nsmap=_NSMAP)


def _el(tag: str, *filhos) -> etree._Element:
    e = _novo(_m(tag))
    for f in filhos:
        if f is not None:
            e.append(f)
    return e


def _prop(tag: str, val: str) -> etree._Element:
    e = _novo(_m(tag))
    e.set(_m("val"), val)
    return e


def _pr(tag: str, **props) -> etree._Element:
    e = _novo(_m(tag))
    for k, v in props.items():
        e.append(_prop(k, v))
    return e


# Operadores n-ários (somatório, integral...)
_NARY_INTEGRAIS = set("∫∬∭∮∯∰∱∲∳⨌")
_NARY = _NARY_INTEGRAIS | set("∑∏∐⋃⋂⋁⋀⨁⨂⨀⨄⨆")
# Operadores com nome que levam limite embaixo
_FUNC_LIMITE = {"lim", "max", "min", "sup", "inf", "limsup", "liminf", "lim sup", "lim inf", "det", "gcd", "Pr",
                "arg max", "arg min", "argmax", "argmin", "mdc", "mmc"}
# Onde termina o operando de um n-ário / de um lim (relações e separadores)
_PARA_OPERANDO = set("=<>≤≥≠≈≡≅∼≃∝→⇒⇔↔⟹⟺,;∈∉⊂⊃⊆⊇")

# Delimitadores
_ABRE = {"(", "[", "{", "⟨", "〈", "⌊", "⌈", "⟦"}
_FECHA = {")", "]", "}", "⟩", "〉", "⌋", "⌉", "⟧"}
_BARRA_PAR = {"|", "‖", "∥", "∣"}
# Operadores/relações que o LibreOffice exige com algo dos dois lados (sozinhos na ponta viram "¿")
_OPERADORES = set("~⧵=≠≈≡≅∼≃∝<>≤≥≪≫±∓×÷·∘+−-∈∉∋⊂⊃⊆⊇∪∩∖∧∨¬⇒⇐⇔→←↔↑↓↦⇌⇀↗↘⊕⊗⊥∠△∴∵∀∃∄/*:⟶⟵⟷⟹⟸⟺≺≻⊢⊨")
_UNARIOS = set("+−-±∓¬∀∃∄∠△")  # podem abrir a linha (−b, ∀x, ∠A)
# Símbolos que a fonte de fórmulas do LibreOffice não tem -> equivalentes que ela tem
_TROCAS = {"∖": "−", "⧵": "−", "⟶": "→", "⟵": "←", "⟷": "↔", "⟹": "⇒", "⟸": "⇐", "⟺": "⇔", "∼": "~"}
_SEMPRE_TEXTO = {"∼", "~"}  # "~" fora de texto é espaço para o LibreOffice
# Operadores n-ários que o LibreOffice importa como tal; os demais (⋃, ⋂...) vão como símbolo com limites
_NARY_LIBREOFFICE = set("∑∏∐∫∬∭∮")
_SEPARADOR = {"∣", "|"}  # \mid dentro de chaves/parênteses: {x | x > 0}, P(A | B)

# Acentos (\hat, \vec...) -> caractere combinante usado pelo Word
_ACENTOS = {
    "^": "\u0302", "\u02c6": "\u0302", "\u0302": "\u0302",
    "~": "\u0303", "\u02dc": "\u0303", "\u0303": "\u0303",
    "→": "\u20d7", "\u20d7": "\u20d7",
    "←": "\u20d6",
    "˙": "\u0307", ".": "\u0307", "\u0307": "\u0307",
    "¨": "\u0308", "\u0308": "\u0308", "..": "\u0308",
    "´": "\u0301", "`": "\u0300", "ˇ": "\u030c", "˘": "\u0306", "\u02d8": "\u0306", "°": "\u030a", "˚": "\u030a",
    "↔": "\u20e1",
}
_BARRAS = {"¯", "‾", "―", "_", "\u0305", "−", "-"}
_CHAVES_SUP = {"⏞", "︷"}
_CHAVES_INF = {"⏟", "︸"}


def _letras_comuns(texto: str) -> str:
    """Letras matemáticas especiais (𝐅, 𝔸, ℝ fica) -> letras comuns; a fonte da prova nem sempre as tem."""
    saida = []
    for ch in texto:
        if 0x1D400 <= ord(ch) <= 0x1D7FF:
            saida.append(unicodedata.normalize("NFKC", ch))
        else:
            saida.append(ch)
    return "".join(saida)


class _Conversor:
    def __init__(self, tamanho_meio_pontos: Optional[int] = None, cor: str = "000000"):
        self.sz = tamanho_meio_pontos
        self.cor = cor

    # ---------- utilidades ----------
    def _run(self, texto: str, reto: bool = False, negrito: bool = False, normal: bool = False) -> etree._Element:
        r = _novo(_m("r"))
        if reto or negrito or normal:
            rpr = etree.SubElement(r, _m("rPr"))
            # m:nor = texto reto (o LibreOffice ignora m:sty; o Word respeita os dois)
            if normal or (reto and any(c.isalpha() for c in texto)) or negrito:
                etree.SubElement(rpr, _m("nor"))
            if not negrito:  # negrito vai por w:b (com m:sty="b" o LibreOffice volta para itálico)
                rpr.append(_prop("sty", "p"))
        # Cor preta explícita (com "cor automática" a fórmula pode sair BRANCA no PDF quando o sistema usa
        # tema escuro) e o tamanho da fonte da prova.
        wrpr = etree.SubElement(r, _w("rPr"))
        if negrito:
            etree.SubElement(wrpr, _w("b"))
        cor = etree.SubElement(wrpr, _w("color"))
        cor.set(_w("val"), self.cor)
        if self.sz:
            sz = etree.SubElement(wrpr, _w("sz"))
            sz.set(_w("val"), str(self.sz))
        t = etree.SubElement(r, _m("t"))
        t.text = texto
        if texto != texto.strip():
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        return r

    @staticmethod
    def _nome(no) -> str:
        return etree.QName(no).localname if isinstance(no.tag, str) else ""

    @staticmethod
    def _texto(no) -> str:
        return "".join(no.itertext()).strip()

    def _filhos(self, no) -> list:
        return [f for f in no if isinstance(f.tag, str)]

    def _container(self, tag: str, nos: Iterable) -> etree._Element:
        e = _novo(_m(tag))
        for x in self.lista(nos):
            e.append(x)
        return e

    def _arg(self, tag: str, no) -> etree._Element:
        return self._container(tag, [no] if no is not None else [])

    def _operador_base(self, no) -> str:
        nome = self._nome(no)
        if nome in ("mo", "mi", "mtext"):
            return self._texto(no)
        if nome == "mrow" and len(self._filhos(no)) == 1:
            return self._operador_base(self._filhos(no)[0])
        return ""

    def _mo(self, no) -> str:
        return self._texto(no) if self._nome(no) == "mo" else ""

    # ---------- listas: delimitadores, n-ários e lim ----------
    def lista(self, nos: Iterable) -> list:
        nos = [n for n in nos if isinstance(n.tag, str)]
        saida: list = []
        i = 0
        while i < len(nos):
            no = nos[i]
            txt = self._mo(no)
            # \left( ... \right)  (mo com fence)
            if txt is not None and no.get("fence") == "true" and no.get("form") == "prefix":
                j = self._fecha_fence(nos, i)
                if j is not None:
                    saida.append(self._delimitador(txt, self._mo(nos[j]), nos[i + 1:j]))
                    i = j + 1
                    continue
                # \left\{ sem \right (ex.: cases)
                saida.append(self._delimitador(txt, "", nos[i + 1:]))
                break
            # ( [ { ... sem \left/\right
            if txt in _ABRE:
                j = self._fecha_par(nos, i)
                if j is not None:
                    fecha = nos[j]
                    if self._nome(fecha) == "mo":
                        saida.append(self._delimitador(txt, self._mo(fecha), nos[i + 1:j]))
                    else:
                        # (x-1)^2: o ")" vem dentro do expoente/índice -> parênteses com o expoente em volta
                        f = self._filhos(fecha)
                        d = _el("e", self._delimitador(txt, self._operador_base(f[0]), nos[i + 1:j]))
                        nome_f = self._nome(fecha)
                        if nome_f == "msup":
                            saida.append(_el("sSup", d, self._arg("sup", f[1])))
                        elif nome_f == "msub":
                            saida.append(_el("sSub", d, self._arg("sub", f[1])))
                        else:
                            saida.append(_el("sSubSup", d, self._arg("sub", f[1]), self._arg("sup", f[2])))
                    i = j + 1
                    continue
                if i + 1 < len(nos) and self._nome(nos[i + 1]) == "mtable":
                    saida.append(self._delimitador(txt, "", nos[i + 1:i + 2]))
                    i += 2
                    continue
            # |x|, ‖v‖
            if txt in _BARRA_PAR:
                j = self._fecha_barra(nos, i)
                if j is not None:
                    saida.append(self._delimitador(txt, self._mo(nos[j]), nos[i + 1:j], separar=False))
                    i = j + 1
                    continue
            if not txt and self._nome(no) == "mi" and self._texto(no) in _OPERADORES:
                txt = self._texto(no)  # alguns símbolos (\sim, \setminus, \longrightarrow) vêm como <mi>
            if self._nome(no) in ("mo", "mi") and txt and not self._eh_nary(no):
                # Colchete/barra sem par e operador na ponta da linha (ex.: "=" sozinho, a carga "+" de Na⁺):
                # vão como texto, senão o LibreOffice imprime "¿" no lugar do lado que falta.
                if txt in _ABRE or txt in _FECHA or txt in _BARRA_PAR:
                    if txt in "()":
                        # parêntese sem par: como texto o LibreOffice imprimiria "\(" — vai como símbolo
                        saida.append(self._run(txt, reto=True))
                    else:
                        saida.append(self._run(" | " if txt in ("|", "∣") else txt, normal=True))
                    i += 1
                    continue
                if txt in _OPERADORES and (i == len(nos) - 1 or (i == 0 and txt not in _UNARIOS)):
                    saida.append(self._run(_TROCAS.get(txt, txt), normal=True))
                    i += 1
                    continue
            # n-ário (∑, ∫...) e lim/max/min: operando = itens seguintes até a próxima relação
            if self._eh_nary(no) or self._eh_func_limite(no):
                j = i + 1
                while j < len(nos) and self._mo(nos[j]) not in _PARA_OPERANDO:
                    j += 1
                operando = nos[i + 1:j]
                saida.append(self._nary(no, operando) if self._eh_nary(no) else self._func_limite(no, operando))
                i = j
                continue
            saida.extend(self.no(no))
            i += 1
        return saida

    def _fecha_fence(self, nos, i):
        profundidade = 0
        for j in range(i, len(nos)):
            nj = nos[j]
            if self._nome(nj) == "mo" and nj.get("fence") == "true":
                if nj.get("form") == "prefix":
                    profundidade += 1
                elif nj.get("form") == "postfix":
                    profundidade -= 1
                    if profundidade == 0:
                        return j
        return None

    def _fecha_par(self, nos, i):
        profundidade = 0
        for j in range(i, len(nos)):
            t = self._mo(nos[j])
            if nos[j].get("fence") == "true":
                continue
            if not t and self._nome(nos[j]) in ("msup", "msub", "msubsup") and self._filhos(nos[j]):
                base = self._filhos(nos[j])[0]
                if self._nome(base) == "mo" and self._texto(base) in _FECHA:
                    t = self._texto(base)  # ")" com expoente: (x-1)^2
            if t in _ABRE:
                profundidade += 1
            elif t in _FECHA:
                profundidade -= 1
                if profundidade == 0:
                    return j
        return None

    def _fecha_barra(self, nos, i):
        alvo = self._mo(nos[i])
        profundidade = 0
        for j in range(i + 1, len(nos)):
            t = self._mo(nos[j])
            if t in _ABRE:
                profundidade += 1
            elif t in _FECHA:
                profundidade -= 1
                if profundidade < 0:
                    return None
            elif t == alvo and profundidade == 0:
                return j
        return None

    def _eh_nary(self, no) -> bool:
        nome = self._nome(no)
        if nome in ("msub", "msup", "msubsup", "munder", "mover", "munderover"):
            f = self._filhos(no)
            return bool(f) and self._operador_base(f[0]) in _NARY
        return nome == "mo" and self._texto(no) in _NARY

    def _eh_func_limite(self, no) -> bool:
        nome = self._nome(no)
        f = self._filhos(no)
        return nome in ("msub", "munder") and len(f) >= 2 and self._operador_base(f[0]) in _FUNC_LIMITE

    def _nary(self, no, operando) -> etree._Element:
        nome = self._nome(no)
        f = self._filhos(no)
        chr_ = self._operador_base(f[0]) if f and nome != "mo" else self._texto(no)
        sub = sup = None
        if nome in ("msub", "munder"):
            sub = f[1]
        elif nome in ("msup", "mover"):
            sup = f[1]
        elif nome in ("msubsup", "munderover"):
            sub, sup = f[1], f[2]
        for arg in (sub, sup):
            if arg is not None:
                self._nao_vazio(arg, "o limite do somatório/integral")
        if chr_ not in _NARY_LIBREOFFICE:
            # ⋃, ⋂, ⨁...: símbolo com limite embaixo/em cima (sai igual no Word e no PDF)
            base = self._run(chr_, reto=True)
            if sub is not None:
                base = _el("limLow", _el("e", base), self._arg("lim", sub))
            if sup is not None:
                base = _el("limUpp", _el("e", base), self._arg("lim", sup))
            return _el("func", _el("fName", base), self._container("e", operando))
        pr = _pr("naryPr", chr=chr_)
        local ="subSup" if (chr_ in _NARY_INTEGRAIS and nome not in ("munder", "mover", "munderover")) else "undOvr"
        pr.append(_prop("limLoc", local))
        if sub is None:
            pr.append(_prop("subHide", "1"))
        if sup is None:
            pr.append(_prop("supHide", "1"))
        return _el("nary", pr, self._arg("sub", sub), self._arg("sup", sup), self._container("e", operando))

    def _func_limite(self, no, operando) -> etree._Element:
        f = self._filhos(no)
        self._nao_vazio(f[1], "o limite (ex.: x \\to 0)")
        nome_f = _el("limLow", _el("e", self._run(self._operador_base(f[0]), reto=True)), self._arg("lim", f[1]))
        return _el("func", _el("fName", nome_f), self._container("e", operando))

    def _delimitador(self, abre: str, fecha: str, conteudo, separar: bool = True) -> etree._Element:
        conteudo = [c for c in conteudo if isinstance(c.tag, str)]
        partes, atual = [], []
        for c in conteudo:
            if separar and self._mo(c) in _SEPARADOR and c.get("fence") != "true":
                partes.append(atual)
                atual = []
            else:
                atual.append(c)
        partes.append(atual)
        pr = _novo(_m("dPr"))
        pr.append(_prop("begChr", abre))
        if len(partes) > 1:
            pr.append(_prop("sepChr", "|"))
        pr.append(_prop("endChr", fecha))
        d = _el("d", pr)
        for p in partes:
            d.append(self._container("e", p))
        return d

    # ---------- um nó MathML ----------
    def no(self, no) -> list:
        nome = self._nome(no)
        f = self._filhos(no)
        if nome in ("math", "mrow", "mstyle", "mpadded", "mlabeledtr"):
            return self.lista(f)
        if nome == "semantics":
            return self.lista(f[:1])
        if nome in ("mphantom", "annotation", "annotation-xml", "none", "mprescripts"):
            return []
        if nome in ("mi", "mo"):
            bruto = self._texto(no)
            if bruto.startswith("\\") and len(bruto) > 1:
                if bruto == "\\ce":
                    raise EquacaoInvalida("Fórmula química com \\ce não é suportada na prova: use \\mathrm{H_2O}.")
                raise EquacaoInvalida(f"Comando desconhecido: {bruto[:40]}")
            if bruto in ("{", "}") and nome == "mi":
                raise EquacaoInvalida("Chave { } sobrando: para imprimir uma chave use \\{ ou \\}.")
        if nome == "mi":
            texto = _letras_comuns(self._texto(no))
            if not texto:
                return []
            if texto in _TROCAS or texto in _SEMPRE_TEXTO:
                return [self._run(_TROCAS.get(texto, texto), reto=True, normal=texto in _SEMPRE_TEXTO)]
            variante = no.get("mathvariant") or ""
            negrito = "bold" in variante
            reto = variante in ("normal", "bold") or (len(texto) > 1 and "italic" not in variante)
            return [self._run(texto, reto=reto, negrito=negrito)]
        if nome == "mn":
            return [self._run(_letras_comuns(self._texto(no)), reto=True, negrito="bold" in (no.get("mathvariant") or ""))]
        if nome == "mo":
            texto = self._texto(no)
            if not texto:
                return []
            return [self._run(_TROCAS.get(texto, texto), reto=True, normal=texto in _SEMPRE_TEXTO)]
        if nome in ("mtext", "ms"):
            texto = "".join(no.itertext())
            if not texto:
                return []
            pedacos = [p for p in re.split(r"([()\[\]])", texto) if p]
            parenteses = [p for p in pedacos if p in "()[]"]
            pareados = parenteses.count("(") == parenteses.count(")") and parenteses.count("[") == parenteses.count("]")
            if parenteses and pareados:
                # "(aq)": parênteses fora do texto — dentro dele o LibreOffice imprime "\(aq\)"
                return [self._run(p, reto=True) if p in "()[]" else self._run(p, normal=True) for p in pedacos]
            return [self._run(texto, normal=True)]
        if nome == "mspace":
            return [self._run(self._espaco(no.get("width") or ""), normal=True)]
        if nome == "mfrac":
            self._exigir(no, 2)
            self._nao_vazio(f[0], "o numerador da fração")
            self._nao_vazio(f[1], "o denominador da fração")
            pr = None
            if (no.get("linethickness") or "").strip() in ("0", "0px", "0em", "0pt"):
                pr = _pr("fPr", type="noBar")
            return [_el("f", pr, self._arg("num", f[0]), self._arg("den", f[1]))]
        if nome == "msqrt":
            self._nao_vazio(no, "o que fica dentro da raiz")
            return [_el("rad", _pr("radPr", degHide="1"), _el("deg"), self._container("e", f))]
        if nome == "mroot":
            self._exigir(no, 2)
            self._nao_vazio(f[0], "o que fica dentro da raiz")
            if self._vazio(f[1]):  # \sqrt[]{x} = raiz quadrada
                return [_el("rad", _pr("radPr", degHide="1"), _el("deg"), self._arg("e", f[0]))]
            return [_el("rad", _novo(_m("radPr")), self._arg("deg", f[1]), self._arg("e", f[0]))]
        if nome in ("msub", "msup", "msubsup", "munder", "mover", "munderover"):
            if self._eh_nary(no):
                return [self._nary(no, [])]
            if self._eh_func_limite(no):
                return [self._func_limite(no, [])]
            return [self._script(nome, f, no)]
        if nome == "mtable":
            return [self._tabela(no)]
        if nome == "mfenced":
            pr = _novo(_m("dPr"))
            pr.append(_prop("begChr", no.get("open", "(")))
            pr.append(_prop("sepChr", (no.get("separators", ",") or ",")[:1]))
            pr.append(_prop("endChr", no.get("close", ")")))
            d = _el("d", pr)
            for x in f:
                d.append(self._arg("e", x))
            return [d]
        if nome == "menclose":
            # O Word desenha, mas o PDF da prova (LibreOffice) perde a caixa/o risco: a equação mudaria de
            # sentido no papel. Melhor recusar do que imprimir diferente do que o autor vê.
            raise EquacaoInvalida("Caixa (\\boxed) e risco (\\cancel) não aparecem no PDF da prova.")
        if nome == "merror":
            raise EquacaoInvalida(f"Comando não reconhecido: {self._texto(no)[:60]}")
        if nome == "mmultiscripts":
            raise EquacaoInvalida("Índices à esquerda não são suportados na prova.")
        raise EquacaoInvalida(f"Elemento de equação não suportado na prova: <{nome}>.")

    @staticmethod
    def _espaco(largura: str) -> str:
        m = re.match(r"([\d.]+)\s*em", largura or "")
        em = float(m.group(1)) if m else 0.2
        if em >= 1.9:
            return "\u2003\u2003"
        if em >= 0.9:
            return "\u2003"
        if em >= 0.4:
            return "\u2002"
        return "\u2009"

    def _vazio(self, no) -> bool:
        return not "".join(no.itertext()).strip() and not any(
            self._nome(x) in ("mspace", "mtable") for x in no.iter() if isinstance(x.tag, str))

    def _nao_vazio(self, no, parte: str):
        if self._vazio(no):
            raise EquacaoInvalida(f"Equação com parte vazia: preencha {parte}.")

    def _exigir(self, no, n):
        if len(self._filhos(no)) < n:
            nomes = {"mfrac": "fração sem denominador", "mroot": "raiz sem índice", "msub": "índice vazio",
                     "msup": "expoente vazio", "msubsup": "índice ou expoente vazio", "munder": "limite vazio",
                     "mover": "marca vazia", "munderover": "limite vazio"}
            raise EquacaoInvalida(f"Equação incompleta: {nomes.get(self._nome(no), 'falta uma parte')}.")

    def _script(self, nome, f, no) -> etree._Element:
        self._exigir(no, 3 if nome in ("msubsup", "munderover") else 2)
        base = f[0]
        for arg in f[1:3]:
            self._nao_vazio(arg, "o expoente, o índice ou o limite")
        if nome in ("munder", "mover", "munderover"):
            self._nao_vazio(base, "a parte principal")
        if nome in ("msub", "msup", "msubsup") and not self._filhos(base) and not self._texto(base):
            # expoente sem base (ex.: {}^{\circ}C): base invisível, senão o LibreOffice imprime um quadradinho
            vazio = _el("e", self._run("​", normal=True))
            if nome == "msub":
                return _el("sSub", vazio, self._arg("sub", f[1]))
            if nome == "msup":
                return _el("sSup", vazio, self._arg("sup", f[1]))
            return _el("sSubSup", vazio, self._arg("sub", f[1]), self._arg("sup", f[2]))
        if nome == "msub":
            return _el("sSub", self._arg("e", base), self._arg("sub", f[1]))
        if nome == "msup":
            return _el("sSup", self._arg("e", base), self._arg("sup", f[1]))
        if nome == "msubsup":
            return _el("sSubSup", self._arg("e", base), self._arg("sub", f[1]), self._arg("sup", f[2]))
        if nome == "munder":
            marca = self._operador_base(f[1])
            if marca in _CHAVES_INF:
                return _el("groupChr", _pr("groupChrPr", chr=marca, pos="bot", vertJc="top"), self._arg("e", base))
            if marca in _BARRAS:
                return _el("bar", _pr("barPr", pos="bot"), self._arg("e", base))
            return _el("limLow", self._arg("e", base), self._arg("lim", f[1]))
        if nome == "mover":
            marca = self._operador_base(f[1])
            if marca in _CHAVES_SUP:
                return _el("groupChr", _pr("groupChrPr", chr=marca, pos="top", vertJc="bot"), self._arg("e", base))
            if marca in _BARRAS:
                return _el("bar", _pr("barPr", pos="top"), self._arg("e", base))
            if marca in _ACENTOS:
                return _el("acc", _pr("accPr", chr=_ACENTOS[marca]), self._arg("e", base))
            return _el("limUpp", self._arg("e", base), self._arg("lim", f[1]))
        baixo = _el("limLow", self._arg("e", base), self._arg("lim", f[1]))
        return _el("limUpp", _el("e", baixo), self._arg("lim", f[2]))

    def _tabela(self, no) -> etree._Element:
        linhas = [r for r in self._filhos(no) if self._nome(r) in ("mtr", "mlabeledtr")]
        if not linhas:
            raise EquacaoInvalida("Matriz vazia.")
        celulas = [[c for c in self._filhos(r) if self._nome(c) == "mtd"] for r in linhas]
        alinhada = any((c.get("columnalign") or "center") != "center" for linha in celulas for c in linha)
        if alinhada:
            # sistemas (cases) e equações alinhadas: uma linha por equação, células emendadas
            arr = _el("eqArr")
            for linha in celulas:
                nos = []
                for k, c in enumerate(linha):
                    if k and self._filhos(c) and self._mo(self._filhos(c)[0]) not in _PARA_OPERANDO:
                        nos.append(None)  # espaço entre colunas de texto (ex.: "x, se x > 0")
                    nos.extend(self._filhos(c))
                e = _novo(_m("e"))
                for x in nos:
                    if x is None:
                        e.append(self._run("\u2003", normal=True))
                    else:
                        for y in self.lista([x]):
                            e.append(y)
                arr.append(e)
            return arr
        ncols = max(len(linha) for linha in celulas)
        pr = _novo(_m("mPr"))
        mcs = etree.SubElement(pr, _m("mcs"))
        mc = etree.SubElement(mcs, _m("mc"))
        mcpr = etree.SubElement(mc, _m("mcPr"))
        mcpr.append(_prop("count", str(max(ncols, 1))))
        mcpr.append(_prop("mcJc", "center"))
        m = _el("m", pr)
        for linha in celulas:
            mr = etree.SubElement(m, _m("mr"))
            for c in linha:
                mr.append(self._container("e", self._filhos(c)))
            for _ in range(ncols - len(linha)):
                mr.append(_el("e"))
        return m


def _limpar_latex(latex: str) -> str:
    latex = _html.unescape(str(latex or "")).strip()
    # delimitadores que às vezes vêm colados: $...$, \( \), \[ \]
    for a, b in (("$$", "$$"), ("$", "$"), ("\\(", "\\)"), ("\\[", "\\]")):
        if latex.startswith(a) and latex.endswith(b) and len(latex) > len(a) + len(b):
            latex = latex[len(a):-len(b)].strip()
            break
    # ambientes alinhados -> array alinhado (vira pilha de equações; o Word não tem "align")
    latex = re.sub(r"\\begin\{(align\*?|aligned|alignat\*?|eqnarray\*?)\}(\{\d+\})?", r"\\begin{array}{rl}", latex)
    latex = re.sub(r"\\end\{(align\*?|aligned|alignat\*?|eqnarray\*?)\}", r"\\end{array}", latex)
    latex = re.sub(r"\\begin\{(gather\*?|gathered)\}", r"\\begin{array}{l}", latex)
    latex = re.sub(r"\\end\{(gather\*?|gathered)\}", r"\\end{array}", latex)
    for cmd in ("\\displaystyle", "\\textstyle", "\\limits", "\\nolimits"):
        latex = latex.replace(cmd, "")
    # comandos que o editor visual (MathLive) gera -> LaTeX padrão
    for de, para in (("\\mleft", "\\left"), ("\\mright", "\\right"), ("\\differentialD", "\\mathrm{d}"),
                     ("\\exponentialE", "\\mathrm{e}"), ("\\imaginaryI", "\\mathrm{i}"), ("\\lbrace", "\\{"),
                     ("\\rbrace", "\\}")):
        latex = re.sub(re.escape(de) + r"(?![A-Za-z])", lambda _m, p=para: p, latex)
    return latex


_ERROS_CONVERSOR = {
    "MissingSuperScriptOrSubscriptError": "Falta o expoente ou o índice depois de ^ ou _.",
    "MissingEndError": "Falta o \\end de uma matriz, sistema ou ambiente.",
    "NoAvailableTokensError": "Comando incompleto: falta o que vem dentro dele (ex.: \\sqrt{x}).",
    "ExtraLeftOrMissingRightError": "\\left sem o \\right correspondente.",
    "MissingRightError": "\\left sem o \\right correspondente.",
    "DoubleSuperscriptsError": "Dois expoentes seguidos: use chaves, ex.: x^{2^3}.",
    "DoubleSubscriptsError": "Dois índices seguidos: use chaves, ex.: x_{i_j}.",
    "InvalidAlignmentError": "Alinhamento de colunas inválido na matriz.",
    "InvalidStyleForGenfracError": "Fração com formato inválido.",
    "InvalidWidthError": "Largura inválida.",
    "LimitsMustFollowMathOperatorError": "\\limits só pode vir depois de um operador (ex.: \\sum).",
    "DenominatorNotFoundError": "Fração sem denominador.",
    "NumeratorNotFoundError": "Fração sem numerador.",
}


def _conferir_chaves(latex: str) -> None:
    """Chaves { } de agrupamento balanceadas (\\{ e \\} são chaves impressas e não contam)."""
    nivel = 0
    i = 0
    while i < len(latex):
        c = latex[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            nivel += 1
        elif c == "}":
            nivel -= 1
            if nivel < 0:
                raise EquacaoInvalida("Chave } fechando sem ter sido aberta.")
        i += 1
    if nivel:
        raise EquacaoInvalida("Falta fechar uma chave { }.")


def latex_para_mathml(latex: str) -> str:
    from latex2mathml.converter import convert
    latex = _limpar_latex(latex)
    if not latex:
        raise EquacaoInvalida("Equação vazia.")
    if len(latex) > LIMITE_LATEX:
        raise EquacaoInvalida(f"Equação longa demais (máximo de {LIMITE_LATEX} caracteres).")
    if "\\placeholder" in latex:
        raise EquacaoInvalida("Preencha todas as lacunas (quadradinhos) da equação.")
    _conferir_chaves(latex)
    try:
        return convert(latex)
    except Exception as exc:  # o conversor levanta vários tipos para LaTeX inválido
        raise EquacaoInvalida(_ERROS_CONVERSOR.get(exc.__class__.__name__, "Equação com erro de escrita (LaTeX).")) from None


def latex_para_omml(latex: str, bloco: bool = False, tamanho_pt: Optional[float] = None) -> etree._Element:
    """Devolve <m:oMath> (na linha) ou <m:oMathPara> (equação em destaque, centralizada)."""
    mathml = latex_para_mathml(latex)
    try:
        raiz = etree.fromstring(mathml.encode("utf-8"), parser=etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError:
        if "&" in _limpar_latex(latex):
            raise EquacaoInvalida("O & só pode ser usado dentro de matrizes, sistemas e equações alinhadas.") from None
        raise EquacaoInvalida("Equação inválida.") from None
    conv = _Conversor(int(round(float(tamanho_pt) * 2)) if tamanho_pt else None)
    omath = _novo(_m("oMath"))
    for x in conv.no(raiz):
        omath.append(x)
    if len(omath) == 0:
        raise EquacaoInvalida("Equação vazia.")
    if not bloco:
        return omath
    para = _novo(_m("oMathPara"))
    para.append(_pr("oMathParaPr", jc="center"))
    para.append(omath)
    return para


def validar(latex: str) -> Optional[str]:
    """None se a equação vai sair na prova; senão a mensagem do problema."""
    try:
        latex_para_omml(latex)
        return None
    except EquacaoInvalida as exc:
        return str(exc)


# ---------- equações dentro do HTML do editor ----------
_RX_EQ = re.compile(r'<(span|div)\b[^>]*\bdata-type="(inline-math|block-math|math)"[^>]*>', re.I)
_RX_LATEX = re.compile(r'\bdata-latex="([^"]*)"', re.I)


def equacoes_no_html(html: str) -> list[str]:
    """LaTeX de cada equação do HTML do editor (formato atual e o antigo span[data-type=math])."""
    saida = []
    for m in _RX_EQ.finditer(str(html or "")):
        lx = _RX_LATEX.search(m.group(0))
        saida.append(_html.unescape(lx.group(1)) if lx else "")
    return saida


def problemas_no_html(html: str) -> list[str]:
    probs = []
    for lx in equacoes_no_html(html):
        erro = validar(lx)
        if erro:
            probs.append(f"Equação \"{lx[:50]}\" não pode ir para a prova: {erro}")
    return probs
