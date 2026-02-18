"""LangChain-oriented CascadeAgent wrapper with closed tool loops."""

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from .wrapper import CascadeFlow

ToolHandler = Callable[[dict[str, Any], dict[str, Any], list[BaseMessage]], Any]


@dataclass
class CascadeAgentResult:
    """Result object returned by CascadeAgent run/arun."""

    message: AIMessage
    messages: list[BaseMessage]
    steps: int
    status: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class CascadeAgent:
    """Simple LangChain agent loop around a chat model (or CascadeFlow model).

    The loop calls the model, executes returned tool calls via provided handlers,
    appends tool results as ToolMessages, and repeats until no tools are requested
    or max steps is reached.
    """

    def __init__(
        self,
        model: Optional[BaseChatModel] = None,
        *,
        cascade: Optional[dict[str, Any]] = None,
        max_steps: int = 8,
        tool_handlers: Optional[dict[str, ToolHandler]] = None,
    ):
        if model is None:
            if cascade is None:
                raise ValueError("Provide either 'model' or 'cascade' config")
            model = CascadeFlow(**cascade)

        self.model = model
        self.max_steps = max_steps
        self.tool_handlers = tool_handlers or {}

    def run(
        self,
        query: Any,
        *,
        system_prompt: Optional[str] = None,
        max_steps: Optional[int] = None,
        tool_handlers: Optional[dict[str, ToolHandler]] = None,
        **kwargs: Any,
    ) -> CascadeAgentResult:
        messages = self._coerce_messages(query, system_prompt=system_prompt)
        handlers = tool_handlers or self.tool_handlers
        limit = max_steps or self.max_steps
        all_tool_calls: list[dict[str, Any]] = []

        for step in range(1, limit + 1):
            response = self.model.invoke(messages, **kwargs)
            ai_message = self._coerce_ai_message(response)
            messages.append(ai_message)

            tool_calls = self._extract_tool_calls(ai_message)
            if not tool_calls:
                return CascadeAgentResult(
                    message=ai_message,
                    messages=messages,
                    steps=step,
                    status="completed",
                    tool_calls=all_tool_calls,
                )

            all_tool_calls.extend(tool_calls)
            for i, call in enumerate(tool_calls):
                tool_message = self._execute_tool_call_sync(call, handlers, messages, step, i)
                messages.append(tool_message)

        return CascadeAgentResult(
            message=self._latest_ai_message(messages),
            messages=messages,
            steps=limit,
            status="max_steps_reached",
            tool_calls=all_tool_calls,
        )

    async def arun(
        self,
        query: Any,
        *,
        system_prompt: Optional[str] = None,
        max_steps: Optional[int] = None,
        tool_handlers: Optional[dict[str, ToolHandler]] = None,
        **kwargs: Any,
    ) -> CascadeAgentResult:
        messages = self._coerce_messages(query, system_prompt=system_prompt)
        handlers = tool_handlers or self.tool_handlers
        limit = max_steps or self.max_steps
        all_tool_calls: list[dict[str, Any]] = []

        for step in range(1, limit + 1):
            response = await self.model.ainvoke(messages, **kwargs)
            ai_message = self._coerce_ai_message(response)
            messages.append(ai_message)

            tool_calls = self._extract_tool_calls(ai_message)
            if not tool_calls:
                return CascadeAgentResult(
                    message=ai_message,
                    messages=messages,
                    steps=step,
                    status="completed",
                    tool_calls=all_tool_calls,
                )

            all_tool_calls.extend(tool_calls)
            for i, call in enumerate(tool_calls):
                tool_message = await self._execute_tool_call_async(call, handlers, messages, step, i)
                messages.append(tool_message)

        return CascadeAgentResult(
            message=self._latest_ai_message(messages),
            messages=messages,
            steps=limit,
            status="max_steps_reached",
            tool_calls=all_tool_calls,
        )

    def _coerce_messages(self, query: Any, *, system_prompt: Optional[str]) -> list[BaseMessage]:
        out: list[BaseMessage] = []

        if system_prompt:
            out.append(SystemMessage(content=system_prompt))

        if isinstance(query, str):
            out.append(HumanMessage(content=query))
            return out

        if isinstance(query, BaseMessage):
            out.append(query)
            return out

        if isinstance(query, list):
            for msg in query:
                coerced = self._coerce_message(msg)
                if coerced is not None:
                    out.append(coerced)
            return out

        out.append(HumanMessage(content=str(query)))
        return out

    def _coerce_message(self, value: Any) -> Optional[BaseMessage]:
        if isinstance(value, BaseMessage):
            return value

        if not isinstance(value, dict):
            return HumanMessage(content=str(value))

        role = str(value.get("role", "user"))
        content = value.get("content", "")

        if role == "system":
            return SystemMessage(content=str(content))
        if role == "assistant":
            return AIMessage(
                content=str(content),
                tool_calls=value.get("tool_calls") or value.get("toolCalls") or [],
            )
        if role == "tool":
            return ToolMessage(
                content=self._serialize_tool_output(content),
                tool_call_id=str(value.get("tool_call_id") or value.get("toolCallId") or "tool"),
                name=str(value.get("name") or "tool"),
            )
        return HumanMessage(content=str(content))

    def _coerce_ai_message(self, response: Any) -> AIMessage:
        if isinstance(response, AIMessage):
            return response
        if isinstance(response, BaseMessage):
            return AIMessage(
                content=response.content if isinstance(response.content, str) else str(response.content),
                additional_kwargs=getattr(response, "additional_kwargs", {}),
                tool_calls=getattr(response, "tool_calls", None),
                response_metadata=getattr(response, "response_metadata", {}),
            )
        return AIMessage(content=str(response))

    def _extract_tool_calls(self, message: AIMessage) -> list[dict[str, Any]]:
        calls = getattr(message, "tool_calls", None)
        if isinstance(calls, list):
            return [c for c in calls if isinstance(c, dict)]

        additional = getattr(message, "additional_kwargs", {}) or {}
        raw = additional.get("tool_calls")
        if isinstance(raw, list):
            out: list[dict[str, Any]] = []
            for call in raw:
                if not isinstance(call, dict):
                    continue
                function = call.get("function") if isinstance(call.get("function"), dict) else {}
                name = call.get("name") or function.get("name")
                arguments = function.get("arguments")
                parsed_args: dict[str, Any]
                if isinstance(arguments, str):
                    try:
                        parsed_args = json.loads(arguments)
                    except Exception:
                        parsed_args = {"raw": arguments}
                elif isinstance(arguments, dict):
                    parsed_args = arguments
                else:
                    parsed_args = {}
                out.append({"id": call.get("id"), "name": name, "args": parsed_args})
            return out

        return []

    def _execute_tool_call_sync(
        self,
        call: dict[str, Any],
        handlers: dict[str, ToolHandler],
        messages: list[BaseMessage],
        step: int,
        index: int,
    ) -> ToolMessage:
        name = str(call.get("name") or "tool")
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        tool_call_id = str(call.get("id") or f"tool_{step}_{index}")
        handler = handlers.get(name)

        if handler is None:
            content = f"Tool '{name}' is not available"
        else:
            try:
                result = self._invoke_handler_sync(handler, args, call, messages)
                content = self._serialize_tool_output(result)
            except Exception as exc:
                content = f"Tool '{name}' execution failed: {exc}"

        return ToolMessage(content=content, tool_call_id=tool_call_id, name=name)

    async def _execute_tool_call_async(
        self,
        call: dict[str, Any],
        handlers: dict[str, ToolHandler],
        messages: list[BaseMessage],
        step: int,
        index: int,
    ) -> ToolMessage:
        name = str(call.get("name") or "tool")
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        tool_call_id = str(call.get("id") or f"tool_{step}_{index}")
        handler = handlers.get(name)

        if handler is None:
            content = f"Tool '{name}' is not available"
        else:
            try:
                result = self._invoke_handler_flexible(handler, args, call, messages)
                if inspect.isawaitable(result):
                    result = await result
                content = self._serialize_tool_output(result)
            except Exception as exc:
                content = f"Tool '{name}' execution failed: {exc}"

        return ToolMessage(content=content, tool_call_id=tool_call_id, name=name)

    def _invoke_handler_sync(
        self,
        handler: ToolHandler,
        args: dict[str, Any],
        call: dict[str, Any],
        messages: list[BaseMessage],
    ) -> Any:
        result = self._invoke_handler_flexible(handler, args, call, messages)
        if inspect.isawaitable(result):
            raise RuntimeError(
                "Async tool handler used in run(). Use arun() or provide sync handlers only."
            )
        return result

    def _invoke_handler_flexible(
        self,
        handler: ToolHandler,
        args: dict[str, Any],
        call: dict[str, Any],
        messages: list[BaseMessage],
    ) -> Any:
        try:
            return handler(args, call, messages)
        except TypeError:
            pass

        try:
            return handler(args, call)
        except TypeError:
            pass

        try:
            return handler(args)
        except TypeError:
            return handler()

    def _serialize_tool_output(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        try:
            return json.dumps(value, ensure_ascii=True)
        except Exception:
            return str(value)

    def _latest_ai_message(self, messages: list[BaseMessage]) -> AIMessage:
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return msg
        return AIMessage(content="")
