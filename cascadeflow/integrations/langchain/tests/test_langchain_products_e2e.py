"""LangChain ecosystem integration fixtures (LangGraph/LangSmith/LangServe)."""

from typing import Any, Optional

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from cascadeflow.integrations.langchain import CascadeFlow


class MockEcosystemChatModel(BaseChatModel):
    model_name: str = "mock-ecosystem"
    text: str = "mock"
    calls: int = 0
    last_kwargs: dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, text: str, **kwargs: Any):
        super().__init__(text=text, calls=0, last_kwargs={}, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "mock_ecosystem"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls += 1
        self.last_kwargs = kwargs
        return ChatResult(
            generations=[ChatGeneration(text=self.text, message=AIMessage(content=self.text))],
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


def test_langsmith_style_metadata_and_domain_tags_fixture() -> None:
    drafter = MockEcosystemChatModel("draft")
    verifier = MockEcosystemChatModel("verify")

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        enable_pre_router=False,
        domain_policies={"finance": {"quality_threshold": 0.5}},
        quality_validator=lambda _: 0.6,
        quality_threshold=0.9,
    )

    result = cascade._generate(
        [HumanMessage(content="Summarize earnings")],
        tags=["langsmith-fixture"],
        metadata={"cascadeflow_domain": "finance", "app": "fixture"},
    )

    cascade_metadata = result.llm_output.get("cascade", {})
    assert cascade_metadata.get("domain") == "finance"
    assert cascade_metadata.get("effective_quality_threshold") == 0.5
    assert cascade_metadata.get("cascade_decision") == "accepted"


@pytest.mark.asyncio
async def test_langgraph_fixture_with_domain_policy() -> None:
    try:
        from langgraph.graph import END, StateGraph  # type: ignore
    except Exception:
        pytest.skip("langgraph is not installed")

    drafter = MockEcosystemChatModel("draft")
    verifier = MockEcosystemChatModel("verify")

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        enable_pre_router=False,
        quality_threshold=0.9,
        quality_validator=lambda _: 0.6,
        domain_policies={"finance": {"quality_threshold": 0.5}},
    )

    def planner(state: dict[str, Any]) -> dict[str, Any]:
        msg = cascade.invoke(
            [HumanMessage(content=state["input"])],
            config={
                "tags": ["langgraph", "fixture"],
                "metadata": {"cascadeflow_domain": "finance", "example": "langgraph-fixture"},
            },
        )
        return {**state, "result": msg.content}

    graph = StateGraph(dict)
    graph.add_node("planner", planner)
    graph.set_entry_point("planner")
    graph.add_edge("planner", END)

    app = graph.compile()
    out = app.invoke({"input": "Summarize Q4 earnings"})

    assert out.get("result") == "draft"
    assert drafter.calls == 1
    assert verifier.calls == 0


def test_langserve_fixture_route_registration() -> None:
    try:
        from fastapi import FastAPI
        from langserve import add_routes  # type: ignore
    except Exception:
        pytest.skip("langserve/fastapi is not installed")

    drafter = MockEcosystemChatModel("draft")
    verifier = MockEcosystemChatModel("verify")

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        enable_pre_router=False,
        domain_policies={"legal": {"direct_to_verifier": True}},
    )

    app = FastAPI()
    add_routes(app, cascade, path="/cascade")

    paths = {route.path for route in app.routes}
    assert any(path.startswith("/cascade") for path in paths)
