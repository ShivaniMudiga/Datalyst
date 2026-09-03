"""R2 self-check: the matcher is right, not merely productive.

Tier counts landing on the planted class counts proves nothing on its own - the
matcher could pair every line with the wrong payment and still produce a tidy
histogram. Everything here is about identity and about money: did each rule
claim the payment that actually issued that line, and does the arithmetic tie.

The test may read `recon_labels`. The matcher may not, and the first assertion
is that it does not.

  python -m packs.recon.match --reset
  python test_recon_r2.py
"""

from pathlib import Path

from packs.recon.db import cursor
from packs.recon.match import run

# Which tier is supposed to catch which planted defect.
OWNS = {
    "T0": {"clean"},
    "T1": {"ref_drift", "date_skew"},
    "T1b": {"ref_missing"},
    "T2": {"split"},
    "T3": {"fee_residual", "fx"},
}

# What no rule is expected to reach: the gateway echoed neither its own
# reference nor the merchant's order id, leaving only free text. Those lines are
# the agent's work in R3, and a rule quietly solving them would hollow that out.
NAMELESS = "l.gateway_reference IS NULL AND l.order_reference IS NULL"


def one(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()["value"]


def main() -> None:
    source = (Path(__file__).parent / "packs/recon/match.py").read_text()
    assert "recon_labels" not in source.replace("`recon_labels`", ""), \
        "the matcher reads the answer key"

    with cursor() as cur:
        matched = one(cur, "SELECT count(*) AS value FROM matches")
        lines = one(cur, "SELECT count(*) AS value FROM settlement_lines")
        assert matched > 0, "no matches - run `python -m packs.recon.match --reset` first"

        # 1. Precision. Every match must name the payment that truly issued the
        #    line. This is the assertion the tier histogram cannot make.
        wrong = one(cur, """
            SELECT count(*) AS value FROM matches m
            JOIN settlement_lines l ON l.line_id = m.line_id
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            WHERE b.payment_id IS DISTINCT FROM m.payment_id""")
        assert wrong == 0, f"{wrong} matches point at the wrong payment"

        # 2. Each tier catches only what it is for. A tier quietly doing the tier
        #    below's work would show up in R4 as a figure nobody can explain.
        cur.execute("""
            SELECT m.match_tier, b.defect_class, count(*) AS n FROM matches m
            JOIN settlement_lines l ON l.line_id = m.line_id
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            GROUP BY 1, 2""")
        seen: dict[str, set] = {}
        for row in cur.fetchall():
            seen.setdefault(row["match_tier"], set()).add(row["defect_class"])
        for tier, classes in OWNS.items():
            assert seen.get(tier) == classes, f"{tier} caught {seen.get(tier)}, expected {classes}"

        # 3. Recall, within the rules' remit. Every line carrying an identifier of
        #    either kind must be matched.
        missed = one(cur, f"""
            SELECT count(*) AS value FROM settlement_lines l
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            WHERE b.payment_id IS NOT NULL AND NOT ({NAMELESS})
              AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.line_id = l.line_id)""")
        assert missed == 0, f"{missed} identifiable lines were not matched"

        # ...and a line carrying only free text must not be, because no rule here
        #    reads free text. Reading it is probabilistic, so it has to be
        #    proposed and verified rather than applied by a rule.
        guessed = one(cur, f"""
            SELECT count(*) AS value FROM settlement_lines l
            JOIN matches m ON m.line_id = l.line_id WHERE {NAMELESS}""")
        assert guessed == 0, f"{guessed} nameless lines were matched by a rule - that is the agent's work"

        # 4. Only splits may claim a payment more than once, and then only as the
        #    whole group. Anything else is one capture being paid twice.
        overclaimed = one(cur, """
            SELECT count(*) AS value FROM (
              SELECT payment_id FROM matches GROUP BY payment_id
              HAVING count(*) > 1 AND max(match_tier) <> 'T2') s""")
        assert overclaimed == 0, f"{overclaimed} payments were claimed twice outside T2"

        # 5. The money ties. Exact tiers to the paisa; T3 only inside its band.
        untied = one(cur, """
            SELECT count(*) AS value FROM matches m
            JOIN settlement_lines l ON l.line_id = m.line_id
            JOIN payments p ON p.payment_id = m.payment_id
            WHERE m.match_tier IN ('T0','T1','T1b')
              AND (l.gross_minor <> round(p.amount * 100) OR l.fee_minor <> round(p.gateway_fee * 100))""")
        assert untied == 0, f"{untied} exact matches do not tie to the paisa"

        untied_groups = one(cur, """
            SELECT count(*) AS value FROM (
              SELECT m.payment_id, sum(l.gross_minor) AS gross, sum(l.fee_minor) AS fee,
                     max(round(p.amount * 100)) AS want_gross, max(round(p.gateway_fee * 100)) AS want_fee
              FROM matches m
              JOIN settlement_lines l ON l.line_id = m.line_id
              JOIN payments p ON p.payment_id = m.payment_id
              WHERE m.match_tier = 'T2' GROUP BY m.payment_id
            ) g WHERE g.gross <> g.want_gross OR g.fee <> g.want_fee""")
        assert untied_groups == 0, f"{untied_groups} split groups do not sum back to their capture"

        # 6. The queue holds only what the rules genuinely could not place, and it
        #    says which of the two problems each line has - they need different work.
        wrong_line_exceptions = one(cur, f"""
            SELECT count(*) AS value FROM exceptions e
            JOIN settlement_lines l ON l.line_id = e.line_id
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            WHERE b.defect_class <> 'orphan_gateway' AND NOT ({NAMELESS})""")
        assert wrong_line_exceptions == 0, f"{wrong_line_exceptions} matchable lines were sent to the queue"

        cur.execute("SELECT reason_code, count(*) AS n FROM exceptions WHERE line_id IS NOT NULL GROUP BY 1")
        reasons = {row["reason_code"]: row["n"] for row in cur.fetchall()}
        assert set(reasons) == {"no_ledger_counterpart", "no_reference"}, f"unexpected reasons: {reasons}"

        nameless_without_narration = one(cur, f"""
            SELECT count(*) AS value FROM exceptions e
            JOIN settlement_lines l ON l.line_id = e.line_id
            WHERE e.reason_code = 'no_reference' AND (l.narration IS NULL OR {NAMELESS} IS NOT TRUE)""")
        assert nameless_without_narration == 0, "a nameless line reached the queue with nothing to read"

        wrong_payment_exceptions = one(cur, """
            SELECT count(*) AS value FROM exceptions e
            WHERE e.payment_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM recon_labels b
              WHERE b.payment_id = e.payment_id
                AND b.defect_class IN ('orphan_ledger', 'ref_missing'))""")
        assert wrong_payment_exceptions == 0, \
            f"{wrong_payment_exceptions} settled payments were reported unsettled"

        uncaught = one(cur, """
            SELECT count(*) AS value FROM recon_labels b
            WHERE b.defect_class = 'orphan_ledger'
              AND NOT EXISTS (SELECT 1 FROM exceptions e WHERE e.payment_id = b.payment_id)""")
        assert uncaught == 0, f"{uncaught} unsettled captures never reached the queue"

        # 7. Every line is accounted for: matched, or in the queue. Never neither.
        stranded = one(cur, """
            SELECT count(*) AS value FROM settlement_lines l
            WHERE NOT EXISTS (SELECT 1 FROM matches m WHERE m.line_id = l.line_id)
              AND NOT EXISTS (SELECT 1 FROM exceptions e WHERE e.line_id = l.line_id)""")
        assert stranded == 0, f"{stranded} lines are neither matched nor queued"

        exceptions = one(cur, "SELECT count(*) AS value FROM exceptions")

    # 8. Re-running the matcher over its own output changes nothing.
    again = run(reset=False)
    assert again["matched"] == matched, f"a second pass matched more: {matched} -> {again['matched']}"
    with cursor() as cur:
        assert one(cur, "SELECT count(*) AS value FROM exceptions") == exceptions, \
            "a second pass opened duplicate exceptions"

    print(f"ok - {matched}/{lines} lines matched ({matched / lines:.2%}), every match on the right payment")
    print(f"ok - {exceptions} exceptions, {reasons['no_reference']} of them nameless and left for the agent")


if __name__ == "__main__":
    main()
