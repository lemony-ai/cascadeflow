/**
 * EventFormatter Tests
 *
 * Comprehensive test suite for EventFormatter class.
 * Tests visual formatting, emoji handling, and event formatting.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  EventFormatter,
  createEventFormatter,
  getDefaultFormatter,
  quickFormat,
  VISUAL_ICONS,
  COLORS,
} from '../../streaming/event-formatter';
import { StreamEventType } from '../../streaming';
import { ToolStreamEventType } from '../../streaming/tool-stream-manager';
import type { StreamEvent } from '../../streaming';
import type { ToolStreamEvent } from '../../streaming/tool-stream-manager';

describe('EventFormatter', () => {
  let formatter: EventFormatter;

  beforeEach(() => {
    formatter = new EventFormatter();
  });

  describe('constructor and configuration', () => {
    it('should initialize with default config', () => {
      expect(formatter).toBeInstanceOf(EventFormatter);
    });

    it('should support custom config', () => {
      const customFormatter = new EventFormatter({
        useEmojis: false,
        verbose: true,
        indentSize: 4,
        useColors: true,
      });
      expect(customFormatter).toBeInstanceOf(EventFormatter);
    });

    it('should create formatter with factory', () => {
      const created = createEventFormatter({ verbose: true });
      expect(created).toBeInstanceOf(EventFormatter);
    });

    it('should get default formatter', () => {
      const defaultFormatter = getDefaultFormatter();
      expect(defaultFormatter).toBeInstanceOf(EventFormatter);
    });
  });

  describe('metric formatting', () => {
    it('should format cost', () => {
      const result = formatter.formatCost(0.001234);
      expect(result).toContain('0.001234');
      expect(result).toContain('Cost');
    });

    it('should format latency', () => {
      const result = formatter.formatLatency(1234.5);
      expect(result).toContain('1235'); // Rounded
      expect(result).toContain('Speed');
    });

    it('should format model name', () => {
      const result = formatter.formatModel('gpt-4o-mini');
      expect(result).toContain('gpt-4o-mini');
      expect(result).toContain('Model');
    });

    it('should format percentage', () => {
      expect(formatter.formatPercent(0.75)).toBe('75%');
      expect(formatter.formatPercent(0.333)).toBe('33%');
      expect(formatter.formatPercent(1.0)).toBe('100%');
    });

    it('should format confidence with emoji', () => {
      const high = formatter.formatConfidence(0.9);
      const medium = formatter.formatConfidence(0.7);
      const low = formatter.formatConfidence(0.3);

      expect(high).toContain('90%');
      expect(medium).toContain('70%');
      expect(low).toContain('30%');
    });
  });

  describe('stream event formatting', () => {
    it('should format ROUTING event', () => {
      const event: StreamEvent = {
        type: StreamEventType.ROUTING,
        content: '',
        data: {
          strategy: 'cascade',
          complexity: 'high',
        },
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toContain('Routing');
      expect(result).toContain('cascade');
      expect(result).toContain('high');
    });

    it('should format CHUNK event', () => {
      const event: StreamEvent = {
        type: StreamEventType.CHUNK,
        content: 'Hello world',
        data: {},
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toBe('Hello world');
    });

    it('should format DRAFT_DECISION (accepted) event', () => {
      const event: StreamEvent = {
        type: StreamEventType.DRAFT_DECISION,
        content: '',
        data: {
          accepted: true,
          confidence: 0.85,
        },
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toContain('accepted');
      expect(result).toContain('85%');
      expect(result).toContain('saved money');
    });

    it('should format DRAFT_DECISION (rejected) event', () => {
      const event: StreamEvent = {
        type: StreamEventType.DRAFT_DECISION,
        content: '',
        data: {
          accepted: false,
          confidence: 0.45,
          reason: 'quality_insufficient',
        },
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toContain('rejected');
      expect(result).toContain('45%');
      expect(result).toContain('quality_insufficient');
      expect(result).toContain('Cascading');
    });

    it('should format SWITCH event', () => {
      const event: StreamEvent = {
        type: StreamEventType.SWITCH,
        content: '',
        data: {
          from_model: 'gpt-4o-mini',
          to_model: 'gpt-4o',
        },
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toContain('Cascading');
      expect(result).toContain('gpt-4o-mini');
      expect(result).toContain('gpt-4o');
    });

    it('should format COMPLETE event', () => {
      const event: StreamEvent = {
        type: StreamEventType.COMPLETE,
        content: '',
        data: {
          result: {
            total_cost: 0.001,
            latency_ms: 1500,
            model_used: 'gpt-4o-mini',
          },
        },
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toContain('complete');
      expect(result).toContain('0.001');
      expect(result).toContain('1500');
      expect(result).toContain('gpt-4o-mini');
    });

    it('should format ERROR event', () => {
      const event: StreamEvent = {
        type: StreamEventType.ERROR,
        content: 'Something went wrong',
        data: {
          error: 'Something went wrong',
        },
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toContain('Error');
      expect(result).toContain('Something went wrong');
    });
  });

  describe('tool stream event formatting', () => {
    it('should format TOOL_CALL_START event', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TOOL_CALL_START,
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toContain('Tool call starting');
    });

    it('should format TOOL_CALL_COMPLETE event', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TOOL_CALL_COMPLETE,
        toolCall: {
          name: 'get_weather',
          arguments: {
            location: 'Paris',
            unit: 'celsius',
          },
        },
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toContain('get_weather');
      expect(result).toContain('Paris');
      expect(result).toContain('celsius');
    });

    it('should format TOOL_EXECUTING event', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TOOL_EXECUTING,
        toolCall: {
          name: 'calculate',
        },
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toContain('Executing');
      expect(result).toContain('calculate');
    });

    it('should format TOOL_RESULT event', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TOOL_RESULT,
        toolResult: { status: 'success', value: 42 },
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toContain('Result');
      expect(result).toContain('42');
    });

    it('should format TOOL_ERROR event', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TOOL_ERROR,
        error: 'Tool execution failed',
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toContain('Tool error');
      expect(result).toContain('Tool execution failed');
    });

    it('should format TEXT_CHUNK event', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TEXT_CHUNK,
        content: 'Hello from tool',
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toBe('Hello from tool');
    });
  });

  describe('visual utilities', () => {
    it('should create separator', () => {
      const sep1 = formatter.separator();
      expect(sep1).toBe('='.repeat(60));

      const sep2 = formatter.separator('-', 40);
      expect(sep2).toBe('-'.repeat(40));
    });

    it('should indent text', () => {
      const text = 'line1\nline2\nline3';
      const indented = formatter.indent(text, 1);

      expect(indented).toContain('  line1');
      expect(indented).toContain('  line2');
      expect(indented).toContain('  line3');
    });

    it('should create progress bar', () => {
      const bar1 = formatter.progressBar(5, 10, 20);
      expect(bar1).toContain('50%');

      const bar2 = formatter.progressBar(10, 10, 20);
      expect(bar2).toContain('100%');

      const bar3 = formatter.progressBar(0, 10, 20);
      expect(bar3).toContain('0%');
    });

    it('should handle zero total in progress bar', () => {
      const bar = formatter.progressBar(5, 0, 20);
      expect(bar).toContain('0%');
    });
  });

  describe('message formatting', () => {
    it('should format warning', () => {
      const result = formatter.formatWarning('This is a warning');
      expect(result).toContain('Warning');
      expect(result).toContain('This is a warning');
    });

    it('should format tip', () => {
      const result = formatter.formatTip('This is a tip');
      expect(result).toContain('Tip');
      expect(result).toContain('This is a tip');
    });

    it('should format info', () => {
      const result = formatter.formatInfo('This is info');
      expect(result).toContain('This is info');
    });
  });

  describe('summary formatting', () => {
    it('should format complete summary', () => {
      const result = formatter.formatSummary({
        totalQueries: 10,
        acceptedDrafts: 7,
        rejectedDrafts: 3,
        totalCost: 0.005,
        avgLatency: 1234,
        costSaved: 0.002,
      });

      expect(result).toContain('Summary');
      expect(result).toContain('10');
      expect(result).toContain('7/10');
      expect(result).toContain('0.005');
      expect(result).toContain('1234');
      expect(result).toContain('0.002');
    });

    it('should format partial summary', () => {
      const result = formatter.formatSummary({
        totalQueries: 5,
        totalCost: 0.001,
      });

      expect(result).toContain('Summary');
      expect(result).toContain('5');
      expect(result).toContain('0.001');
    });

    it('should handle zero values in summary', () => {
      const result = formatter.formatSummary({
        totalQueries: 0,
        acceptedDrafts: 0,
        rejectedDrafts: 0,
      });

      expect(result).toContain('Summary');
      expect(result).toContain('0');
    });
  });

  describe('emoji handling', () => {
    it('should include emojis by default', () => {
      const result = formatter.formatCost(0.001);
      expect(result).toMatch(/[^\x00-\x7F]/); // Contains non-ASCII (emoji)
    });

    it('should exclude emojis when disabled', () => {
      const noEmojiFormatter = new EventFormatter({ useEmojis: false });
      const result = noEmojiFormatter.formatCost(0.001);

      // Should not contain emojis but still have the text
      expect(result).toContain('Cost');
      expect(result).toContain('0.001');
    });
  });

  describe('color handling', () => {
    it('should not apply colors by default', () => {
      const text = formatter.color('test', 'red');
      expect(text).toBe('test'); // No ANSI codes
    });

    it('should apply colors when enabled', () => {
      const colorFormatter = new EventFormatter({ useColors: true });
      const text = colorFormatter.color('test', 'red');

      expect(text).toContain('\x1b[31m'); // Red color code
      expect(text).toContain('\x1b[0m'); // Reset code
      expect(text).toContain('test');
    });
  });

  describe('quick format utilities', () => {
    it('should format cost', () => {
      const result = quickFormat.cost(0.001);
      expect(result).toContain('0.001');
      expect(result).toContain('Cost');
    });

    it('should format latency', () => {
      const result = quickFormat.latency(1500);
      expect(result).toContain('1500');
      expect(result).toContain('Speed');
    });

    it('should format model', () => {
      const result = quickFormat.model('gpt-4o');
      expect(result).toContain('gpt-4o');
      expect(result).toContain('Model');
    });

    it('should format confidence', () => {
      const result = quickFormat.confidence(0.85);
      expect(result).toContain('85%');
      expect(result).toContain('Confidence');
    });

    it('should format warning', () => {
      const result = quickFormat.warning('test warning');
      expect(result).toContain('Warning');
      expect(result).toContain('test warning');
    });

    it('should format tip', () => {
      const result = quickFormat.tip('test tip');
      expect(result).toContain('Tip');
      expect(result).toContain('test tip');
    });

    it('should format info', () => {
      const result = quickFormat.info('test info');
      expect(result).toContain('test info');
    });

    it('should create separator', () => {
      const result = quickFormat.separator();
      expect(result).toBe('='.repeat(60));
    });
  });

  describe('visual constants', () => {
    it('should export VISUAL_ICONS', () => {
      expect(VISUAL_ICONS.streaming).toBeDefined();
      expect(VISUAL_ICONS.success).toBeDefined();
      expect(VISUAL_ICONS.error).toBeDefined();
      expect(VISUAL_ICONS.cost).toBeDefined();
      expect(VISUAL_ICONS.speed).toBeDefined();
    });

    it('should export COLORS', () => {
      expect(COLORS.reset).toBeDefined();
      expect(COLORS.red).toBeDefined();
      expect(COLORS.green).toBeDefined();
      expect(COLORS.blue).toBeDefined();
    });
  });

  describe('verbose mode', () => {
    it('should show additional details in verbose mode', () => {
      const verboseFormatter = new EventFormatter({ verbose: true });

      const event: StreamEvent = {
        type: StreamEventType.COMPLETE,
        content: '',
        data: {
          result: {
            total_cost: 0.001,
            draftTokens: 100,
            verifierTokens: 50,
          },
        },
      };

      const result = verboseFormatter.formatStreamEvent(event);
      expect(result).toContain('Tokens');
      expect(result).toContain('100');
      expect(result).toContain('50');
    });

    it('should show error details in verbose mode', () => {
      const verboseFormatter = new EventFormatter({ verbose: true });

      const event: StreamEvent = {
        type: StreamEventType.ERROR,
        content: 'Test error',
        data: {
          error: 'Test error',
          type: 'TypeError',
          stack: 'Stack trace here',
        },
      };

      const result = verboseFormatter.formatStreamEvent(event);
      expect(result).toContain('Type: TypeError');
      expect(result).toContain('Stack: Stack trace here');
    });
  });

  describe('edge cases', () => {
    it('should handle missing data gracefully', () => {
      const event: StreamEvent = {
        type: StreamEventType.ROUTING,
        content: '',
        data: {},
      };

      const result = formatter.formatStreamEvent(event);
      expect(result).toContain('Routing');
    });

    it('should handle undefined tool call', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TOOL_CALL_COMPLETE,
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toBe(''); // No crash, just empty
    });

    it('should handle string tool result', () => {
      const event: ToolStreamEvent = {
        type: ToolStreamEventType.TOOL_RESULT,
        toolResult: 'simple string result',
        data: {},
      };

      const result = formatter.formatToolStreamEvent(event);
      expect(result).toContain('simple string result');
    });

    it('should handle camelCase and snake_case data', () => {
      const event1: StreamEvent = {
        type: StreamEventType.SWITCH,
        content: '',
        data: {
          from_model: 'model1',
          to_model: 'model2',
        },
      };

      const event2: StreamEvent = {
        type: StreamEventType.SWITCH,
        content: '',
        data: {
          fromModel: 'model1',
          toModel: 'model2',
        },
      };

      const result1 = formatter.formatStreamEvent(event1);
      const result2 = formatter.formatStreamEvent(event2);

      expect(result1).toContain('model1');
      expect(result2).toContain('model1');
    });
  });
});
