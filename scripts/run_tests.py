"""
Roda a suíte de testes do DiagPro num banco PostgreSQL DESCARTÁVEL, com dados sintéticos.

O que este script faz:
  1. recria o banco `diagpro_test` no mesmo servidor do .env (o banco real NÃO é tocado);
  2. aplica as migrações Alembic, as políticas RLS e os grants das roles nesse banco;
  3. gera uma chave mestra DE TESTE e uma pasta de arquivos temporárias (a chave real nunca é usada);
  4. roda o pytest conectado como diagpro_runtime/diagpro_platform via TLS;
  5. apaga a chave de teste e a pasta temporária ao final.

Uso (na raiz do projeto, com o contêiner diagpro_postgres no ar):
  .\\.venv\\Scripts\\python.exe scripts\\run_tests.py            # suíte completa
  .\\.venv\\Scripts\\python.exe scripts\\run_tests.py -k cifra   # argumentos extras vão para o pytest
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
TEST_DB = "diagpro_test"
CONTAINER = os.getenv("DIAGPRO_PG_CONTAINER", "diagpro_postgres")


def trocar_banco(url: str) -> str:
    base, _, real = url.rpartition("/")
    if real.split("?")[0] == TEST_DB:
        return url
    return f"{base}/{TEST_DB}"


def psql(*sql: str, db: str = "postgres", arquivo: Path | None = None) -> None:
    cmd = ["docker", "exec", "-i", CONTAINER, "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", "diagpro_admin", "-d", db]
    for s in sql:
        cmd += ["-c", s]
    r = subprocess.run(cmd, input=arquivo.read_bytes() if arquivo else None, capture_output=True)
    if r.returncode:
        sys.exit("Falha no psql: " + r.stderr.decode(errors="replace")[:400])


def main() -> int:
    cfg = dotenv_values(ROOT / ".env")
    for var in ("DATABASE_URL", "PLATFORM_DATABASE_URL", "ALEMBIC_DATABASE_URL", "DB_SSL_ROOT_CERT"):
        if not cfg.get(var):
            sys.exit(f"{var} ausente no .env.")
    urls = {v: trocar_banco(cfg[v]) for v in ("DATABASE_URL", "PLATFORM_DATABASE_URL", "ALEMBIC_DATABASE_URL")}
    if any(not u.endswith("/" + TEST_DB) for u in urls.values()):
        sys.exit("Trava de segurança: as URLs de teste não apontam para o banco descartável.")

    tmp = Path(tempfile.mkdtemp(prefix="diagpro_tests_"))
    env = dict(os.environ)
    env.update(urls)
    env.update({
        "ADMIN_DATABASE_URL": urls["ALEMBIC_DATABASE_URL"],
        "DB_SSLMODE": cfg.get("DB_SSLMODE", "verify-full"),
        "DB_SSL_ROOT_CERT": cfg["DB_SSL_ROOT_CERT"],
        "DIAGPRO_MASTER_KEY_FILE": str(tmp / "test_master.key"),  # chave só de teste
        "DIAGPRO_FILES_DIR": str(tmp / "files"),
        "DIAGPRO_TEMPLATES_DIR": str(tmp / "templates"),  # nunca a pasta real de templates
        "RECAPTCHA_SECRET_KEY": "",
        "DIAGPRO_RECAPTCHA_DESATIVADO": "1",  # só no banco de teste; em produção o reCAPTCHA falha fechado
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    try:
        print(f"1/4 Recriando o banco descartável {TEST_DB}...")
        psql(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)", f"CREATE DATABASE {TEST_DB} OWNER diagpro_admin")

        print("2/4 Aplicando migrações, RLS e grants...")
        r = subprocess.run([PY, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode:
            sys.exit("Falha no Alembic:\n" + r.stderr[-1500:])
        psql(db=TEST_DB, arquivo=ROOT / "backend" / "app" / "rls_policies.sql")
        r = subprocess.run([PY, str(ROOT / "scripts" / "setup_postgres_roles.py"), "--env-file", os.devnull],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            sys.exit("Falha ao configurar as roles:\n" + (r.stdout + r.stderr)[-1500:])

        print("3/4 Gerando chave mestra de teste...")
        subprocess.run([PY, "-m", "backend.app.field_crypto", "genkey"], cwd=ROOT, env=env, check=True,
                       capture_output=True)

        print("4/4 Rodando pytest...\n")
        # a pasta de trabalho temporária evita que a API crie arquivos dentro do projeto
        return subprocess.run([PY, "-m", "pytest", "-c", str(ROOT / "pytest.ini"), "--rootdir", str(ROOT),
                               str(ROOT / "tests"), "-p", "no:cacheprovider", "-q", "-W", "ignore"] + sys.argv[1:],
                              cwd=tmp, env=env).returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
