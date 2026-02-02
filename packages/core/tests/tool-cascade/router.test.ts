import { describe, expect, it } from 'vitest';
import { ToolCascadeRouter } from '../../src/tool-cascade/router';
import type { Tool } from '../../src/types';
import type { ToolComplexityAnalyzerLike } from '../../src/tool-cascade/types';

const weatherTool: Tool = {
  type: 'function',
  function: {
    name: 'get_weather',
    description: 'Get the weather forecast',
    parameters: {
      type: 'object',
      properties: { location: { type: 'string' } },
      required: ['location'],
    },
  },
};

const searchTool: Tool = {
  type: 'function',
  function: {
    name: 'web_search',
    description: 'Search the web for information',
    parameters: {
      type: 'object',
      properties: { query: { type: 'string' } },
      required: ['query'],
    },
  },
};

const deleteTool: Tool = {
  type: 'function',
  function: {
    name: 'delete_file',
    description: 'Delete a file from disk',
    parameters: {
      type: 'object',
      properties: { path: { type: 'string' } },
      required: ['path'],
    },
  },
};

const stubAnalyzer: ToolComplexityAnalyzerLike = {
  analyzeToolCall: () => ({ complexityLevel: 'simple', score: 2 }),
};

describe('ToolCascadeRouter', () => {
  it('classifies risk tiers for common tools', () => {
    const router = new ToolCascadeRouter();
    expect(router.classifyRiskTier(weatherTool)).toBe('low');
    expect(router.classifyRiskTier(searchTool)).toBe('medium');
    expect(router.classifyRiskTier(deleteTool)).toBe('critical');
  });

  it('routes to skip when intent confidence is low', () => {
    const router = new ToolCascadeRouter(stubAnalyzer);
    const decision = router.route(
      { query: 'Hello', tools: [weatherTool] },
      0.2
    );

    expect(decision.strategy).toBe('skip');
  });

  it('routes high-risk tools to direct', () => {
    const router = new ToolCascadeRouter(stubAnalyzer);
    const decision = router.route(
      { query: 'Delete file', tools: [deleteTool] },
      0.9
    );

    expect(decision.strategy).toBe('direct');
  });

  it('routes low-risk, simple complexity to cascade', () => {
    const router = new ToolCascadeRouter(stubAnalyzer);
    const decision = router.route(
      { query: 'Weather in Paris', tools: [weatherTool] },
      0.9
    );

    expect(decision.strategy).toBe('cascade');
  });
});
