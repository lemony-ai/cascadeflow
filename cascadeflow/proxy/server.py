"""
Minimal HTTP gateway for cascadeflow-compatible APIs.

Goals:
- "Ship tomorrow" developer experience: run locally, point existing OpenAI/Anthropic clients at it.
- Dependency-light: uses `http.server` (no FastAPI/Flask required).

Modes:
- Mock mode (default): deterministic local responses (no API keys required).
- Agent mode: if an `agent` is provided, route requests through `agent.run()` and
  optionally `agent.stream_events()` (OpenAI-style streaming).

Endpoints:
- POST /v1/chat/completions  (OpenAI-compatible)
- POST /v1/embeddings        (OpenAI-compatible)
- POST /v1/completions       (OpenAI-compatible, legacy)
- GET  /v1/models            (OpenAI-compatible)
- POST /v1/messages          (Anthropic-compatible)
- GET  /health
- GET  /stats                (best-effort: `agent.telemetry.export_to_dict()` if available)
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from cascadeflow.telemetry.cost_tracker import CostTracker


def _maybe_write_port_file(port: int) -> None:
    """
    Best-effort hook for tests/CI: write the bound port to a file.

    Some CI environments may not reliably surface subprocess stdout quickly enough
    to parse the ephemeral port. A port file provides a stdout-independent signal.
    """

    path = os.getenv("CASCADEFLOW_GATEWAY_PORT_FILE")
    if not path:
        return

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(int(port)))
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        # Don't fail gateway start for an optional debugging/testing feature.
        return


@dataclass
class ProxyConfig:
    """Configuration for the gateway server."""

    host: str = "127.0.0.1"
    port: int = 0
    allow_streaming: bool = True
    token_cost: float = 0.00001
    cors_allow_origin: str | None = "*"
    include_gateway_headers: bool = True
    include_gateway_metadata: bool = False
    virtual_models: dict[str, str] = field(
        default_factory=lambda: {
            "cascadeflow-auto": "cascadeflow-auto-resolved",
            "cascadeflow-fast": "cascadeflow-fast-resolved",
            "cascadeflow-quality": "cascadeflow-quality-resolved",
            "cascadeflow-cheap": "cascadeflow-cheap-resolved",
        }
    )


class RoutingProxy:
    """HTTP server exposing OpenAI and Anthropic endpoints."""

    def __init__(
        self,
        config: ProxyConfig | None = None,
        cost_tracker: CostTracker | None = None,
        agent: Any | None = None,
    ) -> None:
        self.config = config or ProxyConfig()
        self.cost_tracker = cost_tracker or CostTracker()
        self.agent = agent
        self._embedder: Any | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

    def start(self) -> int:
        """Start the server. Returns the bound port."""
        if self._server:
            return self.port

        server = ThreadingHTTPServer((self.config.host, self.config.port), ProxyRequestHandler)
        server.proxy = self  # type: ignore[attr-defined]
        self._server = server

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        _maybe_write_port_file(self.port)
        return self.port

    def stop(self) -> None:
        """Stop the server."""
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

    @property
    def host(self) -> str:
        return self.config.host

    @property
    def port(self) -> int:
        if not self._server:
            return self.config.port
        return self._server.server_address[1]

    def resolve_model(self, model: str) -> str | None:
        """Resolve virtual model names to concrete ones."""
        if model in self.config.virtual_models:
            return self.config.virtual_models[model]
        return model if model else None

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

    def _agent_query(self, messages: list[dict[str, Any]]) -> str:
        try:
            from cascadeflow.utils.messages import get_last_user_message

            return get_last_user_message(messages) or self.extract_prompt_text(messages)
        except Exception:
            return self.extract_prompt_text(messages)

    def _maybe_call_agent(self, func_name: str, **kwargs):
        if not self.agent or not hasattr(self.agent, func_name):
            raise RuntimeError(f"Agent does not support '{func_name}'")
        fn = getattr(self.agent, func_name)
        result = fn(**kwargs)
        if inspect.isawaitable(result):
            return self.run_coroutine(result)
        return result

    # ---------------------------------------------------------------------
    # Mock mode helpers (used when agent is None)
    # ---------------------------------------------------------------------

    def decide_draft_acceptance(self, prompt: str) -> bool:
        lowered = prompt.lower()
        return not any(keyword in lowered for keyword in ("hard", "complex", "difficult"))

    def build_response_text(self, prompt: str) -> str:
        return f"Proxy response: {prompt.strip()[:80]}".strip()

    def estimate_tokens(self, text: str) -> int:
        return len([w for w in text.split() if w])

    def extract_prompt_text(self, messages: list[dict[str, Any]]) -> str:
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

    # ---------------------------------------------------------------------
    # Embeddings helpers
    # ---------------------------------------------------------------------

    def _deterministic_embedding(self, text: str, dim: int = 384) -> list[float]:
        # Deterministic, dependency-free fallback for quick integration tests.
        # We intentionally don't normalize; most clients only require stable shape.
        buf = bytearray()
        seed = text.encode("utf-8", errors="replace")
        digest = hashlib.sha256(seed).digest()
        while len(buf) < dim:
            buf.extend(digest)
            digest = hashlib.sha256(digest).digest()
        vals = [(b - 127.5) / 127.5 for b in buf[:dim]]
        return [float(v) for v in vals]

    def _ensure_embedder(self) -> Any | None:
        if self._embedder is not None:
            return self._embedder
        try:
            from cascadeflow.ml.embedding import UnifiedEmbeddingService

            embedder = UnifiedEmbeddingService()
            if embedder.is_available:
                self._embedder = embedder
                return self._embedder
        except Exception:
            return None
        return None

    def embed_texts(self, texts: list[str], dim: int = 384) -> tuple[list[list[float]], str]:
        embedder = self._ensure_embedder()
        if embedder is not None:
            try:
                vectors = embedder.embed_batch(texts)
            except Exception:
                vectors = None
            if vectors is not None and len(vectors) == len(texts):
                out: list[list[float]] = []
                for vec in vectors:
                    if hasattr(vec, "tolist"):
                        out.append([float(x) for x in vec.tolist()])
                    else:
                        out.append([float(x) for x in list(vec)])
                return out, "fastembed"
        return [self._deterministic_embedding(t, dim=dim) for t in texts], "deterministic"


def _parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return dict(parsed)
    return {}


def _normalize_result_metadata(result: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if hasattr(result, "metadata") and isinstance(result.metadata, dict):
        meta = dict(result.metadata)

    # Stable minimal contract for clients.
    meta.setdefault("draft_accepted", bool(getattr(result, "draft_accepted", False)))
    meta.setdefault("quality_score", getattr(result, "quality_score", None))
    meta.setdefault("complexity", getattr(result, "complexity", None))

    if "cascade_overhead" not in meta:
        overhead = meta.get("cascade_overhead_ms")
        if overhead is None:
            overhead = getattr(result, "cascade_overhead_ms", None)
        meta["cascade_overhead"] = 0 if overhead is None else overhead

    return meta


def _build_openai_response(model: str, result: Any) -> dict[str, Any]:
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

    message: dict[str, Any] = {"role": "assistant", "content": getattr(result, "content", "")}
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = "tool_calls" if tool_calls else "stop"

    return {
        "id": "chatcmpl-cascadeflow",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
        },
        "cascadeflow": {
            "model_used": getattr(result, "model_used", None),
            "metadata": meta,
        },
    }


def _build_anthropic_response(model: str, result: Any) -> dict[str, Any]:
    meta = _normalize_result_metadata(result)
    input_tokens = meta.get("prompt_tokens", meta.get("input_tokens", 0)) or 0
    output_tokens = meta.get("completion_tokens", meta.get("output_tokens", 0)) or 0

    content_blocks: list[dict[str, Any]] = []
    text = getattr(result, "content", "")
    if isinstance(text, str) and text:
        content_blocks.append({"type": "text", "text": text})

    # Best-effort: translate OpenAI-style tool_calls to Anthropic tool_use blocks.
    tool_calls = meta.get("tool_calls")
    if isinstance(tool_calls, list):
        for idx, call in enumerate(tool_calls):
            if not isinstance(call, dict):
                continue
            call_id = call.get("id") or f"toolu_{idx}"
            fn = call.get("function") if isinstance(call.get("function"), dict) else None
            name = (fn.get("name") if fn else None) or call.get("name")
            if not isinstance(name, str) or not name:
                continue

            args: Any = {}
            raw_args = fn.get("arguments") if fn else None
            if isinstance(raw_args, str) and raw_args.strip():
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {"raw": raw_args}
            elif isinstance(raw_args, dict):
                args = raw_args

            content_blocks.append({"type": "tool_use", "id": call_id, "name": name, "input": args})

    return {
        "id": "msg_cascadeflow",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content_blocks,
        "stop_reason": "tool_use" if tool_calls else "end_turn",
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "cascadeflow": {"model_used": getattr(result, "model_used", None), "metadata": meta},
    }


def _extract_openai_tools(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]] | None, str | None]:
    tools_payload = payload.get("tools")
    if tools_payload is None and isinstance(payload.get("functions"), list):
        tools_payload = [
            {"type": "function", "function": func}
            for func in payload.get("functions", [])
            if isinstance(func, dict)
        ]

    tool_choice_value = payload.get("tool_choice")
    tool_choice: str | None = None
    if isinstance(tool_choice_value, str):
        tool_choice = tool_choice_value
    elif isinstance(tool_choice_value, dict):
        fn = (
            tool_choice_value.get("function")
            if isinstance(tool_choice_value.get("function"), dict)
            else None
        )
        name = fn.get("name") if fn else None
        if isinstance(name, str) and name:
            tool_choice = name

    if tool_choice is None and "function_call" in payload:
        legacy_choice = payload.get("function_call")
        if isinstance(legacy_choice, str):
            tool_choice = legacy_choice
        elif isinstance(legacy_choice, dict):
            name = legacy_choice.get("name")
            if isinstance(name, str) and name:
                tool_choice = name

    if tools_payload is None:
        return None, tool_choice

    try:
        from cascadeflow.tools.formats import normalize_tools

        return normalize_tools(tools_payload), tool_choice
    except Exception:
        return tools_payload, tool_choice


def _anthropic_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(p for p in parts if p).strip()
    return ""


def _anthropic_payload_to_openai_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    system_value = payload.get("system")
    if system_value is not None:
        system_text = _anthropic_content_to_text(system_value)
        if system_text:
            messages.append({"role": "system", "content": system_text})

    raw_messages = payload.get("messages", [])
    if isinstance(raw_messages, list):
        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in {"user", "assistant"}:
                continue
            content = _anthropic_content_to_text(msg.get("content"))
            messages.append({"role": role, "content": content})

    return messages


class ProxyRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CascadeFlowGateway/0.1"

    def _set_gateway_context(self, proxy: RoutingProxy, *, api: str, endpoint: str) -> None:
        self._gateway_api = api
        self._gateway_endpoint = endpoint
        self._gateway_mode = "agent" if proxy.agent is not None else "mock"

    def _request_path(self) -> str:
        # Drop query string. Many SDKs add no query params, but this keeps routing safe.
        return urlparse(self.path).path

    def _normalize_api_path(self) -> str:
        # Accept both styles:
        # - base_url="http://host:port/v1"  -> requests to /v1/...
        # - base_url="http://host:port"     -> requests to /...
        path = self._request_path()
        if path.startswith("/v1/"):
            return path[len("/v1") :]
        return path

    def _extract_agent_hints(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Optional cascadeflow-specific hints. These are non-standard and safe to ignore.

        They are intended to improve DX by enabling opt-in routing hints without
        changing the OpenAI/Anthropic request schema.
        """

        hints: dict[str, Any] = {}

        domain_hint = self.headers.get("X-Cascadeflow-Domain")
        complexity_hint = self.headers.get("X-Cascadeflow-Complexity")

        cf = payload.get("cascadeflow")
        if isinstance(cf, dict):
            if not domain_hint:
                domain_hint = cf.get("domain_hint") or cf.get("domain")
            if not complexity_hint:
                complexity_hint = cf.get("complexity_hint") or cf.get("complexity")

        if domain_hint:
            value = str(domain_hint).strip().lower()
            if value:
                hints["domain_hint"] = value

        if complexity_hint:
            value = str(complexity_hint).strip().lower()
            if value:
                hints["complexity_hint"] = value

        return hints

    @staticmethod
    def _domain_hint_from_model(model: str) -> str | None:
        """
        Optional DX feature: allow forcing a domain via the standard `model` field,
        without custom headers. This keeps existing OpenAI/Anthropic clients working.

        Examples:
        - model="cascadeflow:code"  -> domain_hint="code"
        - model="cascadeflow/math"  -> domain_hint="math"
        """

        raw = str(model or "").strip()
        if not raw:
            return None
        lowered = raw.lower()

        domain = None
        if lowered.startswith("cascadeflow:"):
            domain = lowered.split(":", 1)[1].strip()
        elif lowered.startswith("cascadeflow/"):
            domain = lowered.split("/", 1)[1].strip()

        if not domain:
            return None

        # Conservative validation to avoid surprising routing behavior.
        for ch in domain:
            if not (ch.isalnum() or ch in ("_", "-")):
                return None
        return domain

    def do_OPTIONS(self) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        self._set_gateway_context(proxy, api="gateway", endpoint="options")
        self.send_response(204)
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()

    def do_GET(self) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        path = self._request_path()
        normalized = self._normalize_api_path()

        if path == "/health":
            self._set_gateway_context(proxy, api="gateway", endpoint="health")
            return self._send_json({"status": "ok"})

        if path.startswith("/stats"):
            self._set_gateway_context(proxy, api="gateway", endpoint="stats")
            telemetry = getattr(proxy.agent, "telemetry", None) if proxy.agent else None
            if telemetry is None or not hasattr(telemetry, "export_to_dict"):
                self.send_response(404)
                self._send_cors_headers(proxy)
                self._send_gateway_headers(proxy)
                self.end_headers()
                return
            try:
                payload = telemetry.export_to_dict()
            except Exception as exc:
                return self._send_openai_error(f"Metrics export failed: {exc}", status=500)
            return self._send_json(payload)

        if normalized == "/models":
            self._set_gateway_context(proxy, api="openai", endpoint="models.list")
            return self._send_json(self._build_openai_models_list(proxy))

        if normalized.startswith("/models/"):
            self._set_gateway_context(proxy, api="openai", endpoint="models.retrieve")
            model_id = normalized[len("/models/") :]
            return self._send_json(self._build_openai_model_object(model_id))

        self.send_response(404)
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()

    def do_POST(self) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        normalized = self._normalize_api_path()
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._send_openai_error("Invalid JSON payload", status=400)

        if normalized == "/chat/completions":
            self._set_gateway_context(proxy, api="openai", endpoint="chat.completions")
            self._handle_openai(proxy, payload)
            return

        if normalized == "/messages":
            self._set_gateway_context(proxy, api="anthropic", endpoint="messages")
            self._handle_anthropic(proxy, payload)
            return

        if normalized == "/completions":
            self._set_gateway_context(proxy, api="openai", endpoint="completions")
            self._handle_openai_completions(proxy, payload)
            return

        if normalized == "/embeddings":
            self._set_gateway_context(proxy, api="openai", endpoint="embeddings")
            self._handle_openai_embeddings(proxy, payload)
            return

        self.send_response(404)
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()

    # ------------------------------------------------------------------
    # OpenAI endpoint
    # ------------------------------------------------------------------

    def _handle_openai(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        if proxy.agent is not None:
            return self._handle_openai_agent(proxy, payload)
        return self._handle_openai_mock(proxy, payload)

    def _handle_openai_mock(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
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
            "id": "chatcmpl-proxy",
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
                "promptTokens": input_tokens,
                "completionTokens": output_tokens,
                "totalTokens": input_tokens + output_tokens,
            },
            "cascadeflow": {
                "virtual_model": model,
                "resolved_model": resolved,
                "draft_accepted": draft_accepted,
                "cost": cost,
            },
        }
        self._send_json(response)

    def _handle_openai_agent(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return self._send_openai_error("Messages are required", status=400)

        model = payload.get("model", "cascadeflow")
        if not isinstance(model, str) or not model:
            model = "cascadeflow"

        hints = self._extract_agent_hints(payload)
        if "domain_hint" not in hints:
            model_domain = self._domain_hint_from_model(model)
            if model_domain:
                hints["domain_hint"] = model_domain

        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("max_tokens")
        if max_tokens is None:
            max_tokens = payload.get("max_completion_tokens", 100)

        tools, tool_choice = _extract_openai_tools(payload)

        stream_options = payload.get("stream_options")
        include_usage = (
            isinstance(stream_options, dict) and bool(stream_options.get("include_usage"))
        )

        if payload.get("stream"):
            if not proxy.config.allow_streaming:
                return self._send_openai_error("Streaming not enabled", status=400)
            if not hasattr(proxy.agent, "stream_events"):
                return self._send_openai_error("Streaming not supported by agent", status=400)
            return self._send_openai_agent_stream(
                proxy,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                complexity_hint=hints.get("complexity_hint"),
                domain_hint=hints.get("domain_hint"),
                include_usage=include_usage,
            )

        try:
            result = proxy._maybe_call_agent(
                "run",
                query=proxy._agent_query(messages),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                **hints,
            )
        except Exception as exc:
            return self._send_openai_error(str(exc), status=500)

        response = _build_openai_response(model, result)
        self._send_json(response)

    # ------------------------------------------------------------------
    # OpenAI legacy completions endpoint
    # ------------------------------------------------------------------

    def _handle_openai_completions(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        if proxy.agent is not None:
            return self._handle_openai_completions_agent(proxy, payload)
        return self._handle_openai_completions_mock(proxy, payload)

    def _handle_openai_completions_mock(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        model = payload.get("model", "")
        resolved = proxy.resolve_model(model)
        if not resolved:
            return self._send_openai_error("Model is required", status=400)

        prompt_value = payload.get("prompt", "")
        if isinstance(prompt_value, list):
            prompt = "\n".join(str(p) for p in prompt_value if p is not None)
        else:
            prompt = str(prompt_value or "")
        if not prompt.strip():
            return self._send_openai_error("Prompt is required", status=400)

        response_text = proxy.build_response_text(prompt)
        input_tokens = proxy.estimate_tokens(prompt)
        output_tokens = proxy.estimate_tokens(response_text)

        response = {
            "id": "cmpl-proxy",
            "object": "text_completion",
            "created": int(time.time()),
            "model": resolved,
            "choices": [
                {
                    "text": response_text,
                    "index": 0,
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "promptTokens": input_tokens,
                "completionTokens": output_tokens,
                "totalTokens": input_tokens + output_tokens,
            },
        }
        self._send_json(response)

    def _handle_openai_completions_agent(
        self, proxy: RoutingProxy, payload: dict[str, Any]
    ) -> None:
        prompt_value = payload.get("prompt", "")
        if isinstance(prompt_value, list):
            prompt = "\n".join(str(p) for p in prompt_value if p is not None)
        else:
            prompt = str(prompt_value or "")
        if not prompt.strip():
            return self._send_openai_error("Prompt is required", status=400)

        model = payload.get("model", "cascadeflow")
        if not isinstance(model, str) or not model:
            model = "cascadeflow"

        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("max_tokens", 100)
        messages = [{"role": "user", "content": prompt}]
        hints = self._extract_agent_hints(payload)

        try:
            result = proxy._maybe_call_agent(
                "run",
                query=prompt,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=None,
                tool_choice=None,
                **hints,
            )
        except Exception as exc:
            return self._send_openai_error(str(exc), status=500)

        meta = _normalize_result_metadata(result)
        prompt_tokens = meta.get("prompt_tokens", 0) or 0
        completion_tokens = meta.get("completion_tokens", 0) or 0
        total_tokens = meta.get("total_tokens")
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens

        response = {
            "id": "cmpl-cascadeflow",
            "object": "text_completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "text": getattr(result, "content", ""),
                    "index": 0,
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "totalTokens": total_tokens,
            },
            "cascadeflow": {
                "model_used": getattr(result, "model_used", None),
                "metadata": meta,
            },
        }
        self._send_json(response)

    # ------------------------------------------------------------------
    # OpenAI embeddings endpoint
    # ------------------------------------------------------------------

    def _handle_openai_embeddings(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        model = payload.get("model", "cascadeflow")
        if not isinstance(model, str) or not model:
            model = "cascadeflow"

        input_value = payload.get("input")
        if isinstance(input_value, list):
            texts = [str(x) for x in input_value]
        elif input_value is None:
            texts = []
        else:
            texts = [str(input_value)]
        if not texts:
            return self._send_openai_error("Input is required", status=400)

        vectors, source = proxy.embed_texts(texts)
        prompt_tokens = proxy.estimate_tokens(" ".join(texts))

        response = {
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": vec, "index": idx}
                for idx, vec in enumerate(vectors)
            ],
            "model": model,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "total_tokens": prompt_tokens,
                "promptTokens": prompt_tokens,
                "totalTokens": prompt_tokens,
            },
            "cascadeflow": {"embedding_source": source},
        }
        self._send_json(response)

    def _send_openai_agent_stream(
        self,
        proxy: RoutingProxy,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        complexity_hint: str | None = None,
        domain_hint: str | None = None,
        include_usage: bool = False,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()

        event_queue: queue.Queue[object] = queue.Queue()
        sentinel = object()
        error_box: dict[str, Exception] = {}
        chunk_parts: list[str] = []
        completion_result: dict[str, Any] = {}

        async def _produce() -> None:
            try:
                async for event in proxy.agent.stream_events(
                    query=proxy._agent_query(messages),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    complexity_hint=complexity_hint,
                    domain_hint=domain_hint,
                    tools=tools,
                    tool_choice=tool_choice,
                ):
                    event_queue.put(event)
            except Exception as exc:  # pragma: no cover
                error_box["error"] = exc
            finally:
                event_queue.put(sentinel)

        future = proxy.submit_coroutine(_produce())

        initial_chunk = {
            "id": "chatcmpl-cascadeflow",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}
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
            if event_type != "chunk":
                continue

            content = getattr(event, "content", None)
            if not isinstance(content, str):
                continue
            chunk_parts.append(content)

            chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()

        try:
            future.result(timeout=1)
        except Exception as exc:  # pragma: no cover
            error_box.setdefault("error", exc)

        if "error" in error_box:  # pragma: no cover
            self.log_error("Streaming error: %s", error_box["error"])

        full_content = "".join(chunk_parts)
        if not full_content:
            completion_content = completion_result.get("content")
            if isinstance(completion_content, str):
                full_content = completion_content
        # Emit a proper content chunk when no streaming chunks were captured.
        # OpenAI SDKs only accumulate delta.content from chunks with
        # finish_reason=null, so this must come before the stop chunk.
        if full_content and not chunk_parts:
            fallback_chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {"index": 0, "delta": {"content": full_content}, "finish_reason": None}
                ],
            }
            chunk_parts.append(full_content)
            self.wfile.write(f"data: {json.dumps(fallback_chunk)}\n\n".encode())
            self.wfile.flush()

        prompt_tokens = int(completion_result.get("prompt_tokens") or 0)
        completion_tokens = int(completion_result.get("completion_tokens") or 0)
        total_tokens_value = completion_result.get("total_tokens")
        total_tokens = int(total_tokens_value) if total_tokens_value is not None else 0
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        if prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0:
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

        final_chunk = {
            "id": "chatcmpl-cascadeflow",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {} if chunk_parts else {"content": full_content},
                    "message": {"role": "assistant", "content": full_content},
                    "finish_reason": "stop",
                }
            ],
            "usage": usage_payload,
        }
        self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode())
        self.wfile.flush()

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

    # ------------------------------------------------------------------
    # Anthropic endpoint
    # ------------------------------------------------------------------

    def _handle_anthropic(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        if proxy.agent is not None:
            return self._handle_anthropic_agent(proxy, payload)
        return self._handle_anthropic_mock(proxy, payload)

    def _handle_anthropic_mock(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        model = payload.get("model", "")
        resolved = proxy.resolve_model(model)
        if not resolved:
            return self._send_anthropic_error("model is required", status=400)

        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return self._send_anthropic_error("messages are required", status=400)

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
            "id": "msg_proxy",
            "type": "message",
            "role": "assistant",
            "model": resolved,
            "content": [{"type": "text", "text": response_text}],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "cascadeflow": {
                "virtual_model": model,
                "resolved_model": resolved,
                "draft_accepted": draft_accepted,
                "cost": cost,
            },
        }
        self._send_json(response)

    def _handle_anthropic_agent(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        model = payload.get("model", "")
        if not isinstance(model, str) or not model:
            return self._send_anthropic_error("model is required", status=400)

        hints = self._extract_agent_hints(payload)
        if "domain_hint" not in hints:
            model_domain = self._domain_hint_from_model(model)
            if model_domain:
                hints["domain_hint"] = model_domain

        messages = _anthropic_payload_to_openai_messages(payload)
        if not messages:
            return self._send_anthropic_error("messages are required", status=400)

        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("max_tokens", 100)

        tools, tool_choice = _extract_openai_tools(payload)

        if payload.get("stream"):
            if not proxy.config.allow_streaming:
                return self._send_anthropic_error("streaming not enabled", status=400)
            if not hasattr(proxy.agent, "stream_events"):
                return self._send_anthropic_error("streaming not supported by agent", status=400)
            return self._send_anthropic_agent_stream(
                proxy,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                complexity_hint=hints.get("complexity_hint"),
                domain_hint=hints.get("domain_hint"),
            )

        try:
            result = proxy._maybe_call_agent(
                "run",
                query=proxy._agent_query(messages),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                **hints,
            )
        except Exception as exc:
            return self._send_anthropic_error(str(exc), status=500)

        response = _build_anthropic_response(model, result)
        self._send_json(response)

    def _send_anthropic_agent_stream(
        self,
        proxy: RoutingProxy,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        complexity_hint: str | None = None,
        domain_hint: str | None = None,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()

        start_event = {
            "type": "message_start",
            "message": {
                "id": "msg_cascadeflow",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        }
        self._send_event("message_start", start_event)

        event_queue: queue.Queue[object] = queue.Queue()
        sentinel = object()

        async def _produce() -> None:
            async for event in proxy.agent.stream_events(
                query=proxy._agent_query(messages),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                complexity_hint=complexity_hint,
                domain_hint=domain_hint,
                tools=tools,
                tool_choice=tool_choice,
            ):
                event_queue.put(event)
            event_queue.put(sentinel)

        future = proxy.submit_coroutine(_produce())

        while True:
            item = event_queue.get()
            if item is sentinel:
                break
            event = item
            if getattr(getattr(event, "type", None), "value", None) != "chunk":
                continue

            content = getattr(event, "content", None)
            if not isinstance(content, str):
                continue

            delta_event = {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": content},
            }
            self._send_event("content_block_delta", delta_event)

        try:
            future.result(timeout=1)
        except Exception:  # pragma: no cover
            pass

        self._send_event("message_stop", {"type": "message_stop"})
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    # ------------------------------------------------------------------
    # Streaming helpers (mock mode)
    # ------------------------------------------------------------------

    def _send_openai_stream(
        self, resolved: str, response_text: str, draft_accepted: bool, virtual_model: str
    ) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()

        chunk = {
            "id": "chatcmpl-proxy",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": resolved,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            "cascadeflow": {
                "virtual_model": virtual_model,
                "resolved_model": resolved,
                "draft_accepted": draft_accepted,
            },
        }

        data = json.dumps(chunk)
        self.wfile.write(f"data: {data}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_anthropic_stream(
        self, resolved: str, response_text: str, draft_accepted: bool, virtual_model: str
    ) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()

        start_event = {
            "type": "message_start",
            "message": {
                "id": "msg_proxy",
                "type": "message",
                "role": "assistant",
                "model": resolved,
                "content": [],
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
            "cascadeflow": {
                "virtual_model": virtual_model,
                "resolved_model": resolved,
                "draft_accepted": draft_accepted,
            },
        }
        self._send_event("message_start", start_event)

        delta_event = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": response_text},
        }
        self._send_event("content_block_delta", delta_event)

        self._send_event("message_stop", {"type": "message_stop"})
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.wfile.write(f"event: {event_type}\n".encode())
        self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())

    # ------------------------------------------------------------------
    # Error + JSON helpers
    # ------------------------------------------------------------------

    def _send_openai_error(self, message: str, status: int = 400) -> None:
        payload = {
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "param": None,
                "code": None,
            }
        }
        self._send_json(payload, status=status)

    def _send_anthropic_error(self, message: str, status: int = 400) -> None:
        payload = {"error": {"type": "invalid_request_error", "message": message}}
        self._send_json(payload, status=status)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        if proxy.config.include_gateway_metadata and isinstance(payload, dict):
            info = self._gateway_info(proxy)
            cf = payload.get("cascadeflow")
            if isinstance(cf, dict):
                cf.setdefault("gateway", info)
            else:
                payload.setdefault("cascadeflow_gateway", info)

        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers(proxy)
        self._send_gateway_headers(proxy)
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self, proxy: RoutingProxy) -> None:
        allow_origin = proxy.config.cors_allow_origin
        if not allow_origin:
            return
        self.send_header("Access-Control-Allow-Origin", allow_origin)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-API-Key, anthropic-version, "
            "OpenAI-Organization, OpenAI-Project, X-Cascadeflow-Domain, X-Cascadeflow-Complexity, "
            "X-Correlation-Id",
        )
        self.send_header(
            "Access-Control-Expose-Headers",
            "X-Cascadeflow-Gateway, X-Cascadeflow-Gateway-Version, X-Cascadeflow-Gateway-Mode, "
            "X-Cascadeflow-Gateway-API, X-Cascadeflow-Gateway-Endpoint",
        )
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_gateway_headers(self, proxy: RoutingProxy) -> None:
        if not proxy.config.include_gateway_headers:
            return
        info = self._gateway_info(proxy)
        self.send_header("X-Cascadeflow-Gateway", "cascadeflow")
        self.send_header("X-Cascadeflow-Gateway-Version", info["version"])
        self.send_header("X-Cascadeflow-Gateway-Mode", info["mode"])
        self.send_header("X-Cascadeflow-Gateway-API", info["api"])
        self.send_header("X-Cascadeflow-Gateway-Endpoint", info["endpoint"])

    def _gateway_info(self, proxy: RoutingProxy) -> dict[str, str]:
        api = getattr(self, "_gateway_api", None) or "gateway"
        endpoint = getattr(self, "_gateway_endpoint", None) or self._normalize_api_path().lstrip(
            "/"
        )
        mode = getattr(self, "_gateway_mode", None) or (
            "agent" if proxy.agent is not None else "mock"
        )
        return {
            "api": str(api),
            "endpoint": str(endpoint),
            "mode": str(mode),
            "version": str(self.server_version),
        }

    def _build_openai_models_list(self, proxy: RoutingProxy) -> dict[str, Any]:
        now = int(time.time())
        ids = ["cascadeflow", *sorted(proxy.config.virtual_models.keys())]
        return {
            "object": "list",
            "data": [self._build_openai_model_object(model_id, created=now) for model_id in ids],
        }

    def _build_openai_model_object(
        self, model_id: str, created: int | None = None
    ) -> dict[str, Any]:
        return {
            "id": model_id,
            "object": "model",
            "created": int(time.time()) if created is None else created,
            "owned_by": "cascadeflow",
        }
