"""guard_tenant_change_requires_reencryption + codigos unicos por cliente

Trava no banco: impede trocar o tenant_id de uma linha sem recifrar as colunas cifradas.
Os valores cifrados são amarrados ao cliente (AAD); um UPDATE direto de tenant_id que mantenha a cifra
antiga deixa a linha ilegível (foi o que aconteceu com o usuário "admin" em 18/11/2026).
A camada ORM (field_crypto) sempre recifra ao trocar o cliente, gerando valores novos, então passa.

Também troca a unicidade GLOBAL dos códigos gerados (identificador de evento/cargo/conteúdo e código curto
da questão) por unicidade POR CLIENTE. Sob RLS, cada cliente só enxerga os próprios códigos; com unicidade
global, dois clientes geravam o mesmo código (ex.: EV001) e a gravação falhava com erro 500, além de revelar
indiretamente a existência de códigos de outro cliente.

Revision ID: a9d4c2e6f0b1
Revises: e7b2d4f8a1c6
Create Date: 2026-11-18 21:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a9d4c2e6f0b1'
down_revision: Union[str, Sequence[str], None] = 'e7b2d4f8a1c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Lista congelada (tabelas com tenant_id e suas colunas cifradas no momento desta revisão).
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
 'users': ['address', 'agencia', 'avatar_url', 'banco', 'birth_date', 'conta_corrente', 'cpf', 'department',
           'email', 'full_name', 'institution', 'notes', 'phone', 'pix_key', 'specialty', 'terms_acceptance',
           'username']}

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION diagpro_exige_recifra_ao_trocar_tenant() RETURNS trigger AS $$
DECLARE
    col text;
    o jsonb := to_jsonb(OLD);
    n jsonb := to_jsonb(NEW);
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
        FOREACH col IN ARRAY TG_ARGV LOOP
            IF o ->> col IS NOT NULL AND o ->> col = n ->> col THEN
                RAISE EXCEPTION 'Troca de tenant em %.% sem recifrar o valor: use a aplicação (ORM), nunca SQL direto.',
                    TG_TABLE_NAME, col USING ERRCODE = 'check_violation';
            END IF;
        END LOOP;
    END IF;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;
"""

# (tabela, coluna, constraint global antiga)
CODIGOS = [
    ("Eventos", "identificador_evento", "Eventos_identificador_evento_key"),
    ("Cargos", "identificador_cargo", "Cargos_identificador_cargo_key"),
    ("QuestoesBanco", "codigo_curto_questao", "QuestoesBanco_codigo_curto_questao_key"),
    ("conteudos", "identificador_conteudo", "conteudos_identificador_conteudo_key"),
]


def upgrade() -> None:
    for table, col, old in CODIGOS:
        op.drop_constraint(old, table, type_="unique")
        op.create_unique_constraint(f"uq_{table.lower()}_tenant_{col}", table, ["tenant_id", col])
    op.execute(FUNCTION_SQL)
    for table, cols in ENCRYPTED_COLUMNS.items():
        args = ", ".join("'" + c + "'" for c in cols)
        op.execute(f'DROP TRIGGER IF EXISTS trg_exige_recifra_tenant ON "{table}"')
        op.execute(
            f'CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON "{table}" '
            f'FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})'
        )


def downgrade() -> None:
    for table, col, old in CODIGOS:
        op.drop_constraint(f"uq_{table.lower()}_tenant_{col}", table, type_="unique")
        op.create_unique_constraint(old, table, [col])
    for table in ENCRYPTED_COLUMNS:
        op.execute(f'DROP TRIGGER IF EXISTS trg_exige_recifra_tenant ON "{table}"')
    op.execute("DROP FUNCTION IF EXISTS diagpro_exige_recifra_ao_trocar_tenant()")
