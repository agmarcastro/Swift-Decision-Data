-- Override readonly_changeme via POSTGRES_READONLY_PASSWORD env var in production

-- =============================================================================
-- InfoAgent read-only analytics user
-- Compatible with Docker PostgreSQL init scripts (runs as superuser on startup)
-- =============================================================================
-- The idempotent DO block below prevents errors on container restarts.
-- In production, replace 'readonly_changeme' by injecting this file after
-- substituting the value of the POSTGRES_READONLY_PASSWORD environment variable,
-- or use the psql \set / :'READONLY_PASSWORD' approach shown in the comment
-- block at the bottom of this file.
-- =============================================================================

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'infoagent_readonly') THEN
    CREATE ROLE infoagent_readonly WITH LOGIN PASSWORD 'readonly_changeme';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE infoagent TO infoagent_readonly;
GRANT USAGE ON SCHEMA public TO infoagent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO infoagent_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO infoagent_readonly;


-- =============================================================================
-- psql interactive / CI alternative (requires variable to be set externally):
--
--   psql -v READONLY_PASSWORD="$POSTGRES_READONLY_PASSWORD" -f create_readonly_user.sql
--
-- \set password :'READONLY_PASSWORD'
-- CREATE ROLE infoagent_readonly WITH LOGIN PASSWORD :'password';
-- GRANT CONNECT ON DATABASE infoagent TO infoagent_readonly;
-- GRANT USAGE ON SCHEMA public TO infoagent_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO infoagent_readonly;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO infoagent_readonly;
-- =============================================================================
