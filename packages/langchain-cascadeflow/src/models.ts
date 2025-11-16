/**
 * Model discovery and analysis for LangChain models
 *
 * This module helps users discover which of THEIR configured LangChain
 * models work best for cascading, without requiring any specific API keys.
 *
 * Users bring their own models - we just help them find the best pairs!
 */

import type { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { analyzeCascadePair, suggestCascadePairs, type CascadeAnalysis } from './helpers.js';

/**
 * Model pricing reference (per 1M tokens)
 * This is read-only reference data to help users understand costs
 */
export const MODEL_PRICING_REFERENCE = {
  // OpenAI Models
  'gpt-4o-mini': { input: 0.15, output: 0.60, tier: 'fast' },
  'gpt-4o': { input: 2.50, output: 10.00, tier: 'powerful' },
  'gpt-4-turbo': { input: 10.00, output: 30.00, tier: 'powerful' },
  'gpt-3.5-turbo': { input: 0.50, output: 1.50, tier: 'fast' },

  // Anthropic Models
  'claude-3-haiku-20240307': { input: 0.25, output: 1.25, tier: 'fast' },
  'claude-3-5-haiku-20241022': { input: 0.80, output: 4.00, tier: 'balanced' },
  'claude-3-5-sonnet-20241022': { input: 3.00, output: 15.00, tier: 'powerful' },
  'claude-3-sonnet-20240229': { input: 3.00, output: 15.00, tier: 'balanced' },
  'claude-3-opus-20240229': { input: 15.00, output: 75.00, tier: 'powerful' },

  // Google Models
  'gemini-1.5-flash': { input: 0.075, output: 0.30, tier: 'fast' },
  'gemini-1.5-pro': { input: 1.25, output: 5.00, tier: 'powerful' },
} as const;

/**
 * Extract model name from a LangChain model instance
 */
function getModelName(model: BaseChatModel): string {
  const modelAny = model as any;
  return modelAny.model || modelAny.modelName || modelAny.model_name || model._llmType();
}

/**
 * Discover and analyze cascade pairs from user's models
 *
 * This is the main helper - give it YOUR models and it will suggest
 * the best cascade configurations.
 *
 * @param models - Array of YOUR configured LangChain models
 * @param options - Analysis options
 * @returns Ranked cascade pair suggestions
 *
 * @example
 * ```typescript
 * // YOUR models (already configured with YOUR API keys)
 * const myModels = [
 *   new ChatOpenAI({ model: 'gpt-4o-mini' }),
 *   new ChatOpenAI({ model: 'gpt-4o' }),
 *   new ChatAnthropic({ model: 'claude-3-haiku' }),
 * ];
 *
 * // Find best cascade pairs
 * const suggestions = discoverCascadePairs(myModels);
 *
 * // Use the best one
 * const best = suggestions[0];
 * const cascade = new CascadeWrapper({
 *   drafter: best.drafter,
 *   verifier: best.verifier,
 * });
 * ```
 */
export function discoverCascadePairs(
  models: BaseChatModel[],
  options: {
    minSavings?: number;
    requireSameProvider?: boolean;
  } = {}
): Array<{
  drafter: BaseChatModel;
  verifier: BaseChatModel;
  analysis: CascadeAnalysis;
  rank: number;
}> {
  const minSavings = options.minSavings ?? 20;

  // Use the existing suggestCascadePairs helper
  let suggestions = suggestCascadePairs(models);

  // Filter by provider if requested
  if (options.requireSameProvider) {
    suggestions = suggestions.filter(s => {
      const drafterProvider = getProvider(s.drafter);
      const verifierProvider = getProvider(s.verifier);
      return drafterProvider === verifierProvider;
    });
  }

  // Filter by minimum savings
  suggestions = suggestions.filter(s => s.analysis.estimatedSavings >= minSavings);

  // Add ranking
  return suggestions.map((s, i) => ({
    ...s,
    rank: i + 1,
  }));
}

/**
 * Get provider name from a model
 */
function getProvider(model: BaseChatModel): string {
  const modelName = getModelName(model).toLowerCase();

  if (modelName.includes('gpt') || modelName.includes('openai')) return 'openai';
  if (modelName.includes('claude') || modelName.includes('anthropic')) return 'anthropic';
  if (modelName.includes('gemini') || modelName.includes('google')) return 'google';
  if (modelName.includes('ollama')) return 'ollama';

  return 'unknown';
}

/**
 * Analyze a user's model and provide insights
 *
 * @param model - YOUR configured LangChain model
 * @returns Analysis with pricing and tier information
 *
 * @example
 * ```typescript
 * const myModel = new ChatOpenAI({ model: 'gpt-4o' });
 * const info = analyzeModel(myModel);
 * console.log(info.modelName); // 'gpt-4o'
 * console.log(info.tier); // 'powerful'
 * console.log(info.estimatedCost); // { input: 2.50, output: 10.00 }
 * ```
 */
export function analyzeModel(model: BaseChatModel): {
  modelName: string;
  provider: string;
  tier: 'fast' | 'balanced' | 'powerful' | 'unknown';
  estimatedCost: { input: number; output: number } | null;
  recommendation: string;
} {
  const modelName = getModelName(model);
  const provider = getProvider(model);

  // Look up pricing
  const pricing = Object.entries(MODEL_PRICING_REFERENCE).find(([key]) =>
    modelName.toLowerCase().includes(key.toLowerCase())
  );

  const estimatedCost = pricing ? { input: pricing[1].input, output: pricing[1].output } : null;
  const tier = pricing?.[ 1].tier || 'unknown';

  // Generate recommendation
  let recommendation = '';
  if (tier === 'fast') {
    recommendation = 'Good choice for drafter (cheap, fast model)';
  } else if (tier === 'powerful') {
    recommendation = 'Good choice for verifier (expensive, accurate model)';
  } else if (tier === 'balanced') {
    recommendation = 'Can work as either drafter or verifier';
  } else {
    recommendation = 'Unknown model - consider testing cascade performance';
  }

  return {
    modelName,
    provider,
    tier,
    estimatedCost,
    recommendation,
  };
}

/**
 * Compare multiple models and rank them for cascade use
 *
 * @param models - YOUR configured models to compare
 * @returns Ranked models with recommendations
 *
 * @example
 * ```typescript
 * const myModels = [
 *   new ChatOpenAI({ model: 'gpt-4o-mini' }),
 *   new ChatOpenAI({ model: 'gpt-4o' }),
 *   new ChatAnthropic({ model: 'claude-3-5-sonnet' }),
 * ];
 *
 * const comparison = compareModels(myModels);
 * console.log(comparison.drafterCandidates); // Best for drafter
 * console.log(comparison.verifierCandidates); // Best for verifier
 * ```
 */
export function compareModels(models: BaseChatModel[]): {
  drafterCandidates: Array<{ model: BaseChatModel; analysis: ReturnType<typeof analyzeModel> }>;
  verifierCandidates: Array<{ model: BaseChatModel; analysis: ReturnType<typeof analyzeModel> }>;
  all: Array<{ model: BaseChatModel; analysis: ReturnType<typeof analyzeModel> }>;
} {
  const analyzed = models.map(model => ({
    model,
    analysis: analyzeModel(model),
  }));

  // Sort by cost (input + output average)
  const sorted = [...analyzed].sort((a, b) => {
    const aCost = a.analysis.estimatedCost
      ? (a.analysis.estimatedCost.input + a.analysis.estimatedCost.output) / 2
      : Infinity;
    const bCost = b.analysis.estimatedCost
      ? (b.analysis.estimatedCost.input + b.analysis.estimatedCost.output) / 2
      : Infinity;
    return aCost - bCost;
  });

  // Drafters = cheap models (first half)
  const drafterCandidates = sorted.slice(0, Math.ceil(sorted.length / 2));

  // Verifiers = expensive models (second half)
  const verifierCandidates = sorted.slice(Math.ceil(sorted.length / 2));

  return {
    drafterCandidates,
    verifierCandidates,
    all: analyzed,
  };
}

/**
 * Quick helper to find the best cascade pair from user's models
 *
 * @param models - YOUR configured LangChain models
 * @returns Best drafter and verifier, or null if no good pair found
 *
 * @example
 * ```typescript
 * const myModels = [
 *   new ChatOpenAI({ model: 'gpt-4o-mini' }),
 *   new ChatOpenAI({ model: 'gpt-4o' }),
 * ];
 *
 * const best = findBestCascadePair(myModels);
 * if (best) {
 *   const cascade = new CascadeWrapper({
 *     drafter: best.drafter,
 *     verifier: best.verifier,
 *   });
 * }
 * ```
 */
export function findBestCascadePair(models: BaseChatModel[]): {
  drafter: BaseChatModel;
  verifier: BaseChatModel;
  estimatedSavings: number;
  analysis: CascadeAnalysis;
} | null {
  const suggestions = discoverCascadePairs(models);

  if (suggestions.length === 0) return null;

  const best = suggestions[0];
  return {
    drafter: best.drafter,
    verifier: best.verifier,
    estimatedSavings: best.analysis.estimatedSavings,
    analysis: best.analysis,
  };
}

/**
 * Validate that a model pair makes sense for cascading
 *
 * @param drafter - YOUR configured drafter model
 * @param verifier - YOUR configured verifier model
 * @returns Validation result with warnings
 *
 * @example
 * ```typescript
 * const result = validateCascadePair(
 *   new ChatOpenAI({ model: 'gpt-4o-mini' }),
 *   new ChatOpenAI({ model: 'gpt-4o' })
 * );
 *
 * if (!result.valid) {
 *   console.warn('Issues:', result.warnings);
 * }
 * ```
 */
export function validateCascadePair(
  drafter: BaseChatModel,
  verifier: BaseChatModel
): {
  valid: boolean;
  warnings: string[];
  estimatedSavings: number;
  recommendation: string;
} {
  const analysis = analyzeCascadePair(drafter, verifier);

  return {
    valid: analysis.valid,
    warnings: analysis.warnings,
    estimatedSavings: analysis.estimatedSavings,
    recommendation: analysis.recommendation,
  };
}

// Re-export helpers for convenience
export { analyzeCascadePair, suggestCascadePairs } from './helpers.js';
