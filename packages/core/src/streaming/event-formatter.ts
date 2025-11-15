/**
 * Event Formatter - Visual Feedback for Streaming Events
 *
 * Provides rich visual formatting for streaming events with emojis, colors,
 * and structured output.
 *
 * Features:
 * - Emoji-based event indicators
 * - Cost and latency formatting
 * - Progress indicators
 * - Confidence scoring display
 * - Tool call formatting
 * - Error and warning display
 *
 * @example
 * ```typescript
 * import { EventFormatter } from '@cascadeflow/core/streaming';
 *
 * const formatter = new EventFormatter();
 * console.log(formatter.formatCost(0.000123)); // "💰 Cost: $0.000123"
 * console.log(formatter.formatLatency(1500)); // "⚡ Speed: 1500ms"
 * ```
 */

import { StreamEventType } from '../streaming';
import type { StreamEvent } from '../streaming';
import { ToolStreamEventType } from './tool-stream-manager';
import type { ToolStreamEvent } from './tool-stream-manager';

/**
 * Visual icons for different event types and states
 */
export const VISUAL_ICONS = {
  // General
  streaming: '🌊',
  success: '✓',
  failure: '✗',
  complete: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
  tip: '💡',

  // Metrics
  cost: '💰',
  speed: '⚡',
  target: '🎯',
  rocket: '🚀',
  clock: '⏱️',

  // Actions
  cascade: '⤴️',
  tool: '🔧',
  search: '🔍',
  fire: '🔥',
  sparkles: '✨',

  // Documentation
  book: '📖',
  books: '📚',
  scroll: '📜',
  memo: '📝',

  // Status
  thinking: '🤔',
  robot: '🤖',
  brain: '🧠',
  eyes: '👀',
  check: '✔️',
  cross: '❌',
} as const;

/**
 * Configuration for EventFormatter
 */
export interface EventFormatterConfig {
  /** Use emojis in output */
  useEmojis?: boolean;

  /** Show detailed metrics */
  verbose?: boolean;

  /** Indent size for nested content */
  indentSize?: number;

  /** Use colors (ANSI escape codes) */
  useColors?: boolean;
}

/**
 * ANSI color codes for terminal output
 */
export const COLORS = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  gray: '\x1b[90m',
} as const;

/**
 * EventFormatter - Rich visual formatting for streaming events
 *
 * Provides consistent visual feedback for streaming operations with:
 * - Emoji indicators for different event types
 * - Formatted metrics (cost, latency, confidence)
 * - Progress indicators
 * - Tool call display
 * - Error and warning formatting
 */
export class EventFormatter {
  private useEmojis: boolean;
  private verbose: boolean;
  private indentSize: number;
  private useColors: boolean;

  constructor(config: EventFormatterConfig = {}) {
    this.useEmojis = config.useEmojis ?? true;
    this.verbose = config.verbose ?? false;
    this.indentSize = config.indentSize ?? 2;
    this.useColors = config.useColors ?? false;
  }

  /**
   * Format a complete streaming event
   */
  formatStreamEvent(event: StreamEvent): string {
    switch (event.type) {
      case StreamEventType.ROUTING:
        return this.formatRouting(event);
      case StreamEventType.CHUNK:
        return event.content; // Raw content, no formatting
      case StreamEventType.DRAFT_DECISION:
        return this.formatDraftDecision(event);
      case StreamEventType.SWITCH:
        return this.formatSwitch(event);
      case StreamEventType.COMPLETE:
        return this.formatComplete(event);
      case StreamEventType.ERROR:
        return this.formatError(event);
      default:
        return '';
    }
  }

  /**
   * Format a tool streaming event
   */
  formatToolStreamEvent(event: ToolStreamEvent): string {
    switch (event.type) {
      case ToolStreamEventType.ROUTING:
        return this.formatRouting(event as any);
      case ToolStreamEventType.TOOL_CALL_START:
        return this.formatToolCallStart();
      case ToolStreamEventType.TOOL_CALL_DELTA:
        return ''; // Progressive updates, no formatting needed
      case ToolStreamEventType.TOOL_CALL_COMPLETE:
        return this.formatToolCallComplete(event);
      case ToolStreamEventType.TOOL_EXECUTING:
        return this.formatToolExecuting(event);
      case ToolStreamEventType.TOOL_RESULT:
        return this.formatToolResult(event);
      case ToolStreamEventType.TOOL_ERROR:
        return this.formatToolError(event);
      case ToolStreamEventType.TEXT_CHUNK:
        return event.content || '';
      case ToolStreamEventType.COMPLETE:
        return this.formatComplete(event as any);
      case ToolStreamEventType.ERROR:
        return this.formatError(event as any);
      default:
        return '';
    }
  }

  /**
   * Format routing event
   */
  private formatRouting(event: StreamEvent): string {
    const icon = this.emoji(VISUAL_ICONS.streaming);
    const strategy = event.data?.strategy || 'cascade';
    const complexity = event.data?.complexity || 'unknown';

    return `${icon} Routing: ${strategy} (complexity: ${complexity})`;
  }

  /**
   * Format draft decision event
   */
  private formatDraftDecision(event: StreamEvent): string {
    const accepted = event.data?.accepted ?? false;
    const confidence = event.data?.confidence ?? 0;
    const reason = event.data?.reason;

    if (accepted) {
      const icon = this.emoji(VISUAL_ICONS.success);
      return `\n${icon} Draft accepted (${this.formatPercent(confidence)} confidence)` +
        `\n  ${this.emoji(VISUAL_ICONS.rocket)} Verifier skipped (saved money!)`;
    } else {
      const icon = this.emoji(VISUAL_ICONS.failure);
      let msg = `\n${icon} Draft rejected (${this.formatPercent(confidence)} confidence)`;
      if (reason) {
        msg += `: ${reason}`;
      }
      msg += `\n  ${this.emoji(VISUAL_ICONS.cascade)} Cascading to better model...`;
      return msg;
    }
  }

  /**
   * Format switch/cascade event
   */
  private formatSwitch(event: StreamEvent): string {
    const fromModel = event.data?.from_model || event.data?.fromModel || 'tier-1';
    const toModel = event.data?.to_model || event.data?.toModel || 'tier-2';
    const icon = this.emoji(VISUAL_ICONS.cascade);

    return `${icon} Cascading: ${fromModel} → ${toModel}`;
  }

  /**
   * Format completion event
   */
  private formatComplete(event: StreamEvent): string {
    const result = event.data?.result || {};
    const lines: string[] = [];

    lines.push(`\n${this.emoji(VISUAL_ICONS.complete)} Streaming complete`);

    if (result.total_cost !== undefined || result.totalCost !== undefined) {
      const cost = result.total_cost ?? result.totalCost;
      lines.push(this.formatCost(cost));
    }

    if (result.latency_ms !== undefined || result.latencyMs !== undefined) {
      const latency = result.latency_ms ?? result.latencyMs;
      lines.push(this.formatLatency(latency));
    }

    if (result.model_used || result.modelUsed) {
      const model = result.model_used || result.modelUsed;
      lines.push(this.formatModel(model));
    }

    if (this.verbose && result.draftTokens) {
      lines.push(`${this.emoji(VISUAL_ICONS.memo)} Tokens: ${result.draftTokens}` +
        (result.verifierTokens ? ` + ${result.verifierTokens}` : ''));
    }

    return lines.join('\n');
  }

  /**
   * Format error event
   */
  private formatError(event: StreamEvent): string {
    const error = event.data?.error || event.content || 'Unknown error';
    const icon = this.emoji(VISUAL_ICONS.error);

    let msg = `\n${icon} Error: ${error}`;

    if (this.verbose && event.data?.type) {
      msg += `\n  Type: ${event.data.type}`;
    }

    if (this.verbose && event.data?.stack) {
      msg += `\n  Stack: ${event.data.stack}`;
    }

    return msg;
  }

  /**
   * Format tool call start event
   */
  private formatToolCallStart(): string {
    const icon = this.emoji(VISUAL_ICONS.tool);
    return `\n${icon} Tool call starting...`;
  }

  /**
   * Format tool call complete event
   */
  private formatToolCallComplete(event: ToolStreamEvent): string {
    const toolCall = event.toolCall || event.data?.tool_call || event.data?.toolCall;
    if (!toolCall) {
      return '';
    }

    const icon = this.emoji(VISUAL_ICONS.tool);
    const name = toolCall.name || 'unknown';
    const args = toolCall.arguments || toolCall.args || {};

    return `\n${icon} Tool: ${name}(${this.formatArgs(args)})`;
  }

  /**
   * Format tool executing event
   */
  private formatToolExecuting(event: ToolStreamEvent): string {
    const toolCall = event.toolCall || event.data?.tool_call;
    const name = toolCall?.name || 'unknown';
    const icon = this.emoji(VISUAL_ICONS.thinking);

    return `${icon} Executing ${name}...`;
  }

  /**
   * Format tool result event
   */
  private formatToolResult(event: ToolStreamEvent): string {
    const result = event.toolResult || event.data?.result;
    const icon = this.emoji(VISUAL_ICONS.check);

    if (typeof result === 'object') {
      return `${icon} Result: ${JSON.stringify(result, null, 2)}`;
    }

    return `${icon} Result: ${result}`;
  }

  /**
   * Format tool error event
   */
  private formatToolError(event: ToolStreamEvent): string {
    const error = event.error || event.data?.error || 'Unknown error';
    const icon = this.emoji(VISUAL_ICONS.error);

    return `${icon} Tool error: ${error}`;
  }

  /**
   * Format cost value
   */
  formatCost(cost: number): string {
    const icon = this.emoji(VISUAL_ICONS.cost);
    return `${icon} Cost: $${cost.toFixed(6)}`;
  }

  /**
   * Format latency value
   */
  formatLatency(latency: number): string {
    const icon = this.emoji(VISUAL_ICONS.speed);
    return `${icon} Speed: ${Math.round(latency)}ms`;
  }

  /**
   * Format model name
   */
  formatModel(model: string): string {
    const icon = this.emoji(VISUAL_ICONS.target);
    return `${icon} Model: ${model}`;
  }

  /**
   * Format confidence as percentage
   */
  formatPercent(value: number): string {
    return `${Math.round(value * 100)}%`;
  }

  /**
   * Format confidence score with emoji indicator
   */
  formatConfidence(confidence: number): string {
    let icon: string;
    if (confidence >= 0.8) {
      icon = this.emoji(VISUAL_ICONS.fire);
    } else if (confidence >= 0.6) {
      icon = this.emoji(VISUAL_ICONS.check);
    } else if (confidence >= 0.4) {
      icon = this.emoji(VISUAL_ICONS.warning);
    } else {
      icon = this.emoji(VISUAL_ICONS.cross);
    }

    return `${icon} Confidence: ${this.formatPercent(confidence)}`;
  }

  /**
   * Format function arguments
   */
  private formatArgs(args: Record<string, any>): string {
    if (Object.keys(args).length === 0) {
      return '';
    }

    const pairs = Object.entries(args).map(([key, value]) => {
      if (typeof value === 'string') {
        return `${key}="${value}"`;
      }
      return `${key}=${JSON.stringify(value)}`;
    });

    return pairs.join(', ');
  }

  /**
   * Create a separator line
   */
  separator(char: string = '=', length: number = 60): string {
    return char.repeat(length);
  }

  /**
   * Create an indented block
   */
  indent(text: string, level: number = 1): string {
    const spaces = ' '.repeat(this.indentSize * level);
    return text.split('\n').map((line) => spaces + line).join('\n');
  }

  /**
   * Create a progress bar
   */
  progressBar(current: number, total: number, width: number = 20): string {
    const percent = total > 0 ? current / total : 0;
    const filled = Math.round(width * percent);
    const empty = width - filled;

    const bar = '█'.repeat(filled) + '░'.repeat(empty);
    return `[${bar}] ${Math.round(percent * 100)}%`;
  }

  /**
   * Format a warning message
   */
  formatWarning(message: string): string {
    const icon = this.emoji(VISUAL_ICONS.warning);
    return `${icon} Warning: ${message}`;
  }

  /**
   * Format a tip message
   */
  formatTip(message: string): string {
    const icon = this.emoji(VISUAL_ICONS.tip);
    return `${icon} Tip: ${message}`;
  }

  /**
   * Format an info message
   */
  formatInfo(message: string): string {
    const icon = this.emoji(VISUAL_ICONS.info);
    return `${icon} ${message}`;
  }

  /**
   * Apply color to text (if colors enabled)
   */
  color(text: string, color: keyof typeof COLORS): string {
    if (!this.useColors) {
      return text;
    }

    return `${COLORS[color]}${text}${COLORS.reset}`;
  }

  /**
   * Get emoji or empty string if disabled
   */
  private emoji(icon: string): string {
    return this.useEmojis ? icon : '';
  }

  /**
   * Format a summary of results
   */
  formatSummary(data: {
    totalQueries?: number;
    acceptedDrafts?: number;
    rejectedDrafts?: number;
    totalCost?: number;
    avgLatency?: number;
    costSaved?: number;
  }): string {
    const lines: string[] = [];

    lines.push(this.separator());
    lines.push(`\n${this.emoji(VISUAL_ICONS.books)} Summary\n`);

    if (data.totalQueries !== undefined) {
      lines.push(`  Total queries: ${data.totalQueries}`);
    }

    if (data.acceptedDrafts !== undefined && data.rejectedDrafts !== undefined) {
      const total = data.acceptedDrafts + data.rejectedDrafts;
      const acceptRate = total > 0 ? data.acceptedDrafts / total : 0;
      lines.push(`  Accepted drafts: ${data.acceptedDrafts}/${total} (${this.formatPercent(acceptRate)})`);
    }

    if (data.totalCost !== undefined) {
      lines.push(`  ${this.formatCost(data.totalCost)}`);
    }

    if (data.avgLatency !== undefined) {
      lines.push(`  Avg latency: ${Math.round(data.avgLatency)}ms`);
    }

    if (data.costSaved !== undefined && data.costSaved > 0) {
      lines.push(`  ${this.emoji(VISUAL_ICONS.sparkles)} Saved: $${data.costSaved.toFixed(6)}`);
    }

    return lines.join('\n');
  }
}

/**
 * Create an EventFormatter instance
 *
 * @param config - Formatter configuration
 * @returns EventFormatter instance
 *
 * @example
 * ```typescript
 * import { createEventFormatter } from '@cascadeflow/core/streaming';
 *
 * const formatter = createEventFormatter({ verbose: true });
 * console.log(formatter.formatCost(0.001));
 * ```
 */
export function createEventFormatter(config?: EventFormatterConfig): EventFormatter {
  return new EventFormatter(config);
}

/**
 * Default formatter instance (singleton)
 */
let defaultFormatter: EventFormatter | null = null;

/**
 * Get or create the default formatter instance
 */
export function getDefaultFormatter(): EventFormatter {
  if (!defaultFormatter) {
    defaultFormatter = new EventFormatter();
  }
  return defaultFormatter;
}

/**
 * Quick format functions using default formatter
 */
export const quickFormat = {
  cost: (value: number) => getDefaultFormatter().formatCost(value),
  latency: (value: number) => getDefaultFormatter().formatLatency(value),
  model: (value: string) => getDefaultFormatter().formatModel(value),
  confidence: (value: number) => getDefaultFormatter().formatConfidence(value),
  warning: (message: string) => getDefaultFormatter().formatWarning(message),
  tip: (message: string) => getDefaultFormatter().formatTip(message),
  info: (message: string) => getDefaultFormatter().formatInfo(message),
  separator: (char?: string, length?: number) => getDefaultFormatter().separator(char, length),
};
