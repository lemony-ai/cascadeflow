from __future__ import annotations

import inspect
import json
import logging
import os
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable, Literal, Optional, TypeVar, cast
from uuid import uuid4

logger = logging.getLogger("cascadeflow.harness")

HarnessMode = Literal["off", "observe", "enforce"]


@dataclass
class HarnessConfig:
    mode: HarnessMode = "off"
    verbose: bool = False
    budget: Optional[float] = None
    max_tool_calls: Optional[int] = None
    max_latency_ms: Optional[float] = None
    max_energy: Optional[float] = None
    kpi_targets: Optional[dict[str, float]] = None
    kpi_weights: Optional[dict[str, float]] = None
    compliance: Optional[str] = None


@dataclass
class HarnessInitReport:
    mode: HarnessMode
    instrumented: list[str]
    detected_but_not_instrumented: list[str]
    config_sources: dict[str, str]


@dataclass
class HarnessRunContext:
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    started_at_ms: float = field(default_factory=lambda: time.time() * 1000)
    ended_at_ms: Optional[float] = None
    mode: HarnessMode = "off"
    budget_max: Optional[float] = None
    tool_calls_max: Optional[int] = None
    latency_max_ms: Optional[float] = None
    energy_max: Optional[float] = None
    kpi_targets: Optional[dict[str, float]] = None
    kpi_weights: Optional[dict[str, float]] = None
    compliance: Optional[str] = None

    cost: float = 0.0
    savings: float = 0.0
    tool_calls: int = 0
    step_count: int = 0
    latency_used_ms: float = 0.0
    energy_used: float = 0.0
    budget_remaining: Optional[float] = None
    model_used: Optional[str] = None
    last_action: str = "allow"
    draft_accepted: Optional[bool] = None
    _trace: list[dict[str, Any]] = field(default_factory=list)
    _token: Optional[Token[Optional[HarnessRunContext]]] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.budget_max is not None and self.budget_remaining is None:
            self.budget_remaining = self.budget_max

    def __enter__(self) -> HarnessRunContext:
        self._token = _current_run.set(self)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.ended_at_ms = time.time() * 1000
        self._log_summary()
        if self._token is not None:
            _current_run.reset(self._token)
            self._token = None

    async def __aenter__(self) -> HarnessRunContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.__exit__(exc_type, exc, tb)

    def trace(self) -> list[dict[str, Any]]:
        return list(self._trace)

    def summary(self) -> dict[str, Any]:
        duration_ms: Optional[float] = None
        if self.ended_at_ms is not None:
            duration_ms = max(0.0, self.ended_at_ms - self.started_at_ms)
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "step_count": self.step_count,
            "tool_calls": self.tool_calls,
            "cost": self.cost,
            "savings": self.savings,
            "latency_used_ms": self.latency_used_ms,
            "energy_used": self.energy_used,
            "budget_max": self.budget_max,
            "budget_remaining": self.budget_remaining,
            "last_action": self.last_action,
            "model_used": self.model_used,
            "duration_ms": duration_ms,
        }

    def _log_summary(self) -> None:
        if self.mode == "off" or self.step_count <= 0:
            return
        logger.info(
            (
                "harness run summary run_id=%s mode=%s steps=%d tool_calls=%d "
                "cost=%.6f latency_ms=%.2f energy=%.4f last_action=%s model=%s "
                "budget_remaining=%s"
            ),
            self.run_id,
            self.mode,
            self.step_count,
            self.tool_calls,
            self.cost,
            self.latency_used_ms,
            self.energy_used,
            self.last_action,
            self.model_used,
            self.budget_remaining,
        )

    def record(
        self,
        action: str,
        reason: str,
        model: Optional[str] = None,
        *,
        applied: Optional[bool] = None,
        decision_mode: Optional[str] = None,
    ) -> None:
        safe_action = _sanitize_trace_value(action, max_length=64) or "allow"
        safe_reason = _sanitize_trace_value(reason, max_length=160) or "unspecified"
        safe_model = _sanitize_trace_value(model, max_length=128) if model is not None else None

        self.last_action = safe_action
        self.model_used = safe_model
        entry: dict[str, Any] = {
            "action": safe_action,
            "reason": safe_reason,
            "model": safe_model,
            "run_id": self.run_id,
            "mode": self.mode,
            "step": self.step_count,
            "timestamp_ms": time.time() * 1000,
            "tool_calls_total": self.tool_calls,
            "cost_total": self.cost,
            "latency_used_ms": self.latency_used_ms,
            "energy_used": self.energy_used,
            "budget_state": {
                "max": self.budget_max,
                "remaining": self.budget_remaining,
            },
        }
        if applied is not None:
            entry["applied"] = applied
        if decision_mode is not None:
            entry["decision_mode"] = decision_mode
        self._trace.append(entry)
        _emit_harness_decision(entry)


_harness_config: HarnessConfig = HarnessConfig()
_current_run: ContextVar[Optional[HarnessRunContext]] = ContextVar("cascadeflow_harness_run", default=None)
_is_instrumented: bool = False
_harness_callback_manager: Any = None
_UNSET = object()


def _validate_mode(mode: str) -> HarnessMode:
    if mode not in {"off", "observe", "enforce"}:
        raise ValueError("mode must be one of: off, observe, enforce")
    return cast(HarnessMode, mode)


def _detect_sdks() -> dict[str, bool]:
    return {
        "openai": find_spec("openai") is not None,
        "anthropic": find_spec("anthropic") is not None,
    }


def get_harness_config() -> HarnessConfig:
    return HarnessConfig(**_harness_config.__dict__)


def get_current_run() -> Optional[HarnessRunContext]:
    return _current_run.get()


def get_harness_callback_manager() -> Any:
    return _harness_callback_manager


def set_harness_callback_manager(callback_manager: Any) -> None:
    global _harness_callback_manager
    _harness_callback_manager = callback_manager


def reset() -> None:
    """
    Reset harness global state and unpatch instrumented clients.

    Intended for tests and controlled shutdown paths.
    """

    global _harness_config
    global _is_instrumented
    global _harness_callback_manager

    from cascadeflow.harness.instrument import unpatch_openai

    unpatch_openai()
    _harness_config = HarnessConfig()
    _is_instrumented = False
    _harness_callback_manager = None
    _current_run.set(None)


def _sanitize_trace_value(value: Any, *, max_length: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    return text


def _emit_harness_decision(entry: dict[str, Any]) -> None:
    manager = get_harness_callback_manager()
    if manager is None:
        return

    trigger = getattr(manager, "trigger", None)
    if not callable(trigger):
        logger.debug("harness callback manager has no trigger() method")
        return

    try:
        from cascadeflow.telemetry.callbacks import CallbackEvent
    except Exception:
        logger.debug("telemetry callbacks unavailable for harness decision emit", exc_info=True)
        return

    try:
        trigger(
            CallbackEvent.CASCADE_DECISION,
            query="[harness]",
            data=dict(entry),
            workflow="harness",
        )
    except Exception:
        logger.debug("failed to emit harness decision callback", exc_info=True)


def _parse_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _parse_float(raw: str) -> float:
    return float(raw.strip())


def _parse_int(raw: str) -> int:
    return int(raw.strip())


def _parse_json_dict(raw: str) -> dict[str, float]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    parsed: dict[str, float] = {}
    for key, item in value.items():
        parsed[str(key)] = float(item)
    return parsed


def _read_env_config() -> dict[str, Any]:
    env_config: dict[str, Any] = {}

    mode = os.getenv("CASCADEFLOW_HARNESS_MODE") or os.getenv("CASCADEFLOW_MODE")
    if mode:
        env_config["mode"] = mode

    verbose = os.getenv("CASCADEFLOW_HARNESS_VERBOSE")
    if verbose is not None:
        env_config["verbose"] = _parse_bool(verbose)

    budget = os.getenv("CASCADEFLOW_HARNESS_BUDGET") or os.getenv("CASCADEFLOW_BUDGET")
    if budget is not None:
        env_config["budget"] = _parse_float(budget)

    max_tool_calls = os.getenv("CASCADEFLOW_HARNESS_MAX_TOOL_CALLS")
    if max_tool_calls is not None:
        env_config["max_tool_calls"] = _parse_int(max_tool_calls)

    max_latency_ms = os.getenv("CASCADEFLOW_HARNESS_MAX_LATENCY_MS")
    if max_latency_ms is not None:
        env_config["max_latency_ms"] = _parse_float(max_latency_ms)

    max_energy = os.getenv("CASCADEFLOW_HARNESS_MAX_ENERGY")
    if max_energy is not None:
        env_config["max_energy"] = _parse_float(max_energy)

    compliance = os.getenv("CASCADEFLOW_HARNESS_COMPLIANCE")
    if compliance is not None:
        env_config["compliance"] = compliance

    kpi_targets = os.getenv("CASCADEFLOW_HARNESS_KPI_TARGETS")
    if kpi_targets is not None:
        env_config["kpi_targets"] = _parse_json_dict(kpi_targets)

    kpi_weights = os.getenv("CASCADEFLOW_HARNESS_KPI_WEIGHTS")
    if kpi_weights is not None:
        env_config["kpi_weights"] = _parse_json_dict(kpi_weights)

    return env_config


def _read_file_config() -> tuple[dict[str, Any], Optional[str]]:
    """
    Read harness config from CASCADEFLOW_CONFIG path or default config discovery.
    """

    config_path: Optional[str] = os.getenv("CASCADEFLOW_CONFIG")
    loaded_path: Optional[str] = None

    try:
        from cascadeflow.config_loader import find_config, load_config
    except Exception:
        logger.debug("config_loader unavailable while reading harness config", exc_info=True)
        return {}, None

    try:
        if config_path:
            loaded_path = str(Path(config_path))
            raw = load_config(config_path)
        else:
            discovered = find_config()
            if not discovered:
                return {}, None
            loaded_path = str(discovered)
            raw = load_config(discovered)
    except Exception:
        logger.warning("failed to load harness config file", exc_info=True)
        return {}, None

    if not isinstance(raw, dict):
        return {}, loaded_path

    harness_block = raw.get("harness")
    if isinstance(harness_block, dict):
        return dict(harness_block), loaded_path

    # Fallback: allow top-level harness keys.
    keys = {
        "mode",
        "verbose",
        "budget",
        "max_tool_calls",
        "max_latency_ms",
        "max_energy",
        "kpi_targets",
        "kpi_weights",
        "compliance",
    }
    fallback = {k: v for k, v in raw.items() if k in keys}
    return fallback, loaded_path


def _resolve_value(
    name: str,
    explicit: Any,
    env_config: dict[str, Any],
    file_config: dict[str, Any],
    default: Any,
    sources: dict[str, str],
) -> Any:
    if explicit is not _UNSET:
        sources[name] = "code"
        return explicit
    if name in env_config:
        sources[name] = "env"
        return env_config[name]
    if name in file_config:
        sources[name] = "file"
        return file_config[name]
    sources[name] = "default"
    return default


def init(
    *,
    mode: HarnessMode | object = _UNSET,
    verbose: bool | object = _UNSET,
    budget: Optional[float] | object = _UNSET,
    max_tool_calls: Optional[int] | object = _UNSET,
    max_latency_ms: Optional[float] | object = _UNSET,
    max_energy: Optional[float] | object = _UNSET,
    kpi_targets: Optional[dict[str, float]] | object = _UNSET,
    kpi_weights: Optional[dict[str, float]] | object = _UNSET,
    compliance: Optional[str] | object = _UNSET,
    callback_manager: Any | object = _UNSET,
) -> HarnessInitReport:
    """
    Initialize global harness settings and instrument detected SDK clients.
    """

    global _harness_config
    global _is_instrumented

    env_config = _read_env_config()
    file_config, file_path = _read_file_config()
    sources: dict[str, str] = {}

    resolved_mode = _resolve_value("mode", mode, env_config, file_config, "off", sources)
    resolved_verbose = _resolve_value("verbose", verbose, env_config, file_config, False, sources)
    resolved_budget = _resolve_value("budget", budget, env_config, file_config, None, sources)
    resolved_max_tool_calls = _resolve_value(
        "max_tool_calls", max_tool_calls, env_config, file_config, None, sources
    )
    resolved_max_latency_ms = _resolve_value(
        "max_latency_ms", max_latency_ms, env_config, file_config, None, sources
    )
    resolved_max_energy = _resolve_value("max_energy", max_energy, env_config, file_config, None, sources)
    resolved_kpi_targets = _resolve_value(
        "kpi_targets", kpi_targets, env_config, file_config, None, sources
    )
    resolved_kpi_weights = _resolve_value(
        "kpi_weights", kpi_weights, env_config, file_config, None, sources
    )
    resolved_compliance = _resolve_value(
        "compliance", compliance, env_config, file_config, None, sources
    )
    if callback_manager is not _UNSET:
        set_harness_callback_manager(callback_manager)
        sources["callback_manager"] = "code"

    validated_mode = _validate_mode(str(resolved_mode))
    _harness_config = HarnessConfig(
        mode=validated_mode,
        verbose=bool(resolved_verbose),
        budget=cast(Optional[float], resolved_budget),
        max_tool_calls=cast(Optional[int], resolved_max_tool_calls),
        max_latency_ms=cast(Optional[float], resolved_max_latency_ms),
        max_energy=cast(Optional[float], resolved_max_energy),
        kpi_targets=cast(Optional[dict[str, float]], resolved_kpi_targets),
        kpi_weights=cast(Optional[dict[str, float]], resolved_kpi_weights),
        compliance=cast(Optional[str], resolved_compliance),
    )

    sdk_presence = _detect_sdks()
    instrumented: list[str] = []
    detected_but_not_instrumented: list[str] = []

    if validated_mode != "off" and sdk_presence["openai"]:
        from cascadeflow.harness.instrument import patch_openai

        if patch_openai():
            instrumented.append("openai")
    elif validated_mode == "off":
        from cascadeflow.harness.instrument import is_patched, unpatch_openai

        if is_patched():
            unpatch_openai()
    if sdk_presence["anthropic"]:
        detected_but_not_instrumented.append("anthropic")

    if _is_instrumented:
        logger.debug("harness init called again; instrumentation remains idempotent")
    _is_instrumented = True

    logger.info("harness init mode=%s instrumented=%s", validated_mode, instrumented)
    if detected_but_not_instrumented:
        logger.info(
            "harness detected but not instrumented=%s",
            detected_but_not_instrumented,
        )
    if file_path:
        logger.debug("harness loaded config file=%s", file_path)

    return HarnessInitReport(
        mode=validated_mode,
        instrumented=instrumented,
        detected_but_not_instrumented=detected_but_not_instrumented,
        config_sources=sources,
    )


def run(
    *,
    budget: Optional[float] = None,
    max_tool_calls: Optional[int] = None,
    max_latency_ms: Optional[float] = None,
    max_energy: Optional[float] = None,
    kpi_targets: Optional[dict[str, float]] = None,
    kpi_weights: Optional[dict[str, float]] = None,
    compliance: Optional[str] = None,
) -> HarnessRunContext:
    """
    Create a scoped run context.

    Scope-level values override global init defaults for the scope only.
    """

    config = get_harness_config()
    resolved_budget = budget if budget is not None else config.budget
    resolved_tool_calls = max_tool_calls if max_tool_calls is not None else config.max_tool_calls
    resolved_latency = max_latency_ms if max_latency_ms is not None else config.max_latency_ms
    resolved_energy = max_energy if max_energy is not None else config.max_energy
    resolved_kpi_targets = kpi_targets if kpi_targets is not None else config.kpi_targets
    resolved_kpi_weights = kpi_weights if kpi_weights is not None else config.kpi_weights
    resolved_compliance = compliance if compliance is not None else config.compliance

    return HarnessRunContext(
        mode=config.mode,
        budget_max=resolved_budget,
        tool_calls_max=resolved_tool_calls,
        latency_max_ms=resolved_latency,
        energy_max=resolved_energy,
        kpi_targets=resolved_kpi_targets,
        kpi_weights=resolved_kpi_weights,
        compliance=resolved_compliance,
    )


F = TypeVar("F", bound=Callable[..., Any])


def agent(
    *,
    budget: Optional[float] = None,
    kpi_targets: Optional[dict[str, float]] = None,
    kpi_weights: Optional[dict[str, float]] = None,
    compliance: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Attach policy metadata to an agent function without changing behavior.
    """

    metadata = {
        "budget": budget,
        "kpi_targets": kpi_targets,
        "kpi_weights": kpi_weights,
        "compliance": compliance,
    }

    def decorator(func: F) -> F:
        func.__cascadeflow_agent_policy__ = metadata  # type: ignore[attr-defined]

        if inspect.iscoroutinefunction(func):

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await func(*args, **kwargs)

            async_wrapper.__cascadeflow_agent_policy__ = metadata  # type: ignore[attr-defined]
            async_wrapper.__name__ = getattr(func, "__name__", "wrapped_agent")
            return cast(F, async_wrapper)

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        sync_wrapper.__cascadeflow_agent_policy__ = metadata  # type: ignore[attr-defined]
        sync_wrapper.__name__ = getattr(func, "__name__", "wrapped_agent")
        return cast(F, sync_wrapper)

    return decorator
