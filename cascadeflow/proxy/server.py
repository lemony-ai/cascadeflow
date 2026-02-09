"""
Minimal HTTP server for cascadeflow-compatible APIs.

This module intentionally supports two modes:
1) Mock mode (default): deterministic local responses for unit tests.
2) Agent mode: if an agent is provided, routes requests through `agent.run()` /
   `agent.stream_events()` using the OpenAI-compatible schema.

Supported endpoints:
- POST /v1/chat/completions (OpenAI format)
- POST /v1/messages (Anthropic format)
- GET  /health
- GET  /stats (best-effort: `agent.telemetry.export_to_dict()` if available)

Notes:
- This uses `http.server` to stay dependency-light and easy to embed.
- Streaming uses SSE framing similar to OpenAI/Anthropic.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import queue
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from cascadeflow.telemetry.cost_tracker import CostTracker


@dataclass
class ProxyConfig:
    """Configuration for the routing proxy."""

    host: str = "127.0.0.1"
    port: int = 0
    allow_streaming: bool = True
    enable_classifier: bool = True
    default_domain_confidence: float = 0.8
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
    """HTTP server exposing OpenAI/Anthropic-compatible endpoints."""

    def __init__(
        self,
        config: ProxyConfig | None = None,
        cost_tracker: CostTracker | None = None,
        agent: Any | None = None,
    ) -> None:
        self.config = config or ProxyConfig()
        self.cost_tracker = cost_tracker or CostTracker()
        self.agent = agent
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

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
        # Create a dedicated loop to run agent coroutines from the sync HTTP handler.
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

    def _agent_query(self, messages: list[dict[str, Any]]) -> str:
        # Prefer the last user message (OpenAI style). Fallback to concatenated content.
        try:
            from cascadeflow.utils.messages import get_last_user_message

            return get_last_user_message(messages) or self.extract_prompt_text(messages)
        except Exception:
            return self.extract_prompt_text(messages)

    def _agent_has_streaming(self) -> bool:
        return bool(self.agent and hasattr(self.agent, "stream_events"))

    def _maybe_call_agent(self, func_name: str, **kwargs):
        if not self.agent or not hasattr(self.agent, func_name):
            raise RuntimeError(f"Agent does not support '{func_name}'")
        fn = getattr(self.agent, func_name)
        result = fn(**kwargs)
        if inspect.isawaitable(result):
            return self.run_coroutine(result)
        return result


def _parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return dict(parsed)
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_result_metadata(result: Any) -> dict[str, Any]:
    """
    Ensure the API response exposes a stable cascadeflow.metadata contract.

    The OpenClaw integration tests expect these keys to exist even for direct
    (non-cascaded) routes or when upstream providers omit certain fields.
    """
    meta: dict[str, Any] = {}
    if hasattr(result, "metadata") and isinstance(result.metadata, dict):
        meta = dict(result.metadata)

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

    prompt_tokens = meta.get("prompt_tokens")
    completion_tokens = meta.get("completion_tokens")
    total_tokens = meta.get("total_tokens")
    tool_calls = meta.get("tool_calls")

    if total_tokens is None:
        prompt_tokens = prompt_tokens or 0
        completion_tokens = completion_tokens or 0
        total_tokens = prompt_tokens + completion_tokens

    message: dict[str, Any] = {"role": "assistant", "content": getattr(result, "content", "")}
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = "tool_calls" if tool_calls else "stop"
    model_used = getattr(result, "model_used", None)

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
        },
        "cascadeflow": {"model_used": model_used, "metadata": meta},
    }


def _extract_openai_tools(payload: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, Any | None]:
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

    if tools_payload is None:
        return None, tool_choice

    try:
        from cascadeflow.tools.formats import normalize_tools

        return normalize_tools(tools_payload), tool_choice
    except Exception:
        # If tooling helpers are missing, pass through and let the agent/provider handle.
        return tools_payload, tool_choice


def _extract_anthropic_tools(payload: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, Any | None]:
    tools_payload = payload.get("tools")
    tool_choice = payload.get("tool_choice")

    if isinstance(tool_choice, dict):
        choice_type = tool_choice.get("type")
        if choice_type in {"auto", "any"}:
            tool_choice = "auto"
        elif choice_type == "tool":
            name = tool_choice.get("name")
            if isinstance(name, str) and name:
                tool_choice = {"type": "function", "function": {"name": name}}

    if not isinstance(tools_payload, list) or not tools_payload:
        return None, tool_choice

    openai_tools: list[dict[str, Any]] = []
    for tool in tools_payload:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            continue
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description"),
                    "parameters": tool.get("input_schema") or tool.get("parameters") or {},
                },
            }
        )

    try:
        from cascadeflow.tools.formats import normalize_tools

        return normalize_tools(openai_tools), tool_choice
    except Exception:
        return openai_tools, tool_choice


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


def _build_anthropic_response(model: str, result: Any) -> dict[str, Any]:
    meta = _normalize_result_metadata(result)
    input_tokens = meta.get("prompt_tokens", meta.get("input_tokens", 0)) or 0
    output_tokens = meta.get("completion_tokens", meta.get("output_tokens", 0)) or 0

    content_blocks: list[dict[str, Any]] = []
    text = getattr(result, "content", "")
    if isinstance(text, str) and text:
        content_blocks.append({"type": "text", "text": text})

    tool_calls = meta.get("tool_calls")
    if isinstance(tool_calls, list):
        for idx, call in enumerate(tool_calls):
            if not isinstance(call, dict):
                continue
            call_id = call.get("id") or f"toolu_{idx}"
            name = None
            args: Any = {}
            if isinstance(call.get("function"), dict):
                name = call["function"].get("name")
                raw_args = call["function"].get("arguments")
                if isinstance(raw_args, str) and raw_args.strip():
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {"raw": raw_args}
                elif isinstance(raw_args, dict):
                    args = raw_args
            if not name:
                name = call.get("name")
            if isinstance(name, str) and name:
                content_blocks.append(
                    {"type": "tool_use", "id": call_id, "name": name, "input": args}
                )

    stop_reason = "tool_use" if tool_calls else "end_turn"
    model_used = getattr(result, "model_used", None)

    return {
        "id": "msg_cascadeflow",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "cascadeflow": {"model_used": model_used, "metadata": meta},
    }


def _maybe_build_openclaw_tags(
    *,
    method: Any,
    event: Any,
    params: dict[str, Any],
    metadata: dict[str, Any],
    enable_classifier: bool,
) -> tuple[dict[str, Any], Any | None]:
    try:
        from cascadeflow.integrations.openclaw.adapter import build_routing_decision

        decision = build_routing_decision(
            method=method if isinstance(method, str) else None,
            event=event if isinstance(event, str) else None,
            params=params,
            payload=metadata,
            enable_classifier=enable_classifier,
        )
        return (decision.tags or {}), decision.hint
    except Exception:
        return ({}, None)


def _resolve_domain_and_channel(
    *,
    tags: dict[str, Any],
    hint: Any | None,
    default_domain_confidence: float,
    metadata: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[str | None, float, str | None]:
    domain_hint = tags.get("domain") if isinstance(tags.get("domain"), str) else None
    if not domain_hint and hint is not None and getattr(hint, "cascadeflow_domain", None):
        domain_hint = getattr(hint, "cascadeflow_domain")
    if not domain_hint and isinstance(tags.get("category"), str):
        try:
            from cascadeflow.integrations.openclaw.pre_router import CATEGORY_TO_DOMAIN

            domain_hint = CATEGORY_TO_DOMAIN.get(tags.get("category"))
        except Exception:
            domain_hint = None

    channel = metadata.get("channel") or payload.get("channel")
    if not channel and isinstance(tags.get("channel"), str):
        channel = tags.get("channel")
    if not channel and isinstance(tags.get("category"), str):
        channel = tags.get("category")

    domain_confidence_hint = (
        float(getattr(hint, "confidence")) if hint is not None else float(default_domain_confidence)
    )

    return domain_hint, domain_confidence_hint, channel if isinstance(channel, str) else None


class ProxyRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for the routing proxy."""

    server_version = "CascadeFlowProxy/0.1"

    def do_GET(self) -> None:
        proxy: RoutingProxy = self.server.proxy  # type: ignore[attr-defined]
        if self.path == "/health":
            return self._send_json({"status": "ok"})

        if self.path.startswith("/stats"):
            telemetry = getattr(proxy.agent, "telemetry", None) if proxy.agent else None
            if telemetry is None or not hasattr(telemetry, "export_to_dict"):
                self.send_response(404)
                self.end_headers()
                return
            try:
                payload = telemetry.export_to_dict()
            except Exception as exc:
                return self._send_openai_error(f"Metrics export failed: {exc}", status=500)
            return self._send_json(payload)

        self.send_response(404)
        self.end_headers()

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
        if proxy.agent is not None:
            return self._handle_openai_agent(proxy, payload)

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
        if proxy.agent is not None:
            return self._handle_anthropic_agent(proxy, payload)

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

    def _handle_openai_agent(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return self._send_openai_error("Messages are required", status=400)

        model = payload.get("model", "cascadeflow")
        if not isinstance(model, str) or not model:
            model = "cascadeflow"

        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("max_tokens")
        if max_tokens is None:
            max_tokens = payload.get("max_completion_tokens", 100)

        tools, tool_choice = _extract_openai_tools(payload)
        stream = bool(payload.get("stream"))
        if stream and not proxy.config.allow_streaming:
            return self._send_openai_error("Streaming not enabled", status=400)

        metadata = _parse_metadata(payload.get("metadata"))
        method = metadata.get("method") or payload.get("method")
        event = metadata.get("event") or payload.get("event")

        tags, hint = _maybe_build_openclaw_tags(
            method=method,
            event=event,
            params=payload,
            metadata=metadata,
            enable_classifier=proxy.config.enable_classifier,
        )

        domain_hint, domain_confidence_hint, channel = _resolve_domain_and_channel(
            tags=tags,
            hint=hint,
            default_domain_confidence=proxy.config.default_domain_confidence,
            metadata=metadata,
            payload=payload,
        )

        kpi_flags = metadata.get("kpi_flags") if isinstance(metadata.get("kpi_flags"), dict) else {}
        tenant_id = metadata.get("tenant_id") or payload.get("tenant_id")
        tenant_id = tenant_id if isinstance(tenant_id, str) else None

        if stream:
            if not proxy._agent_has_streaming():
                return self._send_openai_error("Streaming not supported by agent", status=400)
            return self._send_openai_agent_stream(
                proxy,
                model=model,
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

        try:
            result = proxy._maybe_call_agent(
                "run",
                query=proxy._agent_query(messages),
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
        except Exception as exc:
            return self._send_openai_error(str(exc), status=500)

        response = _build_openai_response(model, result)
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
        tool_choice: Any | None,
        domain_hint: str | None,
        domain_confidence_hint: float,
        kpi_flags: dict[str, Any],
        tenant_id: str | None,
        channel: str | None,
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
                async for event in proxy.agent.stream_events(
                    query=proxy._agent_query(messages),
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

            chunk = {
                "id": "chatcmpl-cascadeflow",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            future.result(timeout=1)
        except Exception as exc:  # pragma: no cover - logging only
            error_box.setdefault("error", exc)

        if "error" in error_box:  # pragma: no cover - logging only
            self.log_error("Streaming error: %s", error_box["error"])

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _handle_anthropic_agent(self, proxy: RoutingProxy, payload: dict[str, Any]) -> None:
        model = payload.get("model", "")
        if not isinstance(model, str) or not model:
            return self._send_anthropic_error("model is required", status=400)

        messages = _anthropic_payload_to_openai_messages(payload)
        if not messages:
            return self._send_anthropic_error("messages are required", status=400)

        temperature = payload.get("temperature", 0.7)
        max_tokens = payload.get("max_tokens", 100)

        tools, tool_choice = _extract_anthropic_tools(payload)
        stream = bool(payload.get("stream"))
        if stream and not proxy.config.allow_streaming:
            return self._send_anthropic_error("streaming not enabled", status=400)

        metadata = _parse_metadata(payload.get("metadata"))
        method = metadata.get("method") or payload.get("method")
        event = metadata.get("event") or payload.get("event")

        tags, hint = _maybe_build_openclaw_tags(
            method=method,
            event=event,
            params=payload,
            metadata=metadata,
            enable_classifier=proxy.config.enable_classifier,
        )

        domain_hint, domain_confidence_hint, channel = _resolve_domain_and_channel(
            tags=tags,
            hint=hint,
            default_domain_confidence=proxy.config.default_domain_confidence,
            metadata=metadata,
            payload=payload,
        )

        kpi_flags = metadata.get("kpi_flags") if isinstance(metadata.get("kpi_flags"), dict) else {}
        tenant_id = metadata.get("tenant_id") or payload.get("tenant_id")
        tenant_id = tenant_id if isinstance(tenant_id, str) else None

        if stream:
            if not proxy._agent_has_streaming():
                return self._send_anthropic_error("streaming not supported by agent", status=400)
            return self._send_anthropic_agent_stream(
                proxy,
                model=model,
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

        try:
            result = proxy._maybe_call_agent(
                "run",
                query=proxy._agent_query(messages),
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
        tool_choice: Any | None,
        domain_hint: str | None,
        domain_confidence_hint: float,
        kpi_flags: dict[str, Any],
        tenant_id: str | None,
        channel: str | None,
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
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
            try:
                async for event in proxy.agent.stream_events(
                    query=proxy._agent_query(messages),
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
            finally:
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
        except Exception:  # pragma: no cover - best-effort
            pass

        stop_event = {"type": "message_stop"}
        self._send_event("message_stop", stop_event)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_openai_stream(
        self, resolved: str, response_text: str, draft_accepted: bool, virtual_model: str
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
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
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
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

        stop_event = {"type": "message_stop"}
        self._send_event("message_stop", stop_event)

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.wfile.write(f"event: {event_type}\n".encode())
        self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())

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

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
