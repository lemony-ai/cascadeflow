import type { PreRouter } from './routers/pre-router.js';
import type { QueryComplexity } from './complexity.js';

export interface DomainPolicy {
  /**
   * Optional quality threshold override for this domain
   */
  qualityThreshold?: number;

  /**
   * Always escalate to verifier after drafting
   */
  forceVerifier?: boolean;

  /**
   * Skip drafter and route directly to verifier
   */
  directToVerifier?: boolean;

  /**
   * Optional policy metadata for observability
   */
  metadata?: Record<string, any>;
}

/**
 * Configuration for the CascadeFlow wrapper
 */
export interface CascadeConfig {
  /**
   * The drafter model (cheap, fast) - tries first
   */
  drafter: any; // BaseChatModel from @langchain/core

  /**
   * The verifier model (expensive, accurate) - used when quality is insufficient
   */
  verifier: any; // BaseChatModel from @langchain/core

  /**
   * Quality threshold for accepting drafter responses (0-1)
   * @default 0.7
   */
  qualityThreshold?: number;

  /**
   * Enable automatic cost tracking
   * @default true
   */
  enableCostTracking?: boolean;

  /**
   * Cost tracking provider
   * - 'langsmith': Use LangSmith's server-side cost calculation (default, requires LANGSMITH_API_KEY)
   * - 'cascadeflow': Use CascadeFlow's built-in pricing table (no external dependencies)
   * @default 'langsmith'
   */
  costTrackingProvider?: 'langsmith' | 'cascadeflow';

  /**
   * Custom quality validator function
   * Returns confidence score between 0-1
   */
  qualityValidator?: (response: any) => Promise<number> | number;

  /**
   * Enable pre-routing based on query complexity
   * When enabled, 'hard' and 'expert' queries skip the drafter and go directly to the verifier
   * @default true
   */
  enablePreRouter?: boolean;

  /**
   * Custom PreRouter instance for advanced routing control
   * If not provided, a default PreRouter will be created when enablePreRouter is true
   */
  preRouter?: PreRouter;

  /**
   * Complexity levels that should use cascade (try drafter first)
   * Queries with other complexity levels go directly to verifier
   * @default ['trivial', 'simple', 'moderate']
   */
  cascadeComplexities?: QueryComplexity[];

  /**
   * Per-domain policy overrides (threshold/routing)
   * Domain keys are case-insensitive
   */
  domainPolicies?: Record<string, DomainPolicy>;
}

/**
 * Cascade execution result with cost metadata
 */
export interface CascadeResult {
  /**
   * The final response content
   */
  content: string;

  /**
   * Model that provided the final response ('drafter' | 'verifier')
   */
  modelUsed: 'drafter' | 'verifier';

  /**
   * Quality score of the drafter response (0-1)
   */
  drafterQuality?: number;

  /**
   * Whether the drafter response was accepted
   */
  accepted: boolean;

  /**
   * Cost of the drafter call
   */
  drafterCost: number;

  /**
   * Cost of the verifier call (0 if not used)
   */
  verifierCost: number;

  /**
   * Total cost of the cascade
   */
  totalCost: number;

  /**
   * Cost savings percentage (0-100)
   */
  savingsPercentage: number;

  /**
   * Latency in milliseconds
   */
  latencyMs: number;
}

/**
 * Internal cost calculation metadata
 */
export interface CostMetadata {
  drafterTokens: {
    input: number;
    output: number;
  };
  verifierTokens?: {
    input: number;
    output: number;
  };
  drafterCost: number;
  verifierCost: number;
  totalCost: number;
  savingsPercentage: number;
  modelUsed: 'drafter' | 'verifier';
  accepted: boolean;
  drafterQuality?: number;
}
