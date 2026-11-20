"""registro das operações de LGPD (exportação de dados, anonimização, aceite de termos)

Prestação de contas da banca: quem pediu o quê, sobre quem e quando. Detalhes cifrados; RLS forçado.
tenant nulo = operação do admin geral sem banca.

Revision ID: f9b1d3e5a7c9
Revises: e8a0c2d4f6b8
Create Date: 2026-11-20 15:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f9b1d3e5a7c9'
down_revision: Union[str, Sequence[str], None] = 'e8a0c2d4f6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'registros_lgpd',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('titular_id', sa.Integer(), nullable=True),   # sem FK: o registro sobrevive à anonimização
        sa.Column('autor_id', sa.Integer(), nullable=True),
        sa.Column('acao', sa.String(30), nullable=False),        # exportacao | anonimizacao | aceite_termos | limpeza
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('detalhes', sa.Text(), nullable=True),         # cifrado
    )
    op.create_index('ix_registros_lgpd_tenant_id', 'registros_lgpd', ['tenant_id'])
    op.execute('ALTER TABLE registros_lgpd ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE registros_lgpd FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON registros_lgpd "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    op.execute(
        "CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON registros_lgpd "
        "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('detalhes')"
    )


def downgrade() -> None:
    op.drop_table('registros_lgpd')
