"""
Phase 3: Semantic Quality + Domain Detection Demo

This example demonstrates the Phase 3 features:
1. Optional semantic ML quality validation (FastEmbed-based)
2. 15-domain detection system with 4-tier keyword weighting
3. Domain-based model recommendations
4. Multi-domain query handling

Features:
- Semantic similarity checking (query ↔ response)
- Toxicity detection
- Domain classification (CODE, DATA, STRUCTURED, RAG, etc.)
- Model recommendations per domain
- Cost optimization through domain routing

Requirements:
- pip install fastembed  # Optional for semantic quality
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def demo_semantic_quality():
    """Demo 1: Optional Semantic ML Quality Validation."""
    print("=" * 80)
    print("DEMO 1: SEMANTIC ML QUALITY VALIDATION")
    print("=" * 80)
    print()

    from cascadeflow.quality.semantic import SemanticQualityChecker

    # Initialize checker (downloads model on first use)
    checker = SemanticQualityChecker(
        similarity_threshold=0.5,
        toxicity_threshold=0.7
    )

    if not checker.is_available():
        print("⚠️  FastEmbed not available. Install with: pip install fastembed")
        print("   Skipping semantic quality demo...")
        print()
        return

    print("✅ FastEmbed model loaded successfully")
    print()

    # Test Case 1: High similarity (related query and response)
    print("Test 1: High Similarity")
    print("-" * 40)
    query1 = "What is machine learning?"
    response1 = "Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed."

    result1 = checker.validate(query1, response1)

    print(f"Query:      {query1}")
    print(f"Response:   {response1}")
    print(f"Similarity: {result1.similarity:.2%}")
    print(f"Passed:     {result1.passed}")
    print(f"Toxic:      {result1.is_toxic}")
    print()

    # Test Case 2: Low similarity (unrelated query and response)
    print("Test 2: Low Similarity")
    print("-" * 40)
    query2 = "What is machine learning?"
    response2 = "The weather in Paris is sunny today with a temperature of 22 degrees."

    result2 = checker.validate(query2, response2)

    print(f"Query:      {query2}")
    print(f"Response:   {response2}")
    print(f"Similarity: {result2.similarity:.2%}")
    print(f"Passed:     {result2.passed}")
    print(f"Reason:     {result2.reason}")
    print()

    # Test Case 3: Toxicity detection
    print("Test 3: Toxicity Detection")
    print("-" * 40)
    query3 = "Explain the implementation."
    response3 = "This violent and hateful approach is racist and should be avoided."

    result3 = checker.validate(query3, response3, check_toxicity=True)

    print(f"Query:        {query3}")
    print(f"Response:     {response3}")
    print(f"Similarity:   {result3.similarity:.2%}")
    print(f"Toxic:        {result3.is_toxic}")
    print(f"Toxic Score:  {result3.toxicity_score:.2f}")
    print(f"Passed:       {result3.passed}")
    print(f"Reason:       {result3.reason}")
    print()

    print("=" * 80)
    print()


def demo_domain_detection():
    """Demo 2: 15-Domain Detection System."""
    print("=" * 80)
    print("DEMO 2: DOMAIN DETECTION (15 DOMAINS)")
    print("=" * 80)
    print()

    from cascadeflow.routing.domain import DomainDetector, Domain

    # Initialize detector
    detector = DomainDetector(confidence_threshold=0.3)

    print("✅ Domain detector initialized (15 production domains)")
    print()

    # Test queries for each major domain
    test_queries = [
        ("Write a Python function to sort a list using async/await", Domain.CODE),
        ("Use pandas to perform ETL on SQL database and calculate correlation", Domain.DATA),
        ("Extract JSON fields from this XML and validate with pydantic schema", Domain.STRUCTURED),
        ("Search documents using semantic search and vector embeddings", Domain.RAG),
        ("Let's have a multi-turn conversation about this topic", Domain.CONVERSATION),
        ("Call the weather API function and execute the tool", Domain.TOOL),
        ("Write a creative story with vivid imagery", Domain.CREATIVE),
        ("Summarize this document and provide a concise synopsis", Domain.SUMMARY),
        ("Translate this text from English to Spanish", Domain.TRANSLATION),
        ("Calculate the derivative of x^2 + 3x + 5", Domain.MATH),
        ("Analyze patient symptoms for medical diagnosis", Domain.MEDICAL),
        ("Review this contract for legal compliance", Domain.LEGAL),
        ("Analyze stock market forecast and portfolio risk", Domain.FINANCIAL),
        ("Analyze this image and describe visual elements", Domain.MULTIMODAL),
    ]

    for query, expected_domain in test_queries:
        domain, confidence = detector.detect(query)

        # Check if detection matches expected
        match_status = "✅" if domain == expected_domain else "⚠️"

        print(f"{match_status} Query: {query[:60]}...")
        print(f"   Detected: {domain.value.upper()} (confidence: {confidence:.0%})")
        print()

    print("=" * 80)
    print()


def demo_domain_scores():
    """Demo 3: Multi-Domain Query Detection."""
    print("=" * 80)
    print("DEMO 3: MULTI-DOMAIN QUERY DETECTION")
    print("=" * 80)
    print()

    from cascadeflow.routing.domain import DomainDetector

    detector = DomainDetector(confidence_threshold=0.3)

    # Complex query spanning multiple domains
    query = "Write a Python algorithm to analyze medical patient data and predict diagnosis"

    print(f"Query: {query}")
    print()

    result = detector.detect_with_scores(query)

    print(f"Primary Domain: {result.domain.value.upper()}")
    print(f"Confidence: {result.confidence:.0%}")
    print()

    print("All Domain Scores:")
    print("-" * 40)

    # Show top 5 domains
    sorted_scores = sorted(result.scores.items(), key=lambda x: x[1], reverse=True)
    for i, (domain, score) in enumerate(sorted_scores[:5], 1):
        bar = "█" * int(score * 40)
        print(f"{i}. {domain.value.upper():15} {score:.0%} {bar}")

    print()

    # Check for multi-domain
    high_conf_domains = [d for d, s in result.scores.items() if s > 0.4]
    if len(high_conf_domains) > 1:
        print(f"🔍 Multi-domain query detected: {[d.value for d in high_conf_domains]}")
        print("   → Recommend using most capable model (GPT-4o or Claude Opus)")

    print()
    print("=" * 80)
    print()


def demo_model_recommendations():
    """Demo 4: Domain-Specific Model Recommendations."""
    print("=" * 80)
    print("DEMO 4: DOMAIN-SPECIFIC MODEL RECOMMENDATIONS")
    print("=" * 80)
    print()

    from cascadeflow.routing.domain import DomainDetector, Domain

    detector = DomainDetector()

    # Show recommendations for key domains
    domains_to_check = [
        Domain.CODE,
        Domain.DATA,
        Domain.STRUCTURED,
        Domain.RAG,
        Domain.MEDICAL,
        Domain.CREATIVE,
    ]

    for domain in domains_to_check:
        print(f"Domain: {domain.value.upper()}")
        print("-" * 40)

        models = detector.get_recommended_models(domain)

        for i, model in enumerate(models[:3], 1):  # Show top 3
            print(f"{i}. {model['name']}")
            reason = model.get('reason', 'Recommended for this domain')
            print(f"   Reason: {reason}")

        print()

    print("=" * 80)
    print()


def demo_keyword_weighting():
    """Demo 5: 4-Tier Keyword Weighting System."""
    print("=" * 80)
    print("DEMO 5: KEYWORD WEIGHTING (4-TIER SYSTEM)")
    print("=" * 80)
    print()

    from cascadeflow.routing.domain import DomainDetector, Domain

    detector = DomainDetector()

    print("Keyword Weight Tiers:")
    print("-" * 40)
    print("• Very Strong (1.5): Highly discriminative (e.g., 'async', 'pandas')")
    print("• Strong (1.0):      Domain-specific terms (e.g., 'function', 'query')")
    print("• Moderate (0.7):    Contextual keywords (e.g., 'code', 'data')")
    print("• Weak (0.3):        Generic terms (minimized per research)")
    print()

    # Show how keywords affect confidence
    queries = [
        ("Use async and await in Python", "Many very_strong CODE keywords"),
        ("Write some code", "Generic keywords only"),
        ("Implement pandas ETL with SQL correlation analysis", "Multiple very_strong DATA keywords"),
    ]

    for query, description in queries:
        domain, confidence = detector.detect(query)
        print(f"Query: {query}")
        print(f"  → {domain.value.upper()} (confidence: {confidence:.0%})")
        print(f"  → {description}")
        print()

    print("=" * 80)
    print()


def demo_cost_optimization():
    """Demo 6: Cost Optimization with Domain Routing."""
    print("=" * 80)
    print("DEMO 6: COST OPTIMIZATION WITH DOMAIN ROUTING")
    print("=" * 80)
    print()

    from cascadeflow.routing.domain import DomainDetector, Domain

    detector = DomainDetector()

    # Scenario: Route queries to optimal models based on domain
    scenarios = [
        {
            "query": "Write a Python function to parse JSON",
            "without_routing": "GPT-4o",
            "without_cost": 0.30,
        },
        {
            "query": "Analyze this medical diagnosis data",
            "without_routing": "GPT-4o",
            "without_cost": 0.30,
        },
        {
            "query": "Extract structured data from this form",
            "without_routing": "GPT-4o",
            "without_cost": 0.30,
        },
    ]

    total_without = 0
    total_with = 0

    print("Routing Comparison:")
    print("-" * 80)
    print(f"{'Query':<50} {'Without':<20} {'With Domain':<20} {'Savings'}")
    print("-" * 80)

    for scenario in scenarios:
        query = scenario["query"]
        domain, confidence = detector.detect(query)

        # Get recommended models
        models = detector.get_recommended_models(domain)
        recommended_model = models[0]["name"] if models else "GPT-4o"

        # Estimate cost savings
        without_cost = scenario["without_cost"]

        # Simple cost model (example)
        if domain == Domain.CODE and "deepseek" in recommended_model.lower():
            with_cost = without_cost * 0.15  # 85% savings
        elif domain == Domain.STRUCTURED and "mini" in recommended_model.lower():
            with_cost = without_cost * 0.20  # 80% savings
        elif domain in [Domain.MEDICAL, Domain.LEGAL]:
            with_cost = without_cost  # Use premium model (no savings)
        else:
            with_cost = without_cost * 0.40  # 60% savings

        savings_pct = ((without_cost - with_cost) / without_cost) * 100

        total_without += without_cost
        total_with += with_cost

        print(f"{query[:48]:<50} ${without_cost:.2f} ({scenario['without_routing']:<8}) "
              f"${with_cost:.2f} ({domain.value[:8]:<8}) {savings_pct:>5.0f}%")

    print("-" * 80)
    total_savings_pct = ((total_without - total_with) / total_without) * 100
    print(f"{'TOTAL':<50} ${total_without:.2f}{' '*12}${total_with:.2f}{' '*12}{total_savings_pct:>5.0f}%")
    print()

    print(f"💰 Total savings: ${total_without - total_with:.2f} ({total_savings_pct:.0f}%)")
    print()
    print("=" * 80)
    print()


def main():
    """Run all Phase 3 demos."""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "PHASE 3: SEMANTIC QUALITY + DOMAIN DETECTION" + " " * 14 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # Demo 1: Semantic Quality Validation
    demo_semantic_quality()

    # Demo 2: Domain Detection
    demo_domain_detection()

    # Demo 3: Multi-Domain Detection
    demo_domain_scores()

    # Demo 4: Model Recommendations
    demo_model_recommendations()

    # Demo 5: Keyword Weighting
    demo_keyword_weighting()

    # Demo 6: Cost Optimization
    demo_cost_optimization()

    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 32 + "DEMO COMPLETE!" + " " * 31 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    print("Summary:")
    print("• Semantic quality validation provides ML-based similarity checking")
    print("• 15-domain detection with research-validated keywords (88% accuracy)")
    print("• 4-tier keyword weighting (very_strong/strong/moderate/weak)")
    print("• Domain-specific model recommendations")
    print("• 60-85% cost savings with intelligent domain routing")
    print()
    print("Next steps:")
    print("1. Install FastEmbed for semantic quality: pip install fastembed")
    print("2. Integrate domain detection into your CascadeAgent")
    print("3. Monitor domain distribution in production")
    print("4. Collect production logs for keyword validation")
    print()


if __name__ == "__main__":
    main()
