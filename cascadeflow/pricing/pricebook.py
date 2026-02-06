"""Pricing resolution for cascadeflow cost calculations."""

from dataclasses import dataclass
from typing import Any, Optional

from cascadeflow.schema.usage import Usage


@dataclass(frozen=True)
class ModelPrice:
    input_per_1k: float
    output_per_1k: float
    cached_input_per_1k: float = 0.0


class PriceBook:
    """Internal default model pricing table (USD / 1K tokens)."""

    def __init__(self) -> None:
        self._prices: dict[str, ModelPrice] = {
            "gpt-4o": ModelPrice(input_per_1k=0.0025, output_per_1k=0.01),
            "gpt-4o-mini": ModelPrice(input_per_1k=0.00015, output_per_1k=0.0006),
            "gpt-3.5-turbo": ModelPrice(input_per_1k=0.0005, output_per_1k=0.0015),
        }

    def get(self, model: str) -> Optional[ModelPrice]:
        return self._prices.get(model)


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
