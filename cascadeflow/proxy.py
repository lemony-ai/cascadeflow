"""
Minimal routing proxy for cascadeflow.

Provides OpenAI- and Anthropic-compatible endpoints for local testing and validation:
- POST /v1/chat/completions (OpenAI format)
- POST /v1/messages (Anthropic format)

This implementation is intentionally lightweight and dependency-free.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from cascadeflow.telemetry.cost_tracker import CostTracker


@dataclass
class ProxyConfig:
    """Configuration for the routing proxy."""

    host: str = "127.0.0.1"
    port: int = 0
    token_cost: float = 0.00001
    virtual_models: dict[str, str] = field(
        default_factory=lambda: {
            "cascadeflow-auto": "cascadeflow-auto-resolved",
            "cascadeflow-fast": "cascadeflow-fast-resolved",
            "cascadeflow-quality": "cascadeflow-quality-resolved",
            "cascadeflow-cheap": "cascadeflow-cheap-resolved",
        }
    )


class RoutingProxy:
    """Lightweight routing proxy with OpenAI and Anthropic endpoints."""

    def __init__(
        self,
        config: Optional[ProxyConfig] = None,
        cost_tracker: Optional[CostTracker] = None,
    ) -> None:
        self.config = config or ProxyConfig()
        self.cost_tracker = cost_tracker or CostTracker()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        """Start the proxy server. Returns the bound port."""
        if self._server:
            return self.port

        server = ThreadingHTTPServer((self.config.host, self.config.port), ProxyRequestHandler)
        server.proxy = self  # type: ignore[attr-defined]
        self._server = server

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        return self.port

    def stop(self) -> None:
        """Stop the proxy server."""
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None

    @property
    def host(self) -> str:
        return self.config.host

    @property
    def port(self) -> int:
        if not self._server:
            return self.config.port
        return self._server.server_address[1]

    def resolve_model(self, model: str) -> Optional[str]:
        """Resolve virtual model names to concrete ones."""
        if model in self.config.virtual_models:
            return self.config.virtual_models[model]
        return model if model else None

    def decide_draft_acceptance(self, prompt: str) -> bool:
        """Simulate draft acceptance based on prompt heuristics."""
        lowered = prompt.lower()
        return not any(keyword in lowered for keyword in ("hard", "complex", "difficult"))

    def build_response_text(self, prompt: str) -> str:
        """Generate a deterministic response string."""
        return f"Proxy response: {prompt.strip()[:80]}".strip()

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using a simple word heuristic."""
        words = [w for w in text.split() if w]
        return len(words)

    def extract_prompt_text(self, messages: list[dict[str, Any]]) -> str:
        """Extract text content from a list of message objects."""
        parts: list[str] = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("content") or ""
                        if text:
                            parts.append(str(text))
                    elif isinstance(item, str):
                        parts.append(item)
        return " ".join(parts).strip()

    def record_cost(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        virtual_model: str,
        draft_accepted: bool,
    ) -> float:
        total_tokens = input_tokens + output_tokens
        cost = total_tokens * self.config.token_cost
        self.cost_tracker.add_cost(
            model=model,
            provider=provider,
            tokens=total_tokens,
            cost=cost,
            metadata={
                "virtual_model": virtual_model,
                "draft_accepted": draft_accepted,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )
        return cost


class ProxyRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for the routing proxy."""

    server_version = "CascadeFlowProxy/0.1"

    def do_POST(self) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._send_openai_error("Invalid JSON payload", status=400)

        if self.path == "/v1/chat/completions":
            self._handle_openai(proxy, payload)
            return
        if self.path == "/v1/messages":
            self._handle_anthropic(proxy, payload)
            return

        self.send_response(404)
        self.end_headers()

    def _handle_openai(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        model = payload.get("model", "")
        resolved = proxy.resolve_model(model)
        if not resolved:
            return self._send_openai_error("Model is required", status=400)

        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return self._send_openai_error("Messages are required", status=400)

        prompt = proxy.extract_prompt_text(messages)
        draft_accepted = proxy.decide_draft_acceptance(prompt)
        response_text = proxy.build_response_text(prompt)
        input_tokens = proxy.estimate_tokens(prompt)
        output_tokens = proxy.estimate_tokens(response_text)
        cost = proxy.record_cost(
            resolved,
            "proxy",
            input_tokens,
            output_tokens,
            virtual_model=model,
            draft_accepted=draft_accepted,
        )

        if payload.get("stream"):
            self._send_openai_stream(resolved, response_text, draft_accepted, model)
            return

        response = {
            "id": f"cfproxy-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": resolved,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "cascadeflow": {
                "virtual_model": model,
                "resolved_model": resolved,
                "draft_accepted": draft_accepted,
                "cost": cost,
            },
        }
        self._send_json(response)

    def _handle_anthropic(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        model = payload.get("model", "")
        resolved = proxy.resolve_model(model)
        if not resolved:
            return self._send_anthropic_error("Model is required", status=400)

        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return self._send_anthropic_error("Messages are required", status=400)

        prompt = proxy.extract_prompt_text(messages)
        draft_accepted = proxy.decide_draft_acceptance(prompt)
        response_text = proxy.build_response_text(prompt)
        input_tokens = proxy.estimate_tokens(prompt)
        output_tokens = proxy.estimate_tokens(response_text)
        cost = proxy.record_cost(
            resolved,
            "proxy",
            input_tokens,
            output_tokens,
            virtual_model=model,
            draft_accepted=draft_accepted,
        )

        if payload.get("stream"):
            self._send_anthropic_stream(resolved, response_text, draft_accepted, model)
            return

        response = {
            "id": f"cfproxy-{int(time.time() * 1000)}",
            "type": "message",
            "role": "assistant",
            "model": resolved,
            "content": [{"type": "text", "text": response_text}],
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "cascadeflow": {
                "virtual_model": model,
                "resolved_model": resolved,
                "draft_accepted": draft_accepted,
                "cost": cost,
            },
        }
        self._send_json(response)

    def _send_openai_stream(
        self, model: str, response_text: str, draft_accepted: bool, virtual_model: str
    ) -> None:
        chunks = self._chunk_text(response_text)
        self._start_stream()
        for chunk in chunks:
            payload = {
                "id": f"cfproxy-{int(time.time() * 1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                "cascadeflow": {
                    "virtual_model": virtual_model,
                    "resolved_model": model,
                    "draft_accepted": draft_accepted,
                },
            }
            self._write_stream_event(payload)
        final_payload = {
            "id": f"cfproxy-{int(time.time() * 1000)}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        self._write_stream_event(final_payload)
        self._write_stream_done()

    def _send_anthropic_stream(
        self, model: str, response_text: str, draft_accepted: bool, virtual_model: str
    ) -> None:
        chunks = self._chunk_text(response_text)
        self._start_stream()
        message_start = {
            "type": "message_start",
            "message": {"id": f"cfproxy-{int(time.time() * 1000)}", "model": model},
            "cascadeflow": {
                "virtual_model": virtual_model,
                "resolved_model": model,
                "draft_accepted": draft_accepted,
            },
        }
        self._write_stream_event(message_start, event="message_start")
        for chunk in chunks:
            delta = {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": chunk},
            }
            self._write_stream_event(delta, event="content_block_delta")
        message_stop = {"type": "message_stop"}
        self._write_stream_event(message_stop, event="message_stop")
        self._write_stream_done()

    def _chunk_text(self, text: str) -> list[str]:
        if len(text) <= 1:
            return [text]
        midpoint = max(1, len(text) // 2)
        return [text[:midpoint], text[midpoint:]]

    def _start_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _write_stream_event(self, payload: dict[str, Any], event: Optional[str] = None) -> None:
        data = json.dumps(payload)
        if event:
            self.wfile.write(f"event: {event}\n".encode("utf-8"))
        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _write_stream_done(self) -> None:
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_openai_error(self, message: str, status: int = 400) -> None:
        payload = {
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "code": "invalid_request_error",
            }
        }
        self._send_json(payload, status=status)

    def _send_anthropic_error(self, message: str, status: int = 400) -> None:
        payload = {"error": {"type": "invalid_request_error", "message": message}}
        self._send_json(payload, status=status)
