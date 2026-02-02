"""Tests for proxy routing logic."""

import pytest

from cascadeflow.proxy import ProxyRequest, ProxyRoute, ProxyRouter
from cascadeflow.proxy.errors import ProxyRoutingError


@pytest.fixture
def routes():
    return [
        ProxyRoute(
            name="openai-route",
            provider="openai",
            base_url="https://api.openai.test",
            models={"gpt-4o", "gpt-4o-mini"},
        ),
        ProxyRoute(
            name="anthropic-route",
            provider="anthropic",
            base_url="https://api.anthropic.test",
            models={"claude-3-5-sonnet"},
        ),
    ]


def test_route_with_provider_prefix(routes):
    router = ProxyRouter(routes)
    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={},
        body={"model": "openai:gpt-4o", "messages": []},
    )

    plan = router.plan(request)

    assert plan.provider == "openai"
    assert plan.model == "gpt-4o"
    assert plan.route.name == "openai-route"
    assert plan.request.body["model"] == "gpt-4o"


def test_route_with_slash_prefix(routes):
    router = ProxyRouter(routes)
    request = ProxyRequest(
        method="POST",
        path="/v1/messages",
        headers={},
        body={"model": "anthropic/claude-3-5-sonnet", "messages": []},
    )

    plan = router.plan(request)

    assert plan.provider == "anthropic"
    assert plan.model == "claude-3-5-sonnet"
    assert plan.route.name == "anthropic-route"


def test_route_with_registry_lookup(routes):
    router = ProxyRouter(routes)
    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={},
        body={"model": "gpt-4o", "messages": []},
    )

    plan = router.plan(request)

    assert plan.provider == "openai"
    assert plan.model == "gpt-4o"


def test_route_with_model_map_fallback():
    route = ProxyRoute(
        name="custom-route",
        provider="custom",
        base_url="https://proxy.custom",
        models={"my-model"},
    )
    router = ProxyRouter([route])
    request = ProxyRequest(
        method="POST",
        path="/v1/completions",
        headers={},
        body={"model": "my-model", "prompt": "hi"},
    )

    plan = router.plan(request)

    assert plan.provider == "custom"
    assert plan.model == "my-model"


def test_route_missing_model(routes):
    router = ProxyRouter(routes)
    request = ProxyRequest(method="POST", path="/v1/chat/completions", headers={}, body={})

    with pytest.raises(ProxyRoutingError):
        router.plan(request)


def test_route_unknown_model(routes):
    router = ProxyRouter(routes)
    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={},
        body={"model": "unknown-model", "messages": []},
    )

    with pytest.raises(ProxyRoutingError):
        router.plan(request)
