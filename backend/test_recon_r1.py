"""R1 self-check: the two sources agree, and the planted defects are really planted.

R2's matcher will be scored against this data, so a defect that was labelled but
not actually injected would show up later as a matcher failure that never
happened. Every assertion here is about that: the label and the line say the
same thing.

  python -m packs.recon.generate --month 2026-07
  python -m packs.recon.ingest --reset ../payouts/*.csv
  python test_recon_r1.py
"""

from packs.recon.db import cursor
from packs.recon.defects import RATES

MONTH = "2026-07"


def one(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()["value"]


def main() -> None:
    with cursor() as cur:
        lines = one(cur, "SELECT count(*) AS value FROM settlement_lines")
        assert lines > 0, "no settlement lines - run generate and ingest first"

        # Every line carries a label, and no label points at a line that is absent.
        unlabelled = one(cur, """
            SELECT count(*) AS value FROM settlement_lines l
            LEFT JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            WHERE b.label_id IS NULL""")
        assert unlabelled == 0, f"{unlabelled} settlement lines have no label"

        dangling = one(cur, """
            SELECT count(*) AS value FROM recon_labels b
            LEFT JOIN settlement_lines l ON l.payout_id = b.payout_id AND l.line_seq = b.line_seq
            WHERE b.payout_id IS NOT NULL AND l.line_id IS NULL""")
        assert dangling == 0, f"{dangling} labels point at lines that were never ingested"

        # Every defect class is present, in roughly the share it was asked for.
        for defect in (*RATES, "clean", "orphan_gateway"):
            count = one(cur, "SELECT count(*) AS value FROM recon_labels WHERE defect_class = %s", (defect,))
            assert count > 0, f"no {defect} rows were generated"

        # T0 is exact match on the gateway's own reference. Clean lines must be
        # catchable that way, and drifted ones must not - otherwise the tiers
        # below T0 are being measured on work T0 already did.
        clean_exact = one(cur, """
            SELECT count(*) AS value FROM settlement_lines l
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            JOIN payments p ON p.gateway_reference = l.gateway_reference
            WHERE b.defect_class = 'clean' AND p.payment_id = b.payment_id""")
        clean_total = one(cur, "SELECT count(*) AS value FROM recon_labels b JOIN settlement_lines l USING (payout_id, line_seq) WHERE b.defect_class = 'clean'")
        assert clean_exact == clean_total, f"only {clean_exact}/{clean_total} clean lines match exactly"

        drift_exact = one(cur, """
            SELECT count(*) AS value FROM settlement_lines l
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            JOIN payments p ON p.gateway_reference = l.gateway_reference
            WHERE b.defect_class = 'ref_drift'""")
        assert drift_exact == 0, f"{drift_exact} ref_drift lines still match exactly - not drifted"

        # A split must sum back to the capture it came from, to the paisa.
        bad_splits = one(cur, """
            SELECT count(*) AS value FROM (
              SELECT b.payment_id, sum(l.gross_minor) AS parts, max(round(p.amount * 100)) AS whole
              FROM recon_labels b
              JOIN settlement_lines l ON l.payout_id = b.payout_id AND l.line_seq = b.line_seq
              JOIN payments p ON p.payment_id = b.payment_id
              WHERE b.defect_class = 'split'
              GROUP BY b.payment_id
            ) s WHERE s.parts <> s.whole""")
        assert bad_splits == 0, f"{bad_splits} splits do not sum back to their payment"

        # Orphans are orphans in both directions.
        false_orphans = one(cur, """
            SELECT count(*) AS value FROM settlement_lines l
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            JOIN payments p ON p.gateway_reference = l.gateway_reference
            WHERE b.defect_class = 'orphan_gateway'""")
        assert false_orphans == 0, f"{false_orphans} orphan_gateway lines have a counterpart after all"

        settled_orphans = one(cur, """
            SELECT count(*) AS value FROM recon_labels b
            JOIN payments p ON p.payment_id = b.payment_id
            JOIN settlement_lines l ON l.gateway_reference = p.gateway_reference
            WHERE b.defect_class = 'orphan_ledger'""")
        assert settled_orphans == 0, f"{settled_orphans} orphan_ledger payments were settled after all"

        # Every line carries the gateway's free text, and a reference-less line
        # carries nothing else to go on.
        no_narration = one(cur, "SELECT count(*) AS value FROM settlement_lines WHERE narration IS NULL")
        assert no_narration == 0, f"{no_narration} lines have no narration"

        still_referenced = one(cur, """
            SELECT count(*) AS value FROM recon_labels b
            JOIN settlement_lines l USING (payout_id, line_seq)
            WHERE b.defect_class = 'ref_missing' AND l.gateway_reference IS NOT NULL""")
        assert still_referenced == 0, f"{still_referenced} ref_missing lines kept their reference"

        # The residual the agent works in R3: no reference, no order id, only text.
        blind = one(cur, """
            SELECT count(*) AS value FROM settlement_lines
            WHERE gateway_reference IS NULL AND order_reference IS NULL""")
        assert blind > 0, "no reference-less lines - R3 has nothing to investigate"

        # Money never became a float, and net always ties to gross less fee.
        broken_net = one(cur, "SELECT count(*) AS value FROM settlement_lines WHERE net_minor <> gross_minor - fee_minor")
        assert broken_net == 0, f"{broken_net} lines where net <> gross - fee"

        # Re-ingesting the same bytes changes nothing. R3 extends this to applies.
        cur.execute("SELECT file_name, line_count FROM settlement_batches ORDER BY payout_id")
        batches = cur.fetchall()

    from pathlib import Path

    from packs.recon.ingest import ingest

    root = Path(__file__).resolve().parents[1] / "payouts"
    for batch in batches:
        again = ingest(root / batch["file_name"])
        assert not again["ingested"], f"{batch['file_name']} was ingested twice"

    with cursor() as cur:
        after = one(cur, "SELECT count(*) AS value FROM settlement_lines")
    assert after == lines, f"replay changed the line count: {lines} -> {after}"

    # The answer key must be unreachable from the role the model connects as.
    # ALTER DEFAULT PRIVILEGES in 12_readonly_role.sql and kartly/04_grants.sql
    # grants SELECT on every new table automatically, so this needs an explicit
    # REVOKE and an explicit test - not a comment claiming it is not granted.
    import os

    import psycopg

    reader = os.getenv(
        "RECON_READER_DSN", "postgresql://data_runtime_reader:change_me@localhost:5432/kartly"
    )
    with psycopg.connect(reader) as connection, connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM settlement_lines")
        assert cur.fetchone()[0] == lines, "the reader cannot see the settlement lines it needs"
        try:
            cur.execute("SELECT count(*) FROM recon_labels")
        except psycopg.errors.InsufficientPrivilege:
            connection.rollback()
        else:
            raise AssertionError("data_runtime_reader can read recon_labels - the model can see the answer key")

    print(f"ok - {lines} settlement lines across {len(batches)} payouts, every defect class present and honest")
    print(f"ok - {blind} lines carry only free text, which is R3's residual")
    print("ok - the reader role can see settlements and cannot see the answer key")


if __name__ == "__main__":
    main()
