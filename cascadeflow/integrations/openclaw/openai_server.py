"""
OpenAI-compatible server for OpenClaw custom providers.

This is a thin compatibility wrapper around `cascadeflow.proxy.server.RoutingProxy`
configured with a CascadeAgent instance.

Endpoints:
- POST /v1/chat/completions (OpenAI format)
- POST /v1/messages (Anthropic format)
- GET  /health
- GET  /stats (best-effort: agent telemetry export)
"""

from __future__ import annotations

import argparse
import time

from cascadeflow.proxy.server import ProxyConfig as OpenClawOpenAIConfig
from cascadeflow.proxy.server import RoutingProxy


class OpenClawOpenAIServer(RoutingProxy):
    """OpenAI-compatible server that routes via a CascadeAgent."""

    def __init__(self, agent, config: OpenClawOpenAIConfig | None = None):
        super().__init__(config=config, agent=agent)


__all__ = ["OpenClawOpenAIServer", "OpenClawOpenAIConfig"]


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw OpenAI-compatible server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8084, help="Bind port (default: 8084)")
    parser.add_argument(
        "--config",
        help="Optional Cascadeflow config file (yaml/json) for models + channel routing",
    )
    parser.add_argument(
        "--preset",
        default="balanced",
        help="Cascadeflow preset (balanced, cost_optimized, speed_optimized, quality_optimized, development)",
    )
    parser.add_argument("--no-classifier", action="store_true", help="Disable pre-router classifier")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming responses")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.config:
        from cascadeflow.config_loader import load_agent

        agent = load_agent(args.config, verbose=args.verbose)
    else:
        from cascadeflow.utils.presets import auto_agent

        agent = auto_agent(preset=args.preset, verbose=args.verbose, enable_cascade=True)

    server = OpenClawOpenAIServer(
        agent,
        OpenClawOpenAIConfig(
            host=args.host,
            port=args.port,
            enable_classifier=not args.no_classifier,
            allow_streaming=not args.no_stream,
        ),
    )
    port = server.start()
    print(f"OpenClaw OpenAI server running at http://{server.host}:{port}/v1")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()

