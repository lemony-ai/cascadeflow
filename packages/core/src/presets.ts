/**
 * Preset Configurations for cascadeflow
 *
 * These presets provide pre-configured model cascades for common use cases,
 * making it easy to get started without detailed configuration.
 */

import type { ModelConfig } from './config';

/**
 * Preset options for quality mode
 *
 * - **cost-optimized**: Maximum cost savings, accepts more drafts (quality threshold: 0.6)
 * - **balanced**: Balance between cost and quality (quality threshold: 0.7) - Default
 * - **strict**: Higher quality, more escalations (quality threshold: 0.8)
 */
export type QualityMode = 'cost-optimized' | 'balanced' | 'strict';

/**
 * Preset options for performance
 *
 * - **fast**: Ultra-fast providers (Groq) for low latency
 * - **balanced**: Good speed and reliability (mix of providers)
 * - **reliable**: Most reliable providers (OpenAI, Anthropic)
 */
export type PerformanceMode = 'fast' | 'balanced' | 'reliable';

/**
 * Configuration for creating a preset
 */
export interface PresetConfig {
  /**
   * Quality mode - controls draft acceptance rate
   * @default 'balanced'
   */
  quality?: QualityMode;

  /**
   * Performance mode - controls provider selection
   * @default 'balanced'
   */
  performance?: PerformanceMode;

  /**
   * Whether to include a premium tier (gpt-4o, claude-opus)
   * @default false
   */
  includePremium?: boolean;
}

/**
 * Quality threshold presets
 */
const QUALITY_THRESHOLDS: Record<QualityMode, number> = {
  'cost-optimized': 0.6,
  'balanced': 0.7,
  'strict': 0.8,
};

/**
 * Get quality configuration for a mode
 */
function getQualityConfig(mode: QualityMode = 'balanced') {
  return {
    threshold: QUALITY_THRESHOLDS[mode],
    mode,
  };
}

/**
 * PRESET: Best Overall
 *
 * Recommended for most use cases. Uses Claude Haiku (fast, high quality)
 * with GPT-4o-mini as backup. Requires Anthropic and OpenAI API keys.
 *
 * **Cost:** ~$0.0008/query avg
 * **Speed:** Fast (~2-3s)
 * **Quality:** Excellent
 *
 * @example
 * ```typescript
 * import { CascadeAgent, PRESET_BEST_OVERALL } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent(PRESET_BEST_OVERALL);
 * const result = await agent.run('Your query here');
 * ```
 */
export const PRESET_BEST_OVERALL: { models: ModelConfig[] } = {
  models: [
    {
      name: 'claude-haiku-4-5',
      provider: 'anthropic',
      cost: 0.001,
    },
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
    },
  ],
};

/**
 * PRESET: Ultra Fast
 *
 * Maximum speed with Groq's ultra-fast inference. Best for real-time
 * applications where latency is critical. Requires Groq API key.
 *
 * **Cost:** ~$0.00005/query avg
 * **Speed:** Ultra-fast (~1-2s)
 * **Quality:** Good
 *
 * @example
 * ```typescript
 * import { CascadeAgent, PRESET_ULTRA_FAST } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent(PRESET_ULTRA_FAST);
 * const result = await agent.run('Quick question');
 * ```
 */
export const PRESET_ULTRA_FAST: { models: ModelConfig[] } = {
  models: [
    {
      name: 'llama-3.1-8b-instant',
      provider: 'groq',
      cost: 0.00005,
    },
    {
      name: 'llama-3.3-70b-versatile',
      provider: 'groq',
      cost: 0.00069,
    },
  ],
};

/**
 * PRESET: Ultra Cheap
 *
 * Minimum cost with Groq + OpenAI. Best for high-volume, cost-sensitive
 * applications. Requires Groq and OpenAI API keys.
 *
 * **Cost:** ~$0.00008/query avg
 * **Speed:** Very fast (~1-3s)
 * **Quality:** Good
 *
 * @example
 * ```typescript
 * import { CascadeAgent, PRESET_ULTRA_CHEAP } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent(PRESET_ULTRA_CHEAP);
 * const result = await agent.run('Cost-effective query');
 * ```
 */
export const PRESET_ULTRA_CHEAP: { models: ModelConfig[] } = {
  models: [
    {
      name: 'llama-3.1-8b-instant',
      provider: 'groq',
      cost: 0.00005,
    },
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
    },
  ],
};

/**
 * PRESET: OpenAI Only
 *
 * Uses only OpenAI models. Best when you want to stay within one provider
 * or don't have other API keys. Requires OpenAI API key.
 *
 * **Cost:** ~$0.0005/query avg
 * **Speed:** Fast (~2-4s)
 * **Quality:** Excellent
 *
 * @example
 * ```typescript
 * import { CascadeAgent, PRESET_OPENAI_ONLY } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent(PRESET_OPENAI_ONLY);
 * const result = await agent.run('OpenAI-powered query');
 * ```
 */
export const PRESET_OPENAI_ONLY: { models: ModelConfig[] } = {
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.0025,
    },
  ],
};

/**
 * PRESET: Anthropic Only
 *
 * Uses only Anthropic Claude models. Best for Claude enthusiasts or
 * when you prefer Anthropic's approach. Requires Anthropic API key.
 *
 * **Cost:** ~$0.002/query avg
 * **Speed:** Fast (~2-3s)
 * **Quality:** Excellent
 *
 * @example
 * ```typescript
 * import { CascadeAgent, PRESET_ANTHROPIC_ONLY } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent(PRESET_ANTHROPIC_ONLY);
 * const result = await agent.run('Claude-powered query');
 * ```
 */
export const PRESET_ANTHROPIC_ONLY: { models: ModelConfig[] } = {
  models: [
    {
      name: 'claude-haiku-4-5',
      provider: 'anthropic',
      cost: 0.001,
    },
    {
      name: 'claude-sonnet-4-5',
      provider: 'anthropic',
      cost: 0.003,
    },
  ],
};

/**
 * PRESET: Free (Local)
 *
 * Uses Ollama for free, local inference. No API keys needed, but requires
 * Ollama installation and models downloaded locally. Best for privacy or
 * when offline.
 *
 * **Cost:** $0 (free, local)
 * **Speed:** Moderate (~3-5s, depends on hardware)
 * **Quality:** Good
 *
 * @example
 * ```typescript
 * import { CascadeAgent, PRESET_FREE_LOCAL } from '@cascadeflow/core';
 *
 * // Requires: ollama pull llama3.1:8b && ollama pull llama3.1:70b
 * const agent = new CascadeAgent(PRESET_FREE_LOCAL);
 * const result = await agent.run('Local, private query');
 * ```
 */
export const PRESET_FREE_LOCAL: { models: ModelConfig[] } = {
  models: [
    {
      name: 'llama3.1:8b',
      provider: 'ollama',
      cost: 0,
    },
    {
      name: 'llama3.1:70b',
      provider: 'ollama',
      cost: 0,
    },
  ],
};

/**
 * Create a custom preset with specified quality and performance modes
 *
 * @param config - Preset configuration options
 * @returns Model configuration for CascadeAgent
 *
 * @example
 * ```typescript
 * import { CascadeAgent, createPreset } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent(
 *   createPreset({
 *     quality: 'strict',      // Higher quality threshold
 *     performance: 'fast',    // Use fast providers
 *     includePremium: true    // Add premium tier
 *   })
 * );
 * ```
 */
export function createPreset(config: PresetConfig = {}): {
  models: ModelConfig[];
  quality?: { threshold: number; mode: QualityMode };
} {
  const {
    quality = 'balanced',
    performance = 'balanced',
    includePremium = false,
  } = config;

  const models: ModelConfig[] = [];

  // Select models based on performance mode
  if (performance === 'fast') {
    // Groq for maximum speed
    models.push({
      name: 'llama-3.1-8b-instant',
      provider: 'groq',
      cost: 0.00005,
    });
    models.push({
      name: 'llama-3.3-70b-versatile',
      provider: 'groq',
      cost: 0.00069,
    });
  } else if (performance === 'reliable') {
    // OpenAI/Anthropic for reliability
    models.push({
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
    });
    models.push({
      name: 'claude-haiku-4-5',
      provider: 'anthropic',
      cost: 0.001,
    });
  } else {
    // Balanced - mix of speed and reliability
    models.push({
      name: 'claude-haiku-4-5',
      provider: 'anthropic',
      cost: 0.001,
    });
    models.push({
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
    });
  }

  // Add premium tier if requested
  if (includePremium) {
    models.push({
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.0025,
    });
  }

  return {
    models,
    quality: getQualityConfig(quality),
  };
}

/**
 * All available presets
 */
export const PRESETS = {
  BEST_OVERALL: PRESET_BEST_OVERALL,
  ULTRA_FAST: PRESET_ULTRA_FAST,
  ULTRA_CHEAP: PRESET_ULTRA_CHEAP,
  OPENAI_ONLY: PRESET_OPENAI_ONLY,
  ANTHROPIC_ONLY: PRESET_ANTHROPIC_ONLY,
  FREE_LOCAL: PRESET_FREE_LOCAL,
} as const;

/**
 * Type for preset names
 */
export type PresetName = keyof typeof PRESETS;
