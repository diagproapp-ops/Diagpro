from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
import os
from typing import List

from backend.app.security import evento_autorizado, nome_arquivo_seguro, caminho_dentro_de, require_roles
from backend.app.roles import UserRole

router = APIRouter()

TEMPLATES_BASE_DIR = "templates_eventos"
EXTENSOES_TEMPLATE = {".docx", ".dotx", ".pdf"}
TAMANHO_MAX_TEMPLATE = 20 * 1024 * 1024  # 20 MB

MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".dotx": "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    ".pdf": "application/pdf",
}


def get_event_templates_dir(evento_id: str) -> str:
    # evento_id já foi validado contra o banco por evento_autorizado
    dir_path = caminho_dentro_de(TEMPLATES_BASE_DIR, str(evento_id))
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


@router.get("/eventos/{evento_id}/templates", response_model=List[dict])
def listar_templates(evento=Depends(evento_autorizado)):
    evento_id = evento.id_evento
    dir_path = get_event_templates_dir(evento_id)
    files = []
    for fname in os.listdir(dir_path):
        fpath = os.path.join(dir_path, fname)
        if os.path.isfile(fpath):
            files.append({
                "nome_arquivo": fname,
                "url": f"/api/eventos/{evento_id}/templates/{fname}",
                "descricao": ""
            })
    return files


@router.get("/eventos/{evento_id}/templates/{nome_arquivo}")
def baixar_template(nome_arquivo: str, evento=Depends(evento_autorizado)):
    nome = nome_arquivo_seguro(nome_arquivo, EXTENSOES_TEMPLATE)
    file_path = caminho_dentro_de(get_event_templates_dir(evento.id_evento), nome)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    return FileResponse(
        path=file_path,
        filename=nome,
        media_type=MEDIA_TYPES[os.path.splitext(nome)[1].lower()],
    )


@router.post("/eventos/{evento_id}/templates/upload")
def upload_template(
    file: UploadFile = File(...),
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    nome = nome_arquivo_seguro(file.filename, EXTENSOES_TEMPLATE)
    file_path = caminho_dentro_de(get_event_templates_dir(evento.id_evento), nome)
    conteudo = file.file.read(TAMANHO_MAX_TEMPLATE + 1)
    if len(conteudo) > TAMANHO_MAX_TEMPLATE:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 20 MB.")
    with open(file_path, "wb") as f:
        f.write(conteudo)
    return {"ok": True, "nome_arquivo": nome}


@router.delete("/eventos/{evento_id}/templates/{nome_arquivo}")
def deletar_template(
    nome_arquivo: str,
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    nome = nome_arquivo_seguro(nome_arquivo)
    file_path = caminho_dentro_de(get_event_templates_dir(evento.id_evento), nome)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    os.remove(file_path)
    return {"ok": True}
