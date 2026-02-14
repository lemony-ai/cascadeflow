"""
OpenAI-compatible server for OpenClaw custom providers.

Implements POST /v1/chat/completions and routes requests through CascadeAgent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import queue
import secrets
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from cascadeflow.schema.exceptions import ProviderError
from cascadeflow.tools.formats import normalize_tools
from cascadeflow.utils.messages import get_last_user_message

from .adapter import build_routing_decision
from .decision_trace import log_decision
from .pre_router import CATEGORY_TO_DOMAIN

oc_logger = logging.getLogger("cascadeflow.openclaw")

_DEFAULT_SENTINELS = ("NO_REPLY",)


class DemoRateLimiter:
    """In-memory per-IP rate limiter for demo mode."""

    def __init__(self, max_queries: int = 20, window_seconds: int = 3600):
        self.max_queries = max_queries
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def _prune(self, ip: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._timestamps[ip] = [t for t in self._timestamps[ip] if t > cutoff]

    def check(self, ip: str) -> tuple[bool, int]:
        """Check if ip is allowed. Returns (allowed, remaining)."""
        now = time.time()
        with self._lock:
            self._prune(ip, now)
            used = len(self._timestamps[ip])
            remaining = max(0, self.max_queries - used)
            return (used < self.max_queries, remaining)

    def record(self, ip: str) -> int:
        """Record a query for ip. Returns remaining queries."""
        now = time.time()
        with self._lock:
            self._prune(ip, now)
            self._timestamps[ip].append(now)
            return max(0, self.max_queries - len(self._timestamps[ip]))


def _strip_sentinel(content: str, sentinels: tuple[str, ...]) -> str:
    """Strip known sentinel patterns from content. Returns empty string if only sentinels."""
    if not content:
        return content
    cleaned = content.strip()
    for sentinel in sentinels:
        cleaned = cleaned.replace(sentinel, "")
    return cleaned.strip()


def _to_openai_tool_calls(
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert cascadeflow universal tool call format to OpenAI API format."""
    result: list[dict[str, Any]] = []
    for i, tc in enumerate(tool_calls):
        args = tc.get("arguments", {})
        args_str = json.dumps(args) if isinstance(args, dict) else str(args or "")
        result.append(
            {
                "index": i,
                "id": tc.get("id", f"call_{i}"),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": args_str,
                },
            }
        )
    return result


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
    # Demo mode: allow unauthenticated requests with per-IP rate limiting.
    demo_mode: bool = False
    demo_max_queries: int = 20
    demo_window_seconds: int = 3600
    # Optional directory for serving static files (e.g. install.sh).
    static_dir: Optional[str] = None


class OpenClawOpenAIServer:
    """OpenAI-compatible server that routes via CascadeAgent."""

    def __init__(self, agent, config: Optional[OpenClawOpenAIConfig] = None):
        self.agent = agent
        self.config = config or OpenClawOpenAIConfig()
        self._demo_limiter: DemoRateLimiter | None = (
            DemoRateLimiter(
                max_queries=self.config.demo_max_queries,
                window_seconds=self.config.demo_window_seconds,
            )
            if self.config.demo_mode
            else None
        )
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

    def _get_client_ip(self) -> str:
        """Get client IP, respecting X-Forwarded-For for proxied requests."""
        forwarded = self.headers.get("X-Forwarded-For")
        if isinstance(forwarded, str) and forwarded.strip():
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def _is_demo_request(self) -> bool:
        """True when demo_mode is on and the request has no valid auth token."""
        server: OpenClawOpenAIServer = self.server.openclaw_server  # type: ignore[attr-defined]
        if not server.config.demo_mode:
            return False
        expected = server.config.auth_token
        if not expected:
            return True  # No auth_token configured — all requests are demo
        presented = self._get_presented_token()
        if isinstance(presented, str) and secrets.compare_digest(presented, expected):
            return False  # Valid auth — not a demo request
        return True

    def _require_auth(self, expected: Optional[str]) -> bool:
        server: OpenClawOpenAIServer = self.server.openclaw_server  # type: ignore[attr-defined]
        if server.config.demo_mode:
            # In demo mode, allow unauthenticated/invalid-token requests through
            if not expected:
                return True
            presented = self._get_presented_token()
            if isinstance(presented, str) and secrets.compare_digest(presented, expected):
                return True
            # No valid token — allow through as demo (rate limited in _handle_chat)
            return True
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

        # Serve static files (e.g. /install.sh) from configured directory
        if server.config.static_dir:
            import os

            # Sanitize path to prevent directory traversal
            clean = os.path.normpath(self.path.lstrip("/"))
            if not clean.startswith("..") and os.sep not in clean:
                fpath = os.path.join(server.config.static_dir, clean)
                if os.path.isfile(fpath):
                    with open(fpath, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

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
        # Demo rate limiting
        is_demo = self._is_demo_request()
        if is_demo and server._demo_limiter:
            ip = self._get_client_ip()
            allowed, remaining = server._demo_limiter.check(ip)
            if not allowed:
                return self._send_openai_error(
                    f"Demo limit reached ({server.config.demo_max_queries} queries/"
                    f"{server.config.demo_window_seconds}s). "
                    "Thank you for trying cascadeflow!",
                    status=429,
                    error_type="rate_limit_error",
                )

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
                    tool_choice = {
                        "type": "function",
                        "function": {"name": legacy_choice},
                    }
            elif isinstance(legacy_choice, dict):
                name = legacy_choice.get("name")
                if isinstance(name, str) and name:
                    tool_choice = {
                        "type": "function",
                        "function": {"name": name},
                    }
        tools = normalize_tools(tools_payload)
        stream = bool(payload.get("stream"))
        stream_options = payload.get("stream_options")
        include_usage = isinstance(stream_options, dict) and bool(
            stream_options.get("include_usage")
        )

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

        request_id = f"req_{uuid.uuid4().hex[:12]}"
        request_start = time.time()
        query_text = get_last_user_message(messages) or ""

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
                include_usage,
                request_id=request_id,
                request_start=request_start,
                query_text=query_text,
                is_demo=is_demo,
            )

        try:
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
        except ProviderError as exc:
            return self._send_upstream_error(exc)
        except Exception as exc:
            self.log_error("Agent error: %s", exc)
            return self._send_openai_error(
                f"Internal error: {type(exc).__name__}",
                status=500,
                error_type="server_error",
            )

        # Check for upstream errors propagated through cascade metadata
        upstream_err = _extract_upstream_error(result)
        if upstream_err and not _has_content(result):
            return self._send_upstream_error_from_meta(upstream_err)

        total_ms = (time.time() - request_start) * 1000
        meta = _normalize_result_metadata(result)
        trace = _build_trace(
            request_id=request_id,
            query=query_text,
            stream=False,
            tools=tools,
            domain_hint=domain_hint,
            domain_confidence_hint=domain_confidence_hint,
            meta=meta,
            result=result,
            total_ms=total_ms,
        )
        # Skip ghost traces where cascade wasn't initialised (null models)
        if trace.get("draft", {}).get("model"):
            log_decision(trace)
        accepted = meta.get("draft_accepted", False)
        model_used = getattr(result, "model_used", "unknown")
        oc_logger.info(
            "DECISION req=%s accepted=%s model=%s cost=%.6f latency=%.0fms domain=%s q=%s",
            request_id,
            accepted,
            model_used,
            meta.get("total_cost", getattr(result, "total_cost", 0.0)),
            total_ms,
            domain_hint or "none",
            query_text[:60],
        )

        response = _build_openai_response(model, result)

        # Inject demo metadata
        if is_demo and server._demo_limiter:
            remaining = server._demo_limiter.record(self._get_client_ip())
            response.setdefault("cascadeflow", {}).setdefault("metadata", {})
            response["cascadeflow"]["metadata"]["demo_queries_remaining"] = remaining
            response["cascadeflow"]["metadata"][
                "demo_queries_limit"
            ] = server.config.demo_max_queries

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
        include_usage: bool = False,
        request_id: str = "",
        request_start: float = 0.0,
        query_text: str = "",
        is_demo: bool = False,
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
        pending_draft_chunks: list[str] = []
        captured_tool_calls: list[dict[str, Any]] = []
        completion_result: dict[str, Any] = {}
        captured_decision: dict[str, Any] = {}
        route_strategy: Optional[str] = None
        draft_accepted: Optional[bool] = None
        switched_to_verifier = False

        def _emit_chunk(content: str) -> None:
            chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": content},
                        "finish_reason": None,
                    }
                ],
            }
            chunk_parts.append(content)
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()

        def _flush_pending_draft() -> None:
            if not pending_draft_chunks:
                return
            buffered = list(pending_draft_chunks)
            pending_draft_chunks.clear()
            for buffered_chunk in buffered:
                _emit_chunk(buffered_chunk)

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
            if event_type == "routing":
                event_data = getattr(event, "data", None)
                if isinstance(event_data, dict):
                    strategy = event_data.get("strategy")
                    if isinstance(strategy, str) and strategy:
                        route_strategy = strategy
                continue
            if event_type == "draft_decision":
                event_data = getattr(event, "data", None)
                if isinstance(event_data, dict):
                    captured_decision = event_data if isinstance(event_data, dict) else {}
                    if isinstance(event_data.get("accepted"), bool):
                        draft_accepted = event_data.get("accepted")
                        if draft_accepted:
                            _flush_pending_draft()
                        else:
                            pending_draft_chunks.clear()
                continue
            # When switching from draft to verifier, discard buffered draft chunks.
            if event_type == "switch":
                switched_to_verifier = True
                pending_draft_chunks.clear()
                continue
            # Capture completed tool calls from ToolStreamManager.
            if event_type == "tool_call_complete":
                tc = getattr(event, "tool_call", None)
                if isinstance(tc, dict):
                    captured_tool_calls.append(tc)
                continue
            if event_type not in {"chunk", "text_chunk"}:
                continue
            content = getattr(event, "content", None)
            if not isinstance(content, str) or not content:
                continue

            event_data = getattr(event, "data", None)
            phase = event_data.get("phase") if isinstance(event_data, dict) else None

            should_emit_now = False
            if switched_to_verifier or phase == "verifier":
                switched_to_verifier = True
                should_emit_now = True
            elif phase == "direct" or route_strategy == "direct":
                should_emit_now = True
            elif draft_accepted is True:
                _flush_pending_draft()
                should_emit_now = True
            elif draft_accepted is False:
                # Draft was rejected; stream only clearly non-draft content.
                should_emit_now = bool(phase and phase != "draft")
            elif phase not in {"draft", None}:
                should_emit_now = True

            if should_emit_now:
                _emit_chunk(content)
            else:
                pending_draft_chunks.append(content)

        # Some providers may not emit an explicit draft_decision event.
        # If no verifier switch happened, release buffered draft chunks.
        if pending_draft_chunks and not switched_to_verifier:
            _flush_pending_draft()

        try:
            future.result(timeout=1)
        except Exception as exc:  # pragma: no cover - logging only
            error_box.setdefault("error", exc)

        if "error" in error_box:
            self.log_error("Streaming error: %s", error_box["error"])

        full_content = _strip_sentinel("".join(chunk_parts), _DEFAULT_SENTINELS)
        if not full_content:
            completion_content = completion_result.get("content")
            if isinstance(completion_content, str):
                full_content = _strip_sentinel(completion_content, _DEFAULT_SENTINELS)

        # If no content was produced and there's an upstream error, send an
        # error event so the client gets a meaningful failure instead of an
        # empty response.  The initial role chunk was already sent, so we send
        # an error-content chunk followed by [DONE].
        if not full_content and "error" in error_box:
            exc = error_box["error"]
            err_msg, err_status = _describe_upstream_error(exc)
            error_chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "error",
                    }
                ],
                "error": {
                    "message": err_msg,
                    "type": "upstream_error",
                    "code": err_status,
                },
            }
            self.wfile.write(f"data: {json.dumps(error_chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        # If no content chunks were emitted (e.g. draft-accepted where buffering
        # lost chunks), emit the content as a proper delta chunk now.  OpenAI SDKs
        # only accumulate delta.content from chunks with finish_reason=null and
        # ignore it on the stop chunk, so this must come before the final chunk.
        if full_content and not chunk_parts:
            _emit_chunk(full_content)

        # Merge tool calls from streaming events and complete result.
        result_tool_calls = completion_result.get("tool_calls")
        if isinstance(result_tool_calls, list) and result_tool_calls:
            # Prefer complete-event tool calls (may be more complete).
            captured_tool_calls = result_tool_calls
        openai_tool_calls = (
            _to_openai_tool_calls(captured_tool_calls) if captured_tool_calls else []
        )

        # Emit tool call delta chunks so OpenAI SDKs can parse them.
        if openai_tool_calls:
            tc_chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": openai_tool_calls},
                        "finish_reason": None,
                    }
                ],
            }
            self.wfile.write(f"data: {json.dumps(tc_chunk)}\n\n".encode())
            self.wfile.flush()

        prompt_tokens = int(completion_result.get("prompt_tokens") or 0)
        completion_tokens = int(completion_result.get("completion_tokens") or 0)
        total_tokens_value = completion_result.get("total_tokens")
        total_tokens = int(total_tokens_value) if total_tokens_value is not None else 0
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        if prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0:
            # Fallback estimate for streaming-only consumers that require usage.
            completion_tokens = max(1, len(full_content.split()))
            total_tokens = completion_tokens
        if prompt_tokens == 0 and completion_tokens == 0 and total_tokens > 0:
            completion_tokens = total_tokens
        usage_payload = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
        }

        finish_reason = "tool_calls" if openai_tool_calls else "stop"
        final_message: dict[str, Any] = {
            "role": "assistant",
            "content": full_content,
        }
        if openai_tool_calls:
            final_message["tool_calls"] = openai_tool_calls

        final_chunk: dict[str, Any] = {
            "id": "chatcmpl-cascadeflow",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {} if chunk_parts else {"content": full_content},
                    "message": final_message,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": usage_payload,
        }

        # Inject demo metadata into streaming final chunk
        if is_demo and server._demo_limiter:
            remaining = server._demo_limiter.record(self._get_client_ip())
            final_chunk["cascadeflow"] = {
                "metadata": {
                    "demo_queries_remaining": remaining,
                    "demo_queries_limit": server.config.demo_max_queries,
                },
            }

        self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode())
        self.wfile.flush()

        # OpenAI spec: when stream_options.include_usage is set, send a separate
        # usage-only chunk with choices=[] before [DONE].  The OpenAI Node SDK
        # (used by pi-ai / OpenClaw) expects this format.
        if include_usage:
            usage_chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [],
                "usage": usage_payload,
            }
            self.wfile.write(f"data: {json.dumps(usage_chunk)}\n\n".encode())
            self.wfile.flush()

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

        total_ms = (time.time() - request_start) * 1000 if request_start else 0.0
        trace = _build_stream_trace(
            request_id=request_id,
            query=query_text,
            tools=tools,
            domain_hint=domain_hint,
            domain_confidence_hint=domain_confidence_hint,
            complete_data=completion_result,
            decision_data=captured_decision,
            total_ms=total_ms,
        )
        # Skip ghost traces where cascade wasn't initialised (null models)
        if trace.get("draft", {}).get("model"):
            log_decision(trace)
        accepted = captured_decision.get("accepted", False)
        model_used = completion_result.get("model_used", "unknown")
        total_cost = completion_result.get("total_cost", 0.0)
        oc_logger.info(
            "DECISION req=%s accepted=%s model=%s cost=%.6f latency=%.0fms domain=%s q=%s",
            request_id,
            accepted,
            model_used,
            total_cost,
            total_ms,
            domain_hint or "none",
            query_text[:60],
        )

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
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

    def _send_upstream_error(self, exc: Exception) -> None:
        """Send an OpenAI-format error response for an upstream provider failure."""
        msg, status = _describe_upstream_error(exc)
        self.log_error("Upstream provider error: %s", exc)
        self._send_openai_error(msg, status=status, error_type="upstream_error")

    def _send_upstream_error_from_meta(self, error_info: dict[str, Any]) -> None:
        """Send an OpenAI-format error from cascade metadata upstream_error dict."""
        upstream_status = error_info.get("status_code", 502)
        provider = error_info.get("provider", "upstream")
        err_msg = error_info.get("message", "Upstream provider error")
        if upstream_status == 529:
            status, msg = (
                503,
                f"Upstream provider overloaded ({provider} 529). Please retry.",
            )
        elif upstream_status == 429:
            status, msg = (
                429,
                f"Upstream rate limit exceeded ({provider}). Please retry later.",
            )
        elif isinstance(upstream_status, int) and upstream_status >= 500:
            status, msg = (
                502,
                f"Upstream server error ({provider} {upstream_status}): {err_msg}",
            )
        else:
            status, msg = (
                502,
                f"Upstream provider error ({provider}): {err_msg}",
            )
        self.log_error("Upstream error from metadata: %s", msg)
        self._send_openai_error(msg, status=status, error_type="upstream_error")


def _describe_upstream_error(exc: Exception) -> tuple[str, int]:
    """Return (message, http_status) for an upstream provider error."""
    status = getattr(exc, "status_code", None) or 502
    provider = getattr(exc, "provider", None) or "upstream"
    if status == 529:
        return (
            f"Upstream provider overloaded ({provider} 529). Please retry.",
            503,
        )
    if status == 429:
        return (
            f"Upstream rate limit exceeded ({provider}). Please retry later.",
            429,
        )
    if status == 401:
        return f"Upstream authentication error ({provider}).", 401
    if isinstance(status, int) and status >= 500:
        return (
            f"Upstream server error ({provider} {status}). Please retry.",
            502,
        )
    return f"Upstream provider error: {exc}", 502


def _extract_upstream_error(result) -> dict[str, Any] | None:
    """Extract upstream_error dict from CascadeResult/SpeculativeResult metadata."""
    meta = getattr(result, "metadata", None)
    if isinstance(meta, dict):
        return meta.get("upstream_error")
    return None


def _has_content(result) -> bool:
    """Check if a result has non-empty content (excluding sentinels)."""
    content = getattr(result, "content", None)
    if not isinstance(content, str) or not content.strip():
        return False
    return bool(_strip_sentinel(content, _DEFAULT_SENTINELS))


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


def _build_trace(
    *,
    request_id,
    query,
    stream,
    tools,
    domain_hint,
    domain_confidence_hint,
    meta,
    result,
    total_ms,
):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "query": query[:200],
        "query_length": len(query),
        "stream": stream,
        "tools_sent": tools is not None,
        "tool_count": len(tools) if tools else 0,
        "routing": {
            "strategy": meta.get("routing_strategy", "cascade"),
            "domain": domain_hint,
            "domain_confidence": domain_confidence_hint if domain_hint else None,
            "complexity": meta.get("complexity"),
        },
        "draft": {
            "model": meta.get("draft_model") or meta.get("drafter_model"),
            "had_tool_calls": bool(meta.get("tool_calls")),
            "text_length": len(getattr(result, "content", "") or ""),
            "latency_ms": meta.get("draft_latency_ms") or meta.get("drafter_latency_ms"),
        },
        "decision": {
            "accepted": meta.get("draft_accepted", False),
            "confidence": meta.get("draft_confidence"),
            "alignment_score": meta.get("quality_score"),
            "quality_score": meta.get("quality_score"),
            "threshold": meta.get("quality_threshold"),
            "reason": meta.get("routing_reason") or meta.get("reason"),
            "checks": meta.get("checks", {}),
        },
        "verifier": {
            "model": meta.get("verifier_model"),
            "used": not meta.get("draft_accepted", False),
            "latency_ms": meta.get("verifier_latency_ms"),
        },
        "cost": {
            "draft_cost": meta.get("draft_cost") or meta.get("drafter_cost", 0.0),
            "verifier_cost": meta.get("verifier_cost", 0.0),
            "total_cost": meta.get("total_cost", getattr(result, "total_cost", 0.0)),
            "baseline_cost": meta.get("bigonly_cost"),
            "saved": meta.get("cost_saved"),
        },
        "tokens": {
            "draft_input": meta.get("draft_prompt_tokens"),
            "draft_output": meta.get("draft_completion_tokens"),
            "verifier_input": meta.get("verifier_prompt_tokens") or meta.get("prompt_tokens"),
            "verifier_output": meta.get("verifier_completion_tokens")
            or meta.get("completion_tokens"),
            "total": meta.get("total_tokens"),
        },
        "latency_ms": total_ms,
    }


def _build_stream_trace(
    *,
    request_id,
    query,
    tools,
    domain_hint,
    domain_confidence_hint,
    complete_data,
    decision_data,
    total_ms,
):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "query": query[:200],
        "query_length": len(query),
        "stream": True,
        "tools_sent": tools is not None,
        "tool_count": len(tools) if tools else 0,
        "routing": {
            "strategy": complete_data.get("routing_strategy", "cascade"),
            "domain": domain_hint,
            "domain_confidence": domain_confidence_hint if domain_hint else None,
            "complexity": decision_data.get("complexity") or complete_data.get("complexity"),
        },
        "draft": {
            "model": decision_data.get("draft_model") or complete_data.get("draft_model"),
            "had_tool_calls": bool(complete_data.get("tool_calls")),
            "text_length": complete_data.get("response_length", 0),
            "latency_ms": complete_data.get("draft_latency_ms")
            or complete_data.get("drafter_latency_ms"),
        },
        "decision": {
            "accepted": decision_data.get("accepted", complete_data.get("draft_accepted", False)),
            "confidence": decision_data.get("confidence"),
            "alignment_score": decision_data.get("alignment_score") or decision_data.get("score"),
            "quality_score": decision_data.get("score"),
            "threshold": decision_data.get("threshold") or decision_data.get("quality_threshold"),
            "reason": decision_data.get("reason"),
            "checks": decision_data.get("checks", {}),
        },
        "verifier": {
            "model": decision_data.get("verifier_model") or complete_data.get("verifier_model"),
            "used": not decision_data.get("accepted", complete_data.get("draft_accepted", False)),
            "latency_ms": complete_data.get("verifier_latency_ms"),
        },
        "cost": {
            "draft_cost": complete_data.get("draft_cost") or complete_data.get("drafter_cost", 0.0),
            "verifier_cost": complete_data.get("verifier_cost", 0.0),
            "total_cost": complete_data.get("total_cost", 0.0),
            "baseline_cost": complete_data.get("bigonly_cost"),
            "saved": complete_data.get("cost_saved"),
        },
        "tokens": {
            "draft_input": complete_data.get("draft_prompt_tokens"),
            "draft_output": complete_data.get("draft_completion_tokens"),
            "verifier_input": complete_data.get("verifier_prompt_tokens"),
            "verifier_output": complete_data.get("verifier_completion_tokens"),
            "total": complete_data.get("total_tokens"),
        },
        "latency_ms": total_ms,
    }


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
    content = _strip_sentinel(content, _DEFAULT_SENTINELS)

    # Never return an empty assistant message if we have usable content in metadata.
    # This can happen when an upstream verifier returns only reasoning output.
    if not tool_calls and not content.strip():
        for source_key in ("verifier_response", "draft_response"):
            candidate = meta.get(source_key)
            if isinstance(candidate, str):
                candidate = _strip_sentinel(candidate, _DEFAULT_SENTINELS)
                if candidate.strip():
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
        "--no-classifier",
        action="store_true",
        help="Disable pre-router classifier",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming responses",
    )
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
    parser.add_argument(
        "--demo-mode",
        action="store_true",
        help="Enable demo mode: allow unauthenticated requests with per-IP rate limiting.",
    )
    parser.add_argument(
        "--demo-max-queries",
        type=int,
        default=20,
        help="Max demo queries per IP per window (default: 20).",
    )
    parser.add_argument(
        "--demo-window",
        type=int,
        default=3600,
        help="Demo rate limit window in seconds (default: 3600).",
    )
    parser.add_argument(
        "--static-dir",
        default=None,
        help="Directory to serve static files from (e.g. install.sh).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.config:
        from cascadeflow.config_loader import load_agent

        agent = load_agent(args.config, verbose=args.verbose)
    else:
        from cascadeflow.utils.presets import auto_agent

        agent = auto_agent(
            preset=args.preset,
            verbose=args.verbose,
            enable_cascade=True,
            use_hybrid=True,
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
            demo_mode=args.demo_mode,
            demo_max_queries=args.demo_max_queries,
            demo_window_seconds=args.demo_window,
            static_dir=args.static_dir,
        ),
    )
    port = server.start()
    print(f"OpenClaw OpenAI server running at http://{server.host}:{port}/v1")
    if args.demo_mode:
        print(f"  Demo mode: {args.demo_max_queries} queries/{args.demo_window}s per IP")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
