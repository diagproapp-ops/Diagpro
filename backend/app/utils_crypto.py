from cryptography.fernet import Fernet
import os

# Lê a chave Fernet da variável de ambiente FERNET_KEY
FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    raise RuntimeError("A variável de ambiente FERNET_KEY não está definida. Gere uma chave Fernet válida e configure corretamente.")

fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)

def encrypt_text(plain_text: str) -> str:
    if plain_text is None:
        return None
    return fernet.encrypt(plain_text.encode()).decode()

def decrypt_text(cipher_text: str) -> str:
    if cipher_text is None:
        return None
    return fernet.decrypt(cipher_text.encode()).decode()