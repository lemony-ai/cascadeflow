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

__version__ = "0.4.2"  # Updated for Day 4.2
__author__ = "Your Name"
__license__ = "MIT"

# ==================== CORE CONFIGURATION ====================

# Original config classes
from .config import (
    ModelConfig,
    CascadeConfig,
    UserTier,
    # Day 4.2 additions
    WorkflowProfile,
    LatencyProfile,
    OptimizationWeights,
    DEFAULT_TIERS,
    EXAMPLE_WORKFLOWS
)

# ==================== MAIN AGENT & RESULT ====================

from .agent import CascadeAgent
from .result import CascadeResult

# ==================== INTELLIGENCE LAYER (Day 4.2) ====================

# Complexity detection
from .complexity import (
    ComplexityDetector,
    QueryComplexity
)

# Execution planning with domain detection
from .execution import (
    DomainDetector,
    ModelScorer,
    LatencyAwareExecutionPlanner,
    ExecutionStrategy,
    ExecutionPlan
)

# Speculative cascades (Google's research)
from .speculative import (
    SpeculativeCascade,
    DeferralStrategy,
    FlexibleDeferralRule,
    SpeculativeResult
)

# ==================== SUPPORTING FEATURES (Day 4.2) ====================

# Callbacks for monitoring
from .callbacks import (
    CallbackManager,
    CallbackEvent,
    CallbackData
)

# Response caching
from .caching import ResponseCache

# Streaming support
from .streaming import StreamManager

# Smart presets for easy setup
from .presets import CascadePresets

# ==================== PROVIDERS ====================

from .providers import (
    ModelResponse,
    BaseProvider,
    PROVIDER_REGISTRY
)

# ==================== UTILITIES ====================

from .utils import (
    setup_logging,
    format_cost,
    estimate_tokens
)

# ==================== EXCEPTIONS ====================

from .exceptions import (
    CascadeFlowError,
    ConfigError,
    ProviderError,
    ModelError,
    BudgetExceededError,
    RateLimitError,
    QualityThresholdError,
    RoutingError,
    ValidationError,
)

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
    # Day 4.2 additions
    "WorkflowProfile",
    "LatencyProfile",
    "OptimizationWeights",
    "DEFAULT_TIERS",
    "EXAMPLE_WORKFLOWS",

    # ===== MAIN AGENT & RESULT =====
    "CascadeAgent",
    "CascadeResult",

    # ===== INTELLIGENCE LAYER (Day 4.2) =====
    # Complexity detection
    "ComplexityDetector",
    "QueryComplexity",
    # Execution planning
    "DomainDetector",
    "ModelScorer",
    "LatencyAwareExecutionPlanner",
    "ExecutionStrategy",
    "ExecutionPlan",
    # Speculative cascades
    "SpeculativeCascade",
    "DeferralStrategy",
    "FlexibleDeferralRule",
    "SpeculativeResult",

    # ===== SUPPORTING FEATURES (Day 4.2) =====
    "CallbackManager",
    "CallbackEvent",
    "CallbackData",
    "ResponseCache",
    "StreamManager",
    "CascadePresets",

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