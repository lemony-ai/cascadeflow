"""Deterministic task classifier for Hermes Agent delegation routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity

from .types import HermesDelegationRequest

DOMAIN_KEYWORDS = {
    "debugging": {
        "traceback",
        "stack trace",
        "failing test",
        "regression",
        "root cause",
        "bug",
        "debug",
    },
    "code": {
        "code",
        "implement",
        "refactor",
        "typescript",
        "python",
        "api",
        "schema",
        "database",
        "pull request",
        "unit test",
    },
    "research": {
        "research",
        "investigate",
        "summarize",
        "compare",
        "source",
        "citations",
        "web",
        "market",
    },
    "data": {
        "dataset",
        "sql",
        "analytics",
        "csv",
        "postgres",
        "warehouse",
        "metrics",
        "dashboard",
    },
    "creative": {
        "copy",
        "creative",
        "design",
        "story",
        "brand",
        "headline",
        "script",
        "visual",
    },
    "ops": {
        "deploy",
        "docker",
        "kubernetes",
        "ci",
        "workflow",
        "infrastructure",
        "logs",
        "incident",
    },
    "legal": {"legal", "contract", "law", "compliance", "terms", "privacy"},
    "medical": {"medical", "health", "diagnosis", "treatment", "patient", "clinical"},
    "finance": {"finance", "financial", "investment", "tax", "invoice", "revenue"},
}

HIGH_STAKES_DOMAINS = {"legal", "medical", "finance"}
TOOLSET_DOMAIN_HINTS = {
    "terminal": "code",
    "file": "code",
    "git": "code",
    "browser": "research",
    "web": "research",
}


@dataclass(frozen=True)
class HermesTaskClassification:
    domain: str
    complexity: str
    confidence: float
    reason: str
    topic: Optional[str] = None


class HermesTaskClassifier:
    """Classify Hermes delegated tasks by domain and complexity."""

    def __init__(self, complexity_detector: Optional[ComplexityDetector] = None):
        self.complexity_detector = complexity_detector or ComplexityDetector()

    def classify(self, request: HermesDelegationRequest) -> HermesTaskClassification:
        text = request.text_for_classification()
        lowered = text.lower()
        domain, domain_confidence, domain_reason = self._detect_domain(
            lowered,
            request.toolsets,
        )
        complexity, complexity_confidence = self._detect_complexity(text)
        confidence = max(domain_confidence, complexity_confidence * 0.75)
        if domain == "general" and complexity in {"trivial", "simple"}:
            domain = "simple"
            domain_reason = "simple_complexity"
            confidence = max(confidence, 0.72)
        return HermesTaskClassification(
            domain=domain,
            topic=domain if domain != "simple" else None,
            complexity=complexity,
            confidence=max(0.0, min(1.0, confidence)),
            reason=domain_reason,
        )

    def _detect_domain(self, lowered: str, toolsets: tuple[str, ...]) -> tuple[str, float, str]:
        scores: dict[str, int] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            hits = sum(1 for keyword in keywords if keyword in lowered)
            if hits:
                scores[domain] = hits

        for toolset in toolsets:
            hinted = TOOLSET_DOMAIN_HINTS.get(toolset)
            if hinted:
                scores[hinted] = scores.get(hinted, 0) + 1

        if not scores:
            return "general", 0.35, "no_domain_markers"

        domain = max(scores, key=scores.get)
        confidence = min(0.95, 0.55 + (scores[domain] * 0.12))
        return domain, confidence, "keyword_and_toolset_match"

    def _detect_complexity(self, text: str) -> tuple[str, float]:
        try:
            complexity, confidence = self.complexity_detector.detect(text)
        except Exception:
            return "moderate", 0.4
        if isinstance(complexity, QueryComplexity):
            complexity_value = complexity.value
        else:
            complexity_value = str(complexity)
        return complexity_value, max(0.0, min(1.0, float(confidence or 0.0)))
