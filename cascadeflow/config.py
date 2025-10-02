"""Configuration classes for CascadeFlow."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


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
    keywords: List[str] = Field(default_factory=list, description="Keywords for routing")
    domains: List[str] = Field(default_factory=list, description="Domains (e.g., 'code', 'math')")
    max_tokens: int = Field(4096, description="Maximum tokens for generation")
    system_prompt: Optional[str] = Field(None, description="System prompt override")
    temperature: float = Field(0.7, description="Temperature for generation")

    # API configuration
    api_key: Optional[str] = Field(None, description="API key (or use env var)")
    base_url: Optional[str] = Field(None, description="Custom base URL (for vLLM, etc.)")

    # Provider-specific options
    extra: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific options")

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
        allowed = ["openai", "anthropic", "groq", "ollama", "huggingface", "together", "vllm", "replicate", "custom"]
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
    routing_strategy: str = Field("adaptive", description="Routing strategy (adaptive, cost_first, quality_first, semantic)")

    # Speculative cascades (NEW!)
    use_speculative: bool = Field(True, description="Use speculative cascades (recommended!)")
    deferral_strategy: str = Field("comparative", description="Deferral strategy for speculative cascades")
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


class UserTier(BaseModel):
    """
    User tier configuration for dynamic parameter adjustment.

    Example:
        >>> tier = UserTier(
        ...     name="premium",
        ...     max_budget=0.10,
        ...     quality_threshold=0.9
        ... )
    """

    name: str = Field("free", description="Tier name")

    # Budget limits
    max_budget: float = Field(0.001, description="Max cost per query")
    daily_budget: Optional[float] = Field(None, description="Daily budget limit")
    monthly_budget: Optional[float] = Field(None, description="Monthly budget limit")

    # Quality settings
    quality_threshold: float = Field(0.6, description="Min confidence threshold")
    require_minimum_tokens: int = Field(10, description="Min response length")

    # Model access
    allowed_models: List[str] = Field(default_factory=lambda: ["*"], description="Allowed models (* = all)")
    excluded_models: List[str] = Field(default_factory=list, description="Excluded models")
    preferred_models: List[str] = Field(default_factory=list, description="Preferred models")

    # Performance
    timeout: int = Field(30, description="Timeout in seconds")
    max_retries: int = Field(2, description="Max retries")
    priority: bool = Field(False, description="Priority queue access")

    # Rate limiting
    rate_limit: Optional[int] = Field(None, description="Requests per hour")

    # Features
    features: List[str] = Field(default_factory=lambda: ["basic"], description="Enabled features")
    use_speculative: bool = Field(True, description="Enable speculative cascades")

    def allows_model(self, model_name: str) -> bool:
        """
        Check if a model is allowed for this tier.

        Args:
            model_name: Name of the model to check

        Returns:
            True if model is allowed, False otherwise
        """
        # Check exclusions first
        if model_name in self.excluded_models:
            return False

        # Check if wildcard or specific model
        if "*" in self.allowed_models:
            return True

        return model_name in self.allowed_models

    def to_cascade_config(self) -> Dict[str, Any]:
        """Convert tier to CascadeConfig parameters."""
        return {
            "max_budget": self.max_budget,
            "quality_threshold": self.quality_threshold,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "use_speculative": self.use_speculative,
        }