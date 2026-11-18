"""
Script idempotente de migração de dados: SQLite (diagprooff.db) -> PostgreSQL Multi-Tenant com RLS.
Pré-requisito: o schema já deve ter sido criado via `alembic upgrade head`.

Uso:
    .\.venv\Scripts\python.exe scripts/migrate_sqlite_to_postgres.py
"""
import json
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, create_engine, inspect, text

load_dotenv()

import backend.app.db_models  # noqa: E402, F401

SQLITE_PATH = PROJECT_ROOT / "diagprooff.db"
RLS_SQL_PATH = PROJECT_ROOT / "backend" / "app" / "rls_policies.sql"

ORDERED_MODELS = [
    backend.app.db_models.Tenant,
    backend.app.db_models.User,
    backend.app.db_models.Company,
    backend.app.db_models.AuditLogGeracao,
    backend.app.db_models.Evento,
    backend.app.db_models.Cargo,
    backend.app.db_models.Disciplina,
    backend.app.db_models.DisciplinaDaProva,
    backend.app.db_models.Conteudo,
    backend.app.db_models.TextoReferenciaGeral,
    backend.app.db_models.QuestoesBanco,
    backend.app.db_models.OpcoesQuestao,
    backend.app.db_models.ItensVerdadeiroFalso,
    backend.app.db_models.DetalhesQuestaoDiscursiva,
    backend.app.db_models.HistoricoRevisaoQuestao,
    backend.app.db_models.ProvaMontada,
    backend.app.db_models.BancoFrases,
]


def get_pg_sync_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url or url.startswith("sqlite"):
        raise RuntimeError(
            "Defina DATABASE_URL apontando para o PostgreSQL antes de rodar a migração."
        )
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def coerce_value(val, col_type):
    if val is None:
        return None
    if isinstance(col_type, Boolean):
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        return str(val).strip().lower() in {"1", "true", "t", "yes", "sim"}
    if isinstance(col_type, Integer):
        return int(val) if val != "" else None
    if isinstance(col_type, DateTime):
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            val_clean = val.strip().replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(val_clean)
            except ValueError:
                return datetime.strptime(val_clean[:19], "%Y-%m-%d %H:%M:%S")
    if isinstance(col_type, Date):
        if isinstance(val, date):
            return val
        if isinstance(val, str):
            return date.fromisoformat(val.strip()[:10])
    if isinstance(col_type, JSON):
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
        return None
    return val


def build_backfill_maps(sqlite_conn: sqlite3.Connection) -> dict:
    eventos_map = {
        r[0]: int(r[1])
        for r in sqlite_conn.execute('SELECT id_evento, tenant_id FROM "Eventos" WHERE tenant_id IS NOT NULL').fetchall()
    }
    cargos_map = {
        r[0]: int(r[1])
        for r in sqlite_conn.execute('SELECT id_cargo, tenant_id FROM "Cargos" WHERE tenant_id IS NOT NULL').fetchall()
    }
    disciplinas_ids = {r[0] for r in sqlite_conn.execute('SELECT id_disciplina FROM "Disciplinas"').fetchall()}
    questoes_map = {}
    for qid, tid, eid in sqlite_conn.execute('SELECT id_questao, tenant_id, id_evento_fk FROM "QuestoesBanco"').fetchall():
        resolved = int(tid) if tid is not None else eventos_map.get(eid)
        if resolved is not None:
            questoes_map[qid] = resolved
    return {
        "eventos": eventos_map,
        "cargos": cargos_map,
        "disciplinas_ids": disciplinas_ids,
        "questoes": questoes_map,
        "seen_conteudo_ids": set(),
        "seen_codigos_curtos": set(),
    }


def resolve_row_for_postgres(table_name: str, item: dict, maps: dict) -> tuple[bool, str]:
    """Faz backfill determinístico de tenant_id nulo e filtra registros órfãos de FKs inexistentes."""
    if table_name == "conteudos":
        ident = item.get("identificador_conteudo")
        if ident:
            if ident in maps["seen_conteudo_ids"]:
                item["identificador_conteudo"] = f"{ident}_{str(item.get('id_conteudo', ''))[:6]}"
            maps["seen_conteudo_ids"].add(item["identificador_conteudo"])
    elif table_name == "Disciplinas" and item.get("tenant_id") is None:
        item["tenant_id"] = maps["eventos"].get(item.get("id_evento_fk"))
    elif table_name == "DisciplinasDaProva":
        if item.get("id_cargo_fk") not in maps["cargos"]:
            return False, "cargo órfão"
        if item.get("id_disciplina_base_fk") and item["id_disciplina_base_fk"] not in maps["disciplinas_ids"]:
            item["id_disciplina_base_fk"] = None
        if item.get("tenant_id") is None:
            item["tenant_id"] = maps["cargos"].get(item.get("id_cargo_fk"))
    elif table_name == "ProvasMontadas" and item.get("tenant_id") is None:
        item["tenant_id"] = maps["eventos"].get(item.get("id_evento_fk")) or maps["cargos"].get(item.get("id_cargo_fk"))
    elif table_name == "QuestoesBanco":
        if item.get("tenant_id") is None:
            item["tenant_id"] = maps["eventos"].get(item.get("id_evento_fk"))
        cod = item.get("codigo_curto_questao")
        if cod:
            if cod in maps["seen_codigos_curtos"]:
                item["codigo_curto_questao"] = f"{cod}-{str(item.get('id_questao', ''))[:4]}"
            maps["seen_codigos_curtos"].add(item["codigo_curto_questao"])
    elif table_name in {"OpcoesQuestao", "ItensVerdadeiroFalso", "DetalhesQuestaoDiscursiva"}:
        if item.get("id_questao_fk") not in maps["questoes"]:
            return False, "questão órfã"
        if item.get("tenant_id") is None:
            item["tenant_id"] = maps["questoes"].get(item.get("id_questao_fk"))
    return True, ""


def main() -> None:
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"Banco SQLite não encontrado em: {SQLITE_PATH}")

    pg_engine = create_engine(get_pg_sync_url())
    inspector = inspect(pg_engine)
    existing_tables = set(inspector.get_table_names())
    required_tables = {m.__table__.name for m in ORDERED_MODELS}
    missing = sorted(required_tables - existing_tables)
    if missing:
        raise RuntimeError(
            f"Tabelas ausentes no PostgreSQL: {missing}. Execute `alembic upgrade head` antes da migração de dados."
        )

    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    maps = build_backfill_maps(sqlite_conn)

    with pg_engine.begin() as pg_conn:
        for model in ORDERED_MODELS:
            table = model.__table__
            table_name = table.name

            try:
                rows = sqlite_conn.execute(f'SELECT * FROM "{table_name}"').fetchall()
            except sqlite3.OperationalError as exc:
                print(f"[SKIP] Tabela '{table_name}' ausente no SQLite: {exc}")
                continue

            existing_count = pg_conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
            if existing_count and existing_count > 0:
                print(f"[SKIP] '{table_name}' já possui {existing_count} registros no Postgres.")
                continue

            if not rows:
                print(f"[OK]   '{table_name}': 0 registros.")
                continue

            payload = []
            skipped_orphans = 0
            for row in rows:
                row_dict = dict(row)
                item = {}
                for col in table.columns:
                    if col.name in row_dict:
                        item[col.name] = coerce_value(row_dict[col.name], col.type)
                keep, _ = resolve_row_for_postgres(table_name, item, maps)
                if not keep:
                    skipped_orphans += 1
                    continue
                payload.append(item)

            if payload:
                pg_conn.execute(table.insert(), payload)

            pk_cols = list(table.primary_key.columns)
            if len(pk_cols) == 1 and isinstance(pk_cols[0].type, Integer):
                pk_name = pk_cols[0].name
                pg_conn.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('\"{table_name}\"', '{pk_name}'), "
                        f"COALESCE((SELECT MAX(\"{pk_name}\") FROM \"{table_name}\"), 1), true)"
                    )
                )

            extra = f" ({skipped_orphans} órfãos ignorados)" if skipped_orphans else ""
            print(f"[OK]   '{table_name}': {len(payload)} registros migrados{extra}.")

        if RLS_SQL_PATH.exists():
            rls_sql = RLS_SQL_PATH.read_text(encoding="utf-8")
            pg_conn.execute(text(rls_sql))
            print("[OK]   Políticas RLS (ENABLE + FORCE) aplicadas com sucesso.")

    sqlite_conn.close()
    print("Migração concluída!")


if __name__ == "__main__":
    main()
