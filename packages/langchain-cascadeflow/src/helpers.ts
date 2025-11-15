import { BaseChatModel } from '@langchain/core/language_models/chat_models';

/**
 * Model pricing information (per 1M tokens)
 */
interface ModelPricing {
  input: number;
  output: number;
}

/**
 * Result of analyzing a cascade pair
 */
export interface CascadeAnalysis {
  drafterModel: string;
  verifierModel: string;
  drafterCost: ModelPricing;
  verifierCost: ModelPricing;
  valid: boolean;
  warnings: string[];
  estimatedSavings: number;
  recommendation: string;
}

/**
 * Get pricing information for a model
 * Returns pricing per 1M tokens
 */
function getModelPricing(modelName: string): ModelPricing | null {
  // Normalize model name (remove version suffixes for lookup)
  const normalizedName = modelName.toLowerCase();

  // OpenAI Models
  if (normalizedName.includes('gpt-4o-mini')) {
    return { input: 0.150, output: 0.600 };
  }
  if (normalizedName.includes('gpt-4o')) {
    return { input: 2.50, output: 10.00 };
  }
  if (normalizedName.includes('gpt-4-turbo')) {
    return { input: 10.00, output: 30.00 };
  }
  if (normalizedName.includes('gpt-3.5-turbo')) {
    return { input: 0.50, output: 1.50 };
  }

  // Anthropic Models
  if (normalizedName.includes('claude-3-5-haiku') || normalizedName.includes('claude-3-haiku')) {
    return { input: 0.80, output: 4.00 };
  }
  if (normalizedName.includes('claude-3-5-sonnet') || normalizedName.includes('claude-3-sonnet')) {
    return { input: 3.00, output: 15.00 };
  }
  if (normalizedName.includes('claude-3-opus')) {
    return { input: 15.00, output: 75.00 };
  }

  // Unknown model
  return null;
}

/**
 * Extract model name from a LangChain model instance
 */
function extractModelName(model: BaseChatModel): string {
  // Try different property names that LangChain models use
  const modelAny = model as any;

  if (modelAny.model) return modelAny.model;
  if (modelAny.modelName) return modelAny.modelName;
  if (modelAny.model_name) return modelAny.model_name;

  // Fallback to _llmType if no model name found
  return model._llmType();
}

/**
 * Calculate estimated savings percentage
 * Assumes typical 70% drafter acceptance rate
 */
function calculateEstimatedSavings(
  drafterPricing: ModelPricing,
  verifierPricing: ModelPricing,
  acceptanceRate: number = 0.7
): number {
  // Average tokens for a typical query
  const avgInputTokens = 500;
  const avgOutputTokens = 300;

  // Cost if always using verifier
  const verifierOnlyCost =
    (avgInputTokens / 1_000_000) * verifierPricing.input +
    (avgOutputTokens / 1_000_000) * verifierPricing.output;

  // Cost with cascade (drafter tries all, verifier only on failures)
  const drafterCost =
    (avgInputTokens / 1_000_000) * drafterPricing.input +
    (avgOutputTokens / 1_000_000) * drafterPricing.output;

  const cascadeCost =
    drafterCost + // Always try drafter
    (1 - acceptanceRate) * verifierOnlyCost; // Verifier only when drafter fails

  // Calculate savings
  if (verifierOnlyCost === 0) return 0;

  const savings = ((verifierOnlyCost - cascadeCost) / verifierOnlyCost) * 100;
  return Math.max(0, Math.min(100, savings));
}

/**
 * Analyze a cascade configuration and provide insights
 *
 * @param drafter - The drafter (cheap, fast) model instance
 * @param verifier - The verifier (expensive, accurate) model instance
 * @returns Analysis with pricing, validation, and recommendations
 *
 * @example
 * ```typescript
 * const drafter = new ChatOpenAI({ model: 'gpt-4o-mini' });
 * const verifier = new ChatOpenAI({ model: 'gpt-4o' });
 *
 * const analysis = analyzeCascadePair(drafter, verifier);
 * console.log(analysis.estimatedSavings); // => 55-65%
 * console.log(analysis.warnings); // => []
 * ```
 */
export function analyzeCascadePair(
  drafter: BaseChatModel,
  verifier: BaseChatModel
): CascadeAnalysis {
  const drafterModel = extractModelName(drafter);
  const verifierModel = extractModelName(verifier);

  const drafterPricing = getModelPricing(drafterModel);
  const verifierPricing = getModelPricing(verifierModel);

  const warnings: string[] = [];
  let valid = true;

  // Check if we have pricing info
  if (!drafterPricing) {
    warnings.push(`Unknown pricing for drafter model: ${drafterModel}`);
  }
  if (!verifierPricing) {
    warnings.push(`Unknown pricing for verifier model: ${verifierModel}`);
  }

  // Validate configuration
  if (drafterPricing && verifierPricing) {
    // Check if drafter is more expensive than verifier (misconfiguration)
    const drafterAvgCost = (drafterPricing.input + drafterPricing.output) / 2;
    const verifierAvgCost = (verifierPricing.input + verifierPricing.output) / 2;

    if (drafterAvgCost > verifierAvgCost) {
      valid = false;
      warnings.push(
        `Drafter (${drafterModel}) is more expensive than verifier (${verifierModel}). ` +
        `This defeats the purpose of cascading. Consider swapping them.`
      );
    }

    // Check if models are the same
    if (drafterModel === verifierModel) {
      valid = false;
      warnings.push(
        `Drafter and verifier are the same model (${drafterModel}). ` +
        `Cascading provides no benefit in this configuration.`
      );
    }

    // Check if drafter is only slightly cheaper
    const savingsRatio = (verifierAvgCost - drafterAvgCost) / verifierAvgCost;
    if (savingsRatio < 0.3 && savingsRatio > 0) {
      warnings.push(
        `Drafter is only ${(savingsRatio * 100).toFixed(0)}% cheaper than verifier. ` +
        `Consider using a cheaper drafter for better cost savings.`
      );
    }
  }

  // Calculate estimated savings
  const estimatedSavings = drafterPricing && verifierPricing
    ? calculateEstimatedSavings(drafterPricing, verifierPricing)
    : 0;

  // Generate recommendation
  let recommendation = '';
  if (!valid) {
    recommendation = 'Configuration needs attention. See warnings above.';
  } else if (estimatedSavings > 50) {
    recommendation = 'Excellent cascade configuration! Expected savings > 50%.';
  } else if (estimatedSavings > 30) {
    recommendation = 'Good cascade configuration. Expected savings 30-50%.';
  } else if (estimatedSavings > 0) {
    recommendation = 'Marginal cascade configuration. Consider a cheaper drafter.';
  } else {
    recommendation = 'Unable to estimate savings (unknown model pricing).';
  }

  return {
    drafterModel,
    verifierModel,
    drafterCost: drafterPricing || { input: 0, output: 0 },
    verifierCost: verifierPricing || { input: 0, output: 0 },
    valid,
    warnings,
    estimatedSavings,
    recommendation,
  };
}

/**
 * Suggest optimal cascade pairs from a list of available models
 *
 * @param models - Array of LangChain model instances
 * @returns Array of suggested cascade configurations
 *
 * @example
 * ```typescript
 * const models = [
 *   new ChatOpenAI({ model: 'gpt-4o-mini' }),
 *   new ChatOpenAI({ model: 'gpt-4o' }),
 *   new ChatAnthropic({ model: 'claude-3-5-haiku' }),
 * ];
 *
 * const suggestions = suggestCascadePairs(models);
 * // => [{ drafter: models[0], verifier: models[1], estimatedSavings: 60% }]
 * ```
 */
export function suggestCascadePairs(
  models: BaseChatModel[]
): Array<{
  drafter: BaseChatModel;
  verifier: BaseChatModel;
  analysis: CascadeAnalysis;
}> {
  const suggestions: Array<{
    drafter: BaseChatModel;
    verifier: BaseChatModel;
    analysis: CascadeAnalysis;
  }> = [];

  // Try all pairs
  for (let i = 0; i < models.length; i++) {
    for (let j = 0; j < models.length; j++) {
      if (i === j) continue;

      const analysis = analyzeCascadePair(models[i], models[j]);

      // Only include valid pairs with meaningful savings
      if (analysis.valid && analysis.estimatedSavings > 20) {
        suggestions.push({
          drafter: models[i],
          verifier: models[j],
          analysis,
        });
      }
    }
  }

  // Sort by estimated savings (highest first)
  suggestions.sort((a, b) => b.analysis.estimatedSavings - a.analysis.estimatedSavings);

  return suggestions;
}
