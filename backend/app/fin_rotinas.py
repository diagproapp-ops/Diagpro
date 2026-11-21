"""
Rotinas automáticas do financeiro (rodam junto com a API, a cada poucas horas; cada aviso sai uma vez por dia no máximo):
 - fatura vencendo (N dias antes) e em atraso (repete a cada N dias) — avisa a banca; atraso avisa também a plataforma;
 - suspensão opcional: N dias após o vencimento, a banca é bloqueada e os acessos caem (configurável; 0 = nunca);
 - contrato não aceito: lembra o professor a cada N dias; depois de 7 dias avisa a banca uma vez;
 - parcelas cujo gatilho se cumpriu são liberadas (e avisadas) mesmo sem ninguém abrir a tela.
O que já foi avisado fica guardado no `dados` cifrado de cada linha (sem tabela nova).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

from sqlalchemy import select

from backend.app import configuracoes, notificacoes
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import FinContrato, FinFatura, Tenant, User
from backend.app.fin_calculo import contrato_completo, moeda, num

logger = logging.getLogger(__name__)


def _ja_avisou(dados: dict, chave: str, hoje: date, cada_dias: int | None = None) -> bool:
    ultimo = (dados.get("lembretes") or {}).get(chave)
    if not ultimo:
        return False
    if cada_dias is None:
        return True
    return (hoje - date.fromisoformat(ultimo)).days < cada_dias


def _marcar(obj, chave: str, hoje: date) -> None:
    d = dict(obj.dados or {})
    d["lembretes"] = {**(d.get("lembretes") or {}), chave: hoje.isoformat()}
    obj.dados = d


async def _admins(db, tenant_id: int) -> list[int]:
    return [u.id for u in (await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == "administrador",
                                                               User.is_active.is_(True)))).scalars()]


async def _admins_gerais(db) -> list[int]:
    return [u.id for u in (await db.execute(select(User).where(User.tenant_id.is_(None), User.role == "administrador geral",
                                                               User.is_active.is_(True)))).scalars()]


async def executar(hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    cfg = (await configuracoes.ler_plataforma())["financeiro"]
    r = {"vencendo": 0, "atraso": 0, "suspensas": 0, "aceite": 0, "liberadas": 0}
    async with PlatformSessionLocal() as db:
        # ---------------------------------------------------------------- faturas da plataforma
        for f in (await db.execute(select(FinFatura).where(FinFatura.status == "aberta"))).scalars().all():
            d = f.dados or {}
            dias = (f.vencimento - hoje).days
            valor = moeda(num(d.get("valor")))
            if 0 <= dias <= cfg["lembrete_fatura_dias"] and not _ja_avisou(d, "vencendo", hoje):
                await notificacoes.notificar_varios(await _admins(db, f.tenant_id), "sistema", f"Fatura {f.numero} vence em {dias} dia(s)",
                                                    f"{valor} com vencimento em {f.vencimento.strftime('%d/%m/%Y')}.", "/financeiro",
                                                    tenant_id=f.tenant_id)
                _marcar(f, "vencendo", hoje)
                r["vencendo"] += 1
            if dias < 0:
                atraso = -dias
                if not _ja_avisou(d, "atraso", hoje, cfg["aviso_atraso_cada_dias"]):
                    await notificacoes.notificar_varios(await _admins(db, f.tenant_id), "sistema", f"Fatura {f.numero} em atraso",
                                                        f"{valor} venceu há {atraso} dia(s). Envie o comprovante em Financeiro > Minha conta na plataforma.",
                                                        "/financeiro", tenant_id=f.tenant_id)
                    t = (await db.execute(select(Tenant).where(Tenant.id == f.tenant_id))).scalars().first()
                    await notificacoes.notificar_varios(await _admins_gerais(db), "sistema", f"Fatura {f.numero} em atraso",
                                                        f"{t.name if t else 'Banca'}: {valor}, {atraso} dia(s) de atraso.", "/financeiro")
                    _marcar(f, "atraso", hoje)
                    r["atraso"] += 1
                limite = cfg["suspender_apos_dias"]
                if limite and atraso >= limite and not _ja_avisou(f.dados or {}, "suspensao", hoje):
                    t = (await db.execute(select(Tenant).where(Tenant.id == f.tenant_id))).scalars().first()
                    if t and t.status == "ativo":
                        from backend.app.admin_clients import _derrubar_acessos
                        await notificacoes.notificar_varios(await _admins(db, f.tenant_id), "sistema", "Acesso suspenso por atraso",
                                                            f"A fatura {f.numero} está {atraso} dias em atraso. Fale com a plataforma.",
                                                            "/financeiro", tenant_id=f.tenant_id)
                        t.status = "bloqueado"
                        _marcar(f, "suspensao", hoje)
                        await db.commit()
                        await _derrubar_acessos(f.tenant_id, "inadimplencia")
                        await notificacoes.notificar_varios(await _admins_gerais(db), "sistema", f"{t.name} suspensa por atraso",
                                                            f"Fatura {f.numero}: {atraso} dias de atraso.", "/financeiro")
                        r["suspensas"] += 1
        await db.commit()

        # ---------------------------------------------------------------- contratos dos professores
        for c in (await db.execute(select(FinContrato).where(FinContrato.status == "enviado"))).scalars().all():
            if not c.enviado_em:
                continue
            dias = (hoje - c.enviado_em.date()).days
            d = c.dados or {}
            if dias >= cfg["lembrete_aceite_dias"] and not _ja_avisou(d, "aceite", hoje, cfg["lembrete_aceite_dias"]):
                await notificacoes.notificar(c.professor_id, "sistema", f"Contrato {c.numero} aguardando o seu aceite",
                                             "Leia e aceite o contrato em Financeiro para que as parcelas possam ser liberadas.",
                                             "/financeiro", tenant_id=c.tenant_id)
                _marcar(c, "aceite", hoje)
                r["aceite"] += 1
            if dias >= 7 and not _ja_avisou(c.dados or {}, "aceite_banca", hoje):
                await notificacoes.notificar_varios(await _admins(db, c.tenant_id), "sistema", f"Contrato {c.numero} sem aceite",
                                                    f"Enviado há {dias} dias e ainda não aceito pelo professor.", "/financeiro",
                                                    tenant_id=c.tenant_id)
                _marcar(c, "aceite_banca", hoje)
        await db.commit()

        for c in (await db.execute(select(FinContrato).where(FinContrato.status == "aceito"))).scalars().all():
            antes = sum(1 for p in (await contrato_completo(db, c, persistir=False))["parcelas"] if p["status"] != "prevista")
            depois = sum(1 for p in (await contrato_completo(db, c))["parcelas"] if p["status"] != "prevista")
            r["liberadas"] += max(0, depois - antes)
    return r


async def laco(intervalo: int = 3 * 3600) -> None:
    await asyncio.sleep(60)  # deixa a API subir primeiro
    while True:
        try:
            r = await executar()
            if any(r.values()):
                logger.warning("Rotinas do financeiro: %s", r)
        except Exception as exc:  # o laço nunca morre por uma falha pontual
            logger.error("Rotinas do financeiro: %s", type(exc).__name__)
        await asyncio.sleep(intervalo)
