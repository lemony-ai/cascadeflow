"""Tests for LangChain tool calling with CascadeFlow.

This test suite validates that bind_tools() and with_structured_output()
work correctly with the cascade pattern, ensuring tools are properly bound
to both drafter and verifier models.
"""

from typing import Any, Optional

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from cascadeflow.integrations.langchain import CascadeFlow


class MockToolChatModel(BaseChatModel):
    """Mock chat model with tool calling support for testing."""

    model_name: str = "mock"
    response_text: str = "Mock response"

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
        extra = "allow"  # Allow setting bound_tools and other attributes

    def __init__(self, model_name: str = "mock", response_text: str = "Mock response", **kwargs):
        super().__init__(model_name=model_name, response_text=response_text, **kwargs)
        # Set mutable attributes after initialization to avoid Pydantic issues
        self.bound_tools = []
        self.bound_schema = None
        self.generate_called = 0
        self.agenerate_called = 0

    @property
    def _llm_type(self) -> str:
        return "mock_tool_model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate mock response."""
        self.generate_called += 1
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=self.response_text,
                        additional_kwargs={
                            "tool_calls": (
                                [{"name": "test_tool", "args": {"param": "value"}}]
                                if self.bound_tools
                                else []
                            )
                        },
                    )
                )
            ]
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate mock response."""
        self.agenerate_called += 1
        return self._generate(messages, stop, run_manager, **kwargs)

    def bind_tools(self, tools: Any, **kwargs: Any) -> "MockToolChatModel":
        """Bind tools to this model."""
        new_model = MockToolChatModel(model_name=self.model_name, response_text=self.response_text)
        new_model.bound_tools = list(tools) if tools else []
        new_model.bound_schema = getattr(self, "bound_schema", None)
        return new_model

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "MockToolChatModel":
        """Bind structured output schema to this model."""
        new_model = MockToolChatModel(model_name=self.model_name, response_text=self.response_text)
        new_model.bound_tools = (
            getattr(self, "bound_tools", []).copy() if hasattr(self, "bound_tools") else []
        )
        new_model.bound_schema = schema
        return new_model


class TestBindTools:
    """Test bind_tools() method."""

    def test_bind_tools_creates_new_instance(self):
        """Test that bind_tools returns a new CascadeFlow instance."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        tools = [{"name": "test_tool", "description": "A test tool"}]
        cascade_with_tools = cascade.bind_tools(tools)

        assert isinstance(cascade_with_tools, CascadeFlow)
        assert cascade_with_tools is not cascade
        assert cascade_with_tools.drafter is not drafter
        assert cascade_with_tools.verifier is not verifier

    def test_bind_tools_binds_to_drafter(self):
        """Test that tools are bound to the drafter model."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        tools = [{"name": "calculator", "description": "Calculate numbers"}]
        cascade_with_tools = cascade.bind_tools(tools)

        # Check drafter has tools bound
        assert hasattr(cascade_with_tools.drafter, "bound_tools")
        assert len(cascade_with_tools.drafter.bound_tools) == 1
        assert cascade_with_tools.drafter.bound_tools[0]["name"] == "calculator"

    def test_bind_tools_binds_to_verifier(self):
        """Test that tools are bound to the verifier model."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        tools = [
            {"name": "tool1", "description": "First tool"},
            {"name": "tool2", "description": "Second tool"},
        ]
        cascade_with_tools = cascade.bind_tools(tools)

        # Check verifier has tools bound
        assert hasattr(cascade_with_tools.verifier, "bound_tools")
        assert len(cascade_with_tools.verifier.bound_tools) == 2

    def test_bind_tools_with_tool_choice(self):
        """Test bind_tools with tool_choice parameter."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        tools = [{"name": "test_tool", "description": "A test tool"}]
        cascade_with_tools = cascade.bind_tools(tools, tool_choice="auto")

        assert isinstance(cascade_with_tools, CascadeFlow)

    def test_bind_tools_preserves_config(self):
        """Test that bind_tools preserves cascade configuration."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(
            drafter=drafter,
            verifier=verifier,
            quality_threshold=0.8,
            enable_pre_router=False,
        )

        tools = [{"name": "test_tool", "description": "A test tool"}]
        cascade_with_tools = cascade.bind_tools(tools)

        assert cascade_with_tools.quality_threshold == 0.8
        assert cascade_with_tools.enable_pre_router is False

    def test_bind_tools_chains_with_bind(self):
        """Test that bind_tools can be chained with bind()."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        tools = [{"name": "test_tool", "description": "A test tool"}]
        chained = cascade.bind(temperature=0.5).bind_tools(tools)

        assert isinstance(chained, CascadeFlow)
        assert chained._bind_kwargs.get("temperature") == 0.5

    def test_bind_tools_error_when_drafter_lacks_support(self):
        """Test error when drafter doesn't support bind_tools."""

        # Create a minimal model class without bind_tools
        class MinimalChatModel(BaseChatModel):
            @property
            def _llm_type(self) -> str:
                return "basic"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="test"))])

        drafter = MinimalChatModel()
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        tools = [{"name": "test_tool", "description": "A test tool"}]

        with pytest.raises((AttributeError, NotImplementedError)):
            cascade.bind_tools(tools)

    def test_bind_tools_error_when_verifier_lacks_support(self):
        """Test error when verifier doesn't support bind_tools."""
        drafter = MockToolChatModel("drafter")

        # Create a minimal model class without bind_tools
        class MinimalChatModel(BaseChatModel):
            @property
            def _llm_type(self) -> str:
                return "basic"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="test"))])

        verifier = MinimalChatModel()
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        tools = [{"name": "test_tool", "description": "A test tool"}]

        with pytest.raises((AttributeError, NotImplementedError)):
            cascade.bind_tools(tools)


class TestWithStructuredOutput:
    """Test with_structured_output() method."""

    def test_with_structured_output_creates_new_instance(self):
        """Test that with_structured_output returns a new CascadeFlow instance."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        schema = {"name": "User", "type": "object"}
        cascade_structured = cascade.with_structured_output(schema)

        assert isinstance(cascade_structured, CascadeFlow)
        assert cascade_structured is not cascade
        assert cascade_structured.drafter is not drafter
        assert cascade_structured.verifier is not verifier

    def test_with_structured_output_binds_to_drafter(self):
        """Test that schema is bound to the drafter model."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        schema = {"name": "User", "properties": {"name": {"type": "string"}}}
        cascade_structured = cascade.with_structured_output(schema)

        # Check drafter has schema bound
        assert hasattr(cascade_structured.drafter, "bound_schema")
        assert cascade_structured.drafter.bound_schema == schema

    def test_with_structured_output_binds_to_verifier(self):
        """Test that schema is bound to the verifier model."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        schema = {"name": "Response", "type": "object"}
        cascade_structured = cascade.with_structured_output(schema)

        # Check verifier has schema bound
        assert hasattr(cascade_structured.verifier, "bound_schema")
        assert cascade_structured.verifier.bound_schema == schema

    def test_with_structured_output_with_include_raw(self):
        """Test with_structured_output with include_raw parameter."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        schema = {"name": "Data", "type": "object"}
        cascade_structured = cascade.with_structured_output(schema, include_raw=True)

        assert isinstance(cascade_structured, CascadeFlow)

    def test_with_structured_output_preserves_config(self):
        """Test that with_structured_output preserves cascade configuration."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(
            drafter=drafter,
            verifier=verifier,
            quality_threshold=0.9,
            enable_cost_tracking=False,
        )

        schema = {"name": "Output", "type": "object"}
        cascade_structured = cascade.with_structured_output(schema)

        assert cascade_structured.quality_threshold == 0.9
        assert cascade_structured.enable_cost_tracking is False

    def test_with_structured_output_chains_with_bind(self):
        """Test that with_structured_output can be chained with bind()."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        schema = {"name": "Result", "type": "object"}
        chained = cascade.bind(temperature=0.3).with_structured_output(schema)

        assert isinstance(chained, CascadeFlow)
        assert chained._bind_kwargs.get("temperature") == 0.3

    def test_with_structured_output_error_when_drafter_lacks_support(self):
        """Test error when drafter doesn't support with_structured_output."""

        # Create a minimal model class without with_structured_output
        class MinimalChatModel(BaseChatModel):
            @property
            def _llm_type(self) -> str:
                return "basic"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="test"))])

        drafter = MinimalChatModel()
        verifier = MockToolChatModel("verifier")
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        schema = {"name": "Output", "type": "object"}

        with pytest.raises((AttributeError, NotImplementedError)):
            cascade.with_structured_output(schema)

    def test_with_structured_output_error_when_verifier_lacks_support(self):
        """Test error when verifier doesn't support with_structured_output."""
        drafter = MockToolChatModel("drafter")

        # Create a minimal model class without with_structured_output
        class MinimalChatModel(BaseChatModel):
            @property
            def _llm_type(self) -> str:
                return "basic"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="test"))])

        verifier = MinimalChatModel()
        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        schema = {"name": "Output", "type": "object"}

        with pytest.raises((AttributeError, NotImplementedError)):
            cascade.with_structured_output(schema)


class TestToolCallingIntegration:
    """Integration tests for tool calling with cascade."""

    def test_cascade_uses_drafter_with_tools(self):
        """Test that cascade can use drafter with bound tools."""
        drafter = MockToolChatModel("drafter", "Drafter response with tool call")
        verifier = MockToolChatModel("verifier", "Verifier response")

        cascade = CascadeFlow(
            drafter=drafter,
            verifier=verifier,
            quality_threshold=0.0,  # Zero threshold to always use drafter
            enable_pre_router=False,  # Disable pre-router to simplify test
        )

        tools = [{"name": "calculator", "description": "Calculate numbers"}]
        cascade_with_tools = cascade.bind_tools(tools)

        # Invoke cascade
        result = cascade_with_tools.invoke([HumanMessage(content="What is 2+2?")])

        # Drafter should have been used (with tools)
        assert cascade_with_tools.drafter.generate_called > 0
        # With quality threshold 0, drafter response should be accepted
        assert result.content == "Drafter response with tool call"

    def test_cascade_escalates_to_verifier_with_tools(self):
        """Test that cascade escalates to verifier when quality is insufficient."""
        drafter = MockToolChatModel("drafter", "Low quality response")
        verifier = MockToolChatModel("verifier", "High quality verifier response")

        cascade = CascadeFlow(
            drafter=drafter,
            verifier=verifier,
            quality_threshold=0.99,  # High threshold to force verifier
            enable_pre_router=False,  # Disable pre-router to simplify test
        )

        tools = [{"name": "search", "description": "Search the web"}]
        cascade_with_tools = cascade.bind_tools(tools)

        # Invoke cascade
        result = cascade_with_tools.invoke([HumanMessage(content="Complex query")])

        # Both drafter and verifier should have been called
        assert cascade_with_tools.drafter.generate_called > 0
        assert cascade_with_tools.verifier.generate_called > 0
        assert result.content == "High quality verifier response"

    @pytest.mark.asyncio
    async def test_cascade_async_with_tools(self):
        """Test async cascade invocation with tools."""
        drafter = MockToolChatModel("drafter", "Async drafter response")
        verifier = MockToolChatModel("verifier", "Async verifier response")

        cascade = CascadeFlow(
            drafter=drafter,
            verifier=verifier,
            quality_threshold=0.0,  # Zero threshold to always use drafter
            enable_pre_router=False,  # Disable pre-router to simplify test
        )

        tools = [{"name": "async_tool", "description": "An async tool"}]
        cascade_with_tools = cascade.bind_tools(tools)

        # Async invoke
        result = await cascade_with_tools.ainvoke([HumanMessage(content="Test query")])

        assert cascade_with_tools.drafter.agenerate_called > 0
        # With quality threshold 0, drafter response should be accepted
        assert result.content == "Async drafter response"

    def test_chaining_bind_and_bind_tools(self):
        """Test chaining bind() and bind_tools() methods."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")

        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        # Chain bind and bind_tools
        tools = [{"name": "tool1", "description": "Tool 1"}]
        chained = cascade.bind(temperature=0.7).bind_tools(tools)

        assert isinstance(chained, CascadeFlow)
        assert chained._bind_kwargs.get("temperature") == 0.7
        assert len(chained.drafter.bound_tools) == 1
        assert len(chained.verifier.bound_tools) == 1

    def test_chaining_bind_tools_and_with_structured_output(self):
        """Test chaining bind_tools() and with_structured_output()."""
        drafter = MockToolChatModel("drafter")
        verifier = MockToolChatModel("verifier")

        cascade = CascadeFlow(drafter=drafter, verifier=verifier)

        # Chain bind_tools and with_structured_output
        tools = [{"name": "tool1", "description": "Tool 1"}]
        schema = {"name": "Output", "type": "object"}

        chained = cascade.bind_tools(tools).with_structured_output(schema)

        assert isinstance(chained, CascadeFlow)
        # Tools should be on the models before structured output was applied
        assert hasattr(chained.drafter, "bound_schema")
        assert hasattr(chained.verifier, "bound_schema")
