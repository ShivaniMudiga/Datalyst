"""
Compare expected and agent SQL execution results.

Comparison philosophy:
- Compare returned DATA, not SQL syntax.
- Ignore additional columns returned by the agent.
- Ignore column names completely.
- Ignore row ordering unless the SQL explicitly requires it.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from evaluation.utils.result_normalizer import normalize_result


ORDER_SENSITIVE_KEYWORDS = (
    "ORDER BY",
    "LIMIT",
    "OFFSET",
    "FETCH",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
)


def _row_values(row: Any) -> tuple:
    """
    Convert a row into a comparable tuple of values.
    """

    if isinstance(row, dict):
        return tuple(row.values())

    if isinstance(row, (list, tuple)):
        return tuple(row)

    return (row,)


def _contains_expected_values(expected_row, actual_row) -> bool:
    """
    Returns True if every expected value exists in the actual row.

    Extra values in the actual row are ignored.
    """

    actual_values = list(_row_values(actual_row))

    for value in _row_values(expected_row):

        if value not in actual_values:
            return False

        # Remove matched value so duplicates work correctly.
        actual_values.remove(value)

    return True


def _order_matters(sql: str) -> bool:
    sql = sql.upper()

    return any(
        keyword in sql
        for keyword in ORDER_SENSITIVE_KEYWORDS
    )


def compare_results(
    expected: Any,
    actual: Any,
    ground_truth_sql: str,
) -> bool:

    expected = normalize_result(expected)
    actual = normalize_result(actual)

    # ---------------------------------------------------
    # Scalar / Dict comparison
    # ---------------------------------------------------

    if not isinstance(expected, list):
        return expected == actual

    if not isinstance(actual, list):
        return False

    # Different number of rows.
    if len(expected) != len(actual):
        return False

    # ---------------------------------------------------
    # ORDER MATTERS
    # ---------------------------------------------------

    if _order_matters(ground_truth_sql):

        for expected_row, actual_row in zip(expected, actual):

            if not _contains_expected_values(expected_row, actual_row):
                return False

        return True

    # ---------------------------------------------------
    # ORDER DOES NOT MATTER
    # ---------------------------------------------------

    unmatched_actual = list(actual)

    for expected_row in expected:

        found = False

        for i, actual_row in enumerate(unmatched_actual):

            if _contains_expected_values(expected_row, actual_row):
                found = True
                unmatched_actual.pop(i)
                break

        if not found:
            return False

    return True