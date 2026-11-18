from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend.app import secure_files
from backend.app.roles import UserRole
from backend.app.security import evento_autorizado, require_roles

router = APIRouter()

TAMANHO_MAX_TEMPLATE = secure_files.KINDS["template"][1]


@router.get("/eventos/{evento_id}/templates", response_model=List[dict])
def listar_templates(evento=Depends(evento_autorizado)):
    evento_id = evento.id_evento
    return [
        {"nome_arquivo": nome, "url": f"/api/eventos/{evento_id}/templates/{nome}", "descricao": ""}
        for nome in secure_files.list_templates(evento_id)
    ]


@router.get("/eventos/{evento_id}/templates/{nome_arquivo}")
def baixar_template(nome_arquivo: str, evento=Depends(evento_autorizado)):
    try:
        data = secure_files.read_template(evento.id_evento, nome_arquivo, evento.tenant_id)
    except secure_files.SecureFileError:
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    ext = nome_arquivo.rsplit(".", 1)[-1].lower()
    return Response(
        content=data,
        media_type=secure_files.MEDIA_TYPES.get(ext, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{nome_arquivo}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/eventos/{evento_id}/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    conteudo = await file.read(TAMANHO_MAX_TEMPLATE + 1)
    if len(conteudo) > TAMANHO_MAX_TEMPLATE:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 20 MB.")
    try:
        secure_files.write_template(evento.id_evento, file.filename or "", conteudo, evento.tenant_id)
    except secure_files.SecureFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "nome_arquivo": file.filename}


@router.delete("/eventos/{evento_id}/templates/{nome_arquivo}")
def deletar_template(
    nome_arquivo: str,
    evento=Depends(evento_autorizado),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ADMIN_GERAL, UserRole.DIAGRAMADOR)),
):
    if not secure_files.delete_template(evento.id_evento, nome_arquivo):
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    return {"ok": True}
