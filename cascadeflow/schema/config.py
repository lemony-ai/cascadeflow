"""
Configuration System for cascadeflow
====================================

This module contains all configuration dataclasses for cascadeflow.

Core Classes:
    - ModelConfig: Configure individual model providers
    - CascadeConfig: Top-level cascade configuration
    - OptimizationWeights: Cost/speed/quality optimization weights
    - LatencyProfile: Latency constraints and preferences
    - UserTier: User-tier specific settings
    - WorkflowProfile: Workflow-specific configuration profiles

Predefined Constants:
    - DEFAULT_TIERS: Pre-configured user tier settings
    - EXAMPLE_WORKFLOWS: Example workflow profiles (interactive, batch, realtime)

Usage:
    >>> model = ModelConfig(
    ...     name="gpt-4o",
    ...     provider="openai",
    ...     cost=0.00625
    ... )
    >>>
    >>> config = CascadeConfig(
    ...     max_cascade_depth=2,
    ...     enable_caching=True
    ... )

See Also:
    - schema.result.CascadeResult for result types
    - quality.quality.QualityConfig for quality validation settings
"""

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==================== EXISTING: ModelConfig (KEEP AS-IS) ====================


class ModelConfig(BaseModel):
    """
    Configuration for a single model in the cascade.

    Example:
        >>> model = ModelConfig(
        ...     name="gpt-3.5-turbo",
        ...     provider="openai",
        ...     cost=0.002
        ... )
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Model name (e.g., 'gpt-3.5-turbo')")
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic')")
    cost: float = Field(0.0, description="Cost per 1K tokens in USD")

    # Optional settings
    keywords: list[str] = Field(default_factory=list, description="Keywords for routing")
    domains: list[str] = Field(default_factory=list, description="Domains (e.g., 'code', 'math')")
    max_tokens: int = Field(4096, description="Maximum tokens for generation")
    system_prompt: Optional[str] = Field(None, description="System prompt override")
    temperature: float = Field(0.7, description="Temperature for generation")

    # API configuration
    api_key: Optional[str] = Field(None, description="API key (or use env var)")
    base_url: Optional[str] = Field(None, description="Custom base URL (for vLLM, etc.)")

    # Provider-specific options
    extra: dict[str, Any] = Field(default_factory=dict, description="Provider-specific options")

    # NEW: Add these for Day 4.2 support
    speed_ms: int = Field(1000, description="Expected latency in milliseconds")
    quality_score: float = Field(0.7, description="Base quality score (0-1)")

    # Phase 3: Tool calling support
    supports_tools: bool = Field(True, description="Whether model supports tool/function calling")

    def __init__(self, name: Optional[str] = None, **kwargs):
        """
        Initialize ModelConfig with support for positional name argument.

        This allows both:
            ModelConfig(name="gpt-4", provider="openai", cost=0.03)
            ModelConfig("gpt-4", provider="openai", cost=0.03)
        """
        if name is not None:
            kwargs["name"] = name
        super().__init__(**kwargs)

    @field_validator("cost")
    @classmethod
    def validate_cost(cls, v):
        if v < 0:
            raise ValueError("Cost must be non-negative")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        # Make case-insensitive
        v = v.lower()
        allowed = [
            "openai",
            "anthropic",
            "groq",
            "ollama",
            "huggingface",
            "together",
            "vllm",
            "replicate",
            "custom",
        ]
        if v not in allowed:
            raise ValueError(f"Provider must be one of {allowed}")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v):
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v):
        if v <= 0:
            raise ValueError("max_tokens must be positive")
        return v


# ==================== EXISTING: CascadeConfig (KEEP AS-IS) ====================


class CascadeConfig(BaseModel):
    """
    Configuration for cascading strategy.

    Example:
        >>> config = CascadeConfig(
        ...     quality_threshold=0.85,
        ...     max_budget=0.05
        ... )
    """

    # Quality control
    quality_threshold: float = Field(0.7, description="Minimum confidence to accept result (0-1)")
    require_minimum_tokens: int = Field(10, description="Minimum response length in tokens")

    # Budget control
    max_budget: float = Field(1.0, description="Maximum cost per query in USD")
    track_costs: bool = Field(True, description="Enable cost tracking")

    # Performance
    max_retries: int = Field(2, description="Max retries per model")
    timeout: int = Field(30, description="Timeout per model call in seconds")

    # Routing strategy
    routing_strategy: str = Field(
        "adaptive", description="Routing strategy (adaptive, cost_first, quality_first, semantic)"
    )

    # Speculative cascades (NEW!)
    use_speculative: bool = Field(True, description="Use speculative cascades (recommended!)")
    deferral_strategy: str = Field(
        "comparative", description="Deferral strategy for speculative cascades"
    )
    comparative_delta: float = Field(0.2, description="Min confidence delta for deferral")

    # Logging & debugging
    verbose: bool = Field(False, description="Show routing decisions")
    log_level: str = Field("INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    track_metrics: bool = Field(True, description="Track latency, tokens, etc.")

    @field_validator("quality_threshold")
    @classmethod
    def validate_threshold(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Quality threshold must be between 0 and 1")
        return v

    @field_validator("max_budget")
    @classmethod
    def validate_budget(cls, v):
        if v < 0:
            raise ValueError("Max budget must be non-negative")
        return v

    @field_validator("routing_strategy")
    @classmethod
    def validate_routing_strategy(cls, v):
        allowed = ["adaptive", "cost_first", "quality_first", "speed_first", "semantic"]
        if v not in allowed:
            raise ValueError(f"Routing strategy must be one of {allowed}")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v):
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v


# ==================== NEW: Latency Profile ====================


@dataclass
class LatencyProfile:
    """
    Defines acceptable latency ranges and preferences.

    Used by UserTier to control speed vs cost tradeoffs.

    Example:
        >>> profile = LatencyProfile(
        ...     max_total_ms=1500,
        ...     max_per_model_ms=1000,
        ...     prefer_parallel=True,
        ...     skip_cascade_threshold=1000
        ... )
    """

    max_total_ms: int  # Max total query time (milliseconds)
    max_per_model_ms: int  # Max time per model call (milliseconds)
    prefer_parallel: bool  # Use parallel execution when beneficial
    skip_cascade_threshold: int  # If latency < this, consider skipping cascade


# ==================== NEW: Optimization Weights ====================


@dataclass
class OptimizationWeights:
    """
    Multi-factor optimization weights (must sum to 1.0).

    These GUIDE decisions, not dictate them.

    Example:
        >>> weights = OptimizationWeights(
        ...     cost=0.20,
        ...     speed=0.50,
        ...     quality=0.30
        ... )
    """

    cost: float  # Weight for cost optimization (0-1)
    speed: float  # Weight for speed optimization (0-1)
    quality: float  # Weight for quality optimization (0-1)

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = self.cost + self.speed + self.quality
        if not (0.99 <= total <= 1.01):  # Allow small floating point error
            raise ValueError(f"Weights must sum to 1.0, got {total}")


# ==================== ENHANCED: User Tier (REPLACES OLD VERSION) ====================


class UserTier(BaseModel):
    """
    ENHANCED: Dynamic user tier with latency awareness.

    Key features:
    - Latency profiles for speed control
    - Optimization weights for multi-factor scoring
    - No fixed execution modes (adapts per query)
    - Full developer control

    Example:
        >>> tier = UserTier(
        ...     name="premium",
        ...     latency=LatencyProfile(
        ...         max_total_ms=2000,
        ...         max_per_model_ms=1500,
        ...         prefer_parallel=True,
        ...         skip_cascade_threshold=1500
        ...     ),
        ...     optimization=OptimizationWeights(
        ...         cost=0.2, speed=0.5, quality=0.3
        ...     ),
        ...     max_budget=0.05
        ... )
    """

    name: str = Field(..., description="Tier name")

    # ===== LATENCY CONFIGURATION =====
    latency: LatencyProfile = Field(..., description="Latency profile for this tier")

    # ===== OPTIMIZATION WEIGHTS =====
    optimization: OptimizationWeights = Field(..., description="Multi-factor optimization weights")

    # ===== BUDGET CONTROL =====
    max_budget: float = Field(..., description="Max cost per query (USD)")
    preferred_budget: Optional[float] = Field(None, description="Target budget to aim for")
    daily_budget: Optional[float] = Field(None, description="Daily budget cap")
    monthly_budget: Optional[float] = Field(None, description="Monthly budget cap")

    # ===== QUALITY CONTROL =====
    quality_threshold: float = Field(0.7, description="Minimum acceptable quality (0-1)")
    target_quality: Optional[float] = Field(None, description="Target quality to aim for")
    require_minimum_tokens: int = Field(10, description="Min response tokens")

    # ===== PERFORMANCE =====
    timeout: int = Field(30, description="Timeout per model call (seconds)")
    max_retries: int = Field(2, description="Max retries per model")

    # ===== MODEL ACCESS =====
    allowed_models: list[str] = Field(
        default_factory=lambda: ["*"], description="Models this tier can use (* = all)"
    )
    preferred_models: list[str] = Field(
        default_factory=list, description="Prefer these models when available"
    )
    exclude_models: list[str] = Field(default_factory=list, description="Never use these models")

    # Keep for backwards compatibility
    excluded_models: list[str] = Field(
        default_factory=list, description="Excluded models (alias for exclude_models)"
    )

    # ===== OPTIMIZATION FLAGS =====
    optimize_simple_queries: bool = Field(True, description="Optimize even simple queries for cost")
    prefer_local_models: bool = Field(False, description="Prefer local models when available")
    local_only: bool = Field(False, description="Only use local models (no cloud)")

    # ===== EXECUTION FEATURES =====
    enable_parallel: bool = Field(False, description="Allow parallel execution")
    enable_speculative: bool = Field(True, description="Allow speculative cascading")
    parallel_race_count: int = Field(2, description="Number of models to race")

    # Backwards compatibility
    use_speculative: bool = Field(True, description="Enable speculative cascades (alias)")

    # ===== ADVANCED FEATURES =====
    enable_streaming: bool = Field(False, description="Enable streaming responses")
    enable_caching: bool = Field(False, description="Enable response caching")
    cache_ttl: int = Field(3600, description="Cache TTL in seconds")

    # ===== RATE LIMITING =====
    rate_limit_per_hour: Optional[int] = Field(None, description="Max requests per hour")
    daily_request_limit: Optional[int] = Field(None, description="Max requests per day")

    # Keep for backwards compatibility
    rate_limit: Optional[int] = Field(None, description="Requests per hour (alias)")
    priority: bool = Field(False, description="Priority queue access")

    # ===== FEATURES =====
    features: list[str] = Field(
        default_factory=lambda: ["basic"], description="Enabled features list"
    )

    @field_validator("quality_threshold")
    @classmethod
    def validate_quality(cls, v):
        """Validate quality threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Quality threshold must be between 0 and 1")
        return v

    def allows_model(self, model_name: str) -> bool:
        """
        Check if a model is allowed for this tier.

        BACKWARDS COMPATIBLE with old method.
        """
        # Check exclusions first
        if model_name in self.exclude_models or model_name in self.excluded_models:
            return False

        # Check if wildcard or specific model
        if "*" in self.allowed_models:
            return True

        return model_name in self.allowed_models

    def to_cascade_config(self) -> dict[str, Any]:
        """
        Convert tier to CascadeConfig parameters.

        BACKWARDS COMPATIBLE with old method.
        """
        return {
            "max_budget": self.max_budget,
            "quality_threshold": self.quality_threshold,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "use_speculative": self.use_speculative or self.enable_speculative,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert tier to dict for logging/debugging."""
        return {
            "name": self.name,
            "optimization": {
                "cost": self.optimization.cost,
                "speed": self.optimization.speed,
                "quality": self.optimization.quality,
            },
            "latency": {
                "max_total_ms": self.latency.max_total_ms,
                "max_per_model_ms": self.latency.max_per_model_ms,
            },
            "max_budget": self.max_budget,
            "quality_threshold": self.quality_threshold,
        }

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


# ==================== NEW: Workflow Profile ====================


class WorkflowProfile(BaseModel):
    """
    Developer-defined workflow profiles for specific use cases.

    Example:
        >>> workflow = WorkflowProfile(
        ...     name="draft_mode",
        ...     max_budget_override=0.0001,
        ...     quality_threshold_override=0.5,
        ...     description="Quick drafts"
        ... )
    """

    name: str = Field(..., description="Workflow name")

    # ===== OVERRIDES =====
    latency_override: Optional[LatencyProfile] = Field(
        None, description="Override tier latency settings"
    )
    optimization_override: Optional[OptimizationWeights] = Field(
        None, description="Override tier optimization weights"
    )
    max_budget_override: Optional[float] = Field(None, description="Override tier max budget")
    quality_threshold_override: Optional[float] = Field(
        None, description="Override tier quality threshold"
    )

    # ===== MODEL CONTROL =====
    force_models: Optional[list[str]] = Field(None, description="Force use of specific models only")
    preferred_models: list[str] = Field(default_factory=list, description="Prefer these models")
    exclude_models: list[str] = Field(default_factory=list, description="Exclude these models")

    # ===== FEATURES =====
    enable_caching: Optional[bool] = Field(None, description="Override caching")
    enable_parallel: Optional[bool] = Field(None, description="Override parallel")
    enable_speculative: Optional[bool] = Field(None, description="Override speculative")
    enable_streaming: Optional[bool] = Field(None, description="Override streaming")

    # ===== METADATA =====
    description: Optional[str] = Field(None, description="Workflow description")
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


# ==================== DEFAULT TIERS ====================

DEFAULT_TIERS = {
    "free": UserTier(
        name="free",
        latency=LatencyProfile(
            max_total_ms=15000,
            max_per_model_ms=10000,
            prefer_parallel=False,
            skip_cascade_threshold=0,
        ),
        optimization=OptimizationWeights(cost=0.70, speed=0.15, quality=0.15),
        max_budget=0.001,
        quality_threshold=0.65,
        enable_speculative=True,
        enable_parallel=False,
        enable_caching=False,
    ),
    "standard": UserTier(
        name="standard",
        latency=LatencyProfile(
            max_total_ms=8000,
            max_per_model_ms=5000,
            prefer_parallel=False,
            skip_cascade_threshold=2000,
        ),
        optimization=OptimizationWeights(cost=0.40, speed=0.30, quality=0.30),
        max_budget=0.01,
        preferred_budget=0.005,
        quality_threshold=0.70,
        target_quality=0.80,
        enable_speculative=True,
        enable_parallel=False,
        enable_caching=True,
        cache_ttl=1800,
    ),
    "premium": UserTier(
        name="premium",
        latency=LatencyProfile(
            max_total_ms=3000,
            max_per_model_ms=2000,
            prefer_parallel=True,
            skip_cascade_threshold=1500,
        ),
        optimization=OptimizationWeights(cost=0.20, speed=0.50, quality=0.30),
        max_budget=0.05,
        preferred_budget=0.02,
        quality_threshold=0.75,
        target_quality=0.85,
        enable_speculative=True,
        enable_parallel=True,
        enable_streaming=True,
        enable_caching=True,
        cache_ttl=3600,
    ),
    "enterprise": UserTier(
        name="enterprise",
        latency=LatencyProfile(
            max_total_ms=1500,
            max_per_model_ms=1000,
            prefer_parallel=True,
            skip_cascade_threshold=1000,
        ),
        optimization=OptimizationWeights(cost=0.10, speed=0.60, quality=0.30),
        max_budget=0.20,
        preferred_budget=0.05,
        quality_threshold=0.70,
        target_quality=0.90,
        enable_speculative=True,
        enable_parallel=True,
        parallel_race_count=3,
        enable_streaming=True,
        enable_caching=True,
        cache_ttl=7200,
    ),
}


# ==================== EXAMPLE WORKFLOWS ====================

EXAMPLE_WORKFLOWS = {
    "draft_mode": WorkflowProfile(
        name="draft_mode",
        optimization_override=OptimizationWeights(cost=0.80, speed=0.15, quality=0.05),
        max_budget_override=0.0001,
        quality_threshold_override=0.50,
        preferred_models=["llama3:8b"],
        description="Quick drafts, ultra cost optimized",
    ),
    "production": WorkflowProfile(
        name="production",
        quality_threshold_override=0.85,
        enable_caching=True,
        description="Production queries, balanced",
    ),
    "critical": WorkflowProfile(
        name="critical",
        optimization_override=OptimizationWeights(cost=0.10, speed=0.30, quality=0.60),
        quality_threshold_override=0.90,
        force_models=["gpt-4", "claude-3-opus"],
        description="Critical queries, quality priority",
    ),
    "realtime": WorkflowProfile(
        name="realtime",
        latency_override=LatencyProfile(
            max_total_ms=800, max_per_model_ms=600, prefer_parallel=True, skip_cascade_threshold=700
        ),
        optimization_override=OptimizationWeights(cost=0.15, speed=0.70, quality=0.15),
        preferred_models=["gpt-3.5-turbo", "claude-3-haiku"],
        description="Realtime responses, latency critical",
    ),
    "batch_processing": WorkflowProfile(
        name="batch_processing",
        latency_override=LatencyProfile(
            max_total_ms=30000,
            max_per_model_ms=20000,
            prefer_parallel=False,
            skip_cascade_threshold=0,
        ),
        optimization_override=OptimizationWeights(cost=0.70, speed=0.10, quality=0.20),
        enable_caching=True,
        description="Batch processing, cost optimized",
    ),
}

# ==================== EXPORTS ====================

__all__ = [
    # Core configuration
    "ModelConfig",
    "CascadeConfig",
    # Optimization & constraints
    "OptimizationWeights",
    "LatencyProfile",
    # User tiers & workflows
    "UserTier",
    "WorkflowProfile",
    # Predefined constants
    "DEFAULT_TIERS",
    "EXAMPLE_WORKFLOWS",
]
