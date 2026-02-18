import type { QueryComplexity, WorkflowProfile } from '../types';
import type { DomainConfig } from '../config/domain-config';
import type { TierRouterConfig } from '../routers/tier-router';

/**
 * Structured input for rule-engine evaluation.
 */
export interface RuleContext {
  query: string;
  complexity?: QueryComplexity | string;
  complexityConfidence?: number;
  detectedDomain?: string;
  domainConfidence?: number;
  domainConfig?: DomainConfig;
  hasTools?: boolean;
  hasMultiTurn?: boolean;
  hasCode?: boolean;
  hasToolPrompt?: boolean;
  userTier?: string;
  tierConfig?: TierRouterConfig;
  workflowName?: string;
  workflowProfile?: WorkflowProfile;
  kpiFlags?: Record<string, any>;
  tenantId?: string;
  channel?: string;
}
