/**
 * ToolRouter Tests
 *
 * Comprehensive test suite for ToolRouter class.
 * Tests tool capability filtering, validation, suggestions, and statistics.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  ToolRouter,
  createToolRouter,
  type ToolRouterConfig,
} from '../../routers/tool-router';
import type { ModelConfig } from '../../config';
import type { Tool } from '../../types';
import { ConfigurationError } from '../../errors';

describe('ToolRouter', () => {
  // Test models
  const toolCapableModel1: ModelConfig = {
    name: 'gpt-4',
    provider: 'openai',
    cost: 0.03,
    supportsTools: true,
  };

  const toolCapableModel2: ModelConfig = {
    name: 'claude-3-sonnet',
    provider: 'anthropic',
    cost: 0.015,
    supportsTools: true,
  };

  const nonToolModel1: ModelConfig = {
    name: 'gpt-3.5',
    provider: 'openai',
    cost: 0.002,
    supportsTools: false,
  };

  const nonToolModel2: ModelConfig = {
    name: 'text-davinci-003',
    provider: 'openai',
    cost: 0.02,
  };

  const allModels = [
    toolCapableModel1,
    toolCapableModel2,
    nonToolModel1,
    nonToolModel2,
  ];

  // Test tools
  const weatherTool: Tool = {
    type: 'function',
    function: {
      name: 'get_weather',
      description: 'Get current weather',
      parameters: {
        type: 'object',
        properties: {
          city: { type: 'string' },
        },
        required: ['city'],
      },
    },
  };

  const calculatorTool: Tool = {
    type: 'function',
    function: {
      name: 'calculator',
      description: 'Perform calculations',
      parameters: {
        type: 'object',
        properties: {
          expression: { type: 'string' },
        },
        required: ['expression'],
      },
    },
  };

  let router: ToolRouter;

  beforeEach(() => {
    router = new ToolRouter({ models: allModels });
  });

  describe('constructor and configuration', () => {
    it('should initialize with models', () => {
      expect(router).toBeInstanceOf(ToolRouter);
    });

    it('should count tool-capable models', () => {
      const stats = router.getStats();
      expect(stats.toolCapableModels).toBe(2);
      expect(stats.totalModels).toBe(4);
    });

    it('should calculate tool capability rate', () => {
      const stats = router.getStats();
      expect(stats.toolCapabilityRate).toBe(50);
    });

    it('should support verbose mode', () => {
      const verboseRouter = new ToolRouter({
        models: allModels,
        verbose: true,
      });
      expect(verboseRouter).toBeInstanceOf(ToolRouter);
    });

    it('should handle no tool-capable models', () => {
      const router = new ToolRouter({
        models: [nonToolModel1, nonToolModel2],
      });
      const stats = router.getStats();
      expect(stats.toolCapableModels).toBe(0);
      expect(stats.toolCapabilityRate).toBe(0);
    });
  });

  describe('filterToolCapableModels', () => {
    it('should return all models when no tools provided', () => {
      const result = router.filterToolCapableModels({
        availableModels: allModels,
      });

      expect(result.models).toEqual(allModels);
      expect(result.filteredCount).toBe(0);
      expect(result.hasCapableModels).toBe(true);
      expect(result.reason).toContain('No tools');
    });

    it('should return all models when empty tools array', () => {
      const result = router.filterToolCapableModels({
        tools: [],
        availableModels: allModels,
      });

      expect(result.models).toEqual(allModels);
      expect(result.filteredCount).toBe(0);
    });

    it('should filter to tool-capable models when tools provided', () => {
      const result = router.filterToolCapableModels({
        tools: [weatherTool],
        availableModels: allModels,
      });

      expect(result.models).toHaveLength(2);
      expect(result.models).toContain(toolCapableModel1);
      expect(result.models).toContain(toolCapableModel2);
      expect(result.filteredCount).toBe(2);
      expect(result.hasCapableModels).toBe(true);
    });

    it('should throw error when tools provided but no capable models', () => {
      const nonToolModels = [nonToolModel1, nonToolModel2];

      expect(() => {
        router.filterToolCapableModels({
          tools: [weatherTool],
          availableModels: nonToolModels,
        });
      }).toThrow(ConfigurationError);
    });

    it('should include helpful error message with model names', () => {
      const nonToolModels = [nonToolModel1, nonToolModel2];

      try {
        router.filterToolCapableModels({
          tools: [weatherTool],
          availableModels: nonToolModels,
        });
        expect.fail('Should have thrown error');
      } catch (error: any) {
        expect(error.message).toContain('gpt-3.5');
        expect(error.message).toContain('text-davinci-003');
        expect(error.message).toContain('Tools provided: 1');
      }
    });

    it('should handle multiple tools', () => {
      const result = router.filterToolCapableModels({
        tools: [weatherTool, calculatorTool],
        availableModels: allModels,
      });

      expect(result.models).toHaveLength(2);
      expect(result.reason).toContain('2 tools');
    });

    it('should provide detailed reason', () => {
      const result = router.filterToolCapableModels({
        tools: [weatherTool],
        availableModels: allModels,
      });

      expect(result.reason).toContain('2/4');
      expect(result.reason).toContain('tool-capable');
    });
  });

  describe('validateTools', () => {
    it('should validate well-formed tools', () => {
      const validation = router.validateTools([weatherTool, calculatorTool]);

      expect(validation.valid).toBe(true);
      expect(validation.errors).toHaveLength(0);
    });

    it('should return valid for empty tools array', () => {
      const validation = router.validateTools([]);

      expect(validation.valid).toBe(true);
      expect(validation.errors).toHaveLength(0);
      expect(validation.warnings).toHaveLength(0);
    });

    it('should detect missing name field', () => {
      const invalidTool = {
        type: 'function',
        function: {
          description: 'Test',
          parameters: { type: 'object' },
        },
      } as Tool;

      const validation = router.validateTools([invalidTool]);

      expect(validation.valid).toBe(false);
      expect(validation.errors.length).toBeGreaterThan(0);
      expect(validation.errors.some((e) => e.includes('name'))).toBe(true);
    });

    it('should warn about missing description', () => {
      const toolWithoutDesc: Tool = {
        type: 'function',
        function: {
          name: 'test',
          parameters: { type: 'object', properties: {} },
        },
      } as Tool;

      const validation = router.validateTools([toolWithoutDesc]);

      expect(validation.valid).toBe(true); // Still valid
      expect(validation.warnings.length).toBeGreaterThan(0);
      expect(validation.warnings.some((w) => w.includes('description'))).toBe(
        true
      );
    });

    it('should detect missing parameters field', () => {
      const invalidTool = {
        type: 'function',
        function: {
          name: 'test',
          description: 'Test tool',
        },
      } as Tool;

      const validation = router.validateTools([invalidTool]);

      expect(validation.valid).toBe(false);
      expect(validation.errors.some((e) => e.includes('parameters'))).toBe(
        true
      );
    });

    it('should detect invalid parameters type', () => {
      const invalidTool = {
        type: 'function',
        function: {
          name: 'test',
          description: 'Test',
          parameters: 'invalid' as any,
        },
      };

      const validation = router.validateTools([invalidTool]);

      expect(validation.valid).toBe(false);
      expect(validation.errors.some((e) => e.includes('object'))).toBe(true);
    });

    it('should warn about missing type in parameters', () => {
      const toolWithoutType: Tool = {
        type: 'function',
        function: {
          name: 'test',
          description: 'Test',
          parameters: {
            properties: { foo: { type: 'string' } },
          } as any,
        },
      };

      const validation = router.validateTools([toolWithoutType]);

      expect(validation.warnings.some((w) => w.includes('type'))).toBe(true);
    });

    it('should warn about missing properties in parameters', () => {
      const toolWithoutProps: Tool = {
        type: 'function',
        function: {
          name: 'test',
          description: 'Test',
          parameters: {
            type: 'object',
          } as any,
        },
      };

      const validation = router.validateTools([toolWithoutProps]);

      expect(validation.warnings.some((w) => w.includes('properties'))).toBe(
        true
      );
    });

    it('should detect duplicate tool names', () => {
      const tools: Tool[] = [
        { ...weatherTool },
        { ...weatherTool }, // Duplicate
      ];

      const validation = router.validateTools(tools);

      expect(validation.valid).toBe(false);
      expect(validation.errors.some((e) => e.includes('Duplicate'))).toBe(true);
      expect(validation.errors.some((e) => e.includes('get_weather'))).toBe(
        true
      );
    });

    it('should handle multiple validation errors', () => {
      const invalidTools: Tool[] = [
        { name: 'test1' } as Tool, // Missing parameters
        { name: 'test2' } as Tool, // Missing parameters
      ];

      const validation = router.validateTools(invalidTools);

      expect(validation.valid).toBe(false);
      expect(validation.errors.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('suggestModelsForTools', () => {
    it('should suggest tool-capable models', () => {
      const suggested = router.suggestModelsForTools({
        tools: [weatherTool],
      });

      expect(suggested).toHaveLength(2);
      expect(suggested.every((m) => m.supportsTools)).toBe(true);
    });

    it('should filter by max cost', () => {
      const suggested = router.suggestModelsForTools({
        tools: [weatherTool],
        maxCost: 0.02,
      });

      expect(suggested).toHaveLength(1);
      expect(suggested[0].name).toBe('claude-3-sonnet');
      expect(suggested[0].cost).toBeLessThanOrEqual(0.02);
    });

    it('should sort by tool quality and cost', () => {
      const modelWithQuality: ModelConfig = {
        name: 'high-quality',
        provider: 'test',
        cost: 0.05,
        supportsTools: true,
        toolQuality: 0.9,
      };

      const router = new ToolRouter({
        models: [modelWithQuality, toolCapableModel1, toolCapableModel2],
      });

      const suggested = router.suggestModelsForTools({
        tools: [weatherTool],
      });

      // Should prioritize high quality
      expect(suggested[0].name).toBe('high-quality');
    });

    it('should sort by cost when quality is same', () => {
      const suggested = router.suggestModelsForTools({
        tools: [weatherTool],
      });

      // Lower cost should come first (when quality is same/missing)
      expect(suggested[0].cost).toBeLessThan(suggested[1].cost);
    });

    it('should return empty array when no models meet criteria', () => {
      const suggested = router.suggestModelsForTools({
        tools: [weatherTool],
        maxCost: 0.001, // Too low
      });

      expect(suggested).toHaveLength(0);
    });
  });

  describe('statistics tracking', () => {
    it('should track total filters', () => {
      router.filterToolCapableModels({ availableModels: allModels });
      router.filterToolCapableModels({ availableModels: allModels });

      const stats = router.getStats();
      expect(stats.totalFilters).toBe(2);
    });

    it('should track filter hits (when tools provided)', () => {
      router.filterToolCapableModels({ availableModels: allModels }); // No tools
      router.filterToolCapableModels({
        tools: [weatherTool],
        availableModels: allModels,
      }); // With tools

      const stats = router.getStats();
      expect(stats.filterHits).toBe(1);
    });

    it('should track no capable models errors', () => {
      const nonToolModels = [nonToolModel1, nonToolModel2];

      try {
        router.filterToolCapableModels({
          tools: [weatherTool],
          availableModels: nonToolModels,
        });
      } catch (e) {
        // Expected
      }

      const stats = router.getStats();
      expect(stats.noCapableModels).toBe(1);
    });

    it('should calculate average models before filter', () => {
      router.filterToolCapableModels({ availableModels: allModels }); // 4 models
      router.filterToolCapableModels({
        availableModels: [toolCapableModel1, toolCapableModel2],
      }); // 2 models

      const stats = router.getStats();
      expect(stats.avgModelsBeforeFilter).toBe(3); // (4 + 2) / 2
    });

    it('should calculate average models after filter', () => {
      router.filterToolCapableModels({ availableModels: allModels }); // Returns 4
      router.filterToolCapableModels({
        tools: [weatherTool],
        availableModels: allModels,
      }); // Returns 2

      const stats = router.getStats();
      expect(stats.avgModelsAfterFilter).toBe(3); // (4 + 2) / 2
    });

    it('should reset statistics', () => {
      router.filterToolCapableModels({ availableModels: allModels });
      router.filterToolCapableModels({
        tools: [weatherTool],
        availableModels: allModels,
      });

      router.resetStats();

      const stats = router.getStats();
      expect(stats.totalFilters).toBe(0);
      expect(stats.filterHits).toBe(0);
      expect(stats.noCapableModels).toBe(0);
      expect(stats.avgModelsBeforeFilter).toBe(0);
      expect(stats.avgModelsAfterFilter).toBe(0);
    });

    it('should handle zero stats gracefully', () => {
      const stats = router.getStats();
      expect(stats.avgModelsBeforeFilter).toBe(0);
      expect(stats.avgModelsAfterFilter).toBe(0);
    });
  });

  describe('getToolCapableModels', () => {
    it('should return list of tool-capable models', () => {
      const capable = router.getToolCapableModels();

      expect(capable).toHaveLength(2);
      expect(capable).toContain(toolCapableModel1);
      expect(capable).toContain(toolCapableModel2);
    });

    it('should return copy of array', () => {
      const capable1 = router.getToolCapableModels();
      const capable2 = router.getToolCapableModels();

      expect(capable1).not.toBe(capable2); // Different arrays
      expect(capable1).toEqual(capable2); // Same contents
    });

    it('should return empty array when no tool-capable models', () => {
      const router = new ToolRouter({
        models: [nonToolModel1, nonToolModel2],
      });

      const capable = router.getToolCapableModels();
      expect(capable).toHaveLength(0);
    });
  });

  describe('createToolRouter factory', () => {
    it('should create router with factory', () => {
      const router = createToolRouter({ models: allModels });

      expect(router).toBeInstanceOf(ToolRouter);
    });

    it('should pass config to constructor', () => {
      const router = createToolRouter({
        models: allModels,
        verbose: true,
      });

      expect(router).toBeInstanceOf(ToolRouter);
    });
  });

  describe('edge cases', () => {
    it('should handle empty models array', () => {
      const router = new ToolRouter({ models: [] });

      const stats = router.getStats();
      expect(stats.totalModels).toBe(0);
      expect(stats.toolCapableModels).toBe(0);
      expect(stats.toolCapabilityRate).toBe(0);
    });

    it('should handle models without supportsTools property', () => {
      const modelWithoutProp: ModelConfig = {
        name: 'test',
        provider: 'test',
        cost: 0.01,
      };

      const router = new ToolRouter({ models: [modelWithoutProp] });

      // Should be treated as not supporting tools
      expect(() => {
        router.filterToolCapableModels({
          tools: [weatherTool],
          availableModels: [modelWithoutProp],
        });
      }).toThrow(ConfigurationError);
    });

    it('should handle null parameters in tool validation', () => {
      const invalidTool = {
        type: 'function',
        function: {
          name: 'test',
          description: 'Test',
          parameters: null as any,
        },
      };

      const validation = router.validateTools([invalidTool]);

      expect(validation.valid).toBe(false);
      expect(validation.errors.some((e) => e.includes('object'))).toBe(true);
    });

    it('should handle very large model arrays', () => {
      const manyModels: ModelConfig[] = Array.from({ length: 1000 }, (_, i) => ({
        name: `model-${i}`,
        provider: 'test',
        cost: 0.01,
        supportsTools: i % 2 === 0, // Half support tools
      }));

      const router = new ToolRouter({ models: manyModels });

      const stats = router.getStats();
      expect(stats.totalModels).toBe(1000);
      expect(stats.toolCapableModels).toBe(500);
    });
  });
});
