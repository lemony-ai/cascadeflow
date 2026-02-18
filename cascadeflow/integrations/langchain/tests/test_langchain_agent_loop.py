from typing import Any, Optional

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from cascadeflow.integrations.langchain import CascadeAgent


class MockLoopChatModel(BaseChatModel):
    model_name: str = "mock-loop"
    loop_forever: bool = False
    calls: int = 0

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, loop_forever: bool = False, **kwargs: Any):
        super().__init__(loop_forever=loop_forever, calls=0, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "mock_loop"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls += 1
        has_tool_result = any(isinstance(m, ToolMessage) for m in messages)

        if self.loop_forever or not has_tool_result:
            message = AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "get_weather", "args": {"city": "Berlin"}}],
            )
            return ChatResult(generations=[ChatGeneration(text="", message=message)], llm_output={})

        message = AIMessage(content="Weather in Berlin is sunny.")
        return ChatResult(
            generations=[ChatGeneration(text="Weather in Berlin is sunny.", message=message)],
            llm_output={},
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def test_cascade_agent_run_completes_tool_loop() -> None:
    model = MockLoopChatModel()
    agent = CascadeAgent(model=model, tool_handlers={"get_weather": lambda args: "sunny"}, max_steps=4)

    result = agent.run("What is the weather?")

    assert result.status == "completed"
    assert result.steps == 2
    assert result.message.content == "Weather in Berlin is sunny."
    assert any(isinstance(m, ToolMessage) for m in result.messages)


@pytest.mark.asyncio
async def test_cascade_agent_arun_supports_async_tool_handler() -> None:
    async def weather_handler(args: dict[str, Any]) -> str:
        return f"sunny in {args.get('city', 'unknown')}"

    model = MockLoopChatModel()
    agent = CascadeAgent(model=model, tool_handlers={"get_weather": weather_handler}, max_steps=4)

    result = await agent.arun([{"role": "user", "content": "Weather?"}])

    assert result.status == "completed"
    assert result.steps == 2
    assert isinstance(result.message, AIMessage)


def test_cascade_agent_run_stops_at_max_steps() -> None:
    model = MockLoopChatModel(loop_forever=True)
    agent = CascadeAgent(model=model, tool_handlers={"get_weather": lambda args: "sunny"}, max_steps=2)

    result = agent.run([HumanMessage(content="loop")])

    assert result.status == "max_steps_reached"
    assert result.steps == 2
    assert len(result.tool_calls) >= 2
