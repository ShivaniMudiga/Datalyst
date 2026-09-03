-- Reconciliation: the gateway's side of the money, and the labels that say
-- what the right answer was.
--
-- Kartly's `payments` table is the internal ledger - what we think we captured.
-- A payment gateway does not confirm that in real time; it sends a payout file
-- a couple of days later saying what it actually settled, net of fees. The two
-- disagree, and reconciling them is the job.
--
--   psql -d kartly -f database/kartly/05_reconciliation.sql
--
-- Money here is in integer minor units (paise). Kartly's own columns are
-- numeric rupees; the conversion happens once, in the generator. Nothing in
-- reconciliation compares floats.

-- --------------------------------------------------------------- ledger side
-- The reference the gateway echoes back. Real PSPs hand you their own id at
-- capture time and repeat it on the payout file - without it stored on our
-- side, there is no exact match to attempt. Deterministic, so re-running this
-- file does not invent new references.
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway_reference text;

UPDATE payments SET gateway_reference =
  CASE gateway
    WHEN 'razorpay' THEN 'pay_'
    WHEN 'payu'     THEN 'PU'
    WHEN 'cashfree' THEN 'CF-'
  END || upper(substr(md5('gwref:' || payment_id::text), 1, 14))
WHERE payment_status = 'captured'
  AND gateway <> 'cod_collection'
  AND gateway_reference IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS payments_gateway_reference_idx
  ON payments (gateway_reference) WHERE gateway_reference IS NOT NULL;

-- Cash on delivery never reaches a gateway payout file - the courier collects
-- it and remits separately. Out of scope on both sides, deliberately.

-- ------------------------------------------------------------- gateway side
-- One row per file received. `file_hash` is what makes re-ingesting the same
-- file a no-op instead of a double count.
CREATE TABLE IF NOT EXISTS settlement_batches (
  payout_id      text PRIMARY KEY,
  gateway        text NOT NULL,
  payout_date    date NOT NULL,
  currency       char(3) NOT NULL,
  file_name      text NOT NULL,
  file_hash      text NOT NULL UNIQUE,
  line_count     int  NOT NULL,
  net_total_minor bigint NOT NULL,
  ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- One row per line of the payout file, exactly as received. Never edited by
-- matching: a match is a row in `matches` (R2), not a mutation here.
CREATE TABLE IF NOT EXISTS settlement_lines (
  line_id           bigserial PRIMARY KEY,
  payout_id         text NOT NULL REFERENCES settlement_batches(payout_id) ON DELETE CASCADE,
  line_seq          int  NOT NULL,
  settled_at        timestamptz NOT NULL,
  gateway_reference text,
  order_reference   text,
  currency          char(3) NOT NULL,
  gross_minor       bigint NOT NULL,
  fee_minor         bigint NOT NULL,
  net_minor         bigint NOT NULL,
  -- Free text, exactly as the gateway wrote it. When a reference is missing
  -- this is sometimes the only clue to what the line is, and it is the one
  -- field in the file no rule should try to parse: the formats vary, some
  -- carry a batch number rather than an order id, and a wrong extraction moves
  -- money. Reading it is the agent's job in R3; verifying what it read is the
  -- committer's.
  narration         text,
  UNIQUE (payout_id, line_seq)
);

CREATE INDEX IF NOT EXISTS settlement_lines_reference_idx ON settlement_lines (gateway_reference);
CREATE INDEX IF NOT EXISTS settlement_lines_order_idx     ON settlement_lines (order_reference);
CREATE INDEX IF NOT EXISTS settlement_lines_settled_idx   ON settlement_lines (settled_at);

-- ------------------------------------------------------------------- labels
-- Ground truth, written by the generator, read only by the evaluation harness
-- (R4). The matcher must never read this table - `05_grants` does not stop it,
-- so the discipline is that `packs/recon/match.py` does not import it.
--
-- Two directions in one table:
--   payout_id IS NOT NULL  a settlement line, and the payment it truly belongs
--                          to (NULL payment_id = genuinely no counterpart)
--   payout_id IS NULL      a captured payment that was truly never settled
CREATE TABLE IF NOT EXISTS recon_labels (
  label_id      bigserial PRIMARY KEY,
  payout_id     text,
  line_seq      int,
  payment_id    int REFERENCES payments(payment_id),
  defect_class  text NOT NULL,
  UNIQUE (payout_id, line_seq)
);

CREATE INDEX IF NOT EXISTS recon_labels_payment_idx ON recon_labels (payment_id);

GRANT SELECT ON settlement_batches, settlement_lines TO data_runtime_reader;

-- The answer key has to be revoked, not merely left ungranted. Both
-- `12_readonly_role.sql` and `kartly/04_grants.sql` set ALTER DEFAULT
-- PRIVILEGES ... GRANT SELECT ON TABLES, so every table created here is handed
-- to the reader the moment it exists. Simply not writing a GRANT does nothing.
-- `test_recon_r1.py` connects as the reader and asserts this, because the first
-- version of this file got it wrong and said so in a comment.
REVOKE ALL ON recon_labels FROM data_runtime_reader;
REVOKE ALL ON SEQUENCE recon_labels_label_id_seq FROM data_runtime_reader;
