"""Google ADK (Agent Development Kit) harness integration for cascadeflow.

Uses ADK's ``BasePlugin`` system to intercept all LLM calls across all agents
in a Runner, feeding metrics into ``cascadeflow.harness`` run contexts.

This module is optional — ``pip install cascadeflow[google-adk]`` pulls in the
google-adk dependency.  When google-adk is not installed the public helpers
return gracefully and ``GOOGLE_ADK_AVAILABLE`` is ``False``.

Integration surface:
    - ``enable()``:  create and return a plugin instance
    - ``disable()``: deactivate the plugin and clean up
    - ``CascadeFlowADKPlugin``: BasePlugin subclass for Runner(plugins=[...])

Unlike CrewAI (global hooks), ADK plugins are registered per-Runner.
``enable()`` returns the plugin instance; the user passes it to
``Runner(plugins=[plugin])``.

Design note — no tool gating:
    ADK's ``tools_dict`` is part of agent definition, not per-call.
    Budget gate via ``before_model_callback`` provides sufficient cost control.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any, Optional

from cascadeflow.harness.api import get_current_run
from cascadeflow.harness.pricing import estimate_cost, estimate_energy

logger = logging.getLogger("cascadeflow.integrations.google_adk")

GOOGLE_ADK_AVAILABLE = find_spec("google.adk") is not None

# Resolve the base class: use ADK's BasePlugin when available, else object.
_ADKBasePlugin: type
if GOOGLE_ADK_AVAILABLE:
    try:
        from google.adk.plugins import BasePlugin as _ADKBasePlugin  # type: ignore[assignment]
    except ImportError:
        _ADKBasePlugin = object  # type: ignore[assignment,misc]
        GOOGLE_ADK_AVAILABLE = False
else:
    _ADKBasePlugin = object  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class GoogleADKHarnessConfig:
    """Runtime configuration for the Google ADK harness integration.

    fail_open:
        If ``True`` (default), errors inside callbacks never break ADK
        execution — they are logged and swallowed.
    enable_budget_gate:
        If ``True`` (default), ``before_model_callback`` blocks calls when
        the harness run budget is exhausted (enforce mode only).
    """

    fail_open: bool = True
    enable_budget_gate: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_model_name(model: str) -> str:
    """Strip LiteLlm-style provider prefix (``openai/gpt-4o`` → ``gpt-4o``).

    Also handles ``models/gemini-2.5-flash`` → ``gemini-2.5-flash``.
    """
    if "/" in model:
        return model.rsplit("/", 1)[-1]
    return model


def _count_function_calls(content: Any) -> int:
    """Count ``function_call`` parts in an ADK LlmResponse content."""
    if content is None:
        return 0
    parts = getattr(content, "parts", None)
    if not parts:
        return 0
    count = 0
    for part in parts:
        if getattr(part, "function_call", None) is not None:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class CascadeFlowADKPlugin(_ADKBasePlugin):  # type: ignore[misc]
    """Google ADK BasePlugin with cascadeflow harness awareness.

    Intercepts every LLM call across all agents in a Runner to provide:
    - Budget enforcement (enforce mode: short-circuits with error response)
    - Cost, latency, and energy tracking
    - Tool call counting
    - Full trace recording into HarnessRunContext
    """

    def __init__(self, config: Optional[GoogleADKHarnessConfig] = None) -> None:
        # google-adk BasePlugin requires a stable plugin name.
        try:
            super().__init__(name="cascadeflow_harness")
        except TypeError:
            # Fallback for local test environments where BasePlugin is ``object``.
            super().__init__()
            self.name = "cascadeflow_harness"
        self._config = config or GoogleADKHarnessConfig()
        self._active = True
        self._call_seq: int = 0
        # Track call metadata between before/after callbacks.
        # Keyed by id(callback_context) to guarantee uniqueness even when
        # two concurrent calls share (invocation_id, agent_name).
        self._call_start_times: dict[int, float] = {}
        self._call_models: dict[int, str] = {}
        # Fallback mapping for runtimes that provide distinct callback_context
        # objects between before/after callbacks.
        self._call_fallback_keys: dict[tuple[str, str], list[int]] = {}

    @staticmethod
    def _callback_key(callback_context: Any) -> int:
        """Return a unique key for a callback_context object.

        Uses ``id()`` which is guaranteed unique for the lifetime of the
        object — ADK keeps the same CallbackContext alive across the
        before/after/error callback sequence for a single LLM call.
        """
        return id(callback_context)

    @staticmethod
    def _fallback_key(callback_context: Any) -> tuple[str, str]:
        """Return a stable fallback key for correlation across callbacks."""
        invocation_id = str(getattr(callback_context, "invocation_id", "") or "")
        agent_name = str(getattr(callback_context, "agent_name", "") or "")
        return (invocation_id, agent_name)

    def _track_call_key(self, callback_context: Any, key: int) -> None:
        """Register key in fallback queue for cross-object callback matching."""
        fallback_key = self._fallback_key(callback_context)
        if not fallback_key[0] and not fallback_key[1]:
            return
        self._call_fallback_keys.setdefault(fallback_key, []).append(key)

    def _resolve_call_key(self, callback_context: Any) -> int | None:
        """Resolve stored key for callback context across runtime variants."""
        key = self._callback_key(callback_context)
        if key in self._call_models or key in self._call_start_times:
            return key

        fallback_key = self._fallback_key(callback_context)
        keys = self._call_fallback_keys.get(fallback_key)
        if not keys:
            return None

        resolved = keys.pop(0)
        if not keys:
            self._call_fallback_keys.pop(fallback_key, None)
        return resolved

    async def before_model_callback(
        self,
        callback_context: Any,
        llm_request: Any,
    ) -> Any:
        """Budget gate and timing setup.

        Returns ``None`` to proceed normally, or an ``LlmResponse`` with
        an error to short-circuit the call when budget is exhausted.
        """
        if not self._active:
            return None

        try:
            ctx = get_current_run()
            if ctx is None:
                return None
            if ctx.mode == "off":
                return None

            # Extract model name from request
            model_raw = getattr(llm_request, "model", None) or "unknown"
            model = _normalize_model_name(str(model_raw))

            key = self._callback_key(callback_context)

            # Budget gate in enforce mode
            if (
                self._config.enable_budget_gate
                and ctx.mode == "enforce"
                and ctx.budget_max is not None
                and ctx.cost >= ctx.budget_max
            ):
                logger.warning(
                    "google-adk: blocking LLM call — budget exhausted "
                    "(spent $%.4f of $%.4f max)",
                    ctx.cost,
                    ctx.budget_max,
                )
                ctx.record(action="stop", reason="budget_exhausted", model=model)
                return self._make_budget_error_response(ctx)

            # Record start time and model for after_model_callback
            self._call_start_times[key] = time.monotonic()
            self._call_models[key] = model
            self._track_call_key(callback_context, key)

            return None
        except Exception:
            if self._config.fail_open:
                logger.debug("google-adk before_model_callback error (fail_open)", exc_info=True)
                return None
            raise

    async def after_model_callback(
        self,
        callback_context: Any,
        llm_response: Any,
    ) -> Any:
        """Extract tokens, count tool calls, estimate cost/energy, update run context."""
        if not self._active:
            return None

        try:
            ctx = get_current_run()
            if ctx is None:
                return None
            if ctx.mode == "off":
                return None

            key = self._resolve_call_key(callback_context)

            # Recover model name stored during before_model_callback
            model = self._call_models.pop(key, "unknown") if key is not None else "unknown"

            # Extract token counts from usage_metadata
            input_tokens, output_tokens = self._extract_tokens(llm_response)

            # Count function_call parts in response content
            content = getattr(llm_response, "content", None)
            tool_calls = _count_function_calls(content)

            # Cost and energy estimation
            cost = estimate_cost(model, input_tokens, output_tokens)
            energy = estimate_energy(model, input_tokens, output_tokens)

            # Latency
            start_time = self._call_start_times.pop(key, None) if key is not None else None
            elapsed_ms = (time.monotonic() - start_time) * 1000 if start_time else 0.0

            # Update run context
            ctx.cost += cost
            ctx.step_count += 1
            ctx.latency_used_ms += elapsed_ms
            ctx.energy_used += energy
            ctx.tool_calls += tool_calls

            if ctx.budget_max is not None:
                ctx.budget_remaining = ctx.budget_max - ctx.cost

            ctx.model_used = model
            ctx.record(action="allow", reason=ctx.mode, model=model)

            logger.debug(
                "google-adk: tracked call model=%s cost=$%.6f latency=%.0fms tools=%d",
                model,
                cost,
                elapsed_ms,
                tool_calls,
            )

            return None
        except Exception:
            if self._config.fail_open:
                logger.debug("google-adk after_model_callback error (fail_open)", exc_info=True)
                return None
            raise

    async def on_model_error_callback(
        self,
        callback_context: Any,
        llm_request: Any = None,
        error: Exception | None = None,
    ) -> Any:
        """Record error in trace and clean up timing state."""
        if not self._active:
            return None

        try:
            # Backward-compatible calling form used in existing tests:
            # on_model_error_callback(callback_context, error)
            if error is None and isinstance(llm_request, Exception):
                error = llm_request

            key = self._resolve_call_key(callback_context)
            model = self._call_models.pop(key, "unknown") if key is not None else "unknown"
            if key is not None:
                self._call_start_times.pop(key, None)

            ctx = get_current_run()
            if ctx is not None and error is not None:
                error_type = type(error).__name__
                ctx.record(
                    action="error",
                    reason=f"model_error:{error_type}",
                    model=model,
                )

            return None
        except Exception:
            if self._config.fail_open:
                logger.debug("google-adk on_model_error_callback error (fail_open)", exc_info=True)
                return None
            raise

    def deactivate(self) -> None:
        """Make all callbacks no-ops without unregistering from Runner."""
        self._active = False
        self._call_seq = 0
        self._call_start_times.clear()
        self._call_models.clear()
        self._call_fallback_keys.clear()

    @staticmethod
    def _extract_tokens(llm_response: Any) -> tuple[int, int]:
        """Extract input/output token counts from an ADK LlmResponse.

        ADK responses carry ``usage_metadata`` with ``prompt_token_count``
        and ``candidates_token_count``.  Falls back to estimating from
        content text (4 chars ≈ 1 token).
        """
        usage = getattr(llm_response, "usage_metadata", None)
        if usage is not None:
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0
            if input_tokens > 0 or output_tokens > 0:
                return int(input_tokens), int(output_tokens)

        # Fallback: estimate from content text
        content = getattr(llm_response, "content", None)
        if content is not None:
            parts = getattr(content, "parts", None)
            if parts:
                text_chars = sum(len(getattr(p, "text", "") or "") for p in parts)
                return 0, max(text_chars // 4, 1)

        return 0, 0

    @staticmethod
    def _make_budget_error_response(ctx: Any) -> Any:
        """Build an LlmResponse that short-circuits the LLM call.

        When ADK is available we return a real ``LlmResponse``.  When not
        (shouldn't happen in practice), we return a sentinel dict.

        The user-facing message is intentionally generic to avoid leaking
        internal spend/limit numbers.  Exact figures are logged separately.
        """
        # Generic message safe for end-user exposure.
        msg = "cascadeflow harness budget exceeded"
        # Detailed figures for operators only.
        logger.warning(
            "google-adk: budget exceeded — spent $%.4f of $%.4f max",
            ctx.cost,
            ctx.budget_max,
        )
        if GOOGLE_ADK_AVAILABLE:
            try:
                from google.adk.models import LlmResponse  # type: ignore[import-untyped]
                from google.genai.types import Content, Part  # type: ignore[import-untyped]

                return LlmResponse(
                    content=Content(parts=[Part(text=msg)]),
                    error_code="BUDGET_EXCEEDED",
                    error_message=msg,
                )
            except ImportError:
                pass

        return {"error_code": "BUDGET_EXCEEDED", "error_message": msg}


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_config: GoogleADKHarnessConfig = GoogleADKHarnessConfig()
_plugin_instance: Optional[CascadeFlowADKPlugin] = None
_enabled: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Return whether the google-adk package is installed."""
    return GOOGLE_ADK_AVAILABLE


def is_enabled() -> bool:
    """Return whether a plugin instance has been created via ``enable()``."""
    return _enabled


def get_config() -> GoogleADKHarnessConfig:
    """Return a copy of the current configuration."""
    return GoogleADKHarnessConfig(
        fail_open=_config.fail_open,
        enable_budget_gate=_config.enable_budget_gate,
    )


def enable(
    config: Optional[GoogleADKHarnessConfig] = None,
) -> CascadeFlowADKPlugin:
    """Create a cascadeflow-instrumented ADK plugin instance.

    Unlike CrewAI (global hooks), ADK plugins are per-Runner.  Pass the
    returned plugin to ``Runner(plugins=[plugin])``.

    Idempotent: returns the same instance on repeated calls unless
    ``disable()`` was called in between.

    Args:
        config: Optional configuration overrides.

    Returns:
        ``CascadeFlowADKPlugin`` instance ready for ``Runner(plugins=[...])``.
    """
    global _config, _plugin_instance, _enabled

    if _enabled and _plugin_instance is not None:
        logger.debug("google-adk plugin already enabled; returning existing instance")
        return _plugin_instance

    if config is not None:
        _config = config

    _plugin_instance = CascadeFlowADKPlugin(config=_config)
    _enabled = True
    logger.info("google-adk harness plugin created")
    return _plugin_instance


def disable() -> None:
    """Deactivate the plugin and clear module state.

    Safe to call even if not enabled.
    """
    global _plugin_instance, _enabled

    if _plugin_instance is not None:
        _plugin_instance.deactivate()

    _plugin_instance = None
    _enabled = False
    logger.info("google-adk harness plugin disabled")


__all__ = [
    "GOOGLE_ADK_AVAILABLE",
    "GoogleADKHarnessConfig",
    "CascadeFlowADKPlugin",
    "enable",
    "disable",
    "is_available",
    "is_enabled",
    "get_config",
]
