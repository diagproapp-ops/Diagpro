# backend/app/lgpd.py
"""
LGPD: direitos do titular e prestação de contas.

- Acesso/portabilidade (art. 18, II e V): a pessoa baixa os próprios dados pessoais em JSON (sem segredos).
- Eliminação (art. 18, VI): o administrador anonimiza quem saiu; o conteúdo produzido (questões) é da banca e
  continua, ligado só ao id. Acessos e avisos (que têm IP/textos pessoais) são apagados.
- Termos e política com versão: mudou a versão, todos aceitam de novo; o aceite fica registrado.
- Retenção: avisos, acessos e registros de uso da IA antigos são apagados automaticamente.
- Tudo vira registro em `registros_lgpd` (cifrado, por banca).
"""
import asyncio
import json
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app import configuracoes, sessoes
from backend.app.auth import get_password_hash
from backend.app.database import PlatformSessionLocal
from backend.app.db_models import Notificacao, QuestoesBanco, RegistroLGPD, Sessao, UsoIA, User

logger = logging.getLogger("lgpd")

CAMPOS_PESSOAIS = ["full_name", "email", "cpf", "phone", "department", "institution", "birth_date", "address",
                   "specialty", "pix_key", "banco", "agencia", "conta_corrente"]
# apagados na anonimização (inclui segredos e observações)
CAMPOS_APAGAR = CAMPOS_PESSOAIS + ["notes", "avatar_url", "terms_acceptance", "totp_secret", "codigos_recuperacao",
                                   "senha_historico", "preferencias"]


def registrar(db: AsyncSession, tenant_id, titular_id, autor_id, acao: str, detalhes: dict | None = None) -> None:
    db.add(RegistroLGPD(tenant_id=tenant_id, titular_id=titular_id, autor_id=autor_id, acao=acao,
                        criado_em=datetime.utcnow(), detalhes=detalhes or {}))


def aceite_de(user: User) -> dict | None:
    try:
        dados = json.loads(user.terms_acceptance) if user.terms_acceptance else None
        return dados if isinstance(dados, dict) else None
    except (TypeError, ValueError):
        return None


async def exportar(db: AsyncSession, user: User) -> dict:
    """Dados pessoais do titular. Nunca: hash de senha, segredo do 2FA, códigos de recuperação."""
    perfil = {c: getattr(user, c, None) for c in ["username", *CAMPOS_PESSOAIS, "role", "status"]}
    acessos = (await db.execute(select(Sessao).where(Sessao.usuario_id == user.id).order_by(Sessao.criada_em.desc()))).scalars().all()
    avisos = (await db.execute(select(Notificacao).where(Notificacao.usuario_id == user.id).order_by(Notificacao.id.desc()))).scalars().all()
    usos = (await db.execute(select(UsoIA).where(UsoIA.usuario_id == user.id))).scalars().all()
    questoes = (await db.execute(select(QuestoesBanco.codigo_curto_questao).where(QuestoesBanco.criador_id == str(user.id)))).scalars().all()
    return {
        "gerado_em": datetime.utcnow().isoformat() + "Z",
        "titular": perfil,
        "aceite_dos_termos": aceite_de(user),
        "preferencias_de_aviso": (user.preferencias or {}) if isinstance(user.preferencias, dict) else {},
        "acessos": [{"inicio": s.criada_em.isoformat(), "ultimo_uso": s.ultimo_uso_em.isoformat(),
                     "encerrado_em": s.encerrada_em.isoformat() if s.encerrada_em else None, **(s.detalhes or {})} for s in acessos],
        "avisos": [{"em": n.criado_em.isoformat(), "tipo": n.tipo, "titulo": (n.conteudo or {}).get("titulo"),
                    "mensagem": (n.conteudo or {}).get("mensagem")} for n in avisos],
        "uso_do_assistente_de_ia": [{"em": u.criado_em.isoformat(), "recurso": (u.detalhes or {}).get("recurso"),
                                     "tokens": (u.tokens_entrada or 0) + (u.tokens_saida or 0)} for u in usos],
        "questoes_elaboradas": sorted(c for c in questoes if c),
        "observacao": ("Conteúdo de provas pertence à banca e não é dado pessoal; aqui aparecem só os códigos das questões "
                       "que você elaborou. Para corrigir ou eliminar dados, fale com o administrador da sua banca."),
    }


async def anonimizar(db: AsyncSession, user: User, autor_id: int) -> None:
    for campo in CAMPOS_APAGAR:
        setattr(user, campo, None)
    user.username = f"anonimizado-{user.id}"
    user.password_hash = get_password_hash(secrets.token_urlsafe(32))  # ninguém mais entra
    user.is_active = False
    user.status = "inativo"
    user.totp_ativo = False
    user.totp_ultimo_passo = None
    await db.execute(delete(Notificacao).where(Notificacao.usuario_id == user.id))
    registrar(db, user.tenant_id, user.id, autor_id, "anonimizacao", {"campos": CAMPOS_APAGAR})
    await db.commit()
    await sessoes.encerrar_do_usuario(user.id, "anonimizado")
    async with PlatformSessionLocal() as pdb:  # acessos guardam IP: some tudo
        await pdb.execute(delete(Sessao).where(Sessao.usuario_id == user.id))
        await pdb.commit()
    logger.warning("Usuário %s anonimizado por %s", user.id, autor_id)


async def limpar_por_retencao() -> dict:
    """Apaga o que passou do prazo (configurável na plataforma). Roda todo dia."""
    rd = (await configuracoes.ler_plataforma())["lgpd"]["retencao_dias"]
    agora = datetime.utcnow()
    async with PlatformSessionLocal() as db:
        n_av = (await db.execute(delete(Notificacao).where(
            Notificacao.criado_em < agora - timedelta(days=rd["notificacoes"]), Notificacao.email_estado != "pendente"))).rowcount
        n_se = (await db.execute(delete(Sessao).where(Sessao.criada_em < agora - timedelta(days=rd["sessoes"])))).rowcount
        n_ia = (await db.execute(delete(UsoIA).where(UsoIA.criado_em < agora - timedelta(days=rd["uso_ia"])))).rowcount
        resultado = {"avisos": n_av, "acessos": n_se, "uso_ia": n_ia}
        if any(resultado.values()):
            registrar(db, None, None, None, "limpeza", resultado)
        await db.commit()
    return resultado


async def laco_retencao(intervalo: int = 6 * 3600) -> None:
    while True:
        try:
            r = await limpar_por_retencao()
            if any(r.values()):
                logger.warning("Retenção LGPD: %s", r)
        except Exception as exc:
            logger.error("Retenção LGPD: %s", type(exc).__name__)
        await asyncio.sleep(intervalo)
