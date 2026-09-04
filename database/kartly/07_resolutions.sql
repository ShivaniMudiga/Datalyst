-- The gate. Everything the agent proposes stops here until a person moves it.
--
-- The agent writes rows in `resolutions` and nothing else, ever. It has no
-- connection that could write anywhere: its only reach into the database is the
-- runtime's read-only `run_query`, on a role granted SELECT inside a read-only
-- transaction. Applying a resolution is done by packs/recon/commit.py, which
-- the model cannot call and cannot name.
--
--   psql -d kartly -f database/kartly/07_resolutions.sql

ALTER TABLE exceptions ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'open';
ALTER TABLE exceptions DROP CONSTRAINT IF EXISTS exceptions_status_check;
ALTER TABLE exceptions ADD CONSTRAINT exceptions_status_check
  CHECK (status IN ('open', 'resolved', 'written_off', 'escalated'));

-- A match the agent proposed and a person approved is still a match, but it
-- must never be mistaken for one a rule made.
ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_match_tier_check;
ALTER TABLE matches ADD CONSTRAINT matches_match_tier_check
  CHECK (match_tier IN ('T0', 'T1', 'T1b', 'T2', 'T3', 'AGENT'));

CREATE TABLE IF NOT EXISTS resolutions (
  resolution_id   bigserial PRIMARY KEY,
  exception_id    bigint NOT NULL REFERENCES exceptions(exception_id),
  kind            text NOT NULL CHECK (kind IN ('link', 'write_off', 'escalate')),
  target_ids      bigint[] NOT NULL DEFAULT '{}',
  confidence      numeric(4,3) NOT NULL CHECK (confidence > 0 AND confidence <= 1),
  reason          text NOT NULL,

  -- What the proposal rests on. `evidence_sql` is recomputed at apply time and
  -- its result re-hashed; if the ledger moved underneath the proposal, the
  -- apply is refused rather than applied to a world that no longer exists.
  evidence_sql    text NOT NULL,
  evidence_hash   text NOT NULL,

  state           text NOT NULL DEFAULT 'proposed'
                  CHECK (state IN ('proposed', 'approved', 'rejected', 'applied', 'reversed')),
  proposed_by     text NOT NULL DEFAULT 'agent',
  decided_by      text,
  -- Set only at apply time. Unique, so the same decision applied twice is one row.
  idempotency_key text UNIQUE,
  applied_effect  jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS resolutions_exception_idx ON resolutions (exception_id);
CREATE INDEX IF NOT EXISTS resolutions_state_idx     ON resolutions (state);

-- Only one proposal per exception may be live at a time. A second opinion is
-- fine; two applied answers to the same question is not.
CREATE UNIQUE INDEX IF NOT EXISTS resolutions_one_live_idx
  ON resolutions (exception_id) WHERE state IN ('proposed', 'approved', 'applied');

-- ------------------------------------------------------------ state machine
-- In the database, not in Python. Code that forgets the rule still obeys it.
CREATE OR REPLACE FUNCTION resolutions_transition() RETURNS trigger AS $$
BEGIN
  IF NEW.state = OLD.state THEN
    NEW.updated_at := now();
    RETURN NEW;
  END IF;

  IF NOT (OLD.state, NEW.state) IN (
        ('proposed', 'approved'), ('proposed', 'rejected'),
        ('approved', 'applied'),  ('applied',  'reversed')) THEN
    RAISE EXCEPTION 'illegal resolution transition: % -> %', OLD.state, NEW.state;
  END IF;

  IF NEW.state IN ('approved', 'rejected') AND NEW.decided_by IS NULL THEN
    RAISE EXCEPTION 'a decision needs a decider';
  END IF;

  IF NEW.state = 'applied' AND NEW.idempotency_key IS NULL THEN
    RAISE EXCEPTION 'an applied resolution needs an idempotency key';
  END IF;

  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS resolutions_transition_trg ON resolutions;
CREATE TRIGGER resolutions_transition_trg BEFORE UPDATE ON resolutions
  FOR EACH ROW EXECUTE FUNCTION resolutions_transition();

-- --------------------------------------------------------------- audit log
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id      bigserial PRIMARY KEY,
  actor         text NOT NULL,
  action        text NOT NULL,
  resolution_id bigint,
  exception_id  bigint,
  before_state  jsonb,
  after_state   jsonb,
  evidence_hash text,
  at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_resolution_idx ON audit_log (resolution_id);

-- Append-only, enforced. A REVOKE would not stop the owner, and the owner is
-- what the pack connects as.
CREATE OR REPLACE FUNCTION audit_log_is_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only (attempted %)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_append_only_trg ON audit_log;
CREATE TRIGGER audit_log_append_only_trg BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();

-- A row trigger never sees TRUNCATE, so without this one the whole log could be
-- erased in a statement that fires nothing.
DROP TRIGGER IF EXISTS audit_log_no_truncate_trg ON audit_log;
CREATE TRIGGER audit_log_no_truncate_trg BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_is_append_only();

-- The model may read what it proposed and what happened to it. It still cannot
-- write here: its only database access is the runtime's read-only role.
GRANT SELECT ON resolutions, audit_log TO data_runtime_reader;
