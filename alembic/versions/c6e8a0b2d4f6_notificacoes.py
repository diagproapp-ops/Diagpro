"""notificações (no sistema e por e-mail) e preferências pessoais de aviso

`notificacoes`: uma linha por aviso a um usuário. Título, mensagem e link ficam cifrados; o e-mail sai por uma
fila (estado/tentativas em claro, sem conteúdo). RLS forçado por banca; tenant nulo = admin geral (só a role
de plataforma enxerga). `users.preferencias` (cifrado) guarda quais avisos a pessoa quer por e-mail.

Revision ID: c6e8a0b2d4f6
Revises: b4d6f8a0c2e3
Create Date: 2026-11-20 09:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c6e8a0b2d4f6'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USERS_ANTES = ['address', 'agencia', 'avatar_url', 'banco', 'birth_date', 'conta_corrente', 'cpf', 'department',
               'email', 'full_name', 'institution', 'notes', 'phone', 'pix_key', 'specialty', 'terms_acceptance',
               'username', 'totp_secret', 'codigos_recuperacao', 'senha_historico']
USERS_DEPOIS = USERS_ANTES + ['preferencias']


def _trava(tabela: str, colunas: list[str]) -> None:
    args = ", ".join("'" + c + "'" for c in colunas)
    op.execute(f'DROP TRIGGER IF EXISTS trg_exige_recifra_tenant ON "{tabela}"')
    op.execute(
        f'CREATE TRIGGER trg_exige_recifra_tenant BEFORE UPDATE OF tenant_id ON "{tabela}" '
        f'FOR EACH ROW EXECUTE FUNCTION diagpro_exige_recifra_ao_trocar_tenant({args})'
    )


def upgrade() -> None:
    op.add_column('users', sa.Column('preferencias', sa.Text(), nullable=True))
    _trava('users', USERS_DEPOIS)

    op.create_table(
        'notificacoes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(40), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('lida_em', sa.DateTime(), nullable=True),
        sa.Column('conteudo', sa.Text(), nullable=False),           # cifrado: {titulo, mensagem, link}
        sa.Column('email_estado', sa.String(12), nullable=False),   # pendente | enviado | falhou | nao_enviar
        sa.Column('email_tentativas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('email_proxima_tentativa', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_notificacoes_tenant_id', 'notificacoes', ['tenant_id'])
    op.create_index('ix_notificacoes_usuario', 'notificacoes', ['usuario_id', 'criado_em'])
    op.create_index('ix_notificacoes_fila', 'notificacoes', ['email_estado', 'email_proxima_tentativa'])
    op.execute('ALTER TABLE notificacoes ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE notificacoes FORCE ROW LEVEL SECURITY')
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON notificacoes "
        "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"
    )
    _trava('notificacoes', ['conteudo'])


def downgrade() -> None:
    op.drop_table('notificacoes')
    _trava('users', USERS_ANTES)
    op.drop_column('users', 'preferencias')
