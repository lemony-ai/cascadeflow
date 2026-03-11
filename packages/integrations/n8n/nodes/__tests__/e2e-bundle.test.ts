import { describe, expect, it } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

import { AIMessage, HumanMessage } from '@langchain/core/messages';

import {
  QualityValidator,
  CASCADE_QUALITY_CONFIG,
  CostCalculator,
  ComplexityDetector,
  PreRouter,
  DomainRouter,
  ToolCascadeValidator,
  RoutingStrategy,
} from '@cascadeflow/core';

import { CascadeChatModel } from '../LmChatCascadeFlow/LmChatCascadeFlow.node';
import { CascadeFlowAgent, CascadeFlowAgentExecutor } from '../CascadeFlowAgent/CascadeFlowAgent.node';
import { LmChatCascadeFlow } from '../LmChatCascadeFlow/LmChatCascadeFlow.node';

const distDir = path.resolve(__dirname, '../../dist');

// ─────────────────────────────────────────────────
// 1. Bundle integrity
// ─────────────────────────────────────────────────
describe('Bundle integrity', () => {
  const lmChatBundle = path.join(distDir, 'nodes/LmChatCascadeFlow/LmChatCascadeFlow.node.js');
  const agentBundle = path.join(distDir, 'nodes/CascadeFlowAgent/CascadeFlowAgent.node.js');

  it('dist/ files exist', () => {
    expect(fs.existsSync(lmChatBundle)).toBe(true);
    expect(fs.existsSync(agentBundle)).toBe(true);
  });

  it('bundles contain no require("@cascadeflow/…") calls', () => {
    const lmChatCode = fs.readFileSync(lmChatBundle, 'utf-8');
    const agentCode = fs.readFileSync(agentBundle, 'utf-8');

    // Match require("@cascadeflow/core") or require('@cascadeflow/core') etc.
    // @cascadeflow/ml is expected (dynamic import, external) — exclude it
    const cascadeflowRequire = /require\(["']@cascadeflow\/(?!ml\b)[^"']+["']\)/g;

    expect(lmChatCode.match(cascadeflowRequire)).toBeNull();
    expect(agentCode.match(cascadeflowRequire)).toBeNull();
  });

  it('LmChatCascadeFlow bundle exports expected classes', () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require(lmChatBundle);
    expect(mod.LmChatCascadeFlow).toBeDefined();
    expect(mod.CascadeChatModel).toBeDefined();
  });

  it('CascadeFlowAgent bundle exports expected classes', () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require(agentBundle);
    expect(mod.CascadeFlowAgent).toBeDefined();
    expect(mod.CascadeFlowAgentExecutor).toBeDefined();
  });
});

// ─────────────────────────────────────────────────
// 2. Cascadeflow intelligence is active
// ─────────────────────────────────────────────────
describe('Cascadeflow intelligence is active', () => {
  it('QualityValidator validates a good response', async () => {
    const validator = new QualityValidator({
      ...CASCADE_QUALITY_CONFIG,
      minConfidence: 0.4,
      useSemanticValidation: false,
    });

    const result = await validator.validate(
      'The capital of France is Paris, which is located in the north-central part of the country along the Seine river.',
      'What is the capital of France?',
    );

    expect(result).toHaveProperty('passed');
    expect(result).toHaveProperty('confidence');
    expect(result).toHaveProperty('score');
    expect(typeof result.passed).toBe('boolean');
    expect(result.confidence).toBeGreaterThan(0);
    expect(result.score).toBeGreaterThan(0);
  });

  it('ComplexityDetector detects simple queries as low complexity', () => {
    const detector = new ComplexityDetector();
    const result = detector.detect('What is 2+2?');

    expect(result).toHaveProperty('complexity');
    expect(result).toHaveProperty('confidence');
    expect(['trivial', 'simple']).toContain(result.complexity);
    expect(result.confidence).toBeGreaterThan(0);
  });

  it('DomainRouter detects code domain for programming queries', () => {
    const router = new DomainRouter();
    const result = router.detect('Write a Python function to sort a list');

    expect(result).toHaveProperty('domain');
    expect(result.domain).toBe('code');
  });

  it('CostCalculator returns a positive cost estimate', () => {
    const calc = new CostCalculator();
    expect(CostCalculator.estimateTokens('Hello world, this is a test sentence.')).toBeGreaterThan(0);
  });

  it('PreRouter routes trivial queries to cascade', async () => {
    const router = new PreRouter();
    const decision = await router.route('What is 2+2?');

    expect(decision).toHaveProperty('strategy');
    expect(decision).toHaveProperty('reason');
    expect(decision).toHaveProperty('confidence');
    expect(decision.strategy).toBe(RoutingStrategy.CASCADE);
  });

  it('PreRouter routes expert queries to direct_best', async () => {
    const router = new PreRouter();
    const decision = await router.route(
      'Prove the Riemann Hypothesis and explain the implications for the distribution of prime numbers in analytic number theory',
    );

    expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
    expect(decision.confidence).toBeGreaterThan(0);
  });

  it('ToolCascadeValidator validates a well-formed tool call', () => {
    const validator = new ToolCascadeValidator();

    const toolCalls = [{
      id: 'call_1',
      type: 'function' as const,
      function: {
        name: 'get_weather',
        arguments: JSON.stringify({ location: 'Paris' }),
      },
    }];

    const tools = [{
      type: 'function' as const,
      function: {
        name: 'get_weather',
        description: 'Get current weather for a location',
        parameters: {
          type: 'object',
          properties: { location: { type: 'string' } },
          required: ['location'],
        },
      },
    }];

    const result = validator.validate(toolCalls, tools);

    expect(result).toHaveProperty('valid');
    expect(result).toHaveProperty('score');
    expect(result.valid).toBe(true);
    expect(result.score).toBeGreaterThan(0);
  });

  it('CascadeChatModel constructor initializes intelligence classes', () => {
    const model = new CascadeChatModel(
      async () => ({ invoke: async () => new AIMessage('draft') } as any),
      async () => ({ invoke: async () => new AIMessage('verify') } as any),
      0.7,   // qualityThreshold
      false,  // useSemanticValidation (skip @cascadeflow/ml)
      true,   // useAlignmentScoring
      true,   // useComplexityRouting
      true,   // useComplexityThresholds
    );

    // The constructor initializes these when the core classes are available.
    // Access the private fields via casting to verify they are not null.
    const internal = model as any;
    expect(internal.qualityValidator).not.toBeNull();
    expect(internal.complexityDetector).not.toBeNull();
    expect(internal.preRouter).not.toBeNull();
    expect(internal.costCalculator).not.toBeNull();
  });
});

// ─────────────────────────────────────────────────
// 3. End-to-end cascade flow
// ─────────────────────────────────────────────────
describe('End-to-end cascade flow', () => {
  /** Helper: build mock LLM returning a fixed response with token metadata */
  function mockLLM(content: string) {
    return {
      invoke: async () => {
        const msg = new AIMessage(content);
        (msg as any).response_metadata = {
          tokenUsage: { promptTokens: 10, completionTokens: 20 },
        };
        return msg;
      },
      _llmType: () => 'mock',
      modelName: 'mock-model',
    } as any;
  }

  it('escalates to verifier when drafter quality is low', async () => {
    const drafterResponse = 'ok'; // Very short → low quality
    const verifierResponse =
      'The answer to your question is that the capital of France is Paris, a beautiful city known for its culture and history.';

    const model = new CascadeChatModel(
      async () => mockLLM(drafterResponse),
      async () => mockLLM(verifierResponse),
      0.9,    // high threshold — forces escalation
      false,  // no semantic validation
      true,   // alignment scoring
      false,  // no complexity routing (keep it simple)
      false,  // no complexity thresholds
    );

    const result = await model._generate(
      [new HumanMessage('What is the capital of France?')],
      {} as any,
    );

    expect(result.generations).toHaveLength(1);
    expect(result.generations[0].text).toBe(verifierResponse);

    const metadata = (result.generations[0].message as any).response_metadata?.cascadeflow;
    expect(metadata).toBeDefined();
    expect(metadata.flow).toBe('escalated_to_verifier');
  });

  it('accepts drafter when quality is high enough', async () => {
    const drafterResponse =
      'Paris is the capital and largest city of France. It is situated on the River Seine in northern France and has a rich cultural heritage spanning centuries.';

    const model = new CascadeChatModel(
      async () => mockLLM(drafterResponse),
      async () => mockLLM('verifier should not be called'),
      0.3,    // low threshold — drafter should pass
      false,  // no semantic validation
      false,  // no alignment scoring
      false,  // no complexity routing
      false,  // no complexity thresholds
    );

    const result = await model._generate(
      [new HumanMessage('What is the capital of France?')],
      {} as any,
    );

    expect(result.generations).toHaveLength(1);
    expect(result.generations[0].text).toBe(drafterResponse);

    const metadata = (result.generations[0].message as any).response_metadata?.cascadeflow;
    expect(metadata).toBeDefined();
    expect(metadata.flow).toBe('drafter_accepted');
  });

  it('routes complex queries directly to verifier when complexity routing is enabled', async () => {
    const verifierResponse =
      'A comprehensive proof of the Riemann Hypothesis involves deep analysis of the zeta function zeros and their distribution on the critical strip.';

    const model = new CascadeChatModel(
      async () => mockLLM('drafter should not be called'),
      async () => mockLLM(verifierResponse),
      0.7,
      false,  // no semantic validation
      true,   // alignment scoring
      true,   // useComplexityRouting — enables direct verifier for hard/expert
      true,   // useComplexityThresholds
    );

    const result = await model._generate(
      [new HumanMessage(
        'Prove the Riemann Hypothesis and explain the implications for the distribution of prime numbers in analytic number theory',
      )],
      {} as any,
    );

    expect(result.generations).toHaveLength(1);
    expect(result.generations[0].text).toBe(verifierResponse);

    const metadata = (result.generations[0].message as any).response_metadata?.cascadeflow;
    expect(metadata).toBeDefined();
    expect(metadata.flow).toBe('direct_verifier');
    expect(metadata.router).toBe('pre-router');
  });
});
