"""sessões de acesso (lista de acessos ativos, saída remota, alerta de novo acesso)

Uma linha por login concluído (depois do 2FA). O token carrega o id da sessão; sessão encerrada derruba o token
na hora. IP e navegador ficam cifrados em `detalhes`. RLS forçado; tenant nulo = admin geral.

Revision ID: d7f9b1c3e5a7
Revises: c6e8a0b2d4f6
Create Date: 2026-11-20 11:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd7f9b1c3e5a7'
down_revision: Union[str, Sequence[str], None] = 'c6e8a0b2d4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sessoes',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('criada_em', sa.DateTime(), nullable=False),
        sa.Column('ultimo_uso_em', sa.DateTime(), nullable=False),
        sa.Column('encerrada_em', sa.DateTime(), nullable=True),
        sa.Column('motivo_encerramento', sa.String(30), nullable=True),
        sa.Column('detalhes', sa.Text(), nullable=False),  # cifrado: {ip, navegador, sistema}
    )
    op.create_index('ix_sessoes_tenant_id', 'sessoes', ['tenant_id'])
    op.create_index('ix_sessoes_usuario', 'sessoes', ['usuario_id', 'criada_em'])
    op.execute('ALTER TABLE sessoes ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE sessoes FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON sessoes "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    op.execute(
        "CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON sessoes "
        "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('detalhes')"
    )


def downgrade() -> None:
    op.drop_table('sessoes')
