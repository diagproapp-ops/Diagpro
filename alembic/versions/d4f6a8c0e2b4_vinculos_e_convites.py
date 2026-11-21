"""vínculos com outras bancas e convites por link

`vinculos_banca`: professores e revisores atendem várias bancas com UMA conta. A banca de origem
(users.tenant_id) continua sendo o próprio cadastro; cada outra banca tem uma linha aqui, com função e
aprovação próprias. A banca vê a identidade de quem está vinculado a ela (política extra de SELECT em
users) mas só a banca de origem altera os dados da pessoa (a política de escrita não muda).

`convites`: link de uso único (só o hash do token é guardado) para a pessoa se cadastrar com os próprios
dados, aceitar o vínculo com outra banca ou criar uma nova senha. E-mail e nome cifrados.

Nenhum dado existente é alterado.

Revision ID: d4f6a8c0e2b4
Revises: c3e5a7c9e1f3
Create Date: 2026-11-20 23:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd4f6a8c0e2b4'
down_revision: Union[str, Sequence[str], None] = 'c3e5a7c9e1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_ATUAL = "NULLIF(current_setting('app.current_tenant_id', true), '')::integer"
_POLITICA = ("CREATE POLICY tenant_isolation_policy ON {t} "
             f"USING (tenant_id = {_TENANT_ATUAL}) WITH CHECK (tenant_id = {_TENANT_ATUAL})")


def _rls(tabela: str) -> None:
    op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY")
    op.execute(_POLITICA.format(t=tabela))


def upgrade() -> None:
    op.create_table(
        'vinculos_banca',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pendente'),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('convidado_por', sa.Integer(), nullable=True),
        sa.Column('aprovado_por', sa.Integer(), nullable=True),
        sa.Column('aprovado_em', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_vinculos_banca_tenant_user'),
    )
    op.create_index('ix_vinculos_banca_tenant_id', 'vinculos_banca', ['tenant_id'])
    op.create_index('ix_vinculos_banca_user_id', 'vinculos_banca', ['user_id'])
    _rls('vinculos_banca')

    op.create_table(
        'convites',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('tipo', sa.String(20), nullable=False, server_default='cadastro'),
        sa.Column('email', sa.Text(), nullable=False),   # cifrado
        sa.Column('nome', sa.Text(), nullable=True),     # cifrado
        sa.Column('role', sa.String(30), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('expira_em', sa.DateTime(), nullable=False),
        sa.Column('usado_em', sa.DateTime(), nullable=True),
        sa.Column('cancelado_em', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_convites_tenant_id', 'convites', ['tenant_id'])
    _rls('convites')
    op.execute("CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON convites "
               "FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant('email', 'nome')")

    # A banca LÊ a identidade de quem tem vínculo com ela (nome, foto, e-mail). Só SELECT: alterar os dados
    # continua restrito à banca de origem pela tenant_isolation_policy (políticas permissivas somam por comando).
    op.execute(
        "CREATE POLICY membros_da_banca ON users FOR SELECT USING (EXISTS ("
        "SELECT 1 FROM vinculos_banca v WHERE v.user_id = users.id "
        f"AND v.tenant_id = {_TENANT_ATUAL}))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS membros_da_banca ON users")
    op.drop_table('convites')
    op.drop_table('vinculos_banca')
