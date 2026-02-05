"""
OpenAI-compatible server for OpenClaw custom providers.

Implements POST /v1/chat/completions and routes requests through CascadeAgent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import queue
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from cascadeflow.utils.messages import get_last_user_message

from .adapter import build_routing_decision
from .pre_router import CATEGORY_TO_DOMAIN
from .wrapper import OpenClawAdapterConfig


@dataclass
class OpenClawOpenAIConfig:
    host: str = "127.0.0.1"
    port: int = 0
    enable_classifier: bool = True
    default_domain_confidence: float = 0.8
    allow_streaming: bool = True


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
    server_version = "CascadeflowOpenAI/0.1"

    def do_POST(self) -> None:
        server: OpenClawOpenAIServer = self.server.openclaw_server  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length", "0"))
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
        max_tokens = payload.get("max_tokens", 100)
        tools = payload.get("tools")
        tool_choice = payload.get("tool_choice")
        stream = bool(payload.get("stream"))

        if stream and not server.config.allow_streaming:
            return self._send_openai_error("Streaming not enabled", status=400)

        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        routing_decision = build_routing_decision(
            method=metadata.get("method"),
            event=metadata.get("event"),
            params=payload,
            payload=metadata,
            enable_classifier=server.config.enable_classifier,
        )

        cascadeflow_tags = routing_decision.tags or {}
        domain_hint = cascadeflow_tags.get("domain")
        if not domain_hint and cascadeflow_tags.get("category"):
            domain_hint = CATEGORY_TO_DOMAIN.get(cascadeflow_tags.get("category"))

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
        channel = metadata.get("channel") or payload.get("channel")

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
        self.end_headers()

        event_queue: queue.Queue[object] = queue.Queue()
        sentinel = object()
        error_box: dict[str, Exception] = {}

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

        while True:
            item = event_queue.get()
            if item is sentinel:
                break
            event = item
            if getattr(event.type, "value", None) != "chunk":
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
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            future.result(timeout=1)
        except Exception as exc:  # pragma: no cover - logging only
            error_box.setdefault("error", exc)

        if "error" in error_box:
            self.log_error("Streaming error: %s", error_box["error"])

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_openai_error(self, message: str, status: int = 400) -> None:
        body = {
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "code": None,
            }
        }
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


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
    import asyncio

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


def _build_openai_response(model: str, result) -> dict[str, Any]:
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    if hasattr(result, "metadata") and result.metadata:
        prompt_tokens = result.metadata.get("prompt_tokens")
        completion_tokens = result.metadata.get("completion_tokens")
        total_tokens = result.metadata.get("total_tokens")

    if total_tokens is None:
        prompt_tokens = prompt_tokens or 0
        completion_tokens = completion_tokens or 0
        total_tokens = prompt_tokens + completion_tokens

    return {
        "id": "chatcmpl-cascadeflow",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        "cascadeflow": {
            "model_used": result.model_used,
            "metadata": result.metadata,
        },
    }


__all__ = ["OpenClawOpenAIServer", "OpenClawOpenAIConfig"]


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw OpenAI-compatible server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8084, help="Bind port (default: 8084)")
    parser.add_argument(
        "--preset",
        default="balanced",
        help="Cascadeflow preset (balanced, cost_optimized, speed_optimized, quality_optimized, development)",
    )
    parser.add_argument("--no-classifier", action="store_true", help="Disable pre-router classifier")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming responses")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

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
