from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select
import random
import secrets
import uuid
import json

from backend.app.security import get_tenant_db, require_roles
from backend.app.roles import UserRole
from backend.app.db_models import Cargo as DBCargo, ProvaMontada as DBProvaMontada, Disciplina as DBDisciplina
from backend.app.models import (
    Cargo as PydanticCargo,
    ProvaMontada as PydanticProvaMontada,
    BlocoQuestao as PydanticBlocoQuestao,
    )
from backend.app.auth import get_current_user
from backend.app.db_models import DisciplinaDaProva as DBDisciplinaDaProva
from backend.app.db_models import QuestoesBanco, TextoReferenciaGeral, Conteudo, OpcoesQuestao
from backend.app.db_models import DetalhesQuestaoDiscursiva as DBDetalhesDiscursiva


router = APIRouter()

# 1. Listar todos os cargos do tenant logado (por evento), com status da montagem
@router.get("/eventos/{id_evento}/cargos-com-status-prova")
async def listar_cargos_com_status_prova(
    id_evento: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(DBCargo).where(
            DBCargo.tenant_id == current_user.tenant_id,
            DBCargo.id_evento_fk == id_evento,
        )
    )
    cargos = result.scalars().all()

    provas_result = await db.execute(
        select(DBProvaMontada).where(
            DBProvaMontada.tenant_id == current_user.tenant_id,
            DBProvaMontada.id_evento_fk == id_evento,
        )
    )
    provas_por_cargo = {p.id_cargo_fk: p for p in provas_result.scalars().all()}

    resposta = []
    for c in cargos:
        prova = provas_por_cargo.get(c.id_cargo)
        if not prova:
            status = "Não Iniciada"
        elif prova.status_montagem and prova.status_montagem.lower() == "concluída":
            status = "Concluída"
        else:
            status = "Concluída"
        resposta.append({
            "id_cargo": c.id_cargo,
            "codigo_cargo": c.codigo_cargo,
            "nome_cargo": c.nome_cargo,
            "nivel": c.nivel,
            "turno": c.turno,
            "status_montagem": status
        })
    return resposta

# 2. Obter montagem de prova de um cargo
@router.get("/eventos/{id_evento}/provas-montadas/{id_cargo}", response_model=Optional[PydanticProvaMontada])
async def get_prova_montada(
    id_evento: str,
    id_cargo: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(DBProvaMontada).where(
            DBProvaMontada.tenant_id == current_user.tenant_id,
            DBProvaMontada.id_evento_fk == id_evento,
            DBProvaMontada.id_cargo_fk == id_cargo,
        )
    )
    prova = result.scalar_one_or_none()
    if not prova:
        return None
    blocos = prova.__dict__.get("blocos_questoes", [])
    if isinstance(blocos, str):
        import json
        blocos = json.loads(blocos)
    return PydanticProvaMontada(
        nome_prova_montada=prova.nome_prova_montada,
        blocos_questoes=blocos or []
    )

# 3. Criar ou atualizar montagem de prova
@router.post("/eventos/{id_evento}/provas-montadas/{id_cargo}")
async def salvar_prova_montada(
    id_evento: str,
    id_cargo: str,
    payload: PydanticProvaMontada,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    import random
    import json
    from datetime import datetime

    result = await db.execute(
        select(DBProvaMontada).where(
            DBProvaMontada.tenant_id == current_user.tenant_id,
            DBProvaMontada.id_evento_fk == id_evento,
            DBProvaMontada.id_cargo_fk == id_cargo,
        )
    )
    prova = result.scalar_one_or_none()
    now = datetime.now()  # mesmo relógio das questões (data_modificacao local), para comparar
    blocos_dict = []
    
    # Busca informações do cargo para montar o nome da prova
    cargo_result = await db.execute(
        select(DBCargo).where(
            DBCargo.id_cargo == id_cargo,
            DBCargo.tenant_id == current_user.tenant_id,
            DBCargo.id_evento_fk == id_evento,
        )
    )
    cargo = cargo_result.scalar_one_or_none()
    if not cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")

    # Busca todas as disciplinas da prova/cargo, já em ordem
    disc_prova_query = await db.execute(
        select(DBDisciplinaDaProva)
        .where(DBDisciplinaDaProva.id_cargo_fk == id_cargo)
        .where(DBDisciplinaDaProva.tenant_id == current_user.tenant_id)
        .order_by(DBDisciplinaDaProva.ordem_na_prova.asc())
    )
    disciplinas_ordenadas = disc_prova_query.scalars().all()

    # Busca todos os conteúdos
    conteudos_query = await db.execute(
        select(Conteudo).where(Conteudo.is_deleted == False)
    )
    conteudos = conteudos_query.scalars().all()
    mapa_conteudo_nome_id = {
        (c.nome_conteudo or "").strip().lower(): c.id_conteudo for c in conteudos
    }

    blocos = list(payload.blocos_questoes)
    for i, bloco in enumerate(blocos):
        bloco_dict = bloco.dict() if hasattr(bloco, "dict") else bloco
        # Atribui dados da disciplina pela ordem
        if i < len(disciplinas_ordenadas):
            disciplina = disciplinas_ordenadas[i]
            bloco_dict["id_disciplina_prova"] = disciplina.id_disciplina_prova
            bloco_dict["nome_disciplina_na_prova"] = disciplina.nome_disciplina_na_prova
            bloco_dict["tipo_conhecimento"] = disciplina.tipo_conhecimento
        else:
            bloco_dict["id_disciplina_prova"] = None
            bloco_dict["nome_disciplina_na_prova"] = None
            bloco_dict["tipo_conhecimento"] = None

        # Trata nome_conteudo
        nome_conteudo = (bloco_dict.get("nome_disciplina") or bloco_dict.get("nome_conteudo") or "").strip().lower()
        conteudo_id = bloco_dict.get("conteudo_id")
        if not conteudo_id:
            conteudo_id = mapa_conteudo_nome_id.get(nome_conteudo)
        bloco_dict["conteudo_id"] = conteudo_id

        # Se já tem questões, apenas coleta textos de referência depois
        if "questoes" in bloco_dict and bloco_dict["questoes"]:
            blocos_dict.append(bloco_dict)
            continue

        # Se não tem conteudo_id, pula as questões
        if not conteudo_id:
            bloco_dict["questoes"] = []
            blocos_dict.append(bloco_dict)
            continue

        qtd_questoes = bloco_dict.get("qtd_questoes", 0)
        questoes_query = await db.execute(
            select(QuestoesBanco)
            .where(QuestoesBanco.id_evento_fk == id_evento)
            .where(QuestoesBanco.conteudo_id == conteudo_id)
        )
        questoes = questoes_query.scalars().all()
        if not questoes:
            bloco_dict["questoes"] = []
        else:
            secrets.SystemRandom().shuffle(questoes)  # sorteio das questões imprevisível
            questoes_sorteadas = questoes[:qtd_questoes]
            bloco_dict["questoes"] = []
            for q in questoes_sorteadas:
                # PATCH: opções com suporte a imagem
                opcoes_query = await db.execute(
                    select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == q.id_questao)
                )
                opcoes_objs = opcoes_query.scalars().all()
                opcoes = []
                for o in opcoes_objs:
                    op_dict = {
                        "texto_opcao": o.texto_opcao,
                        "correta": o.correta,
                    }
                    if getattr(o, "imagem_path_opcao", None):
                        op_dict["imagem_path_opcao"] = o.imagem_path_opcao
                    opcoes.append(op_dict)

                detalhes_discursiva = None
                if q.tipo and q.tipo.strip().upper() == "DISCURSIVA":
                    detalhes_result = await db.execute(
                        select(DBDetalhesDiscursiva).where(DBDetalhesDiscursiva.id_questao_fk == q.id_questao)
                    )
                    detalhes_obj = detalhes_result.scalar_one_or_none()
                    if detalhes_obj:
                        detalhes_discursiva = {
                            "numero_linhas_resposta": detalhes_obj.numero_linhas_resposta
                        }
                    # PATCH: para discursiva, opcoes sempre vazio
                    opcoes = []

                questao_dict = {
                    "id_questao": q.id_questao,
                    "enunciado": q.enunciado,
                    "resposta_correta": q.resposta_correta,
                    "id_texto_ref_vinculado": getattr(q, "id_texto_ref_vinculado", None),
                    "opcoes": opcoes,
                }
                # PATCH: inclui caminho_imagem_relativo se existir na questao original
                if getattr(q, "caminho_imagem_relativo", None):
                    questao_dict["caminho_imagem_relativo"] = q.caminho_imagem_relativo

                if detalhes_discursiva:
                    questao_dict["detalhes_discursiva"] = detalhes_discursiva

                bloco_dict["questoes"].append(questao_dict)
            blocos_dict.append(bloco_dict)

    # NOVO: textos de referência apenas pelo questoes_vinculo
    ids_questoes_na_prova = set()
    for bloco in blocos_dict:
        for questao in bloco.get("questoes", []):
            id_questao = questao.get("id_questao")
            if id_questao:
                ids_questoes_na_prova.add(str(id_questao))

    textos_query = await db.execute(
        select(TextoReferenciaGeral).where(TextoReferenciaGeral.id_evento_fk == id_evento)
    )
    textos_objs = textos_query.scalars().all()

    textos_referencia = []
    for t in textos_objs:
        if not t.questoes_vinculo:
            continue
        questoes_ligadas = set(q.strip() for q in t.questoes_vinculo.split(",") if q.strip())
        if ids_questoes_na_prova & questoes_ligadas:
            textos_referencia.append({
                "id_texto_ref": t.id_texto_ref,
                "codigo_ref": t.codigo_ref,
                "titulo": t.titulo,
                "conteudo": getattr(t, "conteudo", None),
                "tipo_conteudo": t.tipo_conteudo,
                "metadados_texto_ref": getattr(t, "metadados_texto_ref", {}),
                "data_criacao": getattr(t, "data_criacao", None),
                "data_modificacao": getattr(t, "data_modificacao", None),
                "conteudo_formatado": getattr(t, "conteudo_formatado", []),
                "caminho_imagem_relativo": getattr(t, "caminho_imagem_relativo", None),
                "descricao_imagem": getattr(t, "descricao_imagem", None),
                "questoes_vinculo": t.questoes_vinculo,
            })

    # Adiciona o vínculo explícito com o texto/imagem de referência em cada questão
    for bloco in blocos_dict:
        for questao in bloco.get("questoes", []):
            id_questao = str(questao.get("id_questao"))
            id_referencia = None
            tipo_referencia = None
            for t in textos_referencia:
                questoes_vinculo = set(q.strip() for q in (t.get("questoes_vinculo") or "").split(",") if q.strip())
                if id_questao in questoes_vinculo:
                    id_referencia = t.get("id_texto_ref")
                    tipo_referencia = t.get("tipo_conteudo")  # "texto" ou "imagem"
                    break
            questao["id_referencia_vinculo"] = id_referencia      # ID do texto/imagem de referência (ou None)
            questao["tipo_referencia_vinculo"] = tipo_referencia  # "texto", "imagem" ou None
        

    for bloco in blocos_dict:
        questoes = bloco.get("questoes") or []
        for questao in questoes:
            if not questao.get("codigo_curto_questao"):
                id_questao = questao.get("id_questao")
                if id_questao:
                    result = await db.execute(
                        select(QuestoesBanco.codigo_curto_questao).where(QuestoesBanco.id_questao == id_questao)
                    )
                    codigo_curto = result.scalar_one_or_none()
                    questao["codigo_curto_questao"] = codigo_curto or ""
                else:
                    questao["codigo_curto_questao"] = ""

    nome_prova_montada = f"{cargo.codigo_cargo} – {cargo.nome_cargo}"
    blocos_json = json.dumps(blocos_dict, ensure_ascii=False)
    textos_referencia_json = json.dumps(textos_referencia, ensure_ascii=False)

    # Semente secreta da prova: criada a cada montagem (que sorteia as questões de novo) e gravada
    # cifrada. Todas as exportações desta montagem saem idênticas; ninguém prevê o gabarito.
    meta = (prova.metadados_prova if prova else None) or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            meta = {}
    meta["semente_gabarito"] = secrets.token_hex(32)
    meta_json = json.dumps(meta, ensure_ascii=False)

    if prova:
        prova.nome_prova_montada = nome_prova_montada
        prova.metadados_prova = meta_json
        prova.blocos_questoes = blocos_json
        prova.textos_referencia_prova_json = textos_referencia_json
        prova.data_modificacao = now
    else:
        prova = DBProvaMontada(
            id_prova_montada=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            id_evento_fk=id_evento,
            id_cargo_fk=id_cargo,
            nome_prova_montada=nome_prova_montada,
            blocos_questoes=blocos_json,
            textos_referencia_prova_json=textos_referencia_json,
            metadados_prova=meta_json,
            data_criacao=now,
            data_modificacao=now,
            status_montagem="Em Andamento"
        )
        db.add(prova)
    await db.commit()
    return {"ok": True}

# 3b. Atualizar as questões da montagem SEM sortear de novo
def _assinatura(questao: dict) -> str:
    """O que vai impresso de cada questão: se não mudou, a cópia fica intocada (prova idêntica)."""
    ops = [(str(o.get("texto_opcao") or ""), bool(o.get("correta")), str(o.get("imagem_path_opcao") or ""))
           for o in (questao.get("opcoes") or [])]
    return json.dumps([questao.get("enunciado") or "", questao.get("resposta_correta") or "",
                       questao.get("caminho_imagem_relativo") or "", sorted(ops),
                       (questao.get("detalhes_discursiva") or {}).get("numero_linhas_resposta")], ensure_ascii=False)


@router.post("/eventos/{id_evento}/provas-montadas/{id_cargo}/atualizar-questoes")
async def atualizar_questoes_da_montagem(
    id_evento: str,
    id_cargo: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    """
    Relê do banco as questões JÁ escolhidas na montagem (mesmas questões, mesma ordem, mesma semente).
    Só as que mudaram desde a montagem são trocadas; as demais ficam idênticas, então a prova só muda
    onde a questão foi corrigida. Útil quando uma questão é editada/revisada depois de montar.
    """
    prova = (await db.execute(select(DBProvaMontada).where(
        DBProvaMontada.tenant_id == current_user.tenant_id,
        DBProvaMontada.id_evento_fk == id_evento,
        DBProvaMontada.id_cargo_fk == id_cargo,
    ))).scalar_one_or_none()
    if not prova:
        raise HTTPException(status_code=404, detail="Montagem não encontrada.")
    blocos = prova.blocos_questoes
    if isinstance(blocos, str):
        blocos = json.loads(blocos or "[]")
    blocos = blocos or []

    atualizadas, iguais, excluidas = [], 0, []
    for bloco in blocos:
        for i, antiga in enumerate(bloco.get("questoes") or []):
            q = (await db.execute(select(QuestoesBanco).where(QuestoesBanco.id_questao == antiga.get("id_questao")))).scalar_one_or_none()
            if q is None:
                excluidas.append(antiga.get("codigo_curto_questao") or antiga.get("id_questao"))
                continue
            ops = (await db.execute(select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == q.id_questao)
                                    .order_by(OpcoesQuestao.ordem_original, OpcoesQuestao.letra))).scalars().all()
            nova = dict(antiga)
            nova["enunciado"] = q.enunciado
            nova["resposta_correta"] = q.resposta_correta
            nova["codigo_curto_questao"] = q.codigo_curto_questao or antiga.get("codigo_curto_questao")
            nova["opcoes"] = []
            if not (q.tipo and "DISCURSIVA" in q.tipo.upper()):
                for o in ops:
                    op = {"texto_opcao": o.texto_opcao, "correta": o.correta}
                    if o.imagem_path_opcao:
                        op["imagem_path_opcao"] = o.imagem_path_opcao
                    nova["opcoes"].append(op)
            if q.caminho_imagem_relativo:
                nova["caminho_imagem_relativo"] = q.caminho_imagem_relativo
            else:
                nova.pop("caminho_imagem_relativo", None)
            if q.tipo and q.tipo.upper() == "DISCURSIVA":
                det = (await db.execute(select(DBDetalhesDiscursiva).where(DBDetalhesDiscursiva.id_questao_fk == q.id_questao))).scalar_one_or_none()
                if det:
                    nova["detalhes_discursiva"] = {"numero_linhas_resposta": det.numero_linhas_resposta}
            if _assinatura(nova) == _assinatura(antiga):
                iguais += 1
                continue
            bloco["questoes"][i] = nova
            atualizadas.append(nova["codigo_curto_questao"] or nova.get("id_questao"))

    if atualizadas:
        prova.blocos_questoes = json.dumps(blocos, ensure_ascii=False)  # metadados (e a semente) intocados
    # a montagem passa a refletir o banco de agora (some o aviso "editada depois da montagem")
    prova.data_modificacao = datetime.now()
    await db.commit()
    return {"atualizadas": atualizadas, "sem_mudanca": iguais, "excluidas_do_banco": excluidas}


# 4. Excluir montagem de prova
@router.delete("/eventos/{id_evento}/provas-montadas/{id_cargo}")
async def delete_prova_montada(
    id_evento: str,
    id_cargo: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    result = await db.execute(
        select(DBProvaMontada).where(
            DBProvaMontada.tenant_id == current_user.tenant_id,
            DBProvaMontada.id_evento_fk == id_evento,
            DBProvaMontada.id_cargo_fk == id_cargo,
        )
    )
    prova = result.scalar_one_or_none()
    if prova:
        await db.delete(prova)
        await db.commit()
        return {"ok": True}
    return {"ok": False, "error": "Prova não encontrada"}

# 5. Listar disciplinas disponíveis para montagem de prova
@router.get("/eventos/{id_evento}/disciplinas", response_model=List[str])
async def get_disciplinas_do_evento(
    id_evento: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(DBDisciplina).where(
            DBDisciplina.tenant_id == current_user.tenant_id,
            DBDisciplina.id_evento_fk == id_evento,
        )
    )
    disciplinas = result.scalars().all()
    return [d.nome_disciplina for d in disciplinas]

@router.get("/eventos/{event_id}/cargos-quantidade-questoes")
async def cargos_quantidade_questoes(
    event_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(DBCargo)
        .where(DBCargo.id_evento_fk == event_id)
        .where(DBCargo.tenant_id == current_user.tenant_id)
    )
    cargos = result.scalars().all()
    resposta = []
    for cargo in cargos:
        disc_result = await db.execute(
            select(DBDisciplinaDaProva.qtd_questoes)
            .where(DBDisciplinaDaProva.id_cargo_fk == cargo.id_cargo)
            .where(DBDisciplinaDaProva.tenant_id == current_user.tenant_id)
        )
        questoes = disc_result.scalars().all()
        total_questoes = sum([q or 0 for q in questoes])
        resposta.append({
            "id_cargo": cargo.id_cargo,
            "codigo_cargo": cargo.codigo_cargo,
            "nome_cargo": cargo.nome_cargo,
            "nivel": cargo.nivel,
            "turno": cargo.turno,
            "total_questoes": total_questoes
        })
    return resposta