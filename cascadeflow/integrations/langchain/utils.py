"""Utility functions for CascadeFlow LangChain integration."""

import re
from typing import Any, Optional

from .types import CostMetadata, TokenUsage

# Model pricing per 1M tokens (input/output)
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Anthropic
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost based on token usage and model.

    Args:
        model_name: Name of the model
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Total cost in dollars
    """
    pricing = MODEL_PRICING.get(model_name)

    if not pricing:
        print(f"Warning: Unknown model for pricing: {model_name}, using default")
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


def extract_token_usage(response: Any) -> TokenUsage:
    """Extract token usage from LangChain response.

    Args:
        response: LangChain ChatResult or similar response object

    Returns:
        TokenUsage dictionary with input and output token counts
    """
    # LangChain ChatResult structure
    llm_output = getattr(response, "llm_output", None) or {}

    # Try to get usage from various possible locations
    usage = llm_output.get("token_usage") or llm_output.get("usage") or {}

    # Also check response_metadata if available
    if hasattr(response, "response_metadata"):
        metadata_usage = (
            response.response_metadata.get("token_usage")
            or response.response_metadata.get("usage")
            or {}
        )
        usage = usage or metadata_usage

    # OpenAI format (snake_case)
    if "prompt_tokens" in usage or "completion_tokens" in usage:
        return TokenUsage(
            input=usage.get("prompt_tokens", 0), output=usage.get("completion_tokens", 0)
        )

    # OpenAI format (camelCase - LangChain uses this)
    if "promptTokens" in usage or "completionTokens" in usage:
        return TokenUsage(
            input=usage.get("promptTokens", 0), output=usage.get("completionTokens", 0)
        )

    # Anthropic format
    if "input_tokens" in usage or "output_tokens" in usage:
        return TokenUsage(input=usage.get("input_tokens", 0), output=usage.get("output_tokens", 0))

    # Default
    return TokenUsage(input=0, output=0)


def calculate_quality(response: Any) -> float:
    """Calculate quality score from LangChain response.

    Uses logprobs if available, otherwise heuristics.

    Args:
        response: LangChain ChatResult or similar response object

    Returns:
        Quality score between 0 and 1
    """
    # 1. Try logprobs-based confidence (OpenAI)
    if hasattr(response, "generations") and response.generations:
        generation = response.generations[0]

        # Check for logprobs in generation_info
        if hasattr(generation, "generation_info"):
            generation_info = generation.generation_info
            if generation_info and "logprobs" in generation_info:
                logprobs_data = generation_info["logprobs"]
                if logprobs_data and "content" in logprobs_data:
                    # OpenAI format: content is array of {token, logprob}
                    logprobs = [
                        item["logprob"]
                        for item in logprobs_data["content"]
                        if item.get("logprob") is not None
                    ]

                    if logprobs:
                        import math

                        avg_logprob = sum(logprobs) / len(logprobs)
                        confidence = math.exp(avg_logprob)  # Convert log probability to probability
                        return max(0.1, min(1.0, confidence * 1.5))  # Boost slightly

    # 2. Heuristic-based quality scoring
    # Extract text from response
    text = ""
    if hasattr(response, "generations") and response.generations:
        generation = response.generations[0]
        text = getattr(generation, "text", "")
        if not text and hasattr(generation, "message"):
            text = getattr(generation.message, "content", "")
    elif hasattr(response, "content"):
        text = response.content

    if not text or len(text) < 5:
        return 0.2  # Low quality for empty/very short responses

    # Check for common quality indicators
    score = 0.4  # Base score (lowered from 0.6 for more realistic evaluation)

    # Length bonus (reasonable response)
    if len(text) > 50:  # Increased threshold from 20
        score += 0.1
    if len(text) > 200:  # Increased threshold from 100
        score += 0.1

    # Structure bonus (has punctuation, capitalization)
    if re.search(r"[.!?]", text):
        score += 0.05
    if re.match(r"^[A-Z]", text):
        score += 0.05

    # Completeness bonus (ends with punctuation)
    if re.search(r"[.!?]$", text.strip()):
        score += 0.05  # Reduced from 0.1

    # Penalize hedging phrases
    hedging_phrases = ["i don't know", "i'm not sure", "i cannot", "i can't"]
    lower_text = text.lower()
    hedge_count = sum(1 for phrase in hedging_phrases if phrase in lower_text)
    score -= hedge_count * 0.15  # Increased penalty from 0.1

    return max(0.1, min(1.0, score))


def calculate_savings(drafter_cost: float, verifier_cost: float) -> float:
    """Calculate savings percentage.

    Args:
        drafter_cost: Cost of drafter call
        verifier_cost: Cost of verifier call

    Returns:
        Savings percentage (0-100)
    """
    if verifier_cost == 0:
        return 0.0

    total_cost = drafter_cost + verifier_cost
    potential_cost = verifier_cost  # If we had used verifier directly

    return ((potential_cost - total_cost) / potential_cost) * 100


def create_cost_metadata(
    drafter_response: Any,
    verifier_response: Optional[Any],
    drafter_model: str,
    verifier_model: str,
    accepted: bool,
    drafter_quality: float,
    cost_provider: str = "langsmith",
) -> CostMetadata:
    """Create cost metadata with configurable provider.

    Args:
        drafter_response: Response from drafter model
        verifier_response: Response from verifier model (None if not used)
        drafter_model: Name of drafter model
        verifier_model: Name of verifier model
        accepted: Whether drafter response was accepted
        drafter_quality: Quality score of drafter response
        cost_provider: 'langsmith' (server-side) or 'cascadeflow' (local calculation)

    Returns:
        CostMetadata dictionary
    """
    drafter_tokens = extract_token_usage(drafter_response)

    if cost_provider == "cascadeflow":
        # Use CascadeFlow's built-in pricing calculation
        drafter_cost = calculate_cost(
            drafter_model, drafter_tokens["input"], drafter_tokens["output"]
        )

        if verifier_response:
            verifier_tokens = extract_token_usage(verifier_response)
            verifier_cost = calculate_cost(
                verifier_model, verifier_tokens["input"], verifier_tokens["output"]
            )
        else:
            verifier_tokens = None
            verifier_cost = 0.0
    else:
        # LangSmith provider - costs calculated server-side
        # We still track tokens for metadata, but costs are 0 (calculated by LangSmith)
        drafter_cost = 0.0

        if verifier_response:
            verifier_tokens = extract_token_usage(verifier_response)
            verifier_cost = 0.0
        else:
            verifier_tokens = None
            verifier_cost = 0.0

    total_cost = drafter_cost + verifier_cost
    savings_percentage = calculate_savings(drafter_cost, verifier_cost)

    metadata: CostMetadata = {
        "drafter_tokens": drafter_tokens,
        "drafter_cost": drafter_cost,
        "verifier_cost": verifier_cost,
        "total_cost": total_cost,
        "savings_percentage": savings_percentage,
        "model_used": "drafter" if accepted else "verifier",
        "accepted": accepted,
        "drafter_quality": drafter_quality,
    }

    if verifier_tokens:
        metadata["verifier_tokens"] = verifier_tokens

    return metadata
