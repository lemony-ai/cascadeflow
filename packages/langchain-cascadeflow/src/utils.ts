import type { CostMetadata } from './types.js';

/**
 * Model pricing per 1M tokens (input/output)
 * TODO: Import from @cascadeflow/core or make configurable
 */
const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  // OpenAI
  'gpt-4o-mini': { input: 0.150, output: 0.600 },
  'gpt-4o': { input: 2.50, output: 10.00 },
  'gpt-4-turbo': { input: 10.00, output: 30.00 },
  'gpt-3.5-turbo': { input: 0.50, output: 1.50 },

  // Anthropic
  'claude-3-5-sonnet-20241022': { input: 3.00, output: 15.00 },
  'claude-3-5-haiku-20241022': { input: 0.80, output: 4.00 },
  'claude-3-opus-20240229': { input: 15.00, output: 75.00 },
  'claude-3-sonnet-20240229': { input: 3.00, output: 15.00 },
  'claude-3-haiku-20240307': { input: 0.25, output: 1.25 },
};

/**
 * Calculate cost based on token usage and model
 */
export function calculateCost(
  modelName: string,
  inputTokens: number,
  outputTokens: number
): number {
  const pricing = MODEL_PRICING[modelName];

  if (!pricing) {
    console.warn(`Unknown model for pricing: ${modelName}, using default`);
    return 0;
  }

  const inputCost = (inputTokens / 1_000_000) * pricing.input;
  const outputCost = (outputTokens / 1_000_000) * pricing.output;

  return inputCost + outputCost;
}

/**
 * Extract token usage from LangChain response
 */
export function extractTokenUsage(response: any): { input: number; output: number } {
  // LangChain response structure varies by provider
  const usage = response?.llmOutput?.tokenUsage || response?.usage_metadata || {};

  return {
    input: usage.prompt_tokens || usage.input_tokens || 0,
    output: usage.completion_tokens || usage.output_tokens || 0,
  };
}

/**
 * Calculate quality score from LangChain response
 * Uses logprobs if available, otherwise heuristics
 */
export function calculateQuality(response: any): number {
  // 1. Try logprobs-based confidence
  const logprobs = response?.generations?.[0]?.[0]?.generationInfo?.logprobs;
  if (logprobs && Array.isArray(logprobs.token_logprobs)) {
    const avgLogprob = logprobs.token_logprobs.reduce((a: number, b: number) => a + b, 0) / logprobs.token_logprobs.length;
    const confidence = Math.exp(avgLogprob); // Convert log probability to probability
    return Math.max(0, Math.min(1, confidence));
  }

  // 2. Heuristic-based quality scoring
  const text = response?.generations?.[0]?.[0]?.text || response?.text || '';

  if (!text || text.length < 10) {
    return 0.1; // Very low quality for empty/short responses
  }

  // Check for common quality indicators
  let score = 0.5; // Base score

  // Length bonus (but not too verbose)
  if (text.length > 50 && text.length < 2000) score += 0.2;

  // Structure bonus (has punctuation, capitalization)
  if (/[.!?]/.test(text)) score += 0.1;
  if (/^[A-Z]/.test(text)) score += 0.1;

  // Penalize hedging phrases
  const hedgingPhrases = [
    'i think', 'maybe', 'possibly', 'perhaps',
    'i\'m not sure', 'it seems', 'it appears'
  ];
  const lowerText = text.toLowerCase();
  const hedgeCount = hedgingPhrases.filter(phrase => lowerText.includes(phrase)).length;
  score -= hedgeCount * 0.05;

  return Math.max(0, Math.min(1, score));
}

/**
 * Calculate savings percentage
 */
export function calculateSavings(drafterCost: number, verifierCost: number): number {
  if (verifierCost === 0) return 0;

  const totalCost = drafterCost + verifierCost;
  const potentialCost = verifierCost; // If we had used verifier directly

  return ((potentialCost - totalCost) / potentialCost) * 100;
}

/**
 * Create cost metadata for LangSmith injection
 */
export function createCostMetadata(
  drafterResponse: any,
  verifierResponse: any | null,
  drafterModel: string,
  verifierModel: string,
  accepted: boolean,
  drafterQuality: number
): CostMetadata {
  const drafterTokens = extractTokenUsage(drafterResponse);
  const drafterCost = calculateCost(drafterModel, drafterTokens.input, drafterTokens.output);

  let verifierTokens, verifierCost;
  if (verifierResponse) {
    verifierTokens = extractTokenUsage(verifierResponse);
    verifierCost = calculateCost(verifierModel, verifierTokens.input, verifierTokens.output);
  } else {
    verifierTokens = undefined;
    verifierCost = 0;
  }

  const totalCost = drafterCost + verifierCost;
  const savingsPercentage = calculateSavings(drafterCost, verifierCost);

  return {
    drafterTokens,
    verifierTokens,
    drafterCost,
    verifierCost,
    totalCost,
    savingsPercentage,
    modelUsed: accepted ? 'drafter' : 'verifier',
    accepted,
    drafterQuality,
  };
}
