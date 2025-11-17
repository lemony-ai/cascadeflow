"""Model discovery and analysis for LangChain models.

This module helps users discover which of THEIR configured LangChain
models work best for cascading, without requiring any specific API keys.

Users bring their own models - we just help them find the best pairs!
"""

from typing import Any, Optional, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from typing_extensions import NotRequired


class ModelPricing(TypedDict):
    """Model pricing information (per 1M tokens)."""

    input: float
    output: float
    tier: str


class CascadeAnalysis(TypedDict):
    """Result of analyzing a cascade pair."""

    drafter_model: str
    verifier_model: str
    drafter_cost: ModelPricing
    verifier_cost: ModelPricing
    valid: bool
    warnings: list[str]
    estimated_savings: float
    recommendation: str


class ModelAnalysis(TypedDict):
    """Analysis of a single model."""

    model_name: str
    provider: str
    tier: str
    estimated_cost: Optional[dict[str, float]]
    recommendation: str


class CascadePairSuggestion(TypedDict):
    """Suggested cascade pair with analysis."""

    drafter: BaseChatModel
    verifier: BaseChatModel
    analysis: CascadeAnalysis
    rank: NotRequired[int]


# Model pricing reference (per 1M tokens)
# This is read-only reference data to help users understand costs
MODEL_PRICING_REFERENCE: dict[str, ModelPricing] = {
    # OpenAI Models
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "tier": "fast"},
    "gpt-4o": {"input": 2.50, "output": 10.00, "tier": "powerful"},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00, "tier": "powerful"},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "tier": "fast"},
    # GPT-5 Models (estimated pricing - subject to change)
    "gpt-5": {"input": 1.25, "output": 10.00, "tier": "powerful"},
    "gpt-5-mini": {"input": 0.25, "output": 2.00, "tier": "fast"},
    "gpt-5-nano": {"input": 0.05, "output": 0.40, "tier": "fast"},
    "gpt-5.1": {"input": 2.00, "output": 15.00, "tier": "powerful"},
    # Anthropic Models
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25, "tier": "fast"},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00, "tier": "balanced"},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00, "tier": "powerful"},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00, "tier": "balanced"},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00, "tier": "powerful"},
    # Claude 4 Models (estimated pricing - subject to change)
    "claude-sonnet-4": {"input": 3.00, "output": 15.00, "tier": "powerful"},
    "claude-haiku-4.5": {"input": 1.00, "output": 5.00, "tier": "balanced"},
    # Google Models
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "tier": "fast"},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00, "tier": "powerful"},
    # Gemini 2.5 Models (estimated pricing - subject to change)
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "tier": "fast"},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "tier": "powerful"},
}


def extract_model_name(model: BaseChatModel) -> str:
    """Extract model name from a LangChain model instance.

    Args:
        model: LangChain chat model instance

    Returns:
        Model name string
    """
    # Try different property names that LangChain models use
    if hasattr(model, "model") and model.model:
        return model.model
    if hasattr(model, "model_name") and model.model_name:
        return model.model_name
    if hasattr(model, "modelName") and model.modelName:
        return model.modelName

    # Fallback to _llm_type if no model name found
    return model._llm_type


def get_provider(model: BaseChatModel) -> str:
    """Get provider name from a model.

    Args:
        model: LangChain chat model instance

    Returns:
        Provider name (openai, anthropic, google, ollama, or unknown)
    """
    model_name = extract_model_name(model).lower()

    if "gpt" in model_name or "openai" in model_name:
        return "openai"
    if "claude" in model_name or "anthropic" in model_name:
        return "anthropic"
    if "gemini" in model_name or "google" in model_name:
        return "google"
    if "ollama" in model_name:
        return "ollama"

    return "unknown"


def get_model_pricing(model_name: str) -> Optional[dict[str, float]]:
    """Get pricing information for a model.

    Args:
        model_name: Model name to look up

    Returns:
        Pricing dict with input/output costs, or None if unknown
    """
    normalized_name = model_name.lower()

    # Try exact match first
    for key, pricing in MODEL_PRICING_REFERENCE.items():
        if normalized_name == key.lower():
            return {"input": pricing["input"], "output": pricing["output"]}

    # If no exact match, try contains (prefer longer keys first to avoid partial matches)
    sorted_items = sorted(MODEL_PRICING_REFERENCE.items(), key=lambda x: len(x[0]), reverse=True)

    for key, pricing in sorted_items:
        if key.lower() in normalized_name:
            return {"input": pricing["input"], "output": pricing["output"]}

    return None


def calculate_estimated_savings(
    drafter_pricing: dict[str, float],
    verifier_pricing: dict[str, float],
    acceptance_rate: float = 0.7,
) -> float:
    """Calculate estimated savings percentage.

    Assumes typical 70% drafter acceptance rate by default.

    Args:
        drafter_pricing: Drafter pricing with input/output
        verifier_pricing: Verifier pricing with input/output
        acceptance_rate: Expected drafter acceptance rate (0-1)

    Returns:
        Estimated savings percentage (0-100)
    """
    # Average tokens for a typical query
    avg_input_tokens = 500
    avg_output_tokens = 300

    # Cost if always using verifier
    verifier_only_cost = (avg_input_tokens / 1_000_000) * verifier_pricing["input"] + (
        avg_output_tokens / 1_000_000
    ) * verifier_pricing["output"]

    # Cost with cascade (drafter tries all, verifier only on failures)
    drafter_cost = (avg_input_tokens / 1_000_000) * drafter_pricing["input"] + (
        avg_output_tokens / 1_000_000
    ) * drafter_pricing["output"]

    cascade_cost = (
        drafter_cost  # Always try drafter
        + (1 - acceptance_rate) * verifier_only_cost  # Verifier only when drafter fails
    )

    # Calculate savings
    if verifier_only_cost == 0:
        return 0.0

    savings = ((verifier_only_cost - cascade_cost) / verifier_only_cost) * 100
    return max(0.0, min(100.0, savings))


def analyze_cascade_pair(drafter: BaseChatModel, verifier: BaseChatModel) -> CascadeAnalysis:
    """Analyze a cascade configuration and provide insights.

    Args:
        drafter: The drafter (cheap, fast) model instance
        verifier: The verifier (expensive, accurate) model instance

    Returns:
        Analysis with pricing, validation, and recommendations

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> drafter = ChatOpenAI(model='gpt-4o-mini')
        >>> verifier = ChatOpenAI(model='gpt-4o')
        >>> analysis = analyze_cascade_pair(drafter, verifier)
        >>> print(analysis['estimated_savings'])  # => 55-65%
        >>> print(analysis['warnings'])  # => []
    """
    drafter_model = extract_model_name(drafter)
    verifier_model = extract_model_name(verifier)

    drafter_pricing = get_model_pricing(drafter_model)
    verifier_pricing = get_model_pricing(verifier_model)

    warnings: list[str] = []
    valid = True

    # Check if we have pricing info
    if not drafter_pricing:
        valid = False
        warnings.append(f"Unknown pricing for drafter model: {drafter_model}")
    if not verifier_pricing:
        valid = False
        warnings.append(f"Unknown pricing for verifier model: {verifier_model}")

    # Validate configuration
    if drafter_pricing and verifier_pricing:
        # Check if drafter is more expensive than verifier (misconfiguration)
        drafter_avg_cost = (drafter_pricing["input"] + drafter_pricing["output"]) / 2
        verifier_avg_cost = (verifier_pricing["input"] + verifier_pricing["output"]) / 2

        if drafter_avg_cost > verifier_avg_cost:
            valid = False
            warnings.append(
                f"Drafter ({drafter_model}) is more expensive than verifier ({verifier_model}). "
                f"This defeats the purpose of cascading. Consider swapping them."
            )

        # Check if models are the same
        if drafter_model == verifier_model:
            valid = False
            warnings.append(
                f"Drafter and verifier are the same model ({drafter_model}). "
                f"Cascading provides no benefit in this configuration."
            )

        # Check if drafter is only slightly cheaper
        savings_ratio = (verifier_avg_cost - drafter_avg_cost) / verifier_avg_cost
        if 0 < savings_ratio < 0.3:
            warnings.append(
                f"Drafter is only {int(savings_ratio * 100)}% cheaper than verifier. "
                f"Consider using a cheaper drafter for better cost savings."
            )

    # Calculate estimated savings
    estimated_savings = 0.0
    if drafter_pricing and verifier_pricing:
        estimated_savings = calculate_estimated_savings(drafter_pricing, verifier_pricing)

    # Generate recommendation
    if not valid:
        recommendation = "Configuration needs attention. See warnings above."
    elif estimated_savings > 50:
        recommendation = "Excellent cascade configuration! Expected savings > 50%."
    elif estimated_savings > 30:
        recommendation = "Good cascade configuration. Expected savings 30-50%."
    elif estimated_savings > 0:
        recommendation = "Marginal cascade configuration. Consider a cheaper drafter."
    else:
        recommendation = "Unable to estimate savings (unknown model pricing)."

    # Default fallback costs (type: ignore to handle TypedDict/dict compatibility)
    default_cost: ModelPricing = {"input": 0, "output": 0, "tier": "unknown"}  # type: ignore[typeddict-item]
    return {
        "drafter_model": drafter_model,
        "verifier_model": verifier_model,
        "drafter_cost": drafter_pricing or default_cost,  # type: ignore[typeddict-item]
        "verifier_cost": verifier_pricing or default_cost,  # type: ignore[typeddict-item]
        "valid": valid,
        "warnings": warnings,
        "estimated_savings": estimated_savings,
        "recommendation": recommendation,
    }


def suggest_cascade_pairs(models: list[BaseChatModel]) -> list[CascadePairSuggestion]:
    """Suggest optimal cascade pairs from a list of available models.

    Args:
        models: Array of LangChain model instances

    Returns:
        Array of suggested cascade configurations sorted by estimated savings

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> models = [
        ...     ChatOpenAI(model='gpt-4o-mini'),
        ...     ChatOpenAI(model='gpt-4o'),
        ... ]
        >>> suggestions = suggest_cascade_pairs(models)
        >>> best = suggestions[0]
        >>> print(best['analysis']['estimated_savings'])  # => ~60%
    """
    suggestions: list[CascadePairSuggestion] = []

    # Try all pairs
    for i, drafter in enumerate(models):
        for j, verifier in enumerate(models):
            if i == j:
                continue

            analysis = analyze_cascade_pair(drafter, verifier)

            # Only include valid pairs
            if analysis["valid"]:
                suggestions.append(
                    {
                        "drafter": drafter,
                        "verifier": verifier,
                        "analysis": analysis,
                    }
                )

    # Sort by estimated savings (highest first)
    suggestions.sort(key=lambda x: x["analysis"]["estimated_savings"], reverse=True)

    return suggestions


def discover_cascade_pairs(
    models: list[BaseChatModel], min_savings: float = 20.0, require_same_provider: bool = False
) -> list[CascadePairSuggestion]:
    """Discover and analyze cascade pairs from user's models.

    This is the main helper - give it YOUR models and it will suggest
    the best cascade configurations.

    Args:
        models: Array of YOUR configured LangChain models
        min_savings: Minimum estimated savings percentage (default: 20%)
        require_same_provider: Only suggest pairs from same provider

    Returns:
        Ranked cascade pair suggestions

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> from cascadeflow.integrations.langchain import discover_cascade_pairs
        >>>
        >>> # YOUR models (already configured with YOUR API keys)
        >>> my_models = [
        ...     ChatOpenAI(model='gpt-4o-mini'),
        ...     ChatOpenAI(model='gpt-4o'),
        ... ]
        >>>
        >>> # Find best cascade pairs
        >>> suggestions = discover_cascade_pairs(my_models)
        >>>
        >>> # Use the best one
        >>> best = suggestions[0]
        >>> cascade = CascadeFlow(
        ...     drafter=best['drafter'],
        ...     verifier=best['verifier'],
        ... )
    """
    # Use the existing suggest_cascade_pairs helper
    suggestions = suggest_cascade_pairs(models)

    # Filter by provider if requested
    if require_same_provider:
        suggestions = [
            s for s in suggestions if get_provider(s["drafter"]) == get_provider(s["verifier"])
        ]

    # Filter by minimum savings
    suggestions = [s for s in suggestions if s["analysis"]["estimated_savings"] >= min_savings]

    # Add ranking
    for i, suggestion in enumerate(suggestions):
        suggestion["rank"] = i + 1

    return suggestions


def analyze_model(model: BaseChatModel) -> ModelAnalysis:
    """Analyze a user's model and provide insights.

    Args:
        model: YOUR configured LangChain model

    Returns:
        Analysis with pricing and tier information

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> my_model = ChatOpenAI(model='gpt-4o')
        >>> info = analyze_model(my_model)
        >>> print(info['model_name'])  # 'gpt-4o'
        >>> print(info['tier'])  # 'powerful'
        >>> print(info['estimated_cost'])  # {'input': 2.50, 'output': 10.00}
    """
    model_name = extract_model_name(model)
    provider = get_provider(model)

    # Look up pricing - try exact match first, then fallback to contains
    pricing_entry = None
    normalized_name = model_name.lower()

    for key, value in MODEL_PRICING_REFERENCE.items():
        if normalized_name == key.lower():
            pricing_entry = (key, value)
            break

    # If no exact match, try contains (prefer longer keys first)
    if not pricing_entry:
        sorted_items = sorted(
            MODEL_PRICING_REFERENCE.items(), key=lambda x: len(x[0]), reverse=True
        )
        for key, value in sorted_items:
            if key.lower() in normalized_name:
                pricing_entry = (key, value)
                break

    estimated_cost = None
    tier = "unknown"

    if pricing_entry:
        estimated_cost = {"input": pricing_entry[1]["input"], "output": pricing_entry[1]["output"]}
        tier = pricing_entry[1]["tier"]

    # Generate recommendation
    if tier == "fast":
        recommendation = "Good choice for drafter (cheap, fast model)"
    elif tier == "powerful":
        recommendation = "Good choice for verifier (expensive, accurate model)"
    elif tier == "balanced":
        recommendation = "Can work as either drafter or verifier"
    else:
        recommendation = "Unknown model - consider testing cascade performance"

    return {
        "model_name": model_name,
        "provider": provider,
        "tier": tier,
        "estimated_cost": estimated_cost,
        "recommendation": recommendation,
    }


def compare_models(models: list[BaseChatModel]) -> dict[str, list[dict[str, Any]]]:
    """Compare multiple models and rank them for cascade use.

    Args:
        models: YOUR configured models to compare

    Returns:
        Dict with drafter_candidates, verifier_candidates, and all models

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> my_models = [
        ...     ChatOpenAI(model='gpt-4o-mini'),
        ...     ChatOpenAI(model='gpt-4o'),
        ... ]
        >>> comparison = compare_models(my_models)
        >>> print(comparison['drafter_candidates'])  # Best for drafter
        >>> print(comparison['verifier_candidates'])  # Best for verifier
    """
    analyzed = [{"model": model, "analysis": analyze_model(model)} for model in models]

    # Sort by cost (input + output average)
    def get_cost(item: dict[str, Any]) -> float:
        cost = item["analysis"]["estimated_cost"]
        if cost:
            return (cost["input"] + cost["output"]) / 2
        return float("inf")

    sorted_models = sorted(analyzed, key=get_cost)

    # Drafters = cheap models (first half)
    mid_point = len(sorted_models) // 2 + (len(sorted_models) % 2)
    drafter_candidates = sorted_models[:mid_point]

    # Verifiers = expensive models (second half)
    verifier_candidates = sorted_models[mid_point:]

    return {
        "drafter_candidates": drafter_candidates,
        "verifier_candidates": verifier_candidates,
        "all": analyzed,
    }


def find_best_cascade_pair(models: list[BaseChatModel]) -> Optional[dict[str, Any]]:
    """Quick helper to find the best cascade pair from user's models.

    Args:
        models: YOUR configured LangChain models

    Returns:
        Best drafter and verifier, or None if no good pair found

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> my_models = [
        ...     ChatOpenAI(model='gpt-4o-mini'),
        ...     ChatOpenAI(model='gpt-4o'),
        ... ]
        >>> best = find_best_cascade_pair(my_models)
        >>> if best:
        ...     cascade = CascadeFlow(
        ...         drafter=best['drafter'],
        ...         verifier=best['verifier'],
        ...     )
    """
    suggestions = discover_cascade_pairs(models)

    if not suggestions:
        return None

    best = suggestions[0]
    return {
        "drafter": best["drafter"],
        "verifier": best["verifier"],
        "estimated_savings": best["analysis"]["estimated_savings"],
        "analysis": best["analysis"],
    }


def validate_cascade_pair(drafter: BaseChatModel, verifier: BaseChatModel) -> dict[str, Any]:
    """Validate that a model pair makes sense for cascading.

    Args:
        drafter: YOUR configured drafter model
        verifier: YOUR configured verifier model

    Returns:
        Validation result with warnings

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> result = validate_cascade_pair(
        ...     ChatOpenAI(model='gpt-4o-mini'),
        ...     ChatOpenAI(model='gpt-4o')
        ... )
        >>> if not result['valid']:
        ...     print('Issues:', result['warnings'])
    """
    analysis = analyze_cascade_pair(drafter, verifier)

    return {
        "valid": analysis["valid"],
        "warnings": analysis["warnings"],
        "estimated_savings": analysis["estimated_savings"],
        "recommendation": analysis["recommendation"],
    }
