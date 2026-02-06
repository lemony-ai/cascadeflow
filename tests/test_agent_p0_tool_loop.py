from unittest.mock import Mock, patch

import asyncio
import pytest

from cascadeflow.agent import CascadeAgent
from cascadeflow.providers.base import ModelResponse
from cascadeflow.schema.config import ModelConfig


def test_run_direct_uses_provider_usage_and_emits_transcript():
    models = [
        ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
        ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
    ]

    class Provider:
        def __init__(self):
            self.calls = 0

        async def complete_with_tools(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse(
                    content="",
                    model="gpt-4o",
                    provider="openai",
                    cost=0.55,
                    tokens_used=20,
                    confidence=0.9,
                    tool_calls=[
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": "{}"},
                        }
                    ],
                    metadata={"usage": {"input_tokens": 10, "output_tokens": 10}},
                )
            return ModelResponse(
                content="final",
                model="gpt-4o",
                provider="openai",
                cost=0.66,
                tokens_used=30,
                confidence=0.9,
                tool_calls=[],
                metadata={"usage": {"input_tokens": 12, "output_tokens": 18}},
            )

    provider = Provider()
    with patch("cascadeflow.agent.PROVIDER_REGISTRY") as mock_registry:
        mock_registry.__getitem__.return_value = lambda: provider
        mock_registry.__contains__.return_value = True
        agent = CascadeAgent(models=models, enable_tool_complexity_routing=False)
        agent.providers = {"openai": provider}
        agent.model_providers = {m.name: provider for m in models}

    result = asyncio.run(
        agent.run(
            "q",
            force_direct=True,
            tools=[{"type": "function", "function": {"name": "lookup", "parameters": {}}}],
            max_steps=3,
        )
    )

    assert result.total_cost == pytest.approx(0.66)
    transcript = result.metadata.get("transcript")
    assert transcript and len(transcript) >= 2
    assert result.metadata.get("usage", {}).get("input_tokens") == 12
