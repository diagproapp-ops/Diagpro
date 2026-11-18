"""
Camada LEGADA de cifra (Fernet) — desativada.

A cifragem dos dados agora é feita em um único lugar, na camada ORM (backend/app/field_crypto.py):
toda coluna sensível é cifrada com AES-256-GCM e chave por tenant ao gravar e decifrada ao carregar.

As funções abaixo existem apenas para não quebrar chamadas antigas espalhadas pelas rotas e pelo
core: elas não cifram nem decifram mais nada (os valores que chegam aqui já estão em texto claro na
memória da aplicação). A FERNET_KEY não é mais lida pela API; ela só é usada pelo script de migração
scripts/reencrypt_fields.py para converter dados antigos.
"""

PII_FIELDS = ("cpf", "pix_key", "banco", "agencia", "conta_corrente")


def encrypt_text(plain_text):
    """Legado: devolve o valor sem alteração (a cifra é aplicada pelo ORM ao gravar)."""
    return plain_text


def decrypt_text(cipher_text):
    """Legado: devolve o valor sem alteração (o ORM já entregou texto claro)."""
    return cipher_text


def encrypt_pii(value):
    """Legado: devolve o valor sem alteração (campos PII são cifrados pelo ORM)."""
    return value


def safe_decrypt_pii(value):
    """Legado: devolve o valor sem alteração."""
    return value


def mask_pii(value: str | None, keep_last: int = 2) -> str:
    """Mascara dado pessoal para uso seguro em logs."""
    if not value:
        return ""
    if len(value) <= keep_last:
        return "*" * len(value)
    return ("*" * (len(value) - keep_last)) + value[-keep_last:]
