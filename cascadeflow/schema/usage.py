"""Canonical usage schema for cascadeflow."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Usage:
    """Canonical token usage across providers and execution paths."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @classmethod
    def from_payload(cls, usage: Any) -> "Usage":
        """Create canonical usage from provider/metadata payload variants."""
        if usage is None:
            return cls()
        if isinstance(usage, cls):
            return usage
        if not isinstance(usage, dict):
            return cls()

        input_tokens = usage.get("input_tokens")
        if input_tokens is None:
            input_tokens = usage.get("prompt_tokens", 0)

        output_tokens = usage.get("output_tokens")
        if output_tokens is None:
            output_tokens = usage.get("completion_tokens", 0)

        cached_input_tokens = usage.get("cached_input_tokens")
        if cached_input_tokens is None:
            cached_input_tokens = usage.get("cache_read_input_tokens", 0)

        return cls(
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            cached_input_tokens=int(cached_input_tokens or 0),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "total_tokens": self.total_tokens,
        }
