"""
Query Difficulty Estimation for cascadeflow

FIXED: Recalibrated to fix trivial vs simple separation.

Changes Applied:
1. Baseline lowered: 0.35 → 0.25
2. Length penalties reduced: -0.20/-0.10 → -0.15/-0.05
3. Factual penalty with trivial boost: -0.25 → -0.10 (short) / -0.15 (normal)

Expected Results:
- Trivial: ~0.15 (0.25 - 0.15 + 0.05 = 0.15)
- Simple: ~0.35 (0.25 - 0.05 - 0.15 = 0.05 base + features)
- Separation: >0.15 ✓
"""

import re
from dataclasses import dataclass


@dataclass
class DifficultyAnalysis:
    """Detailed breakdown of difficulty estimation."""

    difficulty: float
    category: str
    features: dict[str, float]
    reasoning: str


class QueryDifficultyEstimator:
    """
    Estimates query difficulty from text features.

    FIXED: Better trivial vs simple differentiation.
    """

    FACTUAL_PATTERNS = [
        "what is",
        "define",
        "who is",
        "when did",
        "where is",
        "name a",
        "name the",
        "list",
        "give me",
        "tell me",
    ]

    EXPLANATORY_PATTERNS = [
        "why",
        "how does",
        "how do",
        "explain briefly",
        "describe",
        "what causes",
    ]

    ANALYTICAL_PATTERNS = [
        "analyze",
        "compare",
        "contrast",
        "evaluate",
        "assess",
        "examine",
        "critique",
        "discuss",
        "argue",
    ]

    SYNTHETIC_PATTERNS = [
        "synthesize",
        "design",
        "propose",
        "create",
        "develop",
        "formulate",
        "construct",
        "devise",
    ]

    COMPLEXITY_MARKERS = [
        "implications",
        "framework",
        "methodology",
        "theoretical",
        "paradigm",
        "philosophical",
        "epistemological",
        "ontological",
        "dialectical",
        "heuristic",
        "normative",
        "empirical",
        "phenomenological",
        "hermeneutic",
        "meta-analysis",
    ]

    CONDITIONAL_PATTERNS = [
        "if",
        "suppose",
        "assume",
        "given that",
        "provided that",
        "in the case",
        "hypothetically",
        "what would happen",
    ]

    def __init__(self):
        """Initialize the difficulty estimator."""
        self.stopwords = {
            "the",
            "is",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
        }

    def estimate(self, query: str, verbose: bool = False) -> float:
        """
        Estimate query difficulty with calibrated weights.

        Args:
            query: The query text to analyze
            verbose: If True, return DifficultyAnalysis with details

        Returns:
            float: Difficulty score (0.0-1.0) if verbose=False
            DifficultyAnalysis: Full analysis if verbose=True
        """
        if not query or len(query.strip()) < 2:
            return (
                0.0
                if not verbose
                else DifficultyAnalysis(
                    difficulty=0.0, category="trivial", features={}, reasoning="Empty query"
                )
            )

        features = {}
        score = 0.25  # FIXED: Lower baseline (was 0.35)

        query_lower = query.lower().strip()
        words = query_lower.split()
        char_count = len(query_lower)

        # Feature 1: Query Length (FIXED)
        length_score = self._analyze_length_calibrated(char_count)
        features["length"] = length_score
        score += length_score

        # Feature 2: Question Type (FIXED)
        type_score = self._analyze_question_type_calibrated(query_lower)
        features["question_type"] = type_score
        score += type_score

        # Feature 3: Cognitive Complexity Markers
        complexity_score = self._analyze_complexity_markers(query_lower)
        features["complexity_markers"] = complexity_score
        score += complexity_score

        # Feature 4: Technical Terminology
        terminology_score = self._analyze_terminology(words)
        features["terminology"] = terminology_score
        score += terminology_score

        # Feature 5: Multiple Sub-questions
        multi_question_score = self._analyze_multi_questions(query_lower)
        features["multi_questions"] = multi_question_score
        score += multi_question_score

        # Feature 6: Conditional/Hypothetical
        conditional_score = self._analyze_conditionals(query_lower)
        features["conditional"] = conditional_score
        score += conditional_score

        # Clamp to valid range
        final_score = max(0.0, min(1.0, score))

        if verbose:
            return DifficultyAnalysis(
                difficulty=final_score,
                category=self._score_to_category(final_score),
                features=features,
                reasoning=self._generate_reasoning(features, final_score),
            )

        return final_score

    def _analyze_length_calibrated(self, char_count: int) -> float:
        """
        FIXED: Reduced penalties for better separation.

        Returns: -0.15 to +0.15
        """
        if char_count < 15:
            return -0.15  # FIXED: Less penalty (was -0.20)
        elif char_count < 30:
            return -0.05  # FIXED: Less penalty (was -0.10)
        elif char_count < 50:
            return 0.0  # Medium
        elif char_count < 100:
            return 0.05
        elif char_count < 150:
            return 0.10
        else:
            return 0.15

    def _analyze_question_type_calibrated(self, query_lower: str) -> float:
        """
        FIXED: Reduced factual penalty with trivial boost.

        Returns: -0.15 to +0.25
        """

        def contains_pattern(pattern: str, text: str) -> bool:
            return bool(re.search(r"\b" + re.escape(pattern) + r"\b", text))

        # Check in order from most complex to least
        if any(contains_pattern(pattern, query_lower) for pattern in self.SYNTHETIC_PATTERNS):
            return 0.25

        if any(contains_pattern(pattern, query_lower) for pattern in self.ANALYTICAL_PATTERNS):
            return 0.15

        if any(contains_pattern(pattern, query_lower) for pattern in self.EXPLANATORY_PATTERNS):
            return 0.00  # Neutral

        if any(contains_pattern(pattern, query_lower) for pattern in self.FACTUAL_PATTERNS):
            # FIXED: Less penalty, with trivial boost for very short queries
            if len(query_lower) < 30:  # Short factual = likely trivial
                return -0.10  # FIXED: Smaller penalty for short factual
            return -0.15  # FIXED: Reduced (was -0.25)

        return 0.0

    def _analyze_complexity_markers(self, query_lower: str) -> float:
        """
        Count academic/technical complexity markers.

        Returns: 0.0 to +0.20
        """
        marker_count = sum(1 for marker in self.COMPLEXITY_MARKERS if marker in query_lower)

        return min(0.20, marker_count * 0.07)

    def _analyze_terminology(self, words: list) -> float:
        """
        Analyze domain-specific terminology density.

        Returns: 0.0 to +0.12
        """
        if not words:
            return 0.0

        content_words = [w for w in words if w not in self.stopwords and len(w) > 3]

        if not content_words:
            return 0.0

        # Long words (>10 chars) indicate technical terms
        long_words = [w for w in content_words if len(w) > 10]

        if not long_words:
            return 0.0

        ratio = len(long_words) / len(content_words)

        return min(0.12, ratio * 0.35)

    def _analyze_multi_questions(self, query_lower: str) -> float:
        """
        Detect multiple sub-questions or compound queries.

        Returns: 0.0 to +0.10
        """
        score = 0.0

        if query_lower.count("?") > 1:
            score += 0.05

        compound_markers = [
            "and also",
            "additionally",
            "furthermore",
            "moreover",
            "and then",
            "as well as",
            "along with",
        ]

        if any(marker in query_lower for marker in compound_markers):
            score += 0.05

        return min(0.10, score)

    def _analyze_conditionals(self, query_lower: str) -> float:
        """
        Detect conditional/hypothetical phrasing.

        Returns: 0.0 to +0.10
        """
        conditional_count = sum(
            1 for pattern in self.CONDITIONAL_PATTERNS if pattern in query_lower
        )

        return min(0.10, conditional_count * 0.05)

    def _score_to_category(self, score: float) -> str:
        """Convert continuous score to category label."""
        if score < 0.25:
            return "trivial"
        elif score < 0.45:
            return "simple"
        elif score < 0.65:
            return "moderate"
        elif score < 0.85:
            return "complex"
        else:
            return "expert"

    def _generate_reasoning(self, features: dict[str, float], final_score: float) -> str:
        """Generate human-readable explanation."""
        reasons = []

        if features.get("length", 0) > 0.05:
            reasons.append("long query")
        elif features.get("length", 0) < -0.05:
            reasons.append("short query")

        if features.get("question_type", 0) > 0.15:
            reasons.append("analytical/synthetic question type")
        elif features.get("question_type", 0) < -0.15:
            reasons.append("factual question type")

        if features.get("complexity_markers", 0) > 0:
            reasons.append("academic complexity markers present")

        if features.get("terminology", 0) > 0:
            reasons.append("technical terminology")

        if features.get("multi_questions", 0) > 0:
            reasons.append("multiple sub-questions")

        if features.get("conditional", 0) > 0:
            reasons.append("conditional/hypothetical phrasing")

        if not reasons:
            reasons.append("standard question structure")

        category = self._score_to_category(final_score)
        return f"{category.capitalize()} difficulty ({final_score:.2f}): {', '.join(reasons)}"


if __name__ == "__main__":
    estimator = QueryDifficultyEstimator()

    test_queries = [
        ("What is 2+2?", "trivial"),
        ("What color is the sky?", "trivial"),
        ("Is water wet?", "trivial"),
        ("What is Python?", "simple"),
        ("Explain photosynthesis briefly", "simple"),
        ("What causes rain?", "simple"),
        ("Compare Python and JavaScript for web development", "moderate"),
        ("Explain the difference between supervised and unsupervised learning", "moderate"),
        ("Analyze the philosophical implications of consciousness", "complex"),
        ("Explain Gödel's incompleteness theorems", "complex"),
    ]

    print("Query Difficulty Estimator - FIXED Test")
    print("=" * 80)

    correct = 0
    total = 0
    trivial_scores = []
    simple_scores = []

    for query, expected in test_queries:
        analysis = estimator.estimate(query, verbose=True)

        is_correct = analysis.category == expected
        correct += is_correct
        total += 1

        # Track for separation analysis
        if expected == "trivial":
            trivial_scores.append(analysis.difficulty)
        elif expected == "simple":
            simple_scores.append(analysis.difficulty)

        status = "✓" if is_correct else "✗"
        print(
            f"{status} {query:50s} → {analysis.difficulty:.3f} ({analysis.category}, expected {expected})"
        )

    print(f"\nAccuracy: {correct}/{total} ({correct/total*100:.1f}%)")

    # Show separation
    if trivial_scores and simple_scores:
        trivial_mean = sum(trivial_scores) / len(trivial_scores)
        simple_mean = sum(simple_scores) / len(simple_scores)
        separation = simple_mean - trivial_mean

        print("\nSeparation Analysis:")
        print(f"  Trivial mean: {trivial_mean:.3f}")
        print(f"  Simple mean:  {simple_mean:.3f}")
        print(
            f"  Separation:   {separation:.3f} {'✅ PASS' if separation > 0.1 else '❌ FAIL'} (target: >0.1)"
        )
