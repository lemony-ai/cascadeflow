/**
 * Tool Call Detector
 *
 * Four-layer detection pipeline:
 * 1) Explicit tool call objects
 * 2) Structured tool call markup/JSON
 * 3) Heuristic intent keywords
 * 4) Fallback tool-name matching
 */

import type { Tool } from '../types';
import type { ToolCallIntent } from './types';

export interface ToolCallDetectionInput {
  query?: string;
  toolCalls?: Record<string, unknown>[];
  tools?: Tool[];
}

const STRUCTURED_TOOL_PATTERNS = [
  /"tool_calls"\s*:/i,
  /"function"\s*:\s*\{/i,
  /"arguments"\s*:\s*\{/i,
  /"tool"\s*:\s*\{/i,
];

const HEURISTIC_KEYWORDS = [
  'search',
  'lookup',
  'find',
  'fetch',
  'get',
  'call',
  'invoke',
  'api',
  'weather',
  'forecast',
  'file',
  'read',
  'write',
  'delete',
  'upload',
  'download',
];

const FALLBACK_HINTS = ['tool', 'function', 'run', 'execute', 'query'];

export class ToolCallDetector {
  detect(input: ToolCallDetectionInput): ToolCallIntent {
    const reasons: string[] = [];
    const layers: ToolCallIntent['layers'] = [];
    const toolHints: string[] = [];

    const query = input.query?.trim() ?? '';
    const toolCalls = input.toolCalls ?? [];
    const tools = input.tools ?? [];

    if (toolCalls.length > 0) {
      layers.push('explicit');
      reasons.push('Tool call objects provided.');
      return {
        shouldCallTool: true,
        confidence: 1,
        layers,
        reasons,
        toolHints,
        rawToolCalls: toolCalls as any,
      };
    }

    if (query && STRUCTURED_TOOL_PATTERNS.some((pattern) => pattern.test(query))) {
      layers.push('structured');
      reasons.push('Structured tool-call schema detected in text.');
    }

    const lowerQuery = query.toLowerCase();
    if (query && HEURISTIC_KEYWORDS.some((keyword) => lowerQuery.includes(keyword))) {
      layers.push('heuristic');
      reasons.push('Heuristic tool-intent keywords detected.');
    }

    const toolNameHints = tools
      .map((tool) => tool.function.name)
      .filter((name) => lowerQuery.includes(name.toLowerCase()));
    if (toolNameHints.length > 0) {
      layers.push('fallback');
      toolHints.push(...toolNameHints);
      reasons.push('Tool name hints matched in query.');
    } else if (query && FALLBACK_HINTS.some((hint) => lowerQuery.includes(hint))) {
      layers.push('fallback');
      reasons.push('Fallback tool call phrasing detected.');
    }

    const confidence = this.calculateConfidence(layers);

    return {
      shouldCallTool: confidence >= 0.5,
      confidence,
      layers,
      reasons,
      toolHints,
    };
  }

  private calculateConfidence(layers: ToolCallIntent['layers']): number {
    if (layers.includes('explicit')) return 1;

    const weights: Record<NonNullable<ToolCallIntent['layers'][number]>, number> = {
      structured: 0.8,
      heuristic: 0.6,
      fallback: 0.4,
      explicit: 1,
    };

    const total = layers.reduce((sum, layer) => sum + weights[layer], 0);
    return Math.min(1, total / 1.2);
  }
}
