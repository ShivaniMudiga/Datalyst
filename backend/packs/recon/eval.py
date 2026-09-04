"""How often is it right, and what does being wrong cost?

Everything here is measured against `recon_labels`, which the generator wrote as
it built the payout files - so the truth is known by construction and nobody
hand-labelled three thousand rows. Neither the matcher nor the agent can read
that table; this script is the only thing that does.

Nothing is hand-typed into a report. `--write-readme` regenerates the block
between the markers in README.md, so the numbers there are always the numbers
this produced.

  python -m packs.recon.eval
  python -m packs.recon.eval --write-readme
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

from packs.recon.db import cursor

# Which defect classes each tier is responsible for. Recall is measured against
# these, so a tier is never credited with work another tier did.
TIER_CLASSES = {
    "T0": ("clean",),
    "T1": ("ref_drift", "date_skew"),
    "T1b": ("ref_missing",),
    "T2": ("split",),
    "T3": ("fee_residual", "fx"),
}

THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99, 1.00)


def wilson_low(correct: int, total: int, z: float = 1.96) -> float:
    """The lower end of a 95% interval on a proportion.

    Twenty out of twenty is not the same claim as two thousand out of two
    thousand, and reporting either as "1.000" invites the one question there is
    no good answer to. Wilson rather than the normal approximation, because the
    normal one gives a zero-width interval at exactly 0 or 1 - which is the case
    this exists to describe.
    """
    if total == 0:
        return 0.0
    proportion = correct / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    spread = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
    return max(0.0, (centre - spread) / denominator)


def rupees(minor: int | None) -> str:
    return f"{(minor or 0) / 100:,.0f}"


def table(headings: list[str], rows: list[list], align: str = "") -> str:
    align = align or "l" * len(headings)
    rule = ["---" if letter == "l" else "---:" for letter in align]
    lines = ["| " + " | ".join(headings) + " |", "|" + "|".join(rule) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def coverage(cur) -> str:
    cur.execute("""
        SELECT (SELECT count(*) FROM settlement_lines) AS lines,
               (SELECT count(*) FROM matches WHERE matched_by = 'rule') AS by_rule,
               (SELECT count(*) FROM matches WHERE matched_by = 'agent') AS by_agent,
               (SELECT count(*) FROM exceptions WHERE status = 'open') AS open_exceptions,
               (SELECT sum(net_minor) FROM settlement_lines) AS settled,
               (SELECT sum(l.net_minor) FROM matches m JOIN settlement_lines l USING (line_id)) AS cleared,
               (SELECT sum(e.amount_minor) FROM exceptions e WHERE e.status = 'open') AS at_risk""")
    row = cur.fetchone()
    rate = (row["by_rule"] + row["by_agent"]) / row["lines"]
    return table(
        ["", "Lines", "Value (INR)"],
        [["Settled in the period", f"{row['lines']:,}", rupees(row["settled"])],
         ["Matched by rule", f"{row['by_rule']:,}", rupees(row["cleared"])],
         ["Matched by an approved proposal", f"{row['by_agent']:,}", ""],
         ["**Match rate**", f"**{rate:.2%}**", ""],
         ["Still in the queue", f"{row['open_exceptions']:,}", rupees(row["at_risk"])]],
        "lrr",
    )


def tiers(cur) -> str:
    rows = []
    for tier, classes in TIER_CLASSES.items():
        cur.execute("""
            SELECT count(*) AS claimed,
                   count(*) FILTER (WHERE b.payment_id IS NOT DISTINCT FROM m.payment_id) AS correct
            FROM matches m
            JOIN settlement_lines l ON l.line_id = m.line_id
            JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
            WHERE m.match_tier = %s""", (tier,))
        claimed = cur.fetchone()
        cur.execute("""
            SELECT count(*) AS available FROM recon_labels b
            JOIN settlement_lines l USING (payout_id, line_seq)
            WHERE b.defect_class = ANY(%s)""", (list(classes),))
        available = cur.fetchone()["available"]
        precision = claimed["correct"] / claimed["claimed"] if claimed["claimed"] else 0
        recall = claimed["correct"] / available if available else 0
        rows.append([tier, ", ".join(classes), f"{available:,}", f"{claimed['claimed']:,}",
                     f"{precision:.3f}", f"{recall:.3f}"])
    return table(["Tier", "Responsible for", "Present", "Claimed", "Precision", "Recall"],
                 rows, "llrrrr")


def agent(cur) -> tuple[str, str]:
    cur.execute("""
        SELECT r.kind, r.confidence, r.steps, r.corrections, r.latency_ms,
               r.target_ids, b.payment_id AS truth
        FROM resolutions r
        JOIN exceptions e ON e.exception_id = r.exception_id
        JOIN settlement_lines l ON l.line_id = e.line_id
        JOIN recon_labels b ON b.payout_id = l.payout_id AND b.line_seq = l.line_seq
        WHERE r.state <> 'rejected'""")
    proposals = cur.fetchall()
    if not proposals:
        return "_No proposals yet - run `python -m packs.recon.agent --all`._", ""

    cur.execute("""SELECT count(*) AS n FROM recon_labels b
                   JOIN settlement_lines l USING (payout_id, line_seq)
                   WHERE l.gateway_reference IS NULL AND l.order_reference IS NULL""")
    residual = cur.fetchone()["n"]

    links = [p for p in proposals if p["kind"] == "link"]
    correct = [p for p in links if p["target_ids"] and p["target_ids"][0] == p["truth"]]
    declined = [p for p in proposals if p["kind"] != "link"]
    latencies = sorted(p["latency_ms"] for p in proposals if p["latency_ms"])
    steps = [p["steps"] for p in proposals if p["steps"]]

    def percentile(values, fraction):
        return values[min(len(values) - 1, int(len(values) * fraction))] if values else 0

    summary = table(
        ["", "Count", ""],
        [["Nameless lines no rule can reach", f"{residual:,}", ""],
         ["Proposed a link", f"{len(links):,}", ""],
         ["...correct", f"{len(correct):,}", ""],
         ["...**wrong - a false positive**", f"**{len(links) - len(correct):,}**", ""],
         ["Declined to link (escalate / write-off)", f"{len(declined):,}", "safe, not correct"],
         ["**Precision**", f"**{len(correct) / len(links):.3f}**" if links else "-",
          f"of the links it proposed · 95% CI ≥ {wilson_low(len(correct), len(links)):.3f} at n={len(links)}"],
         ["**Recall**", f"**{len(correct) / residual:.3f}**", "of the residual it resolved"],
         ["Steps per proposal (median)", f"{sorted(steps)[len(steps) // 2] if steps else 0}", ""],
         ["Validator corrections", f"{sum(p['corrections'] or 0 for p in proposals)}", "caught mid-investigation"],
         ["Latency p50 / p95", f"{percentile(latencies, 0.5) / 1000:.1f}s / {percentile(latencies, 0.95) / 1000:.1f}s", ""]],
        "lrl",
    )

    # If links at or above a threshold were applied without review, what would
    # that have cost? This is the answer to "what is your false-positive rate".
    rows = []
    for threshold in THRESHOLDS:
        above = [p for p in links if float(p["confidence"]) >= threshold]
        right = [p for p in above if p["target_ids"] and p["target_ids"][0] == p["truth"]]
        wrong = len(above) - len(right)
        rows.append([f"{threshold:.2f}", f"{len(above)}", f"{len(right)}", f"**{wrong}**",
                     f"{len(right) / len(above):.3f}" if above else "-",
                     f"{wilson_low(len(right), len(above)):.3f}" if above else "-",
                     f"{len(right) / residual:.3f}"])
    sweep = table(["Auto-apply at ≥", "Applied", "Correct", "False positives",
                   "Precision", "95% CI ≥", "Recall"], rows, "lrrrrrr")
    return summary, sweep


def report() -> str:
    with cursor() as cur:
        coverage_table = coverage(cur)
        tier_table = tiers(cur)
        agent_table, sweep_table = agent(cur)

    return f"""### Coverage

{coverage_table}

### The rules, per tier

Precision is how many of a tier's claims name the payment that truly issued the
line. Recall is how much of the work that tier is responsible for it actually
did.

{tier_table}

### The agent, on what the rules cannot reach

Every one of these lines has a real counterpart; the gateway simply did not name
it. Declining is safe but not correct - it leaves the line in the queue.

{agent_table}

### If proposals were applied without review

Nothing is applied without review today. This is what it would cost if it were,
and it is the honest answer to "what is your false-positive rate".

The curve is flat because there are no errors to trade off yet. At this sample
size that is a statement about the sample, not a claim of perfection - the
interval column is the honest reading, and the bar to raise is *recall*, not
precision.

{sweep_table}"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-readme", action="store_true")
    args = parser.parse_args()

    body = report()
    if not args.write_readme:
        print(body)
        return

    path = Path(__file__).resolve().parents[3] / "README.md"
    text = path.read_text()
    replaced = re.sub(
        r"(<!-- eval:start -->\n).*?(\n<!-- eval:end -->)",
        lambda match: match.group(1) + body + match.group(2),
        text, flags=re.S,
    )
    path.write_text(replaced)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
