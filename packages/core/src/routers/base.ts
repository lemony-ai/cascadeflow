/**
 * Base router interface for all routing strategies
 *
 * Routers decide HOW to execute a query before execution starts.
 * This is "pre-routing" - decisions made BEFORE calling models.
 *
 * Port from Python cascadeflow/routing/base.py
 */

/**
 * How to execute a query
 *
 * This tells the agent what execution path to take
 */
export enum RoutingStrategy {
  /** Route to cheapest model */
  DIRECT_CHEAP = 'direct_cheap',

  /** Route to best model */
  DIRECT_BEST = 'direct_best',

  /** Use cascade system */
  CASCADE = 'cascade',

  /** Call multiple models in parallel (future) */
  PARALLEL = 'parallel',
}

/**
 * Decision made by router about query execution
 *
 * This is what routers return to the agent
 */
export interface RoutingDecision {
  /** How to execute (DIRECT_BEST, CASCADE, etc) */
  strategy: RoutingStrategy;

  /** Human-readable explanation */
  reason: string;

  /** Confidence in this decision (0-1) */
  confidence: number;

  /** Additional routing metadata */
  metadata: Record<string, any>;

  /** Specific model to use (optional) */
  modelName?: string;

  /** Budget constraint (optional) */
  maxCost?: number;

  /** Quality requirement (optional) */
  minQuality?: number;
}

/**
 * Helper functions for RoutingDecision
 */
export class RoutingDecisionHelper {
  /**
   * Check if decision is direct routing
   */
  static isDirect(decision: RoutingDecision): boolean {
    return (
      decision.strategy === RoutingStrategy.DIRECT_BEST ||
      decision.strategy === RoutingStrategy.DIRECT_CHEAP
    );
  }

  /**
   * Check if decision is cascade routing
   */
  static isCascade(decision: RoutingDecision): boolean {
    return decision.strategy === RoutingStrategy.CASCADE;
  }

  /**
   * Validate routing decision
   */
  static validate(decision: RoutingDecision): void {
    if (decision.confidence < 0 || decision.confidence > 1) {
      throw new Error(`Confidence must be 0-1, got ${decision.confidence}`);
    }
  }

  /**
   * Create a routing decision
   */
  static create(
    strategy: RoutingStrategy,
    reason: string,
    confidence: number,
    metadata: Record<string, any> = {}
  ): RoutingDecision {
    const decision: RoutingDecision = {
      strategy,
      reason,
      confidence,
      metadata,
    };

    RoutingDecisionHelper.validate(decision);
    return decision;
  }
}

/**
 * Abstract base class for all routers
 *
 * Routers decide HOW to execute a query before execution starts.
 *
 * Future routers:
 * - PreRouter: Based on complexity (current implementation)
 * - SemanticRouter: Based on semantic similarity to examples
 * - DomainRouter: Based on detected domain (code, math, etc)
 * - HybridRouter: Combine multiple routing strategies
 * - LearnedRouter: ML-based routing decisions
 */
export abstract class Router {
  /**
   * Decide how to handle this query
   *
   * @param query - User query text
   * @param context - Optional context (user tier, budget, complexity, etc)
   * @returns RoutingDecision with strategy and metadata
   */
  abstract route(
    query: string,
    context?: Record<string, any>
  ): Promise<RoutingDecision>;

  /**
   * Get router statistics (optional override)
   *
   * @returns Dictionary with routing statistics
   */
  getStats(): Record<string, any> {
    return {};
  }

  /**
   * Reset router statistics (optional override)
   */
  resetStats(): void {
    // Override in subclasses
  }
}

/**
 * Chain multiple routers together
 *
 * Useful for combining different routing strategies.
 * First router to make a decision wins.
 *
 * @example
 * ```typescript
 * const chain = new RouterChain([
 *   new ToolRouter(),
 *   new TierRouter(),
 *   new PreRouter(),
 * ]);
 *
 * const decision = await chain.route('What is AI?');
 * ```
 */
export class RouterChain {
  private routers: Router[];

  constructor(routers: Router[]) {
    this.routers = routers;
  }

  /**
   * Route through chain of routers
   *
   * @param query - User query text
   * @param context - Optional context
   * @returns First non-null routing decision
   */
  async route(
    query: string,
    context?: Record<string, any>
  ): Promise<RoutingDecision> {
    for (const router of this.routers) {
      const decision = await router.route(query, context);
      if (decision) {
        return decision;
      }
    }

    // Fallback: direct to best
    return RoutingDecisionHelper.create(
      RoutingStrategy.DIRECT_BEST,
      'No router made a decision, using fallback',
      0.5,
      { fallback: true }
    );
  }
}
