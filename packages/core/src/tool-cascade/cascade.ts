/**
 * Tool Cascade Orchestrator
 *
 * Coordinates detection, routing, validation, and retry feedback.
 */

import type { ToolCall } from '../types';
import { ToolCallDetector } from './detector';
import { ToolCascadeRouter } from './router';
import { ToolCascadeValidator } from './validator';
import type {
  ToolCascadeContext,
  ToolCascadeOptions,
  ToolCascadeResult,
  ToolCallGenerator,
  ToolRoutingDecision,
  ValidationResult,
} from './types';

export class ToolCascade {
  private detector: ToolCallDetector;
  private router: ToolCascadeRouter;
  private validator: ToolCascadeValidator;
  private maxRetries: number;
  private allowUnsafe: boolean;

  constructor(options: ToolCascadeOptions = {}) {
    this.detector = new ToolCallDetector();
    this.router = new ToolCascadeRouter(options.complexityAnalyzer);
    this.validator = new ToolCascadeValidator({ router: this.router });
    this.maxRetries = options.maxRetries ?? 2;
    this.allowUnsafe = options.allowUnsafe ?? false;
  }

  async execute(
    context: ToolCascadeContext,
    generator: ToolCallGenerator
  ): Promise<ToolCascadeResult> {
    const intent = this.detector.detect({
      query: context.query,
      toolCalls: context.toolCalls as unknown as Record<string, unknown>[],
      tools: context.tools,
    });

    const decision = this.router.route(context, intent.confidence);

    if (decision.strategy === 'skip') {
      return this.buildResult({
        accepted: false,
        attempts: 0,
        intent,
        decision,
        validation: emptyValidation(),
        toolCalls: [],
      });
    }

    let lastValidation = emptyValidation();
    let lastToolCalls: ToolCall[] = [];

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      const toolCalls = await generator(context, attempt === 0
        ? undefined
        : {
            attempt,
            issues: lastValidation.errors,
            warnings: lastValidation.warnings,
            strategy: decision.strategy,
          }
      );

      const callsArray = Array.isArray(toolCalls) ? toolCalls : [toolCalls];
      const validation = this.validator.validate(
        callsArray,
        context.tools,
        decision.complexity.complexityLevel
      );

      lastValidation = validation;
      lastToolCalls = callsArray;

      if (validation.valid || (this.allowUnsafe && validation.structural.isValid)) {
        return this.buildResult({
          accepted: true,
          attempts: attempt + 1,
          intent,
          decision,
          validation,
          toolCalls: callsArray,
        });
      }
    }

    return this.buildResult({
      accepted: false,
      attempts: this.maxRetries + 1,
      intent,
      decision,
      validation: lastValidation,
      toolCalls: lastToolCalls,
    });
  }

  private buildResult(result: ToolCascadeResult): ToolCascadeResult {
    return result;
  }
}

function emptyValidation(): ValidationResult {
  return {
    valid: false,
    score: 0,
    errors: [],
    warnings: [],
    structural: { isValid: false, score: 0, issues: [] },
    semantic: { isValid: false, score: 0, issues: [] },
    safety: { isValid: false, score: 0, issues: [], flaggedFields: [] },
  };
}
