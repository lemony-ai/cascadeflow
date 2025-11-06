"""
Content moderation for cascadeflow.

Provides basic content moderation using regex patterns and keyword matching.
For v0.2.1, we use simple pattern matching. Future versions can integrate
with LiteLLM's moderation APIs.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ModerationResult:
    """Result from content moderation check"""

    is_safe: bool
    violations: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    confidence: float = 1.0


class ContentModerator:
    """
    Basic content moderator using regex patterns.

    Detects potentially harmful content categories:
    - Hate speech
    - Violence
    - Self-harm
    - Sexual content (explicit)
    - Harassment

    Note: This is a basic v0.2.1 implementation using patterns.
    For production, consider integrating with OpenAI Moderation API
    or other dedicated moderation services.
    """

    def __init__(self, strict_mode: bool = False):
        """
        Initialize content moderator.

        Args:
            strict_mode: If True, use more aggressive pattern matching
        """
        self.strict_mode = strict_mode

        # Basic harmful patterns (v0.2.1)
        self._hate_patterns = [
            r"\b(hate|despise)\s+(all\s+)?(jews|muslims|christians|blacks|whites|gays|trans)",
            r"\bgenocide\b",
            r"\bexterminate\b.*\b(race|religion|ethnicity)",
        ]

        self._violence_patterns = [
            r"\b(kill|murder|assassinate|torture)\s+(someone|people|them)",
            r"\bhow\s+to\s+(build|make)\s+(bomb|weapon|explosive)",
            r"\bshoot\s+up\s+(school|mall|church)",
        ]

        self._self_harm_patterns = [
            r"\bhow\s+to\s+(kill|hurt)\s+(myself|yourself)",
            r"\bsuicide\s+(method|plan|instructions)",
            r"\bcut\s+(myself|yourself|wrists)",
        ]

        self._sexual_patterns = [
            r"\bexplicit\s+sexual\s+content",
            r"\bchild\s+(porn|sexual)",
        ]

        self._harassment_patterns = [
            r"\bstalk\b.*\bperson",
            r"\bdox\b.*\bsomeone",
        ]

        # Compile patterns
        self._compiled_patterns: dict[str, list[re.Pattern]] = {
            "hate": [re.compile(p, re.IGNORECASE) for p in self._hate_patterns],
            "violence": [re.compile(p, re.IGNORECASE) for p in self._violence_patterns],
            "self-harm": [re.compile(p, re.IGNORECASE) for p in self._self_harm_patterns],
            "sexual": [re.compile(p, re.IGNORECASE) for p in self._sexual_patterns],
            "harassment": [re.compile(p, re.IGNORECASE) for p in self._harassment_patterns],
        }

    def check(self, text: str) -> ModerationResult:
        """
        Check text for harmful content.

        Args:
            text: Text to moderate

        Returns:
            ModerationResult with safety status and violations
        """
        violations = []
        categories = []

        # Check each category
        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    violations.append(f"Detected {category} content")
                    categories.append(category)
                    break  # One match per category is enough

        is_safe = len(violations) == 0

        return ModerationResult(
            is_safe=is_safe,
            violations=violations,
            categories=categories,
            confidence=0.8 if violations else 1.0,  # Lower confidence on pattern matches
        )

    async def check_async(self, text: str) -> ModerationResult:
        """Async version of check (for future API integration)"""
        return self.check(text)
