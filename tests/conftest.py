import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _no_proxy_for_localhost() -> None:
    """
    Ensure local test servers remain reachable in CI environments that set HTTP(S)_PROXY.

    Some runners (notably macOS) may have proxy env vars configured without NO_PROXY
    covering localhost/127.0.0.1, which can break httpx connections to local servers.
    """

    for key in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(key, "").strip()
        needed = "127.0.0.1,localhost"
        if not current:
            os.environ[key] = needed
            continue
        if "127.0.0.1" not in current or "localhost" not in current:
            os.environ[key] = f"{current},{needed}"
