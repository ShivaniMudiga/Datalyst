"""Compute execution-accuracy metrics from detailed test results."""
from typing import Iterable, Mapping


def calculate_metrics(detailed_results: Iterable[Mapping]) -> dict:
	"""Compute summary metrics from `detailed_results`.

	Each item in `detailed_results` is expected to include at least:
	- `match` (bool)
	- `latency` (float)
	- `error` (nullable)
	"""
	total = 0
	passed = 0
	total_latency = 0.0

	for r in detailed_results:
		total += 1
		if r.get("match"):
			passed += 1
		latency = r.get("latency") or 0.0
		try:
			total_latency += float(latency)
		except Exception:
			pass

	failed = total - passed
	accuracy = (passed / total * 100.0) if total else 0.0
	average_latency = (total_latency / total) if total else 0.0

	return {
		"total_tests": total,
		"passed": passed,
		"failed": failed,
		"execution_accuracy": round(accuracy, 2),
		"average_latency": round(average_latency, 4),
	}

