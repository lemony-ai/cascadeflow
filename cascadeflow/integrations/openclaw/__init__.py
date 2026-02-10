"""OpenClaw integration helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .pre_router import (
    OpenClawRouteHint,
    OPENCLAW_NATIVE_CATEGORIES,
    CATEGORY_TO_DOMAIN,
    extract_explicit_tags,
    classify_openclaw_frame,
)
from .adapter import (
    OpenClawRoutingDecision,
    build_routing_decision,
)
from .wrapper import (
    OpenClawAdapter,
    OpenClawAdapterConfig,
)
from .gateway import OpenClawGatewayAdapter

# Avoid importing the OpenAI-compatible HTTP server at module import time.
# This keeps `python -m cascadeflow.integrations.openclaw.openai_server` free of
# noisy `runpy` warnings and preserves fast import for users who only need
# the frame gateway or routing helpers.
if TYPE_CHECKING:  # pragma: no cover
    from .openai_server import OpenClawOpenAIServer, OpenClawOpenAIConfig

__all__ = [
    "OpenClawRouteHint",
    "OPENCLAW_NATIVE_CATEGORIES",
    "CATEGORY_TO_DOMAIN",
    "extract_explicit_tags",
    "classify_openclaw_frame",
    "OpenClawRoutingDecision",
    "build_routing_decision",
    "OpenClawAdapter",
    "OpenClawAdapterConfig",
    "OpenClawGatewayAdapter",
    "OpenClawOpenAIServer",
    "OpenClawOpenAIConfig",
]


def __getattr__(name: str):
    if name == "OpenClawOpenAIServer":
        from .openai_server import OpenClawOpenAIServer

        return OpenClawOpenAIServer
    if name == "OpenClawOpenAIConfig":
        from .openai_server import OpenClawOpenAIConfig

        return OpenClawOpenAIConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
