"""
OpenClaw pre-router classifier.

Classifies OpenClaw-native requests/events using method/payload hints only.
Explicit tags (from skills) should take precedence when provided.
"""

from dataclasses import dataclass
from typing import Any, Optional

OPENCLAW_NATIVE_CATEGORIES = {
    "heartbeat",
    "voice",
    "image_understanding",
    "web_search",
    "brain",
    "coding",
    "content",
    "cron",
}

CATEGORY_TO_DOMAIN = {
    "coding": "code",
    "image_understanding": "multimodal",
    "brain": "general",
    "cron": "general",
}

HEARTBEAT_METHODS = {
    "last-heartbeat",
    "set-heartbeats",
    "system-presence",
    "system-event",
}

HEARTBEAT_EVENTS = {
    "heartbeat",
}

VOICE_METHOD_PREFIXES = ("tts.", "voicewake.")
VOICE_METHODS = {"talk.mode"}
VOICE_EVENTS = {"talk.mode", "voicewake.changed"}

WEB_SEARCH_METHODS = {"browser.request"}
CRON_METHOD_PREFIXES = ("cron.",)
CRON_EVENTS = {"cron"}


@dataclass(frozen=True)
class OpenClawRouteHint:
    category: str
    confidence: float
    reason: str
    cascadeflow_domain: Optional[str] = None


def extract_explicit_tags(params: Optional[dict[str, Any]], payload: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Extract explicit cascadeflow tags from OpenClaw params/payload."""
    params = params or {}
    payload = payload or {}

    for source in (params, payload):
        cascadeflow = source.get("cascadeflow")
        if isinstance(cascadeflow, dict):
            return cascadeflow

    return {}


def classify_openclaw_frame(
    method: Optional[str] = None,
    event: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
) -> Optional[OpenClawRouteHint]:
    """Return a route hint for OpenClaw-native categories, if deterministic."""
    explicit = extract_explicit_tags(params, payload)
    explicit_category = explicit.get("category") if isinstance(explicit, dict) else None
    if explicit_category in OPENCLAW_NATIVE_CATEGORIES:
        return OpenClawRouteHint(
            category=explicit_category,
            confidence=1.0,
            reason="explicit_tag",
            cascadeflow_domain=CATEGORY_TO_DOMAIN.get(explicit_category),
        )

    method = (method or "").strip()
    event = (event or "").strip()

    if method in HEARTBEAT_METHODS or event in HEARTBEAT_EVENTS:
        return OpenClawRouteHint(
            category="heartbeat",
            confidence=0.95,
            reason="heartbeat_method_or_event",
        )

    if method.startswith(CRON_METHOD_PREFIXES) or event in CRON_EVENTS:
        return OpenClawRouteHint(
            category="cron",
            confidence=0.9,
            reason="cron_method_or_event",
        )

    if method.startswith(VOICE_METHOD_PREFIXES) or method in VOICE_METHODS or event in VOICE_EVENTS:
        return OpenClawRouteHint(
            category="voice",
            confidence=0.9,
            reason="voice_method_or_event",
        )

    if method in WEB_SEARCH_METHODS:
        return OpenClawRouteHint(
            category="web_search",
            confidence=0.8,
            reason="browser_request",
        )

    if _has_image_attachment(params) or _has_image_attachment(payload):
        return OpenClawRouteHint(
            category="image_understanding",
            confidence=0.85,
            reason="image_attachment",
            cascadeflow_domain=CATEGORY_TO_DOMAIN.get("image_understanding"),
        )

    category_hint = _category_from_payload(params) or _category_from_payload(payload)
    if category_hint:
        return OpenClawRouteHint(
            category=category_hint,
            confidence=0.7,
            reason="payload_category_hint",
            cascadeflow_domain=CATEGORY_TO_DOMAIN.get(category_hint),
        )

    return None


def _category_from_payload(data: Optional[dict[str, Any]]) -> Optional[str]:
    if not isinstance(data, dict):
        return None

    for key in ("category", "domain", "label", "lane"):
        value = data.get(key)
        if isinstance(value, str):
            value_lower = value.strip().lower()
            if value_lower in OPENCLAW_NATIVE_CATEGORIES:
                return value_lower

    return None


def _has_image_attachment(data: Optional[dict[str, Any]]) -> bool:
    if not isinstance(data, dict):
        return False

    attachments = data.get("attachments") or data.get("attachment") or []
    if isinstance(attachments, dict):
        attachments = [attachments]

    if not isinstance(attachments, list):
        return False

    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        for key in ("type", "content_type", "mime", "mime_type"):
            value = attachment.get(key)
            if isinstance(value, str) and "image" in value.lower():
                return True
        url = attachment.get("url") or attachment.get("image_url") or attachment.get("mediaUrl")
        if isinstance(url, str) and _looks_like_image(url):
            return True

    return False


def _looks_like_image(url: str) -> bool:
    lowered = url.lower()
    return lowered.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"))


__all__ = [
    "OpenClawRouteHint",
    "OPENCLAW_NATIVE_CATEGORIES",
    "CATEGORY_TO_DOMAIN",
    "extract_explicit_tags",
    "classify_openclaw_frame",
]
