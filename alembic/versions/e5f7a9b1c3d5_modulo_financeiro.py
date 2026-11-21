"""módulo financeiro: remuneração de professores e planos/faturas de bancas

Revision ID: e5f7a9b1c3d5
Revises: d4f6a8c0e2b4
Create Date: 2026-11-21 00:35:00
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e5f7a9b1c3d5'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8c0e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_ATUAL = "NULLIF(current_setting('app.current_tenant_id', true), '')::integer"
_POLITICA = (
    "CREATE POLICY tenant_isolation_policy ON {t} "
    f"USING (tenant_id = {_TENANT_ATUAL}) WITH CHECK (tenant_id = {_TENANT_ATUAL})"
)


def _rls(tabela: str, cifradas: list[str]) -> None:
    op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(t=tabela))
    if cifradas:
        args = ", ".join("'" + c + "'" for c in cifradas)
        op.execute(
            f"CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON {tabela} "
            f"FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})"
        )


def _grant_roles(tabela: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'diagpro_runtime') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tabela} TO diagpro_runtime;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'diagpro_platform') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tabela} TO diagpro_platform;
            END IF;
        END $$;
        """
    )


def _grant_sequences() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'diagpro_runtime') THEN
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO diagpro_runtime;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'diagpro_platform') THEN
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO diagpro_platform;
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        'regras_remuneracao_banca',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, unique=True),
        sa.Column('valor_multipla_escolha', sa.Float(), nullable=False, server_default='0'),
        sa.Column('valor_item_certo_errado', sa.Float(), nullable=False, server_default='0'),
        sa.Column('valor_questao_certo_errado_base', sa.Float(), nullable=False, server_default='0'),
        sa.Column('valor_discursiva', sa.Float(), nullable=False, server_default='0'),
        sa.Column('valor_subjetiva', sa.Float(), nullable=False, server_default='0'),
        sa.Column('somente_aprovadas', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_por', sa.Integer(), nullable=True),
    )
    op.create_index('ix_regras_remuneracao_banca_tenant_id', 'regras_remuneracao_banca', ['tenant_id'])
    _rls('regras_remuneracao_banca', ['observacoes'])
    _grant_roles('regras_remuneracao_banca')

    op.create_table(
        'pagamentos_professores',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('professor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evento_id', sa.String(), nullable=True),
        sa.Column('competencia', sa.String(20), nullable=False),
        sa.Column('qtd_multipla_escolha', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('qtd_certo_errado', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('qtd_itens_vf', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('qtd_discursiva', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('qtd_subjetiva', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valor_calculado', sa.Float(), nullable=False, server_default='0'),
        sa.Column('valor_pago', sa.Float(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendente'),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('pago_em', sa.DateTime(), nullable=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
    )
    op.create_index('ix_pagamentos_professores_tenant_id', 'pagamentos_professores', ['tenant_id'])
    op.create_index('ix_pagamentos_professores_professor_id', 'pagamentos_professores', ['professor_id'])
    op.create_index('ix_pagamentos_professores_evento_id', 'pagamentos_professores', ['evento_id'])
    _rls('pagamentos_professores', ['observacoes'])
    _grant_roles('pagamentos_professores')

    op.create_table(
        'planos_banca',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('codigo', sa.String(40), nullable=False, unique=True),
        sa.Column('nome', sa.String(100), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('valor_mensal', sa.Float(), nullable=False, server_default='0'),
        sa.Column('valor_anual', sa.Float(), nullable=False, server_default='0'),
        sa.Column('limite_eventos', sa.Integer(), nullable=True),
        sa.Column('limite_usuarios', sa.Integer(), nullable=True),
        sa.Column('limite_questoes', sa.Integer(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
    )
    _grant_roles('planos_banca')

    op.create_table(
        'faturas_bancas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('plano_id', sa.Integer(), sa.ForeignKey('planos_banca.id', ondelete='SET NULL'), nullable=True),
        sa.Column('plano_nome', sa.String(100), nullable=False),
        sa.Column('competencia', sa.String(20), nullable=False),
        sa.Column('vencimento', sa.Date(), nullable=False),
        sa.Column('valor', sa.Float(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendente'),
        sa.Column('forma_pagamento', sa.String(40), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('pago_em', sa.DateTime(), nullable=True),
        sa.Column('observacoes', sa.Text(), nullable=True),
    )
    op.create_index('ix_faturas_bancas_tenant_id', 'faturas_bancas', ['tenant_id'])
    _rls('faturas_bancas', ['observacoes'])
    _grant_roles('faturas_bancas')
    _grant_sequences()

    agora = datetime.utcnow()
    planos_tbl = sa.table(
        'planos_banca',
        sa.column('codigo', sa.String),
        sa.column('nome', sa.String),
        sa.column('descricao', sa.Text),
        sa.column('valor_mensal', sa.Float),
        sa.column('valor_anual', sa.Float),
        sa.column('limite_eventos', sa.Integer),
        sa.column('limite_usuarios', sa.Integer),
        sa.column('limite_questoes', sa.Integer),
        sa.column('ativo', sa.Boolean),
        sa.column('criado_em', sa.DateTime),
    )
    op.bulk_insert(
        planos_tbl,
        [
            {
                'codigo': 'basico',
                'nome': 'Plano Básico',
                'descricao': 'Ideal para bancas em início de operação com concursos regionais.',
                'valor_mensal': 490.0,
                'valor_anual': 4900.0,
                'limite_eventos': 5,
                'limite_usuarios': 25,
                'limite_questoes': 3000,
                'ativo': True,
                'criado_em': agora,
            },
            {
                'codigo': 'profissional',
                'nome': 'Plano Profissional',
                'descricao': 'Para bancas com múltiplos certames simultâneos, variações e IA integrada.',
                'valor_mensal': 1290.0,
                'valor_anual': 12900.0,
                'limite_eventos': 25,
                'limite_usuarios': 120,
                'limite_questoes': 25000,
                'ativo': True,
                'criado_em': agora,
            },
            {
                'codigo': 'enterprise',
                'nome': 'Plano Enterprise',
                'descricao': 'Operação estadual/nacional sem limites de eventos, equipe ou banco de questões.',
                'valor_mensal': 2990.0,
                'valor_anual': 29900.0,
                'limite_eventos': None,
                'limite_usuarios': None,
                'limite_questoes': None,
                'ativo': True,
                'criado_em': agora,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table('faturas_bancas')
    op.drop_table('planos_banca')
    op.drop_table('pagamentos_professores')
    op.drop_table('regras_remuneracao_banca')
