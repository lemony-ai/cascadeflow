"""
Guardrails manager for coordinating content safety checks.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .content_moderator import ContentModerator, ModerationResult
from .pii_detector import PIIDetector, PIIMatch

if TYPE_CHECKING:
    from cascadeflow.profiles import UserProfile


class GuardrailViolation(Exception):
    """Exception raised when content violates guardrails"""

    def __init__(self, message: str, violations: list[str]):
        super().__init__(message)
        self.violations = violations


@dataclass
class GuardrailsCheck:
    """Result from guardrails check"""

    is_safe: bool
    content_moderation: Optional[ModerationResult] = None
    pii_detected: Optional[list[PIIMatch]] = None
    violations: list[str] = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []


class GuardrailsManager:
    """
    Centralized guardrails management.

    Coordinates content moderation and PII detection based on
    user profile settings.

    Example:
        >>> manager = GuardrailsManager()
        >>> result = await manager.check_content(
        ...     text="user input",
        ...     profile=profile
        ... )
        >>> if not result.is_safe:
        ...     raise GuardrailViolation("Content blocked", result.violations)
    """

    def __init__(self):
        """Initialize guardrails manager"""
        self._content_moderator = ContentModerator()
        self._pii_detector = PIIDetector()

    async def check_content(
        self,
        text: str,
        profile: "UserProfile",
    ) -> GuardrailsCheck:
        """
        Check content against enabled guardrails.

        Args:
            text: Text to check
            profile: User profile with guardrail settings

        Returns:
            GuardrailsCheck with results
        """
        violations = []
        moderation_result = None
        pii_matches = None

        # Check content moderation if enabled
        if profile.enable_content_moderation:
            moderation_result = await self._content_moderator.check_async(text)
            if not moderation_result.is_safe:
                violations.extend(moderation_result.violations)

        # Check PII if enabled
        if profile.enable_pii_detection:
            pii_matches = await self._pii_detector.detect_async(text)
            if pii_matches:
                pii_types = {m.pii_type for m in pii_matches}
                violations.append(f"PII detected: {', '.join(pii_types)}")

        is_safe = len(violations) == 0

        return GuardrailsCheck(
            is_safe=is_safe,
            content_moderation=moderation_result,
            pii_detected=pii_matches,
            violations=violations,
        )

    async def redact_pii(
        self,
        text: str,
        profile: "UserProfile",
    ) -> tuple[str, list[PIIMatch]]:
        """
        Redact PII from text if PII detection is enabled.

        Args:
            text: Text to redact
            profile: User profile

        Returns:
            Tuple of (redacted_text, pii_matches)
        """
        if not profile.enable_pii_detection:
            return text, []

        return self._pii_detector.redact(text)
