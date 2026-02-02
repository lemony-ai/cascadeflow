import json
import os
import subprocess
import sys
from typing import List


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print(json.dumps({"status": "skipped", "reason": "OPENAI_API_KEY not set"}, indent=2))
        return 0

    results = []

    def is_litellm_installed() -> bool:
        try:
            run([sys.executable, "-m", "pip", "show", "litellm"])
            return True
        except subprocess.CalledProcessError:
            return False

    originally_installed = is_litellm_installed()

    try:
        run([sys.executable, "-m", "pip", "install", "litellm"])
        output_with = run([sys.executable, "examples/basic_usage.py"]).stdout
        results.append({"mode": "with_litellm", "output_snippet": output_with[-500:]})

        run([sys.executable, "-m", "pip", "uninstall", "litellm", "-y"])
        output_without = run([sys.executable, "examples/basic_usage.py"]).stdout
        results.append({"mode": "without_litellm", "output_snippet": output_without[-500:]})
    finally:
        if originally_installed:
            run([sys.executable, "-m", "pip", "install", "litellm"])

    print(json.dumps({"status": "completed", "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
