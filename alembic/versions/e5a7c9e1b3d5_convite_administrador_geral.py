"""convite de administrador geral (sem banca)

A plataforma pode ter vários administradores gerais: um administrador geral convida outro por link (a pessoa cria
a própria senha, envia a foto e cadastra o 2FA) e outro aprova. O convite de plataforma não pertence a banca
nenhuma: tenant_id nulo. O RLS continua igual (a sessão de banca não enxerga essas linhas; só a da plataforma).

Revision ID: e5a7c9e1b3d5
Revises: d4f6a8c0e2b4
Create Date: 2026-11-21 10:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5a7c9e1b3d5'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8c0e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('convites', 'tenant_id', nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM convites WHERE tenant_id IS NULL")
    op.alter_column('convites', 'tenant_id', nullable=False)
