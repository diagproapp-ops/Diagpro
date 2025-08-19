import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_FILENAME = "app_config.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / DEFAULT_CONFIG_FILENAME

class ConfigManager:
    def __init__(self, config_path: Optional[Path] = None):
        self.PROJECT_ROOT = Path(__file__).resolve().parent.parent
        self.config_path = config_path if config_path else (self.PROJECT_ROOT / "app_config.json")
        self._config_data: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Carrega o arquivo de configuração JSON. Se não existir, cria um com os padrões."""
        try:
            logger.info(f"Tentando carregar arquivo de configuração de: {self.config_path}")
            if not self.config_path.exists():
                logger.warning(f"Arquivo de configuração não encontrado. Criando um novo com configurações padrão.")
                self._config_data = self._get_default_config()
                self._save_config() # Salva o arquivo padrão para que ele exista no disco
                return

            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_data = json.load(f)
            logger.info(f"Configurações carregadas com sucesso de {self.config_path}.")

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON do arquivo {self.config_path}: {e}", exc_info=True)
            self._config_data = self._get_default_config()
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar config de {self.config_path}: {e}", exc_info=True)
            self._config_data = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Retorna estrutura padrão 100% portátil para qualquer computador."""
        logger.info("Retornando configuração padrão para distribuição.")
        return {
            "default_theme": "System",
            "default_ui_scaling": "100%",
            "output_dir_base": "ProvasGeradas",
            "media_files_base_dir": "media_files",
            "templates_base_dir": "templates",
            "log_level": "INFO",
            "logging": {
                "level": "INFO",
                "file": "logs/diagprooff_app.log",
                "format": "%(asctime)s - %(levelname)s - [%(name)s:%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
                "date_format": "%Y-%m-%d %H:%M:%S",
                "max_bytes": 5242880,
                "backup_count": 3
            },
            "database": {
                "path": "data/diagprooff.db",
                "timeout": 15.0
            },
            "paths": {
                "logo_path_light": "assets/logo_escura.png",
                "logo_path_dark": "assets/logo_clara.png"
            },
            "format_options_default": {},
            "template_capa_prova_pdf": None,
            "template_prova_docx": None,
            "max_recent_files": 10,
            "user_profile_id": None,
            "auto_save_interval_minutes": 5,
            "application_settings": {
                "appearance_mode": "Dark",
                "company_name": "",
                "company_cnpj": "",
                "company_address": "",
                "company_phone": "",
                "company_email": "",
                "company_website": "",
                "company_logo_path": ""
            }
        }
    
    def _save_config(self):
        """Salva os dados de configuração atuais no arquivo JSON."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Configurações salvas com sucesso em {self.config_path}.")
        except Exception as e:
            logger.error(f"Não foi possível salvar o arquivo de configuração em {self.config_path}: {e}", exc_info=True)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Busca primeiro em application_settings, depois no nível raiz do config."""
        app_settings = self._config_data.get("application_settings", {})
        if key in app_settings:
            return app_settings.get(key)
        # busca no nível raiz, se não encontrou
        return self._config_data.get(key, default)

    def save_setting(self, key: str, value: Any):
        """Salva um valor na seção 'application_settings' e persiste no arquivo."""
        if "application_settings" not in self._config_data:
            self._config_data["application_settings"] = {}
        
        self._config_data["application_settings"][key] = value
        self._save_config()

    # --- MÉTODOS ORIGINAIS E ROBUSTOS (MANTIDOS) ---

    def get_config_section(self, section_name: str) -> Dict[str, Any]:
        """Retorna uma seção inteira da configuração."""
        return self._config_data.get(section_name, {})

    def get_db_config(self) -> Dict[str, Any]:
        """Retorna as configurações do banco de dados."""
        return self.get_config_section("database")

    def get_db_path(self) -> str:
        """Retorna o caminho para o arquivo do banco de dados, garantindo que a pasta exista."""
        db_conf = self.get_db_config()
        path_str = db_conf.get("path", str(PROJECT_ROOT / "data" / "diagpro_default.db"))
        if not Path(path_str).is_absolute():
            abs_path = PROJECT_ROOT / path_str
        else:
            abs_path = Path(path_str)
        abs_path.parent.mkdir(parents=True, exist_ok=True)  # Garante que a pasta do banco existe
        return str(abs_path)

    def get_log_config(self) -> Dict[str, Any]:
        """Retorna o dicionário de configuração de logging completo."""
        logging_section_from_json = self._config_data.get("logging", {})
        defaults = self._get_default_config().get("logging", {})

        final_config = defaults.copy()
        final_config.update(logging_section_from_json)

        log_file_path = Path(final_config["file"])
        if not log_file_path.is_absolute():
            final_config["file"] = str(PROJECT_ROOT / log_file_path)

        return final_config

    def get_app_settings(self) -> Dict[str, Any]:
        """Retorna as configurações gerais da aplicação."""
        return self.get_config_section("application_settings")

    def get_path_config(self) -> Dict[str, Any]:
        """Retorna as configurações de caminhos, resolvendo para caminhos absolutos."""
        path_conf = self.get_config_section("paths")
        resolved_paths = {}
        for key, value in path_conf.items():
            if isinstance(value, str) and not Path(value).is_absolute():
                resolved_paths[key] = str(PROJECT_ROOT / value)
            else:
                resolved_paths[key] = value
        return resolved_paths

    def get_specific_path(self, path_key: str) -> Optional[str]:
        """Retorna um caminho específico da seção 'paths', resolvido para absoluto."""
        path_conf = self.get_path_config()
        return path_conf.get(path_key)

    def reload_config(self):
        """Recarrega o arquivo de configuração."""
        logger.info("Recarregando configurações...")
        self._load_config()
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Retorna um valor do nível raiz da configuração carregada."""
        return self._config_data.get(key, default)

    def get_resolved_path(self, key: str, default_relative_path: Optional[str] = None) -> Optional[str]:
        """
        Obtém um caminho da configuração, resolve para absoluto e retorna um padrão se não encontrado.
        Este é o método que estava faltando.
        """
        path_str = self._config_data.get(key)
        if not path_str and default_relative_path:
            path_str = default_relative_path
        
        if not path_str:
            return None

        path_obj = Path(path_str)
        if not path_obj.is_absolute():
            return str(self.PROJECT_ROOT / path_obj)
        
        return str(path_obj)
    
    def get_config(self):
        return self._config_data