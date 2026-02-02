import { describe, expect, it } from 'vitest';
import { ToolCallDetector } from '../../src/tool-cascade/detector';
import type { Tool } from '../../src/types';

const weatherTool: Tool = {
  type: 'function',
  function: {
    name: 'get_weather',
    description: 'Get the weather forecast',
    parameters: {
      type: 'object',
      properties: {
        location: { type: 'string' },
      },
      required: ['location'],
    },
  },
};

describe('ToolCallDetector', () => {
  it('detects explicit tool calls', () => {
    const detector = new ToolCallDetector();
    const intent = detector.detect({
      toolCalls: [{ name: 'get_weather', arguments: { location: 'Paris' } }],
    });

    expect(intent.shouldCallTool).toBe(true);
    expect(intent.confidence).toBe(1);
    expect(intent.layers).toContain('explicit');
  });

  it('detects structured tool call schemas in text', () => {
    const detector = new ToolCallDetector();
    const intent = detector.detect({
      query: '{"tool_calls":[{"function":{"name":"get_weather"}}]}',
    });

    expect(intent.shouldCallTool).toBe(true);
    expect(intent.layers).toContain('structured');
  });

  it('detects heuristic tool intent keywords', () => {
    const detector = new ToolCallDetector();
    const intent = detector.detect({
      query: 'Search for the latest cascadeflow release notes.',
    });

    expect(intent.shouldCallTool).toBe(true);
    expect(intent.layers).toContain('heuristic');
  });

  it('detects tool name hints as fallback', () => {
    const detector = new ToolCallDetector();
    const intent = detector.detect({
      query: 'Use get_weather for Tokyo.',
      tools: [weatherTool],
    });

    expect(intent.shouldCallTool).toBe(true);
    expect(intent.toolHints).toContain('get_weather');
    expect(intent.layers).toContain('fallback');
  });
});
