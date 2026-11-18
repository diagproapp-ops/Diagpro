"""
Cifra/decifra backups do DiagPro com AES-256-GCM em blocos (streaming).

Formato: MAGIC(6) | nonce_prefix(8) | blocos...
  bloco = tamanho(4, big-endian) | ciphertext+tag
  nonce do bloco i = nonce_prefix || i (4 bytes)
  AAD do bloco i   = MAGIC || nonce_prefix || i || flag_final
Truncar, reordenar ou alterar qualquer bloco faz a decifragem falhar.

A chave (32 bytes, base64) fica FORA do projeto, por padrão em
%LOCALAPPDATA%\\DiagPro\\secrets\\backup.key (ou DIAGPRO_BACKUP_KEY_FILE).

Uso:
  python scripts/backup_crypto.py genkey
  <comando que gera o dump> | python scripts/backup_crypto.py encrypt ARQUIVO.enc
  python scripts/backup_crypto.py decrypt ARQUIVO.enc | <comando que lê o dump>
  python scripts/backup_crypto.py encrypt-file ORIGEM ARQUIVO.enc
"""
import base64
import os
import struct
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"DPBK1\n"
CHUNK = 1024 * 1024


def key_path() -> Path:
    env = os.getenv("DIAGPRO_BACKUP_KEY_FILE")
    if env:
        return Path(env)
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "DiagPro" / "secrets" / "backup.key"


def load_key() -> bytes:
    p = key_path()
    if not p.exists():
        raise SystemExit(f"Chave de backup não encontrada em {p}. Rode 'genkey' primeiro.")
    key = base64.b64decode(p.read_text().strip())
    if len(key) != 32:
        raise SystemExit("Chave de backup inválida (esperado 32 bytes).")
    return key


def genkey() -> None:
    p = key_path()
    if p.exists():
        raise SystemExit(f"Já existe uma chave em {p}; não sobrescrevo.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(base64.b64encode(os.urandom(32)).decode())
    print(f"Chave criada em {p}. Guarde uma cópia offline: sem ela os backups são irrecuperáveis.")


def _aad(prefix: bytes, i: int, final: bool) -> bytes:
    return MAGIC + prefix + struct.pack(">I?", i, final)


def encrypt_stream(src, dst, key: bytes) -> int:
    aes = AESGCM(key)
    prefix = os.urandom(8)
    dst.write(MAGIC + prefix)
    i, total = 0, 0
    buf = src.read(CHUNK)
    while True:
        nxt = src.read(CHUNK) if buf else b""
        final = not nxt
        ct = aes.encrypt(prefix + struct.pack(">I", i), buf, _aad(prefix, i, final))
        dst.write(struct.pack(">I", len(ct)) + ct)
        total += len(buf)
        if final:
            return total
        buf, i = nxt, i + 1


def decrypt_stream(src, dst, key: bytes) -> int:
    aes = AESGCM(key)
    if src.read(len(MAGIC)) != MAGIC:
        raise SystemExit("Arquivo não é um backup DiagPro (cabeçalho inválido).")
    prefix = src.read(8)
    i, total = 0, 0
    while True:
        hdr = src.read(4)
        if len(hdr) != 4:
            raise SystemExit("Backup truncado: bloco final ausente.")
        ct = src.read(struct.unpack(">I", hdr)[0])
        nonce = prefix + struct.pack(">I", i)
        try:
            pt = aes.decrypt(nonce, ct, _aad(prefix, i, False))
            final = False
        except Exception:
            pt = aes.decrypt(nonce, ct, _aad(prefix, i, True))  # falha => adulterado
            final = True
        dst.write(pt)
        total += len(pt)
        if final:
            if src.read(1):
                raise SystemExit("Dados extras após o bloco final: arquivo adulterado.")
            return total
        i += 1


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "genkey":
        genkey()
    elif cmd == "encrypt" and len(sys.argv) == 3:
        with open(sys.argv[2], "xb") as out:
            n = encrypt_stream(sys.stdin.buffer, out, load_key())
        print(f"{n} bytes cifrados em {sys.argv[2]}", file=sys.stderr)
    elif cmd == "encrypt-file" and len(sys.argv) == 4:
        with open(sys.argv[2], "rb") as src, open(sys.argv[3], "xb") as out:
            n = encrypt_stream(src, out, load_key())
        print(f"{n} bytes cifrados em {sys.argv[3]}", file=sys.stderr)
    elif cmd == "decrypt" and len(sys.argv) == 3:
        with open(sys.argv[2], "rb") as src:
            n = decrypt_stream(src, sys.stdout.buffer, load_key())
        sys.stdout.buffer.flush()
        print(f"{n} bytes decifrados", file=sys.stderr)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
