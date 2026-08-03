"""Entry point to run the benchmark evaluation."""
from evaluation.runner.evaluation_runner import EvaluationRunner
def main() -> None:
	runner = EvaluationRunner("evaluation/dataset/benchmark.json", reports_dir="evaluation/reports")
	results = runner.run()
	summary = results.get("summary")

	print("Evaluation complete")
	print(summary)


if __name__ == "__main__":
	main()
