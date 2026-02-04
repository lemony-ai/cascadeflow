"""MMLU (Massive Multitask Language Understanding) Benchmark.

Evaluates CascadeFlow on diverse knowledge tasks across STEM, humanities,
social sciences, and other domains.

MMLU is a 57-subject benchmark testing knowledge and reasoning across:
- STEM: math, physics, chemistry, biology, computer science
- Humanities: history, philosophy, law, ethics
- Social Sciences: economics, psychology, sociology, politics
- Other: business, health, misc

Target: ≥45% cost reduction while maintaining ≥95% of baseline accuracy.
"""

import asyncio
import re
import time
from typing import Any, Optional

from .base import Benchmark, BenchmarkResult, BenchmarkSummary
from .benchmark_config import BenchmarkConfig, BenchmarkMode


class MMLUCategory:
    """MMLU category definitions."""

    STEM = "stem"
    HUMANITIES = "humanities"
    SOCIAL_SCIENCES = "social_sciences"
    OTHER = "other"

    # Mapping of subjects to categories
    SUBJECT_TO_CATEGORY = {
        # STEM
        "mathematics": STEM,
        "physics": STEM,
        "chemistry": STEM,
        "biology": STEM,
        "computer_science": STEM,
        "astronomy": STEM,
        # Humanities
        "history": HUMANITIES,
        "philosophy": HUMANITIES,
        "law": HUMANITIES,
        "ethics": HUMANITIES,
        "world_religions": HUMANITIES,
        # Social Sciences
        "economics": SOCIAL_SCIENCES,
        "psychology": SOCIAL_SCIENCES,
        "sociology": SOCIAL_SCIENCES,
        "political_science": SOCIAL_SCIENCES,
        "geography": SOCIAL_SCIENCES,
        # Other
        "business": OTHER,
        "health": OTHER,
        "marketing": OTHER,
        "management": OTHER,
    }


class MMLUBenchmark(Benchmark):
    """MMLU knowledge benchmark with cascade optimization."""

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o",
        quality_threshold: float = 0.75,
        max_samples: Optional[int] = 40,
        config: Optional[BenchmarkConfig] = None,
    ):
        """
        Initialize MMLU benchmark.

        Args:
            drafter_model: Cost-effective model for initial answers
            verifier_model: High-quality model for verification
            quality_threshold: Threshold for drafter acceptance
            max_samples: Maximum number of questions to test
            config: Full benchmark configuration
        """
        super().__init__(
            name="MMLU",
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            quality_threshold=quality_threshold,
            max_samples=max_samples,
        )
        self.config = config or BenchmarkConfig.for_mmlu()
        self.category_results: dict[str, list[BenchmarkResult]] = {
            MMLUCategory.STEM: [],
            MMLUCategory.HUMANITIES: [],
            MMLUCategory.SOCIAL_SCIENCES: [],
            MMLUCategory.OTHER: [],
        }

    def load_dataset(self) -> list[tuple[str, Any]]:
        """
        Load MMLU dataset with representative questions from each category.

        Returns:
            List of (question_id, question_data) tuples
        """
        # Representative MMLU questions (10 per category = 40 total)
        questions = [
            # ========================================================================
            # STEM (10 questions)
            # ========================================================================
            {
                "id": "mmlu_stem_1",
                "subject": "mathematics",
                "category": MMLUCategory.STEM,
                "question": "What is the derivative of x^3?",
                "choices": ["A. 3x^2", "B. x^2", "C. 3x", "D. x^3"],
                "answer": "A",
            },
            {
                "id": "mmlu_stem_2",
                "subject": "physics",
                "category": MMLUCategory.STEM,
                "question": "What is the SI unit of force?",
                "choices": ["A. Joule", "B. Newton", "C. Watt", "D. Pascal"],
                "answer": "B",
            },
            {
                "id": "mmlu_stem_3",
                "subject": "chemistry",
                "category": MMLUCategory.STEM,
                "question": "What is the chemical symbol for gold?",
                "choices": ["A. Go", "B. Gd", "C. Au", "D. Ag"],
                "answer": "C",
            },
            {
                "id": "mmlu_stem_4",
                "subject": "biology",
                "category": MMLUCategory.STEM,
                "question": "What organelle is responsible for producing ATP in cells?",
                "choices": ["A. Nucleus", "B. Ribosome", "C. Mitochondria", "D. Golgi apparatus"],
                "answer": "C",
            },
            {
                "id": "mmlu_stem_5",
                "subject": "computer_science",
                "category": MMLUCategory.STEM,
                "question": "What is the time complexity of binary search?",
                "choices": ["A. O(n)", "B. O(n^2)", "C. O(log n)", "D. O(1)"],
                "answer": "C",
            },
            {
                "id": "mmlu_stem_6",
                "subject": "mathematics",
                "category": MMLUCategory.STEM,
                "question": "If f(x) = 2x + 3, what is f(5)?",
                "choices": ["A. 10", "B. 13", "C. 8", "D. 15"],
                "answer": "B",
            },
            {
                "id": "mmlu_stem_7",
                "subject": "physics",
                "category": MMLUCategory.STEM,
                "question": "What is the speed of light in a vacuum (approximately)?",
                "choices": ["A. 300,000 km/s", "B. 300,000 m/s", "C. 3,000 km/s", "D. 30,000 km/s"],
                "answer": "A",
            },
            {
                "id": "mmlu_stem_8",
                "subject": "chemistry",
                "category": MMLUCategory.STEM,
                "question": "What is the pH of a neutral solution?",
                "choices": ["A. 0", "B. 7", "C. 14", "D. 1"],
                "answer": "B",
            },
            {
                "id": "mmlu_stem_9",
                "subject": "biology",
                "category": MMLUCategory.STEM,
                "question": "What molecule carries genetic information in most organisms?",
                "choices": ["A. RNA", "B. Protein", "C. DNA", "D. Lipid"],
                "answer": "C",
            },
            {
                "id": "mmlu_stem_10",
                "subject": "computer_science",
                "category": MMLUCategory.STEM,
                "question": "Which data structure uses LIFO (Last In, First Out) principle?",
                "choices": ["A. Queue", "B. Stack", "C. Array", "D. Linked List"],
                "answer": "B",
            },
            # ========================================================================
            # HUMANITIES (10 questions)
            # ========================================================================
            {
                "id": "mmlu_humanities_1",
                "subject": "history",
                "category": MMLUCategory.HUMANITIES,
                "question": "In what year did World War II end?",
                "choices": ["A. 1943", "B. 1944", "C. 1945", "D. 1946"],
                "answer": "C",
            },
            {
                "id": "mmlu_humanities_2",
                "subject": "philosophy",
                "category": MMLUCategory.HUMANITIES,
                "question": "Who wrote 'The Republic'?",
                "choices": ["A. Aristotle", "B. Socrates", "C. Plato", "D. Descartes"],
                "answer": "C",
            },
            {
                "id": "mmlu_humanities_3",
                "subject": "law",
                "category": MMLUCategory.HUMANITIES,
                "question": "What is the principle of 'innocent until proven guilty' called?",
                "choices": [
                    "A. Due process",
                    "B. Presumption of innocence",
                    "C. Habeas corpus",
                    "D. Double jeopardy",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_humanities_4",
                "subject": "ethics",
                "category": MMLUCategory.HUMANITIES,
                "question": "What ethical theory judges actions by their consequences?",
                "choices": [
                    "A. Deontology",
                    "B. Virtue ethics",
                    "C. Consequentialism",
                    "D. Divine command theory",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_humanities_5",
                "subject": "world_religions",
                "category": MMLUCategory.HUMANITIES,
                "question": "What is the holy book of Islam?",
                "choices": ["A. Torah", "B. Bible", "C. Quran", "D. Vedas"],
                "answer": "C",
            },
            {
                "id": "mmlu_humanities_6",
                "subject": "history",
                "category": MMLUCategory.HUMANITIES,
                "question": "Who was the first President of the United States?",
                "choices": [
                    "A. Thomas Jefferson",
                    "B. John Adams",
                    "C. George Washington",
                    "D. Benjamin Franklin",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_humanities_7",
                "subject": "philosophy",
                "category": MMLUCategory.HUMANITIES,
                "question": "What is Descartes' famous philosophical statement?",
                "choices": [
                    "A. 'Knowledge is power'",
                    "B. 'I think, therefore I am'",
                    "C. 'God is dead'",
                    "D. 'The unexamined life is not worth living'",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_humanities_8",
                "subject": "law",
                "category": MMLUCategory.HUMANITIES,
                "question": "What does 'habeas corpus' protect against?",
                "choices": [
                    "A. Self-incrimination",
                    "B. Unlawful detention",
                    "C. Double jeopardy",
                    "D. Unreasonable search",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_humanities_9",
                "subject": "ethics",
                "category": MMLUCategory.HUMANITIES,
                "question": "According to Kant, what should guide moral actions?",
                "choices": [
                    "A. Consequences",
                    "B. Emotions",
                    "C. Duty and universal laws",
                    "D. Self-interest",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_humanities_10",
                "subject": "history",
                "category": MMLUCategory.HUMANITIES,
                "question": "What ancient civilization built the pyramids at Giza?",
                "choices": ["A. Romans", "B. Greeks", "C. Egyptians", "D. Mesopotamians"],
                "answer": "C",
            },
            # ========================================================================
            # SOCIAL SCIENCES (10 questions)
            # ========================================================================
            {
                "id": "mmlu_social_1",
                "subject": "economics",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What does GDP stand for?",
                "choices": [
                    "A. Gross Domestic Product",
                    "B. General Domestic Production",
                    "C. Gross Development Plan",
                    "D. Global Domestic Product",
                ],
                "answer": "A",
            },
            {
                "id": "mmlu_social_2",
                "subject": "psychology",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "Who is known as the father of psychoanalysis?",
                "choices": [
                    "A. Carl Jung",
                    "B. B.F. Skinner",
                    "C. Sigmund Freud",
                    "D. Ivan Pavlov",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_social_3",
                "subject": "sociology",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What term describes the process of learning cultural norms?",
                "choices": [
                    "A. Assimilation",
                    "B. Socialization",
                    "C. Acculturation",
                    "D. Modernization",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_social_4",
                "subject": "political_science",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What is a government ruled by a single person called?",
                "choices": ["A. Democracy", "B. Oligarchy", "C. Autocracy", "D. Theocracy"],
                "answer": "C",
            },
            {
                "id": "mmlu_social_5",
                "subject": "geography",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What is the largest continent by area?",
                "choices": ["A. Africa", "B. North America", "C. Asia", "D. Europe"],
                "answer": "C",
            },
            {
                "id": "mmlu_social_6",
                "subject": "economics",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What is inflation?",
                "choices": [
                    "A. Decrease in prices",
                    "B. Increase in unemployment",
                    "C. General increase in prices",
                    "D. Decrease in GDP",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_social_7",
                "subject": "psychology",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What is classical conditioning associated with?",
                "choices": ["A. Freud", "B. Pavlov", "C. Maslow", "D. Piaget"],
                "answer": "B",
            },
            {
                "id": "mmlu_social_8",
                "subject": "sociology",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "Who wrote 'The Protestant Ethic and the Spirit of Capitalism'?",
                "choices": [
                    "A. Karl Marx",
                    "B. Emile Durkheim",
                    "C. Max Weber",
                    "D. Auguste Comte",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_social_9",
                "subject": "political_science",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What principle divides government into branches?",
                "choices": [
                    "A. Federalism",
                    "B. Separation of powers",
                    "C. Pluralism",
                    "D. Sovereignty",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_social_10",
                "subject": "geography",
                "category": MMLUCategory.SOCIAL_SCIENCES,
                "question": "What is the longest river in the world?",
                "choices": ["A. Amazon", "B. Mississippi", "C. Nile", "D. Yangtze"],
                "answer": "C",
            },
            # ========================================================================
            # OTHER (10 questions)
            # ========================================================================
            {
                "id": "mmlu_other_1",
                "subject": "business",
                "category": MMLUCategory.OTHER,
                "question": "What does ROI stand for?",
                "choices": [
                    "A. Rate of Interest",
                    "B. Return on Investment",
                    "C. Revenue of Industry",
                    "D. Risk of Investment",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_other_2",
                "subject": "health",
                "category": MMLUCategory.OTHER,
                "question": "What vitamin is produced by the body when exposed to sunlight?",
                "choices": ["A. Vitamin A", "B. Vitamin C", "C. Vitamin D", "D. Vitamin B12"],
                "answer": "C",
            },
            {
                "id": "mmlu_other_3",
                "subject": "marketing",
                "category": MMLUCategory.OTHER,
                "question": "What are the 4 P's of marketing?",
                "choices": [
                    "A. Price, Product, Place, Promotion",
                    "B. People, Process, Place, Product",
                    "C. Plan, Price, Promote, Place",
                    "D. Product, People, Process, Promotion",
                ],
                "answer": "A",
            },
            {
                "id": "mmlu_other_4",
                "subject": "management",
                "category": MMLUCategory.OTHER,
                "question": "What management theory emphasizes employee motivation?",
                "choices": [
                    "A. Scientific Management",
                    "B. Human Relations Theory",
                    "C. Bureaucratic Theory",
                    "D. Systems Theory",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_other_5",
                "subject": "business",
                "category": MMLUCategory.OTHER,
                "question": "What is a company's market capitalization?",
                "choices": [
                    "A. Total revenue",
                    "B. Total debt",
                    "C. Share price × Outstanding shares",
                    "D. Net profit",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_other_6",
                "subject": "health",
                "category": MMLUCategory.OTHER,
                "question": "What organ is primarily responsible for filtering blood?",
                "choices": ["A. Heart", "B. Liver", "C. Kidneys", "D. Lungs"],
                "answer": "C",
            },
            {
                "id": "mmlu_other_7",
                "subject": "marketing",
                "category": MMLUCategory.OTHER,
                "question": "What is market segmentation?",
                "choices": [
                    "A. Combining markets",
                    "B. Dividing market into distinct groups",
                    "C. Pricing strategy",
                    "D. Distribution channel",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_other_8",
                "subject": "management",
                "category": MMLUCategory.OTHER,
                "question": "What is SWOT analysis used for?",
                "choices": [
                    "A. Financial planning",
                    "B. Strategic planning",
                    "C. Employee evaluation",
                    "D. Product design",
                ],
                "answer": "B",
            },
            {
                "id": "mmlu_other_9",
                "subject": "business",
                "category": MMLUCategory.OTHER,
                "question": "What is a balance sheet?",
                "choices": [
                    "A. Cash flow statement",
                    "B. Income statement",
                    "C. Statement of assets, liabilities, and equity",
                    "D. Budget forecast",
                ],
                "answer": "C",
            },
            {
                "id": "mmlu_other_10",
                "subject": "health",
                "category": MMLUCategory.OTHER,
                "question": "What is the recommended daily water intake for adults (approximately)?",
                "choices": ["A. 1 liter", "B. 2 liters", "C. 4 liters", "D. 0.5 liters"],
                "answer": "B",
            },
        ]

        return [(q["id"], q) for q in questions[: self.max_samples]]

    def evaluate_prediction(self, prediction: str, ground_truth: Any) -> tuple[bool, float]:
        """
        Evaluate if prediction matches the correct answer.

        Args:
            prediction: Model's response
            ground_truth: Question data with correct answer

        Returns:
            (is_correct, confidence_score)
        """
        try:
            correct_answer = ground_truth["answer"]

            # Extract answer letter from prediction
            predicted_answer = self._extract_answer(prediction)

            if predicted_answer is None:
                return False, 0.0

            # Compare answers
            is_correct = predicted_answer.upper() == correct_answer.upper()

            return is_correct, 1.0 if is_correct else 0.0

        except Exception as e:
            print(f"  Warning: Evaluation error: {e}")
            return False, 0.0

    def _extract_answer(self, text: str) -> Optional[str]:
        """Extract answer letter (A, B, C, or D) from response."""
        # Look for explicit "Answer: X" or "The answer is X"
        patterns = [
            r"(?:answer|choice)[\s:]+is[\s:]+([A-Da-d])",
            r"(?:answer|choice)[\s:]+([A-Da-d])",
            r"^([A-Da-d])[\.\)\s]",
            r"\b([A-Da-d])\s+is\s+(?:correct|the answer)",
            r"(?:select|choose)\s+([A-Da-d])",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).upper()

        # Look for standalone letter at the start or end
        start_match = re.match(r"^\s*([A-Da-d])\b", text)
        if start_match:
            return start_match.group(1).upper()

        # Last resort: find first single letter A-D
        letters = re.findall(r"\b([A-Da-d])\b", text)
        if letters:
            return letters[0].upper()

        return None

    async def run_cascade(self, query: str) -> dict[str, Any]:
        """
        Run cascade on a multiple-choice question.

        Args:
            query: The question ID (question data passed separately)

        Returns:
            Cascade result dict
        """
        # Import here to avoid circular imports
        from cascadeflow import CascadeAgent, ModelConfig

        # Get question data from results lookup
        question_data = None
        for qid, qdata in self.load_dataset():
            if qid == query:
                question_data = qdata
                break

        if question_data is None:
            raise ValueError(f"Question not found: {query}")

        # Format question with choices
        formatted_question = self._format_question(question_data)

        # Create agent with config
        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider="openai", cost=0.00015),
                ModelConfig(name=self.verifier_model, provider="openai", cost=0.0025),
            ],
            quality_threshold=self.quality_threshold,
            enable_domain_detection=self.config.enable_domain_pipeline,
            use_semantic_domains=self.config.enable_semantic_detection,
        )

        # Run with timing
        start_time = time.time()
        result = await agent.run(formatted_question)
        latency_ms = (time.time() - start_time) * 1000

        return {
            "prediction": result.content,
            "model_used": "drafter" if result.model_used == self.drafter_model else "verifier",
            "accepted": result.model_used == self.drafter_model,
            "quality_score": result.metadata.get("quality_score", 0.7),
            "routing_strategy": result.routing_strategy,
            "drafter_cost": result.draft_cost or 0.0,
            "verifier_cost": result.verifier_cost or 0.0,
            "total_cost": result.total_cost,
            "latency_ms": latency_ms,
            "cascadeflow_latency_ms": (
                (result.complexity_detection_ms or 0)
                + (result.metadata.get("domain_detection_ms", 0) if result.metadata else 0)
                + (result.metadata.get("tool_complexity_analysis_ms", 0) if result.metadata else 0)
                + (result.quality_verification_ms or 0)
            ),
            "tokens_input": result.metadata.get("prompt_tokens", 0),
            "tokens_output": result.metadata.get("completion_tokens", 0),
        }

    def _format_question(self, question_data: dict) -> str:
        """Format a multiple-choice question for the model."""
        question = question_data["question"]
        choices = "\n".join(question_data["choices"])

        return f"""Answer the following multiple-choice question. Provide your answer as a single letter (A, B, C, or D).

Question: {question}

{choices}

Answer:"""

    def get_baseline_cost(self, query: str) -> float:
        """
        Calculate cost if using GPT-4o for all questions.

        Args:
            query: Question ID

        Returns:
            Estimated baseline cost
        """
        # MMLU questions are short - ~50 tokens input, ~20 tokens output
        input_tokens = 50
        output_tokens = 20

        # GPT-4o pricing
        input_cost = (input_tokens / 1_000_000) * 2.50
        output_cost = (output_tokens / 1_000_000) * 10.00

        return input_cost + output_cost

    def get_category_summary(self) -> dict[str, dict[str, float]]:
        """Get accuracy breakdown by category."""
        summary = {}

        for category in [
            MMLUCategory.STEM,
            MMLUCategory.HUMANITIES,
            MMLUCategory.SOCIAL_SCIENCES,
            MMLUCategory.OTHER,
        ]:
            cat_results = self.category_results.get(category, [])
            if cat_results:
                correct = sum(1 for r in cat_results if r.is_correct)
                accuracy = correct / len(cat_results) * 100
                summary[category] = {
                    "total": len(cat_results),
                    "correct": correct,
                    "accuracy": accuracy,
                }

        return summary


async def run_mmlu_benchmark(
    config: Optional[BenchmarkConfig] = None,
    max_samples: int = 40,
) -> BenchmarkSummary:
    """
    Run MMLU benchmark with specified configuration.

    Args:
        config: Benchmark configuration (default: full mode)
        max_samples: Maximum questions to test

    Returns:
        BenchmarkSummary with results
    """
    import os

    print("\n" + "=" * 80)
    print("MMLU: MASSIVE MULTITASK LANGUAGE UNDERSTANDING BENCHMARK")
    print("=" * 80 + "\n")

    # Verify API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return None

    config = config or BenchmarkConfig.for_mmlu()

    print("Configuration:")
    print(f"  Mode: {config.mode.value}")
    print(f"  Drafter: {config.default_drafter}")
    print(f"  Verifier: {config.default_verifier}")
    print(f"  Quality Threshold: {config.default_quality_threshold}")
    print(f"  Semantic Detection: {config.enable_semantic_detection}")
    print(f"  Domain Pipeline: {config.enable_domain_pipeline}")
    print(f"  Max Samples: {max_samples}\n")

    # Create benchmark
    benchmark = MMLUBenchmark(
        drafter_model=config.default_drafter,
        verifier_model=config.default_verifier,
        quality_threshold=config.default_quality_threshold,
        max_samples=max_samples,
        config=config,
    )

    # Run benchmark
    print("Running benchmark...\n")
    summary = await benchmark.run()

    # Category breakdown
    print("\nCategory Breakdown:")
    for category, stats in benchmark.get_category_summary().items():
        print(f"  {category}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.1f}%)")

    return summary


if __name__ == "__main__":
    asyncio.run(run_mmlu_benchmark())
