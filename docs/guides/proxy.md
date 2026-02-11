# Proxy Routing & Execution Guide

cascadeflow includes lightweight proxy routing components to help you build
provider-agnostic API gateways. You can route requests to multiple providers,
track usage costs, and normalize request handling.

If you want a drop-in integration for existing OpenAI/Anthropic SDK clients
(change only `base_url`), use the **Gateway Server** instead:
`docs/guides/gateway.md`.

## When to use the proxy components

Use the proxy tooling when you need to:

- Route OpenAI/Anthropic-style requests through a single endpoint
- Attach provider-specific headers or API keys
- Track costs and token usage centrally
- Swap providers without changing client code

## Core concepts

- **ProxyRoute**: Provider-specific configuration (base URL, API key, model allowlist).
- **ProxyRouter**: Determines which route to use for a request.
- **ProxyHandler**: Sends the request upstream, parses usage, and tracks costs.
- **ProxyService**: End-to-end convenience wrapper (router + handler).

## Basic setup

See also: `examples/proxy_service_basic.py`

```python
import asyncio
import os

from cascadeflow.proxy import ProxyHandler, ProxyRequest, ProxyRoute, ProxyRouter, ProxyService
from cascadeflow.telemetry import CostTracker

routes = [
    ProxyRoute(
        name="openai",
        provider="openai",
        base_url="https://api.openai.com",
        api_key=os.getenv("OPENAI_API_KEY"),
        models={"gpt-4o", "gpt-4o-mini"},
    ),
    ProxyRoute(
        name="anthropic",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        models={"claude-3-5-sonnet"},
    ),
]

router = ProxyRouter(routes)
tracker = CostTracker()
handler = ProxyHandler(cost_tracker=tracker)
service = ProxyService(router, handler)

request = ProxyRequest(
    method="POST",
    path="/v1/chat/completions",
    headers={"x-correlation-id": "trace-001"},
    body={
        "model": "openai:gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}],
    },
)

async def main() -> None:
    result = await service.handle(request)
    print(result.data)
    print(result.cost)

asyncio.run(main())
```

## Routing behavior

- Prefix the model with `provider:model` or `provider/model` to force a route.
- If no prefix is present, the router will use the model registry to infer the provider.
- You can also configure explicit model allowlists per route for strict routing.

## Cost tracking

The proxy handler extracts token usage from provider responses (OpenAI-style
`usage` payloads) and uses the model registry to calculate costs. You can also
override pricing per route with `cost_per_1k_tokens` when needed.

## Configuration tips

- **API keys**: Set `api_key` per route (usually from env vars) or pass `Authorization` headers on each request.
- **Timeouts**: Adjust `ProxyRoute.timeout` for slow providers.
- **Custom models**: Add custom model pricing via `ModelRegistry.register` if needed.

## Error handling

The proxy layer raises structured errors you can catch in your API handler:

- `ProxyRoutingError`: No route matches the request.
- `ProxyUpstreamError`: The upstream provider returned an error status.
- `ProxyTransportError`: Network/connection failures reaching the provider.

These errors include the upstream status code or payload when available, making
it easier to map them to API responses.
