"""
Example: User Profile System with cascadeflow v0.2.1

This example demonstrates the user profile system for managing
thousands of users with different subscription tiers.
"""

import asyncio
from cascadeflow import CascadeAgent, UserProfile, TierLevel, UserProfileManager


async def main():
    print("=" * 60)
    print("cascadeflow v0.2.1 - User Profile System")
    print("=" * 60)

    # ========================================================================
    # Example 1: Simple tier-based profile
    # ========================================================================
    print("\n1. Create agent from PRO tier profile")
    print("-" * 60)

    # Create profile from tier preset
    profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")

    print(f"User ID: {profile.user_id}")
    print(f"Tier: {profile.tier.name}")
    print(f"Daily budget: ${profile.get_daily_budget()}")
    print(f"Requests per hour: {profile.get_requests_per_hour()}")
    print(f"Requests per day: {profile.get_requests_per_day()}")
    print(f"Streaming enabled: {profile.tier.enable_streaming}")
    print(f"Batch enabled: {profile.tier.enable_batch}")
    print(f"Target quality: {profile.tier.target_quality}")

    # Create agent from profile
    agent = CascadeAgent.from_profile(profile)

    # Run query with profile limits
    result = await agent.run("What is the capital of France?")
    print(f"\nQuery result:")
    print(f"  Model: {result.model_used}")
    print(f"  Cost: ${result.total_cost:.6f}")
    print(f"  Quality: {result.quality_score:.2f}")
    print(f"  Cascaded: {result.cascaded}")
    print(f"  Content: {result.content[:100]}...")

    # ========================================================================
    # Example 2: Custom profile with overrides
    # ========================================================================
    print("\n2. Custom profile with tier overrides")
    print("-" * 60)

    # Start with FREE tier but customize limits
    custom_profile = UserProfile.from_tier(
        TierLevel.FREE,
        user_id="user_456",
        custom_daily_budget=0.50,  # Override FREE tier budget
        custom_requests_per_hour=50,  # Override FREE tier rate limit
        preferred_models=["gpt-4o-mini"],  # Only use specific models
        cost_sensitivity="aggressive",  # Prioritize cost savings
    )

    print(f"User ID: {custom_profile.user_id}")
    print(f"Base tier: {custom_profile.tier.name}")
    print(f"Custom daily budget: ${custom_profile.get_daily_budget()}")
    print(f"Custom requests/hour: {custom_profile.get_requests_per_hour()}")
    print(f"Preferred models: {custom_profile.preferred_models}")
    print(f"Cost sensitivity: {custom_profile.cost_sensitivity}")

    # ========================================================================
    # Example 3: Profile manager for scaling (thousands of users)
    # ========================================================================
    print("\n3. Profile manager with caching")
    print("-" * 60)

    # Initialize profile manager
    manager = UserProfileManager(cache_ttl_seconds=300)

    # Simulate loading profiles for multiple users
    user_profiles = []
    for i in range(5):
        user_id = f"user_{i}"
        # First call will create profile (cache miss)
        profile = await manager.get_profile(user_id)
        user_profiles.append(profile)
        print(f"Loaded profile for {user_id} (tier: {profile.tier.name})")

    # Second call will use cache (fast!)
    cached_profile = await manager.get_profile("user_0")
    print(f"\nCached lookup for user_0: {cached_profile.user_id}")

    # Bulk profile creation
    bulk_users = [
        {"user_id": "bulk_1", "tier": "starter"},
        {"user_id": "bulk_2", "tier": "pro"},
        {"user_id": "bulk_3", "tier": "business"},
    ]
    bulk_profiles = manager.create_bulk(bulk_users)
    print(f"\nCreated {len(bulk_profiles)} profiles in bulk:")
    for p in bulk_profiles:
        print(f"  - {p.user_id}: {p.tier.name} tier")

    # ========================================================================
    # Example 4: Compare tiers
    # ========================================================================
    print("\n4. Compare different tiers")
    print("-" * 60)

    tiers_to_compare = [TierLevel.FREE, TierLevel.STARTER, TierLevel.PRO, TierLevel.ENTERPRISE]

    print(f"{'Tier':<12} {'Daily Budget':<15} {'Req/Hour':<12} {'Streaming':<12} {'Batch':<12}")
    print("-" * 60)

    for tier_level in tiers_to_compare:
        p = UserProfile.from_tier(tier_level, user_id="compare")
        budget = f"${p.get_daily_budget()}" if p.get_daily_budget() else "Unlimited"
        req_hour = str(p.get_requests_per_hour()) if p.get_requests_per_hour() else "Unlimited"
        streaming = "Yes" if p.tier.enable_streaming else "No"
        batch = "Yes" if p.tier.enable_batch else "No"

        print(f"{tier_level.value:<12} {budget:<15} {req_hour:<12} {streaming:<12} {batch:<12}")

    # ========================================================================
    # Example 5: Profile serialization (for database storage)
    # ========================================================================
    print("\n5. Profile serialization")
    print("-" * 60)

    # Create profile
    profile_to_save = UserProfile.from_tier(TierLevel.BUSINESS, user_id="user_789")

    # Serialize to dict (for database storage)
    profile_dict = profile_to_save.to_dict()
    print(f"Serialized profile: {profile_dict['user_id']}")
    print(f"  Tier: {profile_dict['tier']['name']}")

    # Deserialize from dict (load from database)
    loaded_profile = UserProfile.from_dict(profile_dict)
    print(f"\nDeserialized profile: {loaded_profile.user_id}")
    print(f"  Tier: {loaded_profile.tier.name}")
    print(f"  Daily budget: ${loaded_profile.get_daily_budget()}")

    print("\n" + "=" * 60)
    print("User profile examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
