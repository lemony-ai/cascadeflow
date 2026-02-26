"""
OpenAI Agents SDK integration for cascadeflow harness.

This module provides an opt-in ModelProvider implementation that applies
cascadeflow harness decisions (model switching, tool gating, run accounting)
inside OpenAI Agents SDK execution.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from cascadeflow.harness import get_current_run
from cascadeflow.harness.pricing import (
    OPENAI_MODEL_POOL,
)
from cascadeflow.harness.pricing import (
    estimate_cost as _estimate_shared_cost,
)
from cascadeflow.harness.pricing import (
    estimate_energy as _estimate_shared_energy,
)
from cascadeflow.harness.pricing import (
    model_total_price as _shared_model_total_price,
)
from cascadeflow.schema.exceptions import BudgetExceededError

logger = logging.getLogger("cascadeflow.harness.openai_agents")

OPENAI_AGENTS_SDK_AVAILABLE = find_spec("agents") is not None

if TYPE_CHECKING:
    from agents.items import ModelResponse
    from agents.model_settings import ModelSettings
    from agents.models.interface import Model, ModelProvider, ModelTracing
    from agents.tool import Tool
    from openai.types.responses.response_prompt_param import ResponsePromptParam
else:
    Model = object
    ModelProvider = object
    ModelSettings = Any
    ModelTracing = Any
    ModelResponse = Any
    Tool = Any
    ResponsePromptParam = Any


@dataclass
class OpenAIAgentsIntegrationConfig:
    """
    Runtime behavior for the OpenAI Agents integration.

    model_candidates:
        Optional ordered list of candidate models used when harness decides
        to switch models under pressure (for example low remaining budget).
    enable_tool_gating:
        If enabled, removes tools from a model call when the run already
        exceeded tool-call caps in enforce mode.
    fail_open:
        If True, harness-side integration errors never break the agent call.
    """

    model_candidates: Optional[list[str]] = None
    enable_tool_gating: bool = True
    fail_open: bool = True


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    return _estimate_shared_cost(model, input_tokens, output_tokens)


def _estimate_energy(model: str, input_tokens: int, output_tokens: int) -> float:
    return _estimate_shared_energy(model, input_tokens, output_tokens)


def _total_model_price(model: str) -> float:
    return _shared_model_total_price(model)


def _extract_usage_tokens(usage: Any) -> tuple[int, int]:
    if usage is None:
        return 0, 0

    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)

    if input_tokens is None:
        input_tokens = getattr(usage, "prompt_tokens", 0)
    if output_tokens is None:
        output_tokens = getattr(usage, "completion_tokens", 0)

    return int(input_tokens or 0), int(output_tokens or 0)


def _count_tool_calls(output_items: Any) -> int:
    if not output_items:
        return 0

    count = 0
    for item in output_items:
        item_type = None
        if isinstance(item, dict):
            item_type = item.get("type")
        else:
            item_type = getattr(item, "type", None)

        if item_type in {"function_call", "tool_call"}:
            count += 1

    return count


def _safe_record(action: str, reason: str, model: Optional[str]) -> None:
    run = get_current_run()
    if run is None:
        return
    run.record(action=action, reason=reason, model=model)


def _apply_run_metrics(
    *,
    model_name: str,
    response: Any,
    elapsed_ms: float,
    pre_action: str,
    allow_reason: str,
) -> None:
    run = get_current_run()
    if run is None:
        return

    usage = getattr(response, "usage", None) if response is not None else None
    input_tokens, output_tokens = _extract_usage_tokens(usage)
    tool_calls = _count_tool_calls(getattr(response, "output", None)) if response is not None else 0

    run.step_count += 1
    run.latency_used_ms += elapsed_ms
    run.energy_used += _estimate_energy(model_name, input_tokens, output_tokens)
    run.cost += _estimate_cost(model_name, input_tokens, output_tokens)
    run.tool_calls += tool_calls

    if run.budget_max is not None:
        run.budget_remaining = run.budget_max - run.cost

    if pre_action == "deny_tool":
        run.last_action = "deny_tool"
        run.model_used = model_name
    else:
        run.record("allow", allow_reason, model_name)

    if run.mode == "enforce" and run.budget_remaining is not None and run.budget_remaining <= 0:
        logger.info("openai-agents step exhausted budget; next step will be blocked")


class CascadeFlowModelProvider(ModelProvider):  # type: ignore[misc]
    """
    OpenAI Agents SDK ModelProvider with cascadeflow harness awareness.

    Works as an integration layer only. It is opt-in and never enabled by
    default for existing cascadeflow users.
    """

    def __init__(
        self,
        *,
        base_provider: Optional[Any] = None,
        config: Optional[OpenAIAgentsIntegrationConfig] = None,
    ) -> None:
        self._config = config or OpenAIAgentsIntegrationConfig()
        self._base_provider = base_provider or self._create_default_provider()

    def _create_default_provider(self) -> Any:
        if not OPENAI_AGENTS_SDK_AVAILABLE:
            raise ImportError(
                "OpenAI Agents SDK not installed. Install with `pip install cascadeflow[openai-agents]`."
            )

        # Local import keeps this integration optional for users who don't
        # install the extra.
        from agents.models.openai_provider import OpenAIProvider

        return OpenAIProvider()

    def _initial_model_candidate(self, requested_model: Optional[str]) -> str:
        if requested_model:
            return requested_model
        if self._config.model_candidates:
            return self._config.model_candidates[0]
        return "gpt-4o-mini"

    def _resolve_model(self, requested_model: Optional[str]) -> str:
        candidate = self._initial_model_candidate(requested_model)

        run = get_current_run()
        if run is None:
            return candidate
        if run.mode != "enforce":
            return candidate

        if run.budget_remaining is not None and run.budget_remaining <= 0:
            run.record("stop", "budget_exceeded", candidate)
            raise BudgetExceededError(
                "cascadeflow harness budget exceeded",
                remaining=run.budget_remaining,
            )

        if not self._config.model_candidates or run.budget_max is None or run.budget_max <= 0:
            return candidate

        if run.budget_remaining is None:
            return candidate

        # Under budget pressure, switch to the cheapest configured candidate.
        if run.budget_remaining / run.budget_max < 0.2:
            compatible_candidates = [name for name in self._config.model_candidates if name in OPENAI_MODEL_POOL]
            candidates = compatible_candidates or self._config.model_candidates
            cheapest = min(
                candidates,
                key=_total_model_price,
            )
            if cheapest != candidate:
                run.record("switch_model", "budget_pressure", cheapest)
                return cheapest

        return candidate

    def get_model(self, model_name: str | None) -> Model:
        fallback_model = self._initial_model_candidate(model_name)
        selected_model = fallback_model

        try:
            selected_model = self._resolve_model(model_name)
        except BudgetExceededError:
            raise
        except Exception:
            if not self._config.fail_open:
                raise
            logger.exception(
                "openai-agents model resolution failed; falling back to requested model (fail-open)"
            )
            selected_model = fallback_model

        try:
            base_model = self._base_provider.get_model(selected_model)
        except Exception:
            if not self._config.fail_open:
                raise
            logger.exception(
                "openai-agents provider.get_model failed; retrying with fallback model (fail-open)"
            )
            selected_model = fallback_model
            base_model = self._base_provider.get_model(selected_model)

        return _CascadeFlowWrappedModel(
            base_model=base_model,
            model_name=selected_model,
            config=self._config,
        )

    async def aclose(self) -> None:
        close = getattr(self._base_provider, "aclose", None)
        if close is None:
            return
        await close()


class _CascadeFlowWrappedModel(Model):  # type: ignore[misc]
    def __init__(
        self,
        *,
        base_model: Any,
        model_name: str,
        config: OpenAIAgentsIntegrationConfig,
    ) -> None:
        self._base_model = base_model
        self._model_name = model_name
        self._config = config

    def _gate_tools(self, tools: list[Tool]) -> tuple[list[Tool], str]:
        run = get_current_run()
        if run is None:
            return tools, "allow"
        if run.mode != "enforce" or not self._config.enable_tool_gating:
            return tools, "allow"
        if run.tool_calls_max is None:
            return tools, "allow"
        if run.tool_calls < run.tool_calls_max:
            return tools, "allow"
        if not tools:
            return tools, "allow"

        run.record("deny_tool", "max_tool_calls_reached", self._model_name)
        return [], "deny_tool"

    def _update_run_metrics(
        self,
        *,
        response: Any,
        elapsed_ms: float,
        pre_action: str,
    ) -> None:
        _apply_run_metrics(
            model_name=self._model_name,
            response=response,
            elapsed_ms=elapsed_ms,
            pre_action=pre_action,
            allow_reason="openai_agents_step",
        )

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],  # noqa: A002 - required by OpenAI Agents SDK Model interface
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Any | None,
        handoffs: list[Any],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> ModelResponse:
        gated_tools, pre_action = self._gate_tools(tools)
        started_at = time.monotonic()

        response = await self._base_model.get_response(
            system_instructions=system_instructions,
            input=input,
            model_settings=model_settings,
            tools=gated_tools,
            output_schema=output_schema,
            handoffs=handoffs,
            tracing=tracing,
            previous_response_id=previous_response_id,
            conversation_id=conversation_id,
            prompt=prompt,
        )

        elapsed_ms = (time.monotonic() - started_at) * 1000.0

        try:
            self._update_run_metrics(response=response, elapsed_ms=elapsed_ms, pre_action=pre_action)
        except Exception:
            if self._config.fail_open:
                logger.exception("openai-agents harness metric update failed (fail-open)")
            else:
                raise

        return response

    def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],  # noqa: A002 - required by OpenAI Agents SDK Model interface
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Any | None,
        handoffs: list[Any],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> AsyncIterator[Any]:
        gated_tools, pre_action = self._gate_tools(tools)
        started_at = time.monotonic()

        stream = self._base_model.stream_response(
            system_instructions=system_instructions,
            input=input,
            model_settings=model_settings,
            tools=gated_tools,
            output_schema=output_schema,
            handoffs=handoffs,
            tracing=tracing,
            previous_response_id=previous_response_id,
            conversation_id=conversation_id,
            prompt=prompt,
        )
        return _CascadeFlowStreamWrapper(
            stream=stream,
            model_name=self._model_name,
            started_at=started_at,
            pre_action=pre_action,
            fail_open=self._config.fail_open,
        )


class _CascadeFlowStreamWrapper:
    def __init__(
        self,
        *,
        stream: AsyncIterator[Any],
        model_name: str,
        started_at: float,
        pre_action: str,
        fail_open: bool,
    ) -> None:
        self._stream = stream
        self._model_name = model_name
        self._started_at = started_at
        self._pre_action = pre_action
        self._fail_open = fail_open
        self._finalized = False
        self._last_response = None

    def __aiter__(self) -> _CascadeFlowStreamWrapper:
        return self

    async def __anext__(self) -> Any:
        try:
            event = await self._stream.__anext__()
        except StopAsyncIteration:
            await self._finalize()
            raise

        response = getattr(event, "response", None)
        if response is not None:
            self._last_response = response
        return event

    async def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True

        run = get_current_run()
        if run is None:
            return

        elapsed_ms = (time.monotonic() - self._started_at) * 1000.0
        response = self._last_response

        try:
            _apply_run_metrics(
                model_name=self._model_name,
                response=response,
                elapsed_ms=elapsed_ms,
                pre_action=self._pre_action,
                allow_reason="openai_agents_stream_step",
            )
        except Exception:
            if self._fail_open:
                logger.exception("openai-agents stream metric update failed (fail-open)")
                return
            raise


def create_openai_agents_provider(
    *,
    model_candidates: Optional[list[str]] = None,
    enable_tool_gating: bool = True,
    fail_open: bool = True,
) -> CascadeFlowModelProvider:
    """
    Convenience factory for OpenAI Agents SDK integration.
    """

    return CascadeFlowModelProvider(
        config=OpenAIAgentsIntegrationConfig(
            model_candidates=model_candidates,
            enable_tool_gating=enable_tool_gating,
            fail_open=fail_open,
        )
    )


def is_openai_agents_sdk_available() -> bool:
    return OPENAI_AGENTS_SDK_AVAILABLE


__all__ = [
    "OPENAI_AGENTS_SDK_AVAILABLE",
    "OpenAIAgentsIntegrationConfig",
    "CascadeFlowModelProvider",
    "create_openai_agents_provider",
    "is_openai_agents_sdk_available",
]
