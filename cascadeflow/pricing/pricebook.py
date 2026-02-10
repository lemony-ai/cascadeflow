"""Pricing resolution for cascadeflow cost calculations.

PriceBook provides a default pricing table that can be extended at runtime
via ``update()`` or by loading LiteLLM's live pricing with
``sync_from_litellm()``.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from cascadeflow.schema.usage import Usage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPrice:
    input_per_1k: float
    output_per_1k: float
    cached_input_per_1k: float = 0.0


# Comprehensive built-in pricing (USD / 1K tokens, updated 2026-02)
_DEFAULT_PRICES: dict[str, ModelPrice] = {
    # OpenAI
    "gpt-4o": ModelPrice(input_per_1k=0.0025, output_per_1k=0.01),
    "gpt-4o-mini": ModelPrice(input_per_1k=0.00015, output_per_1k=0.0006),
    "gpt-4-turbo": ModelPrice(input_per_1k=0.01, output_per_1k=0.03),
    "gpt-3.5-turbo": ModelPrice(input_per_1k=0.0005, output_per_1k=0.0015),
    "o1": ModelPrice(input_per_1k=0.015, output_per_1k=0.06),
    "o1-mini": ModelPrice(input_per_1k=0.003, output_per_1k=0.012),
    "o3-mini": ModelPrice(input_per_1k=0.001, output_per_1k=0.005),
    "gpt-5": ModelPrice(input_per_1k=0.00125, output_per_1k=0.01),
    "gpt-5-mini": ModelPrice(input_per_1k=0.00025, output_per_1k=0.002),
    "gpt-5-nano": ModelPrice(input_per_1k=0.00005, output_per_1k=0.0004),
    # Anthropic (blended per-1K approximation)
    "claude-sonnet-4-5-20250929": ModelPrice(input_per_1k=0.003, output_per_1k=0.015),
    "claude-3-haiku-20240307": ModelPrice(input_per_1k=0.00025, output_per_1k=0.00125),
    # Groq (nearly free)
    "llama-3.1-8b-instant": ModelPrice(input_per_1k=0.00005, output_per_1k=0.00008),
    "llama-3.1-70b-versatile": ModelPrice(input_per_1k=0.00059, output_per_1k=0.00079),
}


class PriceBook:
    """Internal default model pricing table (USD / 1K tokens).

    Supports runtime updates via ``update()`` and automatic sync from
    LiteLLM's live model cost database via ``sync_from_litellm()``.
    """

    def __init__(self) -> None:
        self._prices: dict[str, ModelPrice] = dict(_DEFAULT_PRICES)

    def get(self, model: str) -> Optional[ModelPrice]:
        price = self._prices.get(model)
        if price is not None:
            return price
        # Prefix match for versioned model names (e.g. gpt-4o-2024-08-06)
        for name, p in self._prices.items():
            if model.startswith(name):
                return p
        return None

    def update(self, model: str, input_per_1k: float, output_per_1k: float) -> None:
        """Add or update a model's pricing at runtime.

        Example::

            pricebook.update("gpt-5-turbo", input_per_1k=0.002, output_per_1k=0.008)
        """
        self._prices[model] = ModelPrice(input_per_1k=input_per_1k, output_per_1k=output_per_1k)

    def update_batch(self, prices: dict[str, dict[str, float]]) -> None:
        """Bulk update pricing.

        Example::

            pricebook.update_batch({
                "gpt-5": {"input_per_1k": 0.00125, "output_per_1k": 0.01},
                "gpt-5-mini": {"input_per_1k": 0.00025, "output_per_1k": 0.002},
            })
        """
        for model, rates in prices.items():
            self._prices[model] = ModelPrice(
                input_per_1k=rates.get("input_per_1k", 0.0),
                output_per_1k=rates.get("output_per_1k", 0.0),
            )

    def sync_from_litellm(self) -> int:
        """Pull latest pricing from LiteLLM's model_cost database.

        Returns the number of models updated. If LiteLLM is not installed,
        returns 0 and logs a warning.

        Example::

            count = pricebook.sync_from_litellm()
            print(f"Updated {count} model prices from LiteLLM")
        """
        try:
            from litellm import model_cost
        except ImportError:
            logger.warning("LiteLLM not installed -- cannot sync pricing")
            return 0

        updated = 0
        for model_name, info in model_cost.items():
            input_cost = info.get("input_cost_per_token", 0.0) * 1000
            output_cost = info.get("output_cost_per_token", 0.0) * 1000
            if input_cost > 0 or output_cost > 0:
                self._prices[model_name] = ModelPrice(
                    input_per_1k=input_cost, output_per_1k=output_cost
                )
                updated += 1

        logger.info(f"Synced {updated} model prices from LiteLLM")
        return updated

    @property
    def models(self) -> list[str]:
        """List all models with pricing."""
        return sorted(self._prices.keys())


class PricingResolver:
    """Resolve cost priority: provider-reported > LiteLLM > internal defaults."""

    def __init__(self, pricebook: Optional[PriceBook] = None) -> None:
        self.pricebook = pricebook or PriceBook()

    def resolve_cost(
        self,
        *,
        model: str,
        usage: Usage,
        provider_cost: Optional[float] = None,
        litellm_cost: Optional[float] = None,
        fallback_rate_per_1k: Optional[float] = None,
    ) -> float:
        if provider_cost is not None:
            return float(provider_cost)
        if litellm_cost is not None:
            return float(litellm_cost)

        price = self.pricebook.get(model)
        if price:
            return (
                (usage.input_tokens / 1000) * price.input_per_1k
                + (usage.output_tokens / 1000) * price.output_per_1k
                + (usage.cached_input_tokens / 1000) * price.cached_input_per_1k
            )

        if fallback_rate_per_1k is not None:
            return (usage.total_tokens / 1000) * float(fallback_rate_per_1k)

        return 0.0

    def extract_usage(self, response: Any) -> Usage:
        metadata = getattr(response, "metadata", None) or {}
        usage_payload = metadata.get("usage") or metadata
        return Usage.from_payload(usage_payload)
