# core/database_setup.py
import sqlite3
import os
import logging
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager



# Adiciona o diretório raiz ao path para que possamos importar de 'core'
# Isso garante que o script funcione tanto importado quanto executado diretamente.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importações dos módulos do seu projeto
# Elas são necessárias para a criação do usuário admin através do AuthService
from core.auth_service import AuthService
from core.models import create_all_tables_from_models, Base, User, BancoFrases
 

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_NAME = 'diagprooff.db'
_engine = None
_SessionLocal = None

def initialize_database(config_manager):
    """
    Função principal que inicializa o banco de dados, o engine do SQLAlchemy
    e garante que todas as tabelas sejam criadas.
    """
    logger.info("Iniciando verificação e configuração do banco de dados...")
    db_path = config_manager.get_db_path()  # USO CORRETO DO CAMINHO DO BANCO
    print(f"db_path utilizado: {db_path}")
    print(f"*** CAMINHO DO BANCO USADO: {db_path}")
    
    # Inicializa o SQLAlchemy para ter o _engine pronto
    _initialize_sqlalchemy(db_path)
    
    # --- INÍCIO DA CORREÇÃO DEFINITIVA ---
    logger.info("Criando tabelas do banco de dados (se não existirem)...")
    Base.metadata.create_all(bind=_engine)
    # --- FIM DA CORREÇÃO DEFINITIVA ---
    
    create_default_admin_user_if_needed()
    logger.info("Inicialização do banco de dados concluída.")

def get_db_connection(db_path: str = None, timeout_seconds: float = 20.0) -> sqlite3.Connection:
    """
    Cria e retorna uma nova conexão SQLite, ativando WAL e foreign keys.
    """
    if not db_path:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager()
        db_path = config_manager.get_db_path()

    try:
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Diretório do banco de dados criado: {db_dir}")

        conn = sqlite3.connect(db_path, timeout=timeout_seconds)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode=WAL;")  # <- ADICIONADO: garante modo WAL
        conn.row_factory = sqlite3.Row 
        logger.debug(f"Conexão com '{db_path}' estabelecida e configurada.")
        return conn
    except sqlite3.Error as e:
        logger.critical(f"Falha CRÍTICA ao conectar ou configurar o banco de dados em '{db_path}': {e}", exc_info=True)
        raise

def create_all_tables(conn: sqlite3.Connection):
    """Cria todas as tabelas necessárias para a aplicação, se não existirem."""
    cursor = conn.cursor()
    try:
        # --- ESTRUTURA COMPLETA DAS SUAS TABELAS ---
        # (Esta é a sua estrutura detalhada, que está ótima)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Eventos (
            id_evento TEXT PRIMARY KEY, nome_evento TEXT NOT NULL, data_prova TEXT, numero_edital TEXT,
            local_prova TEXT, instituicao_organizadora TEXT, logo_path TEXT, observacoes TEXT,
            status TEXT DEFAULT 'Planejado', qtd_cargos_estimada INTEGER DEFAULT 0, responsavel_criacao TEXT, configuracoes_evento TEXT,
            nome_curto_evento TEXT, identificador_unico_evento TEXT, data_criacao TEXT DEFAULT CURRENT_TIMESTAMP, data_modificacao TEXT DEFAULT CURRENT_TIMESTAMP,
            banco_questoes_json TEXT, is_deleted BOOLEAN NOT NULL DEFAULT FALSE, deleted_at TIMESTAMP NULL
        );
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_eventos_modificacao AFTER UPDATE ON Eventos FOR EACH ROW
            BEGIN UPDATE Eventos SET data_modificacao = CURRENT_TIMESTAMP WHERE id_evento = OLD.id_evento; END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_eventos_modificacao AFTER UPDATE ON Eventos FOR EACH ROW
            BEGIN UPDATE Eventos SET data_modificacao = CURRENT_TIMESTAMP WHERE id_evento = OLD.id_evento; END;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Cargos (
            id_cargo TEXT PRIMARY KEY, id_evento_fk TEXT NOT NULL, nome_cargo TEXT NOT NULL, codigo_cargo TEXT,
            nivel TEXT, turno TEXT, vagas INTEGER, salario REAL, requisitos TEXT, tem_discursiva INTEGER DEFAULT 0,
            letterhead_pdf_path TEXT, cover_pdf_paths TEXT, peso_total_prova REAL, metadados_cargo TEXT,
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP, data_modificacao TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_evento_fk) REFERENCES Eventos(id_evento) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_cargos_modificacao AFTER UPDATE ON Cargos FOR EACH ROW
            BEGIN UPDATE Cargos SET data_modificacao = CURRENT_TIMESTAMP WHERE id_cargo = OLD.id_cargo; END;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Disciplinas (
            id_disciplina TEXT PRIMARY KEY, id_evento_fk TEXT, nome_disciplina TEXT NOT NULL, codigo_disciplina TEXT,
            descricao TEXT, data_criacao TEXT DEFAULT CURRENT_TIMESTAMP, data_modificacao TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (id_evento_fk, nome_disciplina), UNIQUE (id_evento_fk, codigo_disciplina),
            FOREIGN KEY (id_evento_fk) REFERENCES Eventos(id_evento) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_disciplinas_modificacao AFTER UPDATE ON Disciplinas FOR EACH ROW
            BEGIN UPDATE Disciplinas SET data_modificacao = CURRENT_TIMESTAMP WHERE id_disciplina = OLD.id_disciplina; END;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Conteudos (
            id_conteudo TEXT PRIMARY KEY, id_disciplina_fk TEXT NOT NULL, nome_conteudo TEXT NOT NULL, descricao TEXT,
            palavras_chave TEXT, data_criacao TEXT DEFAULT CURRENT_TIMESTAMP, data_modificacao TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (id_disciplina_fk, nome_conteudo), FOREIGN KEY (id_disciplina_fk) REFERENCES Disciplinas(id_disciplina) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_conteudos_modificacao AFTER UPDATE ON Conteudos FOR EACH ROW
            BEGIN UPDATE Conteudos SET data_modificacao = CURRENT_TIMESTAMP WHERE id_conteudo = OLD.id_conteudo; END;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS TextosReferenciaGeral (
            id_texto_ref TEXT PRIMARY KEY,
            id_evento_fk TEXT,
            codigo_ref TEXT NOT NULL,
            titulo TEXT,
            conteudo TEXT,
            tipo_conteudo TEXT,
            caminho_imagem_relativo TEXT,
            descricao_imagem TEXT,
            metadados_texto_ref TEXT,
            conteudo_formatado TEXT,  -- <<<<<<<<<<< ADICIONE ESTA LINHA
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
            data_modificacao TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_evento_fk) REFERENCES Eventos(id_evento) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_textos_referencia_modificacao AFTER UPDATE ON TextosReferenciaGeral FOR EACH ROW
            BEGIN UPDATE TextosReferenciaGeral SET data_modificacao = CURRENT_TIMESTAMP WHERE id_texto_ref = OLD.id_texto_ref; END;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS QuestoesBanco (
            id_questao TEXT PRIMARY KEY,
            id_evento_fk TEXT,
            enunciado TEXT NOT NULL,
            enunciado_formatado TEXT, -- <<<<<< NOVO CAMPO
            tipo TEXT NOT NULL,
            disciplina_banco TEXT,
            resposta_correta TEXT,
            gabarito_preliminar TEXT,
            gabarito_definitivo TEXT,
            nivel_dificuldade TEXT,
            tempo_esperado_resposta_segundos INTEGER,
            tags_keywords TEXT,
            id_texto_ref_vinculado TEXT,
            status_revisao TEXT,
            justificativa_anulacao TEXT,
            criador_id TEXT,
            metadados_questao TEXT,
            disciplina_id TEXT,
            conteudo_id TEXT,
            conteudo_nome TEXT,
            pontuacao REAL,
            feedback_geral_questao TEXT,
            revisada BOOLEAN,
            autor_elaborador TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_modificacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            numero_questao_original_docx TEXT,
            hash_conteudo_questao TEXT,
            fonte_questao TEXT,
            anulada BOOLEAN,
            justificativa_anulacao_recurso TEXT,
            justificativa_anulacao_recurso_formatado TEXT, -- <<<<<< NOVO CAMPO
            imagens_enunciado TEXT,
            imagens_enunciado_refs TEXT,
            textos_referencia_questao TEXT,
            FOREIGN KEY (id_evento_fk) REFERENCES Eventos(id_evento) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_questoes_banco_modificacao AFTER UPDATE ON QuestoesBanco FOR EACH ROW
            BEGIN UPDATE QuestoesBanco SET data_modificacao = CURRENT_TIMESTAMP WHERE id_questao = OLD.id_questao; END;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS OpcoesQuestao (
            id_opcao_questao TEXT PRIMARY KEY,
            id_questao_fk TEXT NOT NULL,
            letra TEXT,
            texto_opcao TEXT,
            texto_opcao_formatado TEXT, -- <<<<<< NOVO CAMPO
            ordem_original INTEGER,
            correta INTEGER DEFAULT 0,
            feedback_opcao TEXT,
            imagem_path_opcao TEXT,
            FOREIGN KEY (id_questao_fk) REFERENCES QuestoesBanco(id_questao) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ItensVerdadeiroFalso (
            id_item_vf TEXT PRIMARY KEY, id_questao_fk TEXT NOT NULL, afirmacao TEXT NOT NULL,
            valor_correto INTEGER NOT NULL, feedback_item TEXT, ordem INTEGER,
            FOREIGN KEY (id_questao_fk) REFERENCES QuestoesBanco(id_questao) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS DetalhesQuestaoDiscursiva (
            id_detalhe_discursiva TEXT PRIMARY KEY, id_questao_fk TEXT NOT NULL UNIQUE,
            resposta_esperada_texto TEXT, palavras_chave_resposta TEXT, numero_linhas_resposta INTEGER,
            FOREIGN KEY (id_questao_fk) REFERENCES QuestoesBanco(id_questao) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ImagensQuestao (
            id_imagem TEXT PRIMARY KEY, id_questao_fk TEXT, id_opcao_questao_fk TEXT,
            caminho_relativo_imagem TEXT NOT NULL, descricao_imagem TEXT, tipo_associacao TEXT NOT NULL,
            data_adicao TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_questao_fk) REFERENCES QuestoesBanco(id_questao) ON DELETE CASCADE,
            FOREIGN KEY (id_opcao_questao_fk) REFERENCES OpcoesQuestao(id_opcao_questao) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ProvasMontadas (
                id_prova_montada TEXT PRIMARY KEY,
                id_evento_fk TEXT NOT NULL,
                id_cargo_fk TEXT NOT NULL,

                nome_prova_montada TEXT NOT NULL,
                identificador_prova TEXT,
                titulo_prova TEXT,
                instrucoes_gerais TEXT,
                texto_cabecalho_prova_docx TEXT,
                texto_rodape_prova_docx TEXT,
                frase_assinatura_folha_rosto TEXT,

                status_montagem TEXT DEFAULT 'Em Elaboração',
                responsavel_montagem TEXT,

                data_criacao TEXT DEFAULT CURRENT_TIMESTAMP,
                data_modificacao TEXT DEFAULT CURRENT_TIMESTAMP,
                data_ultima_geracao TEXT,

                caminho_arquivo_gerado TEXT,
                hash_prova_gerada TEXT,

                -- JSON/estruturas complexas
                estrutura_prova_json TEXT,
                blocos_questoes_json TEXT,
                textos_referencia_prova_json TEXT,
                configuracoes_prova TEXT,
                metadados_prova TEXT,

                tipo_prova TEXT,
                numero_versoes INTEGER,

                -- Outros campos que você possa precisar...

                FOREIGN KEY (id_evento_fk) REFERENCES Eventos(id_evento) ON DELETE CASCADE,
                FOREIGN KEY (id_cargo_fk) REFERENCES Cargos(id_cargo) ON DELETE CASCADE,
                UNIQUE (id_evento_fk, id_cargo_fk, identificador_prova)
            );
        """)

        # Trigger para atualizar data_modificacao automaticamente
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_provas_montadas_modificacao
            AFTER UPDATE ON ProvasMontadas
            FOR EACH ROW
            BEGIN
                UPDATE ProvasMontadas SET data_modificacao = CURRENT_TIMESTAMP WHERE id_prova_montada = OLD.id_prova_montada;
            END;
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS BlocosQuestoesProva (
            id_bloco_prova TEXT PRIMARY KEY, id_prova_montada_fk TEXT NOT NULL, id_disciplina_fk TEXT,
            titulo_bloco TEXT, instrucoes_bloco TEXT, ordem_bloco INTEGER,
            embaralhar_questoes_neste_bloco INTEGER DEFAULT 0, numero_questoes_sortear_do_bloco INTEGER,
            FOREIGN KEY (id_prova_montada_fk) REFERENCES ProvasMontadas(id_prova_montada) ON DELETE CASCADE,
            FOREIGN KEY (id_disciplina_fk) REFERENCES Disciplinas(id_disciplina) ON DELETE SET NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS QuestoesPorBlocoProva (
            id_questao_bloco_prova TEXT PRIMARY KEY, id_bloco_prova_fk TEXT NOT NULL, id_questao_banco_fk TEXT NOT NULL,
            numero_questao_na_prova INTEGER, pontuacao_especifica_nesta_prova REAL,
            FOREIGN KEY (id_bloco_prova_fk) REFERENCES BlocosQuestoesProva(id_bloco_prova) ON DELETE CASCADE,
            FOREIGN KEY (id_questao_banco_fk) REFERENCES QuestoesBanco(id_questao) ON DELETE CASCADE,
            UNIQUE (id_bloco_prova_fk, id_questao_banco_fk), UNIQUE (id_bloco_prova_fk, numero_questao_na_prova)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS DisciplinasDaProva (
            id_disciplina_prova TEXT PRIMARY KEY, id_cargo_fk TEXT NOT NULL, id_disciplina_base_fk TEXT NOT NULL,
            nome_disciplina_na_prova TEXT NOT NULL, qtd_questoes INTEGER, peso_por_questao REAL,
            observacoes TEXT, ordem_na_prova INTEGER,
            FOREIGN KEY (id_cargo_fk) REFERENCES Cargos(id_cargo) ON DELETE CASCADE,
            FOREIGN KEY (id_disciplina_base_fk) REFERENCES Disciplinas(id_disciplina) ON DELETE RESTRICT,
            UNIQUE (id_cargo_fk, id_disciplina_base_fk), UNIQUE (id_cargo_fk, nome_disciplina_na_prova)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS QuestoesSelecionadasParaDisciplinaProva (
            id_selecao TEXT PRIMARY KEY, id_disciplina_prova_fk TEXT NOT NULL, id_questao_banco_fk TEXT NOT NULL,
            ordem_na_disciplina INTEGER,
            FOREIGN KEY (id_disciplina_prova_fk) REFERENCES DisciplinasDaProva(id_disciplina_prova) ON DELETE CASCADE,
            FOREIGN KEY (id_questao_banco_fk) REFERENCES QuestoesBanco(id_questao) ON DELETE CASCADE,
            UNIQUE (id_disciplina_prova_fk, id_questao_banco_fk)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS banco_frases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            texto_frase TEXT NOT NULL,
            identificador TEXT UNIQUE,
            ativo INTEGER DEFAULT 1
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users ( 
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            full_name TEXT,
            email TEXT UNIQUE,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP,
            celular TEXT,
            endereco TEXT,
            cpf TEXT UNIQUE,
            cargo TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS UserSettings (
            user_id_fk INTEGER PRIMARY KEY, theme TEXT DEFAULT 'System', language TEXT DEFAULT 'pt_BR',
            show_tooltips INTEGER DEFAULT 1, FOREIGN KEY (user_id_fk) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS AppConfig (
            config_key TEXT PRIMARY KEY, config_value TEXT
        );
        """)

        conn.commit()
        logger.info("Estrutura de tabelas verificada/criada com sucesso.")
    except sqlite3.Error as e:
        logger.error(f"Erro durante a criação das tabelas: {e}", exc_info=True)
        conn.rollback()
        raise

def create_default_admin_user_if_needed():
    """Verifica se o usuário 'admin' existe e, se não, o cria usando o AuthService."""
    auth_service = AuthService(get_db_connection)
    
    # Verifica se o usuário 'admin' já existe
    user_dict = auth_service._fetch_one("SELECT id FROM users WHERE username = ?", ("admin",))
    
    if not user_dict:
        logger.info("Nenhum usuário 'admin' encontrado. Criando usuário administrador padrão...")
        
        admin_user = auth_service.create_user(
            username="admin",
            password="admin", # Senha padrão, o usuário deve trocar
            role="admin",
            full_name="Administrador Padrão",
            email="admin@localhost"
        )
        
        if admin_user:
            logger.info("Usuário 'admin' padrão criado com SUCESSO. A senha é 'admin'.")
        else:
            logger.error(f"FALHA ao criar usuário admin padrão. Erro: {auth_service.get_last_error()}")
    else:
        logger.info("Usuário 'admin' já existe no banco de dados.")

def init_db():
    logger.info("Iniciando verificação e configuração do banco de dados...")
    from core.config_manager import ConfigManager
    config_manager = ConfigManager()
    db_path = config_manager.get_db_path()
    conn = None
    try:
        conn = get_db_connection(db_path)
        create_all_tables(conn)
    finally:
        if conn:
            conn.close()
    create_default_admin_user_if_needed()
    logger.info("Inicialização do banco de dados concluída.")


def _initialize_sqlalchemy(db_path: str):
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(f'sqlite:///{db_path}')
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

@contextmanager
def get_sqlalchemy_session():
    global _engine, _SessionLocal
    if _SessionLocal is None:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager()
        db_path = config_manager.get_db_path()
        _initialize_sqlalchemy(db_path)
    
    session = _SessionLocal()
    try:
        yield session
    except SQLAlchemyError as e:
        logger.error(f"Erro na sessão do SQLAlchemy: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == '__main__':
    print("Executando o setup do banco de dados diretamente...")
    try:
        init_db()
        print("\nSetup concluído com sucesso!")
    except Exception as e:
        print(f"\nOcorreu um erro durante o setup: {e}")

# --- FIM DO NOVO CÓDIGO ---