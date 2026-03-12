"""
Trace Export & Offline Cascade Simulation

Demonstrates how to simulate different cascade configurations offline,
without making any real API calls. Useful for tuning quality thresholds,
comparing model tiers, and projecting cost savings.

Usage:
    python examples/trace_simulation.py
"""

from cascadeflow import ModelConfig, SimulationResult, simulate

# Sample queries representing a realistic workload mix
queries = [
    # Simple queries (should stay on draft model)
    "What is Python?",
    "Hello, how are you?",
    "What's the capital of France?",
    "Convert 100 degrees Fahrenheit to Celsius",
    # Moderate queries
    "Explain the difference between REST and GraphQL APIs",
    "Write a Python function to find the nth Fibonacci number",
    "What are the pros and cons of microservices architecture?",
    # Complex queries (should escalate to verifier)
    "Prove that the square root of 2 is irrational",
    "Explain the proof of Gödel's incompleteness theorem",
    "Derive the Navier-Stokes equations from conservation of momentum",
]

# Define two model configurations to compare
config_a = [
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.005),
]

config_b = [
    ModelConfig(name="llama-3.1-8b", provider="groq", cost=0.00005),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.005),
]


def print_result(label: str, result: SimulationResult) -> None:
    print(f"\n{'=' * 50}")
    print(f"  {label}")
    print(f"{'=' * 50}")
    print(f"  Queries:          {result.total_queries}")
    print(f"  Projected cost:   ${result.projected_cost:.6f}")
    print(f"  Escalation rate:  {result.escalation_rate:.1%}")
    print(f"  Model usage:      {result.model_distribution}")
    print(f"  Complexity:       {result.complexity_distribution}")


# Simulate with different quality thresholds
print("Comparing quality thresholds with GPT-4o-mini -> GPT-4o cascade:\n")

for threshold in [0.4, 0.7, 0.9]:
    result = simulate(queries=queries, models=config_a, quality_threshold=threshold)
    print_result(f"Threshold = {threshold}", result)

# Compare two different draft models
print("\n\nComparing draft models (threshold=0.7):\n")

result_a = simulate(queries=queries, models=config_a, quality_threshold=0.7)
result_b = simulate(queries=queries, models=config_b, quality_threshold=0.7)

print_result("GPT-4o-mini (draft) -> GPT-4o", result_a)
print_result("Llama-3.1-8b (draft) -> GPT-4o", result_b)

diff = result_b.compare(result_a)
print(
    f"\nSwitching to Llama-3.1-8b saves ${-diff['cost_change']:.6f} ({-diff['cost_change_pct']:.1f}%)"
)

# Per-query breakdown
print("\n\nPer-query breakdown (config B, threshold=0.7):")
print(f"{'Query':<50} {'Complexity':<10} {'Model':<20} {'Cost':<10}")
print("-" * 90)
for entry in result_b.per_query:
    print(
        f"{entry.query:<50} {entry.complexity:<10} {entry.projected_model:<20} ${entry.projected_cost:.6f}"
    )
