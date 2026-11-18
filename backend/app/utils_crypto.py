from cryptography.fernet import Fernet, InvalidToken
import os

# Lê a chave Fernet da variável de ambiente FERNET_KEY
FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    raise RuntimeError("A variável de ambiente FERNET_KEY não está definida. Gere uma chave Fernet válida e configure corretamente.")

fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)

PII_FIELDS = ("cpf", "pix_key", "banco", "agencia", "conta_corrente")


def encrypt_text(plain_text: str) -> str:
    if plain_text is None:
        return None
    return fernet.encrypt(plain_text.encode()).decode()


def decrypt_text(cipher_text: str) -> str:
    if cipher_text is None:
        return None
    return fernet.decrypt(cipher_text.encode()).decode()


def encrypt_pii(value: str | None) -> str | None:
    """Criptografa campo pessoal/bancário (LGPD), evitando dupla criptografia."""
    if value is None or value == "":
        return value
    if value.startswith("gAAAAA"):
        try:
            fernet.decrypt(value.encode())
            return value
        except InvalidToken:
            pass
    return encrypt_text(str(value))


def safe_decrypt_pii(value: str | None) -> str | None:
    """Descriptografa campo PII; mantém compatibilidade com valores legados em texto claro."""
    if value is None or value == "":
        return value
    try:
        return decrypt_text(value)
    except InvalidToken:
        return value


def mask_pii(value: str | None, keep_last: int = 2) -> str:
    """Mascara dado pessoal para uso seguro em logs."""
    if not value:
        return ""
    if len(value) <= keep_last:
        return "*" * len(value)
    return ("*" * (len(value) - keep_last)) + value[-keep_last:]
