# backend/app/log_redaction.py
"""
Filtro de redação de logs: impede que segredos e conteúdo de prova cheguem aos logs.

Mascara, em qualquer mensagem (inclusive o log de acesso do uvicorn, que registra a URL completa):
- valores de senha/assinatura/token em query strings e cabeçalhos (ex.: ?senha=..., &sig=..., Bearer ...);
- caminhos de arquivo (Windows e Unix) e nomes de arquivos de prova/imagem, que contêm nomes de
  concursos, cargos e disciplinas.
"""
import logging
import re

_PATTERNS = [
    (re.compile(r"(?i)\b(senha|password|sig|token|access_token|recaptcha_token)=([^&\s\"']+)"), r"\1=<redigido>"),
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-]+"), "Bearer <redigido>"),
    (re.compile(r"(?i)\b[A-Z]:\\[^\"'\n]*?(?=['\"]|\s{2}|$|\s[A-Z]{2,}:|,\s)"), "<caminho>"),
    (re.compile(r"(?i)(?:/[^\s'\"/]+){2,}\.(?:docx|dotx|pdf|zip|csv|png|jpe?g|gif|webp|bmp|json|bin|enc)\b"), "<caminho>"),
    (re.compile(r"(?i)[^\s'\"\\/]+\.(?:docx|dotx|pdf|zip|csv|png|jpe?g|gif|webp|bmp)\b"), "<arquivo>"),
]


def redact(text: str) -> str:
    for rx, rep in _PATTERNS:
        text = rx.sub(rep, text)
    return text


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
        except Exception:
            pass  # o filtro nunca derruba o log
        return True


_FILTER = RedactionFilter()


def install() -> None:
    """Instala o filtro nos handlers da raiz e nos loggers do uvicorn (inclui o log de acesso)."""
    root = logging.getLogger()
    for h in root.handlers:
        if _FILTER not in h.filters:
            h.addFilter(_FILTER)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        if _FILTER not in lg.filters:
            lg.addFilter(_FILTER)
        for h in lg.handlers:
            if _FILTER not in h.filters:
                h.addFilter(_FILTER)
