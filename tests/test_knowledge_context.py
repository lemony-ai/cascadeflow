from __future__ import annotations

from unittest.mock import patch

import pytest

from cascadeflow.agent import CascadeAgent
from cascadeflow.context import KnowledgeCache, KnowledgeSnapshot, provider_cache_kwargs
from cascadeflow.providers.base import ModelResponse
from cascadeflow.schema.config import ModelConfig


def test_snapshot_is_content_addressed_and_reused() -> None:
    cache = KnowledgeCache(max_entries=2)
    first, first_hit = cache.prepare(KnowledgeSnapshot("alpha", key="docs"))
    second, second_hit = cache.prepare(KnowledgeSnapshot("alpha", key="docs"))

    assert not first_hit
    assert second_hit
    assert first is second
    assert cache.get_stats() == {"size": 1, "hits": 1, "misses": 1, "evictions": 0}


def test_explicit_version_cannot_silently_change_content() -> None:
    cache = KnowledgeCache()
    cache.prepare(KnowledgeSnapshot("current", key="docs", version="v1"))

    with pytest.raises(ValueError, match="version collision"):
        cache.prepare(KnowledgeSnapshot("stale-or-different", key="docs", version="v1"))


def test_provider_key_remains_content_bound_after_local_eviction() -> None:
    cache = KnowledgeCache(max_entries=1)
    old, _ = cache.prepare(KnowledgeSnapshot("old", key="docs", version="v1"))
    cache.prepare(KnowledgeSnapshot("other", key="other", version="v1"))
    new, _ = cache.prepare(KnowledgeSnapshot("new", key="docs", version="v1"))

    assert old.prompt_cache_key != new.prompt_cache_key


def test_provider_cache_hints_are_capability_specific() -> None:
    prepared, _ = KnowledgeCache().prepare(
        KnowledgeSnapshot("shared", key="docs", version="v3", cache_ttl="1h")
    )

    assert provider_cache_kwargs("openai", prepared) == {
        "prompt_cache_key": prepared.prompt_cache_key,
        "_cascadeflow_knowledge_cache_prefix": prepared.system_prefix,
    }
    assert provider_cache_kwargs("anthropic", prepared) == {
        "cache_control": {"type": "ephemeral", "ttl": "1h"}
    }
    assert provider_cache_kwargs("ollama", prepared) == {}


@pytest.mark.asyncio
async def test_agent_switches_knowledge_without_leaking_previous_snapshot() -> None:
    model = ModelConfig(name="gpt-test", provider="openai", cost=0.001)

    class RecordingProvider:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def complete(self, **kwargs):
            self.calls.append(kwargs)
            return ModelResponse(
                content="ok",
                model="gpt-test",
                provider="openai",
                cost=0.001,
                tokens_used=2,
                confidence=0.9,
                metadata={"input_tokens": 1, "output_tokens": 1},
            )

    provider = RecordingProvider()
    with patch("cascadeflow.agent.PROVIDER_REGISTRY") as registry:
        registry.__getitem__.return_value = lambda: provider
        registry.__contains__.return_value = True
        agent = CascadeAgent(models=[model], enable_cascade=False)
        agent.providers = {"openai": provider}
        agent.model_providers = {model.name: provider}

    alpha = KnowledgeSnapshot("ALPHA_ONLY", key="tenant", version="a")
    beta = KnowledgeSnapshot("BETA_ONLY", key="tenant", version="b")

    first = await agent.run("question", force_direct=True, knowledge=alpha)
    second = await agent.run("question", force_direct=True, knowledge=beta)
    third = await agent.run("question", force_direct=True, knowledge=beta)

    first_prompt = provider.calls[0]["prompt"]
    second_prompt = provider.calls[1]["prompt"]
    assert "ALPHA_ONLY" in first_prompt
    assert "BETA_ONLY" not in first_prompt
    assert "BETA_ONLY" in second_prompt
    assert "ALPHA_ONLY" not in second_prompt
    assert provider.calls[0]["prompt_cache_key"] != provider.calls[1]["prompt_cache_key"]
    assert first.metadata["knowledge"]["local_cache_hit"] is False
    assert second.metadata["knowledge"]["local_cache_hit"] is False
    assert third.metadata["knowledge"]["local_cache_hit"] is True


@pytest.mark.asyncio
async def test_system_prompt_is_kept_after_stable_knowledge_prefix() -> None:
    model = ModelConfig(name="local-test", provider="ollama", cost=0.0)

    class RecordingProvider:
        async def complete(self, **kwargs):
            self.kwargs = kwargs
            return ModelResponse(
                content="ok",
                model="local-test",
                provider="ollama",
                cost=0.0,
                tokens_used=2,
                confidence=0.9,
            )

    provider = RecordingProvider()
    with patch("cascadeflow.agent.PROVIDER_REGISTRY") as registry:
        registry.__getitem__.return_value = lambda: provider
        registry.__contains__.return_value = True
        agent = CascadeAgent(models=[model], enable_cascade=False)
        agent.providers = {"ollama": provider}
        agent.model_providers = {model.name: provider}

    await agent.run(
        "question",
        force_direct=True,
        system_prompt="SYSTEM_RULE",
        knowledge=KnowledgeSnapshot("KNOWLEDGE", key="docs", version="1"),
    )

    prompt = provider.kwargs["prompt"]
    assert prompt.index("KNOWLEDGE") < prompt.index("SYSTEM_RULE") < prompt.index("question")
    assert "prompt_cache_key" not in provider.kwargs
    assert "cache_control" not in provider.kwargs
