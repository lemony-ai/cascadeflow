"""
Core harness API scaffold for V2 planning work.

This module provides a minimal, backward-compatible surface:
- init(): global harness settings (opt-in)
- run(): scoped run context for budget/trace accounting
- agent(): decorator for attaching policy metadata

The implementation intentionally avoids modifying existing CascadeAgent behavior.
"""

from .api import (
    HarnessConfig,
    HarnessInitReport,
    HarnessRunContext,
    agent,
    get_current_run,
    get_harness_config,
    init,
    reset,
    run,
)

__all__ = [
    "HarnessConfig",
    "HarnessInitReport",
    "HarnessRunContext",
    "init",
    "run",
    "agent",
    "get_current_run",
    "get_harness_config",
    "reset",
]
