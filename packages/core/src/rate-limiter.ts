/**
 * Rate Limiting for CascadeFlow TypeScript (v0.2.1+)
 *
 * Sliding window rate limiter for production multi-tenant applications.
 */

import { UserProfile, RateLimitState } from './types';

/**
 * Rate limit error
 */
export class RateLimitError extends Error {
  constructor(
    message: string,
    public retryAfterSeconds?: number,
    public limitType?: 'hourly' | 'daily' | 'budget'
  ) {
    super(message);
    this.name = 'RateLimitError';
  }
}

/**
 * Rate limiter with sliding window algorithm
 *
 * Tracks requests and costs per user with hourly/daily limits.
 *
 * @example
 * ```typescript
 * const limiter = new RateLimiter();
 *
 * try {
 *   await limiter.checkRateLimit(profile, 0.005);
 *   // Request allowed
 *   await limiter.recordRequest(profile.userId, 0.005);
 * } catch (err) {
 *   if (err instanceof RateLimitError) {
 *     console.log(`Rate limited. Retry after ${err.retryAfterSeconds}s`);
 *   }
 * }
 * ```
 */
export class RateLimiter {
  private states = new Map<string, RateLimitState>();
  private cleanupIntervalMs: number;
  private cleanupTimer?: NodeJS.Timeout;

  constructor(options?: { cleanupIntervalMs?: number }) {
    this.cleanupIntervalMs = options?.cleanupIntervalMs ?? 3600000; // 1 hour
    this.startCleanup();
  }

  /**
   * Check if request is allowed under rate limits
   *
   * @param profile - User profile with tier limits
   * @param estimatedCost - Estimated request cost
   * @throws RateLimitError if limits exceeded
   */
  async checkRateLimit(profile: UserProfile, estimatedCost: number = 0): Promise<void> {
    const state = this.getOrCreateState(profile.userId);
    const now = Date.now();

    // Get limits from profile
    const hourlyLimit = profile.customRequestsPerHour ?? profile.tier.requestsPerHour;
    const dailyLimit = profile.customRequestsPerDay ?? profile.tier.requestsPerDay;
    const dailyBudget = profile.customDailyBudget ?? profile.tier.dailyBudget;

    // Check hourly limit (sliding window)
    if (hourlyLimit !== undefined) {
      const oneHourAgo = now - 3600000;
      const recentRequests = state.hourlyRequests.filter((t) => t > oneHourAgo);
      state.hourlyRequests = recentRequests;

      if (recentRequests.length >= hourlyLimit) {
        const oldestRequest = Math.min(...recentRequests);
        const retryAfter = Math.ceil((oldestRequest + 3600000 - now) / 1000);
        throw new RateLimitError(
          `Hourly rate limit exceeded (${hourlyLimit} req/hour)`,
          retryAfter,
          'hourly'
        );
      }
    }

    // Check daily limit (sliding window)
    if (dailyLimit !== undefined) {
      const oneDayAgo = now - 86400000;
      const recentRequests = state.dailyRequests.filter((t) => t > oneDayAgo);
      state.dailyRequests = recentRequests;

      if (recentRequests.length >= dailyLimit) {
        const oldestRequest = Math.min(...recentRequests);
        const retryAfter = Math.ceil((oldestRequest + 86400000 - now) / 1000);
        throw new RateLimitError(
          `Daily rate limit exceeded (${dailyLimit} req/day)`,
          retryAfter,
          'daily'
        );
      }
    }

    // Check daily budget
    if (dailyBudget !== undefined) {
      // Reset daily cost if needed
      const lastReset = new Date(state.lastReset);
      const today = new Date();
      if (lastReset.getDate() !== today.getDate()) {
        state.dailyCost = 0;
        state.lastReset = today;
      }

      if (state.dailyCost + estimatedCost > dailyBudget) {
        const remaining = dailyBudget - state.dailyCost;
        throw new RateLimitError(
          `Daily budget exceeded ($${dailyBudget.toFixed(2)}/day). Remaining: $${remaining.toFixed(4)}`,
          undefined,
          'budget'
        );
      }
    }
  }

  /**
   * Record a completed request
   *
   * @param userId - User ID
   * @param cost - Actual request cost
   */
  async recordRequest(userId: string, cost: number = 0): Promise<void> {
    const state = this.getOrCreateState(userId);
    const now = Date.now();

    state.hourlyRequests.push(now);
    state.dailyRequests.push(now);
    state.dailyCost += cost;
  }

  /**
   * Get usage statistics for a user
   *
   * @param userId - User ID
   * @param profile - User profile (for limits)
   * @returns Usage stats
   */
  getUsageStats(userId: string, profile: UserProfile): {
    hourly: { used: number; limit?: number };
    daily: { used: number; limit?: number };
    cost: { used: number; limit?: number };
  } {
    const state = this.getOrCreateState(userId);
    const now = Date.now();

    // Count recent requests
    const oneHourAgo = now - 3600000;
    const oneDayAgo = now - 86400000;
    const hourlyUsed = state.hourlyRequests.filter((t) => t > oneHourAgo).length;
    const dailyUsed = state.dailyRequests.filter((t) => t > oneDayAgo).length;

    return {
      hourly: {
        used: hourlyUsed,
        limit: profile.customRequestsPerHour ?? profile.tier.requestsPerHour,
      },
      daily: {
        used: dailyUsed,
        limit: profile.customRequestsPerDay ?? profile.tier.requestsPerDay,
      },
      cost: {
        used: state.dailyCost,
        limit: profile.customDailyBudget ?? profile.tier.dailyBudget,
      },
    };
  }

  /**
   * Reset limits for a user (e.g., manual override)
   *
   * @param userId - User ID to reset
   */
  resetUser(userId: string): void {
    this.states.delete(userId);
  }

  /**
   * Clear all rate limit state
   */
  clearAll(): void {
    this.states.clear();
  }

  /**
   * Stop cleanup timer
   */
  destroy(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }
  }

  private getOrCreateState(userId: string): RateLimitState {
    let state = this.states.get(userId);
    if (!state) {
      state = {
        userId,
        hourlyRequests: [],
        dailyRequests: [],
        dailyCost: 0,
        lastReset: new Date(),
      };
      this.states.set(userId, state);
    }
    return state;
  }

  private startCleanup(): void {
    this.cleanupTimer = setInterval(() => {
      const now = Date.now();
      const oneDayAgo = now - 86400000;

      // Remove old state
      for (const [userId, state] of this.states.entries()) {
        const hasRecentRequests = state.dailyRequests.some((t) => t > oneDayAgo);
        if (!hasRecentRequests) {
          this.states.delete(userId);
        }
      }
    }, this.cleanupIntervalMs);
  }
}
