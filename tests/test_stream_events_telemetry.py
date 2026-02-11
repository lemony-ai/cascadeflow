"""
Tests for stream_events() telemetry tracking.

Verifies that draft_accepted and draft_rejected counters are updated
when streaming via stream_events(), matching the non-streaming path behavior.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from cascadeflow import CascadeAgent
from cascadeflow.schema.config import ModelConfig
from cascadeflow.streaming.base import StreamEvent, StreamEventType
from cascadeflow.streaming.tools import ToolStreamEvent, ToolStreamEventType


@pytest.fixture
def models():
    return [
        ModelConfig(name="small-model", provider="ollama", cost=0.0, domains=["general"]),
        ModelConfig(name="big-model", provider="openai", cost=0.01, domains=["general"]),
    ]


@pytest.fixture
def agent(models):
    with patch("cascadeflow.agent.PROVIDER_REGISTRY") as mock_registry:
        mock_provider = Mock()
        mock_provider.complete = AsyncMock(
            return_value=Mock(content="test", confidence=0.9, tokens_used=10)
        )
        mock_registry.__getitem__.return_value = lambda: mock_provider
        mock_registry.__contains__.return_value = True

        agent = CascadeAgent(models=models, verbose=False)
        agent.providers = {"ollama": mock_provider, "openai": mock_provider}
        yield agent


def _make_stream_events(result_data, event_cls=StreamEvent, type_cls=StreamEventType):
    """Create a mock async generator that yields ROUTING, CHUNK, and COMPLETE events."""

    async def fake_stream(**kwargs):
        yield event_cls(
            type=type_cls.ROUTING,
            content="",
            data={"strategy": "cascade"},
        )
        yield event_cls(
            type=type_cls.CHUNK if hasattr(type_cls, "CHUNK") else type_cls.TEXT_CHUNK,
            content="Hello world",
            data={},
        )
        yield event_cls(
            type=type_cls.COMPLETE,
            content="",
            data={"result": result_data},
        )

    return fake_stream


class TestStreamEventsTelemetry:
    """Test that stream_events() records draft_accepted/draft_rejected stats."""

    @pytest.mark.asyncio
    async def test_cascade_draft_accepted_tracked(self, agent):
        """When cascade accepts draft, draft_accepted counter increments."""
        result_data = {
            "content": "Draft response",
            "model_used": "small-model",
            "total_cost": 0.001,
            "latency_ms": 50.0,
            "draft_accepted": True,
            "cascaded": False,
        }

        mock_manager = Mock()
        mock_manager.stream = _make_stream_events(result_data)

        with patch.object(agent, "_get_streaming_manager", return_value=mock_manager):
            with patch.object(agent.router, "route", new_callable=AsyncMock) as mock_route:
                mock_route.return_value = Mock(is_cascade=lambda: True)

                events = []
                async for event in agent.stream_events("What is 2+2?", max_tokens=50):
                    events.append(event)

        assert agent.telemetry.stats["draft_accepted"] == 1
        assert agent.telemetry.stats["draft_rejected"] == 0
        assert agent.telemetry.stats["cascade_used"] == 1
        assert agent.telemetry.stats["streaming_used"] == 1
        assert agent.telemetry.stats["total_queries"] == 1

    @pytest.mark.asyncio
    async def test_cascade_draft_rejected_tracked(self, agent):
        """When cascade rejects draft, draft_rejected counter increments."""
        result_data = {
            "content": "Verified response",
            "model_used": "big-model",
            "total_cost": 0.01,
            "latency_ms": 200.0,
            "draft_accepted": False,
            "cascaded": True,
        }

        mock_manager = Mock()
        mock_manager.stream = _make_stream_events(result_data)

        with patch.object(agent, "_get_streaming_manager", return_value=mock_manager):
            with patch.object(agent.router, "route", new_callable=AsyncMock) as mock_route:
                mock_route.return_value = Mock(is_cascade=lambda: True)

                events = []
                async for event in agent.stream_events("Explain quantum physics", max_tokens=50):
                    events.append(event)

        assert agent.telemetry.stats["draft_rejected"] == 1
        assert agent.telemetry.stats["draft_accepted"] == 0
        assert agent.telemetry.stats["cascade_used"] == 1

    @pytest.mark.asyncio
    async def test_direct_route_no_draft_counters(self, agent):
        """Direct routes should not increment draft_accepted or draft_rejected."""
        result_data = {
            "content": "Direct response",
            "model_used": "big-model",
            "total_cost": 0.01,
            "latency_ms": 100.0,
            "draft_accepted": None,
            "routing_strategy": "direct",
        }

        mock_manager = Mock()
        mock_manager.stream = _make_stream_events(result_data)

        with patch.object(agent, "_get_streaming_manager", return_value=mock_manager):
            with patch.object(agent.router, "route", new_callable=AsyncMock) as mock_route:
                mock_route.return_value = Mock(is_cascade=lambda: False)

                events = []
                async for event in agent.stream_events(
                    "Hi", max_tokens=50, force_direct=True
                ):
                    events.append(event)

        assert agent.telemetry.stats["draft_accepted"] == 0
        assert agent.telemetry.stats["draft_rejected"] == 0
        assert agent.telemetry.stats["direct_routed"] == 1

    @pytest.mark.asyncio
    async def test_tool_stream_draft_accepted_tracked(self, agent):
        """Tool streaming (ToolStreamEvent) should also track draft_accepted."""
        result_data = {
            "content": "Tool response",
            "model_used": "small-model",
            "total_cost": 0.002,
            "latency_ms": 80.0,
            "draft_accepted": True,
            "cascaded": False,
            "tool_calls": [{"name": "get_weather", "arguments": "{}"}],
        }

        mock_tool_manager = Mock()
        mock_tool_manager.stream = _make_stream_events(
            result_data, event_cls=ToolStreamEvent, type_cls=ToolStreamEventType
        )

        with patch.object(agent, "_get_streaming_manager", return_value=mock_tool_manager):
            with patch.object(agent.router, "route", new_callable=AsyncMock) as mock_route:
                mock_route.return_value = Mock(is_cascade=lambda: True)

                tools = [{"type": "function", "function": {"name": "get_weather"}}]
                events = []
                async for event in agent.stream_events(
                    "What's the weather?", max_tokens=50, tools=tools
                ):
                    events.append(event)

        assert agent.telemetry.stats["draft_accepted"] == 1
        assert agent.telemetry.stats["draft_rejected"] == 0
        assert agent.telemetry.stats["cascade_used"] == 1

    @pytest.mark.asyncio
    async def test_multiple_streams_accumulate_stats(self, agent):
        """Multiple stream_events() calls should accumulate stats correctly."""
        accepted_data = {
            "content": "Accepted",
            "model_used": "small-model",
            "total_cost": 0.001,
            "latency_ms": 50.0,
            "draft_accepted": True,
        }
        rejected_data = {
            "content": "Rejected",
            "model_used": "big-model",
            "total_cost": 0.01,
            "latency_ms": 200.0,
            "draft_accepted": False,
        }

        with patch.object(agent.router, "route", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = Mock(is_cascade=lambda: True)

            # First call: draft accepted
            mock_manager = Mock()
            mock_manager.stream = _make_stream_events(accepted_data)
            with patch.object(agent, "_get_streaming_manager", return_value=mock_manager):
                async for _ in agent.stream_events("Simple question", max_tokens=50):
                    pass

            # Second call: draft rejected
            mock_manager = Mock()
            mock_manager.stream = _make_stream_events(rejected_data)
            with patch.object(agent, "_get_streaming_manager", return_value=mock_manager):
                async for _ in agent.stream_events("Hard question", max_tokens=50):
                    pass

            # Third call: draft accepted again
            mock_manager = Mock()
            mock_manager.stream = _make_stream_events(accepted_data)
            with patch.object(agent, "_get_streaming_manager", return_value=mock_manager):
                async for _ in agent.stream_events("Another simple one", max_tokens=50):
                    pass

        assert agent.telemetry.stats["draft_accepted"] == 2
        assert agent.telemetry.stats["draft_rejected"] == 1
        assert agent.telemetry.stats["total_queries"] == 3
        assert agent.telemetry.stats["streaming_used"] == 3
        assert agent.telemetry.stats["cascade_used"] == 3
