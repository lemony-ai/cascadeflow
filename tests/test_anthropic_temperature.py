"""Exercise sampling parameters at the Anthropic HTTP boundary."""

import json

import httpx
import pytest

from cascadeflow.providers.anthropic import AnthropicProvider
from cascadeflow.providers.base import RetryConfig


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["complete", "tools", "stream"])
@pytest.mark.parametrize("temperature", [None, 0, 0.2])
@pytest.mark.parametrize(
    ("model", "supports_temperature"),
    [
        ("claude-opus-4-7", False),
        ("claude-opus-4-8", False),
        ("claude-opus-5-5", False),
        ("claude-sonnet-5-5", False),
        ("claude-haiku-5-5", False),
        ("claude-fable-5", False),
        ("anthropic/CLAUDE-MYTHOS-5", False),
        ("claude-opus-4.7-latest", False),
        ("anthropic/claude_opus_4_7", False),
        ("claude-opus-4-6", True),
        ("claude-sonnet-4-5", True),
        ("custom-model", True),
    ],
)
async def test_anthropic_temperature_payload(model, supports_temperature, temperature, operation):
    payloads = []

    def handle(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        if not supports_temperature and "temperature" in payload:
            return httpx.Response(400, json={"error": {"message": "temperature not supported"}})
        if payload.get("stream"):
            return httpx.Response(
                200,
                text='data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"ok"}}\n\n'
                'data: {"type":"message_stop"}\n\n',
            )
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    provider = AnthropicProvider(api_key="test", retry_config=RetryConfig(max_attempts=1))
    await provider.client.aclose()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider.client = client
        options = {"model": model}
        if temperature is not None:
            options["temperature"] = temperature
        if operation == "stream":
            assert (
                "".join([chunk async for chunk in provider.stream(prompt="hi", **options)]) == "ok"
            )
        elif operation == "tools":
            response = await provider.complete_with_tools(
                messages=[{"role": "user", "content": "hi"}],
                tools=[{"name": "noop", "parameters": {"type": "object"}}],
                **options,
            )
            assert response.content == "ok"
        else:
            response = await provider.complete(prompt="hi", **options)
            assert response.content == "ok"

    assert len(payloads) == 1
    if supports_temperature:
        assert payloads[0]["temperature"] == (0.7 if temperature is None else temperature)
    else:
        assert "temperature" not in payloads[0]
