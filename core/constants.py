# DiagProOFF/core/constants.py
import os

# --- Informações da Aplicação ---
APP_NAME = "DiagProOFF"
VERSION = "1.0.0" # Defina a versão atual da sua aplicação

# --- Nomes de Arquivos e Diretórios Base ---
DB_NAME = "diagprooff.db" #
CONFIG_FILE_APP = "app_config.json"
CONFIG_FILE_USER_TEMPLATE = "user_settings_{username}.json" # Placeholder para o nome do usuário

CONFIG_KEY_OUTPUT_DIR = "output_dir_base"  # Ou o nome correto da chave no seu JSON de config
DEFAULT_OUTPUT_DIR = "media_files/arquivos_importados"  # Ou o caminho padrão desejado

# --- Chaves de Configuração e Padrões para Diretórios ---
CONFIG_KEY_MEDIA_DIR = "media_files_base_dir"  # Chave usada no app_config.json
DEFAULT_MEDIA_DIR = "media_files"              # Valor padrão se a chave não for encontrada no config

# Certifique-se que DEFAULT_APP_CONFIG (definido neste arquivo ou em outro lugar e importado)
# também reflete as chaves de configuração que seu código espera, como "media_files_base_dir".
# Exemplo de como DEFAULT_APP_CONFIG poderia estar (se você não o tiver já):
# DEFAULT_APP_CONFIG = {
#     "default_theme": "System",
#     "default_ui_scaling": "100%",
#     "log_level": "INFO",
#     "media_files_base_dir": "media_files", # <--- Chave importante
#     "templates_base_dir": "templates",
#     "default_export_directory": "exports"
#     # ... outras configurações padrão ...
# }

# --- Configurações Padrão da Aplicação (DEFAULT_APP_CONFIG) ---
# Estes valores devem corresponder aos campos e tipos em AppConfigType (core/elements.py)
# Os caminhos aqui são relativos e serão combinados com o project_root em main.py
DEFAULT_APP_CONFIG = {
    "default_theme": "System",                   # "System", "Light", "Dark"
    "default_ui_scaling": "100%",                # "80%", "90%", "100%", "110%", "120%" etc.
    "log_level": "INFO",                         # "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    "media_files_base_dir": "media_files",       # Diretório para imagens de questões, etc.
    "templates_base_dir": "templates",           # Diretório para templates de documentos (DOCX, PDF)
    "default_export_directory": "exports"        # Diretório padrão para salvar provas geradas, relatórios
}

# --- Configurações Padrão do Usuário (DEFAULT_USER_SETTINGS) ---
# Estes valores devem corresponder aos campos e tipos em UserSettingsType (core/elements.py)
DEFAULT_USER_SETTINGS = {
    "theme": "System",
    "ui_scaling": "100%",
    "last_event_id": None # Ou um ID padrão se fizer sentido
    # Adicione outras configurações de usuário que você queira persistir
    # "show_tooltips": True,
    # "results_per_page": 20,
}

# --- CAMINHO PADRÃO PARA O BANCO DE DADOS ---
# Define onde o arquivo de banco de dados deve estar por padrão,
# geralmente na raiz do projeto ou em um diretório de dados específico.
# Este caminho pode ser relativo e será resolvido para um caminho absoluto
# pelo AppController usando resource_path().
DB_PATH_MAIN = DB_NAME # Simplesmente o nome do arquivo, se for para estar na raiz resolvida
# OU, se você quiser em uma subpasta 'data' dentro da raiz do projeto:
# DB_PATH_MAIN = os.path.join("data", DB_NAME) 
# (O AppController resolverá "data/diagprooff.db" para um caminho absoluto)


# --- Constantes para Modelos de Dados e UI ---
NIVEIS_CARGO = ("Fundamental", "Médio", "Superior", "Técnico", "Outro")
AREAS_CONHECIMENTO = (
    "Administração", "Direito", "Educação", "Engenharia", "Finanças", "Geral",
    "Humanas", "Saúde", "Segurança", "Tecnologia da Informação", "Outra"
)
TIPOS_QUESTAO = ("multipla_escolha", "dissertativa", "verdadeiro_falso", "associacao_colunas", "preenchimento_lacunas")
STATUS_EVENTO = ("Planejamento", "Em Andamento", "Concluído", "Cancelado", "Adiado")
TURNOS_PROVA = ("Manhã", "Tarde", "Noite", "Integral")

# --- Constantes para Campos de PDF e CSV (do seu arquivo original) ---

# Campos PDF para a capa/folha de rosto
PDF_FIELD_CARGO_TIPO = "PDF_FIELD_CARGO_TIPO" #
PDF_FIELD_FRASE = "PDF_FIELD_FRASE" #

# Novos campos para capa de provas de tipo (sem candidato)
PDF_FIELD_CODIGO_CARGO = "PDF_FIELD_CODIGO_CARGO"  # Ex: "123 - Analista"
PDF_FIELD_CODIGO_CARGO_TIPO = "PDF_FIELD_CODIGO_CARGO_TIPO"  # Ex: "123 - Analista - Tipo A"
PDF_FIELD_TIPO_APENAS_LETRA = "PDF_FIELD_TIPO_APENAS_LETRA"   # Ex: "A", "B", etc. (sem a palavra "Tipo")

# Campos PDF para informações do candidato (ajuste os nomes dos campos conforme seus PDFs)
PDF_FIELD_NOME_CANDIDATO = "NomeCompleto" #
PDF_FIELD_INSCRICAO = "Inscricao" #
PDF_FIELD_ESCOLA = "Escola" #
PDF_FIELD_SALA = "Sala" #
PDF_FIELD_ORDEM_SALA_ASSENTO = "OrdemSalaAssento" #
PDF_FIELD_DATA_NASC = "DataNascimento" #
PDF_FIELD_CPF = "CPF" #
PDF_FIELD_IDENTIDADE = "Identidade" #
PDF_FIELD_COD_ETAPA_PROVA_SISTEMA = "CodEtapaProvaSistema" #
PDF_FIELD_TEXTO_CABECALHO = "TextoCabecalhoProva" #

# Delimitador padrão para arquivos CSV
CSV_DELIMITER = ";"

# Nomes das colunas para o gabarito COMPLETO
GABARITO_QUESTAO_NUM = "Numero Questao"
GABARITO_DISCIPLINA = "Disciplina"
GABARITO_CONTEUDO = "Conteudo"
GABARITO_RESPOSTA_CORRETA = "Resposta Correta"
GABARITO_TEXTO_RESPOSTA_CORRETA = "Texto Resposta Correta"
GABARITO_TIPO_QUESTAO = "Tipo Questao"
GABARITO_PONTUACAO = "Pontuacao"

# Nomes das colunas no arquivo CSV de candidatos (ajuste conforme seu CSV)
COLUNA_NOME_COMPLETO_CSV = 'NOME_COMPLETO_CANDIDATO' #
COLUNA_ID_CANDIDATO_CSV = 'ID_CANDIDATO' #
COLUNA_TIPO_PROVA_CSV = 'TIPO_PROVA' #
COLUNA_ESCOLA_CSV = 'ESCOLA_CANDIDATO' #
COLUNA_SALA_CSV = 'SALA_CANDIDATO' #
COLUNA_ORDEM_SALA_ASSENTO_CSV = 'ORDEM_SALA_ASSENTO' #
COLUNA_DATA_NASC_CSV = 'DATA_NASCIMENTO' #
COLUNA_CPF_CSV = 'CPF_CANDIDATO' #
COLUNA_IDENTIDADE_CSV = 'IDENTIDADE_CANDIDATO' #
COLUNA_COD_ETAPA_PROVA_SISTEMA_CSV = 'COD_ETAPA_PROVA' #
COLUNA_TEXTO_CABECALHO_CSV = 'TEXTO_CABECALHO_PROVA_CSV' #

# --- Outras Constantes ---
DEFAULT_EVENT_ID_ON_STARTUP = None #

# Limites e Padrões Diversos
MAX_FILE_SIZE_UPLOAD_MB = 50
DEFAULT_PASSWORD_HASH_ITERATIONS = 260000 # Para PBKDF2HMAC

# Marcadores para Parsing de Documentos (Exemplo, se usado pelo DocxParser)
MARCADOR_INICIO_QUESTAO = "###QUESTAO_INICIO###"
MARCADOR_FIM_QUESTAO = "###QUESTAO_FIM###"
MARCADOR_TEXTO_REF_INICIO = "###TEXTO_REFERENCIA_INICIO###" # Já usado no seu DocxParser
MARCADOR_TEXTO_REF_FIM = "###TEXTO_REFERENCIA_FIM###"       # Já usado no seu DocxParser

# Constantes para tipos de log (se quiser centralizar)
LOG_TYPE_APP = "APPLICATION"
LOG_TYPE_USER_ACTION = "USER_ACTION"
LOG_TYPE_SYSTEM_EVENT = "SYSTEM_EVENT"
LOG_TYPE_ERROR = "ERROR"

# Adicione quaisquer outras constantes que sejam usadas em múltiplos lugares da sua aplicação.
# Exemplo:
# TEMPO_MAX_SESSAO_MINUTOS = 60
# URL_BASE_API_EXTERNA = "https://api.example.com/v1/"