export enum ToolRiskLevel {
  LOW = 1,
  MEDIUM = 2,
  HIGH = 3,
  CRITICAL = 4,
}

export type ToolRiskClassification = {
  level: ToolRiskLevel;
  confidence: number;
  reasons: string[];
};

type ToolDef = { name?: string; description?: string };

// Keep this intentionally aligned with `cascadeflow/routing/tool_risk.py`.
const RISK_INDICATORS = {
  critical: {
    keywords: [
      'delete_all',
      'drop_table',
      'truncate',
      'destroy',
      'financial_transaction',
      'payment',
      'charge',
      'transfer_funds',
      'withdraw',
      'deploy_production',
      'publish_live',
      'send_mass',
      'broadcast',
    ],
    patterns: [
      /delete.*all/i,
      /remove.*all/i,
      /drop.*table/i,
      /financial|payment|transaction|charge|withdraw/i,
      /deploy.*prod/i,
      /publish.*live/i,
      /broadcast/i,
    ],
    descriptions: ['permanently', 'irreversible', 'cannot be undone', 'financial', 'payment', 'production', 'mass'],
  },
  high: {
    keywords: [
      'delete',
      'remove',
      'send_email',
      'send_message',
      'post',
      'publish',
      'submit',
      'execute_query',
      'modify_permissions',
      'change_role',
      'revoke',
      'disable',
      'suspend',
      'ban',
      'terminate',
    ],
    patterns: [
      /delete_\w+/i,
      /remove_\w+/i,
      /send_\w+/i,
      /post_\w+/i,
      /publish_\w+/i,
      /submit_\w+/i,
      /execute.*query/i,
      /modify.*permission/i,
      /disable|suspend|ban|terminate/i,
    ],
    descriptions: [
      'delete',
      'remove',
      'send',
      'email',
      'message',
      'post',
      'publish',
      'execute',
      'permission',
      'disable',
      'suspend',
      'terminate',
    ],
  },
  medium: {
    keywords: ['update', 'edit', 'modify', 'create', 'add', 'set', 'change', 'write', 'save', 'upload', 'insert', 'append', 'replace'],
    patterns: [/update_\w+/i, /edit_\w+/i, /modify_\w+/i, /create_\w+/i, /add_\w+/i, /set_\w+/i, /write_\w+/i, /save_\w+/i, /upload_\w+/i],
    descriptions: ['update', 'edit', 'modify', 'create', 'add', 'change', 'write', 'save', 'upload'],
  },
  low: {
    keywords: ['get', 'read', 'list', 'search', 'query', 'fetch', 'retrieve', 'find', 'lookup', 'check', 'verify', 'validate', 'count', 'calculate', 'analyze', 'preview'],
    patterns: [/get_\w+/i, /read_\w+/i, /list_\w+/i, /search_\w+/i, /query_\w+/i, /fetch_\w+/i, /find_\w+/i, /lookup_\w+/i, /check_\w+/i],
    descriptions: ['get', 'read', 'list', 'search', 'query', 'fetch', 'find', 'lookup', 'check', 'verify', 'calculate', 'analyze', 'preview', 'retrieve'],
  },
} as const;

function toLevel(category: keyof typeof RISK_INDICATORS): ToolRiskLevel {
  if (category === 'critical') return ToolRiskLevel.CRITICAL;
  if (category === 'high') return ToolRiskLevel.HIGH;
  if (category === 'medium') return ToolRiskLevel.MEDIUM;
  return ToolRiskLevel.LOW;
}

export function classifyTool(
  tool: ToolDef,
  defaultLevel: ToolRiskLevel = ToolRiskLevel.MEDIUM
): ToolRiskClassification {
  const name = (tool.name || '').toLowerCase();
  const description = (tool.description || '').toLowerCase();

  const scores = new Map<ToolRiskLevel, number>([
    [ToolRiskLevel.CRITICAL, 0],
    [ToolRiskLevel.HIGH, 0],
    [ToolRiskLevel.MEDIUM, 0],
    [ToolRiskLevel.LOW, 0],
  ]);
  const reasons = new Map<ToolRiskLevel, string[]>([
    [ToolRiskLevel.CRITICAL, []],
    [ToolRiskLevel.HIGH, []],
    [ToolRiskLevel.MEDIUM, []],
    [ToolRiskLevel.LOW, []],
  ]);

  for (const category of Object.keys(RISK_INDICATORS) as (keyof typeof RISK_INDICATORS)[]) {
    const level = toLevel(category);
    const indicators = RISK_INDICATORS[category];

    for (const keyword of indicators.keywords) {
      if (name.includes(keyword)) {
        scores.set(level, (scores.get(level) || 0) + 2.0);
        reasons.get(level)!.push(`name:${keyword}`);
      }
    }

    for (const pattern of indicators.patterns) {
      if (pattern.test(name)) {
        scores.set(level, (scores.get(level) || 0) + 1.5);
        reasons.get(level)!.push(`pattern:${pattern.source}`);
      }
    }

    for (const kw of indicators.descriptions) {
      if (description.includes(kw)) {
        scores.set(level, (scores.get(level) || 0) + 0.5);
        reasons.get(level)!.push(`desc:${kw}`);
      }
    }
  }

  let maxScore = 0;
  for (const v of scores.values()) maxScore = Math.max(maxScore, v);

  if (maxScore === 0) {
    return { level: defaultLevel, confidence: 0.3, reasons: ['no_match:using_default'] };
  }

  let bestLevel: ToolRiskLevel = ToolRiskLevel.MEDIUM;
  for (const [level, score] of scores.entries()) {
    if (score === maxScore) {
      bestLevel = level;
      break;
    }
  }

  let totalScore = 0;
  for (const v of scores.values()) totalScore += v;
  const confidence = totalScore > 0 ? maxScore / totalScore : 0.5;

  return { level: bestLevel, confidence, reasons: reasons.get(bestLevel)! };
}

export function getToolRiskRouting(
  tools: ToolDef[]
): {
  maxRisk: ToolRiskLevel;
  maxRiskName: string;
  useVerifier: boolean;
  classifications: Record<string, { level: string; confidence: number }>;
  highRiskTools: string[];
} {
  const classifications: Record<string, { level: string; confidence: number }> = {};
  const highRiskTools: string[] = [];

  let maxRisk: ToolRiskLevel = ToolRiskLevel.LOW;
  for (const tool of tools) {
    const name = tool?.name || 'unknown';
    const c = classifyTool(tool || {});
    classifications[name] = { level: ToolRiskLevel[c.level], confidence: c.confidence };
    if (c.level > maxRisk) maxRisk = c.level;
    if (c.level >= ToolRiskLevel.HIGH) highRiskTools.push(name);
  }

  return {
    maxRisk,
    maxRiskName: ToolRiskLevel[maxRisk],
    useVerifier: maxRisk >= ToolRiskLevel.HIGH,
    classifications,
    highRiskTools,
  };
}

