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
   * Enable automatic cost tracking via LangSmith metadata
   * @default true
   */
  enableCostTracking?: boolean;

  /**
   * Custom quality validator function
   * Returns confidence score between 0-1
   */
  qualityValidator?: (response: any) => Promise<number> | number;
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
