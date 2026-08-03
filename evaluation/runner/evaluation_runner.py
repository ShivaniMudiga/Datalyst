"""
Orchestrate benchmark execution without changing production behavior.

Responsibilities:
- Load benchmarks
- Execute ground-truth SQL using QueryExecutor
- Query the conversational agent
- Compare agent output against expected output
- Calculate metrics
- Write evaluation reports
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from src.executor.query_executor import QueryExecutor
from src.agent.agent import ConversationalAgent

from evaluation.comparator.result_comparator import compare_results
from evaluation.metrics.execution_accuracy import calculate_metrics


class EvaluationRunner:
    def __init__(
        self,
        benchmark_path: str,
        reports_dir: str = "evaluation/reports",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.benchmark_path = benchmark_path
        self.reports_dir = reports_dir
        self.max_retries = max_retries
        self.retry_delay = retry_delay


    def load_benchmarks(self) -> List[Dict[str, Any]]:
        with open(self.benchmark_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def run(self) -> Dict[str, Any]:

        benchmarks = self.load_benchmarks()

        detailed_results: List[Dict[str, Any]] = []

        # Ground truth executor
        gt_executor = QueryExecutor()

        # Dedicated agent instance for evaluation
        agent = ConversationalAgent(thread_id="evaluation-thread")

        for record in benchmarks:

            test_id = record.get("id")
            question = record.get("question")
            ground_sql = record.get("ground_truth_sql", "")

            expected_result = None
            agent_result = None
            match = False
            latency = None
            error = None

            # --------------------------------------------------
            # Execute Ground Truth SQL
            # --------------------------------------------------

            try:
                expected_result = gt_executor.execute(ground_sql)

            except Exception as err:
                error = f"ground_truth_error: {err}"

            # --------------------------------------------------
            # Execute Agent
            # --------------------------------------------------

            evaluation_response = None
            retries_used = 0

            for attempt in range(1, self.max_retries + 1):

                try:
                    evaluation_response = agent.ask_for_evaluation(question)

                    latency = evaluation_response.get("latency")
                    agent_result = evaluation_response.get("execution_result")

                    # Success
                    if (
                        agent_result is not None
                        and evaluation_response.get("error") is None
                    ):
                        retries_used = attempt - 1
                        break

                    print(
                        f"[Retry {attempt}/{self.max_retries}] "
                        f"Test {test_id}: Empty response."
                    )

                except Exception as err:

                    print(
                        f"[Retry {attempt}/{self.max_retries}] "
                        f"Test {test_id}: {err}"
                    )

                    if attempt == self.max_retries:

                        if error:
                            error += " ; "

                        error = (error or "") + f"agent_exception: {err}"

                        break

                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

            # If all retries failed because the model returned an error
            if (
                agent_result is None
                and evaluation_response is not None
                and evaluation_response.get("error")
            ):

                if error:
                    error += " ; "

                error = (error or "") + f"agent_error: {evaluation_response['error']}"

            # --------------------------------------------------
            # Compare Results
            # --------------------------------------------------

            try:

                if (
                    expected_result is not None
                    and agent_result is not None
                ):

                    match = compare_results(
                        expected_result,
                        agent_result,
                        ground_sql,
                    )

                else:
                    match = False

            except Exception as err:

                match = False

                if error:
                    error += " ; "

                error = (error or "") + f"compare_error: {err}"

            # --------------------------------------------------
            # Store Result
            # --------------------------------------------------

            detailed_results.append(
            {
                "test_id": test_id,
                "question": question,
                "expected_result": expected_result,
                "agent_result": agent_result,
                "match": match,
                "latency": latency,
                "retries": retries_used,
                "error": error,
            }
        )

        # ------------------------------------------------------
        # Summary Metrics
        # ------------------------------------------------------

        summary = calculate_metrics(detailed_results)

        # ------------------------------------------------------
        # Write Reports
        # ------------------------------------------------------

        self._write_reports(detailed_results, summary)

        return {
            "detailed": detailed_results,
            "summary": summary,
        }

    def _write_reports(
        self,
        detailed: List[Dict[str, Any]],
        summary: Dict[str, Any],
    ) -> None:

        os.makedirs(self.reports_dir, exist_ok=True)

        detailed_path = os.path.join(
            self.reports_dir,
            "detailed.json",
        )

        summary_path = os.path.join(
            self.reports_dir,
            "summary.json",
        )

        with open(detailed_path, "w", encoding="utf-8") as file:
            json.dump(
                detailed,
                file,
                indent=2,
                default=str,
            )

        with open(summary_path, "w", encoding="utf-8") as file:
            json.dump(
                summary,
                file,
                indent=2,
                default=str,
            )