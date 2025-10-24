/**
 * Result types for CascadeFlow operations
 */

import type { ToolCall } from './types';

/**
 * Comprehensive result from cascade agent execution
 *
 * Contains the generated content plus detailed metrics about costs, latency,
 * quality validation, and cascade behavior.
 *
 * @example Basic usage
 * ```typescript
 * const result = await agent.run('What is TypeScript?');
 * console.log(result.content);  // Generated response
 * console.log(`Model: ${result.modelUsed}`);
 * console.log(`Cost: $${result.totalCost.toFixed(6)}`);
 * ```
 *
 * @example Cascade metrics
 * ```typescript
 * const result = await agent.run('Explain quantum computing');
 *
 * if (result.cascaded) {
 *   console.log(`Draft model: ${result.draftModel}`);
 *   console.log(`Draft accepted: ${result.draftAccepted}`);
 *
 *   if (!result.draftAccepted) {
 *     console.log(`Escalated to: ${result.verifierModel}`);
 *     console.log(`Reason: ${result.rejectionReason}`);
 *   }
 * }
 * ```
 *
 * @example Cost and savings
 * ```typescript
 * const result = await agent.run(query);
 *
 * console.log(`Total cost: $${result.totalCost.toFixed(6)}`);
 * console.log(`Cost saved: $${result.costSaved?.toFixed(6)}`);
 * console.log(`Savings: ${result.savingsPercentage}%`);
 *
 * if (result.draftCost && result.verifierCost) {
 *   console.log(`Draft: $${result.draftCost.toFixed(6)}`);
 *   console.log(`Verifier: $${result.verifierCost.toFixed(6)}`);
 * }
 * ```
 *
 * @example Latency breakdown
 * ```typescript
 * const result = await agent.run(query);
 *
 * const providerLatency = (result.draftLatencyMs || 0) + (result.verifierLatencyMs || 0);
 * const cascadeOverhead = result.latencyMs - providerLatency;
 *
 * console.log(`Total latency: ${result.latencyMs}ms`);
 * console.log(`Provider API: ${providerLatency}ms (${(providerLatency/result.latencyMs*100).toFixed(1)}%)`);
 * console.log(`Cascade overhead: ${cascadeOverhead}ms (${(cascadeOverhead/result.latencyMs*100).toFixed(1)}%)`);
 * ```
 *
 * @example Quality metrics
 * ```typescript
 * const result = await agent.run(query);
 *
 * console.log(`Quality score: ${result.qualityScore}`);
 * console.log(`Threshold: ${result.qualityThreshold}`);
 * console.log(`Quality passed: ${result.qualityCheckPassed}`);
 *
 * if (!result.qualityCheckPassed) {
 *   console.log(`Rejection reason: ${result.rejectionReason}`);
 * }
 * ```
 *
 * @example Tool calls
 * ```typescript
 * const result = await agent.run('What\'s the weather?', { tools: [...] });
 *
 * if (result.hasToolCalls && result.toolCalls) {
 *   for (const call of result.toolCalls) {
 *     console.log(`Tool: ${call.name}`);
 *     console.log(`Args: ${JSON.stringify(call.arguments)}`);
 *   }
 * }
 * ```
 */
export interface CascadeResult {
  // Core fields
  /** Generated response content */
  content: string;

  /** Name of model that produced final response */
  modelUsed: string;

  /** Total cost in USD */
  totalCost: number;

  /** Total latency in milliseconds */
  latencyMs: number;

  /** Detected complexity level */
  complexity: string;

  /** Whether cascade was used */
  cascaded: boolean;

  /** If cascaded, whether draft was accepted */
  draftAccepted: boolean;

  /** Routing strategy used ('direct' or 'cascade') */
  routingStrategy: string;

  /** Explanation for routing decision */
  reason: string;

  // Tool calling
  /** Tool calls made by model (if any) */
  toolCalls?: ToolCall[];

  /** Whether response includes tool calls */
  hasToolCalls: boolean;

  // Quality diagnostics
  /** Quality score from validator (0-1) */
  qualityScore?: number;

  /** Threshold used for validation */
  qualityThreshold?: number;

  /** Whether quality check passed */
  qualityCheckPassed?: boolean;

  /** Why draft was rejected (if applicable) */
  rejectionReason?: string;

  // Response tracking
  /** Full draft response text */
  draftResponse?: string;

  /** Full verifier response text */
  verifierResponse?: string;

  /** Length of final response */
  responseLength?: number;

  /** Word count of final response */
  responseWordCount?: number;

  // Timing breakdown
  /** Time to detect complexity */
  complexityDetectionMs?: number;

  /** Time to generate draft */
  draftGenerationMs?: number;

  /** Time for quality validation */
  qualityVerificationMs?: number;

  /** Time to generate verifier response */
  verifierGenerationMs?: number;

  /** Additional overhead from cascade system */
  cascadeOverheadMs?: number;

  // Cost breakdown
  /** Cost of draft generation */
  draftCost?: number;

  /** Cost of verifier generation */
  verifierCost?: number;

  /** Cost saved vs always using best model */
  costSaved?: number;

  /** Savings percentage */
  savingsPercentage?: number;

  // Model information
  /** Draft model name */
  draftModel?: string;

  /** Draft latency */
  draftLatencyMs?: number;

  /** Draft confidence score */
  draftConfidence?: number;

  /** Verifier model name */
  verifierModel?: string;

  /** Verifier latency */
  verifierLatencyMs?: number;

  /** Verifier confidence score */
  verifierConfidence?: number;

  // Additional metadata
  /** Custom metadata */
  metadata?: Record<string, any>;
}

/**
 * Convert CascadeResult to plain object
 */
export function resultToObject(result: CascadeResult): Record<string, any> {
  return {
    content: result.content,
    model_used: result.modelUsed,
    total_cost: result.totalCost,
    latency_ms: result.latencyMs,
    complexity: result.complexity,
    cascaded: result.cascaded,
    draft_accepted: result.draftAccepted,
    routing_strategy: result.routingStrategy,
    reason: result.reason,
    tool_calls: result.toolCalls,
    has_tool_calls: result.hasToolCalls,
    quality_score: result.qualityScore,
    quality_threshold: result.qualityThreshold,
    quality_check_passed: result.qualityCheckPassed,
    rejection_reason: result.rejectionReason,
    response_length: result.responseLength,
    response_word_count: result.responseWordCount,
    timing_breakdown: {
      complexity_detection_ms: result.complexityDetectionMs,
      draft_generation_ms: result.draftGenerationMs,
      quality_verification_ms: result.qualityVerificationMs,
      verifier_generation_ms: result.verifierGenerationMs,
      cascade_overhead_ms: result.cascadeOverheadMs,
    },
    cost_breakdown: {
      draft_cost: result.draftCost,
      verifier_cost: result.verifierCost,
      cost_saved: result.costSaved,
      savings_percentage: result.savingsPercentage,
    },
    metadata: result.metadata,
  };
}
