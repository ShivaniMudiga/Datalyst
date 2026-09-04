-- The read-only role. This, not Python, is what stands between the model and
-- the data. Run as a superuser, once per database.
--
--   psql -d talk_to_my_data_v2 -f database/12_readonly_role.sql
--
-- Then set DB_READONLY_USER / DB_READONLY_PASSWORD in backend/.env.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'data_runtime_reader') THEN
        CREATE ROLE data_runtime_reader LOGIN PASSWORD 'change_me';
    END IF;
END
$$;

-- No password in production: set it out of band.
--   ALTER ROLE data_runtime_reader PASSWORD '...';

REVOKE ALL ON DATABASE talk_to_my_data_v2 FROM data_runtime_reader;
GRANT CONNECT ON DATABASE talk_to_my_data_v2 TO data_runtime_reader;

GRANT USAGE ON SCHEMA public TO data_runtime_reader;
REVOKE CREATE ON SCHEMA public FROM data_runtime_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO data_runtime_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO data_runtime_reader;

-- The application's own tables are not the user's data. Keep them out of reach
-- so the model cannot read other conversations or its own checkpoints.
REVOKE ALL ON chat_sessions, chat_messages FROM data_runtime_reader;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'checkpoints') THEN
        REVOKE ALL ON checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations
            FROM data_runtime_reader;
    END IF;
END
$$;

-- Belt and braces: the session is opened read-only by the pool as well.
ALTER ROLE data_runtime_reader SET default_transaction_read_only = on;
ALTER ROLE data_runtime_reader SET statement_timeout = '15s';
