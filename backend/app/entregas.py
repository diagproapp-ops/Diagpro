# backend/app/entregas.py
"""
Entrega segura de pacotes de prova (ex.: para a gráfica), em vez de mandar o arquivo por e-mail/WhatsApp.

- O ZIP é o mesmo da exportação: já protegido pela senha do evento. Aqui ele fica guardado cifrado por banca.
- O link (id aleatório de 128 bits) sozinho não baixa nada: é preciso o código de acesso (12 caracteres),
  mostrado uma única vez para quem criou e guardado só como hash bcrypt. Mande link e código por canais diferentes.
- Vale até a data/hora escolhida (1 a 72 h) e por N downloads (1 a 5). Cinco códigos errados bloqueiam o link.
- Revogável a qualquer momento. Encerrada, o arquivo é apagado na hora.
- Cada download registra data e IP e avisa quem criou (sino/e-mail).
"""
import asyncio
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from backend.app import notificacoes, secure_files
from backend.app.auth import get_password_hash, verify_password
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Entrega

logger = logging.getLogger("entregas")
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I para ditar por telefone
MAX_FALHAS = 5


def novo_codigo() -> str:
    c = "".join(secrets.choice(_ALFABETO) for _ in range(12))
    return f"{c[:4]}-{c[4:8]}-{c[8:]}"


def _normalizar(codigo: str) -> str:
    c = "".join(ch for ch in (codigo or "").upper() if ch.isalnum())
    return f"{c[:4]}-{c[4:8]}-{c[8:]}" if len(c) == 12 else c


def criar(db, tenant_id: int, evento_id: str, criado_por: int, zip_bytes: bytes, nome_arquivo: str,
          horas: int, max_downloads: int, destinatario: str, cargos: list[str]) -> tuple[Entrega, str]:
    codigo = novo_codigo()
    ref = secure_files.store_bytes(zip_bytes, tenant_id, "zip", validate=False)
    agora = datetime.utcnow()
    e = Entrega(id=secrets.token_hex(16), tenant_id=tenant_id, evento_id=evento_id, criado_por=criado_por, criado_em=agora,
                expira_em=agora + timedelta(hours=horas), max_downloads=max_downloads, downloads=0, falhas_codigo=0,
                codigo_hash=get_password_hash(codigo), arquivo=ref,
                detalhes={"nome_arquivo": nome_arquivo, "destinatario": destinatario[:120], "cargos": cargos[:50],
                          "tamanho": len(zip_bytes), "log": []})
    db.add(e)
    return e, codigo


def situacao(e: Entrega) -> str:
    if e.encerrada_em:
        return e.motivo_encerramento or "encerrada"
    if datetime.utcnow() >= e.expira_em:
        return "vencida"
    if e.downloads >= e.max_downloads:
        return "esgotada"
    return "ativa"


def encerrar(e: Entrega, motivo: str) -> None:
    secure_files.delete(e.arquivo)
    e.arquivo = None
    e.encerrada_em = e.encerrada_em or datetime.utcnow()
    e.motivo_encerramento = e.motivo_encerramento or motivo


def publico(e: Entrega) -> dict:
    d = e.detalhes or {}
    return {"id": e.id, "situacao": situacao(e), "nome_arquivo": d.get("nome_arquivo"), "destinatario": d.get("destinatario"),
            "cargos": d.get("cargos", []), "tamanho": d.get("tamanho"), "criado_em": e.criado_em.isoformat() + "Z",
            "expira_em": e.expira_em.isoformat() + "Z", "downloads": e.downloads, "max_downloads": e.max_downloads,
            "log": d.get("log", [])}


class ErroEntrega(Exception):
    def __init__(self, mensagem: str, status: int = 400):
        super().__init__(mensagem)
        self.mensagem, self.status = mensagem, status


async def baixar(entrega_id: str, codigo: str, ip: str) -> tuple[bytes, str]:
    """Download público (sem login): confere situação e código, conta o download e avisa quem criou."""
    async with PlatformSessionLocal() as db:
        e = (await db.execute(select(Entrega).where(Entrega.id == entrega_id).with_for_update())).scalar_one_or_none()
        if e is None:
            raise ErroEntrega("Link inválido.", 404)
        sit = situacao(e)
        if sit != "ativa":
            if e.arquivo:
                encerrar(e, sit)
                await db.commit()
            raise ErroEntrega({"vencida": "Este link venceu.", "esgotada": "Este link já foi usado o número máximo de vezes."}
                              .get(sit, "Este link não está mais disponível."), 410)
        if not verify_password(_normalizar(codigo), e.codigo_hash):
            e.falhas_codigo += 1
            if e.falhas_codigo >= MAX_FALHAS:
                encerrar(e, "bloqueada")
            await db.commit()
            logger.warning("Código errado na entrega %s (%s falhas)", e.id, e.falhas_codigo)
            raise ErroEntrega("Código de acesso incorreto." + (" O link foi bloqueado." if e.falhas_codigo >= MAX_FALHAS else ""), 403)
        dados = secure_files.read_bytes(e.arquivo, e.tenant_id)
        e.downloads += 1
        det = dict(e.detalhes or {})
        det["log"] = (det.get("log") or []) + [{"em": datetime.utcnow().isoformat() + "Z", "ip": ip}]
        e.detalhes = det
        nome = det.get("nome_arquivo") or "pacote.zip"
        if e.downloads >= e.max_downloads:
            encerrar(e, "esgotada")
        criador, restantes = e.criado_por, e.max_downloads - e.downloads
        await db.commit()
    if criador:
        await notificacoes.notificar(criador, "sistema", "Pacote de prova baixado",
                                     f"O pacote {nome} foi baixado pelo link de entrega (IP {ip or 'desconhecido'}). "
                                     f"Downloads restantes: {max(0, restantes)}.", "/dashboard")
    return dados, nome


async def limpar_vencidas() -> int:
    agora = datetime.utcnow()
    n = 0
    async with PlatformSessionLocal() as db:
        for e in (await db.execute(select(Entrega).where(Entrega.arquivo.is_not(None)))).scalars():
            sit = situacao(e)
            if sit != "ativa" or e.expira_em <= agora:
                encerrar(e, sit)
                n += 1
        await db.commit()
    return n


async def laco_limpeza(intervalo: int = 600) -> None:
    while True:
        try:
            n = await limpar_vencidas()
            if n:
                logger.warning("Entregas encerradas por validade/limite: %s", n)
        except Exception as exc:
            logger.error("Limpeza de entregas: %s", type(exc).__name__)
        await asyncio.sleep(intervalo)
