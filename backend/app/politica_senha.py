# backend/app/politica_senha.py
"""
Política de senha do DiagPro (valores padrão; a etapa de Configurações vai permitir ajustá-los).

- mínimo de 12 caracteres e 3 dos 4 tipos (maiúscula, minúscula, número, símbolo);
- não pode conter o usuário nem o nome do e-mail; não pode ser senha comum nem sequência óbvia;
- não pode repetir nenhuma das últimas 5 senhas;
- vence a cada 180 dias; senha definida por administrador (provisória) precisa ser trocada no 1º acesso.
"""
import re
from datetime import datetime, timedelta

from backend.app.auth import get_password_hash, verify_password

TAMANHO_MINIMO = 12
TIPOS_MINIMOS = 3
HISTORICO = 5
VALIDADE_DIAS = 180

# lista curta das senhas/bases mais usadas (comparadas sem números e símbolos no fim)
_COMUNS = {
    "senha", "password", "123456", "12345678", "123456789", "qwerty", "abc123", "admin", "administrador",
    "diagpro", "brasil", "mudar", "mudarsenha", "trocar", "bemvindo", "welcome", "letmein", "iloveyou",
    "teste", "test", "usuario", "user", "concurso", "prova", "banca", "qwertyuiop", "asdfgh", "zxcvbn",
}
_SEQUENCIAS = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl", "zxcvbnm")


def _cfg(cfg: dict | None) -> dict:
    """Seção "seguranca" das configurações da plataforma (ou os padrões deste módulo)."""
    cfg = cfg or {}
    return {
        "tamanho": cfg.get("senha_tamanho_minimo", TAMANHO_MINIMO),
        "tipos": cfg.get("senha_tipos_minimos", TIPOS_MINIMOS),
        "historico": cfg.get("senha_historico", HISTORICO),
        "validade": cfg.get("senha_validade_dias", VALIDADE_DIAS),
    }


def regras(cfg: dict | None = None) -> list[str]:
    c = _cfg(cfg)
    return [
        f"Pelo menos {c['tamanho']} caracteres",
        f"Pelo menos {c['tipos']} destes tipos: letra maiúscula, letra minúscula, número, símbolo",
        "Não conter o seu usuário nem o seu e-mail",
        "Não ser uma senha comum nem uma sequência (ex.: 123456, qwerty)",
        f"Ser diferente das suas últimas {c['historico']} senhas",
    ]


def problemas(senha: str, username: str = "", email: str = "", cfg: dict | None = None) -> list[str]:
    """Lista do que falta para a senha valer (vazia = senha aceita). Não consulta o histórico."""
    c = _cfg(cfg)
    senha = senha or ""
    erros = []
    if len(senha) < c["tamanho"]:
        erros.append(f"A senha precisa ter pelo menos {c['tamanho']} caracteres.")
    tipos = sum(bool(re.search(p, senha)) for p in (r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]"))
    if tipos < c["tipos"]:
        erros.append(f"Use pelo menos {c['tipos']} tipos: maiúscula, minúscula, número e símbolo.")
    baixa = senha.lower()
    for termo in {(username or "").lower(), (email or "").split("@")[0].lower()}:
        if len(termo) >= 3 and termo in baixa:
            erros.append("A senha não pode conter o seu usuário nem o seu e-mail.")
            break
    base = re.sub(r"[^a-z]", "", baixa) or baixa
    if base in _COMUNS or baixa in _COMUNS or re.sub(r"[\d\W_]+$", "", baixa) in _COMUNS:
        erros.append("Essa senha é muito comum. Escolha outra.")
    elif any(seq[i:i + 6] in baixa for seq in _SEQUENCIAS for i in range(len(seq) - 5)) or re.search(r"(.)\1{3,}", senha):
        erros.append("Evite sequências e repetições (ex.: 123456, aaaa).")
    return erros


def repetida(senha: str, hash_atual: str | None, historico: list[str] | None) -> bool:
    for h in ([hash_atual] if hash_atual else []) + list(historico or []):
        try:
            if verify_password(senha, h):
                return True
        except ValueError:
            continue
    return False


def precisa_trocar(user, senha_digitada: str | None = None, cfg: dict | None = None) -> bool:
    """Troca obrigatória: senha provisória, vencida ou (ao logar) fora da política atual."""
    if getattr(user, "deve_trocar_senha", False):
        return True
    alterada = getattr(user, "senha_alterada_em", None)
    if alterada and datetime.utcnow() - alterada > timedelta(days=_cfg(cfg)["validade"]):
        return True
    if senha_digitada is not None and problemas(senha_digitada, user.username, user.email or "", cfg):
        return True
    return False


def aplicar_nova_senha(user, nova: str, provisoria: bool = False, cfg: dict | None = None) -> None:
    """Grava a nova senha (já validada) guardando a anterior no histórico."""
    historico = list(getattr(user, "senha_historico", None) or [])
    if user.password_hash:
        historico = ([user.password_hash] + historico)[:_cfg(cfg)["historico"]]
    user.senha_historico = historico
    user.password_hash = get_password_hash(nova)
    user.senha_alterada_em = datetime.utcnow()
    user.deve_trocar_senha = provisoria
