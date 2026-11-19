import logging
import os
import uuid

# Nível de log padrão WARNING: logs de depuração (que podem conter conteúdo de prova) ficam desligados.
logging.basicConfig(
    level=os.getenv("DIAGPRO_LOG_LEVEL", "WARNING").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
from backend.app import log_redaction  # noqa: E402
log_redaction.install()  # mascara senhas, assinaturas, tokens, caminhos e nomes de arquivo em todos os logs
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from backend.app.database import SessionLocal
from backend.app.routes.ia_chat import router as ia_chat_router
from backend.app.routes.plagio import router as plagio_router
from backend.app.routes.biblioteca import router as biblioteca_router
from backend.app.routes.dicionario import router as dicionario_router
from backend.app.routes import users, eventos, cargos, provas, auth, frases
from backend.app.admin_clients import router as admin_clients_router
from backend.app.routes import company
from backend.app.routes.cargos_import import router as cargos_import_router
from backend.app.routes.conteudos import router as conteudos_router
from backend.app.routes import textos_referencia
from backend.app.routes.questoes import router as questoes_router
from backend.app.routes.provas import router as provas
from backend.app.routes.provas_geracao import router as provas_geracao_router
from backend.app.routes import audit_log
from backend.app.routes import configuracoes as configuracoes_routes
from backend.app.routes.exportacao import router as export_router
from backend.app.routes.gabarito import router as gabarito_router
from backend.app.routes.templates import router as templates_router
from backend.app.routes.files import router as files_router

# Aqui está o segredo!
app = FastAPI(multipart_params={"max_part_size": 50 * 1024 * 1024})  # 50 MB por parte

_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Tenant-Id", "X-Senha-Evento"],
    # a tela de Exportação lê o resumo do lote (falhas/avisos) e o nome do arquivo
    expose_headers=["Content-Disposition", "X-Exportacao-Falhas", "X-Exportacao-Avisos"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if os.getenv("ENABLE_HSTS", "false").lower() == "true":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith(("/api/", "/auth/", "/users/", "/admin/")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response

app.include_router(admin_clients_router)
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/users")
app.include_router(eventos.router, prefix="/eventos")
app.include_router(cargos.router)  # <<< Sem prefixo!
app.include_router(provas, prefix="/provas")  # <- CORRETO!
app.include_router(frases.router, prefix="/frases")
app.include_router(company.router)
app.include_router(cargos_import_router)
app.include_router(conteudos_router, prefix="/conteudos")
app.include_router(textos_referencia.router)
app.include_router(questoes_router)
app.include_router(ia_chat_router, prefix="/api")
app.include_router(plagio_router, prefix="/api")
app.include_router(biblioteca_router, prefix="/api")
app.include_router(dicionario_router, prefix="/api")
# Não há mais pastas públicas (/static, /avatars): arquivos ficam cifrados e são servidos por URL assinada.
app.include_router(files_router, prefix="/api")
app.include_router(provas_geracao_router)
app.include_router(audit_log.router)
app.include_router(configuracoes_routes.router)
app.include_router(export_router, prefix="/api/export")
app.include_router(gabarito_router, prefix="/api/gabarito")
app.include_router(templates_router, prefix="/api")

@app.get("/")
def read_root():
    return {"msg": "DiagPro API funcionando!"}


@app.get("/health")
async def health_check():
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail={"status": "degraded", "database": "unavailable"})
