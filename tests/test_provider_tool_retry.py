import asyncio

from cascadeflow.providers.base import BaseProvider, ModelResponse, RetryConfig


class _FakeToolProvider(BaseProvider):
    def __init__(self, *, retry_config: RetryConfig) -> None:
        super().__init__(api_key="test", retry_config=retry_config, enable_circuit_breaker=False)
        self.complete_with_tools_calls = 0

    async def _complete_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: str | None = None,
        **kwargs,
    ) -> ModelResponse:
        return ModelResponse(
            content="ok",
            model=model,
            provider="fake",
            cost=0.0,
            tokens_used=0,
            confidence=1.0,
            latency_ms=0.0,
            tool_calls=None,
            metadata={},
        )

    async def _stream_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: str | None = None,
        **kwargs,
    ):
        if False:  # pragma: no cover
            yield ""

    def estimate_cost(self, tokens: int, model: str) -> float:
        return 0.0

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools=None,
        model: str = "x",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice=None,
        **kwargs,
    ) -> ModelResponse:
        self.complete_with_tools_calls += 1
        if self.complete_with_tools_calls == 1:
            raise RuntimeError("429 Too Many Requests")
        return ModelResponse(
            content="tool-ok",
            model=model,
            provider="fake",
            cost=0.0,
            tokens_used=0,
            confidence=1.0,
            latency_ms=0.0,
            tool_calls=[],
            metadata={},
        )


def test_tool_calls_use_retry_wrapper() -> None:
    async def _run() -> None:
        provider = _FakeToolProvider(
            retry_config=RetryConfig(
                max_attempts=2,
                initial_delay=0,
                max_delay=0,
                jitter=False,
                rate_limit_backoff=0,
            )
        )

        response = await provider.complete(
            messages=[{"role": "user", "content": "hi"}],
            tools=[
                {
                    "type": "function",
                    "function": {"name": "noop", "parameters": {"type": "object"}},
                }
            ],
            model="x",
        )

        assert response.content == "tool-ok"
        assert provider.complete_with_tools_calls == 2
        assert provider.retry_metrics.total_attempts == 2

    asyncio.run(_run())
