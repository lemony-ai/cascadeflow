/**
 * Shared harness pricing and energy profiles (TypeScript port).
 *
 * Ported from cascadeflow/harness/pricing.py — single source of truth for
 * cost/energy estimation in the n8n integration.
 */

// USD per 1M tokens [input, output].
export const PRICING_USD_PER_M: Record<string, [number, number]> = {
  // OpenAI
  'gpt-4o': [2.50, 10.00],
  'gpt-4o-mini': [0.15, 0.60],
  'gpt-5': [1.25, 10.00],
  'gpt-5-mini': [0.20, 0.80],
  'gpt-4-turbo': [10.00, 30.00],
  'gpt-4': [30.00, 60.00],
  'gpt-3.5-turbo': [0.50, 1.50],
  'o1': [15.00, 60.00],
  'o1-mini': [3.00, 12.00],
  'o3-mini': [1.10, 4.40],
  // Anthropic
  'claude-sonnet-4': [3.00, 15.00],
  'claude-haiku-3.5': [1.00, 5.00],
  'claude-opus-4.5': [5.00, 25.00],
  // Google Gemini
  'gemini-2.5-flash': [0.15, 0.60],
  'gemini-2.5-pro': [1.25, 10.00],
  'gemini-2.0-flash': [0.10, 0.40],
  'gemini-1.5-flash': [0.075, 0.30],
  'gemini-1.5-pro': [1.25, 5.00],
};

export const DEFAULT_PRICING_USD_PER_M: [number, number] = [2.50, 10.00];

// Deterministic proxy coefficients for energy tracking.
export const ENERGY_COEFFICIENTS: Record<string, number> = {
  // OpenAI
  'gpt-4o': 1.0,
  'gpt-4o-mini': 0.3,
  'gpt-5': 1.2,
  'gpt-5-mini': 0.35,
  'gpt-4-turbo': 1.5,
  'gpt-4': 1.5,
  'gpt-3.5-turbo': 0.2,
  'o1': 2.0,
  'o1-mini': 0.8,
  'o3-mini': 0.5,
  // Anthropic
  'claude-sonnet-4': 1.0,
  'claude-haiku-3.5': 0.3,
  'claude-opus-4.5': 1.8,
  // Google Gemini
  'gemini-2.5-flash': 0.3,
  'gemini-2.5-pro': 1.2,
  'gemini-2.0-flash': 0.25,
  'gemini-1.5-flash': 0.2,
  'gemini-1.5-pro': 1.0,
};

export const DEFAULT_ENERGY_COEFFICIENT = 1.0;
export const ENERGY_OUTPUT_WEIGHT = 1.5;

// ---------------------------------------------------------------------------
// Fuzzy model-name resolution
// ---------------------------------------------------------------------------

// Strips version/preview/date suffixes.
// Matches: -preview, -preview-05-20, -20250120, -latest, -exp-0827, -it
const VERSION_SUFFIX_RE = /(-preview(?:-\d{2,4}-\d{2})?|-\d{8,}|-latest|-exp(?:-\d+)?|-it)$/;

// Cache for resolved model → pricing key lookups.
const pricingKeyCache = new Map<string, string | null>();

export function resolvePricingKey(model: string): string | null {
  const cached = pricingKeyCache.get(model);
  if (cached !== undefined) return cached;

  // Exact match
  if (model in PRICING_USD_PER_M) {
    pricingKeyCache.set(model, model);
    return model;
  }

  // Strip version suffixes and retry
  const stripped = model.replace(VERSION_SUFFIX_RE, '');
  if (stripped !== model && stripped in PRICING_USD_PER_M) {
    pricingKeyCache.set(model, stripped);
    return stripped;
  }

  // Longest-prefix match (e.g. "gemini-2.5-flash-8b" → "gemini-2.5-flash")
  let best: string | null = null;
  let bestLen = 0;
  for (const known of Object.keys(PRICING_USD_PER_M)) {
    if (model.startsWith(known) && known.length > bestLen) {
      best = known;
      bestLen = known.length;
    }
  }
  if (best !== null) {
    pricingKeyCache.set(model, best);
    return best;
  }

  pricingKeyCache.set(model, null);
  return null;
}

// ---------------------------------------------------------------------------
// Public estimation helpers
// ---------------------------------------------------------------------------

export function estimateCost(model: string, inputTokens: number, outputTokens: number): number {
  const key = resolvePricingKey(model);
  const [inPrice, outPrice] = key !== null
    ? (PRICING_USD_PER_M[key] ?? DEFAULT_PRICING_USD_PER_M)
    : DEFAULT_PRICING_USD_PER_M;
  return (inputTokens / 1_000_000) * inPrice + (outputTokens / 1_000_000) * outPrice;
}

export function estimateEnergy(model: string, inputTokens: number, outputTokens: number): number {
  const key = resolvePricingKey(model);
  const coeff = key !== null
    ? (ENERGY_COEFFICIENTS[key] ?? DEFAULT_ENERGY_COEFFICIENT)
    : DEFAULT_ENERGY_COEFFICIENT;
  return coeff * (inputTokens + outputTokens * ENERGY_OUTPUT_WEIGHT);
}

export function modelTotalPrice(model: string): number {
  const key = resolvePricingKey(model);
  const [inPrice, outPrice] = key !== null
    ? (PRICING_USD_PER_M[key] ?? DEFAULT_PRICING_USD_PER_M)
    : DEFAULT_PRICING_USD_PER_M;
  return inPrice + outPrice;
}
