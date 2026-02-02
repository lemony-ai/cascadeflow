import type { CascadePlan, CascadeStageConfig, ProviderRole } from './types';
import { vercelAIProviderRegistry } from './provider-registry';

const DEFAULT_ROLE: ProviderRole = 'drafter';

export function buildCascadePlan(stages: CascadeStageConfig[]): CascadePlan {
  const models = stages.map((stage) => {
    const provider = vercelAIProviderRegistry.get(stage.providerId);
    return provider.toModelConfig(stage.model, stage.overrides);
  });

  const roles = stages.map((stage) => stage.role ?? DEFAULT_ROLE);
  const fallbackOrder = stages.map(
    (stage) => `${stage.providerId}:${stage.model}`
  );
  const estimatedCostPer1k = models.reduce((sum, model) => sum + model.cost, 0);

  return {
    models,
    roles,
    fallbackOrder,
    estimatedCostPer1k,
  };
}

export function buildFallbackCascade(
  primary: CascadeStageConfig,
  fallbacks: CascadeStageConfig[]
): CascadePlan {
  return buildCascadePlan([primary, ...fallbacks]);
}

export function createDraftVerifierCascade(
  drafter: CascadeStageConfig,
  verifier: CascadeStageConfig,
  fallbacks: CascadeStageConfig[] = []
): CascadePlan {
  return buildCascadePlan([
    { ...drafter, role: 'drafter' },
    { ...verifier, role: 'verifier' },
    ...fallbacks,
  ]);
}
