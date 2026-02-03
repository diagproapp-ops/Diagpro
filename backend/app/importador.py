from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from core.docx_parser import DocxParser
from core.elements import QuestaoType, OpcaoMultiplaEscolha, TextoReferenciaType
import shutil, os, tempfile

router = APIRouter()

@router.post("/importar-questoes-docx", summary="Importa questões e textos referência de um arquivo DOCX")
async def importar_questoes_docx(
    arquivo: UploadFile = File(...),
    disciplina: str = Form(...)
):
    # 1. Salva arquivo temporariamente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        shutil.copyfileobj(arquivo.file, tmp)
        tmp_path = tmp.name

    # 2. Instancia o parser
    parser = DocxParser(
        base_media_dir="media/questoes",
        questao_model=QuestaoType,
        opcao_model=OpcaoMultiplaEscolha,
        texto_ref_model=TextoReferenciaType
    )

    # 3. Faz o parse
    questoes, textos_referencia = parser.parse_document(tmp_path, disciplina)

    # 4. Remove arquivo temporário
    os.remove(tmp_path)

    # 5. Aqui você pode salvar as questões/textos no banco, ou só retornar para preview
    # Exemplo: retorna lista de questões para preview rápido
    return {
        "questoes": [q.to_dict() for q in questoes],
        "textos_referencia": textos_referencia
    }