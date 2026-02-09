import httpx
import pytest

from cascadeflow.proxy import ProxyConfig, RoutingProxy
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

    response = httpx.post(url, json=payload, timeout=5.0)
    assert response.status_code == 200

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

    with httpx.stream("POST", url, json=payload, timeout=5.0) as response:
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

    response = httpx.post(url, json=payload, timeout=5.0)
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

    with httpx.stream("POST", url, json=payload, timeout=5.0) as response:
        assert response.status_code == 200
        lines = _get_lines(response)

    assert any(line.startswith("event: message_start") for line in lines)
    assert any(line.startswith("event: message_stop") for line in lines)
    assert any(line == "data: [DONE]" for line in lines)


def test_error_handling(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/chat/completions"
    payload = {"messages": [{"role": "user", "content": "Missing model"}]}

    response = httpx.post(url, json=payload, timeout=5.0)
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

    response = httpx.post(url, json=payload, timeout=5.0)
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

    response = httpx.post(url, json=payload, timeout=5.0)
    assert response.status_code == 200
    data = response.json()
    assert data["cascadeflow"]["virtual_model"] == "cascadeflow-fast"
    assert data["cascadeflow"]["resolved_model"] == proxy.config.virtual_models["cascadeflow-fast"]


def test_models_list(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/models"
    response = httpx.get(url, timeout=5.0)
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "list"
    ids = {item["id"] for item in data["data"]}
    assert "cascadeflow" in ids
    assert "cascadeflow-auto" in ids


def test_openai_legacy_completions(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/completions"
    payload = {"model": "cascadeflow-auto", "prompt": "Hello legacy completions"}
    response = httpx.post(url, json=payload, timeout=5.0)
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "text_completion"
    assert data["choices"][0]["text"]


def test_openai_embeddings(proxy_server):
    proxy, _ = proxy_server
    url = f"http://{proxy.host}:{proxy.port}/v1/embeddings"
    payload = {"model": "cascadeflow", "input": "hello embeddings"}
    response = httpx.post(url, json=payload, timeout=5.0)
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

    response = httpx.post(url, json=payload, timeout=5.0)
    assert response.status_code == 200
