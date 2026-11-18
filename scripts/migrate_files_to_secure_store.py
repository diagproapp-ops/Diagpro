"""
Fase 2a: move os arquivos em claro (static/, avatars/, templates_eventos/) para o armazenamento cifrado.

1. Percorre todas as linhas do banco (sessão de plataforma, já decifrada pelo ORM) e, em cada campo de
   texto/JSON, troca caminhos "static/..." / "avatars/..." por referências sf1:<tenant>:<id>.<ext>,
   cifrando o arquivo com a chave do tenant da linha.
2. Converte os templates de templates_eventos/<evento>/<arquivo> para <arquivo>.enc (chave do tenant do evento).
3. Verifica por SHA-256 que cada arquivo cifrado decifra idêntico ao original.
4. (sem --keep-sources) Empacota TODO o conteúdo original (inclusive arquivos órfãos) num tar cifrado em
   %LOCALAPPDATA%\\DiagPro\\backups, verifica o pacote e só então apaga as pastas em claro.

Uso:
  python scripts/migrate_files_to_secure_store.py [--dry-run] [--keep-sources]
"""
import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.chdir(ROOT)

from sqlalchemy import select  # noqa: E402

from backend.app import secure_files as sf  # noqa: E402
from backend.app.database import Base, PlatformSessionLocal  # noqa: E402
import backend.app.db_models as m  # noqa: E402
import backup_crypto  # noqa: E402

SOURCE_DIRS = ["static", "avatars", "templates_eventos"]
PAT = re.compile(r"/?(?:static|avatars)(?:/|\\{1,2})[^\"'<>,\]\n]+")


def norm(p: str) -> str:
    return re.sub(r"\\+", "/", p).lstrip("/").strip()


async def migrate_db(dry_run: bool):
    created: dict[tuple, tuple[str, str]] = {}  # (tenant, caminho) -> (ref, sha256)
    missing, changed_rows = [], 0

    def to_ref(path: str, tenant):
        key = (tenant, path)
        if key not in created:
            data = Path(path).read_bytes()
            ext = os.path.splitext(path)[1].lstrip(".").lower() or "bin"
            ref = sf.store_bytes(data, tenant, ext, validate=False) if not dry_run else f"sf1:dry:{len(created)}"
            created[key] = (ref, hashlib.sha256(data).hexdigest())
        return created[key][0]

    def convert(value, tenant):
        if isinstance(value, dict):
            return {k: convert(v, tenant) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v, tenant) for v in value]
        if isinstance(value, str) and ("static" in value or "avatars" in value):
            def repl(mt):
                path = norm(mt.group(0))
                if os.path.isfile(path):
                    return to_ref(path, tenant)
                missing.append(path)
                return mt.group(0)
            return PAT.sub(repl, value)
        return value

    async with PlatformSessionLocal() as db:
        for mapper in Base.registry.mappers:
            table = mapper.local_table.name
            cols = [c.key for c in mapper.columns if c.name in sf.fc.ENCRYPTED.get(table, {})]
            if not cols:
                continue
            for obj in (await db.execute(select(mapper.class_))).scalars().all():
                tenant = None if table == "tenants" else getattr(obj, "tenant_id", None)
                dirty = False
                for col in cols:
                    old = getattr(obj, col)
                    new = convert(old, tenant)
                    if new != old:
                        setattr(obj, col, new)
                        dirty = True
                changed_rows += dirty
        if dry_run:
            await db.rollback()
        else:
            await db.commit()
    return created, missing, changed_rows


async def tenant_of_events():
    async with PlatformSessionLocal() as db:
        return {e.id_evento: e.tenant_id for e in (await db.execute(select(m.Evento))).scalars().all()}


def migrate_templates(event_tenants, dry_run):
    done, skipped = [], []
    base = ROOT / "templates_eventos"
    if not base.is_dir():
        return done, skipped
    for ev_dir in base.iterdir():
        if not ev_dir.is_dir():
            continue
        tenant = event_tenants.get(ev_dir.name)
        for f in ev_dir.iterdir():
            if not f.is_file() or f.suffix in (".enc", ".tmp"):
                continue
            if tenant is None:
                skipped.append(str(f.relative_to(ROOT)))
                continue
            data = f.read_bytes()
            if not dry_run:
                sf.write_template(ev_dir.name, f.name, data, tenant)
                assert sf.read_template(ev_dir.name, f.name, tenant) == data
            done.append((f, hashlib.sha256(data).hexdigest()))
    return done, skipped


def backup_and_remove_sources():
    files = [p for d in SOURCE_DIRS if (ROOT / d).is_dir() for p in (ROOT / d).rglob("*")
             if p.is_file() and p.suffix not in (".enc", ".tmp")]
    if not files:
        return None, 0
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in files:
            tar.add(p, arcname=str(p.relative_to(ROOT)))
    raw = buf.getvalue()
    out = Path(os.environ["LOCALAPPDATA"]) / "DiagPro" / "backups" / f"arquivos_em_claro_{time.strftime('%Y%m%d-%H%M%S')}.tar.gz.enc"
    key = backup_crypto.load_key()
    with open(out, "xb") as f:
        backup_crypto.encrypt_stream(io.BytesIO(raw), f, key)
    check = io.BytesIO()
    with open(out, "rb") as f:
        backup_crypto.decrypt_stream(f, check, key)
    if check.getvalue() != raw:
        raise SystemExit("ABORTADO: backup cifrado dos arquivos não confere; nada foi apagado.")
    with tarfile.open(fileobj=io.BytesIO(check.getvalue()), mode="r:gz") as tar:
        if len(tar.getnames()) != len(files):
            raise SystemExit("ABORTADO: pacote incompleto; nada foi apagado.")
    for p in files:
        p.unlink()
    for d in ("static", "avatars"):
        if (ROOT / d).is_dir():
            shutil.rmtree(ROOT / d)
    return out, len(files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-sources", action="store_true")
    args = ap.parse_args()

    async def db_steps():
        try:
            res = await migrate_db(args.dry_run)
            return res, await tenant_of_events()
        finally:
            from backend.app.database import engine, platform_engine
            await engine.dispose()
            await platform_engine.dispose()

    (created, missing, rows), event_tenants = asyncio.run(db_steps())
    print(f"Banco: {rows} linhas atualizadas | {len(created)} arquivos cifrados | caminhos sem arquivo: {sorted(set(missing))}")
    tpl_done, tpl_skipped = migrate_templates(event_tenants, args.dry_run)
    print(f"Templates: {len(tpl_done)} cifrados | sem evento correspondente (ficam no backup): {tpl_skipped}")
    if args.dry_run:
        print("DRY-RUN: nada foi gravado.")
        return

    for (tenant, path), (ref, digest) in created.items():
        if hashlib.sha256(sf.read_bytes(ref, tenant)).hexdigest() != digest:
            raise SystemExit(f"ABORTADO: {path} não confere após a cifra; fontes mantidas.")
    print(f"Verificação SHA-256: {len(created)} arquivos conferidos.")
    if args.keep_sources:
        print("--keep-sources: arquivos em claro mantidos.")
        return
    out, n = backup_and_remove_sources()
    print(f"Backup cifrado das fontes ({n} arquivos): {out}. Pastas em claro removidas.")


if __name__ == "__main__":
    main()
