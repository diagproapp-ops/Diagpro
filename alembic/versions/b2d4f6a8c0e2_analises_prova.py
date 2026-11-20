"""análises estatísticas pós-prova (só resultados agregados; nenhum dado de candidato)

Revision ID: b2d4f6a8c0e2
Revises: a1c3e5f7b9d1
Create Date: 2026-11-20 19:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b2d4f6a8c0e2'
down_revision: Union[str, Sequence[str], None] = 'a1c3e5f7b9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'analises_prova',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('evento_id', sa.String(), nullable=False),
        sa.Column('cargo_id', sa.String(), nullable=False),
        sa.Column('criada_em', sa.DateTime(), nullable=False),
        sa.Column('criada_por', sa.Integer(), nullable=True),
        sa.Column('n_candidatos', sa.Integer(), nullable=False),
        sa.Column('resultado', sa.Text(), nullable=False),  # cifrado: estatísticas agregadas por questão
    )
    op.create_index('ix_analises_prova_tenant_id', 'analises_prova', ['tenant_id'])
    op.create_index('ix_analises_prova_cargo', 'analises_prova', ['evento_id', 'cargo_id'])
    op.execute('ALTER TABLE analises_prova ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE analises_prova FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON analises_prova "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    op.execute(
        "CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON analises_prova "
        "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('resultado')"
    )


def downgrade() -> None:
    op.drop_table('analises_prova')
