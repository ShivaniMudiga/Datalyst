-- Read-only access for the model, same role as the other databases.
-- Requires data_runtime_reader to exist: run database/12_readonly_role.sql first.
--   psql -d kartly -f database/kartly/04_grants.sql
REVOKE ALL ON DATABASE kartly FROM data_runtime_reader;
GRANT CONNECT ON DATABASE kartly TO data_runtime_reader;
GRANT USAGE ON SCHEMA public TO data_runtime_reader;
REVOKE CREATE ON SCHEMA public FROM data_runtime_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO data_runtime_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO data_runtime_reader;
DROP FUNCTION IF EXISTS rnd(text);   -- seeding helper, not part of the model's world
