import logging as _diag_logging
_diag_print_logger = _diag_logging.getLogger(__name__)


def print(*args, **kwargs):  # noqa: A001
    """Prints de depuração viram log DEBUG: não expõem conteúdo de prova em produção (DIAGPRO_LOG_LEVEL)."""
    _diag_print_logger.debug(" ".join(str(a) for a in args))


from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Body, Request
from sqlalchemy import select
from backend.app import secure_files
from backend.app.db_models import QuestoesBanco, OpcoesQuestao, ItensVerdadeiroFalso, DetalhesQuestaoDiscursiva, Conteudo
from backend.app.models import QuestaoOut, OpcaoQuestao, ItemVerdadeiroFalso, DetalhesQuestaoDiscursiva as DetalhesQuestaoDiscursivaModel
from backend.app import configuracoes
from backend.app import fluxo_revisao
from backend.app import versoes_questao
from backend.app.db_models import VersaoQuestao
from backend.app.auth import get_current_user
from backend.app.security import get_tenant_db, require_roles
from backend.app.roles import UserRole
from backend.app.utils_crypto import encrypt_text, decrypt_text
from backend.app.db_models import TextoReferenciaGeral
from backend.app.db_models import HistoricoRevisaoQuestao
from backend.app.utils_codigo_curto import gerar_codigo_curto
from backend.app.security import evento_autorizado
import uuid, os, shutil, json
from uuid import uuid4
from datetime import datetime
import ast

from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

def safe_decrypt(text):
    if not text:
        return None
    try:
        return decrypt_text(text)
    except Exception:
        return text



@router.post(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/questoes",
    response_model=QuestaoOut,
    summary="Criar uma nova questão (múltipla escolha, VF, discursiva ou subjetiva)"
)
async def criar_questao(
    request: Request,
    evento_id: str,
    conteudo_id: str,
    enunciado: str = Form(...),
    tipo: str = Form(...),
    alternativas: str = Form(None),
    itens_vf: str = Form(None),
    detalhes_discursiva: str = Form(None),
    resposta_correta: str = Form(None),
    nivel_dificuldade: str = Form(None),
    pontuacao: float = Form(1.0),
    tags: str = Form(None),
    anulada: bool = Form(False),
    justificativa_anulacao: str = Form(None),
    justificativa_questao: str = Form(None),
    texto_referencia_vinculo: str = Form(None),
    texto_referencia_direto: str = Form(None),
    indicacao_conteudo: str = Form(None),
    metadados: str = Form(None),
    tenant_id: int | None = Form(None),  # ignorado: o tenant vem do evento autorizado
    imagem_enunciado: UploadFile = File(None),
    imagem_justificativa: UploadFile = File(None),
    alternativa_imagem_A: UploadFile = File(None),
    alternativa_imagem_B: UploadFile = File(None),
    alternativa_imagem_C: UploadFile = File(None),
    alternativa_imagem_D: UploadFile = File(None),
    alternativa_imagem_E: UploadFile = File(None),
    autor_elaborador: str = Form(None),
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado),
    current_user=Depends(get_current_user),
):
    tenant_id = evento.tenant_id
    # tipos de questão que a banca usa (Configurações > Regras das questões)
    permitidos = (await configuracoes.ler_banca(db, tenant_id))["regras_questoes"]["tipos_permitidos"]
    if str(tipo or "").upper() not in permitidos:
        raise HTTPException(status_code=400, detail="Este tipo de questão não está habilitado para a banca.")
    tags_list = tags.split(",") if tags else []
    metadados_dict = None
    if metadados:
        try:
            metadados_dict = json.loads(metadados)
        except Exception:
            raise HTTPException(status_code=400, detail="metadados deve ser JSON válido")

    caminho_imagem_enunciado = None
    if imagem_enunciado:
        caminho_imagem_enunciado = await secure_files.save_upload_http(imagem_enunciado, tenant_id, "image")

    caminho_imagem_justificativa = None
    if imagem_justificativa:
        caminho_imagem_justificativa = await secure_files.save_upload_http(imagem_justificativa, tenant_id, "image")

    enunciado_criptografado = encrypt_text(enunciado) if enunciado else None
    justificativa_anulacao_criptografada = encrypt_text(justificativa_anulacao) if justificativa_anulacao else None
    justificativa_questao_criptografada = encrypt_text(justificativa_questao) if justificativa_questao else None
    texto_referencia_vinculo_criptografado = encrypt_text(texto_referencia_vinculo) if texto_referencia_vinculo else None
    texto_referencia_direto_criptografado = encrypt_text(texto_referencia_direto) if texto_referencia_direto else None
    indicacao_conteudo_criptografada = encrypt_text(indicacao_conteudo) if indicacao_conteudo else None

    conteudo_result = await db.execute(
        select(Conteudo).where(
            Conteudo.id_conteudo == conteudo_id,
            Conteudo.evento_id == evento.id_evento,
            Conteudo.tenant_id == evento.tenant_id,
        )
    )
    conteudo_obj = conteudo_result.scalar_one_or_none()
    codigo_curto_questao = await gerar_codigo_curto(tipo, tenant_id, db)

    nova_questao = QuestoesBanco(
        id_questao=str(uuid.uuid4()),
        codigo_curto_questao=codigo_curto_questao,
        id_evento_fk=evento_id,
        tenant_id=tenant_id,
        enunciado=enunciado_criptografado,
        tipo=tipo,
        resposta_correta=encrypt_text(resposta_correta) if resposta_correta else None,
        pontuacao=pontuacao,
        autor_elaborador=autor_elaborador,
        criador_id=str(current_user.id),  # quem elaborou (avisos da revisão vão para essa pessoa)
        status_revisao=fluxo_revisao.RASCUNHO,
        nivel_dificuldade=nivel_dificuldade,
        tags_keywords=",".join(tags_list),
        anulada=anulada,
        justificativa_anulacao=justificativa_anulacao_criptografada,
        justificativa_questao=justificativa_questao_criptografada,
        texto_referencia_vinculo=texto_referencia_vinculo_criptografado,
        texto_referencia_direto=texto_referencia_direto_criptografado,
        indicacao_conteudo=indicacao_conteudo_criptografada,
        metadados_questao=json.dumps(metadados_dict) if metadados_dict else None,
        caminho_imagem_relativo=caminho_imagem_enunciado,
        caminho_imagem_justificativa=caminho_imagem_justificativa,
        conteudo_id=conteudo_id,
        conteudo_nome=conteudo_obj.nome_conteudo if conteudo_obj else None,
        data_criacao=datetime.now(),
        data_modificacao=datetime.now(),
    )
    db.add(nova_questao)
    await db.commit()
    await db.refresh(nova_questao)

    # Alternativas - com imagem para cada uma
    alternativas_list = json.loads(alternativas) if alternativas else []
    for alt in alternativas_list:
        letra = alt.get("letra")
        imagem_file = locals().get(f"alternativa_imagem_{letra}")
        imagem_path_opcao = None
        if imagem_file:
            imagem_path_opcao = await secure_files.save_upload_http(imagem_file, tenant_id, "image")

        texto_opcao = alt.get("texto") or alt.get("texto_opcao") or ""
        texto_opcao_cript = encrypt_text(texto_opcao) if texto_opcao else None
        texto_formatado_cript = encrypt_text(alt.get("texto_opcao_formatado")) if alt.get("texto_opcao_formatado") else None
        feedback_opcao_cript = encrypt_text(alt.get("feedback_opcao")) if alt.get("feedback_opcao") else None

        nova_opcao = OpcoesQuestao(
            id_opcao_questao=str(uuid.uuid4()),
            id_questao_fk=nova_questao.id_questao,
            letra=letra,
            texto_opcao=texto_opcao_cript,
            correta=alt.get("correta", False),
            texto_opcao_formatado=texto_formatado_cript,
            ordem_original=alt.get("ordem_original", None),
            feedback_opcao=feedback_opcao_cript,
            imagem_path_opcao=imagem_path_opcao,
            tenant_id=tenant_id,
        )
        db.add(nova_opcao)

    # Itens VF - aceita imagens dos itens do comando
    itens_vf_list = json.loads(itens_vf) if itens_vf else []
    # Pegue todos os arquivos do request que começam com "item_imagem_"
    files = await request.form()
    item_imagem_map = {}
    for key in files:
        if key.startswith("item_imagem_"):
            idx = int(key.replace("item_imagem_", ""))
            item_imagem_map[idx] = files[key]
    for idx, item in enumerate(itens_vf_list):
        imagem_file = item_imagem_map.get(idx)
        imagem_path_item = None
        if imagem_file is not None and hasattr(imagem_file, "filename"):
            imagem_path_item = await secure_files.save_upload_http(imagem_file, tenant_id, "image")
        afirmacao_cript = encrypt_text(item.get("afirmacao")) if item.get("afirmacao") else None
        feedback_item_cript = encrypt_text(item.get("feedback_item")) if item.get("feedback_item") else None
        novo_item = ItensVerdadeiroFalso(
            id_item_vf=str(uuid.uuid4()),
            id_questao_fk=nova_questao.id_questao,
            afirmacao=afirmacao_cript,
            valor_correto=item.get("valor_correto"),
            feedback_item=feedback_item_cript,
            ordem=item.get("ordem", None),
            imagem_path_item=imagem_path_item,
            tenant_id=tenant_id,  # obrigatório: sem ele o RLS recusa a linha
        )
        db.add(novo_item)

    # Discursiva/Subjetiva: criptografar todos os textos
    detalhes_obj = json.loads(detalhes_discursiva) if detalhes_discursiva else {}
    if detalhes_obj:
        resposta_esperada_texto_cript = encrypt_text(detalhes_obj.get("resposta_esperada_texto")) if detalhes_obj.get("resposta_esperada_texto") else None
        palavras_chave_resposta_cript = [encrypt_text(palavra) for palavra in detalhes_obj.get("palavras_chave_resposta", [])]
        texto_subjetivo_orientacao_cript = encrypt_text(detalhes_obj.get("texto_subjetivo_orientacao")) if detalhes_obj.get("texto_subjetivo_orientacao") else None
        texto_subjetivo_nota_maxima_cript = encrypt_text(detalhes_obj.get("texto_subjetivo_nota_maxima")) if detalhes_obj.get("texto_subjetivo_nota_maxima") else None

        novo_detalhe = DetalhesQuestaoDiscursiva(
            id_detalhe_discursiva=str(uuid.uuid4()),
            id_questao_fk=nova_questao.id_questao,
            resposta_esperada_texto=resposta_esperada_texto_cript,
            palavras_chave_resposta=json.dumps(palavras_chave_resposta_cript),
            numero_linhas_resposta=detalhes_obj.get("numero_linhas_resposta"),
            texto_subjetivo_orientacao=texto_subjetivo_orientacao_cript,
            texto_subjetivo_nota_maxima=texto_subjetivo_nota_maxima_cript,
            tenant_id=tenant_id,  # obrigatório: sem ele o RLS recusa a linha
        )
        db.add(novo_detalhe)

    await db.commit()

    # Buscar alternativas, VF e detalhes para resposta (descriptografa para o frontend)
    alt_result = await db.execute(
        select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == nova_questao.id_questao)
    )
    alternativas_out = []
    for a in alt_result.scalars().all():
        alternativas_out.append(OpcaoQuestao(
            id_opcao_questao=a.id_opcao_questao,
            id_questao_fk=a.id_questao_fk,
            letra=a.letra,
            texto_opcao=safe_decrypt(a.texto_opcao),
            correta=a.correta,
            texto_opcao_formatado=json.loads(safe_decrypt(a.texto_opcao_formatado)) if a.texto_opcao_formatado else None,
            ordem_original=a.ordem_original,
            feedback_opcao=safe_decrypt(a.feedback_opcao),
            imagem_path_opcao=a.imagem_path_opcao,
        ))

    vf_result = await db.execute(
        select(ItensVerdadeiroFalso).where(ItensVerdadeiroFalso.id_questao_fk == nova_questao.id_questao)
    )
    vf_out = []
    for i in vf_result.scalars().all():
        vf_out.append(ItemVerdadeiroFalso(
            id_item_vf=i.id_item_vf,
            id_questao_fk=i.id_questao_fk,
            afirmacao=safe_decrypt(i.afirmacao),
            valor_correto=i.valor_correto,
            feedback_item=safe_decrypt(i.feedback_item),
            ordem=i.ordem,
            imagem_path_item=i.imagem_path_item,
        ))

    detalhes_result = await db.execute(
        select(DetalhesQuestaoDiscursiva).where(DetalhesQuestaoDiscursiva.id_questao_fk == nova_questao.id_questao)
    )
    detalhes_obj = detalhes_result.scalar_one_or_none()
    detalhes_out = None
    if detalhes_obj:
        detalhes_dict = dict(detalhes_obj.__dict__)
        detalhes_dict.pop('_sa_instance_state', None)
        if 'palavras_chave_resposta' in detalhes_dict and detalhes_dict['palavras_chave_resposta']:
            try:
                palavras_chave_lista = json.loads(detalhes_dict['palavras_chave_resposta'])
                detalhes_dict['palavras_chave_resposta'] = [safe_decrypt(p) for p in palavras_chave_lista]
            except Exception:
                detalhes_dict['palavras_chave_resposta'] = []
        detalhes_dict['resposta_esperada_texto'] = safe_decrypt(detalhes_dict.get('resposta_esperada_texto'))
        detalhes_dict['texto_subjetivo_orientacao'] = safe_decrypt(detalhes_dict.get('texto_subjetivo_orientacao'))
        detalhes_dict['texto_subjetivo_nota_maxima'] = safe_decrypt(detalhes_dict.get('texto_subjetivo_nota_maxima'))
        detalhes_out = DetalhesQuestaoDiscursiva(**detalhes_dict)

    saida = QuestaoOut(
        id_questao=nova_questao.id_questao,
        codigo_curto_questao=nova_questao.codigo_curto_questao,
        enunciado=safe_decrypt(nova_questao.enunciado),
        tipo=nova_questao.tipo,
        alternativas=alternativas_out if alternativas_out is not None else [],
        itens_vf=vf_out,
        detalhes_discursiva=detalhes_out,
        resposta_correta=safe_decrypt(nova_questao.resposta_correta),
        nivel_dificuldade=nova_questao.nivel_dificuldade,
        pontuacao=nova_questao.pontuacao,
        tags=tags_list,
        anulada=nova_questao.anulada,
        justificativa_anulacao=safe_decrypt(nova_questao.justificativa_anulacao),
        texto_referencia_vinculo=safe_decrypt(nova_questao.texto_referencia_vinculo),
        texto_referencia_direto=safe_decrypt(nova_questao.texto_referencia_direto),
        indicacao_conteudo=safe_decrypt(nova_questao.indicacao_conteudo),
        metadados_questao=metadados_dict,
        caminho_imagem_relativo=nova_questao.caminho_imagem_relativo,
        conteudo_id=nova_questao.conteudo_id,
        evento_id=nova_questao.id_evento_fk,
        tenant_id=nova_questao.tenant_id,
        data_criacao=nova_questao.data_criacao,
        data_modificacao=nova_questao.data_modificacao,
        status_revisao=nova_questao.status_revisao,
        observacao_revisor=getattr(nova_questao, "observacao_revisor", None),
        autor_elaborador=nova_questao.autor_elaborador,
    )
    await versoes_questao.salvar(db, saida, tenant_id, "criada", current_user.username)
    return saida

@router.get(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/questoes",
    response_model=list[QuestaoOut],
    summary="Listar questões por evento e conteúdo"
)
async def listar_questoes(
    evento_id: str,
    conteudo_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    result = await db.execute(
        select(QuestoesBanco).where(
            QuestoesBanco.id_evento_fk == evento_id,
            QuestoesBanco.conteudo_id == conteudo_id
        )
    )
    
    questoes = result.scalars().all()
    lista = []
    for q in questoes:
        alt_result = await db.execute(
            select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == q.id_questao)
        )
        alternativas_out = []
        for a in alt_result.scalars().all():
            alternativas_out.append(OpcaoQuestao(
                id_opcao_questao=a.id_opcao_questao,
                id_questao_fk=a.id_questao_fk,
                letra=a.letra,
                texto_opcao=safe_decrypt(a.texto_opcao),
                correta=a.correta,
                texto_opcao_formatado=safe_decrypt(a.texto_opcao_formatado),
                ordem_original=a.ordem_original,
                feedback_opcao=safe_decrypt(a.feedback_opcao),
                imagem_path_opcao=a.imagem_path_opcao,
            ))

        vf_result = await db.execute(
            select(ItensVerdadeiroFalso).where(ItensVerdadeiroFalso.id_questao_fk == q.id_questao)
        )
        vf_out = []
        for i in vf_result.scalars().all():
            vf_out.append(ItemVerdadeiroFalso(
                id_item_vf=i.id_item_vf,
                id_questao_fk=i.id_questao_fk,
                afirmacao=safe_decrypt(i.afirmacao),
                valor_correto=i.valor_correto,
                feedback_item=safe_decrypt(i.feedback_item),
                ordem=i.ordem,
                imagem_path_item=i.imagem_path_item,
            ))

        detalhes_result = await db.execute(
            select(DetalhesQuestaoDiscursiva).where(DetalhesQuestaoDiscursiva.id_questao_fk == q.id_questao)
        )
        detalhes_obj = detalhes_result.scalar_one_or_none()
        detalhes_out = None
        if detalhes_obj:
            detalhes_dict = dict(detalhes_obj.__dict__)
            detalhes_dict.pop('_sa_instance_state', None)
            if 'palavras_chave_resposta' in detalhes_dict and detalhes_dict['palavras_chave_resposta']:
                try:
                    palavras_chave_lista = json.loads(detalhes_dict['palavras_chave_resposta'])
                    detalhes_dict['palavras_chave_resposta'] = [safe_decrypt(p) for p in palavras_chave_lista]
                except Exception:
                    detalhes_dict['palavras_chave_resposta'] = []
            detalhes_dict['resposta_esperada_texto'] = safe_decrypt(detalhes_dict.get('resposta_esperada_texto'))
            detalhes_dict['texto_subjetivo_orientacao'] = safe_decrypt(detalhes_dict.get('texto_subjetivo_orientacao'))
            detalhes_dict['texto_subjetivo_nota_maxima'] = safe_decrypt(detalhes_dict.get('texto_subjetivo_nota_maxima'))
            detalhes_out = DetalhesQuestaoDiscursiva(**detalhes_dict)

        tags_list = q.tags_keywords.split(",") if q.tags_keywords else []
        try:
            metadados_dict = json.loads(q.metadados_questao) if q.metadados_questao else None
        except Exception:
            metadados_dict = None

        lista.append(QuestaoOut(
            id_questao=q.id_questao,
            codigo_curto_questao=q.codigo_curto_questao,
            enunciado=safe_decrypt(q.enunciado),
            tipo=q.tipo,
            alternativas=alternativas_out,
            itens_vf=vf_out,
            detalhes_discursiva=detalhes_out,
            resposta_correta=safe_decrypt(q.resposta_correta),
            nivel_dificuldade=q.nivel_dificuldade,
            pontuacao=q.pontuacao,
            revisada=q.revisada,
            tags=tags_list,
            anulada=q.anulada,
            justificativa_anulacao=safe_decrypt(q.justificativa_anulacao),
            texto_referencia_vinculo=safe_decrypt(q.texto_referencia_vinculo),
            texto_referencia_direto=safe_decrypt(q.texto_referencia_direto),
            indicacao_conteudo=safe_decrypt(q.indicacao_conteudo),
            metadados_questao=metadados_dict,
            caminho_imagem_relativo=q.caminho_imagem_relativo.replace("\\", "/") if q.caminho_imagem_relativo else None,
            conteudo_id=q.conteudo_id,
            evento_id=q.id_evento_fk,
            tenant_id=q.tenant_id,
            data_criacao=q.data_criacao,
            data_modificacao=q.data_modificacao,
        ))
    return lista

@router.delete(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}",
    summary="Excluir uma questão"
)
async def excluir_questao(
    evento_id: str,
    conteudo_id: str,
    id_questao: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.PROFESSOR)),
):
    result = await db.execute(
        select(QuestoesBanco).where(
            QuestoesBanco.id_questao == id_questao,
            QuestoesBanco.id_evento_fk == evento_id,
            QuestoesBanco.conteudo_id == conteudo_id
        )
    )
    questao = result.scalar_one_or_none()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")

    # Excluir históricos de revisão e versões relacionados
    await db.execute(VersaoQuestao.__table__.delete().where(VersaoQuestao.id_questao_fk == id_questao))
    await db.execute(
        HistoricoRevisaoQuestao.__table__.delete().where(HistoricoRevisaoQuestao.id_questao_fk == id_questao)
    )
    # Excluir itens dependentes (alternativas, VF, discursivas)
    await db.execute(
        OpcoesQuestao.__table__.delete().where(OpcoesQuestao.id_questao_fk == id_questao)
    )
    await db.execute(
        ItensVerdadeiroFalso.__table__.delete().where(ItensVerdadeiroFalso.id_questao_fk == id_questao)
    )
    await db.execute(
        DetalhesQuestaoDiscursiva.__table__.delete().where(DetalhesQuestaoDiscursiva.id_questao_fk == id_questao)
    )
    await db.delete(questao)
    await db.commit()
    return {"ok": True, "detail": "Questão excluída com sucesso."}

@router.get(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}",
    response_model=QuestaoOut,
    summary="Buscar uma questão específica"
)
async def buscar_questao(
    evento_id: str,
    conteudo_id: str,
    id_questao: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado),
):
    result = await db.execute(
        select(QuestoesBanco).where(
            QuestoesBanco.id_questao == id_questao,
            QuestoesBanco.id_evento_fk == evento_id,
            QuestoesBanco.conteudo_id == conteudo_id
        )
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")

    # Alternativas
    alt_result = await db.execute(
        select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == q.id_questao)
    )
    alternativas_out = []
    for a in alt_result.scalars().all():
        alternativas_out.append(OpcaoQuestao(
            id_opcao_questao=a.id_opcao_questao,
            id_questao_fk=a.id_questao_fk,
            letra=a.letra,
            texto_opcao=safe_decrypt(a.texto_opcao),
            correta=a.correta,
            texto_opcao_formatado=safe_decrypt(a.texto_opcao_formatado),
            ordem_original=a.ordem_original,
            feedback_opcao=safe_decrypt(a.feedback_opcao),
            imagem_path_opcao=a.imagem_path_opcao,
        ))

    # Verdadeiro/Falso
    vf_result = await db.execute(
        select(ItensVerdadeiroFalso).where(ItensVerdadeiroFalso.id_questao_fk == q.id_questao)
    )
    vf_out = []
    for i in vf_result.scalars().all():
        vf_out.append(ItemVerdadeiroFalso(
            id_item_vf=i.id_item_vf,
            id_questao_fk=i.id_questao_fk,
            afirmacao=safe_decrypt(i.afirmacao),
            valor_correto=i.valor_correto,
            feedback_item=safe_decrypt(i.feedback_item),
            ordem=i.ordem,
            imagem_path_item=i.imagem_path_item,
        ))

    # Discursiva/Subjetiva
    detalhes_result = await db.execute(
        select(DetalhesQuestaoDiscursiva).where(DetalhesQuestaoDiscursiva.id_questao_fk == q.id_questao)
    )
    detalhes_obj = detalhes_result.scalar_one_or_none()
    detalhes_out = None
    if detalhes_obj:
        detalhes_dict = dict(detalhes_obj.__dict__)
        detalhes_dict.pop('_sa_instance_state', None)
        if 'palavras_chave_resposta' in detalhes_dict and detalhes_dict['palavras_chave_resposta']:
            try:
                palavras_chave_lista = json.loads(detalhes_dict['palavras_chave_resposta'])
                detalhes_dict['palavras_chave_resposta'] = [safe_decrypt(p) for p in palavras_chave_lista]
            except Exception:
                detalhes_dict['palavras_chave_resposta'] = []
        detalhes_dict['resposta_esperada_texto'] = safe_decrypt(detalhes_dict.get('resposta_esperada_texto'))
        detalhes_dict['texto_subjetivo_orientacao'] = safe_decrypt(detalhes_dict.get('texto_subjetivo_orientacao'))
        detalhes_dict['texto_subjetivo_nota_maxima'] = safe_decrypt(detalhes_dict.get('texto_subjetivo_nota_maxima'))
        detalhes_out = DetalhesQuestaoDiscursiva(**detalhes_dict)

    tags_list = q.tags_keywords.split(",") if q.tags_keywords else []
    try:
        metadados_dict = json.loads(q.metadados_questao) if q.metadados_questao else None
    except Exception:
        metadados_dict = None

    print('DEBUG OBSERVACAO RAW:', repr(q.observacao_revisor))
    print('DEBUG OBSERVACAO DECRYPT:', repr(safe_decrypt(q.observacao_revisor)))
    print("DEBUG texto_referencia_vinculo:", safe_decrypt(q.texto_referencia_vinculo))
    return QuestaoOut(
        id_questao=q.id_questao,
        codigo_curto_questao=q.codigo_curto_questao,
        enunciado=safe_decrypt(q.enunciado),
        tipo=q.tipo,
        alternativas=alternativas_out,
        itens_vf=vf_out,
        detalhes_discursiva=detalhes_out,
        resposta_correta=safe_decrypt(q.resposta_correta),
        nivel_dificuldade=q.nivel_dificuldade,
        pontuacao=q.pontuacao,
        tags=tags_list,
        anulada=q.anulada,
        justificativa_anulacao=safe_decrypt(q.justificativa_anulacao),
        texto_referencia_vinculo=safe_decrypt(q.texto_referencia_vinculo),
        texto_referencia_direto=safe_decrypt(q.texto_referencia_direto),
        indicacao_conteudo=safe_decrypt(q.indicacao_conteudo),
        metadados_questao=metadados_dict,
        caminho_imagem_relativo=q.caminho_imagem_relativo.replace("\\", "/") if q.caminho_imagem_relativo else None,
        conteudo_id=q.conteudo_id,
        evento_id=q.id_evento_fk,
        tenant_id=q.tenant_id,
        data_criacao=q.data_criacao,
        data_modificacao=q.data_modificacao,
        status_revisao=q.status_revisao,
        observacao_revisor=safe_decrypt(q.observacao_revisor),  
        autor_elaborador=q.autor_elaborador,
    )

@router.put(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}",
    response_model=QuestaoOut,
    summary="Editar uma questão existente"
)
async def editar_questao(
    request: Request,
    evento_id: str,
    conteudo_id: str,
    id_questao: str,
    enunciado: str = Form(...),
    tipo: str = Form(...),
    alternativas: str = Form(None),
    itens_vf: str = Form(None),
    detalhes_discursiva: str = Form(None),
    resposta_correta: str = Form(None),
    nivel_dificuldade: str = Form(None),
    pontuacao: float = Form(1.0),
    tags: str = Form(None),
    anulada: bool = Form(False),
    justificativa_anulacao: str = Form(None),
    texto_referencia_vinculo: str = Form(None),
    texto_referencia_direto: str = Form(None),
    indicacao_conteudo: str = Form(None),
    metadados: str = Form(None),
    tenant_id: int | None = Form(None),  # ignorado: o tenant vem do evento autorizado
    imagem_enunciado: UploadFile = File(None),
    alternativa_imagem_A: UploadFile = File(None),
    alternativa_imagem_B: UploadFile = File(None),
    alternativa_imagem_C: UploadFile = File(None),
    alternativa_imagem_D: UploadFile = File(None),
    alternativa_imagem_E: UploadFile = File(None),
    item_imagem_0: UploadFile = File(None),
    item_imagem_1: UploadFile = File(None),
    item_imagem_2: UploadFile = File(None),
    item_imagem_3: UploadFile = File(None),
    item_imagem_4: UploadFile = File(None),
    item_imagem_5: UploadFile = File(None),
    item_imagem_6: UploadFile = File(None),
    item_imagem_7: UploadFile = File(None),
    item_imagem_8: UploadFile = File(None),
    item_imagem_9: UploadFile = File(None),
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.PROFESSOR, UserRole.REVISOR, UserRole.ADMIN, UserRole.ADMIN_GERAL)),
):
    tenant_id = evento.tenant_id
    from backend.app.utils_crypto import encrypt_text

    result = await db.execute(
        select(QuestoesBanco).where(
            QuestoesBanco.id_questao == id_questao,
            QuestoesBanco.id_evento_fk == evento_id,
            QuestoesBanco.conteudo_id == conteudo_id,
            QuestoesBanco.tenant_id == tenant_id,
        )
    )
    questao = result.scalar_one_or_none()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")
    await versoes_questao.guardar_estado_anterior(db, await buscar_questao(evento_id, conteudo_id, id_questao, db), tenant_id)

    tags_list = tags.split(",") if tags else []
    metadados_dict = None
    if metadados:
        try:
            metadados_dict = json.loads(metadados)
        except Exception:
            raise HTTPException(status_code=400, detail="metadados deve ser JSON válido")

    caminho_imagem_relativo = questao.caminho_imagem_relativo
    if imagem_enunciado:
        caminho_imagem_relativo = await secure_files.save_upload_http(imagem_enunciado, tenant_id, "image")

    questao.enunciado = encrypt_text(enunciado) if enunciado else None
    questao.tipo = tipo
    questao.resposta_correta = encrypt_text(resposta_correta) if resposta_correta else None
    questao.pontuacao = pontuacao
    questao.nivel_dificuldade = nivel_dificuldade
    questao.tags_keywords = ",".join(tags_list)
    questao.anulada = anulada
    questao.justificativa_anulacao = encrypt_text(justificativa_anulacao) if justificativa_anulacao else None
    questao.texto_referencia_vinculo = encrypt_text(texto_referencia_vinculo) if texto_referencia_vinculo else None
    questao.texto_referencia_direto = encrypt_text(texto_referencia_direto) if texto_referencia_direto else None
    questao.indicacao_conteudo = encrypt_text(indicacao_conteudo) if indicacao_conteudo else None
    questao.metadados_questao = json.dumps(metadados_dict) if metadados_dict else None
    questao.caminho_imagem_relativo = caminho_imagem_relativo
    questao.data_modificacao = datetime.now()
    fluxo_revisao.reabrir_se_aprovada(db, questao, current_user.username)

    # --------- ALTERNATIVAS COM IMAGEM -----------
    alt_anteriores = {}
    alt_result = await db.execute(
        select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == id_questao)
    )
    for a in alt_result.scalars().all():
        alt_anteriores[a.letra] = a.imagem_path_opcao

    await db.execute(
        OpcoesQuestao.__table__.delete().where(OpcoesQuestao.id_questao_fk == id_questao)
    )

    alternativas_list = json.loads(alternativas) if alternativas else []
    for alt in alternativas_list:
        letra = alt.get("letra")
        imagem_file = None
        if letra == "A":
            imagem_file = alternativa_imagem_A
        elif letra == "B":
            imagem_file = alternativa_imagem_B
        elif letra == "C":
            imagem_file = alternativa_imagem_C
        elif letra == "D":
            imagem_file = alternativa_imagem_D
        elif letra == "E":
            imagem_file = alternativa_imagem_E

        if imagem_file and hasattr(imagem_file, "filename") and imagem_file.filename:
            imagem_path_opcao = await secure_files.save_upload_http(imagem_file, tenant_id, "image")
        else:
            imagem_path_opcao = alt_anteriores.get(letra)

        texto_opcao = alt.get("texto") or alt.get("texto_opcao") or ""
        texto_formatado_cript = encrypt_text(alt.get("texto_opcao_formatado")) if alt.get("texto_opcao_formatado") else None
        feedback_opcao_cript = encrypt_text(alt.get("feedback_opcao")) if alt.get("feedback_opcao") else None

        nova_opcao = OpcoesQuestao(
            id_opcao_questao=str(uuid.uuid4()),
            id_questao_fk=id_questao,
            letra=letra,
            texto_opcao=encrypt_text(texto_opcao) if texto_opcao else None,
            correta=alt.get("correta", False),
            texto_opcao_formatado=texto_formatado_cript,
            ordem_original=alt.get("ordem_original", None),
            feedback_opcao=feedback_opcao_cript,
            imagem_path_opcao=imagem_path_opcao,
            tenant_id=tenant_id,
        )
        db.add(nova_opcao)

    # --------- ITENS VF (CERTO/ERRADO) COM IMAGEM -----------
    item_anteriores = {}
    item_result = await db.execute(
        select(ItensVerdadeiroFalso).where(ItensVerdadeiroFalso.id_questao_fk == id_questao)
    )
    for idx, a in enumerate(item_result.scalars().all()):
        item_anteriores[idx] = a.imagem_path_item

    await db.execute(
        ItensVerdadeiroFalso.__table__.delete().where(ItensVerdadeiroFalso.id_questao_fk == id_questao)
    )

    itens_vf_list = json.loads(itens_vf) if itens_vf else []
    for idx, item in enumerate(itens_vf_list):
        imagem_path_item = None
        item_imagem_file = None
        if idx == 0: item_imagem_file = item_imagem_0
        if idx == 1: item_imagem_file = item_imagem_1
        if idx == 2: item_imagem_file = item_imagem_2
        if idx == 3: item_imagem_file = item_imagem_3
        if idx == 4: item_imagem_file = item_imagem_4
        if idx == 5: item_imagem_file = item_imagem_5
        if idx == 6: item_imagem_file = item_imagem_6
        if idx == 7: item_imagem_file = item_imagem_7
        if idx == 8: item_imagem_file = item_imagem_8
        if idx == 9: item_imagem_file = item_imagem_9

        if item_imagem_file and hasattr(item_imagem_file, "filename") and item_imagem_file.filename:
            imagem_path_item = await secure_files.save_upload_http(item_imagem_file, tenant_id, "image")
        else:
            imagem_path_item = item_anteriores.get(idx)

        afirmacao_cript = encrypt_text(item.get("afirmacao")) if item.get("afirmacao") else None
        feedback_item_cript = encrypt_text(item.get("feedback_item")) if item.get("feedback_item") else None
        novo_item = ItensVerdadeiroFalso(
            id_item_vf=str(uuid.uuid4()),
            id_questao_fk=id_questao,
            afirmacao=afirmacao_cript,
            valor_correto=item.get("valor_correto"),
            feedback_item=feedback_item_cript,
            ordem=item.get("ordem", None),
            imagem_path_item=imagem_path_item,
            tenant_id=tenant_id,
        )
        db.add(novo_item)

    # --------- DETALHES DISCURSIVA / SUBJETIVA -----------
    await db.execute(
        DetalhesQuestaoDiscursiva.__table__.delete().where(DetalhesQuestaoDiscursiva.id_questao_fk == id_questao)
    )
    detalhes_obj = json.loads(detalhes_discursiva) if detalhes_discursiva else {}
    if detalhes_obj:
        resposta_esperada_texto_cript = encrypt_text(detalhes_obj.get("resposta_esperada_texto")) if detalhes_obj.get("resposta_esperada_texto") else None
        palavras_chave_resposta_cript = [encrypt_text(palavra) for palavra in detalhes_obj.get("palavras_chave_resposta", [])]
        texto_subjetivo_orientacao_cript = encrypt_text(detalhes_obj.get("texto_subjetivo_orientacao")) if detalhes_obj.get("texto_subjetivo_orientacao") else None
        texto_subjetivo_nota_maxima_cript = encrypt_text(detalhes_obj.get("texto_subjetivo_nota_maxima")) if detalhes_obj.get("texto_subjetivo_nota_maxima") else None

        novo_detalhe = DetalhesQuestaoDiscursiva(
            id_detalhe_discursiva=str(uuid.uuid4()),
            id_questao_fk=id_questao,
            resposta_esperada_texto=resposta_esperada_texto_cript,
            palavras_chave_resposta=json.dumps(palavras_chave_resposta_cript),
            numero_linhas_resposta=detalhes_obj.get("numero_linhas_resposta"),
            texto_subjetivo_orientacao=texto_subjetivo_orientacao_cript,
            texto_subjetivo_nota_maxima=texto_subjetivo_nota_maxima_cript,
            tenant_id=tenant_id,  # obrigatório: sem ele o RLS recusa a linha
        )
        db.add(novo_detalhe)

    await db.commit()
    await db.refresh(questao)
    saida = await buscar_questao(evento_id, conteudo_id, id_questao, db)
    await versoes_questao.salvar(db, saida, tenant_id, "editada", current_user.username)
    return saida

@router.patch(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}/revisao",
    summary="Salvar revisão da questão e registrar no histórico"
)
async def revisar_questao(
    request: Request,
    evento_id: str,
    conteudo_id: str,
    id_questao: str,
    status_revisao: str = Form(...),
    observacao_revisor: str = Form(""),
    usuario_revisor: str = Form(...),
    dados_revisao: str = Form(...),
    tenant_id: int | None = Form(None),  # ignorado: o tenant vem do evento autorizado
    imagem_enunciado: UploadFile = File(None),
    alternativa_imagem_A: UploadFile = File(None),
    alternativa_imagem_B: UploadFile = File(None),
    alternativa_imagem_C: UploadFile = File(None),
    alternativa_imagem_D: UploadFile = File(None),
    alternativa_imagem_E: UploadFile = File(None),
    # Imagens dos itens VF (ajuste o máximo conforme sua interface/frontend)
    item_imagem_0: UploadFile = File(None),
    item_imagem_1: UploadFile = File(None),
    item_imagem_2: UploadFile = File(None),
    item_imagem_3: UploadFile = File(None),
    item_imagem_4: UploadFile = File(None),
    item_imagem_5: UploadFile = File(None),
    item_imagem_6: UploadFile = File(None),
    item_imagem_7: UploadFile = File(None),
    item_imagem_8: UploadFile = File(None),
    item_imagem_9: UploadFile = File(None),
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.REVISOR, UserRole.ADMIN, UserRole.ADMIN_GERAL)),
):
    tenant_id = evento.tenant_id
    from backend.app.utils_crypto import encrypt_text

    status_revisao = (status_revisao or "").upper()
    if status_revisao not in fluxo_revisao.DECISOES_DO_REVISOR:
        raise HTTPException(status_code=400, detail="Escolha Aprovada, Reprovada ou Solicitar ajustes.")
    revisao = HistoricoRevisaoQuestao(
        id=str(uuid4()),
        id_questao_fk=id_questao,
        usuario_revisor=current_user.username,  # nunca o nome enviado pela tela
        data_revisao=datetime.now(),
        status_revisao=status_revisao,
        observacao_revisor=observacao_revisor,
        dados_revisao=encrypt_text(dados_revisao),
        tenant_id=tenant_id
    )
    db.add(revisao)

    result = await db.execute(
        select(QuestoesBanco).where(
            QuestoesBanco.id_questao == id_questao,
            QuestoesBanco.id_evento_fk == evento_id,
            QuestoesBanco.conteudo_id == conteudo_id
        )
    )
    questao = result.scalar_one_or_none()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")
    await versoes_questao.guardar_estado_anterior(db, await buscar_questao(evento_id, conteudo_id, id_questao, db), tenant_id)

    form = json.loads(dados_revisao)
    caminho_imagem_relativo = questao.caminho_imagem_relativo
    if imagem_enunciado:
        caminho_imagem_relativo = await secure_files.save_upload_http(imagem_enunciado, tenant_id, "image")
    questao.caminho_imagem_relativo = caminho_imagem_relativo
    questao.enunciado = encrypt_text(form.get("enunciado", ""))
    questao.indicacao_conteudo = encrypt_text(form.get("indicacao_conteudo", ""))
    questao.nivel_dificuldade = form.get("nivel_dificuldade", "")
    questao.pontuacao = float(form.get("pontuacao", 1.0))
    questao.tags_keywords = ",".join(form.get("tags", []))
    questao.anulada = form.get("anulada", False)
    questao.justificativa_anulacao = encrypt_text(form.get("justificativa_anulacao", ""))
    questao.justificativa_questao = encrypt_text(form.get("justificativa_questao", ""))
    questao.status_revisao = status_revisao
    questao.observacao_revisor = observacao_revisor
    questao.revisada = True if status_revisao == "APROVADA" else False
    questao.texto_referencia_vinculo = encrypt_text(form.get("texto_referencia_vinculo", ""))
    questao.texto_referencia_direto = encrypt_text(form.get("texto_referencia_direto", ""))
    questao.resposta_correta = encrypt_text(form.get("resposta_correta", ""))
    questao.data_modificacao = datetime.now()
    questao.tenant_id = tenant_id
    db.add(questao)

    # --------- ALTERNATIVAS -----------
    alt_anteriores = {}
    alt_result = await db.execute(
        select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == id_questao)
    )
    for a in alt_result.scalars().all():
        alt_anteriores[a.letra] = a.imagem_path_opcao

    await db.execute(
        OpcoesQuestao.__table__.delete().where(OpcoesQuestao.id_questao_fk == id_questao)
    )

    alternativas = form.get("alternativas", [])
    for alt in alternativas:
        letra = alt.get("letra")
        imagem_file = None
        if letra == "A":
            imagem_file = alternativa_imagem_A
        elif letra == "B":
            imagem_file = alternativa_imagem_B
        elif letra == "C":
            imagem_file = alternativa_imagem_C
        elif letra == "D":
            imagem_file = alternativa_imagem_D
        elif letra == "E":
            imagem_file = alternativa_imagem_E

        if imagem_file and hasattr(imagem_file, "filename") and imagem_file.filename:
            imagem_path_opcao = await secure_files.save_upload_http(imagem_file, tenant_id, "image")
        else:
            imagem_path_opcao = alt_anteriores.get(letra)

        nova_opcao = OpcoesQuestao(
            id_opcao_questao=str(uuid4()),
            id_questao_fk=id_questao,
            letra=letra,
            texto_opcao=encrypt_text(alt.get("texto", "")),
            correta=alt.get("correta", False),
            texto_opcao_formatado=encrypt_text(alt.get("texto_formatado", "")) if alt.get("texto_formatado") else None,
            ordem_original=None,
            feedback_opcao=None,
            imagem_path_opcao=imagem_path_opcao,
            tenant_id=tenant_id,
        )
        db.add(nova_opcao)

    # --------- ITENS VF (CERTO/ERRADO) COM IMAGEM -----------
    # imagens já gravadas dos itens: preservadas quando o revisor não envia uma nova
    item_anteriores = {}
    item_result = await db.execute(
        select(ItensVerdadeiroFalso).where(ItensVerdadeiroFalso.id_questao_fk == id_questao)
    )
    for idx, a in enumerate(item_result.scalars().all()):
        item_anteriores[idx] = a.imagem_path_item

    await db.execute(
        ItensVerdadeiroFalso.__table__.delete().where(ItensVerdadeiroFalso.id_questao_fk == id_questao)
    )

    # A tela sempre envia itens_comando (com [""] por padrão); só questões Certo/Errado têm itens.
    eh_certo_errado = form.get("tipo") == "CERTO_ERRADO"
    itens_comando = form.get("itens_comando", []) if eh_certo_errado else []
    respostas_certo_errado = form.get("respostas_certo_errado", [])
    for idx, afirmacao in enumerate(itens_comando):
        if not afirmacao or afirmacao == "<p></p>":
            continue
        valor_correto = (idx < len(respostas_certo_errado) and respostas_certo_errado[idx] == "CERTO")
        imagem_path_item = item_anteriores.get(idx)
        # Pegue o argumento certo para o item (item_imagem_0, item_imagem_1, ...)
        item_imagem_file = None
        if idx == 0: item_imagem_file = item_imagem_0
        if idx == 1: item_imagem_file = item_imagem_1
        if idx == 2: item_imagem_file = item_imagem_2
        if idx == 3: item_imagem_file = item_imagem_3
        if idx == 4: item_imagem_file = item_imagem_4
        if idx == 5: item_imagem_file = item_imagem_5
        if idx == 6: item_imagem_file = item_imagem_6
        if idx == 7: item_imagem_file = item_imagem_7
        if idx == 8: item_imagem_file = item_imagem_8
        if idx == 9: item_imagem_file = item_imagem_9

        if item_imagem_file and hasattr(item_imagem_file, "filename") and item_imagem_file.filename:
            imagem_path_item = await secure_files.save_upload_http(item_imagem_file, tenant_id, "image")

        novo_item = ItensVerdadeiroFalso(
            id_item_vf=str(uuid4()),
            id_questao_fk=id_questao,
            afirmacao=encrypt_text(afirmacao),
            valor_correto=valor_correto,
            feedback_item=None,
            ordem=idx,
            imagem_path_item=imagem_path_item,
            tenant_id=tenant_id,
        )
        db.add(novo_item)

    # --------- DETALHES DISCURSIVA/SUBJETIVA -----------
    await db.execute(
        DetalhesQuestaoDiscursiva.__table__.delete().where(DetalhesQuestaoDiscursiva.id_questao_fk == id_questao)
    )
    if form.get("tipo") in ("DISCURSIVA", "SUBJETIVA"):
        # num_linhas vem vazio ("") em questões subjetivas: não pode derrubar a revisão
        linhas = str(form.get("num_linhas_discursiva") or "").strip()
        detalhes = {
            "palavras_chave_resposta": [
                encrypt_text(palavra.strip())
                for palavra in str(form.get("palavras_chave_discursiva") or "").split(",")
                if palavra.strip()
            ],
            "numero_linhas_resposta": int(linhas) if linhas.isdigit() else None,
            "texto_subjetivo_orientacao": encrypt_text(form.get("texto_subjetivo_orientacao", "")),
            "texto_subjetivo_nota_maxima": encrypt_text(form.get("texto_subjetivo_nota_maxima", "")),
        }
        novo_detalhe = DetalhesQuestaoDiscursiva(
            id_detalhe_discursiva=str(uuid4()),
            id_questao_fk=id_questao,
            resposta_esperada_texto=None,
            palavras_chave_resposta=json.dumps(detalhes["palavras_chave_resposta"]),
            numero_linhas_resposta=detalhes["numero_linhas_resposta"],
            texto_subjetivo_orientacao=detalhes["texto_subjetivo_orientacao"],
            texto_subjetivo_nota_maxima=detalhes["texto_subjetivo_nota_maxima"],
            tenant_id=tenant_id,
        )
        db.add(novo_detalhe)

    await db.commit()
    await fluxo_revisao.decisao_do_revisor(db, questao, status_revisao, current_user.username)
    await versoes_questao.salvar(db, await buscar_questao(evento_id, conteudo_id, id_questao, db), tenant_id,
                                 f"revisada: {status_revisao.lower()}", current_user.username)
    return {"ok": True}


@router.post(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/importar-docx",
    summary="Importa questões e textos de referência de um DOCX para este conteúdo"
)
async def importar_questoes_docx(
    evento_id: str,
    conteudo_id: str,
    arquivo: UploadFile = File(...),
    tenant_id: int | None = Form(None),  # ignorado: o tenant vem do evento autorizado
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    import tempfile, shutil, os
    from core.docx_parser import DocxParser
    from core.elements import QuestaoType, OpcaoMultiplaEscolha, TextoReferenciaType

    # Salva arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        shutil.copyfileobj(arquivo.file, tmp)
        tmp_path = tmp.name

    # Busca o nome do conteúdo
    conteudo_result = await db.execute(
        select(Conteudo).where(
            Conteudo.id_conteudo == conteudo_id,
            Conteudo.evento_id == evento.id_evento,
            Conteudo.tenant_id == evento.tenant_id,
        )
    )
    conteudo_obj = conteudo_result.scalar_one_or_none()
    if not conteudo_obj:
        os.remove(tmp_path)
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado.")
    disciplina_nome = conteudo_obj.nome_conteudo or "Conteudo"

    # Instancia o parser e faz o parse
    # Imagens extraídas vão para uma pasta temporária privada e, em seguida, para o armazenamento cifrado
    media_dir = tempfile.mkdtemp(prefix="diagpro_docx_")
    parser = DocxParser(
        base_media_dir=media_dir,
        questao_model=QuestaoType,
        opcao_model=OpcaoMultiplaEscolha,
        texto_ref_model=TextoReferenciaType
    )
    questoes, textos_referencia = parser.parse_document(tmp_path, disciplina_nome)
    os.remove(tmp_path)

    # Serialização para preview no mesmo formato da listagem oficial (QuestaoOut)
    def serialize_questao(q):
        def serialize_alt(alt):
            return {
                "letra": getattr(alt, "letra", None) if hasattr(alt, "letra") else alt.get("letra"),
                "texto": getattr(alt, "texto_opcao", None) if hasattr(alt, "texto_opcao") else alt.get("texto"),
                "correta": getattr(alt, "correta", None) if hasattr(alt, "correta") else alt.get("correta"),
            }
        alternativas = getattr(q, "alternativas", None) or getattr(q, "opcoes", [])
        return {
            "id_questao": getattr(q, "id_questao", None),
            "codigo_curto_questao": getattr(q, "codigo_curto_questao", None),
            "enunciado": getattr(q, "enunciado", ""),
            "tipo": getattr(q, "tipo", ""),
            "alternativas": [serialize_alt(alt) for alt in alternativas],
            "itens_vf": getattr(q, "itens_vf", []),
            "detalhes_discursiva": getattr(q, "detalhes_discursiva", {}),
            "resposta_correta": getattr(q, "resposta_correta", ""),
            "nivel_dificuldade": getattr(q, "nivel_dificuldade", None),
            "pontuacao": getattr(q, "pontuacao", 1),
            "revisada": False
        }

    def serialize_texto_ref(t):
        return {
            "id_texto_ref": getattr(t, "id_texto_ref", None),
            "codigo_ref": getattr(t, "codigo_ref", None),
            "titulo": getattr(t, "titulo", getattr(t, "titulo_parser", "")),
            "conteudo": getattr(t, "conteudo", getattr(t, "conteudo_texto_ref", "")),
        }

    resultado = {
        "ok": True,
        "importadas": len(questoes),
        "questoes": [serialize_questao(q) for q in questoes],
        "textos_referencia": [serialize_texto_ref(t) for t in textos_referencia]
    }
    try:
        guardadas: dict[str, str] = {}

        def proteger(v):
            if isinstance(v, dict):
                return {k: proteger(x) for k, x in v.items()}
            if isinstance(v, list):
                return [proteger(x) for x in v]
            if isinstance(v, str) and v and len(v) < 500:
                full = os.path.realpath(os.path.join(media_dir, v))
                if full.startswith(os.path.realpath(media_dir) + os.sep) and os.path.isfile(full):
                    if full not in guardadas:
                        with open(full, "rb") as fh:
                            ref = secure_files.store_bytes(fh.read(), evento.tenant_id, os.path.splitext(full)[1])
                        guardadas[full] = secure_files.signed_url(ref)
                    return guardadas[full]
            return v

        return proteger(resultado)
    finally:
        shutil.rmtree(media_dir, ignore_errors=True)

@router.post(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/importar-docx/confirmar",
    summary="Confirma a importação de questões/textos do preview"
)
async def confirmar_importacao_questoes_docx(
    evento_id: str,
    conteudo_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado)
):
    tenant_id = evento.tenant_id  # ignora tenant_id do corpo
    # Caminhos de arquivo vindos do cliente: só referências cifradas válidas deste cliente sobrevivem
    body = secure_files.sanitize_client_paths(body, tenant_id)
    questoes = body.get("questoes", [])
    textos_referencia = body.get("textos_referencia", [])
    autor_elaborador = body.get("autor_elaborador")

    # Salva textos de referência primeiro (AGORA COM TODOS OS CAMPOS)
    for t in textos_referencia:
        novo_texto = TextoReferenciaGeral(
            id_texto_ref=str(uuid4()),
            codigo_ref=t.get("codigo_ref") or f"TXT-{uuid4().hex[:6].upper()}",
            titulo=t.get("titulo") or "",
            conteudo=t.get("conteudo") or "",
            tipo_conteudo=t.get("tipo_conteudo") or "",
            descricao_imagem=t.get("descricao_imagem") or "",
            fonte_imagem=t.get("fonte_imagem") or "",
            tags_imagem=",".join(t.get("tags_imagem", [])) if isinstance(t.get("tags_imagem"), list) else t.get("tags_imagem") or "",
            licenca_imagem=t.get("licenca_imagem") or "",
            caminho_imagem_relativo=t.get("caminho_imagem_relativo"),
            observacoes=t.get("observacoes") or "",
            ativo=t.get("ativo", True),
            publico=t.get("publico", True),
            metadados_texto_ref=json.dumps(t.get("metadados_texto_ref")) if t.get("metadados_texto_ref") else None,
            questoes_vinculo=",".join(t.get("questoes_vinculo", [])) if isinstance(t.get("questoes_vinculo"), list) else t.get("questoes_vinculo") or "",
            conteudo_formatado=json.dumps(t.get("conteudo_formatado")) if t.get("conteudo_formatado") else None,
            tenant_id=tenant_id,
            id_conteudo_fk=conteudo_id,
            id_evento_fk=evento_id,
            data_criacao=str(datetime.now()),
            data_modificacao=str(datetime.now()),
        )
        db.add(novo_texto)
    await db.commit()

    # Busque o objeto de conteúdo APENAS UMA VEZ
    conteudo_result = await db.execute(
        select(Conteudo).where(
            Conteudo.id_conteudo == conteudo_id,
            Conteudo.evento_id == evento.id_evento,
            Conteudo.tenant_id == evento.tenant_id,
        )
    )
    conteudo_obj = conteudo_result.scalar_one_or_none()

    # Salva questões e alternativas (AGORA COM IMAGENS NAS ALTERNATIVAS)
    for q in questoes:
        codigo_curto = await gerar_codigo_curto(q.get("tipo"), tenant_id, db)
        # Se vier enunciado_formatado, salve como JSON
        enunciado_formatado = q.get("enunciado_formatado", None)
        nova_questao = QuestoesBanco(
            id_questao=str(uuid4()),
            codigo_curto_questao=codigo_curto,
            id_evento_fk=evento_id,
            tenant_id=tenant_id,
            enunciado=encrypt_text(q.get("enunciado")),
            enunciado_formatado=json.dumps(enunciado_formatado) if enunciado_formatado else None,
            tipo=q.get("tipo"),
            resposta_correta=encrypt_text(q.get("resposta_correta")),
            pontuacao=q.get("pontuacao", 1),
            nivel_dificuldade=q.get("nivel_dificuldade"),
            conteudo_id=conteudo_id,
            conteudo_nome=None,
            data_criacao=datetime.now(),
            data_modificacao=datetime.now(),
        )
        db.add(nova_questao)
        await db.flush()

        alternativas_list = q.get("alternativas", [])
        if isinstance(alternativas_list, str):
            try:
                alternativas_list = ast.literal_eval(alternativas_list)
            except Exception:
                alternativas_list = []
        for alt in alternativas_list:
            texto_opcao_formatado = alt.get("texto_formatado") if "texto_formatado" in alt else None
            nova_opcao = OpcoesQuestao(
                id_opcao_questao=str(uuid4()),
                id_questao_fk=nova_questao.id_questao,
                letra=alt.get("letra"),
                texto_opcao=encrypt_text(alt.get("texto") or alt.get("texto_opcao") or ""),
                texto_opcao_formatado=json.dumps(texto_opcao_formatado) if texto_opcao_formatado else None,
                correta=alt.get("correta", False),
                imagem_path_opcao=alt.get("imagem_path_opcao"),
                tenant_id=tenant_id,
            )
            db.add(nova_opcao)

    await db.commit()
    return {"ok": True, "msg": "Importação confirmada!"}


@router.get(
    "/eventos/{evento_id}/conteudos/{conteudo_id}/questoes/{id_questao}/revisoes",
    summary="Listar revisões de uma questão"
)
async def listar_revisoes_questao(
    evento_id: str,
    conteudo_id: str,
    id_questao: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento=Depends(evento_autorizado),
):
    questao_existe = await db.execute(
        select(QuestoesBanco.id_questao).where(
            QuestoesBanco.id_questao == id_questao,
            QuestoesBanco.id_evento_fk == evento.id_evento,
            QuestoesBanco.conteudo_id == conteudo_id,
        )
    )
    if questao_existe.first() is None:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")

    result = await db.execute(
        select(HistoricoRevisaoQuestao)
        .where(HistoricoRevisaoQuestao.id_questao_fk == id_questao)
        .order_by(HistoricoRevisaoQuestao.data_revisao.asc())
    )
    revisoes = result.scalars().all()
    # Se quiser retornar só um resumo:
    return [
        {
            "id": r.id,
            "usuario_revisor": r.usuario_revisor,
            "data_revisao": r.data_revisao,
            "status_revisao": r.status_revisao,
            "observacao_revisor": r.observacao_revisor,
        }
        for r in revisoes
    ]