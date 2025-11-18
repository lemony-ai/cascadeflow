/**
 * Pre-execution router based on query complexity
 *
 * This router makes decisions BEFORE cascade execution starts,
 * routing queries to either cascade or direct execution based
 * on detected complexity level.
 *
 * Routing Logic:
 * - TRIVIAL/SIMPLE/MODERATE → CASCADE (cost optimization)
 * - HARD/EXPERT → DIRECT_BEST (quality priority)
 *
 * Port from Python cascadeflow/routing/pre_router.py
 */

import { ComplexityDetector } from '../complexity';
import type { QueryComplexity } from '../types';
import {
  Router,
  RoutingStrategy,
  RoutingDecisionHelper,
  type RoutingDecision,
} from './base';

/**
 * Configuration for PreRouter
 */
export interface PreRouterConfig {
  /** Enable cascade routing (if false, always direct) */
  enableCascade?: boolean;

  /** Custom complexity detector */
  complexityDetector?: ComplexityDetector;

  /** Which complexities should use cascade */
  cascadeComplexities?: QueryComplexity[];

  /** Enable verbose logging */
  verbose?: boolean;
}

/**
 * Statistics tracked by PreRouter
 */
export interface PreRouterStats {
  /** Total queries routed */
  totalQueries: number;

  /** Distribution by complexity */
  byComplexity: Record<string, number>;

  /** Distribution by strategy */
  byStrategy: Record<string, number>;

  /** Cascade rate percentage */
  cascadeRate: string;

  /** Direct rate percentage */
  directRate: string;

  /** Number of forced direct routes */
  forcedDirect: number;

  /** Number of queries when cascade was disabled */
  cascadeDisabledCount: number;
}

/**
 * Complexity-based pre-execution router
 *
 * Makes routing decisions before cascade execution starts.
 * Routes based on detected query complexity:
 * - Simple queries → cascade for cost savings
 * - Complex queries → direct to best model for quality
 *
 * Features:
 * - Automatic complexity detection
 * - Configurable complexity thresholds
 * - Statistics tracking by complexity and strategy
 * - Confidence scoring for decisions
 *
 * Future Enhancements:
 * - User tier integration (premium → direct)
 * - Budget constraints (low budget → cascade)
 * - Historical performance learning
 * - Domain-specific routing rules
 *
 * @example
 * ```typescript
 * const router = new PreRouter({
 *   enableCascade: true,
 *   cascadeComplexities: ['trivial', 'simple', 'moderate'],
 * });
 *
 * const decision = await router.route('What is 2+2?');
 * console.log(decision.strategy); // 'cascade'
 *
 * const decision2 = await router.route('Explain quantum field theory');
 * console.log(decision2.strategy); // 'direct_best'
 * ```
 */
export class PreRouter extends Router {
  private enableCascade: boolean;
  private detector: ComplexityDetector;
  private cascadeComplexities: Set<QueryComplexity>;
  private verbose: boolean;
  private stats: {
    totalQueries: number;
    byComplexity: Map<string, number>;
    byStrategy: Map<string, number>;
    forcedDirect: number;
    cascadeDisabled: number;
  };

  constructor(config: PreRouterConfig = {}) {
    super();

    this.enableCascade = config.enableCascade ?? true;
    this.detector = config.complexityDetector || new ComplexityDetector();
    this.verbose = config.verbose ?? false;

    // Default: cascade for simple queries, direct for complex
    const defaultCascadeComplexities: QueryComplexity[] = [
      'trivial',
      'simple',
      'moderate',
    ];

    this.cascadeComplexities = new Set(
      config.cascadeComplexities || defaultCascadeComplexities
    );

    // Initialize statistics
    this.stats = {
      totalQueries: 0,
      byComplexity: new Map(),
      byStrategy: new Map(),
      forcedDirect: 0,
      cascadeDisabled: 0,
    };

    if (this.verbose) {
      console.log('PreRouter initialized:');
      console.log(`  Cascade enabled: ${this.enableCascade}`);
      console.log(`  Cascade complexities: ${Array.from(this.cascadeComplexities).join(', ')}`);
      const directComplexities = (['trivial', 'simple', 'moderate', 'hard', 'expert'] as QueryComplexity[])
        .filter((c) => !this.cascadeComplexities.has(c));
      console.log(`  Direct complexities: ${directComplexities.join(', ')}`);
    }
  }

  /**
   * Route query based on complexity
   *
   * Context keys (optional):
   * - 'complexity': Override auto-detection (QueryComplexity string)
   * - 'complexityHint': String hint for complexity
   * - 'forceDirect': Force direct routing
   * - 'userTier': User tier (for future premium routing)
   * - 'budget': Budget constraint (for future cost-aware routing)
   *
   * @param query - User query text
   * @param context - Optional context dict
   * @returns RoutingDecision with strategy and metadata
   *
   * @example
   * ```typescript
   * // Auto-detect complexity
   * const decision1 = await router.route('What is 2+2?');
   *
   * // Override complexity
   * const decision2 = await router.route('Complex query', {
   *   complexity: 'expert'
   * });
   *
   * // Force direct routing
   * const decision3 = await router.route('Any query', {
   *   forceDirect: true
   * });
   * ```
   */
  async route(
    query: string,
    context: Record<string, any> = {}
  ): Promise<RoutingDecision> {
    // Update stats
    this.stats.totalQueries++;

    // === STEP 1: Detect Complexity ===
    let complexity: QueryComplexity;
    let complexityConfidence: number;

    if ('complexity' in context) {
      // Pre-detected complexity passed in
      complexity = context.complexity as QueryComplexity;
      complexityConfidence = context.complexityConfidence ?? 1.0;
    } else if ('complexityHint' in context) {
      // String hint provided
      const hint = context.complexityHint.toLowerCase();
      if (this.isValidComplexity(hint)) {
        complexity = hint as QueryComplexity;
        complexityConfidence = 1.0;
      } else {
        // Invalid hint, auto-detect
        const result = this.detector.detect(query);
        complexity = result.complexity;
        complexityConfidence = result.confidence;
      }
    } else {
      // Auto-detect complexity
      const result = this.detector.detect(query);
      complexity = result.complexity;
      complexityConfidence = result.confidence;
    }

    // Track complexity
    const complexityCount = this.stats.byComplexity.get(complexity) || 0;
    this.stats.byComplexity.set(complexity, complexityCount + 1);

    // === STEP 2: Make Routing Decision ===
    const forceDirect = context.forceDirect === true;

    let strategy: RoutingStrategy;
    let reason: string;
    let confidence: number;

    if (forceDirect) {
      // Forced direct routing
      strategy = RoutingStrategy.DIRECT_BEST;
      reason = 'Forced direct routing (bypass cascade)';
      confidence = 1.0;
      this.stats.forcedDirect++;
    } else if (!this.enableCascade) {
      // Cascade system disabled
      strategy = RoutingStrategy.DIRECT_BEST;
      reason = 'Cascade disabled, routing to best model';
      confidence = 1.0;
      this.stats.cascadeDisabled++;
    } else if (this.cascadeComplexities.has(complexity)) {
      // Simple query → cascade for cost optimization
      strategy = RoutingStrategy.CASCADE;
      reason = `${complexity} query suitable for cascade optimization`;
      confidence = complexityConfidence;
    } else {
      // Complex query → direct for quality
      strategy = RoutingStrategy.DIRECT_BEST;
      reason = `${complexity} query requires best model for quality`;
      confidence = complexityConfidence;
    }

    // Track strategy
    const strategyCount = this.stats.byStrategy.get(strategy) || 0;
    this.stats.byStrategy.set(strategy, strategyCount + 1);

    // === STEP 3: Build Decision ===
    const decision = RoutingDecisionHelper.create(
      strategy,
      reason,
      confidence,
      {
        complexity,
        complexityConfidence,
        router: 'pre',
        routerType: 'complexity_based',
        forceDirect,
        cascadeEnabled: this.enableCascade,
      }
    );

    if (this.verbose) {
      console.log(
        `[PreRouter] ${query.substring(0, 50)}... → ${strategy}\n` +
          `           Complexity: ${complexity} (conf: ${complexityConfidence.toFixed(2)})\n` +
          `           Reason: ${reason}`
      );
    }

    return decision;
  }

  /**
   * Get routing statistics
   *
   * @returns Dictionary with routing stats including:
   *   - total_queries: Total queries routed
   *   - by_complexity: Distribution by complexity
   *   - by_strategy: Distribution by strategy
   *   - cascade_rate: % of queries using cascade
   *   - direct_rate: % of queries using direct
   *
   * @example
   * ```typescript
   * const stats = router.getStats();
   * console.log(`Cascade rate: ${stats.cascadeRate}`);
   * console.log(`Complexity distribution:`, stats.byComplexity);
   * ```
   */
  getStats(): PreRouterStats {
    const total = this.stats.totalQueries;
    if (total === 0) {
      return {
        totalQueries: 0,
        byComplexity: {},
        byStrategy: {},
        cascadeRate: '0.0%',
        directRate: '0.0%',
        forcedDirect: 0,
        cascadeDisabledCount: 0,
      };
    }

    const cascadeCount = this.stats.byStrategy.get(RoutingStrategy.CASCADE) || 0;
    const directCount = Array.from(this.stats.byStrategy.entries())
      .filter(([strategy]) => strategy.startsWith('direct'))
      .reduce((sum, [, count]) => sum + count, 0);

    return {
      totalQueries: total,
      byComplexity: Object.fromEntries(this.stats.byComplexity),
      byStrategy: Object.fromEntries(this.stats.byStrategy),
      cascadeRate: `${((cascadeCount / total) * 100).toFixed(1)}%`,
      directRate: `${((directCount / total) * 100).toFixed(1)}%`,
      forcedDirect: this.stats.forcedDirect,
      cascadeDisabledCount: this.stats.cascadeDisabled,
    };
  }

  /**
   * Reset all routing statistics
   */
  resetStats(): void {
    this.stats = {
      totalQueries: 0,
      byComplexity: new Map(),
      byStrategy: new Map(),
      forcedDirect: 0,
      cascadeDisabled: 0,
    };
  }

  /**
   * Print formatted routing statistics
   */
  printStats(): void {
    const stats = this.getStats();

    if (stats.totalQueries === 0) {
      console.log('No routing statistics available');
      return;
    }

    console.log('\n' + '='.repeat(60));
    console.log('PRE-ROUTER STATISTICS');
    console.log('='.repeat(60));
    console.log(`Total Queries Routed: ${stats.totalQueries}`);
    console.log(`Cascade Rate:         ${stats.cascadeRate}`);
    console.log(`Direct Rate:          ${stats.directRate}`);
    console.log(`Forced Direct:        ${stats.forcedDirect}`);
    console.log();
    console.log('BY COMPLEXITY:');
    for (const [complexity, count] of Object.entries(stats.byComplexity)) {
      const pct = ((count / stats.totalQueries) * 100).toFixed(1);
      console.log(`  ${complexity.padEnd(12)}: ${String(count).padStart(4)} (${pct.padStart(5)}%)`);
    }
    console.log();
    console.log('BY STRATEGY:');
    for (const [strategy, count] of Object.entries(stats.byStrategy)) {
      const pct = ((count / stats.totalQueries) * 100).toFixed(1);
      console.log(`  ${strategy.padEnd(15)}: ${String(count).padStart(4)} (${pct.padStart(5)}%)`);
    }
    console.log('='.repeat(60) + '\n');
  }

  /**
   * Check if string is valid complexity
   */
  private isValidComplexity(str: string): boolean {
    return ['trivial', 'simple', 'moderate', 'hard', 'expert'].includes(str);
  }
}

/**
 * Create a PreRouter with configuration
 *
 * @param config - PreRouter configuration
 * @returns Configured PreRouter instance
 *
 * @example
 * ```typescript
 * import { createPreRouter } from '@cascadeflow/core';
 *
 * const router = createPreRouter({
 *   enableCascade: true,
 *   verbose: true,
 * });
 * ```
 */
export function createPreRouter(config?: PreRouterConfig): PreRouter {
  return new PreRouter(config);
}
