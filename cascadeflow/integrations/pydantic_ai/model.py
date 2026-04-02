"""CascadeFlowModel — full cascade Model for PydanticAI agents.

Implements the PydanticAI ``Model`` abstract base class with speculative
cascade intelligence: a cheap/fast drafter model runs first and its
response is quality-gated before optionally escalating to a more powerful
verifier model.

The cascade flow inside ``request()`` / ``request_stream()``:

    1. Extract query text from the last user message
    2. Pre-route by detected complexity (trivial/simple -> cascade, hard/expert -> verifier)
    3. Check domain policy overrides
    4. Call drafter model
    5. Quality-check the drafter response
    6. Tool-risk check (high-risk tools force verifier)
    7. Accept drafter or escalate to verifier
    8. Record cost/latency/energy on the active HarnessRunContext
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from importlib.util import find_spec
from typing import Any, Optional

from cascadeflow.harness.pricing import estimate_cost

from .config import CascadeFlowPydanticAIConfig
from .harness_bridge import check_budget_gate, record_metrics
from .quality import score_response
from .types import CascadeResult, CostMetadata

logger = logging.getLogger("cascadeflow.integrations.pydantic_ai.model")

# ── PydanticAI Model base class ───────────────────────────────────────
# Use try/except (NOT TYPE_CHECKING) so CascadeFlowModel actually inherits
# from the real Model ABC at runtime when pydantic-ai is installed.  This
# ensures isinstance(model, Model) checks pass in PydanticAI Agent code.

try:
    from pydantic_ai.models import Model as _PydanticAIModel
except ImportError:
    _PydanticAIModel = object  # type: ignore[assignment, misc]

# ── Optional core imports (graceful degradation) ──────────────────────

try:
    from cascadeflow.routing.pre_router import PreRouter

    PRE_ROUTER_AVAILABLE = True
except Exception:
    PRE_ROUTER_AVAILABLE = False

try:
    from cascadeflow.routing.base import RoutingStrategy

    ROUTING_STRATEGY_AVAILABLE = True
except Exception:
    ROUTING_STRATEGY_AVAILABLE = False

try:
    from cascadeflow.routing.tool_risk import get_tool_risk_routing

    TOOL_RISK_AVAILABLE = True
except Exception:
    TOOL_RISK_AVAILABLE = False

try:
    from cascadeflow.quality.complexity import ComplexityDetector

    COMPLEXITY_AVAILABLE = True
except Exception:
    COMPLEXITY_AVAILABLE = False


# ── Helpers ───────────────────────────────────────────────────────────


def _normalize_model_name(name: str) -> str:
    """Strip provider prefix from a model name.

    ``"openai:gpt-4o"`` -> ``"gpt-4o"``
    ``"anthropic/claude-haiku-3.5"`` -> ``"claude-haiku-3.5"``
    ``"gpt-4o-mini"`` -> ``"gpt-4o-mini"``
    """
    if ":" in name:
        return name.split(":", 1)[1]
    if "/" in name:
        return name.split("/", 1)[1]
    return name


def _extract_text_from_parts(parts: Any) -> str:
    """Extract concatenated text content from PydanticAI message parts."""
    if not parts:
        return ""
    texts: list[str] = []
    for part in parts:
        # TextPart has a .content attribute
        content = getattr(part, "content", None)
        if isinstance(content, str):
            texts.append(content)
    return "".join(texts)


def _extract_tool_calls_from_parts(parts: Any) -> list[dict[str, Any]]:
    """Extract tool call dicts from PydanticAI response parts."""
    if not parts:
        return []
    calls: list[dict[str, Any]] = []
    for part in parts:
        tool_name = getattr(part, "tool_name", None)
        if tool_name is not None:
            calls.append(
                {
                    "name": tool_name,
                    "description": getattr(part, "description", ""),
                }
            )
    return calls


def _extract_usage(response: Any) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) from a ModelResponse.

    PydanticAI's ``RequestUsage`` uses ``input_tokens`` / ``output_tokens``.
    We also check the deprecated ``request_tokens`` / ``response_tokens``
    names for backward compatibility with older PydanticAI versions.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    # Prefer PydanticAI's canonical field names
    in_tok = getattr(usage, "input_tokens", None)
    out_tok = getattr(usage, "output_tokens", None)
    # Fallback to deprecated names
    if in_tok is None:
        in_tok = getattr(usage, "request_tokens", 0)
    if out_tok is None:
        out_tok = getattr(usage, "response_tokens", 0)
    return int(in_tok or 0), int(out_tok or 0)


def _extract_query_text(messages: list[Any]) -> str:
    """Extract the user query from the last message in the conversation."""
    if not messages:
        return ""
    last_msg = messages[-1]
    # PydanticAI message types: ModelRequest with parts
    parts = getattr(last_msg, "parts", None)
    if parts:
        return _extract_text_from_parts(parts)
    # Fallback: direct content attribute
    content = getattr(last_msg, "content", None)
    if isinstance(content, str):
        return content
    return ""


def _calculate_savings(drafter_cost: float, verifier_cost_estimate: float) -> float:
    """Calculate savings percentage vs. always using verifier."""
    if verifier_cost_estimate <= 0:
        return 0.0
    return (verifier_cost_estimate - drafter_cost) / verifier_cost_estimate * 100


def _build_cost_metadata(
    *,
    drafter_input: int,
    drafter_output: int,
    drafter_cost: float,
    verifier_input: int,
    verifier_output: int,
    verifier_cost: float,
    accepted: bool,
    drafter_quality: float,
    model_used: str,
) -> CostMetadata:
    """Build a CostMetadata dict from cascade execution data."""
    total_cost = drafter_cost + verifier_cost
    metadata: CostMetadata = {
        "drafter_tokens": {"input": drafter_input, "output": drafter_output},
        "drafter_cost": drafter_cost,
        "verifier_cost": verifier_cost,
        "total_cost": total_cost,
        "savings_percentage": 0.0,
        "model_used": model_used,
        "accepted": accepted,
        "drafter_quality": drafter_quality,
    }
    if verifier_input or verifier_output:
        metadata["verifier_tokens"] = {
            "input": verifier_input,
            "output": verifier_output,
        }
    return metadata


# ── CascadeFlowModel ─────────────────────────────────────────────────


class CascadeFlowModel(_PydanticAIModel):  # type: ignore[misc]
    """PydanticAI Model with full cascade intelligence.

    Wraps a cheap *drafter* and a powerful *verifier* model.  On each
    ``request()`` call the drafter runs first; its response is scored for
    quality and optionally escalated to the verifier when:

    * The quality score falls below the configured threshold
    * A domain policy forces verifier usage
    * The PreRouter classifies the query as hard/expert
    * Tool calls carry high risk

    Usage::

        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIModel
        from cascadeflow.integrations.pydantic_ai import create_cascade_model

        drafter = OpenAIModel("gpt-4o-mini")
        verifier = OpenAIModel("gpt-4o")
        cascade = create_cascade_model(drafter, verifier, quality_threshold=0.7)

        agent = Agent(model=cascade)
        result = await agent.run("What is quantum computing?")
    """

    def __init__(
        self,
        drafter: Any,
        verifier: Any,
        *,
        config: Optional[CascadeFlowPydanticAIConfig] = None,
    ) -> None:
        self._drafter = drafter
        self._verifier = verifier
        self._config = config or CascadeFlowPydanticAIConfig()

        # Pre-router (complexity-based)
        self._pre_router: Optional[Any] = None
        if self._config.enable_pre_router and PRE_ROUTER_AVAILABLE:
            try:
                from cascadeflow.quality.complexity import QueryComplexity

                cascade_qc = [
                    QueryComplexity(c) for c in self._config.cascade_complexities
                ]
                self._pre_router = PreRouter(cascade_complexities=cascade_qc)
            except Exception:
                logger.debug("Failed to initialise PreRouter (non-fatal)")

        # Complexity detector (standalone, for metadata)
        self._complexity_detector: Optional[Any] = None
        if COMPLEXITY_AVAILABLE:
            try:
                self._complexity_detector = ComplexityDetector()
            except Exception:
                pass

        # Last cascade result (accessible via get_last_cascade_result)
        self._last_cascade_result: Optional[CascadeResult] = None

        # Last cost metadata (accessible via get_last_cost_metadata)
        self._last_cost_metadata: Optional[CostMetadata] = None

    # ── Model protocol properties ─────────────────────────────────────

    @property
    def model_name(self) -> str:
        drafter_name = getattr(self._drafter, "model_name", "drafter")
        verifier_name = getattr(self._verifier, "model_name", "verifier")
        return f"cascadeflow:{drafter_name}+{verifier_name}"

    @property
    def system(self) -> str:
        return "cascadeflow"

    # ── Public accessors ──────────────────────────────────────────────

    def get_last_cascade_result(self) -> Optional[CascadeResult]:
        """Return the most recent CascadeResult (or None)."""
        return self._last_cascade_result

    def get_last_cost_metadata(self) -> Optional[CostMetadata]:
        """Return the most recent CostMetadata (or None)."""
        return self._last_cost_metadata

    # ── Resolved model names ──────────────────────────────────────────

    def _drafter_model_name(self) -> str:
        return _normalize_model_name(
            getattr(self._drafter, "model_name", "drafter")
        )

    def _verifier_model_name(self) -> str:
        return _normalize_model_name(
            getattr(self._verifier, "model_name", "verifier")
        )

    # ── request() — full cascade ──────────────────────────────────────

    async def request(
        self,
        messages: list[Any],
        model_settings: Optional[Any] = None,
        model_request_parameters: Optional[Any] = None,
    ) -> Any:
        """Execute the full cascade flow and return a ModelResponse."""
        started_at = time.monotonic()

        # Budget gate
        if self._config.enable_budget_gate:
            check_budget_gate(self.model_name, fail_open=self._config.fail_open)

        # Step 1: extract query text
        query_text = _extract_query_text(messages)

        # Step 2: detect complexity
        complexity: Optional[str] = None
        if self._complexity_detector:
            try:
                detected, _, _ = self._complexity_detector.detect(
                    query_text, return_metadata=True
                )
                complexity = detected.value
            except Exception:
                pass

        # Step 3: pre-route by complexity
        if self._pre_router and ROUTING_STRATEGY_AVAILABLE:
            try:
                decision = await self._pre_router.route(query_text)
                if decision.strategy == RoutingStrategy.DIRECT_BEST:
                    return await self._call_verifier_direct(
                        messages,
                        model_settings,
                        model_request_parameters,
                        query_text=query_text,
                        complexity=complexity,
                        started_at=started_at,
                        reason="pre_router_direct",
                    )
            except Exception:
                if not self._config.fail_open:
                    raise
                logger.debug("PreRouter failed (fail-open), proceeding with cascade")

        # Step 4: check domain policy
        domain = self._resolve_domain(query_text)
        policy = self._get_domain_policy(domain)
        if policy and policy.get("direct_to_verifier"):
            return await self._call_verifier_direct(
                messages,
                model_settings,
                model_request_parameters,
                query_text=query_text,
                complexity=complexity,
                started_at=started_at,
                domain=domain,
                reason="domain_direct_to_verifier",
            )

        # Step 5: call drafter
        drafter_args = self._build_call_args(
            messages, model_settings, model_request_parameters
        )
        drafter_response = await self._drafter.request(**drafter_args)

        drafter_elapsed_ms = (time.monotonic() - started_at) * 1000.0

        # Step 6: quality check
        drafter_text = _extract_text_from_parts(
            getattr(drafter_response, "parts", [])
        )
        try:
            quality = score_response(drafter_text, query_text, complexity)
        except Exception:
            if not self._config.fail_open:
                raise
            logger.debug("Quality scoring failed (fail-open), accepting drafter")
            quality = 1.0  # accept on error

        # Step 7: tool risk check
        force_verifier_tool = False
        tool_calls = _extract_tool_calls_from_parts(
            getattr(drafter_response, "parts", [])
        )
        if tool_calls and TOOL_RISK_AVAILABLE:
            try:
                risk_result = get_tool_risk_routing(tool_calls)
                if risk_result.get("use_verifier"):
                    force_verifier_tool = True
            except Exception:
                logger.debug("Tool risk check failed (non-fatal)")

        # Step 8: accept or escalate
        effective_threshold = self._effective_threshold(domain)
        force_verifier_domain = bool(policy and policy.get("force_verifier"))

        accepted = (
            quality >= effective_threshold
            and not force_verifier_tool
            and not force_verifier_domain
        )

        drafter_input, drafter_output = _extract_usage(drafter_response)
        drafter_model = self._drafter_model_name()
        drafter_cost = estimate_cost(drafter_model, drafter_input, drafter_output)

        if accepted:
            total_elapsed_ms = (time.monotonic() - started_at) * 1000.0

            # Record harness metrics for drafter
            if self._config.enable_cost_tracking:
                record_metrics(
                    drafter_model,
                    drafter_input,
                    drafter_output,
                    total_elapsed_ms,
                    tool_calls_count=len(tool_calls),
                    fail_open=self._config.fail_open,
                )

            # Calculate savings
            verifier_model = self._verifier_model_name()
            verifier_cost_estimate = estimate_cost(
                verifier_model, drafter_input, drafter_output
            )
            savings = _calculate_savings(drafter_cost, verifier_cost_estimate)

            self._last_cascade_result = CascadeResult(
                content=drafter_text,
                model_used="drafter",
                accepted=True,
                drafter_quality=quality,
                drafter_cost=drafter_cost,
                verifier_cost=0.0,
                total_cost=drafter_cost,
                savings_percentage=savings,
                latency_ms=total_elapsed_ms,
                complexity=complexity,
                domain=domain,
            )

            self._last_cost_metadata = _build_cost_metadata(
                drafter_input=drafter_input,
                drafter_output=drafter_output,
                drafter_cost=drafter_cost,
                verifier_input=0,
                verifier_output=0,
                verifier_cost=0.0,
                accepted=True,
                drafter_quality=quality,
                model_used="drafter",
            )
            self._last_cost_metadata["savings_percentage"] = savings

            return drafter_response

        # ── Escalate to verifier ──────────────────────────────────────
        verifier_args = self._build_call_args(
            messages, model_settings, model_request_parameters
        )
        verifier_response = await self._verifier.request(**verifier_args)

        total_elapsed_ms = (time.monotonic() - started_at) * 1000.0

        verifier_input, verifier_output = _extract_usage(verifier_response)
        verifier_model = self._verifier_model_name()
        verifier_cost = estimate_cost(
            verifier_model, verifier_input, verifier_output
        )

        # Record metrics for both models
        if self._config.enable_cost_tracking:
            record_metrics(
                drafter_model,
                drafter_input,
                drafter_output,
                drafter_elapsed_ms,
                tool_calls_count=len(tool_calls),
                fail_open=self._config.fail_open,
            )
            record_metrics(
                verifier_model,
                verifier_input,
                verifier_output,
                total_elapsed_ms - drafter_elapsed_ms,
                tool_calls_count=len(
                    _extract_tool_calls_from_parts(
                        getattr(verifier_response, "parts", [])
                    )
                ),
                fail_open=self._config.fail_open,
            )

        self._last_cascade_result = CascadeResult(
            content=_extract_text_from_parts(
                getattr(verifier_response, "parts", [])
            ),
            model_used="verifier",
            accepted=False,
            drafter_quality=quality,
            drafter_cost=drafter_cost,
            verifier_cost=verifier_cost,
            total_cost=drafter_cost + verifier_cost,
            savings_percentage=0.0,
            latency_ms=total_elapsed_ms,
            complexity=complexity,
            domain=domain,
        )

        self._last_cost_metadata = _build_cost_metadata(
            drafter_input=drafter_input,
            drafter_output=drafter_output,
            drafter_cost=drafter_cost,
            verifier_input=verifier_input,
            verifier_output=verifier_output,
            verifier_cost=verifier_cost,
            accepted=False,
            drafter_quality=quality,
            model_used="verifier",
        )

        return verifier_response

    # ── request_stream() — streaming cascade ──────────────────────────

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[Any],
        model_settings: Optional[Any] = None,
        model_request_parameters: Optional[Any] = None,
    ):
        """Stream the cascade flow.

        Strategy: the drafter stream is consumed first (buffering chunks).
        After the drafter stream completes, a quality/tool-risk check
        determines whether to accept the drafter output or escalate.

        If accepted, the buffered drafter stream wrapper is yielded.
        If escalation is needed, a fresh verifier stream is opened and
        yielded instead — the caller receives only verifier output.

        For direct-to-verifier routes (pre-router hard/expert, domain
        policy), the verifier stream is yielded immediately.
        """
        started_at = time.monotonic()

        if self._config.enable_budget_gate:
            check_budget_gate(self.model_name, fail_open=self._config.fail_open)

        query_text = _extract_query_text(messages)

        complexity: Optional[str] = None
        if self._complexity_detector:
            try:
                detected, _, _ = self._complexity_detector.detect(
                    query_text, return_metadata=True
                )
                complexity = detected.value
            except Exception:
                pass

        # Pre-route: if hard/expert, skip drafter entirely
        skip_drafter = False
        if self._pre_router and ROUTING_STRATEGY_AVAILABLE:
            try:
                decision = await self._pre_router.route(query_text)
                if decision.strategy == RoutingStrategy.DIRECT_BEST:
                    skip_drafter = True
            except Exception:
                if not self._config.fail_open:
                    raise

        domain = self._resolve_domain(query_text)
        policy = self._get_domain_policy(domain)
        if policy and policy.get("direct_to_verifier"):
            skip_drafter = True

        call_args = self._build_call_args(
            messages, model_settings, model_request_parameters
        )

        if skip_drafter:
            # Stream verifier directly
            verifier_model = self._verifier_model_name()
            async with self._verifier.request_stream(**call_args) as stream:
                wrapper = _CascadeFlowStreamedResponse(
                    stream=stream,
                    model_name=verifier_model,
                    started_at=started_at,
                    is_verifier=True,
                    fail_open=self._config.fail_open,
                )
                yield wrapper

            total_elapsed_ms = (time.monotonic() - started_at) * 1000.0
            if self._config.enable_cost_tracking:
                record_metrics(
                    verifier_model,
                    wrapper.tracked_input_tokens,
                    wrapper.tracked_output_tokens,
                    total_elapsed_ms,
                    fail_open=self._config.fail_open,
                    is_stream=True,
                )

            verifier_cost = estimate_cost(
                verifier_model,
                wrapper.tracked_input_tokens,
                wrapper.tracked_output_tokens,
            )
            self._last_cascade_result = CascadeResult(
                content=wrapper.collected_text,
                model_used="verifier",
                accepted=False,
                drafter_quality=0.0,
                drafter_cost=0.0,
                verifier_cost=verifier_cost,
                total_cost=verifier_cost,
                savings_percentage=0.0,
                latency_ms=total_elapsed_ms,
                complexity=complexity,
                domain=domain,
            )
            return

        # ── Cascade path: call drafter non-streaming first to quality-gate ──
        # We use a non-streaming drafter call so we can quality-check
        # before committing to the response stream.  This ensures the
        # caller only sees drafter OR verifier output, never both.
        drafter_response = await self._drafter.request(**call_args)
        drafter_elapsed_ms = (time.monotonic() - started_at) * 1000.0

        drafter_text = _extract_text_from_parts(
            getattr(drafter_response, "parts", [])
        )
        drafter_input, drafter_output = _extract_usage(drafter_response)
        drafter_model = self._drafter_model_name()
        drafter_cost = estimate_cost(drafter_model, drafter_input, drafter_output)

        # Quality check
        try:
            quality = score_response(drafter_text, query_text, complexity)
        except Exception:
            if not self._config.fail_open:
                raise
            quality = 1.0

        # Tool risk check
        force_verifier_tool = False
        tool_calls = _extract_tool_calls_from_parts(
            getattr(drafter_response, "parts", [])
        )
        if tool_calls and TOOL_RISK_AVAILABLE:
            try:
                risk_result = get_tool_risk_routing(tool_calls)
                if risk_result.get("use_verifier"):
                    force_verifier_tool = True
            except Exception:
                logger.debug("Tool risk check failed in stream (non-fatal)")

        effective_threshold = self._effective_threshold(domain)
        force_verifier_domain = bool(policy and policy.get("force_verifier"))

        accepted = (
            quality >= effective_threshold
            and not force_verifier_tool
            and not force_verifier_domain
        )

        if accepted:
            # Yield a wrapper that replays the drafter response as a stream
            wrapper = _ReplayStreamedResponse(
                response=drafter_response,
                text=drafter_text,
                model_name=drafter_model,
            )
            yield wrapper

            total_elapsed_ms = (time.monotonic() - started_at) * 1000.0
            if self._config.enable_cost_tracking:
                record_metrics(
                    drafter_model,
                    drafter_input,
                    drafter_output,
                    total_elapsed_ms,
                    tool_calls_count=len(tool_calls),
                    fail_open=self._config.fail_open,
                    is_stream=True,
                )

            verifier_model = self._verifier_model_name()
            verifier_cost_estimate = estimate_cost(
                verifier_model, drafter_input, drafter_output
            )
            savings = _calculate_savings(drafter_cost, verifier_cost_estimate)

            self._last_cascade_result = CascadeResult(
                content=drafter_text,
                model_used="drafter",
                accepted=True,
                drafter_quality=quality,
                drafter_cost=drafter_cost,
                verifier_cost=0.0,
                total_cost=drafter_cost,
                savings_percentage=savings,
                latency_ms=total_elapsed_ms,
                complexity=complexity,
                domain=domain,
            )

            self._last_cost_metadata = _build_cost_metadata(
                drafter_input=drafter_input,
                drafter_output=drafter_output,
                drafter_cost=drafter_cost,
                verifier_input=0,
                verifier_output=0,
                verifier_cost=0.0,
                accepted=True,
                drafter_quality=quality,
                model_used="drafter",
            )
            self._last_cost_metadata["savings_percentage"] = savings
        else:
            # Escalate: stream verifier
            verifier_model = self._verifier_model_name()
            async with self._verifier.request_stream(**call_args) as stream:
                wrapper = _CascadeFlowStreamedResponse(
                    stream=stream,
                    model_name=verifier_model,
                    started_at=started_at,
                    is_verifier=True,
                    fail_open=self._config.fail_open,
                )
                yield wrapper

            total_elapsed_ms = (time.monotonic() - started_at) * 1000.0

            if self._config.enable_cost_tracking:
                # Record drafter metrics
                record_metrics(
                    drafter_model,
                    drafter_input,
                    drafter_output,
                    drafter_elapsed_ms,
                    tool_calls_count=len(tool_calls),
                    fail_open=self._config.fail_open,
                    is_stream=True,
                )
                # Record verifier metrics
                record_metrics(
                    verifier_model,
                    wrapper.tracked_input_tokens,
                    wrapper.tracked_output_tokens,
                    total_elapsed_ms - drafter_elapsed_ms,
                    fail_open=self._config.fail_open,
                    is_stream=True,
                )

            verifier_cost = estimate_cost(
                verifier_model,
                wrapper.tracked_input_tokens,
                wrapper.tracked_output_tokens,
            )

            self._last_cascade_result = CascadeResult(
                content=wrapper.collected_text,
                model_used="verifier",
                accepted=False,
                drafter_quality=quality,
                drafter_cost=drafter_cost,
                verifier_cost=verifier_cost,
                total_cost=drafter_cost + verifier_cost,
                savings_percentage=0.0,
                latency_ms=total_elapsed_ms,
                complexity=complexity,
                domain=domain,
            )

            self._last_cost_metadata = _build_cost_metadata(
                drafter_input=drafter_input,
                drafter_output=drafter_output,
                drafter_cost=drafter_cost,
                verifier_input=wrapper.tracked_input_tokens,
                verifier_output=wrapper.tracked_output_tokens,
                verifier_cost=verifier_cost,
                accepted=False,
                drafter_quality=quality,
                model_used="verifier",
            )

    # ── Internal helpers ──────────────────────────────────────────────

    async def _call_verifier_direct(
        self,
        messages: list[Any],
        model_settings: Optional[Any],
        model_request_parameters: Optional[Any],
        *,
        query_text: str,
        complexity: Optional[str],
        started_at: float,
        domain: Optional[str] = None,
        reason: str = "direct",
    ) -> Any:
        """Call verifier directly (skipping drafter)."""
        verifier_args = self._build_call_args(
            messages, model_settings, model_request_parameters
        )
        verifier_response = await self._verifier.request(**verifier_args)

        total_elapsed_ms = (time.monotonic() - started_at) * 1000.0
        verifier_input, verifier_output = _extract_usage(verifier_response)
        verifier_model = self._verifier_model_name()
        verifier_cost = estimate_cost(
            verifier_model, verifier_input, verifier_output
        )

        if self._config.enable_cost_tracking:
            record_metrics(
                verifier_model,
                verifier_input,
                verifier_output,
                total_elapsed_ms,
                tool_calls_count=len(
                    _extract_tool_calls_from_parts(
                        getattr(verifier_response, "parts", [])
                    )
                ),
                fail_open=self._config.fail_open,
            )

        self._last_cascade_result = CascadeResult(
            content=_extract_text_from_parts(
                getattr(verifier_response, "parts", [])
            ),
            model_used="verifier",
            accepted=False,
            drafter_quality=0.0,
            drafter_cost=0.0,
            verifier_cost=verifier_cost,
            total_cost=verifier_cost,
            savings_percentage=0.0,
            latency_ms=total_elapsed_ms,
            complexity=complexity,
            domain=domain,
        )

        self._last_cost_metadata = _build_cost_metadata(
            drafter_input=0,
            drafter_output=0,
            drafter_cost=0.0,
            verifier_input=verifier_input,
            verifier_output=verifier_output,
            verifier_cost=verifier_cost,
            accepted=False,
            drafter_quality=0.0,
            model_used="verifier",
        )

        return verifier_response

    @staticmethod
    def _build_call_args(
        messages: list[Any],
        model_settings: Optional[Any],
        model_request_parameters: Optional[Any],
    ) -> dict[str, Any]:
        """Build the kwargs dict for drafter/verifier .request() calls.

        Always passes all three parameters because real PydanticAI Models
        expect all of ``messages``, ``model_settings``, and
        ``model_request_parameters`` as positional arguments.
        """
        return {
            "messages": messages,
            "model_settings": model_settings,
            "model_request_parameters": model_request_parameters,
        }

    def _resolve_domain(self, query_text: str) -> Optional[str]:
        """Detect domain from query text using keyword matching.

        Matches configured domain names as whole words (case-insensitive)
        against the query text.
        """
        if not self._config.domain_policies:
            return None
        lower = query_text.lower()
        for domain_name in self._config.domain_policies:
            if domain_name.lower() in lower:
                return domain_name
        return None

    def _get_domain_policy(self, domain: Optional[str]) -> Optional[dict[str, Any]]:
        """Retrieve the domain policy for a detected domain."""
        if domain is None or not self._config.domain_policies:
            return None
        return self._config.domain_policies.get(domain)

    def _effective_threshold(self, domain: Optional[str] = None) -> float:
        """Return the quality threshold, applying domain override if present."""
        policy = self._get_domain_policy(domain)
        if policy and "quality_threshold" in policy:
            return policy["quality_threshold"]
        return self._config.quality_threshold


# ── Streaming wrappers ────────────────────────────────────────────────


class _CascadeFlowStreamedResponse:
    """Wraps an active PydanticAI StreamedResponse.

    Proxies all attributes to the underlying stream and collects text
    content for post-stream quality evaluation and cost tracking.
    """

    def __init__(
        self,
        *,
        stream: Any,
        model_name: str,
        started_at: float,
        is_verifier: bool,
        fail_open: bool,
    ) -> None:
        self._stream = stream
        self._model_name = model_name
        self._started_at = started_at
        self._is_verifier = is_verifier
        self._fail_open = fail_open
        self.collected_text = ""
        self.tracked_input_tokens = 0
        self.tracked_output_tokens = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self._stream.__anext__()
        # Accumulate text for quality scoring
        if isinstance(chunk, str):
            self.collected_text += chunk
        elif hasattr(chunk, "content") and isinstance(
            getattr(chunk, "content", None), str
        ):
            self.collected_text += chunk.content
        # Track usage if available on the chunk/event
        usage = getattr(chunk, "usage", None)
        if usage is not None:
            in_tok = getattr(usage, "input_tokens", None)
            out_tok = getattr(usage, "output_tokens", None)
            if in_tok is None:
                in_tok = getattr(usage, "request_tokens", 0)
            if out_tok is None:
                out_tok = getattr(usage, "response_tokens", 0)
            self.tracked_input_tokens = int(in_tok or 0)
            self.tracked_output_tokens = int(out_tok or 0)
        return chunk


class _ReplayStreamedResponse:
    """Replays a completed ModelResponse as a single-chunk stream.

    Used when the drafter response has been quality-accepted and we
    need to yield it through the streaming interface.
    """

    def __init__(
        self,
        *,
        response: Any,
        text: str,
        model_name: str,
    ) -> None:
        self._response = response
        self.collected_text = text
        self._model_name = model_name
        self._yielded = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True
        return self.collected_text


# ── Convenience factory ───────────────────────────────────────────────


def create_cascade_model(
    drafter: Any,
    verifier: Any,
    *,
    quality_threshold: float = 0.7,
    enable_pre_router: bool = True,
    cascade_complexities: Optional[list[str]] = None,
    domain_policies: Optional[dict[str, Any]] = None,
    fail_open: bool = True,
    enable_budget_gate: bool = True,
    enable_cost_tracking: bool = True,
) -> CascadeFlowModel:
    """Convenience factory for creating a CascadeFlowModel.

    Args:
        drafter: PydanticAI Model (cheap/fast)
        verifier: PydanticAI Model (powerful/expensive)
        quality_threshold: Quality threshold for accepting drafter responses
        enable_pre_router: Enable complexity-based pre-routing
        cascade_complexities: Which complexity levels should use cascade
        domain_policies: Per-domain policy overrides
        fail_open: If True, integration errors never break the model call
        enable_budget_gate: Enable budget enforcement via harness
        enable_cost_tracking: Enable harness cost/energy/latency recording

    Returns:
        Configured CascadeFlowModel instance
    """
    config = CascadeFlowPydanticAIConfig(
        quality_threshold=quality_threshold,
        enable_pre_router=enable_pre_router,
        cascade_complexities=cascade_complexities or ["trivial", "simple", "moderate"],
        domain_policies=domain_policies,
        fail_open=fail_open,
        enable_budget_gate=enable_budget_gate,
        enable_cost_tracking=enable_cost_tracking,
    )
    return CascadeFlowModel(drafter, verifier, config=config)


__all__ = [
    "CascadeFlowModel",
    "create_cascade_model",
]
