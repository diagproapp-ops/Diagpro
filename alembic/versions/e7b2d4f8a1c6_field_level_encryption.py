"""field_level_encryption

Prepara o schema para a cifragem de campos (backend/app/field_crypto.py):
- converte 122 colunas sensíveis para TEXT (passam a guardar e1.<versão>.<AES-256-GCM>);
- cria as colunas de índice cego (HMAC-SHA256) usadas em buscas exatas e unicidade;
- troca os UNIQUE de users(username), users(email) e banco_frases(categoria, texto_frase) por UNIQUE
  sobre os índices cegos (o valor cifrado é aleatório e não serve para unicidade).

Os DADOS são convertidos por scripts/reencrypt_fields.py, na sequência desta revisão.
Rollback: restaurar o backup cifrado feito antes da migração (ver README). O downgrade de schema
só é seguro com os dados ainda em texto claro, por isso ele recusa rodar se houver valores cifrados.

Revision ID: e7b2d4f8a1c6
Revises: c3f1a9d2b7e4
Create Date: 2026-11-18 21:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e7b2d4f8a1c6'
down_revision: Union[str, Sequence[str], None] = 'c3f1a9d2b7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Lista congelada no momento desta revisão (não importar do código da aplicação).
ENCRYPTED_COLUMNS = {'Cargos': ['cover_pdf_paths', 'letterhead_pdf_path', 'nivel', 'nome_cargo', 'requisitos', 'turno'],
 'DetalhesQuestaoDiscursiva': ['palavras_chave_resposta', 'resposta_esperada_texto',
                               'texto_subjetivo_nota_maxima', 'texto_subjetivo_orientacao'],
 'Disciplinas': ['descricao', 'nome_disciplina'],
 'DisciplinasDaProva': ['nome_disciplina_na_prova', 'observacoes'],
 'Eventos': ['local_prova', 'nome_evento', 'numero_edital', 'observacoes', 'senha_evento_cripto'],
 'HistoricoRevisaoQuestao': ['dados_revisao', 'observacao_revisor', 'usuario_revisor'],
 'ItensVerdadeiroFalso': ['afirmacao', 'feedback_item', 'valor_correto'],
 'OpcoesQuestao': ['correta', 'feedback_opcao', 'imagem_path_opcao', 'texto_opcao', 'texto_opcao_formatado'],
 'ProvasMontadas': ['blocos_questoes', 'metadados_prova', 'nome_prova_montada', 'responsavel_montagem',
                    'textos_referencia_prova_json', 'titulo_prova'],
 'QuestoesBanco': ['autor_elaborador', 'caminho_imagem_justificativa', 'caminho_imagem_relativo',
                   'conteudo_nome', 'disciplina_banco', 'enunciado', 'enunciado_formatado',
                   'feedback_geral_questao', 'fonte_questao', 'gabarito_definitivo', 'gabarito_preliminar',
                   'hash_conteudo_questao', 'imagens_enunciado', 'imagens_enunciado_refs',
                   'indicacao_conteudo', 'justificativa_anulacao', 'justificativa_anulacao_recurso',
                   'justificativa_anulacao_recurso_formatado', 'justificativa_questao', 'metadados_questao',
                   'nivel_dificuldade', 'numero_questao_original_docx', 'observacao_revisor',
                   'resposta_correta', 'tags_keywords', 'texto_referencia_direto', 'texto_referencia_vinculo',
                   'textos_referencia_questao'],
 'TextosReferenciaGeral': ['caminho_imagem_relativo', 'conteudo', 'conteudo_formatado', 'descricao_imagem',
                           'fonte_imagem', 'legenda_texto', 'licenca_imagem', 'metadados_texto_ref',
                           'observacoes', 'questoes_vinculo', 'tags_imagem', 'titulo'],
 'audit_log_geracao': ['cargo', 'evento', 'frases', 'ip', 'parametros', 'seed', 'user_agent', 'usuario'],
 'banco_frases': ['categoria', 'texto_frase'],
 'company_data': ['company_address', 'company_cnpj', 'company_email', 'company_logo_path', 'company_name',
                  'company_phone', 'company_website'],
 'conteudos': ['area_conhecimento', 'descricao', 'disciplina', 'metadados', 'nivel', 'nome_conteudo',
               'turno'],
 'tenants': ['domain', 'name', 'responsible_email', 'responsible_name', 'responsible_phone'],
 'users': ['address', 'agencia', 'avatar_url', 'banco', 'birth_date', 'conta_corrente', 'cpf', 'department',
           'email', 'full_name', 'institution', 'notes', 'phone', 'pix_key', 'specialty', 'terms_acceptance',
           'username']}

BLIND_INDEX_COLUMNS = {'Disciplinas': ['nome_disciplina_bidx'],
 'audit_log_geracao': ['cargo_bidx', 'evento_bidx', 'usuario_bidx'],
 'banco_frases': ['categoria_bidx', 'frase_bidx'],
 'tenants': ['domain_bidx', 'name_bidx'],
 'users': ['email_bidx', 'full_name_bidx', 'username_bidx']}

# Tipos originais para o downgrade (somente os que não eram texto)
ORIGINAL_NON_TEXT = {
    ("Cargos", "cover_pdf_paths"): "JSON",
    ("conteudos", "metadados"): "JSON",
    ("ProvasMontadas", "blocos_questoes"): "JSON",
    ("ProvasMontadas", "metadados_prova"): "JSON",
    ("OpcoesQuestao", "correta"): "BOOLEAN",
    ("ItensVerdadeiroFalso", "valor_correto"): "BOOLEAN",
}


def upgrade() -> None:
    for table, cols in ENCRYPTED_COLUMNS.items():
        for col in cols:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TEXT USING "{col}"::text')
    for table, cols in BLIND_INDEX_COLUMNS.items():
        for col in cols:
            op.add_column(table, sa.Column(col, sa.String(64), nullable=True))
            op.create_index(f"ix_{table.lower()}_{col}", table, [col])
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_unique_constraint("uq_users_username_bidx", "users", ["username_bidx"])
    op.create_unique_constraint("uq_users_email_bidx", "users", ["email_bidx"])
    op.drop_constraint("_tenant_categoria_texto_frase_uc", "banco_frases", type_="unique")
    op.create_unique_constraint("_tenant_frase_bidx_uc", "banco_frases", ["tenant_id", "frase_bidx"])


def downgrade() -> None:
    conn = op.get_bind()
    for table, cols in ENCRYPTED_COLUMNS.items():
        for col in cols:
            n = conn.execute(sa.text(f"SELECT count(*) FROM \"{table}\" WHERE \"{col}\" LIKE 'e1.%'")).scalar()
            if n:
                raise RuntimeError(
                    f"{table}.{col} contém {n} valores cifrados: restaure o backup anterior à fase 1b "
                    "em vez de fazer downgrade de schema."
                )
    op.drop_constraint("_tenant_frase_bidx_uc", "banco_frases", type_="unique")
    op.create_unique_constraint("_tenant_categoria_texto_frase_uc", "banco_frases", ["tenant_id", "categoria", "texto_frase"])
    op.drop_constraint("uq_users_email_bidx", "users", type_="unique")
    op.drop_constraint("uq_users_username_bidx", "users", type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.create_unique_constraint("users_username_key", "users", ["username"])
    for table, cols in BLIND_INDEX_COLUMNS.items():
        for col in cols:
            op.drop_index(f"ix_{table.lower()}_{col}", table_name=table)
            op.drop_column(table, col)
    for (table, col), typ in ORIGINAL_NON_TEXT.items():
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE {typ} USING "{col}"::{typ.lower()}')
