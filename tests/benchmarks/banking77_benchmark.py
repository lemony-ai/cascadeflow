"""Banking77: Full Intent Classification Benchmark

Evaluates CascadeFlow on the complete Banking77 dataset from HuggingFace.
Banking77 contains 13,083 customer queries across 77 fine-grained banking intents.

Dataset: https://huggingface.co/datasets/PolyAI/banking77

The 77 intents cover:
- Card operations (activate, lost, stolen, freeze, delivery)
- Payments (pending, failed, declined, wrong amount)
- Transfers (domestic, international, timing, fees)
- Account management (close, verify identity, edit details)
- ATM operations and cash handling
- Fees, charges, and exchange rates
- Top-ups and balance inquiries
- Security and fraud concerns

Research Questions:
- Can cascade systems accurately classify banking intents?
- What cost savings are achievable on intent classification?
- How does drafter perform vs verifier on financial queries?
- Does query complexity correlate with model routing?
"""

import asyncio
import os
from typing import Any, Optional

from cascadeflow.config import ModelConfig
from cascadeflow.quality import QualityConfig

from cascadeflow.agent import CascadeAgent

from .base import Benchmark, BenchmarkResult, BenchmarkSummary

# Banking77 intent labels (all 77)
BANKING77_LABELS = [
    "activate_my_card",
    "age_limit",
    "apple_pay_or_google_pay",
    "atm_support",
    "automatic_top_up",
    "balance_not_updated_after_bank_transfer",
    "balance_not_updated_after_cheque_or_cash_deposit",
    "beneficiary_not_allowed",
    "cancel_transfer",
    "card_about_to_expire",
    "card_acceptance",
    "card_arrival",
    "card_delivery_estimate",
    "card_linking",
    "card_not_working",
    "card_payment_fee_charged",
    "card_payment_not_recognised",
    "card_payment_wrong_exchange_rate",
    "card_swallowed",
    "cash_withdrawal_charge",
    "cash_withdrawal_not_recognised",
    "change_pin",
    "compromised_card",
    "contactless_not_working",
    "country_support",
    "declined_card_payment",
    "declined_cash_withdrawal",
    "declined_transfer",
    "direct_debit_payment_not_recognised",
    "disposable_card_limits",
    "edit_personal_details",
    "exchange_charge",
    "exchange_rate",
    "exchange_via_app",
    "extra_charge_on_statement",
    "failed_transfer",
    "fiat_currency_support",
    "get_disposable_virtual_card",
    "get_physical_card",
    "getting_spare_card",
    "getting_virtual_card",
    "lost_or_stolen_card",
    "lost_or_stolen_phone",
    "order_physical_card",
    "passcode_forgotten",
    "pending_card_payment",
    "pending_cash_withdrawal",
    "pending_top_up",
    "pending_transfer",
    "pin_blocked",
    "receiving_money",
    "refund_not_showing_up",
    "request_refund",
    "reverted_card_payment",
    "supported_cards_and_currencies",
    "terminate_account",
    "top_up_by_bank_transfer_charge",
    "top_up_by_card_charge",
    "top_up_by_cash_or_cheque",
    "top_up_failed",
    "top_up_limits",
    "top_up_reverted",
    "topping_up_by_card",
    "transaction_charged_twice",
    "transfer_fee_charged",
    "transfer_into_account",
    "transfer_not_received_by_recipient",
    "transfer_timing",
    "unable_to_verify_identity",
    "verify_my_identity",
    "verify_source_of_funds",
    "verify_top_up",
    "virtual_card_not_working",
    "visa_or_mastercard",
    "why_verify_identity",
    "wrong_amount_of_cash_received",
    "wrong_exchange_rate_for_cash_withdrawal",
]


class Banking77Benchmark(Benchmark):
    """Banking77 intent classification benchmark using HuggingFace dataset."""

    def __init__(
        self,
        drafter_model: str = "claude-haiku-4-5-20251001",
        verifier_model: str = "claude-opus-4-5-20251101",
        drafter_provider: str = "anthropic",
        verifier_provider: str = "anthropic",
        quality_threshold: float = 0.7,
        max_samples: Optional[int] = None,  # None = full dataset
        split: str = "test",  # "train" or "test"
    ):
        """Initialize Banking77 benchmark.

        Args:
            drafter_model: Cheap model for drafting
            verifier_model: Premium model for verification
            drafter_provider: Provider for drafter model
            verifier_provider: Provider for verifier model
            quality_threshold: Cascade quality threshold
            max_samples: Max samples to run (None = all)
            split: Dataset split to use ("train" or "test")
        """
        self.split = split
        self.drafter_provider = drafter_provider
        self.verifier_provider = verifier_provider
        super().__init__(
            name=f"Banking77-{split}",
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            quality_threshold=quality_threshold,
            max_samples=max_samples,
        )

    def get_baseline_cost(self, query: str) -> float:
        """
        Calculate baseline cost using actual verifier model pricing.

        Claude Opus 4.5: $15.00 per 1M input, $75.00 per 1M output

        Args:
            query: Input query (used to estimate token count)

        Returns:
            Estimated cost in USD
        """
        # Estimate tokens: ~1000 input (prompt + 77 intents), ~100 output
        input_tokens = 1000
        output_tokens = 100
        # Claude Opus 4.5 pricing
        input_cost = (input_tokens / 1_000_000) * 15.00
        output_cost = (output_tokens / 1_000_000) * 75.00
        return input_cost + output_cost

    def load_dataset(self) -> list[tuple[str, Any]]:
        """
        Load Banking77 dataset from HuggingFace.

        Returns:
            List of (query_id, query_data) tuples
        """
        import os as _os
        import tempfile
        import urllib.request

        print(f"  Loading Banking77 dataset ({self.split} split) from HuggingFace...")

        # Download from HuggingFace's converted parquet branch
        parquet_url = f"https://huggingface.co/datasets/PolyAI/banking77/resolve/refs%2Fconvert%2Fparquet/default/{self.split}/0000.parquet"

        try:
            print("  Downloading parquet from HuggingFace...")
            # Download to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".parquet")
            urllib.request.urlretrieve(parquet_url, temp_file.name)

            # Read parquet file
            try:
                import pandas as pd

                df = pd.read_parquet(temp_file.name)
            except ImportError:
                # Try pyarrow directly
                import pyarrow.parquet as pq

                table = pq.read_table(temp_file.name)
                df = table.to_pandas()

            # Clean up temp file
            _os.unlink(temp_file.name)

            queries = []
            for idx, row in df.iterrows():
                label = int(row["label"])
                text = row["text"]
                query_data = {
                    "query_id": f"B77/{self.split}/{idx}",
                    "text": text,
                    "label": label,
                    "intent": BANKING77_LABELS[label],
                }
                # Return (query_text, ground_truth) - base class passes query_text to run_cascade
                queries.append((text, query_data))

            print(f"  Loaded {len(queries)} queries")

            if self.max_samples:
                queries = queries[: self.max_samples]
                print(f"  Limited to {len(queries)} samples")

            return queries

        except Exception as e:
            import traceback

            print(f"  Error loading parquet: {e}")
            traceback.print_exc()
            return []

    def evaluate_prediction(self, prediction: str, ground_truth: Any) -> tuple[bool, float]:
        """
        Evaluate intent classification accuracy.

        The model is asked to classify the query intent. We check if the
        predicted intent matches the ground truth.

        Args:
            prediction: Model's response (should contain intent classification)
            ground_truth: Query data with correct intent label

        Returns:
            (is_correct, confidence_score)
        """
        try:
            if not prediction or len(prediction.strip()) < 5:
                return False, 0.0

            prediction_lower = prediction.lower()
            correct_intent = ground_truth["intent"].lower().replace("_", " ")

            # Check if correct intent is mentioned
            # Handle both underscore and space formats
            intent_variants = [
                correct_intent,
                ground_truth["intent"].lower(),
                correct_intent.replace(" ", "_"),
            ]

            is_correct = any(variant in prediction_lower for variant in intent_variants)

            # Calculate confidence based on response quality
            # Higher confidence if response is focused and contains the intent
            if is_correct:
                # Bonus for concise, focused responses
                if len(prediction) < 200:
                    confidence = 0.95
                elif len(prediction) < 500:
                    confidence = 0.85
                else:
                    confidence = 0.75
            else:
                # Check if any other intent is strongly present
                other_intents_found = sum(
                    1
                    for intent in BANKING77_LABELS
                    if intent.lower().replace("_", " ") in prediction_lower
                    and intent != ground_truth["intent"]
                )
                confidence = max(0.1, 0.4 - (other_intents_found * 0.1))

            return is_correct, confidence

        except Exception as e:
            print(f"  Warning: Evaluation error: {e}")
            return False, 0.0

    async def run_cascade(self, query: str) -> dict[str, Any]:
        """
        Run cascade on a banking intent classification query.

        Uses 2-model cascade with domain detection enabled.
        The prompt includes all 77 intents and asks for brief reasoning
        to improve alignment scoring for classification tasks.

        Args:
            query: Banking customer query

        Returns:
            Cascade result dict
        """
        import time as _time

        # Build list of all 77 intents for the prompt
        intent_list = "\n".join(f"- {intent}" for intent in BANKING77_LABELS)

        # Classification prompt with all intents listed and reasoning requested
        # Asking for reasoning helps alignment scoring work better
        classification_prompt = f"""Classify this banking customer query into one of the 77 banking intents listed below.

Query: "{query}"

Available intents:
{intent_list}

Instructions:
1. Briefly explain why you chose this intent (1 sentence)
2. Output the exact intent name from the list above

Format your response as:
Reasoning: [your brief explanation]
Intent: [exact_intent_name]"""

        # Use 2-model cascade with domain detection DISABLED
        # Domain detection misclassifies intent classification as "data" domain
        # with 0.80 threshold, causing all drafts to be rejected.
        # Cross-provider cascade: GPT-4o-mini (OpenAI) -> Claude Sonnet 4.5 (Anthropic)
        #
        # Classification tasks need lenient confidence thresholds since:
        # 1. Responses are short (just intent + reasoning)
        # 2. Complexity often detected as "hard" due to 77 categories
        # 3. Alignment scoring already handles classification format (v11)
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name=self.drafter_model,
                    provider=self.drafter_provider,
                    cost=0.003,  # $3/M blended (Haiku 4.5: $1 in, $5 out)
                ),
                ModelConfig(
                    name=self.verifier_model,
                    provider=self.verifier_provider,
                    cost=0.045,  # $45/M blended (Opus 4.5: $15 in, $75 out)
                ),
            ],
            enable_cascade=True,
            enable_domain_detection=False,  # Disabled - causes misclassification
            use_semantic_domains=False,  # Disabled - use standard thresholds
            quality_config=QualityConfig(
                # Lenient thresholds for classification tasks
                confidence_thresholds={
                    "trivial": 0.55,
                    "simple": 0.55,
                    "moderate": 0.55,
                    "hard": 0.55,
                    "expert": 0.55,
                },
                # Short responses are expected for classification
                min_length_thresholds={
                    "trivial": 10,
                    "simple": 10,
                    "moderate": 15,
                    "hard": 15,
                    "expert": 20,
                },
            ),
        )

        # CRITICAL: Patch the PreRouter to cascade ALL complexity levels
        # By default, PreRouter routes "hard" and "expert" directly to verifier
        # For classification benchmarks, we want all queries to go through cascade
        from cascadeflow.quality.complexity import QueryComplexity

        agent.router.cascade_complexities = [
            QueryComplexity.TRIVIAL,
            QueryComplexity.SIMPLE,
            QueryComplexity.MODERATE,
            QueryComplexity.HARD,
            QueryComplexity.EXPERT,
        ]

        start_time = _time.time()
        result = await agent.run(classification_prompt)
        latency_ms = (_time.time() - start_time) * 1000

        # Convert CascadeResult to expected dict format
        prompt_tokens = result.metadata.get("prompt_tokens", 0)
        completion_tokens = result.metadata.get("completion_tokens", 0)

        return {
            "prediction": result.content,
            "model_used": result.model_used,
            "accepted": result.draft_accepted,
            "quality_score": result.quality_score,
            "drafter_cost": result.draft_cost,
            "verifier_cost": result.verifier_cost,
            "total_cost": result.total_cost,
            "latency_ms": latency_ms,
            "tokens_input": prompt_tokens,
            "tokens_output": completion_tokens,
        }


async def run_banking77_benchmark(
    max_samples: Optional[int] = None, split: str = "test"
) -> BenchmarkSummary:
    """Run Banking77 benchmark and generate report.

    Args:
        max_samples: Maximum samples to run (None = full dataset)
        split: Dataset split ("train" = 10,003 samples, "test" = 3,080 samples)
    """

    print("\n" + "=" * 80)
    print("BANKING77: FULL INTENT CLASSIFICATION BENCHMARK")
    print("=" * 80 + "\n")

    # Verify API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        return None

    sample_desc = f"{max_samples} samples" if max_samples else f"full {split} set"
    print("Configuration:")
    print(f"  Dataset:         Banking77 ({sample_desc})")
    print(f"  Split:           {split}")
    print("  Drafter:         claude-haiku-4-5-20251001 (Anthropic)")
    print("  Verifier:        claude-opus-4-5-20251101 (Anthropic)")
    print("  Quality Thresh:  0.7")
    print("  Task:            77-way intent classification")
    print()

    benchmark = Banking77Benchmark(
        drafter_model="claude-haiku-4-5-20251001",
        verifier_model="claude-opus-4-5-20251101",
        drafter_provider="anthropic",
        verifier_provider="anthropic",
        quality_threshold=0.7,
        max_samples=max_samples,
        split=split,
    )

    summary = await benchmark.run()

    # Print detailed summary
    print("\n" + "=" * 80)
    print("BANKING77 BENCHMARK RESULTS")
    print("=" * 80)

    print(f"\nTotal Queries: {summary.total_tests}")
    print(f"Accuracy: {summary.accuracy:.1f}%")
    print(f"Cost Savings: {summary.avg_savings_pct:.1f}%")
    print(f"Drafter Acceptance Rate: {summary.acceptance_rate_pct:.1f}%")

    print("\nCost Breakdown:")
    print(f"  Cascade Cost: ${summary.total_cost:.4f}")
    print(f"  Baseline Cost: ${summary.total_baseline_cost:.4f}")
    print(f"  Savings: ${summary.total_savings:.4f}")

    print("\nRouting Analysis:")
    print(
        f"  Drafter Only: {summary.drafter_accepted}/{summary.total_tests} ({summary.acceptance_rate_pct:.1f}%)"
    )
    print(
        f"  Verifier Used: {summary.escalated_to_verifier}/{summary.total_tests} ({summary.escalation_rate_pct:.1f}%)"
    )

    # Analyze accuracy by model used
    print("\nAccuracy by Model:")
    print(f"  Drafter:  {summary.drafter_accuracy:.1f}%")
    print(f"  Verifier: {summary.verifier_accuracy:.1f}%")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Banking77 benchmark")
    parser.add_argument("--max", type=int, default=None, help="Max samples (default: all)")
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        choices=["train", "test"],
        help="Dataset split (default: test)",
    )
    parser.add_argument("--full", action="store_true", help="Run full test set (3,080 samples)")

    args = parser.parse_args()

    max_samples = None if args.full else args.max

    asyncio.run(run_banking77_benchmark(max_samples=max_samples, split=args.split))
