/**
 * @module @cascadeflow/langchain
 *
 * LangChain integration for cascadeflow - Add intelligent cost optimization
 * to your existing LangChain models without reconfiguration.
 *
 * @example
 * ```typescript
 * import { withCascade } from '@cascadeflow/langchain';
 * import { ChatOpenAI } from '@langchain/openai';
 *
 * // Your existing models
 * const drafter = new ChatOpenAI({ model: 'gpt-4o-mini' });
 * const verifier = new ChatOpenAI({ model: 'gpt-4o' });
 *
 * // Wrap with cascade (2 lines!)
 * const cascadeModel = withCascade({
 *   drafter,
 *   verifier,
 *   qualityThreshold: 0.7
 * });
 *
 * // Use like any LangChain model - all features preserved!
 * const result = await cascadeModel.invoke("What is TypeScript?");
 * console.log(result);
 *
 * // Check cascade stats
 * const stats = cascadeModel.getLastCascadeResult();
 * console.log(`Saved: ${stats.savingsPercentage}%`);
 * ```
 */

export { CascadeFlow } from './wrapper.js';
export { CascadeAgent } from './agent.js';
export type {
  CascadeConfig,
  CascadeResult,
  CostMetadata,
  DomainPolicy,
} from './types.js';
export type {
  CascadeAgentConfig,
  CascadeAgentRunResult,
  CascadeAgentRunOptions,
  AgentToolHandler,
} from './agent.js';
export * from './utils.js';
export { analyzeCascadePair, suggestCascadePairs } from './helpers.js';
export type { CascadeAnalysis } from './helpers.js';

// Routers and complexity detection
export { PreRouter, createPreRouter } from './routers/pre-router.js';
export type { PreRouterConfig, PreRouterStats } from './routers/pre-router.js';
export { Router, RoutingStrategy, RoutingDecisionHelper, RouterChain } from './routers/base.js';
export type { RoutingDecision } from './routers/base.js';
export { ComplexityDetector } from './complexity.js';
export type { QueryComplexity, ComplexityResult } from './complexity.js';

// Model discovery (works with YOUR models!)
export {
  MODEL_PRICING_REFERENCE,
  discoverCascadePairs,
  analyzeModel,
  compareModels,
  findBestCascadePair,
  validateCascadePair,
} from './models.js';

import { CascadeFlow } from './wrapper.js';
import type { CascadeConfig } from './types.js';

/**
 * Convenient helper to create a CascadeFlow model
 *
 * @param config - Cascade configuration with drafter/verifier models
 * @returns A wrapped model that cascades from drafter to verifier
 *
 * @example
 * ```typescript
 * const model = withCascade({
 *   drafter: new ChatOpenAI({ model: 'gpt-4o-mini' }),
 *   verifier: new ChatOpenAI({ model: 'gpt-4o' }),
 *   qualityThreshold: 0.7
 * });
 * ```
 */
export function withCascade(config: CascadeConfig): CascadeFlow {
  return new CascadeFlow(config);
}
