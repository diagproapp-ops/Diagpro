"""recursos dos candidatos e decisões por questão

`recursos`: um pedido (anulação/alteração) sobre uma questão de um caderno, com protocolo e argumentação (cifrados);
nenhum outro dado do candidato é guardado. `decisoes_recurso`: a decisão da banca por questão (ou item de
Certo/Errado), com justificativa publicável. A prova montada nunca é alterada: o gabarito definitivo é calculado.

Revision ID: c3e5a7c9e1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-11-20 21:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c3e5a7c9e1f3'
down_revision: Union[str, Sequence[str], None] = 'b2d4f6a8c0e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLITICA = ("CREATE POLICY tenant_isolation_policy ON {t} "
             "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
             "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)")


def _rls(tabela: str, cifradas: list[str]) -> None:
    op.execute(f'ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY')
    op.execute(_POLITICA.format(t=tabela))
    args = ", ".join("'" + c + "'" for c in cifradas)
    op.execute(f"CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON {tabela} "
               f"FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})")


def upgrade() -> None:
    op.create_table(
        'recursos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('evento_id', sa.String(), nullable=False),
        sa.Column('cargo_id', sa.String(), nullable=False),
        sa.Column('tipo_prova', sa.String(30), nullable=False),
        sa.Column('numero_questao', sa.Integer(), nullable=False),
        sa.Column('id_questao', sa.String(), nullable=False),
        sa.Column('item', sa.Integer(), nullable=True),           # item de Certo/Errado
        sa.Column('pedido', sa.String(20), nullable=False),       # anulacao | alteracao | outro
        sa.Column('status', sa.String(20), nullable=False),       # pendente | deferido | indeferido
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('protocolo', sa.Text(), nullable=True),         # cifrado
        sa.Column('argumentacao', sa.Text(), nullable=True),      # cifrado
        sa.Column('parecer', sa.Text(), nullable=True),           # cifrado: parecer técnico (elaborador/revisor)
        sa.Column('parecer_por', sa.Integer(), nullable=True),
    )
    op.create_index('ix_recursos_tenant_id', 'recursos', ['tenant_id'])
    op.create_index('ix_recursos_evento_questao', 'recursos', ['evento_id', 'id_questao'])
    _rls('recursos', ['protocolo', 'argumentacao', 'parecer'])

    op.create_table(
        'decisoes_recurso',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('evento_id', sa.String(), nullable=False),
        sa.Column('id_questao', sa.String(), nullable=False),
        sa.Column('item', sa.Integer(), nullable=True),
        sa.Column('decisao', sa.String(20), nullable=False),      # manter | anular | alterar
        sa.Column('nova_correta', sa.String(5), nullable=True),   # letra do banco (A-E) ou C/E
        sa.Column('decidido_em', sa.DateTime(), nullable=False),
        sa.Column('decidido_por', sa.Integer(), nullable=True),
        sa.Column('justificativa', sa.Text(), nullable=True),     # cifrado: texto publicável
        sa.UniqueConstraint('evento_id', 'id_questao', 'item', name='uq_decisao_recurso'),
    )
    op.create_index('ix_decisoes_recurso_tenant_id', 'decisoes_recurso', ['tenant_id'])
    _rls('decisoes_recurso', ['justificativa'])


def downgrade() -> None:
    op.drop_table('decisoes_recurso')
    op.drop_table('recursos')
