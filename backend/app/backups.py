# backend/app/backups.py
"""
Backups automáticos do banco, cifrados (AES-256-GCM em blocos, mesmo formato de scripts/backup_crypto.py).

- O dump sai do comando DIAGPRO_BACKUP_CMD (padrão: pg_dump dentro do contêiner) direto para a cifra: nada fica
  em claro no disco. Cada arquivo é conferido logo depois (decifra inteiro e confere a assinatura do pg_dump).
- Ficam em DIAGPRO_BACKUP_DIR (padrão %LOCALAPPDATA%\\DiagPro\\backups), fora do projeto. Não há download pela
  web: o backup tem os dados de todas as bancas.
- Retenção: mantém os N automáticos mais recentes (os manuais e os de migração nunca são apagados aqui).
- Falha avisa o administrador geral (sino/e-mail).
"""
import asyncio
import importlib.util
import io
import logging
import os
import re
import shlex
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from backend.app import configuracoes

logger = logging.getLogger("backups")
_RAIZ = Path(__file__).resolve().parents[2]
_NOME = re.compile(r"^pg_diagpro_(\d{8}-\d{6})_([a-z0-9-]+)\.dump\.enc$")
_PADRAO_CMD = "docker exec diagpro_postgres pg_dump -U diagpro_admin -Fc diagpro"
_TRAVA = asyncio.Lock()
ESTADO = {"ultimo_ok": None, "ultimo_erro": None, "ultimo_erro_em": None, "em_andamento": False}


def _cripto():
    spec = importlib.util.spec_from_file_location("diagpro_backup_crypto", _RAIZ / "scripts" / "backup_crypto.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pasta() -> Path:
    env = os.getenv("DIAGPRO_BACKUP_DIR")
    base = Path(env) if env else Path(os.getenv("LOCALAPPDATA") or Path.home()) / "DiagPro" / "backups"
    base.mkdir(parents=True, exist_ok=True)
    return base


def listar() -> list[dict]:
    itens = []
    for p in pasta().iterdir():
        m = _NOME.match(p.name)
        if m:
            itens.append({"arquivo": p.name, "criado_em": datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").isoformat(),
                          "motivo": m.group(2), "tamanho": p.stat().st_size})
    return sorted(itens, key=lambda x: x["criado_em"], reverse=True)


class ErroBackup(Exception):
    pass


def _executar(motivo: str) -> dict:
    """Síncrono (roda numa thread): dump -> cifra -> confere."""
    cripto = _cripto()
    try:
        chave = cripto.load_key()
    except SystemExit as exc:
        raise ErroBackup(f"Chave de backup indisponível: {exc}")
    momento = datetime.now()
    destino = pasta() / f"pg_diagpro_{momento:%Y%m%d-%H%M%S}_{motivo}.dump.enc"
    while destino.exists():  # dois backups no mesmo segundo: não sobrescreve
        momento += timedelta(seconds=1)
        destino = pasta() / f"pg_diagpro_{momento:%Y%m%d-%H%M%S}_{motivo}.dump.enc"
    bruto = os.getenv("DIAGPRO_BACKUP_CMD", _PADRAO_CMD)
    cmd = bruto if os.name == "nt" else shlex.split(bruto)  # Windows: a própria CreateProcess separa (sem shell)
    inicio = time.monotonic()
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise ErroBackup(f"Não foi possível executar o comando de dump ({type(exc).__name__}).")
    try:
        with open(destino, "xb") as out:
            tamanho = cripto.encrypt_stream(proc.stdout, out, chave)
        _, erro = proc.communicate(timeout=1800)
    except Exception:
        proc.kill()
        destino.unlink(missing_ok=True)
        raise
    if proc.returncode != 0 or tamanho == 0:
        destino.unlink(missing_ok=True)
        detalhe = (erro or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or ["sem saída"]
        raise ErroBackup(f"O dump falhou (código {proc.returncode}): {detalhe[0][:200]}")
    # conferência: decifra tudo e confere a assinatura do formato custom do pg_dump
    claro = io.BytesIO()
    try:
        with open(destino, "rb") as src:
            cripto.decrypt_stream(src, claro, chave)
    except (SystemExit, Exception) as exc:
        destino.unlink(missing_ok=True)
        raise ErroBackup(f"O arquivo gerado não passou na conferência ({type(exc).__name__}).")
    if not claro.getvalue().startswith(b"PGDMP"):
        destino.unlink(missing_ok=True)
        raise ErroBackup("O conteúdo gerado não é um dump do PostgreSQL.")
    return {"arquivo": destino.name, "tamanho_dump": tamanho, "tamanho_cifrado": destino.stat().st_size,
            "segundos": round(time.monotonic() - inicio, 1)}


def aplicar_retencao(manter: int) -> int:
    automaticos = [b for b in listar() if b["motivo"] == "automatico"]
    apagados = 0
    for b in automaticos[manter:]:
        (pasta() / b["arquivo"]).unlink(missing_ok=True)
        apagados += 1
    return apagados


async def fazer_backup(motivo: str = "manual") -> dict:
    if not re.fullmatch(r"[a-z0-9-]{1,30}", motivo):
        raise ErroBackup("Motivo inválido.")
    if _TRAVA.locked():
        raise ErroBackup("Já existe um backup em andamento.")
    async with _TRAVA:
        ESTADO["em_andamento"] = True
        try:
            r = await asyncio.to_thread(_executar, motivo)
            ESTADO.update(ultimo_ok={**r, "em": datetime.now().isoformat()}, ultimo_erro=None, ultimo_erro_em=None)
            cfg = (await configuracoes.ler_plataforma())["backup"]
            r["apagados_pela_retencao"] = await asyncio.to_thread(aplicar_retencao, cfg["manter"])
            logger.warning("Backup %s concluído (%s bytes)", r["arquivo"], r["tamanho_cifrado"])
            return r
        except ErroBackup as exc:
            ESTADO.update(ultimo_erro=str(exc), ultimo_erro_em=datetime.now().isoformat())
            logger.error("Backup falhou: %s", exc)
            await _avisar_falha(str(exc))
            raise
        finally:
            ESTADO["em_andamento"] = False


async def _avisar_falha(motivo: str) -> None:
    from sqlalchemy import select
    from backend.app import notificacoes
    from backend.app.database import PlatformSessionLocal
    from backend.app.db_models import User
    from backend.app.roles import UserRole
    async with PlatformSessionLocal() as db:
        ids = [u.id for u in (await db.execute(select(User).where(User.role == UserRole.ADMIN_GERAL.value,
                                                                   User.is_active.is_(True)))).scalars()]
    await notificacoes.notificar_varios(ids, "sistema", "Backup do banco falhou",
                                        f"O backup automático não foi feito: {motivo}\nVeja em Configurações > Saúde e backups.",
                                        "/settings")


def ja_fez_hoje() -> bool:
    hoje = datetime.now().strftime("%Y-%m-%d")
    return any(b["motivo"] == "automatico" and b["criado_em"].startswith(hoje) for b in listar())


async def laco_agendado(intervalo: int = 60) -> None:
    """Uma vez por dia, na hora configurada (desligável com DIAGPRO_BACKUP_AGENDADO=0)."""
    while True:
        try:
            cfg = (await configuracoes.ler_plataforma())["backup"]
            if cfg["automatico"] and datetime.now().hour == cfg["hora"] and not ja_fez_hoje() and not ESTADO["em_andamento"]:
                await fazer_backup("automatico")
        except ErroBackup:
            pass  # já registrado e avisado
        except Exception as exc:
            logger.error("Agendador de backup: %s", type(exc).__name__)
        await asyncio.sleep(intervalo)


def agendador_ligado() -> bool:
    return os.getenv("DIAGPRO_BACKUP_AGENDADO", "1") != "0"
