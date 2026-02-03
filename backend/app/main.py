from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
from backend.app.routes.exportacao import router as export_router
from backend.app.routes.gabarito import router as gabarito_router
from backend.app.routes.templates import router as templates_router

# Aqui está o segredo!
app = FastAPI(multipart_params={"max_part_size": 50 * 1024 * 1024})  # 50 MB por parte

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_clients_router)
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/users")
app.mount("/avatars", StaticFiles(directory="avatars"), name="avatars")
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
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(provas_geracao_router)
app.include_router(audit_log.router)
app.include_router(export_router, prefix="/api/export")
app.include_router(gabarito_router, prefix="/api/gabarito")
app.include_router(templates_router, prefix="/api")

@app.get("/")
def read_root():
    return {"msg": "DiagPro API funcionando!"}

@app.get("/debug_ping")
def debug_ping():
    print(">>> CHEGOU NO /debug_ping <<<")
    return {"ok": True}