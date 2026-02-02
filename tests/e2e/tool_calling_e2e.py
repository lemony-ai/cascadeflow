import json
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print(json.dumps({"status": "skipped", "reason": "OPENAI_API_KEY not set"}, indent=2))
        return 0

    print(
        json.dumps(
            {
                "status": "skipped",
                "reason": "Tool-calling E2E requires provider access; configure tools in CI",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
