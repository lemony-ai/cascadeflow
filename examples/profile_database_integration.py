"""
Example: Easy Database Integration with cascadeflow User Profiles

This example demonstrates how to integrate cascadeflow profiles
with your existing application database (SQL, NoSQL, etc.) and
support domain-specific models per user.

Key Features:
- Simple profile creation from user data
- Domain-specific model routing
- Database storage/retrieval patterns
- Production-ready integration patterns
"""

import asyncio
import json
from typing import Optional, Dict
from cascadeflow import CascadeAgent, UserProfile, TierLevel, UserProfileManager


# ============================================================================
# Pattern 1: Simple Profile Creation from User Data
# ============================================================================

def create_profile_from_user_data(user_data: Dict) -> UserProfile:
    """
    Create cascadeflow profile from existing user database record.

    This is the simplest integration pattern - map your existing
    user data structure to a UserProfile.

    Example user_data from your database:
    {
        "id": "user_123",
        "subscription": "pro",  # or "free", "starter", "business", "enterprise"
        "daily_budget_override": 15.00,  # optional
        "preferred_models": ["gpt-4", "claude-3-haiku-20240307"],  # optional
        "domains": ["code", "medical"],  # NEW: Domain preferences
    }
    """
    # Map subscription tier
    tier_mapping = {
        "free": TierLevel.FREE,
        "starter": TierLevel.STARTER,
        "pro": TierLevel.PRO,
        "business": TierLevel.BUSINESS,
        "enterprise": TierLevel.ENTERPRISE,
    }

    tier = tier_mapping.get(user_data.get("subscription", "free"), TierLevel.FREE)

    # Create profile with overrides
    profile = UserProfile.from_tier(
        tier=tier,
        user_id=user_data["id"],
        custom_daily_budget=user_data.get("daily_budget_override"),
        preferred_models=user_data.get("preferred_models"),
        preferred_domains=user_data.get("domains"),  # NEW: Domain preferences
        domain_models=user_data.get("domain_models"),  # NEW: Domain-specific models
    )

    return profile


# ============================================================================
# Pattern 2: Domain-Specific Model Routing
# ============================================================================

def create_domain_specific_profile(user_id: str, domains: list) -> UserProfile:
    """
    Create profile with domain-specific model preferences.

    This allows different users to use specialized models
    for specific domains (code, medical, legal, etc.)

    Example domains: ["code", "medical", "legal", "finance"]
    """
    # Define domain-specific models
    # Users working in specific domains can get specialized models
    domain_models = {}

    if "code" in domains:
        # For code domains, prefer models good at coding
        domain_models["code"] = ["gpt-4", "claude-3-haiku-20240307"]

    if "medical" in domains:
        # For medical domains, might want specific fine-tuned models
        domain_models["medical"] = ["gpt-4"]  # Use most capable for safety

    if "legal" in domains:
        # For legal domains, use most careful models
        domain_models["legal"] = ["gpt-4"]

    # Create profile with domain-specific routing
    profile = UserProfile.from_tier(
        TierLevel.PRO,
        user_id=user_id,
        preferred_domains=domains,
        domain_models=domain_models,
    )

    return profile


# ============================================================================
# Pattern 3: Async Database Integration
# ============================================================================

class DatabaseProfileStore:
    """
    Example database integration pattern.

    Replace these methods with calls to your actual database
    (PostgreSQL, MongoDB, Redis, etc.)
    """

    def __init__(self):
        # This would be your actual database connection
        self._mock_db = {}

    async def load_profile(self, user_id: str) -> Optional[UserProfile]:
        """Load profile from database"""
        # Example: Replace with your database query
        # profile_data = await db.query("SELECT * FROM profiles WHERE user_id = ?", user_id)

        profile_data = self._mock_db.get(user_id)
        if profile_data:
            return UserProfile.from_dict(profile_data)
        return None

    async def save_profile(self, profile: UserProfile) -> None:
        """Save profile to database"""
        # Example: Replace with your database insert/update
        # await db.execute("INSERT OR REPLACE INTO profiles VALUES (?)", profile.to_dict())

        self._mock_db[profile.user_id] = profile.to_dict()

    async def get_user_subscription(self, user_id: str) -> Optional[str]:
        """Get user's subscription tier from your existing users table"""
        # Example: This would query your existing users table
        # user = await db.query("SELECT subscription FROM users WHERE id = ?", user_id)
        # return user['subscription']

        # Mock example
        return "pro"  # Would come from your database


# ============================================================================
# Pattern 4: Production-Ready Integration with Caching
# ============================================================================

async def production_integration_example():
    """
    Complete production integration example with caching and database.
    """
    print("=" * 60)
    print("Production Integration Pattern")
    print("=" * 60)

    # Initialize database (replace with your actual DB)
    db = DatabaseProfileStore()

    # Initialize profile manager with database callbacks
    profile_manager = UserProfileManager(
        cache_ttl_seconds=300,  # Cache for 5 minutes
        load_callback=db.load_profile,
        save_callback=db.save_profile,
    )

    # Example: User makes request
    user_id = "user_medical_123"

    print(f"\n1. Loading profile for {user_id}...")
    # This will:
    # - Check cache first (fast!)
    # - Load from DB if not cached
    # - Create default if not in DB
    profile = await profile_manager.get_profile(user_id)
    print(f"   Tier: {profile.tier.name}")
    print(f"   Daily budget: ${profile.get_daily_budget()}")

    # Example: User upgrades to Pro tier
    print(f"\n2. Upgrading user to PRO tier...")
    profile = await profile_manager.update_tier(user_id, TierLevel.PRO)
    print(f"   New tier: {profile.tier.name}")
    print(f"   New daily budget: ${profile.get_daily_budget()}")

    # Example: Create agent from profile
    print(f"\n3. Creating agent from profile...")
    agent = CascadeAgent.from_profile(profile)
    print(f"   Agent created with {len(agent.models)} models")

    # Run query
    result = await agent.run("Explain photosynthesis")
    print(f"   Query cost: ${result.total_cost:.6f}")
    print(f"   Model used: {result.model_used}")


# ============================================================================
# Pattern 5: Simplified One-Liner for Existing Apps
# ============================================================================

async def simple_integration_example():
    """
    Simplest possible integration - just map your user data!
    """
    print("\n" + "=" * 60)
    print("Simple One-Liner Integration")
    print("=" * 60)

    # Your existing user data (from your database)
    user_data = {
        "id": "existing_user_456",
        "subscription": "pro",
        "daily_budget_override": 20.00,
        "preferred_models": ["gpt-4o-mini"],
        "domains": ["code", "finance"],  # NEW: Domain-specific needs
        "domain_models": {  # NEW: Override models per domain
            "code": ["gpt-4", "claude-3-haiku-20240307"],
            "finance": ["gpt-4"],  # Use most capable for finance
        }
    }

    # ONE LINE: Create profile from your existing data
    profile = create_profile_from_user_data(user_data)

    # ONE LINE: Create agent
    agent = CascadeAgent.from_profile(profile)

    # Use it!
    result = await agent.run("Write a Python function to calculate compound interest")

    print(f"\n✓ Profile created from existing user data")
    print(f"✓ User tier: {profile.tier.name}")
    print(f"✓ Domains: {profile.preferred_domains}")
    print(f"✓ Domain models: {profile.domain_models}")
    print(f"✓ Query cost: ${result.total_cost:.6f}")
    print(f"✓ Model: {result.model_used}")


# ============================================================================
# Pattern 6: Domain-Aware Routing
# ============================================================================

async def domain_aware_routing_example():
    """
    Show how domain-specific models work in practice.
    """
    print("\n" + "=" * 60)
    print("Domain-Aware Model Routing")
    print("=" * 60)

    # Medical professional with domain-specific needs
    medical_profile = create_domain_specific_profile(
        user_id="doc_smith",
        domains=["medical", "code"]
    )

    print(f"\n1. Medical Professional Profile")
    print(f"   Tier: {medical_profile.tier.name}")
    print(f"   Domains: {medical_profile.preferred_domains}")
    print(f"   Domain-specific models:")
    for domain, models in (medical_profile.domain_models or {}).items():
        print(f"     - {domain}: {models}")

    # Create agent (will use domain-specific models when available)
    agent = CascadeAgent.from_profile(medical_profile)

    # Run medical query (would use medical-specific models if configured)
    result = await agent.run("Explain the mechanism of action for beta blockers")
    print(f"\n2. Medical Query Result")
    print(f"   Model used: {result.model_used}")
    print(f"   Cost: ${result.total_cost:.6f}")


# ============================================================================
# Pattern 7: Bulk User Migration
# ============================================================================

def bulk_migration_example():
    """
    Migrate existing users in bulk.
    """
    print("\n" + "=" * 60)
    print("Bulk User Migration")
    print("=" * 60)

    # Your existing users from database
    existing_users = [
        {"id": "user_1", "subscription": "free"},
        {"id": "user_2", "subscription": "pro"},
        {"id": "user_3", "subscription": "business"},
        {"id": "user_4", "subscription": "free", "domains": ["code"]},
        {"id": "user_5", "subscription": "pro", "domains": ["medical", "legal"]},
    ]

    # Create profiles for all users
    profiles = []
    for user in existing_users:
        profile = create_profile_from_user_data(user)
        profiles.append(profile)

        # Save to database (would be actual DB call)
        profile_dict = profile.to_dict()
        print(f"\n✓ Migrated {user['id']}:")
        print(f"  - Tier: {profile.tier.name}")
        print(f"  - Daily budget: ${profile.get_daily_budget()}")
        if profile.preferred_domains:
            print(f"  - Domains: {profile.preferred_domains}")

    print(f"\n✓ Migrated {len(profiles)} users successfully")


# ============================================================================
# Main
# ============================================================================

async def main():
    print("\n" + "=" * 70)
    print(" cascadeflow User Profiles - Database Integration Guide")
    print("=" * 70)

    # Run all examples
    await simple_integration_example()
    await production_integration_example()
    await domain_aware_routing_example()
    bulk_migration_example()

    print("\n" + "=" * 70)
    print("Integration examples completed!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("1. Map existing user data → UserProfile (one function)")
    print("2. Use UserProfileManager with database callbacks for caching")
    print("3. Support domain-specific models via preferred_domains & domain_models")
    print("4. Serialize profiles with to_dict()/from_dict() for database storage")
    print("5. Create agents directly from profiles with CascadeAgent.from_profile()")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
