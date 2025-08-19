# core/diagram_manager.py
import logging
import sqlite3
from typing import Optional, Dict, Any, Callable

class DiagramManager:
    """
    Gerencia todas as operações relacionadas a diagramas e visualizações.
    """
    def __init__(self,
                 db_connection_provider: Callable[[], sqlite3.Connection],
                 logger_instance: Optional[logging.Logger] = None):
        """
        Inicializa o manager com um provedor de conexão de banco de dados.
        """
        # Esta parte está PERFEITA. Não mude nada.
        self.get_db_connection = db_connection_provider
        self.logger = logger_instance if logger_instance else logging.getLogger(self.__class__.__name__)
        self.logger.info("DiagramManager instanciado e pronto.")

    # O método _create_connection foi REMOVIDO, pois a classe não
    # é mais responsável por criar conexões, apenas por usá-las.

    # ======================================================================
    # --- EXEMPLO DE MÉTODO CORRIGIDO ---
    # Todas as suas funções devem seguir este padrão.
    # ======================================================================
    
    def get_data_for_difficulty_pie_chart(self, evento_id: str) -> Dict[str, int]:
        """
        Busca a contagem de questões por nível de dificuldade para um evento.
        """
        self.logger.debug(f"Buscando dados do gráfico de dificuldade para o evento_id: {evento_id}")
        data = {'Fácil': 0, 'Médio': 0, 'Difícil': 0}
        query = """
            SELECT nivel_dificuldade, COUNT(id_questao) as count
            FROM QuestoesBanco
            WHERE id_evento_origem = ? AND nivel_dificuldade IS NOT NULL
            GROUP BY nivel_dificuldade;
        """
        
        # Correção: Use 'with self.get_db_connection() as conn:'
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (evento_id,))
                rows = cursor.fetchall()
                for row in rows:
                    # Garante que a chave existe antes de atribuir
                    if row['nivel_dificuldade'] in data:
                        data[row['nivel_dificuldade']] = row['count']
            
            self.logger.debug(f"Dados do gráfico de dificuldade encontrados: {data}")
            return data
            
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar dados para gráfico de pizza: {e}", exc_info=True)
            # Retorna os dados zerados em caso de erro
            return data


    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Cria e retorna uma conexão com o banco de dados."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao conectar ao banco de dados: {e}", exc_info=True)
            return None

    # ======================================================================
    # --- INSIRA AQUI TODA A LÓGICA DO SEU DIAGRAM MANAGER ---
    # Todas as funções que você tinha para gerar diagramas, buscar dados
    # para gráficos, etc., devem ser colocadas aqui.
    # Exemplo de função:
    #
    # def get_data_for_difficulty_pie_chart(self, evento_id: str) -> Dict[str, int]:
    #     """
    #     Busca a contagem de questões por nível de dificuldade para um evento.
    #     """
    #     data = {'Fácil': 0, 'Médio': 0, 'Difícil': 0}
    #     query = """
    #         SELECT nivel_dificuldade, COUNT(id_questao) as count
    #         FROM QuestoesBanco
    #         WHERE id_evento_fk = ? AND nivel_dificuldade IS NOT NULL
    #         GROUP BY nivel_dificuldade;
    #     """
    #     conn = self._create_connection()
    #     if conn:
    #         try:
    #             cursor = conn.cursor()
    #             cursor.execute(query, (evento_id,))
    #             rows = cursor.fetchall()
    #             for row in rows:
    #                 if row['nivel_dificuldade'] in data:
    #                     data[row['nivel_dificuldade']] = row['count']
    #             return data
    #         except sqlite3.Error as e:
    #             self.logger.error(f"Erro ao buscar dados para gráfico de pizza: {e}", exc_info=True)
    #         finally:
    #             conn.close()
    #     return data
    # ======================================================================

