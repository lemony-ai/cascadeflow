"""
cascadeflow - ProxyService Example (Routing + Execution)

This example shows how to use the proxy components directly (router + handler).

Use this when you want to build your own gateway/service and:
- route by `provider:model` prefixes (e.g. "openai:gpt-4o-mini"), and
- centralize usage/cost tracking across providers.

For a drop-in integration that works with existing OpenAI/Anthropic SDK clients,
see the Gateway Server guide: docs/guides/gateway.md

Run:
    export OPENAI_API_KEY=...
    python examples/proxy_service_basic.py
"""

import asyncio
import os

from cascadeflow.proxy import ProxyHandler, ProxyRequest, ProxyRoute, ProxyRouter, ProxyService
from cascadeflow.telemetry.cost_tracker import CostTracker


async def main() -> None:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise SystemExit("Missing OPENAI_API_KEY")

    routes = [
        ProxyRoute(
            name="openai",
            provider="openai",
            base_url="https://api.openai.com",
            api_key=openai_key,
            models={"gpt-4o-mini", "gpt-4o"},
        )
    ]

    router = ProxyRouter(routes, default_provider="openai")
    tracker = CostTracker(verbose=True)

    async with ProxyHandler(cost_tracker=tracker) as handler:
        service = ProxyService(router, handler)
        request = ProxyRequest(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={
                "model": "openai:gpt-4o-mini",
                "messages": [{"role": "user", "content": "Say hello in one sentence."}],
            },
        )

        result = await service.handle(request)
        print(result.data["choices"][0]["message"]["content"])
        print(f"provider={result.provider} model={result.model} cost=${result.cost}")
        print(f"tracker_total=${tracker.total_cost}")


if __name__ == "__main__":
    asyncio.run(main())
