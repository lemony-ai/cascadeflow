"""Types for the Hermes Agent delegation-routing integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

VALID_ACTIONS = {"inherit", "route"}
VALID_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}


def _clean_text(value: Any, *, max_length: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    text = "".join(ch for ch in text if ch.isprintable())
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    return text


def _clean_optional(value: Any, *, max_length: int = 160) -> Optional[str]:
    text = _clean_text(value, max_length=max_length)
    return text or None


def _clean_tuple(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    try:
        return tuple(item for item in (_clean_text(v, max_length=120) for v in values) if item)
    except TypeError:
        return ()


@dataclass(frozen=True)
class HermesDelegationRequest:
    """Normalized task data Hermes passes before spawning a child agent."""

    goal: str
    context: Optional[str] = None
    toolsets: tuple[str, ...] = ()
    role: str = "leaf"
    parent_provider: Optional[str] = None
    parent_model: Optional[str] = None
    loaded_skills: tuple[str, ...] = ()
    skill_metadata: Optional[Mapping[str, Any]] = None
    task_metadata: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal", _clean_text(self.goal, max_length=2000))
        object.__setattr__(
            self,
            "context",
            _clean_optional(self.context, max_length=4000),
        )
        object.__setattr__(self, "toolsets", _clean_tuple(self.toolsets))
        object.__setattr__(self, "role", _clean_text(self.role or "leaf", max_length=32))
        object.__setattr__(
            self,
            "parent_provider",
            _clean_optional(self.parent_provider, max_length=80),
        )
        object.__setattr__(
            self,
            "parent_model",
            _clean_optional(self.parent_model, max_length=160),
        )
        object.__setattr__(self, "loaded_skills", _clean_tuple(self.loaded_skills))

    def text_for_classification(self) -> str:
        parts = [self.goal]
        if self.context:
            parts.append(self.context)
        return "\n".join(part for part in parts if part)


@dataclass(frozen=True)
class HermesDelegationDecision:
    """Routing recommendation returned to Hermes.

    ``action="route"`` means Hermes may apply provider/model/reasoning fields
    after validating them with its own provider and credential system.
    ``action="inherit"`` means Hermes should keep existing behavior. In observe
    mode the decision may still include recommended fields for logging.
    """

    action: str = "inherit"
    provider: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    domain: Optional[str] = None
    topic: Optional[str] = None
    complexity: Optional[str] = None
    confidence: float = 0.0
    reason: str = "default"
    source: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        action = _clean_text(self.action or "inherit", max_length=24).lower()
        if action not in VALID_ACTIONS:
            action = "inherit"
        object.__setattr__(self, "action", action)
        object.__setattr__(
            self,
            "provider",
            _clean_optional(self.provider, max_length=80),
        )
        object.__setattr__(self, "model", _clean_optional(self.model, max_length=160))
        effort = _clean_optional(self.reasoning_effort, max_length=32)
        if effort is not None:
            effort = effort.lower()
        if effort is not None and effort not in VALID_REASONING_EFFORTS:
            effort = None
        object.__setattr__(self, "reasoning_effort", effort)
        object.__setattr__(self, "domain", _clean_optional(self.domain, max_length=80))
        object.__setattr__(self, "topic", _clean_optional(self.topic, max_length=80))
        object.__setattr__(
            self,
            "complexity",
            _clean_optional(self.complexity, max_length=40),
        )
        object.__setattr__(self, "reason", _clean_text(self.reason, max_length=240))
        object.__setattr__(self, "source", _clean_text(self.source, max_length=80))
        confidence = max(0.0, min(1.0, float(self.confidence or 0.0)))
        object.__setattr__(self, "confidence", confidence)

    @property
    def applies(self) -> bool:
        return self.action == "route"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "provider": self.provider,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "domain": self.domain,
            "topic": self.topic,
            "complexity": self.complexity,
            "confidence": self.confidence,
            "reason": self.reason,
            "source": self.source,
            "metadata": dict(self.metadata or {}),
        }
