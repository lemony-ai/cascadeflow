import type { ProviderRateLimitPolicy } from './types';

export interface RateLimitDecision {
  allowed: boolean;
  retryAfterMs?: number;
}

export class ProviderRateLimiter {
  private requestTimestamps: number[] = [];
  private tokenTimestamps: number[] = [];
  private inflight = 0;

  constructor(private policy: ProviderRateLimitPolicy) {}

  check(tokens: number = 0): RateLimitDecision {
    const now = Date.now();
    const windowStart = now - 60000;

    this.requestTimestamps = this.requestTimestamps.filter((ts) => ts > windowStart);
    this.tokenTimestamps = this.tokenTimestamps.filter((ts) => ts > windowStart);

    if (
      this.policy.concurrency !== undefined &&
      this.inflight >= this.policy.concurrency
    ) {
      return { allowed: false, retryAfterMs: 1000 };
    }

    if (
      this.policy.requestsPerMinute !== undefined &&
      this.requestTimestamps.length >= this.policy.requestsPerMinute
    ) {
      const oldest = this.requestTimestamps[0];
      return { allowed: false, retryAfterMs: oldest + 60000 - now };
    }

    if (
      this.policy.tokensPerMinute !== undefined &&
      this.tokenTimestamps.length >= this.policy.tokensPerMinute
    ) {
      const oldest = this.tokenTimestamps[0];
      return { allowed: false, retryAfterMs: oldest + 60000 - now };
    }

    if (tokens > 0 && this.policy.tokensPerMinute !== undefined) {
      const projected = this.tokenTimestamps.length + tokens;
      if (projected > this.policy.tokensPerMinute) {
        const oldest = this.tokenTimestamps[0] ?? now;
        return { allowed: false, retryAfterMs: oldest + 60000 - now };
      }
    }

    return { allowed: true };
  }

  startRequest(tokens: number = 0): RateLimitDecision {
    const decision = this.check(tokens);
    if (!decision.allowed) {
      return decision;
    }

    const now = Date.now();
    this.requestTimestamps.push(now);
    if (tokens > 0) {
      for (let i = 0; i < tokens; i += 1) {
        this.tokenTimestamps.push(now);
      }
    }
    this.inflight += 1;

    return { allowed: true };
  }

  endRequest(): void {
    this.inflight = Math.max(0, this.inflight - 1);
  }
}
