import type { DomainConfig } from '../config/domain-config';
import { RoutingStrategy } from '../routers/base';
import type { TierRouterConfig } from '../routers/tier-router';
import type { QueryComplexity, WorkflowProfile } from '../types';
import type { RuleContext } from './context';
import type { RuleDecision, RuleDecisionLike } from './decision';

const COMPLEXITIES: QueryComplexity[] = ['trivial', 'simple', 'moderate', 'hard', 'expert'];

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

function isRoutingStrategy(value: string): value is RoutingStrategy {
  return (
    value === RoutingStrategy.CASCADE ||
    value === RoutingStrategy.DIRECT_BEST ||
    value === RoutingStrategy.DIRECT_CHEAP ||
    value === RoutingStrategy.PARALLEL
  );
}

function parseRoutingStrategy(value: unknown): RoutingStrategy | undefined {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim().toLowerCase();
  return isRoutingStrategy(normalized) ? normalized : undefined;
}

function cloneDecision(input: RuleDecision): RuleDecision {
  return {
    ...input,
    metadata: input.metadata ? { ...input.metadata } : {},
    allowedModels: input.allowedModels ? [...input.allowedModels] : undefined,
    excludedModels: input.excludedModels ? [...input.excludedModels] : undefined,
    preferredModels: input.preferredModels ? [...input.preferredModels] : undefined,
    forcedModels: input.forcedModels ? [...input.forcedModels] : undefined,
  };
}

export interface RuleEngineConfig {
  enableDomainRouting?: boolean;
  tiers?: Record<string, TierRouterConfig>;
  workflows?: Record<string, WorkflowProfile>;
  tenantRules?: Record<string, RuleDecisionLike | Record<string, unknown>>;
  channelModels?: Record<string, string[]>;
  channelFailover?: Record<string, string>;
  channelStrategies?: Record<string, RoutingStrategy | string>;
  verbose?: boolean;
}

/**
 * Rule engine that computes overrides from domain/tier/workflow/KPI context.
 */
export class RuleEngine {
  private enableDomainRouting: boolean;
  private tiers: Record<string, TierRouterConfig>;
  private workflows: Record<string, WorkflowProfile>;
  private tenantRules: Record<string, RuleDecisionLike | Record<string, unknown>>;
  private channelModels: Record<string, string[]>;
  private channelFailover: Record<string, string>;
  private channelStrategies: Record<string, RoutingStrategy | string>;
  private verbose: boolean;

  constructor(config: RuleEngineConfig = {}) {
    this.enableDomainRouting = config.enableDomainRouting ?? true;
    this.tiers = config.tiers ?? {};
    this.workflows = config.workflows ?? {};
    this.tenantRules = config.tenantRules ?? {};
    this.channelModels = config.channelModels ?? {};
    this.channelFailover = config.channelFailover ?? {};
    this.channelStrategies = config.channelStrategies ?? {};
    this.verbose = config.verbose ?? false;
  }

  decide(context: RuleContext): RuleDecision | undefined {
    let decision: RuleDecision | undefined;

    if (this.enableDomainRouting) {
      decision = this.mergeDecisions(decision, this.applyDomainRules(context));
    }
    decision = this.mergeDecisions(decision, this.applyTenantRules(context));
    decision = this.mergeDecisions(decision, this.applyChannelFailover(context));
    decision = this.mergeDecisions(decision, this.applyTierRules(context));
    decision = this.mergeDecisions(decision, this.applyWorkflowRules(context));
    decision = this.mergeDecisions(decision, this.applyKpiRules(context));

    if (this.verbose && decision) {
      // Keep this intentionally lightweight; full tracing belongs in telemetry.
      console.debug('[RuleEngine] decision', decision);
    }

    return decision;
  }

  private applyDomainRules(context: RuleContext): RuleDecision | undefined {
    const domainConfig = context.domainConfig;
    if (!domainConfig || domainConfig.enabled === false || !context.detectedDomain) {
      return undefined;
    }

    const complexity = this.coerceComplexity(context.complexity);
    const domainConfidence = context.domainConfidence ?? context.complexityConfidence ?? 0;
    const confidence = domainConfidence > 0 ? domainConfidence : 0.6;
    const domainCascadeComplexities = domainConfig.cascadeComplexities;
    const domainCascadeSet =
      domainCascadeComplexities && domainCascadeComplexities.length > 0
        ? new Set(
            domainCascadeComplexities
              .map((level) => this.coerceComplexity(level))
              .filter((level): level is QueryComplexity => Boolean(level))
          )
        : undefined;

    const metadata: Record<string, any> = {
      rule: 'domain_routing',
      domain: context.detectedDomain,
      domainConfidence: context.domainConfidence,
      domainCascadeComplexities,
      domainDrafter: this.getModelName(domainConfig.drafter),
      domainVerifier: this.getModelName(domainConfig.verifier),
      domainThreshold: domainConfig.threshold,
    };

    if (domainConfig.requireVerifier) {
      return {
        routingStrategy: RoutingStrategy.DIRECT_BEST,
        reason: `Rule: domain '${context.detectedDomain}' requires verifier`,
        confidence,
        metadata,
      };
    }

    if (domainCascadeSet && complexity) {
      if (domainCascadeSet.has(complexity)) {
        return {
          routingStrategy: RoutingStrategy.CASCADE,
          reason: `Rule: domain '${context.detectedDomain}' + ${complexity} → cascade`,
          confidence: Math.min(context.complexityConfidence ?? confidence, confidence),
          metadata,
        };
      }
      return {
        routingStrategy: RoutingStrategy.DIRECT_BEST,
        reason: `Rule: domain '${context.detectedDomain}' + ${complexity} → direct`,
        confidence,
        metadata,
      };
    }

    return {
      routingStrategy: RoutingStrategy.CASCADE,
      reason: `Rule: domain '${context.detectedDomain}' configured → cascade`,
      confidence,
      metadata,
    };
  }

  private applyTierRules(context: RuleContext): RuleDecision | undefined {
    const tier = context.tierConfig ?? (context.userTier ? this.tiers[context.userTier] : undefined);
    if (!tier) return undefined;

    const metadata: Record<string, any> = {
      rule: 'tier_constraints',
      tier: tier.name,
    };

    return {
      reason: `Tier '${tier.name}' constraints applied`,
      confidence: 0.7,
      metadata,
      allowedModels: tier.allowedModels ? [...tier.allowedModels] : undefined,
      excludedModels: tier.excludeModels ? [...tier.excludeModels] : undefined,
      qualityThreshold: tier.qualityThreshold,
      maxBudget: tier.maxBudget,
    };
  }

  private applyTenantRules(context: RuleContext): RuleDecision | undefined {
    const tenantId = context.tenantId;
    if (!tenantId) return undefined;

    const rule = this.tenantRules[tenantId];
    if (!rule) return undefined;

    const decision = this.decisionFromValue(rule);
    decision.metadata = {
      ...(decision.metadata ?? {}),
      rule: 'tenant_override',
      tenantId,
    };
    if (!decision.reason) {
      decision.reason = `Tenant '${tenantId}' override applied`;
    }
    if (!decision.confidence || decision.confidence === 0) {
      decision.confidence = 0.75;
    }
    return decision;
  }

  private applyChannelFailover(context: RuleContext): RuleDecision | undefined {
    const channel = context.channel;
    if (!channel) return undefined;

    let selectedChannel = channel;
    let models = this.channelModels[selectedChannel];
    let failover: string | undefined;

    if (!models || models.length === 0) {
      failover = this.channelFailover[selectedChannel];
      if (failover) {
        selectedChannel = failover;
        models = this.channelModels[selectedChannel];
      }
    }

    if ((!models || models.length === 0) && !failover) {
      return undefined;
    }

    const strategyValue = this.channelStrategies[selectedChannel] ?? this.channelStrategies[channel];
    let strategy = parseRoutingStrategy(strategyValue);
    if (!strategy && (selectedChannel === 'heartbeat' || selectedChannel === 'cron')) {
      strategy = RoutingStrategy.DIRECT_CHEAP;
    }

    const metadata: Record<string, any> = {
      rule: 'channel_routing',
      channel,
      selectedChannel,
      failoverChannel: failover,
      channelStrategy: strategy ?? null,
    };

    return {
      reason: `Channel '${channel}' routing applied`,
      confidence: 0.65,
      metadata,
      allowedModels: models && models.length > 0 ? [...models] : undefined,
      preferredChannel: selectedChannel,
      failoverChannel: failover,
      routingStrategy: strategy,
    };
  }

  private applyWorkflowRules(context: RuleContext): RuleDecision | undefined {
    const workflow = context.workflowProfile ?? (context.workflowName ? this.workflows[context.workflowName] : undefined);
    if (!workflow) return undefined;

    const metadata: Record<string, any> = {
      rule: 'workflow_overrides',
      workflow: workflow.name,
    };

    return {
      reason: `Workflow '${workflow.name}' overrides applied`,
      confidence: 0.8,
      metadata,
      forcedModels: workflow.forceModels ? [...workflow.forceModels] : undefined,
      preferredModels: workflow.preferredModels ? [...workflow.preferredModels] : undefined,
      excludedModels: workflow.excludeModels ? [...workflow.excludeModels] : undefined,
      qualityThreshold: workflow.qualityThresholdOverride,
      maxBudget: workflow.maxBudgetOverride,
    };
  }

  private applyKpiRules(context: RuleContext): RuleDecision | undefined {
    const flags = context.kpiFlags ?? {};
    if (Object.keys(flags).length === 0) return undefined;

    const metadata: Record<string, any> = {
      rule: 'kpi_flags',
      kpis: flags,
    };

    const profile = flags.profile;
    if (typeof profile === 'string') {
      const profileValue = profile.trim().toLowerCase();
      if (['quality', 'best', 'accuracy'].includes(profileValue)) {
        return {
          routingStrategy: RoutingStrategy.DIRECT_BEST,
          reason: 'KPI profile override → direct verifier',
          confidence: 0.75,
          metadata,
        };
      }
      if (['cost', 'cost_savings', 'cheap', 'fast'].includes(profileValue)) {
        return {
          routingStrategy: RoutingStrategy.CASCADE,
          reason: 'KPI profile override → cascade',
          confidence: 0.7,
          metadata,
        };
      }
    }

    const risk = flags.risk ?? flags.compliance;
    const riskString = risk == null ? '' : String(risk).toLowerCase();
    if (risk === true || ['high', 'strict', 'true', '1'].includes(riskString)) {
      return {
        routingStrategy: RoutingStrategy.DIRECT_BEST,
        reason: 'KPI risk/compliance override → direct verifier',
        confidence: 0.8,
        metadata,
      };
    }

    return {
      reason: 'KPI flags recorded',
      confidence: 0.5,
      metadata,
    };
  }

  private decisionFromValue(value: RuleDecisionLike | Record<string, unknown>): RuleDecision {
    const record = toRecord(value);
    const routingStrategy = parseRoutingStrategy(record.routingStrategy ?? record.routing_strategy);
    const confidenceRaw = record.confidence;
    const confidence =
      typeof confidenceRaw === 'number' && confidenceRaw >= 0 && confidenceRaw <= 1
        ? confidenceRaw
        : 0;

    return {
      routingStrategy,
      reason: typeof record.reason === 'string' ? record.reason : '',
      confidence,
      metadata: toRecord(record.metadata),
      preferredChannel:
        typeof (record.preferredChannel ?? record.preferred_channel) === 'string'
          ? String(record.preferredChannel ?? record.preferred_channel)
          : undefined,
      modelName:
        typeof (record.modelName ?? record.model_name) === 'string'
          ? String(record.modelName ?? record.model_name)
          : undefined,
      allowedModels: this.asStringArray(record.allowedModels ?? record.allowed_models),
      excludedModels: this.asStringArray(record.excludedModels ?? record.excluded_models),
      preferredModels: this.asStringArray(record.preferredModels ?? record.preferred_models),
      forcedModels: this.asStringArray(record.forcedModels ?? record.forced_models),
      qualityThreshold:
        typeof (record.qualityThreshold ?? record.quality_threshold) === 'number'
          ? Number(record.qualityThreshold ?? record.quality_threshold)
          : undefined,
      maxBudget:
        typeof (record.maxBudget ?? record.max_budget) === 'number'
          ? Number(record.maxBudget ?? record.max_budget)
          : undefined,
      failoverChannel:
        typeof (record.failoverChannel ?? record.failover_channel) === 'string'
          ? String(record.failoverChannel ?? record.failover_channel)
          : undefined,
    };
  }

  private mergeDecisions(base: RuleDecision | undefined, other: RuleDecision | undefined): RuleDecision | undefined {
    if (!other) return base;
    if (!base) return cloneDecision(other);

    const merged = cloneDecision(base);

    if (other.routingStrategy !== undefined) merged.routingStrategy = other.routingStrategy;
    if (other.reason) merged.reason = merged.reason ? `${merged.reason}; ${other.reason}` : other.reason;
    if ((other.confidence ?? 0) > 0) merged.confidence = Math.max(merged.confidence ?? 0, other.confidence ?? 0);
    if (other.metadata) merged.metadata = { ...(merged.metadata ?? {}), ...other.metadata };
    if (other.preferredChannel !== undefined) merged.preferredChannel = other.preferredChannel;
    if (other.modelName !== undefined) merged.modelName = other.modelName;
    if (other.allowedModels !== undefined) merged.allowedModels = [...other.allowedModels];
    if (other.excludedModels !== undefined) merged.excludedModels = [...other.excludedModels];
    if (other.preferredModels !== undefined) merged.preferredModels = [...other.preferredModels];
    if (other.forcedModels !== undefined) merged.forcedModels = [...other.forcedModels];
    if (other.qualityThreshold !== undefined) merged.qualityThreshold = other.qualityThreshold;
    if (other.maxBudget !== undefined) merged.maxBudget = other.maxBudget;
    if (other.failoverChannel !== undefined) merged.failoverChannel = other.failoverChannel;

    return merged;
  }

  private coerceComplexity(value: unknown): QueryComplexity | undefined {
    if (typeof value !== 'string') return undefined;
    const normalized = value.toLowerCase();
    return COMPLEXITIES.includes(normalized as QueryComplexity)
      ? (normalized as QueryComplexity)
      : undefined;
  }

  private asStringArray(value: unknown): string[] | undefined {
    if (!Array.isArray(value)) return undefined;
    const items = value
      .map((item) => (typeof item === 'string' ? item.trim() : ''))
      .filter((item) => item.length > 0);
    return items.length > 0 ? items : [];
  }

  private getModelName(model: string | DomainConfig['drafter']): string | undefined {
    if (typeof model === 'string') return model;
    const record = toRecord(model);
    return typeof record.name === 'string' ? record.name : undefined;
  }
}
