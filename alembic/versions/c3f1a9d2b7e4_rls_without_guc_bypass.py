"""rls_without_guc_bypass

Remove a cláusula `app.bypass_rls = 'on'` das políticas RLS. Antes, qualquer conexão (inclusive a role
de runtime) podia executar `SET app.bypass_rls = 'on'` e ler/escrever dados de todos os tenants.
Agora o acesso multi-tenant exige a role diagpro_platform (BYPASSRLS), criada por
scripts/setup_postgres_roles.py.

Revision ID: c3f1a9d2b7e4
Revises: 24cbf7a7b399
Create Date: 2026-11-18 20:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3f1a9d2b7e4'
down_revision: Union[str, Sequence[str], None] = '24cbf7a7b399'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    'users', 'audit_log_geracao', 'Eventos', 'Cargos', 'DisciplinasDaProva', 'Disciplinas',
    'ProvasMontadas', 'banco_frases', 'QuestoesBanco', 'OpcoesQuestao', 'ItensVerdadeiroFalso',
    'DetalhesQuestaoDiscursiva', 'company_data', 'conteudos', 'TextosReferenciaGeral',
    'HistoricoRevisaoQuestao',
]

_TENANT_EXPR = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer"
_OLD_EXPR = (
    "NULLIF(current_setting('app.bypass_rls', true), '') = 'on' OR "
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer"
)


def _apply(expr: str) -> None:
    for tbl in TENANT_TABLES:
        op.execute(f'ALTER TABLE "{tbl}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{tbl}" FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation_policy ON "{tbl}"')
        op.execute(
            f'CREATE POLICY tenant_isolation_policy ON "{tbl}" USING ({expr}) WITH CHECK ({expr})'
        )


def upgrade() -> None:
    _apply(_TENANT_EXPR)


def downgrade() -> None:
    _apply(_OLD_EXPR)
