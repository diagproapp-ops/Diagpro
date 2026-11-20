"""
Converte os dados existentes para a cifragem de campos do DiagPro (fase 1b).

Para cada coluna registrada em backend/app/field_crypto.ENCRYPTED:
  1. lê o valor atual (texto claro, ou token Fernet legado, que é decifrado com FERNET_KEY);
  2. cifra com AES-256-GCM usando a chave do tenant da linha e AAD (tabela, coluna, tenant);
  3. preenche os índices cegos (BLIND_INDEXES);
  4. ao final, decifra novamente TODOS os valores e compara com o texto claro de origem.
Tudo ocorre em uma única transação: qualquer divergência desfaz a conversão inteira.

Pré-requisitos: `alembic upgrade head` (revisão e7b2d4f8a1c6) e a chave mestra criada
(python -m backend.app.field_crypto genkey).

Uso:
  python scripts/reencrypt_fields.py [--dry-run] [--database NOME]
Conecta com a role administrativa (ALEMBIC_DATABASE_URL), que ignora o RLS por ser dona das tabelas.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402
from psycopg2 import sql  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

from backend.app import field_crypto as fc  # noqa: E402

cfg = dotenv_values(ROOT / ".env")


def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name) or cfg.get(name) or default


def legacy_fernet():
    """Chave Fernet LEGADA, usada só para converter dados/backups antigos (a API não a usa mais)."""
    key = env("FERNET_KEY")
    if not key:
        path = Path(env("DIAGPRO_LEGACY_FERNET_KEY_FILE") or
                    Path(os.getenv("LOCALAPPDATA", Path.home())) / "DiagPro" / "secrets" / "legacy_fernet.key")
        key = path.read_text().strip() if path.is_file() else None
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def undo_legacy(value: str, fernet, where: str) -> str:
    """Remove até 3 camadas de Fernet legado. Texto que não é token Fernet é devolvido intacto."""
    for _ in range(3):
        if not value.startswith("gAAAAA"):
            return value
        if fernet is None:
            raise SystemExit(f"{where}: valor Fernet legado encontrado, mas FERNET_KEY não está configurada.")
        try:
            value = fernet.decrypt(value.encode()).decode()
        except Exception:
            return value  # começa com gAAAAA mas não é token válido: é texto do usuário
    return value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--database")
    args = ap.parse_args()

    u = urlparse(env("ALEMBIC_DATABASE_URL").replace("postgresql+psycopg2://", "postgresql://"))
    sslmode = env("DB_SSLMODE", "verify-full")
    kw = {"sslmode": sslmode}
    if sslmode == "verify-full":
        kw["sslrootcert"] = env("DB_SSL_ROOT_CERT")
    conn = psycopg2.connect(host=u.hostname, port=u.port, user=u.username, password=u.password,
                            dbname=args.database or u.path.lstrip("/"), **kw)
    conn.autocommit = False
    fernet = legacy_fernet()
    stats = {"linhas": 0, "valores": 0, "ja_cifrados": 0, "fernet_removido": 0}
    expected: dict[tuple, str] = {}

    with conn.cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        if cur.fetchone()[0] not in ("e7b2d4f8a1c6", "a9d4c2e6f0b1", "c5e8f1a3b9d2", "d8b2f4a6c1e3", "e9c3a5b7d2f4", "f1a7c3e5b9d2", "a2b4c6d8e0f1", "b4d6f8a0c2e3"):
            raise SystemExit("O banco precisa estar na revisão e7b2d4f8a1c6 ou posterior (alembic upgrade head).")

        for table, spec in fc.ENCRYPTED.items():
            cur.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
                        "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = %s::regclass AND i.indisprimary",
                        (f'"{table}"',))
            pk = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                        (table,))
            existing = {r[0] for r in cur.fetchall()}
            has_tenant = "tenant_id" in existing
            bidx = fc.BLIND_INDEXES.get(table, {})
            cols = list(spec)
            select_cols = pk + (["tenant_id"] if has_tenant else []) + cols
            cur.execute(sql.SQL("SELECT {} FROM {}").format(
                sql.SQL(", ").join(map(sql.Identifier, select_cols)), sql.Identifier(table)))
            rows = cur.fetchall()
            for row in rows:
                rec = dict(zip(select_cols, row))
                tenant_id = rec["tenant_id"] if has_tenant else None
                key_tenant = fc.row_tenant(table, tenant_id)
                plain_values, updates = {}, {}
                for col in cols:
                    raw = rec[col]
                    if raw is None:
                        plain_values[col] = None
                        continue
                    where = f"{table}.{col} pk={[rec[k] for k in pk]}"
                    if fc.is_encrypted(raw):
                        plain = fc.decrypt_value(raw, table=table, column=col, tenant_id=key_tenant)
                        stats["ja_cifrados"] += 1
                    else:
                        plain = undo_legacy(raw, fernet, where)
                        if plain != raw:
                            stats["fernet_removido"] += 1
                        if spec[col] == "json":
                            json.loads(plain)  # garante que é JSON válido antes de cifrar
                        updates[col] = fc.encrypt_value(plain, table=table, column=col, tenant_id=key_tenant)
                        stats["valores"] += 1
                    expected[(table, col, tuple(rec[k] for k in pk))] = plain
                    plain_values[col] = plain if spec[col] == "text" else json.loads(plain)
                for bcol, digest in fc.compute_blind_indexes(table, plain_values, tenant_id).items():
                    updates[bcol] = digest
                if updates:
                    cur.execute(
                        sql.SQL("UPDATE {} SET {} WHERE {}").format(
                            sql.Identifier(table),
                            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in updates),
                            sql.SQL(" AND ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in pk)),
                        list(updates.values()) + [rec[k] for k in pk])
                stats["linhas"] += 1
            print(f"[OK] {table}: {len(rows)} linhas")

        # Verificação 1: nenhuma coluna registrada pode conter texto claro
        leftovers = []
        for table, spec in fc.ENCRYPTED.items():
            for col in spec:
                cur.execute(sql.SQL("SELECT count(*) FROM {} WHERE {} IS NOT NULL AND {} NOT LIKE 'e1.%%'").format(
                    sql.Identifier(table), sql.Identifier(col), sql.Identifier(col)))
                n = cur.fetchone()[0]
                if n:
                    leftovers.append((table, col, n))
        if leftovers:
            conn.rollback()
            raise SystemExit(f"ABORTADO: valores em texto claro restantes: {leftovers}")

        # Verificação 2: decifrar tudo de novo e comparar com o texto claro de origem
        checked = 0
        for table, spec in fc.ENCRYPTED.items():
            cur.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
                        "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = %s::regclass AND i.indisprimary",
                        (f'"{table}"',))
            pk = [r[0] for r in cur.fetchall()]
            has_tenant = table != "tenants"
            sel = pk + (["tenant_id"] if has_tenant else []) + list(spec)
            cur.execute(sql.SQL("SELECT {} FROM {}").format(sql.SQL(", ").join(map(sql.Identifier, sel)), sql.Identifier(table)))
            for row in cur.fetchall():
                rec = dict(zip(sel, row))
                key_tenant = fc.row_tenant(table, rec.get("tenant_id"))
                for col in spec:
                    if rec[col] is None:
                        continue
                    got = fc.decrypt_value(rec[col], table=table, column=col, tenant_id=key_tenant)
                    if got != expected[(table, col, tuple(rec[k] for k in pk))]:
                        conn.rollback()
                        raise SystemExit(f"ABORTADO: divergência ao decifrar {table}.{col}")
                    checked += 1

    if args.dry_run:
        conn.rollback()
        print(f"DRY-RUN (nada gravado): {stats} | valores verificados: {checked}")
    else:
        conn.commit()
        print(f"CONCLUÍDO: {stats} | valores verificados: {checked}")
    conn.close()


if __name__ == "__main__":
    main()
