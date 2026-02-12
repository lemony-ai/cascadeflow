from tests.benchmarks.customer_support import CustomerSupportBenchmark
from tests.benchmarks.gsm8k.gsm8k import GSM8KBenchmark
from tests.benchmarks.humaneval.humaneval import HumanEvalBenchmark
from tests.benchmarks.mmlu.mmlu import MMLUBenchmark
from tests.benchmarks.mtbench.mtbench import MTBenchmark
from tests.benchmarks.truthfulqa import TruthfulQABenchmark


def test_customer_support_load_dataset_returns_question_text() -> None:
    bench = CustomerSupportBenchmark(max_samples=1)
    query, ground_truth = bench.load_dataset()[0]
    assert query == ground_truth["query"]


def test_truthfulqa_load_dataset_returns_question_text() -> None:
    bench = TruthfulQABenchmark(max_samples=1)
    query, ground_truth = bench.load_dataset()[0]
    assert query == ground_truth["question"]


def test_gsm8k_load_dataset_returns_question_text() -> None:
    bench = GSM8KBenchmark(max_samples=1)
    query, ground_truth = bench.load_dataset()[0]
    assert query == ground_truth["question"]


def test_humaneval_load_dataset_returns_prompt_text() -> None:
    bench = HumanEvalBenchmark(max_samples=1)
    query, ground_truth = bench.load_dataset()[0]
    assert query == ground_truth["prompt"]


def test_mmlu_load_dataset_returns_id_for_lookup() -> None:
    bench = MMLUBenchmark(max_samples=1)
    query, ground_truth = bench.load_dataset()[0]
    assert query == ground_truth["id"]


def test_mtbench_load_dataset_returns_conversation_id_for_lookup() -> None:
    bench = MTBenchmark(max_samples=1)
    query, ground_truth = bench.load_dataset()[0]
    assert query == ground_truth["conversation_id"]
