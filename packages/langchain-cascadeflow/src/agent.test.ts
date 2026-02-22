import { describe, it, expect } from 'vitest';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { AIMessage, BaseMessage, SystemMessage, ToolMessage } from '@langchain/core/messages';
import { ChatResult } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { CascadeAgent } from './agent.js';

class MockToolLoopModel extends BaseChatModel {
  loopForever: boolean;

  constructor(loopForever = false) {
    super({});
    this.loopForever = loopForever;
  }

  _llmType(): string {
    return 'mock-tool-loop';
  }

  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    const hasToolResult = messages.some((m) => m instanceof ToolMessage);

    if (this.loopForever || !hasToolResult) {
      return {
        generations: [
          {
            text: '',
            message: new AIMessage({
              content: '',
              tool_calls: [{ id: 'call_1', name: 'get_weather', args: { city: 'Berlin' } }],
            } as any),
          },
        ],
        llmOutput: {},
      };
    }

    return {
      generations: [{ text: 'Weather is sunny.', message: new AIMessage('Weather is sunny.') }],
      llmOutput: {},
    };
  }
}

class MockMultiToolLoopModel extends BaseChatModel {
  callCount = 0;
  firstCallMessages: BaseMessage[] = [];

  constructor() {
    super({});
  }

  _llmType(): string {
    return 'mock-multi-tool-loop';
  }

  async _generate(
    messages: BaseMessage[],
    _options: this['ParsedCallOptions'],
    _runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    this.callCount += 1;
    if (this.callCount === 1) {
      this.firstCallMessages = messages;
      return {
        generations: [
          {
            text: '',
            message: new AIMessage({
              content: '',
              tool_calls: [
                { id: 'call_weather', name: 'get_weather', args: { city: 'Berlin' } },
                { id: 'call_math', name: 'calculator', args: { expression: '25*4' } },
              ],
            } as any),
          },
        ],
        llmOutput: {},
      };
    }

    return {
      generations: [
        {
          text: 'It is sunny in Berlin and 25*4 equals 100.',
          message: new AIMessage('It is sunny in Berlin and 25*4 equals 100.'),
        },
      ],
      llmOutput: {},
    };
  }
}

describe('CascadeAgent', () => {
  it('completes a tool loop', async () => {
    const model = new MockToolLoopModel();
    const agent = new CascadeAgent({
      model,
      maxSteps: 4,
      toolHandlers: {
        get_weather: ({ city }) => `sunny in ${city}`,
      },
    });

    const result = await agent.run('What is the weather?');

    expect(result.status).toBe('completed');
    expect(result.steps).toBe(2);
    expect(result.message.content).toBe('Weather is sunny.');
    expect(result.messages.some((m) => m instanceof ToolMessage)).toBe(true);
  });

  it('stops at max steps for closed loop protection', async () => {
    const model = new MockToolLoopModel(true);
    const agent = new CascadeAgent({
      model,
      maxSteps: 2,
      toolHandlers: {
        get_weather: () => 'still sunny',
      },
    });

    const result = await agent.run([{ role: 'user', content: 'loop' }]);

    expect(result.status).toBe('max_steps_reached');
    expect(result.steps).toBe(2);
    expect(result.toolCalls.length).toBeGreaterThanOrEqual(2);
  });

  it('handles multi-tool calls in one step with message-list input and system prompt', async () => {
    const model = new MockMultiToolLoopModel();
    const agent = new CascadeAgent({
      model,
      maxSteps: 4,
      toolHandlers: {
        get_weather: ({ city }) => ({ city, weather: 'sunny' }),
        calculator: ({ expression }) => ({ expression, result: 100 }),
      },
    });

    const result = await agent.run(
      [{ role: 'user', content: 'Need weather and a quick calculation' }],
      { systemPrompt: 'You are a precise assistant.' }
    );

    expect(result.status).toBe('completed');
    expect(result.steps).toBe(2);
    expect(result.toolCalls.length).toBe(2);
    expect(result.messages.filter((m) => m instanceof ToolMessage).length).toBe(2);
    expect(result.message.content).toContain('sunny');
    expect(result.message.content).toContain('100');
    expect(model.firstCallMessages[0]).toBeInstanceOf(SystemMessage);
  });
});
