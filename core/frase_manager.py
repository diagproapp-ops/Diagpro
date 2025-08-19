# core/frase_manager.py

import logging
import sqlite3
from typing import List, Optional, Callable, Dict, Any
import csv

# Importa o modelo de dados do seu arquivo de elementos
try:
    # Supondo que o seu modelo de dados para frases se chame BancoFrasesType em elements.py
    from .elements import BancoFrasesType
except ImportError:
    class BancoFrasesType: # Fallback simples
        def __init__(self, **kwargs):
            self.id = kwargs.get('id')
            self.categoria = kwargs.get('categoria')
            self.texto_frase = kwargs.get('texto_frase')
            self.ativo = kwargs.get('ativo')
            # Adicione outros campos se necessário

class FraseManager:
    """
    Gerencia todas as operações de banco de dados para a tabela BancoFrases,
    usando o padrão de conexão compartilhada (db_connection_provider).
    """
    def __init__(self,
                 db_connection_provider: Callable[[], sqlite3.Connection],
                 logger_instance: Optional[logging.Logger] = None):
        """
        Inicializa o manager com um provedor de conexão de banco de dados.
        """
        self.get_db_connection = db_connection_provider
        self.logger = logger_instance if logger_instance else logging.getLogger(self.__class__.__name__)
        self.logger.info("FraseManager instanciado e pronto (padrão sqlite3).")

    def _row_to_object(self, row: sqlite3.Row) -> Optional[BancoFrasesType]:
        """Converte uma linha do banco de dados em um objeto BancoFrasesType."""
        if not row:
            return None
        # O modelo BancoFrasesType deve ter um __init__ que aceita **kwargs ou os nomes das colunas
        return BancoFrasesType(**dict(row))

    def criar_frase(self, categoria: str, texto_frase: str, ativo: bool = True) -> Optional[BancoFrasesType]:
        """Cria e salva uma nova frase no banco de dados."""
        sql = "INSERT INTO banco_frases (categoria, texto_frase, ativo) VALUES (?, ?, ?)"
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (categoria, texto_frase, 1 if ativo else 0))
                last_id = cursor.lastrowid
            
            self.logger.info(f"Frase ID {last_id} criada com sucesso.")
            # Retorna o objeto recém-criado para confirmação
            return self.get_frase_por_id(last_id)
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao criar nova frase: {e}", exc_info=True)
            return None

    def get_frase_por_id(self, frase_id: int) -> Optional[BancoFrasesType]:
        """Busca uma única frase pelo seu ID."""
        sql = "SELECT * FROM banco_frases WHERE id = ?"
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (frase_id,))
                row = cursor.fetchone()
                return self._row_to_object(row)
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar frase por ID {frase_id}: {e}", exc_info=True)
            return None

    def get_todas_as_frases(self) -> List[BancoFrasesType]:
        """Busca todas as frases cadastradas."""
        sql = "SELECT * FROM banco_frases ORDER BY categoria, id"
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                return [self._row_to_object(row) for row in rows if row]
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar todas as frases: {e}", exc_info=True)
            return []

    def get_all_active_frases_by_category(self, categoria: str) -> List[BancoFrasesType]:
        """Busca TODAS as frases ativas de uma categoria específica no banco de dados."""
        self.logger.debug(f"Buscando todas as frases ativas para a categoria: '{categoria}'")
        sql = "SELECT * FROM banco_frases WHERE categoria = ? AND ativo = 1"
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (categoria,))
                rows = cursor.fetchall()
                frases_obj = [self._row_to_object(row) for row in rows if row]
            
            self.logger.debug(f"Encontradas {len(frases_obj)} frases para a categoria '{categoria}'.")
            return frases_obj
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar frases ativas por categoria '{categoria}': {e}", exc_info=True)
            return []

    def atualizar_frase(self, frase_id: int, novos_dados: dict) -> bool:
        """Atualiza os dados de uma frase existente."""
        if not novos_dados:
            return False

        # Constrói a query de atualização dinamicamente
        fields = ", ".join([f"{key} = ?" for key in novos_dados.keys()])
        values = list(novos_dados.values())
        values.append(frase_id)
        
        sql = f"UPDATE banco_frases SET {fields} WHERE id = ?"

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(values))
                # Verifica se alguma linha foi de fato alterada
                if cursor.rowcount == 0:
                    self.logger.warning(f"Tentativa de atualizar frase com ID {frase_id}, mas o ID não foi encontrado.")
                    return False
            
            self.logger.info(f"Frase ID {frase_id} atualizada com sucesso.")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao atualizar frase ID {frase_id}: {e}", exc_info=True)
            return False

    def remover_frase(self, frase_id: int) -> bool:
        """Remove uma frase do banco de dados pelo seu ID."""
        sql = "DELETE FROM banco_frases WHERE id = ?"
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (frase_id,))
                if cursor.rowcount > 0:
                    self.logger.info(f"Frase ID {frase_id} removida com sucesso.")
                    return True
            self.logger.warning(f"Tentativa de remover frase com ID {frase_id}, mas o ID não foi encontrado.")
            return False
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao remover frase ID {frase_id}: {e}", exc_info=True)
            return False

    def importar_de_csv(self, file_path: str) -> tuple[int, str]:
        """Importa frases de um arquivo CSV (separador: ponto e vírgula)."""
        frases_para_adicionar = []
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as csvfile:
                leitor = csv.DictReader(csvfile, delimiter=';')
                for linha in leitor:
                    categoria = linha.get('categoria')
                    texto = linha.get('texto_frase')
                    if not categoria or not texto:
                        self.logger.warning(f"Linha ignorada no CSV por ter dados faltando: {linha}")
                        continue
                    frases_para_adicionar.append((categoria.strip(), texto.strip(), 1)) # ativo=1 (True)
            
            if not frases_para_adicionar:
                return 0, "Nenhuma frase válida encontrada no arquivo."

            sql = "INSERT INTO banco_frases (categoria, texto_frase, ativo) VALUES (?, ?, ?)"
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, frases_para_adicionar)
            
            frases_importadas = len(frases_para_adicionar)
            self.logger.info(f"{frases_importadas} frases importadas com sucesso do arquivo {file_path}.")
            return frases_importadas, f"{frases_importadas} frases importadas com sucesso!"

        except FileNotFoundError:
            self.logger.error(f"Arquivo CSV não encontrado em: {file_path}")
            return 0, "Erro: Arquivo não encontrado."
        except Exception as e:
            self.logger.error(f"Erro ao importar CSV: {e}", exc_info=True)
            return 0, f"Ocorreu um erro ao ler o arquivo:\n{e}"