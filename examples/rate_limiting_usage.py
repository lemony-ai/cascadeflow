"""
Example: Rate Limiting with cascadeflow v0.2.1

This example demonstrates per-user and per-tier rate limiting
with the sliding window algorithm.
"""

import asyncio
from cascadeflow import (
    CascadeAgent,
    UserProfile,
    TierLevel,
    RateLimiter,
    RateLimitError,
)


async def main():
    print("=" * 60)
    print("cascadeflow v0.2.1 - Rate Limiting")
    print("=" * 60)

    # ========================================================================
    # Example 1: Basic rate limiting with FREE tier
    # ========================================================================
    print("\n1. FREE tier rate limiting (10 req/hour, 100 req/day)")
    print("-" * 60)

    # Create FREE tier profile
    free_profile = UserProfile.from_tier(TierLevel.FREE, user_id="free_user")
    print(f"Tier: {free_profile.tier.name}")
    print(f"Hourly limit: {free_profile.get_requests_per_hour()}")
    print(f"Daily limit: {free_profile.get_requests_per_day()}")
    print(f"Daily budget: ${free_profile.get_daily_budget()}")

    # Initialize rate limiter
    limiter = RateLimiter()

    # Create agent
    agent = CascadeAgent.from_profile(free_profile)

    # Make some requests
    print(f"\nMaking 5 requests...")
    for i in range(5):
        # Check rate limit before making request
        allowed, reason = await limiter.check_rate_limit(free_profile)

        if not allowed:
            print(f"  Request {i+1}: BLOCKED - {reason}")
            continue

        # Make request
        result = await agent.run(f"What is {i+1} + {i+1}?")

        # Record the request
        await limiter.record_request(free_profile, cost=result.total_cost)

        print(f"  Request {i+1}: OK - Cost: ${result.total_cost:.6f}")

    # Check usage stats
    stats = await limiter.get_usage_stats(free_profile)
    print(f"\nUsage stats:")
    print(f"  Hourly: {stats['hourly_requests']}/{stats['hourly_limit']}")
    print(f"  Daily: {stats['daily_requests']}/{stats['daily_limit']}")
    print(f"  Cost: ${stats['daily_cost']:.6f}/${stats['daily_budget']}")

    # ========================================================================
    # Example 2: Rate limit enforcement
    # ========================================================================
    print("\n2. Rate limit enforcement demo")
    print("-" * 60)

    # Create profile with very low limits
    test_profile = UserProfile.from_tier(
        TierLevel.FREE,
        user_id="test_user",
        custom_requests_per_hour=3,  # Only 3 requests per hour
        custom_daily_budget=0.01,  # Very low budget
    )

    print(f"Custom limits: {test_profile.get_requests_per_hour()} req/hour, ${test_profile.get_daily_budget()} budget")

    # Try to exceed hourly limit
    print(f"\nAttempting 5 requests (limit is 3)...")
    request_count = 0
    blocked_count = 0

    for i in range(5):
        allowed, reason = await limiter.check_rate_limit(test_profile)

        if not allowed:
            print(f"  Request {i+1}: BLOCKED - {reason}")
            blocked_count += 1
            continue

        result = await agent.run(f"Simple test {i+1}")
        await limiter.record_request(test_profile, cost=result.total_cost)
        request_count += 1
        print(f"  Request {i+1}: OK")

    print(f"\n✓ Processed: {request_count}, Blocked: {blocked_count}")

    # ========================================================================
    # Example 3: PRO tier with higher limits
    # ========================================================================
    print("\n3. PRO tier with higher limits")
    print("-" * 60)

    pro_profile = UserProfile.from_tier(TierLevel.PRO, user_id="pro_user")
    print(f"Tier: {pro_profile.tier.name}")
    print(f"Hourly limit: {pro_profile.get_requests_per_hour()}")
    print(f"Daily limit: {pro_profile.get_requests_per_day()}")
    print(f"Daily budget: ${pro_profile.get_daily_budget()}")

    # PRO users can make many more requests
    print(f"\nMaking 10 rapid requests...")
    for i in range(10):
        allowed, reason = await limiter.check_rate_limit(pro_profile)
        if allowed:
            result = await agent.run(f"Quick query {i+1}")
            await limiter.record_request(pro_profile, cost=result.total_cost)
            print(f"  Request {i+1}: OK")
        else:
            print(f"  Request {i+1}: BLOCKED")

    stats = await limiter.get_usage_stats(pro_profile)
    print(f"\nPRO user usage:")
    print(f"  Hourly: {stats['hourly_requests']}/{stats['hourly_limit']} ({stats['hourly_remaining']} remaining)")
    print(f"  Daily: {stats['daily_requests']}/{stats['daily_limit']} ({stats['daily_remaining']} remaining)")
    print(f"  Budget: ${stats['daily_cost']:.6f}/${stats['daily_budget']} (${stats['budget_remaining']:.4f} remaining)")

    # ========================================================================
    # Example 4: Budget-based rate limiting
    # ========================================================================
    print("\n4. Budget-based rate limiting")
    print("-" * 60)

    budget_profile = UserProfile.from_tier(
        TierLevel.FREE,
        user_id="budget_user",
        custom_daily_budget=0.05,  # $0.05 daily budget
    )

    print(f"Daily budget: ${budget_profile.get_daily_budget()}")

    # Simulate requests until budget is exceeded
    print(f"\nMaking requests until budget exceeded...")
    total_cost = 0.0
    request_num = 0

    while True:
        # Check with estimated cost
        allowed, reason = await limiter.check_rate_limit(budget_profile, cost=0.01)

        if not allowed:
            print(f"\n{reason}")
            break

        result = await agent.run(f"Budget test {request_num+1}")
        await limiter.record_request(budget_profile, cost=result.total_cost)

        request_num += 1
        total_cost += result.total_cost
        print(f"  Request {request_num}: ${result.total_cost:.6f} (total: ${total_cost:.6f})")

        if request_num >= 20:  # Safety limit
            break

    print(f"\n✓ Completed {request_num} requests before hitting budget limit")

    # ========================================================================
    # Example 5: Comparing tier limits
    # ========================================================================
    print("\n5. Comparing tier limits")
    print("-" * 60)

    tiers = [TierLevel.FREE, TierLevel.STARTER, TierLevel.PRO, TierLevel.BUSINESS]

    print(f"{'Tier':<12} {'Req/Hour':<12} {'Req/Day':<12} {'Daily Budget':<15}")
    print("-" * 60)

    for tier in tiers:
        profile = UserProfile.from_tier(tier, user_id=f"{tier.value}_user")
        req_hour = profile.get_requests_per_hour() or "Unlimited"
        req_day = profile.get_requests_per_day() or "Unlimited"
        budget = f"${profile.get_daily_budget()}" if profile.get_daily_budget() else "Unlimited"

        print(f"{tier.value:<12} {str(req_hour):<12} {str(req_day):<12} {budget:<15}")

    print("\n" + "=" * 60)
    print("Rate limiting examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
