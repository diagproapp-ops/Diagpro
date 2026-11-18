"""
Gera uma CA privada e o certificado TLS do servidor PostgreSQL do DiagPro.

Saída (fora do projeto), por padrão em %LOCALAPPDATA%\\DiagPro\\secrets\\pg-tls\\ :
  ca.crt      -> distribuído aos clientes (DB_SSL_ROOT_CERT); não é segredo
  ca.key      -> SEGREDO: só é necessário para emitir/renovar certificados
  server.crt  -> certificado do servidor (assinado pela CA)
  server.key  -> SEGREDO: copiado para dentro do PGDATA com permissão 0600

Uso: python scripts/gen_pg_tls.py [--renew-server]
"""
import datetime as dt
import ipaddress
import os
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

OUT = Path(os.getenv("DIAGPRO_PG_TLS_DIR") or Path(os.getenv("LOCALAPPDATA", Path.home())) / "DiagPro" / "secrets" / "pg-tls")
SERVER_NAMES = ["localhost", "diagpro_postgres", "db"]
SERVER_IPS = ["127.0.0.1", "::1"]


def _write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


def _load_or_create_ca():
    ca_key_p, ca_crt_p = OUT / "ca.key", OUT / "ca.crt"
    if ca_key_p.exists() and ca_crt_p.exists():
        key = serialization.load_pem_private_key(ca_key_p.read_bytes(), password=None)
        return key, x509.load_pem_x509_certificate(ca_crt_p.read_bytes())
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "DiagPro PostgreSQL CA")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(key, hashes.SHA256())
    )
    _write_key(ca_key_p, key)
    ca_crt_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "server.crt").exists() and "--renew-server" not in sys.argv:
        raise SystemExit(f"Certificado do servidor já existe em {OUT}. Use --renew-server para renovar.")
    ca_key, ca_cert = _load_or_create_ca()
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    san = [x509.DNSName(n) for n in SERVER_NAMES] + [x509.IPAddress(ipaddress.ip_address(i)) for i in SERVER_IPS]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_cert.subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=397))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _write_key(OUT / "server.key", key)
    (OUT / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"CA e certificado do servidor em {OUT} (servidor válido até {cert.not_valid_after_utc:%Y-%m-%d}).")


if __name__ == "__main__":
    main()
