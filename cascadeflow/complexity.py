"""
Query complexity detection for intelligent routing.

Detects query complexity to route appropriately:
- TRIVIAL: "What's 2+2?" → cheapest model
- SIMPLE: "Explain AI" → small/medium model
- MODERATE: "Compare X and Y" → medium model
- HARD: "Analyze deeply..." → large model
- EXPERT: "Write production code..." → best model
"""

from typing import Tuple, Optional, List
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels."""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    HARD = "hard"
    EXPERT = "expert"


class ComplexityDetector:
    """
    Detect query complexity using multiple signals.

    Uses:
    1. Length heuristics
    2. Keyword analysis
    3. Structural patterns
    4. Domain indicators

    Example:
        >>> detector = ComplexityDetector()
        >>> complexity, confidence = detector.detect("What is 2+2?")
        >>> print(complexity)  # TRIVIAL
    """

    TRIVIAL_PATTERNS = [
        r'^what\s+(is|are)\s+\d+\s*[\+\-\*\/]\s*\d+',
        r'^(capital|population|currency)\s+of',
        r'^who\s+(is|was)\s+\w+\s+\w+$',
        r'^when\s+(is|was)',
        r'^where\s+(is|was)',
    ]

    SIMPLE_KEYWORDS = [
        'what', 'who', 'when', 'where', 'define', 'explain',
        'describe', 'meaning', 'definition'
    ]

    MODERATE_KEYWORDS = [
        'compare', 'contrast', 'difference', 'versus', 'vs',
        'how does', 'why does', 'summarize', 'outline'
    ]

    HARD_KEYWORDS = [
        'analyze', 'evaluate', 'assess', 'critically', 'implications',
        'comprehensive', 'detailed', 'in-depth', 'thorough'
    ]

    EXPERT_KEYWORDS = [
        'implement', 'production', 'enterprise', 'scalable', 'optimize',
        'architecture', 'design pattern', 'best practice', 'refactor',
        'performance', 'security', 'deploy'
    ]

    def __init__(self):
        self.stats = {
            "total_detected": 0,
            "by_complexity": {c: 0 for c in QueryComplexity}
        }

    def detect(
            self,
            query: str,
            context: Optional[dict] = None
    ) -> Tuple[QueryComplexity, float]:
        """
        Detect query complexity.

        Args:
            query: User query
            context: Optional context (user tier, domain, etc.)

        Returns:
            Tuple of (complexity_level, confidence_score)
        """
        self.stats["total_detected"] += 1
        query_lower = query.lower().strip()

        # Check trivial patterns first
        for pattern in self.TRIVIAL_PATTERNS:
            if re.match(pattern, query_lower):
                self.stats["by_complexity"][QueryComplexity.TRIVIAL] += 1
                logger.debug(f"Detected TRIVIAL: {query[:50]}...")
                return QueryComplexity.TRIVIAL, 0.95

        # Length-based initial classification
        word_count = len(query.split())

        if word_count <= 10:
            base_complexity = QueryComplexity.SIMPLE
            base_confidence = 0.6
        elif word_count <= 25:
            base_complexity = QueryComplexity.MODERATE
            base_confidence = 0.5
        elif word_count <= 50:
            base_complexity = QueryComplexity.HARD
            base_confidence = 0.5
        else:
            base_complexity = QueryComplexity.EXPERT
            base_confidence = 0.5

        # Keyword-based refinement
        keyword_scores = {
            QueryComplexity.SIMPLE: self._count_keywords(
                query_lower, self.SIMPLE_KEYWORDS
            ),
            QueryComplexity.MODERATE: self._count_keywords(
                query_lower, self.MODERATE_KEYWORDS
            ),
            QueryComplexity.HARD: self._count_keywords(
                query_lower, self.HARD_KEYWORDS
            ),
            QueryComplexity.EXPERT: self._count_keywords(
                query_lower, self.EXPERT_KEYWORDS
            ),
        }

        # Find highest scoring complexity
        max_score = max(keyword_scores.values())
        if max_score > 0:
            for complexity, score in keyword_scores.items():
                if score == max_score:
                    final_complexity = complexity
                    final_confidence = min(0.95, base_confidence + (score * 0.1))
                    break
        else:
            final_complexity = base_complexity
            final_confidence = base_confidence

        # Structural pattern adjustments
        has_multiple_questions = query.count('?') > 1
        has_conditionals = any(
            w in query_lower
            for w in ['if', 'when', 'unless', 'provided']
        )
        has_requirements = any(
            w in query_lower
            for w in ['must', 'should', 'need to', 'required']
        )

        if has_multiple_questions or (has_conditionals and has_requirements):
            if final_complexity == QueryComplexity.SIMPLE:
                final_complexity = QueryComplexity.MODERATE
            elif final_complexity == QueryComplexity.MODERATE:
                final_complexity = QueryComplexity.HARD

        # Context-based adjustment
        if context:
            domain = context.get("domain")
            if domain == "code" and word_count > 15:
                if final_complexity in [
                    QueryComplexity.SIMPLE,
                    QueryComplexity.MODERATE
                ]:
                    final_complexity = QueryComplexity.HARD

        self.stats["by_complexity"][final_complexity] += 1

        logger.debug(
            f"Detected {final_complexity.value} "
            f"(confidence: {final_confidence:.2f}): {query[:50]}..."
        )

        return final_complexity, final_confidence

    def _count_keywords(self, text: str, keywords: List[str]) -> int:
        """Count matching keywords in text."""
        return sum(1 for kw in keywords if kw in text)

    def get_stats(self) -> dict:
        """Get detection statistics."""
        total = self.stats["total_detected"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "distribution": {
                c.value: count / total
                for c, count in self.stats["by_complexity"].items()
            }
        }