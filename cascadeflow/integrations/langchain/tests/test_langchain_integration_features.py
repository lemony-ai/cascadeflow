from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from cascadeflow.integrations.langchain import CascadeFlow


class MockSequenceChatModel(BaseChatModel):
    model_name: str = "mock"
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
        return "mock_seq"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls += 1
        self.last_kwargs = kwargs
        message = AIMessage(content=self.text)
        return ChatResult(generations=[ChatGeneration(text=self.text, message=message)], llm_output={})

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def test_domain_policy_quality_threshold_override_accepts_drafter() -> None:
    drafter = MockSequenceChatModel("draft")
    verifier = MockSequenceChatModel("verified")

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.9,
        quality_validator=lambda _: 0.6,
        domain_policies={"finance": {"quality_threshold": 0.5}},
        enable_pre_router=False,
    )

    result = cascade._generate(
        [HumanMessage(content="Summarize earnings")],
        metadata={"cascadeflow_domain": "finance"},
    )

    assert result.generations[0].text == "draft"
    assert drafter.calls == 1
    assert verifier.calls == 0
    assert result.llm_output["cascade"]["effective_quality_threshold"] == 0.5


def test_domain_policy_force_verifier_escalates() -> None:
    drafter = MockSequenceChatModel("draft")
    verifier = MockSequenceChatModel("verified")

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.1,
        quality_validator=lambda _: 0.99,
        domain_policies={"medical": {"force_verifier": True}},
        enable_pre_router=False,
    )

    result = cascade._generate(
        [HumanMessage(content="Medical guidance")],
        metadata={"cascadeflow": {"domain": "medical"}},
    )

    assert result.generations[0].text == "verified"
    assert drafter.calls == 1
    assert verifier.calls == 1
    assert result.llm_output["cascade"]["cascade_decision"] == "domain_policy"


def test_domain_policy_direct_to_verifier_skips_drafter() -> None:
    drafter = MockSequenceChatModel("draft")
    verifier = MockSequenceChatModel("verified")

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        domain_policies={"legal": {"direct_to_verifier": True}},
        enable_pre_router=False,
    )

    result = cascade._generate(
        [HumanMessage(content="Review this contract")],
        metadata={"domain": "legal"},
    )

    assert result.generations[0].text == "verified"
    assert drafter.calls == 0
    assert verifier.calls == 1
    assert result.llm_output["cascade"]["routing_reason"] == "domain_policy_direct"
