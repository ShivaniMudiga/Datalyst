-- What the rules decided. Written by packs/recon/match.py, read by everything else.
--
-- Settlement lines are never edited by matching. A match is a row here that
-- points at a line and a payment; the file as received stays the file as
-- received, which is what makes a disputed match arguable after the fact.
--
--   psql -d kartly -f database/kartly/06_matching.sql

-- The comparable form of a gateway reference.
--
-- Every reference in this data is a per-gateway prefix followed by a 14-character
-- hex core, and every way a payout file mangles one - lower-casing, dropping the
-- separator, padding with spaces, stripping the prefix - leaves that core intact.
-- Taking the last 14 alphanumerics is therefore the whole of T1's normalisation.
--
-- ponytail: 14 is this data's core length, not a universal truth. A gateway with
-- a different reference shape needs a per-gateway rule here, not a longer regex.
CREATE OR REPLACE FUNCTION recon_core(reference text) RETURNS text AS $$
  SELECT right(lower(regexp_replace(coalesce(reference, ''), '[^a-zA-Z0-9]', '', 'g')), 14)
$$ LANGUAGE sql IMMUTABLE;

CREATE INDEX IF NOT EXISTS payments_reference_core_idx
  ON payments (recon_core(gateway_reference)) WHERE gateway_reference IS NOT NULL;
CREATE INDEX IF NOT EXISTS settlement_lines_core_idx
  ON settlement_lines (recon_core(gateway_reference));

CREATE TABLE IF NOT EXISTS matches (
  match_id        bigserial PRIMARY KEY,
  line_id         bigint NOT NULL UNIQUE REFERENCES settlement_lines(line_id) ON DELETE CASCADE,
  payment_id      int    NOT NULL REFERENCES payments(payment_id),
  match_tier      text   NOT NULL CHECK (match_tier IN ('T0', 'T1', 'T1b', 'T2', 'T3')),
  confidence      numeric(4,3) NOT NULL CHECK (confidence > 0 AND confidence <= 1),
  matched_by      text   NOT NULL DEFAULT 'rule' CHECK (matched_by IN ('rule', 'agent')),
  gross_variance_minor bigint NOT NULL DEFAULT 0,
  fee_variance_minor   bigint NOT NULL DEFAULT 0,
  matched_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS matches_payment_idx ON matches (payment_id);

-- Unmatched on either side. A line with no payment, or a payment with no line.
CREATE TABLE IF NOT EXISTS exceptions (
  exception_id  bigserial PRIMARY KEY,
  line_id       bigint REFERENCES settlement_lines(line_id) ON DELETE CASCADE,
  payment_id    int    REFERENCES payments(payment_id),
  reason_code   text   NOT NULL,
  amount_minor  bigint NOT NULL,
  opened_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (line_id IS NOT NULL OR payment_id IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS exceptions_line_idx    ON exceptions (line_id)    WHERE line_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS exceptions_payment_idx ON exceptions (payment_id) WHERE payment_id IS NOT NULL;

GRANT SELECT ON matches, exceptions TO data_runtime_reader;
