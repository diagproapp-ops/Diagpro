"""financeiro completo: contratos de professores (parcelas, ajustes, documentos) e plataforma (propostas, termos, faturas)

Substitui o primeiro rascunho do financeiro (regras_remuneracao_banca, pagamentos_professores, faturas_bancas —
vazias quando esta migração foi escrita) por:
 - banca x professor: fin_config, fin_contratos, fin_parcelas, fin_ajustes, fin_documentos (escopo 'professor');
 - plataforma x banca: fin_propostas, fin_termos, fin_faturas, fin_documentos (escopo 'plataforma').
planos_banca (catálogo da plataforma) continua.

Todas com RLS forçado por banca e `dados` cifrados; trocar a banca de uma linha exige recifrar (trigger).

Revision ID: f2c4e6a8b0d1
Revises: 1c7d662f9f71
Create Date: 2026-11-21 16:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f2c4e6a8b0d1'
down_revision: Union[str, Sequence[str], None] = '1c7d662f9f71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_ATUAL = "NULLIF(current_setting('app.current_tenant_id', true), '')::integer"


def _rls(tabela: str, cifradas: list[str]) -> None:
    op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_policy ON {tabela} "
               f"USING (tenant_id = {_TENANT_ATUAL}) WITH CHECK (tenant_id = {_TENANT_ATUAL})")
    args = ", ".join(f"'{c}'" for c in cifradas)
    op.execute(f"CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON {tabela} "
               f"FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})")


def _tenant():
    return sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True)


def upgrade() -> None:
    for antiga in ('pagamentos_professores', 'regras_remuneracao_banca', 'faturas_bancas'):
        op.execute(f"DROP TABLE IF EXISTS {antiga} CASCADE")

    op.create_table(
        'fin_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, unique=True, index=True),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_por', sa.Integer(), nullable=True),
    )
    _rls('fin_config', ['dados'])

    op.create_table(
        'fin_contratos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column('professor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('evento_id', sa.String(), nullable=False, index=True),
        sa.Column('numero', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='rascunho'),
        sa.Column('modalidade', sa.String(20), nullable=False, server_default='por_questao'),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('documento_ref', sa.Text(), nullable=True),
        sa.Column('documento_sha256', sa.String(64), nullable=True),
        sa.Column('aceite', sa.Text(), nullable=True),
        sa.Column('codigo_verificacao', sa.String(20), nullable=True, index=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('enviado_em', sa.DateTime(), nullable=True),
        sa.Column('respondido_em', sa.DateTime(), nullable=True),
        sa.Column('encerrado_em', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('tenant_id', 'numero', name='uq_fin_contratos_tenant_numero'),
    )
    _rls('fin_contratos', ['dados', 'documento_ref', 'aceite'])

    op.create_table(
        'fin_parcelas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column('contrato_id', sa.Integer(), sa.ForeignKey('fin_contratos.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('gatilho', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='prevista'),
        sa.Column('data_prevista', sa.Date(), nullable=True),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('liberada_em', sa.DateTime(), nullable=True),
        sa.Column('paga_em', sa.DateTime(), nullable=True),
        sa.Column('confirmada_em', sa.DateTime(), nullable=True),
    )
    _rls('fin_parcelas', ['dados'])

    op.create_table(
        'fin_ajustes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column('contrato_id', sa.Integer(), sa.ForeignKey('fin_contratos.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('parcela_id', sa.Integer(), sa.ForeignKey('fin_parcelas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
    )
    _rls('fin_ajustes', ['dados'])

    op.create_table(
        'fin_documentos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column('escopo', sa.String(20), nullable=False),
        sa.Column('tipo', sa.String(30), nullable=False),
        sa.Column('contrato_id', sa.Integer(), sa.ForeignKey('fin_contratos.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('parcela_id', sa.Integer(), sa.ForeignKey('fin_parcelas.id', ondelete='SET NULL'), nullable=True),
        sa.Column('professor_id', sa.Integer(), nullable=True),
        sa.Column('referencia_id', sa.Integer(), nullable=True),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('arquivo_ref', sa.Text(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('enviado_por', sa.Integer(), nullable=True),
        sa.Column('enviado_em', sa.DateTime(), nullable=False),
    )
    _rls('fin_documentos', ['dados', 'arquivo_ref'])

    op.create_table(
        'fin_propostas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column('numero', sa.String(30), nullable=False),
        sa.Column('versao', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(20), nullable=False, server_default='enviada'),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('validade', sa.Date(), nullable=True),
        sa.Column('documento_ref', sa.Text(), nullable=True),
        sa.Column('aceite', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('respondido_em', sa.DateTime(), nullable=True),
    )
    _rls('fin_propostas', ['dados', 'documento_ref', 'aceite'])

    op.create_table(
        'fin_termos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendente'),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('documento_ref', sa.Text(), nullable=False),
        sa.Column('documento_sha256', sa.String(64), nullable=False),
        sa.Column('aceite', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('respondido_em', sa.DateTime(), nullable=True),
    )
    _rls('fin_termos', ['dados', 'documento_ref', 'aceite'])

    op.create_table(
        'fin_faturas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column('numero', sa.String(30), nullable=False),
        sa.Column('competencia', sa.String(7), nullable=False),
        sa.Column('vencimento', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='aberta'),
        sa.Column('dados', sa.Text(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('informada_em', sa.DateTime(), nullable=True),
        sa.Column('paga_em', sa.DateTime(), nullable=True),
    )
    _rls('fin_faturas', ['dados'])


def downgrade() -> None:
    for t in ('fin_faturas', 'fin_termos', 'fin_propostas', 'fin_documentos', 'fin_ajustes', 'fin_parcelas',
              'fin_contratos', 'fin_config'):
        op.drop_table(t)
