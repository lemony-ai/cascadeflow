"""Model discovery example for cascadeflow LangChain integration.

Demonstrates automatic discovery and analysis of optimal cascade pairs.

Run:
    OPENAI_API_KEY=sk-... python examples/langchain_model_discovery.py
"""

import os

from langchain_openai import ChatOpenAI

from cascadeflow.integrations.langchain import (
    CascadeFlow,
    analyze_cascade_pair,
    analyze_model,
    compare_models,
    discover_cascade_pairs,
    find_best_cascade_pair,
)


def main():
    """Run model discovery examples."""
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Usage: OPENAI_API_KEY=sk-... python examples/langchain_model_discovery.py")
        return

    print("\n" + "=" * 80)
    print("cascadeflow Model Discovery - Python LangChain")
    print("=" * 80)

    # YOUR models (configured with YOUR API keys)
    my_models = [
        ChatOpenAI(model="gpt-4o-mini"),
        ChatOpenAI(model="gpt-4o"),
    ]

    print("\n1. ANALYZE INDIVIDUAL MODELS")
    print("-" * 80)
    for model in my_models:
        analysis = analyze_model(model)
        print(f"\nModel: {analysis['model_name']}")
        print(f"  Provider: {analysis['provider']}")
        print(f"  Tier: {analysis['tier']}")
        if analysis["estimated_cost"]:
            print(
                f"  Cost (per 1M tokens): Input ${analysis['estimated_cost']['input']}, Output ${analysis['estimated_cost']['output']}"
            )
        print(f"  Recommendation: {analysis['recommendation']}")

    print("\n\n2. DISCOVER OPTIMAL CASCADE PAIRS")
    print("-" * 80)
    suggestions = discover_cascade_pairs(my_models, min_savings=20.0)

    if suggestions:
        print(f"\nFound {len(suggestions)} cascade pair suggestions:\n")
        for suggestion in suggestions:
            analysis = suggestion["analysis"]
            print(
                f"Rank {suggestion['rank']}: {analysis['drafter_model']} → {analysis['verifier_model']}"
            )
            print(f"  Estimated Savings: {analysis['estimated_savings']:.1f}%")
            print(f"  Recommendation: {analysis['recommendation']}")
            if analysis["warnings"]:
                print(f"  Warnings: {', '.join(analysis['warnings'])}")
            print()

    print("\n3. FIND BEST CASCADE PAIR")
    print("-" * 80)
    best = find_best_cascade_pair(my_models)

    if best:
        print(
            f"\nBest cascade pair: {best['analysis']['drafter_model']} → {best['analysis']['verifier_model']}"
        )
        print(f"Estimated Savings: {best['estimated_savings']:.1f}%")
        print(f"Recommendation: {best['analysis']['recommendation']}\n")

        # Use the best pair
        print("Creating cascadeflow with best pair...")
        CascadeFlow(drafter=best["drafter"], verifier=best["verifier"], quality_threshold=0.7)
        print("✓ cascadeflow created successfully!")

    print("\n4. COMPARE MODELS")
    print("-" * 80)
    comparison = compare_models(my_models)

    print("\nBest Drafter Candidates:")
    for item in comparison["drafter_candidates"]:
        analysis = item["analysis"]
        cost_str = (
            f"${(analysis['estimated_cost']['input'] + analysis['estimated_cost']['output'])/2:.2f}"
            if analysis["estimated_cost"]
            else "Unknown"
        )
        print(f"  - {analysis['model_name']} (Avg cost per 1M: {cost_str})")

    print("\nBest Verifier Candidates:")
    for item in comparison["verifier_candidates"]:
        analysis = item["analysis"]
        cost_str = (
            f"${(analysis['estimated_cost']['input'] + analysis['estimated_cost']['output'])/2:.2f}"
            if analysis["estimated_cost"]
            else "Unknown"
        )
        print(f"  - {analysis['model_name']} (Avg cost per 1M: {cost_str})")

    print("\n5. ANALYZE SPECIFIC PAIR")
    print("-" * 80)
    drafter = ChatOpenAI(model="gpt-4o-mini")
    verifier = ChatOpenAI(model="gpt-4o")

    analysis = analyze_cascade_pair(drafter, verifier)
    print(f"\nPair: {analysis['drafter_model']} → {analysis['verifier_model']}")
    print(f"Valid Configuration: {analysis['valid']}")
    print(f"Estimated Savings: {analysis['estimated_savings']:.1f}%")
    print(f"Recommendation: {analysis['recommendation']}")
    if analysis["warnings"]:
        print(f"Warnings: {len(analysis['warnings'])} warning(s)")
        for warning in analysis["warnings"]:
            print(f"  - {warning}")

    print("\n" + "=" * 80)
    print("Model Discovery Complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
