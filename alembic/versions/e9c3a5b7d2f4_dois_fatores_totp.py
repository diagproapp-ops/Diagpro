"""2FA (TOTP) obrigatório para todos os usuários

Segredo do autenticador e códigos de recuperação (HMAC) ficam cifrados por cliente; as duas colunas cifradas
entram na trava que impede trocar o cliente da linha sem recifrar.

Revision ID: e9c3a5b7d2f4
Revises: d8b2f4a6c1e3
Create Date: 2026-11-19 18:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e9c3a5b7d2f4'
down_revision: Union[str, Sequence[str], None] = 'd8b2f4a6c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELA = "users"
CIFRADAS_ANTES = ['address', 'agencia', 'avatar_url', 'banco', 'birth_date', 'conta_corrente', 'cpf', 'department',
                  'email', 'full_name', 'institution', 'notes', 'phone', 'pix_key', 'specialty', 'terms_acceptance',
                  'username']
CIFRADAS_DEPOIS = CIFRADAS_ANTES + ['totp_secret', 'codigos_recuperacao']


def _trava(colunas: list[str]) -> None:
    args = ", ".join("'" + c + "'" for c in colunas)
    op.execute(f'DROP TRIGGER IF EXISTS trg_exige_recifra_tenant ON "{TABELA}"')
    op.execute(
        f'CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON "{TABELA}" '
        f'FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})'
    )


def upgrade() -> None:
    op.add_column(TABELA, sa.Column('totp_secret', sa.Text(), nullable=True))
    op.add_column(TABELA, sa.Column('totp_ativo', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column(TABELA, sa.Column('totp_ultimo_passo', sa.Integer(), nullable=True))
    op.add_column(TABELA, sa.Column('codigos_recuperacao', sa.Text(), nullable=True))
    _trava(CIFRADAS_DEPOIS)


def downgrade() -> None:
    _trava(CIFRADAS_ANTES)
    for col in ('codigos_recuperacao', 'totp_ultimo_passo', 'totp_ativo', 'totp_secret'):
        op.drop_column(TABELA, col)
