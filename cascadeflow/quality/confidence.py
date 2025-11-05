"""
Production-grade confidence estimation for cascadeflow.

UPDATED: Multi-signal confidence using:
1. Query difficulty estimation (NEW)
2. Query-response alignment (NEW)
3. Logprobs (when available) - Primary signal
4. Semantic quality analysis - Always available
5. Provider calibration - Empirical adjustments
6. Temperature-aware scaling

Research-based confidence calculation.

References:
- "Teaching Models to Express Their Uncertainty in Words" (OpenAI, 2022)
- "Language Models (Mostly) Know What They Know" (Kadavath et al., 2022)
- "Calibrating Language Model Probabilities" (Anthropic, 2023)
- "Context-Aware Dual-Metric Framework for Confidence Estimation" (2025)

CHANGELOG:
- 2025-10-06: Fixed semantic analyzer continuous scoring
- 2025-10-06: Added multi-signal confidence (query + alignment + semantic + logprobs)
- 2025-10-07: CRITICAL FIX - Added alignment safety floor to prevent off-topic acceptance
- 2025-10-20: v7.1 FIX - Lowered alignment floor thresholds (0.25, 0.20, 0.15) for improved scorer
"""

import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Optional

from cascadeflow.quality.alignment_scorer import QueryResponseAlignmentScorer

# NEW: Import query difficulty and alignment scorers
from cascadeflow.quality.query_difficulty import QueryDifficultyEstimator

logger = logging.getLogger(__name__)


# ==========================================
# PROVIDER CALIBRATION (Empirical)
# ==========================================

PROVIDER_CONFIDENCE_CALIBRATION = {
    "openai": {
        "base_multiplier": 1.0,
        "logprobs_available": True,
        "finish_reason_boost": {
            "stop": 0.05,
            "length": -0.10,
        },
        "temperature_penalty": lambda t: 0.05 * t,
        "min_confidence": 0.3,
        "max_confidence": 0.98,
    },
    "anthropic": {
        "base_multiplier": 0.95,
        "logprobs_available": False,
        "finish_reason_boost": {
            "end_turn": 0.05,
            "max_tokens": -0.10,
        },
        "temperature_penalty": lambda t: 0.05 * t,
        "min_confidence": 0.3,
        "max_confidence": 0.95,
    },
    "groq": {
        "base_multiplier": 0.90,
        "logprobs_available": False,
        "finish_reason_boost": {
            "stop": 0.05,
            "length": -0.10,
        },
        "temperature_penalty": lambda t: 0.08 * t,
        "min_confidence": 0.25,
        "max_confidence": 0.92,
    },
    "together": {
        "base_multiplier": 1.0,
        "logprobs_available": True,
        "finish_reason_boost": {
            "stop": 0.05,
            "length": -0.10,
        },
        "temperature_penalty": lambda t: 0.05 * t,
        "min_confidence": 0.3,
        "max_confidence": 0.98,
    },
    "vllm": {
        "base_multiplier": 1.0,
        "logprobs_available": True,
        "finish_reason_boost": {
            "stop": 0.05,
            "length": -0.10,
        },
        "temperature_penalty": lambda t: 0.05 * t,
        "min_confidence": 0.3,
        "max_confidence": 0.98,
    },
    "ollama": {
        "base_multiplier": 0.85,
        "logprobs_available": False,
        "finish_reason_boost": {
            "stop": 0.05,
        },
        "temperature_penalty": lambda t: 0.10 * t,
        "min_confidence": 0.2,
        "max_confidence": 0.88,
    },
    "huggingface": {
        "base_multiplier": 0.90,
        "logprobs_available": False,
        "finish_reason_boost": {
            "stop": 0.05,
        },
        "temperature_penalty": lambda t: 0.08 * t,
        "min_confidence": 0.25,
        "max_confidence": 0.92,
    },
}


# ==========================================
# SEMANTIC QUALITY PATTERNS
# ==========================================

STRONG_HEDGING = [
    "i don't know",
    "i'm not sure",
    "i cannot",
    "i don't have information",
    "i don't have access",
    "i'm unable to",
    "i can't answer",
    "uncertain",
    "unclear about",
]

MODERATE_HEDGING = [
    "probably",
    "might be",
    "could be",
    "perhaps",
    "it seems",
    "appears to",
    "may",
    "possibly",
    "likely",
    "i think",
    "i believe",
]

EVASIVE_PATTERNS = [
    "it depends",
    "that's a complex question",
    "there are many factors",
    "it varies",
]


@dataclass
class ConfidenceAnalysis:
    """Detailed confidence analysis with breakdown."""

    final_confidence: float
    logprobs_confidence: Optional[float]
    semantic_confidence: float
    calibrated_confidence: float
    components: dict[str, float]
    method_used: (
        str  # 'logprobs', 'semantic', 'hybrid', 'multi-signal-hybrid', 'multi-signal-semantic'
    )

    # Multi-signal components
    query_difficulty: Optional[float] = None
    alignment_score: Optional[float] = None

    # CRITICAL SAFETY: Alignment floor tracking
    alignment_floor_applied: bool = False


class ProductionConfidenceEstimator:
    """
    Production-grade confidence estimation with multi-signal approach.

    Hierarchy (best to worst):
    1. Multi-signal with logprobs (query + alignment + semantic + logprobs) - Best
    2. Multi-signal semantic (query + alignment + semantic) - Good
    3. Hybrid (logprobs + semantic) - Acceptable
    4. Semantic only - Fallback

    Features:
    - Query difficulty estimation
    - Query-response alignment scoring
    - Provider-specific calibration
    - Temperature-aware scaling
    - Research-backed semantic analysis
    - Continuous scoring (prevents discrete clustering)
    - CRITICAL: Alignment safety floor (prevents off-topic acceptance)
    """

    def __init__(self, provider: str = "openai"):
        """
        Initialize confidence estimator with multi-signal support.

        Args:
            provider: Provider name for calibration
        """
        self.provider = provider
        self.calibration = PROVIDER_CONFIDENCE_CALIBRATION.get(
            provider.lower(), PROVIDER_CONFIDENCE_CALIBRATION["openai"]
        )

        # NEW: Initialize query difficulty estimator
        self.query_estimator = QueryDifficultyEstimator()

        # NEW: Initialize alignment scorer
        self.alignment_scorer = QueryResponseAlignmentScorer()

    def estimate(
        self,
        response: str,
        query: Optional[str] = None,  # STRONGLY RECOMMENDED
        logprobs: Optional[list[float]] = None,
        tokens: Optional[list[str]] = None,
        temperature: float = 0.7,
        finish_reason: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ConfidenceAnalysis:
        """
        Estimate confidence using multi-signal approach with safety checks.

        UPDATED: Now includes alignment safety floor to prevent off-topic acceptance.

        Args:
            response: Model response text
            query: Original query (STRONGLY RECOMMENDED for best results)
            logprobs: Token log probabilities (if available)
            tokens: Token list
            temperature: Sampling temperature
            finish_reason: Completion reason
            metadata: Additional context

        Returns:
            ConfidenceAnalysis with detailed breakdown
        """
        components = {}
        query_difficulty = None
        alignment_score = None

        # 1. Query Difficulty (NEW)
        if query:
            query_difficulty = self.query_estimator.estimate(query)
            components["query_difficulty"] = query_difficulty

        # 2. Primary: Use logprobs if available
        logprobs_conf = None
        if logprobs and len(logprobs) > 0:
            logprobs_conf = self._calculate_from_logprobs(logprobs, tokens, response)
            components["logprobs"] = logprobs_conf

        # 3. Semantic analysis (always compute)
        semantic_conf = self._analyze_semantic_quality(response, query)
        components["semantic"] = semantic_conf

        # 4. Query-Response Alignment (NEW)
        if query:
            alignment_score = self.alignment_scorer.score(
                query=query,
                response=response,
                query_difficulty=query_difficulty if query_difficulty else 0.5,
            )
            components["alignment"] = alignment_score

        # 5. Combine signals (UPDATED LOGIC)
        if logprobs_conf is not None and query and alignment_score is not None:
            # Full multi-signal (all signals available)
            base_confidence = (
                0.50 * logprobs_conf
                + 0.20 * semantic_conf
                + 0.20 * alignment_score
                + 0.10 * (1.0 - query_difficulty)  # Higher difficulty = lower threshold
            )
            method = "multi-signal-hybrid"

        elif logprobs_conf is not None:
            # Hybrid: logprobs + semantic (no query info)
            base_confidence = 0.75 * logprobs_conf + 0.25 * semantic_conf
            method = "hybrid"

        elif query and alignment_score is not None:
            # Semantic + alignment + query (no logprobs)
            base_confidence = (
                0.40 * semantic_conf + 0.40 * alignment_score + 0.20 * (1.0 - query_difficulty)
            )
            method = "multi-signal-semantic"

        else:
            # Fallback: Semantic only
            base_confidence = semantic_conf
            method = "semantic"

        components["base"] = base_confidence

        # 6. Apply provider calibration
        calibrated = self._apply_calibration(base_confidence, temperature, finish_reason)
        components["calibrated"] = calibrated

        # ============================================================================
        # CRITICAL SAFETY CHECK: Alignment Floor (v7.1 CALIBRATED)
        # ============================================================================
        # If alignment is very low (off-topic response), cap confidence regardless
        # of other signals. This prevents accepting garbage from the small model.
        #
        # Research basis:
        # - Off-topic responses typically have alignment < 0.25 (v7.1 calibrated)
        # - Good responses have alignment > 0.60
        # - Capping at 0.30-0.40 creates safety buffer above cascade thresholds
        #
        # v7.1 UPDATE: Lowered thresholds to match improved alignment scorer
        # - Was: 0.30, 0.25, 0.20 (too strict for improved scorer)
        # - Now: 0.25, 0.20, 0.15 (calibrated for v7.1 smart filtering)
        #
        # WHY THE CHANGE:
        # - v7.1 alignment scorer now keeps numbers ("4"), abbreviations ("AI"),
        #   and math expressions ("2+2")
        # - Old thresholds were calibrated for buggy v6 scorer that filtered these
        # - New thresholds maintain same safety level with more accurate scoring

        alignment_floor_applied = False

        if alignment_score is not None and alignment_score < 0.25:  # CHANGED from 0.30
            # Off-topic or very poor alignment detected
            # Cap confidence to force cascade to verifier

            original_confidence = calibrated

            # Progressive capping based on how bad the alignment is
            if alignment_score < 0.15:  # CHANGED from 0.20
                # Severely off-topic (e.g., "weather" answer to "2+2")
                calibrated = min(calibrated, 0.30)
                severity = "severe"
            elif alignment_score < 0.20:  # CHANGED from 0.25
                # Very poor alignment
                calibrated = min(calibrated, 0.35)
                severity = "very poor"
            else:  # 0.20 <= alignment < 0.25 (CHANGED from 0.25-0.30)
                # Poor alignment
                calibrated = min(calibrated, 0.40)
                severity = "poor"

            if calibrated < original_confidence:
                alignment_floor_applied = True
                components["alignment_floor_applied"] = True
                components["alignment_floor_reduction"] = original_confidence - calibrated
                components["alignment_floor_severity"] = severity

                logger.warning(
                    f"⚠️  SAFETY: Alignment floor applied ({severity}). "
                    f"Low alignment ({alignment_score:.3f}) detected. "
                    f"Confidence capped: {original_confidence:.3f} → {calibrated:.3f}. "
                    f"Response will cascade to verifier."
                )

        # ============================================================================

        return ConfidenceAnalysis(
            final_confidence=calibrated,
            logprobs_confidence=logprobs_conf,
            semantic_confidence=semantic_conf,
            calibrated_confidence=calibrated,
            components=components,
            method_used=method,
            query_difficulty=query_difficulty,
            alignment_score=alignment_score,
            alignment_floor_applied=alignment_floor_applied,
        )

    def _calculate_from_logprobs(
        self, logprobs: list[float], tokens: Optional[list[str]], response: str
    ) -> float:
        """
        Calculate confidence from token probabilities.

        Uses multiple methods and combines them:
        1. Geometric mean (standard)
        2. Harmonic mean (reduces outlier impact)
        3. Minimum probability (weakest link)
        4. Entropy-based (consistency)

        Args:
            logprobs: List of log probabilities
            tokens: Token list
            response: Full response text

        Returns:
            Confidence score (0-1)
        """
        if not logprobs:
            return None

        # Convert to probabilities
        probs = [math.exp(lp) for lp in logprobs]

        # Method 1: Geometric mean
        geometric_mean = math.exp(sum(logprobs) / len(logprobs))

        # Method 2: Harmonic mean of top 80% tokens
        sorted_probs = sorted(probs, reverse=True)
        top_80_count = max(1, int(len(sorted_probs) * 0.8))
        top_80_probs = sorted_probs[:top_80_count]
        harmonic_mean = len(top_80_probs) / sum(1 / p for p in top_80_probs if p > 0)

        # Method 3: Minimum probability (weakest link)
        min_prob = min(probs)

        # Method 4: Entropy-based consistency
        entropy = -sum(p * math.log(p) if p > 1e-10 else 0 for p in probs)
        max_entropy = math.log(len(probs)) if len(probs) > 1 else 1.0
        normalized_entropy = 1.0 - min(entropy / max_entropy, 1.0)

        # Weighted combination
        confidence = (
            0.50 * geometric_mean
            + 0.20 * harmonic_mean
            + 0.15 * min_prob
            + 0.15 * normalized_entropy
        )

        return confidence

    def _analyze_semantic_quality(self, response: str, query: Optional[str] = None) -> float:
        """
        Analyze response quality with CONTINUOUS scoring.

        scoring across multiple dimensions to prevent discrete clustering.

        Uses continuous scoring across 5 dimensions:
        1. Hedging (0.0-0.30): Ratio of hedge words per 100 words
        2. Completeness (0.0-0.25): Based on sentence length curve
        3. Specificity (0.0-0.20): Numbers, examples, technical terms
        4. Coherence (0.0-0.15): Contradictions, repetition
        5. Directness (0.0-0.10): Evasiveness measurement

        Total range: 0.20-0.95 (continuous distribution)

        Args:
            response: Response text
            query: Original query (for context)

        Returns:
            Continuous quality score (0.20-0.95)
        """
        if not response or len(response.strip()) < 2:
            return 0.15

        response_lower = response.lower()
        response_clean = response.strip()
        scores = {}

        # ============================================
        # 1. HEDGING SCORE (0.0 to 0.30)
        # ============================================

        strong_hedges = [
            "i don't know",
            "i'm not sure",
            "i cannot",
            "i don't have information",
            "i'm unable to",
            "uncertain",
            "unclear about",
        ]

        moderate_hedges = [
            "probably",
            "might be",
            "could be",
            "perhaps",
            "it seems",
            "appears to",
            "may",
            "possibly",
            "likely",
            "i think",
            "i believe",
        ]

        strong_count = sum(response_lower.count(h) for h in strong_hedges)
        moderate_count = sum(response_lower.count(h) for h in moderate_hedges)

        word_count = len(response_clean.split())
        if word_count > 0:
            strong_ratio = (strong_count / word_count) * 100
            moderate_ratio = (moderate_count / word_count) * 100

            hedge_penalty = min(0.30, (strong_ratio * 0.05) + (moderate_ratio * 0.02))
        else:
            hedge_penalty = 0

        scores["hedging"] = 0.30 - hedge_penalty

        # ============================================
        # 2. COMPLETENESS SCORE (0.0 to 0.25)
        # ============================================

        char_count = len(response_clean)
        sentence_count = len(re.findall(r"[.!?]+", response_clean)) or 1
        avg_sentence_length = char_count / sentence_count

        if avg_sentence_length < 10:
            completeness = 0.05
        elif avg_sentence_length < 30:
            completeness = 0.05 + (avg_sentence_length - 10) / 20 * 0.10
        elif avg_sentence_length <= 150:
            completeness = 0.15 + (150 - avg_sentence_length) / 120 * 0.10
        else:
            completeness = 0.15 - (avg_sentence_length - 150) / 200 * 0.10

        completeness = max(0.0, min(0.25, completeness))
        scores["completeness"] = completeness

        # ============================================
        # 3. SPECIFICITY SCORE (0.0 to 0.20)
        # ============================================

        specificity = 0.10  # Base

        if re.search(r"\d+", response_clean):
            specificity += 0.05

        example_markers = ["for example", "such as", "for instance", "like", "e.g."]
        if any(marker in response_lower for marker in example_markers):
            specificity += 0.03

        words = response_clean.split()
        if words:
            long_words = [w for w in words if len(w) > 8]
            if long_words:
                specificity += min(0.02, len(long_words) / len(words) * 0.10)

        scores["specificity"] = min(0.20, specificity)

        # ============================================
        # 4. COHERENCE SCORE (0.0 to 0.15)
        # ============================================

        coherence = 0.12  # Start high

        contradiction_patterns = [
            (r"\byes\b", r"\bno\b"),
            (r"\btrue\b", r"\bfalse\b"),
            (r"\bcorrect\b", r"\bincorrect\b"),
            (r"\bcan\b", r"\bcannot\b"),
        ]

        for p1, p2 in contradiction_patterns:
            if re.search(p1, response_lower) and re.search(p2, response_lower):
                coherence -= 0.04

        if word_count > 10:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.6:
                coherence -= (0.6 - unique_ratio) * 0.15

        scores["coherence"] = max(0.0, min(0.15, coherence))

        # ============================================
        # 5. DIRECTNESS SCORE (0.0 to 0.10)
        # ============================================

        directness = 0.08  # Base

        evasive_patterns = [
            "it depends",
            "that's a complex question",
            "there are many factors",
            "it varies",
            "there's no simple answer",
        ]

        evasive_count = sum(1 for p in evasive_patterns if p in response_lower)
        directness -= evasive_count * 0.03

        if char_count < 10 and query:
            question_words = ["what", "how", "when", "where", "who", "why"]
            if any(qw in query.lower() for qw in question_words):
                directness += 0.02
            else:
                directness -= 0.04

        scores["directness"] = max(0.0, min(0.10, directness))

        # ============================================
        # TOTAL: Sum all components
        # ============================================

        total_score = sum(scores.values())
        final_score = max(0.20, min(0.95, total_score))

        return final_score

    def _apply_calibration(
        self, base_confidence: float, temperature: float, finish_reason: Optional[str]
    ) -> float:
        """
        Apply provider-specific calibration.

        Args:
            base_confidence: Initial confidence
            temperature: Sampling temperature
            finish_reason: Completion reason

        Returns:
            Calibrated confidence
        """
        confidence = base_confidence

        # 1. Provider base multiplier
        confidence *= self.calibration["base_multiplier"]

        # 2. Temperature penalty
        temp_penalty = self.calibration["temperature_penalty"](temperature)
        confidence -= temp_penalty

        # 3. Finish reason adjustment
        if finish_reason:
            boost_map = self.calibration.get("finish_reason_boost", {})
            boost = boost_map.get(finish_reason, 0)
            confidence += boost

        # 4. Clamp to provider-specific bounds
        min_conf = self.calibration["min_confidence"]
        max_conf = self.calibration["max_confidence"]
        confidence = max(min_conf, min(max_conf, confidence))

        return confidence

    def explain_confidence(self, analysis: ConfidenceAnalysis) -> str:
        """
        Generate human-readable explanation of confidence score.

        UPDATED: Now includes multi-signal information and safety mechanism status.

        Args:
            analysis: ConfidenceAnalysis result

        Returns:
            Explanation string
        """
        lines = [
            f"Confidence: {analysis.final_confidence:.2f}",
            f"Method: {analysis.method_used}",
            "",
        ]

        # Query difficulty
        if analysis.query_difficulty is not None:
            category = (
                "trivial"
                if analysis.query_difficulty < 0.3
                else (
                    "simple"
                    if analysis.query_difficulty < 0.5
                    else "moderate" if analysis.query_difficulty < 0.7 else "complex"
                )
            )
            lines.append(f"  Query difficulty: {analysis.query_difficulty:.2f} ({category})")

        # Logprobs
        if analysis.logprobs_confidence:
            lines.append(
                f"  Logprobs-based: {analysis.logprobs_confidence:.2f} "
                f"(token probability analysis)"
            )

        # Semantic
        lines.append(
            f"  Semantic quality: {analysis.semantic_confidence:.2f} "
            f"(hedging, consistency, completeness)"
        )

        # Alignment
        if analysis.alignment_score is not None:
            lines.append(
                f"  Query-response alignment: {analysis.alignment_score:.2f} "
                f"(keyword coverage, length, directness)"
            )

            # CRITICAL: Show if safety mechanism activated
            if analysis.alignment_floor_applied:
                severity = analysis.components.get("alignment_floor_severity", "unknown")
                reduction = analysis.components.get("alignment_floor_reduction", 0.0)
                lines.append(f"  ⚠️  SAFETY: Alignment floor applied ({severity} off-topic)")
                lines.append(
                    f"      Confidence capped by {reduction:.3f} to prevent garbage acceptance"
                )

        # Calibration
        lines.append(
            f"  After calibration: {analysis.calibrated_confidence:.2f} "
            f"(provider-specific adjustments)"
        )

        # Interpretation
        if analysis.final_confidence >= 0.9:
            interpretation = "Very high - strong confidence in response"
        elif analysis.final_confidence >= 0.75:
            interpretation = "High - good confidence"
        elif analysis.final_confidence >= 0.6:
            interpretation = "Moderate - acceptable quality"
        elif analysis.final_confidence >= 0.4:
            interpretation = "Low - uncertain response"
        else:
            interpretation = "Very low - likely poor quality"

        lines.append(f"\n  → {interpretation}")

        return "\n".join(lines)


# ==========================================
# HELPER: Update BaseProvider
# ==========================================


def update_base_provider_confidence(provider_instance: Any) -> None:
    """
    Update a provider instance to use production confidence estimation.

    Call this in provider __init__ to upgrade confidence calculation.

    Args:
        provider_instance: Provider instance to update
    """
    provider_name = provider_instance.__class__.__name__.replace("Provider", "").lower()
    provider_instance._confidence_estimator = ProductionConfidenceEstimator(provider_name)

    def enhanced_calculate_confidence(
        response: str, metadata: Optional[dict[str, Any]] = None
    ) -> float:
        """Enhanced confidence calculation using production estimator."""
        logprobs = metadata.get("logprobs") if metadata else None
        tokens = metadata.get("tokens") if metadata else None
        temperature = metadata.get("temperature", 0.7) if metadata else 0.7
        finish_reason = metadata.get("finish_reason") if metadata else None

        analysis = provider_instance._confidence_estimator.estimate(
            response=response,
            query=metadata.get("query") if metadata else None,
            logprobs=logprobs,
            tokens=tokens,
            temperature=temperature,
            finish_reason=finish_reason,
            metadata=metadata,
        )

        return analysis.final_confidence

    provider_instance.calculate_confidence = enhanced_calculate_confidence
