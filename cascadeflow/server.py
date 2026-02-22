"""
CLI entrypoint for running a local cascadeflow gateway server.

This is the fastest way to test cascadeflow in an existing app:
- Start the gateway.
- Point your existing OpenAI/Anthropic client at `http://127.0.0.1:<port>/v1`.
"""

from __future__ import annotations

import argparse
import os
import time

from cascadeflow.proxy.server import ProxyConfig, RoutingProxy


def _has_any_provider_key() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GROQ_API_KEY",
            "TOGETHER_API_KEY",
        )
    )


def _is_local_bind_host(host: str) -> bool:
    normalized = (host or "").strip().lower()
    return normalized in {"127.0.0.1", "localhost", "::1"}


def _load_env_file(path: str, *, override: bool = False) -> None:
    """
    Minimal .env loader to keep the gateway CLI dependency-light.

    Supports:
    - KEY=value
    - export KEY=value
    - quoted values with single/double quotes
    - ignores empty lines and comments starting with '#'
    """

    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as exc:
        raise SystemExit(f"Failed to read --env-file {path!r}: {exc}") from exc

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if not override and key in os.environ:
            continue
        os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cascadeflow gateway server (OpenAI/Anthropic compatible)"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print cascadeflow version and exit",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8084, help="Bind port (default: 8084)")
    parser.add_argument(
        "--mode",
        choices=("auto", "mock", "agent"),
        default="auto",
        help="auto=agent if keys/config present, else mock (default: auto)",
    )
    parser.add_argument(
        "--env-file",
        help="Optional .env file to load before starting the gateway (dependency-free parser).",
    )
    parser.add_argument(
        "--env-override",
        action="store_true",
        help="Allow --env-file to override already-set environment variables.",
    )
    parser.add_argument(
        "--config",
        help="Optional config file (yaml/json) to define models/channels (agent mode).",
    )
    parser.add_argument(
        "--preset",
        default="balanced",
        help="Preset (balanced, cost_optimized, speed_optimized, quality_optimized, development)",
    )
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming")
    parser.add_argument(
        "--include-gateway-metadata",
        action="store_true",
        help="Include gateway debug metadata in JSON responses (optional; headers are always on by default).",
    )
    parser.add_argument(
        "--no-gateway-headers",
        action="store_true",
        help="Disable X-Cascadeflow-* response headers.",
    )
    parser.add_argument(
        "--cors-allow-origin",
        default="*",
        help="Value for Access-Control-Allow-Origin (default: '*').",
    )
    parser.add_argument(
        "--disable-cors",
        action="store_true",
        help="Disable CORS headers entirely.",
    )
    parser.add_argument(
        "--token-cost",
        type=float,
        default=ProxyConfig().token_cost,
        help="Mock-mode token cost multiplier for cost tracking (default: %(default)s).",
    )
    parser.add_argument(
        "--advertise-model",
        action="append",
        default=[],
        metavar="MODEL_ID",
        help=(
            "Advertise additional model IDs in GET /v1/models (repeatable). "
            "Useful for clients that validate model IDs."
        ),
    )
    parser.add_argument(
        "--virtual-model",
        action="append",
        default=[],
        metavar="ALIAS=TARGET",
        help=(
            "Add or override a virtual model mapping (repeatable). "
            "Affects GET /v1/models and mock-mode model resolution."
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.version:
        from cascadeflow import __version__

        print(__version__)
        return

    if args.env_file:
        _load_env_file(args.env_file, override=bool(args.env_override))

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

    virtual_models = ProxyConfig().virtual_models
    for model_id in args.advertise_model:
        if isinstance(model_id, str):
            model_id = model_id.strip()
            if model_id:
                virtual_models.setdefault(model_id, model_id)

    for mapping in args.virtual_model:
        if not isinstance(mapping, str):
            continue
        raw = mapping.strip()
        if not raw:
            continue
        if "=" not in raw:
            raise SystemExit(f"Invalid --virtual-model '{mapping}' (expected ALIAS=TARGET)")
        alias, target = raw.split("=", 1)
        alias = alias.strip()
        target = target.strip()
        if not alias or not target:
            raise SystemExit(f"Invalid --virtual-model '{mapping}' (expected ALIAS=TARGET)")
        virtual_models[alias] = target

    if (
        not args.disable_cors
        and str(args.cors_allow_origin).strip() == "*"
        and not _is_local_bind_host(str(args.host))
    ):
        print(
            "WARNING: wildcard CORS ('*') is enabled on a non-local bind host. "
            "For production, set --cors-allow-origin to a specific origin.",
            flush=True,
        )

    server = RoutingProxy(
        agent=agent,
        config=ProxyConfig(
            host=args.host,
            port=args.port,
            allow_streaming=not args.no_stream,
            token_cost=float(args.token_cost),
            cors_allow_origin=None if args.disable_cors else str(args.cors_allow_origin),
            include_gateway_headers=not args.no_gateway_headers,
            include_gateway_metadata=bool(args.include_gateway_metadata),
            virtual_models=virtual_models,
        ),
    )
    port = server.start()

    kind = "agent" if agent is not None else "mock"
    # Flush: the CLI is often run under a pipe in tests/CI, where stdout is block-buffered.
    print(f"cascadeflow gateway ({kind}) running at http://{server.host}:{port}/v1", flush=True)
    print(
        "Endpoints: POST /v1/chat/completions, POST /v1/messages, GET /health, GET /stats",
        flush=True,
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
