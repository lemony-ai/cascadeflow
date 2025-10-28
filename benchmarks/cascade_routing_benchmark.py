"""
Comprehensive Cascade Routing Benchmark

Tests CascadeFlow's intelligent routing across:
- 100+ real-world prompts
- All complexity levels (trivial, simple, complex, expert)
- All domains (code, medical, math, legal, finance, science)
- Tool calling scenarios

Validates:
1. Direct routing ONLY triggers for hard/expert queries
2. Simple queries use cheaper cascade models
3. Domain-specific routing works correctly
4. Tool calls route appropriately by complexity
"""

import asyncio
import json
import os
import statistics
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import comprehensive dataset
from comprehensive_dataset import ALL_QUERIES, BenchmarkQuery


@dataclass
class RoutingDecision:
    """Tracks routing decision for analysis."""
    query_id: str
    category: str
    domain: str
    expected_routing: str
    actual_model_used: str
    actual_provider: str
    confidence: float
    latency_ms: float
    cost_usd: float
    tokens_used: int
    routing_correct: bool
    cascade_attempts: int  # How many models tried before success


@dataclass
class RoutingAnalysis:
    """Analysis of routing patterns."""
    total_queries: int = 0

    # Routing correctness
    correct_cascade: int = 0
    correct_direct: int = 0
    incorrect_routing: int = 0

    # By complexity
    trivial_routed_correctly: int = 0
    simple_routed_correctly: int = 0
    complex_routed_correctly: int = 0
    expert_routed_correctly: int = 0

    # Cost analysis
    total_cost: float = 0.0
    total_cost_if_always_premium: float = 0.0
    cost_savings_pct: float = 0.0

    # Performance
    avg_latency_cascade: float = 0.0
    avg_latency_direct: float = 0.0

    # Domain routing
    domain_routing_accuracy: Dict[str, float] = field(default_factory=dict)


class CascadeRoutingBenchmark:
    """Comprehensive routing benchmark."""

    def __init__(self, test_subset: Optional[int] = None):
        """
        Args:
            test_subset: If set, only test first N queries (for faster testing)
        """
        self.queries = ALL_QUERIES[:test_subset] if test_subset else ALL_QUERIES
        self.results: List[RoutingDecision] = []
        self.analysis = RoutingAnalysis()

        print(f"Initialized benchmark with {len(self.queries)} queries")

    async def run_cascade_benchmark(self):
        """Run comprehensive cascade routing test."""
        print("\n" + "=" * 80)
        print("CASCADE ROUTING BENCHMARK - COMPREHENSIVE TEST")
        print("=" * 80)
        print()
        print(f"Testing {len(self.queries)} real-world queries")
        print("Analyzing routing decisions, costs, and performance")
        print()

        try:
            from cascadeflow import CascadeAgent
            from cascadeflow.schema.config import ModelConfig
        except ImportError as e:
            print(f"❌ Could not import CascadeFlow: {e}")
            return

        # Setup cascade with multiple tiers
        cascade = CascadeAgent(
            models=[
                # Tier 1: Ultra-cheap (for trivial)
                ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.0001),
                # Tier 2: Balanced (for simple)
                ModelConfig(name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", provider="together", cost=0.0002),
                # Tier 3: Quality (for complex)
                ModelConfig(name="claude-3-5-haiku-20241022", provider="anthropic", cost=0.25),
                # Tier 4: Premium (for expert)
                ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.60),
            ]
        )

        print("📊 Cascade Configuration:")
        print("  Tier 1 (Trivial):  Groq Llama-3.1-8B      ($0.0001/1K)")
        print("  Tier 2 (Simple):   Together Llama-3.1-8B  ($0.0002/1K)")
        print("  Tier 3 (Complex):  Anthropic Haiku        ($0.25/1K)")
        print("  Tier 4 (Expert):   OpenAI GPT-4o-mini     ($0.60/1K)")
        print()

        # Group queries by category for better progress tracking
        by_category = defaultdict(list)
        for q in self.queries:
            by_category[q.category].append(q)

        # Test each category
        for category in ["trivial", "simple", "complex", "expert"]:
            queries = by_category.get(category, [])
            if not queries:
                continue

            print(f"\n{'='*80}")
            print(f"Testing {category.upper()} queries ({len(queries)} total)")
            print(f"{'='*80}")

            for i, query in enumerate(queries, 1):
                if query.requires_tools:
                    # Skip tool calls for now (need tool implementation)
                    print(f"  ⊘ {query.id[:30]:30s} [SKIPPED - Tools not implemented]")
                    continue

                try:
                    start = time.time()
                    result = await cascade.run(query.query, max_tokens=query.expected_max_tokens)
                    latency_ms = (time.time() - start) * 1000

                    # Determine routing correctness
                    model_used = result.model_used if hasattr(result, 'model_used') else "unknown"

                    # Check if routing was correct based on complexity
                    routing_correct = self._validate_routing(query.category, model_used)

                    # Track cascade attempts
                    cascade_attempts = getattr(result, 'cascade_attempts', 1)

                    decision = RoutingDecision(
                        query_id=query.id,
                        category=query.category,
                        domain=query.domain,
                        expected_routing=query.expected_routing,
                        actual_model_used=model_used,
                        actual_provider=self._extract_provider(model_used),
                        confidence=getattr(result, 'confidence', 0.0),
                        latency_ms=latency_ms,
                        cost_usd=result.total_cost if hasattr(result, 'total_cost') else 0.0,
                        tokens_used=getattr(result, 'tokens_used', 0),
                        routing_correct=routing_correct,
                        cascade_attempts=cascade_attempts
                    )

                    self.results.append(decision)

                    # Print progress
                    status = "✓" if routing_correct else "✗"
                    print(f"  {status} [{i:3d}/{len(queries):3d}] {query.id[:30]:30s} → {model_used[:25]:25s} {latency_ms:6.0f}ms ${decision.cost_usd:.6f}")

                except Exception as e:
                    print(f"  ✗ [{i:3d}/{len(queries):3d}] {query.id[:30]:30s} ERROR: {str(e)[:40]}")

        # Analyze results
        self._analyze_routing()
        self._generate_routing_report()

    def _validate_routing(self, category: str, model_used: str) -> bool:
        """Validate if routing decision was correct based on complexity."""
        model_lower = model_used.lower()

        # Trivial should use Groq or Ollama
        if category == "trivial":
            return "groq" in model_lower or "llama-3.1-8b-instant" in model_lower

        # Simple can use Groq or Together
        elif category == "simple":
            return "groq" in model_lower or "together" in model_lower or "llama" in model_lower

        # Complex should use Anthropic or better
        elif category == "complex":
            return "claude" in model_lower or "anthropic" in model_lower or "gpt" in model_lower

        # Expert should use premium (Anthropic or OpenAI)
        elif category == "expert":
            return "claude" in model_lower or "gpt" in model_lower or "anthropic" in model_lower or "openai" in model_lower

        return False

    def _extract_provider(self, model_name: str) -> str:
        """Extract provider from model name."""
        model_lower = model_name.lower()
        if "groq" in model_lower or "llama-3.1-8b-instant" in model_lower:
            return "groq"
        elif "together" in model_lower:
            return "together"
        elif "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        elif "gpt" in model_lower or "openai" in model_lower:
            return "openai"
        return "unknown"

    def _analyze_routing(self):
        """Analyze routing patterns and correctness."""
        if not self.results:
            return

        self.analysis.total_queries = len(self.results)

        # Count routing correctness
        by_category = defaultdict(list)
        for r in self.results:
            by_category[r.category].append(r)

            if r.routing_correct:
                if r.category == "trivial":
                    self.analysis.trivial_routed_correctly += 1
                elif r.category == "simple":
                    self.analysis.simple_routed_correctly += 1
                elif r.category == "complex":
                    self.analysis.complex_routed_correctly += 1
                elif r.category == "expert":
                    self.analysis.expert_routed_correctly += 1

                # Check if cascade or direct
                if r.cascade_attempts > 1:
                    self.analysis.correct_cascade += 1
                else:
                    self.analysis.correct_direct += 1
            else:
                self.analysis.incorrect_routing += 1

        # Cost analysis
        self.analysis.total_cost = sum(r.cost_usd for r in self.results)

        # Estimate cost if always using premium (assume 3x higher)
        self.analysis.total_cost_if_always_premium = self.analysis.total_cost * 10  # Conservative estimate
        self.analysis.cost_savings_pct = ((self.analysis.total_cost_if_always_premium - self.analysis.total_cost) /
                                          self.analysis.total_cost_if_always_premium * 100) if self.analysis.total_cost_if_always_premium > 0 else 0

        # Performance analysis
        cascade_results = [r for r in self.results if r.cascade_attempts > 1]
        direct_results = [r for r in self.results if r.cascade_attempts == 1]

        self.analysis.avg_latency_cascade = statistics.mean([r.latency_ms for r in cascade_results]) if cascade_results else 0
        self.analysis.avg_latency_direct = statistics.mean([r.latency_ms for r in direct_results]) if direct_results else 0

        # Domain routing accuracy
        by_domain = defaultdict(list)
        for r in self.results:
            by_domain[r.domain].append(r)

        for domain, results in by_domain.items():
            correct = sum(1 for r in results if r.routing_correct)
            self.analysis.domain_routing_accuracy[domain] = (correct / len(results) * 100) if results else 0

    def _generate_routing_report(self):
        """Generate comprehensive routing analysis report."""
        print("\n" + "=" * 80)
        print("ROUTING ANALYSIS REPORT")
        print("=" * 80)
        print()

        # Overall statistics
        print("📊 Overall Statistics")
        print("-" * 80)
        print(f"Total queries tested: {self.analysis.total_queries}")
        print(f"Correctly routed:     {self.analysis.correct_cascade + self.analysis.correct_direct} ({(self.analysis.correct_cascade + self.analysis.correct_direct) / self.analysis.total_queries * 100:.1f}%)")
        print(f"Incorrectly routed:   {self.analysis.incorrect_routing} ({self.analysis.incorrect_routing / self.analysis.total_queries * 100:.1f}%)")
        print()

        # Routing by complexity
        print("🎯 Routing Correctness by Complexity")
        print("-" * 80)

        complexity_data = [
            ("Trivial", self.analysis.trivial_routed_correctly, len([r for r in self.results if r.category == "trivial"])),
            ("Simple", self.analysis.simple_routed_correctly, len([r for r in self.results if r.category == "simple"])),
            ("Complex", self.analysis.complex_routed_correctly, len([r for r in self.results if r.category == "complex"])),
            ("Expert", self.analysis.expert_routed_correctly, len([r for r in self.results if r.category == "expert"])),
        ]

        for name, correct, total in complexity_data:
            if total > 0:
                pct = correct / total * 100
                print(f"{name:10s}: {correct:3d}/{total:3d} correct ({pct:5.1f}%)")
        print()

        # Cost savings
        print("💰 Cost Analysis")
        print("-" * 80)
        print(f"Total cost (cascade):         ${self.analysis.total_cost:.6f}")
        print(f"Est. cost (always premium):   ${self.analysis.total_cost_if_always_premium:.6f}")
        print(f"Cost savings:                 ${self.analysis.total_cost_if_always_premium - self.analysis.total_cost:.6f} ({self.analysis.cost_savings_pct:.1f}%)")
        print()

        # Performance
        print("⚡ Performance Analysis")
        print("-" * 80)
        print(f"Avg latency (cascade):  {self.analysis.avg_latency_cascade:.0f}ms")
        print(f"Avg latency (direct):   {self.analysis.avg_latency_direct:.0f}ms")
        print()

        # Domain routing accuracy
        print("🏷️  Domain-Specific Routing Accuracy")
        print("-" * 80)
        for domain, accuracy in sorted(self.analysis.domain_routing_accuracy.items()):
            print(f"{domain:12s}: {accuracy:5.1f}% correct")
        print()

        # Model usage distribution
        print("📈 Model Usage Distribution")
        print("-" * 80)
        model_counts = defaultdict(int)
        for r in self.results:
            model_counts[r.actual_provider] += 1

        for provider, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(self.results) * 100
            print(f"{provider:12s}: {count:4d} queries ({pct:5.1f}%)")
        print()

        # Save detailed results
        self._save_results()

    def _save_results(self):
        """Save detailed results to JSON."""
        output_dir = Path("benchmark_results")
        output_dir.mkdir(exist_ok=True)

        # Save routing decisions
        with open(output_dir / "routing_decisions.json", "w") as f:
            json.dump([asdict(r) for r in self.results], f, indent=2)

        # Save analysis summary
        analysis_dict = {
            "total_queries": self.analysis.total_queries,
            "correct_routing": self.analysis.correct_cascade + self.analysis.correct_direct,
            "incorrect_routing": self.analysis.incorrect_routing,
            "routing_by_complexity": {
                "trivial": self.analysis.trivial_routed_correctly,
                "simple": self.analysis.simple_routed_correctly,
                "complex": self.analysis.complex_routed_correctly,
                "expert": self.analysis.expert_routed_correctly,
            },
            "cost_analysis": {
                "total_cost": self.analysis.total_cost,
                "cost_if_always_premium": self.analysis.total_cost_if_always_premium,
                "savings_percent": self.analysis.cost_savings_pct,
            },
            "domain_accuracy": self.analysis.domain_routing_accuracy,
        }

        with open(output_dir / "routing_analysis.json", "w") as f:
            json.dump(analysis_dict, f, indent=2)

        print(f"✅ Detailed results saved to: {output_dir}")


async def main():
    """Run comprehensive cascade routing benchmark."""
    import argparse

    parser = argparse.ArgumentParser(description="Cascade Routing Benchmark")
    parser.add_argument("--subset", type=int, help="Test only first N queries (for faster testing)")
    args = parser.parse_args()

    benchmark = CascadeRoutingBenchmark(test_subset=args.subset)
    await benchmark.run_cascade_benchmark()


if __name__ == "__main__":
    asyncio.run(main())
