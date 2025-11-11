/**
 * Tool Router - Tool Capability Filtering and Routing
 *
 * The ToolRouter handles tool-specific routing logic:
 * - Filters models by tool support capability
 * - Validates tool schemas
 * - Tracks tool usage statistics
 * - Separate from PreRouter (complexity-based routing)
 *
 * Architecture:
 *   PreRouter → Complexity-based routing
 *   ToolRouter → Tool capability filtering
 *   Agent → Orchestrates both
 *
 * Port from Python cascadeflow/routing/tool_router.py
 *
 * @example
 * ```typescript
 * const toolRouter = new ToolRouter({
 *   models: allModels,
 *   verbose: true
 * });
 *
 * const result = toolRouter.filterToolCapableModels({
 *   tools: [weatherTool],
 *   availableModels: allModels
 * });
 *
 * console.log(`Capable models: ${result.models.length}`);
 * ```
 */

import type { ModelConfig } from '../config';
import type { Tool } from '../types';
import { ConfigurationError } from '../errors';

/**
 * Result from tool capability filtering
 */
export interface ToolFilterResult {
  /** Models that support tools */
  models: ModelConfig[];

  /** Number of models filtered out */
  filteredCount: number;

  /** Whether any capable models found */
  hasCapableModels: boolean;

  /** Explanation */
  reason: string;
}

/**
 * Tool validation result
 */
export interface ToolValidationResult {
  /** Whether validation passed */
  valid: boolean;

  /** List of validation errors */
  errors: string[];

  /** List of warnings */
  warnings: string[];
}

/**
 * ToolRouter statistics
 */
export interface ToolRouterStats {
  /** Total number of filter operations */
  totalFilters: number;

  /** Times filtering was needed (tools provided) */
  filterHits: number;

  /** Times no capable models found */
  noCapableModels: number;

  /** Average models before filtering */
  avgModelsBeforeFilter: number;

  /** Average models after filtering */
  avgModelsAfterFilter: number;

  /** Number of tool-capable models */
  toolCapableModels: number;

  /** Total number of models */
  totalModels: number;

  /** Percentage of models that support tools */
  toolCapabilityRate: number;
}

/**
 * Configuration for ToolRouter
 */
export interface ToolRouterConfig {
  /** List of all available models */
  models: ModelConfig[];

  /** Enable verbose logging */
  verbose?: boolean;
}

/**
 * Options for filterToolCapableModels
 */
export interface FilterToolCapableModelsOptions {
  /** List of tools (if undefined, returns all models) */
  tools?: Tool[];

  /** Models to filter from */
  availableModels: ModelConfig[];
}

/**
 * Options for suggestModelsForTools
 */
export interface SuggestModelsOptions {
  /** List of tools */
  tools: Tool[];

  /** Maximum cost per 1M tokens */
  maxCost?: number;
}

/**
 * Router for tool capability filtering
 *
 * Responsibilities:
 * - Filter models by tool support capability
 * - Validate tool configurations
 * - Track tool routing statistics
 * - Provide insights on tool-capable models
 *
 * Separate from PreRouter to maintain clean separation of concerns:
 * - PreRouter: Complexity-based routing (HARD → direct, SIMPLE → cascade)
 * - ToolRouter: Capability-based filtering (tools → only tool-capable models)
 *
 * @example
 * ```typescript
 * const router = new ToolRouter({
 *   models: [
 *     { name: 'gpt-4', provider: 'openai', supportsTools: true },
 *     { name: 'gpt-3.5', provider: 'openai', supportsTools: false }
 *   ],
 *   verbose: true
 * });
 *
 * const result = router.filterToolCapableModels({
 *   tools: [weatherTool],
 *   availableModels: allModels
 * });
 *
 * console.log(`Found ${result.models.length} capable models`);
 * ```
 */
export class ToolRouter {
  private models: ModelConfig[];
  private verbose: boolean;
  private toolCapableModels: ModelConfig[];
  private stats: {
    totalFilters: number;
    modelsBeforeFilter: number[];
    modelsAfterFilter: number[];
    filterHits: number;
    noCapableModels: number;
  };

  constructor(config: ToolRouterConfig) {
    this.models = config.models;
    this.verbose = config.verbose ?? false;

    // Initialize statistics
    this.stats = {
      totalFilters: 0,
      modelsBeforeFilter: [],
      modelsAfterFilter: [],
      filterHits: 0,
      noCapableModels: 0,
    };

    // Count tool-capable models
    this.toolCapableModels = this.models.filter(
      (m) => m.supportsTools === true
    );

    if (this.verbose) {
      console.log(
        `ToolRouter initialized: ${this.toolCapableModels.length}/${this.models.length} models support tools`
      );
      if (this.toolCapableModels.length > 0) {
        console.log(
          `Tool-capable models: ${this.toolCapableModels.map((m) => m.name).join(', ')}`
        );
      }
    }
  }

  /**
   * Filter models to only those that support tool calling
   *
   * @param options - Filter options
   * @returns ToolFilterResult with capable models and statistics
   * @throws ConfigurationError if tools provided but no capable models
   *
   * @example
   * ```typescript
   * const result = router.filterToolCapableModels({
   *   tools: [weatherTool, calculatorTool],
   *   availableModels: allModels
   * });
   *
   * if (result.hasCapableModels) {
   *   console.log(`Using ${result.models.length} tool-capable models`);
   * }
   * ```
   */
  filterToolCapableModels(
    options: FilterToolCapableModelsOptions
  ): ToolFilterResult {
    const { tools, availableModels } = options;

    // Update statistics
    this.stats.totalFilters++;
    this.stats.modelsBeforeFilter.push(availableModels.length);

    // If no tools, return all models
    if (!tools || tools.length === 0) {
      this.stats.modelsAfterFilter.push(availableModels.length);
      return {
        models: availableModels,
        filteredCount: 0,
        hasCapableModels: true,
        reason: 'No tools provided, all models available',
      };
    }

    // Filter to tool-capable models
    const capableModels = availableModels.filter(
      (m) => m.supportsTools === true
    );

    const filteredCount = availableModels.length - capableModels.length;
    this.stats.filterHits++;
    this.stats.modelsAfterFilter.push(capableModels.length);

    // Check if we have any capable models
    if (capableModels.length === 0) {
      this.stats.noCapableModels++;

      // Get names of models that don't support tools
      const nonCapableNames = availableModels.map((m) => m.name);

      const errorMsg =
        `No tool-capable models available. ` +
        `Tools provided: ${tools.length}, ` +
        `Models available: ${nonCapableNames.join(', ')}. ` +
        `Please add tool-capable models to your configuration.`;

      if (this.verbose) {
        console.error(errorMsg);
      }

      throw new ConfigurationError(errorMsg);
    }

    const reason =
      `Filtered to ${capableModels.length}/${availableModels.length} ` +
      `tool-capable models for ${tools.length} tools`;

    if (this.verbose) {
      console.log(reason);
      console.log(
        `Tool-capable models: ${capableModels.map((m) => m.name).join(', ')}`
      );
    }

    return {
      models: capableModels,
      filteredCount,
      hasCapableModels: true,
      reason,
    };
  }

  /**
   * Validate tool configurations
   *
   * Checks:
   * - Required fields present (name, description, parameters)
   * - Parameters is valid JSON Schema
   * - No duplicate tool names
   *
   * @param tools - List of tools to validate
   * @returns ToolValidationResult with validation status
   *
   * @example
   * ```typescript
   * const validation = router.validateTools([
   *   {
   *     name: 'weather',
   *     description: 'Get weather',
   *     parameters: {
   *       type: 'object',
   *       properties: { city: { type: 'string' } }
   *     }
   *   }
   * ]);
   *
   * if (!validation.valid) {
   *   console.error('Validation errors:', validation.errors);
   * }
   * ```
   */
  validateTools(tools: Tool[]): ToolValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!tools || tools.length === 0) {
      return { valid: true, errors: [], warnings: [] };
    }

    // Check for duplicate names
    const names = tools.map((tool) => tool.name);
    const duplicates = new Set(
      names.filter((name, index) => names.indexOf(name) !== index)
    );

    if (duplicates.size > 0) {
      errors.push(`Duplicate tool names: ${Array.from(duplicates).join(', ')}`);
    }

    // Validate each tool
    for (let i = 0; i < tools.length; i++) {
      const tool = tools[i];
      const toolId = tool.name || `tool_${i}`;

      // Check required fields
      if (!tool.name) {
        errors.push(`${toolId}: Missing 'name' field`);
      }

      if (!tool.description) {
        warnings.push(`${toolId}: Missing 'description' (recommended)`);
      }

      // Check parameters field
      if (!('parameters' in tool)) {
        errors.push(`${toolId}: Missing 'parameters' field`);
      } else if (tool.parameters === null) {
        // Check null explicitly (typeof null === 'object' in JavaScript)
        errors.push(`${toolId}: 'parameters' must be an object`);
      } else if (typeof tool.parameters !== 'object') {
        // Check if it's an object type
        errors.push(`${toolId}: 'parameters' must be an object`);
      } else {
        // Check for JSON Schema structure
        if (!('type' in tool.parameters)) {
          warnings.push(`${toolId}: 'parameters' missing 'type' field`);
        }
        if (!('properties' in tool.parameters)) {
          warnings.push(`${toolId}: 'parameters' missing 'properties' field`);
        }
      }
    }

    const valid = errors.length === 0;

    if (!valid && this.verbose) {
      console.warn(`Tool validation failed: ${errors.join(', ')}`);
    }

    if (warnings.length > 0 && this.verbose) {
      console.log(`Tool validation warnings: ${warnings.join(', ')}`);
    }

    return { valid, errors, warnings };
  }

  /**
   * Suggest best models for given tools
   *
   * Considers:
   * - Tool support capability
   * - Cost constraints
   * - Model quality for tool calling
   *
   * @param options - Suggestion options
   * @returns List of suggested models (sorted by quality/cost)
   *
   * @example
   * ```typescript
   * const suggested = router.suggestModelsForTools({
   *   tools: [weatherTool, calculatorTool],
   *   maxCost: 0.01  // $0.01 per 1M tokens
   * });
   *
   * console.log(`Best model: ${suggested[0].name}`);
   * ```
   */
  suggestModelsForTools(options: SuggestModelsOptions): ModelConfig[] {
    const { tools, maxCost } = options;

    // Start with tool-capable models
    let candidates = [...this.toolCapableModels];

    // Filter by cost if specified
    if (maxCost !== undefined) {
      candidates = candidates.filter((m) => m.cost <= maxCost);
    }

    // Sort by tool quality (if available) and cost
    candidates.sort((a, b) => {
      // Higher quality first, then lower cost
      const qualityA = (a as any).toolQuality ?? 0.5;
      const qualityB = (b as any).toolQuality ?? 0.5;

      if (qualityA !== qualityB) {
        return qualityB - qualityA; // Higher quality first
      }

      return a.cost - b.cost; // Lower cost first
    });

    if (this.verbose && candidates.length > 0) {
      const topModels = candidates.slice(0, 3).map((m) => m.name);
      console.log(
        `Suggested models for ${tools.length} tools: ${topModels.join(', ')}`
      );
    }

    return candidates;
  }

  /**
   * Get tool router statistics
   *
   * @returns ToolRouterStats with filtering and usage statistics
   *
   * @example
   * ```typescript
   * const stats = router.getStats();
   * console.log(`Tool capability rate: ${stats.toolCapabilityRate.toFixed(1)}%`);
   * console.log(`Average models after filter: ${stats.avgModelsAfterFilter.toFixed(1)}`);
   * ```
   */
  getStats(): ToolRouterStats {
    // Calculate averages
    const avgBefore =
      this.stats.modelsBeforeFilter.length > 0
        ? this.stats.modelsBeforeFilter.reduce((a, b) => a + b, 0) /
          this.stats.modelsBeforeFilter.length
        : 0;

    const avgAfter =
      this.stats.modelsAfterFilter.length > 0
        ? this.stats.modelsAfterFilter.reduce((a, b) => a + b, 0) /
          this.stats.modelsAfterFilter.length
        : 0;

    const toolCapabilityRate =
      this.models.length > 0
        ? (this.toolCapableModels.length / this.models.length) * 100
        : 0;

    return {
      totalFilters: this.stats.totalFilters,
      filterHits: this.stats.filterHits,
      noCapableModels: this.stats.noCapableModels,
      avgModelsBeforeFilter: avgBefore,
      avgModelsAfterFilter: avgAfter,
      toolCapableModels: this.toolCapableModels.length,
      totalModels: this.models.length,
      toolCapabilityRate,
    };
  }

  /**
   * Reset statistics tracking
   *
   * @example
   * ```typescript
   * router.resetStats();
   * console.log(router.getStats().totalFilters); // 0
   * ```
   */
  resetStats(): void {
    this.stats = {
      totalFilters: 0,
      modelsBeforeFilter: [],
      modelsAfterFilter: [],
      filterHits: 0,
      noCapableModels: 0,
    };

    if (this.verbose) {
      console.log('ToolRouter statistics reset');
    }
  }

  /**
   * Get list of tool-capable models
   *
   * @returns List of models that support tools
   *
   * @example
   * ```typescript
   * const capable = router.getToolCapableModels();
   * console.log(`${capable.length} models support tools`);
   * ```
   */
  getToolCapableModels(): ModelConfig[] {
    return [...this.toolCapableModels];
  }
}

/**
 * Create a ToolRouter with configuration
 *
 * @param config - ToolRouter configuration
 * @returns Configured ToolRouter instance
 *
 * @example
 * ```typescript
 * import { createToolRouter } from '@cascadeflow/core';
 *
 * const router = createToolRouter({
 *   models: allModels,
 *   verbose: true
 * });
 * ```
 */
export function createToolRouter(config: ToolRouterConfig): ToolRouter {
  return new ToolRouter(config);
}
