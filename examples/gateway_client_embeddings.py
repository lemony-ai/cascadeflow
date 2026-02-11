"""
cascadeflow - Gateway Client Example (Embeddings)

This example demonstrates calling the gateway's OpenAI-compatible embeddings endpoint.

Start the gateway:
    python -m cascadeflow.server --mode mock --port 8084

Then run this example:
    python examples/gateway_client_embeddings.py
"""

import os

import httpx


def main() -> None:
    base_url = os.getenv("CASCADEFLOW_GATEWAY_URL", "http://127.0.0.1:8084/v1")
    url = f"{base_url.rstrip('/')}/embeddings"

    payload = {"model": "cascadeflow", "input": ["hello", "world"]}
    resp = httpx.post(url, json=payload, timeout=10.0)
    resp.raise_for_status()

    data = resp.json()
    print(f"model={data.get('model')}")
    print(f"n={len(data.get('data', []))}")
    print(f"dim={len(data['data'][0]['embedding'])}")


if __name__ == "__main__":
    main()
