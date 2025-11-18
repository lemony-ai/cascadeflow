"""Test suite for LangChain callback handlers."""

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from cascadeflow.integrations.langchain.langchain_callbacks import (
    CascadeFlowCallbackHandler,
    get_cascade_callback,
)


class TestCascadeFlowCallbackHandler:
    """Test CascadeFlowCallbackHandler functionality."""

    def test_initialization(self):
        """Test callback handler initializes with correct defaults."""
        handler = CascadeFlowCallbackHandler()

        assert handler.total_tokens == 0
        assert handler.prompt_tokens == 0
        assert handler.completion_tokens == 0
        assert handler.total_cost == 0.0
        assert handler.drafter_cost == 0.0
        assert handler.verifier_cost == 0.0
        assert handler.successful_requests == 0
        assert handler.drafter_accepted == 0
        assert handler.escalated_to_verifier == 0
        assert handler.current_model is None
        assert handler.current_is_drafter is False

    def test_on_llm_start_extracts_model(self):
        """Test on_llm_start extracts model name from invocation params."""
        handler = CascadeFlowCallbackHandler()

        handler.on_llm_start(
            serialized={},
            prompts=["test prompt"],
            invocation_params={"model_name": "gpt-4o-mini"},
            tags=["drafter"],
        )

        assert handler.current_model == "gpt-4o-mini"
        assert handler.current_is_drafter is True

    def test_on_llm_start_detects_drafter_tag(self):
        """Test on_llm_start correctly identifies drafter based on tags."""
        handler = CascadeFlowCallbackHandler()

        handler.on_llm_start(
            serialized={},
            prompts=["test"],
            invocation_params={"model": "gpt-4o-mini"},
            tags=["drafter", "other-tag"],
        )

        assert handler.current_is_drafter is True

    def test_on_llm_start_detects_verifier(self):
        """Test on_llm_start correctly identifies verifier (no drafter tag)."""
        handler = CascadeFlowCallbackHandler()

        handler.on_llm_start(
            serialized={},
            prompts=["test"],
            invocation_params={"model": "gpt-4o"},
            tags=["verifier"],
        )

        assert handler.current_is_drafter is False

    def test_on_llm_new_token_increments_counts(self):
        """Test on_llm_new_token increments token counts."""
        handler = CascadeFlowCallbackHandler()

        handler.on_llm_new_token("Hello")
        handler.on_llm_new_token(" world")
        handler.on_llm_new_token("!")

        assert handler.completion_tokens == 3
        assert handler.total_tokens == 3

    def test_on_llm_end_updates_token_counts(self):
        """Test on_llm_end updates token counts from LLMResult."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "gpt-4o-mini"
        handler.current_is_drafter = True

        # Create mock LLMResult with token usage
        generation = ChatGeneration(message=AIMessage(content="Test response"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "gpt-4o-mini",
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            },
        )

        handler.on_llm_end(llm_result)

        assert handler.prompt_tokens == 10
        assert handler.completion_tokens == 20
        assert handler.total_tokens == 30
        assert handler.successful_requests == 1

    def test_on_llm_end_calculates_drafter_cost(self):
        """Test on_llm_end calculates cost for drafter model."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "gpt-4o-mini"
        handler.current_is_drafter = True

        generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "gpt-4o-mini",
                "token_usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 2000,
                    "total_tokens": 3000,
                },
            },
        )

        handler.on_llm_end(llm_result)

        # gpt-4o-mini: $0.150 per 1M input, $0.600 per 1M output
        expected_cost = (1000 / 1_000_000 * 0.150) + (2000 / 1_000_000 * 0.600)
        assert abs(handler.drafter_cost - expected_cost) < 0.000001
        assert handler.verifier_cost == 0.0
        assert handler.total_cost == handler.drafter_cost

    def test_on_llm_end_calculates_verifier_cost(self):
        """Test on_llm_end calculates cost for verifier model."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "gpt-4o"
        handler.current_is_drafter = False

        generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "gpt-4o",
                "token_usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 1000,
                    "total_tokens": 2000,
                },
            },
        )

        handler.on_llm_end(llm_result)

        # gpt-4o: $2.50 per 1M input, $10.00 per 1M output
        expected_cost = (1000 / 1_000_000 * 2.50) + (1000 / 1_000_000 * 10.00)
        assert abs(handler.verifier_cost - expected_cost) < 0.000001
        assert handler.drafter_cost == 0.0
        assert handler.total_cost == handler.verifier_cost

    def test_on_llm_end_accumulates_costs(self):
        """Test multiple on_llm_end calls accumulate costs correctly."""
        handler = CascadeFlowCallbackHandler()

        # First call - drafter
        handler.current_model = "gpt-4o-mini"
        handler.current_is_drafter = True

        generation1 = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        result1 = LLMResult(
            generations=[[generation1]],
            llm_output={
                "model_name": "gpt-4o-mini",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 200,
                    "total_tokens": 300,
                },
            },
        )
        handler.on_llm_end(result1)

        drafter_cost_1 = handler.drafter_cost

        # Second call - verifier
        handler.current_model = "gpt-4o"
        handler.current_is_drafter = False

        generation2 = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        result2 = LLMResult(
            generations=[[generation2]],
            llm_output={
                "model_name": "gpt-4o",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 100,
                    "total_tokens": 200,
                },
            },
        )
        handler.on_llm_end(result2)

        assert handler.drafter_cost == drafter_cost_1
        assert handler.verifier_cost > 0
        assert handler.total_cost == handler.drafter_cost + handler.verifier_cost
        assert handler.successful_requests == 2

    def test_on_llm_end_extracts_model_from_llm_output(self):
        """Test on_llm_end falls back to llm_output for model name."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = None  # No model set from on_llm_start
        handler.current_is_drafter = False

        generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "gpt-4o",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 100,
                    "total_tokens": 200,
                },
            },
        )

        handler.on_llm_end(llm_result)

        # Should still calculate cost even though model wasn't set in on_llm_start
        assert handler.verifier_cost > 0

    def test_on_llm_end_handles_unknown_model(self):
        """Test on_llm_end handles unknown models gracefully."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "unknown-model-xyz"
        handler.current_is_drafter = True

        generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "unknown-model-xyz",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 100,
                    "total_tokens": 200,
                },
            },
        )

        handler.on_llm_end(llm_result)

        # Should track tokens but not cost for unknown model
        assert handler.total_tokens == 200
        assert handler.total_cost == 0.0
        assert handler.successful_requests == 1

    def test_on_llm_error_does_not_affect_counts(self):
        """Test on_llm_error does not affect token/cost counts."""
        handler = CascadeFlowCallbackHandler()

        # Set some initial values
        handler.total_tokens = 100
        handler.total_cost = 0.01

        # Trigger error
        handler.on_llm_error(Exception("Test error"))

        # Should not change counts
        assert handler.total_tokens == 100
        assert handler.total_cost == 0.01

    def test_repr_format(self):
        """Test __repr__ produces correct output format."""
        handler = CascadeFlowCallbackHandler()
        handler.total_tokens = 3000
        handler.prompt_tokens = 1000
        handler.completion_tokens = 2000
        handler.successful_requests = 2
        handler.drafter_cost = 0.001
        handler.verifier_cost = 0.002
        handler.total_cost = 0.003

        repr_str = repr(handler)

        assert "Tokens Used: 3000" in repr_str
        assert "Prompt Tokens: 1000" in repr_str
        assert "Completion Tokens: 2000" in repr_str
        assert "Successful Requests: 2" in repr_str
        assert "Total Cost (USD): $0.003000" in repr_str
        assert "Drafter Cost: $0.001000" in repr_str
        assert "Verifier Cost: $0.002000" in repr_str


class TestGetCascadeCallback:
    """Test get_cascade_callback context manager."""

    def test_context_manager_returns_handler(self):
        """Test context manager returns a CascadeFlowCallbackHandler."""
        with get_cascade_callback() as cb:
            assert isinstance(cb, CascadeFlowCallbackHandler)
            assert cb.total_tokens == 0
            assert cb.total_cost == 0.0

    def test_context_manager_normal_exit(self):
        """Test context manager exits normally without budget warning."""
        with get_cascade_callback() as cb:
            cb.total_cost = 0.05
        # Should exit cleanly without warnings

    def test_context_manager_budget_warning(self, capsys):
        """Test context manager warns when budget exceeded."""
        with get_cascade_callback(budget=0.01) as cb:
            cb.total_cost = 0.02

        captured = capsys.readouterr()
        assert "Warning: Cost $0.020000 exceeded budget $0.010000" in captured.out

    def test_context_manager_no_budget_warning_when_under(self, capsys):
        """Test context manager does not warn when under budget."""
        with get_cascade_callback(budget=0.10) as cb:
            cb.total_cost = 0.05

        captured = capsys.readouterr()
        assert "Warning" not in captured.out

    def test_context_manager_tracks_usage(self):
        """Test context manager can track usage across operations."""
        with get_cascade_callback() as cb:
            # Simulate drafter call
            cb.current_model = "gpt-4o-mini"
            cb.current_is_drafter = True

            generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
            llm_result = LLMResult(
                generations=[[generation]],
                llm_output={
                    "model_name": "gpt-4o-mini",
                    "token_usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 200,
                        "total_tokens": 300,
                    },
                },
            )
            cb.on_llm_end(llm_result)

            assert cb.total_tokens == 300
            assert cb.drafter_cost > 0
            assert cb.total_cost > 0


class TestCallbackIntegrationWithMocks:
    """Test callback handler integration with mocked LangChain components."""

    def test_callback_receives_all_lifecycle_events(self):
        """Test callback handler receives all LLM lifecycle events."""
        handler = CascadeFlowCallbackHandler()

        # on_llm_start
        handler.on_llm_start(
            serialized={},
            prompts=["test prompt"],
            invocation_params={"model_name": "gpt-4o-mini"},
            tags=["drafter"],
        )
        assert handler.current_model == "gpt-4o-mini"

        # on_llm_new_token (streaming)
        handler.on_llm_new_token("Hello")
        handler.on_llm_new_token(" ")
        handler.on_llm_new_token("world")
        # Streaming adds 3 to completion_tokens and total_tokens
        assert handler.completion_tokens == 3
        assert handler.total_tokens == 3

        # on_llm_end
        generation = ChatGeneration(message=AIMessage(content="Hello world"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "gpt-4o-mini",
                "token_usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
            },
        )
        handler.on_llm_end(llm_result)

        # After on_llm_end, counts include both streaming tokens and metadata tokens
        # prompt_tokens: 5, completion_tokens: 3 (streaming) + 10 (metadata) = 13
        assert handler.prompt_tokens == 5
        assert handler.completion_tokens == 13
        assert handler.total_tokens == 18  # 5 + 13
        assert handler.successful_requests == 1

    def test_streaming_tokens_included_in_total(self):
        """Test streaming tokens are included in total count."""
        handler = CascadeFlowCallbackHandler()

        # Simulate streaming (on_llm_new_token)
        for _ in range(10):
            handler.on_llm_new_token("token")

        # on_llm_end with final counts
        handler.current_model = "gpt-4o-mini"
        generation = ChatGeneration(message=AIMessage(content="Response"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "gpt-4o-mini",
                "token_usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
            },
        )
        handler.on_llm_end(llm_result)

        # Streaming added 10 tokens, on_llm_end adds metadata counts
        # prompt_tokens: 5, completion_tokens: 10 (streaming) + 10 (metadata) = 20
        assert handler.prompt_tokens == 5
        assert handler.completion_tokens == 20  # 10 (streaming) + 10 (metadata)
        assert handler.total_tokens == 25  # 5 + 20

    def test_multiple_model_calls_tracked_separately(self):
        """Test multiple model calls tracked with separate drafter/verifier costs."""
        handler = CascadeFlowCallbackHandler()

        # Drafter call
        handler.current_model = "gpt-4o-mini"
        handler.current_is_drafter = True
        generation1 = ChatGeneration(message=AIMessage(content="Draft"), generation_info={})
        result1 = LLMResult(
            generations=[[generation1]],
            llm_output={
                "model_name": "gpt-4o-mini",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 100,
                    "total_tokens": 200,
                },
            },
        )
        handler.on_llm_end(result1)

        drafter_cost = handler.drafter_cost
        assert drafter_cost > 0
        assert handler.verifier_cost == 0

        # Verifier call
        handler.current_model = "gpt-4o"
        handler.current_is_drafter = False
        generation2 = ChatGeneration(message=AIMessage(content="Verified"), generation_info={})
        result2 = LLMResult(
            generations=[[generation2]],
            llm_output={
                "model_name": "gpt-4o",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 100,
                    "total_tokens": 200,
                },
            },
        )
        handler.on_llm_end(result2)

        assert handler.drafter_cost == drafter_cost  # Unchanged
        assert handler.verifier_cost > 0
        assert handler.total_cost == handler.drafter_cost + handler.verifier_cost


class TestAnthropicModels:
    """Test callback handler with Anthropic models."""

    def test_anthropic_model_cost_calculation(self):
        """Test cost calculation for Anthropic models."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "claude-3-5-sonnet-20241022"
        handler.current_is_drafter = False

        generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "claude-3-5-sonnet-20241022",
                "token_usage": {
                    "input_tokens": 1000,
                    "output_tokens": 1000,
                },
            },
        )

        handler.on_llm_end(llm_result)

        # claude-3-5-sonnet: $3.00 per 1M input, $15.00 per 1M output
        expected_cost = (1000 / 1_000_000 * 3.00) + (1000 / 1_000_000 * 15.00)
        assert abs(handler.total_cost - expected_cost) < 0.000001


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_llm_result(self):
        """Test handler with empty LLMResult."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "gpt-4o-mini"

        llm_result = LLMResult(generations=[], llm_output={})

        # Should not crash
        handler.on_llm_end(llm_result)
        assert handler.successful_requests == 1

    def test_llm_result_without_token_usage(self):
        """Test handler with LLMResult missing token usage."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "gpt-4o-mini"

        generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={"model_name": "gpt-4o-mini"},
            # No token_usage
        )

        handler.on_llm_end(llm_result)

        # Should handle gracefully with 0 tokens
        assert handler.total_tokens == 0
        assert handler.total_cost == 0.0
        assert handler.successful_requests == 1

    def test_llm_result_with_partial_token_usage(self):
        """Test handler with partial token usage data."""
        handler = CascadeFlowCallbackHandler()
        handler.current_model = "gpt-4o-mini"

        generation = ChatGeneration(message=AIMessage(content="Test"), generation_info={})
        llm_result = LLMResult(
            generations=[[generation]],
            llm_output={
                "model_name": "gpt-4o-mini",
                "token_usage": {
                    "prompt_tokens": 100,
                    # Missing completion_tokens
                },
            },
        )

        handler.on_llm_end(llm_result)

        assert handler.prompt_tokens == 100
        assert handler.completion_tokens == 0
