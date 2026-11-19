from fastapi import APIRouter, Query, HTTPException, Request, status, Depends

from backend.app.auditoria_exportacao import registrar_exportacao
from backend.app.verificacao_prova import verificar_prova
from backend.app.dados_prova import completar_questoes
from fastapi.responses import FileResponse, Response
from backend.app import secure_files
from backend.app.rate_limit import rate_limit
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db_models import Evento, Cargo, ProvaMontada
from backend.app.database import get_db
from core.document_generator import DocumentGenerator
from backend.app.utils_crypto import decrypt_text
from backend.app.security import evento_autorizado, evento_com_senha, exigir_texto_claro, get_tenant_db, require_roles
from backend.app.roles import UserRole
import hmac
import tempfile, os, zipfile, csv, logging, json

router = APIRouter()

document_generator = DocumentGenerator(
    templates_base_dir="templates",
    # a API informa sempre a pasta de saída; evita criar ProvasGeradas_DG
    config={"default_export_directory": os.path.join(tempfile.gettempdir(), "diagpro_core_default")},
    logger=logging.getLogger("core.document_generator"),
    core_elements_module=None  # ajuste se necessário
)

def normalize_prova_montada(prova):
    """Garante que metadados_prova e blocos_questoes sejam dict/list, não string."""
    if prova is None:
        return None
    # metadados_prova sempre dict
    meta = getattr(prova, "metadados_prova", None)
    if meta is None or meta == "":
        prova.metadados_prova = {}
    elif isinstance(meta, str):
        try:
            prova.metadados_prova = json.loads(meta)
        except Exception:
            prova.metadados_prova = {}
    # blocos_questoes sempre lista/dict
    blocos = getattr(prova, "blocos_questoes", None)
    if blocos is None or blocos == "":
        prova.blocos_questoes = []
    elif isinstance(blocos, str):
        try:
            prova.blocos_questoes = json.loads(blocos)
        except Exception:
            prova.blocos_questoes = []
    # nunca gerar gabarito com texto cifrado (dados legados)
    exigir_texto_claro(prova.blocos_questoes, "prova")
    # campos string importantes
    if getattr(prova, "identificador_prova", None) is None:
        prova.identificador_prova = ""
    if getattr(prova, "titulo_prova", None) is None:
        prova.titulo_prova = ""
    if getattr(prova, "nome_prova_montada", None) is None:
        prova.nome_prova_montada = ""
    return prova

@router.get("/eventos/{evento_id}/cargos/{cargo_id}/exportacoes")
async def listar_gabaritos_exportaveis(
    evento_id: str,
    cargo_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento_autorizado_obj=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    """
    Lista os arquivos de gabarito disponíveis para o cargo selecionado.
    """
    # Nada é guardado no servidor: o download regenera o gabarito a partir do banco cifrado.
    return [{
        "nome_arquivo": f"Gabarito_{cargo_id}.csv",
        "tipo": "gabarito",
        "url": f"/api/export/download?evento_id={evento_id}&cargo_id={cargo_id}&tipo=gabarito",
    }]

@router.post("/eventos/{evento_id}/exportar-gabaritos-zip", dependencies=[Depends(rate_limit(5, 60, "gabaritos-zip"))])
async def exportar_gabaritos_zip(
    evento_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
    evento: Evento = Depends(evento_com_senha),  # senha no cabeçalho X-Senha-Evento (antes ia na URL)
    workdir: str = Depends(secure_files.request_workdir),
):
    import pyzipper

    senha_original = evento.senha_evento_cripto  # o ORM entrega decifrada; também cifra o ZIP

    result_cargos = await db.execute(select(Cargo).filter(Cargo.id_evento_fk == evento_id))
    cargos = result_cargos.scalars().all()
    if not cargos:
        raise HTTPException(status_code=404, detail="Nenhum cargo para este evento.")

    output_dir = workdir  # pasta temporária da requisição, apagada ao final (antes ficava para sempre no %TEMP%)
    arquivos_csv = []

    # Estrutura: { (codigo_cargo, nome_cargo, tipo_prova): [questoes...] }
    all_gabaritos_por_variacao = {}
    problemas_gabarito = []

    for cargo in cargos:
        result_prova = await db.execute(
            select(ProvaMontada).filter(
                ProvaMontada.id_evento_fk == evento_id,
                ProvaMontada.id_cargo_fk == cargo.id_cargo
            )
        )
        prova_montada = normalize_prova_montada(result_prova.scalar_one_or_none())
        if not prova_montada:
            continue

        # Só processa se há blocos com ao menos uma questão
        blocos = prova_montada.blocos_questoes
        if not blocos or not any(bloco.get("questoes") for bloco in blocos):
            continue

        prova_montada.evento = evento
        prova_montada.cargo = cargo
        await completar_questoes(db, blocos)

        # gabarito de prova com problema sairia errado: mesma checagem da exportação das provas
        checagem = await verificar_prova(db, cargo, prova_montada, blocos)
        if checagem["bloqueios"]:
            problemas_gabarito.append(checagem)
            continue

        gabaritos_por_variacao = document_generator.gerar_gabaritos_balanceados_por_variacao(prova_montada)
        for tipo_prova, lista in gabaritos_por_variacao.items():
            key = (getattr(cargo, "codigo_cargo", ""), getattr(cargo, "nome_cargo", ""), tipo_prova)
            all_gabaritos_por_variacao[key] = lista

    if problemas_gabarito:
        total = sum(len(v["bloqueios"]) for v in problemas_gabarito)
        raise HTTPException(status_code=409, detail={
            "mensagem": f"Gabaritos bloqueados: {total} problema(s) em {len(problemas_gabarito)} cargo(s) deixariam o gabarito errado.",
            "verificacao": problemas_gabarito,
        })

    # GABARITO COMPLETO: uma linha por questão/tipo/cargo
    completo_csv_path = os.path.join(output_dir, f"GABARITO_COMPLETO_EVENTO_{evento.nome_evento.replace(' ', '_')}.csv")
    with open(completo_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow([
            "CódigoCargo", "Cargo", "TipoProva", "Questão", "Disciplina",
            "LetraCorreta", "TextoAlternativaCorreta", "CodigoCurtoQuestao"
        ])
        for (codigo_cargo, cargo_nome, tipo_prova), questoes in all_gabaritos_por_variacao.items():
            for item in questoes:
                # Busca o codigo_curto_questao de modo robusto
                codigo_curto = (
                    item.get("codigo_curto_questao")
                    or item.get("codigo_curto")
                    or (item.get("metadados_questao", {}) or {}).get("codigo_curto_questao")
                    or ""
                )
                writer.writerow([
                    codigo_cargo,
                    cargo_nome,
                    tipo_prova,
                    item.get("numero_questao_exibido", ""),
                    item.get("disciplina_nome", ""),
                    item.get("gabarito_letra_exibida", ""),
                    item.get("texto_opcao_correta_original", ""),
                    item.get("codigo_curto_questao", ""),
                ])
    arquivos_csv.append(completo_csv_path)

    # GABARITO SIMPLIFICADO: uma linha por (cargo, tipo), colunas Q1, Q2, ...
    simplificado_csv_path = os.path.join(output_dir, f"GABARITO_SIMPLIFICADO_EVENTO_{evento.nome_evento.replace(' ', '_')}.csv")
    with open(simplificado_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        max_q = 0
        for questoes in all_gabaritos_por_variacao.values():
            if len(questoes) > max_q:
                max_q = len(questoes)
        headers = ["CódigoCargo", "Cargo", "TipoProva"] + [f"Q{i+1}" for i in range(max_q)]
        writer = csv.writer(f, delimiter=';')
        writer.writerow(headers)
        for (codigo_cargo, cargo_nome, tipo_prova), questoes in all_gabaritos_por_variacao.items():
            row = [codigo_cargo, cargo_nome, tipo_prova]
            row += [item.get("gabarito_letra_exibida", "") for item in questoes]
            while len(row) < len(headers):
                row.append("")
            writer.writerow(row)
    arquivos_csv.append(simplificado_csv_path)

    # Compacta tudo em ZIP PROTEGIDO COM SENHA DO EVENTO
    zip_path = os.path.join(output_dir, f"GABARITOS_EVENTO_{evento.nome_evento.replace(' ','_')}.zip")
    with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
        zipf.setpassword(senha_original.encode('utf-8'))
        for file in arquivos_csv:
            zipf.write(file, arcname=os.path.basename(file))

    await registrar_exportacao(
        db, request, current_user, evento, "exportacao_gabaritos",
        cargos=sorted({f"{k[0]} - {k[1]}" for k in all_gabaritos_por_variacao}),
        parametros={"variacoes": sorted({k[2] for k in all_gabaritos_por_variacao})},
        arquivos=[(os.path.basename(zip_path), zip_path)],
    )
    with open(zip_path, "rb") as fh:
        conteudo = fh.read()
    return Response(content=conteudo, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{os.path.basename(zip_path)}"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })

@router.get("/eventos/{evento_id}/cargos/{cargo_id}/gabarito")
async def visualizar_gabarito(
    evento_id: str,
    cargo_id: str,
    tipo_prova: str = "PADRÃO",  # permite escolher variação, se quiser
    db: AsyncSession = Depends(get_tenant_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
    evento_liberado=Depends(evento_com_senha),  # gabarito é prova pronta: só com a senha do evento
):
    # Busca evento, cargo e prova montada (igual já faz)
    result_evento = await db.execute(select(Evento).filter(Evento.id_evento == evento_id))
    evento = result_evento.scalar_one_or_none()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    result_cargo = await db.execute(select(Cargo).filter(Cargo.id_cargo == cargo_id, Cargo.id_evento_fk == evento_id))
    cargo = result_cargo.scalar_one_or_none()
    if not cargo:
        raise HTTPException(status_code=404, detail="Cargo não encontrado ou não pertence ao evento.")

    result_prova = await db.execute(
        select(ProvaMontada).filter(
            ProvaMontada.id_evento_fk == evento_id,
            ProvaMontada.id_cargo_fk == cargo_id,
        )
    )
    prova_montada = result_prova.scalar_one_or_none()
    if not prova_montada:
        return []

    prova_montada = normalize_prova_montada(prova_montada)
    prova_montada.evento = evento
    prova_montada.cargo = cargo
    await completar_questoes(db, prova_montada.blocos_questoes)

    checagem = await verificar_prova(db, cargo, prova_montada, prova_montada.blocos_questoes)
    if checagem["bloqueios"]:
        raise HTTPException(status_code=409, detail={
            "mensagem": "Esta prova tem problemas que deixariam o gabarito errado. Corrija antes de consultar.",
            "verificacao": [checagem],
        })

    # Usa o generator igual no ZIP
    gabaritos_por_variacao = document_generator.gerar_gabaritos_balanceados_por_variacao(prova_montada)

    # Seleciona a variação desejada
    lista_questoes = gabaritos_por_variacao.get(tipo_prova)
    if not lista_questoes:
        lista_questoes = next(iter(gabaritos_por_variacao.values()), [])

    # Mapeia para o formato esperado pelo frontend
    questoes = []
    for q in lista_questoes:
        disciplina_nome = (
            q.get("nome_disciplina_na_prova")
            or q.get("disciplina_nome")
            or ""
        )
        texto_correto = q.get("texto_opcao_correta_original", "")
        if texto_correto:
            try:
                texto_correto = decrypt_text(texto_correto)
            except Exception:
                pass

        questoes.append({
            "numero_questao": q.get("numero_questao_exibido", ""),
            "tipo_prova": tipo_prova,
            "disciplina": disciplina_nome,
            "letra_correta": q.get("gabarito_letra_exibida", ""),
            "texto_correto": texto_correto,
            "codigo_curto": q.get("codigo_curto_questao", ""),
        })


    return questoes

@router.get("/eventos/{evento_id}/cargos/{cargo_id}/variacoes")
async def listar_variacoes(
    evento_id: str,
    cargo_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    evento_autorizado_obj=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    result_prova = await db.execute(
        select(ProvaMontada).filter(
            ProvaMontada.id_evento_fk == evento_id,
            ProvaMontada.id_cargo_fk == cargo_id,
        )
    )
    prova_montada = result_prova.scalar_one_or_none()
    if not prova_montada:
        return []
    prova_montada = normalize_prova_montada(prova_montada)
    await completar_questoes(db, prova_montada.blocos_questoes)
    # Use o mesmo generator da exportação
    prova_montada.evento = evento_id  # ou o objeto evento, se necessário para o generator
    prova_montada.cargo = cargo_id    # ou o objeto cargo, se necessário
    gabaritos_por_variacao = document_generator.gerar_gabaritos_balanceados_por_variacao(prova_montada)
    return list(gabaritos_por_variacao.keys())