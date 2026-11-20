# backend/app/saude.py
"""
Painel de saúde (admin geral): conferências rápidas do que mantém o DiagPro seguro e no ar.
Cada item: {"item", "estado": ok|aviso|erro, "detalhe"}. Nenhum dado de banca aparece aqui.
"""
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text

from backend.app import backups, configuracoes
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Notificacao

_INICIO = time.time()
_RAIZ = Path(__file__).resolve().parents[2]


def _item(nome, estado, detalhe):
    return {"item": nome, "estado": estado, "detalhe": detalhe}


def _gb(n: int) -> str:
    return f"{n / 1024 ** 3:.1f} GB"


async def conferir() -> dict:
    itens = []
    # banco: conexão, latência, TLS, tamanho, migração e RLS
    try:
        t0 = time.monotonic()
        async with PlatformSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            ms = (time.monotonic() - t0) * 1000
            itens.append(_item("Banco de dados", "ok" if ms < 500 else "aviso", f"Respondendo em {ms:.0f} ms"))
            ssl = (await db.execute(text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()"))).scalar()
            itens.append(_item("Conexão cifrada (TLS) com o banco", "ok" if ssl else "erro",
                               "Ativa" if ssl else "Sem TLS: a conexão com o banco não está cifrada"))
            tamanho = (await db.execute(text("SELECT pg_database_size(current_database())"))).scalar()
            itens.append(_item("Tamanho do banco", "ok", f"{tamanho / 1024 ** 2:.1f} MB"))
            versao = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            cabeca = _cabeca_alembic()
            itens.append(_item("Migrações do banco", "ok" if versao == cabeca else "erro",
                               f"Em dia ({versao})" if versao == cabeca else f"Banco em {versao}, código espera {cabeca}"))
            sem_rls = (await db.execute(text(
                "SELECT c.relname FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' "
                "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'r' "
                "AND NOT (c.relrowsecurity AND c.relforcerowsecurity)"))).scalars().all()
            itens.append(_item("Isolamento entre bancas (RLS)", "ok" if not sem_rls else "erro",
                               "Forçado em todas as tabelas com banca" if not sem_rls else "Sem RLS forçado: " + ", ".join(sem_rls)))
            pend = (await db.execute(select(func.count(Notificacao.id)).where(Notificacao.email_estado == "pendente"))).scalar_one()
            falhas = (await db.execute(select(func.count(Notificacao.id)).where(
                Notificacao.email_estado == "falhou", Notificacao.criado_em >= datetime.utcnow() - timedelta(days=7)))).scalar_one()
            itens.append(_item("Fila de e-mails", "ok" if pend < 50 and not falhas else "aviso",
                               f"{pend} pendente(s), {falhas} com falha nos últimos 7 dias"))
    except Exception as exc:
        itens.append(_item("Banco de dados", "erro", f"Sem conexão ({type(exc).__name__})"))

    plataforma = await configuracoes.ler_plataforma()
    # backups
    lista = backups.listar()
    if not lista:
        itens.append(_item("Último backup", "erro", "Nenhum backup encontrado"))
    else:
        ultimo = datetime.fromisoformat(lista[0]["criado_em"])
        horas = (datetime.now() - ultimo).total_seconds() / 3600
        itens.append(_item("Último backup", "ok" if horas <= 26 else ("aviso" if horas <= 72 else "erro"),
                           f"{ultimo:%d/%m/%Y %H:%M} ({lista[0]['motivo']}), há {horas:.0f} h"))
    if backups.ESTADO["ultimo_erro"]:
        itens.append(_item("Falha recente de backup", "erro", backups.ESTADO["ultimo_erro"]))
    itens.append(_item("Backup automático", "ok" if plataforma["backup"]["automatico"] else "aviso",
                       f"Todo dia às {plataforma['backup']['hora']:02d}h, guarda {plataforma['backup']['manter']}"
                       if plataforma["backup"]["automatico"] else "Desligado"))
    # chaves e disco
    mestra = Path(os.getenv("DIAGPRO_MASTER_KEY_FILE") or Path(os.getenv("LOCALAPPDATA") or Path.home()) / "DiagPro" / "secrets" / "master.key")
    itens.append(_item("Chave mestra de cifra", "ok" if mestra.exists() else "erro",
                       "Presente fora do projeto" if mestra.exists() else "Arquivo da chave mestra não encontrado"))
    chave_bk = Path(os.getenv("DIAGPRO_BACKUP_KEY_FILE") or Path(os.getenv("LOCALAPPDATA") or Path.home()) / "DiagPro" / "secrets" / "backup.key")
    itens.append(_item("Chave dos backups", "ok" if chave_bk.exists() else "erro",
                       "Presente (guarde uma cópia offline)" if chave_bk.exists() else "Sem chave: backups não podem ser feitos"))
    for nome, caminho in (("Disco dos backups", backups.pasta()),):
        livre = shutil.disk_usage(caminho).free
        itens.append(_item(nome, "ok" if livre > 5 * 1024 ** 3 else ("aviso" if livre > 1024 ** 3 else "erro"), f"{_gb(livre)} livres"))
    # serviços
    soffice = shutil.which("soffice") or any(Path(p).exists() for p in (
        r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"))
    itens.append(_item("LibreOffice (PDF das provas)", "ok" if soffice else "aviso",
                       "Encontrado" if soffice else "Não encontrado: provas saem só em DOCX"))
    em = plataforma["email"]
    itens.append(_item("E-mail de avisos", "ok" if em["habilitado"] else "aviso",
                       f"Ligado ({em['host']})" if em["habilitado"] else "Desligado: avisos só no sino"))
    ia = plataforma["ia"]
    itens.append(_item("Assistente de IA", "ok", f"Ligado ({ia['provedor']})" if ia["habilitada"] else "Desligado"))
    man = plataforma["manutencao"]
    itens.append(_item("Modo manutenção", "aviso" if man["ativa"] else "ok", "ATIVO: só o admin geral entra" if man["ativa"] else "Desligado"))
    horas_no_ar = (time.time() - _INICIO) / 3600
    itens.append(_item("API no ar", "ok", f"Há {horas_no_ar:.1f} h"))

    pior = "erro" if any(i["estado"] == "erro" for i in itens) else ("aviso" if any(i["estado"] == "aviso" for i in itens) else "ok")
    return {"geral": pior, "conferido_em": datetime.now().isoformat(), "itens": itens}


def _cabeca_alembic() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(str(_RAIZ / "alembic.ini"))
        cfg.set_main_option("script_location", str(_RAIZ / "alembic"))
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception:
        return None
