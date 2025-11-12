/**
 * User Profile System for cascadeflow TypeScript (v0.2.1+)
 *
 * Multi-tenant subscription tier management for production applications.
 *
 * Enhanced in v1.0.1+ with:
 * - Latency awareness for speed control
 * - Optimization weights for multi-factor routing
 * - Cost sensitivity modes
 */

import {
  TierConfig,
  TierLevel,
  UserProfile,
  LatencyProfile,
  OptimizationWeights,
  CostSensitivity,
} from './types';

// ==================== VALIDATION FUNCTIONS ====================

/**
 * Validate optimization weights sum to 1.0
 *
 * @param weights - Optimization weights to validate
 * @throws Error if weights don't sum to 1.0
 */
export function validateOptimizationWeights(weights: OptimizationWeights): void {
  const total = weights.cost + weights.speed + weights.quality;
  // Allow small floating point error (0.99 to 1.01)
  if (total < 0.99 || total > 1.01) {
    throw new Error(`Optimization weights must sum to 1.0, got ${total}`);
  }

  // Validate individual weights are in range
  if (weights.cost < 0 || weights.cost > 1) {
    throw new Error(`Cost weight must be between 0 and 1, got ${weights.cost}`);
  }
  if (weights.speed < 0 || weights.speed > 1) {
    throw new Error(`Speed weight must be between 0 and 1, got ${weights.speed}`);
  }
  if (weights.quality < 0 || weights.quality > 1) {
    throw new Error(`Quality weight must be between 0 and 1, got ${weights.quality}`);
  }
}

/**
 * Create optimization weights with validation
 *
 * @param cost - Cost weight (0-1)
 * @param speed - Speed weight (0-1)
 * @param quality - Quality weight (0-1)
 * @returns Validated optimization weights
 *
 * @example
 * ```typescript
 * const weights = createOptimizationWeights(0.2, 0.5, 0.3);
 * ```
 */
export function createOptimizationWeights(
  cost: number,
  speed: number,
  quality: number
): OptimizationWeights {
  const weights: OptimizationWeights = { cost, speed, quality };
  validateOptimizationWeights(weights);
  return weights;
}

/**
 * Create a latency profile with defaults
 *
 * @param options - Partial latency profile options
 * @returns Complete latency profile
 *
 * @example
 * ```typescript
 * const profile = createLatencyProfile({ maxTotalMs: 2000 });
 * ```
 */
export function createLatencyProfile(
  options: Partial<LatencyProfile> = {}
): LatencyProfile {
  return {
    maxTotalMs: options.maxTotalMs ?? 5000,
    maxPerModelMs: options.maxPerModelMs ?? 3000,
    preferParallel: options.preferParallel ?? false,
    skipCascadeThreshold: options.skipCascadeThreshold ?? 0,
  };
}

// ==================== DEFAULT OPTIMIZATION PRESETS ====================

/**
 * Predefined optimization weight presets for common use cases
 */
export const OPTIMIZATION_PRESETS: Record<CostSensitivity, OptimizationWeights> = {
  aggressive: { cost: 0.7, speed: 0.15, quality: 0.15 },
  balanced: { cost: 0.4, speed: 0.3, quality: 0.3 },
  quality_first: { cost: 0.1, speed: 0.3, quality: 0.6 },
};

/**
 * Predefined latency profile presets for common use cases
 */
export const LATENCY_PRESETS = {
  realtime: createLatencyProfile({
    maxTotalMs: 1000,
    maxPerModelMs: 800,
    preferParallel: true,
    skipCascadeThreshold: 800,
  }),
  interactive: createLatencyProfile({
    maxTotalMs: 3000,
    maxPerModelMs: 2000,
    preferParallel: true,
    skipCascadeThreshold: 1500,
  }),
  standard: createLatencyProfile({
    maxTotalMs: 8000,
    maxPerModelMs: 5000,
    preferParallel: false,
    skipCascadeThreshold: 2000,
  }),
  batch: createLatencyProfile({
    maxTotalMs: 30000,
    maxPerModelMs: 20000,
    preferParallel: false,
    skipCascadeThreshold: 0,
  }),
};

// ==================== TIER PRESETS ====================

/**
 * Predefined tier configurations
 */
export const TIER_PRESETS: Record<TierLevel, TierConfig> = {
  FREE: {
    name: 'Free',
    requestsPerHour: 10,
    requestsPerDay: 100,
    dailyBudget: 0.10,
    maxConcurrentRequests: 1,
    enableCaching: true,
    enableSpeculative: false,
    minQuality: 0.6,
    targetQuality: 0.7,
  },
  STARTER: {
    name: 'Starter',
    requestsPerHour: 100,
    requestsPerDay: 1000,
    dailyBudget: 5.0,
    maxConcurrentRequests: 3,
    enableCaching: true,
    enableSpeculative: true,
    minQuality: 0.7,
    targetQuality: 0.8,
  },
  PRO: {
    name: 'Pro',
    requestsPerHour: 500,
    requestsPerDay: 5000,
    dailyBudget: 50.0,
    maxConcurrentRequests: 10,
    enableCaching: true,
    enableSpeculative: true,
    minQuality: 0.75,
    targetQuality: 0.85,
  },
  BUSINESS: {
    name: 'Business',
    requestsPerHour: 2000,
    requestsPerDay: 20000,
    dailyBudget: 200.0,
    maxConcurrentRequests: 25,
    enableCaching: true,
    enableSpeculative: true,
    minQuality: 0.8,
    targetQuality: 0.9,
  },
  ENTERPRISE: {
    name: 'Enterprise',
    maxConcurrentRequests: 100,
    enableCaching: true,
    enableSpeculative: true,
    minQuality: 0.85,
    targetQuality: 0.95,
  },
};

/**
 * Create a user profile from a tier level
 *
 * @param tierLevel - Subscription tier level
 * @param userId - Unique user identifier
 * @param options - Optional profile customizations
 * @returns UserProfile instance
 *
 * @example
 * ```typescript
 * const profile = createUserProfile('PRO', 'user-123', {
 *   preferredModels: ['gpt-4', 'claude-3-opus'],
 *   enableContentModeration: true,
 * });
 * ```
 */
export function createUserProfile(
  tierLevel: TierLevel,
  userId: string,
  options?: Partial<Omit<UserProfile, 'userId' | 'tier'>>
): UserProfile {
  const tier = TIER_PRESETS[tierLevel];

  return {
    userId,
    tier,
    ...options,
  };
}

/**
 * User Profile Manager with caching
 *
 * Manages user profiles at scale with in-memory caching and
 * optional database integration.
 *
 * @example
 * ```typescript
 * const manager = new UserProfileManager({
 *   cacheTtlMs: 300000, // 5 minutes
 *   loadProfile: async (userId) => {
 *     return await database.users.findOne({ id: userId });
 *   },
 *   saveProfile: async (profile) => {
 *     await database.users.updateOne(
 *       { id: profile.userId },
 *       { $set: profile }
 *     );
 *   },
 * });
 *
 * const profile = await manager.getProfile('user-123');
 * ```
 */
export class UserProfileManager {
  private cache = new Map<string, { profile: UserProfile; expiresAt: number }>();
  private cacheTtlMs: number;
  private loadCallback?: (userId: string) => Promise<UserProfile | null>;
  private saveCallback?: (profile: UserProfile) => Promise<void>;

  constructor(options?: {
    cacheTtlMs?: number;
    loadProfile?: (userId: string) => Promise<UserProfile | null>;
    saveProfile?: (profile: UserProfile) => Promise<void>;
  }) {
    this.cacheTtlMs = options?.cacheTtlMs ?? 300000; // 5 minutes default
    this.loadCallback = options?.loadProfile;
    this.saveCallback = options?.saveProfile;
  }

  /**
   * Get user profile (with caching)
   *
   * @param userId - User ID to fetch
   * @returns User profile
   */
  async getProfile(userId: string): Promise<UserProfile> {
    // Check cache first
    const cached = this.cache.get(userId);
    if (cached && Date.now() < cached.expiresAt) {
      return cached.profile;
    }

    // Try database load
    if (this.loadCallback) {
      const loaded = await this.loadCallback(userId);
      if (loaded) {
        this.cacheProfile(loaded);
        return loaded;
      }
    }

    // Create default FREE profile
    const defaultProfile = createUserProfile('FREE', userId);
    this.cacheProfile(defaultProfile);
    return defaultProfile;
  }

  /**
   * Save user profile (cache + database)
   *
   * @param profile - Profile to save
   */
  async saveProfile(profile: UserProfile): Promise<void> {
    this.cacheProfile(profile);

    if (this.saveCallback) {
      await this.saveCallback(profile);
    }
  }

  /**
   * Update user tier
   *
   * @param userId - User ID
   * @param newTier - New tier level
   */
  async updateTier(userId: string, newTier: TierLevel): Promise<UserProfile> {
    const profile = await this.getProfile(userId);
    profile.tier = TIER_PRESETS[newTier];
    await this.saveProfile(profile);
    return profile;
  }

  /**
   * Clear profile from cache
   *
   * @param userId - User ID to evict
   */
  evictProfile(userId: string): void {
    this.cache.delete(userId);
  }

  /**
   * Clear all cached profiles
   */
  clearCache(): void {
    this.cache.clear();
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): { size: number; maxTtlMs: number } {
    return {
      size: this.cache.size,
      maxTtlMs: this.cacheTtlMs,
    };
  }

  private cacheProfile(profile: UserProfile): void {
    this.cache.set(profile.userId, {
      profile,
      expiresAt: Date.now() + this.cacheTtlMs,
    });
  }
}

/**
 * Serialize profile to JSON-safe object
 */
export function serializeProfile(profile: UserProfile): Record<string, any> {
  return {
    user_id: profile.userId,
    created_at: profile.createdAt?.toISOString(),
    tier: profile.tier,
    custom_daily_budget: profile.customDailyBudget,
    custom_requests_per_hour: profile.customRequestsPerHour,
    custom_requests_per_day: profile.customRequestsPerDay,
    preferred_models: profile.preferredModels,
    cost_sensitivity: profile.costSensitivity,
    preferred_domains: profile.preferredDomains,
    domain_models: profile.domainModels,
    latency: profile.latency,
    optimization: profile.optimization,
    enable_content_moderation: profile.enableContentModeration,
    enable_pii_detection: profile.enablePiiDetection,
    metadata: profile.metadata,
  };
}

/**
 * Deserialize profile from JSON
 */
export function deserializeProfile(data: Record<string, any>): UserProfile {
  return {
    userId: data.user_id,
    createdAt: data.created_at ? new Date(data.created_at) : undefined,
    tier: data.tier,
    customDailyBudget: data.custom_daily_budget,
    customRequestsPerHour: data.custom_requests_per_hour,
    customRequestsPerDay: data.custom_requests_per_day,
    preferredModels: data.preferred_models,
    costSensitivity: data.cost_sensitivity,
    preferredDomains: data.preferred_domains,
    domainModels: data.domain_models,
    latency: data.latency,
    optimization: data.optimization,
    enableContentModeration: data.enable_content_moderation,
    enablePiiDetection: data.enable_pii_detection,
    metadata: data.metadata,
  };
}

// ==================== HELPER FUNCTIONS ====================

/**
 * Get effective daily budget for a profile
 *
 * Returns custom budget if set, otherwise tier default
 *
 * @param profile - User profile
 * @returns Effective daily budget or undefined
 */
export function getDailyBudget(profile: UserProfile): number | undefined {
  return profile.customDailyBudget !== undefined
    ? profile.customDailyBudget
    : profile.tier.dailyBudget;
}

/**
 * Get effective requests per hour for a profile
 *
 * Returns custom limit if set, otherwise tier default
 *
 * @param profile - User profile
 * @returns Effective hourly request limit or undefined
 */
export function getRequestsPerHour(profile: UserProfile): number | undefined {
  return profile.customRequestsPerHour !== undefined
    ? profile.customRequestsPerHour
    : profile.tier.requestsPerHour;
}

/**
 * Get effective requests per day for a profile
 *
 * Returns custom limit if set, otherwise tier default
 *
 * @param profile - User profile
 * @returns Effective daily request limit or undefined
 */
export function getRequestsPerDay(profile: UserProfile): number | undefined {
  return profile.customRequestsPerDay !== undefined
    ? profile.customRequestsPerDay
    : profile.tier.requestsPerDay;
}

/**
 * Get optimization weights for a profile
 *
 * Returns explicit weights if set, otherwise derives from cost sensitivity
 *
 * @param profile - User profile
 * @returns Optimization weights
 */
export function getOptimizationWeights(profile: UserProfile): OptimizationWeights {
  if (profile.optimization) {
    return profile.optimization;
  }

  // Fallback to cost sensitivity preset
  const sensitivity = profile.costSensitivity ?? 'balanced';
  return OPTIMIZATION_PRESETS[sensitivity];
}

/**
 * Get latency profile for a profile
 *
 * Returns explicit latency profile if set, otherwise standard preset
 *
 * @param profile - User profile
 * @returns Latency profile
 */
export function getLatencyProfile(profile: UserProfile): LatencyProfile {
  return profile.latency ?? LATENCY_PRESETS.standard;
}
