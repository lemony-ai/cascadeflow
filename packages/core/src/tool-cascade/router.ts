/**
 * Tool Cascade Router
 *
 * Routes tool calls based on risk tiers and complexity analysis.
 */

import type { Tool } from '../types';
import type {
  RiskTier,
  ToolCascadeContext,
  ToolComplexityAnalysis,
  ToolComplexityAnalyzerLike,
  ToolComplexityLevel,
  ToolRoutingDecision,
} from './types';

const TOOL_RISK_PATTERNS: Array<{
  tier: RiskTier;
  patterns: RegExp[];
  reason: string;
}> = [
  {
    tier: 'critical',
    patterns: [/delete/i, /remove/i, /unlink/i, /drop/i, /truncate/i],
    reason: 'Destructive file operations require critical handling.',
  },
  {
    tier: 'low',
    patterns: [/weather/i, /forecast/i],
    reason: 'Weather lookups are low-risk and read-only.',
  },
  {
    tier: 'medium',
    patterns: [/search/i, /lookup/i, /query/i],
    reason: 'Search tools are external but generally read-only.',
  },
  {
    tier: 'high',
    patterns: [/file/i, /read/i, /write/i, /upload/i, /download/i],
    reason: 'File operations can access sensitive data.',
  },
  {
    tier: 'high',
    patterns: [/api/i, /http/i, /webhook/i, /request/i],
    reason: 'API calls may trigger external side effects.',
  },
];

const COMPLEXITY_THRESHOLDS: Array<{ level: ToolComplexityLevel; maxScore: number }> = [
  { level: 'trivial', maxScore: 3 },
  { level: 'simple', maxScore: 6 },
  { level: 'moderate', maxScore: 9 },
  { level: 'hard', maxScore: 13 },
  { level: 'expert', maxScore: Number.POSITIVE_INFINITY },
];

export class ToolCascadeRouter {
  private analyzer: ToolComplexityAnalyzerLike;

  constructor(analyzer?: ToolComplexityAnalyzerLike) {
    this.analyzer = analyzer ?? new FallbackToolComplexityAnalyzer();
  }

  route(context: ToolCascadeContext, intentScore: number): ToolRoutingDecision {
    const complexity = this.analyzer.analyzeToolCall(
      context.query,
      context.tools,
      { messages: context.messages }
    );
    const risk = this.calculateOverallRisk(context.tools);

    const reasons: string[] = [];
    if (intentScore < 0.5) {
      reasons.push('Tool intent confidence below threshold.');
      return {
        strategy: 'skip',
        complexity,
        risk,
        reasons,
      };
    }

    if (risk === 'critical' || risk === 'high') {
      reasons.push(`Risk tier ${risk} requires direct handling.`);
      return {
        strategy: 'direct',
        complexity,
        risk,
        reasons,
      };
    }

    if (complexity.complexityLevel === 'hard' || complexity.complexityLevel === 'expert') {
      reasons.push(`Complexity ${complexity.complexityLevel} routes to direct.`);
      return {
        strategy: 'direct',
        complexity,
        risk,
        reasons,
      };
    }

    reasons.push('Low/medium risk and manageable complexity - use cascade.');
    return {
      strategy: 'cascade',
      complexity,
      risk,
      reasons,
    };
  }

  calculateOverallRisk(tools: Tool[]): RiskTier {
    const tiers = tools.map((tool) => this.classifyRiskTier(tool));
    return tiers.reduce<RiskTier>((highest, tier) => {
      const order: RiskTier[] = ['low', 'medium', 'high', 'critical'];
      return order.indexOf(tier) > order.indexOf(highest) ? tier : highest;
    }, 'low');
  }

  classifyRiskTier(tool: Tool): RiskTier {
    const name = tool.function.name;
    const description = tool.function.description ?? '';
    const haystack = `${name} ${description}`.toLowerCase();

    for (const entry of TOOL_RISK_PATTERNS) {
      if (entry.patterns.some((pattern) => pattern.test(haystack))) {
        return entry.tier;
      }
    }

    return 'medium';
  }
}

class FallbackToolComplexityAnalyzer implements ToolComplexityAnalyzerLike {
  analyzeToolCall(query: string, tools: Tool[], context?: Record<string, unknown>): ToolComplexityAnalysis {
    const signals: Record<string, boolean> = {
      multiStep: hasKeyword(query, MULTI_STEP_KEYWORDS),
      ambiguous: hasKeyword(query, AMBIGUOUS_KEYWORDS),
      nested: tools.some((tool) => hasNestedSchema(tool.function.parameters)),
      toolSelection: tools.length >= 5,
      context: Boolean(context && Array.isArray(context.messages) && context.messages.length > 2),
      conditional: hasKeyword(query, CONDITIONAL_KEYWORDS),
      iterative: hasKeyword(query, ITERATIVE_KEYWORDS),
      parameterHeavy: tools.some((tool) => countParameters(tool.function.parameters) >= 5),
    };

    const score =
      (signals.multiStep ? 8.0 : 0) +
      (signals.ambiguous ? 4.0 : 0) +
      (signals.nested ? 3.0 : 0) +
      (signals.toolSelection ? 2.0 : 0) +
      (signals.context ? 2.5 : 0) +
      (signals.conditional ? 2.0 : 0) +
      (signals.iterative ? 1.5 : 0) +
      (signals.parameterHeavy ? 1.0 : 0);

    const complexityLevel = mapScoreToLevel(score);

    return {
      complexityLevel,
      score,
      signals,
      reasoning: buildReasoning(signals),
    };
  }
}

const MULTI_STEP_KEYWORDS = [
  'then',
  'after',
  'next',
  'first',
  'second',
  'finally',
  'before',
  'step',
  'sequence',
];

const CONDITIONAL_KEYWORDS = [
  'if',
  'when',
  'unless',
  'only if',
  'depending',
  'based on',
];

const ITERATIVE_KEYWORDS = ['all', 'each', 'every', 'for each', 'compare', 'across'];

const AMBIGUOUS_KEYWORDS = ['best', 'latest', 'recent', 'appropriate', 'relevant', 'around'];

function hasKeyword(query: string, keywords: string[]): boolean {
  const haystack = query.toLowerCase();
  return keywords.some((keyword) => haystack.includes(keyword));
}

function mapScoreToLevel(score: number): ToolComplexityLevel {
  return COMPLEXITY_THRESHOLDS.find((entry) => score <= entry.maxScore)?.level ?? 'expert';
}

function buildReasoning(signals: Record<string, boolean>): string[] {
  return Object.entries(signals)
    .filter(([, value]) => value)
    .map(([key]) => `Signal ${key} detected`);
}

function hasNestedSchema(parameters: Record<string, unknown> | undefined): boolean {
  if (!parameters || typeof parameters !== 'object') return false;
  const schema = parameters as Record<string, unknown>;
  const properties = schema.properties as Record<string, unknown> | undefined;
  if (!properties) return false;
  return Object.values(properties).some((value) => {
    if (!value || typeof value !== 'object') return false;
    const child = value as Record<string, unknown>;
    return Boolean(child.properties || child.items);
  });
}

function countParameters(parameters: Record<string, unknown> | undefined): number {
  if (!parameters || typeof parameters !== 'object') return 0;
  const schema = parameters as Record<string, unknown>;
  const properties = schema.properties as Record<string, unknown> | undefined;
  return properties ? Object.keys(properties).length : 0;
}
