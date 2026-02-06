// Model pricing per 1M tokens

export interface ModelPricing {
  input: number;
  output: number;
}

export const PRICING: Record<string, ModelPricing> = {
  "gpt-4o-mini": { input: 0.15, output: 0.60 },
  "gpt-4o": { input: 2.50, output: 10.00 },
  "claude-haiku": { input: 0.25, output: 1.25 },
  "claude-opus": { input: 15.00, output: 75.00 },
};

export function calculateCost(
  model: string,
  inputTokens: number,
  outputTokens: number
): number {
  const pricing = PRICING[model];
  if (!pricing) return 0;
  return (
    (inputTokens / 1_000_000) * pricing.input +
    (outputTokens / 1_000_000) * pricing.output
  );
}

export function calculateSavings(
  actualCost: number,
  validatorOnlyCost: number
): number {
  if (validatorOnlyCost <= 0) return 0;
  return (1 - actualCost / validatorOnlyCost) * 100;
}
