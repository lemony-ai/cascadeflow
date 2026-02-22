import asyncio
import json

import httpx
import pytest

from cascadeflow.proxy import ProxyConfig, RoutingProxy
from cascadeflow.proxy.server import _build_openai_response
from cascadeflow.telemetry.cost_tracker import CostTracker


@pytest.fixture
def proxy_server():
    cost_tracker = CostTracker()
    config = ProxyConfig()
    proxy = RoutingProxy(config=config, cost_tracker=cost_tracker)
    proxy.start()
    yield proxy, cost_tracker
    proxy.stop()


def _get_lines(response: httpx.Response) -> list[str]:
    lines: list[str] = []
    for line in response.iter_lines():
        if line:
            lines.append(line)
    return lines


def test_openai_request(proxy_server):
    proxy, cost_tracker = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/chat/completions"
    payload = {
        "model": "cascadeflow-auto",
        "messages": [{"role": "user", "content": "Hello world"}],
    }

    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 200
    assert response.headers.get("X-Cascadeflow-Gateway") == "cascadeflow"
    assert response.headers.get("X-Cascadeflow-Gateway-API") == "openai"
    assert response.headers.get("X-Cascadeflow-Gateway-Endpoint") == "chat.completions"

    data = response.json()
    assert data["model"] == proxy.config.virtual_models["cascadeflow-auto"]
    assert data["cascadeflow"]["virtual_model"] == "cascadeflow-auto"
    assert data["usage"]["prompt_tokens"] > 0
    assert data["cascadeflow"]["cost"] > 0
    assert cost_tracker.total_cost > 0


def test_openai_streaming(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/chat/completions"
    payload = {
        "model": "cascadeflow-fast",
        "messages": [{"role": "user", "content": "Stream this response"}],
        "stream": True,
    }

    with httpx.stream("POST", url, json=payload, timeout=5.0, trust_env=False) as response:
        assert response.status_code == 200
        lines = _get_lines(response)

    data_lines = [line for line in lines if line.startswith("data: ")]
    assert data_lines[-1] == "data: [DONE]"
    assert any("chat.completion.chunk" in line for line in data_lines)


def test_anthropic_request(proxy_server):
    proxy, cost_tracker = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/messages"
    payload = {
        "model": "cascadeflow-quality",
        "messages": [{"role": "user", "content": "Hello from Anthropic"}],
    }

    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 200

    data = response.json()
    assert data["model"] == proxy.config.virtual_models["cascadeflow-quality"]
    assert data["content"][0]["text"].startswith("Proxy response")
    assert data["cascadeflow"]["draft_accepted"] is True
    assert data["cascadeflow"]["cost"] > 0
    assert cost_tracker.total_cost > 0


def test_anthropic_streaming(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/messages"
    payload = {
        "model": "cascadeflow-cheap",
        "messages": [{"role": "user", "content": "Stream via Anthropic"}],
        "stream": True,
    }

    with httpx.stream("POST", url, json=payload, timeout=5.0, trust_env=False) as response:
        assert response.status_code == 200
        lines = _get_lines(response)

    assert any(line.startswith("event: message_start") for line in lines)
    assert any(line.startswith("event: message_stop") for line in lines)
    assert any(line == "data: [DONE]" for line in lines)


def test_error_handling(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/chat/completions"
    payload = {"messages": [{"role": "user", "content": "Missing model"}]}

    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["type"] == "invalid_request_error"


def test_cascade_behavior(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/chat/completions"
    payload = {
        "model": "cascadeflow-auto",
        "messages": [{"role": "user", "content": "This is a hard question"}],
    }

    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 200
    data = response.json()
    assert data["cascadeflow"]["draft_accepted"] is False


def test_virtual_model_names(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/messages"
    payload = {
        "model": "cascadeflow-fast",
        "messages": [{"role": "user", "content": "Test virtual model mapping"}],
    }

    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 200
    data = response.json()
    assert data["cascadeflow"]["virtual_model"] == "cascadeflow-fast"
    assert data["cascadeflow"]["resolved_model"] == proxy.config.virtual_models["cascadeflow-fast"]


def test_models_list(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/models"
    response = httpx.get(url, timeout=5.0, trust_env=False)
    assert response.status_code == 200
    assert response.headers.get("X-Cascadeflow-Gateway-Endpoint") == "models.list"

    data = response.json()
    assert data["object"] == "list"
    ids = {item["id"] for item in data["data"]}
    assert "cascadeflow" in ids
    assert "cascadeflow-auto" in ids


@pytest.mark.parametrize("path", ["/stats", "/v1/stats"])
def test_stats_endpoint_returns_json_not_found_in_mock_mode(proxy_server, path):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}{path}"
    response = httpx.get(url, timeout=5.0, trust_env=False)
    assert response.status_code == 404

    data = response.json()
    assert data["error"]["type"] == "not_found_error"
    assert "mock mode" in data["error"]["message"].lower()


def test_unknown_endpoint_returns_json_not_found(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/unknown-endpoint"
    response = httpx.get(url, timeout=5.0, trust_env=False)
    assert response.status_code == 404

    data = response.json()
    assert data["error"]["type"] == "not_found_error"
    assert "unknown endpoint" in data["error"]["message"].lower()


def test_openai_legacy_completions(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/completions"
    payload = {"model": "cascadeflow-auto", "prompt": "Hello legacy completions"}
    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "text_completion"
    assert data["choices"][0]["text"]


def test_openai_embeddings(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/embeddings"
    payload = {"model": "cascadeflow", "input": "hello embeddings"}
    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "list"
    assert data["data"]
    assert isinstance(data["data"][0]["embedding"], list)
    assert len(data["data"][0]["embedding"]) == 384


def test_openai_base_url_without_v1(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/chat/completions"
    payload = {
        "model": "cascadeflow-auto",
        "messages": [{"role": "user", "content": "Hello without /v1 base_url"}],
    }

    response = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
    assert response.status_code == 200


def test_openai_response_normalizes_universal_tool_calls_to_openai_shape():
    class _Result:
        content = ""
        metadata = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "name": "get_weather",
                    "arguments": {"city": "Berlin", "unit": "celsius"},
                }
            ]
        }
        draft_accepted = False
        quality_score = None
        complexity = "moderate"
        cascade_overhead_ms = 0

    response = _build_openai_response("cascadeflow", _Result())
    choice = response["choices"][0]

    assert choice["finish_reason"] == "tool_calls"
    tool_calls = choice["message"]["tool_calls"]
    assert isinstance(tool_calls, list)
    assert len(tool_calls) == 1
    first = tool_calls[0]
    assert first["id"] == "call_1"
    assert first["type"] == "function"
    assert first["function"]["name"] == "get_weather"
    parsed_args = json.loads(first["function"]["arguments"])
    assert parsed_args == {"city": "Berlin", "unit": "celsius"}


@pytest.mark.asyncio
async def test_concurrent_requests_cost_tracking(proxy_server):
    proxy, cost_tracker = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/chat/completions"
    timeout = httpx.Timeout(20.0, connect=5.0)
    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:

        async def _one(i: int) -> float:
            async with semaphore:
                payload = {
                    "model": "cascadeflow-auto",
                    "messages": [{"role": "user", "content": f"Hello concurrent {i}"}],
                }
                for attempt in range(3):
                    try:
                        resp = await client.post(url, json=payload)
                        assert resp.status_code == 200
                        data = resp.json()
                        return float(data["cascadeflow"]["cost"])
                    except (httpx.ConnectTimeout, httpx.ConnectError):
                        if attempt == 2:
                            raise
                        await asyncio.sleep(0.05 * (2**attempt))
                raise AssertionError("unreachable")

        n = 40
        costs = await asyncio.gather(*[_one(i) for i in range(n)])

    assert len(costs) == n
    assert len(cost_tracker.entries) == n
    assert cost_tracker.total_cost == pytest.approx(sum(costs), rel=1e-9, abs=1e-9)
