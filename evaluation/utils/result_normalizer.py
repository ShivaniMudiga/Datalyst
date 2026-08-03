"""Normalize SQL execution results into deterministic comparable structures.

Responsibilities:
- Convert database row tuples to lists
- Convert Decimal to float
- Convert datetime/date/time to ISO strings
- Convert bytes to utf-8 strings
- Produce order-insensitive deterministic representations for row sets
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterable, List
import json


def _normalize_value(value: Any) -> Any:
	"""Normalize a single atomic value."""
	if value is None:
		return None
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, (datetime, date, time)):
		return value.isoformat()
	if isinstance(value, bytes):
		try:
			return value.decode("utf-8")
		except Exception:
			return str(value)
	if isinstance(value, (list, tuple)):
		return [_normalize_value(v) for v in value]
	if isinstance(value, dict):
		return {k: _normalize_value(v) for k, v in sorted(value.items())}
	# basic types (int, float, str, bool)
	return value


def normalize_result(result: Any) -> Any:
	"""Normalize a full SQL execution result.

	Typical inputs:
	- List[tuple] (rows from cursor.fetchall())
	- Dict (status messages)
	- Scalar values

	Returns a deterministic structure suitable for comparison.
	For row sets, returns a list of rows where each row is a list of
	normalized values. The overall list is sorted deterministically by
	the JSON representation of rows to make comparison order-insensitive.
	"""
	# Row set (list-like)
	if isinstance(result, Iterable) and not isinstance(result, (str, bytes, dict)):
		# Materialize iterable
		rows = list(result)
		# If rows are empty, return empty list
		if not rows:
			return []

		normalized_rows: List[Any] = []
		for row in rows:
			if isinstance(row, dict):
				# Normalize dict row with sorted keys
				normalized = {k: _normalize_value(v) for k, v in sorted(row.items())}
			elif isinstance(row, (list, tuple)):
				normalized = [_normalize_value(v) for v in row]
			else:
				# Single-value row
				normalized = _normalize_value(row)
			normalized_rows.append(normalized)

		# To ignore ordering, produce a sorted list by JSON representation
		try:
			row_strings = [json.dumps(r, sort_keys=True, default=str) for r in normalized_rows]
			row_strings.sort()
			return [json.loads(s) for s in row_strings]
		except TypeError:
			# Fallback: return the raw normalized rows
			return normalized_rows

	# Dict -> normalize values and sort keys
	if isinstance(result, dict):
		return {k: _normalize_value(v) for k, v in sorted(result.items())}

	# Scalar
	return _normalize_value(result)


def rows_multiset_key(rows: Iterable[Any]) -> Counter:
	"""Return a Counter keyed by JSON representation of rows.

	Useful for multiset comparisons.
	"""
	rows_list = list(rows)
	row_strings = [json.dumps(r, sort_keys=True, default=str) for r in rows_list]
	return Counter(row_strings)
