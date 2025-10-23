"""
Test Text Cascading Only - Minimal Validation
==============================================

PURPOSE: Validate that text cascading works with alignment scorer fix.

TESTS:
1. Simple math: "What is 2+2?" → Should accept draft
2. Simple facts: "What is Python?" → Should accept draft
3. Trivial query: "Hi" → Should accept draft

EXPECTED RESULTS:
- Draft acceptance rate: 80-100%
- Alignment scores: 0.60-0.80 (not 0.000)
- No alignment floor rejections

BEFORE FIX:
- Acceptance: 0% (all rejected)
- Alignment: 0.000
- Rejection: "alignment_floor_triggered"

AFTER FIX:
- Acceptance: 80-100%
- Alignment: 0.65-0.75
- Drafts accepted
"""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

# Load .env file
try:
    from dotenv import load_dotenv

    # Look for .env in project root
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env from {env_path}")
    else:
        load_dotenv()  # Try to find .env anywhere
        print("✅ Loaded .env")
except ImportError:
    print("⚠️  python-dotenv not installed, trying without it...")
    pass

# Import CascadeFlow components
from cascadeflow.config import ModelConfig
from cascadeflow.quality import QualityConfig
from cascadeflow.quality.alignment_scorer import QueryResponseAlignmentScorer
from cascadeflow.speculative import WholeResponseCascade


@dataclass
class TextCascadeResult:
    """Result from text cascade test."""

    query: str
    draft_accepted: bool
    alignment_score: float
    draft_confidence: float
    rejection_reason: str = None
    quality_score: float = None


class TextCascadeTester:
    """Test text cascading only."""

    def __init__(self):
        """Initialize with OpenAI only."""
        self.results = []
        self.alignment_scorer = QueryResponseAlignmentScorer()

    async def setup_cascade(self):
        """Setup OpenAI cascade (drafter + verifier)."""
        from cascadeflow.providers.openai import OpenAIProvider

        # Check API key
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not set")

        # Create provider
        provider = OpenAIProvider()

        # Setup models
        drafter = ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015, speed_ms=1500)

        verifier = ModelConfig(name="gpt-4o", provider="openai", cost=0.0025, speed_ms=2500)

        providers = {"openai": provider}

        # Create cascade with quality config
        quality_config = QualityConfig.for_cascade()

        cascade = WholeResponseCascade(
            drafter=drafter,
            verifier=verifier,
            providers=providers,
            quality_config=quality_config,
            verbose=True,
        )

        return cascade

    async def test_query(
        self, cascade, query: str, expected_complexity: str = "simple"
    ) -> TextCascadeResult:
        """Test a single text query."""
        print(f"\n{'='*60}")
        print(f"TESTING: {query}")
        print(f"{'='*60}")

        # Execute cascade (TEXT PATH - no tools)
        result = await cascade.execute(
            query=query, max_tokens=100, temperature=0.7, complexity=expected_complexity
        )

        # Extract metrics
        draft_accepted = result.draft_accepted
        draft_confidence = result.draft_confidence
        metadata = result.metadata

        # Get alignment score from metadata
        alignment_score = metadata.get("alignment", 0.0)

        # Get quality metrics
        quality_score = metadata.get("quality_score")
        rejection_reason = metadata.get("rejection_reason")

        print("\n📊 RESULTS:")
        print(f"   Draft Accepted: {'✅ YES' if draft_accepted else '❌ NO'}")
        print(f"   Draft Confidence: {draft_confidence:.3f}")
        print(f"   Alignment Score: {alignment_score:.3f}")
        if quality_score is not None:
            print(f"   Quality Score: {quality_score:.3f}")
        else:
            print("   Quality Score: N/A")

        if rejection_reason:
            print(f"   ⚠️  Rejection: {rejection_reason}")

        # Also test alignment scorer directly
        draft_response = metadata.get("draft_response", "")
        if draft_response:
            direct_alignment = self.alignment_scorer.score(
                query=query, response=draft_response, query_difficulty=0.2
            )
            print(f"   Direct Alignment Test: {direct_alignment:.3f}")

            # Check if they match
            if abs(alignment_score - direct_alignment) > 0.01:
                print("   ⚠️  Warning: Alignment mismatch!")

        test_result = TextCascadeResult(
            query=query,
            draft_accepted=draft_accepted,
            alignment_score=alignment_score,
            draft_confidence=draft_confidence,
            rejection_reason=rejection_reason,
            quality_score=quality_score,
        )

        self.results.append(test_result)
        return test_result

    def print_summary(self):
        """Print test summary."""
        print(f"\n{'='*60}")
        print("TEXT CASCADING TEST SUMMARY")
        print(f"{'='*60}")

        total = len(self.results)
        accepted = sum(1 for r in self.results if r.draft_accepted)
        acceptance_rate = (accepted / total * 100) if total > 0 else 0

        print("\n📈 OVERALL METRICS:")
        print(f"   Total Queries: {total}")
        print(f"   Drafts Accepted: {accepted}")
        print(f"   Drafts Rejected: {total - accepted}")
        print(f"   Acceptance Rate: {acceptance_rate:.1f}%")

        # Alignment analysis
        alignments = [r.alignment_score for r in self.results]
        if alignments:
            avg_alignment = sum(alignments) / len(alignments)
            min_alignment = min(alignments)
            max_alignment = max(alignments)

            print("\n🎯 ALIGNMENT SCORES:")
            print(f"   Average: {avg_alignment:.3f}")
            print(f"   Range: {min_alignment:.3f} - {max_alignment:.3f}")

            # Check for alignment floor issues
            floor_failures = sum(1 for a in alignments if a < 0.30)
            if floor_failures > 0:
                print(f"   ⚠️  Alignment Floor Failures: {floor_failures}")

        # Detailed results
        print("\n📋 DETAILED RESULTS:")
        for i, r in enumerate(self.results, 1):
            status = "✅ ACCEPT" if r.draft_accepted else "❌ REJECT"
            print(f"\n   {i}. {r.query[:40]}...")
            print(f"      Status: {status}")
            print(f"      Confidence: {r.draft_confidence:.3f}")
            print(f"      Alignment: {r.alignment_score:.3f}")
            if r.rejection_reason:
                print(f"      Reason: {r.rejection_reason}")

        # Final verdict
        print(f"\n{'='*60}")
        if acceptance_rate >= 80:
            print("✅ TEXT CASCADING: WORKING!")
            print("   Alignment scorer is functioning correctly.")
        elif acceptance_rate >= 50:
            print("⚠️  TEXT CASCADING: PARTIAL")
            print("   Some issues remain, check alignment scores.")
        else:
            print("❌ TEXT CASCADING: FAILING")
            print("   Alignment scorer needs fixing.")
            print("   Expected alignment > 0.60, seeing < 0.30")
        print(f"{'='*60}\n")


async def run_text_cascade_tests():
    """Run all text cascade tests."""
    tester = TextCascadeTester()

    print("🚀 STARTING TEXT CASCADE TESTS")
    print("=" * 60)

    # Setup cascade
    cascade = await tester.setup_cascade()

    # Test queries - various complexities
    test_cases = [
        # Math queries
        ("What is 2+2?", "trivial"),
        ("Calculate 15 * 7", "trivial"),
        ("What's 100 divided by 4?", "trivial"),
        # Simple facts
        ("What is Python?", "simple"),
        ("What's the capital of France?", "trivial"),
        ("Who wrote Romeo and Juliet?", "trivial"),
        ("Define photosynthesis", "moderate"),
        # Short explanations
        ("Explain AI briefly", "simple"),
        ("What is machine learning?", "simple"),
        ("Describe gravity in one sentence", "simple"),
        # Greetings/casual
        ("Hi", "trivial"),
        ("Hello, how are you?", "trivial"),
    ]

    print(f"\nTesting {len(test_cases)} text queries...\n")

    for query, complexity in test_cases:
        await tester.test_query(cascade, query, complexity)
        await asyncio.sleep(0.5)  # Rate limit

    # Print summary
    tester.print_summary()

    # Return for pytest
    return tester.results


@pytest.mark.asyncio
async def test_text_cascading_only():
    """Pytest entry point."""
    results = await run_text_cascade_tests()

    # Assertions
    acceptance_rate = sum(1 for r in results if r.draft_accepted) / len(results)

    # Check alignment scores are reasonable
    alignments = [r.alignment_score for r in results]
    avg_alignment = sum(alignments) / len(alignments)

    # Assertions
    assert acceptance_rate >= 0.7, f"Acceptance rate too low: {acceptance_rate:.1%}"
    assert avg_alignment >= 0.50, f"Average alignment too low: {avg_alignment:.3f}"
    assert all(a >= 0.10 for a in alignments), "Some alignments are near zero"


if __name__ == "__main__":
    """Run directly for quick testing."""
    asyncio.run(run_text_cascade_tests())
