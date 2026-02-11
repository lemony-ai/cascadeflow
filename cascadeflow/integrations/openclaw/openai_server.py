"""
OpenAI-compatible server for OpenClaw custom providers.

Implements POST /v1/chat/completions and routes requests through CascadeAgent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import queue
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from cascadeflow.tools.formats import normalize_tools
from cascadeflow.utils.messages import get_last_user_message

from .adapter import build_routing_decision
from .pre_router import CATEGORY_TO_DOMAIN


@dataclass
class OpenClawOpenAIConfig:
    host: str = "127.0.0.1"
    port: int = 0
    enable_classifier: bool = True
    default_domain_confidence: float = 0.8
    allow_streaming: bool = True
    # Optional auth. If unset, server behaves as before (no auth), which is ideal for localhost.
    auth_token: Optional[str] = None
    # If unset, /stats uses auth_token when auth_token is set; otherwise /stats is public.
    stats_auth_token: Optional[str] = None
    # Request hardening (production-friendly defaults, should not break local usage).
    max_body_bytes: int = 2_000_000
    socket_timeout_s: float = 30.0


class OpenClawOpenAIServer:
    """OpenAI-compatible server that routes via CascadeAgent."""

    def __init__(self, agent, config: Optional[OpenClawOpenAIConfig] = None):
        self.agent = agent
        self.config = config or OpenClawOpenAIConfig()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

    def start(self) -> int:
        if self._server:
            return self.port

        server = ThreadingHTTPServer((self.config.host, self.config.port), OpenAIRequestHandler)
        server.openclaw_server = self  # type: ignore[attr-defined]
        self._server = server

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        return self.port

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=1)
            self._loop = None
            self._loop_thread = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop and self._loop.is_running():
            return self._loop

        loop = asyncio.new_event_loop()

        def _run_loop() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=_run_loop, daemon=True)
        thread.start()
        self._loop = loop
        self._loop_thread = thread
        return loop

    def run_coroutine(self, coro):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def submit_coroutine(self, coro):
        loop = self._ensure_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop)

    @property
    def host(self) -> str:
        return self.config.host

    @property
    def port(self) -> int:
        if not self._server:
            return self.config.port
        return self._server.server_address[1]


class OpenAIRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CascadeflowOpenAI/0.1"

    def _get_presented_token(self) -> Optional[str]:
        auth = self.headers.get("Authorization")
        if isinstance(auth, str) and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            return token or None
        api_key = self.headers.get("X-API-Key")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
        return None

    def _require_auth(self, expected: Optional[str]) -> bool:
        if not expected:
            return True
        presented = self._get_presented_token()
        if isinstance(presented, str) and secrets.compare_digest(presented, expected):
            return True
        self._send_openai_error(
            "Unauthorized",
            status=401,
            error_type="authentication_error",
            extra_headers={"WWW-Authenticate": "Bearer"},
        )
        return False

    def do_GET(self) -> None:
        server: OpenClawOpenAIServer = self.server.openclaw_server  # type: ignore[attr-defined]
        if self.path.startswith("/stats"):
            expected = server.config.stats_auth_token or server.config.auth_token
            if not self._require_auth(expected):
                return
            return self._handle_stats(server)
        if self.path == "/health":
            # Check if any providers were successfully initialized
            providers_count = len(server.agent.providers) if server.agent.providers else 0
            if providers_count == 0:
                return self._send_json(
                    {
                        "status": "degraded",
                        "reason": "no_providers_initialized",
                        "message": "Server is running but no providers could be initialized. Check API keys.",
                    }
                )
            return self._send_json({"status": "ok", "providers_initialized": providers_count})

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        server: OpenClawOpenAIServer = self.server.openclaw_server  # type: ignore[attr-defined]
        if not self._require_auth(server.config.auth_token):
            return

        # Prevent slowloris and accidental huge requests.
        try:
            if server.config.socket_timeout_s:
                self.connection.settimeout(server.config.socket_timeout_s)
        except Exception:
            pass  # pragma: no cover - best effort only

        transfer_encoding = self.headers.get("Transfer-Encoding", "")
        if isinstance(transfer_encoding, str) and transfer_encoding.lower().strip() == "chunked":
            return self._send_openai_error("Chunked requests are not supported", status=400)

        length = int(self.headers.get("Content-Length", "0"))
        if server.config.max_body_bytes and length > server.config.max_body_bytes:
            return self._send_openai_error("Request too large", status=413)

        raw_body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._send_openai_error("Invalid JSON payload", status=400)

        if self.path == "/v1/chat/completions":
            return self._handle_chat(server, payload)

        self.send_response(404)
        self.end_headers()

    def _handle_chat(self, server: OpenClawOpenAIServer, payload: dict[str, Any]) -> None:
        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return self._send_openai_error("Messages are required", status=400)

        model = payload.get("model", "cascadeflow")
        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("max_tokens")
        if max_tokens is None:
            max_tokens = payload.get("max_completion_tokens", 100)
        tools_payload = payload.get("tools")
        if tools_payload is None and isinstance(payload.get("functions"), list):
            tools_payload = [
                {"type": "function", "function": func}
                for func in payload.get("functions", [])
                if isinstance(func, dict)
            ]
        tool_choice = payload.get("tool_choice")
        if tool_choice is None and "function_call" in payload:
            legacy_choice = payload.get("function_call")
            if isinstance(legacy_choice, str):
                if legacy_choice in {"auto", "none"}:
                    tool_choice = legacy_choice
                else:
                    tool_choice = {"type": "function", "function": {"name": legacy_choice}}
            elif isinstance(legacy_choice, dict):
                name = legacy_choice.get("name")
                if isinstance(name, str) and name:
                    tool_choice = {"type": "function", "function": {"name": name}}
        tools = normalize_tools(tools_payload)
        stream = bool(payload.get("stream"))

        if stream and not server.config.allow_streaming:
            return self._send_openai_error("Streaming not enabled", status=400)

        metadata = {}
        metadata_value = payload.get("metadata")
        if isinstance(metadata_value, dict):
            metadata = metadata_value
        elif isinstance(metadata_value, str) and metadata_value.strip():
            try:
                parsed = json.loads(metadata_value)
                if isinstance(parsed, dict):
                    metadata = parsed
            except json.JSONDecodeError:
                metadata = {}

        method = metadata.get("method") or payload.get("method")
        event = metadata.get("event") or payload.get("event")
        routing_decision = build_routing_decision(
            method=method,
            event=event,
            params=payload,
            payload=metadata,
            enable_classifier=server.config.enable_classifier,
        )

        cascadeflow_tags = routing_decision.tags or {}
        domain_hint = cascadeflow_tags.get("domain")
        if not domain_hint and cascadeflow_tags.get("category"):
            domain_hint = CATEGORY_TO_DOMAIN.get(cascadeflow_tags.get("category"))

        channel = metadata.get("channel") or payload.get("channel")
        if not channel and cascadeflow_tags.get("channel"):
            channel = cascadeflow_tags.get("channel")
        if not channel and cascadeflow_tags.get("category"):
            channel = cascadeflow_tags.get("category")

        if cascadeflow_tags:
            self.log_message(
                "Cascadeflow tags=%s channel=%s profile=%s domain=%s method=%s event=%s",
                cascadeflow_tags,
                channel,
                cascadeflow_tags.get("profile"),
                domain_hint,
                method,
                event,
            )

        domain_confidence_hint = (
            routing_decision.hint.confidence
            if routing_decision.hint
            else server.config.default_domain_confidence
        )

        kpi_flags = {}
        if isinstance(metadata.get("kpi_flags"), dict):
            kpi_flags.update(metadata.get("kpi_flags"))
        if cascadeflow_tags.get("category"):
            kpi_flags["openclaw_category"] = cascadeflow_tags.get("category")
        if cascadeflow_tags.get("profile"):
            kpi_flags["profile"] = cascadeflow_tags.get("profile")

        tenant_id = metadata.get("tenant_id") or payload.get("tenant_id")

        # Profile inference from model id (optional)
        if "quality" in model:
            kpi_flags.setdefault("profile", "quality")
        elif "cost" in model or "cheap" in model or "fast" in model:
            kpi_flags.setdefault("profile", "cost_savings")

        if stream:
            return self._send_openai_stream(
                server,
                model,
                messages,
                temperature,
                max_tokens,
                tools,
                tool_choice,
                domain_hint,
                domain_confidence_hint,
                kpi_flags,
                tenant_id,
                channel,
            )

        result = _run_agent(
            server,
            messages,
            temperature,
            max_tokens,
            tools,
            tool_choice,
            domain_hint,
            domain_confidence_hint,
            kpi_flags,
            tenant_id,
            channel,
        )

        response = _build_openai_response(model, result)
        self._send_json(response)

    def _handle_stats(self, server: OpenClawOpenAIServer) -> None:
        telemetry = getattr(server.agent, "telemetry", None)
        if telemetry is None or not hasattr(telemetry, "export_to_dict"):
            return self._send_openai_error("Metrics export not available", status=404)

        payload = telemetry.export_to_dict()
        self._send_json(payload)

    def _send_openai_stream(
        self,
        server: OpenClawOpenAIServer,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]],
        tool_choice: Optional[str],
        domain_hint: Optional[str],
        domain_confidence_hint: float,
        kpi_flags: dict[str, Any],
        tenant_id: Optional[str],
        channel: Optional[str],
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        event_queue: queue.Queue[object] = queue.Queue()
        sentinel = object()
        error_box: dict[str, Exception] = {}
        chunk_parts: list[str] = []
        completion_result: dict[str, Any] = {}

        async def _produce() -> None:
            try:
                async for event in server.agent.stream_events(
                    query=get_last_user_message(messages),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                    domain_hint=domain_hint,
                    domain_confidence_hint=domain_confidence_hint,
                    kpi_flags=kpi_flags,
                    tenant_id=tenant_id,
                    channel=channel,
                ):
                    event_queue.put(event)
            except Exception as exc:  # pragma: no cover - streaming error path
                error_box["error"] = exc
            finally:
                event_queue.put(sentinel)

        future = server.submit_coroutine(_produce())

        initial_chunk = {
            "id": "chatcmpl-cascadeflow",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ],
        }
        self.wfile.write(f"data: {json.dumps(initial_chunk)}\n\n".encode())
        self.wfile.flush()

        while True:
            item = event_queue.get()
            if item is sentinel:
                break
            event = item
            event_type = getattr(getattr(event, "type", None), "value", None)
            if event_type == "complete":
                event_data = getattr(event, "data", None)
                if isinstance(event_data, dict):
                    result_payload = event_data.get("result")
                    if isinstance(result_payload, dict):
                        completion_result = result_payload
                continue
            # When switching from draft to verifier, discard draft chunks
            if event_type == "switch":
                chunk_parts.clear()
                continue
            if event_type != "chunk":
                continue
            chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": event.content},
                        "finish_reason": None,
                    }
                ],
            }
            if isinstance(getattr(event, "content", None), str):
                chunk_parts.append(event.content)
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()

        try:
            future.result(timeout=1)
        except Exception as exc:  # pragma: no cover - logging only
            error_box.setdefault("error", exc)

        if "error" in error_box:
            self.log_error("Streaming error: %s", error_box["error"])

        prompt_tokens = int(completion_result.get("prompt_tokens") or 0)
        completion_tokens = int(completion_result.get("completion_tokens") or 0)
        total_tokens_value = completion_result.get("total_tokens")
        total_tokens = int(total_tokens_value) if total_tokens_value is not None else 0
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        if prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0:
            # Fallback estimate for streaming-only consumers that require usage.
            completion_tokens = max(1, len("".join(chunk_parts).split()))
            total_tokens = completion_tokens
        if prompt_tokens == 0 and completion_tokens == 0 and total_tokens > 0:
            completion_tokens = total_tokens
        full_content = "".join(chunk_parts)
        usage_payload = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
        }

        final_chunk = {
            "id": "chatcmpl-cascadeflow",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},  # Empty delta - full content is in message only
                    # Compatibility: some streaming clients inspect final message content only.
                    "message": {"role": "assistant", "content": full_content},
                    "finish_reason": "stop",
                }
            ],
            "usage": usage_payload,
        }
        self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode())
        self.wfile.flush()

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:  # pragma: no cover - client disconnected
            return

    def _send_openai_error(
        self,
        message: str,
        status: int = 400,
        error_type: str = "invalid_request_error",
        extra_headers: Optional[dict[str, str]] = None,
    ) -> None:
        body = {
            "error": {
                "message": message,
                "type": error_type,
                "code": None,
            }
        }
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except BrokenPipeError:  # pragma: no cover - client disconnected
            return


def _run_agent(
    server: OpenClawOpenAIServer,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    tools: Optional[list[dict[str, Any]]],
    tool_choice: Optional[str],
    domain_hint: Optional[str],
    domain_confidence_hint: float,
    kpi_flags: dict[str, Any],
    tenant_id: Optional[str],
    channel: Optional[str],
):

    return server.run_coroutine(
        server.agent.run(
            query=get_last_user_message(messages),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            domain_hint=domain_hint,
            domain_confidence_hint=domain_confidence_hint,
            kpi_flags=kpi_flags,
            tenant_id=tenant_id,
            channel=channel,
        )
    )


def _normalize_result_metadata(result) -> dict[str, Any]:
    """
    Ensure a stable cascadeflow.metadata contract for the OpenClaw OpenAI server.

    External clients (and our integration tests) expect these keys to exist even for
    direct-routed (non-cascaded) responses and when upstream providers omit fields.
    """
    meta: dict[str, Any] = {}
    if hasattr(result, "metadata") and isinstance(result.metadata, dict):
        meta = dict(result.metadata)

    meta.setdefault("draft_accepted", bool(getattr(result, "draft_accepted", False)))
    meta.setdefault("quality_score", getattr(result, "quality_score", None))
    meta.setdefault("complexity", getattr(result, "complexity", None))

    # Tests expect "cascade_overhead" (no units specified). Prefer *_ms if present.
    if "cascade_overhead" not in meta:
        overhead = meta.get("cascade_overhead_ms")
        if overhead is None:
            overhead = getattr(result, "cascade_overhead_ms", None)
        meta["cascade_overhead"] = 0 if overhead is None else overhead

    return meta


def _build_openai_response(model: str, result) -> dict[str, Any]:
    meta = _normalize_result_metadata(result)

    prompt_tokens_raw = meta.get("prompt_tokens")
    completion_tokens_raw = meta.get("completion_tokens")
    total_tokens_raw = meta.get("total_tokens")
    tool_calls = meta.get("tool_calls")

    prompt_tokens = int(prompt_tokens_raw or 0)
    completion_tokens = int(completion_tokens_raw or 0)
    total_tokens = int(total_tokens_raw) if total_tokens_raw is not None else None
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    elif prompt_tokens == 0 and completion_tokens == 0 and total_tokens > 0:
        completion_tokens = total_tokens

    content = getattr(result, "content", "") or ""
    if not isinstance(content, str):
        content = str(content)

    # Never return an empty assistant message if we have usable content in metadata.
    # This can happen when an upstream verifier returns only reasoning output.
    if not tool_calls and not content.strip():
        for source_key in ("verifier_response", "draft_response"):
            candidate = meta.get(source_key)
            if isinstance(candidate, str) and candidate.strip():
                meta.setdefault("openclaw_content_fallback", source_key)
                content = candidate
                break

    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = "tool_calls" if tool_calls else "stop"

    return {
        "id": "chatcmpl-cascadeflow",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            # Compatibility aliases for clients that normalize camelCase usage fields.
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
        },
        "cascadeflow": {
            "model_used": result.model_used,
            "metadata": meta,
        },
    }


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
    parser.add_argument(
        "--no-classifier", action="store_true", help="Disable pre-router classifier"
    )
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming responses")
    parser.add_argument(
        "--auth-token",
        default=None,
        help="Optional shared secret. If set, require Authorization: Bearer <token> (or X-API-Key).",
    )
    parser.add_argument(
        "--stats-auth-token",
        default=None,
        help="Optional separate token for GET /stats (defaults to --auth-token if set).",
    )
    parser.add_argument(
        "--max-body-bytes",
        type=int,
        default=2_000_000,
        help="Max request body size in bytes (default: 2000000).",
    )
    parser.add_argument(
        "--socket-timeout",
        type=float,
        default=30.0,
        help="Socket read timeout in seconds (default: 30).",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.config:
        from cascadeflow.config_loader import load_agent

        agent = load_agent(args.config, verbose=args.verbose)
    else:
        from cascadeflow.utils.presets import auto_agent

        agent = auto_agent(
            preset=args.preset, verbose=args.verbose, enable_cascade=True, use_hybrid=True
        )
    server = OpenClawOpenAIServer(
        agent,
        OpenClawOpenAIConfig(
            host=args.host,
            port=args.port,
            enable_classifier=not args.no_classifier,
            allow_streaming=not args.no_stream,
            auth_token=args.auth_token,
            stats_auth_token=args.stats_auth_token,
            max_body_bytes=args.max_body_bytes,
            socket_timeout_s=args.socket_timeout,
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
