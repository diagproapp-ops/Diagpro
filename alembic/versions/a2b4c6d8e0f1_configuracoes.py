"""configurações da plataforma e de cada banca

Uma linha por escopo: tenant_id nulo = plataforma (só a role de plataforma enxerga); tenant_id = banca
(RLS forçado, igual às demais tabelas). Conteúdo cifrado; entra na trava de troca de tenant.

Revision ID: a2b4c6d8e0f1
Revises: f1a7c3e5b9d2
Create Date: 2026-11-19 22:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a2b4c6d8e0f1'
down_revision: Union[str, Sequence[str], None] = 'f1a7c3e5b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'configuracoes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_por', sa.Text(), nullable=True),
    )
    op.create_index('ix_configuracoes_tenant_id', 'configuracoes', ['tenant_id'])
    # uma única linha por banca e uma única da plataforma (tenant nulo)
    op.execute('CREATE UNIQUE INDEX uq_configuracoes_escopo ON configuracoes ((COALESCE(tenant_id, 0)))')
    op.execute('ALTER TABLE configuracoes ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE configuracoes FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON configuracoes "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    op.execute(
        "CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON configuracoes "
        "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('dados', 'atualizado_por')"
    )


def downgrade() -> None:
    op.drop_table('configuracoes')
