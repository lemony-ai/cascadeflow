"""Profile manager for scaling to thousands of users."""

import asyncio
from collections.abc import Awaitable
from datetime import datetime, timedelta
from typing import Callable, Optional

from .tier_config import TierLevel
from .user_profile import UserProfile


class UserProfileManager:
    """
    Manage user profiles at scale (thousands of users).

    Features:
    - In-memory caching (configurable TTL)
    - Database integration (via callback)
    - Bulk operations
    - Tier upgrades/downgrades
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 300,  # 5 minutes
        load_callback: Optional[Callable[[str], Awaitable[Optional[UserProfile]]]] = None,
        save_callback: Optional[Callable[[UserProfile], Awaitable[None]]] = None,
    ):
        """
        Initialize profile manager.

        Args:
            cache_ttl_seconds: How long to cache profiles in memory
            load_callback: Async function to load profile from database
            save_callback: Async function to save profile to database
        """
        self._cache: dict[str, tuple[UserProfile, datetime]] = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._load_callback = load_callback
        self._save_callback = save_callback
        self._lock = asyncio.Lock()

    async def get_profile(self, user_id: str) -> UserProfile:
        """
        Get user profile (from cache or load).

        Fast path: Cached profile (microseconds)
        Slow path: Load from database (milliseconds)
        Default path: Create free tier profile (microseconds)
        """
        # Check cache
        if user_id in self._cache:
            profile, cached_at = self._cache[user_id]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                return profile

        # Load from database
        async with self._lock:
            if self._load_callback:
                profile = await self._load_callback(user_id)
                if profile:
                    self._cache[user_id] = (profile, datetime.utcnow())
                    return profile

        # Default: Create free tier profile
        profile = UserProfile.from_tier(TierLevel.FREE, user_id=user_id)
        self._cache[user_id] = (profile, datetime.utcnow())
        return profile

    async def save_profile(self, profile: UserProfile) -> None:
        """Save profile to database and cache"""
        self._cache[profile.user_id] = (profile, datetime.utcnow())
        if self._save_callback:
            await self._save_callback(profile)

    async def update_tier(self, user_id: str, new_tier: TierLevel) -> UserProfile:
        """Upgrade/downgrade user tier"""
        from .tier_config import TierConfig

        profile = await self.get_profile(user_id)
        profile.tier = TierConfig.from_preset(new_tier)
        await self.save_profile(profile)
        return profile

    def invalidate_cache(self, user_id: str) -> None:
        """Invalidate cached profile (e.g., after tier change)"""
        if user_id in self._cache:
            del self._cache[user_id]

    def create_bulk(self, user_data: list[dict]) -> list[UserProfile]:
        """Create multiple profiles efficiently"""
        profiles = []
        for data in user_data:
            tier = TierLevel(data.get("tier", "free"))
            profile = UserProfile.from_tier(tier, user_id=data["user_id"])
            profiles.append(profile)
            self._cache[profile.user_id] = (profile, datetime.utcnow())
        return profiles
