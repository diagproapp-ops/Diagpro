# DiagProOFF/core/event_manager.py

import sqlite3
import json
import uuid
import typing
from typing import List, Dict, Optional, Any, Callable, Union, TYPE_CHECKING
from datetime import datetime, date # Importa date também
import logging
import os
from enum import Enum
import dataclasses
import re

# Importe seus modelos Pydantic e funções utilitárias
try:
    from .elements import (
        EventoType, CargoType, QuestaoType, OpcaoMultiplaEscolha,
        TextoReferenciaType, DisciplinaType, ConteudoType, ProvaMontadaType,
        ConfiguracoesProvaType, BlocoQuestoesType, DisciplinaProvaType,
        EventoSummaryType, TipoQuestao, NivelDificuldadeQuestao, DetalhesQuestaoDiscursiva,
        ItemVerdadeiroFalso # Certifique-se de importar todos os modelos Pydantic necessários
    )
    from .utils import parse_iso_to_datetime, parse_enunciado_formatado # Importe se precisar de parsing explícito
    # Se você tiver modelos de dataclass para retorno (embora Pydantic seja o foco aqui)
    # from .models import AlgumOutroModeloSeNecessario
except ImportError as e:
    # Log de erro crítico se as importações principais falharem
    temp_logger = logging.getLogger(__name__)
    temp_logger.critical(f"Falha CRÍTICA ao importar modelos de .elements ou .utils em EventManager: {e}", exc_info=True)
    # Em um cenário real, você pode querer levantar a exceção para parar a aplicação
    # ou ter um fallback muito robusto se for absolutamente necessário continuar.
    # Por enquanto, vamos re-levantar para sinalizar o problema grave.
    raise ImportError(f"EventManager não pôde importar dependências essenciais: {e}")



class EventManager:
    def __init__(self,
                 db_connection_provider: Callable[[], sqlite3.Connection],
                 app_controller: Optional[Any] = None,
                 logger_instance: Optional[logging.Logger] = None):

        # Provider de conexão: sempre use este atributo para abrir uma nova conexão!
        self.db_connection_provider: Callable[[], sqlite3.Connection] = db_connection_provider
        self.app_controller = app_controller

        if logger_instance:
            self.logger = logger_instance
        else:
            # Fallback para logger se não fornecido
            self.logger = logging.getLogger(f"{__name__}.EventManagerInstance")
            if not self.logger.hasHandlers() or not self.logger.handlers:
                self.logger.setLevel(logging.DEBUG)
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                if not self.logger.handlers:
                    self.logger.addHandler(handler)
                self.logger.propagate = False
                self.logger.warning("EventManager usou configuração de logger de fallback.")

        self.logger.info("EventManager instanciado e pronto.")
    
    def _get_connection(self, timeout=20) -> sqlite3.Connection:
        # Se nos foi dada uma conexão pronta, use-a.
        if hasattr(self, 'db_conn') and self.db_conn:
            return self.db_conn

        # Senão, cria uma nova conexão
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row

        # Recomenda-se rodar o PRAGMA só uma vez na inicialização do banco.
        # Mas se fizer questão, pode deixar aqui:
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _convert_date_field(self, value: Any, field_name: str, event_id: Optional[str] = None) -> Optional[Any]:
        """
        Função auxiliar para converter strings de data/hora para objetos datetime/date.
        Lida com diferentes formatos e registra avisos em caso de falha.
        Esta função é chamada para os valores de data/hora *do banco de dados*.
        """
        if value is None:
            return None
        
        # Se já é um objeto datetime ou date, retorna como está
        if isinstance(value, (datetime, date)):
            return value

        # Se é um inteiro, tenta tratar como timestamp (defensivo)
        if isinstance(value, int):
            try:
                # Assume que é um timestamp Unix
                return datetime.fromtimestamp(value)
            except (ValueError, OSError) as e_timestamp: # OSError para timestamp inválido (ex: ano muito distante)
                self.logger.warning(
                    f"Não foi possível converter int '{value}' para timestamp no campo '{field_name}' "
                    f"do evento '{event_id if event_id else 'N/A'}'. Erro: {e_timestamp}. Deixando como None."
                )
                return None

        # Se é uma string, tenta converter
        if isinstance(value, str):
            # Primeiro, tenta o parser genérico do utils, que lida com ISO e outros comuns
            dt_obj = parse_iso_to_datetime(value)
            if dt_obj:
                # Se o campo específico for apenas uma data (e não datetime), retorna .date()
                if field_name == 'data_prova' or field_name == 'data_evento': # Supondo que 'data_prova' e 'data_evento' no modelo Pydantic são `date`
                    return dt_obj.date()
                return dt_obj # Retorna o objeto datetime

            # Se o parse_iso_to_datetime falhou, registra um aviso mais específico
            self.logger.warning(
                f"Não foi possível converter string de data '{value}' para o campo '{field_name}' "
                f"do evento '{event_id if event_id else 'N/A'}'. Formato não reconhecido. Deixando como None."
            )
            return None
        
        # Se o tipo não for string, int, datetime ou date, registra um aviso
        self.logger.warning(
            f"Não foi possível converter tipo inesperado '{type(value)}' para o campo '{field_name}' "
            f"do evento '{event_id if event_id else 'N/A'}'. Deixando como None."
        )
        return None

    # Adicione esta função no topo do event_manager.py

    
    
    # --- Métodos para Eventos ---
    def create_event(self, evento_data: EventoType) -> Optional[str]:
        self.logger.info(f"Criando novo evento: {evento_data.nome_evento}")
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Pydantic model_dump já deve serializar datas para ISO strings se configurado (json_encoders)
            # ou elas já virão como objetos datetime/date.
            # Convertemos para ISO format aqui para garantir que o SQLite receba strings.
            data_prova_iso = evento_data.data_prova.isoformat() if isinstance(evento_data.data_prova, (datetime, date)) else None
            data_criacao_iso = evento_data.data_criacao.isoformat() if isinstance(evento_data.data_criacao, datetime) else datetime.now().isoformat()
            data_modificacao_iso = evento_data.data_modificacao.isoformat() if isinstance(evento_data.data_modificacao, datetime) else datetime.now().isoformat()
            
            sql = """
                INSERT INTO Eventos (
                    id_evento, nome_evento, data_prova, numero_edital, local_prova,
                    instituicao_organizadora, logo_path, observacoes, status, qtd_cargos_estimada,
                    data_criacao, data_modificacao, responsavel_criacao, configuracoes_evento, 
                    nome_curto_evento, identificador_unico_evento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            # Serializar campos complexos para JSON string para o DB
            configuracoes_evento_json = json.dumps(evento_data.configuracoes_evento or {})

            params = (
                evento_data.id_evento, evento_data.nome_evento, data_prova_iso,
                evento_data.numero_edital, evento_data.local_prova,
                evento_data.instituicao_organizadora, evento_data.logo_path,
                evento_data.observacoes, evento_data.status.value if isinstance(evento_data.status, Enum) else evento_data.status,
                evento_data.qtd_cargos_estimada,
                data_criacao_iso, data_modificacao_iso,
                evento_data.responsavel_criacao, configuracoes_evento_json,
                evento_data.nome_curto_evento, evento_data.identificador_unico_evento
            )
            
            cursor.execute(sql, params)
            conn.commit()
            self.logger.info(f"Evento '{evento_data.nome_evento}' (ID: {evento_data.id_evento}) criado com sucesso.")
            return evento_data.id_evento
        except sqlite3.IntegrityError as ie:
            self.logger.error(f"Erro de integridade ao criar evento '{evento_data.nome_evento}' (ID: {evento_data.id_evento}): {ie}", exc_info=True)
            if conn: conn.rollback()
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao criar evento '{evento_data.nome_evento}': {e}", exc_info=True)
            if conn: conn.rollback()
            return None
        except Exception as e_general:
             self.logger.error(f"Erro geral ao criar evento '{evento_data.nome_evento}': {e_general}", exc_info=True)
             if conn: conn.rollback()
             return None
        finally:
            if conn:
                conn.close()
                self.logger.debug("Conexão (create_event) fechada.")

    def get_event_by_id(self, id_event: str) -> Optional['EventoType']:
        """
        Busca um evento completo pelo ID, montando o objeto final em etapas para maior robustez.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.debug(f"Buscando evento completo por ID: {id_event}")

        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Buscar e criar o objeto EventoType principal (Seu código original - mantido)
            cursor.execute("SELECT * FROM Eventos WHERE id_evento = ?", (id_event,))
            event_row = cursor.fetchone()
            if not event_row:
                self.logger.warning(f"Evento com ID '{id_event}' não encontrado.")
                return None
            
            evento_dict = dict(event_row)

            # Desserialização dos campos (Seu código original - mantido)
            for field_json, default_value in [('configuracoes_evento', {})]:
                if field_json in evento_dict and isinstance(evento_dict[field_json], str):
                    try:
                        evento_dict[field_json] = json.loads(evento_dict[field_json])
                    except json.JSONDecodeError:
                        self.logger.error(f"JSONDecodeError no campo '{field_json}' do evento {id_event}")
                        evento_dict[field_json] = default_value
                elif field_json not in evento_dict or evento_dict[field_json] is None:
                    evento_dict[field_json] = default_value

            evento_dict['data_prova'] = self._convert_date_field(evento_dict.get('data_prova'), 'data_prova', id_event)
            evento_dict['data_criacao'] = self._convert_date_field(evento_dict.get('data_criacao'), 'data_criacao', id_event)
            evento_dict['data_modificacao'] = self._convert_date_field(evento_dict.get('data_modificacao'), 'data_modificacao', id_event)
            if 'is_deleted' in evento_dict and isinstance(evento_dict['is_deleted'], int):
                evento_dict['is_deleted'] = bool(evento_dict['is_deleted'])
            if 'deleted_at' in evento_dict:
                evento_dict['deleted_at'] = self._convert_date_field(evento_dict.get('deleted_at'), 'deleted_at', id_event)
            
            evento_obj = EventoType(**evento_dict)

            # 2. Buscar e atribuir os Cargos (Seu código original - mantido)
            evento_obj.cargos = self.get_cargos_by_event_id(id_event)

            # --- INÍCIO DA CORREÇÃO DE ORDEM ---

            # PASSO 3 (Antigo Passo 5): Buscar e atribuir o Banco de Questões PRIMEIRO.
            all_questions = self.obter_questoes_do_evento(id_event=id_event)
            banco_questoes_dict = {}
            if all_questions:
                for q in all_questions:
                    disciplina = getattr(q, 'disciplina_banco', 'Sem Disciplina') or 'Sem Disciplina'
                    if disciplina not in banco_questoes_dict:
                        banco_questoes_dict[disciplina] = []
                    banco_questoes_dict[disciplina].append(q)
            evento_obj.banco_questoes = banco_questoes_dict
            self.logger.debug(f"Banco de questões para evento {id_event} carregado com {len(banco_questoes_dict)} disciplinas.")

            # PASSO 4 (Antigo Passo 3): AGORA, com o banco de questões já carregado, buscar e preencher as Provas Montadas.
            provas_list = self.get_all_proof_assemblies_for_event(id_event, evento_obj.banco_questoes)
            provas_montadas_dict = {}
            for prova in provas_list:
                if getattr(prova, 'id_cargo', None):
                    provas_montadas_dict[prova.id_cargo] = prova
                else:
                    self.logger.warning(f"Prova montada '{prova.id_prova_montada}' sem id_cargo, ignorando.")
            evento_obj.provas_montadas_por_cargo = provas_montadas_dict
            self.logger.info(f"Evento '{evento_obj.nome_evento}' carregado com {len(provas_montadas_dict)} prova(s) montada(s) e preenchidas.")
            
            # PASSO 5 (Antigo Passo 4): Buscar e atribuir os Textos de Referência.
            textos_ref_list = self.get_all_reference_texts_for_event(id_event)
            evento_obj.textos_referencia = {tr.codigo_ref: tr for tr in textos_ref_list if tr.codigo_ref}

            # --- FIM DA CORREÇÃO DE ORDEM ---
            
            # Seu bloco de Debug no final, como estava
            print("\n\n--- DEBUG CHAVES DO BANCO DE QUESTÕES ---")
            if evento_obj.banco_questoes:
                print("As chaves 'agrupamento_banco' encontradas nas QUESTÕES são:")
                print(list(evento_obj.banco_questoes.keys()))
            else:
                print(">>> ALERTA: O banco de questões está VAZIO.")
            print("------------------------------------------\n\n")

            return evento_obj

        except sqlite3.Error as e_sql:
            self.logger.error(f"Erro SQLite ao buscar evento ID '{id_event}': {e_sql}", exc_info=True)
            return None
        except Exception as e_final:
            self.logger.error(f"Erro CRÍTICO ao montar objeto EventoType para ID '{id_event}': {e_final}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
                self.logger.debug(f"Conexão (get_event_by_id para {id_event}) fechada.")

    
    def _serialize_field_to_json_string(self, data: Any, default_empty_for_list: bool = True) -> Optional[str]:
        print("DEBUG SERIALIZANDO:", data)
        """Função auxiliar para converter dados em texto JSON."""
        if data is None:
            return "[]" if default_empty_for_list else "{}"
        try:
            def default_serializer(item):
                # Protege contra ellipsis
                if isinstance(item, type(...)):
                    return None  # ou outro valor padrão, se desejar

                # UUID
                if isinstance(item, uuid.UUID):
                    return str(item)
                # Pydantic v2
                if hasattr(item, 'model_dump'):
                    return item.model_dump(exclude_none=True)
                # Pydantic v1
                if hasattr(item, 'dict'):
                    return item.dict()
                # Dataclass
                try:
                    from dataclasses import asdict, is_dataclass
                    if is_dataclass(item):
                        return asdict(item)
                except ImportError:
                    pass
                # Objetos comuns com __dict__
                if hasattr(item, '__dict__'):
                    return vars(item)
                # datetime/date
                if isinstance(item, (datetime, date)):
                    return item.isoformat()
                # Enum
                if isinstance(item, Enum):
                    return item.value
                # set
                if isinstance(item, set):
                    return list(item)
                raise TypeError(f"O tipo '{type(item).__name__}' não é serializável em JSON")

            return json.dumps(data, default=default_serializer, ensure_ascii=False)
        except TypeError as e:
            self.logger.error(f"Erro de serialização JSON: {e}", exc_info=True)
            return "[]" if default_empty_for_list else "{}"
    

    def _default_serializer(item: Any) -> Any:
        # Tratamento para ellipsis ("...")
        if isinstance(item, type(...)):
            return None  # ou outro valor padrão

        # Para modelos Pydantic
        if hasattr(item, 'model_dump'):
            return item.model_dump(exclude_none=True)

        # Para datas e datetimes
        if isinstance(item, (datetime, date)):
            return item.isoformat()

        # Para Enums
        if isinstance(item, Enum):
            return item.value

        # Se chegou aqui, tipo não suportado
        raise TypeError(f"O tipo '{type(item).__name__}' não é serializável em JSON")
    
    def get_cargos_by_event_id(self, event_id: str) -> List['CargoType']:
        """
        Busca todos os cargos associados a um determinado ID de evento.
        Desserializa campos JSON e converte para objetos CargoType.
        """
        conn = None
        cargos = []
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row # Garante que pode acessar colunas por nome
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Cargos WHERE id_evento_fk = ?", (event_id,))
            rows = cursor.fetchall()
            self.logger.info(f"LOG DEBUG EventManager - get_cargos_by_event_id - Rows de Cargos do DB para evento {event_id}: {rows}")
            
            for row in rows:
                cargo_dict = dict(row)
                self.logger.info(f"LOG DEBUG EventManager - get_cargos_by_event_id - Processando cargo_dict bruto: {cargo_dict}")
                
                # Mapeamento e conversão de tipos do DB para CargoType Pydantic
                # Renomear 'id_evento_fk' para 'id_evento' para o modelo Pydantic
                if 'id_evento_fk' in cargo_dict:
                    cargo_dict['id_evento'] = cargo_dict.pop('id_evento_fk')
                
                # Tratar booleanos
                if 'tem_discursiva' in cargo_dict and isinstance(cargo_dict['tem_discursiva'], int):
                    cargo_dict['tem_discursiva'] = bool(cargo_dict['tem_discursiva'])

                # Desserialização de campos JSON
                for json_field, default_val in [('cover_pdf_paths', []), ('metadados_cargo', {})]:
                    if json_field in cargo_dict and isinstance(cargo_dict[json_field], str):
                        try:
                            cargo_dict[json_field] = json.loads(cargo_dict[json_field])
                        except json.JSONDecodeError:
                            self.logger.error(f"JSONDecodeError em '{json_field}' para cargo {cargo_dict.get('id_cargo')}. Valor: {cargo_dict[json_field]}", exc_info=True)
                            cargo_dict[json_field] = default_val
                    elif json_field not in cargo_dict or cargo_dict[json_field] is None:
                        cargo_dict[json_field] = default_val

                # Carregar e desserializar disciplinas_prova
                disciplinas_prova_list = []
                cursor_disciplinas = conn.cursor() # Novo cursor para a sub-query
                cursor_disciplinas.execute(
                    "SELECT * FROM DisciplinasDaProva WHERE id_cargo_fk = ? ORDER BY ordem_na_prova, nome_disciplina_na_prova;",
                    (cargo_dict['id_cargo'],)
                )
                disciplinas_rows = cursor_disciplinas.fetchall()
                self.logger.info(f"LOG DEBUG EventManager - get_cargos_by_event_id - Rows de DisciplinasDaProva para cargo {cargo_dict.get('id_cargo')}: {disciplinas_rows}")
                
                for dp_row in disciplinas_rows:
                    dp_dict = dict(dp_row)
                    # Renomear nome_disciplina_na_prova para nome_disciplina para o modelo Pydantic
                    if 'nome_disciplina_na_prova' in dp_dict:
                        dp_dict['nome_disciplina'] = dp_dict.pop('nome_disciplina_na_prova')
                    # Garantir que id_cargo_fk seja mapeado para id_cargo_fk no modelo
                    if 'id_cargo_fk' in dp_dict:
                        dp_dict['id_cargo_fk'] = dp_dict['id_cargo_fk'] # Já está no nome correto do campo DisciplinaProvaType

                    try:
                        disciplinas_prova_list.append(DisciplinaProvaType(**dp_dict))
                    except Exception as e_dp_pydantic:
                        self.logger.error(f"Erro ao criar DisciplinaProvaType para cargo {cargo_dict.get('id_cargo')} com dados {dp_dict}: {e_dp_pydantic}", exc_info=True)
                
                cargo_dict['disciplinas_prova'] = disciplinas_prova_list

                # Aplicar _convert_date_field para datas do CargoType (se houver)
                # Você mencionou data_criacao, data_modificacao em CargoType
                for date_field in ['data_criacao', 'data_modificacao']:
                    if date_field in cargo_dict:
                        cargo_dict[date_field] = self._convert_date_field(cargo_dict.get(date_field), date_field, event_id)


                self.logger.info(f"LOG DEBUG EventManager - get_cargos_by_event_id - Tentando criar CargoType com dict final: {cargo_dict}")
                cargos.append(CargoType(**cargo_dict))
            
            self.logger.info(f"EventManager - Retornando de get_cargos_by_event_id: {len(cargos)} cargos.")
            return cargos
        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao buscar cargos para o evento {event_id}: {e}", exc_info=True)
            return []
        except Exception as e_pydantic: # Captura quaisquer outras exceções, incluindo Pydantic ValidationErrors
            self.logger.error(f"Erro geral ao buscar cargos para o evento {event_id}: {e_pydantic}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
                self.logger.debug("Conexão (get_cargos_by_event_id) fechada.")
    
    def get_all_events_summary(self) -> List[EventoSummaryType]: #
        conn: Optional[sqlite3.Connection] = None
        summaries: List[EventoSummaryType] = [] #
        try:
            conn = self.get_db_connection() #
            conn.row_factory = sqlite3.Row # Garante que pode acessar colunas por nome
            cursor = conn.cursor() #
            # Query SQL CORRIGIDA:
            sql = """
                SELECT 
                    e.id_evento, e.nome_evento, e.data_prova, e.status as status_evento, e.numero_edital,
                    (SELECT COUNT(*) FROM Cargos c WHERE c.id_evento_fk = e.id_evento) as numero_cargos, 
                    (SELECT COUNT(*) FROM ProvasMontadas pm WHERE pm.id_evento_fk = e.id_evento) as numero_provas_montadas
                FROM Eventos e
                WHERE e.is_deleted = 0  -- Filtra apenas eventos não deletados
                ORDER BY e.data_modificacao DESC;
            """
            cursor.execute(sql) #
            rows = cursor.fetchall() #
            if rows: #
                for row_data in rows: #
                    summary_dict = dict(row_data) #
                    
                    # CORREÇÃO AQUI: Renomear 'data_prova' para 'data_evento'
                    if 'data_prova' in summary_dict:
                        summary_dict['data_evento'] = summary_dict.pop('data_prova')

                    # Aplica a função de conversão para 'data_evento'
                    if 'data_evento' in summary_dict:
                        summary_dict['data_evento'] = self._convert_date_field(summary_dict['data_evento'], 'data_evento', summary_dict.get('id_evento'))
                    
                    # Converte status para o tipo Enum se necessário (se EventoSummaryType espera Enum)
                    if 'status_evento' in summary_dict and isinstance(summary_dict['status_evento'], str):
                        try:
                            # Se status_evento no EventoType for um Enum e não uma string arbitrária
                            # summary_dict['status_evento'] = StatusEventoEnum(summary_dict['status_evento'])
                            pass # Mantém como string se EventoSummaryType.status_evento for str
                        except ValueError:
                            self.logger.warning(f"Status '{summary_dict['status_evento']}' inválido para EventoSummaryType.")

                    summaries.append(EventoSummaryType(**summary_dict)) #
            return summaries #
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao buscar resumos de eventos: {e}", exc_info=True) #
            return []
        except Exception as e_pydantic: # Erro mais genérico para problemas de instanciação do Pydantic
            self.logger.error(f"Erro ao criar EventoSummaryType a partir dos dados do DB: {e_pydantic}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close() #
                self.logger.debug("Conexão (get_all_events_summary) fechada.")

    def update_event(self, id_event: str, updates: Dict[str, Any]) -> bool: # Changed signature
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Attempting to update event ID {id_event} with data: {updates}")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            set_clauses = []
            params = []

            # Campos diretos que podem ser atualizados
            direct_fields = {
                "nome_evento": "nome_evento", "data_prova": "data_prova", 
                "numero_edital": "numero_edital", "local_prova": "local_prova",
                "instituicao_organizadora": "instituicao_organizadora", 
                "logo_path": "logo_path", "observacoes": "observacoes",
                "status": "status", "qtd_cargos_estimada": "qtd_cargos_estimada",
                "responsavel_criacao": "responsavel_criacao",
                "nome_curto_evento": "nome_curto_evento",
                "identificador_unico_evento": "identificador_unico_evento"
            }

            for model_field, db_column in direct_fields.items():
                if model_field in updates:
                    value = updates[model_field]
                    if model_field == "data_prova" and isinstance(value, (datetime, date)):
                        value = value.isoformat()
                    elif model_field == "status" and isinstance(value, Enum):
                        value = value.value # Usa o valor da Enum
                    # Converte outros tipos para string ISO se forem datetime/date
                    elif isinstance(value, (datetime, date)):
                        value = value.isoformat()
                    set_clauses.append(f"{db_column} = ?")
                    params.append(value)
            
            # Tratar campos JSON específicos (configuracoes_evento)
            if "configuracoes_evento" in updates:
                set_clauses.append("configuracoes_evento = ?")
                params.append(json.dumps(updates["configuracoes_evento"] or {}))

            # Handle banco_questoes specifically (if stored as JSON in Eventos table)
            if "banco_questoes" in updates:
                set_clauses.append("banco_questoes_json = ?") 
                serializable_banco_questoes = {}
                if updates["banco_questoes"]:
                    for discipline, qs_list in updates["banco_questoes"].items():
                        # Certifica que cada QuestaoType é convertida para dict de forma serializável
                        serializable_banco_questoes[discipline] = [q.model_dump(mode='json', exclude_none=True) if hasattr(q, 'model_dump') else q for q in qs_list]
                params.append(json.dumps(serializable_banco_questoes or {}))

            if not set_clauses:
                self.logger.info(f"No valid fields to update for event ID {id_event}.")
                return True 

            set_clauses.append("data_modificacao = CURRENT_TIMESTAMP")
            
            sql = f"UPDATE Eventos SET {', '.join(set_clauses)} WHERE id_evento = ?"
            params.append(id_event)
            
            self.logger.debug(f"Executing SQL for update_event: {sql} with params: {params}")
            cursor.execute(sql, tuple(params))
            conn.commit()

            return cursor.rowcount > 0
        except sqlite3.Error as e_update:
            self.logger.error(f"Falha ao atualizar evento ID {id_event}: {e_update}", exc_info=True)
            if conn: conn.rollback()
            return False
        except Exception as e_general:
            self.logger.error(f"Erro geral ao atualizar evento ID {id_event}: {e_general}", exc_info=True)
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug("Conexão (update_event) fechada.")

    def delete_event(self, id_event: str) -> bool:
        """
        Marca um evento como deletado (soft delete) no banco de dados.
        Não remove fisicamente o evento nem suas associações diretas,
        permitindo a preservação de dados históricos e potenciais restaurações.
        """
        sql_soft_delete_evento = """
            UPDATE Eventos
            SET is_deleted = ?, deleted_at = ?
            WHERE id_evento = ?
        """
        conn: Optional[sqlite3.Connection] = None # Ensure Optional and sqlite3 are imported
        try:
            conn = self.get_db_connection() # Corrected from self.db_connection_provider
            cursor = conn.cursor()
            self.logger.info(f"Tentando marcar evento ID '{id_event}' como deletado (soft delete).")
            
            # Passa True (1) e a data/hora atual para SQLite
            cursor.execute(sql_soft_delete_evento, (1, datetime.now().isoformat(), id_event)) 
            
            if cursor.rowcount == 0:
                self.logger.warning(f"Nenhum evento encontrado com ID '{id_event}' para marcar como deletado.")
                return False

            conn.commit()
            self.logger.info(f"Evento ID '{id_event}' marcado como deletado com sucesso.")
            return True
        except sqlite3.Error as e_sql:
            self.logger.error(f"Erro SQLite ao tentar marcar evento ID '{id_event}' como deletado: {e_sql}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        except Exception as e_general: # Catch other potential errors
            self.logger.error(f"Erro geral ao tentar marcar evento ID '{id_event}' como deletado: {e_general}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug(f"Conexão (delete_event para evento {id_event}) fechada.")
    
    def get_cargo_by_id(self, event_id: str, cargo_id: str) -> Optional[CargoType]:
        conn = None
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # CORREÇÃO AQUI: Mudar 'id' para 'id_cargo'
            cursor.execute("SELECT * FROM Cargos WHERE id_cargo = ? AND id_evento_fk = ?", (cargo_id, event_id))
            cargo_row = cursor.fetchone()

            if cargo_row:
                cargo_dict = dict(cargo_row)
                
                # --- Correção: Desserializar campos JSON antes de passar para o Pydantic ---
                if 'cover_pdf_paths' in cargo_dict and isinstance(cargo_dict['cover_pdf_paths'], str):
                    try:
                        cargo_dict['cover_pdf_paths'] = json.loads(cargo_dict['cover_pdf_paths'])
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Erro ao decodificar JSON para cover_pdf_paths do cargo {cargo_id}: {e}")
                        cargo_dict['cover_pdf_paths'] = [] # Define um valor padrão seguro em caso de erro

                if 'metadados_cargo' in cargo_dict and isinstance(cargo_dict['metadados_cargo'], str):
                    try:
                        cargo_dict['metadados_cargo'] = json.loads(cargo_dict['metadados_cargo'])
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Erro ao decodificar JSON para metadados_cargo do cargo {cargo_id}: {e}")
                        cargo_dict['metadados_cargo'] = {} # Define um valor padrão seguro em caso de erro

                # Retorna o CargoType com os dados processados
                return CargoType(**cargo_dict)
            return None
        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao buscar cargo por ID '{cargo_id}': {e}", exc_info=True)
            return None
        except Exception as e_general:
            self.logger.error(f"Erro geral ao buscar cargo por ID '{cargo_id}': {e_general}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
    
    def _get_or_create_disciplina_base_id(self, cursor: sqlite3.Cursor, 
                                          id_event_context: Optional[str], 
                                          nome_disciplina: str,
                                          codigo_disciplina: Optional[str] = None,
                                          descricao_disciplina: Optional[str] = None) -> Optional[str]:
        """
        Verifica se uma disciplina base com este nome (e opcionalmente código) já existe.
        Prioriza disciplinas específicas do evento, depois globais.
        Se não existir, cria uma nova (associada ao evento se id_event_context for fornecido, senão global).
        Retorna o ID da disciplina base ou None em caso de falha grave.
        """
        if not nome_disciplina:
            self.logger.warning("_get_or_create_disciplina_base_id: Nome da disciplina está vazio. Pulando.")
            return None

        # Tentar encontrar por nome e contexto do evento (se fornecido)
        if id_event_context:
            cursor.execute("SELECT id_disciplina FROM Disciplinas WHERE nome_disciplina = ? AND id_evento_fk = ?", 
                           (nome_disciplina, id_event_context))
            row = cursor.fetchone()
            if row:
                self.logger.debug(f"Disciplina base '{nome_disciplina}' encontrada para o evento {id_event_context} com ID: {row['id_disciplina']}")
                return row['id_disciplina']

        # Tentar encontrar por nome globalmente (id_evento_fk IS NULL)
        cursor.execute("SELECT id_disciplina FROM Disciplinas WHERE nome_disciplina = ? AND id_evento_fk IS NULL", (nome_disciplina,))
        row = cursor.fetchone()
        if row:
            self.logger.debug(f"Disciplina base global '{nome_disciplina}' encontrada com ID: {row['id_disciplina']}")
            return row['id_disciplina']

        # Se não encontrou, cria uma nova
        new_disc_id = str(uuid.uuid4())
        # Por padrão, novas disciplinas criadas a partir de um cargo são associadas ao evento do cargo.
        # Se você quiser que sejam sempre globais, defina id_evento_para_nova_disc = None
        id_evento_para_nova_disc = id_event_context 

        self.logger.info(f"Criando nova disciplina base '{nome_disciplina}' com ID {new_disc_id} (Contexto do Evento: {id_evento_para_nova_disc or 'Global'})")
        try:
            cursor.execute("""
                INSERT INTO Disciplinas (id_disciplina, id_evento_fk, nome_disciplina, codigo_disciplina, descricao) 
                VALUES (?, ?, ?, ?, ?)
            """, (new_disc_id, id_evento_para_nova_disc, nome_disciplina, codigo_disciplina, descricao_disciplina))
            return new_disc_id
        except sqlite3.Error as e_create_disc:
            self.logger.error(f"Erro ao criar nova disciplina base '{nome_disciplina}': {e_create_disc}", exc_info=True)
            return None # Falha ao criar

    # --- Métodos para Cargos ---
    def add_cargo_to_event(self, id_event: str, cargo_data: CargoType) -> Optional[str]:
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Adicionando cargo '{cargo_data.nome_cargo}' (ID: {cargo_data.id_cargo}) ao evento ID '{id_event}'")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Serializar campos complexos para JSON string para o banco
            cover_pdf_paths_json = self._serialize_field_to_json_string(cargo_data.cover_pdf_paths)
            metadados_cargo_json = self._serialize_field_to_json_string(cargo_data.metadados_cargo, default_empty_for_list=False)

            sql_cargo = """
                INSERT INTO Cargos (
                    id_cargo, id_evento_fk, nome_cargo, codigo_cargo, nivel, turno, vagas, salario, 
                    requisitos, tem_discursiva, letterhead_pdf_path, cover_pdf_paths, 
                    peso_total_prova, metadados_cargo, data_criacao, data_modificacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params_cargo = (
                cargo_data.id_cargo, id_event, cargo_data.nome_cargo, cargo_data.codigo_cargo,
                cargo_data.nivel, cargo_data.turno, cargo_data.vagas, cargo_data.salario,
                cargo_data.requisitos, 
                1 if cargo_data.tem_discursiva else 0, # Converte bool para int para SQLite
                cargo_data.letterhead_pdf_path, cover_pdf_paths_json,
                cargo_data.peso_total_prova, metadados_cargo_json,
                (cargo_data.data_criacao.isoformat() if cargo_data.data_criacao else datetime.now().isoformat()),
                (cargo_data.data_modificacao.isoformat() if cargo_data.data_modificacao else datetime.now().isoformat())
            )
            cursor.execute(sql_cargo, params_cargo)
            self.logger.info(f"Cargo '{cargo_data.nome_cargo}' inserido na tabela Cargos.")

            # Salvar Disciplinas da Prova associadas ao Cargo
            if cargo_data.disciplinas_prova:
                self.logger.info(f"Salvando {len(cargo_data.disciplinas_prova)} disciplinas para o cargo ID {cargo_data.id_cargo}")
                sql_disciplina_prova = """
                    INSERT INTO DisciplinasDaProva (
                        id_disciplina_prova, id_cargo_fk, id_disciplina_base_fk, 
                        nome_disciplina_na_prova, qtd_questoes, peso_por_questao, ordem_na_prova, observacoes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                for disc_prova_obj in cargo_data.disciplinas_prova:
                    # Garantir que é do tipo correto, embora Pydantic já valide isso
                    if not isinstance(disc_prova_obj, DisciplinaProvaType):
                        self.logger.warning(f"Item inesperado em disciplinas_prova: {type(disc_prova_obj)}. Pulando.")
                        continue

                    # Obter/Criar ID da disciplina base
                    id_base_fk = disc_prova_obj.disciplina_base_id
                    if not id_base_fk: # Se não veio da UI, tenta buscar/criar pelo nome
                        id_base_fk = self._get_or_create_disciplina_base_id(
                            cursor, 
                            id_event, # Contexto do evento do cargo
                            disc_prova_obj.nome_disciplina # Nome para buscar/criar
                        )
                    
                    if not id_base_fk:
                        self.logger.error(f"Não foi possível determinar id_disciplina_base_fk para '{disc_prova_obj.nome_disciplina}' no cargo '{cargo_data.nome_cargo}'. Pulando esta disciplina.")
                        continue # Pula para a próxima disciplina

                    params_disciplina = (
                        disc_prova_obj.id_disciplina_prova, # UUID do DisciplinaProvaType
                        cargo_data.id_cargo,                # FK para o cargo atual
                        id_base_fk,                         # ID da disciplina na tabela Disciplinas
                        disc_prova_obj.nome_disciplina,     # Nome específico para esta prova/cargo
                        disc_prova_obj.qtd_questoes,
                        disc_prova_obj.peso_por_questao,
                        disc_prova_obj.ordem_na_prova,
                        disc_prova_obj.observacoes          # Campo observacoes
                    )
                    try:
                        cursor.execute(sql_disciplina_prova, params_disciplina)
                        self.logger.debug(f"DisciplinaDaProva '{disc_prova_obj.nome_disciplina}' (ID: {disc_prova_obj.id_disciplina_prova}) associada ao cargo '{cargo_data.id_cargo}'.")
                    except sqlite3.Error as e_disc_insert:
                        self.logger.error(f"Erro ao inserir DisciplinaDaProva '{disc_prova_obj.nome_disciplina}' para cargo '{cargo_data.id_cargo}': {e_disc_insert}", exc_info=True)
                        raise # Re-levanta para que o bloco except principal faça rollback
            
            conn.commit() # Commit final para cargo e suas disciplinas
            self.logger.info(f"Cargo '{cargo_data.nome_cargo}' (ID: {cargo_data.id_cargo}) e suas disciplinas (se houver) foram salvos para o evento ID {id_event}.")
            return cargo_data.id_cargo
        except sqlite3.IntegrityError as ie:
            self.logger.error(f"Erro de integridade ao adicionar cargo '{cargo_data.nome_cargo}' (ID: {cargo_data.id_cargo}): {ie}", exc_info=True)
            if conn: conn.rollback()
            return None
        except sqlite3.Error as e: # Captura outros erros SQLite
            self.logger.error(f"Erro SQLite ao adicionar cargo '{cargo_data.nome_cargo}': {e}", exc_info=True)
            if conn: conn.rollback()
            return None
        except Exception as e_general: # Captura erros não SQLite (ex: atributo faltando em disc_prova_obj)
             self.logger.error(f"Erro geral ao adicionar cargo '{cargo_data.nome_cargo}': {e_general}", exc_info=True)
             if conn: conn.rollback()
             return None
        finally:
            if conn:
                conn.close()
                self.logger.debug("Conexão (add_cargo_to_event) fechada.")
    
    def delete_cargo_from_event(self, id_event: str, cargo_id: str) -> bool:
        """
        Deleta um cargo específico de um evento, incluindo suas disciplinas associadas
        (assumindo ON DELETE CASCADE nas FKs da tabela DisciplinasDaProva para id_cargo_fk).
        Também deleta provas montadas associadas se houver ON DELETE CASCADE.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Tentando deletar cargo ID '{cargo_id}' do evento ID '{id_event}'")
        try:
            conn = self.get_db_connection() # Garante foreign_keys=ON
            cursor = conn.cursor()

            sql_delete_cargo = "DELETE FROM Cargos WHERE id_cargo = ? AND id_evento_fk = ?"
            cursor.execute(sql_delete_cargo, (cargo_id, id_event))
            
            conn.commit()

            if cursor.rowcount > 0:
                self.logger.info(f"Cargo ID '{cargo_id}' deletado com sucesso do evento ID '{id_event}'.")
                self.update_event_modification_timestamp(id_event) # Atualiza data de modificação do evento pai
                return True
            else:
                self.logger.warning(f"Nenhum cargo encontrado com ID '{cargo_id}' no evento '{id_event}' para deleção, ou deleção não afetou linhas.")
                return False
        except sqlite3.Error as e_delete:
            self.logger.error(f"Erro SQLite ao deletar cargo ID '{cargo_id}': {e_delete}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        except Exception as e_general:
            self.logger.error(f"Erro geral ao deletar cargo ID '{cargo_id}': {e_general}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug(f"Conexão (delete_cargo_from_event para cargo {cargo_id}) fechada.")
    
    def delete_questao_from_banco(self, id_event: str, disciplina_banco: str, questao_id: str) -> bool:
        """
        Exclui uma questão específica do banco de questões de um evento,
        incluindo suas opções, se houver.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Tentando excluir questão ID '{questao_id}' da disciplina '{disciplina_banco}' do evento ID '{id_event}'.")
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Etapa 1: Excluir opções associadas da tabela OpcoesQuestao (se houver)
            sql_delete_opcoes = "DELETE FROM OpcoesQuestao WHERE id_questao_fk = ?"
            cursor.execute(sql_delete_opcoes, (questao_id,))
            opcoes_deleted_count = cursor.rowcount
            self.logger.debug(f"Opções para questão ID '{questao_id}' excluídas (se existiam): {opcoes_deleted_count} linhas afetadas.")

            # Etapa 2: Excluir a questão da tabela QuestoesBanco
            sql_delete_questao = "DELETE FROM QuestoesBanco WHERE id_questao = ?"
            cursor.execute(sql_delete_questao, (questao_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                self.logger.info(f"Questão ID '{questao_id}' excluída com sucesso do banco de dados.")
                self.update_event_modification_timestamp(id_event)
                return True
            else:
                conn.rollback() 
                self.logger.warning(f"Questão ID '{questao_id}' não encontrada na tabela QuestoesBanco para exclusão.")
                return False

        except sqlite3.Error as e_sql:
            self.logger.error(f"Erro SQLite ao excluir questão ID '{questao_id}': {e_sql}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        except Exception as e_general:
            self.logger.error(f"Erro geral ao excluir questão ID '{questao_id}': {e_general}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug(f"Conexão (delete_questao_from_banco para questão {questao_id}) fechada.")
    
    def delete_reference_text(self, event_id_param: str, id_texto_ref_param: str) -> bool:
        """
        Exclui um texto de referência e, crucialmente, desvincula todas as questões
        associadas a ele no banco de dados antes da exclusão.
        """
        self.logger.info(f"Iniciando exclusão do texto de referência ID: {id_texto_ref_param} do evento ID: {event_id_param}")
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Inicia uma transação para garantir que todas as operações sejam bem-sucedidas ou nenhuma o seja.
            cursor.execute("BEGIN TRANSACTION;")

            # 1. Buscar o código do texto (necessário para limpar os metadados das questões)
            cursor.execute("SELECT codigo_ref, tipo_conteudo, caminho_imagem_relativo FROM TextosReferenciaGeral WHERE id_texto_ref = ?", (id_texto_ref_param,))
            ref_text_data_row = cursor.fetchone()

            if not ref_text_data_row:
                self.logger.warning(f"Texto de referência com ID {id_texto_ref_param} não encontrado para exclusão.")
                if conn: conn.rollback()
                return False

            codigo_ref_db = ref_text_data_row['codigo_ref']
            tipo_conteudo_db = ref_text_data_row['tipo_conteudo']
            caminho_imagem_relativo_db = ref_text_data_row['caminho_imagem_relativo']

            # --- INÍCIO DA CORREÇÃO DEFINITIVA ---
            # 2. Atualizar TODAS as questões vinculadas para remover as referências.
            #    Isso é feito diretamente no banco de dados para garantir a operação.
            self.logger.info(f"Procurando e desvinculando questões associadas ao texto ID {id_texto_ref_param}...")

            sql_update_questoes = """
                UPDATE QuestoesBanco
                SET 
                    id_texto_ref_vinculado = NULL,
                    metadados_questao = json_remove(metadados_questao, '$.codigo_ref_vinculado_gerado')
                WHERE 
                    id_texto_ref_vinculado = ? AND id_evento_fk = ?;
            """
            
            cursor.execute(sql_update_questoes, (id_texto_ref_param, event_id_param))
            questoes_atualizadas = cursor.rowcount
            self.logger.info(f"{questoes_atualizadas} questão(ões) foram desvinculadas com sucesso.")
            # --- FIM DA CORREÇÃO DEFINITIVA ---

            # 3. Excluir o registro do texto de referência
            cursor.execute("DELETE FROM TextosReferenciaGeral WHERE id_texto_ref = ?", (id_texto_ref_param,))
            self.logger.info(f"Registro do texto de referência ID {id_texto_ref_param} excluído da tabela.")

            # 4. Se era uma imagem, excluir o arquivo físico
            if tipo_conteudo_db == "imagem" and caminho_imagem_relativo_db:
                try:
                    media_storage_path = self.app_controller.config_manager.get_value("media_files_base_dir")
                    if not media_storage_path: media_storage_path = 'media_files'
                    
                    event_specific_media_path = os.path.join(media_storage_path, event_id_param)
                    absolute_image_path = os.path.join(event_specific_media_path, caminho_imagem_relativo_db)

                    if os.path.exists(absolute_image_path):
                        os.remove(absolute_image_path)
                        self.logger.info(f"Arquivo de imagem '{absolute_image_path}' excluído com sucesso.")
                except Exception as e_file_delete:
                    self.logger.error(f"Erro ao excluir arquivo de imagem: {e_file_delete}", exc_info=True)
                    if conn: conn.rollback() # Desfaz tudo se a exclusão do arquivo falhar
                    return False

            # 5. Se tudo correu bem, confirma as alterações no banco.
            conn.commit()
            self.logger.info(f"Exclusão do texto de referência ID {id_texto_ref_param} e desvinculação das questões concluídas com sucesso.")
            self.update_event_modification_timestamp(event_id_param)
            return True

        except Exception as e_general:
            self.logger.error(f"Erro geral ao excluir texto de referência ID {id_texto_ref_param}: {e_general}", exc_info=True)
            if conn: conn.rollback() # Desfaz tudo em caso de qualquer erro
            return False
        finally:
            if conn:
                conn.close()
    
    def update_event_modification_timestamp(self, id_event: str, conn: Optional[sqlite3.Connection] = None):
        """Atualiza o campo data_modificacao de um evento para o timestamp atual."""
        should_close = False
        try:
            if conn is None:
                conn = self.get_db_connection()
                should_close = True

            cursor = conn.cursor()
            sql = "UPDATE Eventos SET data_modificacao = CURRENT_TIMESTAMP WHERE id_evento = ?"
            cursor.execute(sql, (id_event,))
            conn.commit()

            if cursor.rowcount > 0:
                self.logger.debug(f"Timestamp de modificação atualizado para evento ID {id_event}")
            else:
                self.logger.warning(f"Evento ID {id_event} não encontrado para atualizar timestamp de modificação.")
        except sqlite3.Error as e:
            self.logger.error(f"Erro ao atualizar timestamp de modificação para evento {id_event}: {e}", exc_info=True)
        finally:
            if should_close and conn:
                conn.close()

    
    def update_cargo(self, cargo_id: str, cargo_data: CargoType) -> bool: # cargo_id é o ID do cargo a ser atualizado
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Atualizando cargo ID '{cargo_id}' com nome '{cargo_data.nome_cargo}'")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Serializar campos complexos para JSON string
            cover_pdf_paths_json = self._serialize_field_to_json_string(cargo_data.cover_pdf_paths)
            metadados_cargo_json = self._serialize_field_to_json_string(cargo_data.metadados_cargo, default_empty_for_list=False)
            
            id_event_context = cargo_data.id_evento 
            if not id_event_context:
                self.logger.error(f"id_evento não encontrado no objeto CargoType para o cargo ID '{cargo_id}'. Não é possível processar disciplinas.")
                raise ValueError(f"id_evento ausente no CargoType para o cargo {cargo_id}")

            sql_update_cargo = """
                UPDATE Cargos SET
                    nome_cargo = ?, codigo_cargo = ?, nivel = ?, turno = ?, vagas = ?, salario = ?,
                    requisitos = ?, tem_discursiva = ?, letterhead_pdf_path = ?, cover_pdf_paths = ?,
                    peso_total_prova = ?, metadados_cargo = ?, data_modificacao = CURRENT_TIMESTAMP
                WHERE id_cargo = ? 
            """
            params_update_cargo = (
                cargo_data.nome_cargo, cargo_data.codigo_cargo, cargo_data.nivel, cargo_data.turno,
                cargo_data.vagas, cargo_data.salario, cargo_data.requisitos,
                1 if cargo_data.tem_discursiva else 0, # Converte bool para int
                cargo_data.letterhead_pdf_path,
                cover_pdf_paths_json, cargo_data.peso_total_prova, metadados_cargo_json,
                cargo_id
            )
            cursor.execute(sql_update_cargo, params_update_cargo)
            self.logger.debug(f"Tabela Cargos atualizada para ID {cargo_id}. Rowcount: {cursor.rowcount}")

            # Atualizar DisciplinasDaProva (estratégia: delete all e re-insert)
            self.logger.debug(f"Deletando disciplinas antigas para o cargo ID {cargo_id}")
            cursor.execute("DELETE FROM DisciplinasDaProva WHERE id_cargo_fk = ?", (cargo_id,))
            
            if cargo_data.disciplinas_prova:
                self.logger.info(f"Reinserindo {len(cargo_data.disciplinas_prova)} disciplinas para o cargo ID {cargo_id}")
                sql_disciplina_prova = """
                    INSERT INTO DisciplinasDaProva (
                        id_disciplina_prova, id_cargo_fk, id_disciplina_base_fk, 
                        nome_disciplina_na_prova, qtd_questoes, peso_por_questao, ordem_na_prova, observacoes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                for disc_prova_obj in cargo_data.disciplinas_prova:
                    if not isinstance(disc_prova_obj, DisciplinaProvaType): continue

                    id_base_fk = disc_prova_obj.disciplina_base_id
                    if not id_base_fk and id_event_context: # Usa o id_event do cargo
                        id_base_fk = self._get_or_create_disciplina_base_id(
                            cursor, 
                            id_event_context, 
                            disc_prova_obj.nome_disciplina
                        )
                    
                    if not id_base_fk:
                        self.logger.error(f"Não foi possível determinar id_disciplina_base_fk para '{disc_prova_obj.nome_disciplina}' ao atualizar cargo '{cargo_id}'. Pulando.")
                        continue
                    
                    params_disciplina = (
                        disc_prova_obj.id_disciplina_prova, cargo_id, id_base_fk,
                        disc_prova_obj.nome_disciplina, disc_prova_obj.qtd_questoes,
                        disc_prova_obj.peso_por_questao, disc_prova_obj.ordem_na_prova,
                        disc_prova_obj.observacoes
                    )
                    cursor.execute(sql_disciplina_prova, params_disciplina)
            
            conn.commit()
            self.logger.info(f"Cargo ID {cargo_id} e suas disciplinas (se houver) atualizados.")
            self.update_event_modification_timestamp(id_event_context)
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao atualizar cargo ID {cargo_id}: {e}", exc_info=True)
            if conn: conn.rollback()
            return False
        except Exception as e_general:
            self.logger.error(f"Erro geral ao atualizar cargo ID {cargo_id}: {e_general}", exc_info=True)
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug("Conexão (update_cargo) fechada.")


    def add_or_update_reference_text(self, id_event: str, texto_ref_data: Union['TextoReferenciaType', Dict[str, Any]]) -> bool:
        import json
        conn: Optional[sqlite3.Connection] = None
        
        TextoRefModel = TextoReferenciaType

        self.logger.info(f"Attempting to save/update reference text for event ID {id_event}.")
        
        texto_ref_obj: 'TextoReferenciaType'

        if isinstance(texto_ref_data, dict):
            if 'id_evento_origem' not in texto_ref_data: 
                texto_ref_data['id_evento_origem'] = id_event
            if 'id_texto_ref' not in texto_ref_data: 
                texto_ref_data['id_texto_ref'] = str(uuid.uuid4())
            if 'codigo_ref' not in texto_ref_data : 
                self.logger.error("codigo_ref is missing from texto_ref_data dictionary.")
                return False
            try:
                texto_ref_obj = TextoRefModel(**texto_ref_data)
            except Exception as e_pydantic:
                self.logger.error(f"Error converting dict to TextoReferenciaType: {e_pydantic}", exc_info=True)
                return False
        elif isinstance(texto_ref_data, TextoRefModel):
            texto_ref_obj = texto_ref_data
            if getattr(texto_ref_obj, 'id_evento_origem', None) is None:
                try:
                    update_data = texto_ref_obj.model_dump()
                    update_data['id_evento_origem'] = id_event
                    texto_ref_obj = TextoRefModel(**update_data)
                except Exception as e_update_obj: 
                    self.logger.warning(f"Could not ensure id_evento_origem on existing TextoReferenciaType instance: {e_update_obj}. Using id_event from context for DB if needed.")
        else:
            self.logger.error(f"Invalid type for texto_ref_data: {type(texto_ref_data)}")
            return False

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            sql = """
                INSERT INTO TextosReferenciaGeral (
                    id_texto_ref, id_evento_fk, codigo_ref, titulo, conteudo, 
                    tipo_conteudo, caminho_imagem_relativo, descricao_imagem, 
                    metadados_texto_ref, data_criacao, data_modificacao, conteudo_formatado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id_texto_ref) DO UPDATE SET
                    id_evento_fk = excluded.id_evento_fk,
                    codigo_ref = excluded.codigo_ref,
                    titulo = excluded.titulo,
                    conteudo = excluded.conteudo,
                    tipo_conteudo = excluded.tipo_conteudo,
                    caminho_imagem_relativo = excluded.caminho_imagem_relativo,
                    descricao_imagem = excluded.descricao_imagem,
                    metadados_texto_ref = excluded.metadados_texto_ref,
                    conteudo_formatado = excluded.conteudo_formatado,
                    data_modificacao = CURRENT_TIMESTAMP;
            """
            
            db_id_texto_ref = texto_ref_obj.id_texto_ref
            db_id_evento_fk = texto_ref_obj.id_evento_origem if texto_ref_obj.id_evento_origem else id_event

            params = (
                db_id_texto_ref,
                db_id_evento_fk, 
                texto_ref_obj.codigo_ref,
                texto_ref_obj.titulo,
                texto_ref_obj.conteudo,
                texto_ref_obj.tipo_conteudo,
                texto_ref_obj.caminho_imagem_relativo,
                texto_ref_obj.descricao_imagem,
                json.dumps(texto_ref_obj.metadados_texto_ref or {}),
                (texto_ref_obj.data_criacao.isoformat() if texto_ref_obj.data_criacao else datetime.now().isoformat()),
                (texto_ref_obj.data_modificacao.isoformat() if texto_ref_obj.data_modificacao else datetime.now().isoformat()),
                json.dumps(texto_ref_obj.conteudo_formatado) if texto_ref_obj.conteudo_formatado is not None else None
            )
            
            self.logger.debug(f"Executing SQL for TextosReferenciaGeral: {sql} with params: {params}")
            cursor.execute(sql, params)
            conn.commit()
            self.logger.info(f"Reference text '{texto_ref_obj.codigo_ref}' (ID: {db_id_texto_ref}) for event '{id_event}' saved/updated successfully.")
            self.update_event_modification_timestamp(id_event)
            return True
        except AttributeError as ae: 
            self.logger.error(f"AttributeError while preparing SQL params for reference text: {ae}. Object data: {texto_ref_obj}", exc_info=True)
            if conn: conn.rollback()
            return False
        except sqlite3.Error as e_sql:
            self.logger.error(f"SQLite error saving/updating reference text '{getattr(texto_ref_obj, 'codigo_ref', 'N/A')}': {e_sql}", exc_info=True)
            if conn: conn.rollback()
            return False
        except Exception as e_general: 
            self.logger.error(f"General error saving/updating reference text '{getattr(texto_ref_obj, 'codigo_ref', 'N/A')}': {e_general}", exc_info=True)
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug("Connection (add_or_update_reference_text) closed.")


    def get_reference_text_data(self, id_event: str, codigo_ref: str) -> Optional['TextoReferenciaType']:
        conn: Optional[sqlite3.Connection] = None
        self.logger.debug(f"Attempting to retrieve reference text with codigo_ref '{codigo_ref}' for id_event '{id_event}'.")

        TextoRefModel = TextoReferenciaType

        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            sql = """
                SELECT * FROM TextosReferenciaGeral 
                WHERE id_evento_fk = ? AND codigo_ref = ?;
            """
            params = (id_event, codigo_ref)
            
            cursor.execute(sql, params)
            row = cursor.fetchone()
            
            if row:
                texto_ref_dict = dict(row)
                
                # Desserializar metadados_texto_ref
                if 'metadados_texto_ref' in texto_ref_dict and isinstance(texto_ref_dict['metadados_texto_ref'], str):
                    try:
                        texto_ref_dict['metadados_texto_ref'] = json.loads(texto_ref_dict['metadados_texto_ref'])
                    except json.JSONDecodeError:
                        self.logger.error(f"JSONDecodeError for metadados_texto_ref of {codigo_ref}. Defaulting to empty dict.")
                        texto_ref_dict['metadados_texto_ref'] = {}
                elif 'metadados_texto_ref' not in texto_ref_dict or texto_ref_dict['metadados_texto_ref'] is None:
                    texto_ref_dict['metadados_texto_ref'] = {}
                
                # Desserializar conteudo_formatado
                if 'conteudo_formatado' in texto_ref_dict and texto_ref_dict['conteudo_formatado']:
                    try:
                        texto_ref_dict['conteudo_formatado'] = json.loads(texto_ref_dict['conteudo_formatado'])
                    except Exception:
                        texto_ref_dict['conteudo_formatado'] = None
                else:
                    texto_ref_dict['conteudo_formatado'] = None

                # Mapear id_evento_fk para id_evento_origem para o modelo Pydantic
                if 'id_evento_fk' in texto_ref_dict and 'id_evento_origem' not in texto_ref_dict:
                    texto_ref_dict['id_evento_origem'] = texto_ref_dict.pop('id_evento_fk')

                # Converter datas para objetos datetime
                texto_ref_dict['data_criacao'] = self._convert_date_field(texto_ref_dict.get('data_criacao'), 'data_criacao', id_event)
                texto_ref_dict['data_modificacao'] = self._convert_date_field(texto_ref_dict.get('data_modificacao'), 'data_modificacao', id_event)

                self.logger.info(f"Reference text '{codigo_ref}' found for event '{id_event}'.")
                return TextoRefModel(**texto_ref_dict)
            else:
                self.logger.warning(f"No reference text found with codigo_ref '{codigo_ref}' for id_event '{id_event}'.")
                return None
                
        except sqlite3.Error as e_sql:
            self.logger.error(f"SQLite error retrieving reference text '{codigo_ref}' for event '{id_event}': {e_sql}", exc_info=True)
            return None
        except Exception as e_general:
            self.logger.error(f"General error retrieving reference text '{codigo_ref}' for event '{id_event}': {e_general}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
                self.logger.debug("Connection (get_reference_text_data) closed.")


    def get_all_reference_texts_for_event(self, event_id: str) -> List['TextoReferenciaType']:
        conn: Optional[sqlite3.Connection] = None
        texts: List[TextoReferenciaType] = []
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = "SELECT * FROM TextosReferenciaGeral WHERE id_evento_fk = ? ORDER BY codigo_ref;"
            cursor.execute(sql, (event_id,))
            rows = cursor.fetchall()

            for row_data in rows:
                text_dict = dict(row_data)
                # Desserializar e converter datas como em get_reference_text_data
                if 'metadados_texto_ref' in text_dict and isinstance(text_dict['metadados_texto_ref'], str):
                    try: text_dict['metadados_texto_ref'] = json.loads(text_dict['metadados_texto_ref'])
                    except json.JSONDecodeError: text_dict['metadados_texto_ref'] = {}
                elif 'metadados_texto_ref' not in text_dict or text_dict['metadados_texto_ref'] is None:
                    text_dict['metadados_texto_ref'] = {}

                # PATCH: Desserializar conteudo_formatado SEMPRE como dict, list ou None
                if 'conteudo_formatado' in text_dict:
                    val = text_dict['conteudo_formatado']
                    if isinstance(val, str) and val:
                        try:
                            val = json.loads(val)
                        except Exception:
                            val = None
                    if not isinstance(val, (dict, list)):
                        val = None
                    text_dict['conteudo_formatado'] = val
                else:
                    text_dict['conteudo_formatado'] = None

                print(
                    "DEBUG conteudo_formatado:", 
                    type(text_dict.get('conteudo_formatado')), 
                    text_dict.get('conteudo_formatado')
                )

                if 'id_evento_fk' in text_dict and 'id_evento_origem' not in text_dict:
                    text_dict['id_evento_origem'] = text_dict.pop('id_evento_fk')
                
                text_dict['data_criacao'] = self._convert_date_field(text_dict.get('data_criacao'), 'data_criacao', event_id)
                text_dict['data_modificacao'] = self._convert_date_field(text_dict.get('data_modificacao'), 'data_modificacao', event_id)

                try:
                    texts.append(TextoReferenciaType(**text_dict))
                except Exception as e_pydantic:
                    self.logger.error(f"Erro ao criar TextoReferenciaType para evento {event_id} com dados {text_dict}: {e_pydantic}", exc_info=True)
            return texts
        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao buscar textos de referência para evento {event_id}: {e}", exc_info=True)
            return []
        except Exception as e:
            self.logger.error(f"Erro geral ao buscar textos de referência para evento {event_id}: {e}", exc_info=True)
            return []
        finally:
            if conn: conn.close()
    
    def get_reference_texts_by_event_id(self, event_id: str, key_by: str = "codigo_ref") -> Dict[str, 'TextoReferenciaType']:
        """
        Busca os textos de referência de um evento específico, corrigindo a desserialização.
        Permite chavear por 'codigo_ref' (default) ou por 'id_texto_ref' (UUID).
        """
        self.logger.info(f"Buscando textos de referência para o evento ID: {event_id}...")
        texts_map = {}

        sql = "SELECT * FROM TextosReferenciaGeral WHERE id_evento_fk = ?"

        try:
            with self.get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, (event_id,))
                rows = cursor.fetchall()

                from core.elements import TextoReferenciaType
                for row in rows:
                    row_dict = dict(row)

                    # CORREÇÃO: Desserializar metadados
                    if 'metadados_texto_ref' in row_dict and isinstance(row_dict['metadados_texto_ref'], str):
                        try:
                            row_dict['metadados_texto_ref'] = json.loads(row_dict['metadados_texto_ref'])
                        except json.JSONDecodeError:
                            row_dict['metadados_texto_ref'] = {}

                    # PATCH: Desserializar conteudo_formatado para garantir que seja uma lista
                    if 'conteudo_formatado' in row_dict and isinstance(row_dict['conteudo_formatado'], str):
                        try:
                            row_dict['conteudo_formatado'] = json.loads(row_dict['conteudo_formatado'])
                        except Exception:
                            row_dict['conteudo_formatado'] = []
                    elif 'conteudo_formatado' not in row_dict or row_dict['conteudo_formatado'] is None:
                        row_dict['conteudo_formatado'] = []

                    text_obj = TextoReferenciaType(**row_dict)
                    # Chaveamento flexível
                    if key_by == "id_texto_ref":
                        texts_map[text_obj.id_texto_ref] = text_obj
                    else:
                        texts_map[text_obj.codigo_ref] = text_obj

                self.logger.info(f"Carregados {len(texts_map)} textos de referência para o evento (key_by={key_by}).")

        except Exception as e:
            self.logger.error(f"Falha ao buscar textos de referência: {e}", exc_info=True)

        return texts_map
    
    def limpar_questoes_disciplina_evento(self, id_event: str, disciplina_banco: str) -> bool:
        """
        Remove todas as questões (e suas opções) de uma disciplina específica
        de um evento do banco de dados.
        Também atualiza o campo banco_questoes_json na tabela Eventos, se existir.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Iniciando limpeza de todas as questões da disciplina '{disciplina_banco}' do evento ID '{id_event}'.")
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # 1. Encontrar todas as questões da disciplina para este evento
            cursor.execute(
                "SELECT id_questao FROM QuestoesBanco WHERE id_evento_fk = ? AND disciplina_banco = ?",
                (id_event, disciplina_banco)
            )
            questao_ids_para_excluir = [row['id_questao'] for row in cursor.fetchall()]

            if not questao_ids_para_excluir:
                self.logger.info(f"Nenhuma questão encontrada para a disciplina '{disciplina_banco}' no evento '{id_event}'.")
            else:
                # 2. Para cada questão, excluir suas opções da tabela OpcoesQuestao
                opcoes_deleted_total = 0
                for questao_id in questao_ids_para_excluir:
                    cursor.execute("DELETE FROM OpcoesQuestao WHERE id_questao_fk = ?", (questao_id,))
                    opcoes_deleted_total += cursor.rowcount
                self.logger.debug(f"{opcoes_deleted_total} opções excluídas para as questões da disciplina '{disciplina_banco}'.")

                # 3. Excluir as questões da tabela QuestoesBanco
                placeholders = ', '.join('?' for _ in questao_ids_para_excluir)
                sql_delete_questoes = f"DELETE FROM QuestoesBanco WHERE id_questao IN ({placeholders})"
                cursor.execute(sql_delete_questoes, tuple(questao_ids_para_excluir)) # Use tuple() for params
                questoes_deleted_count = cursor.rowcount
                self.logger.info(f"{questoes_deleted_count} questões da disciplina '{disciplina_banco}' excluídas da tabela QuestoesBanco.")

            # 4. Atualizar o Eventos.banco_questoes_json para remover a disciplina
            cursor.execute("SELECT banco_questoes_json FROM Eventos WHERE id_evento = ?", (id_event,))
            event_row = cursor.fetchone()
            
            if event_row:
                banco_questoes_json_str = event_row['banco_questoes_json']
                current_banco_questoes_dict = {}
                if banco_questoes_json_str:
                    try:
                        current_banco_questoes_dict = json.loads(banco_questoes_json_str)
                    except json.JSONDecodeError:
                        self.logger.error(f"Erro ao decodificar banco_questoes_json para o evento {id_event} ao limpar disciplina.")
                
                if disciplina_banco in current_banco_questoes_dict:
                    del current_banco_questoes_dict[disciplina_banco]
                    self.logger.info(f"Disciplina '{disciplina_banco}' removida da estrutura banco_questoes para atualização do JSON.")
                    
                    updated_banco_json = json.dumps(current_banco_questoes_dict)
                    sql_update_event_json = "UPDATE Eventos SET banco_questoes_json = ?, data_modificacao = CURRENT_TIMESTAMP WHERE id_evento = ?"
                    cursor.execute(sql_update_event_json, (updated_banco_json, id_event))
                    if cursor.rowcount == 0:
                        self.logger.warning(f"Não foi possível encontrar o evento {id_event} para atualizar banco_questoes_json após limpar disciplina.")
                else:
                    self.logger.info(f"Disciplina '{disciplina_banco}' não estava presente no banco_questoes_json do evento {id_event} (ou JSON estava vazio/nulo). Nenhuma atualização de JSON necessária.")
            else:
                self.logger.warning(f"Evento {id_event} não encontrado ao tentar atualizar banco_questoes_json após limpar disciplina.")

            conn.commit()
            self.logger.info(f"Limpeza de questões da disciplina '{disciplina_banco}' do evento ID '{id_event}' concluída com sucesso.")
            self.update_event_modification_timestamp(id_event)
            return True

        except sqlite3.Error as e_sql:
            self.logger.error(f"Erro SQLite ao limpar questões da disciplina '{disciplina_banco}' para evento '{id_event}': {e_sql}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        except Exception as e_general:
            self.logger.error(f"Erro geral ao limpar questões da disciplina '{disciplina_banco}' para evento '{id_event}': {e_general}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug(f"Conexão (limpar_questoes_disciplina_evento para {disciplina_banco}) fechada.")

    def save_questao_banco(self, questao_obj: 'QuestaoType', event_id_param: Optional[str] = None) -> Optional[str]:
        """Salva (insere ou atualiza) uma questão e seus detalhes no banco de dados, incluindo campos formatados."""
        import json
        conn: Optional[sqlite3.Connection] = None
        q_id = questao_obj.id_questao
        self.logger.info(f"Salvando questão ID {q_id}...")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            q_event_id_para_db = event_id_param or questao_obj.id_evento_origem
            if not q_event_id_para_db:
                self.logger.error(f"ID do evento não fornecido para questão ID {q_id}.")
                return None 

            # Serialização dos campos para JSON
            q_tags_json = self._serialize_field_to_json_string(questao_obj.tags)
            q_metadados_json = self._serialize_field_to_json_string(questao_obj.metadados_questao, default_empty_for_list=False)
            q_imagens_enunciado_json = self._serialize_field_to_json_string(questao_obj.imagens_enunciado)
            q_imagens_enunciado_refs_json = self._serialize_field_to_json_string(questao_obj.imagens_enunciado_refs)
            q_textos_referencia_questao_json = self._serialize_field_to_json_string(questao_obj.textos_referencia_questao)

            tipo_db_val = questao_obj.tipo.value if isinstance(questao_obj.tipo, Enum) else questao_obj.tipo
            nivel_dificuldade_db_val = questao_obj.nivel_dificuldade.value if isinstance(questao_obj.nivel_dificuldade, Enum) else questao_obj.nivel_dificuldade

            # Serialização dos campos formatados
            enunciado_formatado_json = json.dumps(questao_obj.enunciado_formatado) if questao_obj.enunciado_formatado is not None else None
            justificativa_anulacao_recurso_formatado_json = json.dumps(questao_obj.justificativa_anulacao_recurso_formatado) if questao_obj.justificativa_anulacao_recurso_formatado is not None else None

            sql_insert_questao = """
                INSERT OR REPLACE INTO QuestoesBanco (
                    id_questao, id_evento_fk, enunciado, enunciado_formatado, tipo, disciplina_banco, resposta_correta,
                    gabarito_preliminar, gabarito_definitivo, nivel_dificuldade, 
                    tempo_esperado_resposta_segundos, tags_keywords, id_texto_ref_vinculado, 
                    status_revisao, justificativa_anulacao, criador_id, metadados_questao, 
                    disciplina_id, conteudo_id, conteudo_nome, pontuacao, feedback_geral_questao, 
                    revisada, autor_elaborador, data_modificacao, numero_questao_original_docx,
                    hash_conteudo_questao, fonte_questao, anulada, justificativa_anulacao_recurso,
                    justificativa_anulacao_recurso_formatado, imagens_enunciado, imagens_enunciado_refs, textos_referencia_questao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params_questoes = (
                q_id, q_event_id_para_db, questao_obj.enunciado, enunciado_formatado_json, tipo_db_val, questao_obj.disciplina_banco,
                questao_obj.resposta_correta, questao_obj.gabarito_preliminar, questao_obj.gabarito_definitivo,
                nivel_dificuldade_db_val, questao_obj.tempo_esperado_resposta_segundos, q_tags_json,
                questao_obj.id_texto_ref_vinculado, questao_obj.status_revisao, questao_obj.justificativa_anulacao,
                questao_obj.criador_id, q_metadados_json, questao_obj.disciplina_id, questao_obj.conteudo_id,
                questao_obj.conteudo_nome, questao_obj.pontuacao, questao_obj.feedback_geral_questao,
                1 if questao_obj.revisada else 0, 
                questao_obj.autor_elaborador,
                datetime.now().isoformat(),
                questao_obj.numero_questao_original_docx, 
                questao_obj.hash_conteudo_questao, 
                questao_obj.fonte_questao,
                1 if questao_obj.anulada else 0, 
                questao_obj.justificativa_anulacao_recurso,
                justificativa_anulacao_recurso_formatado_json,
                q_imagens_enunciado_json, 
                q_imagens_enunciado_refs_json, 
                q_textos_referencia_questao_json, 
            )
            print("DEBUG SQL INSERT QUESTAO:", params_questoes)
            cursor.execute(sql_insert_questao, params_questoes)

            # Salvar Opções (se for múltipla escolha)
            if questao_obj.tipo == TipoQuestao.MULTIPLA_ESCOLHA and questao_obj.opcoes: 
                cursor.execute("DELETE FROM OpcoesQuestao WHERE id_questao_fk = ?", (q_id,))
                sql_insert_opcao = """
                    INSERT INTO OpcoesQuestao (
                        id_opcao_questao, id_questao_fk, letra, texto_opcao, texto_opcao_formatado, correta, 
                        feedback_opcao, imagem_path_opcao, ordem_original
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                for opcao in questao_obj.opcoes:
                    id_opcao_str = str(opcao.id_opcao) 
                    texto_opcao_formatado_json = json.dumps(opcao.texto_opcao_formatado) if opcao.texto_opcao_formatado is not None else None
                    cursor.execute(sql_insert_opcao, (
                        id_opcao_str,  
                        q_id, 
                        opcao.letra, 
                        opcao.texto_opcao, 
                        texto_opcao_formatado_json,
                        1 if opcao.correta else 0, 
                        opcao.feedback, 
                        opcao.imagem_path_opcao,
                        opcao.ordem_original
                    ))
            
            self.logger.debug(f"Rowcount insert Questao: {cursor.rowcount}")

            # Salvar Detalhes Discursiva
            if questao_obj.tipo == TipoQuestao.DISCURSIVA and questao_obj.detalhes_discursiva:
                self.logger.info(f"Salvando/Atualizando detalhes discursivos para questão ID {q_id}")
                detalhes = questao_obj.detalhes_discursiva
                id_detalhe_db = str(detalhes.id_detalhe_discursiva)

                sql_detalhes_discursiva = """
                    INSERT INTO DetalhesQuestaoDiscursiva (
                        id_detalhe_discursiva, id_questao_fk, resposta_esperada_texto,
                        palavras_chave_resposta, numero_linhas_resposta
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id_questao_fk) DO UPDATE SET 
                        resposta_esperada_texto = excluded.resposta_esperada_texto,
                        palavras_chave_resposta = excluded.palavras_chave_resposta,
                        numero_linhas_resposta = excluded.numero_linhas_resposta;
                """
                palavras_chave_json = self._serialize_field_to_json_string(detalhes.palavras_chave_resposta)
                
                params_detalhes = (
                    id_detalhe_db,
                    q_id,
                    detalhes.resposta_esperada_texto,
                    palavras_chave_json,
                    detalhes.numero_linhas_resposta
                )
                cursor.execute(sql_detalhes_discursiva, params_detalhes)
                self.logger.info(f"Detalhes discursivos para questão ID {q_id} salvos/atualizados.")
            elif questao_obj.tipo != TipoQuestao.DISCURSIVA:
                cursor.execute("DELETE FROM DetalhesQuestaoDiscursiva WHERE id_questao_fk = ?", (q_id,))
                self.logger.info(f"Detalhes discursivos removidos para questão ID {q_id} (se existiam), pois tipo não é mais Discursiva.")

            # Salvar Itens Verdadeiro/Falso
            if questao_obj.tipo == TipoQuestao.VERDADEIRO_FALSO and questao_obj.itens_verdadeiro_falso:
                self.logger.info(f"Salvando/Atualizando itens V/F para questão ID {q_id}")
                cursor.execute("DELETE FROM ItensVerdadeiroFalso WHERE id_questao_fk = ?", (q_id,))
                sql_itens_vf = """
                    INSERT INTO ItensVerdadeiroFalso (
                        id_item_vf, id_questao_fk, afirmacao, valor_correto, feedback_item, ordem
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """
                for item_vf in questao_obj.itens_verdadeiro_falso:
                    id_item_vf_str = str(item_vf.id_item_vf)
                    cursor.execute(sql_itens_vf, (
                        id_item_vf_str,
                        q_id,
                        item_vf.afirmacao,
                        1 if item_vf.valor_correto else 0,
                        item_vf.feedback_item,
                        item_vf.ordem
                    ))
                self.logger.info(f"Itens V/F para questão ID {q_id} salvos/atualizados.")
            elif questao_obj.tipo != TipoQuestao.VERDADEIRO_FALSO:
                cursor.execute("DELETE FROM ItensVerdadeiroFalso WHERE id_questao_fk = ?", (q_id,))
                self.logger.info(f"Itens V/F removidos para questão ID {q_id} (se existiam), pois tipo não é mais Verdadeiro/Falso.")

            conn.commit()
            self.logger.info(f"Questão ID {q_id} salva com sucesso.")
            return q_id

        except sqlite3.Error as e_sqlite:
            self.logger.error(f"Erro SQLite ao salvar questão ID {q_id}: {e_sqlite}", exc_info=True)
            if conn: conn.rollback()
            return None
        
        except Exception as e_general:
            self.logger.error(f"Erro geral ao salvar questão ID {q_id}: {e_general}", exc_info=True)
            if conn: conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    
    def get_todos_blocos_de_questoes_do_evento(self, id_evento: str) -> List[str]:
        """
        Busca todos os nomes de "blocos de questões" (arquivos DOCX originais,
        da coluna QuestoesBanco.disciplina_banco) para um dado id_evento.
        Retorna uma lista de strings (nomes dos blocos/arquivos).
        """
        conn: Optional[sqlite3.Connection] = None
        nomes_blocos: List[str] = []
        self.logger.debug(f"EventManager: Buscando nomes de blocos de questões para evento ID: {id_evento}")
        if not id_evento:
            self.logger.warning("ID do evento não fornecido para buscar blocos de questões.")
            return []
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()
            
            query = """
                SELECT DISTINCT disciplina_banco 
                FROM QuestoesBanco
                WHERE id_evento_fk = ?  -- Filtra pelo evento atual
                  AND disciplina_banco IS NOT NULL 
                  AND disciplina_banco != ''
                ORDER BY disciplina_banco;
            """
            
            self.logger.debug(f"Executando query para buscar blocos de questões: {query} com params: ({id_evento},)")
            cursor.execute(query, (id_evento,))
            rows = cursor.fetchall() 
            
            if rows:
                for row in rows:
                    nomes_blocos.append(row["disciplina_banco"])
            
            self.logger.info(f"Encontrados {len(nomes_blocos)} blocos de questões distintos para o evento '{id_evento}'.")
            return nomes_blocos

        except sqlite3.OperationalError as e_op:
            if "no such table: questoesbanco" in str(e_op).lower():
                self.logger.error(f"Erro SQLite: A tabela QuestoesBanco não existe. Detalhe: {e_op}", exc_info=True)
            else:
                self.logger.error(f"Erro SQLite operacional ao buscar blocos de questões: {e_op}", exc_info=True)
            return []
        except Exception as e_gen:
            self.logger.error(f"Erro geral ao buscar blocos de questões: {e_gen}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
                self.logger.debug("EventManager (get_todos_blocos_de_questoes_do_evento): Conexão fechada.")

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
    
    
    def obter_questoes_do_evento(self, id_event: str, disciplina_banco: Optional[str] = None) -> List[QuestaoType]:
        conn: Optional[sqlite3.Connection] = None
        questoes_list: List[QuestaoType] = [] 
        self.logger.debug(f"Buscando questões para evento ID '{id_event}', bloco (disciplina_banco): '{disciplina_banco}'")

        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()

            sql_questoes = "SELECT * FROM QuestoesBanco WHERE id_evento_fk = ?"
            params_questoes_list = [id_event] 

            if disciplina_banco:
                sql_questoes += " AND disciplina_banco = ?" 
                params_questoes_list.append(disciplina_banco)
            
            sql_questoes += " ORDER BY data_criacao ASC, id_questao ASC;"
            params_questoes = tuple(params_questoes_list)

            self.logger.debug(f"Executando query: {sql_questoes} com params: {params_questoes}")
            cursor.execute(sql_questoes, params_questoes)
            questao_rows = cursor.fetchall()
            self.logger.debug(f"Encontradas {len(questao_rows)} linhas de questões no banco.")

            for row_data in questao_rows:
                questao_dict = dict(row_data)
                print("DEBUG QUESTAO DO BANCO:", questao_dict['id_questao'], questao_dict.get('id_texto_ref_vinculado'))

                # Corrige campos formatados que vêm como string JSON ou None
                for field in ['enunciado_formatado', 'justificativa_anulacao_recurso_formatado']:
                    if isinstance(questao_dict.get(field), str):
                        try:
                            questao_dict[field] = json.loads(questao_dict[field])
                        except Exception:
                            questao_dict[field] = []
                    elif field not in questao_dict or questao_dict[field] is None:
                        questao_dict[field] = []

                # PATCH: Desserializar conteudo_formatado (caso exista no questao_dict)
                if 'conteudo_formatado' in questao_dict and questao_dict['conteudo_formatado']:
                    try:
                        questao_dict['conteudo_formatado'] = json.loads(questao_dict['conteudo_formatado'])
                    except Exception:
                        questao_dict['conteudo_formatado'] = []
                else:
                    questao_dict['conteudo_formatado'] = []

                # Desserializar campos JSON já existentes (mantido)
                for json_field, default_val in [
                    ('tags_keywords', []),
                    ('metadados_questao', {}),
                    ('imagens_enunciado', []),
                    ('imagens_enunciado_refs', []),
                    ('textos_referencia_questao', [])
                ]:
                    if json_field in questao_dict and isinstance(questao_dict[json_field], str):
                        try:
                            questao_dict[json_field] = json.loads(questao_dict[json_field])
                        except json.JSONDecodeError:
                            self.logger.error(f"JSONDecodeError para '{json_field}' em questao {questao_dict.get('id_questao')}")
                            questao_dict[json_field] = default_val
                    elif json_field not in questao_dict or questao_dict[json_field] is None:
                        questao_dict[json_field] = default_val

                # Mapear tags_keywords para tags
                if 'tags_keywords' in questao_dict:
                    questao_dict['tags'] = questao_dict.pop('tags_keywords')

                print("DEBUG (ANTES DO PARSE):", questao_dict.get('enunciado_formatado'))

                from core.utils import parse_enunciado_formatado

                enunciado_formatado_raw = questao_dict.get('enunciado_formatado')
                enunciado_formatado_final = []

                # 1. Se vier como string JSON, tenta desserializar
                if isinstance(enunciado_formatado_raw, str) and enunciado_formatado_raw.strip():
                    try:
                        lista_bruta = json.loads(enunciado_formatado_raw)
                        if isinstance(lista_bruta, list):
                            for item in lista_bruta:
                                if isinstance(item, list):
                                    enunciado_formatado_final.append(tuple(item))
                    except (json.JSONDecodeError, TypeError):
                        self.logger.warning(f"Falha ao decodificar enunciado_formatado da questão {questao_dict.get('id_questao')}")
                        enunciado_formatado_final = parse_enunciado_formatado(questao_dict.get('enunciado', ''))

                # ✅ 2. Se já vier como lista (do banco ou processado), apenas normaliza para tuplas
                elif isinstance(enunciado_formatado_raw, list):
                    enunciado_formatado_final = [tuple(item) for item in enunciado_formatado_raw]

                # 3. Se vier vazio ou None, usa o parser como fallback
                elif not enunciado_formatado_raw:
                    enunciado_formatado_final = parse_enunciado_formatado(questao_dict.get('enunciado', ''))

                # 4. Atribui ao dict
                questao_dict['enunciado_formatado'] = enunciado_formatado_final

                # 5. Debug
                print("DEBUG ENUNCIADO FORMATADO FINAL:", questao_dict['enunciado_formatado'])

                # 6. Backup de segurança
                if not questao_dict['enunciado_formatado']:
                    questao_dict['enunciado_formatado'] = parse_enunciado_formatado(questao_dict.get('enunciado', ''))

                print("DEBUG ENUNCIADO FORMATADO FINAL:", questao_dict['enunciado_formatado'])



                if 'justificativa_anulacao_recurso_formatado' in questao_dict and questao_dict['justificativa_anulacao_recurso_formatado']:
                    try:
                        questao_dict['justificativa_anulacao_recurso_formatado'] = json.loads(questao_dict['justificativa_anulacao_recurso_formatado'])
                    except Exception:
                        questao_dict['justificativa_anulacao_recurso_formatado'] = []
                else:
                    questao_dict['justificativa_anulacao_recurso_formatado'] = []

                # Converter booleanos de int para bool
                if 'revisada' in questao_dict: questao_dict['revisada'] = bool(questao_dict['revisada'])
                if 'anulada' in questao_dict: questao_dict['anulada'] = bool(questao_dict['anulada'])

                # Converter datas para objetos datetime
                questao_dict['data_criacao'] = self._convert_date_field(questao_dict.get('data_criacao'), 'data_criacao', id_event)
                questao_dict['data_modificacao'] = self._convert_date_field(questao_dict.get('data_modificacao'), 'data_modificacao', id_event)
                
                # Converter tipo e nivel_dificuldade para Enum
                if 'tipo' in questao_dict and isinstance(questao_dict['tipo'], str):
                    try:
                        questao_dict['tipo'] = TipoQuestao(questao_dict['tipo'])
                    except ValueError:
                        self.logger.warning(f"Valor de tipo inválido '{questao_dict['tipo']}' para questão {questao_dict.get('id_questao')}. Mantendo como string.")
                
                if 'nivel_dificuldade' in questao_dict and isinstance(questao_dict['nivel_dificuldade'], str):
                    try:
                        questao_dict['nivel_dificuldade'] = NivelDificuldadeQuestao(questao_dict['nivel_dificuldade'])
                    except ValueError:
                        self.logger.warning(f"Valor de nivel_dificuldade inválido '{questao_dict['nivel_dificuldade']}' para questão {questao_dict.get('id_questao')}. Mantendo como string.")

                # Carregar opções se for múltipla escolha
                opcoes_list_for_model: List[OpcaoMultiplaEscolha] = []
                if questao_dict.get('tipo') == TipoQuestao.MULTIPLA_ESCOLHA:
                    cursor.execute("SELECT * FROM OpcoesQuestao WHERE id_questao_fk = ? ORDER BY letra ASC;", (questao_dict['id_questao'],))
                    opcao_rows = cursor.fetchall()
                    for opt_row_data in opcao_rows:
                        opt_dict = dict(opt_row_data)
                        if 'correta' in opt_dict:
                            opt_dict['correta'] = bool(opt_dict['correta'])
                        if 'id_opcao_questao' in opt_dict:
                            opt_dict['id_opcao'] = opt_dict.pop('id_opcao_questao')
                        # Desserializar campo formatado da alternativa (NOVO)
                        if 'texto_opcao_formatado' in opt_dict and opt_dict['texto_opcao_formatado']:
                            try:
                                opt_dict['texto_opcao_formatado'] = json.loads(opt_dict['texto_opcao_formatado'])
                            except Exception:
                                opt_dict['texto_opcao_formatado'] = None
                        else:
                            opt_dict['texto_opcao_formatado'] = None
                        try:
                            opcoes_list_for_model.append(OpcaoMultiplaEscolha(**opt_dict))
                        except Exception as e_opt_pydantic:
                            self.logger.error(f"Error creating OpcaoMultiplaEscolha object for q {questao_dict['id_questao']}, opt_data {opt_dict}: {e_opt_pydantic}", exc_info=True)
                questao_dict['opcoes'] = opcoes_list_for_model
                
                # Carregar detalhes discursivos (mantido)
                detalhes_discursiva_model: Optional[DetalhesQuestaoDiscursiva] = None
                if questao_dict.get('tipo') == TipoQuestao.DISCURSIVA:
                    cursor.execute("SELECT * FROM DetalhesQuestaoDiscursiva WHERE id_questao_fk = ?", (questao_dict['id_questao'],))
                    detalhes_row = cursor.fetchone()
                    if detalhes_row:
                        detalhes_dict = dict(detalhes_row)
                        if 'palavras_chave_resposta' in detalhes_dict and isinstance(detalhes_dict['palavras_chave_resposta'], str):
                            try: detalhes_dict['palavras_chave_resposta'] = json.loads(detalhes_dict['palavras_chave_resposta'])
                            except json.JSONDecodeError: detalhes_dict['palavras_chave_resposta'] = []
                        try:
                            detalhes_discursiva_model = DetalhesQuestaoDiscursiva(**detalhes_dict)
                        except Exception as e_det_pydantic:
                            self.logger.error(f"Error creating DetalhesQuestaoDiscursiva for q {questao_dict['id_questao']}, data {detalhes_dict}: {e_det_pydantic}", exc_info=True)
                questao_dict['detalhes_discursiva'] = detalhes_discursiva_model

                # Carregar itens verdadeiro/falso (mantido)
                itens_verdadeiro_falso_list: List[ItemVerdadeiroFalso] = []
                if questao_dict.get('tipo') == TipoQuestao.VERDADEIRO_FALSO:
                    cursor.execute("SELECT * FROM ItensVerdadeiroFalso WHERE id_questao_fk = ? ORDER BY ordem ASC;", (questao_dict['id_questao'],))
                    itens_vf_rows = cursor.fetchall()
                    for item_vf_row_data in itens_vf_rows:
                        item_vf_dict = dict(item_vf_row_data)
                        if 'valor_correto' in item_vf_dict: item_vf_dict['valor_correto'] = bool(item_vf_dict['valor_correto'])
                        if 'id_item_vf_questao' in item_vf_dict and 'id_item_vf' not in item_vf_dict:
                            item_vf_dict['id_item_vf'] = item_vf_dict.pop('id_item_vf_questao')
                        try:
                            itens_verdadeiro_falso_list.append(ItemVerdadeiroFalso(**item_vf_dict))
                        except Exception as e_vf_pydantic:
                            self.logger.error(f"Error creating ItemVerdadeiroFalso for q {questao_dict['id_questao']}, data {item_vf_dict}: {e_vf_pydantic}", exc_info=True)
                questao_dict['itens_verdadeiro_falso'] = itens_verdadeiro_falso_list

                # Mapear id_evento_fk para id_evento_origem
                if 'id_evento_fk' in questao_dict and 'id_evento_origem' not in questao_dict:
                    questao_dict['id_evento_origem'] = questao_dict.pop('id_evento_fk')
                
                print(
                    "DEBUG enunciado_formatado:", 
                    type(questao_dict.get('enunciado_formatado')), 
                    questao_dict.get('enunciado_formatado')
                )

                # >>>>> ADICIONE ESTE BLOCO <<<<<
                # Garante enunciado_formatado sempre presente e formatado
                if not questao_dict.get('enunciado_formatado'):
                    questao_dict['enunciado_formatado'] = parse_enunciado_formatado(questao_dict.get('enunciado', ''))
                # >>>>> FIM DO BLOCO <<<<<
                
                # Cria a instância final do QuestaoType
                try:
                    campos_validos_questao = {k: v for k, v in questao_dict.items() if k in QuestaoType.model_fields}
                    questoes_list.append(QuestaoType(**campos_validos_questao))
                except Exception as e_ques_pydantic:
                    self.logger.error(f"Error creating QuestaoType object for questao {questao_dict.get('id_questao')}: {e_ques_pydantic}", exc_info=True)
                    self.logger.debug(f"Data causing QuestaoType hydration error: {questao_dict}")

            self.logger.info(f"Retrieved {len(questoes_list)} objetos QuestaoType for evento '{id_event}', bloco (disciplina_banco) '{disciplina_banco}'.")
            return questoes_list

        except sqlite3.Error as e_sql:
            self.logger.error(f"SQLite error retrieving questions for event '{id_event}': {e_sql}", exc_info=True)
            return []
        except Exception as e_general:
            self.logger.error(f"General error retrieving questions for event '{id_event}': {e_general}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
                self.logger.debug("Connection (obter_questoes_do_evento) closed.")

    def get_nomes_arquivos_origem_por_disciplina_id(self, disciplina_id_selecionada: str) -> List[str]:
        self.logger.info(f"EventManager: Buscando nomes de arquivos DOCX (de QuestoesBanco.disciplina_banco) para disciplina_id: {disciplina_id_selecionada}")
        
        if not disciplina_id_selecionada:
            self.logger.warning("EventManager: disciplina_id_selecionada não fornecida.")
            return []

        conn: Optional[sqlite3.Connection] = None
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()

            query = """
                SELECT DISTINCT disciplina_banco 
                FROM QuestoesBanco 
                WHERE disciplina_id = ?
                  AND disciplina_banco IS NOT NULL 
                  AND disciplina_banco != ''
                ORDER BY disciplina_banco;
            """
            
            self.logger.debug(f"Executando query: {query} com params: ({disciplina_id_selecionada},)")
            cursor.execute(query, (disciplina_id_selecionada,))
            rows = cursor.fetchall()
            
            nomes_arquivos = [row[0] for row in rows if row[0]] 
            
            self.logger.info(f"EventManager: Encontrados {len(nomes_arquivos)} arquivos DOCX para disciplina_id: {disciplina_id_selecionada}. Arquivos: {nomes_arquivos}")
            return nomes_arquivos

        except sqlite3.Error as e_sqlite:
            self.logger.error(f"EventManager: Erro SQLite ao buscar nomes de arquivos DOCX: {e_sqlite}", exc_info=True)
            return []
        except Exception as e_general:
            self.logger.error(f"EventManager: Erro geral ao buscar nomes de arquivos DOCX: {e_general}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
                self.logger.debug("EventManager (get_nomes_arquivos_origem_por_disciplina_id): Conexão fechada.")

    def get_db_connection(self, *args, **kwargs) -> sqlite3.Connection:
        """
        Retorna uma nova conexão SQLite usando o provider passado ao EventManager.
        Aceita argumentos opcionais para timeout, etc.
        """
        if hasattr(self, "db_connection_provider") and callable(self.db_connection_provider):
            return self.db_connection_provider(*args, **kwargs)
        else:
            self.logger.error("db_connection_provider não configurado corretamente no EventManager.")
            raise ValueError("Configuração de banco de dados ausente no EventManager para get_db_connection")

    def get_todas_disciplinas_do_banco(self) -> List[DisciplinaType]:
        conn: Optional[sqlite3.Connection] = None
        disciplinas_encontradas: List[DisciplinaType] = [] 
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()
            
            sql = """ 
                SELECT DISTINCT 
                    id_disciplina_banco_fk as id_disciplina, 
                    disciplina_banco
                FROM BlocosQuestoes 
                WHERE id_disciplina_banco_fk IS NOT NULL AND disciplina_banco IS NOT NULL
                ORDER BY disciplina_banco;
            """
            
            cursor.execute(sql)
            rows = cursor.fetchall()
            self.logger.info(f"EventManager (get_todas_disciplinas_do_banco) - Rows do DB: {len(rows) if rows else 0}")

            if rows:
                for row_data in rows:
                    try:
                        disc_dict = {
                            'id_disciplina': row_data['id_disciplina'],
                            'nome_disciplina': row_data['nome_disciplina'],
                        }
                        disciplinas_encontradas.append(DisciplinaType(**disc_dict))
                    except KeyError as ke:
                        self.logger.error(f"Erro de Chave ao criar DisciplinaType em get_todas_disciplinas_do_banco: {ke} - Row: {dict(row_data)}", exc_info=False)
                    except Exception as e_obj:
                        self.logger.error(f"Erro ao criar objeto DisciplinaType em get_todas_disciplinas_do_banco: {e_obj} - Row: {dict(row_data)}", exc_info=True)
            
            self.logger.info(f"EventManager (get_todas_disciplinas_do_banco) - Retornando: {len(disciplinas_encontradas)} disciplinas")
            return disciplinas_encontradas 

        except sqlite3.Error as e_sqlite:
            self.logger.error(f"Erro SQLite em get_todas_disciplinas_do_banco: {e_sqlite}", exc_info=True)
            return []
        except Exception as e_geral:
            self.logger.error(f"Erro geral em get_todas_disciplinas_do_banco: {e_geral}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
    
    def check_if_value_exists(self, table_name: str, column_name: str, value: Any) -> bool:
        """
        Verifica de forma genérica se um valor já existe em uma tabela e coluna específicas.
        Retorna True se o valor existir, False caso contrário.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.debug(f"Verificando existência de valor na Tabela: '{table_name}', Coluna: '{column_name}' para o Valor: '{value}'")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Usar aspas duplas em volta dos nomes de tabela/coluna para segurança, 
            # embora a formatação de string aqui seja geralmente segura, pois os nomes vêm do nosso próprio código.
            query = f'SELECT 1 FROM "{table_name}" WHERE "{column_name}" = ? LIMIT 1'
            
            cursor.execute(query, (value,))
            result = cursor.fetchone()
            
            # Se fetchone() retornar algo, significa que o valor existe.
            return result is not None

        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao verificar existência em '{table_name}': {e}", exc_info=True)
            # Em caso de erro, é mais seguro assumir que o valor pode existir para evitar duplicatas.
            # Ou você pode querer que ele retorne False e registre o erro. Retornar True é mais seguro.
            return True 
        finally:
            if conn:
                conn.close()
    
    def get_arquivos_com_contagem_questoes_por_disciplina_id(self, disciplina_id_fk: str) -> List[Dict[str, Any]]:
        """
        Busca os nomes distintos de arquivos DOCX (da coluna QuestoesBanco.disciplina_banco)
        e a contagem de questões para um determinado disciplina_id_fk.
        Retorna uma lista de dicionários: [{'nome_arquivo': str, 'caminho_completo_arquivo': str, 'qtd_questoes': int}, ...].
        """
        conn: Optional[sqlite3.Connection] = None
        arquivos_info_list: List[Dict[str, Any]] = []
        self.logger.debug(f"EventManager: Buscando arquivos DOCX e contagem para disciplina_id: {disciplina_id_fk}")

        if not disciplina_id_fk:
            self.logger.warning("EventManager: disciplina_id_fk não fornecido para get_arquivos_com_contagem_questoes_por_disciplina_id.")
            return []
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()

            query = """
                SELECT 
                    disciplina_banco, 
                    COUNT(id_questao) as qtd_questoes
                FROM QuestoesBanco
                WHERE disciplina_id = ? 
                  AND disciplina_banco IS NOT NULL 
                  AND disciplina_banco != ''
                GROUP BY disciplina_banco
                ORDER BY disciplina_banco;
            """
            self.logger.debug(f"Executando query: {query} com params: ({disciplina_id_fk},)")
            cursor.execute(query, (disciplina_id_fk,))
            rows = cursor.fetchall()

            if rows:
                for row in rows:
                    caminho_completo_arquivo = row["disciplina_banco"] 
                    nome_arquivo_display = os.path.basename(caminho_completo_arquivo) if caminho_completo_arquivo else "Desconhecido"
                    qtd_questoes = row["qtd_questoes"] 
                    
                    arquivos_info_list.append({
                        "nome_arquivo": nome_arquivo_display,
                        "caminho_completo_arquivo": caminho_completo_arquivo, 
                        "qtd_questoes": qtd_questoes
                    })
            
            self.logger.info(f"Encontrados {len(arquivos_info_list)} arquivos com questões para a disciplina_id '{disciplina_id_fk}'.")
            return arquivos_info_list
        except sqlite3.OperationalError as e_op:
            if "no such table: questoesbanco" in str(e_op).lower():
                 self.logger.error(f"Erro SQLite: A tabela QuestoesBanco não existe. Detalhe: {e_op}", exc_info=True)
            elif "no such column" in str(e_op).lower():
                 self.logger.error(f"Erro SQLite: A query em get_arquivos_com_contagem_questoes_por_disciplina_id referencia uma coluna que não existe. Verifique os nomes das colunas. Detalhe: {e_op}", exc_info=True)
            else:
                self.logger.error(f"Erro SQLite operacional ao buscar arquivos para disciplina '{disciplina_id_fk}': {e_op}", exc_info=True)
            return []
        except Exception as e_gen:
            self.logger.error(f"Erro geral ao buscar arquivos para disciplina '{disciplina_id_fk}': {e_gen}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
                self.logger.debug("EventManager (get_arquivos_com_contagem_questoes_por_disciplina_id): Conexão fechada.")
    
    def get_all_proof_assemblies_for_event(self, event_id: str, banco_questoes_evento: Dict[str, List['QuestaoType']]) -> List['ProvaMontadaType']:
        """
        Busca todas as provas montadas para um evento e PREENCHE os blocos
        com as questões correspondentes do banco de questões do evento.
        """
        import json
        conn: Optional[sqlite3.Connection] = None
        proofs: List['ProvaMontadaType'] = []
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = "SELECT * FROM ProvasMontadas WHERE id_evento_fk = ? ORDER BY nome_prova_montada;"
            cursor.execute(sql, (event_id,))
            rows = cursor.fetchall()

            for row_data in rows:
                proof_dict = dict(row_data)
                
                if 'id_evento_fk' in proof_dict: proof_dict['id_evento'] = proof_dict.pop('id_evento_fk')
                if 'id_cargo_fk' in proof_dict: proof_dict['id_cargo'] = proof_dict.pop('id_cargo_fk')

                blocos_json_str = proof_dict.get('blocos_questoes_json') or '[]'
                blocos_questoes_list = []
                if blocos_json_str:
                    try:
                        list_of_dicts = json.loads(blocos_json_str)
                        for bloco_dict in list_of_dicts:
                            # --- INÍCIO DA LÓGICA DE CORREÇÃO ---
                            chave_busca = bloco_dict.get("agrupamento_banco")
                            questoes_para_o_bloco = []

                            # Busca as questões no banco de questões que a função recebeu
                            if chave_busca and chave_busca in banco_questoes_evento:
                                questoes_do_banco = banco_questoes_evento[chave_busca]
                                num_a_usar = bloco_dict.get("qtd_questoes", len(questoes_do_banco))
                                # Pega uma amostra das questões para o bloco
                                questoes_para_o_bloco = questoes_do_banco[:num_a_usar]
                            
                            # Adiciona a lista de questões (agora preenchida) ao dicionário
                            bloco_dict['questoes'] = questoes_para_o_bloco
                            # --- FIM DA LÓGICA DE CORREÇÃO ---

                            blocos_questoes_list.append(BlocoQuestoesType(**bloco_dict))
                    except Exception as e_json:
                        self.logger.error(f"Erro ao processar blocos de questões: {e_json}")

                proof_dict['blocos_questoes'] = blocos_questoes_list

                # ======================= NOVO BLOCO DE CÓDIGO ADICIONADO AQUI =======================
                # Desserializar Textos de Referência
                textos_ref_json_str = proof_dict.get('textos_referencia_prova_json', '[]')
                textos_ref_list = []
                if textos_ref_json_str:
                    try:
                        # Carrega a string JSON em uma lista de dicionários
                        list_of_dicts = json.loads(textos_ref_json_str)
                        # Converte cada dicionário em um objeto TextoReferenciaType
                        for texto_ref_dict in list_of_dicts:
                            textos_ref_list.append(TextoReferenciaType(**texto_ref_dict))
                    except (json.JSONDecodeError, TypeError) as e:
                        self.logger.error(f"Erro ao desserializar textos_referencia_prova_json para prova {proof_dict.get('id_prova_montada')}: {e}")
                
                # Atribui a lista de objetos ao dicionário que será usado para criar o objeto final
                proof_dict['textos_referencia_prova'] = textos_ref_list
                # ====================================================================================

                # Desserializar outros campos JSON (configurações, metadados, etc.)
                for json_field, default_val in [('metadados_prova', {}), ('configuracoes', {})]:
                    db_field_name = 'configuracoes_prova' if json_field == 'configuracoes' else json_field
                    if db_field_name in proof_dict and isinstance(proof_dict[db_field_name], str):
                        try:
                            proof_dict[json_field] = json.loads(proof_dict[db_field_name])
                        except json.JSONDecodeError:
                            proof_dict[json_field] = default_val
                    elif json_field not in proof_dict or proof_dict[json_field] is None:
                        proof_dict[json_field] = default_val
                    if db_field_name != json_field and db_field_name in proof_dict:
                        del proof_dict[db_field_name]

                # Converter datas
                for date_field in ['data_criacao', 'data_modificacao', 'data_ultima_geracao']:
                    proof_dict[date_field] = self._convert_date_field(proof_dict.get(date_field), date_field, event_id)

                unwanted_fields = [
                    'estrutura_prova_json', 'textos_referencia_prova_json', 'blocos_questoes_json',
                    'questoes_por_disciplina', 'ordem_disciplinas_na_prova', 'questoes_por_disciplina_json',
                    'ordem_disciplinas_na_prova_json', 'tipo_prova', 'numero_versoes',
                    'instrucoes_gerais', 'texto_cabecalho_prova_docx', 'texto_rodape_prova_docx',
                    'frase_assinatura_folha_rosto', 'data_geracao'
                ]
                for unwanted in unwanted_fields:
                    proof_dict.pop(unwanted, None)

                try:
                    if 'configuracoes' in proof_dict and isinstance(proof_dict['configuracoes'], dict):
                        proof_dict['configuracoes'] = ConfiguracoesProvaType(**proof_dict['configuracoes'])
                    else:
                        proof_dict['configuracoes'] = ConfiguracoesProvaType()

                    prova = ProvaMontadaType(**proof_dict)
                    print("DEBUG ProvaMontadaType criado:", prova)
                    proofs.append(prova)
                except Exception as e_pydantic:
                    print("ERRO ao criar ProvaMontadaType:", e_pydantic)
                    self.logger.error(f"Erro ao criar ProvaMontadaType para evento {event_id} com dados {proof_dict}: {e_pydantic}", exc_info=True)
            print(f"DEBUG: Retornando {len(proofs)} provas montadas do método")
            return proofs
        except sqlite3.Error as e:
            print("ERRO SQLite:", e)
            self.logger.error(f"Erro SQLite ao buscar provas montadas para evento {event_id}: {e}", exc_info=True)
            return []
        except Exception as e:
            print("ERRO geral:", e)
            self.logger.error(f"Erro geral ao buscar provas montadas para evento {event_id}: {e}", exc_info=True)
            return []
        finally:
            if conn: conn.close()

    def update_proof_assembly(self, proof_id: str, updates: Dict[str, Any]) -> bool:
        """
        Atualiza uma prova montada existente.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Attempting to update proof assembly ID {proof_id} with data: {updates}")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            set_clauses = []
            params = []

            # Campos diretos
            direct_fields = {
                "nome_prova_montada": "nome_prova_montada", "caminho_arquivo_gerado": "caminho_arquivo_gerado",
                "tipo_prova": "tipo_prova", "numero_versoes": "numero_versoes",
                "identificador_prova": "identificador_prova", "responsavel_montagem": "responsavel_montagem",
                "status_montagem": "status_montagem", "titulo_prova": "titulo_prova",
                "frase_assinatura_folha_rosto": "frase_assinatura_folha_rosto",
                "hash_prova_gerada": "hash_prova_gerada"
            }
            for model_field, db_column in direct_fields.items():
                if model_field in updates:
                    value = updates[model_field]
                    if isinstance(value, Enum): value = value.value
                    set_clauses.append(f"{db_column} = ?")
                    params.append(value)
            
            # Campos de data
            if "data_geracao" in updates:
                value = updates["data_geracao"]
                if isinstance(value, (datetime, date)): value = value.isoformat()
                set_clauses.append("data_geracao = ?")
                params.append(value)
            
            # Campos JSON
            if "estrutura_prova_json" in updates:
                set_clauses.append("estrutura_prova_json = ?")
                params.append(self._serialize_field_to_json_string(updates["estrutura_prova_json"], default_empty_for_list=False))
            if "metadados_prova" in updates:
                set_clauses.append("metadados_prova = ?")
                params.append(self._serialize_field_to_json_string(updates["metadados_prova"], default_empty_for_list=False))
            if "blocos_questoes" in updates:
                set_clauses.append("blocos_questoes_json = ?") # Assumindo nome da coluna no DB
                params.append(self._serialize_field_to_json_string(updates["blocos_questoes"], default_empty_for_list=True))
            if "textos_referencia_prova" in updates:
                set_clauses.append("textos_referencia_prova_json = ?") # Assumindo nome da coluna no DB
                params.append(self._serialize_field_to_json_string(updates["textos_referencia_prova"], default_empty_for_list=True))
            
            # Campo de configuração aninhado
            if "configuracoes" in updates and isinstance(updates["configuracoes"], ConfiguracoesProvaType):
                set_clauses.append("configuracoes_prova = ?") # Coluna no DB para ConfiguracoesProvaType
                params.append(json.dumps(updates["configuracoes"].model_dump(exclude_none=True)))
            elif "configuracoes" in updates and isinstance(updates["configuracoes"], dict): # Se for um dict bruto
                set_clauses.append("configuracoes_prova = ?")
                params.append(json.dumps(updates["configuracoes"]))

            if not set_clauses:
                self.logger.info(f"No valid fields to update for proof assembly ID {proof_id}.")
                return True 

            set_clauses.append("data_modificacao = CURRENT_TIMESTAMP") # Atualiza timestamp
            
            sql = f"UPDATE ProvasMontadas SET {', '.join(set_clauses)} WHERE id_prova_montada = ?"
            params.append(proof_id)
            
            self.logger.debug(f"Executing SQL for update_proof_assembly: {sql} with params: {params}")
            cursor.execute(sql, tuple(params))
            conn.commit()

            if cursor.rowcount > 0:
                self.logger.info(f"Prova montada ID {proof_id} atualizada com sucesso.")
                # Atualizar a data de modificação do evento pai
                current_proof = self.get_prova_montada_by_id(proof_id)
                if current_proof and current_proof.id_evento:
                    self.update_event_modification_timestamp(current_proof.id_evento)
                return True
            return False
        except sqlite3.Error as e_update:
            self.logger.error(f"Falha ao atualizar prova montada ID {proof_id}: {e_update}", exc_info=True)
            if conn: conn.rollback()
            return False
        except Exception as e_general:
            self.logger.error(f"Erro geral ao atualizar prova montada ID {proof_id}: {e_general}", exc_info=True)
            if conn: conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug("Connection (update_proof_assembly) closed.")

    def save_prova_montada(self, prova_obj: ProvaMontadaType) -> Optional[str]:
        self.logger.debug(f"type={type(prova_obj)} | dict={getattr(prova_obj, '__dict__', prova_obj)} | dir={dir(prova_obj)}")
        id_prova = prova_obj.id_prova_montada
        self.logger.info(f"Salvando/Atualizando prova montada ID {id_prova}...")

        try:
            required_fields = {
                "id_evento_fk": getattr(prova_obj, "id_evento", None),
                "id_cargo_fk": getattr(prova_obj, "id_cargo", None),
                "nome_prova_montada": getattr(prova_obj, "nome_prova_montada", None)
            }
            missing = [k for k, v in required_fields.items() if not v]
            if missing:
                raise ValueError(f"Campos obrigatórios não preenchidos: {', '.join(missing)}")

            # >>>>>>>>>>>> GARANTA AQUI OS CAMPOS OBRIGATÓRIOS <<<<<<<<<<<<<<<<<<<<<
            # Se algum campo vier como None, preencha com estrutura padrão!
            estrutura_prova = getattr(prova_obj, "blocos_questoes", None) or []
            metadados_prova = getattr(prova_obj, "metadados_prova", None) or {}
            # ======================= LINHA CORRIGIDA =======================
            configuracoes_prova = getattr(prova_obj, "configuracoes", None) or ConfiguracoesProvaType()
            # ===============================================================
            blocos_questoes = getattr(prova_obj, "blocos_questoes", None) or []
            textos_referencia_prova = getattr(prova_obj, "textos_referencia_prova", None) or []

            # Agora serialize SEMPRE com dados válidos
            estrutura_prova_json = self._serialize_field_to_json_string(estrutura_prova)
            metadados_prova_json = self._serialize_field_to_json_string(metadados_prova)
            configuracoes_json = self._serialize_field_to_json_string(configuracoes_prova)
            blocos_questoes_json = self._serialize_field_to_json_string(blocos_questoes)
            textos_referencia_prova_json = self._serialize_field_to_json_string(textos_referencia_prova)

            # Enums
            status_montagem = getattr(prova_obj, "status_montagem", "Em Elaboração")
            tipo_prova = getattr(prova_obj, "tipo_prova", None)
            status_montagem_db = status_montagem.value if isinstance(status_montagem, Enum) else status_montagem
            tipo_prova_db = tipo_prova.value if isinstance(tipo_prova, Enum) else tipo_prova

            with self.get_db_connection(timeout_seconds=30) as conn:
                cursor = conn.cursor()

                sql = """
                    INSERT OR REPLACE INTO ProvasMontadas (
                        id_prova_montada, id_evento_fk, id_cargo_fk, nome_prova_montada,
                        estrutura_prova_json, data_criacao, data_modificacao,
                        caminho_arquivo_gerado, tipo_prova, numero_versoes,
                        identificador_prova, responsavel_montagem, status_montagem,
                        titulo_prova, blocos_questoes_json, textos_referencia_prova_json,
                        configuracoes_prova, data_ultima_geracao, hash_prova_gerada,
                        frase_assinatura_folha_rosto
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    id_prova,
                    getattr(prova_obj, "id_evento", None),
                    getattr(prova_obj, "id_cargo", None),
                    getattr(prova_obj, "nome_prova_montada", ""),
                    estrutura_prova_json,
                    (getattr(prova_obj, "data_criacao", None).isoformat() if getattr(prova_obj, "data_criacao", None) else datetime.now().isoformat()),
                    (getattr(prova_obj, "data_modificacao", None).isoformat() if getattr(prova_obj, "data_modificacao", None) else datetime.now().isoformat()),
                    getattr(prova_obj, "caminho_arquivo_gerado", None),
                    tipo_prova_db,
                    getattr(prova_obj, "numero_versoes", None),
                    getattr(prova_obj, "identificador_prova", None),
                    getattr(prova_obj, "responsavel_montagem", None),
                    status_montagem_db,
                    getattr(prova_obj, "titulo_prova", None),
                    blocos_questoes_json,
                    textos_referencia_prova_json,
                    configuracoes_json,
                    (getattr(prova_obj, "data_ultima_geracao", None).isoformat() if getattr(prova_obj, "data_ultima_geracao", None) else None),
                    getattr(prova_obj, "hash_prova_gerada", None),
                    getattr(prova_obj, "frase_assinatura_folha_rosto", None)
                )

                cursor.execute(sql, params)
                conn.commit()

                self.update_event_modification_timestamp(prova_obj.id_evento, conn=conn)

                self.logger.info(f"Prova montada '{prova_obj.nome_prova_montada}' (ID: {id_prova}) salva/atualizada com sucesso.")
                return id_prova

        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao salvar prova montada ID {id_prova}: {e}", exc_info=True)
            return None
        except Exception as e_general:
            self.logger.error(f"Erro geral ao salvar prova montada ID {id_prova}: {e_general}", exc_info=True)
            return None

        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao salvar prova montada ID {id_prova}: {e}", exc_info=True)
            return None
        except Exception as e_general:
            self.logger.error(f"Erro geral ao salvar prova montada ID {id_prova}: {e_general}", exc_info=True)
            return None

    def get_prova_montada_by_id(self, id_prova: str) -> Optional['ProvaMontadaType']:
        """
        Busca uma prova montada pelo seu ID.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.debug(f"Buscando prova montada por ID: {id_prova}")
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = "SELECT * FROM ProvasMontadas WHERE id_prova_montada = ?;"
            cursor.execute(sql, (id_prova,))
            row = cursor.fetchone()

            if not row:
                self.logger.warning(f"Prova montada com ID '{id_prova}' não encontrada.")
                return None
            
            proof_dict = dict(row)

            # Mapear id_evento_fk para id_evento, id_cargo_fk para id_cargo
            if 'id_evento_fk' in proof_dict: proof_dict['id_evento'] = proof_dict.pop('id_evento_fk')
            if 'id_cargo_fk' in proof_dict: proof_dict['id_cargo'] = proof_dict.pop('id_cargo_fk')

            # Desserializar campos JSON
            for json_field, default_val in [
                ('estrutura_prova_json', None), ('metadados_prova', {}),
                ('configuracoes_prova', {}), ('blocos_questoes_json', []),
                ('textos_referencia_prova_json', [])
            ]:
                # Mapear nomes de colunas do DB para nomes de campos Pydantic
                pydantic_field_name = json_field
                if json_field == 'configuracoes_prova': pydantic_field_name = 'configuracoes'
                elif json_field == 'blocos_questoes_json': pydantic_field_name = 'blocos_questoes'
                elif json_field == 'textos_referencia_prova_json': pydantic_field_name = 'textos_referencia_prova'

                if json_field in proof_dict and isinstance(proof_dict[json_field], str):
                    try:
                        proof_dict[pydantic_field_name] = json.loads(proof_dict[json_field])
                    except json.JSONDecodeError:
                        self.logger.error(f"JSONDecodeError para '{json_field}' em prova {id_prova}. Valor: {proof_dict[json_field]}", exc_info=True)
                        proof_dict[pydantic_field_name] = default_val
                elif pydantic_field_name not in proof_dict or proof_dict[json_field] is None:
                    proof_dict[pydantic_field_name] = default_val
            
            # Converter datas
            proof_dict['data_geracao'] = self._convert_date_field(proof_dict.get('data_geracao'), 'data_geracao', proof_dict.get('id_evento'))
            proof_dict['data_criacao'] = self._convert_date_field(proof_dict.get('data_criacao'), 'data_criacao', proof_dict.get('id_evento'))
            proof_dict['data_modificacao'] = self._convert_date_field(proof_dict.get('data_modificacao'), 'data_modificacao', proof_dict.get('id_evento'))
            proof_dict['data_ultima_geracao'] = self._convert_date_field(proof_dict.get('data_ultima_geracao'), 'data_ultima_geracao', proof_dict.get('id_evento'))

            # Converter booleanos
            if 'incluir_folha_rascunho' in proof_dict and isinstance(proof_dict['incluir_folha_rascunho'], int):
                proof_dict['incluir_folha_rascunho'] = bool(proof_dict['incluir_folha_rascunho'])
            # Adicione outros booleanos como 'embaralhar_questoes', 'mostrar_pontuacao_questoes' etc.

            # Converter Enums
            if 'status_montagem' in proof_dict and isinstance(proof_dict['status_montagem'], str):
                try: proof_dict['status_montagem'] = proof_dict['status_montagem'] # Mantenha como string se não houver Enum
                except ValueError: self.logger.warning(f"Status '{proof_dict['status_montagem']}' inválido para ProvaMontadaType.")
            if 'tipo_prova' in proof_dict and isinstance(proof_dict['tipo_prova'], str):
                try: proof_dict['tipo_prova'] = proof_dict['tipo_prova'] # Mantenha como string se não houver Enum
                except ValueError: self.logger.warning(f"Tipo prova '{proof_dict['tipo_prova']}' inválido para ProvaMontadaType.")

            # Instanciar ConfiguracoesProvaType
            if 'configuracoes' in proof_dict and isinstance(proof_dict['configuracoes'], dict):
                proof_dict['configuracoes'] = ConfiguracoesProvaType(**proof_dict['configuracoes'])
            else:
                proof_dict['configuracoes'] = ConfiguracoesProvaType() # Default

            # Instanciar BlocoQuestoesType para cada item em blocos_questoes
            if 'blocos_questoes' in proof_dict and isinstance(proof_dict['blocos_questoes'], list):
                proof_dict['blocos_questoes'] = [BlocoQuestoesType(**b) for b in proof_dict['blocos_questoes']]
            else:
                proof_dict['blocos_questoes'] = []

            # Instanciar TextoReferenciaType para cada item em textos_referencia_prova
            if 'textos_referencia_prova' in proof_dict and isinstance(proof_dict['textos_referencia_prova'], list):
                proof_dict['textos_referencia_prova'] = [TextoReferenciaType(**tr) for tr in proof_dict['textos_referencia_prova']]
            else:
                proof_dict['textos_referencia_prova'] = []

            self.logger.info(f"Prova montada '{id_prova}' encontrada e processada.")
            return ProvaMontadaType(**proof_dict)

        except sqlite3.Error as e_sql:
            self.logger.error(f"Erro SQLite ao buscar prova montada ID '{id_prova}': {e_sql}", exc_info=True)
            return None
        except Exception as e_general:
            self.logger.error(f"Erro geral ao buscar prova montada ID '{id_prova}': {e_general}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
                self.logger.debug("Conexão (get_prova_montada_by_id) fechada.")
    
    def get_prova_montada_do_cargo(self, event_id: str, cargo_id: str) -> Optional['ProvaMontadaType']:
        """
        Retorna a prova montada para um cargo específico em um evento.
        """
        all_proofs = self.get_all_proof_assemblies_for_event(event_id)
        for proof in all_proofs:
            if getattr(proof, "id_cargo", None) == cargo_id:
                return proof
        return None

    def excluir_prova_montada_do_cargo(self, event_id: str, cargo_id: str) -> bool:
        """
        Exclui todas as provas montadas para um cargo específico em um evento.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Tentando excluir prova(s) montada(s) para Evento ID '{event_id}', Cargo ID '{cargo_id}'.")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            sql = "DELETE FROM ProvasMontadas WHERE id_evento_fk = ? AND id_cargo_fk = ?"
            cursor.execute(sql, (event_id, cargo_id))
            conn.commit()

            if cursor.rowcount > 0:
                self.logger.info(f"Prova(s) montada(s) excluída(s) com sucesso para Evento ID '{event_id}', Cargo ID '{cargo_id}'.")
                self.update_event_modification_timestamp(event_id, conn=conn)  # ← Correção aqui
                return True
            else:
                self.logger.warning(f"Nenhuma prova montada encontrada para Evento ID '{event_id}', Cargo ID '{cargo_id}'.")
                return False
        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao excluir prova montada para evento {event_id}, cargo {cargo_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        except Exception as e:
            self.logger.error(f"Erro geral ao excluir prova montada para evento {event_id}, cargo {cargo_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug(f"Conexão (excluir_prova_montada_do_cargo para evento {event_id}, cargo {cargo_id}) fechada.")
    
    def excluir_prova_montada_do_cargo(self, event_id: str, cargo_id: str) -> bool:
        """
        Exclui todas as provas montadas para um cargo específico em um evento.
        """
        conn: Optional[sqlite3.Connection] = None
        self.logger.info(f"Tentando excluir prova(s) montada(s) para Evento ID '{event_id}', Cargo ID '{cargo_id}'.")
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = "DELETE FROM ProvasMontadas WHERE id_evento_fk = ? AND id_cargo_fk = ?"
            cursor.execute(sql, (event_id, cargo_id))
            conn.commit()
            if cursor.rowcount > 0:
                self.logger.info(f"Prova(s) montada(s) excluída(s) com sucesso para Evento ID '{event_id}', Cargo ID '{cargo_id}'.")
                self.update_event_modification_timestamp(event_id)
                return True
            else:
                self.logger.warning(f"Nenhuma prova montada encontrada para Evento ID '{event_id}', Cargo ID '{cargo_id}'.")
                return False
        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao excluir prova montada para evento {event_id}, cargo {cargo_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        except Exception as e:
            self.logger.error(f"Erro geral ao excluir prova montada para evento {event_id}, cargo {cargo_id}: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
                self.logger.debug(f"Conexão (excluir_prova_montada_do_cargo para evento {event_id}, cargo {cargo_id}) fechada.")

    def _get_unique_disciplinas_from_banco_questoes(self, event_id: str) -> List[Dict[str, str]]:
        # Este método está correto como definimos anteriormente
        # (código completo no meu post anterior)
        pass # Deixando 'pass' aqui para não repetir o código, mas mantenha o seu

    def get_questoes_by_event_id(self, event_id: str) -> List[QuestaoType]:
        """
        Método para carregar todas as questões de um evento.
        (Presumo que você já tenha um método como este ou algo parecido)
        """
        self.logger.info(f"Buscando questões para o evento com ID: {event_id}")
        questoes = []
        conn = None
        try:
            conn = self.db_controller.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM QuestoesBanco WHERE id_evento_fk = ?", (event_id,))
            
            for row in cursor.fetchall():
                print("QUESTAO DO BANCO:", row)  # Veja se o campo está realmente aqui
                questao_dict = dict(row)
                print("DEBUG QUESTAO id:", questao_dict.get("id_questao"), "| id_texto_ref_vinculado:", questao_dict.get("id_texto_ref_vinculado"))
                # Desserializar campos JSON que são esperados como objetos/listas
                for key_json in ['opcoes', 'detalhes_discursiva', 'itens_verdadeiro_falso', 'tags_keywords', 'metadados_questao', 'imagens_enunciado', 'imagens_enunciado_refs', 'textos_referencia_questao']:
                    if key_json in questao_dict and isinstance(questao_dict[key_json], str):
                        try:
                            # Tags e outros podem vir como string JSON
                            questao_dict[key_json] = json.loads(questao_dict[key_json])
                        except json.JSONDecodeError:
                            self.logger.warning(f"Campo '{key_json}' da questão {questao_dict.get('id_questao')} não é um JSON válido. Deixando como string ou None.")
                            questao_dict[key_json] = None # Ou manter como string se for o caso
                    elif key_json in questao_dict and questao_dict[key_json] is None:
                        # Garante que campos que são List/Dict no Pydantic não sejam None
                        if key_json in ['opcoes', 'itens_verdadeiro_falso', 'tags_keywords', 'imagens_enunciado', 'imagens_enunciado_refs', 'textos_referencia_questao']:
                            questao_dict[key_json] = []
                        elif key_json in ['metadados_questao', 'detalhes_discursiva']:
                            questao_dict[key_json] = {}
                
                # Conversões de tipo para Pydantic
                if 'data_criacao' in questao_dict and isinstance(questao_dict['data_criacao'], str):
                    questao_dict['data_criacao'] = parse_iso_to_datetime(questao_dict['data_criacao'])
                if 'data_modificacao' in questao_dict and isinstance(questao_dict['data_modificacao'], str):
                    questao_dict['data_modificacao'] = parse_iso_to_datetime(questao_dict['data_modificacao'])

                # Tratar booleanos
                questao_dict['revisada'] = bool(questao_dict.get('revisada', False))
                questao_dict['anulada'] = bool(questao_dict.get('anulada', False))

                # Converter ENUMs de string para o tipo Enum
                if 'tipo' in questao_dict and questao_dict['tipo'] in [e.value for e in TipoQuestao]:
                    questao_dict['tipo'] = TipoQuestao(questao_dict['tipo'])
                if 'nivel_dificuldade' in questao_dict and questao_dict['nivel_dificuldade'] in [e.value for e in NivelDificuldadeQuestao]:
                    questao_dict['nivel_dificuldade'] = NivelDificuldadeQuestao(questao_dict['nivel_dificuldade'])
                
                # Se 'opcoes' é uma lista de dicionários, precisamos converter para OpcaoMultiplaEscolha
                if 'opcoes' in questao_dict and isinstance(questao_dict['opcoes'], list):
                    questao_dict['opcoes'] = [OpcaoMultiplaEscolha(**opt) for opt in questao_dict['opcoes']]

                questoes.append(QuestaoType(**questao_dict))

            self.logger.info(f"Carregadas {len(questoes)} questões para o evento {event_id}.")
            return questoes
        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao buscar questões para evento {event_id}: {e}", exc_info=True)
            return []
        except Exception as e_general:
            self.logger.error(f"Erro geral ao carregar questões para evento {event_id}: {e_general}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
                print("ERRO AO SALVAR QUESTAO:", e)

    def get_evento_by_id(self, event_id: str) -> Optional[EventoType]:
        self.logger.info(f"Buscando evento com ID: {event_id}")
        conn = None
        try:
            conn = self.db_controller.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Eventos WHERE id_evento = ?", (event_id,))
            evento_row = cursor.fetchone()

            if not evento_row:
                self.logger.warning(f"Evento com ID {event_id} não encontrado.")
                return None

            evento_dict = dict(evento_row)

            # Desserializa os campos JSON, se existirem e forem strings
            for key in ['metadados_evento', 'recursos_evento']: # Adicione outros campos JSON se houver
                if key in evento_dict and isinstance(evento_dict[key], str):
                    try:
                        evento_dict[key] = json.loads(evento_dict[key])
                    except json.JSONDecodeError:
                        self.logger.warning(f"Campo '{key}' do evento {event_id} não é um JSON válido. Deixando como string ou None.")
                        evento_dict[key] = None # Ou manter como string se for o caso

            # Converte timestamps para datetime objects
            if 'data_criacao' in evento_dict and isinstance(evento_dict['data_criacao'], str):
                evento_dict['data_criacao'] = parse_iso_to_datetime(evento_dict['data_criacao'])
            if 'data_modificacao' in evento_dict and isinstance(evento_dict['data_modificacao'], str):
                evento_dict['data_modificacao'] = parse_iso_to_datetime(evento_dict['data_modificacao'])

            # --- CORREÇÃO AQUI ---
            # 1. Popule 'banco_questoes' com as disciplinas únicas (para o ComboBox da UI)
            evento_dict['banco_questoes'] = self._get_unique_disciplinas_from_banco_questoes(event_id)


            # 2. Popule a NOVA CHAVE 'questoes' com a lista completa de QuestaoType
            evento_dict['questoes'] = self.get_questoes_by_event_id(event_id) # Chame sua função para obter as questões
            # --- FIM DA CORREÇÃO ---
            
            # Use o evento_dict modificado para instanciar EventoType
            evento_obj = EventoType(**evento_dict)
            self.logger.info(f"Evento '{evento_obj.nome_evento}' carregado com sucesso.")
            return evento_obj

        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao buscar evento com ID {event_id}: {e}", exc_info=True)
            return None
        except Exception as e_general:
            self.logger.error(f"Erro geral ao carregar evento com ID {event_id}: {e_general}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
    
   
    def get_provas_montadas_por_evento(self, id_evento: str) -> List[ProvaMontadaType]:
        """
        Recupera e monta corretamente todas as provas montadas para um evento.
        """
        self.logger.info(f"Buscando e montando provas para o evento ID: {id_evento}")
        conn = None
        try:
            conn = self.get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql_query = "SELECT * FROM ProvasMontadas WHERE id_evento_fk = ?"
            cursor.execute(sql_query, (id_evento,))
            rows = cursor.fetchall()

            provas_montadas_types = []
            for row in rows:
                try:
                    prova_dict = dict(row)

                    # --- SUA LÓGICA ORIGINAL DE MAPEAMENTO (MANTIDA INTACTA) ---
                    if 'id_evento_fk' in prova_dict:
                        prova_dict['id_evento'] = prova_dict.pop('id_evento_fk')
                    if 'id_cargo_fk' in prova_dict:
                        prova_dict['id_cargo'] = prova_dict.pop('id_cargo_fk')
                    
                    # --- SUA LÓGICA ORIGINAL DE CONFIGURAÇÕES (MANTIDA INTACTA) ---
                    config_data = {}
                    config_json_str = prova_dict.pop('configuracoes_prova', '{}')
                    if config_json_str and isinstance(config_json_str, str):
                        config_data.update(json.loads(config_json_str))
                    # ... (etc) ...
                    prova_dict['configuracoes'] = ConfiguracoesProvaType(**config_data)

                    # --- SEU BLOCO DE PROCESSAMENTO DE JSON, AGORA SEPARADO E CORRIGIDO ---

                    # 1. Processa BLOCOS DE QUESTÕES (Sua lógica original que funcionava para a UI)
                    blocos_json_str = prova_dict.pop('blocos_questoes_json', '[]')
                    blocos_reconstruidos = []
                    if blocos_json_str and isinstance(blocos_json_str, str):
                        try:
                            blocos_data = json.loads(blocos_json_str)
                            for b_data in blocos_data:
                                questoes_data = b_data.pop('questoes', [])
                                questoes_reconstruidas = []
                                if questoes_data:
                                    for q_data in questoes_data:
                                        opcoes_data = q_data.pop('opcoes', [])
                                        if opcoes_data:
                                            q_data['opcoes'] = [OpcaoMultiplaEscolha(**opt) for opt in opcoes_data]
                                        questoes_reconstruidas.append(QuestaoType(**q_data))
                                b_data['questoes'] = questoes_reconstruidas
                                blocos_reconstruidos.append(BlocoQuestoesType(**b_data))
                        except (json.JSONDecodeError, TypeError) as e:
                            self.logger.error(f"Erro ao desserializar blocos_questoes para prova ID {prova_dict.get('id_prova_montada')}: {e}")
                            blocos_reconstruidos = []
                    prova_dict['blocos_questoes'] = blocos_reconstruidos

                    # 2. Desserializa TEXTOS DE REFERÊNCIA (Lógica simples)
                    textos_json_str = prova_dict.pop('textos_referencia_prova_json', '[]')
                    textos_reconstruidos = []
                    if textos_json_str and isinstance(textos_json_str, str):
                        try:
                            textos_data = json.loads(textos_json_str)
                            textos_reconstruidos = [TextoReferenciaType(**t) for t in textos_data]
                        except (json.JSONDecodeError, TypeError) as e:
                            self.logger.error(f"Erro ao desserializar textos de referência para prova ID {prova_dict.get('id_prova_montada')}: {e}")
                            textos_reconstruidos = []
                    prova_dict['textos_referencia_prova'] = textos_reconstruidos
                    
                    # --- FIM DA CORREÇÃO ---

                    # Limpa campos extras (Corrigido para Pydantic)
                    campos_permitidos = ProvaMontadaType.model_fields.keys()
                    chaves_extras = set(prova_dict.keys()) - campos_permitidos
                    for chave in chaves_extras:
                        prova_dict.pop(chave)

                    provas_montadas_types.append(ProvaMontadaType(**prova_dict))

                except Exception as e_parse:
                    prova_id_para_log = dict(row).get('id_prova_montada', 'N/A')
                    self.logger.error(f"Erro ao processar/desserializar dados da prova ID {prova_id_para_log}: {e_parse}", exc_info=True)

            self.logger.info(f"Encontradas e processadas {len(provas_montadas_types)} provas montadas.")
            return provas_montadas_types

        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao buscar provas montadas: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
    
    def update_prova_montada(self, prova_montada: ProvaMontadaType) -> bool:
        """
        Atualiza uma ProvaMontada existente no banco de dados usando um
        gerenciador de contexto ('with') para segurança e simplicidade.
        """
        if not hasattr(prova_montada, 'id_prova_montada') or not prova_montada.id_prova_montada:
            self.logger.error("Tentativa de atualizar ProvaMontada sem um ID válido.")
            return False

        self.logger.info(f"Atualizando ProvaMontada ID: {prova_montada.id_prova_montada} no banco de dados.")
        
        # Prepara todos os dados ANTES de abrir a conexão com o banco
        try:
            # Garante que os objetos dataclass sejam convertidos para dicionário
            configuracoes_dict = dataclasses.asdict(prova_montada.configuracoes) if dataclasses.is_dataclass(prova_montada.configuracoes) else prova_montada.configuracoes
            blocos_questoes_dict = [dataclasses.asdict(b) if dataclasses.is_dataclass(b) else b for b in prova_montada.blocos_questoes]

            configuracoes_json = json.dumps(configuracoes_dict, default=str)
            blocos_questoes_json = json.dumps(blocos_questoes_dict, default=str)
            metadados_json = json.dumps(prova_montada.metadados_prova, default=str)

            update_data = {
                "nome_prova_montada": prova_montada.nome_prova_montada,
                "status_montagem": prova_montada.status_montagem,
                "configuracoes_prova": configuracoes_json,
                "blocos_questoes_json": blocos_questoes_json,
                "metadados_prova": metadados_json,
                # Removido data_modificacao para deixar o TRIGGER do banco de dados cuidar disso
            }

            fields_to_update_str = ", ".join([f"{key} = ?" for key in update_data])
            sql_query = f"UPDATE ProvasMontadas SET {fields_to_update_str} WHERE id_prova_montada = ?"
            values = tuple(update_data.values()) + (prova_montada.id_prova_montada,)
        except Exception as e:
            self.logger.error(f"Erro ao preparar dados para atualização da ProvaMontada ID {prova_montada.id_prova_montada}: {e}", exc_info=True)
            return False

        # A instrução 'with' usa a conexão compartilhada para executar a atualização.
        # É seguro contra 'database is locked' porque a conexão é gerenciada centralmente.
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql_query, values)
            
            self.logger.info(f"ProvaMontada ID: {prova_montada.id_prova_montada} foi atualizada com sucesso.")
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Erro SQLite ao atualizar ProvaMontada ID {prova_montada.id_prova_montada}: {e}", exc_info=True)
            return False