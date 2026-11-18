"""
Cria/ajusta as roles de aplicação do DiagPro com privilégio mínimo.

  diagpro_runtime   LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  diagpro_platform  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS

Ambas recebem apenas SELECT/INSERT/UPDATE/DELETE nas tabelas e USAGE/SELECT nas sequências do schema
public; nenhuma pode criar objetos nem ser dona de tabela (o dono pode desativar o RLS).

Conecta com a role administrativa de ALEMBIC_DATABASE_URL (ou ADMIN_DATABASE_URL).

Senhas (nunca são impressas):
  --rotate            gera senhas aleatórias para as duas roles, aplica no banco e atualiza o .env
                      (DATABASE_URL e PLATFORM_DATABASE_URL)
  sem --rotate        usa DIAGPRO_RUNTIME_DB_PASSWORD / DIAGPRO_PLATFORM_DB_PASSWORD se definidas;
                      role nova sem senha definida => erro (fail-closed)

Uso:
  python scripts/setup_postgres_roles.py [--rotate] [--env-file .env]
"""
import argparse
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ROLES = {
    "diagpro_runtime": {"bypass": False, "env": "DIAGPRO_RUNTIME_DB_PASSWORD", "url_var": "DATABASE_URL", "limit": 50},
    "diagpro_platform": {"bypass": True, "env": "DIAGPRO_PLATFORM_DB_PASSWORD", "url_var": "PLATFORM_DATABASE_URL", "limit": 10},
}


def _admin_conn(cfg: dict):
    url = os.getenv("ADMIN_DATABASE_URL") or os.getenv("ALEMBIC_DATABASE_URL") or cfg.get("ALEMBIC_DATABASE_URL")
    if not url:
        sys.exit("Defina ALEMBIC_DATABASE_URL (role administrativa).")
    u = urlparse(url.replace("postgresql+psycopg2://", "postgresql://"))
    sslmode = os.getenv("DB_SSLMODE") or cfg.get("DB_SSLMODE") or "verify-full"
    kw = {"sslmode": sslmode}
    if sslmode == "verify-full":
        kw["sslrootcert"] = os.getenv("DB_SSL_ROOT_CERT") or cfg.get("DB_SSL_ROOT_CERT")
    return psycopg2.connect(host=u.hostname, port=u.port or 5432, user=u.username, password=u.password,
                            dbname=u.path.lstrip("/"), **kw)


def _set_env_url(env_file: Path, var: str, role: str, password: str, template_url: str) -> None:
    """Atualiza (ou cria) a URL da role no .env trocando somente usuário/senha."""
    text = env_file.read_text(encoding="utf-8")
    current = dotenv_values(env_file).get(var) or template_url
    u = urlparse(current)
    netloc = f"{quote(role, safe='')}:{quote(password, safe='')}@{u.hostname}" + (f":{u.port}" if u.port else "")
    new_url = urlunparse(u._replace(netloc=netloc))
    line = f"{var}={new_url}"
    pattern = re.compile(rf"^{re.escape(var)}=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(lambda _m: line, text, count=1)
    else:
        text = text.rstrip("\n") + f"\n{line}\n"
    env_file.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate", action="store_true")
    ap.add_argument("--env-file", default=str(ROOT / ".env"))
    args = ap.parse_args()
    env_file = Path(args.env_file)
    cfg = dotenv_values(env_file) if env_file.exists() else {}

    new_passwords: dict[str, str] = {}
    conn = _admin_conn(cfg)
    conn.autocommit = False
    with conn, conn.cursor() as cur:
        for role, spec in ROLES.items():
            attrs = sql.SQL("LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION {} CONNECTION LIMIT {}").format(
                sql.SQL("BYPASSRLS" if spec["bypass"] else "NOBYPASSRLS"), sql.Literal(spec["limit"]))
            password = secrets.token_urlsafe(32) if args.rotate else (os.getenv(spec["env"]) or None)
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            exists = cur.fetchone() is not None
            if not exists and not password:
                sys.exit(f"Role {role} não existe e nenhuma senha foi fornecida ({spec['env']} ou --rotate).")
            stmt = sql.SQL("ALTER ROLE {} " if exists else "CREATE ROLE {} ").format(sql.Identifier(role)) + attrs
            if password:
                stmt += sql.SQL(" PASSWORD {}").format(sql.Literal(password))
                new_passwords[role] = password
            cur.execute(stmt)

            ident = sql.Identifier(role)
            cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(ident))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident))
            cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(ident))
            cur.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(ident))
            cur.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(ident))
            cur.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}").format(ident))
        # A tabela de controle do Alembic não deve ser alterável pelas roles de aplicação
        cur.execute("SELECT to_regclass('public.alembic_version')")
        if cur.fetchone()[0]:
            for role in ROLES:
                cur.execute(sql.SQL("REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM {}").format(sql.Identifier(role)))

        cur.execute("SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'public' AND tableowner = ANY(%s)",
                    (list(ROLES),))
        owned = cur.fetchall()
        if owned:
            sys.exit(f"ERRO: roles de aplicação são donas de tabelas (poderiam desativar o RLS): {owned}")

        cur.execute("SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = ANY(%s) ORDER BY 1",
                    (list(ROLES),))
        for name, sup, byp, crr, crd in cur.fetchall():
            print(f"{name}: superuser={sup} bypassrls={byp} createrole={crr} createdb={crd}")
    conn.close()

    if args.rotate:
        template = cfg.get("DATABASE_URL", "")
        for role, password in new_passwords.items():
            _set_env_url(env_file, ROLES[role]["url_var"], role, password, template)
        print(f"Senhas rotacionadas e gravadas em {env_file} (não exibidas).")


if __name__ == "__main__":
    main()
