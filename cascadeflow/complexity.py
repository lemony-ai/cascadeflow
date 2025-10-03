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
    1. Pattern matching (trivial queries)
    2. Keyword analysis (100+ keywords)
    3. Length heuristics
    4. Structural patterns
    5. Code/technical detection
    6. Context awareness

    Example:
        >>> detector = ComplexityDetector()
        >>> complexity, confidence = detector.detect("What is 2+2?")
        >>> print(complexity)  # TRIVIAL
    """

    # Trivial patterns - instant classification
    TRIVIAL_PATTERNS = [
        r'what\s+is\s+\d+\s*[+*/\-]\s*\d+',  # "what is 2+2", "what's 5*3"
        r"what's\s+\d+\s*[+*/\-]\s*\d+",   # "calculate 5+3"
        r'whats\s+\d+\s*[+*/\-]\s*\d+',  # Geography facts
        r'(calculate|compute|solve)\s+\d+\s*[+*/\-]\s*\d+',
        r'(capital|population|currency|language)\s+of\s+\w+',
        r'^(hi|hello|hey|thanks|thank\s+you)[\.\!\?]*$',# Greetings
    ]

    # SIMPLE keywords - basic understanding (30 keywords)
    SIMPLE_KEYWORDS = [
        'what', 'who', 'when', 'where', 'which',
        'define', 'definition', 'meaning', 'means',
        'explain', 'describe', 'tell me',
        'is', 'are', 'does', 'do',
        'simple', 'basic', 'introduction',
        'overview', 'summary', 'briefly',
        'example', 'examples',
        'difference', 'similar',
        'list', 'name',
    ]

    # MODERATE keywords - comparisons, reasoning (35 keywords)
    MODERATE_KEYWORDS = [
        'compare', 'contrast', 'versus', 'vs', 'vs.',
        'difference between', 'distinguish',
        'how does', 'how do', 'why does', 'why do',
        'what are the', 'what is the',
        'advantages', 'disadvantages', 'benefits', 'drawbacks',
        'pros and cons', 'pros', 'cons',
        'summarize', 'outline', 'describe in detail',
        'relationship', 'connection', 'correlation',
        'cause', 'effect', 'impact',
        'process', 'steps', 'procedure',
        'classify', 'categorize',
        'similarities', 'differences',
    ]

    # HARD keywords - deep analysis (40 keywords)
    HARD_KEYWORDS = [
        'analyze', 'analysis', 'examine', 'investigate',
        'evaluate', 'assessment', 'assess', 'appraise',
        'critique', 'critical', 'critically',
        'implications', 'consequences', 'ramifications',
        'comprehensive', 'thorough', 'extensive', 'in-depth',
        'detailed', 'elaborate',
        'justify', 'argue', 'argument',
        'theoretical', 'theory', 'hypothesis',
        'methodology', 'approach', 'framework',
        'perspective', 'viewpoint',
        'synthesize', 'integrate', 'consolidate',
        'interpret', 'interpretation',
        'complex', 'complexity', 'sophisticated',
        'research', 'study',
    ]

    # EXPERT keywords - production/technical (45 keywords)
    EXPERT_KEYWORDS = [
        # Implementation
        'implement', 'implementation', 'build', 'create', 'develop',
        'production', 'production-ready', 'enterprise',
        'deploy', 'deployment', 'release',

        # Architecture
        'architecture', 'design pattern', 'system design',
        'scalable', 'scalability', 'scale',
        'distributed', 'microservices',

        # Optimization
        'optimize', 'optimization', 'performance',
        'efficient', 'efficiency',
        'refactor', 'refactoring',

        # Quality
        'best practice', 'best practices',
        'security', 'secure', 'vulnerability',
        'testing', 'test coverage', 'unit test',
        'debugging', 'troubleshoot',

        # Advanced
        'algorithm', 'algorithmic',
        'integration', 'integrate',
        'migration', 'migrate',
        'infrastructure', 'devops',
        'ci/cd', 'pipeline',
    ]

    # Code patterns that indicate expert complexity
    CODE_PATTERNS = [
        r'\bdef\s+\w+',  # Python function
        r'\bclass\s+\w+',  # Class definition
        r'\bimport\s+\w+',  # Imports
        r'\bfunction\s+\w+',  # JS function
        r'\bconst\s+\w+\s*=',  # Variable declaration
        r'=>',  # Arrow function
        r'\{[\s\S]*\}',  # Code blocks
        r'```',  # Code fence
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

        # 1. Check trivial patterns first (high confidence)
        for pattern in self.TRIVIAL_PATTERNS:
            if re.search(pattern, query_lower):
                self.stats["by_complexity"][QueryComplexity.TRIVIAL] += 1
                logger.debug(f"Detected TRIVIAL (pattern): {query[:50]}...")
                return QueryComplexity.TRIVIAL, 0.95

        # 2. Detect code patterns (auto-boost complexity)
        has_code = any(re.search(p, query) for p in self.CODE_PATTERNS)

        # 3. Length and structure analysis
        words = query.split()
        word_count = len(words)

        # Check for complex structural patterns
        has_multiple_questions = query.count('?') > 1
        has_conditionals = any(w in query_lower for w in [
            'if', 'when', 'unless', 'provided', 'assuming', 'given that'
        ])
        has_requirements = any(w in query_lower for w in [
            'must', 'should', 'need to', 'required', 'ensure', 'guarantee'
        ])
        has_multiple_parts = any(sep in query for sep in [';', '\n', '1.', '2.'])

        structure_score = sum([
            has_multiple_questions,
            has_conditionals and has_requirements,
            has_multiple_parts,
            ])

        # 4. Count keyword matches
        simple_matches = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in query_lower)
        moderate_matches = sum(1 for kw in self.MODERATE_KEYWORDS if kw in query_lower)
        hard_matches = sum(1 for kw in self.HARD_KEYWORDS if kw in query_lower)
        expert_matches = sum(1 for kw in self.EXPERT_KEYWORDS if kw in query_lower)

        # 5. Determine complexity (priority: expert > hard > moderate > simple)
        if expert_matches >= 2:
            # Multiple expert keywords = EXPERT
            final_complexity = QueryComplexity.EXPERT
            final_confidence = 0.85
        elif expert_matches >= 1:
            # ANY expert keyword = at least HARD
            if word_count >= 8:
                final_complexity = QueryComplexity.EXPERT
                final_confidence = 0.80
            else:
                # Short but has expert keyword
                final_complexity = QueryComplexity.HARD
                final_confidence = 0.75
        elif hard_matches >= 2:
            final_complexity = QueryComplexity.HARD
            final_confidence = 0.8
        elif hard_matches >= 1 and word_count > 6:
            final_complexity = QueryComplexity.HARD
            final_confidence = 0.7
        elif moderate_matches >= 2:
            final_complexity = QueryComplexity.MODERATE
            final_confidence = 0.8
        elif moderate_matches >= 1 and word_count > 6:
            final_complexity = QueryComplexity.MODERATE
            final_confidence = 0.7
        elif word_count <= 6 and simple_matches >= 1:
            # Short with simple keywords
            final_complexity = QueryComplexity.SIMPLE
            final_confidence = 0.75
        else:
            # Default based on length only
            if word_count <= 8:
                final_complexity = QueryComplexity.SIMPLE
                final_confidence = 0.6
            elif word_count <= 20:
                final_complexity = QueryComplexity.MODERATE
                final_confidence = 0.6
            else:
                final_complexity = QueryComplexity.HARD
                final_confidence = 0.6

        # 6. Apply code boost
        if has_code:
            if final_complexity == QueryComplexity.SIMPLE:
                final_complexity = QueryComplexity.MODERATE
            elif final_complexity == QueryComplexity.MODERATE:
                final_complexity = QueryComplexity.HARD
            final_confidence = min(0.95, final_confidence + 0.1)

        # 7. Apply structure complexity boost
        if structure_score >= 2:
            if final_complexity == QueryComplexity.SIMPLE:
                final_complexity = QueryComplexity.MODERATE
            elif final_complexity == QueryComplexity.MODERATE:
                final_complexity = QueryComplexity.HARD
            final_confidence = min(0.95, final_confidence + 0.05)

        # 8. Context-based adjustments
        if context:
            final_complexity, final_confidence = self._apply_context(
                final_complexity, final_confidence, context, word_count, has_code
            )

        # 9. Sanity checks
        # Very short queries with expert keywords should be HARD, not EXPERT
        if word_count < 10 and final_complexity == QueryComplexity.EXPERT:
            final_complexity = QueryComplexity.HARD

        # Very long queries without expert keywords should be at least HARD
        if word_count > 50 and final_complexity in [
            QueryComplexity.SIMPLE, QueryComplexity.MODERATE
        ]:
            final_complexity = QueryComplexity.HARD

        self.stats["by_complexity"][final_complexity] += 1

        logger.debug(
            f"Detected {final_complexity.value} "
            f"(confidence: {final_confidence:.2f}, words: {word_count}, "
            f"expert_kw: {expert_matches}, hard_kw: {hard_matches}): "
            f"{query[:50]}..."
        )

        return final_complexity, final_confidence

    def _apply_context(
            self,
            complexity: QueryComplexity,
            confidence: float,
            context: dict,
            word_count: int,
            has_code: bool
    ) -> Tuple[QueryComplexity, float]:
        """Apply context-based adjustments."""

        # Domain-specific complexity boosts
        domain = context.get("domain")

        # Handle None and convert to list
        if domain is None:
            domain = []
        elif isinstance(domain, str):
            domain = [domain]

        # Code domain: boost medium+ queries
        if "code" in domain:
            if word_count > 10 and not has_code:
                # Verbal code questions are often harder
                if complexity == QueryComplexity.SIMPLE:
                    complexity = QueryComplexity.MODERATE
                confidence = min(0.95, confidence + 0.05)
            elif has_code and word_count > 20:
                # Long code queries are expert
                if complexity == QueryComplexity.MODERATE:
                    complexity = QueryComplexity.HARD
                elif complexity == QueryComplexity.HARD:
                    complexity = QueryComplexity.EXPERT

        # Math domain: formulas and proofs are harder
        if "math" in domain:
            if word_count > 15 or any(c in context.get("query", "") for c in ['∫', '∑', '∏', '√']):
                if complexity == QueryComplexity.SIMPLE:
                    complexity = QueryComplexity.MODERATE

        # User tier context
        tier = context.get("tier")
        if tier in ["premium", "enterprise"]:
            # Premium users tend to ask harder questions
            # Slightly boost confidence in higher complexity
            if complexity in [QueryComplexity.HARD, QueryComplexity.EXPERT]:
                confidence = min(0.95, confidence + 0.05)

        return complexity, confidence

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