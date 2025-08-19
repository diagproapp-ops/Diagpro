import os
import sys
import customtkinter
from CTkMessagebox import CTkMessagebox # LINHA CORRETA
import tkinter as tk
import tkinter.messagebox as tk_messagebox
import logging
from typing import TYPE_CHECKING, Dict, Optional, Any, List, Type, Callable, Union
import datetime
import uuid
import sqlite3
import json
import random
from pathlib import Path
import threading  # <-- 1. ADICIONE ESTA IMPORTAÇÃO
import csv

# Em core/app_controller.py
from core.database_setup import get_sqlalchemy_session
from core.models import QuestoesBanco # Garanta que esta importação também existe
from sqlalchemy.sql.expression import func # E esta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .auth_service import AuthService
from .models import User
from .config_manager import ConfigManager
from .event_manager import EventManager
from .diagram_manager import DiagramManager
from .elements import EventoType, CargoType, ProvaMontadaType, TextoReferenciaType, QuestaoType, OpcaoMultiplaEscolha, BlocoQuestoesType, BancoFrasesType, TipoQuestao
from .docx_parser import DocxParser
from .document_generator import DocumentGenerator
from .frase_manager import FraseManager
from. utils import trata_campos_json


if TYPE_CHECKING:
    from ui.splash_screen import SplashScreen
    from ui.login_window import LoginWindow
    from ui.settings_window import SettingsWindow
    from ui.app_window import AppWindow
    from ui.cargo_manager_window import CargoManagerWindow
    from ui.dialogs import show_error, show_info, show_warning

if TYPE_CHECKING:
    from .models import User, QuestoesBanco, OpcoesQuestao # MODELO DO BANCO DE DADOS

class AppController:
    def __init__(self, root: customtkinter.CTk, auth_service: AuthService, config_manager: ConfigManager, db_connection_provider):
        self.root = root
        self.auth_service = auth_service
        self.config_manager = config_manager
        self.db_connection_provider = db_connection_provider
        self.logger = logging.getLogger(self.__class__.__name__)

        # 1. Importa o módulo de elementos
        from . import elements as core_elements_module
        # 2. Atribui o módulo a um atributo da instância para que outras partes do app possam usá-lo
        self.core_elements_module = core_elements_module

        self.current_user: Optional[User] = None

        self._initialize_core_components()

        self.splash_screen: 'SplashScreen' | None = None
        self.login_window: 'LoginWindow' | None = None
        self.main_window: 'AppWindow' | None = None
        self.main_view: Optional['AppWindow'] = None
        self.active_windows: Dict[str, customtkinter.CTkToplevel] = {}

        self._setup_ui_theme()
        self.root.title(self.config_manager.get_app_settings().get("app_title", "DiagProOFF"))
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown_application)
        self.logger.info("AppController inicializado com sucesso.")
        
    
    # --- NOVA FUNÇÃO ---
    def change_appearance_mode(self, new_theme_name: str):
        """
        Altera o tema da aplicação. Se for um tema padrão, apenas muda o modo.
        Se for um tema personalizado, carrega o ficheiro JSON correspondente.
        """
        try:
            self.logger.info(f"Tentando alterar tema/modo para: {new_theme_name}")

            # Nomes dos temas padrão que não precisam de um ficheiro
            standard_themes = ["Light", "Dark", "System"]

            if new_theme_name in standard_themes:
                # --- LÓGICA PARA TEMAS PADRÃO ---
                customtkinter.set_appearance_mode(new_theme_name)
                # Garante que, ao voltar para um tema padrão, a cor base também volte ao padrão.
                customtkinter.set_default_color_theme("blue") 
                self.logger.info(f"Modo de aparência padrão alterado para: {new_theme_name}")
            else:
                # --- LÓGICA PARA TEMAS PERSONALIZADOS (JSON) ---
                # Converte o nome do tema (ex: "Red Dark") para um nome de ficheiro (ex: "red-dark.json")
                theme_file_name = new_theme_name.lower().replace(" ", "-") + ".json"
                
                # Constrói o caminho para o ficheiro na pasta 'themes' do seu projeto
                theme_path = Path(__file__).resolve().parent.parent / "themes" / theme_file_name

                if theme_path.exists():
                    customtkinter.set_default_color_theme(str(theme_path))
                    customtkinter.set_appearance_mode("Dark")
                    self.logger.info(f"Tema personalizado '{theme_file_name}' carregado com sucesso.")
                else:
                    self.logger.error(f"Ficheiro de tema não encontrado: {theme_path}. A voltar para o tema padrão.")
                    customtkinter.set_appearance_mode("System") # Fallback seguro
                    customtkinter.set_default_color_theme("blue")
                    new_theme_name = "System" # Atualiza a variável para salvar a opção de fallback

            # Salva a escolha do tema no ficheiro de configuração para ser lembrada da próxima vez
            self.config_manager.save_setting("appearance_mode", new_theme_name)

        except Exception as e:
            self.logger.error(f"Falha ao alterar o tema da aplicação: {e}", exc_info=True)

    def show_settings_window(self):
        """Abre a janela de configurações da forma correta e simplificada."""
        from ui.settings_window import SettingsWindow # Importação local

        master = self.main_window or self.root
        
        if hasattr(self, 'settings_win') and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return

        # A chamada agora é mais simples, passando apenas o master e o controller
        self.settings_win = SettingsWindow(master=master, app_controller=self)
        self.settings_win.grab_set()

    def handle_user_creation(self, **kwargs):
        username = kwargs.get("usuario_login")
        self.logger.info(f"Controller: recebido pedido para criar usuário '{username}'.")
        try:
            if self.auth_service.find_user_by_username(username):
                msg = f"Usuário '{username}' já existe."
                self.logger.warning(msg)
                return False, msg
            self.auth_service.create_user(**kwargs)
            msg = f"Usuário '{username}' criado com sucesso."
            self.logger.info(msg)
            return True, msg
        except Exception as e:
            msg = f"Erro ao criar usuário: {e}"
            self.logger.error(msg, exc_info=True)
            return False, msg

    def _initialize_core_components(self):
        self.logger.debug("Inicializando componentes core...")
        try:
            # Cria todos os managers que acessam o banco, usando o mesmo provedor.
            self.event_manager = EventManager(
                db_connection_provider=self.db_connection_provider,
                app_controller=self,
                logger_instance=self.logger.getChild("EventManager")
            )
            self.diagram_manager = DiagramManager(
                db_connection_provider=self.db_connection_provider,
                logger_instance=self.logger.getChild("DiagramManager")
            )
            self.frase_manager = FraseManager(
                db_connection_provider=self.db_connection_provider,
                logger_instance=self.logger.getChild("FraseManager")
            )

            # O restante do seu método permanece igual
            db_path = self.config_manager.get_db_path()
            if not db_path:
                raise ValueError("Caminho do banco de dados não configurado.")

            # O resto do seu código que não depende dos managers pode vir aqui
            media_base_dir = self.config_manager.get_resolved_path("media_files_base_dir", "media")
            self.docx_parser = DocxParser(
                base_media_dir=media_base_dir,
                questao_model=QuestaoType,
                opcao_model=OpcaoMultiplaEscolha,
                texto_ref_model=TextoReferenciaType
            )
            templates_base_dir = self.config_manager.get_resolved_path("templates_base_dir", "templates")
            import core.elements as core_elements_module
            self.document_generator = DocumentGenerator(
                templates_base_dir=templates_base_dir,
                event_manager_instance=self.event_manager,
                logger=self.logger.getChild("DocumentGenerator"),
                core_elements_module=core_elements_module
            )
            self.logger.info("Componentes core inicializados com sucesso.")
        except Exception as e:
            self.logger.critical(f"Falha CRÍTICA ao inicializar componentes core: {e}", exc_info=True)
            # Considere fechar o app se componentes críticos falharem
            # self.root.destroy()
            pass
    
    @property
    def user_is_admin(self) -> bool:
        """Verifica se o usuário logado tem a função de administrador."""
        # Esta função já estava correta e continua funcionando, pois lê de self.current_user
        if self.current_user:
            return self.current_user.role == 'admin'
        return False

    def show_splash_screen(self):
        from ui.splash_screen import SplashScreen, DEFAULT_SPLASH_DURATION_MS
        import os # Garante que o 'os' está importado aqui
        from core.utils import resolve_path

        self.logger.info("Mostrando SplashScreen.")
        self.root.withdraw()
        app_settings = self.config_manager.get_app_settings()

        # --- TESTE COM CAMINHOS FIXOS (HARDCODED) ---

        # --- VERSÃO FINAL E LIMPA ---
        # Busca os caminhos das duas logos a partir do ConfigManager.
        logo_light = self.config_manager.get_setting("paths", {}).get("logo_path_light")
        logo_dark  = self.config_manager.get_setting("paths", {}).get("logo_path_dark")

        logo_light = resolve_path(logo_light)
        logo_dark  = resolve_path(logo_dark)
        print("LOGO LIGHT:", logo_light, "EXISTS?", os.path.exists(logo_light) if logo_light else "None")
        print("LOGO DARK:", logo_dark, "EXISTS?", os.path.exists(logo_dark) if logo_dark else "None")
        # --- FIM DA VERSÃO FINAL ---

        # Prints de verificação (agora mais seguros para evitar o erro)
        print("--- DEBUG CAMINHOS ---")
        print(f"Caminho HARDCODED para logo light: {logo_light}")
        if logo_light:
            print(f"Arquivo existe? {os.path.exists(logo_light)}")
        else:
            print("Caminho para logo light está Vazio (None).")

        print(f"Caminho HARDCODED para logo dark: {logo_dark}")
        if logo_dark:
            print(f"Arquivo existe? {os.path.exists(logo_dark)}")
        else:
            print("Caminho para logo dark está Vazio (None).")
        print("----------------------")
        
        # --- FIM DO TESTE ---

        self.splash_screen = SplashScreen(
            master=self.root,
            on_close_callback=self._on_splash_closed,
            duration_ms=app_settings.get("splash_duration", DEFAULT_SPLASH_DURATION_MS),
            app_name=app_settings.get("app_title", "DiagProOFF"),
            version=app_settings.get("app_version", "1.0.0"),
            
            logo_path_light=logo_light,
            logo_path_dark=logo_dark
        )

    def _on_splash_closed(self):
        self.logger.info("SplashScreen fechada, mostrando LoginWindow.")
        if self.splash_screen and self.splash_screen.winfo_exists():
            self.splash_screen.destroy()
        self.splash_screen = None
        self.show_login_window()

    def shutdown_application(self, prompt: bool = True):
        confirmed_to_exit = not prompt
        if prompt:
            if tk_messagebox.askyesno("Confirmar Saída", "Tem certeza que deseja sair do DiagProOFF?", parent=self.root):
                confirmed_to_exit = True
        if confirmed_to_exit:
            self.logger.info("Encerrando a aplicação...")
            self.root.destroy()
            sys.exit(0)

    def _setup_ui_theme(self):
        """
        Lê a configuração de tema salva e a aplica corretamente no arranque da aplicação,
        carregando temas personalizados de ficheiros JSON se necessário.
        """
        # Obtém o nome do tema que foi salvo da última vez. O padrão é "System".
        theme_name = self.config_manager.get_setting("appearance_mode", "System")
        
        self.logger.info(f"Configurando tema inicial da UI para: '{theme_name}'")

        # Lista de temas que vêm com o customtkinter e não precisam de ficheiro
        standard_themes = ["Light", "Dark", "System"]

        if theme_name in standard_themes:
            # Se for um tema padrão, aplica-o diretamente
            customtkinter.set_appearance_mode(theme_name)
            customtkinter.set_default_color_theme("blue") # A cor base para temas padrão
        else:
            # Se for um tema personalizado (ex: "Red Dark")
            # Converte o nome para o formato do nome do ficheiro (ex: "red-dark.json")
            theme_file_name = theme_name.lower().replace(" ", "-") + ".json"
            theme_path = Path(__file__).resolve().parent.parent / "themes" / theme_file_name

            if theme_path.exists():
                # Se o ficheiro do tema existir, carrega-o
                customtkinter.set_default_color_theme(str(theme_path))
                # E força a aplicação a usar o modo "Dark" para que as cores sejam aplicadas
                customtkinter.set_appearance_mode("Dark")
                self.logger.info(f"Tema personalizado '{theme_name}' aplicado com sucesso no arranque.")
            else:
                # Se o ficheiro do tema não for encontrado, volta para um modo seguro
                self.logger.error(f"Ficheiro do tema '{theme_file_name}' não encontrado. A usar tema padrão 'System'.")
                customtkinter.set_appearance_mode("System")
                customtkinter.set_default_color_theme("blue")

    def _open_generic_child_window(self, WindowClass: Type[customtkinter.CTkToplevel], window_key: str, modal: bool = True, **specific_params: Any):
        if window_key in self.active_windows and self.active_windows[window_key].winfo_exists():
            self.active_windows[window_key].lift()
            self.active_windows[window_key].focus_force()
            return
        
        instance = WindowClass(master=self.root, **specific_params)
        self.active_windows[window_key] = instance
        instance.protocol("WM_DELETE_WINDOW", lambda: self.close_child_window(window_key))
        if modal:
            instance.grab_set()

    def close_child_window(self, window_key: str):
        win_instance = self.active_windows.pop(window_key, None)
        if win_instance and win_instance.winfo_exists():
            win_instance.destroy()

    def open_event_manager_window(self):
        if self.main_window:
            self.main_window.show_default_view()
        self.logger.info("Visão EventManager ativada na janela principal.")

    def open_settings_window(self):
        """Abre a janela de configurações, passando todas as dependências necessárias."""
        specific_params = {
            "app_controller": self,
            "config_manager_instance": self.config_manager,
            "auth_service_instance": self.auth_service,
            "on_user_created_callback": self.on_user_created_in_settings
        }
        self._open_generic_child_window(SettingsWindow, "settings_window", modal=True, **specific_params)
        
    def on_user_created_in_settings(self):
        """Callback placeholder para quando um usuário é criado nas configurações."""
        self.logger.info("Callback: um novo usuário foi criado através da janela de configurações.")
        # Futuramente, pode-se adicionar uma lógica para atualizar listas de usuários, se houver.
        pass
        
    # Seus outros métodos para abrir janelas específicas...

    def show_main_window(self):
        if self.login_window and self.login_window.winfo_exists():
            self.login_window.destroy()
        self.login_window = None

        """Cria e exibe a janela principal da aplicação, maximizada."""
        self.logger.info("Criando e mostrando a AppWindow maximizada...")
        
        from ui.app_window import AppWindow

        # Cria a instância da sua janela principal
        self.main_window = AppWindow(master=self.root, controller=self)
        
        # Aplica o comando de maximizar à janela correta (AppWindow)
        self.main_window.state('zoomed')
        
        # Torna a AppWindow visível
        self.main_window.deiconify()
        
        # Garante que a janela raiz em branco permaneça escondida
        self.root.withdraw()

    def show_login_window(self):
        if self.main_window and self.main_window.winfo_exists():
            self.main_window.destroy()
        self.main_window = None
        self.root.withdraw()
        
        from ui.login_window import LoginWindow  # <-- ESSENCIAL
        self.login_window = LoginWindow(
            master=self.root, 
            app_controller=self,
            on_login_success_callback=self.handle_login_success,
            on_close_callback=self.handle_login_close,
            logger=self.logger.getChild("LoginWindow")
        )

    def attempt_login(self, username, password):
        """
        Chama o AuthService para validar o login e, se for sucesso,
        o AppController armazena o usuário e prossegue.
        """
        # AuthService.login agora só retorna o usuário ou None.
        user = self.auth_service.login(username, password)
        
        if user:
            # O AppController assume a responsabilidade de guardar o estado.
            self.current_user = user
            self.handle_login_success() # Chama a transição de tela
            return None # Retorna None para a UI, indicando sucesso
        else:
            # Retorna a mensagem de erro para a UI
            return self.auth_service.get_last_error()

    def handle_login_success(self):
        """Callback chamado após um login bem-sucedido."""
        # Não precisa mais receber 'user' como argumento, pois já está em self.current_user
        self.logger.info(f"Callback de sucesso de login para: {self.current_user.username}")
        if self.login_window:
            self.login_window.destroy()
            self.login_window = None
        self.show_main_window()

    def handle_login_close(self):
        self.logger.info("Janela de login fechada pelo usuário. Encerrando a aplicação.")
        self.shutdown_application(prompt=False)

    def logout(self):
        """Desloga o usuário, limpando o estado no AppController."""
        self.logger.info(f"Usuário '{self.current_user.username}' deslogado.")
        self.current_user = None # Limpa o estado da sessão
        # Não precisa mais chamar self.auth_service.logout()
        self.show_login_window() # Mostra a tela de login

    def get_current_user(self) -> Optional[User]:
        return self.auth_service.current_user
    
    def show_main_app_window(self):
        """Esconde a janela de login e mostra a janela principal da aplicação."""
        if self.login_window:
            self.login_window.destroy()
        
        # Cria a janela principal, passando a si mesmo como controller
        from ui.app_window import AppWindow
        self.main_window = AppWindow(controller=self)
        self.main_window.deiconify()

    def get_all_events(self):
        """Busca todos os eventos através do EventManager."""
        try:
            return self.event_manager.get_all_events()
        except Exception as e:
            self.logger.error(f"Erro ao buscar todos os eventos: {e}")
            return []

    def create_event(self, event_data: dict):
        """Cria um novo evento através do EventManager."""
        try:
            # Supondo que seu event_manager.create_event retorne (sucesso, mensagem)
            success, message = self.event_manager.create_event(event_data)
            if success:
                self.logger.info(f"Evento '{event_data.get('nome')}' criado com sucesso.")
            else:
                self.logger.error(f"Falha ao criar evento: {message}")
            return success, message
        except Exception as e:
            self.logger.error(f"Erro crítico ao criar evento: {e}", exc_info=True)
            return False, "Erro inesperado no sistema."
            
    def quit_app(self):
        """Encerra a aplicação de forma limpa."""
        self.logger.info("Encerrando a aplicação a pedido do usuário...")
        if self.root:
            self.root.quit()
            self.root.destroy()

    def get_all_events_summary(self):
        """Busca um resumo de todos os eventos através do EventManager."""
        try:
            return self.event_manager.get_all_events_summary()
        except Exception as e:
            self.logger.error(f"Erro ao buscar resumo de eventos: {e}", exc_info=True)
            return []

    def get_event_details(self, event_id: str):
        """Busca os detalhes de um evento específico."""
        try:
            return self.event_manager.get_event_by_id(event_id)
        except Exception as e:
            self.logger.error(f"Erro ao buscar detalhes do evento {event_id}: {e}", exc_info=True)
            return None

    def save_event(self, event_data: dict, event_id: Optional[str] = None):
        """Salva (cria ou atualiza) um evento, respeitando a assinatura de cada método."""
        try:
            if event_id:
                # A lógica de atualização, que já funciona, permanece a mesma.
                # Ela envia o dicionário diretamente.
                success = self.event_manager.update_event(event_id, event_data)
                msg = "Evento atualizado com sucesso!" if success else "Falha ao atualizar o evento."
            else:
                # LÓGICA DE CRIAÇÃO CORRIGIDA:
                # 1. Converte o dicionário da UI para o objeto EventoType, como sua função espera.
                # Adiciona um ID único aqui, pois o create_event pode precisar dele.
                event_data['id_evento'] = str(uuid.uuid4())
                novo_evento_obj = EventoType(**event_data)
                
                # 2. Chama o método com o NOME e o TIPO DE DADO corretos.
                new_id = self.event_manager.create_event(novo_evento_obj)
                
                success = new_id is not None
                msg = "Evento criado com sucesso!" if success else "Falha ao criar o evento."
            
            return success, msg
        except Exception as e:
            self.logger.error(f"Erro no controller ao salvar evento: {e}", exc_info=True)
            return False, f"Ocorreu um erro interno: {e}"

    def delete_event(self, event_id: str):
        """Deleta um evento através do EventManager."""
        self.logger.debug(f"Controller: recebido pedido para deletar evento ID: {event_id}")
        if not event_id:
            return False
        try:
            return self.event_manager.delete_event(event_id)
        except Exception as e:
            self.logger.error(f"Erro no controller ao deletar evento: {e}", exc_info=True)
            return False
    
    def run(self):
        """Inicia o ciclo de vida da aplicação, mostrando a primeira tela e o loop principal."""
        self.logger.info("Iniciando o ciclo de vida da aplicação...")
        # A lógica para mostrar o splash screen ou a tela de login já deve existir
        # em outros métodos que 'run' pode chamar.
        # Por enquanto, vamos chamar a tela de login diretamente.
        self.show_splash_screen()
        #self.show_login_window()
        self.root.mainloop()

    def get_all_users_for_settings(self) -> list:
        """Busca a lista de usuários para a tela de configurações."""
        return self.auth_service.get_all_users()

    def get_user_details_for_settings(self, user_id: int) -> dict:
        """Busca os detalhes de um usuário para preencher o formulário de edição."""
        # Supondo que você tenha um método para buscar um usuário por ID
        return self.auth_service.find_user_by_id(user_id)

    def save_user(self, user_data: dict, user_id: Optional[int] = None):
        """Salva um usuário (cria ou atualiza) a partir da tela de configurações."""
        try:
            if user_id:
                # Lógica de Atualização
                success = self.auth_service.update_user(user_id, user_data)
                msg = "Usuário atualizado com sucesso!" if success else f"Falha ao atualizar: {self.auth_service.get_last_error()}"
            else:
                # Lógica de Criação
                success = self.auth_service.create_user(**user_data)
                msg = "Usuário criado com sucesso!" if success else f"Falha ao criar: {self.auth_service.get_last_error()}"
            
            return success, msg
        except Exception as e:
            self.logger.error(f"Erro no controller ao salvar usuário: {e}", exc_info=True)
            return False, "Ocorreu um erro interno."
    
    def show_cargo_manager_window(self, event_id: str):
        from ui.cargo_manager_window import CargoManagerWindow
        """Abre a janela do Gerenciador de Cargos para um evento específico."""
        self.logger.info(f"Abrindo gerenciador de cargos para o evento ID: {event_id}")
        try:
            # Busca o objeto completo do evento para passar para a janela
            evento_obj = self.event_manager.get_event_by_id(event_id)
            if not evento_obj:
                self.logger.error(f"Evento com ID {event_id} não encontrado.")
                # from ui.dialogs import show_error (importação necessária)
                # show_error(self.main_window, "Erro", "Não foi possível encontrar o evento selecionado.")
                return

            # CORREÇÃO: A chamada agora passa todos os argumentos que a janela precisa
            cargo_win = CargoManagerWindow(
                master=self.main_window, 
                app_controller=self, 
                event_manager=self.event_manager,  # <--- Dependência que faltava
                logger=self.logger,                # <--- Dependência que faltava
                evento_selecionado=evento_obj
            )
            cargo_win.grab_set() # Mantém a janela em foco

        except Exception as e:
            self.logger.error(f"Erro ao abrir CargoManagerWindow: {e}", exc_info=True)
            # from ui.dialogs import show_error (importação necessária)
            # show_error(self.main_window, "Erro Crítico", f"Não foi possível abrir o gerenciador de cargos:\n{e}")
    
    def show_question_bank_manager_window(self, event_id: str):
        from ui.question_bank_manager_window import QuestionBankManagerWindow
        """Abre a janela do Gerenciador do Banco de Questões para um evento."""
        self.logger.info(f"Abrindo banco de questões para o evento ID: {event_id}")
        try:
            evento_obj = self.event_manager.get_event_by_id(event_id)
            if not evento_obj:
                self.logger.error(f"Evento com ID {event_id} não encontrado.")
                return

            # CORREÇÃO: Passando todas as dependências que a janela precisa
            q_bank_win = QuestionBankManagerWindow(
                master=self.main_window, 
                app_controller=self, 
                event_manager=self.event_manager,
                evento_selecionado=evento_obj,
                logger=self.logger,
                config=self.config_manager,
                docx_parser=self.docx_parser
            )
            q_bank_win.grab_set()
        except Exception as e:
            self.logger.error(f"Erro ao abrir QuestionBankManagerWindow: {e}", exc_info=True)

    def show_reference_text_manager_window(self, event_id: str):
        from ui.reference_text_manager_window import ReferenceTextManagerWindow
        """Abre a janela do Gerenciador de Textos de Referência para um evento."""
        self.logger.info(f"Abrindo gerenciador de textos de referência para o evento ID: {event_id}")
        try:
            evento_obj = self.event_manager.get_event_by_id(event_id)
            if not evento_obj:
                self.logger.error(f"Evento com ID {event_id} não encontrado.")
                return

            # CORREÇÃO: Passando todas as dependências que a janela precisa
            ref_text_win = ReferenceTextManagerWindow(
                master=self.main_window, 
                app_controller=self, 
                event_manager_instance=self.event_manager, # Verifique se o nome do parâmetro é este
                logger=self.logger,
                config=self.config_manager,
                docx_parser=self.docx_parser,
                evento_selecionado=evento_obj
            )
            ref_text_win.grab_set()
        except Exception as e:
            self.logger.error(f"Erro ao abrir ReferenceTextManagerWindow: {e}", exc_info=True)
    
    def show_proof_assembly_dashboard_window(self, event_id: str):
        """Abre o Dashboard de Montagem de Provas para um evento específico."""
        self.logger.info(f"Abrindo dashboard de montagem de provas para o evento ID: {event_id}")
        try:
            evento_obj = self.event_manager.get_event_by_id(event_id)
            if not evento_obj:
                self.logger.error(f"Evento com ID {event_id} não encontrado.")
                return

            # A importação deve ser local para evitar problemas de importação circular
            from ui.proof_assembly_dashboard_window import ProofAssemblyDashboardWindow

            # CORREÇÃO: A chamada agora passa o 'event_manager' que estava faltando
            dashboard_win = ProofAssemblyDashboardWindow(
                master=self.main_window, 
                app_controller=self,
                event_manager=self.event_manager,  # <--- O argumento que faltava
                evento_selecionado=evento_obj
            )
            dashboard_win.grab_set()
        except Exception as e:
            self.logger.error(f"Erro ao abrir ProofAssemblyDashboardWindow: {e}", exc_info=True)
        
    def get_top_level_window(self) -> Union[customtkinter.CTk, customtkinter.CTkToplevel]:
        """
        Retorna a janela de topo visível para ser usada como master para novas janelas.
        Isso garante que caixas de diálogo e novas janelas apareçam sobre a janela ativa.
        """
        # Itera sobre as janelas ativas em ordem reversa (a mais recente primeiro)
        if hasattr(self, 'active_windows'):
            for window in reversed(list(self.active_windows.values())):
                # Checa se a janela ainda existe e está visível
                if window and window.winfo_exists() and window.winfo_ismapped():
                    return window
        
        # Se nenhuma janela ativa for encontrada, retorna a janela principal
        if self.main_view and self.main_view.winfo_exists():
             return self.main_view
             
        # Como último recurso, retorna a raiz da aplicação
        return self.root
    
    def get_cargos_for_event(self, event_id: Union[str, int]) -> List[Dict[str, Any]]:
        """
        Busca os cargos associados a um evento pelo seu ID.
        Retorna uma lista de dicionários para uso na UI.
        """
        # <--- MÉTODO ADICIONADO --- >
        self.logger.debug(f"Buscando cargos para o evento ID: {event_id}")
        evento_obj = self.event_manager.get_event_by_id(event_id)
        if evento_obj and evento_obj.cargos:
            return [{'id_cargo': c.id_cargo, 'nome_cargo': c.nome_cargo} for c in evento_obj.cargos]
        return []

    def abrir_janela_montagem_prova(self, evento: 'EventoType', cargo: Optional['CargoType'] = None, on_close_callback: Optional[Callable] = None):
        """
        Abre a janela de montagem de prova (ProvaMontagemWindow).
        """
        self.logger.info(f"Abrindo janela de montagem de prova para o evento: {evento.nome_evento} | Cargo: {cargo.nome_cargo if cargo else 'Nenhum'}")
        
        try:
            from ui.prova_montagem_window import ProvaMontagemWindow
            
            window_key = f"montagem_{evento.id_evento}_{cargo.id_cargo if cargo else 'novo'}" 
            if window_key in self.active_windows and self.active_windows[window_key].winfo_exists():
                self.active_windows[window_key].lift()
                return

            # --- INÍCIO DA CORREÇÃO ---
            # 1. Busca a prova montada que já existe para este cargo.
            #    Usa o dicionário 'provas_montadas_por_cargo' que já foi carregado no objeto 'evento'.
            prova_existente = evento.provas_montadas_por_cargo.get(cargo.id_cargo) if cargo else None
            # --- FIM DA CORREÇÃO ---

            montagem_window = ProvaMontagemWindow(
                master=self.get_top_level_window(),
                app_controller=self,
                event_manager=self.event_manager,
                evento_obj=evento,
                cargo_obj=cargo,
                # --- INÍCIO DA CORREÇÃO ---
                # 2. Passa a prova encontrada (ou None) para a janela.
                #    A janela de montagem usará este objeto para carregar os dados.
                prova_montada_existente=prova_existente,
                # --- FIM DA CORREÇÃO ---
                on_close_callback=on_close_callback,
                logger=self.logger,
                config=self.config_manager.get_config(),
                docx_parser=self.docx_parser,
                event_id=evento.id_evento
            )

        except Exception as e:
            self.logger.error(f"Falha crítica ao abrir a ProvaMontagemWindow: {e}", exc_info=True)
            CTkMessagebox(title="Erro Crítico", 
                          message=f"Não foi possível abrir a janela de montagem de prova:\n{e}", 
                          icon="cancel")
    
    def get_all_question_bank_groups(self) -> List[str]:
        """
        Busca todos os nomes de 'agrupamento_banco' únicos do banco de dados
        usando a conexão nativa do sqlite3.
        """
        self.logger.info("Buscando lista de todos os agrupamentos (método SQL nativo).")
        try:
            # Usa a conexão original que já funciona no resto do app
            with self.db_connection_provider() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # CORREÇÃO: Busca pela coluna correta 'disciplina_banco'
                cursor.execute("SELECT DISTINCT disciplina_banco FROM QuestoesBanco WHERE disciplina_banco IS NOT NULL ORDER BY disciplina_banco")
                rows = cursor.fetchall()
                
                # Extrai os nomes das disciplinas do banco
                disciplinas = [row['disciplina_banco'] for row in rows]
                self.logger.info(f"Disciplinas do banco encontradas: {disciplinas}")
                return disciplinas
        except sqlite3.OperationalError as e:
            self.logger.error(f"ERRO DE BANCO DE DADOS: A tabela 'QuestoesBanco' ou a coluna 'agrupamento_banco' não foi encontrada. Detalhes: {e}", exc_info=True)
            return []
        except Exception as e:
            self.logger.error(f"Falha ao buscar agrupamentos com SQL nativo: {e}", exc_info=True)
            return []

    # Em core/app_controller.py

        
    def iniciar_nova_montagem_em_branco(self, evento: EventoType, on_close_callback: Optional[Callable] = None):
        """
        Abre a janela de montagem de prova em modo de criação, sem um cargo pré-selecionado.
        A seleção do cargo será feita dentro da própria janela.
        """
        self.logger.info(f"Iniciando nova montagem em branco para o evento: {evento.nome_evento}")
        
        self.abrir_janela_montagem_prova(
            evento=evento,
            cargo=None,
            on_close_callback=on_close_callback
        )
    
    def open_prova_selecao_geracao_window(self, evento: EventoType, master_window: Any):
        """
        Carrega os dados completos do evento e abre a janela de seleção de geração.
        """
        try:
            from ui.prova_selecao_geracao_window import ProvaSelecaoGeracaoWindow

            self.logger.info(f"Controller: Carregando dados completos do evento '{evento.nome_evento}' para geração.")
            evento_completo = self.event_manager.get_event_by_id(evento.id_evento)
            
            if not evento_completo:
                CTkMessagebox(title="Erro", message="Não foi possível recarregar os dados do evento.", icon="cancel", master=master_window)
                return

            if not getattr(evento_completo, 'provas_montadas_por_cargo', None):
                self.logger.warning(f"Nenhuma prova montada encontrada para o evento '{evento.nome_evento}'.")
                CTkMessagebox(title="Aviso", 
                            message=f"Não há provas montadas para o evento '{evento.nome_evento}'.\n\nÉ necessário montar as provas de cada cargo antes de poder gerá-las.",
                            icon="warning",
                            master=master_window)
                return

            self.logger.info(f"Dados do evento carregados. Abrindo a janela de seleção com {len(evento_completo.provas_montadas_por_cargo)} provas.")

            # A chamada para a janela agora é limpa e passa as instâncias prontas.
            # SEM db_path, pois a janela não gerencia mais a conexão.
            selecao_window = ProvaSelecaoGeracaoWindow(
                master=master_window,
                app_controller=self,
                evento_selecionado=evento_completo,
                event_manager=self.event_manager, # Passa a instância pronta
                frase_manager=self.frase_manager  # Passa a instância pronta
                # Passe outros objetos que ela possa precisar, como config, logger, etc.
            )

        except Exception as e:
            self.logger.error(f"Falha crítica ao abrir a ProvaSelecaoGeracaoWindow: {e}", exc_info=True)
            CTkMessagebox(title="Erro Crítico", 
                        message=f"Não foi possível abrir a janela de seleção de provas:\n{e}",
                        icon="cancel",
                        master=master_window)
    
    # Em core/app_controller.py

    def open_prova_geracao_window(self, event_id: Optional[str] = None):
        """
        VERSÃO CORRIGIDA: Abre a janela de geração e prepara a função para iniciar a tarefa em segundo plano.
        """
        from ui.prova_geracao_window import ProvaGeracaoWindow # Importação local
        from CTkMessagebox import CTkMessagebox # Importação local

        if not event_id:
            self.logger.error("Tentativa de abrir a janela de geração sem um ID de evento.")
            CTkMessagebox(title="Erro Interno", message="Não foi possível identificar o evento.", icon="cancel")
            return

        evento_obj = self.event_manager.get_event_by_id(event_id)
        if not evento_obj:
            self.logger.error(f"Evento com ID {event_id} não encontrado.")
            CTkMessagebox(title="Erro", message="Não foi possível carregar os dados do evento.", icon="cancel")
            return

        try:
            if hasattr(self, 'prova_geracao_win') and self.prova_geracao_win.winfo_exists():
                self.prova_geracao_win.lift()
                return

            # Função que executa a tarefa pesada
            def generation_task(params: dict):
                self.logger.info("Thread de geração de provas iniciada.")
                try:
                    # --- CORREÇÃO PONTUAL AQUI ---
                    # A função agora retorna 4 valores, incluindo os dados do gabarito
                    _, _, gabarito_data = self.document_generator.gerar_pacote_provas_completo(
                        evento_id_str=evento_obj.id_evento,
                        app_progress_callback=self.prova_geracao_win.update_progress_safe,
                        **params
                    )
                    
                    # Guarda os dados do gabarito na janela para serem usados mais tarde pelo botão "Gerar Gabaritos"
                    if hasattr(self.prova_geracao_win, 'set_gabarito_data'):
                        self.prova_geracao_win.set_gabarito_data(gabarito_data)

                    self.logger.info("Thread de geração de provas concluída com sucesso.")
                    self.root.after(100, lambda: CTkMessagebox(title="Sucesso", message="Geração de provas concluída!", icon="check"))
                except Exception as e:
                    self.logger.error(f"Erro na thread de geração de provas: {e}", exc_info=True)
                    self.root.after(100, lambda err=e: CTkMessagebox(title="Erro na Geração", message=f"Ocorreu um erro: {err}", icon="cancel"))
                finally:
                    # Reativa os botões da janela de forma segura
                    if hasattr(self, 'prova_geracao_win') and self.prova_geracao_win.winfo_exists():
                        self.prova_geracao_win.after(0, self.prova_geracao_win.enable_buttons_after_generation)

            # Função que a janela irá chamar para INICIAR a thread
            def start_generation_in_background(params: dict):
                thread = threading.Thread(target=generation_task, args=(params,), daemon=True)
                thread.start()

            # Cria a janela, passando a função de arranque como callback
            self.prova_geracao_win = ProvaGeracaoWindow(
                master=self.root,
                event_manager_instance=self.event_manager,
                evento_selecionado=evento_obj,
                app_controller=self,
                start_generation_callback=start_generation_in_background
            )

        except Exception as e:
                self.logger.error(f"Erro na thread de geração: {e}", exc_info=True)
                # A correção é passar 'e' como um argumento para a lambda, capturando o seu valor.
                self.root.after(100, lambda err=e: CTkMessagebox(title="Erro na Geração", message=f"Ocorreu um erro: {err}", icon="cancel"))
    
    # Coloque esta função dentro da sua classe AppController

    def gerar_pacote_de_provas(self, evento_id, cargos_ids, output_folder, format_options, progress_callback=None):
        """
        Orquestra a geração do pacote de provas de forma inteligente.
        Lê as definições de geração salvas para cada cargo e decide se a
        geração é para provas-modelo ou individual por candidato (carregando o CSV).
        """
        try:
            self.logger.info(f"Iniciando processo de geração de pacote completo para evento {evento_id}")
            evento = self.event_manager.get_event_by_id(evento_id)
            if not evento:
                self.logger.error("Evento não encontrado para geração.")
                return False, "Evento não encontrado."

            provas_selecionadas = {
                cargo_id: prova for cargo_id, prova in evento.provas_montadas_por_cargo.items()
                if cargo_id in cargos_ids
            }
            
            if not provas_selecionadas:
                return False, "Nenhuma prova válida selecionada para geração."

            # --- 1. LÓGICA INTELIGENTE PARA CARREGAR DADOS DE CANDIDATOS ---
            
            candidatos_data_por_cargo = {}
            # Itera sobre as provas que serão geradas para verificar as regras salvas
            for cargo_id, prova in provas_selecionadas.items():
                definicoes = prova.metadados_prova.get("definicao_geracao", {})
                
                # Se a regra "geracao_individual" estiver ligada nos metadados...
                if definicoes.get("geracao_individual"):
                    caminho_csv = definicoes.get("caminho_csv_candidatos")
                    if caminho_csv and os.path.exists(caminho_csv):
                        self.logger.info(f"Carregando candidatos do CSV '{caminho_csv}' para o cargo {cargo_id}")
                        
                        try:
                            with open(caminho_csv, mode='r', encoding='utf-8-sig') as infile:
                                # As colunas foram baseadas na sua tela de definição
                                colunas_obrigatorias = ['ID_CANDIDATO', 'NOME_COMPLETO_CANDIDATO', 'ID_CARGO_INSCRITO']
                                
                                reader = csv.DictReader(infile, delimiter=';')
                                # Heurística para tentar vírgula se ponto e vírgula falhar
                                if not all(col in reader.fieldnames for col in colunas_obrigatorias):
                                    infile.seek(0)
                                    reader = csv.DictReader(infile, delimiter=',')

                                # Filtra apenas os candidatos que pertencem ao cargo atual
                                lista_candidatos_cargo = [row for row in reader if row.get('ID_CARGO_INSCRITO') == cargo_id]
                                
                                if lista_candidatos_cargo:
                                    candidatos_data_por_cargo[cargo_id] = lista_candidatos_cargo
                                    self.logger.info(f"Encontrados {len(lista_candidatos_cargo)} candidatos para o cargo {cargo_id}.")
                                else:
                                    self.logger.warning(f"Nenhum candidato correspondente ao cargo ID '{cargo_id}' encontrado no CSV.")
                        except Exception as e_csv:
                            self.logger.error(f"Falha ao ler o arquivo CSV '{caminho_csv}': {e_csv}")
                    else:
                        self.logger.warning(f"Geração individual para o cargo {cargo_id} solicitada, mas o arquivo CSV não foi encontrado ou não está definido.")

            # --- 2. PREPARAÇÃO DOS PARÂMETROS DE GERAÇÃO ---
            
            # Obtém o número de linhas de rascunho das opções gerais
            num_linhas_rascunho = format_options.get("num_linhas_rascunho", 30)
            
            # Torna os parâmetros mais flexíveis, lendo-os das opções gerais
            manter_docx = format_options.get("manter_docx_corpo_global", False)
            gerar_zip = format_options.get("gerar_zip_final_global", True)
            gerar_gabarito_simples = format_options.get("gerar_gabarito_simplificado_global", True)
            template_prova = format_options.get("template_path")

            # --- 3. CHAMADA FINAL PARA O GERADOR DE DOCUMENTOS ---
            
            # A chamada agora usa o dicionário que acabamos de preencher.
            # Se nenhuma prova for individual, ele estará vazio, como na versão original.
            caminho_final, _, _ = self.document_generator.gerar_pacote_provas_completo(
                evento_id_str=evento.id_evento,
                provas_montadas_selecionadas_map=provas_selecionadas,
                candidatos_data_por_cargo=candidatos_data_por_cargo, # <-- USA O DICIONÁRIO PREENCHIDO
                output_dir_base_lote_param=output_folder,
                format_options_gerais=format_options,
                template_prova_path_override=template_prova,
                gerar_pdf_final_global=True, # Gerar PDF é sempre o objetivo
                manter_docx_corpo_global=manter_docx,
                gerar_zip_final_global=gerar_zip,
                gerar_gabarito_simplificado_global=gerar_gabarito_simples,
                num_linhas_rascunho=num_linhas_rascunho,
                app_progress_callback=progress_callback
            )
            
            return True, f"Pacote gerado com sucesso em:\n{caminho_final}"

        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar pacote de provas: {e}", exc_info=True)
            return False, f"Ocorreu um erro inesperado: {e}"
    
    

    def _selecionar_questoes_com_balanceamento(self, pool_de_questoes: List[QuestaoType], qtd_a_selecionar: int) -> List[QuestaoType]:
        """
        Seleciona um número de questões de um pool, garantindo balanceamento
        e um embaralhamento intercalado para evitar padrões e repetições.
        """
        if not pool_de_questoes or qtd_a_selecionar <= 0:
            return []

        # 1. Separa as questões em listas, uma para cada gabarito.
        # Esta etapa agora respeita o seu fluxo de "A sempre correto"
        # e vai colocar todas as questões no monte 'A'.
        questoes_por_gabarito = {'A': [], 'B': [], 'C': [], 'D': [], 'E': []}
        for q in pool_de_questoes:
            # No seu caso, o gabarito original será sempre 'A'.
            gabarito = getattr(q, 'resposta_correta', 'A').upper()
            if gabarito in questoes_por_gabarito:
                questoes_por_gabarito[gabarito].append(q)

        # Embaralha a lista principal de questões 'A'
        random.shuffle(questoes_por_gabarito['A'])
        
        # Simplesmente pega as primeiras 'qtd_a_selecionar' questões, pois
        # o balanceamento real acontecerá no DocumentGenerator.
        prova_final = questoes_por_gabarito['A'][:qtd_a_selecionar]
        
        # Embaralha a ordem final das questões selecionadas
        random.shuffle(prova_final)

        self.logger.info(f"Seleção aleatória de {len(prova_final)} questões concluída.")
        return prova_final
    
    # PASSO 2: Modifique a função 'populate_exam_with_questions' para usar a nova lógica
    def populate_exam_with_questions(self, exam_structure: List['BlocoQuestoesType']) -> List['BlocoQuestoesType']:
        """
        Preenche a estrutura da prova com questões sorteadas aleatoriamente do banco.
        O balanceamento e embaralhamento final ocorrerá no DocumentGenerator.
        """
        self.logger.info("Populando prova com questões (sorteio simples).")
        try:
            with self.db_connection_provider() as conn:
                cursor = conn.cursor()

                for bloco in exam_structure:
                    print(f"[DEBUG] Bloco: {bloco.nome_disciplina_prova} | Agrupamento: {bloco.agrupamento_banco} | Qtd: {bloco.qtd_questoes}")
                    disciplina_selecionada = getattr(bloco, 'agrupamento_banco', None)
                    qtd_questoes = int(bloco.qtd_questoes) if bloco.qtd_questoes is not None else 0

                    if not disciplina_selecionada or qtd_questoes <= 0:
                        continue
                    
                    # Sorteio aleatório simples
                    sql_questoes = "SELECT * FROM QuestoesBanco WHERE disciplina_banco = ? ORDER BY RANDOM() LIMIT ?"
                    cursor.execute(sql_questoes, (disciplina_selecionada, qtd_questoes))
                    questoes_rows = cursor.fetchall()
                    
                    bloco.questoes = []
                    for q_row in questoes_rows:
                        questao_dict = dict(q_row)
                        questao_dict = trata_campos_json(questao_dict)
                        
                        # PATCH: Corrigir enunciado_formatado se for string
                        import json
                        enf = questao_dict.get('enunciado_formatado')
                        if isinstance(enf, str):
                            try:
                                questao_dict['enunciado_formatado'] = json.loads(enf)
                            except Exception:
                                questao_dict['enunciado_formatado'] = []
                        # PATCH: Garantir id_texto_ref_vinculado preenchido corretamente
                        if not questao_dict.get('id_texto_ref_vinculado') and questao_dict.get('metadados_questao', {}).get('id_texto_referencia'):
                            questao_dict['id_texto_ref_vinculado'] = questao_dict['metadados_questao']['id_texto_referencia']
                        
                        print("DICT QUESTAO ANTES DE QuestaoType:", questao_dict)
                        questao_obj = QuestaoType(**questao_dict)
                        
                        sql_opcoes = "SELECT * FROM OpcoesQuestao WHERE id_questao_fk = ? ORDER BY ordem_original"
                        cursor.execute(sql_opcoes, (questao_obj.id_questao,))
                        opcoes_rows = cursor.fetchall()
                        # PATCH: Corrigir texto_opcao_formatado em cada opção
                        opcoes_obj = []
                        for o_row in opcoes_rows:
                            opcao_dict = dict(o_row)
                            tof = opcao_dict.get('texto_opcao_formatado')
                            if isinstance(tof, str):
                                try:
                                    opcao_dict['texto_opcao_formatado'] = json.loads(tof)
                                except Exception:
                                    opcao_dict['texto_opcao_formatado'] = []
                            opcoes_obj.append(OpcaoMultiplaEscolha(**opcao_dict))
                        questao_obj.opcoes = opcoes_obj
                        
                        bloco.questoes.append(questao_obj)
                    
                    self.logger.info(f"Bloco '{disciplina_selecionada}' foi populado com {len(bloco.questoes)} questões.")

                return exam_structure
        except Exception as e:
            self.logger.error(f"Falha crítica ao popular prova com questões: {e}", exc_info=True)
            return exam_structure
    
    def start_answer_key_generation_in_background(self, gabarito_data, output_folder, nome_base_cargos, gerar_simplificado):
        """Inicia a geração APENAS dos gabaritos em uma thread separada."""
        
        def task():
            self.logger.info("Thread de geração de gabaritos iniciada.")
            try:
                self.document_generator.gerar_apenas_gabaritos(
                    gabaritos_data=gabarito_data,
                    output_dir=output_folder,
                    nome_base_cargos=nome_base_cargos,
                    gerar_simplificado=gerar_simplificado
                )
                self.root.after(100, lambda: CTkMessagebox(title="Sucesso", message="Gabaritos gerados com sucesso!", icon="check"))
            except Exception as e:
                self.logger.error(f"Erro na thread de geração de gabaritos: {e}", exc_info=True)
                self.root.after(100, lambda err=e: CTkMessagebox(title="Erro", message=f"Erro ao gerar gabaritos: {err}", icon="cancel"))

        thread = threading.Thread(target=task, daemon=True)
        thread.start()
    
    def gerar_gabaritos_para_cargo(self, evento, cargo, gabaritos_por_variacao, dir_saida_cargo):
        """
        Gera os arquivos de gabarito (completo e simplificado) para o cargo informado.
        """
        from core.utils import sanitize_filename

        nome_cargo_sanitizado = sanitize_filename(cargo.nome_cargo)
        todos_gabaritos_gerados_no_lote = []
        todos_arquivos_finais_gerados_no_lote = []

        # Gabarito Completo (todos os tipos juntos)
        gab_completo_filename = sanitize_filename(
            f"GABARITO_COMPLETO_{evento.evento}_{cargo.codigo_cargo}.csv"
        )
        gab_completo_path = os.path.join(dir_saida_cargo, gab_completo_filename)
        if self.document_generator.answer_key_generator.generate_complete_csv(gab_completo_path, gabaritos_por_variacao):
            todos_gabaritos_gerados_no_lote.append(gab_completo_path)
            todos_arquivos_finais_gerados_no_lote.append(gab_completo_path)
            self.logger.info(f"Gabarito completo para {nome_cargo_sanitizado} gerado.", "info")

        # Gabarito Simples (uma linha por tipo de prova)
        gerar_gabarito_simplificado_global = True  # Ajuste se isso vier de configuração externa
        if gerar_gabarito_simplificado_global:
            gab_simples_filename = sanitize_filename(
                f"GABARITO_SIMPLES_{evento.evento}_{cargo.codigo_cargo}.csv"
            )
            gab_simples_path = os.path.join(dir_saida_cargo, gab_simples_filename)
            if self.document_generator.answer_key_generator.generate_simple_row_based_csv(
                filepath=gab_simples_path,
                cargo_obj=cargo,
                gabaritos_por_variacao=gabaritos_por_variacao
            ):
                todos_gabaritos_gerados_no_lote.append(gab_simples_path)
                todos_arquivos_finais_gerados_no_lote.append(gab_simples_path)
                self.logger.info(f"Gabarito simples para {nome_cargo_sanitizado} gerado.", "info")

        if not todos_gabaritos_gerados_no_lote:
            self.logger.info(f"Sem dados de gabarito para {nome_cargo_sanitizado}.", "warning")

        # Você pode retornar os caminhos dos arquivos gerados, se quiser
        return todos_gabaritos_gerados_no_lote

    def gerar_gabarito_completo_evento(self, evento, output_path):
        """
        Gera um único arquivo de gabarito completo do evento (todos os cargos e tipos no mesmo arquivo).
        """
        all_rows = []
        for cargo in evento.cargos:
            gabaritos_por_variacao = self.document_generator.gerar_gabaritos_balanceados_por_variacao(evento, cargo)
            for variacao, dados_gabarito in gabaritos_por_variacao.items():
                for item in dados_gabarito:
                    row = {
                        "Código do Cargo": getattr(cargo, "codigo_cargo", ""),
                        "Cargo": getattr(cargo, "nome_cargo", ""),
                        "Tipo de Prova": variacao,
                        "numero_questao_exibido": item.get("numero_questao_exibido"),
                        "disciplina_nome": item.get("disciplina_nome"),
                        "gabarito_letra_exibida": item.get("gabarito_letra_exibida"),
                        "texto_opcao_correta_original": item.get("texto_opcao_correta_original"),
                        "questao_id_original": item.get("questao_id_original"),
                    }
                    all_rows.append(row)
        headers = [
            "Código do Cargo", "Cargo", "Tipo de Prova",
            "numero_questao_exibido", "disciplina_nome",
            "gabarito_letra_exibida", "texto_opcao_correta_original", "questao_id_original"
        ]
        with open(output_path, "w", encoding="utf-8-sig", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=';')
            writer.writeheader()
            for row in all_rows:
                writer.writerow(row)

    def gerar_gabarito_simplificado_evento(self, evento, output_path):
        """
        Gera um único arquivo de gabarito simplificado do evento (uma linha por tipo/cargo, respostas em colunas Q1, Q2,...).
        """
        all_rows = []
        max_questoes = 0

        # Descobrir o maior número de questões entre todas as variações de todos os cargos
        for cargo in evento.cargos:
            gabaritos_por_variacao = self.document_generator.gerar_gabaritos_balanceados_por_variacao(evento, cargo)
            for dados_gabarito in gabaritos_por_variacao.values():
                max_questoes = max(max_questoes, len(dados_gabarito))

        question_headers = [f"Q{i+1}" for i in range(max_questoes)]
        headers = ["Código do Cargo", "Cargo", "Tipo de Prova"] + question_headers

        # Monta as linhas
        for cargo in evento.cargos:
            gabaritos_por_variacao = self.document_generator.gerar_gabaritos_balanceados_por_variacao(evento, cargo)
            for variacao, dados_gabarito in gabaritos_por_variacao.items():
                row = {
                    "Código do Cargo": getattr(cargo, "codigo_cargo", ""),
                    "Cargo": getattr(cargo, "nome_cargo", ""),
                    "Tipo de Prova": variacao
                }
                for idx, item in enumerate(dados_gabarito):
                    row[f"Q{idx+1}"] = item.get("gabarito_letra_exibida")
                all_rows.append(row)

        with open(output_path, "w", encoding="utf-8-sig", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=';')
            writer.writeheader()
            for row in all_rows:
                writer.writerow(row)
