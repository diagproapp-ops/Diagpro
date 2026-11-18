---
name: diagpro-postgres-rls
description: Implementa e audita PostgreSQL, SQLAlchemy assíncrono, Alembic, migrações, índices, contexto de tenant e Row-Level Security no DiagPro.
---

# PostgreSQL, Alembic e isolamento multi-tenant

## Estado descrito no relatório
O projeto foi preparado para `postgresql+asyncpg`, `set_tenant_context()`, `app.current_tenant_id` e `app.bypass_rls`, com `rls_policies.sql`, Docker Compose, Alembic e script `scripts/migrate_sqlite_to_postgres.py`. O relatório lista a conclusão do runtime role, dependência `get_tenant_db`, aplicação global do contexto e índices compostos como pendências. Verifique tudo no código e no banco antes de agir.

## Invariantes de isolamento
- O tenant efetivo deriva da identidade autenticada e validada no servidor, nunca de um valor arbitrário do request.
- `ADMIN_GERAL` é uma exceção operacional explícita, não um bypass implícito espalhado pelas rotas.
- Toda tabela tenant-scoped deve ter estratégia clara de `tenant_id`, política RLS e testes. Tabelas globais/catálogos devem ser classificadas explicitamente.
- A conexão da aplicação deve usar role não-superuser, sem `BYPASSRLS`, sem ser owner das tabelas quando isso permitir contornar políticas; avalie `FORCE ROW LEVEL SECURITY` conforme arquitetura.
- O contexto de tenant deve ser transacional e por conexão: use `SET LOCAL`/`set_config(..., true)` dentro da mesma transação que executa as consultas. Não use estado de sessão global que possa vazar entre requisições no pool.
- Falha ao definir contexto deve falhar fechada; nunca continue como se o tenant estivesse configurado.

## Procedimento
1. Inspecione modelos, constraints, FKs, índices, `database.py`, migrations e `rls_policies.sql`.
2. Monte inventário tabela → tenant-scoped/global → coluna tenant → política → FK/índices → testes.
3. Verifique criação da role runtime, privilégios mínimos, ownership, `BYPASSRLS`, grants e conexão usada pela aplicação.
4. Desenhe migração reversível e compatível com dados existentes. Faça backup antes de operações de produção; não rode migração destrutiva sem autorização.
5. Garanta que `get_tenant_db` abre/gerencia transação, define contexto antes de qualquer consulta e faz commit/rollback corretamente.
6. Teste pool de conexões, concorrência e alternância tenant A/B na mesma pool.
7. Teste acesso direto via SQL usando a role runtime: SELECT, INSERT, UPDATE e DELETE cruzando tenants; confirme bloqueio em todos os casos aplicáveis.
8. Teste operações `ADMIN_GERAL` com caminho explícito, auditado e restrito.
9. Adicione índices compostos começando por `tenant_id` quando padrões de consulta justificarem; use `EXPLAIN` ou métricas, não adicione índices cegamente.

## Modelos/tabelas citados
`tenants`, `users`, `company_data`, `audit_log_geracao`, `Eventos`, `Cargos`, `Disciplinas`, `DisciplinasDaProva`, `conteudos`, `TextosReferenciaGeral`, `QuestoesBanco`, `OpcoesQuestao`, `ItensVerdadeiroFalso`, `DetalhesQuestaoDiscursiva`, `HistoricoRevisaoQuestao`, `ProvasMontadas`, `banco_frases`. O relatório cita 17 tabelas; confirme nomes reais e escopo de cada uma.

## Checklist de aceitação
- [ ] Role de runtime é não-superuser e não tem `BYPASSRLS`.
- [ ] Políticas cobrem todas as tabelas tenant-scoped.
- [ ] Contexto é aplicado por transação e não vaza pelo pool.
- [ ] Rotas não dependem de `tenant_id` fornecido pelo usuário.
- [ ] Testes A não lê/escreve dados de B.
- [ ] Migrações foram testadas em cópia representativa.
- [ ] Backup e rollback documentados para mudanças operacionais.
