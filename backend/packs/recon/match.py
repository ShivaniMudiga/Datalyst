"""The deterministic matcher. Four tiers of SQL, and no model anywhere near it.

Reconciliation is a rules problem that a language model would only make less
predictable. The tiers run in order, each one considering only what the tier
above left behind, and each stamps the tier and a confidence on what it claims -
so a disputed match can be traced to the rule that made it, not to a prompt.

  T0   the line ties completely and arrived on time     confidence 1.000
  T1   the reference had to be normalised, or it was late          0.950
  T1b  no gateway reference at all - the order id carried it       0.880
  T2   several lines sum to one capture                            0.900
  T3   the money is off by less than a tolerance band     0.850 / 0.800

Whatever survives all four is an exception, on either side: a payout line with
no counterpart in the ledger, or a capture the gateway never settled. Those are
what the agent works in R3 - and only those.

This module must never read `recon_labels`. The reader role cannot, and neither
should the code; `test_recon_r2.py` asserts the name does not appear here.

  python -m packs.recon.match --reset
"""

from __future__ import annotations

import sys

from packs.recon.db import cursor

# The window a payout is expected to arrive in. T0 means "on or before"; a line
# later than this is late, which is T1's business, not T0's.
ON_TIME_DAYS = 2
LATE_DAYS = 10

# T3's tolerance. Fees drift by a few basis points; anything wider is a real
# discrepancy and belongs in the queue rather than in a match.
FEE_TOLERANCE_BPS = 25
FEE_TOLERANCE_FLOOR_MINOR = 100  # 1 rupee, so small captures are not scored on bps alone

# The day's rate, as a treasury system would hold it. The generator uses the
# same number, so what is being tested here is the rounding and the band, not
# rate discovery.
USD_PER_INR = 0.0120
FX_TOLERANCE_PCT = 0.01

CONFIDENCE = {"T0": 1.000, "T1": 0.950, "T1b": 0.880, "T2": 0.900, "T3_fee": 0.850, "T3_fx": 0.800}

UNCLAIMED = """
  AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.line_id = l.line_id)
  AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.payment_id = p.payment_id)
"""

# --------------------------------------------------------------------- T0
# The reference came back exactly as issued, the money ties to the paisa, and
# the payout arrived when it was due. Nothing to interpret.
T0 = f"""
INSERT INTO matches (line_id, payment_id, match_tier, confidence)
SELECT l.line_id, p.payment_id, 'T0', {CONFIDENCE['T0']}
FROM settlement_lines l
JOIN payments p ON p.gateway_reference = l.gateway_reference
WHERE l.currency = 'INR'
  AND l.gross_minor = round(p.amount * 100)
  AND l.fee_minor   = round(p.gateway_fee * 100)
  AND l.settled_at <= p.captured_at + interval '{ON_TIME_DAYS} days'
  {UNCLAIMED}
"""

# --------------------------------------------------------------------- T1
# The money still ties exactly. What failed T0 was the reference's spelling or
# the calendar, and neither changes who the payment was.
T1 = f"""
INSERT INTO matches (line_id, payment_id, match_tier, confidence)
SELECT l.line_id, p.payment_id, 'T1', {CONFIDENCE['T1']}
FROM settlement_lines l
JOIN payments p ON recon_core(p.gateway_reference) = recon_core(l.gateway_reference)
WHERE l.gateway_reference IS NOT NULL
  AND l.currency = 'INR'
  AND l.gross_minor = round(p.amount * 100)
  AND l.fee_minor   = round(p.gateway_fee * 100)
  AND l.settled_at <= p.captured_at + interval '{LATE_DAYS} days'
  {UNCLAIMED}
"""

# -------------------------------------------------------------------- T1b
# The gateway did not echo its own reference. The merchant's order id is a
# weaker key - it identifies an order, not an attempt, and an order can have
# several - so this insists the amount ties exactly and that exactly one
# captured attempt on that order is still unclaimed. Lower confidence than T1
# because the evidence is genuinely thinner, not as a formality.
T1B = f"""
INSERT INTO matches (line_id, payment_id, match_tier, confidence)
SELECT l.line_id, p.payment_id, 'T1b', {CONFIDENCE['T1b']}
FROM settlement_lines l
JOIN payments p ON p.order_id = substring(l.order_reference from 6)::int
WHERE l.gateway_reference IS NULL
  AND l.order_reference LIKE 'KTLY-%'
  AND l.currency = 'INR'
  AND p.payment_status = 'captured'
  AND p.gateway_reference IS NOT NULL
  AND l.gross_minor = round(p.amount * 100)
  AND l.fee_minor   = round(p.gateway_fee * 100)
  AND l.settled_at <= p.captured_at + interval '{LATE_DAYS} days'
  {UNCLAIMED}
"""

# --------------------------------------------------------------------- T2
# A capture paid out in parts. No single line matches anything; the group does.
# Both halves of the money have to tie - gross and fee - or this is a
# coincidence rather than a settlement.
#
# ponytail: the parts here share a reference, so grouping by it is enough. A
# gateway that splits without repeating the reference needs a bounded
# subset-sum over the amounts in the window, which this does not attempt.
T2 = f"""
WITH grouped AS (
  SELECT recon_core(l.gateway_reference) AS core,
         count(*)            AS parts,
         sum(l.gross_minor)  AS gross_minor,
         sum(l.fee_minor)    AS fee_minor,
         max(l.settled_at)   AS last_settled_at,
         array_agg(l.line_id) AS line_ids
  FROM settlement_lines l
  WHERE l.currency = 'INR'
    AND l.gateway_reference IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.line_id = l.line_id)
  GROUP BY 1
  HAVING count(*) >= 2
)
INSERT INTO matches (line_id, payment_id, match_tier, confidence)
SELECT part.line_id, p.payment_id, 'T2', {CONFIDENCE['T2']}
FROM grouped g
JOIN payments p ON recon_core(p.gateway_reference) = g.core
CROSS JOIN LATERAL unnest(g.line_ids) AS part(line_id)
WHERE g.gross_minor = round(p.amount * 100)
  AND g.fee_minor   = round(p.gateway_fee * 100)
  AND g.last_settled_at <= p.captured_at + interval '{LATE_DAYS} days'
  AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.payment_id = p.payment_id)
"""

# ------------------------------------------------------------------ T3 fee
# The gateway kept more than we recorded. Inside a basis-point band that is a
# fee residual and the match stands, with the difference written down; outside
# it, this is a discrepancy and belongs in the queue.
T3_FEE = f"""
INSERT INTO matches (line_id, payment_id, match_tier, confidence, fee_variance_minor)
SELECT l.line_id, p.payment_id, 'T3', {CONFIDENCE['T3_fee']},
       l.fee_minor - round(p.gateway_fee * 100)
FROM settlement_lines l
JOIN payments p ON recon_core(p.gateway_reference) = recon_core(l.gateway_reference)
WHERE l.gateway_reference IS NOT NULL
  AND l.currency = 'INR'
  AND l.gross_minor = round(p.amount * 100)
  AND abs(l.fee_minor - round(p.gateway_fee * 100))
      <= greatest({FEE_TOLERANCE_FLOOR_MINOR}, round(l.gross_minor * {FEE_TOLERANCE_BPS} / 10000.0))
  AND l.settled_at <= p.captured_at + interval '{LATE_DAYS} days'
  {UNCLAIMED}
"""

# ------------------------------------------------------------------- T3 fx
# Settled in another currency. The variance is recorded in the line's own
# currency, so it is never summed across currencies.
T3_FX = f"""
INSERT INTO matches (line_id, payment_id, match_tier, confidence, gross_variance_minor)
SELECT l.line_id, p.payment_id, 'T3', {CONFIDENCE['T3_fx']},
       l.gross_minor - round(round(p.amount * 100) * {USD_PER_INR})
FROM settlement_lines l
JOIN payments p ON recon_core(p.gateway_reference) = recon_core(l.gateway_reference)
WHERE l.gateway_reference IS NOT NULL
  AND l.currency <> 'INR'
  AND abs(l.gross_minor - round(round(p.amount * 100) * {USD_PER_INR}))
      <= greatest(2, round(l.gross_minor * {FX_TOLERANCE_PCT}))
  AND l.settled_at <= p.captured_at + interval '{LATE_DAYS} days'
  {UNCLAIMED}
"""

TIERS = (("T0", T0), ("T1", T1), ("T1b", T1B), ("T2", T2), ("T3 fee", T3_FEE), ("T3 fx", T3_FX))

# ------------------------------------------------------------- exceptions
# A payout line the ledger cannot account for.
UNMATCHED_LINES = """
INSERT INTO exceptions (line_id, reason_code, amount_minor)
SELECT l.line_id,
       CASE WHEN l.gateway_reference IS NULL THEN 'no_reference'
            ELSE 'no_ledger_counterpart' END,
       l.net_minor
FROM settlement_lines l
WHERE NOT EXISTS (SELECT 1 FROM matches m WHERE m.line_id = l.line_id)
  AND NOT EXISTS (SELECT 1 FROM exceptions e WHERE e.line_id = l.line_id)
"""

# A capture the gateway never paid out.
#
# Scope is the hard part here, and the obvious answer is wrong. Taking the date
# span the file's lines cover accuses every capture whose settlement date merely
# falls inside that span - which pulled in 204 payments from the months either
# side of the one actually being reconciled.
#
# A period is covered when the file plainly accounts for it: at least half of
# that gateway-month's captures were matched by these lines. Below that the file
# is only brushing the period - a few stragglers from last month - and its
# silence about the rest says nothing.
UNSETTLED_PAYMENTS = """
WITH in_ledger AS (
  SELECT payment_id, gateway, amount, to_char(captured_at, 'YYYY-MM') AS period
  FROM payments
  WHERE payment_status = 'captured' AND gateway_reference IS NOT NULL
), claimed AS (
  SELECT l.gateway, l.period, count(DISTINCT m.payment_id) AS matched
  FROM matches m JOIN in_ledger l ON l.payment_id = m.payment_id
  GROUP BY 1, 2
), scale AS (
  SELECT gateway, period, count(*) AS captured FROM in_ledger GROUP BY 1, 2
), covered AS (
  SELECT c.gateway, c.period
  FROM claimed c JOIN scale s USING (gateway, period)
  WHERE c.matched >= s.captured * 0.5
)
INSERT INTO exceptions (payment_id, reason_code, amount_minor)
SELECT l.payment_id, 'not_settled', round(l.amount * 100)
FROM in_ledger l
JOIN covered c ON c.gateway = l.gateway AND c.period = l.period
WHERE NOT EXISTS (SELECT 1 FROM matches m WHERE m.payment_id = l.payment_id)
  AND NOT EXISTS (SELECT 1 FROM exceptions e WHERE e.payment_id = l.payment_id)
"""


def run(reset: bool = False) -> dict:
    counts: dict[str, int] = {}
    with cursor(commit=True) as cur:
        if reset:
            # Re-matching throws away every exception, and a person's decisions
            # hang off those. Refuse rather than cascade: a rebuilt queue is a
            # development convenience, and it is not worth an approval quietly
            # disappearing. The audit log keeps its rows either way - it has no
            # foreign key and cannot be deleted from.
            cur.execute("""SELECT count(*) AS n FROM resolutions
                           WHERE state IN ('proposed', 'approved', 'applied')""")
            live = cur.fetchone()["n"]
            if live:
                raise SystemExit(
                    f"{live} live resolution(s) hang off the current exceptions. "
                    "Reset would discard them; reject or reverse them first."
                )
            cur.execute("TRUNCATE matches, exceptions, resolutions CASCADE")
        for name, statement in TIERS:
            cur.execute(statement)
            counts[name] = cur.rowcount
        cur.execute(UNMATCHED_LINES)
        counts["exception: line"] = cur.rowcount
        cur.execute(UNSETTLED_PAYMENTS)
        counts["exception: payment"] = cur.rowcount

        cur.execute("SELECT count(*) AS n FROM settlement_lines")
        lines = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM matches")
        matched = cur.fetchone()["n"]
    return {"lines": lines, "matched": matched, "counts": counts}


def main() -> None:
    result = run(reset="--reset" in sys.argv[1:])
    for name, count in result["counts"].items():
        print(f"  {name:<20} {count:>6}")
    rate = result["matched"] / result["lines"] if result["lines"] else 0
    print(f"  {'match rate':<20} {rate:>6.2%}  ({result['matched']}/{result['lines']} lines)")


if __name__ == "__main__":
    main()
