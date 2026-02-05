"""
Message normalization utilities for cascadeflow.

Provides consistent handling for multi-turn message history across providers.
"""

from typing import Any, Optional


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


def is_multi_turn_messages(messages: list[dict[str, Any]]) -> bool:
    """Return True if the message list represents a multi-turn conversation."""
    normalized = normalize_messages(messages)
    if not normalized:
        return False
    user_count = sum(1 for message in normalized if message["role"].lower() == "user")
    return user_count >= 2


def is_multi_turn_prompt(prompt: str) -> bool:
    """
    Detect if a prompt contains multi-turn conversation markers.

    Uses lightweight heuristics (history markers, turn markers, user/assistant pairs).
    """
    if not prompt:
        return False

    prompt_lower = prompt.lower()

    multi_turn_markers = [
        "previous conversation:",
        "conversation history:",
        "conversation so far:",
        "prior context:",
        "chat history:",
        "dialogue history:",
        "earlier in the conversation:",
    ]
    if any(marker in prompt_lower for marker in multi_turn_markers):
        return True

    turn_markers = [
        "turn 1:",
        "turn 2:",
        "[turn 1]",
        "[turn 2]",
        "turn 1\n",
        "turn 2\n",
    ]
    if any(marker in prompt_lower for marker in turn_markers):
        return True

    user_markers = ["user:", "human:", "question:"]
    assistant_markers = ["assistant:", "ai:", "answer:"]
    user_count = sum(prompt_lower.count(marker) for marker in user_markers)
    assistant_count = sum(prompt_lower.count(marker) for marker in assistant_markers)
    if user_count >= 2 and assistant_count >= 1:
        return True

    current_turn_markers = ["current turn:", "current question:", "now answer:", "now respond:"]
    has_user_assistant = any(
        user in prompt_lower and assistant in prompt_lower
        for user in user_markers
        for assistant in assistant_markers
    )
    if has_user_assistant and any(marker in prompt_lower for marker in current_turn_markers):
        return True

    return False


def detect_multi_turn(prompt: str, messages: Optional[list[dict[str, Any]]] = None) -> bool:
    """Detect multi-turn conversation from messages or prompt text."""
    if messages and is_multi_turn_messages(messages):
        return True
    return is_multi_turn_prompt(prompt)
