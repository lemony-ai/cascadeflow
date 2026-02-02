import type { DomainType } from './config';

export interface CostBreakdown {
  drafter: number;
  verifier: number;
  total: number;
  domain?: number;
}

export interface SavingsBreakdown {
  usd: number;
  percent: number;
}

export interface CascadeFlowMetadata {
  model_used: string;
  domain: DomainType | null;
  confidence?: number;
  costs: CostBreakdown;
  savings: SavingsBreakdown;
}

export const calculateSavings = (
  totalCost: number,
  baselineCost?: number
): SavingsBreakdown => {
  const baseline = baselineCost ?? totalCost;
  const usd = Math.max(0, baseline - totalCost);
  const percent = baseline > 0 ? (usd / baseline) * 100 : 0;

  return { usd, percent };
};

export const buildCascadeMetadata = (params: {
  modelUsed: string;
  domain: DomainType | null;
  confidence?: number;
  costs: CostBreakdown;
  baselineCost?: number;
}): CascadeFlowMetadata => {
  return {
    model_used: params.modelUsed,
    domain: params.domain,
    confidence: params.confidence,
    costs: params.costs,
    savings: calculateSavings(params.costs.total, params.baselineCost),
  };
};
