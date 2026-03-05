"""Reproducibility metadata collector.

Captures a full environment fingerprint so benchmark runs can be reproduced
by third parties.  The metadata is embedded in every artifact bundle.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ReproMetadata:
    """Immutable snapshot of the environment at benchmark start."""

    git_sha: str
    git_dirty: bool
    python_version: str
    platform: str
    cascadeflow_version: str
    profile: str
    drafter_model: str
    verifier_model: str
    baseline_model: str
    harness_mode: str
    package_versions: dict[str, str]
    run_id: str
    timestamp_utc: str


# Packages whose versions we record for reproducibility.
_TRACKED_PACKAGES = (
    "cascadeflow",
    "openai",
    "anthropic",
    "httpx",
    "pydantic",
    "tiktoken",
)


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    try:
        out = (
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        return bool(out)
    except Exception:
        return False


def _package_version(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        return "not installed"


def collect_repro_metadata(
    *,
    profile: str = "smoke",
    drafter_model: str = "",
    verifier_model: str = "",
    baseline_model: str = "",
    harness_mode: str = "off",
) -> ReproMetadata:
    """Capture a reproducibility fingerprint of the current environment."""

    versions = {pkg: _package_version(pkg) for pkg in _TRACKED_PACKAGES}

    return ReproMetadata(
        git_sha=_git_sha(),
        git_dirty=_git_dirty(),
        python_version=sys.version,
        platform=platform.platform(),
        cascadeflow_version=versions.get("cascadeflow", "not installed"),
        profile=profile,
        drafter_model=drafter_model,
        verifier_model=verifier_model,
        baseline_model=baseline_model,
        harness_mode=harness_mode,
        package_versions=versions,
        run_id=uuid.uuid4().hex[:12],
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


def metadata_to_dict(meta: ReproMetadata) -> dict[str, Any]:
    """Convert *meta* to a JSON-serializable dict."""

    return {
        "git_sha": meta.git_sha,
        "git_dirty": meta.git_dirty,
        "python_version": meta.python_version,
        "platform": meta.platform,
        "cascadeflow_version": meta.cascadeflow_version,
        "profile": meta.profile,
        "drafter_model": meta.drafter_model,
        "verifier_model": meta.verifier_model,
        "baseline_model": meta.baseline_model,
        "harness_mode": meta.harness_mode,
        "package_versions": dict(meta.package_versions),
        "run_id": meta.run_id,
        "timestamp_utc": meta.timestamp_utc,
    }
