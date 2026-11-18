from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.security import get_tenant_db, is_admin_geral, require_roles
from backend.app.jobs import create_job, get_job_for_tenant, update_job
from backend.app.rate_limit import rate_limit
from backend.app.roles import UserRole
from backend.app.db_models import (
    Evento as DBEvento,
    Cargo as DBCargo,
    ProvaMontada as DBProvaMontada,
    OpcoesQuestao,
    TextoReferenciaGeral,  # IMPORTANTE: adicionado!
)
import datetime
import tempfile
from fastapi import BackgroundTasks
from backend.app.auth import get_current_user
from backend.app.security import carregar_evento_autorizado, caminho_dentro_de
import os
import hmac
import json
import logging
import pprint
import sys
import re
import shutil
import time
import zipfile
import pyzipper
from pypdf import PdfWriter

from backend.app.utils_crypto import decrypt_text
from backend.app.campos_capa import montar_dados_capa
from backend.app.db_models import Evento

from core.document_generator import DocumentGenerator
import core.elements as elements

logging.basicConfig(
    level=logging.DEBUG,  # DEBUG, INFO, WARNING, ERROR
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("exportacao")

router = APIRouter()

document_generator = DocumentGenerator(
    templates_base_dir="templates",
    logger=logging.getLogger("DocumentGenerator"),
    core_elements_module=elements
)

async def get_output_dir(evento_id, cargo_id, db: AsyncSession):
    from backend.app.db_models import Evento as DBEvento
    from sqlalchemy.future import select

    evento_result = await db.execute(select(DBEvento).where(DBEvento.id_evento == evento_id))
    evento = evento_result.scalar_one_or_none()
    if not evento:
        raise Exception("Evento não encontrado")
    base_dir = os.path.realpath("ProvasGeradas_DG")
    nome_evento = re.sub(r"[^A-Za-z0-9_.-]", "_", evento.nome_evento.strip().replace(" ", "_"))
    safe_cargo_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(cargo_id))
    output_dir = os.path.realpath(os.path.join(base_dir, nome_evento, safe_cargo_id))
    if not output_dir.startswith(base_dir + os.sep):
        raise HTTPException(status_code=400, detail="Caminho de saída inválido.")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

@router.post("/eventos/{evento_id}/validar-senha", dependencies=[Depends(rate_limit(5, 60, "validar-senha"))])
async def validar_senha_evento(
    evento_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    body = await request.json()
    senha_usuario = body.get("senha", "")
    if not senha_usuario:
        return {"valida": False}

    query = select(DBEvento).where(DBEvento.id_evento == evento_id)
    if current_user.tenant_id is not None:
        query = query.where(DBEvento.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    evento = result.scalar_one_or_none()
    if not evento:
        return {"valida": False}

    senha_evento_cripto = getattr(evento, "senha_evento_cripto", "")
    if not senha_evento_cripto:
        return {"valida": False}
    senha_evento = decrypt_text(senha_evento_cripto)
    return {"valida": hmac.compare_digest(senha_usuario, senha_evento)}


async def fetch_evento_cargo_prova(
    evento_id: str,
    cargo_id: str,
    db: AsyncSession,
    tenant_id: int
):
    evento_result = await db.execute(
        select(DBEvento).where(DBEvento.id_evento == evento_id, DBEvento.tenant_id == tenant_id)
    )
    evento = evento_result.scalar_one_or_none()
    if not evento:
        raise HTTPException(404, "Evento não encontrado")

    cargo_result = await db.execute(
        select(DBCargo).where(DBCargo.id_cargo == cargo_id, DBCargo.tenant_id == tenant_id)
    )
    cargo = cargo_result.scalar_one_or_none()
    if not cargo:
        raise HTTPException(404, "Cargo não encontrado")

    prova_result = await db.execute(
        select(DBProvaMontada).where(
            DBProvaMontada.id_evento_fk == evento_id,
            DBProvaMontada.id_cargo_fk == cargo_id,
            DBProvaMontada.tenant_id == tenant_id,
        )
    )
    prova_montada = prova_result.scalar_one_or_none()
    if not prova_montada:
        raise HTTPException(404, "Prova montada não encontrada para este cargo")

    # Conversão de campos json
    blocos_questoes = prova_montada.blocos_questoes
    if isinstance(blocos_questoes, str):
        try:
            blocos_questoes = json.loads(blocos_questoes)
        except Exception:
            blocos_questoes = []
    metadados_prova = prova_montada.metadados_prova
    if isinstance(metadados_prova, str):
        try:
            metadados_prova = json.loads(metadados_prova)
        except Exception:
            metadados_prova = {}

    return evento, cargo, prova_montada, blocos_questoes, metadados_prova

async def montar_prova_completa(evento, cargo, prova_montada, blocos_questoes, metadados_prova, db):
    evento_dict = {
        "id_evento": evento.id_evento,
        "nome_evento": getattr(evento, "nome_evento", ""),
        "data_prova": str(getattr(evento, "data_prova", "")),
        "numero_edital": getattr(evento, "numero_edital", ""),
    }
    cargo_dict = {
        "id_cargo": cargo.id_cargo,
        "nome_cargo": getattr(cargo, "nome_cargo", ""),
        "codigo_cargo": getattr(cargo, "codigo_cargo", ""),
    }
    print(">>> ENTROU NA FUNÇÃO montar_prova_completa <<<")
    # --- PATCH: Adiciona company com o logo ao cargo_dict ---
    from backend.app.db_models import Company
    from sqlalchemy.future import select
    tenant_id = getattr(evento, "tenant_id", None) or getattr(cargo, "tenant_id", None)
    company = None
    if tenant_id:
        company_result = await db.execute(select(Company).where(Company.tenant_id == tenant_id))
        company = company_result.scalar_one_or_none()
        if company:
            cargo_dict["company"] = {
                "company_logo_path": company.company_logo_path or ""
            }
        else:
            cargo_dict["company"] = {"company_logo_path": ""}
    else:
        cargo_dict["company"] = {"company_logo_path": ""}
    # --- FIM PATCH LOGO ---
    print("DEBUG cargo_dict final:", cargo_dict)

    # Preenche alternativas se necessário
    for bloco in blocos_questoes:
        questoes = bloco.get("questoes") or bloco.get("questions") or []
        for questao in questoes:
            # PATCH: Garante que codigo_curto_questao esteja presente
            if "codigo_curto_questao" not in questao:
                # Tenta buscar do banco se tiver id_questao, senão coloca ""
                id_questao = questao.get("id_questao")
                if id_questao:
                    # Busca do banco (async)
                    from backend.app.db_models import QuestoesBanco
                    result = await db.execute(
                        select(QuestoesBanco.codigo_curto_questao).where(QuestoesBanco.id_questao == id_questao)
                    )
                    codigo_curto = result.scalar_one_or_none()
                    questao["codigo_curto_questao"] = codigo_curto or ""
                else:
                    questao["codigo_curto_questao"] = ""

            opcoes = questao.get("opcoes") or questao.get("alternativas")
            if not opcoes:
                id_questao = questao.get("id_questao")
                if id_questao:
                    opcoes_result = await db.execute(
                        select(OpcoesQuestao).where(OpcoesQuestao.id_questao_fk == id_questao)
                    )
                    novas_opcoes = []
                    for op in opcoes_result.scalars():
                        op_dict = {
                            "id_opcao_questao": op.id_opcao_questao,
                            "letra": op.letra,
                            "texto_opcao": op.texto_opcao,
                            "texto_opcao_formatado": op.texto_opcao_formatado,
                            "correta": op.correta,
                            "ordem_original": op.ordem_original,
                            "imagem_path_opcao": op.imagem_path_opcao,
                            "feedback_opcao": op.feedback_opcao,
                        }
                        novas_opcoes.append(op_dict)
                    questao["opcoes"] = novas_opcoes

    # --- NOVO: monta textos_referencia_prova usando questoes_vinculo ---
    ids_questoes_na_prova = set()
    for bloco in blocos_questoes:
        questoes = bloco.get("questoes") or bloco.get("questions") or []
        for questao in questoes:
            id_questao = questao.get("id_questao")
            if id_questao:
                ids_questoes_na_prova.add(str(id_questao))

    # Busca todos os textos de referência do evento
    textos_query = await db.execute(
        select(TextoReferenciaGeral).where(TextoReferenciaGeral.id_evento_fk == evento.id_evento)
    )
    textos_objs = textos_query.scalars().all()

    textos_referencia_prova = []
    for t in textos_objs:
        if not t.questoes_vinculo:
            continue
        questoes_ligadas = set(q.strip() for q in t.questoes_vinculo.split(",") if q.strip())
        if ids_questoes_na_prova & questoes_ligadas:
            textos_referencia_prova.append({
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
            })

    prova_dict = {
        "id_prova_montada": prova_montada.id_prova_montada,
        "nome_prova_montada": getattr(prova_montada, "nome_prova_montada", ""),
        "blocos_questoes": blocos_questoes,
        "metadados_prova": metadados_prova,
        "textos_referencia_prova": textos_referencia_prova,
        "evento": evento_dict,
        "cargo": cargo_dict,
    }
    return prova_dict

@router.get("/eventos/{evento_id}/cargos/{cargo_id}/exportacoes")
async def listar_arquivos_exportaveis(
    evento_id: str,
    cargo_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    output_dir = await get_output_dir(evento_id, cargo_id, db)
    arquivos = []
    tipos = [
        ("prova_pdf", "pdf", "Prova PDF"),
        ("prova_docx", "docx", "Prova DOCX"),
        ("gabarito", "csv", "Gabarito CSV"),
        ("zip", "zip", "Pacote ZIP"),
    ]
    nomes = {
        "prova_pdf": f"Prova_{cargo_id}.pdf",
        "prova_docx": f"Prova_{cargo_id}.docx",
        "gabarito": f"Gabarito_{cargo_id}.csv",
        "zip": f"Pacote_{cargo_id}.zip",
    }
    for tipo, ext, label in tipos:
        nome = nomes[tipo]
        caminho = os.path.join(output_dir, nome)
        if os.path.exists(caminho):
            arquivos.append({
                "nome_arquivo": nome,
                "tipo": tipo,
                "label": label,
                "url": f"/api/export/download?evento_id={evento_id}&cargo_id={cargo_id}&tipo={tipo}"
            })
    return arquivos

@router.get("/download")
async def baixar_arquivo(
    evento_id: str = Query(...),
    cargo_id: str = Query(...),
    tipo: str = Query(..., description="prova_pdf, prova_docx, gabarito, zip"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    logger.debug("=== CHEGOU NO ENDPOINT baixar_arquivo ===")
    import sys
    print("sys.stdout.isatty:", sys.stdout.isatty())
    import logging
    logging.warning("=== LOGGING FUNCIONA AQUI? ===")
    output_dir = await get_output_dir(evento_id, cargo_id, db)
    evento, cargo, prova_montada, blocos_questoes, metadados_prova = await fetch_evento_cargo_prova(
        evento_id, cargo_id, db, current_user.tenant_id
    )
    prova_dict = await montar_prova_completa(evento, cargo, prova_montada, blocos_questoes, metadados_prova, db)
    nome_cargo = cargo.nome_cargo
    textos_map = {}

    if tipo == "prova_pdf":
        filename = f"Prova_{cargo_id}_COM_CAPA.pdf"
        caminho_arquivo = os.path.join(output_dir, filename)
        # SEM CHECAR se arquivo já existe — sempre gera do zero!
        docx_path = document_generator.gerar_prova_docx(
            prova_montada=prova_dict,
            nome_cargo=nome_cargo,
            variacao_num=1,
            output_folder=output_dir,
            format_options={},
            textos_map=textos_map
        )
        pdf_path = document_generator.pdf_converter.convert_to_pdf(docx_path, output_dir)
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(500, "Falha ao gerar PDF")

        # PATCH PARA CAPA — sempre executa
        print("=" * 70)
        print("INÍCIO DO PATCH PARA CAPA")

        cover_pdf_paths = getattr(cargo, 'cover_pdf_paths', None)
        logger.debug("cover_pdf_paths (raw): %s", repr(cover_pdf_paths))

        def resolve_capa_template_path(cover_pdf_paths):
            print("Entrou em resolve_capa_template_path")
            if isinstance(cover_pdf_paths, str):
                try:
                    paths = json.loads(cover_pdf_paths)
                    print("[DEBUG] Parsed paths from JSON:", paths)
                    if isinstance(paths, str):
                        paths = [paths]
                except Exception as e:
                    print("[DEBUG] Exception parsing cover_pdf_paths:", e)
                    paths = [cover_pdf_paths]
            elif isinstance(cover_pdf_paths, list):
                print("[DEBUG] cover_pdf_paths já é lista:", cover_pdf_paths)
                paths = cover_pdf_paths
            else:
                print("[DEBUG] cover_pdf_paths é outro tipo:", type(cover_pdf_paths))
                paths = []
            if paths:
                template_path = os.path.normpath(paths[0])
                print("[DEBUG] template_path normpath:", template_path)
                if not os.path.isabs(template_path):
                    template_path = os.path.abspath(template_path)
                    print("[DEBUG] template_path abspath:", template_path)
                print("[DEBUG] template_path exists:", os.path.exists(template_path))
                return template_path
            print("[DEBUG] paths está vazio")
            return None

        template_folha_rosto_pdf = resolve_capa_template_path(cover_pdf_paths)
        logger.debug("template_folha_rosto_pdf: %s", template_folha_rosto_pdf)
        logger.debug("template_folha_rosto_pdf exists: %s", os.path.exists(template_folha_rosto_pdf) if template_folha_rosto_pdf else None)


        dir_capas_java = os.path.join(output_dir, "CapasPreenchidas")
        try:
            os.makedirs(dir_capas_java, exist_ok=True)
            logger.debug("Pasta CapasPreenchidas criada? %s -> %s", os.path.exists(dir_capas_java), dir_capas_java)
        except Exception as e:
            logger.error("ERRO ao criar pasta CapasPreenchidas: %s", e)

        if template_folha_rosto_pdf and os.path.exists(template_folha_rosto_pdf):
            logger.debug(">>>>> ENTROU NO BLOCO DE CAPA <<<<<")
            dados_para_capa = [{
                "Inscricao": "PROVA_UNICA",
                "NomeCandidato": "",
                "CodigoCargo": getattr(cargo, "codigo_cargo", ""),
                "NomeCargo": getattr(cargo, "nome_cargo", ""),
                "Frase": "",
                "DataProva": datetime.datetime.now().strftime("%d/%m/%Y"),
            }]
            json_capa_path = os.path.join(dir_capas_java, "dados_capa_prova_unica.json")
            with open(json_capa_path, "w", encoding="utf-8") as f:
                json.dump(dados_para_capa, f, ensure_ascii=False, indent=2)
            def preencher_capas_java(template_pdf, dados_json, saida_dir):
                import subprocess
                comando = [
                    "java", "-cp",
                    "backend/app/pdfbox-app-3.0.5.jar;backend/app/json.jar;backend/app",
                    "PreencheCapaPDF_JSON_PDFBox",
                    template_pdf,
                    dados_json,
                    saida_dir
                ]
                logger.debug("Comando JAVA: %s", " ".join(comando))
                resultado = subprocess.run(comando, capture_output=True, text=True)
                logger.info("[JAVA STDOUT]: %s", resultado.stdout.strip())
                logger.debug("[JAVA STDERR]: %s", resultado.stderr)
                return resultado.returncode == 0

            preencher_capas_java(template_folha_rosto_pdf, json_capa_path, dir_capas_java)
            path_capa_pdf = os.path.join(dir_capas_java, "PROVA_UNICA_capa.pdf")
            logger.debug("Arquivo da capa preenchida: %s", path_capa_pdf)
            logger.debug("Capa existe? %s", os.path.exists(path_capa_pdf))
            logger.debug("Arquivos na pasta de capas: %s", os.listdir(dir_capas_java))
            if os.path.exists(path_capa_pdf):
                from pypdf import PdfWriter
                merger = PdfWriter()
                merger.append(path_capa_pdf)
                merger.append(pdf_path)
                logger.debug("Merge: capa = %s corpo = %s saida = %s", path_capa_pdf, pdf_path, caminho_arquivo)
                with open(caminho_arquivo, "wb") as f_out:
                    merger.write(f_out)
                logger.debug("PDF final com capa gerado: %s", caminho_arquivo)
            else:
                logger.debug("Capa não gerada! PDF sairá sem capa.")
                caminho_arquivo = pdf_path
        else:
            logger.debug(">>>>> BLOCO DE CAPA NÃO EXECUTADO. <<<<<")
            logger.debug("Template da capa não encontrado! PDF sairá sem capa.")
            caminho_arquivo = pdf_path

        logger.debug("=" * 70)

    elif tipo == "prova_docx":
        filename = f"Prova_{cargo_id}.docx"
        caminho_arquivo = os.path.join(output_dir, filename)
        docx_path = document_generator.gerar_prova_docx(
            prova_montada=prova_dict,
            nome_cargo=nome_cargo,
            variacao_num=1,
            output_folder=output_dir,
            format_options={},
            textos_map=textos_map
        )
        if not docx_path or not os.path.exists(docx_path):
            raise HTTPException(500, "Falha ao gerar DOCX")
        caminho_arquivo = docx_path

    elif tipo == "gabarito":
        filename = f"Gabarito_{cargo_id}.csv"
        caminho_arquivo = os.path.join(output_dir, filename)
        gabaritos = document_generator.gerar_gabaritos_balanceados_por_variacao(prova_dict)
        if not gabaritos:
            raise HTTPException(404, "Falha ao gerar gabaritos")
        document_generator.answer_key_generator.generate_simple_row_based_csv(
            filepath=caminho_arquivo,
            cargo_obj=cargo,
            gabaritos_por_variacao=gabaritos
        )

    elif tipo == "zip":
        filename = f"Pacote_{cargo_id}.zip"
        caminho_arquivo = os.path.join(output_dir, filename)
        pdf_path = os.path.join(output_dir, f"Prova_{cargo_id}_COM_CAPA.pdf")
        if not os.path.exists(pdf_path):
            # Gera o PDF com capa do zero!
            docx_path = document_generator.gerar_prova_docx(
                prova_montada=prova_dict,
                nome_cargo=nome_cargo,
                variacao_num=1,
                output_folder=output_dir,
                format_options={},
                textos_map=textos_map
            )
            pdf_path = document_generator.pdf_converter.convert_to_pdf(docx_path, output_dir)
            # PATCH PARA CAPA pode ser chamado aqui também se quiser garantir
        gabarito_path = os.path.join(output_dir, f"Gabarito_{cargo_id}.csv")
        if not os.path.exists(gabarito_path):
            gabaritos = document_generator.gerar_gabaritos_balanceados_por_variacao(prova_dict)
            document_generator.answer_key_generator.generate_simple_row_based_csv(
                filepath=gabarito_path,
                cargo_obj=cargo,
                gabaritos_por_variacao=gabaritos
            )
        files = [
            f for f in [
                pdf_path,
                gabarito_path,
            ] if f and os.path.exists(f)
        ]
        if not files:
            raise HTTPException(404, "Nada para zipar")
        document_generator.archive_manager.create_zip(
            file_paths=files,
            output_zip_path=caminho_arquivo
        )
    else:
        raise HTTPException(400, "Tipo de arquivo não suportado")

    if not os.path.exists(caminho_arquivo):
        raise HTTPException(404, "Arquivo não encontrado")

    media_types = {
        "prova_pdf": "application/pdf",
        "prova_docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "gabarito": "text/csv",
        "zip": "application/zip",
    }
    return FileResponse(
        path=caminho_arquivo,
        filename=os.path.basename(caminho_arquivo),
        media_type=media_types.get(tipo, "application/octet-stream")
    )

@router.post("/eventos/{evento_id}/cargos/{cargo_id}/gerar-arquivos")
async def gerar_todos_arquivos(
    evento_id: str,
    cargo_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    import os, json, time, shutil
    from pypdf import PdfWriter

    body = await request.json()
    fonte = body.get("fonte", "Calibri")
    tamanhoFonte = body.get("tamanhoFonte", 12)
    duasColunas = body.get("duasColunas", False)
    quebraBloco = body.get("quebraBloco", True)
    manterDocx = body.get("manterDocx", True)
    template = body.get("template", None)
    exibir_codigo_curto_questao = body.get("exibir_codigo_curto_questao", False)
    exibir_gabarito_marcado = body.get("exibir_gabarito_marcado", False)

    if template:
        path_template = os.path.join("templates_eventos", str(evento_id), template)
    else:
        path_template = None

    format_options = {
        "fonte_principal": fonte,
        "tamanho_fonte_principal": tamanhoFonte,
        "duas_colunas": duasColunas,
        "quebra_de_pagina_por_bloco": quebraBloco,
        "manter_arquivos_docx_individuais": manterDocx,
        "template_path": path_template,
        "exibir_codigo_curto_questao": exibir_codigo_curto_questao,
        "exibir_gabarito_marcado": exibir_gabarito_marcado,
    }

    output_dir = await get_output_dir(evento_id, cargo_id, db)
    evento, cargo, prova_montada, blocos_questoes, metadados_prova = await fetch_evento_cargo_prova(
        evento_id, cargo_id, db, current_user.tenant_id
    )
    prova_dict = await montar_prova_completa(evento, cargo, prova_montada, blocos_questoes, metadados_prova, db)
    nome_cargo = cargo.nome_cargo
    codigo_cargo = getattr(cargo, "codigo_cargo", "")
    textos_map = {}

    num_variacoes = metadados_prova.get("definicao_geracao", {}).get("num_variacoes", 1)
    docx_paths = []
    pdf_paths = []

    cover_pdf_paths = getattr(cargo, 'cover_pdf_paths', None)
    def resolve_capa_template_path(cover_pdf_paths):
        if isinstance(cover_pdf_paths, str):
            try:
                paths = json.loads(cover_pdf_paths)
                if isinstance(paths, str):
                    paths = [paths]
            except Exception:
                paths = [cover_pdf_paths]
        elif isinstance(cover_pdf_paths, list):
            paths = cover_pdf_paths
        else:
            paths = []
        if paths:
            template_path = os.path.normpath(paths[0])
            if not os.path.isabs(template_path):
                template_path = os.path.abspath(template_path)
            return template_path
        return None

    template_folha_rosto_pdf = resolve_capa_template_path(cover_pdf_paths)
    print(f"[LOG] Template capa: {template_folha_rosto_pdf} existe? {os.path.exists(template_folha_rosto_pdf) if template_folha_rosto_pdf else False}")
    dir_capas_java = os.path.join(output_dir, "CapasPreenchidas")
    os.makedirs(dir_capas_java, exist_ok=True)

    def preencher_capas_java(template_pdf, dados_json, saida_dir):
        import subprocess
        comando = [
            "java", "-cp",
            "backend/app/pdfbox-app-3.0.5.jar;backend/app/json.jar;backend/app",
            "PreencheCapaPDF_JSON_PDFBox",
            template_pdf,
            dados_json,
            saida_dir
        ]
        print(f"[LOG] Comando Java: {' '.join(str(x) for x in comando)}")
        print(f"[LOG] Template existe? {os.path.exists(template_pdf)}")
        print(f"[LOG] JSON existe? {os.path.exists(dados_json)}")
        with open(dados_json, "r", encoding="utf-8") as fj:
            print(f"[LOG] Conteúdo JSON capa:\n{fj.read()}")
        resultado = subprocess.run(comando, capture_output=True, text=True)
        print(f"[JAVA STDOUT]: {resultado.stdout}")
        print(f"[JAVA STDERR]: {resultado.stderr}")
        print(f"[LOG] Pasta saída ({saida_dir}): {os.listdir(saida_dir)}")
        return resultado.returncode == 0

    for variacao_num in range(1, num_variacoes + 1):
        tipo_letra = chr(ord('A') + variacao_num - 1) if num_variacoes > 1 else ""
        sufixo_tipo = f"Tipo {tipo_letra}" if tipo_letra else "PADRÃO"
        tipo_so_letra = tipo_letra or "PADRÃO"

        tipo_prova_nome = f"Tipo {tipo_letra}" if tipo_letra else "PADRÃO"
        if isinstance(prova_dict, dict):
            prova_dict["identificador_prova"] = tipo_prova_nome
        else:
            setattr(prova_dict, "identificador_prova", tipo_prova_nome)

        frase_para_capa = metadados_prova.get("frases_por_tipo_prova", {}).get(sufixo_tipo, "")
        dados_para_capa = [montar_dados_capa(
            candidato={},
            cargo=cargo,
            evento=evento,
            prova=prova_montada,
            frase=frase_para_capa,
            tipo=sufixo_tipo,
            letra_tipo=tipo_letra,
            tempo_prova="",
            quantidade_questoes="",
            empresa="NOME DA BANCA",
            qrcode="",
            outros=""
        )]
        json_capa_path = os.path.join(dir_capas_java, f"dados_capa_{tipo_so_letra}.json")
        with open(json_capa_path, "w", encoding="utf-8") as f:
            json.dump(dados_para_capa, f, ensure_ascii=False, indent=2)

        preencher_capas_java(template_folha_rosto_pdf, json_capa_path, dir_capas_java)

        capa_pdf_antes = set([fn for fn in os.listdir(dir_capas_java) if fn.endswith('.pdf')])
        timeout, interval = 5, 0.1
        found = None
        for _ in range(int(timeout / interval)):
            time.sleep(interval)
            arquivos = [fn for fn in os.listdir(dir_capas_java) if fn.endswith('.pdf')]
            novos = set(arquivos) - capa_pdf_antes
            if novos:
                found = novos.pop()
                break
            for nome in ["PROVA_UNICA_capa.pdf", "_capa.pdf"]:
                if nome in arquivos:
                    found = nome
                    break
            if found:
                break

        if found and os.path.exists(os.path.join(dir_capas_java, found)):
            path_capa_pdf_origem = os.path.join(dir_capas_java, found)
            nome_capa_pdf_final = f"{codigo_cargo} - {nome_cargo.replace(' ', '_')} - Tipo_{tipo_so_letra}_capa.pdf"
            path_capa_pdf_final = os.path.join(dir_capas_java, nome_capa_pdf_final)
            shutil.copy2(path_capa_pdf_origem, path_capa_pdf_final)
            print(f"[ROBUSTO] Capa salva para tipo: {path_capa_pdf_final}")
        else:
            print(f"[ERRO] Não foi gerada a capa para {tipo_so_letra}. Lista atual: {os.listdir(dir_capas_java)}")
            raise Exception(f"Capa não foi gerada para {tipo_so_letra}! O Java falhou?")

        docx_path = document_generator.gerar_prova_docx(
            prova_montada=prova_dict,
            nome_cargo=nome_cargo,
            variacao_num=variacao_num,
            output_folder=output_dir,
            format_options=format_options,
            textos_map=textos_map
        )
        docx_paths.append(docx_path)
        pdf_path = document_generator.pdf_converter.convert_to_pdf(docx_path, output_dir) if docx_path else None

        nome_prova_final = f"{codigo_cargo} - {nome_cargo.replace(' ', '_')} - Tipo_{tipo_so_letra}.pdf"
        caminho_pdf_final = os.path.join(output_dir, nome_prova_final)

        if path_capa_pdf_final and os.path.exists(path_capa_pdf_final) and pdf_path and os.path.exists(pdf_path):
            merger = PdfWriter()
            merger.append(path_capa_pdf_final)
            merger.append(pdf_path)
            with open(caminho_pdf_final, "wb") as f_out:
                merger.write(f_out)
            print("[DEBUG] PDF final com capa gerado:", caminho_pdf_final)
            pdf_paths.append(caminho_pdf_final)
        else:
            print(f"[ERRO] Não foi possível mesclar capa ({tipo_so_letra})! PDF sairá sem capa.")
            if pdf_path:
                pdf_paths.append(pdf_path)

    # Apenas retorna os caminhos dos arquivos criados, não faz ZIP nem apaga arquivos!
    return {
        "docx": docx_paths if manterDocx else [],
        "pdf": pdf_paths
    }


@router.get("/debug_export_ping")
async def debug_export_ping():
    print(">>> CHEGOU NO /api/export/debug_export_ping <<<")
    return {"ok": True}


@router.post("/eventos/{evento_id}/cargos/{cargo_id}/exportar-gabarito")
async def exportar_gabarito(
    evento_id: str,
    cargo_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    import os
    # Carrega dados necessários do banco
    evento, cargo, prova_montada, blocos_questoes, metadados_prova = await fetch_evento_cargo_prova(
        evento_id, cargo_id, db, current_user.tenant_id
    )
    prova_dict = await montar_prova_completa(evento, cargo, prova_montada, blocos_questoes, metadados_prova, db)

    output_dir = await get_output_dir(evento_id, cargo_id, db)
    os.makedirs(output_dir, exist_ok=True)
    gabarito_path = os.path.join(output_dir, f"Gabarito_{cargo_id}.csv")

    # Gera gabarito balanceado de todas as variações
    gabaritos_por_variacao = document_generator.gerar_gabaritos_balanceados_por_variacao(prova_dict)

    if not gabaritos_por_variacao:
        return {"erro": "Não foi possível gerar o gabarito. Verifique os dados da prova."}

    # Gera o CSV
    document_generator.answer_key_generator.generate_simple_row_based_csv(
        filepath=gabarito_path,
        cargo_obj=cargo,
        gabaritos_por_variacao=gabaritos_por_variacao
    )

    # (Opcional) Retorne o caminho, ou envie o arquivo como download
    return {
        "gabarito": gabarito_path if os.path.exists(gabarito_path) else None
    }


async def zip_provas_cargos_selecionados(
    evento_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    result = await db.execute(select(Evento).where(Evento.id_evento == evento_id))
    evento = result.scalar_one_or_none()
    senha_evento_cripto = getattr(evento, "senha_evento_cripto", "")
    senha_evento = decrypt_text(senha_evento_cripto)
    
    if not evento:
        return {"erro": "Evento não encontrado."}
    nome_evento = evento.nome_evento.strip().replace(" ", "_")

    body = await request.json()
    cargos_id = body.get("cargos_id", [])
    manter_docx = body.get("manterDocx", False)
    if not cargos_id:
        return {"erro": "Nenhum cargo selecionado."}

    base_dir = os.path.join("ProvasGeradas_DG", nome_evento)
    arquivos_para_zip = []
    padrao_pdf = r"^\d+\s*-\s*[^-]+-\s*Tipo_([A-Z]|PADRAO|PADRÃO)\.pdf$"

    for cargo_id in cargos_id:
        dir_cargo = os.path.join(base_dir, cargo_id)
        if not os.path.isdir(dir_cargo):
            continue

        # Buscar código e nome do cargo do banco
        cargo_result = await db.execute(select(DBCargo).where(DBCargo.id_cargo == cargo_id))
        cargo_obj = cargo_result.scalar_one_or_none()
        if cargo_obj:
            codigo_cargo = str(getattr(cargo_obj, "codigo_cargo", cargo_id))
            nome_cargo = getattr(cargo_obj, "nome_cargo", cargo_id)
        else:
            codigo_cargo = cargo_id
            nome_cargo = cargo_id
        nome_pasta_cargo = f"{codigo_cargo}_{nome_cargo.replace(' ', '_')}".replace('/', '_')

        # PDFs finais (sempre vão!)
        for file in os.listdir(dir_cargo):
            file_path = os.path.join(dir_cargo, file)
            if (
                file.lower().endswith('.pdf')
                and re.match(padrao_pdf, file, re.IGNORECASE)
            ):
                arcname = f"{nome_pasta_cargo}/{file}"
                arquivos_para_zip.append((file_path, arcname))

        if manter_docx:
            # DOCX (opcional)
            for file in os.listdir(dir_cargo):
                if file.lower().endswith('.docx'):
                    file_path = os.path.join(dir_cargo, file)
                    arcname = f"{nome_pasta_cargo}/{file}"
                    arquivos_para_zip.append((file_path, arcname))
            # CapasPreenchidas (opcional)
            dir_capas = os.path.join(dir_cargo, "CapasPreenchidas")
            if os.path.isdir(dir_capas):
                for root, dirs, files in os.walk(dir_capas):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(
                            nome_pasta_cargo,
                            os.path.relpath(file_path, dir_cargo)
                        )
                        arquivos_para_zip.append((file_path, arcname))

    if not arquivos_para_zip:
        return {"erro": "Nenhum arquivo encontrado para os cargos selecionados."}

    # Cria ZIP em arquivo temporário
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmpzip:
        with pyzipper.AESZipFile(tmpzip, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
            zipf.setpassword(senha_evento.encode('utf-8'))
            for file_path, arcname in arquivos_para_zip:
                zipf.write(file_path, arcname=arcname)
        tmpzip_path = tmpzip.name

    # Remove o arquivo temporário após download
    def remover_arquivo_tmp(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f'[WARN] Não foi possível apagar o ZIP temporário: {path} - {e}')

    background_tasks.add_task(remover_arquivo_tmp, tmpzip_path)

    return FileResponse(
        tmpzip_path,
        filename=f"Provas_{nome_evento}.zip",
        media_type="application/zip",
        background=background_tasks,
    )

import shutil

def limpar_pasta_evento(nome_evento):
    """
    Remove toda a pasta do evento após exportação:
    ProvasGeradas_DG/<nome_evento>
    """
    dir_evento = os.path.join("ProvasGeradas_DG", nome_evento)
    try:
        if os.path.isdir(dir_evento):
            shutil.rmtree(dir_evento)
            print(f"[CLEANUP] Apagou pasta do evento: {dir_evento}")
    except Exception as e:
        print(f"[CLEANUP][ERRO] Não conseguiu apagar {dir_evento}: {e}")

@router.post("/eventos/{evento_id}/cargos/gerar-arquivos-multiplos")
async def gerar_todos_arquivos_multiplos(
    evento_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    """
    Exportação em lote, só permite com a senha correta do evento!
    """
    body = await request.json()
    cargos_id = body.get("cargos_id", [])
    senha_usuario = body.get("senha", "")

    if not cargos_id or not isinstance(cargos_id, list):
        return {"erro": "Nenhum cargo selecionado."}

    # Busca o evento e a senha criptografada
    result = await db.execute(select(DBEvento).where(DBEvento.id_evento == evento_id))
    evento = result.scalar_one_or_none()
    senha_evento_cripto = getattr(evento, "senha_evento_cripto", "")
    senha_evento = decrypt_text(senha_evento_cripto)

    if not evento:
        return {"erro": "Evento não encontrado."}
    nome_evento = evento.nome_evento.strip().replace(" ", "_")
    senha_evento_cripto = getattr(evento, "senha_evento_cripto", "")

    # Valida a senha ANTES de gerar qualquer arquivo
    if not senha_usuario:
        return {"erro": "Senha não informada."}
    if not senha_evento_cripto:
        return {"erro": "Evento não possui senha cadastrada."}
    senha_evento = decrypt_text(senha_evento_cripto)
    if senha_usuario != senha_evento:
        print(f"[SECURITY] Tentativa de exportação com senha inválida para evento {evento_id}")
        return {"erro": "Senha do evento inválida!"}

    # Opções de formatação e exportação
    fonte = body.get("fonte", "Calibri")
    tamanhoFonte = body.get("tamanhoFonte", 12)
    duasColunas = body.get("duasColunas", False)
    quebraBloco = body.get("quebraBloco", True)
    manterDocx = body.get("manterDocx", True)
    template = body.get("template", None)
    exibir_codigo_curto_questao = body.get("exibir_codigo_curto_questao", False)
    exibir_gabarito_marcado = body.get("exibir_gabarito_marcado", False)
    if template:
        path_template = os.path.join("templates_eventos", str(evento_id), template)
    else:
        path_template = None

    format_options = {
        "fonte_principal": fonte,
        "tamanho_fonte_principal": tamanhoFonte,
        "duas_colunas": duasColunas,
        "quebra_de_pagina_por_bloco": quebraBloco,
        "manter_arquivos_docx_individuais": manterDocx,
        "template_path": path_template,
        "exibir_codigo_curto_questao": exibir_codigo_curto_questao,
        "exibir_gabarito_marcado": exibir_gabarito_marcado,
    }

    # --- Geração dos arquivos para cada cargo ---
    from backend.app.routes.exportacao import (
        fetch_evento_cargo_prova, montar_prova_completa, document_generator, montar_dados_capa
    )

    for cargo_id in cargos_id:
        output_dir = os.path.join("ProvasGeradas_DG", nome_evento, cargo_id)
        os.makedirs(output_dir, exist_ok=True)
        evento, cargo, prova_montada, blocos_questoes, metadados_prova = await fetch_evento_cargo_prova(
            evento_id, cargo_id, db, current_user.tenant_id
        )
        prova_dict = await montar_prova_completa(evento, cargo, prova_montada, blocos_questoes, metadados_prova, db)
        nome_cargo = cargo.nome_cargo
        codigo_cargo = getattr(cargo, "codigo_cargo", "")
        num_variacoes = metadados_prova.get("definicao_geracao", {}).get("num_variacoes", 1)
        cover_pdf_paths = getattr(cargo, 'cover_pdf_paths', None)

        def resolve_capa_template_path(cover_pdf_paths):
            if isinstance(cover_pdf_paths, str):
                try:
                    paths = json.loads(cover_pdf_paths)
                    if isinstance(paths, str):
                        paths = [paths]
                except Exception:
                    paths = [cover_pdf_paths]
            elif isinstance(cover_pdf_paths, list):
                paths = cover_pdf_paths
            else:
                paths = []
            if paths:
                template_path = os.path.normpath(paths[0])
                if not os.path.isabs(template_path):
                    template_path = os.path.abspath(template_path)
                return template_path
            return None

        template_folha_rosto_pdf = resolve_capa_template_path(cover_pdf_paths)
        dir_capas_java = os.path.join(output_dir, "CapasPreenchidas")
        os.makedirs(dir_capas_java, exist_ok=True)
        def preencher_capas_java(template_pdf, dados_json, saida_dir):
            import subprocess
            comando = [
                "java", "-cp",
                "backend/app/pdfbox-app-3.0.5.jar;backend/app/json.jar;backend/app",
                "PreencheCapaPDF_JSON_PDFBox",
                template_pdf,
                dados_json,
                saida_dir
            ]
            subprocess.run(comando, capture_output=True, text=True)
        for variacao_num in range(1, num_variacoes + 1):
            tipo_letra = chr(ord('A') + variacao_num - 1) if num_variacoes > 1 else ""
            sufixo_tipo = f"Tipo {tipo_letra}" if tipo_letra else "PADRÃO"
            tipo_so_letra = tipo_letra or "PADRÃO"
            tipo_prova_nome = f"Tipo {tipo_letra}" if tipo_letra else "PADRÃO"
            if isinstance(prova_dict, dict):
                prova_dict["identificador_prova"] = tipo_prova_nome
            else:
                setattr(prova_dict, "identificador_prova", tipo_prova_nome)
            frase_para_capa = metadados_prova.get("frases_por_tipo_prova", {}).get(sufixo_tipo, "")
            dados_para_capa = [montar_dados_capa(
                candidato={},
                cargo=cargo,
                evento=evento,
                prova=prova_montada,
                frase=frase_para_capa,
                tipo=sufixo_tipo,
                letra_tipo=tipo_letra,
                tempo_prova="",
                quantidade_questoes="",
                empresa="NOME DA BANCA",
                qrcode="",
                outros=""
            )]
            json_capa_path = os.path.join(dir_capas_java, f"dados_capa_{tipo_so_letra}.json")
            with open(json_capa_path, "w", encoding="utf-8") as f:
                json.dump(dados_para_capa, f, ensure_ascii=False, indent=2)
            if template_folha_rosto_pdf and os.path.exists(template_folha_rosto_pdf):
                preencher_capas_java(template_folha_rosto_pdf, json_capa_path, dir_capas_java)
            capa_pdf_antes = set([fn for fn in os.listdir(dir_capas_java) if fn.endswith('.pdf')])
            timeout, interval = 5, 0.1
            found = None
            for _ in range(int(timeout / interval)):
                time.sleep(interval)
                arquivos = [fn for fn in os.listdir(dir_capas_java) if fn.endswith('.pdf')]
                novos = set(arquivos) - capa_pdf_antes
                if novos:
                    found = novos.pop()
                    break
                for nome in ["PROVA_UNICA_capa.pdf", "_capa.pdf"]:
                    if nome in arquivos:
                        found = nome
                        break
                if found:
                    break
            path_capa_pdf_final = None
            if found and os.path.exists(os.path.join(dir_capas_java, found)):
                path_capa_pdf_origem = os.path.join(dir_capas_java, found)
                nome_capa_pdf_final = f"{codigo_cargo} - {nome_cargo.replace(' ', '_')} - Tipo_{tipo_so_letra}_capa.pdf"
                path_capa_pdf_final = os.path.join(dir_capas_java, nome_capa_pdf_final)
                shutil.copy2(path_capa_pdf_origem, path_capa_pdf_final)
            docx_path = document_generator.gerar_prova_docx(
                prova_montada=prova_dict,
                nome_cargo=nome_cargo,
                variacao_num=variacao_num,
                output_folder=output_dir,
                format_options=format_options,
                textos_map={}
            )
            pdf_path = document_generator.pdf_converter.convert_to_pdf(docx_path, output_dir) if docx_path else None
            nome_prova_final = f"{codigo_cargo} - {nome_cargo.replace(' ', '_')} - Tipo_{tipo_so_letra}.pdf"
            caminho_pdf_final = os.path.join(output_dir, nome_prova_final)
            if path_capa_pdf_final and os.path.exists(path_capa_pdf_final) and pdf_path and os.path.exists(pdf_path):
                merger = PdfWriter()
                merger.append(path_capa_pdf_final)
                merger.append(pdf_path)
                with open(caminho_pdf_final, "wb") as f_out:
                    merger.write(f_out)
            elif pdf_path and os.path.exists(pdf_path):
                shutil.copy2(pdf_path, caminho_pdf_final)

    # --- Monta lista de arquivos para o ZIP ---
    base_dir = os.path.join("ProvasGeradas_DG", nome_evento)
    arquivos_para_zip = []
    padrao_pdf = r"^\d+\s*-\s*[^-]+-\s*Tipo_([A-Z]|PADRAO|PADRÃO)\.pdf$"

    for cargo_id in cargos_id:
        dir_cargo = os.path.join(base_dir, cargo_id)
        if not os.path.isdir(dir_cargo):
            continue
        cargo_result = await db.execute(select(DBCargo).where(DBCargo.id_cargo == cargo_id))
        cargo_obj = cargo_result.scalar_one_or_none()
        if cargo_obj:
            codigo_cargo = str(getattr(cargo_obj, "codigo_cargo", cargo_id))
            nome_cargo = getattr(cargo_obj, "nome_cargo", cargo_id)
        else:
            codigo_cargo = cargo_id
            nome_cargo = cargo_id
        nome_pasta_cargo = f"{codigo_cargo}_{nome_cargo.replace(' ', '_')}".replace('/', '_')
        for file in os.listdir(dir_cargo):
            file_path = os.path.join(dir_cargo, file)
            if file.lower().endswith('.pdf') and re.match(padrao_pdf, file, re.IGNORECASE):
                arcname = f"{nome_pasta_cargo}/{file}"
                arquivos_para_zip.append((file_path, arcname))
        if manterDocx:
            for file in os.listdir(dir_cargo):
                if file.lower().endswith('.docx'):
                    file_path = os.path.join(dir_cargo, file)
                    arcname = f"{nome_pasta_cargo}/{file}"
                    arquivos_para_zip.append((file_path, arcname))
            dir_capas = os.path.join(dir_cargo, "CapasPreenchidas")
            if os.path.isdir(dir_capas):
                for root, dirs, files in os.walk(dir_capas):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(
                            nome_pasta_cargo,
                            os.path.relpath(file_path, dir_cargo)
                        )
                        arquivos_para_zip.append((file_path, arcname))

    if not arquivos_para_zip:
        return {"erro": "Nenhum arquivo encontrado para os cargos selecionados."}

    # --- Cria ZIP temporário ---
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmpzip:
        with pyzipper.AESZipFile(tmpzip, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
            zipf.setpassword(senha_evento.encode('utf-8'))
            for file_path, arcname in arquivos_para_zip:
                zipf.write(file_path, arcname=arcname)
        tmpzip_path = tmpzip.name

    def remover_arquivo_tmp(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f'[WARN] Falha ao apagar ZIP temporário: {path} - {e}')

    background_tasks.add_task(remover_arquivo_tmp, tmpzip_path)
    background_tasks.add_task(limpar_pasta_evento, nome_evento)

    return FileResponse(
        tmpzip_path,
        filename=f"Provas_{nome_evento}.zip",
        media_type="application/zip",
        background=background_tasks,
    )


def nome_zip_evento(evento) -> str:
    nome_evento = evento.nome_evento.strip().replace(" ", "_")
    return f"Provas_{nome_evento}.zip"


async def zip_provas_cargos_selecionados_interno(evento_id, cargos_id, manter_docx, db, current_user):
    evento = await carregar_evento_autorizado(evento_id, db, current_user)
    senha_evento_cripto = getattr(evento, "senha_evento_cripto", "")
    senha_evento = decrypt_text(senha_evento_cripto)

    nome_evento = evento.nome_evento.strip().replace(" ", "_")

    # Tente pegar manterDocx do current_user ou de outra fonte se necessário (ajuste conforme seu fluxo)
    # Aqui, por padrão, vamos deixar sempre True para garantir o zip completo (ajuste conforme seu fluxo)
    
    base_dir = os.path.join("ProvasGeradas_DG", nome_evento)
    arquivos_para_zip = []
    padrao_pdf = r"^\d+\s*-\s*[^-]+-\s*Tipo_([A-Z]|PADRAO|PADRÃO)\.pdf$"

    for cargo_id in cargos_id:
        dir_cargo = os.path.join(base_dir, cargo_id)
        print(f"[DEBUG-ZIP] Pasta: {dir_cargo}")
        if not os.path.isdir(dir_cargo):
            print(f"[DEBUG-ZIP] Pasta NÃO EXISTE: {dir_cargo}")
            continue
        print(f"[DEBUG-ZIP] Arquivos na pasta: {os.listdir(dir_cargo)}")

        # Buscar código e nome do cargo do banco
        cargo_result = await db.execute(select(DBCargo).where(DBCargo.id_cargo == cargo_id))
        cargo_obj = cargo_result.scalar_one_or_none()
        if cargo_obj:
            codigo_cargo = str(getattr(cargo_obj, "codigo_cargo", cargo_id))
            nome_cargo = getattr(cargo_obj, "nome_cargo", cargo_id)
        else:
            codigo_cargo = cargo_id
            nome_cargo = cargo_id
        nome_pasta_cargo = f"{codigo_cargo}_{nome_cargo.replace(' ', '_')}".replace('/', '_')

        # PDFs finais
        for file in os.listdir(dir_cargo):
            file_path = os.path.join(dir_cargo, file)
            if (
                file.lower().endswith('.pdf')
                and re.match(padrao_pdf, file, re.IGNORECASE)
            ):
                print(f"[DEBUG-ZIP] Incluindo PDF no ZIP: {file_path}")
                arcname = f"{nome_pasta_cargo}/{file}"
                arquivos_para_zip.append((file_path, arcname))

            # DOCX
            if manter_docx and file.lower().endswith('.docx'):
                arcname = f"{nome_pasta_cargo}/{file}"
                arquivos_para_zip.append((file_path, arcname))
            # CSV
            if file.lower().endswith('.csv'):
                arcname = f"{nome_pasta_cargo}/{file}"
                arquivos_para_zip.append((file_path, arcname))

        # CapasPreenchidas
        if manter_docx:
            dir_capas = os.path.join(dir_cargo, "CapasPreenchidas")
            if os.path.isdir(dir_capas):
                for root, dirs, files in os.walk(dir_capas):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(
                            nome_pasta_cargo,
                            os.path.relpath(file_path, dir_cargo)
                        )
                        arquivos_para_zip.append((file_path, arcname))

    if not arquivos_para_zip:
        return None

    zip_filename = nome_zip_evento(evento)
    zip_path = caminho_dentro_de("ProvasGeradas_DG", zip_filename)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path, arcname in arquivos_para_zip:
            zipf.write(file_path, arcname=arcname)

    return {
        "zip_filename": zip_filename,
        "zip_path": zip_path,
        "download_url": f"/api/export/download-zip?evento_id={evento.id_evento}"
    }


# O router é montado com prefixo /api/export, então a rota final é /api/export/download-zip
@router.get("/download-zip")
async def download_zip(
    evento_id: str = Query(...),
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR))
):
    # O nome do arquivo é derivado do evento autorizado; nunca do que o cliente envia.
    evento = await carregar_evento_autorizado(evento_id, db, current_user)
    filename = nome_zip_evento(evento)
    file_path = caminho_dentro_de("ProvasGeradas_DG", filename)
    if not os.path.isfile(file_path):
        raise HTTPException(404, "Arquivo ZIP não encontrado.")
    return FileResponse(file_path, filename=filename, media_type="application/zip")


@router.post("/eventos/{evento_id}/cargos/{cargo_id}/gerar-arquivos-async", status_code=202)
async def gerar_arquivos_async(
    evento_id: str,
    cargo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    await fetch_evento_cargo_prova(evento_id, cargo_id, db, current_user.tenant_id)
    job = create_job(
        tenant_id=current_user.tenant_id,
        user=current_user.username,
        tipo="gerar_arquivos_cargo",
        params={"evento_id": evento_id, "cargo_id": cargo_id},
    )

    async def _run_export_job(jid: str, ev_id: str, cg_id: str, tid: int | None):
        from backend.app.database import SessionLocal, set_tenant_context
        update_job(jid, status="running")
        try:
            async with SessionLocal() as job_db:
                await set_tenant_context(job_db, tid, bypass_rls=(tid is None))
                out = await gerar_todos_arquivos(ev_id, cg_id, job_db, current_user)
                update_job(jid, status="completed", result=out)
        except Exception as exc:
            update_job(jid, status="failed", error=type(exc).__name__)

    background_tasks.add_task(_run_export_job, job["job_id"], evento_id, cargo_id, current_user.tenant_id)
    return {"job_id": job["job_id"], "status": job["status"]}


@router.get("/jobs/{job_id}")
async def consultar_job_exportacao(
    job_id: str,
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    job = get_job_for_tenant(job_id, current_user.tenant_id, is_admin_geral=is_admin_geral(current_user))
    if not job:
        raise HTTPException(status_code=404, detail="Job de exportação não encontrado.")
    return job