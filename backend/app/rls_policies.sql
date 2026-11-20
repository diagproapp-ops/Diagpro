-- Políticas de Row-Level Security (RLS) Multi-Tenant do DiagPro (fail-closed, sem bypass por variável).
--
-- Modelo de acesso:
--   diagpro_runtime  (NOBYPASSRLS): só enxerga linhas com tenant_id = app.current_tenant_id,
--                                    definido por transação com set_config('app.current_tenant_id', <id>, true).
--                                    Sem contexto, não enxerga nada.
--   diagpro_platform (BYPASSRLS):   única role com visão multi-tenant (login, cadastro, admin geral).
--                                    A liberação depende da credencial, não de variável de sessão.
--
-- Não existe cláusula de bypass na política: nenhuma variável de sessão (como a antiga
-- app.bypass_rls) consegue liberar o acesso para a role de runtime.
-- Mantida em sincronia com a revisão Alembic c3f1a9d2b7e4.

DO $$
DECLARE
    tbl TEXT;
    tables TEXT[] := ARRAY[
        'users',
        'audit_log_geracao',
        'Eventos',
        'Cargos',
        'DisciplinasDaProva',
        'Disciplinas',
        'ProvasMontadas',
        'banco_frases',
        'QuestoesBanco',
        'OpcoesQuestao',
        'ItensVerdadeiroFalso',
        'DetalhesQuestaoDiscursiva',
        'company_data',
        'conteudos',
        'TextosReferenciaGeral',
        'HistoricoRevisaoQuestao',
        'configuracoes',
        'uso_ia'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %I;', tbl);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_policy ON %I
             USING (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::integer)
             WITH CHECK (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::integer);',
            tbl
        );
    END LOOP;
END $$;
