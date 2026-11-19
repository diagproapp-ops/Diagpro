"""imagem do item de questão Certo/Errado

A tela e a API já aceitavam uma imagem por item de Certo/Errado, mas a tabela não tinha a coluna:
criar ou revisar questões (inclusive de múltipla escolha, na revisão) falhava com erro 500.
A coluna guarda a referência cifrada do arquivo (sf1:...), como as demais imagens de questão,
e entra na trava que impede trocar o cliente da linha sem recifrar.

Revision ID: c5e8f1a3b9d2
Revises: a9d4c2e6f0b1
Create Date: 2026-11-19 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c5e8f1a3b9d2'
down_revision: Union[str, Sequence[str], None] = 'a9d4c2e6f0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELA = "ItensVerdadeiroFalso"
CIFRADAS_ANTES = ['afirmacao', 'feedback_item', 'valor_correto']
CIFRADAS_DEPOIS = CIFRADAS_ANTES + ['imagem_path_item']


def _trava(colunas: list[str]) -> None:
    args = ", ".join("'" + c + "'" for c in colunas)
    op.execute(f'DROP TRIGGER IF EXISTS trg_exige_recifra_tenant ON "{TABELA}"')
    op.execute(
        f'CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON "{TABELA}" '
        f'FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})'
    )


def upgrade() -> None:
    op.add_column(TABELA, sa.Column('imagem_path_item', sa.Text(), nullable=True))
    _trava(CIFRADAS_DEPOIS)


def downgrade() -> None:
    _trava(CIFRADAS_ANTES)
    op.drop_column(TABELA, 'imagem_path_item')
