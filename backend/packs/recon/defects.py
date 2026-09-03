"""What goes wrong between a captured payment and the payout file that reports it.

Every class here is a real reconciliation failure mode, and every one of them
is aimed at a matcher tier (R2). Injecting them deliberately is what makes the
match rate in R4 a measurement rather than a claim: the generator knows the
right answer for every line it writes, so precision and recall fall out of the
data instead of out of hand-labelling.

Rates are per captured payment and are read once, at the top, so the whole
distribution is visible in one place.
"""

from __future__ import annotations

from hashlib import md5

# Deliberate defect rates. `clean` is the remainder.
RATES: dict[str, float] = {
    "ref_drift": 0.030,     # the reference comes back mangled          -> T1
    "date_skew": 0.020,     # settled later than T+2                    -> T1
    "split": 0.015,         # one capture paid out over 2-3 lines       -> T2
    "fee_residual": 0.012,  # net is off by a few basis points          -> T3
    "fx": 0.004,            # settled in USD, amounts do not equal INR  -> T3
    "orphan_ledger": 0.008, # captured, never settled       -> a real exception
}

# Extra invented lines with no counterpart at all, as a share of real lines.
ORPHAN_GATEWAY_RATE = 0.004

# The share of lines the gateway bothers to echo the merchant's order id on.
# Real payout files are inconsistent about this, and it is why T0 leans on the
# gateway's own reference instead.
ORDER_REFERENCE_RATE = 0.65

SETTLEMENT_LAG_DAYS = 2
USD_PER_INR = 0.0120


def rnd(key: str) -> float:
    """Deterministic 0..1 from a string, so a regenerated file is byte-identical.

    Mirrors the `rnd(text)` helper the kartly seed uses, which is dropped by
    `04_grants.sql` and so is not available to us in SQL.
    """
    return int(md5(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def classify(payment_id: int) -> str:
    """Which defect, if any, this payment's settlement carries."""
    roll = rnd(f"defect:{payment_id}")
    ceiling = 0.0
    for name, rate in RATES.items():
        ceiling += rate
        if roll < ceiling:
            return name
    return "clean"


def drift(reference: str, payment_id: int) -> str:
    """Mangle a reference the way a real file does: case, separators, prefixes.

    Always returns something different from what went in. Two of these variants
    are no-ops on a reference with no separator - payu's, for one - and a
    `ref_drift` line that is not actually drifted would be scored as a T0 miss
    that never happened. Lowercasing is the fallback because every prefix here
    carries upper-case hex.
    """
    which = int(rnd(f"drift:{payment_id}") * 4)
    if which == 1:
        drifted = reference.replace("_", "").replace("-", "")
    elif which == 2:
        drifted = f" {reference} "
    elif which == 3:
        drifted = reference.split("_")[-1].split("-")[-1]
    else:
        drifted = reference.lower()
    return drifted if drifted != reference else reference.lower()
