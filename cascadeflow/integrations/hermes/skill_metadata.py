"""Skill metadata helpers for Hermes Agent routing."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .config import HermesRouteProfile


def extract_cascadeflow_skill_metadata(metadata: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """Extract a normalized ``cascadeflow`` routing block from skill metadata.

    Hermes skill metadata may eventually arrive as frontmatter, a nested
    ``metadata.hermes.cascadeflow`` block, or a direct ``cascadeflow`` dict.
    This helper accepts already-parsed dictionaries and never reads Hermes
    skill files directly.
    """

    if not isinstance(metadata, Mapping):
        return {}

    direct = metadata.get("cascadeflow")
    if isinstance(direct, Mapping):
        return dict(direct)

    nested = metadata.get("metadata")
    if isinstance(nested, Mapping):
        hermes = nested.get("hermes")
        if isinstance(hermes, Mapping):
            cascadeflow = hermes.get("cascadeflow")
            if isinstance(cascadeflow, Mapping):
                return dict(cascadeflow)

    return {}


def profile_from_skill_metadata(
    metadata: Optional[Mapping[str, Any]],
) -> Optional[HermesRouteProfile]:
    """Return a route profile from explicit skill metadata, if present."""

    block = extract_cascadeflow_skill_metadata(metadata)
    if not block:
        return None
    return HermesRouteProfile.from_dict(block)
