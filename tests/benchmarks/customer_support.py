"""Customer Support Benchmark: Real-World ROI Validation

Evaluates CascadeFlow on realistic customer support scenarios to demonstrate
practical cost savings and quality maintenance in production environments.

Customer support is an ideal use case for cascade systems because:
- 60-70% of queries are simple FAQs (perfect for drafter)
- 20-30% require moderate complexity (borderline)
- 10-20% need expert-level responses (escalate to verifier)

This distribution naturally aligns with cascade economics.

Research Questions:
- What cost savings can cascade achieve in customer support?
- Can drafter maintain quality on simple queries?
- Does verifier escalation improve complex query responses?
- What is the optimal quality threshold for customer support?

Metrics:
- Response correctness (factual accuracy)
- Helpfulness (addresses user's actual question)
- Tone (professional, empathetic, clear)
- Cost savings vs always using premium model
"""

import asyncio
import os
import re
from typing import Any, Optional

from cascadeflow import CascadeAgent, ModelConfig

from .base import Benchmark, BenchmarkResult, BenchmarkSummary


class CustomerSupportBenchmark(Benchmark):
    """Customer support scenario benchmark."""

    COMPANY_POLICY = """Company Policy (use this as ground truth):
- Business hours: Monday-Friday, 9 AM to 5 PM EST.
- Shipping: Standard shipping takes 3-5 business days.
- Returns: 30-day return window for items in original condition; eligible for a refund.
- Payments: Credit card, debit card, and PayPal are accepted.
- Order tracking: Customers receive a tracking number via email confirmation and can also view it in their account.
- Password reset: Use the "Forgot password" link to receive an email reset link.
- Cancellations: Orders can be canceled before shipping by contacting customer service.
- Sizing: Use the size chart/size guide and measure for fit.
- Gift wrapping: Gift wrapping is offered as an optional service at checkout.
- International shipping: International shipping is available to select countries.
- Warranty: 1-year warranty covering manufacturer defects.
- Promotions: Current promotions are shared via promo codes and email; check active sales/codes.
"""

    def __init__(
        self,
        drafter_model: str = "claude-haiku-4-5-20251001",
        verifier_model: str = "claude-opus-4-5-20251101",
        quality_threshold: float = 0.7,
        max_samples: Optional[int] = 20,
    ):
        """Initialize customer support benchmark."""
        dataset_name = (
            "CustomerSupport-full" if max_samples is None else f"CustomerSupport-{max_samples}"
        )
        super().__init__(
            dataset_name=dataset_name,
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            baseline_model=verifier_model,
            quality_threshold=quality_threshold,
            max_samples=max_samples,
        )

    def load_dataset(self) -> list[tuple[str, Any]]:
        """
        Load customer support queries.

        Returns:
            List of (query_id, query_data) tuples
        """
        # Representative customer support scenarios (20 queries)
        queries = [
            # Simple FAQs (60% - should use drafter)
            {
                "query_id": "CS/FAQ/hours",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "What are your business hours?",
                "expected_info": [
                    ["monday-friday", "mon-fri", "monday to friday", "monday through friday"],
                    ["9 am", "9am"],
                    ["5 pm", "5pm"],
                    ["est", "et", "eastern"],
                ],
                "response_quality": "high",  # Drafter should handle easily
            },
            {
                "query_id": "CS/FAQ/shipping",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "How long does shipping take?",
                "expected_info": [["3-5 business days", "3 to 5 business days"], "standard shipping"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/returns",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "What is your return policy?",
                "expected_info": [["30 days", "30-day"], "refund", ["original condition", "unused", "in original packaging"]],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/payment",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "What payment methods do you accept?",
                "expected_info": [["credit card", "card"], "paypal", ["debit", "debit card"]],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/track",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "How do I track my order?",
                "expected_info": [
                    "tracking number",
                    "email",
                    "confirmation",
                    "account",
                ],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/account",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "How do I reset my password?",
                "expected_info": ["forgot password", "link", "email", "reset"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/cancel",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "Can I cancel my order?",
                "expected_info": ["before shipping", "contact", "customer service"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/size",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "How do I find the right size?",
                "expected_info": ["size chart", "guide", "measurements"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/gift",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "Do you offer gift wrapping?",
                "expected_info": ["gift", "wrap", "service", "option"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/international",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "Do you ship internationally?",
                "expected_info": ["international", "shipping", "countries"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/warranty",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "What warranty do you offer?",
                "expected_info": ["warranty", ["1 year", "one year", "1-year"], ["manufacturer", "manufacturing"], ["defects", "defect"]],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/discount",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "Do you have any current promotions?",
                "expected_info": ["promo", "discount", "sale", "code", "email"],
                "response_quality": "high",
            },
            # Moderate complexity (20% - borderline)
            {
                "query_id": "CS/MODERATE/damaged",
                "category": "moderate",
                "complexity": "moderate",
                "query": "I received a damaged item. What should I do?",
                "expected_info": [
                    "sorry",
                    "replacement",
                    "refund",
                    "photo",
                    "contact",
                ],
                "response_quality": "medium",  # Drafter may handle, but verifier adds empathy
            },
            {
                "query_id": "CS/MODERATE/late",
                "category": "moderate",
                "complexity": "moderate",
                "query": "My order is late. Where is it?",
                "expected_info": [
                    "apologize",
                    "check",
                    "tracking",
                    "status",
                    "help",
                ],
                "response_quality": "medium",
            },
            {
                "query_id": "CS/MODERATE/wrong",
                "category": "moderate",
                "complexity": "moderate",
                "query": "I received the wrong item. Can you help?",
                "expected_info": [
                    "sorry",
                    "exchange",
                    "correct item",
                    "return",
                    "ship",
                ],
                "response_quality": "medium",
            },
            {
                "query_id": "CS/MODERATE/refund_status",
                "category": "moderate",
                "complexity": "moderate",
                "query": "I returned an item 2 weeks ago. Where's my refund?",
                "expected_info": [
                    "processing",
                    "check",
                    "status",
                    ["original payment method", "original payment", "to your card", "to your paypal"],
                ],
                "response_quality": "medium",
            },
            # Complex policy questions (20% - should escalate to verifier)
            {
                "query_id": "CS/COMPLEX/exception",
                "category": "complex",
                "complexity": "complex",
                "query": "I'm outside the 30-day return window but the product is defective. Can you make an exception?",
                "expected_info": [
                    "warranty",
                    ["1 year", "one year", "1-year"],
                    ["defect", "defective"],
                    ["contact", "customer service", "support"],
                ],
                "response_quality": "low",  # Drafter likely gives generic response
            },
            {
                "query_id": "CS/COMPLEX/bulk",
                "category": "complex",
                "complexity": "complex",
                "query": "I need to order 500 units for my business. Do you offer bulk pricing and custom branding?",
                "expected_info": [
                    "bulk",
                    "business",
                    ["pricing", "quote", "estimate"],
                    ["contact", "customer service", "support"],
                ],
                "response_quality": "low",
            },
            {
                "query_id": "CS/COMPLEX/legal",
                "category": "complex",
                "complexity": "complex",
                "query": "What are your data privacy practices? I need to know for GDPR compliance.",
                "expected_info": [
                    "GDPR",
                    ["privacy", "privacy policy"],
                    ["contact", "customer service", "support"],
                ],
                "response_quality": "low",
            },
            {
                "query_id": "CS/COMPLEX/escalation",
                "category": "complex",
                "complexity": "complex",
                "query": "I've contacted support 3 times about my broken product and haven't received a satisfactory resolution. I want to speak to a manager.",
                "expected_info": [
                    "apologize",
                    "escalate",
                    "manager",
                    ["supervisor", "lead", "escalation"],
                ],
                "response_quality": "low",
            },
        ]

        # NOTE: The benchmark runner passes the tuple's first element as the actual
        # query sent to the model. For this benchmark, the "query" is the natural-language
        # customer question (not the query_id).
        return [(q["query"], q) for q in queries[: self.max_samples]]

    def _normalize(self, text: str) -> str:
        s = text.lower()
        # Normalize digit/time formats: "9am" -> "9 am"
        s = re.sub(r"(\d)\s*(am|pm)\b", r"\1 \2", s)
        # Normalize ranges: "3-5" -> "3 to 5"
        s = re.sub(r"(\d)\s*-\s*(\d)", r"\1 to \2", s)
        # Normalize common punctuation to spaces
        s = re.sub(r"[^a-z0-9]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _expected_match(self, prediction_norm: str, expected: Any) -> bool:
        # Allow expected_info entries to be either string or list[str] (any-of).
        if isinstance(expected, list):
            return any(self._expected_match(prediction_norm, e) for e in expected)
        if not isinstance(expected, str):
            return False
        return self._normalize(expected) in prediction_norm

    def evaluate_prediction(self, prediction: str, ground_truth: Any) -> tuple[bool, float]:
        """
        Evaluate customer support response quality.

        Evaluates based on:
        1. Correctness (contains expected information)
        2. Helpfulness (actually addresses the query)
        3. Tone (professional, empathetic)

        Args:
            prediction: Model's response
            ground_truth: Query data with expected information

        Returns:
            (is_helpful, quality_score)
        """
        try:
            if not prediction or len(prediction.strip()) < 20:
                return False, 0.0

            prediction_norm = self._normalize(prediction)

            # Check for expected information
            expected_info = ground_truth["expected_info"]
            info_matches = sum(1 for info in expected_info if self._expected_match(prediction_norm, info))
            info_coverage = info_matches / len(expected_info) if expected_info else 0.0

            # Check for helpful indicators
            helpful_phrases = [
                "help",
                "happy to",
                "glad to",
                "assist",
                "i can",
                "let me",
                "here's how",
                "you can",
                "next steps",
                "here's what",
                "i recommend",
                "i suggest",
            ]
            phrase_hits = sum(
                1 for phrase in helpful_phrases if self._normalize(phrase) in prediction_norm
            )

            # Actionability: give credit for concrete next-steps even if the response
            # doesn't contain "helpful" keywords (common for concise, direct answers).
            lines = [ln.strip() for ln in prediction.splitlines() if ln.strip()]
            has_steps = any(
                ln.startswith(("-", "*")) or bool(re.match(r"^\\d+\\.", ln)) for ln in lines
            )
            actionable_markers = [
                "contact",
                "check",
                "visit",
                "click",
                "sign up",
                "subscribe",
                "reply",
                "send",
                "provide",
                "upload",
                "order number",
                "tracking",
                "account",
                "checkout",
            ]
            has_actionable_marker = any(
                self._normalize(m) in prediction_norm for m in actionable_markers
            )

            helpfulness_score = min(
                (phrase_hits + (1 if has_steps else 0) + (1 if has_actionable_marker else 0))
                / 3.0,
                1.0,
            )

            # Check for professional tone
            professional_indicators = [
                "thank you",
                "thanks for",
                "appreciate",
                "apologize",
                "sorry",
                "understand",
            ]
            tone_score = min(
                sum(
                    1
                    for indicator in professional_indicators
                    if self._normalize(indicator) in prediction_norm
                )
                / 2.0,
                1.0,
            )

            # Weighted scoring
            # Info coverage: 60% (most important - did they answer the question?)
            # Helpfulness: 25% (is the response actionable?)
            # Tone: 15% (is it professional?)
            quality_score = info_coverage * 0.6 + helpfulness_score * 0.25 + tone_score * 0.15

            # Consider helpful if quality >= 0.6
            is_helpful = quality_score >= 0.6

            if os.getenv("CASCADEFLOW_BENCH_DEBUG_CUSTOMER_SUPPORT") == "1" and not is_helpful:
                print("\n  [CustomerSupport Debug] NOT HELPFUL")
                print(f"  query_id: {ground_truth.get('query_id')}")
                print(f"  query: {ground_truth.get('query')}")
                print(f"  expected_info: {ground_truth.get('expected_info')}")
                print(f"  info_coverage: {info_coverage:.2f} (matches {info_matches}/{len(expected_info)})")
                print(f"  helpfulness_score: {helpfulness_score:.2f}")
                print(f"  tone_score: {tone_score:.2f}")
                print(f"  quality_score: {quality_score:.2f}")
                print(f"  prediction: {prediction.strip()[:400]}")

            return is_helpful, quality_score

        except Exception as e:
            print(f"  Warning: Evaluation error: {e}")
            return False, 0.0

    async def run_cascade(self, query: str) -> dict[str, Any]:
        """
        Run cascade on a customer support query.

        Args:
            query: Customer support question

        Returns:
            Cascade result dict
        """
        # Add context for customer support
        enhanced_query = f"""You are a helpful customer support agent.

Use the following company policy as ground truth. Do not invent details.

Guidelines:
- Answer the customer's question directly first (lead with the answer).
- Include specific policy facts when applicable (hours, shipping time, return window, payments, warranty).
- Include actionable next steps (what the customer should do next).
- If you need more information (order number, photos), ask for it AFTER you provide the best possible answer.
- Keep the response concise and professional.

{self.COMPANY_POLICY}

Customer inquiry:
{query}

Write the customer support response:"""

        def _provider_for(model_name: str) -> str:
            if model_name.startswith("claude-"):
                return "anthropic"
            if model_name.startswith("gpt-") or model_name.startswith("o"):
                return "openai"
            return "openai"

        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider=_provider_for(self.drafter_model), cost=0.0),
                ModelConfig(name=self.verifier_model, provider=_provider_for(self.verifier_model), cost=0.0),
            ],
            quality={"threshold": self.quality_threshold},
        )

        result = await agent.run(enhanced_query)

        cost_saved = float(getattr(result, "cost_saved", 0.0) or 0.0)
        baseline_cost = float(getattr(result, "baseline_cost", 0.0) or 0.0)

        return {
            "prediction": result.content,
            "model_used": result.model_used,
            "accepted": result.draft_accepted,
            "quality_score": result.quality_score or 0.0,
            "drafter_cost": result.draft_cost or 0.0,
            "verifier_cost": result.verifier_cost or 0.0,
            "total_cost": result.total_cost,
            "cost_saved": cost_saved,
            "baseline_cost": baseline_cost,
            "latency_ms": result.latency_ms,
            "tokens_input": int(result.metadata.get("prompt_tokens") or 0),
            "tokens_output": int(result.metadata.get("completion_tokens") or 0),
            # Diagnostic fields (used only by Benchmark.on_result hooks if present).
            "cascade_reason": getattr(result, "reason", ""),
            "routing_strategy": getattr(result, "routing_strategy", ""),
            "complexity": getattr(result, "complexity", ""),
            "quality_threshold": getattr(result, "quality_threshold", None),
            "quality_check_passed": getattr(result, "quality_check_passed", None),
        }

    def on_result(
        self,
        *,
        result: BenchmarkResult,
        cascade_result: dict[str, Any],
        ground_truth: Any,
    ) -> None:
        if os.getenv("CASCADEFLOW_BENCH_DEBUG_CUSTOMER_SUPPORT") != "1":
            return
        if result.is_correct:
            return
        print("  [Cascade Debug]")
        print(f"  draft_accepted: {cascade_result.get('accepted')}")
        print(f"  cascade_reason: {cascade_result.get('cascade_reason')}")
        print(f"  routing_strategy: {cascade_result.get('routing_strategy')}")
        print(f"  complexity: {cascade_result.get('complexity')}")
        print(f"  quality_score: {cascade_result.get('quality_score')}")
        print(f"  quality_threshold: {cascade_result.get('quality_threshold')}")
        print(f"  quality_check_passed: {cascade_result.get('quality_check_passed')}")


async def run_customer_support_benchmark(
    max_samples: Optional[int] = 20,
) -> BenchmarkSummary:
    """Run customer support benchmark and generate report."""

    print("\n" + "=" * 80)
    print("CUSTOMER SUPPORT: REAL-WORLD ROI BENCHMARK")
    print("=" * 80 + "\n")

    # Verify API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        return

    print("Configuration:")
    dataset_label = (
        "CustomerSupport-full (bundled set)"
        if max_samples is None
        else f"CustomerSupport-{max_samples} (realistic support scenarios)"
    )
    print(f"  Dataset:         {dataset_label}")
    print("  Drafter:         claude-haiku-4-5-20251001")
    print("  Verifier:        claude-opus-4-5-20251101")
    print("  Baseline:        claude-opus-4-5-20251101 (always)")
    print("  Quality Threshold: 0.7\n")

    print("Query Distribution:")
    print("  - 60% Simple FAQs (hours, shipping, returns, payments)")
    print("  - 20% Moderate (damaged items, late orders, wrong items)")
    print("  - 20% Complex (policy exceptions, bulk orders, escalations)\n")

    print("Quality Metrics:")
    print("  - Info Coverage (60%): Contains expected information")
    print("  - Helpfulness (25%): Actionable, clear guidance")
    print("  - Professional Tone (15%): Empathetic, courteous\n")

    # Create benchmark
    benchmark = CustomerSupportBenchmark(
        drafter_model="claude-haiku-4-5-20251001",
        verifier_model="claude-opus-4-5-20251101",
        quality_threshold=0.7,
        max_samples=max_samples,
    )

    # Run benchmark
    print("Running benchmark...")
    summary = await benchmark.run()

    # Print summary
    print("\n" + "=" * 80)
    print("CUSTOMER SUPPORT BENCHMARK RESULTS")
    print("=" * 80 + "\n")

    correct_count = (
        int(summary.accuracy / 100 * summary.successful_tests) if summary.successful_tests else 0
    )

    print(f"Total Queries:       {summary.total_tests}")
    print(f"Helpful Responses:   {correct_count} ({summary.accuracy:.1f}%)")
    print(f"Drafter Accepted:    {summary.drafter_accepted} ({summary.acceptance_rate_pct:.1f}%)")
    print(
        f"Verifier Escalated:  {summary.escalated_to_verifier} ({summary.escalation_rate_pct:.1f}%)"
    )

    print("\nCost Analysis:")
    print(f"  Cascade Total Cost:  ${summary.total_cost:.6f}")
    print(f"  Baseline Total Cost: ${summary.total_baseline_cost:.6f}")
    print(f"  Cost Savings:        ${summary.total_savings:.6f} ({summary.avg_savings_pct:.1f}%)")

    # Calculate monthly/annual savings for typical support volume
    queries_per_month = 10000  # Typical small business support volume
    monthly_cascade = (summary.total_cost / summary.total_tests) * queries_per_month
    monthly_baseline = (summary.total_baseline_cost / summary.total_tests) * queries_per_month
    monthly_savings = monthly_baseline - monthly_cascade
    annual_savings = monthly_savings * 12

    print("\n  💰 Projected ROI (10K queries/month):")
    print(f"     Monthly Savings:  ${monthly_savings:.2f}")
    print(f"     Annual Savings:   ${annual_savings:.2f}")

    print("\nPerformance:")
    print(f"  Average Latency:     {summary.avg_latency_ms:.0f}ms")
    print(f"  Drafter Accuracy:    {summary.drafter_accuracy:.1f}% (when accepted)")

    print("\nKey Findings:")
    if summary.acceptance_rate_pct >= 60:
        print(
            f"  ✅ Drafter handles {summary.acceptance_rate_pct:.0f}% of queries (meets 60% target)"
        )
    else:
        print(f"  ⚠️  Drafter acceptance below 60%: {summary.acceptance_rate_pct:.0f}%")

    if summary.accuracy >= 85:
        print(f"  ✅ High response quality: {summary.accuracy:.0f}% helpful")
    else:
        print(f"  ⚠️  Response quality below 85%: {summary.accuracy:.0f}%")

    if summary.avg_savings_pct >= 50:
        print(f"  💰 Significant cost savings: {summary.avg_savings_pct:.0f}% reduction")

    if summary.drafter_accuracy >= 80:
        print(
            f"  ✅ Drafter maintains quality: {summary.drafter_accuracy:.0f}% accurate on simple queries"
        )

    # Business impact summary
    print("\n📊 Business Impact:")
    print(f"  - Cascade pattern saves ${annual_savings:.0f}/year at 10K queries/month")
    print(f"  - Drafter handles {summary.acceptance_rate_pct:.0f}% of queries at 10x lower cost")
    print("  - Verifier escalation ensures complex queries get premium responses")

    if summary.acceptance_rate_pct >= 60 and summary.accuracy >= 85:
        print("  - ✅ Ready for production deployment in customer support use cases")

    print("\n" + "=" * 80 + "\n")

    return summary


if __name__ == "__main__":
    asyncio.run(run_customer_support_benchmark())
