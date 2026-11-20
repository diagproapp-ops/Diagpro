# backend/app/estatisticas.py
"""
Estatísticas pós-prova (análise de itens) a partir das respostas dos candidatos.

Entrada: CSV com as colunas `tipo_prova` e `respostas` (uma letra por questão, na ordem do caderno daquela
variação; "." ou "*" ou espaço = em branco; "#" = mais de uma marcada). Qualquer outra coluna (inscrição, nome)
é IGNORADA e nunca guardada: o arquivo é lido só em memória.

Saída (a única coisa guardada, cifrada): por questão (código curto) — respostas, % de acerto, % em branco,
correlação ponto-bisserial (com o total sem a própria questão) e índice D (27% superior x inferior), com alertas;
geral — média, desvio, mínimo, máximo e fidedignidade KR-20.
"""
import csv
import io
import math
import statistics

BRANCO = {".", "*", " ", "-", ""}
MULTIPLA = "#"


class ErroAnalise(Exception):
    pass


def ler_csv(conteudo: bytes, max_linhas: int = 200000) -> list[tuple[str, str]]:
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("latin-1")
    amostra = texto[:2000]
    delim = ";" if amostra.count(";") >= amostra.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delim)
    campos = {(c or "").strip().lower(): c for c in (leitor.fieldnames or [])}
    if "respostas" not in campos or "tipo_prova" not in campos:
        raise ErroAnalise("O arquivo precisa das colunas tipo_prova e respostas (separadas por ; ou ,).")
    linhas = []
    for i, linha in enumerate(leitor, start=2):
        if i > max_linhas + 1:
            raise ErroAnalise(f"Arquivo grande demais (máximo {max_linhas} candidatos).")
        linhas.append(((linha.get(campos["tipo_prova"]) or "").strip(), (linha.get(campos["respostas"]) or "").upper()))
    if not linhas:
        raise ErroAnalise("O arquivo não tem respostas.")
    return linhas


def _sem_acento(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).upper().strip()


def _normalizar_variacao(nome: str, disponiveis: list[str]) -> str | None:
    """Aceita 'PADRÃO'/'PADRAO', 'Tipo 2'/'2' e, com uma variação só, vazio."""
    alvo = _sem_acento(nome)
    for d in disponiveis:
        if _sem_acento(d) == alvo or _sem_acento(d) == f"TIPO {alvo}":
            return d
    if not alvo and len(disponiveis) == 1:
        return disponiveis[0]
    return None


def analisar(gabaritos: dict[str, list[dict]], linhas: list[tuple[str, str]]) -> dict:
    """gabaritos: {variação: [{"numero_questao_exibido", "gabarito_letra_exibida", "codigo_curto_questao"}]}"""
    variacoes = list(gabaritos)
    chaves = {v: sorted(g, key=lambda q: int(q.get("numero_questao_exibido") or 0)) for v, g in gabaritos.items()}
    codigos = sorted({q.get("codigo_curto_questao") or f"#{q.get('numero_questao_exibido')}" for g in chaves.values() for q in g})
    anuladas = {q.get("codigo_curto_questao") for g in chaves.values() for q in g if str(q.get("gabarito_letra_exibida")).upper() == "ANULADA"}
    validas = [c for c in codigos if c not in anuladas]

    candidatos = []  # cada um: {codigo: 1/0} e brancos; só em memória
    erros = []
    for n, (var_nome, resp) in enumerate(linhas, start=2):
        var = _normalizar_variacao(var_nome, variacoes)
        if var is None:
            erros.append(f"Linha {n}: tipo de prova '{var_nome[:20]}' não existe neste cargo.")
            continue
        chave = chaves[var]
        resp = resp.replace(" ", ".") if len(resp.strip()) else resp
        if len(resp) != len(chave):
            erros.append(f"Linha {n}: {len(resp)} respostas, o caderno {var} tem {len(chave)} questões.")
            continue
        acertos, brancos = {}, set()
        for q, r in zip(chave, resp):
            cod = q.get("codigo_curto_questao") or f"#{q.get('numero_questao_exibido')}"
            if cod in anuladas:
                continue
            if r in BRANCO:
                brancos.add(cod)
            acertos[cod] = 1 if (r not in BRANCO and r != MULTIPLA and r == str(q.get("gabarito_letra_exibida")).upper()) else 0
        candidatos.append((acertos, brancos))
        if len(erros) > 50:
            break
    if erros and len(erros) > len(linhas) * 0.05:
        raise ErroAnalise("Muitas linhas com problema: " + " | ".join(erros[:5]))
    if len(candidatos) < 10:
        raise ErroAnalise("São precisos pelo menos 10 candidatos para uma análise com sentido.")

    totais = [sum(a.values()) for a, _ in candidatos]
    n = len(candidatos)
    media = statistics.fmean(totais)
    desvio = statistics.pstdev(totais)
    ordenados = sorted(range(n), key=lambda i: totais[i])
    corte = max(1, round(n * 0.27))
    inferior, superior = set(ordenados[:corte]), set(ordenados[-corte:])

    itens, soma_pq = [], 0.0
    for cod in validas:
        x = [c[0].get(cod, 0) for c in candidatos]
        p = sum(x) / n
        soma_pq += p * (1 - p)
        brancos = sum(1 for c in candidatos if cod in c[1]) / n
        resto = [t - xi for t, xi in zip(totais, x)]  # total sem a própria questão
        s_resto = statistics.pstdev(resto)
        if 0 < p < 1 and s_resto > 0:
            m1 = statistics.fmean([r for r, xi in zip(resto, x) if xi])
            m0 = statistics.fmean([r for r, xi in zip(resto, x) if not xi])
            rpb = (m1 - m0) / s_resto * math.sqrt(p * (1 - p))
        else:
            rpb = 0.0
        d = sum(x[i] for i in superior) / len(superior) - sum(x[i] for i in inferior) / len(inferior)
        alertas = []
        if rpb < 0:
            alertas.append("Discriminação negativa: quem foi melhor na prova errou mais. Confira o gabarito e a redação.")
        elif rpb < 0.15:
            alertas.append("Discrimina pouco entre candidatos melhores e piores.")
        if p < 0.15:
            alertas.append("Acerto muito baixo: confira se o gabarito está certo.")
        elif p > 0.95:
            alertas.append("Quase todos acertaram: questão fácil demais.")
        if brancos > 0.2:
            alertas.append("Muitos em branco: enunciado pode estar confuso.")
        itens.append({"codigo": cod, "acerto": round(p * 100, 1), "brancos": round(brancos * 100, 1),
                      "discriminacao": round(rpb, 3), "indice_d": round(d, 3),
                      "dificuldade": "muito fácil" if p > 0.85 else "fácil" if p > 0.65 else "média" if p > 0.35 else "difícil" if p > 0.15 else "muito difícil",
                      "alertas": alertas})
    k = len(validas)
    var_total = desvio ** 2
    kr20 = (k / (k - 1)) * (1 - soma_pq / var_total) if k > 1 and var_total > 0 else None
    itens.sort(key=lambda i: (not i["alertas"], i["discriminacao"]))
    return {
        "candidatos": n, "linhas_ignoradas": len(linhas) - n, "problemas": erros[:20], "questoes": k,
        "anuladas": sorted(c for c in anuladas if c), "media": round(media, 2), "desvio": round(desvio, 2),
        "minimo": min(totais), "maximo": max(totais), "kr20": round(kr20, 3) if kr20 is not None else None,
        "itens": itens,
    }
