# DiagPro/create_db.py (VERSÃO FINAL)
import os
import sys
import logging
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from core.models import Base, Events # Importamos os modelos que precisamos popular
    logger.info("SUCESSO: Modelos importados de core.models.")
except Exception as e:
    logger.error(f"ERRO ao importar modelos: {e}")
    sys.exit(1)

def create_and_populate_database():
    try:
        db_name = 'diagprooff.db'
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)
        logger.info(f"Conectando ao banco de dados em: {db_path}")

        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("Criando/Verificando todas as tabelas a partir de core.models...")
        Base.metadata.create_all(engine)
        logger.info("SUCESSO! Tabelas criadas/verificadas.")

        # --- Popular a tabela de eventos a partir do JSON ---
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events_data.json')
        if os.path.exists(json_path):
            logger.info(f"Populando tabela 'events' a partir de {json_path}...")
            with open(json_path, 'r', encoding='utf-8') as f:
                events_data = json.load(f)

            for event_item in events_data:
                exists = session.query(Events).filter_by(id=event_item['id']).first()
                if not exists:
                    new_event = Events(
                        id=event_item['id'],
                        nome_evento=event_item.get('nome_evento'),
                        data_inicio=event_item.get('data_inicio'),
                        data_fim=event_item.get('data_fim'),
                        status=event_item.get('status')
                    )
                    session.add(new_event)
            session.commit()
            logger.info("Eventos inseridos/atualizados com sucesso.")

        session.close()
        logger.info("--- SUCESSO! Base de dados pronta! ---")

    except Exception as e:
        logger.error(f"Ocorreu um erro: {e}", exc_info=True)
        if 'session' in locals() and session.is_active:
            session.rollback()
            session.close()

if __name__ == "__main__":
    create_and_populate_database()