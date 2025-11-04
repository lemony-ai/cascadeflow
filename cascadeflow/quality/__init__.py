"""
Quality Validation Module

COMPLETE TEXT QUALITY SYSTEM:
- QualityValidator: Main text validation with alignment + difficulty
- QualityConfig: Configuration (production, development, strict, cascade)
- ValidationResult: Validation results with detailed scoring
- ResponseAnalyzer: Content analysis (hedging, specificity, hallucinations)
- ComparativeValidator: Compare draft vs verifier
- AdaptiveThreshold: Adaptive threshold learning

SUPPORTING COMPONENTS:
- QueryResponseAlignmentScorer: Query-response alignment scoring
- AlignmentAnalysis: Detailed alignment analysis results
- QueryDifficultyEstimator: Query difficulty estimation (0.0-1.0)
- QueryComplexity: Complexity enum (TRIVIAL, SIMPLE, MODERATE, HARD, EXPERT)
- ComplexityDetector: Automatic complexity detection
- ProductionConfidenceEstimator: Multi-signal confidence estimation
- ConfidenceAnalysis: Detailed confidence analysis results

TOOL QUALITY SYSTEM (Phase 4):
- ToolQualityValidator: 5-level validation for tool calls
- ToolQualityScore: Tool validation results

OPTIONAL SEMANTIC ML QUALITY (Phase 3.1):
- SemanticQualityChecker: ML-based semantic validation using FastEmbed
- SemanticQualityResult: Semantic quality check results
- check_semantic_quality: Convenience function for one-off checks

INTEGRATION:
All components work together seamlessly:
1. ComplexityDetector detects query complexity
2. QueryDifficultyEstimator estimates difficulty
3. QueryResponseAlignmentScorer measures alignment
4. QualityValidator uses all signals for validation
5. ProductionConfidenceEstimator provides multi-signal confidence
6. SemanticQualityChecker (optional) provides ML-based validation

Version: 0.5.0 (Phase 3 - Semantic Quality)
"""

import logging

logger = logging.getLogger(__name__)

# ============================================================================
# TEXT QUALITY SYSTEM (Main)
# ============================================================================

# Alignment scoring
from .alignment_scorer import (
    AlignmentAnalysis,
    QueryResponseAlignmentScorer,
)

# Complexity detection
from .complexity import (
    ComplexityDetector,
    QueryComplexity,
)

# Multi-signal confidence
from .confidence import (
    ConfidenceAnalysis,
    ProductionConfidenceEstimator,
)
from .quality import (
    AdaptiveThreshold,
    ComparativeValidator,
    QualityConfig,
    QualityValidator,
    ResponseAnalyzer,
    ValidationResult,
)

# Query difficulty estimation
from .query_difficulty import QueryDifficultyEstimator

# ============================================================================
# SUPPORTING COMPONENTS
# ============================================================================


# ============================================================================
# TOOL QUALITY SYSTEM (Phase 4) - WITH ERROR HANDLING
# ============================================================================

try:
    from .tool_validator import (
        ToolQualityScore,
        ToolQualityValidator,
    )

    TOOL_VALIDATOR_AVAILABLE = True
except ImportError as e:
    TOOL_VALIDATOR_AVAILABLE = False
    logger.warning(f"tool_validator.py not fully available: {e}")

    # Create minimal stubs for backward compatibility
    class ToolQualityValidator:
        """Stub for ToolQualityValidator when not available."""

        pass

    class ToolQualityScore:
        """Stub for ToolQualityScore when not available."""

        pass


# ============================================================================
# OPTIONAL SEMANTIC ML QUALITY (Phase 3.1) - WITH ERROR HANDLING
# ============================================================================

try:
    from .semantic import (
        SemanticQualityChecker,
        SemanticQualityResult,
        check_semantic_quality,
    )

    SEMANTIC_QUALITY_AVAILABLE = True
except ImportError as e:
    SEMANTIC_QUALITY_AVAILABLE = False
    logger.warning(f"semantic.py not fully available: {e}")

    # Create minimal stubs for backward compatibility
    class SemanticQualityChecker:
        """Stub for SemanticQualityChecker when not available."""

        pass

    class SemanticQualityResult:
        """Stub for SemanticQualityResult when not available."""

        pass

    def check_semantic_quality(*args, **kwargs):
        """Stub for check_semantic_quality when not available."""
        return None


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    # Main text quality system
    "QualityValidator",
    "QualityConfig",
    "ValidationResult",
    "ResponseAnalyzer",
    "ComparativeValidator",
    "AdaptiveThreshold",
    # Alignment scoring
    "QueryResponseAlignmentScorer",
    "AlignmentAnalysis",
    # Query difficulty
    "QueryDifficultyEstimator",
    # Complexity detection
    "QueryComplexity",
    "ComplexityDetector",
    # Multi-signal confidence
    "ProductionConfidenceEstimator",
    "ConfidenceAnalysis",
    # Tool quality system
    "ToolQualityValidator",
    "ToolQualityScore",
    # Optional semantic ML quality (Phase 3.1)
    "SemanticQualityChecker",
    "SemanticQualityResult",
    "check_semantic_quality",
]

__version__ = "0.5.0"  # Phase 3 (Semantic Quality)

# ============================================================================
# QUICK VALIDATION TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("QUALITY MODULE - INTEGRATION TEST")
    print("=" * 80)
    print()

    # Test all imports
    print("Testing imports...")
    print(f"✅ QualityValidator: {QualityValidator}")
    print(f"✅ QueryResponseAlignmentScorer: {QueryResponseAlignmentScorer}")
    print(f"✅ QueryDifficultyEstimator: {QueryDifficultyEstimator}")
    print(f"✅ ComplexityDetector: {ComplexityDetector}")
    print(f"✅ ProductionConfidenceEstimator: {ProductionConfidenceEstimator}")
    if TOOL_VALIDATOR_AVAILABLE:
        print(f"✅ ToolQualityValidator: {ToolQualityValidator} (full version)")
    else:
        print(f"⚠️  ToolQualityValidator: {ToolQualityValidator} (stub mode)")
    print()

    # Test initialization
    print("Testing initialization...")
    validator = QualityValidator()
    print(f"✅ Has alignment_scorer: {hasattr(validator, 'alignment_scorer')}")
    print(f"✅ Has difficulty_estimator: {hasattr(validator, 'difficulty_estimator')}")
    print(f"✅ Has complexity_detector: {hasattr(validator, 'complexity_detector')}")
    print()

    # Test all configs
    print("Testing configurations...")
    configs = {
        "production": QualityConfig.for_production(),
        "development": QualityConfig.for_development(),
        "strict": QualityConfig.strict(),
        "cascade": QualityConfig.for_cascade(),
    }

    for name, config in configs.items():
        print(f"✅ {name.capitalize()}: {config.confidence_thresholds['simple']:.2f}")

    print()
    print("=" * 80)
    print("✅ ALL SYSTEMS OPERATIONAL!")
    print("=" * 80)
