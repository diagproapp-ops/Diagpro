# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Importe o CORS
from backend.app.routes import users, eventos, cargos, provas, auth

app = FastAPI()

# Defina as origens que podem fazer pedidos à sua API
origins = [
    "http://localhost:3000",  # A origem do seu front-end React
]

# Adicione o middleware do CORS à sua aplicação
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos os cabeçalhos
)

# O resto do seu código continua igual
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/users")
app.include_router(eventos.router, prefix="/eventos")
app.include_router(cargos.router, prefix="/cargos")
app.include_router(provas.router, prefix="/provas")

@app.get("/")
def read_root():
    return {"msg": "DiagPro API funcionando!"}