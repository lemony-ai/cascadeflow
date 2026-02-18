import { RoutingStrategy } from '../routers/base';

/**
 * Rule-engine output consumed by routing and model selection.
 */
export interface RuleDecision {
  routingStrategy?: RoutingStrategy;
  reason?: string;
  confidence?: number;
  metadata?: Record<string, any>;
  preferredChannel?: string;
  modelName?: string;
  allowedModels?: string[];
  excludedModels?: string[];
  preferredModels?: string[];
  forcedModels?: string[];
  qualityThreshold?: number;
  maxBudget?: number;
  failoverChannel?: string;
}

/**
 * External form accepted for backward compatibility with snake_case payloads.
 */
export type RuleDecisionLike = RuleDecision & {
  routing_strategy?: RoutingStrategy | string;
  preferred_channel?: string;
  model_name?: string;
  allowed_models?: string[];
  excluded_models?: string[];
  preferred_models?: string[];
  forced_models?: string[];
  quality_threshold?: number;
  max_budget?: number;
  failover_channel?: string;
};
