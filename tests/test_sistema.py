"""Backups (dump falso, nunca o banco real), retenção, painel de saúde e modo manutenção."""
import base64
import importlib.util
import io
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import select, text

from backend.app import backups
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Notificacao
from backend.app.rate_limit import reset_rate_limits
from backend.app.roles import UserRole
from tests.conftest import auth_headers

_RAIZ = Path(__file__).resolve().parents[1]


def _cripto():
    spec = importlib.util.spec_from_file_location("bc_teste", _RAIZ / "scripts" / "backup_crypto.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ambiente_backup(tmp_path, monkeypatch):
    chave = tmp_path / "backup.key"
    chave.write_text(base64.b64encode(os.urandom(32)).decode())
    pasta = tmp_path / "backups"
    monkeypatch.setenv("DIAGPRO_BACKUP_KEY_FILE", str(chave))
    monkeypatch.setenv("DIAGPRO_BACKUP_DIR", str(pasta))
    # "dump" sintético: nunca toca no banco real
    monkeypatch.setenv("DIAGPRO_BACKUP_CMD", f'{sys.executable} -c "import sys; sys.stdout.buffer.write(b\'PGDMP\' + b\'SINTETICO\' * 2000)"')
    backups.ESTADO.update(ultimo_ok=None, ultimo_erro=None, ultimo_erro_em=None, em_andamento=False)
    return pasta


@pytest.mark.asyncio
async def test_backup_retention_health_and_maintenance(async_client, ambiente_backup, monkeypatch):
    reset_rate_limits()
    ag = auth_headers("Victor Hugo", UserRole.ADMIN_GERAL)
    a1 = auth_headers("admin1", UserRole.ADMIN, tenant_id=1)
    hp = auth_headers("vhugo", UserRole.PROFESSOR, tenant_id=1)
    try:
        # 1) backup manual: cifrado no disco, conferido, listado; só o admin geral
        assert (await async_client.post("/admin/sistema/backups", headers=a1)).status_code == 403
        r = await async_client.post("/admin/sistema/backups", headers=ag)
        assert r.status_code == 200, r.text
        arq = ambiente_backup / r.json()["arquivo"]
        bruto = arq.read_bytes()
        assert b"PGDMP" not in bruto and b"SINTETICO" not in bruto  # nada em claro
        claro = io.BytesIO()
        with open(arq, "rb") as f:
            _cripto().decrypt_stream(f, claro, base64.b64decode((ambiente_backup.parent / "backup.key").read_text()))
        assert claro.getvalue().startswith(b"PGDMPSINTETICO")
        lista = (await async_client.get("/admin/sistema/backups", headers=ag)).json()
        assert lista["itens"][0]["arquivo"] == arq.name and lista["itens"][0]["motivo"] == "manual"

        # 2) dump que não é do PostgreSQL: recusado, arquivo apagado, admin geral avisado
        monkeypatch.setenv("DIAGPRO_BACKUP_CMD", f'{sys.executable} -c "print(123)"')
        reset_rate_limits()
        r = await async_client.post("/admin/sistema/backups", headers=ag)
        assert r.status_code == 500 and "não é um dump" in r.json()["detail"]
        assert len(list(ambiente_backup.iterdir())) == 1
        async with PlatformSessionLocal() as s:
            avisos = [(n.conteudo or {}).get("titulo") for n in (await s.execute(select(Notificacao))).scalars()]
        assert "Backup do banco falhou" in avisos

        # 3) retenção: guarda os N automáticos mais novos; manuais ficam
        for i in range(5):
            (ambiente_backup / f"pg_diagpro_2026010{i + 1}-020000_automatico.dump.enc").write_bytes(b"x")
        assert backups.aplicar_retencao(3) == 2
        nomes = sorted(p.name for p in ambiente_backup.iterdir())
        assert "pg_diagpro_20260101-020000_automatico.dump.enc" not in nomes and arq.name in nomes and len(nomes) == 4

        # 4) painel de saúde: RLS forçado e migração em dia; só admin geral
        assert (await async_client.get("/admin/sistema/saude", headers=a1)).status_code == 403
        painel = (await async_client.get("/admin/sistema/saude", headers=ag)).json()
        itens = {i["item"]: i for i in painel["itens"]}
        assert itens["Isolamento entre bancas (RLS)"]["estado"] == "ok", itens["Isolamento entre bancas (RLS)"]
        assert itens["Migrações do banco"]["estado"] == "ok", itens["Migrações do banco"]
        assert itens["Falha recente de backup"]["estado"] == "erro"

        # 5) validação das configurações novas
        assert (await async_client.put("/config/plataforma", headers=ag, json={"backup": {"hora": 25}})).status_code == 400
        assert (await async_client.put("/config/plataforma", headers=ag, json={"manutencao": {"mensagem": ""}})).status_code == 400

        # 6) modo manutenção: todos recebem 503 com a mensagem, menos o admin geral; login continua aberto
        r = await async_client.put("/config/plataforma", headers=ag, json={"manutencao": {"ativa": True, "mensagem": "Volta às 14h."}})
        assert r.status_code == 200
        r = await async_client.get("/users/me", headers=hp)
        assert r.status_code == 503 and r.json() == {"detail": "Volta às 14h.", "manutencao": True}
        assert (await async_client.get("/users/me", headers=a1)).status_code == 503
        assert (await async_client.get("/users/me", headers=ag)).status_code == 200
        assert (await async_client.get("/status/manutencao")).json() == {"ativa": True, "mensagem": "Volta às 14h."}
        assert (await async_client.get("/auth/senha/regras")).status_code == 200
        assert (await async_client.put("/config/plataforma", headers=ag, json={"manutencao": {"ativa": False}})).status_code == 200
        assert (await async_client.get("/users/me", headers=hp)).status_code == 200
        assert (await async_client.get("/status/manutencao")).json()["ativa"] is False
    finally:
        await async_client.put("/config/plataforma", headers=ag, json={"manutencao": {"ativa": False, "mensagem": "O DiagPro está em manutenção. Volte em alguns minutos."}})
        async with PlatformSessionLocal() as s:
            await s.execute(text("DELETE FROM notificacoes"))
            await s.commit()
        backups.ESTADO.update(ultimo_ok=None, ultimo_erro=None, ultimo_erro_em=None, em_andamento=False)
        reset_rate_limits()
