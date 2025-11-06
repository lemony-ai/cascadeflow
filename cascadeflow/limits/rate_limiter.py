"""
Rate limiter with sliding window algorithm.

Implements per-user and per-tier rate limiting for cascadeflow.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cascadeflow.profiles import UserProfile


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class RateLimitState:
    """
    Rate limit state for a user.

    Tracks request timestamps in sliding windows for accurate rate limiting.
    """

    user_id: str
    hourly_requests: list[float] = field(default_factory=list)
    daily_requests: list[float] = field(default_factory=list)
    daily_cost: float = 0.0
    cost_reset_time: float = field(default_factory=time.time)

    def clean_old_requests(self, current_time: float) -> None:
        """Remove requests older than tracking windows"""
        # Keep requests from last hour
        hour_ago = current_time - 3600
        self.hourly_requests = [t for t in self.hourly_requests if t > hour_ago]

        # Keep requests from last day
        day_ago = current_time - 86400
        self.daily_requests = [t for t in self.daily_requests if t > day_ago]

        # Reset daily cost if day has passed
        if current_time - self.cost_reset_time > 86400:
            self.daily_cost = 0.0
            self.cost_reset_time = current_time


class RateLimiter:
    """
    Sliding window rate limiter for per-user and per-tier limits.

    Features:
    - Sliding window algorithm (accurate rate limiting)
    - Per-user request tracking
    - Hourly and daily limits
    - Daily budget tracking
    - Automatic cleanup of old data
    - Thread-safe with asyncio locks

    Example:
        >>> limiter = RateLimiter()
        >>> profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
        >>>
        >>> # Check rate limit
        >>> allowed, reason = await limiter.check_rate_limit(profile)
        >>> if not allowed:
        >>>     raise RateLimitError(reason)
        >>>
        >>> # Record request
        >>> await limiter.record_request(profile, cost=0.01)
    """

    def __init__(self):
        """Initialize rate limiter with user state tracking"""
        self._states: dict[str, RateLimitState] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self, profile: "UserProfile", cost: float = 0.0
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed under rate limits.

        Args:
            profile: User profile with tier limits
            cost: Expected cost of the request

        Returns:
            Tuple of (allowed, reason)
            - allowed: True if request is allowed
            - reason: Description of why request was denied (if not allowed)
        """
        async with self._lock:
            current_time = time.time()

            # Get or create state for user
            if profile.user_id not in self._states:
                self._states[profile.user_id] = RateLimitState(user_id=profile.user_id)

            state = self._states[profile.user_id]

            # Clean old requests
            state.clean_old_requests(current_time)

            # Check hourly limit
            hourly_limit = profile.get_requests_per_hour()
            if hourly_limit is not None:
                if len(state.hourly_requests) >= hourly_limit:
                    oldest_request = min(state.hourly_requests)
                    retry_after = 3600 - (current_time - oldest_request)
                    return (
                        False,
                        f"Hourly rate limit exceeded ({hourly_limit} req/hour). Retry after {retry_after:.0f}s",
                    )

            # Check daily limit
            daily_limit = profile.get_requests_per_day()
            if daily_limit is not None:
                if len(state.daily_requests) >= daily_limit:
                    oldest_request = min(state.daily_requests)
                    retry_after = 86400 - (current_time - oldest_request)
                    return (
                        False,
                        f"Daily rate limit exceeded ({daily_limit} req/day). Retry after {retry_after:.0f}s",
                    )

            # Check daily budget
            daily_budget = profile.get_daily_budget()
            if daily_budget is not None:
                if state.daily_cost + cost > daily_budget:
                    remaining = daily_budget - state.daily_cost
                    return (
                        False,
                        f"Daily budget exceeded (${daily_budget:.2f}/day). Remaining: ${remaining:.4f}",
                    )

            return True, None

    async def record_request(self, profile: "UserProfile", cost: float = 0.0) -> None:
        """
        Record a successful request.

        Args:
            profile: User profile
            cost: Actual cost of the request
        """
        async with self._lock:
            current_time = time.time()

            # Get or create state
            if profile.user_id not in self._states:
                self._states[profile.user_id] = RateLimitState(user_id=profile.user_id)

            state = self._states[profile.user_id]

            # Record request timestamps
            state.hourly_requests.append(current_time)
            state.daily_requests.append(current_time)

            # Add cost to daily total
            state.daily_cost += cost

    async def get_usage_stats(self, profile: "UserProfile") -> dict:
        """
        Get current usage statistics for a user.

        Returns dict with:
        - hourly_requests: Number of requests in last hour
        - daily_requests: Number of requests in last day
        - daily_cost: Total cost for today
        - hourly_limit: Hourly request limit
        - daily_limit: Daily request limit
        - daily_budget: Daily budget limit
        """
        async with self._lock:
            current_time = time.time()

            if profile.user_id not in self._states:
                return {
                    "hourly_requests": 0,
                    "daily_requests": 0,
                    "daily_cost": 0.0,
                    "hourly_limit": profile.get_requests_per_hour(),
                    "daily_limit": profile.get_requests_per_day(),
                    "daily_budget": profile.get_daily_budget(),
                }

            state = self._states[profile.user_id]
            state.clean_old_requests(current_time)

            return {
                "hourly_requests": len(state.hourly_requests),
                "daily_requests": len(state.daily_requests),
                "daily_cost": state.daily_cost,
                "hourly_limit": profile.get_requests_per_hour(),
                "daily_limit": profile.get_requests_per_day(),
                "daily_budget": profile.get_daily_budget(),
                "hourly_remaining": (
                    profile.get_requests_per_hour() - len(state.hourly_requests)
                    if profile.get_requests_per_hour() is not None
                    else None
                ),
                "daily_remaining": (
                    profile.get_requests_per_day() - len(state.daily_requests)
                    if profile.get_requests_per_day() is not None
                    else None
                ),
                "budget_remaining": (
                    profile.get_daily_budget() - state.daily_cost
                    if profile.get_daily_budget() is not None
                    else None
                ),
            }

    async def reset_user_limits(self, user_id: str) -> None:
        """Reset rate limits for a specific user (admin function)"""
        async with self._lock:
            if user_id in self._states:
                del self._states[user_id]

    async def cleanup_old_states(self, max_age_hours: int = 24) -> int:
        """
        Cleanup states for users who haven't made requests recently.

        Args:
            max_age_hours: Remove states older than this many hours

        Returns:
            Number of states removed
        """
        async with self._lock:
            current_time = time.time()
            cutoff_time = current_time - (max_age_hours * 3600)

            users_to_remove = []
            for user_id, state in self._states.items():
                # If no recent requests, remove state
                if (
                    not state.hourly_requests
                    and not state.daily_requests
                    or (state.daily_requests and max(state.daily_requests) < cutoff_time)
                ):
                    users_to_remove.append(user_id)

            for user_id in users_to_remove:
                del self._states[user_id]

            return len(users_to_remove)
