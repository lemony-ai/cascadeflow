"""Configuration classes for CascadeFlow."""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class ModelConfig(BaseModel):
    """
    Configuration for a single model in the cascade.

    This defines how to access a model, its cost, and routing hints.

    Example:
        >>> model = ModelConfig(
        ...     name="gpt-3.5-turbo",
        ...     provider="openai",
        ...     cost=0.002
        ... )
        >>> print(model.name)
        'gpt-3.5-turbo'
    """

    # Required fields
    name: str = Field(..., description="Model name (e.g., 'gpt-3.5-turbo', 'llama3:8b')")
    provider: str = Field(..., description="Provider name (openai, anthropic, ollama, etc.)")
    cost: float = Field(0.0, description="Cost per 1K tokens in USD (0.0 for free models)")

    # Routing hints
    keywords: List[str] = Field(
        default_factory=list,
        description="Keywords for routing (e.g., ['simple', 'quick'])"
    )
    domains: List[str] = Field(
        default_factory=list,
        description="Domains this model excels at (e.g., ['code', 'math'])"
    )

    # Model parameters
    max_tokens: int = Field(4096, description="Maximum tokens for generation")
    temperature: float = Field(0.7, description="Sampling temperature (0-2)")
    system_prompt: Optional[str] = Field(None, description="System prompt override")

    # API configuration
    api_key: Optional[str] = Field(None, description="API key (or use env var)")
    base_url: Optional[str] = Field(None, description="Custom base URL (for vLLM, etc.)")

    # Performance hints
    estimated_latency_ms: int = Field(1000, description="Estimated latency in ms")
    supports_streaming: bool = Field(True, description="Whether model supports streaming")

    # Provider-specific options
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific options"
    )

    @field_validator("cost")
    @classmethod
    def validate_cost(cls, v: float) -> float:
        """Validate cost is non-negative."""
        if v < 0:
            raise ValueError("Cost must be non-negative")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider is supported."""
        allowed = [
            "openai", "anthropic", "groq", "ollama",
            "huggingface", "together", "vllm", "replicate", "custom"
        ]
        if v.lower() not in allowed:
            raise ValueError(f"Provider must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max_tokens is positive."""
        if v <= 0:
            raise ValueError("max_tokens must be positive")
        return v

    class Config:
        """Pydantic config."""
        extra = "allow"  # Allow extra fields for provider-specific options


class CascadeConfig(BaseModel):
    """
    Configuration for cascading strategy and behavior.

    This controls how CascadeFlow decides when to cascade and optimize.

    Example:
        >>> config = CascadeConfig(
        ...     quality_threshold=0.85,
        ...     max_budget=0.05
        ... )
        >>> print(config.quality_threshold)
        0.85
    """

    # Quality control
    quality_threshold: float = Field(
        0.7,
        description="Minimum confidence to accept result (0-1)"
    )
    require_minimum_tokens: int = Field(
        10,
        description="Minimum response length in tokens"
    )

    # Budget control
    max_budget: float = Field(
        1.0,
        description="Maximum cost per query in USD"
    )
    track_costs: bool = Field(
        True,
        description="Enable detailed cost tracking"
    )

    # Performance
    max_retries: int = Field(2, description="Max retries per model on failure")
    timeout: int = Field(30, description="Timeout per model call in seconds")
    parallel_verify: bool = Field(True, description="Verify multiple models in parallel")

    # Routing strategy
    routing_strategy: Literal["keyword", "semantic", "adaptive"] = Field(
        "adaptive",
        description="Routing strategy (keyword, semantic, or adaptive)"
    )

    # Speculative cascades (NEW!)
    use_speculative: bool = Field(
        True,
        description="Use speculative cascades (parallel draft + verify)"
    )
    deferral_strategy: Literal["confidence", "comparative", "cost_benefit"] = Field(
        "comparative",
        description="Deferral strategy for speculative cascades"
    )
    comparative_delta: float = Field(
        0.2,
        description="Min confidence delta for deferral (comparative strategy)"
    )

    # Quality estimation
    use_self_consistency: bool = Field(
        False,
        description="Use self-consistency checks (run model 2x)"
    )
    consistency_samples: int = Field(
        2,
        description="Number of samples for self-consistency"
    )

    # Logging & debugging
    verbose: bool = Field(False, description="Show detailed routing decisions")
    log_level: str = Field("INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    track_metrics: bool = Field(True, description="Track latency, tokens, costs")

    @field_validator("quality_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate quality threshold is in valid range."""
        if not 0 <= v <= 1:
            raise ValueError("Quality threshold must be between 0 and 1")
        return v

    @field_validator("max_budget")
    @classmethod
    def validate_budget(cls, v: float) -> float:
        """Validate max budget is non-negative."""
        if v < 0:
            raise ValueError("Max budget must be non-negative")
        return v

    @field_validator("comparative_delta")
    @classmethod
    def validate_comparative_delta(cls, v: float) -> float:
        """Validate comparative delta is in valid range."""
        if not 0 <= v <= 1:
            raise ValueError("Comparative delta must be between 0 and 1")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v


class UserTier(BaseModel):
    """
    User tier configuration for dynamic parameter adjustment.

    This allows you to define different tiers (free, pro, premium) with
    different budgets, quality requirements, and model access.

    Example:
        >>> tier = UserTier(
        ...     name="premium",
        ...     max_budget=0.10,
        ...     quality_threshold=0.9
        ... )
        >>> tier_config = tier.to_cascade_config()
        >>> print(tier_config["max_budget"])
        0.1
    """

    name: str = Field("free", description="Tier name (e.g., 'free', 'pro', 'premium')")

    # Budget limits
    max_budget: float = Field(0.001, description="Max cost per query in USD")
    daily_budget: Optional[float] = Field(None, description="Daily budget limit")
    monthly_budget: Optional[float] = Field(None, description="Monthly budget limit")

    # Quality settings
    quality_threshold: float = Field(0.6, description="Min confidence threshold (0-1)")
    require_minimum_tokens: int = Field(10, description="Min response length in tokens")

    # Model access
    allowed_models: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed models (* = all, or list specific models)"
    )
    preferred_models: List[str] = Field(
        default_factory=list,
        description="Preferred models to try first"
    )
    excluded_models: List[str] = Field(
        default_factory=list,
        description="Models to exclude"
    )

    # Performance
    timeout: int = Field(30, description="Timeout in seconds")
    max_retries: int = Field(2, description="Max retries per model")
    priority: bool = Field(False, description="Priority queue access")

    # Rate limiting
    rate_limit: Optional[int] = Field(None, description="Requests per hour")

    # Features
    features: List[str] = Field(
        default_factory=lambda: ["basic"],
        description="Enabled features (e.g., ['basic', 'analytics', 'priority'])"
    )
    use_speculative: bool = Field(True, description="Enable speculative cascades")
    allow_streaming: bool = Field(False, description="Allow streaming responses")
    cache_enabled: bool = Field(False, description="Enable response caching")

    @field_validator("max_budget")
    @classmethod
    def validate_budget(cls, v: float) -> float:
        """Validate max budget is non-negative."""
        if v < 0:
            raise ValueError("Max budget must be non-negative")
        return v

    @field_validator("quality_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate quality threshold is in valid range."""
        if not 0 <= v <= 1:
            raise ValueError("Quality threshold must be between 0 and 1")
        return v

    def to_cascade_config(self) -> Dict[str, Any]:
        """
        Convert user tier to CascadeConfig parameters.

        Returns:
            Dictionary of CascadeConfig parameters

        Example:
            >>> tier = UserTier(name="premium", max_budget=0.10)
            >>> params = tier.to_cascade_config()
            >>> "max_budget" in params
            True
        """
        return {
            "max_budget": self.max_budget,
            "quality_threshold": self.quality_threshold,
            "require_minimum_tokens": self.require_minimum_tokens,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "use_speculative": self.use_speculative,
        }

    def allows_model(self, model_name: str) -> bool:
        """
        Check if this tier allows access to a model.

        Args:
            model_name: Name of the model to check

        Returns:
            True if model is allowed, False otherwise

        Example:
            >>> tier = UserTier(allowed_models=["gpt-3.5-turbo"])
            >>> tier.allows_model("gpt-3.5-turbo")
            True
            >>> tier.allows_model("gpt-4")
            False
        """
        # Check if explicitly excluded
        if model_name in self.excluded_models:
            return False

        # Check if wildcard allowed
        if "*" in self.allowed_models:
            return True

        # Check if explicitly allowed
        return model_name in self.allowed_models