# backend/app/fluxo_revisao.py
"""
Fluxo de revisão das questões:

    RASCUNHO --enviar--> ENVIADA --revisor--> APROVADA
                             |                   |
                             +--> AJUSTES / REPROVADA --(professor corrige e envia de novo)--> ENVIADA
    APROVADA --(alguém altera a questão)--> RASCUNHO (precisa de nova revisão)

Cada passo vira uma linha em HistoricoRevisaoQuestao (quem, quando, status, observação) e gera aviso
(sino/e-mail) para quem precisa agir. Os avisos levam só o código curto da questão, nunca o conteúdo.
"""
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import notificacoes
from backend.app.db_models import Conteudo, HistoricoRevisaoQuestao, QuestoesBanco, User
from backend.app.roles import UserRole

RASCUNHO, ENVIADA, AJUSTES, REPROVADA, APROVADA = "RASCUNHO", "ENVIADA", "AJUSTES", "REPROVADA", "APROVADA"
DECISOES_DO_REVISOR = (APROVADA, AJUSTES, REPROVADA)
PODE_ENVIAR_DE = (None, "", RASCUNHO, AJUSTES, REPROVADA)
ROTULOS = {RASCUNHO: "Em elaboração", ENVIADA: "Aguardando revisão", AJUSTES: "Devolvida com ajustes",
           REPROVADA: "Reprovada", APROVADA: "Aprovada"}


def status_de(q: QuestoesBanco) -> str:
    return (q.status_revisao or RASCUNHO).upper()


def registrar(db: AsyncSession, q: QuestoesBanco, usuario: str, status: str, observacao: str | None = None) -> None:
    db.add(HistoricoRevisaoQuestao(
        id=str(uuid4()), id_questao_fk=q.id_questao, usuario_revisor=usuario, data_revisao=datetime.now(),
        status_revisao=status, observacao_revisor=observacao, tenant_id=q.tenant_id,
    ))


async def conteudo_da_questao(db: AsyncSession, q: QuestoesBanco) -> Conteudo | None:
    if not q.conteudo_id:
        return None
    return (await db.execute(select(Conteudo).where(Conteudo.id_conteudo == q.conteudo_id))).scalar_one_or_none()


async def autor_id(db: AsyncSession, q: QuestoesBanco) -> int | None:
    """Quem elaborou: criador_id (questões novas) ou o professor do conteúdo (questões antigas)."""
    conteudo = await conteudo_da_questao(db, q)
    for candidato in (q.criador_id, conteudo.professor_id if conteudo else None):
        try:
            if candidato:
                return int(candidato)
        except (TypeError, ValueError):
            continue
    return None


async def revisores_da_banca(db: AsyncSession, tenant_id: int) -> list[int]:
    """Revisores ativos da banca; se não houver, os administradores (alguém precisa receber)."""
    from backend.app import vinculos  # quem é da banca ou tem vínculo ativo com ela (revisores atendem várias)
    usuarios = await vinculos.usuarios_da_banca(db, tenant_id)
    revisores = [u.id for u, role in usuarios if role == UserRole.REVISOR.value]
    return revisores or [u.id for u, role in usuarios if role == UserRole.ADMIN.value]


def _role(user) -> str:
    return user.role.value if isinstance(user.role, UserRole) else str(user.role)


async def enviar_para_revisao(db: AsyncSession, q: QuestoesBanco, user, mensagem: str = "") -> None:
    if _role(user) == UserRole.PROFESSOR.value:
        conteudo = await conteudo_da_questao(db, q)
        donos = {str(q.criador_id or ""), str((conteudo.professor_id if conteudo else "") or "")}
        if str(user.id) not in donos:
            raise HTTPException(status_code=403, detail="Só quem elabora a questão pode enviá-la para revisão.")
    atual = status_de(q)
    if atual == ENVIADA:
        raise HTTPException(status_code=409, detail="A questão já está na fila de revisão.")
    if atual == APROVADA:
        raise HTTPException(status_code=409, detail="A questão já está aprovada.")
    if atual not in PODE_ENVIAR_DE:
        raise HTTPException(status_code=409, detail="A questão não pode ser enviada neste estado.")
    q.status_revisao = ENVIADA
    q.revisada = False
    registrar(db, q, user.username, ENVIADA, (mensagem or "").strip()[:2000] or None)
    await db.commit()
    await notificacoes.notificar_varios(
        await revisores_da_banca(db, q.tenant_id), "revisao_recebida",
        f"Questão {q.codigo_curto_questao or ''} aguardando revisão".strip(),
        f"{user.username} enviou a questão {q.codigo_curto_questao or ''} para revisão.",
        "/revisao", tenant_id=q.tenant_id)


async def decisao_do_revisor(db: AsyncSession, q: QuestoesBanco, status: str, revisor_nome: str) -> None:
    """Chamado depois de salvar a revisão: avisa quem elaborou."""
    autor = await autor_id(db, q)
    if not autor:
        return
    link = f"/eventos/{q.id_evento_fk}/conteudo/{q.conteudo_id}/questao/{q.id_questao}/editar"
    codigo = q.codigo_curto_questao or ""
    if status == APROVADA:
        await notificacoes.notificar(autor, "revisao_aprovada", f"Questão {codigo} aprovada",
                                     f"{revisor_nome} aprovou a questão {codigo}.", link, tenant_id=q.tenant_id)
    elif status in (AJUSTES, REPROVADA):
        acao = "pediu ajustes na" if status == AJUSTES else "reprovou a"
        await notificacoes.notificar(autor, "revisao_devolvida", f"Questão {codigo} voltou da revisão",
                                     f"{revisor_nome} {acao} questão {codigo}. Veja as observações na tela da questão, "
                                     "corrija e envie de novo para revisão.", link, tenant_id=q.tenant_id)


def reabrir_se_aprovada(db: AsyncSession, q: QuestoesBanco, usuario: str) -> bool:
    """Questão aprovada que é alterada volta para elaboração: precisa de nova revisão."""
    if status_de(q) != APROVADA:
        return False
    q.status_revisao = RASCUNHO
    q.revisada = False
    registrar(db, q, usuario, RASCUNHO, "Questão alterada depois de aprovada: precisa de nova revisão.")
    return True
