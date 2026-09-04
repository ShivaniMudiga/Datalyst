"""Load a gateway payout file into the settlement tables.

The whole file is hashed before anything is written, and the hash is unique on
`settlement_batches`. Re-ingesting the same file is therefore a no-op that says
so rather than a silent double count - which is the first half of the
idempotency story R3 finishes at the point of applying a resolution.

Nothing here interprets the file. Lines land exactly as received; matching is a
separate table, so the received truth is never overwritten.

  python -m packs.recon.ingest payouts/razorpay-2026-07.csv
  python -m packs.recon.ingest payouts/*.csv
"""

from __future__ import annotations

import csv
import sys
from hashlib import sha256
from pathlib import Path

from packs.recon.db import cursor

REQUIRED = {
    "payout_id", "line_seq", "settled_at", "gateway_reference",
    "order_reference", "currency", "gross_minor", "fee_minor", "net_minor", "narration",
}


def _rows(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name} has a header and no lines.")
    return rows


def ingest(path: Path) -> dict:
    """Returns the batch, and whether this call is what created it."""
    file_hash = sha256(path.read_bytes()).hexdigest()

    with cursor(commit=True) as cur:
        cur.execute("SELECT payout_id, line_count FROM settlement_batches WHERE file_hash = %s", (file_hash,))
        seen = cur.fetchone()
        if seen:
            return {**seen, "ingested": False, "reason": "identical file already ingested"}

        rows = _rows(path)
        payout_ids = {row["payout_id"] for row in rows}
        if len(payout_ids) != 1:
            raise ValueError(f"{path.name} mixes payout ids: {sorted(payout_ids)}")
        payout_id = payout_ids.pop()
        gateway = payout_id.rsplit("-", 2)[0]
        currencies = {row["currency"] for row in rows}
        net_total = sum(int(row["net_minor"]) for row in rows)

        # A different file claiming a payout id we already hold is an amendment,
        # not a duplicate. Refuse it here rather than guess; R3 owns amendments.
        cur.execute("SELECT file_name FROM settlement_batches WHERE payout_id = %s", (payout_id,))
        clash = cur.fetchone()
        if clash:
            raise ValueError(
                f"{payout_id} was already ingested from {clash['file_name']} with different "
                f"contents. Amendments are not handled yet."
            )

        cur.execute(
            """
            INSERT INTO settlement_batches
              (payout_id, gateway, payout_date, currency, file_name, file_hash, line_count, net_total_minor)
            VALUES (%s, %s, %s::date, %s, %s, %s, %s, %s)
            """,
            (
                payout_id, gateway, min(row["settled_at"] for row in rows)[:10],
                # The batch currency is the one the payout is denominated in; FX
                # lines inside it are an exception for the matcher, not a second batch.
                "INR" if "INR" in currencies else sorted(currencies)[0],
                path.name, file_hash, len(rows), net_total,
            ),
        )
        cur.executemany(
            """
            INSERT INTO settlement_lines
              (payout_id, line_seq, settled_at, gateway_reference, order_reference,
               currency, gross_minor, fee_minor, net_minor, narration)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    row["payout_id"], int(row["line_seq"]), row["settled_at"],
                    row["gateway_reference"] or None, row["order_reference"] or None,
                    row["currency"], int(row["gross_minor"]), int(row["fee_minor"]),
                    int(row["net_minor"]), row["narration"] or None,
                )
                for row in rows
            ],
        )
        return {"payout_id": payout_id, "line_count": len(rows), "ingested": True,
                "net_total_minor": net_total}


def main() -> None:
    arguments = sys.argv[1:]
    if "--reset" in arguments:
        # Regenerating a file changes its hash, and the old payout id is still
        # held - which ingest correctly refuses. Development needs a way out.
        arguments.remove("--reset")
        with cursor(commit=True) as cur:
            cur.execute("TRUNCATE settlement_batches CASCADE")
        print("settlement tables cleared")

    paths = [Path(argument) for argument in arguments]
    if not paths:
        raise SystemExit("Usage: python -m packs.recon.ingest <file.csv> [...]")
    for path in paths:
        result = ingest(path)
        if result["ingested"]:
            print(f"{path.name}: {result['line_count']} lines, "
                  f"net {result['net_total_minor'] / 100:,.2f}")
        else:
            print(f"{path.name}: skipped - {result['reason']} ({result['payout_id']})")


if __name__ == "__main__":
    main()
