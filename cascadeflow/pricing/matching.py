"""Prefix matching helpers for model pricing tables.

Pricing tables are keyed by model family (``gpt-4o``) but callers pass concrete,
often date-pinned model ids (``gpt-4o-2024-08-06``). Resolving those ids by
scanning the table and taking the first prefix hit makes the result depend on
dict insertion order, which silently prices ``gpt-4o-mini`` as ``gpt-4o``.

Matching the *longest* key instead makes resolution order-independent: a more
specific family always wins over the shorter family it extends.

Kept free of cascadeflow imports so provider and telemetry modules can use it
without creating import cycles.
"""

from collections.abc import Iterable
from typing import Optional

__all__ = ["longest_prefix_match"]


def longest_prefix_match(name: str, candidates: Iterable[str]) -> Optional[str]:
    """Return the longest candidate that is a prefix of ``name``.

    Args:
        name: Concrete model id, e.g. ``"gpt-4o-mini-2024-07-18"``.
        candidates: Pricing table keys, e.g. ``{"gpt-4o", "gpt-4o-mini"}``.

    Returns:
        The matching key, or ``None`` when no candidate is a prefix of ``name``.

    Example:
        >>> longest_prefix_match("gpt-4o-mini-2024-07-18", ["gpt-4o", "gpt-4o-mini"])
        'gpt-4o-mini'
        >>> longest_prefix_match("claude-3-opus", ["gpt-4o"]) is None
        True
    """
    matches = [key for key in candidates if name.startswith(key)]
    if not matches:
        return None
    return max(matches, key=len)
