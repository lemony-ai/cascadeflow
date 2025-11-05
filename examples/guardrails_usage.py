"""
Example: Guardrails (Content Moderation + PII Detection) v0.2.1

Demonstrates content safety and PII detection for production use.
"""

import asyncio
from cascadeflow import (
    UserProfile,
    TierLevel,
    GuardrailsManager,
    GuardrailViolation,
)


async def main():
    print("=" * 60)
    print("cascadeflow v0.2.1 - Guardrails")
    print("=" * 60)

    # Create profile with guardrails enabled
    profile = UserProfile.from_tier(
        TierLevel.PRO,
        user_id="secure_user",
        enable_content_moderation=True,
        enable_pii_detection=True
    )

    print(f"\nUser profile:")
    print(f"  Tier: {profile.tier.name}")
    print(f"  Content moderation: {profile.enable_content_moderation}")
    print(f"  PII detection: {profile.enable_pii_detection}")

    # Initialize guardrails manager
    manager = GuardrailsManager()

    # Example 1: Safe content
    print("\n1. Safe content check")
    print("-" * 60)
    safe_text = "What is the capital of France?"
    result = await manager.check_content(safe_text, profile)
    print(f"Text: {safe_text}")
    print(f"Safe: {result.is_safe}")

    # Example 2: PII detection
    print("\n2. PII detection")
    print("-" * 60)
    pii_text = "My email is john.doe@example.com and phone is 555-123-4567"
    result = await manager.check_content(pii_text, profile)
    print(f"Text: {pii_text}")
    print(f"Safe: {result.is_safe}")
    if result.pii_detected:
        print(f"PII detected: {len(result.pii_detected)} matches")
        for match in result.pii_detected:
            print(f"  - {match.pii_type}: {match.value}")

    # Example 3: PII redaction
    print("\n3. PII redaction")
    print("-" * 60)
    redacted_text, matches = await manager.redact_pii(pii_text, profile)
    print(f"Original: {pii_text}")
    print(f"Redacted: {redacted_text}")

    # Example 4: Disable guardrails
    print("\n4. Disabled guardrails")
    print("-" * 60)
    no_guards_profile = UserProfile.from_tier(
        TierLevel.FREE,
        user_id="basic_user",
        enable_content_moderation=False,
        enable_pii_detection=False
    )
    result = await manager.check_content(pii_text, no_guards_profile)
    print(f"Content moderation: {no_guards_profile.enable_content_moderation}")
    print(f"PII detection: {no_guards_profile.enable_pii_detection}")
    print(f"Result: {result.is_safe} (guardrails disabled)")

    print("\n" + "=" * 60)
    print("Guardrails examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
