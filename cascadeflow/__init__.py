"""
cascadeflow - Smart AI model cascading for cost optimization.

Route queries intelligently across multiple AI models from tiny SLMs
to frontier LLMs based on complexity, domain, and budget.

Features:
- 🚀 Speculative cascades (2-3x faster)
- 💰 60-95% cost savings
- 🎯 Per-prompt domain detection
- 🎨 2.0x domain boost for specialists
- 🔍 Multi-factor optimization
- 🆓 Free tier (Ollama + Groq)
- ⚡ 3 lines of code

Example:
    >>> from cascadeflow import CascadeAgent, CascadePresets
    >>>
    >>> # Auto-detect available models
    >>> models = CascadePresets.auto_detect_models()
    >>>
    >>> # Create agent with intelligence layer
    >>> agent = CascadeAgent(models, enable_caching=True)
    >>>
    >>> # Run query (automatically optimized!)
    >>> result = await agent.run("Fix this Python bug")
    >>> print(f"Used {result.model_used} - Cost: ${result.cost:.6f}")
"""

__version__ = "0.4.0"
__author__ = "Sascha Buehrle"
__license__ = "MIT"

# ==================== CORE CONFIGURATION ====================

import sys

# Visual feedback for streaming (Phase 3)
from cascadeflow.interface.visual_consumer import (
    SilentConsumer,  # NEW: Silent consumer (no visual)
    TerminalVisualConsumer,  # NEW: Terminal consumer with visual feedback
    VisualIndicator,  # NEW: Visual indicator (pulsing dot)
)

# Complexity detection
from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity

# Callbacks for monitoring
from cascadeflow.telemetry.callbacks import CallbackData, CallbackEvent, CallbackManager

# ==================== BACKWARD COMPATIBILITY (MUST BE EARLY) ====================
# Set up backward compatibility BEFORE importing agent/providers
# This allows old imports like: from cascadeflow.exceptions import ...
from . import core, schema

sys.modules["cascadeflow.exceptions"] = schema.exceptions
sys.modules["cascadeflow.result"] = schema.result
sys.modules["cascadeflow.config"] = schema.config
sys.modules["cascadeflow.core.config"] = schema.config  # Also support cascadeflow.core.config
sys.modules["cascadeflow.execution"] = core.execution
sys.modules["cascadeflow.speculative"] = core.cascade  # Old name
sys.modules["cascadeflow.cascade"] = core.cascade  # New name (optional)

from .agent import CascadeAgent

# MVP Speculative cascades with quality validation
from .core.cascade import (
    SpeculativeCascade,  # Legacy wrapper (for compatibility)
    SpeculativeResult,  # Result object
    WholeResponseCascade,  # NEW: MVP whole-response cascade
)

# Execution planning with domain detection
from .core.execution import (
    DomainDetector,
    ExecutionPlan,
    ExecutionStrategy,
    LatencyAwareExecutionPlanner,
    ModelScorer,
)
from .providers import PROVIDER_REGISTRY, BaseProvider, ModelResponse

# Quality validation (NEW in MVP)
from .quality import (
    AdaptiveThreshold,  # Adaptive threshold learning
    ComparativeValidator,  # Optional comparative validation
    QualityConfig,  # Quality configuration profiles
    QualityValidator,  # Quality validation logic
    ValidationResult,  # Validation result object
)

# Original config classes
from .schema.config import (
    DEFAULT_TIERS,
    EXAMPLE_WORKFLOWS,
    CascadeConfig,
    LatencyProfile,
    ModelConfig,
    OptimizationWeights,
    UserTier,
    WorkflowProfile,
)
from .schema.exceptions import (
    BudgetExceededError,
    cascadeflowError,
    ConfigError,
    ModelError,
    ProviderError,
    QualityThresholdError,
    RateLimitError,
    RoutingError,
    ValidationError,
)
from .schema.result import CascadeResult

# Streaming support (Phase 2)
from .streaming import (
    StreamEvent,  # NEW: Event dataclass for streaming
    StreamEventType,  # NEW: Event types for streaming
    StreamManager,
)

# Utilities (now in utils/)
# Smart presets for easy setup (now in utils/)
# Response caching (now in utils/)
from .utils import (
    ResponseCache,
    estimate_tokens,
    format_cost,
    setup_logging,
)

# NEW: Presets 2.0 - One-line agent initialization (WEEK 3 - Milestone 3.1)
from .utils.presets import (
    auto_agent,
    get_balanced_agent,
    get_cost_optimized_agent,
    get_development_agent,
    get_quality_optimized_agent,
    get_speed_optimized_agent,
)

# NEW: Batch Processing (v0.2.1 - Milestone 1)
from .core.batch_config import BatchConfig, BatchStrategy
from .core.batch import BatchResult, BatchProcessingError

# NEW: User Profile System (v0.2.1 - Milestone 3)
from .profiles import (
    TierConfig,
    TierLevel,
    TIER_PRESETS,
    UserProfile,
    UserProfileManager,
)

# NEW: Rate Limiting (v0.2.1 - Milestone 4)
from .limits import (
    RateLimiter,
    RateLimitState,
)

# NEW: Guardrails (v0.2.1 - Milestone 5)
from .guardrails import (
    ContentModerator,
    ModerationResult,
    PIIDetector,
    PIIMatch,
    GuardrailsManager,
    GuardrailViolation,
)

# ==================== MAIN AGENT & RESULT ====================


# ==================== INTELLIGENCE LAYER ====================


# ==================== SUPPORTING FEATURES ====================


# ==================== PROVIDERS ====================


# ==================== UTILITIES ====================


# ==================== EXCEPTIONS ====================


# ==================== EXPORTS ====================

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # ===== CORE CONFIGURATION =====
    "ModelConfig",
    "CascadeConfig",
    "UserTier",
    "WorkflowProfile",
    "LatencyProfile",
    "OptimizationWeights",
    "DEFAULT_TIERS",
    "EXAMPLE_WORKFLOWS",
    # ===== MAIN AGENT & RESULT =====
    "CascadeAgent",
    "CascadeResult",
    # ===== INTELLIGENCE LAYER =====
    # Complexity detection
    "ComplexityDetector",
    "QueryComplexity",
    # Execution planning
    "DomainDetector",
    "ModelScorer",
    "LatencyAwareExecutionPlanner",
    "ExecutionStrategy",
    "ExecutionPlan",
    # MVP Speculative cascades
    "WholeResponseCascade",  # NEW: MVP cascade
    "SpeculativeCascade",  # Legacy wrapper
    "SpeculativeResult",
    # Quality validation (NEW)
    "QualityConfig",  # NEW
    "QualityValidator",  # NEW
    "ValidationResult",  # NEW
    "ComparativeValidator",  # NEW
    "AdaptiveThreshold",  # NEW
    # ===== SUPPORTING FEATURES =====
    "CallbackManager",
    "CallbackEvent",
    "CallbackData",
    "ResponseCache",
    "StreamManager",
    "StreamEventType",  # NEW: Phase 2
    "StreamEvent",  # NEW: Phase 2
    "VisualIndicator",  # NEW: Phase 3
    "TerminalVisualConsumer",  # NEW: Phase 3
    "SilentConsumer",  # NEW: Phase 3
    # Presets 2.0 (WEEK 3 - Milestone 3.1)
    "get_cost_optimized_agent",  # NEW: v0.2.0 - One-line cost optimized setup
    "get_balanced_agent",  # NEW: v0.2.0 - One-line balanced setup
    "get_speed_optimized_agent",  # NEW: v0.2.0 - One-line speed optimized setup
    "get_quality_optimized_agent",  # NEW: v0.2.0 - One-line quality optimized setup
    "get_development_agent",  # NEW: v0.2.0 - One-line development setup
    "auto_agent",  # NEW: v0.2.0 - Helper to select preset by name
    # Batch Processing (v0.2.1 - Milestone 1)
    "BatchConfig",  # NEW: v0.2.1 - Batch configuration
    "BatchStrategy",  # NEW: v0.2.1 - Batch strategy enum
    "BatchResult",  # NEW: v0.2.1 - Batch result with statistics
    "BatchProcessingError",  # NEW: v0.2.1 - Batch processing exception
    # User Profile System (v0.2.1 - Milestone 3)
    "TierConfig",  # NEW: v0.2.1 - Tier configuration
    "TierLevel",  # NEW: v0.2.1 - Tier level enum (FREE, STARTER, PRO, BUSINESS, ENTERPRISE)
    "TIER_PRESETS",  # NEW: v0.2.1 - Predefined tier configurations
    "UserProfile",  # NEW: v0.2.1 - Multi-dimensional user profile
    "UserProfileManager",  # NEW: v0.2.1 - Profile manager for scaling
    # Rate Limiting (v0.2.1 - Milestone 4)
    "RateLimiter",  # NEW: v0.2.1 - Sliding window rate limiter
    "RateLimitState",  # NEW: v0.2.1 - Rate limit state tracking
    "RateLimitError",  # NEW: v0.2.1 - Rate limit exception
    # Guardrails (v0.2.1 - Milestone 5)
    "ContentModerator",  # NEW: v0.2.1 - Content moderation
    "ModerationResult",  # NEW: v0.2.1 - Moderation result
    "PIIDetector",  # NEW: v0.2.1 - PII detection
    "PIIMatch",  # NEW: v0.2.1 - PII match
    "GuardrailsManager",  # NEW: v0.2.1 - Centralized guardrails
    "GuardrailViolation",  # NEW: v0.2.1 - Guardrail violation exception
    # ===== PROVIDERS =====
    "ModelResponse",
    "BaseProvider",
    "PROVIDER_REGISTRY",
    # ===== UTILITIES =====
    "setup_logging",
    "format_cost",
    "estimate_tokens",
    # ===== EXCEPTIONS =====
    "cascadeflowError",
    "ConfigError",
    "ProviderError",
    "ModelError",
    "BudgetExceededError",
    "RateLimitError",
    "QualityThresholdError",
    "RoutingError",
    "ValidationError",
]
