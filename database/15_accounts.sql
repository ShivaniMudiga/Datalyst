-- Accounts: conversations and connections become per-user.
--
-- Run once, as the app role:
--   psql -d talk_to_my_data_v2 -f database/15_accounts.sql
--
-- The `users` and `auth_sessions` tables are created by the application on
-- startup, like every other application table. This file only does the part
-- the application cannot: clearing rows that predate accounts and belong to
-- nobody.

BEGIN;

-- Chat history is cleared. chat_sessions.user_id is NOT NULL and no existing
-- row can be attributed to an account, so there is nothing to migrate them to.
DELETE FROM chat_messages;
DELETE FROM chat_sessions;

-- The agent's working state for those same conversations. Not checkpoint_migrations,
-- which is LangGraph's own schema version and must survive.
TRUNCATE checkpoint_writes, checkpoint_blobs, checkpoints;

ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL;

CREATE INDEX IF NOT EXISTS chat_sessions_user_idx
    ON chat_sessions (user_id, updated_at DESC);

-- connection_id is now the user's id. The old singleton belonged to no account;
-- schema_snapshots cascades from it.
DELETE FROM connections WHERE connection_id = 'default';

COMMIT;
