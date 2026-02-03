from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime
import uuid, os, json, shutil, hashlib, random
from backend.app.database import get_db
from backend.app.db_models import (
    Cargo as DBCargo,
    ProvaMontada as DBProvaMontada,
    BancoFrases,
    QuestoesBanco,
    ItensVerdadeiroFalso,
)
from backend.app.auth import get_current_user


router = APIRouter()

# 1. Listar cargos prontos para geração (com definição)
@router.get("/eventos/{event_id}/cargos/provas-geracao")
async def listar_cargos_para_geracao(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    cargos_result = await db.execute(
        select(DBCargo)
        .where(DBCargo.tenant_id == current_user.tenant_id)
        .where(DBCargo.id_evento_fk == event_id)
    )
    cargos = cargos_result.scalars().all()

    provas_result = await db.execute(
        select(DBProvaMontada)
        .where(DBProvaMontada.tenant_id == current_user.tenant_id)
        .where(DBProvaMontada.id_evento_fk == event_id)
    )
    provas_por_cargo = {p.id_cargo_fk: p for p in provas_result.scalars().all()}

    resposta = []
    for c in cargos:
        prova = provas_por_cargo.get(c.id_cargo)
        if not prova:
            continue
        definicao_geracao = None
        frases_por_tipo_prova = None
        meta = getattr(prova, "metadados_prova", None)
        if meta and isinstance(meta, dict):
            definicao_geracao = meta.get("definicao_geracao")
            frases_por_tipo_prova = meta.get("frases_por_tipo_prova")
        elif meta and isinstance(meta, str):
            try:
                meta = json.loads(meta)
                definicao_geracao = meta.get("definicao_geracao")
                frases_por_tipo_prova = meta.get("frases_por_tipo_prova")
            except Exception:
                definicao_geracao = None
                frases_por_tipo_prova = None
        resposta.append({
            "id_cargo": c.id_cargo,
            "nome_cargo": c.nome_cargo,
            "definicao_geracao": definicao_geracao,  # pode ser None!
            "frases_por_tipo_prova": frases_por_tipo_prova  # <-- AGORA INCLUÍDO
        })
    return resposta

# 2. Definir ou atualizar definições de geração 
@router.post("/eventos/{event_id}/provas/definir-geracao")
async def definir_geracao_provas(
    event_id: str,
    cargos_ids: str = Form(...),  # JSON string
    tipo_geracao: str = Form(...),
    num_variacoes: int = Form(...),
    embaralhar_questoes: bool = Form(...),
    embaralhar_alternativas: bool = Form(...),
    csv_candidatos: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    import json
    ids = json.loads(cargos_ids)
    csv_path = None
    if csv_candidatos:
        filename = f"{uuid.uuid4()}.csv"
        upload_dir = "uploads/csv_candidatos"
        os.makedirs(upload_dir, exist_ok=True)
        csv_path = os.path.join(upload_dir, filename)
        with open(csv_path, "wb") as buffer:
            shutil.copyfileobj(csv_candidatos.file, buffer)

    for cargo_id in ids:
        result = await db.execute(
            select(DBProvaMontada)
            .where(DBProvaMontada.tenant_id == current_user.tenant_id)
            .where(DBProvaMontada.id_evento_fk == event_id)
            .where(DBProvaMontada.id_cargo_fk == cargo_id)
        )
        prova = result.scalar_one_or_none()
        if not prova:
            continue

        # Carregar metadados_prova do banco e garantir dict
        meta = getattr(prova, "metadados_prova", None)
        if meta is None or meta == "":
            meta = {}
        elif isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        # Sempre gere nova semente determinística
        semente_str = f"{prova.id_prova_montada}-{cargo_id}-{num_variacoes}-{embaralhar_questoes}-{embaralhar_alternativas}"
        semente_embaralhamento = hashlib.md5(semente_str.encode()).hexdigest()
        
        definicao = {
            "num_variacoes": num_variacoes,
            "geracao_individual": tipo_geracao == "candidato",
            "embaralhar_questoes": embaralhar_questoes,
            "embaralhar_alternativas": embaralhar_alternativas,
            "data_hora_geracao": datetime.utcnow().isoformat(),
            "semente_embaralhamento": semente_embaralhamento,
            "caminho_csv_candidatos": csv_path if (csv_path and tipo_geracao == "candidato") else None
        }

        # Buscar frases motivacionais ativas
        frases_result = await db.execute(
            select(BancoFrases)
            .where(BancoFrases.categoria == "Motivacionais")
            .where(BancoFrases.ativo == True)
            .where(BancoFrases.tenant_id == current_user.tenant_id)
        )
        todas_frases = [f.texto_frase for f in frases_result.scalars().all()]

        # Sorteio determinístico com a semente
        random.seed(semente_embaralhamento)
        frases_embaralhadas = todas_frases.copy()
        random.shuffle(frases_embaralhadas)

        frases_por_tipo_prova = {}
        for i in range(num_variacoes):
            tipo_key = f"Tipo {chr(ord('A') + i)}"
            if i < len(frases_embaralhadas):
                frases_por_tipo_prova[tipo_key] = frases_embaralhadas[i]
            elif frases_embaralhadas:
                frases_por_tipo_prova[tipo_key] = frases_embaralhadas[i % len(frases_embaralhadas)]
            else:
                frases_por_tipo_prova[tipo_key] = ""

        # Atualizar sempre sobrescrevendo
        meta["definicao_geracao"] = definicao
        meta["frases_por_tipo_prova"] = frases_por_tipo_prova

        # Serializar se o campo no banco é string (ajuste conforme seu modelo!)
        prova.metadados_prova = json.dumps(meta)
        prova.data_modificacao = datetime.utcnow()

    await db.commit()
    return {"success": True}

# 3. Simular frases motivacionais
@router.post("/eventos/{event_id}/simular-frases/{cargo_id}")
async def simular_frases_geracao(
    event_id: str,
    cargo_id: str,
    tipo_geracao: str = Form(...),
    num_variacoes: int = Form(...),
    embaralhar_questoes: bool = Form(...),
    embaralhar_alternativas: bool = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    import hashlib, random

    # Seed determinística usando os parâmetros
    semente_str = f"{cargo_id}-{num_variacoes}-{embaralhar_questoes}-{embaralhar_alternativas}-{tipo_geracao}"
    semente_embaralhamento = hashlib.md5(semente_str.encode()).hexdigest()

    # Buscar frases motivacionais ativas
    frases_result = await db.execute(
        select(BancoFrases)
        .where(BancoFrases.categoria == "Motivacionais")
        .where(BancoFrases.ativo == True)
        .where(BancoFrases.tenant_id == current_user.tenant_id)
    )
    todas_frases = [f.texto_frase for f in frases_result.scalars().all()]

    random.seed(semente_embaralhamento)
    frases_embaralhadas = todas_frases.copy()
    random.shuffle(frases_embaralhadas)

    frases_por_tipo_prova = {}
    for i in range(num_variacoes):
        tipo_key = f"Tipo {chr(ord('A') + i)}"
        if i < len(frases_embaralhadas):
            frases_por_tipo_prova[tipo_key] = frases_embaralhadas[i]
        elif frases_embaralhadas:
            frases_por_tipo_prova[tipo_key] = frases_embaralhadas[i % len(frases_embaralhadas)]
        else:
            frases_por_tipo_prova[tipo_key] = ""
    return {
        "frases_por_tipo_prova": frases_por_tipo_prova,
        "frases_unicas": len(set(frases_embaralhadas)),
        "tem_frase_repetida": num_variacoes > len(frases_embaralhadas)
    }

# 4. Simular embaralhamento de itens de certo/errado (verdadeiro/falso)
@router.post("/eventos/{event_id}/simular-certo-errado/{cargo_id}")
async def simular_certo_errado_geracao(
    event_id: str,
    cargo_id: str,
    tipo_geracao: str = Form(...),
    num_variacoes: int = Form(...),
    embaralhar_itens: bool = Form(...),  # novo parâmetro para embaralhar
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Simula o embaralhamento determinístico dos itens de questões do tipo certo/errado
    para um cargo e evento específicos.
    """
    # Buscar todas as questões do tipo Verdadeiro/Falso desse cargo/evento
    questoes_result = await db.execute(
        select(QuestoesBanco)
        .where(QuestoesBanco.id_evento_fk == event_id)
        .where(QuestoesBanco.tenant_id == current_user.tenant_id)
        .where(QuestoesBanco.tipo.in_(["VerdadeiroFalso", "CertoErrado"]))
        .where(QuestoesBanco.id_questao.in_(
            select(ItensVerdadeiroFalso.id_questao_fk)
            .where(ItensVerdadeiroFalso.tenant_id == current_user.tenant_id)
        ))
    )
    questoes_vf = questoes_result.scalars().all()

    # Para cada questão, buscar os itens associados
    blocos = []
    for questao in questoes_vf:
        # Buscar os itens desse comando
        itens_result = await db.execute(
            select(ItensVerdadeiroFalso)
            .where(ItensVerdadeiroFalso.id_questao_fk == questao.id_questao)
            .where(ItensVerdadeiroFalso.tenant_id == current_user.tenant_id)
        )
        itens = itens_result.scalars().all()
        blocos.append({
            "id_questao": questao.id_questao,
            "comando": questao.enunciado,
            "itens": [
                {
                    "id_item_vf": item.id_item_vf,
                    "afirmacao": item.afirmacao,
                    "valor_correto": "C" if item.valor_correto else "E"
                }
                for item in itens
            ]
        })

    # Para cada variação, embaralhar os itens do bloco de forma determinística
    variacoes = []
    for v in range(num_variacoes):
        seed_str = f"{cargo_id}-{event_id}-{v}-{tipo_geracao}-ce"
        seed = hashlib.md5(seed_str.encode()).hexdigest()
        bloco_variacao = []
        for bloco in blocos:
            itens = bloco["itens"][:]
            if embaralhar_itens and len(itens) > 1:
                random.seed(f"{seed}-{bloco['id_questao']}")
                random.shuffle(itens)
            bloco_variacao.append({
                "comando": bloco["comando"],
                "itens": itens
            })
        variacoes.append(bloco_variacao)

    # Montar resposta: cada variação, itens numerados sequencialmente
    variacoes_formatadas = []
    for idx, blocos_var in enumerate(variacoes):
        itens_num = 1
        prova = []
        for bloco in blocos_var:
            prova.append({"comando": bloco["comando"], "itens": []})
            for item in bloco["itens"]:
                prova[-1]["itens"].append({
                    "numero": itens_num,
                    "afirmacao": item["afirmacao"],
                    "gabarito": item["valor_correto"]
                })
                itens_num += 1
        variacoes_formatadas.append({
            "tipo": f"Tipo {chr(ord('A')+idx)}",
            "blocos": prova
        })

    return {"variacoes": variacoes_formatadas}