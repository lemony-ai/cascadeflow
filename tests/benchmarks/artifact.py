"""Artifact bundler.

Writes a single JSON artifact containing benchmark results, reproducibility
metadata, harness-overhead measurements, observe-mode validation, and an
optional baseline comparison.  Also generates a ``REPRODUCE.md`` with exact
pip-install + run commands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "1.0.0"


def bundle_artifact(
    *,
    results: dict[str, Any],
    metadata: dict[str, Any],
    overhead: dict[str, Any],
    observe: dict[str, Any],
    comparison: Optional[dict[str, Any]] = None,
    output_dir: Path | str = ".",
    run_id: str = "unknown",
) -> Path:
    """Write the full artifact bundle as ``artifact_<run_id>.json``.

    Returns the path to the written file.
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "results": results,
        "harness_overhead": overhead,
        "observe_validation": observe,
    }
    if comparison is not None:
        bundle["baseline_comparison"] = comparison

    artifact_path = output_dir / f"artifact_{run_id}.json"
    artifact_path.write_text(json.dumps(bundle, indent=2))

    _write_reproduce_md(output_dir, metadata)

    return artifact_path


# ---------------------------------------------------------------------------
# REPRODUCE.md generation
# ---------------------------------------------------------------------------

_REPRODUCE_TEMPLATE = """\
# Reproducing this benchmark run

## Environment

- **Git SHA:** {git_sha}
- **Python:** {python_version}
- **Platform:** {platform}
- **cascadeflow:** {cascadeflow_version}
- **Profile:** {profile}
- **Harness mode:** {harness_mode}

## Steps

```bash
# 1. Clone and checkout the exact commit
git clone https://github.com/lemony-ai/cascadeflow.git
cd cascadeflow
git checkout {git_sha}

# 2. Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Set API keys
export OPENAI_API_KEY="<your-key>"
export ANTHROPIC_API_KEY="<your-key>"

# 5. Run the benchmark suite
python -m tests.benchmarks.run_all --profile {profile} --with-repro
```

## Package versions at time of run

{package_table}
"""


def _write_reproduce_md(output_dir: Path, metadata: dict[str, Any]) -> Path:
    packages = metadata.get("package_versions", {})
    rows = [f"| {name} | {ver} |" for name, ver in sorted(packages.items())]
    table = (
        "| Package | Version |\n|---------|----------|\n" + "\n".join(rows) if rows else "_none_"
    )

    content = _REPRODUCE_TEMPLATE.format(
        git_sha=metadata.get("git_sha", "unknown"),
        python_version=metadata.get("python_version", "unknown"),
        platform=metadata.get("platform", "unknown"),
        cascadeflow_version=metadata.get("cascadeflow_version", "unknown"),
        profile=metadata.get("profile", "smoke"),
        harness_mode=metadata.get("harness_mode", "off"),
        package_table=table,
    )

    path = output_dir / "REPRODUCE.md"
    path.write_text(content)
    return path
