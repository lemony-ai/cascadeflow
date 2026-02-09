"""
cascadeflow - Gateway Client Example (OpenAI SDK)

This example demonstrates the "drop-in gateway" integration:
1) Start the gateway (mock or agent mode)
2) Point your existing OpenAI client at it via base_url

Start the gateway:
    python -m cascadeflow.server --mode mock --port 8084

Then run this example:
    pip install openai
    python examples/gateway_client_openai.py
"""

import os


def main() -> None:
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover
        raise SystemExit("Missing dependency: pip install openai") from exc

    base_url = os.getenv("CASCADEFLOW_GATEWAY_URL", "http://127.0.0.1:8084/v1")
    client = OpenAI(base_url=base_url, api_key="unused")

    resp = client.chat.completions.create(
        model="cascadeflow",
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
    )
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()
