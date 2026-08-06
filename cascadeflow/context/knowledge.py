"""Versioned, provider-neutral knowledge handoff.

Provider prompt caches are an optimization, not a source of conversation state.
Every request is given the complete immutable knowledge snapshot it selected.  A
stable rendering then lets providers reuse prefix caches when they support them,
without changing correctness for providers that do not.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

CacheTTL = Literal["5m", "1h"]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_label(value: str) -> str:
    """Keep prompt metadata deterministic and free of delimiter injection."""
    return re.sub(r"[^a-zA-Z0-9._:/-]+", "-", value.strip()).strip("-") or "knowledge"


@dataclass(frozen=True)
class KnowledgeSnapshot:
    """An immutable knowledge version selected for one request.

    ``key`` names the logical knowledge set. ``version`` should change whenever
    its content changes; when omitted it is derived from the content digest.
    This prevents a caller from accidentally reusing stale provider-cache state.
    """

    content: str
    key: str = "default"
    version: Optional[str] = None
    enable_provider_cache: bool = True
    cache_ttl: CacheTTL = "5m"

    def __post_init__(self) -> None:
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("KnowledgeSnapshot.content must be a non-empty string")
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("KnowledgeSnapshot.key must be a non-empty string")
        if self.cache_ttl not in ("5m", "1h"):
            raise ValueError("KnowledgeSnapshot.cache_ttl must be '5m' or '1h'")

    @property
    def content_digest(self) -> str:
        return _digest(self.content)

    @property
    def resolved_version(self) -> str:
        return _safe_label(self.version or self.content_digest[:16])

    @property
    def identity(self) -> str:
        return f"{_safe_label(self.key)}:{self.resolved_version}"


@dataclass(frozen=True)
class PreparedKnowledge:
    """Stable prompt material plus provider-cache routing metadata."""

    identity: str
    content_digest: str
    system_prefix: str
    enable_provider_cache: bool
    cache_ttl: CacheTTL

    @property
    def prompt_cache_key(self) -> str:
        # Bind native caches to both the caller's version and the actual content.
        # This remains safe even after local LRU eviction or process restart.
        material = f"{self.identity}:{self.content_digest}"
        return f"cascadeflow:knowledge:{_digest(material)[:24]}"

    def metadata(self, *, local_cache_hit: bool) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "content_digest": self.content_digest,
            "local_cache_hit": local_cache_hit,
            "provider_cache_enabled": self.enable_provider_cache,
            "cache_ttl": self.cache_ttl,
        }


KnowledgeInput = Union[str, KnowledgeSnapshot]


class KnowledgeCache:
    """Small LRU for compiled immutable snapshots.

    This cache deliberately has no global "active knowledge" pointer. Selection is
    request-scoped, which makes concurrent requests and knowledge switches safe.
    """

    def __init__(self, max_entries: int = 128):
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple[str, str, str, bool, CacheTTL], PreparedKnowledge] = (
            OrderedDict()
        )
        self._version_digests: dict[tuple[str, str], str] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def prepare(self, value: KnowledgeInput) -> tuple[PreparedKnowledge, bool]:
        snapshot = value if isinstance(value, KnowledgeSnapshot) else KnowledgeSnapshot(value)
        version_key = (_safe_label(snapshot.key), snapshot.resolved_version)
        digest = snapshot.content_digest
        cache_key = (
            version_key[0],
            version_key[1],
            digest,
            snapshot.enable_provider_cache,
            snapshot.cache_ttl,
        )

        with self._lock:
            prior_digest = self._version_digests.get(version_key)
            if prior_digest is not None and prior_digest != digest:
                raise ValueError(
                    "Knowledge version collision: the same key/version was reused with "
                    "different content. Change KnowledgeSnapshot.version to prevent stale context."
                )

            prepared = self._entries.get(cache_key)
            if prepared is not None:
                self._entries.move_to_end(cache_key)
                self._hits += 1
                return prepared, True

            identity = f"{version_key[0]}:{version_key[1]}"
            prefix = (
                f'<cascadeflow_knowledge version="{identity}">\n'
                f"{snapshot.content.strip()}\n"
                "</cascadeflow_knowledge>"
            )
            prepared = PreparedKnowledge(
                identity=identity,
                content_digest=digest,
                system_prefix=prefix,
                enable_provider_cache=snapshot.enable_provider_cache,
                cache_ttl=snapshot.cache_ttl,
            )
            self._entries[cache_key] = prepared
            self._version_digests[version_key] = digest
            self._misses += 1

            if len(self._entries) > self.max_entries:
                evicted_key, evicted = self._entries.popitem(last=False)
                if not any(item.identity == evicted.identity for item in self._entries.values()):
                    self._version_digests.pop((evicted_key[0], evicted_key[1]), None)
                self._evictions += 1

            return prepared, False

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._version_digests.clear()

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
            }


def provider_cache_kwargs(provider: str, prepared: Optional[PreparedKnowledge]) -> dict[str, Any]:
    """Translate a neutral cache intent into supported provider request fields.

    Unknown and self-hosted providers receive no special arguments. They still get
    the exact knowledge prefix, so behavior remains correct without native caching.
    """
    if prepared is None or not prepared.enable_provider_cache:
        return {}

    provider = provider.lower()
    if provider == "openai":
        return {
            "prompt_cache_key": prepared.prompt_cache_key,
            # Consumed by OpenAIProvider and never forwarded as an API field.
            # GPT-5.6+ needs the exact end of the stable prefix so it can place
            # an explicit breakpoint before the changing query suffix.
            "_cascadeflow_knowledge_cache_prefix": prepared.system_prefix,
        }
    if provider == "anthropic":
        cache_control: dict[str, str] = {"type": "ephemeral"}
        if prepared.cache_ttl == "1h":
            cache_control["ttl"] = "1h"
        return {"cache_control": cache_control}
    return {}
