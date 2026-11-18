-- Criação da role de runtime sem privilégios de superuser e sem BYPASSRLS
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'diagpro_runtime') THEN
        CREATE ROLE diagpro_runtime LOGIN PASSWORD 'diagpro_runtime_dev_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    ELSE
        ALTER ROLE diagpro_runtime NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO diagpro_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO diagpro_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO diagpro_runtime;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO diagpro_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO diagpro_runtime;
