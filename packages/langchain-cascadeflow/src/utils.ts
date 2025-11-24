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
  // LangChain ChatResult structure
  const llmOutput = response?.llmOutput || {};
  const usage = llmOutput?.tokenUsage || llmOutput?.usage || {};

  // OpenAI format (snake_case)
  if (usage.prompt_tokens || usage.completion_tokens) {
    return {
      input: usage.prompt_tokens || 0,
      output: usage.completion_tokens || 0,
    };
  }

  // OpenAI format (camelCase - LangChain uses this)
  if (usage.promptTokens || usage.completionTokens) {
    return {
      input: usage.promptTokens || 0,
      output: usage.completionTokens || 0,
    };
  }

  // Anthropic format
  if (usage.input_tokens || usage.output_tokens) {
    return {
      input: usage.input_tokens || 0,
      output: usage.output_tokens || 0,
    };
  }

  // Default
  return { input: 0, output: 0 };
}

/**
 * Calculate quality score from LangChain response
 * Uses logprobs if available, otherwise heuristics
 */
export function calculateQuality(response: any): number {
  // 1. Try logprobs-based confidence (OpenAI)
  const generationInfo = response?.generations?.[0]?.generationInfo;
  if (generationInfo?.logprobs?.content) {
    // OpenAI format: content is array of {token, logprob}
    const logprobs = generationInfo.logprobs.content
      .map((item: any) => item.logprob)
      .filter((lp: any) => lp !== null && lp !== undefined);

    if (logprobs.length > 0) {
      const avgLogprob = logprobs.reduce((a: number, b: number) => a + b, 0) / logprobs.length;
      const confidence = Math.exp(avgLogprob); // Convert log probability to probability
      return Math.max(0.1, Math.min(1, confidence * 1.5)); // Boost slightly
    }
  }

  // 2. Heuristic-based quality scoring
  // LangChain ChatResult has generations as a flat array, not nested
  const generation = response?.generations?.[0];
  const text = generation?.text || generation?.message?.content || '';

  if (!text || text.length < 5) {
    return 0.2; // Low quality for empty/very short responses
  }

  // Check for common quality indicators
  let score = 0.4; // Base score (lowered from 0.6 to match Python for realistic evaluation)

  // Length bonus (reasonable response) - increased thresholds to match Python
  if (text.length > 50) score += 0.1;  // Increased from 20
  if (text.length > 200) score += 0.1; // Increased from 100

  // Structure bonus (has punctuation, capitalization)
  if (/[.!?]/.test(text)) score += 0.05;
  if (/^[A-Z]/.test(text)) score += 0.05;

  // Completeness bonus (ends with punctuation) - reduced to match Python
  if (/[.!?]$/.test(text.trim())) score += 0.05; // Reduced from 0.1

  // Penalize hedging phrases - increased penalty to match Python
  const hedgingPhrases = [
    'i don\'t know', 'i\'m not sure', 'i cannot', 'i can\'t'
  ];
  const lowerText = text.toLowerCase();
  const hedgeCount = hedgingPhrases.filter(phrase => lowerText.includes(phrase)).length;
  score -= hedgeCount * 0.15; // Increased from 0.1 to match Python

  return Math.max(0.1, Math.min(1, score));
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
 * Create cost metadata with configurable provider
 * @param costProvider - 'langsmith' (server-side) or 'cascadeflow' (local calculation)
 */
export function createCostMetadata(
  drafterResponse: any,
  verifierResponse: any | null,
  drafterModel: string,
  verifierModel: string,
  accepted: boolean,
  drafterQuality: number,
  costProvider: 'langsmith' | 'cascadeflow' = 'langsmith'
): CostMetadata {
  const drafterTokens = extractTokenUsage(drafterResponse);

  let drafterCost: number;
  let verifierCost: number;
  let verifierTokens: { input: number; output: number } | undefined;

  if (costProvider === 'cascadeflow') {
    // Use CascadeFlow's built-in pricing calculation
    drafterCost = calculateCost(drafterModel, drafterTokens.input, drafterTokens.output);

    if (verifierResponse) {
      verifierTokens = extractTokenUsage(verifierResponse);
      verifierCost = calculateCost(verifierModel, verifierTokens.input, verifierTokens.output);
    } else {
      verifierTokens = undefined;
      verifierCost = 0;
    }
  } else {
    // LangSmith provider - costs calculated server-side
    // We still track tokens for metadata, but costs are 0 (calculated by LangSmith)
    drafterCost = 0;

    if (verifierResponse) {
      verifierTokens = extractTokenUsage(verifierResponse);
      verifierCost = 0;
    } else {
      verifierTokens = undefined;
      verifierCost = 0;
    }
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
