"""entregas seguras de pacotes de prova (link com código, validade, limite de downloads)

O ZIP (já protegido pela senha do evento) fica guardado cifrado por banca até vencer, esgotar os downloads ou
ser revogado; depois o arquivo é apagado. O código de acesso só existe como hash. RLS forçado.

Revision ID: a1c3e5f7b9d1
Revises: f9b1d3e5a7c9
Create Date: 2026-11-20 17:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a1c3e5f7b9d1'
down_revision: Union[str, Sequence[str], None] = 'f9b1d3e5a7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'entregas',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('evento_id', sa.String(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('expira_em', sa.DateTime(), nullable=False),
        sa.Column('max_downloads', sa.Integer(), nullable=False),
        sa.Column('downloads', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('falhas_codigo', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('encerrada_em', sa.DateTime(), nullable=True),
        sa.Column('motivo_encerramento', sa.String(30), nullable=True),
        sa.Column('codigo_hash', sa.String(100), nullable=False),
        sa.Column('arquivo', sa.Text(), nullable=True),    # cifrado: referência do arquivo guardado
        sa.Column('detalhes', sa.Text(), nullable=False),  # cifrado: nome, destinatário, cargos, registro de downloads
    )
    op.create_index('ix_entregas_tenant_id', 'entregas', ['tenant_id'])
    op.create_index('ix_entregas_evento', 'entregas', ['evento_id'])
    op.execute('ALTER TABLE entregas ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE entregas FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON entregas "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    op.execute(
        "CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON entregas "
        "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('arquivo', 'detalhes')"
    )


def downgrade() -> None:
    op.drop_table('entregas')
