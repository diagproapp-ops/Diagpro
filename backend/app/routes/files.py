# backend/app/routes/files.py
"""Entrega de arquivos cifrados por URL assinada e de vida curta (ver backend/app/secure_files.py)."""
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.app import secure_files as sf

router = APIRouter()

INLINE_TYPES = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "pdf"}


@router.get("/files/{scope}/{name}")
def baixar_arquivo_assinado(scope: int, name: str, exp: int = Query(...), sig: str = Query(...)):
    m = re.fullmatch(r"([0-9a-f]{32})\.([a-z0-9]{1,5})", name)
    if not m:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    fid, ext = m.groups()
    try:
        ref = sf.verify_signature(scope, fid, ext, exp, sig)
        data = sf.read_bytes(ref, None, any_tenant=True)  # a assinatura HMAC já amarra o arquivo ao link
    except sf.SecureFileError:
        # mesma resposta para assinatura inválida, link expirado ou arquivo inexistente
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou link expirado.")
    disposition = "inline" if ext in INLINE_TYPES else "attachment"
    return Response(
        content=data,
        media_type=sf.MEDIA_TYPES.get(ext, "application/octet-stream"),
        headers={
            "Content-Disposition": f'{disposition}; filename="{fid}.{ext}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox",
            "Cross-Origin-Resource-Policy": "same-site",
            "Referrer-Policy": "no-referrer",
        },
    )
