"""
CascadeFlow - Smart AI model cascading for cost optimization.

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

__version__ = "0.1.0"  # Updated for MVP cascade
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
    CascadeFlowError,
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
    PRESET_ANTHROPIC_ONLY,
    PRESET_BEST_OVERALL,
    PRESET_FREE_LOCAL,
    PRESET_OPENAI_ONLY,
    PRESET_ULTRA_CHEAP,
    PRESET_ULTRA_FAST,
    PRESETS,
    CascadePresets,
    PerformanceMode,
    QualityMode,
    ResponseCache,
    create_preset,
    estimate_tokens,
    format_cost,
    setup_logging,
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
    "CascadePresets",
    "PRESET_BEST_OVERALL",  # NEW: v0.1.1
    "PRESET_ULTRA_FAST",  # NEW: v0.1.1
    "PRESET_ULTRA_CHEAP",  # NEW: v0.1.1
    "PRESET_OPENAI_ONLY",  # NEW: v0.1.1
    "PRESET_ANTHROPIC_ONLY",  # NEW: v0.1.1
    "PRESET_FREE_LOCAL",  # NEW: v0.1.1
    "PRESETS",  # NEW: v0.1.1
    "create_preset",  # NEW: v0.1.1
    "QualityMode",  # NEW: v0.1.1
    "PerformanceMode",  # NEW: v0.1.1
    # ===== PROVIDERS =====
    "ModelResponse",
    "BaseProvider",
    "PROVIDER_REGISTRY",
    # ===== UTILITIES =====
    "setup_logging",
    "format_cost",
    "estimate_tokens",
    # ===== EXCEPTIONS =====
    "CascadeFlowError",
    "ConfigError",
    "ProviderError",
    "ModelError",
    "BudgetExceededError",
    "RateLimitError",
    "QualityThresholdError",
    "RoutingError",
    "ValidationError",
]
