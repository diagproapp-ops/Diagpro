"""política de senha: validade, troca obrigatória e histórico

Para quem já existe, a validade conta a partir de agora (senha_alterada_em = agora). O histórico (bcrypt das
últimas senhas) é cifrado e entra na trava de troca de tenant.

Revision ID: f1a7c3e5b9d2
Revises: e9c3a5b7d2f4
Create Date: 2026-11-19 20:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f1a7c3e5b9d2'
down_revision: Union[str, Sequence[str], None] = 'e9c3a5b7d2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELA = "users"
CIFRADAS_ANTES = ['address', 'agencia', 'avatar_url', 'banco', 'birth_date', 'conta_corrente', 'cpf', 'department',
                  'email', 'full_name', 'institution', 'notes', 'phone', 'pix_key', 'specialty', 'terms_acceptance',
                  'username', 'totp_secret', 'codigos_recuperacao']
CIFRADAS_DEPOIS = CIFRADAS_ANTES + ['senha_historico']


def _trava(colunas: list[str]) -> None:
    args = ", ".join("'" + c + "'" for c in colunas)
    op.execute(f'DROP TRIGGER IF EXISTS trg_exige_recifra_tenant ON "{TABELA}"')
    op.execute(
        f'CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON "{TABELA}" '
        f'FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})'
    )


def upgrade() -> None:
    op.add_column(TABELA, sa.Column('senha_alterada_em', sa.DateTime(), nullable=True))
    op.add_column(TABELA, sa.Column('deve_trocar_senha', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column(TABELA, sa.Column('senha_historico', sa.Text(), nullable=True))
    op.execute(f'UPDATE "{TABELA}" SET senha_alterada_em = (now() AT TIME ZONE \'utc\') WHERE senha_alterada_em IS NULL')
    _trava(CIFRADAS_DEPOIS)


def downgrade() -> None:
    _trava(CIFRADAS_ANTES)
    for col in ('senha_historico', 'deve_trocar_senha', 'senha_alterada_em'):
        op.drop_column(TABELA, col)
