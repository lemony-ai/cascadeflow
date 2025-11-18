"""LangChain-compatible callback handlers for CascadeFlow.

This module provides callback handlers that work with LangChain's standard
callback system, enabling:
- Integration with LangSmith
- Token-level streaming callbacks
- Cost tracking compatible with get_openai_callback() pattern
- Third-party monitoring tool integration
"""

from contextlib import contextmanager
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .utils import calculate_cost, extract_token_usage


class CascadeFlowCallbackHandler(BaseCallbackHandler):
    """LangChain-compatible callback handler for CascadeFlow.

    Tracks costs, tokens, and cascade decisions across both drafter and
    verifier models, making it compatible with LangChain's ecosystem.

    Example:
        >>> from cascadeflow.integrations.langchain import CascadeFlow
        >>> from cascadeflow.integrations.langchain.langchain_callbacks import get_cascade_callback
        >>>
        >>> cascade = CascadeFlow(drafter=drafter, verifier=verifier)
        >>>
        >>> with get_cascade_callback() as cb:
        >>>     response = await cascade.ainvoke("What is Python?")
        >>>     print(f"Cost: ${cb.total_cost}")
        >>>     print(f"Tokens: {cb.total_tokens}")
    """

    def __init__(self):
        """Initialize callback handler with cost/token tracking."""
        super().__init__()

        # Token tracking
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

        # Cost tracking
        self.total_cost = 0.0
        self.drafter_cost = 0.0
        self.verifier_cost = 0.0

        # Cascade tracking
        self.successful_requests = 0
        self.drafter_accepted = 0
        self.escalated_to_verifier = 0

        # Model tracking
        self.current_model: Optional[str] = None
        self.current_is_drafter = False

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Called when LLM starts generating.

        Args:
            serialized: Serialized LLM configuration
            prompts: Input prompts
            **kwargs: Additional metadata (may include 'model', 'tags')
        """
        # Track which model is being called
        invocation_params = kwargs.get("invocation_params", {})
        model_name = invocation_params.get("model_name") or invocation_params.get("model")

        # Store for use in on_llm_end
        self.current_model = model_name

        # Detect if this is drafter or verifier based on tags
        tags = kwargs.get("tags", [])
        self.current_is_drafter = "drafter" in tags or "draft" in str(tags).lower()

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when a new token is generated during streaming.

        Args:
            token: The newly generated token
            **kwargs: Additional metadata
        """
        # Track tokens in real-time during streaming
        self.completion_tokens += 1
        self.total_tokens += 1

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM finishes generating.

        Args:
            response: LLM result with token usage and outputs
            **kwargs: Additional metadata
        """
        # Extract token usage from response
        token_usage = extract_token_usage(response)

        # Update token counts
        self.prompt_tokens += token_usage["input"]
        self.completion_tokens += token_usage["output"]
        self.total_tokens = self.prompt_tokens + self.completion_tokens

        # Try to get model name from llm_output if not set from on_llm_start
        model_name = self.current_model
        if not model_name and response.llm_output:
            model_name = response.llm_output.get("model_name")

        # Calculate cost if we know the model
        if model_name:
            cost = calculate_cost(model_name, token_usage["input"], token_usage["output"])

            # Track drafter vs verifier costs separately
            if self.current_is_drafter:
                self.drafter_cost += cost
            else:
                self.verifier_cost += cost

            self.total_cost = self.drafter_cost + self.verifier_cost

        # Track successful request
        self.successful_requests += 1

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when LLM encounters an error.

        Args:
            error: The exception that occurred
            **kwargs: Additional metadata
        """
        # Errors are tracked but don't affect cost/token counts
        pass

    def __repr__(self) -> str:
        """String representation compatible with get_openai_callback()."""
        return (
            f"Tokens Used: {self.total_tokens}\n"
            f"\tPrompt Tokens: {self.prompt_tokens}\n"
            f"\tCompletion Tokens: {self.completion_tokens}\n"
            f"Successful Requests: {self.successful_requests}\n"
            f"Total Cost (USD): ${self.total_cost:.6f}\n"
            f"\tDrafter Cost: ${self.drafter_cost:.6f}\n"
            f"\tVerifier Cost: ${self.verifier_cost:.6f}"
        )


@contextmanager
def get_cascade_callback(budget: Optional[float] = None):
    """Context manager for tracking cascade costs (compatible with LangChain).

    This provides an API similar to LangChain's get_openai_callback(), making it
    familiar to LangChain users while tracking cascade-specific metrics.

    Args:
        budget: Optional budget limit in USD (not enforced, just for reference)

    Yields:
        CascadeFlowCallbackHandler: Callback handler with cost/token tracking

    Example:
        >>> with get_cascade_callback() as cb:
        >>>     response = await cascade.ainvoke("What is TypeScript?")
        >>>     print(f"Total cost: ${cb.total_cost:.6f}")
        >>>     print(f"Drafter cost: ${cb.drafter_cost:.6f}")
        >>>     print(f"Verifier cost: ${cb.verifier_cost:.6f}")
        >>>     print(f"Savings vs always-verifier: {cb.total_cost < verifier_only_cost}")
    """
    callback = CascadeFlowCallbackHandler()
    try:
        yield callback
    finally:
        # Optionally warn if over budget
        if budget and callback.total_cost > budget:
            print(f"Warning: Cost ${callback.total_cost:.6f} exceeded budget ${budget:.6f}")
