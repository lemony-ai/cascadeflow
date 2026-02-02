/**
 * Tool Cascade Validator
 *
 * Structural + semantic + safety validation for tool calls.
 */

import type { Tool, ToolCall } from '../types';
import { ToolValidator } from '../tools/validator';
import type {
  RiskTier,
  SafetyValidationResult,
  SemanticValidationResult,
  StructuralValidationResult,
  ToolComplexityLevel,
  ValidationResult,
} from './types';
import { ToolCascadeRouter } from './router';

const PLACEHOLDER_VALUES = ['todo', 'tbd', 'unknown', 'n/a', 'null', 'undefined', ''];
const SAFETY_PATTERNS = [/rm\s+-rf/i, /drop\s+table/i, /delete\s+all/i];

export class ToolCascadeValidator {
  private toolValidator: ToolValidator;
  private router: ToolCascadeRouter;

  constructor(options?: { toolValidator?: ToolValidator; router?: ToolCascadeRouter }) {
    this.toolValidator = options?.toolValidator ?? new ToolValidator();
    this.router = options?.router ?? new ToolCascadeRouter();
  }

  validate(
    toolCalls: ToolCall[],
    tools: Tool[],
    complexityLevel?: ToolComplexityLevel
  ): ValidationResult {
    const structural = this.validateStructural(toolCalls, tools, complexityLevel);
    const semantic = this.validateSemantic(toolCalls);
    const safety = this.validateSafety(toolCalls, tools);

    const score = (structural.score * 0.5) + (semantic.score * 0.3) + (safety.score * 0.2);
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!structural.isValid) {
      errors.push(...structural.issues);
    }

    if (!semantic.isValid) {
      warnings.push(...semantic.issues);
    }

    if (!safety.isValid) {
      errors.push(...safety.issues);
    }

    const valid = structural.isValid && safety.isValid && semantic.score >= 0.6;

    return {
      valid,
      score,
      errors,
      warnings,
      structural,
      semantic,
      safety,
    };
  }

  private validateStructural(
    toolCalls: ToolCall[],
    tools: Tool[],
    complexityLevel?: ToolComplexityLevel
  ): StructuralValidationResult {
    const formattedTools = tools.map((tool) => ({
      name: tool.function.name,
      description: tool.function.description,
      parameters: tool.function.parameters,
    }));

    const formattedCalls = toolCalls.map((call) => ({
      name: call.function.name,
      arguments: call.function.arguments,
    }));

    const score = this.toolValidator.validateToolCalls(
      formattedCalls,
      formattedTools,
      complexityLevel === 'hard' || complexityLevel === 'expert'
        ? 'moderate'
        : complexityLevel
    );

    return {
      isValid: score.isValid,
      score: score.overallScore,
      issues: score.issues,
    };
  }

  private validateSemantic(toolCalls: ToolCall[]): SemanticValidationResult {
    const issues: string[] = [];
    let total = 0;
    let validCount = 0;

    for (const call of toolCalls) {
      const args = parseArguments(call.function.arguments);
      if (!args) {
        issues.push(`Tool ${call.function.name} has invalid JSON arguments.`);
        total++;
        continue;
      }

      const argIssues = Object.entries(args)
        .filter(([, value]) => typeof value === 'string')
        .filter(([, value]) => PLACEHOLDER_VALUES.includes(value.toLowerCase().trim()));

      total++;
      if (argIssues.length === 0) {
        validCount++;
      } else {
        for (const [key] of argIssues) {
          issues.push(`Tool ${call.function.name} has placeholder value for ${key}.`);
        }
      }
    }

    const score = total === 0 ? 0 : validCount / total;
    return {
      isValid: score >= 0.7,
      score,
      issues,
    };
  }

  private validateSafety(toolCalls: ToolCall[], tools: Tool[]): SafetyValidationResult {
    const issues: string[] = [];
    const flaggedFields: string[] = [];
    const riskByTool = new Map(
      tools.map((tool) => [tool.function.name, this.router.classifyRiskTier(tool)])
    );

    let total = 0;
    let safeCount = 0;

    for (const call of toolCalls) {
      const args = parseArguments(call.function.arguments) ?? {};
      const risk = riskByTool.get(call.function.name) ?? 'medium';
      const { safe, fieldIssues } = assessSafety(args, risk);

      total++;
      if (safe) {
        safeCount++;
      } else {
        issues.push(`Tool ${call.function.name} failed safety checks (${risk}).`);
        flaggedFields.push(...fieldIssues);
      }
    }

    const score = total === 0 ? 0 : safeCount / total;
    return {
      isValid: score >= 0.8,
      score,
      issues,
      flaggedFields,
    };
  }
}

function parseArguments(raw: string): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

function assessSafety(
  args: Record<string, unknown>,
  risk: RiskTier
): { safe: boolean; fieldIssues: string[] } {
  const issues: string[] = [];

  const serialized = JSON.stringify(args);
  if (SAFETY_PATTERNS.some((pattern) => pattern.test(serialized))) {
    issues.push('Detected destructive pattern in arguments.');
  }

  if (risk === 'critical' || risk === 'high') {
    for (const [key, value] of Object.entries(args)) {
      if (typeof value === 'string' && value.trim().length === 0) {
        issues.push(`Empty value for ${key}.`);
      }
      if (typeof value === 'string' && value.toLowerCase().includes('password')) {
        issues.push(`Sensitive value in ${key}.`);
      }
    }
  }

  return { safe: issues.length === 0, fieldIssues: issues };
}
