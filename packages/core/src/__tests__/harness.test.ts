import { afterEach, describe, expect, it } from 'vitest';

import {
  BudgetExceededError,
  cascadeflow,
  getCurrentRun,
  getHarnessConfig,
  init,
  reset,
  run,
} from '../harness';
import {
  __resetInstrumentationLoadersForTest,
  __resetInstrumentationStateForTest,
  __setInstrumentationLoadersForTest,
  isAnthropicPatched,
  isOpenAIPatched,
} from '../harness-instrument';

class FakeOpenAICompletions {
  constructor(private readonly calls: Array<Record<string, any>>) {}

  create(request: Record<string, any>): Promise<Record<string, any>> {
    this.calls.push({ ...request });
    return Promise.resolve({
      usage: {
        prompt_tokens: 100,
        completion_tokens: 25,
      },
      choices: [
        {
          message: {
            tool_calls: [{ id: 'tool_1', type: 'function' }],
          },
        },
      ],
    });
  }
}

class FakeAnthropicMessages {
  constructor(private readonly calls: Array<Record<string, any>>) {}

  create(request: Record<string, any>): Promise<Record<string, any>> {
    this.calls.push({ ...request });
    return Promise.resolve({
      usage: {
        input_tokens: 120,
        output_tokens: 40,
      },
      content: [
        { type: 'text', text: 'hello' },
        { type: 'tool_use', id: 'tool_1', name: 'search', input: { q: 'x' } },
      ],
    });
  }
}

afterEach(() => {
  reset();
  __resetInstrumentationStateForTest();
  __resetInstrumentationLoadersForTest();
});

describe('harness API (TypeScript parity)', () => {
  it('exposes cascadeflow init/run object API', async () => {
    expect(typeof cascadeflow.init).toBe('function');
    expect(typeof cascadeflow.run).toBe('function');

    init({ mode: 'observe' });
    const value = await cascadeflow.run(async (scope) => {
      expect(scope.mode).toBe('observe');
      expect(getCurrentRun()).toBe(scope);
      return 42;
    });

    expect(value).toBe(42);
    expect(getCurrentRun()).toBeNull();
  });

  it('honors code > env precedence and preserves nested scope isolation', async () => {
    const previousMode = process.env.CASCADEFLOW_HARNESS_MODE;
    process.env.CASCADEFLOW_HARNESS_MODE = 'observe';

    init();
    expect(getHarnessConfig().mode).toBe('observe');

    init({ mode: 'enforce' });
    expect(getHarnessConfig().mode).toBe('enforce');

    await run({ budget: 1.0 }, async (outer) => {
      outer.cost = 0.1;
      expect(outer.budgetMax).toBe(1.0);
      expect(getCurrentRun()).toBe(outer);

      await run({ budget: 0.25 }, async (inner) => {
        expect(getCurrentRun()).toBe(inner);
        expect(inner.budgetMax).toBe(0.25);
        inner.cost = 0.2;
      });

      expect(getCurrentRun()).toBe(outer);
      expect(outer.budgetMax).toBe(1.0);
      expect(outer.cost).toBe(0.1);
    });

    if (previousMode == null) {
      delete process.env.CASCADEFLOW_HARNESS_MODE;
    } else {
      process.env.CASCADEFLOW_HARNESS_MODE = previousMode;
    }
  });

  it('auto-instruments OpenAI and enforces switch_model decisions', async () => {
    const openaiCalls: Array<Record<string, any>> = [];

    __setInstrumentationLoadersForTest({
      openai: () => ({
        Completions: FakeOpenAICompletions,
      }),
      anthropic: () => null,
    });

    init({ mode: 'enforce' });
    expect(isOpenAIPatched()).toBe(true);

    await run({ kpiWeights: { cost: 1 } }, async (scope) => {
      const client = new FakeOpenAICompletions(openaiCalls);
      await client.create({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'hi' }],
      });

      expect(scope.stepCount).toBe(1);
      expect(scope.cost).toBeGreaterThan(0);
      expect(scope.toolCalls).toBe(1);

      const trace = scope.trace();
      expect(trace).toHaveLength(1);
      expect(trace[0]?.action).toBe('switch_model');
      expect(trace[0]?.applied).toBe(true);
      expect(trace[0]?.decisionMode).toBe('enforce');
    });

    expect(openaiCalls).toHaveLength(1);
    expect(openaiCalls[0]?.model).not.toBe('gpt-4o');
  });

  it('observe mode logs non-allow decisions without mutating request', async () => {
    const openaiCalls: Array<Record<string, any>> = [];

    __setInstrumentationLoadersForTest({
      openai: () => ({
        Completions: FakeOpenAICompletions,
      }),
      anthropic: () => null,
    });

    init({ mode: 'observe' });

    await run({ kpiWeights: { cost: 1 } }, async (scope) => {
      const client = new FakeOpenAICompletions(openaiCalls);
      await client.create({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'hi' }],
      });

      const trace = scope.trace();
      expect(trace).toHaveLength(1);
      expect(trace[0]?.action).toBe('switch_model');
      expect(trace[0]?.applied).toBe(false);
      expect(trace[0]?.decisionMode).toBe('observe');
    });

    expect(openaiCalls).toHaveLength(1);
    expect(openaiCalls[0]?.model).toBe('gpt-4o');
  });

  it('enforce mode stops calls when budget is exhausted', async () => {
    const openaiCalls: Array<Record<string, any>> = [];

    __setInstrumentationLoadersForTest({
      openai: () => ({
        Completions: FakeOpenAICompletions,
      }),
      anthropic: () => null,
    });

    init({ mode: 'enforce' });

    await expect(
      run({ budget: 0 }, async () => {
        const client = new FakeOpenAICompletions(openaiCalls);
        await client.create({
          model: 'gpt-4o',
          messages: [{ role: 'user', content: 'hi' }],
        });
      }),
    ).rejects.toBeInstanceOf(BudgetExceededError);

    expect(openaiCalls).toHaveLength(0);
  });

  it('auto-instruments Anthropic and tracks usage/tool calls', async () => {
    const anthropicCalls: Array<Record<string, any>> = [];

    __setInstrumentationLoadersForTest({
      openai: () => null,
      anthropic: () => ({
        Messages: FakeAnthropicMessages,
      }),
    });

    init({ mode: 'enforce' });
    expect(isAnthropicPatched()).toBe(true);

    await run(async (scope) => {
      const client = new FakeAnthropicMessages(anthropicCalls);
      await client.create({
        model: 'claude-sonnet-4-5-20250929',
        messages: [{ role: 'user', content: 'hello' }],
      });

      expect(scope.stepCount).toBe(1);
      expect(scope.toolCalls).toBe(1);
      expect(scope.cost).toBeGreaterThan(0);
      expect(scope.trace()[0]?.action).toBe('allow');
    });

    expect(anthropicCalls).toHaveLength(1);
  });
});
