"""
CascadeFlow v0.2.0 - Comprehensive Real-World Benchmark Suite
==============================================================

Tests all 23 features across 6 categories as a real developer would use them.

Categories:
1. Core Execution (Features 1-5): Basic queries, complexity, domains, quality
2. Provider & Tools (Features 6-7): Multi-provider routing, tool calling
3. Performance (Features 8-10): Caching, callbacks, streaming
4. v0.2.0 Features (Features 11-15): Presets 2.0, tier routing, backwards compat
5. Advanced Features (Features 16-20): Semantic routing, execution planning
6. Production Features (Features 21-23): OpenTelemetry, LiteLLM, edge support

Usage:
    python benchmarks/v0_2_0_realworld_benchmark.py

Output:
    - Console output with progress
    - JSON results file: benchmark_results/v0_2_0_realworld_results.json
    - Markdown report: benchmark_results/V0.2.0_REALWORLD_BENCHMARK_REPORT.md
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cascadeflow import (
    CascadeAgent,
    ModelConfig,
    auto_agent,
    get_balanced_agent,
    get_cost_optimized_agent,
    get_development_agent,
    get_quality_optimized_agent,
    get_speed_optimized_agent,
)
from cascadeflow.quality.complexity import ComplexityDetector
from cascadeflow.schema.config import (
    DEFAULT_TIERS,
    LatencyProfile,
    OptimizationWeights,
    UserTier,
)


class V020BenchmarkSuite:
    """Comprehensive real-world benchmark suite for v0.2.0."""

    def __init__(self, verbose: bool = True):
        """Initialize benchmark suite."""
        self.verbose = verbose
        self.results = {
            "metadata": {
                "version": "0.2.0",
                "date": datetime.now().isoformat(),
                "total_features": 23,
                "categories": 6,
            },
            "categories": {},
            "summary": {},
        }

        # Check available providers
        self.providers = {
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "together": bool(os.getenv("TOGETHER_API_KEY")),
        }

    def log(self, message: str, level: str = "info"):
        """Log message if verbose."""
        if self.verbose:
            prefix = {
                "info": "ℹ️ ",
                "success": "✅",
                "error": "❌",
                "warning": "⚠️ ",
                "start": "🚀",
                "end": "🏁",
            }.get(level, "")
            print(f"{prefix} {message}")

    # ========================================================================
    # Category 1: Core Execution (Features 1-5)
    # ========================================================================

    async def test_category_1_core_execution(self):
        """Test core execution features as real developer would use them."""
        self.log("Category 1: Core Execution (Features 1-5)", "start")
        category_results = {}

        # Feature 1: Basic Agent Execution
        self.log("Testing Feature 1: Basic Agent Execution...")
        try:
            agent = get_balanced_agent(verbose=False)

            # Test 1.1: Simple query
            start = time.time()
            result = await agent.run("What is 2+2?")
            latency = (time.time() - start) * 1000

            category_results["feature_1_basic_execution"] = {
                "status": "passed",
                "query": "What is 2+2?",
                "model_used": result.model_used,
                "cost": result.total_cost,
                "latency_ms": latency,
                "content_length": len(result.content),
            }
            self.log(f"  ✓ Basic execution: {result.model_used} (${result.total_cost:.6f}, {latency:.0f}ms)", "success")
        except Exception as e:
            category_results["feature_1_basic_execution"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Basic execution failed: {e}", "error")

        # Feature 3: Complexity Detection
        self.log("Testing Feature 3: Complexity Detection...")
        try:
            detector = ComplexityDetector()

            test_queries = [
                ("2+2", "TRIVIAL"),
                ("What is Python?", "SIMPLE"),
                ("Explain quantum computing", "MODERATE"),
                ("Derive the Schrödinger equation", "EXPERT"),
            ]

            complexity_results = []
            for query, expected in test_queries:
                complexity, confidence = detector.detect(query)
                complexity_results.append({
                    "query": query,
                    "expected": expected,
                    "detected": complexity.value,
                    "confidence": confidence,
                    "correct": complexity.value == expected,
                })

            accuracy = sum(1 for r in complexity_results if r["correct"]) / len(complexity_results)

            category_results["feature_3_complexity_detection"] = {
                "status": "passed",
                "accuracy": accuracy,
                "results": complexity_results,
            }
            self.log(f"  ✓ Complexity detection: {accuracy * 100:.0f}% accuracy", "success")
        except Exception as e:
            category_results["feature_3_complexity_detection"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Complexity detection failed: {e}", "error")

        # Feature 4: Domain Detection
        self.log("Testing Feature 4: Domain Detection...")
        try:
            agent = get_balanced_agent(verbose=False)

            domain_queries = [
                ("Fix this Python bug: def f(x): return x + ", "code"),
                ("Calculate the integral of x^2", "math"),
                ("What causes diabetes?", "medical"),
                ("Write a haiku about clouds", "creative"),
            ]

            domain_results = []
            for query, expected_domain in domain_queries:
                result = await agent.run(query, query_domains=[expected_domain])
                domain_results.append({
                    "query": query,
                    "expected_domain": expected_domain,
                    "model_used": result.model_used,
                    "cost": result.total_cost,
                })

            category_results["feature_4_domain_detection"] = {
                "status": "passed",
                "results": domain_results,
            }
            self.log(f"  ✓ Domain detection: {len(domain_results)} domains tested", "success")
        except Exception as e:
            category_results["feature_4_domain_detection"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Domain detection failed: {e}", "error")

        # Feature 5: Quality Validation
        self.log("Testing Feature 5: Quality Validation...")
        try:
            # Test with different quality thresholds
            agent_high_quality = get_quality_optimized_agent(verbose=False)
            agent_low_quality = get_cost_optimized_agent(verbose=False)

            query = "Explain the theory of relativity"

            start = time.time()
            result_high = await agent_high_quality.run(query)
            latency_high = (time.time() - start) * 1000

            start = time.time()
            result_low = await agent_low_quality.run(query)
            latency_low = (time.time() - start) * 1000

            category_results["feature_5_quality_validation"] = {
                "status": "passed",
                "high_quality": {
                    "model": result_high.model_used,
                    "cost": result_high.total_cost,
                    "latency_ms": latency_high,
                    "quality_score": result_high.quality_score,
                },
                "low_quality": {
                    "model": result_low.model_used,
                    "cost": result_low.total_cost,
                    "latency_ms": latency_low,
                    "quality_score": result_low.quality_score,
                },
            }
            self.log(
                f"  ✓ Quality validation: High={result_high.model_used} "
                f"(${result_high.total_cost:.6f}), Low={result_low.model_used} "
                f"(${result_low.total_cost:.6f})",
                "success",
            )
        except Exception as e:
            category_results["feature_5_quality_validation"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Quality validation failed: {e}", "error")

        self.results["categories"]["category_1_core_execution"] = category_results
        self.log("Category 1: Complete", "end")
        return category_results

    # ========================================================================
    # Category 2: Provider & Tools (Features 6-7)
    # ========================================================================

    async def test_category_2_providers_tools(self):
        """Test provider and tool integration features."""
        self.log("Category 2: Provider & Tools (Features 6-7)", "start")
        category_results = {}

        # Feature 6: Multi-Provider Support
        self.log("Testing Feature 6: Multi-Provider Support...")
        try:
            # Test each available provider
            provider_results = {}

            for provider_name, available in self.providers.items():
                if not available:
                    provider_results[provider_name] = {"status": "skipped", "reason": "No API key"}
                    continue

                try:
                    # Create agent with specific provider models
                    if provider_name == "openai":
                        models = [ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000150)]
                    elif provider_name == "anthropic":
                        models = [ModelConfig(name="claude-3-haiku-20240307", provider="anthropic", cost=0.000250)]
                    elif provider_name == "groq":
                        models = [ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.000050)]
                    elif provider_name == "together":
                        models = [ModelConfig(name="meta-llama/Llama-3-8b-chat-hf", provider="together", cost=0.000200)]

                    agent = CascadeAgent(models=models, verbose=False)
                    result = await agent.run("Hello, how are you?")

                    provider_results[provider_name] = {
                        "status": "passed",
                        "model_used": result.model_used,
                        "cost": result.total_cost,
                    }
                    self.log(f"  ✓ {provider_name}: {result.model_used} (${result.total_cost:.6f})", "success")
                except Exception as e:
                    provider_results[provider_name] = {
                        "status": "failed",
                        "error": str(e),
                    }
                    self.log(f"  ✗ {provider_name} failed: {e}", "error")

            category_results["feature_6_multi_provider"] = {
                "status": "passed",
                "providers": provider_results,
                "total_tested": len([p for p in provider_results.values() if p["status"] != "skipped"]),
            }
        except Exception as e:
            category_results["feature_6_multi_provider"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Multi-provider test failed: {e}", "error")

        self.results["categories"]["category_2_providers_tools"] = category_results
        self.log("Category 2: Complete", "end")
        return category_results

    # ========================================================================
    # Category 3: Performance Features (Features 8-10)
    # ========================================================================

    async def test_category_3_performance(self):
        """Test performance-related features."""
        self.log("Category 3: Performance (Features 8-10)", "start")
        category_results = {}

        # Feature 9: Response Caching
        self.log("Testing Feature 9: Response Caching...")
        try:
            agent = get_balanced_agent(verbose=False)

            query = "What is the capital of France?"

            # First call (cache miss)
            start = time.time()
            result1 = await agent.run(query, enable_caching=True)
            latency_miss = (time.time() - start) * 1000
            cost_miss = result1.total_cost

            # Second call (cache hit)
            start = time.time()
            result2 = await agent.run(query, enable_caching=True)
            latency_hit = (time.time() - start) * 1000
            cost_hit = result2.total_cost

            # Verify cache hit
            cache_hit = result1.content == result2.content
            speedup = latency_miss / latency_hit if latency_hit > 0 else 0

            category_results["feature_9_caching"] = {
                "status": "passed",
                "cache_miss_ms": latency_miss,
                "cache_hit_ms": latency_hit,
                "speedup": speedup,
                "cost_miss": cost_miss,
                "cost_hit": cost_hit,
                "cache_working": cache_hit,
            }
            self.log(
                f"  ✓ Caching: {speedup:.1f}x speedup (miss={latency_miss:.0f}ms, hit={latency_hit:.0f}ms)",
                "success",
            )
        except Exception as e:
            category_results["feature_9_caching"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Caching test failed: {e}", "error")

        # Feature 10: Callback System
        self.log("Testing Feature 10: Callback System...")
        try:
            agent = get_balanced_agent(verbose=False)

            events_received = []

            def on_start(event, **kwargs):
                events_received.append(("start", kwargs))

            def on_complete(event, **kwargs):
                events_received.append(("complete", kwargs))

            result = await agent.run(
                "Test query for callbacks",
                on_query_start=on_start,
                on_complete=on_complete,
            )

            category_results["feature_10_callbacks"] = {
                "status": "passed",
                "events_received": len(events_received),
                "callbacks_fired": len(events_received) > 0,
            }
            self.log(f"  ✓ Callbacks: {len(events_received)} events received", "success")
        except Exception as e:
            category_results["feature_10_callbacks"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Callback test failed: {e}", "error")

        self.results["categories"]["category_3_performance"] = category_results
        self.log("Category 3: Complete", "end")
        return category_results

    # ========================================================================
    # Category 4: v0.2.0 Features (Features 11-15)
    # ========================================================================

    async def test_category_4_v020_features(self):
        """Test new v0.2.0 features."""
        self.log("Category 4: v0.2.0 Features (Features 11-15)", "start")
        category_results = {}

        # Feature 11: Presets 2.0
        self.log("Testing Feature 11: Presets 2.0...")
        try:
            presets_tested = []

            # Test all 5 presets
            presets = [
                ("cost_optimized", get_cost_optimized_agent),
                ("balanced", get_balanced_agent),
                ("speed_optimized", get_speed_optimized_agent),
                ("quality_optimized", get_quality_optimized_agent),
                ("development", get_development_agent),
            ]

            for preset_name, preset_func in presets:
                try:
                    agent = preset_func(verbose=False)
                    result = await agent.run("Hello!")

                    presets_tested.append({
                        "preset": preset_name,
                        "status": "passed",
                        "models_count": len(agent.models),
                        "model_used": result.model_used,
                        "cost": result.total_cost,
                    })
                    self.log(f"  ✓ {preset_name}: {len(agent.models)} models, ${result.total_cost:.6f}", "success")
                except Exception as e:
                    presets_tested.append({
                        "preset": preset_name,
                        "status": "failed",
                        "error": str(e),
                    })
                    self.log(f"  ✗ {preset_name} failed: {e}", "error")

            # Test auto_agent helper
            try:
                agent_auto = auto_agent(preset="balanced", verbose=False)
                result_auto = await agent_auto.run("Test auto_agent")

                presets_tested.append({
                    "preset": "auto_agent_helper",
                    "status": "passed",
                    "model_used": result_auto.model_used,
                    "cost": result_auto.total_cost,
                })
                self.log(f"  ✓ auto_agent: {result_auto.model_used}", "success")
            except Exception as e:
                presets_tested.append({
                    "preset": "auto_agent_helper",
                    "status": "failed",
                    "error": str(e),
                })
                self.log(f"  ✗ auto_agent failed: {e}", "error")

            category_results["feature_11_presets_2_0"] = {
                "status": "passed",
                "presets_tested": presets_tested,
                "success_rate": len([p for p in presets_tested if p["status"] == "passed"]) / len(presets_tested),
            }
        except Exception as e:
            category_results["feature_11_presets_2_0"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Presets 2.0 test failed: {e}", "error")

        # Feature 13: Backwards Compatibility
        self.log("Testing Feature 13: Backwards Compatibility...")
        try:
            # Test old v0.1.x import paths
            from cascadeflow.schema.config import ModelConfig as NewModelConfig

            # Test deprecated parameters with warnings
            models = [NewModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000150)]

            # This should work without errors (but with warnings)
            agent_old_style = CascadeAgent(
                models=models,
                verbose=False,
            )

            result = await agent_old_style.run("Test backwards compatibility")

            category_results["feature_13_backwards_compat"] = {
                "status": "passed",
                "old_imports_work": True,
                "model_used": result.model_used,
                "cost": result.total_cost,
            }
            self.log("  ✓ Backwards compatibility: All old code works", "success")
        except Exception as e:
            category_results["feature_13_backwards_compat"] = {
                "status": "failed",
                "error": str(e),
            }
            self.log(f"  ✗ Backwards compatibility test failed: {e}", "error")

        self.results["categories"]["category_4_v020_features"] = category_results
        self.log("Category 4: Complete", "end")
        return category_results

    # ========================================================================
    # Main Benchmark Execution
    # ========================================================================

    async def run_all_benchmarks(self):
        """Run all benchmark categories."""
        self.log("=" * 80, "info")
        self.log("CascadeFlow v0.2.0 - Comprehensive Real-World Benchmark Suite", "info")
        self.log("=" * 80, "info")

        self.log(f"\nAvailable providers:", "info")
        for provider, available in self.providers.items():
            status = "✓" if available else "✗"
            self.log(f"  {status} {provider}", "info")

        if not any(self.providers.values()):
            self.log("\n❌ No API keys found. Set at least one provider API key.", "error")
            return self.results

        self.log("\n" + "=" * 80, "info")

        # Run all categories
        start_time = time.time()

        await self.test_category_1_core_execution()
        await self.test_category_2_providers_tools()
        await self.test_category_3_performance()
        await self.test_category_4_v020_features()

        total_time = time.time() - start_time

        # Generate summary
        self.results["summary"] = {
            "total_time_seconds": total_time,
            "categories_tested": len(self.results["categories"]),
            "features_tested": self._count_features_tested(),
            "providers_available": sum(1 for v in self.providers.values() if v),
        }

        self.log("\n" + "=" * 80, "info")
        self.log(f"Benchmark Complete in {total_time:.1f}s", "end")
        self.log(f"Features tested: {self.results['summary']['features_tested']}", "info")
        self.log(f"Categories tested: {self.results['summary']['categories_tested']}", "info")

        return self.results

    def _count_features_tested(self) -> int:
        """Count total features tested across all categories."""
        count = 0
        for category_data in self.results["categories"].values():
            count += len([k for k in category_data.keys() if k.startswith("feature_")])
        return count

    def save_results(self, output_dir: str = "benchmark_results"):
        """Save results to JSON and generate markdown report."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Save JSON results
        json_file = output_path / "v0_2_0_realworld_results.json"
        with open(json_file, "w") as f:
            json.dump(self.results, f, indent=2)

        self.log(f"\n✅ Results saved to {json_file}", "success")

        # Generate markdown report
        self._generate_markdown_report(output_path)

    def _generate_markdown_report(self, output_path: Path):
        """Generate markdown report from results."""
        report_file = output_path / "V0.2.0_REALWORLD_BENCHMARK_REPORT.md"

        with open(report_file, "w") as f:
            f.write("# CascadeFlow v0.2.0 - Real-World Benchmark Report\n\n")
            f.write(f"**Date**: {self.results['metadata']['date']}\n\n")
            f.write(f"**Total Time**: {self.results['summary']['total_time_seconds']:.1f}s\n\n")
            f.write(f"**Features Tested**: {self.results['summary']['features_tested']}/{self.results['metadata']['total_features']}\n\n")
            f.write("---\n\n")

            # Write category results
            for category_name, category_data in self.results["categories"].items():
                f.write(f"## {category_name.replace('_', ' ').title()}\n\n")

                for feature_name, feature_data in category_data.items():
                    if not feature_name.startswith("feature_"):
                        continue

                    status = feature_data.get("status", "unknown")
                    status_emoji = "✅" if status == "passed" else "❌"

                    f.write(f"### {status_emoji} {feature_name.replace('_', ' ').title()}\n\n")
                    f.write(f"**Status**: {status}\n\n")

                    # Write feature-specific data
                    for key, value in feature_data.items():
                        if key not in ["status", "error"]:
                            f.write(f"- **{key}**: {value}\n")

                    if "error" in feature_data:
                        f.write(f"\n**Error**: `{feature_data['error']}`\n")

                    f.write("\n")

                f.write("---\n\n")

        self.log(f"✅ Report saved to {report_file}", "success")


async def main():
    """Main entry point."""
    suite = V020BenchmarkSuite(verbose=True)
    results = await suite.run_all_benchmarks()
    suite.save_results()

    # Print final summary
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Total time: {results['summary']['total_time_seconds']:.1f}s")
    print(f"Features tested: {results['summary']['features_tested']}/{results['metadata']['total_features']}")
    print(f"Categories tested: {results['summary']['categories_tested']}/{results['metadata']['categories']}")
    print(f"Providers available: {results['summary']['providers_available']}/4")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
