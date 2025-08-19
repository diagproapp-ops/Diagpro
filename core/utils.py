#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk # Para o messagebox de fallback
from tkinter import messagebox # Especificamente messagebox
import os
import sys
import re
import json
import logging
import logging.config
import logging.handlers # Para RotatingFileHandler
from typing import TYPE_CHECKING, Dict, Any, Optional, Union, Callable, Type
import time
import random
import string
import datetime
from pathlib import Path
import traceback
import types
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import subprocess
import os
import tempfile
# Assuming DEFAULT_APP_CONFIG is correctly defined in constants.py and imported if needed here.
# If not used directly in THIS file, the import below might be specific to where constants are defined.
# from .constants import DEFAULT_APP_CONFIG 
from docx.text.paragraph import Paragraph 
from docx.enum.text import WD_UNDERLINE

if TYPE_CHECKING:
    from .config_manager import ConfigManager # Para type hinting

# Defina PROJECT_ROOT de forma confiável. Se utils.py está em core/:
PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

# Constante para o nome do arquivo de configuração de logging
LOGGING_CONFIG_FILE = 'logging_config.json'
DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
        },
        "simple": {
            "format": "%(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "DEBUG",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "standard",
            "level": "INFO",
            "filename": "diagpro_off.log", # Default filename, can be overridden by logger setup
            "mode": "a",
            "encoding": "utf-8"
        }
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG"
    },
    "loggers": {
        "werkzeug": {"level": "INFO", "handlers": ["console"], "propagate": False},
    }
}

PATH_KEYS = ["db_path", "output_dir_base", "media_dir", "temp_dir", "logging_config_path", "media_files_base_dir", "templates_base_dir"]

def resource_path(relative_path: str) -> str:
    """ Obtém o caminho absoluto para o recurso, funciona para dev e PyInstaller """
    try:
        base_path = sys._MEIPASS # type: ignore
    except AttributeError: # Changed from generic Exception for clarity
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def format_date_to_br(date_obj: Optional[Union[datetime.date, datetime.datetime]], default_if_none: str = "") -> str:
    """
    Formata um objeto date ou datetime para o padrão brasileiro (DD/MM/YYYY).
    Retorna default_if_none (string vazia por padrão) se o objeto for None.
    """
    if date_obj is None:
        return default_if_none
    try:
        return date_obj.strftime("%d/%m/%Y")
    except AttributeError: # Se não for um objeto date/datetime válido
        logger.warning(f"format_date_to_br: Recebeu objeto inválido para formatação: {date_obj}")
        return str(date_obj) # Retorna a string original ou uma representação
    except Exception as e:
        logger.error(f"Erro ao formatar data para BR: {date_obj} - {e}", exc_info=True)
        return default_if_none


def format_datetime_to_br(datetime_obj: Optional[datetime.datetime], default_if_none: str = "", include_seconds: bool = False) -> str:
    """
    Formata um objeto datetime para o padrão brasileiro (DD/MM/YYYY HH:MM ou DD/MM/YYYY HH:MM:SS).
    Retorna default_if_none (string vazia por padrão) se o objeto for None.
    """
    if datetime_obj is None:
        return default_if_none
    try:
        if include_seconds:
            return datetime_obj.strftime("%d/%m/%Y %H:%M:%S")
        else:
            return datetime_obj.strftime("%d/%m/%Y %H:%M")
    except AttributeError:
        logger.warning(f"format_datetime_to_br: Recebeu objeto inválido para formatação: {datetime_obj}")
        return str(datetime_obj)
    except Exception as e:
        logger.error(f"Erro ao formatar datetime para BR: {datetime_obj} - {e}", exc_info=True)
        return default_if_none

def parse_iso_to_datetime(iso_string: Optional[str]) -> Optional[datetime.datetime]:
    """
    Converte uma string ISO 8601 (com ou sem informações de fuso horário,
    com ou sem milissegundos) para um objeto datetime.
    Retorna None se a string for None ou inválida.
    """
    if not iso_string:
        return None
    try:
        # Tenta com milissegundos e 'Z' ou offset de fuso
        if '.' in iso_string and ('Z' in iso_string.upper() or '+' in iso_string or '-' in iso_string[10:]):
             # Remove 'Z' e trata fusos comuns (simplificado, para Python < 3.11 fromisoformat pode ser limitado)
            processed_string = iso_string.upper().replace('Z', '+00:00')
            # Python 3.7+ fromisoformat lida bem com offsets com ':'
            return datetime.datetime.fromisoformat(processed_string.split('.')[0]) # Ignora milissegundos para simplicidade se der problema
        elif '.' in iso_string: # Com milissegundos, sem fuso explícito
            return datetime.datetime.fromisoformat(iso_string.split('.')[0])
        else: # Sem milissegundos
            return datetime.datetime.fromisoformat(iso_string)
    except ValueError:
        try:
            # Tenta um formato comum sem T (YYYY-MM-DD HH:MM:SS)
            return datetime.datetime.strptime(iso_string, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.warning(f"parse_iso_to_datetime: String ISO inválida ou formato não suportado: '{iso_string}'")
            return None
    except Exception as e:
        logger.error(f"Erro ao parsear string ISO para datetime: '{iso_string}' - {e}", exc_info=True)
        return None

def format_iso_string_to_br_date(iso_string: Optional[str], default_if_none: str = "") -> str:
    """
    Converte uma string ISO (data ou datetime) para o formato de data brasileiro (DD/MM/YYYY).
    """
    dt_obj = parse_iso_to_datetime(iso_string)
    return format_date_to_br(dt_obj, default_if_none=default_if_none)

def format_iso_string_to_br_datetime(iso_string: Optional[str], default_if_none: str = "", include_seconds: bool = False) -> str:
    """
    Converte uma string ISO (data ou datetime) para o formato de datetime brasileiro (DD/MM/YYYY HH:MM(:SS)).
    """
    dt_obj = parse_iso_to_datetime(iso_string)
    return format_datetime_to_br(dt_obj, default_if_none=default_if_none, include_seconds=include_seconds)

def parse_br_date_to_datetime(br_date_str: Optional[str]) -> Optional[datetime.datetime]:
    """
    Converte uma string de data no formato brasileiro (DD/MM/YYYY) para um objeto datetime.
    Retorna None se a string for None ou inválida.
    A hora será meia-noite (00:00:00).
    """
    if not br_date_str:
        return None
    try:
        return datetime.datetime.strptime(br_date_str.strip(), "%d/%m/%Y")
    except ValueError:
        logger.warning(f"parse_br_date_to_datetime: String de data BR inválida: '{br_date_str}'")
        return None
    except Exception as e:
        logger.error(f"Erro ao parsear data BR para datetime: '{br_date_str}' - {e}", exc_info=True)
        return None

def parse_br_date_to_iso(br_date_str: Optional[str]) -> Optional[str]:
    """
    Converte uma string de data no formato brasileiro (DD/MM/YYYY) para uma string ISO (YYYY-MM-DD).
    Retorna None se a entrada for inválida.
    """
    dt_obj = parse_br_date_to_datetime(br_date_str)
    if dt_obj:
        return dt_obj.strftime("%Y-%m-%d")
    return None


def resolve_path(path_str):
    """Converte um caminho relativo a partir do PROJECT_ROOT, se não for absoluto."""
    if not path_str:
        return None
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)

def ensure_dir_exists(dir_path: str):
    """Garante que um diretório exista; cria-o se não existir."""
    path_obj = Path(dir_path)
    if not path_obj.exists():
        try:
            path_obj.mkdir(parents=True, exist_ok=True)
            # Usar print aqui é mais seguro, pois o logger pode não estar configurado ainda.
            print(f"INFO (ensure_dir_exists): Diretório criado: {dir_path}")
        except OSError as e:
            print(f"ERRO (ensure_dir_exists): Falha ao criar diretório {dir_path}: {e}")
            raise # Re-levanta a exceção para que o chamador saiba da falha



def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Limpa o nome de um arquivo removendo caracteres inválidos e truncando o comprimento.
    """
    if not filename:
        return "arquivo_sem_nome"
    # Remove caracteres inválidos para nomes de arquivo na maioria dos OS
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # Garante que apenas caracteres imprimíveis (ou tab/newline/cr) permaneçam
    sanitized = "".join(char for char in sanitized if char.isprintable() or char in ('\t', '\n', '\r'))
    # Substitui espaços múltiplos por um único underscore
    sanitized = re.sub(r'\s+', "_", sanitized)
    # Substitui underscores múltiplos por um único underscore
    sanitized = re.sub(r'_+', "_", sanitized)
    
    name_part, dot, ext_part = sanitized.rpartition('.')
    
    if not dot: # Sem extensão
        name_part = sanitized
        ext_part = ""
    
    name_part = name_part.strip('_') # Remove underscores do início/fim do nome base
    
    if not name_part: # Se o nome base ficou vazio
        name_part = "arquivo_limpo"
        
    sanitized_full_name = f"{name_part}.{ext_part}" if dot and ext_part else name_part

    # Trunca o nome do arquivo se exceder max_length, preservando a extensão
    if len(sanitized_full_name) > max_length:
        if dot and ext_part: # Se tem extensão
            # Calcula o comprimento disponível para o nome base
            available_length_for_base = max_length - (len(ext_part) + 1) # +1 para o ponto
            if available_length_for_base < 1: # Se nem a extensão cabe, trunca o nome todo
                return sanitized_full_name[:max_length]
            name_part = name_part[:available_length_for_base]
            return f"{name_part}.{ext_part}"
        else: # Sem extensão, apenas trunca
            return sanitized_full_name[:max_length]
            
    return sanitized_full_name


def load_app_config(
    config_file_path_rel: str,
    default_settings: Dict[str, Any], # This should be AppConfigType or a dict representing it
    logger_param: Optional[logging.Logger] = None
) -> Dict[str, Any]: # Returns a dict, Pydantic model conversion happens in controller
    """
    Carrega configurações da aplicação de um arquivo JSON, mesclando com padrões.
    Cria um arquivo de configuração padrão se não existir.
    Paths nos default_settings e no arquivo JSON carregado (para chaves em PATH_KEYS)
    serão resolvidos usando resource_path.
    """
    local_logger = logger_param if logger_param else logging.getLogger(__name__)
    local_logger.debug(f"Iniciando load_app_config para '{config_file_path_rel}'")

    # 1. Process default_settings: Se for um modelo Pydantic, converte para dict. Resolve paths.
    if hasattr(default_settings, 'model_dump') and callable(default_settings.model_dump): # Check if Pydantic model
        processed_defaults = default_settings.model_dump()
    elif isinstance(default_settings, dict):
        processed_defaults = default_settings.copy() # type: ignore
    else:
        local_logger.error("default_settings deve ser um dict ou Pydantic model. Usando dict vazio.")
        processed_defaults = {}

    for key, value in processed_defaults.items():
        if key in PATH_KEYS and isinstance(value, str) and value.strip() and not os.path.isabs(value):
            try:
                processed_defaults[key] = resource_path(value)
            except Exception as e_rp_def:
                local_logger.warning(f"Não foi possível resolver o path padrão para '{key}': {value}. Erro: {e_rp_def}")


    current_config = processed_defaults.copy()
    actual_config_file_path = resource_path(config_file_path_rel)
    local_logger.debug(f"Caminho absoluto para o arquivo de config: {actual_config_file_path}")

    if os.path.exists(actual_config_file_path):
        try:
            with open(actual_config_file_path, 'r', encoding='utf-8') as f:
                loaded_config_from_file = json.load(f)
            
            # Resolve paths do arquivo carregado e mescla com os defaults processados
            for key, value in loaded_config_from_file.items():
                if key in PATH_KEYS and isinstance(value, str) and value.strip() and not os.path.isabs(value):
                    try:
                        current_config[key] = resource_path(value)
                    except Exception as e_rp_load:
                         local_logger.warning(f"Não foi possível resolver o path do arquivo para '{key}': {value}. Erro: {e_rp_load}")
                else:
                    current_config[key] = value # Sobrescreve ou adiciona
            local_logger.info(f"Configuração carregada e mesclada de '{actual_config_file_path}'.")

        except json.JSONDecodeError as e:
            local_logger.error(f"Erro ao decodificar JSON de '{actual_config_file_path}': {e}. Usando config derivada dos defaults.")
        except Exception as e:
            local_logger.error(f"Erro inesperado ao carregar config de '{actual_config_file_path}': {e}. Usando config derivada dos defaults.", exc_info=True)
    else:
        local_logger.warning(f"Arquivo de config '{actual_config_file_path}' não encontrado. Usando config derivada dos defaults e tentando salvar.")
        # Tenta salvar os `default_settings` originais (com paths relativos se possível) para portabilidade
        # Se default_settings era Pydantic, usamos o dict original dele.
        save_data = default_settings.model_dump() if hasattr(default_settings, 'model_dump') else default_settings
        
        # Ensure parent directory exists before saving
        config_dir = os.path.dirname(actual_config_file_path)
        ensure_dir_exists(config_dir) # Usa a nova função aqui também

        try:
            with open(actual_config_file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
            local_logger.info(f"Arquivo de configuração padrão criado em '{actual_config_file_path}'.")
        except Exception as e_save:
            local_logger.error(f"Não foi possível criar o arquivo de config padrão em '{actual_config_file_path}': {e_save}", exc_info=True)

    return current_config


def configure_logging(config_path: Optional[str] = None, default_level: int = logging.INFO) -> None:
    """
    Configura o logging usando um arquivo JSON ou uma configuração padrão embutida.
    """
    resolved_config_path = None
    # Define LOGGING_CONFIG_FILE e DEFAULT_LOGGING_CONFIG aqui se não forem globais
    # ou se esta função for autônoma. Se são globais no módulo, podem ser usadas diretamente.

    if config_path:
        resolved_config_path = resource_path(config_path)
    elif os.path.exists(resource_path(LOGGING_CONFIG_FILE)):
        resolved_config_path = resource_path(LOGGING_CONFIG_FILE)

    final_config_to_use = None
    source_of_config = ""

    if resolved_config_path and os.path.exists(resolved_config_path):
        try:
            with open(resolved_config_path, 'rt', encoding='utf-8') as f:
                final_config_to_use = json.load(f)
            source_of_config = f"arquivo: {resolved_config_path}"
        except Exception as e:
            # Log com o logger padrão temporário, pois o logging do app pode não estar pronto
            temp_logger = logging.getLogger(__name__ + ".configure_logging")
            temp_logger.error(f"Erro ao carregar config de logging de {resolved_config_path}: {e}. Usando fallback.", exc_info=True)
            # Fallback para DEFAULT_LOGGING_CONFIG se o arquivo falhar
            final_config_to_use = DEFAULT_LOGGING_CONFIG.copy() # type: ignore
            source_of_config = "config padrão embutida (devido a erro no arquivo)"
    else:
        final_config_to_use = DEFAULT_LOGGING_CONFIG.copy() # type: ignore
        source_of_config = "config padrão embutida (arquivo não encontrado)"

    try:
        # Modifica o path do file handler na config se necessário
        if 'handlers' in final_config_to_use and 'file' in final_config_to_use['handlers']: # type: ignore
            log_file_path_from_config = final_config_to_use['handlers']['file'].get('filename', 'app_default.log') # type: ignore
            # Garante que o diretório de logs exista (usa a nova função)
            log_dir = os.path.dirname(resource_path(log_file_path_from_config)) # Resolve o path do arquivo de log
            ensure_dir_exists(log_dir) # Cria o diretório se não existir
            final_config_to_use['handlers']['file']['filename'] = os.path.join(log_dir, os.path.basename(log_file_path_from_config)) # type: ignore
        
        logging.config.dictConfig(final_config_to_use) # type: ignore
        logging.info(f"Logging configurado usando: {source_of_config}")
    except Exception as e:
        # Fallback final para basicConfig se dictConfig falhar completamente
        logging.basicConfig(level=default_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.error(f"Erro CRÍTICO ao aplicar configuração de logging ({source_of_config}): {e}. Usando BasicConfig.", exc_info=True)


def setup_logging(logger_instance: Optional[logging.Logger] = None, # logger_instance can be None to configure root
                  level: str = "INFO", 
                  log_file: Optional[str] = None,
                  log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)',
                  console_level_override: Optional[str] = None,
                  propagate_to_root: bool = True): # Adicionado controle de propagação
    """
    Configura um logger (raiz ou específico) com handlers para console e, opcionalmente, arquivo.
    Mais flexível e evita reconfiguração excessiva.
    """
    target_logger = logger_instance if logger_instance else logging.getLogger() # Alvo é o root logger se nenhum for passado
    
    # Define o nível do logger alvo
    numeric_level = logging.getLevelName(level.upper()) \
        if isinstance(level, str) and level.upper() in logging._nameToLevel \
        else (level if isinstance(level, int) else logging.INFO)
    target_logger.setLevel(numeric_level)

    # Define o formatador
    formatter = logging.Formatter(log_format)

    # --- Configuração do Console Handler ---
    # Verifica se já existe um StreamHandler para evitar duplicatas no mesmo logger
    has_console_handler = any(isinstance(h, logging.StreamHandler) for h in target_logger.handlers)
    if not has_console_handler or target_logger is logging.getLogger(): # Adiciona ao root ou se não houver
        ch = logging.StreamHandler(sys.stdout)
        console_log_level_str = (console_level_override or level).upper()
        console_numeric_level = logging.getLevelName(console_log_level_str) \
            if console_log_level_str in logging._nameToLevel \
            else numeric_level
        ch.setLevel(console_numeric_level)
        ch.setFormatter(formatter)
        target_logger.addHandler(ch)

    # --- Configuração do File Handler (opcional) ---
    if log_file:
        # Resolve o caminho absoluto do arquivo de log
        abs_log_file_path = resource_path(log_file) # Usa resource_path para consistência
        log_dir = os.path.dirname(abs_log_file_path)
        ensure_dir_exists(log_dir) # Garante que o diretório exista

        # Verifica se já existe um FileHandler para o mesmo arquivo no logger
        has_file_handler_for_this_file = any(
            isinstance(h, logging.FileHandler) and h.baseFilename == abs_log_file_path 
            for h in target_logger.handlers
        )
        if not has_file_handler_for_this_file:
            fh = logging.FileHandler(abs_log_file_path, mode='a', encoding='utf-8')
            fh.setLevel(numeric_level) # Usa o nível principal do logger para o arquivo
            fh.setFormatter(formatter)
            target_logger.addHandler(fh)
    
    # Controla a propagação para handlers do logger raiz (se não for o próprio root)
    if logger_instance: # Apenas para loggers específicos, não para o root
        target_logger.propagate = propagate_to_root

    target_logger.debug(f"Logger '{target_logger.name}' configurado/atualizado. Nível: {level}. Arquivo: {log_file if log_file else 'Nenhum'}. Propagação: {target_logger.propagate}")

def setup_application_logging(config_manager: 'ConfigManager') -> bool:
    """
    Configura o logging global da aplicação (root logger)
    usando configurações do ConfigManager (lidas do app_config.json).
    Retorna True se bem-sucedido, False caso contrário.
    """
    try:
        log_config = config_manager.get_log_config() 
        if not log_config:
            print("AVISO (setup_application_logging): Configurações de log não encontradas no ConfigManager.")
            return False

        log_level_str = log_config.get("level", "INFO").upper()
        # Assumindo que ConfigManager.get_log_config() já resolveu o caminho para ser absoluto ou utilizável
        log_file_abs_path = log_config.get("file") 
        
        log_format_str = log_config.get("format", '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
        date_format_str = log_config.get("date_format", "%Y-%m-%d %H:%M:%S")
        
        max_bytes = int(log_config.get("max_bytes", 5 * 1024 * 1024)) # Padrão 5MB
        backup_count = int(log_config.get("backup_count", 3))

        # --- Configurar o Root Logger ---
        root_logger = logging.getLogger() # Pega o logger raiz

        # Limpa handlers existentes do root logger (importante se basicConfig foi chamado antes)
        if root_logger.handlers:
            print(f"INFO (setup_application_logging): Limpando {len(root_logger.handlers)} handlers existentes do logger raiz.")
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
                handler.close() # É importante fechar o handler
        
        numeric_level = logging.getLevelName(log_level_str)
        if not isinstance(numeric_level, int): # Fallback se o nível for inválido
            print(f"AVISO (setup_application_logging): Nível de log '{log_level_str}' inválido. Usando INFO.")
            numeric_level = logging.INFO
        root_logger.setLevel(numeric_level)

        formatter = logging.Formatter(log_format_str, datefmt=date_format_str)

        # 1. Console Handler (Sempre adicionado)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(numeric_level) 
        root_logger.addHandler(console_handler)

        # 2. File Handler (com rotação, opcional)
        if log_file_abs_path:
            ensure_dir_exists(os.path.dirname(log_file_abs_path)) # Garante que o diretório logs/ exista
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file_abs_path, 
                maxBytes=max_bytes, 
                backupCount=backup_count, 
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        else:
            # Se não houver arquivo de log, não é um erro, apenas um aviso.
            print("INFO (setup_application_logging): Logging para arquivo não configurado (caminho do arquivo não fornecido).")

        # Use o logger configurado para a mensagem de sucesso
        root_logger.info(f"Logging personalizado inicializado via setup_application_logging. Nível: {log_level_str}. Arquivo: {log_file_abs_path or 'Nenhum'}")
        return True

    except Exception as e:
        # Se qualquer erro ocorrer durante o setup, a configuração falhou.
        print(f"ERRO CRÍTICO ao configurar logging em setup_application_logging: {e}")
        traceback.print_exc() # Imprime o traceback completo para ajudar a depurar
        # Fallback para basicConfig se tudo mais falhar, para garantir que haja algum log
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [BasicConfigFallback] - %(message)s')
        logging.error("Falha crítica no setup_application_logging. Usando basicConfig como fallback.")
        return False
def create_global_exception_handler(
    custom_logger: logging.Logger, 
    error_dialog_callback: Optional[Callable[[str, str, Optional[tk.Misc]], None]] = None,
    root_window_for_dialog: Optional[tk.Misc] = None
) -> Callable[[Type[BaseException], BaseException, Optional[types.TracebackType]], None]:
    # ... (corpo da função create_global_exception_handler como antes)
    # Certifique-se que `import types` está no topo do arquivo para `types.TracebackType`
    # e `from typing import Type` para `Type[BaseException]`
    def global_exception_handler(
        exc_type: Type[BaseException], 
        exc_value: BaseException, 
        exc_traceback: Optional[types.TracebackType]
    ):
        error_message_full = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        custom_logger.critical(f"Exceção global não tratada:\n{error_message_full}", exc_info=(exc_type, exc_value, exc_traceback))
        if error_dialog_callback:
            user_friendly_message = f"Ocorreu um erro inesperado na aplicação: {exc_value}\n\n" \
                                    "Recomenda-se salvar seu trabalho (se possível) e reiniciar a aplicação.\n" \
                                    "Consulte os logs para detalhes técnicos."
            try:
                parent_for_dialog = root_window_for_dialog
                if parent_for_dialog and not parent_for_dialog.winfo_exists():
                    parent_for_dialog = None
                error_dialog_callback("Erro Inesperado na Aplicação", user_friendly_message, parent_for_dialog)
            except Exception as e_dialog:
                custom_logger.error(f"Falha ao exibir o diálogo de erro global: {e_dialog}", exc_info=True)
                try:
                    temp_root = None
                    if not parent_for_dialog:
                        temp_root = tk.Tk()
                        temp_root.withdraw()
                        parent_for_dialog = temp_root
                    messagebox.showerror("Erro Crítico", 
                                         f"Ocorreu um erro inesperado: {exc_value}\n"
                                         "A aplicação pode precisar ser reiniciada.", 
                                         parent=parent_for_dialog)
                    if temp_root:
                        temp_root.destroy()
                except Exception as e_tk_fallback:
                    custom_logger.error(f"Falha até no messagebox de fallback do Tkinter: {e_tk_fallback}")
    return global_exception_handler


def setup_global_exception_handler(
    logger_to_use: Optional[logging.Logger] = None,
    dialog_callback: Optional[Callable[[str, str, Optional[tk.Misc]], None]] = None,
    root_window: Optional[tk.Misc] = None
) -> None:
    """
    Define o manipulador global de exceções para a aplicação.
    """
    # A linha problemática estava aqui:
    actual_logger = logger_to_use if logger_to_use else logger # <--- CORRIGIDO AQUI (usa 'logger' do módulo)
    
    handler_func = create_global_exception_handler(actual_logger, dialog_callback, root_window)
    sys.excepthook = handler_func
    actual_logger.info("Manipulador global de exceções configurado.")

# --- Mantenha suas outras funções utilitárias aqui ---
# Ex: resource_path, format_date_to_br, parse_iso_to_datetime, sanitize_filename,
# load_app_config (embora esta lógica possa estar melhor no ConfigManager),
# configure_logging (se quiser manter a opção de dictConfig para outros usos),
# a função setup_logging original (se usada para loggers específicos não-raiz),
# get_project_root, add_html_to_paragraph, salvar_configuracao_app, etc.
# A função setup_logging que você colou pode ser removida se setup_application_logging a substituir para o logger raiz.

# É importante que a função que main.py chama (seja setup_file_logging ou setup_application_logging)
# esteja definida neste arquivo e funcione como esperado.

def get_project_root() -> str:
    """ Retorna o caminho raiz do projeto. """
    # Assume que utils.py está em core/, então ../ sobe para o root do projeto
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def add_html_to_paragraph(paragraph: Paragraph, html_content: str):
    """
    Adiciona conteúdo HTML a um `paragraph` do python-docx, processando tags básicas
    como <b>, <i>, <u>, e <br>.
    """
    if not html_content:
        return

    # Normaliza entidades HTML comuns e tags <br>
    processed_html = html_content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&nbsp;', '\u00A0')
    # Trata <br>, <br/>, <BR>, <BR/> de forma case-insensitive e com ou sem auto-fechamento
    processed_html = re.sub(r'<br\s*/?>', '\n', processed_html, flags=re.IGNORECASE)
    
    # Divide o conteúdo em segmentos baseados nas tags de formatação
    # A regex agora captura as tags e o texto entre elas
    segments = re.split(r'(<(/?)b>|<(/?)i>|<(/?)u>)', processed_html, flags=re.IGNORECASE)
    
    current_bold = False
    current_italic = False
    current_underline = False

    for segment in filter(None, segments): # Remove segmentos vazios resultantes do split
        segment_lower = segment.lower() # Para comparação case-insensitive das tags

        if segment_lower == '<b>': current_bold = True; continue
        if segment_lower == '</b>': current_bold = False; continue
        if segment_lower == '<i>': current_italic = True; continue
        if segment_lower == '</i>': current_italic = False; continue
        if segment_lower == '<u>': current_underline = True; continue
        if segment_lower == '</u>': current_underline = False; continue
        
        # Se não for uma tag de formatação, é texto (ou uma tag não suportada, que será impressa)
        # Agora, processa quebras de linha dentro deste segmento de texto
        text_lines = segment.split('\n')
        for i, text_line in enumerate(text_lines):
            if text_line: # Adiciona texto se não for vazio
                run = paragraph.add_run(text_line)
                run.bold = current_bold
                run.italic = current_italic
                if current_underline:
                    run.underline = WD_UNDERLINE.SINGLE # Enum para sublinhado
            
            if i < len(text_lines) - 1: # Se não for a última linha deste segmento, adiciona <br>
                paragraph.add_run().add_break()


def salvar_configuracao_app(config_data: Dict[str, Any], config_file_rel: str = "app_config.json") -> bool:
    """Salva as configurações da aplicação em um arquivo JSON no caminho relativo resolvido."""
    # Usa AppConfigType se config_data for uma instância, senão assume dict.
    # Idealmente, esta função receberia um AppConfigType e faria model_dump()
    # Mas para manter compatibilidade se for chamada com dict, verificamos.
    data_to_save = config_data
    if hasattr(config_data, 'model_dump') and callable(config_data.model_dump):
         data_to_save = config_data.model_dump(mode='json') # Garante serialização Pydantic adequada
    elif not isinstance(config_data, dict):
        logging.getLogger(__name__).error("salvar_configuracao_app: config_data não é dict nem Pydantic model.")
        return False


    config_path_abs = resource_path(config_file_rel)
    try:
        ensure_dir_exists(os.path.dirname(config_path_abs)) # Garante que o diretório existe
        with open(config_path_abs, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        logging.getLogger(__name__).info(f"Configurações da aplicação salvas em '{config_path_abs}'.")
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"Não foi possível salvar as configurações da aplicação em '{config_path_abs}': {e}", exc_info=True)
        return False

def carregar_settings_usuario(settings_file_rel: str = "user_settings.json") -> Dict[str, Any]:
    """Carrega as configurações do usuário de um arquivo JSON. Retorna um dicionário vazio se não encontrar."""
    settings_path_abs = resource_path(settings_file_rel)
    if os.path.exists(settings_path_abs):
        try:
            with open(settings_path_abs, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.getLogger(__name__).error(f"Erro ao carregar configurações do usuário de '{settings_path_abs}': {e}. Retornando config vazia.", exc_info=True)
            return {}
    return {} # Retorna dict vazio se o arquivo não existir

def salvar_settings_usuario(settings_data: Dict[str, Any], settings_file_rel: str = "user_settings.json") -> bool:
    """Salva as configurações do usuário em um arquivo JSON."""
    settings_path_abs = resource_path(settings_file_rel)
    try:
        ensure_dir_exists(os.path.dirname(settings_path_abs)) # Garante que o diretório existe
        with open(settings_path_abs, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, indent=4, ensure_ascii=False)
        logging.getLogger(__name__).info(f"Configurações do usuário salvas em '{settings_path_abs}'.")
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"Não foi possível salvar as configurações do usuário em '{settings_path_abs}': {e}", exc_info=True)
        return False

# Exemplo de como você pode chamar o setup_logging para o logger deste módulo utils, se necessário.
# logger_utils = logging.getLogger(__name__)
# setup_logging(logger_instance=logger_utils, level="DEBUG")

def gerar_novo_codigo_unico(db_manager, tabela, coluna, prefix="COD_", length=8, random_k=4):
    """
    Gera um novo código único para uma tabela e coluna específicas.
    Consulta o banco de dados para garantir a unicidade.

    Args:
        db_manager: Instância do DBManager para interagir com o banco de dados.
        tabela (str): Nome da tabela onde o código será usado.
        coluna (str): Nome da coluna que deve ser única.
        prefix (str, optional): Prefixo para o código gerado. Defaults to "COD_".
        length (int, optional): Número de dígitos do timestamp a serem usados. Defaults to 8.
        random_k (int, optional): Número de caracteres aleatórios no sufixo. Defaults to 4.

    Returns:
        str: Um código único gerado.
    """
    if not db_manager:
        # logger.error("DBManager não fornecido para gerar_novo_codigo_unico.") # Se estiver usando logger
        print("ERRO: DBManager não fornecido para gerar_novo_codigo_unico.")
        # Retorna um código pseudo-aleatório sem verificação de unicidade como fallback,
        # mas isso não é ideal. O chamador deve lidar com a ausência do db_manager.
        timestamp_part = str(int(time.time() * 1000000))[-length:]
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=random_k))
        return f"{prefix}TEMP_{timestamp_part}_{random_suffix}"

    max_tentativas = 100 # Para evitar loop infinito em caso de problema improvável
    for _ in range(max_tentativas):
        timestamp_part = str(int(time.time() * 1000000))[-length:]
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=random_k))
        codigo = f"{prefix}{timestamp_part}_{random_suffix}"
        if not db_manager.check_if_value_exists(tabela, coluna, codigo):
            return codigo
        # logger.warning(f"Colisão de código gerado '{codigo}' para {tabela}.{coluna}. Tentando novamente.") # Se usando logger
        print(f"AVISO: Colisão de código gerado '{codigo}' para {tabela}.{coluna}. Tentando novamente.")
        time.sleep(0.01) # Pequena pausa antes de tentar novamente

    # logger.error(f"Não foi possível gerar um código único para {tabela}.{coluna} após {max_tentativas} tentativas.") # Se usando logger
    raise Exception(f"Não foi possível gerar um código único para {tabela}.{coluna} após {max_tentativas} tentativas.")

# utils.py

def gerar_novo_codigo_texto_referencia(db_manager, prefix="TR_MANUAL_", length=8, random_k=4):
    """
    Gera um novo código único específico para textos de referência.
    """
    # CORREÇÃO: Use o nome real da sua tabela e o nome da coluna 'codigo_ref'.
    # O nome da coluna é quase certamente 'codigo_ref' com base no seu código da interface.
    # Você PRECISA encontrar o nome correto da tabela no seu código de banco de dados.
    nome_da_tabela_correto = "TextosReferenciaGeral"  # <-- SUBSTITUA AQUI
    nome_da_coluna_correto = "codigo_ref"
    
    return gerar_novo_codigo_unico(db_manager, nome_da_tabela_correto, nome_da_coluna_correto, prefix, length, random_k)

def gerar_novo_codigo_questao(db_manager, prefix="Q_MANUAL_", length=6, random_k=4):
    """
    Gera um novo código único específico para questões (para adição manual).
    """
    return gerar_novo_codigo_unico(db_manager, 'questoes', 'codigo_questao', prefix, length, random_k)


def flatten_pdf_with_pdftk(input_pdf, output_pdf):
    # Nunca use input == output direto!
    temp_output = output_pdf
    if os.path.abspath(input_pdf) == os.path.abspath(output_pdf):
        temp_fd, temp_output = tempfile.mkstemp(suffix=".pdf")
        os.close(temp_fd)
    try:
        subprocess.run(['pdftk', input_pdf, 'output', temp_output, 'flatten'], check=True)
        # Se usou arquivo temporário, sobrescreva o output_pdf final
        if temp_output != output_pdf:
            os.replace(temp_output, output_pdf)
        print("PDF flatten aplicado (texto garantido visível em qualquer leitor).")
        return True
    except Exception as e:
        print(f"Falha ao flattenar PDF com pdftk: {e}")
        return False


def gerar_gabarito_balanceado(n_questoes, alternativas=('A','B','C','D','E'), max_repet=2):
    """
    Gera uma lista de letras corretas balanceada e sem mais de 'max_repet' repetições seguidas.
    """
    n_alt = len(alternativas)
    base = n_questoes // n_alt
    sobra = n_questoes % n_alt
    letras = [alt for alt in alternativas for _ in range(base)] + list(alternativas)[:sobra]

    while True:
        random.shuffle(letras)
        ok = True
        for i in range(n_questoes - max_repet):
            if all(letras[i+j] == letras[i] for j in range(max_repet+1)):
                ok = False
                break
        if ok:
            return letras


def trata_campos_json(questao_dict):
    campos = [
        ('metadados_questao', dict),
        ('imagens_enunciado', list),
        ('imagens_enunciado_refs', list),
        ('textos_referencia_questao', list),
        ('tags_keywords', list)
    ]
    for campo, tipo in campos:
        valor = questao_dict.get(campo)
        if isinstance(valor, str):
            try:
                questao_dict[campo] = json.loads(valor)
            except Exception:
                questao_dict[campo] = tipo()
        elif valor is None:
            questao_dict[campo] = tipo()
    return questao_dict

def get_base_media_dir():
    """
    Retorna o caminho absoluto para a pasta 'media_files' na raiz do projeto,
    mesmo quando chamado de qualquer subdiretório.
    """
    # Caminho do script em execução
    if hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        # Caminho absoluto do diretório do arquivo atual (pode ser /core, /ui, etc)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Sobe até a raiz do projeto (ajuste se seu layout for diferente)
        # Supondo: projeto/ui/question_editor_window.py  ==> projeto/core/utils.py
        # Queremos .../projeto/media_files
        while not os.path.isdir(os.path.join(base_dir, "media_files")) and os.path.dirname(base_dir) != base_dir:
            base_dir = os.path.dirname(base_dir)
    return os.path.join(base_dir, "media_files")

def parse_enunciado_formatado(texto):
    result = []
    i = 0
    while i < len(texto):
        if texto[i:i+3] == '[b]':
            result.append(["tagon", "bold", str(i)])
            i += 3
        elif texto[i:i+4] == '[/b]':
            result.append(["tagoff", "bold", str(i)])
            i += 4
        elif texto[i:i+3] == '[i]':
            result.append(["tagon", "italic", str(i)])
            i += 3
        elif texto[i:i+4] == '[/i]':
            result.append(["tagoff", "italic", str(i)])
            i += 4
        elif texto[i:i+3] == '[u]':
            result.append(["tagon", "underline", str(i)])
            i += 3
        elif texto[i:i+4] == '[/u]':
            result.append(["tagoff", "underline", str(i)])
            i += 4
        elif texto[i:i+7] == '[color=':
            match = re.match(r'\[color=(.*?)\]', texto[i:])
            if match:
                cor = match.group(1)
                result.append(["color", cor, str(i)])
                i += len(match.group(0))
            else:
                i += 1
        elif texto[i:i+8] == '[/color]':
            result.append(["color", None, str(i)])  # sinaliza que deve parar a cor
            i += 8
        else:
            start = i
            while i < len(texto) and not texto[i:i+3] in ['[b]', '[i]', '[u]'] \
                    and not texto[i:i+4] in ['[/b]', '[/i]', '[/u]'] \
                    and not texto[i:i+7] == '[color=' \
                    and not texto[i:i+8] == '[/color]':
                i += 1
            if start < i:
                result.append(["text", texto[start:i], str(start)])
    return result

