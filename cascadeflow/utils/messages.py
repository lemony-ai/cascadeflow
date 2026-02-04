"""
Message normalization utilities for cascadeflow.

Provides consistent handling for multi-turn message history across providers.
"""

from typing import Any


def _extract_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(part for part in parts if part).strip()
    if content is None:
        return ""
    return str(content)


def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize message dicts to ensure role/content are plain strings."""
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = _extract_content(message.get("content", ""))
        normalized.append({"role": role, "content": content})
    return normalized


def messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    """Convert messages into a deterministic prompt string."""
    normalized = normalize_messages(messages)
    lines: list[str] = []
    for message in normalized:
        role = message["role"].strip().capitalize() or "User"
        content = message["content"].strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def get_last_user_message(messages: list[dict[str, Any]]) -> str:
    """Return the most recent user message content, if available."""
    normalized = normalize_messages(messages)
    for message in reversed(normalized):
        if message["role"].lower() == "user":
            return message["content"].strip()
    if normalized:
        return normalized[-1]["content"].strip()
    return ""
