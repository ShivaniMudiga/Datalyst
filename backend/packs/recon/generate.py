"""Produce the payout file a gateway would send, from what kartly captured.

Run it for a month and a gateway and it writes two things:

  payouts/<gateway>-<month>.csv   the file an operations person receives
  recon_labels                    what the right answer was, per line

The labels are the point. Generating the file from the ledger means the truth
is known by construction, so R4 can report precision and recall without anyone
hand-labelling three thousand rows. The matcher never reads that table.

  python -m packs.recon.generate --month 2026-07
  python -m packs.recon.generate --month 2026-07 --gateway razorpay
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import timedelta
from pathlib import Path

from packs.recon.db import cursor
from packs.recon.defects import (
    ORDER_REFERENCE_RATE,
    ORPHAN_GATEWAY_RATE,
    SETTLEMENT_LAG_DAYS,
    USD_PER_INR,
    classify,
    drift,
    rnd,
)

GATEWAYS = ("razorpay", "payu", "cashfree")
OUT_DIR = Path(__file__).resolve().parents[3] / "payouts"
COLUMNS = [
    "payout_id", "line_seq", "settled_at", "gateway_reference",
    "order_reference", "currency", "gross_minor", "fee_minor", "net_minor",
]


def _minor(rupees) -> int:
    """Rupees as numeric -> paise as int. Money stops being a float here."""
    return int(round(float(rupees) * 100))


def _captured(gateway: str, month: str) -> list[dict]:
    with cursor() as cur:
        cur.execute(
            """
            SELECT payment_id, order_id, gateway_reference, amount, gateway_fee, captured_at
            FROM payments
            WHERE payment_status = 'captured'
              AND gateway = %s
              AND to_char(captured_at, 'YYYY-MM') = %s
            ORDER BY captured_at, payment_id
            """,
            (gateway, month),
        )
        return cur.fetchall()


def _lines_for(payment: dict, defect: str) -> list[dict]:
    """The settlement lines one captured payment turns into. Usually exactly one."""
    payment_id = payment["payment_id"]
    gross = _minor(payment["amount"])
    fee = _minor(payment["gateway_fee"])
    settled = payment["captured_at"] + timedelta(days=SETTLEMENT_LAG_DAYS)
    reference = payment["gateway_reference"]
    order_reference = f"KTLY-{payment['order_id']}"
    currency = "INR"

    if rnd(f"orderref:{payment_id}") > ORDER_REFERENCE_RATE or defect == "ref_drift":
        # A drifted reference with the order id still attached would be a free
        # win for the matcher; these are the lines that have to be earned.
        order_reference = None

    if defect == "ref_drift":
        reference = drift(reference, payment_id)
    elif defect == "date_skew":
        settled += timedelta(days=1 + int(rnd(f"skew:{payment_id}") * 3))
    elif defect == "fee_residual":
        # The gateway kept a few extra basis points. Gross and net no longer
        # agree with the fee we recorded, and only a tolerance band catches it.
        fee += max(1, int(gross * (0.0004 + rnd(f"bps:{payment_id}") * 0.0016)))
    elif defect == "fx":
        gross = int(round(gross * USD_PER_INR))
        fee = int(round(fee * USD_PER_INR))
        currency = "USD"

    base = {
        "settled_at": settled,
        "gateway_reference": reference,
        "order_reference": order_reference,
        "currency": currency,
    }

    if defect != "split":
        return [{**base, "gross_minor": gross, "fee_minor": fee, "net_minor": gross - fee}]

    # Split: the payout arrives in parts that sum to the capture. Any single
    # part matches nothing on its own, which is exactly what T2 is for.
    parts = 2 if rnd(f"parts:{payment_id}") < 0.7 else 3
    cuts = sorted(rnd(f"cut:{payment_id}:{i}") for i in range(parts - 1))
    edges = [0.0, *cuts, 1.0]
    lines, spent_gross, spent_fee = [], 0, 0
    for index in range(parts):
        last = index == parts - 1
        part_gross = gross - spent_gross if last else max(1, int(gross * (edges[index + 1] - edges[index])))
        part_fee = fee - spent_fee if last else int(fee * (edges[index + 1] - edges[index]))
        spent_gross += part_gross
        spent_fee += part_fee
        lines.append({
            **base,
            "settled_at": base["settled_at"] + timedelta(days=index),
            "gross_minor": part_gross,
            "fee_minor": part_fee,
            "net_minor": part_gross - part_fee,
        })
    return lines


def _orphans(gateway: str, month: str, count: int, seed: int) -> list[dict]:
    """Lines with no counterpart anywhere in the ledger. A real exception."""
    prefix = {"razorpay": "pay_", "payu": "PU", "cashfree": "CF-"}[gateway]
    year, mon = (int(part) for part in month.split("-"))
    out = []
    for index in range(count):
        key = f"orphan:{gateway}:{month}:{index}:{seed}"
        gross = 10000 + int(rnd(key) * 900000)
        fee = int(gross * 0.0177)
        day = 1 + int(rnd(key + ":day") * 27)
        out.append({
            "settled_at": f"{year:04d}-{mon:02d}-{day:02d} 04:30:00+00",
            "gateway_reference": prefix + f"{int(rnd(key + ':ref') * 1e14):014X}"[:14],
            "order_reference": None,
            "currency": "INR",
            "gross_minor": gross,
            "fee_minor": fee,
            "net_minor": gross - fee,
        })
    return out


def generate(gateway: str, month: str) -> dict:
    payments = _captured(gateway, month)
    if not payments:
        raise SystemExit(f"No captured {gateway} payments in {month}.")

    payout_id = f"{gateway}-{month}"
    rows, labels, counts = [], [], Counter()
    # A payment that was never settled has a label and no line, so it cannot
    # live in the list that runs parallel to `rows` - keeping it there silently
    # shifted every label after the first orphan onto the wrong line.
    never_settled = []

    for payment in payments:
        defect = classify(payment["payment_id"])
        counts[defect] += 1
        if defect == "orphan_ledger":
            never_settled.append(payment["payment_id"])
            continue
        for line in _lines_for(payment, defect):
            rows.append(line)
            labels.append((payment["payment_id"], defect))

    orphan_count = int(len(rows) * ORPHAN_GATEWAY_RATE)
    for line in _orphans(gateway, month, orphan_count, len(rows)):
        rows.append(line)
        labels.append((None, "orphan_gateway"))
        counts["orphan_gateway"] += 1

    # A payout file arrives in settlement order, not in the order we happened to
    # build it - otherwise every split sits conveniently adjacent.
    order = sorted(range(len(rows)), key=lambda i: (str(rows[i]["settled_at"]), rnd(f"seq:{payout_id}:{i}")))
    rows = [rows[i] for i in order]
    labels = [labels[i] for i in order]
    assert len(rows) == len(labels), "every line must carry exactly one label"

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"{payout_id}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for seq, row in enumerate(rows, start=1):
            writer.writerow({**row, "payout_id": payout_id, "line_seq": seq})

    with cursor(commit=True) as cur:
        cur.execute("DELETE FROM recon_labels WHERE payout_id = %s", (payout_id,))
        cur.execute(
            "DELETE FROM recon_labels WHERE payout_id IS NULL AND payment_id = ANY(%s)",
            ([p["payment_id"] for p in payments],),
        )
        cur.executemany(
            "INSERT INTO recon_labels (payout_id, line_seq, payment_id, defect_class) VALUES (%s, %s, %s, %s)",
            [(payout_id, seq, pay, cls) for seq, (pay, cls) in enumerate(labels, start=1)]
            + [(None, None, pay, "orphan_ledger") for pay in never_settled],
        )

    return {"path": path, "payments": len(payments), "lines": len(rows), "defects": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--gateway", default="all", choices=("all", *GATEWAYS))
    args = parser.parse_args()

    gateways = GATEWAYS if args.gateway == "all" else (args.gateway,)
    for gateway in gateways:
        result = generate(gateway, args.month)
        clean = result["defects"]["clean"]
        print(f"{result['path'].name}: {result['lines']} lines from {result['payments']} payments")
        print(f"  clean {clean} ({clean / result['payments']:.1%})", end="")
        for name, count in sorted(result["defects"].items()):
            if name != "clean":
                print(f" · {name} {count}", end="")
        print()


if __name__ == "__main__":
    main()
