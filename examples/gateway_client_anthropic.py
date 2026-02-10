"""
cascadeflow - Gateway Client Example (Anthropic-Compatible via HTTP)

This example demonstrates calling the gateway's Anthropic-compatible endpoint.
It's intentionally dependency-light (uses httpx) so you can test the wiring fast.

Start the gateway:
    python -m cascadeflow.server --mode mock --port 8084

Then run this example:
    python examples/gateway_client_anthropic.py
"""

import os

import httpx


def main() -> None:
    base_url = os.getenv("CASCADEFLOW_GATEWAY_URL", "http://127.0.0.1:8084/v1")
    url = f"{base_url.rstrip('/')}/messages"

    payload = {
        "model": "cascadeflow",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    }
    resp = httpx.post(url, json=payload, timeout=10.0)
    resp.raise_for_status()

    data = resp.json()
    text_blocks = [b.get("text") for b in data.get("content", []) if b.get("type") == "text"]
    print(text_blocks[0] if text_blocks else data)


if __name__ == "__main__":
    main()
