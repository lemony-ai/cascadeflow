"""
Guardrails for cascadeflow - Content Safety and Compliance.

Provides basic content moderation and PII detection for production safety.

Key components:
- ContentModerator: Detect harmful content
- PIIDetector: Detect personally identifiable information
- GuardrailsManager: Centralized guardrails management

Example usage:
    from cascadeflow.guardrails import GuardrailsManager
    from cascadeflow import UserProfile, TierLevel

    profile = UserProfile.from_tier(
        TierLevel.PRO,
        user_id="user_123",
        enable_content_moderation=True,
        enable_pii_detection=True
    )

    manager = GuardrailsManager()

    # Check content before processing
    safe, violations = await manager.check_content(
        text="User input here",
        profile=profile
    )

    if not safe:
        raise GuardrailViolation(f"Content blocked: {violations}")
"""

from .content_moderator import ContentModerator, ModerationResult
from .pii_detector import PIIDetector, PIIMatch
from .manager import GuardrailsManager, GuardrailViolation

__all__ = [
    "ContentModerator",
    "ModerationResult",
    "PIIDetector",
    "PIIMatch",
    "GuardrailsManager",
    "GuardrailViolation",
]
