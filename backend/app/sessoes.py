# backend/app/sessoes.py
"""
Sessões de acesso: cada login concluído (depois do 2FA) vira uma linha; o token leva o id (`sid`).

- Encerrar uma sessão (pela própria pessoa, por um administrador, na troca de senha ou no reset do 2FA)
  derruba o token dela na próxima requisição, sem esperar ele vencer.
- Login de um navegador/aparelho que a pessoa não usou nos últimos 90 dias gera aviso de segurança
  (sino + e-mail, que não pode ser desligado).
- IP e navegador ficam cifrados; nada disso sai em logs.
"""
import ipaddress
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update

from backend.app import notificacoes
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Sessao

logger = logging.getLogger("sessoes")
_JANELA_CONHECIDO = timedelta(days=90)


def resumo_navegador(user_agent: str) -> tuple[str, str]:
    ua = (user_agent or "")[:400]
    if "Edg/" in ua:
        nav = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        nav = "Opera"
    elif "Firefox/" in ua:
        nav = "Firefox"
    elif "Chrome/" in ua:
        nav = "Chrome"
    elif "Safari/" in ua:
        nav = "Safari"
    else:
        nav = "Outro navegador"
    if "Windows" in ua:
        so = "Windows"
    elif "Android" in ua:
        so = "Android"
    elif "iPhone" in ua or "iPad" in ua:
        so = "iOS"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        so = "macOS"
    elif "Linux" in ua:
        so = "Linux"
    else:
        so = "Outro sistema"
    return nav, so


def _rede(ip: str) -> str:
    """Mesma rede = mesmo /24 (IPv4) ou /48 (IPv6): troca de IP dentro da mesma casa/empresa não alerta."""
    try:
        end = ipaddress.ip_address(ip)
        return str(ipaddress.ip_network(f"{ip}/{24 if end.version == 4 else 48}", strict=False))
    except ValueError:
        return ip or "?"


def _dados_da_requisicao(request) -> dict:
    ip = request.client.host if request is not None and request.client else ""
    nav, so = resumo_navegador(request.headers.get("user-agent", "") if request is not None else "")
    return {"ip": ip, "navegador": nav, "sistema": so}


async def abrir(user, request, alertar: bool = True) -> str:
    """Cria a sessão e, se o aparelho for novo para a pessoa, manda o aviso de segurança."""
    sid = secrets.token_hex(16)
    agora = datetime.utcnow()
    det = _dados_da_requisicao(request)
    async with PlatformSessionLocal() as db:
        anteriores = (await db.execute(select(Sessao).where(
            Sessao.usuario_id == user.id, Sessao.criada_em >= agora - _JANELA_CONHECIDO))).scalars().all()
        conhecido = any(
            (s.detalhes or {}).get("navegador") == det["navegador"] and (s.detalhes or {}).get("sistema") == det["sistema"]
            and _rede((s.detalhes or {}).get("ip", "")) == _rede(det["ip"])
            for s in anteriores
        )
        db.add(Sessao(id=sid, tenant_id=user.tenant_id, usuario_id=user.id, criada_em=agora, ultimo_uso_em=agora,
                      detalhes=det))
        await db.commit()
    if alertar and anteriores and not conhecido:
        quando = (agora - timedelta(hours=3)).strftime("%d/%m/%Y às %H:%M")  # horário de Brasília
        await notificacoes.notificar(
            user.id, "seguranca_novo_login", "Novo acesso à sua conta",
            f"Entraram na sua conta em {quando} por {det['navegador']} no {det['sistema']} (IP {det['ip'] or 'desconhecido'}).\n"
            "Se foi você, ignore este aviso. Se não foi, troque sua senha e encerre esse acesso em Minha conta.",
            "/minha-conta")
    return sid


async def valida(sid: str) -> bool:
    async with PlatformSessionLocal() as db:
        linha = (await db.execute(select(Sessao.encerrada_em).where(Sessao.id == sid))).first()
    return linha is not None and linha[0] is None


async def tocar(sid: str) -> None:
    async with PlatformSessionLocal() as db:
        await db.execute(update(Sessao).where(Sessao.id == sid, Sessao.encerrada_em.is_(None)).values(ultimo_uso_em=datetime.utcnow()))
        await db.commit()


async def encerrar(sid: str, usuario_id: int, motivo: str) -> bool:
    """Encerra UMA sessão, só se for da pessoa informada."""
    async with PlatformSessionLocal() as db:
        r = await db.execute(update(Sessao).where(
            Sessao.id == sid, Sessao.usuario_id == usuario_id, Sessao.encerrada_em.is_(None)
        ).values(encerrada_em=datetime.utcnow(), motivo_encerramento=motivo))
        await db.commit()
    return r.rowcount > 0


async def encerrar_do_usuario(usuario_id: int, motivo: str, exceto: str | None = None) -> int:
    async with PlatformSessionLocal() as db:
        q = update(Sessao).where(Sessao.usuario_id == usuario_id, Sessao.encerrada_em.is_(None))
        if exceto:
            q = q.where(Sessao.id != exceto)
        r = await db.execute(q.values(encerrada_em=datetime.utcnow(), motivo_encerramento=motivo))
        await db.commit()
    if r.rowcount:
        logger.warning("%s sessão(ões) do usuário %s encerrada(s): %s", r.rowcount, usuario_id, motivo)
    return r.rowcount


async def ativas_do_usuario(usuario_id: int, max_horas: int) -> list[Sessao]:
    limite = datetime.utcnow() - timedelta(hours=max_horas)
    async with PlatformSessionLocal() as db:
        return (await db.execute(select(Sessao).where(
            Sessao.usuario_id == usuario_id, Sessao.encerrada_em.is_(None), Sessao.criada_em >= limite
        ).order_by(Sessao.ultimo_uso_em.desc()))).scalars().all()
