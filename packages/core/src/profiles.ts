/**
 * User Profile System for cascadeflow TypeScript (v0.2.1+)
 *
 * Multi-tenant subscription tier management for production applications.
 */

import { TierConfig, TierLevel, UserProfile } from './types';

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
    tier: profile.tier,
    custom_daily_budget: profile.customDailyBudget,
    custom_requests_per_hour: profile.customRequestsPerHour,
    custom_requests_per_day: profile.customRequestsPerDay,
    preferred_models: profile.preferredModels,
    preferred_domains: profile.preferredDomains,
    domain_models: profile.domainModels,
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
    tier: data.tier,
    customDailyBudget: data.custom_daily_budget,
    customRequestsPerHour: data.custom_requests_per_hour,
    customRequestsPerDay: data.custom_requests_per_day,
    preferredModels: data.preferred_models,
    preferredDomains: data.preferred_domains,
    domainModels: data.domain_models,
    enableContentModeration: data.enable_content_moderation,
    enablePiiDetection: data.enable_pii_detection,
    metadata: data.metadata,
  };
}
