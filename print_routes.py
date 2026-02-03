print("INÍCIO DO SCRIPT")
try:
    from backend.app.main import app
    print("IMPORTOU app!")
    for route in app.routes:
        print(route.path)
    print("FIM DAS ROTAS")
except Exception as e:
    print("ERRO:", e)