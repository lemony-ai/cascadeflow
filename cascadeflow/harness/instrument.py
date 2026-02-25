from __future__ import annotations

import logging

logger = logging.getLogger("cascadeflow.harness")


def patch_openai() -> bool:
    """
    Placeholder for OpenAI SDK auto-instrumentation.

    Returns False in the core harness phase because patching is implemented in a
    dedicated follow-up branch.
    """

    logger.debug("openai instrumentation scaffold is not active in this branch")
    return False


def unpatch_openai() -> None:
    """
    Placeholder for removing OpenAI SDK instrumentation.
    """

    return None
