"""Quality scoring bridge for the cascadeflow PydanticAI integration.

Bridges PydanticAI ModelResponse to cascadeflow core's quality system.
Falls back to heuristic scoring when core quality classes are unavailable.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("cascadeflow.integrations.pydantic_ai.quality")

# Try to import core QualityValidator
try:
    from cascadeflow.quality.quality import QualityValidator

    QUALITY_VALIDATOR_AVAILABLE = True
except Exception:
    QUALITY_VALIDATOR_AVAILABLE = False


def score_response(
    text: str,
    query: str,
    complexity: Optional[str] = None,
) -> float:
    """Score response quality 0-1.

    Uses core QualityValidator if available, falls back to heuristic scorer.

    Args:
        text: Response text to score
        query: Original query for context
        complexity: Detected complexity level

    Returns:
        Quality score between 0 and 1
    """
    if not text or len(text) < 5:
        return 0.2

    if QUALITY_VALIDATOR_AVAILABLE:
        try:
            validator = QualityValidator()
            result = validator.validate(text, query, confidence=0.5, complexity=complexity)
            return result.final_confidence
        except Exception:
            logger.debug("Core QualityValidator failed, falling back to heuristic")

    return _heuristic_quality(text)


def _heuristic_quality(text: str) -> float:
    """Heuristic quality scoring when core validator is unavailable.

    Matches the LangChain integration's calculate_quality heuristic.
    """
    score = 0.4

    # Length bonus
    if len(text) > 50:
        score += 0.1
    if len(text) > 200:
        score += 0.1

    # Structure bonus
    if re.search(r"[.!?]", text):
        score += 0.05
    if re.match(r"^[A-Z]", text):
        score += 0.05

    # Completeness bonus
    if re.search(r"[.!?]$", text.strip()):
        score += 0.05

    # Penalize hedging phrases
    hedging_phrases = ["i don't know", "i'm not sure", "i cannot", "i can't"]
    lower_text = text.lower()
    hedge_count = sum(1 for phrase in hedging_phrases if phrase in lower_text)
    score -= hedge_count * 0.15

    return max(0.1, min(1.0, score))
