/**
 * Tool Quality Validator
 *
 * Validates tool call quality using 5-level validation with complexity-aware thresholds.
 * Works alongside your existing text quality system - no base class needed.
 *
 * ONLY for tool calls - your existing quality system handles text.
 *
 * 5-Level Validation:
 *   1. JSON syntax valid?
 *   2. Schema matches expected format?
 *   3. Tool exists in available tools?
 *   4. Required fields present?
 *   5. Parameters make sense?
 *
 * Adaptive Thresholds (based on complexity):
 *   - TRIVIAL:  0.70 (more lenient - small model handles well)
 *   - SIMPLE:   0.75
 *   - MODERATE: 0.85 (more strict - riskier for small model)
 *
 * Expected acceptance rates:
 *   - TRIVIAL:  92%
 *   - SIMPLE:   76%
 *   - MODERATE: 47%
 *
 * @example
 * ```typescript
 * import { ToolValidator } from '@cascadeflow/core';
 *
 * const validator = new ToolValidator();
 *
 * // Basic validation
 * const score = validator.validate(toolCalls, availableTools);
 *
 * // With adaptive threshold (recommended)
 * const result = validator.validateToolCalls(
 *   toolCalls,
 *   availableTools,
 *   'simple'
 * );
 *
 * if (result.isValid) {
 *   acceptDraft();
 * } else {
 *   escalateToLargeModel();
 * }
 * ```
 */

/**
 * Complexity level for adaptive thresholds
 */
export type ComplexityLevel = 'trivial' | 'simple' | 'moderate' | 'unknown';

/**
 * Tool quality assessment result
 *
 * Similar to existing ValidationResult but specifically for tools.
 * Contains level-by-level validation results and overall score.
 */
export interface ToolQualityScore {
  /** Overall quality score (0.0-1.0) */
  overallScore: number;

  /** Threshold that was applied */
  thresholdUsed: number;

  /** Did it pass the threshold? */
  isValid: boolean;

  // 5-Level validation results
  /** Level 1: JSON syntax valid */
  jsonValid: boolean;

  /** Level 2: Schema matches expected format */
  schemaValid: boolean;

  /** Level 3: Tool exists in available tools */
  toolExists: boolean;

  /** Level 4: Required fields present */
  requiredFieldsPresent: boolean;

  /** Level 5: Parameters make sense */
  parametersSensible: boolean;

  /** List of validation issues */
  issues: string[];

  /** Complexity level used for adaptive threshold */
  complexityLevel?: ComplexityLevel;

  /** Was adaptive threshold used? */
  adaptiveThreshold: boolean;
}

/**
 * Validates tool call quality using 5-level validation
 *
 * Works independently - doesn't inherit from anything.
 * Your existing text quality system remains unchanged.
 *
 * 5-Level Validation:
 * 1. JSON syntax
 * 2. Schema match
 * 3. Tool exists
 * 4. Required fields
 * 5. Parameters sensible
 *
 * Adaptive Thresholds:
 * - Adjusts based on complexity level
 * - TRIVIAL: 0.70 (lenient)
 * - MODERATE: 0.85 (strict)
 *
 * @example
 * ```typescript
 * const validator = new ToolValidator({ verbose: true });
 *
 * const result = validator.validateToolCalls(
 *   [{ name: 'get_weather', arguments: { location: 'Paris' } }],
 *   [weatherToolConfig],
 *   'simple'
 * );
 *
 * console.log(result.isValid); // true/false
 * console.log(result.overallScore); // 0.0-1.0
 * console.log(result.issues); // Array of issue strings
 * ```
 */
export class ToolValidator {
  /** Adaptive thresholds by complexity */
  private static readonly ADAPTIVE_THRESHOLDS: Record<ComplexityLevel, number> = {
    trivial: 0.70,
    simple: 0.75,
    moderate: 0.85,
    unknown: 0.80,
  };

  /** Default threshold when no complexity specified */
  private static readonly DEFAULT_THRESHOLD = 0.80;

  /** Weights for each validation level */
  private static readonly LEVEL_WEIGHTS = {
    jsonValid: 0.25,
    schemaValid: 0.20,
    toolExists: 0.20,
    requiredFields: 0.20,
    parametersSensible: 0.15,
  };

  private readonly verbose: boolean;

  /**
   * Create a new tool validator
   *
   * @param options - Configuration options
   *
   * @example
   * ```typescript
   * const validator = new ToolValidator({ verbose: true });
   * ```
   */
  constructor(options: { verbose?: boolean } = {}) {
    this.verbose = options.verbose ?? false;
    if (this.verbose) {
      console.log('[ToolValidator] Initialized');
    }
  }

  /**
   * Simple validation - returns quality score 0.0-1.0
   *
   * For basic use when you don't need adaptive thresholds.
   *
   * @param toolCalls - Tool calls to validate
   * @param availableTools - Available tools (optional)
   * @returns Quality score 0.0-1.0
   *
   * @example
   * ```typescript
   * const score = validator.validate(toolCalls, availableTools);
   * console.log(`Quality: ${(score * 100).toFixed(0)}%`);
   * ```
   */
  validate(
    toolCalls: Record<string, any> | Record<string, any>[],
    availableTools?: Record<string, any>[]
  ): number {
    const callsArray = Array.isArray(toolCalls) ? toolCalls : [toolCalls];

    if (!callsArray || callsArray.length === 0) {
      return 0.0;
    }

    const scores = callsArray.map((call) =>
      this._validateSingleToolCall(call, availableTools)
    );

    return scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0.0;
  }

  /**
   * Main validation method with adaptive thresholds
   *
   * This is what you'll use in cascade - integrates with complexity detection.
   *
   * @param toolCalls - Tool calls from draft
   * @param availableTools - Available tools
   * @param complexityLevel - Complexity level for adaptive threshold
   * @returns ToolQualityScore with detailed results
   *
   * @example
   * ```typescript
   * const result = validator.validateToolCalls(
   *   draftToolCalls,
   *   availableTools,
   *   'simple'
   * );
   *
   * if (result.isValid) {
   *   console.log('✓ Tool calls passed validation');
   * } else {
   *   console.log('✗ Issues:', result.issues.join(', '));
   * }
   * ```
   */
  validateToolCalls(
    toolCalls: Record<string, any>[],
    availableTools: Record<string, any>[],
    complexityLevel?: ComplexityLevel
  ): ToolQualityScore {
    // Get threshold (adaptive or default)
    const { threshold, isAdaptive } = this._getThreshold(complexityLevel);

    // Run 5-level validation
    const jsonValid = this._validateJson(toolCalls);
    const schemaValid = this._validateSchema(toolCalls);
    const toolExists = this._validateToolExists(toolCalls, availableTools);
    const requiredFields = this._validateRequiredFields(toolCalls, availableTools);
    const parametersSensible = this._validateParameters(toolCalls, availableTools);

    // Calculate weighted score
    const score =
      ToolValidator.LEVEL_WEIGHTS.jsonValid * (jsonValid ? 1.0 : 0.0) +
      ToolValidator.LEVEL_WEIGHTS.schemaValid * (schemaValid ? 1.0 : 0.0) +
      ToolValidator.LEVEL_WEIGHTS.toolExists * (toolExists ? 1.0 : 0.0) +
      ToolValidator.LEVEL_WEIGHTS.requiredFields * (requiredFields ? 1.0 : 0.0) +
      ToolValidator.LEVEL_WEIGHTS.parametersSensible * (parametersSensible ? 1.0 : 0.0);

    const isValid = score >= threshold;

    // Collect issues
    const issues: string[] = [];
    if (!jsonValid) issues.push('Invalid JSON structure');
    if (!schemaValid) issues.push('Schema validation failed');
    if (!toolExists) issues.push('Tool not found');
    if (!requiredFields) issues.push('Required fields missing');
    if (!parametersSensible) issues.push("Parameters don't make sense");

    if (this.verbose) {
      this._logValidation(score, threshold, isValid, issues, complexityLevel);
    }

    return {
      overallScore: score,
      thresholdUsed: threshold,
      isValid,
      jsonValid,
      schemaValid,
      toolExists,
      requiredFieldsPresent: requiredFields,
      parametersSensible,
      issues,
      complexityLevel,
      adaptiveThreshold: isAdaptive,
    };
  }

  /**
   * Get threshold based on complexity
   */
  private _getThreshold(complexityLevel?: ComplexityLevel): {
    threshold: number;
    isAdaptive: boolean;
  } {
    if (!complexityLevel) {
      return {
        threshold: ToolValidator.DEFAULT_THRESHOLD,
        isAdaptive: false,
      };
    }

    const threshold =
      ToolValidator.ADAPTIVE_THRESHOLDS[complexityLevel] ?? ToolValidator.DEFAULT_THRESHOLD;
    const isAdaptive = complexityLevel in ToolValidator.ADAPTIVE_THRESHOLDS;

    return { threshold, isAdaptive };
  }

  /**
   * Validate single tool call
   */
  private _validateSingleToolCall(
    toolCall: Record<string, any>,
    availableTools?: Record<string, any>[]
  ): number {
    let score = 0.0;

    // Level 1: JSON valid
    if (typeof toolCall === 'object' && toolCall !== null) {
      score += ToolValidator.LEVEL_WEIGHTS.jsonValid;
    }

    // Level 2: Schema valid
    if (this._hasExpectedFields(toolCall)) {
      score += ToolValidator.LEVEL_WEIGHTS.schemaValid;
    }

    // Level 3: Tool exists
    if (!availableTools || this._toolNameExists(toolCall, availableTools)) {
      score += ToolValidator.LEVEL_WEIGHTS.toolExists;
    }

    // Level 4: Required fields
    if (!availableTools || this._hasRequiredFields(toolCall, availableTools)) {
      score += ToolValidator.LEVEL_WEIGHTS.requiredFields;
    }

    // Level 5: Parameters sensible
    if (this._parametersAreSensible(toolCall)) {
      score += ToolValidator.LEVEL_WEIGHTS.parametersSensible;
    }

    return score;
  }

  // ═══════════════════════════════════════════════════════════
  // Validation Levels
  // ═══════════════════════════════════════════════════════════

  /**
   * Level 1: JSON syntax valid
   */
  private _validateJson(toolCalls: Record<string, any>[]): boolean {
    if (!toolCalls || toolCalls.length === 0) return false;
    return toolCalls.every((tc) => typeof tc === 'object' && tc !== null);
  }

  /**
   * Level 2: Schema matches
   */
  private _validateSchema(toolCalls: Record<string, any>[]): boolean {
    return toolCalls.every((tc) => this._hasExpectedFields(tc));
  }

  /**
   * Check for name + arguments fields
   */
  private _hasExpectedFields(toolCall: Record<string, any>): boolean {
    if (typeof toolCall !== 'object' || toolCall === null) {
      return false;
    }
    const hasName = 'name' in toolCall || 'function' in toolCall;
    const hasArgs =
      'arguments' in toolCall || 'parameters' in toolCall || 'args' in toolCall;
    return hasName && hasArgs;
  }

  /**
   * Level 3: Tool exists
   */
  private _validateToolExists(
    toolCalls: Record<string, any>[],
    availableTools: Record<string, any>[]
  ): boolean {
    if (!availableTools || availableTools.length === 0) {
      return true;
    }
    return toolCalls.every((tc) => this._toolNameExists(tc, availableTools));
  }

  /**
   * Check if tool name exists
   */
  private _toolNameExists(
    toolCall: Record<string, any>,
    availableTools: Record<string, any>[]
  ): boolean {
    if (typeof toolCall !== 'object' || toolCall === null) {
      return false;
    }
    const toolName =
      toolCall.name || toolCall.function?.name || toolCall.function?.function?.name;
    if (!toolName) return false;

    const availableNames = new Set(availableTools.map((t) => t.name));
    return availableNames.has(toolName);
  }

  /**
   * Level 4: Required fields present
   */
  private _validateRequiredFields(
    toolCalls: Record<string, any>[],
    availableTools: Record<string, any>[]
  ): boolean {
    if (!availableTools || availableTools.length === 0) {
      return true;
    }
    return toolCalls.every((tc) => this._hasRequiredFields(tc, availableTools));
  }

  /**
   * Check required fields
   */
  private _hasRequiredFields(
    toolCall: Record<string, any>,
    availableTools: Record<string, any>[]
  ): boolean {
    if (typeof toolCall !== 'object' || toolCall === null) {
      return false;
    }
    const toolName =
      toolCall.name || toolCall.function?.name || toolCall.function?.function?.name;
    if (!toolName) return false;

    // Find tool schema
    const toolSchema = availableTools.find((t) => t.name === toolName);
    if (!toolSchema) return false;

    // Get required fields
    const required =
      toolSchema.parameters?.required ||
      toolSchema.input_schema?.required ||
      toolSchema.function?.parameters?.required ||
      [];
    if (!required || required.length === 0) return true;

    // Get arguments
    let args = toolCall.arguments || toolCall.args || toolCall.parameters || {};
    if (typeof args === 'string') {
      try {
        args = JSON.parse(args);
      } catch {
        return false;
      }
    }

    return required.every((field: string) => field in args);
  }

  /**
   * Level 5: Parameters sensible
   */
  private _validateParameters(
    toolCalls: Record<string, any>[],
    _availableTools: Record<string, any>[]
  ): boolean {
    return toolCalls.every((tc) => this._parametersAreSensible(tc));
  }

  /**
   * Basic sanity checks on parameters
   */
  private _parametersAreSensible(toolCall: Record<string, any>): boolean {
    if (typeof toolCall !== 'object' || toolCall === null) {
      return false;
    }
    let args = toolCall.arguments || toolCall.args || toolCall.parameters || {};

    if (typeof args === 'string') {
      try {
        args = JSON.parse(args);
      } catch {
        return false;
      }
    }

    // Must be object (not array) and not null
    return typeof args === 'object' && args !== null && !Array.isArray(args);
  }

  /**
   * Log validation results
   */
  private _logValidation(
    score: number,
    threshold: number,
    isValid: boolean,
    issues: string[],
    complexityLevel?: ComplexityLevel
  ): void {
    const status = isValid ? '✓ VALID' : '✗ INVALID';
    console.log(
      `\n[ToolValidator] Tool Quality Validation\n` +
        `  Score: ${score.toFixed(2)}, Threshold: ${threshold.toFixed(2)}\n` +
        `  Complexity: ${complexityLevel || 'N/A'}\n` +
        `  Result: ${status}\n` +
        `  Issues: ${issues.length > 0 ? issues.join(', ') : 'None'}`
    );
  }
}

/**
 * Format ToolQualityScore as string
 *
 * @param score - Tool quality score
 * @returns Formatted string
 *
 * @example
 * ```typescript
 * console.log(formatToolQualityScore(result));
 * // "ToolQuality(✓ VALID, score=0.95, threshold=0.80)"
 * ```
 */
export function formatToolQualityScore(score: ToolQualityScore): string {
  const status = score.isValid ? '✓ VALID' : '✗ INVALID';
  return `ToolQuality(${status}, score=${score.overallScore.toFixed(2)}, threshold=${score.thresholdUsed.toFixed(2)})`;
}
