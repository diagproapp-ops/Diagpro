from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from fastapi import Depends
import os
from typing import List

router = APIRouter()

TEMPLATES_BASE_DIR = "templates_eventos"

def get_event_templates_dir(evento_id: str) -> str:
    dir_path = os.path.join(TEMPLATES_BASE_DIR, str(evento_id))
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

@router.get("/eventos/{evento_id}/templates", response_model=List[dict])
def listar_templates(evento_id: str):
    dir_path = get_event_templates_dir(evento_id)
    files = []
    for fname in os.listdir(dir_path):
        fpath = os.path.join(dir_path, fname)
        if os.path.isfile(fpath):
            files.append({
                "nome_arquivo": fname,
                "url": f"/api/eventos/{evento_id}/templates/{fname}",
                "descricao": ""  # Adapte se quiser descrição
            })
    return files

@router.get("/eventos/{evento_id}/templates/{nome_arquivo}")
def baixar_template(evento_id: str, nome_arquivo: str):
    print(f"Procurando arquivo: {nome_arquivo} em evento: {evento_id}")
    dir_path = get_event_templates_dir(evento_id)
    file_path = os.path.join(dir_path, nome_arquivo)
    print(f"Caminho completo: {file_path}")
    if not os.path.isfile(file_path):
        print("Arquivo NÃO encontrado!")
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    print("Arquivo encontrado! Retornando.")
    return FileResponse(
        path=file_path,
        filename=nome_arquivo,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

@router.post("/eventos/{evento_id}/templates/upload")
def upload_template(evento_id: str, file: UploadFile = File(...)):
    dir_path = get_event_templates_dir(evento_id)
    file_path = os.path.join(dir_path, file.filename)
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    return {"ok": True, "nome_arquivo": file.filename}

@router.delete("/eventos/{evento_id}/templates/{nome_arquivo}")
def deletar_template(evento_id: str, nome_arquivo: str):
    dir_path = get_event_templates_dir(evento_id)
    file_path = os.path.join(dir_path, nome_arquivo)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    os.remove(file_path)
    return {"ok": True}