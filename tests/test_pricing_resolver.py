from cascadeflow.pricing import PricingResolver
from cascadeflow.schema.usage import Usage


def test_pricing_resolver_prefers_provider_cost():
    resolver = PricingResolver()
    usage = Usage(input_tokens=100, output_tokens=50)
    cost = resolver.resolve_cost(
        model="gpt-4o-mini",
        usage=usage,
        provider_cost=0.123,
        litellm_cost=0.222,
        fallback_rate_per_1k=1.0,
    )
    assert cost == 0.123


def test_pricing_resolver_uses_internal_pricebook_then_fallback():
    resolver = PricingResolver()
    usage = Usage(input_tokens=1000, output_tokens=1000)
    cost = resolver.resolve_cost(model="gpt-4o-mini", usage=usage)
    assert cost > 0

    fallback = resolver.resolve_cost(
        model="unknown-model",
        usage=Usage(input_tokens=500, output_tokens=500),
        fallback_rate_per_1k=0.01,
    )
    assert fallback == 0.01


def test_usage_from_payload_maps_legacy_fields():
    usage = Usage.from_payload(
        {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "cache_read_input_tokens": 3,
        }
    )
    assert usage.input_tokens == 12
    assert usage.output_tokens == 8
    assert usage.cached_input_tokens == 3
