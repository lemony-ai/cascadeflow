"""
CLI entrypoint for running a local Cascadeflow gateway server.

Goal: "ship tomorrow" developer experience.

This starts an OpenAI/Anthropic-compatible HTTP server that can run in two modes:
- mock: deterministic local responses (no API keys required) to validate wiring quickly.
- agent: routes requests through a real CascadeAgent (requires provider keys/config).
"""

from __future__ import annotations

import argparse
import os
import time

from cascadeflow.proxy.server import ProxyConfig, RoutingProxy


def _has_any_provider_key() -> bool:
    return any(
        os.getenv(name)
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cascadeflow gateway server (OpenAI/Anthropic compatible)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8084, help="Bind port (default: 8084)")
    parser.add_argument(
        "--mode",
        choices=("auto", "mock", "agent"),
        default="auto",
        help="Server mode. auto=agent if keys/config present, else mock (default: auto)",
    )
    parser.add_argument(
        "--config",
        help="Optional Cascadeflow config file (yaml/json) for models + channel routing (agent mode).",
    )
    parser.add_argument(
        "--preset",
        default="balanced",
        help="Cascadeflow preset (balanced, cost_optimized, speed_optimized, quality_optimized, development)",
    )
    parser.add_argument("--no-classifier", action="store_true", help="Disable OpenClaw-style frame classifier")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming responses")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    mode = args.mode
    if mode == "auto":
        mode = "agent" if (args.config or _has_any_provider_key()) else "mock"

    agent = None
    if mode == "agent":
        if args.config:
            from cascadeflow.config_loader import load_agent

            agent = load_agent(args.config, verbose=args.verbose)
        else:
            from cascadeflow.utils.presets import auto_agent

            agent = auto_agent(preset=args.preset, verbose=args.verbose, enable_cascade=True)

    server = RoutingProxy(
        agent=agent,
        config=ProxyConfig(
            host=args.host,
            port=args.port,
            enable_classifier=not args.no_classifier,
            allow_streaming=not args.no_stream,
        ),
    )
    port = server.start()

    kind = "agent" if agent is not None else "mock"
    print(f"Cascadeflow gateway ({kind}) running at http://{server.host}:{port}/v1")
    print("Endpoints: POST /v1/chat/completions, POST /v1/messages, GET /health, GET /stats")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()

