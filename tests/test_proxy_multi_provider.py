"""Tests for multi-provider routing."""

from cascadeflow.proxy import ProxyRequest, ProxyRoute, ProxyRouter


def test_multi_provider_routing_by_provider_prefix():
    routes = [
        ProxyRoute(
            name="openai-route",
            provider="openai",
            base_url="https://api.openai.test",
            models={"gpt-4o"},
        ),
        ProxyRoute(
            name="anthropic-route",
            provider="anthropic",
            base_url="https://api.anthropic.test",
            models={"claude-3-5-sonnet"},
        ),
    ]
    router = ProxyRouter(routes)

    openai_request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={},
        body={"model": "openai:gpt-4o", "messages": []},
    )
    anthropic_request = ProxyRequest(
        method="POST",
        path="/v1/messages",
        headers={},
        body={"model": "anthropic:claude-3-5-sonnet", "messages": []},
    )

    openai_plan = router.plan(openai_request)
    anthropic_plan = router.plan(anthropic_request)

    assert openai_plan.provider == "openai"
    assert anthropic_plan.provider == "anthropic"
    assert openai_plan.route.base_url == "https://api.openai.test"
    assert anthropic_plan.route.base_url == "https://api.anthropic.test"
