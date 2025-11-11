/**
 * Streaming Utilities
 *
 * Shared utilities for streaming implementations:
 * - Progressive JSON parsing
 * - Tool call validation helpers
 * - Confidence estimation
 *
 * Port from Python cascadeflow/streaming/utils.py
 */

import type { Tool } from '../types';

/**
 * State of progressive JSON parsing
 */
export enum JSONParseState {
  EMPTY = 'empty',
  PARTIAL = 'partial',
  COMPLETE = 'complete',
  INVALID = 'invalid',
}

/**
 * Result from progressive JSON parsing
 */
export interface ParseResult {
  /** Current parsing state */
  state: JSONParseState;

  /** Parsed data (complete or partial) */
  data?: Record<string, any>;

  /** Keys that have been parsed so far */
  partialKeys?: string[];

  /** Error message if invalid */
  error?: string;
}

/**
 * Progressive JSON Parser
 *
 * Parses JSON progressively as it streams in, handling incomplete JSON gracefully
 * and extracting whatever is parseable.
 *
 * @example
 * ```typescript
 * const parser = new ProgressiveJSONParser();
 * const result = parser.parse('{"name": "get_weat');
 * // result.state === JSONParseState.PARTIAL
 * // result.partialKeys === ['name']
 * // result.data === { name: 'get_weat' }
 * ```
 */
export class ProgressiveJSONParser {
  /**
   * Parse potentially incomplete JSON string
   *
   * @param jsonStr - JSON string (may be incomplete)
   * @returns ParseResult with state and extracted data
   */
  parse(jsonStr: string): ParseResult {
    if (!jsonStr || !jsonStr.trim()) {
      return { state: JSONParseState.EMPTY };
    }

    const trimmed = jsonStr.trim();

    // Try to parse as complete JSON first
    try {
      const data = JSON.parse(trimmed);
      return {
        state: JSONParseState.COMPLETE,
        data,
        partialKeys: typeof data === 'object' && data !== null ? Object.keys(data) : [],
      };
    } catch (e) {
      // Not complete JSON, try partial parsing
    }

    // Try to extract partial data
    const [partialData, partialKeys] = this.extractPartialJSON(trimmed);

    if (partialData && Object.keys(partialData).length > 0) {
      return {
        state: JSONParseState.PARTIAL,
        data: partialData,
        partialKeys,
      };
    }

    // Check if it's a valid JSON start
    if (this.isValidJSONStart(trimmed)) {
      return {
        state: JSONParseState.PARTIAL,
        data: {},
        partialKeys: [],
      };
    }

    return {
      state: JSONParseState.INVALID,
      error: 'Invalid JSON structure',
    };
  }

  /**
   * Extract whatever is parseable from partial JSON
   *
   * Strategy:
   * 1. Try to close incomplete structures
   * 2. Extract complete key-value pairs
   * 3. Return partial dictionary
   */
  private extractPartialJSON(jsonStr: string): [Record<string, any>, string[]] {
    const data: Record<string, any> = {};
    const keys: string[] = [];

    // Pattern: "key": "value"
    const stringPattern = /"([^"]+)"\s*:\s*"([^"]*)"/g;
    let match: RegExpExecArray | null;

    while ((match = stringPattern.exec(jsonStr)) !== null) {
      const [, key, value] = match;
      data[key] = value;
      keys.push(key);
    }

    // Pattern: "key": number
    const numberPattern = /"([^"]+)"\s*:\s*(-?\d+\.?\d*)/g;
    while ((match = numberPattern.exec(jsonStr)) !== null) {
      const [, key, value] = match;
      if (!(key in data)) {
        // Don't override strings
        data[key] = value.includes('.') ? parseFloat(value) : parseInt(value, 10);
        keys.push(key);
      }
    }

    // Pattern: "key": true/false/null
    const boolPattern = /"([^"]+)"\s*:\s*(true|false|null)/g;
    while ((match = boolPattern.exec(jsonStr)) !== null) {
      const [, key, value] = match;
      if (!(key in data)) {
        data[key] = value === 'true' ? true : value === 'false' ? false : null;
        keys.push(key);
      }
    }

    // Pattern: "key": { (nested object start)
    const objectPattern = /"([^"]+)"\s*:\s*\{/g;
    while ((match = objectPattern.exec(jsonStr)) !== null) {
      const key = match[1];
      if (!(key in data)) {
        data[key] = {}; // Placeholder for nested object
        keys.push(key);
      }
    }

    // Pattern: "key": [ (array start)
    const arrayPattern = /"([^"]+)"\s*:\s*\[/g;
    while ((match = arrayPattern.exec(jsonStr)) !== null) {
      const key = match[1];
      if (!(key in data)) {
        data[key] = []; // Placeholder for array
        keys.push(key);
      }
    }

    return [data, keys];
  }

  /**
   * Check if string is a valid JSON start
   */
  private isValidJSONStart(jsonStr: string): boolean {
    const trimmed = jsonStr.trim();

    // Must start with { or [
    if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
      return false;
    }

    return true;
  }

  /**
   * Reset parser state
   */
  reset(): void {
    this.buffer = '';
  }
}

/**
 * Tool Call Validator
 *
 * Validates tool calls for correctness:
 * 1. Tool name exists in available tools
 * 2. Required parameters present
 * 3. Parameter types correct
 * 4. No extra parameters
 */
export class ToolCallValidator {
  /**
   * Validate a tool call
   *
   * @param toolCall - Tool call dict with 'name' and 'arguments'
   * @param availableTools - List of available tool definitions
   * @returns [isValid, reason]
   */
  static validateToolCall(
    toolCall: Record<string, any>,
    availableTools: Tool[]
  ): [boolean, string] {
    // Check structure
    if (!('name' in toolCall)) {
      return [false, "Missing 'name' field"];
    }

    if (!('arguments' in toolCall)) {
      return [false, "Missing 'arguments' field"];
    }

    const toolName = toolCall.name;
    let args = toolCall.arguments;

    // Find tool definition
    let toolDef: any = null;
    for (const tool of availableTools) {
      // Handle both formats: direct dict and function wrapper
      const funcDef = (tool as any).function || tool;
      if (funcDef.name === toolName) {
        toolDef = funcDef;
        break;
      }
    }

    if (!toolDef) {
      return [false, `Tool '${toolName}' not found in available tools`];
    }

    // Get parameter schema
    const paramsSchema = toolDef.parameters || {};
    const requiredParams = paramsSchema.required || [];
    const properties = paramsSchema.properties || {};

    // Parse arguments if string
    if (typeof args === 'string') {
      try {
        args = JSON.parse(args);
      } catch (e) {
        return [false, 'Invalid JSON in arguments'];
      }
    }

    if (typeof args !== 'object' || args === null || Array.isArray(args)) {
      return [false, 'Arguments must be an object'];
    }

    // Check required parameters
    for (const param of requiredParams) {
      if (!(param in args)) {
        return [false, `Missing required parameter: ${param}`];
      }
    }

    // Check parameter types (basic validation)
    for (const [paramName, paramValue] of Object.entries(args)) {
      if (paramName in properties) {
        const expectedType = properties[paramName].type;

        if (expectedType === 'string' && typeof paramValue !== 'string') {
          return [false, `Parameter '${paramName}' must be string`];
        } else if (expectedType === 'number' && typeof paramValue !== 'number') {
          return [false, `Parameter '${paramName}' must be number`];
        } else if (expectedType === 'boolean' && typeof paramValue !== 'boolean') {
          return [false, `Parameter '${paramName}' must be boolean`];
        } else if (expectedType === 'array' && !Array.isArray(paramValue)) {
          return [false, `Parameter '${paramName}' must be array`];
        } else if (
          expectedType === 'object' &&
          (typeof paramValue !== 'object' || paramValue === null || Array.isArray(paramValue))
        ) {
          return [false, `Parameter '${paramName}' must be object`];
        }
      }
    }

    return [true, 'Valid'];
  }

  /**
   * Extract tool calls from LLM response
   *
   * Handles various formats:
   * - Direct JSON
   * - Function calling format
   * - Text with embedded JSON
   */
  static extractToolCallsFromResponse(response: string): Record<string, any>[] {
    const toolCalls: Record<string, any>[] = [];

    // Try to parse as direct JSON
    try {
      const data = JSON.parse(response);
      if (typeof data === 'object' && data !== null && 'name' in data) {
        toolCalls.push(data);
      } else if (Array.isArray(data)) {
        toolCalls.push(...data);
      }
      return toolCalls;
    } catch (e) {
      // Not direct JSON
    }

    // Try to extract JSON blocks
    const jsonPattern = /\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}[^{}]*\}/g;
    const matches = response.match(jsonPattern);

    if (matches) {
      for (const match of matches) {
        try {
          const toolCall = JSON.parse(match);
          toolCalls.push(toolCall);
        } catch (e) {
          // Skip invalid JSON
          continue;
        }
      }
    }

    return toolCalls;
  }
}

/**
 * Estimate confidence from logprobs
 *
 * @param logprobs - List of log probabilities
 * @param method - 'mean', 'min', or 'median'
 * @returns Confidence score 0.0-1.0, or null if not available
 */
export function estimateConfidenceFromLogprobs(
  logprobs: number[],
  method: 'mean' | 'min' | 'median' = 'mean'
): number | null {
  if (!logprobs || logprobs.length === 0) {
    return null;
  }

  try {
    let confidence: number;

    if (method === 'mean') {
      const avgLogprob = logprobs.reduce((a, b) => a + b, 0) / logprobs.length;
      confidence = Math.exp(avgLogprob);
    } else if (method === 'min') {
      const minLogprob = Math.min(...logprobs);
      confidence = Math.exp(minLogprob);
    } else if (method === 'median') {
      const sorted = [...logprobs].sort((a, b) => a - b);
      const medianLogprob = sorted[Math.floor(sorted.length / 2)];
      confidence = Math.exp(medianLogprob);
    } else {
      return null;
    }

    // Clamp to [0, 1]
    return Math.max(0.0, Math.min(1.0, confidence));
  } catch (e) {
    return null;
  }
}

/**
 * Estimate confidence from content characteristics (fallback)
 *
 * Uses heuristics when logprobs unavailable:
 * - Response length
 * - Presence of uncertainty markers
 * - Content structure
 *
 * @param content - Generated content
 * @param query - Original query
 * @returns Estimated confidence 0.0-1.0
 */
export function estimateConfidenceFromContent(content: string, _query: string): number {
  let confidence = 0.75; // Base confidence

  // Check for uncertainty markers
  const uncertaintyMarkers = [
    "i'm not sure",
    "i don't know",
    'maybe',
    'possibly',
    'unclear',
    'uncertain',
    'cannot determine',
    'insufficient',
  ];
  const contentLower = content.toLowerCase();

  if (uncertaintyMarkers.some((marker) => contentLower.includes(marker))) {
    confidence -= 0.15;
  }

  // Very short responses might be uncertain
  if (content.trim().length < 20) {
    confidence -= 0.1;
  }

  // Longer, structured responses suggest confidence
  if (content.split('\n').length > 3) {
    confidence += 0.05;
  }

  // Clamp to reasonable range
  return Math.max(0.5, Math.min(0.85, confidence));
}

/**
 * Estimate token count from text
 *
 * Uses standard approximation: 1 token ≈ 0.75 words (1.3 tokens per word)
 *
 * @param text - Text to estimate tokens for
 * @returns Estimated token count
 */
export function estimateTokens(text: string): number {
  if (!text) {
    return 0;
  }
  const wordCount = text.trim().split(/\s+/).length;
  return Math.max(1, Math.round(wordCount * 1.3));
}
