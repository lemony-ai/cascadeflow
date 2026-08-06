"""CLI entrypoint for serving a configured cascadeflow agent over MCP."""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Any


def _is_local_host(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


def _load_callable(spec: str) -> Any:
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise SystemExit("--knowledge-resolver must use module.path:callable format")
    try:
        module = importlib.import_module(module_name)
        value = getattr(module, attribute)
    except (ImportError, AttributeError) as exc:
        raise SystemExit(f"Failed to load --knowledge-resolver {spec!r}: {exc}") from exc
    if not callable(value):
        raise SystemExit(f"--knowledge-resolver {spec!r} is not callable")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve cascadeflow to ChatGPT, Claude, and other MCP clients"
    )
    parser.add_argument("--version", action="store_true", help="Print cascadeflow version and exit")
    parser.add_argument("--config", help="Cascadeflow YAML or JSON model configuration")
    parser.add_argument(
        "--preset",
        default="balanced",
        choices=(
            "balanced",
            "cost_optimized",
            "speed_optimized",
            "quality_optimized",
            "development",
        ),
        help="Auto-detected provider preset when --config is omitted",
    )
    parser.add_argument(
        "--knowledge-resolver",
        metavar="MODULE:CALLABLE",
        help="Optional server-side knowledge resolver import",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="stdio for Claude Desktop; streamable-http for remote hosts",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host")
    parser.add_argument("--port", type=int, default=8000, help="HTTP bind port")
    parser.add_argument("--path", default="/mcp", help="Streamable HTTP endpoint path")
    parser.add_argument("--no-ui", action="store_true", help="Disable the MCP Apps routing panel")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose cascadeflow logging")
    return parser


def main() -> None:
    args = _parser().parse_args()

    if args.version:
        from cascadeflow import __version__

        print(__version__)
        return

    if args.config:
        from cascadeflow.config_loader import load_agent

        agent = load_agent(args.config, verbose=args.verbose)
    else:
        from cascadeflow.utils.presets import auto_agent

        agent = auto_agent(args.preset, verbose=args.verbose, enable_cascade=True)

    resolver = _load_callable(args.knowledge_resolver) if args.knowledge_resolver else None

    from cascadeflow.integrations.mcp import create_mcp_server

    server = create_mcp_server(
        agent,
        knowledge_resolver=resolver,
        include_ui=not args.no_ui,
        host=args.host,
        port=args.port,
        streamable_http_path=args.path,
    )

    if args.transport == "streamable-http" and not _is_local_host(args.host):
        print(
            "WARNING: cascadeflow-mcp does not add authentication or TLS. "
            "Use a protected HTTPS reverse proxy with OAuth for production.",
            file=sys.stderr,
        )

    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
