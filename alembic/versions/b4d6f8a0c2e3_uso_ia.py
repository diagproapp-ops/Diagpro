"""registro de uso do assistente de IA

Uma linha por chamada à IA: quem, quando, quantos tokens e se deu certo. O TEXTO enviado ou recebido
NUNCA é gravado. Recurso/provedor/modelo/erro ficam cifrados em `detalhes`. RLS forçado por banca;
tenant nulo = admin geral na visão global (só a role de plataforma enxerga).

Revision ID: b4d6f8a0c2e3
Revises: a2b4c6d8e0f1
Create Date: 2026-11-19 23:30:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b4d6f8a0c2e3'
down_revision: Union[str, Sequence[str], None] = 'a2b4c6d8e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'uso_ia',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('tokens_entrada', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_saida', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sucesso', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('detalhes', sa.Text(), nullable=False),
    )
    op.create_index('ix_uso_ia_tenant_id', 'uso_ia', ['tenant_id'])
    op.create_index('ix_uso_ia_usuario_dia', 'uso_ia', ['usuario_id', 'criado_em'])
    op.execute('ALTER TABLE uso_ia ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE uso_ia FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON uso_ia "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    op.execute(
        "CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON uso_ia "
        "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('detalhes')"
    )


def downgrade() -> None:
    op.drop_table('uso_ia')
