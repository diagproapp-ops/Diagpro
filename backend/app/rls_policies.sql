-- Políticas de Row-Level Security (RLS) Multi-Tenant para PostgreSQL (Fail-Closed)
-- Uso:
--   SET LOCAL app.bypass_rls = 'on';                    -- apenas para admin geral / login / migrações
--   SET LOCAL app.current_tenant_id = '<tenant_id>';    -- sessão normal de um tenant

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
        'HistoricoRevisaoQuestao'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %I;', tbl);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_policy ON %I
             USING (
                 NULLIF(current_setting(''app.bypass_rls'', true), '''') = ''on''
                 OR tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::integer
             )
             WITH CHECK (
                 NULLIF(current_setting(''app.bypass_rls'', true), '''') = ''on''
                 OR tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::integer
             );',
            tbl
        );
    END LOOP;
END $$;
