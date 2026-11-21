"""
Retenções do RPA (professor pessoa física): INSS, IRRF e ISS sobre o valor bruto da parcela.

Os valores padrão são só uma REFERÊNCIA (tabela mensal do IRRF e redutor da Lei 15.270/2025, INSS de contribuinte
individual com teto): mudam por lei e por município. A banca confere com a contabilidade e ajusta em Financeiro >
Tabela, parcelas e modelos. Simplificação: cada pagamento é calculado sozinho (não soma outros pagamentos do mês).
"""
from __future__ import annotations

from backend.app.fin_calculo import num

RETENCOES_PADRAO = {
    "inss_percentual": 11.0,      # contribuinte individual com retenção pela empresa
    "inss_teto": 8157.41,         # teto do salário de contribuição (atualize a cada ano)
    "iss_percentual": 0.0,        # depende do município (0 = não reter)
    "irrf_deducao_dependente": 189.59,
    # faixas mensais: [limite superior (None = acima), alíquota %, parcela a deduzir R$]
    "irrf_faixas": [[2428.80, 0.0, 0.0], [2826.65, 7.5, 182.16], [3751.05, 15.0, 394.16],
                    [4664.68, 22.5, 675.49], [None, 27.5, 908.73]],
    # redutor mensal (a partir de 2026): até `isento_ate` não paga; até `faixa_ate`, reduz `a - b x rendimento`
    "irrf_redutor": {"ativo": True, "isento_ate": 5000.0, "faixa_ate": 7350.0, "a": 978.62, "b": 0.133145},
}


def config(cfg_banca: dict | None) -> dict:
    base = {**RETENCOES_PADRAO, "irrf_redutor": dict(RETENCOES_PADRAO["irrf_redutor"])}
    r = (cfg_banca or {}).get("retencoes") or {}
    for k in ("inss_percentual", "inss_teto", "iss_percentual", "irrf_deducao_dependente"):
        if k in r:
            base[k] = max(0.0, num(r[k]))
    if isinstance(r.get("irrf_faixas"), list) and r["irrf_faixas"]:
        base["irrf_faixas"] = [[(None if f[0] in (None, "") else num(f[0])), num(f[1]), num(f[2])] for f in r["irrf_faixas"]]
    if isinstance(r.get("irrf_redutor"), dict):
        red = r["irrf_redutor"]
        base["irrf_redutor"] = {"ativo": bool(red.get("ativo", True)), "isento_ate": num(red.get("isento_ate")),
                                "faixa_ate": num(red.get("faixa_ate")), "a": num(red.get("a")), "b": num(red.get("b"))}
    return base


def calcular(bruto: float, cfg: dict, dependentes: int = 0) -> dict:
    bruto = round(max(0.0, num(bruto)), 2)
    inss = round(min(bruto, cfg["inss_teto"]) * cfg["inss_percentual"] / 100.0, 2)
    base = max(0.0, bruto - inss - dependentes * cfg["irrf_deducao_dependente"])
    irrf = 0.0
    for limite, aliquota, deducao in cfg["irrf_faixas"]:
        if limite is None or base <= limite:
            irrf = max(0.0, base * aliquota / 100.0 - deducao)
            break
    red = cfg["irrf_redutor"]
    if red.get("ativo") and irrf > 0:
        if bruto <= red["isento_ate"]:
            irrf = 0.0
        elif bruto <= red["faixa_ate"]:
            irrf = max(0.0, irrf - max(0.0, red["a"] - red["b"] * bruto))
    irrf = round(irrf, 2)
    iss = round(bruto * cfg["iss_percentual"] / 100.0, 2)
    return {"bruto": bruto, "inss": inss, "base_irrf": round(base, 2), "irrf": irrf, "iss": iss,
            "total_retido": round(inss + irrf + iss, 2), "liquido": round(bruto - inss - irrf - iss, 2)}
