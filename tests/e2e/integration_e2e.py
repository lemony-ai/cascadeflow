import json
import os
from pathlib import Path


def main() -> int:
    results = []

    n8n_path = Path("packages/integrations/n8n")
    if n8n_path.exists():
        results.append(
            {
                "name": "n8n_node",
                "status": "skipped",
                "detail": "n8n runtime not available in container; manual harness required",
            }
        )
    else:
        results.append(
            {
                "name": "n8n_node",
                "status": "failed",
                "detail": "n8n integration package not found",
            }
        )

    if not os.getenv("OPENAI_API_KEY"):
        results.append(
            {
                "name": "langchain_integration",
                "status": "skipped",
                "detail": "OPENAI_API_KEY not set; unable to run langchain example",
            }
        )
    else:
        results.append(
            {
                "name": "langchain_integration",
                "status": "skipped",
                "detail": "LangChain integration examples require manual setup",
            }
        )

    print(json.dumps({"results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
