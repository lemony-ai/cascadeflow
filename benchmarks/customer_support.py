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
from typing import Any

from cascadeflow.agent import CascadeAgent

from .base import Benchmark, BenchmarkResult, BenchmarkSummary


class CustomerSupportBenchmark(Benchmark):
    """Customer support scenario benchmark."""

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o",
        quality_threshold: float = 0.7,
        max_samples: int = 20,
    ):
        """Initialize customer support benchmark."""
        super().__init__(
            dataset_name="CustomerSupport-20",
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
                "expected_info": ["Monday-Friday", "9 AM", "5 PM", "EST"],
                "response_quality": "high",  # Drafter should handle easily
            },
            {
                "query_id": "CS/FAQ/shipping",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "How long does shipping take?",
                "expected_info": ["3-5 business days", "standard shipping"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/returns",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "What is your return policy?",
                "expected_info": ["30 days", "refund", "original condition"],
                "response_quality": "high",
            },
            {
                "query_id": "CS/FAQ/payment",
                "category": "simple_faq",
                "complexity": "simple",
                "query": "What payment methods do you accept?",
                "expected_info": ["credit card", "PayPal", "debit"],
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
                "expected_info": ["warranty", "year", "manufacturer", "defects"],
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
                    "5-10 business days",
                    "check",
                    "status",
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
                    "manufacturer",
                    "defect",
                    "manager",
                    "case-by-case",
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
                    "wholesale",
                    "business",
                    "sales team",
                    "quote",
                ],
                "response_quality": "low",
            },
            {
                "query_id": "CS/COMPLEX/legal",
                "category": "complex",
                "complexity": "complex",
                "query": "What are your data privacy practices? I need to know for GDPR compliance.",
                "expected_info": [
                    "privacy policy",
                    "GDPR",
                    "data protection",
                    "compliance",
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
                    "supervisor",
                    "priority",
                ],
                "response_quality": "low",
            },
        ]

        return [(q["query_id"], q) for q in queries[: self.max_samples]]

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

            prediction_lower = prediction.lower()

            # Check for expected information
            expected_info = ground_truth["expected_info"]
            info_matches = sum(1 for info in expected_info if info.lower() in prediction_lower)
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
            ]
            helpfulness_score = min(
                sum(1 for phrase in helpful_phrases if phrase in prediction_lower) / 3.0,
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
                sum(1 for indicator in professional_indicators if indicator in prediction_lower)
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
        enhanced_query = f"""You are a helpful customer support agent. Please provide a clear, professional, and empathetic response to this customer inquiry:

{query}

Provide a helpful response that addresses their concern."""

        agent = CascadeAgent(
            models=[
                {"name": self.drafter_model, "provider": "openai"},
                {"name": self.verifier_model, "provider": "openai"},
            ],
            quality={"threshold": self.quality_threshold},
        )

        result = await agent.arun(enhanced_query)
        return result


async def run_customer_support_benchmark() -> BenchmarkSummary:
    """Run customer support benchmark and generate report."""

    print("\n" + "=" * 80)
    print("CUSTOMER SUPPORT: REAL-WORLD ROI BENCHMARK")
    print("=" * 80 + "\n")

    # Verify API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    print("Configuration:")
    print("  Dataset:         CustomerSupport-20 (realistic support scenarios)")
    print("  Drafter:         gpt-4o-mini")
    print("  Verifier:        gpt-4o")
    print("  Baseline:        gpt-4o (always)")
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
        drafter_model="gpt-4o-mini",
        verifier_model="gpt-4o",
        quality_threshold=0.7,
        max_samples=20,
    )

    # Run benchmark
    print("Running benchmark...")
    summary = await benchmark.run()

    # Print summary
    print("\n" + "=" * 80)
    print("CUSTOMER SUPPORT BENCHMARK RESULTS")
    print("=" * 80 + "\n")

    print(f"Total Queries:       {summary.total_tests}")
    print(f"Helpful Responses:   {summary.correct} ({summary.accuracy*100:.1f}%)")
    print(f"Drafter Accepted:    {summary.drafter_accepted} ({summary.acceptance_rate*100:.1f}%)")
    print(
        f"Verifier Escalated:  {summary.total_tests - summary.drafter_accepted} ({(1-summary.acceptance_rate)*100:.1f}%)"
    )

    print("\nCost Analysis:")
    print(f"  Cascade Total Cost:  ${summary.total_cost:.6f}")
    print(f"  Baseline Total Cost: ${summary.baseline_cost:.6f}")
    print(f"  Cost Savings:        ${summary.cost_savings:.6f} ({summary.cost_reduction_pct:.1f}%)")

    # Calculate monthly/annual savings for typical support volume
    queries_per_month = 10000  # Typical small business support volume
    monthly_cascade = (summary.total_cost / summary.total_tests) * queries_per_month
    monthly_baseline = (summary.baseline_cost / summary.total_tests) * queries_per_month
    monthly_savings = monthly_baseline - monthly_cascade
    annual_savings = monthly_savings * 12

    print("\n  💰 Projected ROI (10K queries/month):")
    print(f"     Monthly Savings:  ${monthly_savings:.2f}")
    print(f"     Annual Savings:   ${annual_savings:.2f}")

    print("\nPerformance:")
    print(f"  Average Latency:     {summary.avg_latency_ms:.0f}ms")
    print(f"  Average Quality:     {summary.avg_quality_score:.3f}")
    print(f"  Drafter Accuracy:    {summary.drafter_accuracy*100:.1f}% (when accepted)")

    print("\nKey Findings:")
    if summary.acceptance_rate >= 0.6:
        print(
            f"  ✅ Drafter handles {summary.acceptance_rate*100:.0f}% of queries (meets 60% target)"
        )
    else:
        print(f"  ⚠️  Drafter acceptance below 60%: {summary.acceptance_rate*100:.0f}%")

    if summary.accuracy >= 0.85:
        print(f"  ✅ High response quality: {summary.accuracy*100:.0f}% helpful")
    else:
        print(f"  ⚠️  Response quality below 85%: {summary.accuracy*100:.0f}%")

    if summary.cost_reduction_pct >= 50:
        print(f"  💰 Significant cost savings: {summary.cost_reduction_pct:.0f}% reduction")

    if summary.drafter_accuracy >= 0.8:
        print(
            f"  ✅ Drafter maintains quality: {summary.drafter_accuracy*100:.0f}% accurate on simple queries"
        )

    # Business impact summary
    print("\n📊 Business Impact:")
    print(f"  - Cascade pattern saves ${annual_savings:.0f}/year at 10K queries/month")
    print(f"  - Drafter handles {summary.acceptance_rate*100:.0f}% of queries at 10x lower cost")
    print("  - Verifier escalation ensures complex queries get premium responses")

    if summary.acceptance_rate >= 0.6 and summary.accuracy >= 0.85:
        print("  - ✅ Ready for production deployment in customer support use cases")

    print("\n" + "=" * 80 + "\n")

    return summary


if __name__ == "__main__":
    asyncio.run(run_customer_support_benchmark())
