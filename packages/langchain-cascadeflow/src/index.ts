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

export { CascadeWrapper } from './wrapper.js';
export type { CascadeConfig, CascadeResult, CostMetadata } from './types.js';
export * from './utils.js';

import { CascadeWrapper } from './wrapper.js';
import type { CascadeConfig } from './types.js';

/**
 * Convenient helper to create a CascadeWrapper
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
export function withCascade(config: CascadeConfig): CascadeWrapper {
  return new CascadeWrapper(config);
}
