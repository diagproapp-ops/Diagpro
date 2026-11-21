"""merge_financeiro_head

Revision ID: 1c7d662f9f71
Revises: e5a7c9e1b3d5, e5f7a9b1c3d5
Create Date: 2026-11-21 00:39:57.328929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1c7d662f9f71'
down_revision: Union[str, Sequence[str], None] = ('e5a7c9e1b3d5', 'e5f7a9b1c3d5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
