"""histórico de versões das questões

Uma linha por versão salva (criação, edição, revisão): cópia completa da questão, cifrada. Permite ver quem
mudou o quê e trazer de volta uma versão antiga. RLS forçado por banca.

Revision ID: e8a0c2d4f6b8
Revises: d7f9b1c3e5a7
Create Date: 2026-11-20 13:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e8a0c2d4f6b8'
down_revision: Union[str, Sequence[str], None] = 'd7f9b1c3e5a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'versoes_questao',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('id_questao_fk', sa.String(), sa.ForeignKey('QuestoesBanco.id_questao', ondelete='CASCADE'), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('criada_em', sa.DateTime(), nullable=False),
        sa.Column('motivo', sa.String(30), nullable=False),  # criada | editada | revisada | anterior
        sa.Column('autor', sa.Text(), nullable=True),       # cifrado
        sa.Column('snapshot', sa.Text(), nullable=False),   # cifrado: questão completa
        sa.UniqueConstraint('id_questao_fk', 'versao', name='uq_versoes_questao_versao'),
    )
    op.create_index('ix_versoes_questao_tenant_id', 'versoes_questao', ['tenant_id'])
    op.create_index('ix_versoes_questao_questao', 'versoes_questao', ['id_questao_fk'])
    op.execute('ALTER TABLE versoes_questao ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE versoes_questao FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON versoes_questao "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    op.execute(
        "CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON versoes_questao "
        "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('autor', 'snapshot')"
    )


def downgrade() -> None:
    op.drop_table('versoes_questao')
