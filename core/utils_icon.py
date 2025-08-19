from pathlib import Path
import tkinter as tk

def set_app_icon(window, icon_name="app_icon.png"):
    """
    Define o ícone da janela usando PNG (multiplataforma).
    Use no __init__ de cada janela principal: set_app_icon(self)
    """
    icon_path = Path(__file__).resolve().parent.parent / "assets" / icon_name
    if icon_path.exists():
        try:
            img = tk.PhotoImage(file=str(icon_path))
            window.iconphoto(True, img)
            # Previna garbage collection!
            window._icon_img_ref = img
        except Exception as e:
            print(f"[DEBUG] Falha ao definir iconphoto: {e}")