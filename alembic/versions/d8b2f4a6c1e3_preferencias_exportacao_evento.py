"""padrão de exportação por evento (sugestão pré-preenchida na tela)

Guarda, cifrado, o padrão de fonte/tamanho/colunas/template sugerido na exportação das provas do evento.
É só sugestão: cada exportação continua podendo mudar tudo (provas com imagens grandes em uma coluna,
provas especiais com fonte ampliada). A coluna entra na trava que impede trocar o cliente sem recifrar.

Revision ID: d8b2f4a6c1e3
Revises: c5e8f1a3b9d2
Create Date: 2026-11-19 15:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd8b2f4a6c1e3'
down_revision: Union[str, Sequence[str], None] = 'c5e8f1a3b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELA = "Eventos"
CIFRADAS_ANTES = ['local_prova', 'nome_evento', 'numero_edital', 'observacoes', 'senha_evento_cripto']
CIFRADAS_DEPOIS = CIFRADAS_ANTES + ['preferencias_exportacao']


def _trava(colunas: list[str]) -> None:
    args = ", ".join("'" + c + "'" for c in colunas)
    op.execute(f'DROP TRIGGER IF EXISTS trg_exige_recifra_tenant ON "{TABELA}"')
    op.execute(
        f'CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON "{TABELA}" '
        f'FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})'
    )


def upgrade() -> None:
    op.add_column(TABELA, sa.Column('preferencias_exportacao', sa.Text(), nullable=True))
    _trava(CIFRADAS_DEPOIS)


def downgrade() -> None:
    _trava(CIFRADAS_ANTES)
    op.drop_column(TABELA, 'preferencias_exportacao')
